"""
intraday_tracker — 5分足による指値タッチ約定シミュレーション。

既存の signal_tracker は「シグナル翌日の始値で成行エントリー・日足のH/Lで判定」という
粗い前提で戦績を記録している。本モジュールはその前提を実運用に近づけたもの:

  - エントリー: signal_log.entry_price（= シグナル日の終値）に **買い指値** を置き、
    5分足で価格がそこまで押してきた瞬間に約定したとみなす。
    FILL_WINDOW_DAYS 営業日以内にタッチしなければ 'no_fill'（見送り）。
  - 出口: SL / TP1 / ターゲットも5分足でタッチした瞬間に決済。
    TP1 到達で半分利確 → 残りのストップを建値へ。MAX_HOLD_DAYS 営業日でタイムアウト。
  - 同一5分足内で SL と TP の両方に触れた場合の順序は判定不能なため、日足評価器と同じく
    保守的に SL 優先とする（5分足では発生頻度が大幅に下がる）。
  - ギャップ: 寄りがSLを飛び越えた日は「SL価格」ではなく「寄り値」で約定させる。
    したがって負けは -1R を超えうる（日足評価器は -1.0R 固定で負けを過小評価している）。
    ターゲット/TP1 を飛び越えた場合も同様に寄り値（有利側）で計上する。
  - 指値がSLより下でしか約定しない（＝寄りがSLを割った）場合は 'gap_void'。
    サポート割れでセットアップ自体が消滅しており、実質ノートレード（±0R）とみなす。
    勝率の分母からは外すが、件数は必ず表示する（黙って捨てない）。

fill_mode:
  - 'limit' : 上記の指値タッチ方式（本命）
  - 'open'  : 翌日始値で成行（既存 signal_tracker と同じ入口 / 出口だけ5分足）
              → 指値ルールが効いているのかを切り分けるための対照群。

データ源は yfinance の5分足（無料・直近60日のみ）。したがって過去60日より前の
シグナルは評価できない。
"""
from __future__ import annotations

import warnings
from datetime import date, timedelta
from typing import Optional

from backend.db import db_cursor, get_connection

warnings.filterwarnings("ignore")

INTERVAL          = "5m"
LOOKBACK_PERIOD   = "60d"   # yfinance の5分足は直近60日まで
FILL_WINDOW_DAYS  = 5       # 指値が有効な営業日数（次のスキャンまで）
MAX_HOLD_DAYS     = 30      # 保有上限（日足評価器と同一）
PRICE_SANITY_PCT  = 8.0     # シグナル日終値と5分足終値の乖離許容（株式分割・データ不整合の検出）
CHUNK             = 40      # yfinance 一括DLのチャンクサイズ

FILL_MODES = ("limit", "open")


# ────────────────────────────────────────────────────────────────────
# Data
# ────────────────────────────────────────────────────────────────────

def fetch_5m_bars(tickers: list[str]) -> dict[str, list[dict]]:
    """yfinance から5分足を取得し、{ticker: [bar, ...]} で返す（日時昇順）。
    bar = {dt: ISO8601(ET), date: 'YYYY-MM-DD', open, high, low, close}
    """
    import yfinance as yf

    out: dict[str, list[dict]] = {}
    uniq = sorted(set(tickers))

    for i in range(0, len(uniq), CHUNK):
        chunk = uniq[i:i + CHUNK]
        try:
            df = yf.download(chunk, interval=INTERVAL, period=LOOKBACK_PERIOD,
                             group_by="ticker", auto_adjust=False,
                             progress=False, threads=True)
        except Exception as e:
            print(f"[intraday] download error chunk {i}: {e}")
            continue
        if df is None or df.empty:
            continue

        df = df.tz_convert("America/New_York")

        for t in chunk:
            try:
                sub = df[t] if len(chunk) > 1 else df
            except KeyError:
                continue
            sub = sub.dropna(subset=["Open", "High", "Low", "Close"])
            if sub.empty:
                continue
            bars = []
            for ts, row in sub.iterrows():
                bars.append({
                    "dt":    ts.isoformat(),
                    "date":  ts.strftime("%Y-%m-%d"),
                    "open":  float(row["Open"]),
                    "high":  float(row["High"]),
                    "low":   float(row["Low"]),
                    "close": float(row["Close"]),
                })
            out[t] = bars
        print(f"[intraday] fetched {i + len(chunk)}/{len(uniq)} tickers")

    return out


def load_signals(since_days: int = 55) -> list[dict]:
    """5分足でカバーできる範囲のシグナルを signal_log から読む。"""
    cutoff = (date.today() - timedelta(days=since_days)).isoformat()
    with db_cursor() as cur:
        cur.execute("""
            SELECT id, logic_name, ticker, signal_date, direction,
                   entry_price, stop_price, tp1_price, target_price, confidence, meta
            FROM signal_log
            WHERE signal_date >= ? AND direction = 'LONG'
            ORDER BY signal_date ASC, id ASC
        """, (cutoff,))
        rows = [dict(r) for r in cur.fetchall()]

    for r in rows:
        r["verdict"] = _verdict_of(r.pop("meta", None))
    return rows


def _verdict_of(meta) -> Optional[str]:
    """meta から verdict（最優先候補 / サポート接近中 / ウォッチ…）を取り出す。"""
    if isinstance(meta, str):
        import json
        try:
            meta = json.loads(meta)
        except (TypeError, ValueError):
            return None
    if isinstance(meta, dict):
        v = meta.get("verdict")
        return str(v) if v else None
    return None


# ────────────────────────────────────────────────────────────────────
# Simulation
# ────────────────────────────────────────────────────────────────────

def simulate(sig: dict, bars: list[dict], fill_mode: str) -> Optional[dict]:
    """1シグナルを5分足でシミュレートする。データ待ちなら None。

    Returns: dict(status, fill_price, fill_at, exit_price, exit_at, exit_reason,
                  realized_r, mtm_r, hit_tp1, bars_held, days_held, mae_pct, mfe_pct)
    """
    entry_plan = _f(sig["entry_price"])
    stop_plan  = _f(sig["stop_price"])
    tp1_plan   = _f(sig["tp1_price"])
    target     = _f(sig["target_price"])
    if entry_plan is None or stop_plan is None or target is None:
        return _invalid("価格欠損")
    if stop_plan >= entry_plan:
        return _invalid("SL >= エントリー")

    sig_date = str(sig["signal_date"])

    # 株式分割・データ不整合の検出: シグナル日の5分足終値と entry_price(日足終値) を突き合わせる
    same_day = [b for b in bars if b["date"] == sig_date]
    if same_day:
        gap = abs(same_day[-1]["close"] - entry_plan) / entry_plan * 100
        if gap > PRICE_SANITY_PCT:
            return _invalid(f"5分足と日足終値が {gap:.0f}% 乖離（分割等）")

    after = [b for b in bars if b["date"] > sig_date]
    if not after:
        return None  # 翌日以降のデータがまだ無い

    dates = sorted({b["date"] for b in after})

    # ── 約定 ────────────────────────────────────────────────
    if fill_mode == "open":
        fill_idx   = 0
        fill_price = after[0]["open"]
    else:
        window = set(dates[:FILL_WINDOW_DAYS])
        fill_idx = None
        fill_price = None
        for i, b in enumerate(after):
            if b["date"] not in window:
                break
            if b["low"] <= entry_plan:
                # 指値より下で寄り付いた場合は寄り値で約定（有利側）
                fill_price = min(b["open"], entry_plan)
                fill_idx = i
                break
        if fill_idx is None:
            if len(dates) >= FILL_WINDOW_DAYS:
                return {"status": "no_fill", "exit_reason": "指値にタッチせず見送り",
                        "fill_price": None, "fill_at": None, "exit_price": None,
                        "exit_at": None, "realized_r": None, "mtm_r": None,
                        "hit_tp1": False, "bars_held": 0, "days_held": 0,
                        "mae_pct": None, "mfe_pct": None}
            return None  # まだ指値待ちの営業日が残っている

    risk = fill_price - stop_plan
    if risk <= 0:
        # 寄りがSLを割って約定した = サポート崩壊でセットアップ消滅。
        # 現実には約定と同時にストップが発動して同値近辺で撤退する（実質ノートレード）。
        return {"status": "gap_void",
                "exit_reason": "寄りがSLを割って約定（セットアップ消滅・実質ノートレード）",
                "fill_price": round(fill_price, 4), "fill_at": after[fill_idx]["dt"],
                "exit_price": round(fill_price, 4), "exit_at": after[fill_idx]["dt"],
                "realized_r": 0.0, "mtm_r": None, "hit_tp1": False,
                "bars_held": 1, "days_held": 1, "mae_pct": None, "mfe_pct": None}

    target_r = (target - fill_price) / risk

    # ── 出口 ────────────────────────────────────────────────
    hold_bars  = after[fill_idx:]
    hold_dates = sorted({b["date"] for b in hold_bars})
    active     = set(hold_dates[:MAX_HOLD_DAYS])

    cur_stop = stop_plan
    hit_tp1  = False
    tp1_r    = None          # TP1 の実約定R（ギャップで飛び越えたら 1.5R より大きくなる）
    mae = mfe = 0.0
    n_bars = 0
    last_bar = hold_bars[0]

    for b in hold_bars:
        if b["date"] not in active:
            break
        n_bars += 1
        last_bar = b

        mae = min(mae, (b["low"]  - fill_price) / fill_price * 100)
        mfe = max(mfe, (b["high"] - fill_price) / fill_price * 100)

        # 同一5分足内の順序は判定不能 → 保守的にSL優先
        if b["low"] <= cur_stop:
            # ギャップでSLを飛び越えた場合は寄り値で約定（負けが -1R を超える）
            exit_px = min(cur_stop, b["open"])
            exit_r  = (exit_px - fill_price) / risk
            if hit_tp1:
                return _closed("tp1_hit_be", "TP1半決済後に建値ストップ", b, exit_px,
                               0.5 * tp1_r + 0.5 * exit_r, True,
                               n_bars, hold_dates, active, mae, mfe, fill_price, fill_idx, after)
            return _closed("stopped", "損切り", b, exit_px, exit_r, False,
                           n_bars, hold_dates, active, mae, mfe, fill_price, fill_idx, after)

        if b["high"] >= target:
            # ギャップでターゲットを飛び越えたら寄り値（有利側）
            exit_px = max(target, b["open"])
            exit_r  = (exit_px - fill_price) / risk
            if hit_tp1:
                r = 0.5 * tp1_r + 0.5 * exit_r
            else:
                # TP1 を経由せず一気にターゲット到達 → 全量を exit_r で計上
                r = exit_r
            return _closed("tp2_hit", "ターゲット到達", b, exit_px, r, True,
                           n_bars, hold_dates, active, mae, mfe, fill_price, fill_idx, after)

        if tp1_plan is not None and not hit_tp1 and b["high"] >= tp1_plan:
            hit_tp1  = True
            tp1_fill = max(tp1_plan, b["open"])       # ギャップアップなら寄り値で半分利確
            tp1_r    = (tp1_fill - fill_price) / risk
            cur_stop = fill_price                     # 残りは建値ストップへ

    # ── タイムアウト or 継続中 ──────────────────────────────
    days_held = len({b["date"] for b in hold_bars[:n_bars]})
    if len(hold_dates) > MAX_HOLD_DAYS:
        close_r = (last_bar["close"] - fill_price) / risk
        r = (0.5 * tp1_r + 0.5 * close_r) if hit_tp1 else close_r
        return _closed("time_exit", f"{MAX_HOLD_DAYS}営業日でタイムアウト", last_bar,
                       last_bar["close"], r, hit_tp1, n_bars, hold_dates, active,
                       mae, mfe, fill_price, fill_idx, after)

    # 継続中 → 含み評価（時価）
    cur_r = (last_bar["close"] - fill_price) / risk
    mtm_r = (0.5 * tp1_r + 0.5 * cur_r) if hit_tp1 else cur_r
    return {"status": "open", "exit_reason": None,
            "fill_price": round(fill_price, 4), "fill_at": after[fill_idx]["dt"],
            "exit_price": None, "exit_at": None,
            "realized_r": None, "mtm_r": round(mtm_r, 4),
            "hit_tp1": hit_tp1, "bars_held": n_bars, "days_held": days_held,
            "mae_pct": round(mae, 2), "mfe_pct": round(mfe, 2)}


def _closed(status, reason, bar, exit_price, r, hit_tp1, n_bars, hold_dates,
            active, mae, mfe, fill_price, fill_idx, after) -> dict:
    days_held = len({b["date"] for b in after[fill_idx:fill_idx + n_bars]})
    return {"status": status, "exit_reason": reason,
            "fill_price": round(fill_price, 4), "fill_at": after[fill_idx]["dt"],
            "exit_price": round(float(exit_price), 4), "exit_at": bar["dt"],
            "realized_r": round(float(r), 4), "mtm_r": None,
            "hit_tp1": bool(hit_tp1), "bars_held": n_bars, "days_held": days_held,
            "mae_pct": round(mae, 2), "mfe_pct": round(mfe, 2)}


def _invalid(reason: str) -> dict:
    return {"status": "invalid", "exit_reason": reason,
            "fill_price": None, "fill_at": None, "exit_price": None, "exit_at": None,
            "realized_r": None, "mtm_r": None, "hit_tp1": False,
            "bars_held": 0, "days_held": 0, "mae_pct": None, "mfe_pct": None}


def _f(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


# ────────────────────────────────────────────────────────────────────
# Rebuild（冪等・全再計算）
# ────────────────────────────────────────────────────────────────────

def rebuild(since_days: int = 55, fill_modes: tuple = FILL_MODES,
            bars_by_ticker: Optional[dict] = None) -> dict:
    """対象シグナルを5分足で全件シミュレートし、signal_log_intraday を作り直す。

    5分足は直近60日のローリングウィンドウなので差分更新は状態がずれやすい。
    毎回まるごと再計算する（冪等）。
    bars_by_ticker を渡すと再取得をスキップする（検証・再計算用）。
    """
    sigs = load_signals(since_days=since_days)
    if not sigs:
        print("[intraday] 対象シグナルなし")
        return {"signals": 0}

    tickers = sorted({s["ticker"] for s in sigs})
    if bars_by_ticker is None:
        print(f"[intraday] signals={len(sigs)} tickers={len(tickers)} 5分足を取得中…")
        bars_by_ticker = fetch_5m_bars(tickers)
    print(f"[intraday] 5分足: {len(bars_by_ticker)}/{len(tickers)} 銘柄")

    rows = []
    stats: dict = {m: {} for m in fill_modes}
    pending = 0
    no_bars = 0

    for s in sigs:
        bars = bars_by_ticker.get(s["ticker"])
        if not bars:
            no_bars += 1
            continue
        for mode in fill_modes:
            res = simulate(s, bars, mode)
            if res is None:
                pending += 1
                continue
            rows.append((
                s["id"], s["logic_name"], s["ticker"], str(s["signal_date"]),
                mode, s["direction"], res["status"],
                _f(s["entry_price"]), res["fill_price"], res["fill_at"],
                _f(s["stop_price"]), _f(s["tp1_price"]), _f(s["target_price"]),
                res["exit_price"], res["exit_at"], res["exit_reason"],
                res["realized_r"], res["mtm_r"], res["hit_tp1"],
                res["bars_held"], res["days_held"], res["mae_pct"], res["mfe_pct"],
                _f(s["confidence"]), s.get("verdict"),
            ))
            st = stats[mode]
            st[res["status"]] = st.get(res["status"], 0) + 1

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM signal_log_intraday")
        cur.executemany("""
            INSERT INTO signal_log_intraday
                (signal_id, logic_name, ticker, signal_date, fill_mode, direction, status,
                 entry_plan, fill_price, fill_at, stop_price, tp1_price, target_price,
                 exit_price, exit_at, exit_reason, realized_r, mtm_r, hit_tp1,
                 bars_held, days_held, mae_pct, mfe_pct, confidence, verdict)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    out = {"signals": len(sigs), "rows": len(rows), "pending": pending,
           "no_bars": no_bars, "by_mode": stats}
    print(f"[intraday] {out}")
    return out


# ────────────────────────────────────────────────────────────────────
# Stats
# ────────────────────────────────────────────────────────────────────

def get_intraday_stats(fill_mode: str = "limit",
                        since_days: Optional[int] = None,
                        verdict: Optional[str] = None) -> dict:
    """ロジック別の勝率・期待値を集計する。

    勝率は「約定して決済まで終わったトレードのうち勝ったもの」の比率。
    no_fill / gap_void / invalid は分母から除き、件数だけ別途返す。
    verdict を渡すとその判定（例: '最優先候補'）に絞る。
    """
    where = ["fill_mode = ?"]
    params: list = [fill_mode]
    if since_days is not None:
        where.append("signal_date >= ?")
        params.append((date.today() - timedelta(days=since_days)).isoformat())
    if verdict:
        where.append("verdict = ?")
        params.append(verdict)

    with db_cursor() as cur:
        cur.execute(f"""
            SELECT logic_name, ticker, signal_date, status, realized_r, mtm_r,
                   days_held, hit_tp1, mae_pct, mfe_pct, verdict
            FROM signal_log_intraday
            WHERE {' AND '.join(where)}
            ORDER BY signal_date ASC, id ASC
        """, tuple(params))
        rows = [dict(r) for r in cur.fetchall()]

    by_logic: dict[str, list] = {}
    by_verdict: dict[str, list] = {}
    for r in rows:
        by_logic.setdefault(r["logic_name"], []).append(r)
        key = f"{r['logic_name']} / {r['verdict'] or '—'}"
        by_verdict.setdefault(key, []).append(r)

    return {
        "fill_mode":  fill_mode,
        "verdict":    verdict,
        "total":      len(rows),
        "summary":    _agg(rows),
        "by_logic":   {ln: _agg(rs) for ln, rs in sorted(by_logic.items())},
        "by_verdict": {k: _agg(rs) for k, rs in sorted(by_verdict.items())},
    }


def _agg(rows: list[dict]) -> dict:
    n_all    = len(rows)
    no_fill  = [r for r in rows if r["status"] == "no_fill"]
    invalid  = [r for r in rows if r["status"] == "invalid"]
    gap_void = [r for r in rows if r["status"] == "gap_void"]
    opens    = [r for r in rows if r["status"] == "open"]
    closed   = [r for r in rows if r["status"] in ("stopped", "tp1_hit_be", "tp2_hit", "time_exit")]

    rs = [float(r["realized_r"]) for r in closed if r["realized_r"] is not None]
    wins   = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    n = len(rs)

    total_r  = sum(rs)
    win_sum  = sum(wins)
    loss_sum = abs(sum(losses))
    pf = (win_sum / loss_sum) if loss_sum > 0 else None

    equity, cum, peak, max_dd = [], 0.0, float("-inf"), 0.0
    for r in rs:
        cum += r
        equity.append(cum)
        peak = max(peak, cum)
        max_dd = max(max_dd, peak - cum)

    mtm = [float(r["mtm_r"]) for r in opens if r["mtm_r"] is not None]

    # 約定機会 = no_fill + 約定した全部（データ不良の invalid は分母外）
    fillable = n_all - len(invalid)
    filled   = len(opens) + len(closed)

    return {
        "signals":        n_all,
        "invalid":        len(invalid),
        "no_fill":        len(no_fill),
        "gap_void":       len(gap_void),
        "filled":         filled,
        "fill_rate":      round(filled / fillable * 100, 1) if fillable else None,
        "open":           len(opens),
        "closed":         n,
        "win_rate":       round(len(wins) / n * 100, 1) if n else None,
        "expectancy_r":   round(total_r / n, 3) if n else None,
        "avg_win_r":      round(win_sum / len(wins), 3) if wins else None,
        "avg_loss_r":     round(sum(losses) / len(losses), 3) if losses else None,
        "profit_factor":  round(pf, 2) if pf is not None else None,
        "total_r":        round(total_r, 2),
        "max_dd_r":       round(max_dd, 2),
        "open_mtm_r":     round(sum(mtm), 2) if mtm else 0.0,
        "combined_r":     round(total_r + sum(mtm), 2),
        # 決済済みだけの期待値は「負けは数日で確定・勝ちは建値ストップのまま open に残る」ため
        # 構造的に悲観へ偏る。含み評価を足した1トレードあたりRが最もフェアな比較軸。
        "combined_r_per_fill": round((total_r + sum(mtm)) / filled, 3) if filled else None,
        "avg_days_held":  round(sum(r["days_held"] or 0 for r in closed) / n, 1) if n else None,
        "tp1_rate":       round(sum(1 for r in closed if r["hit_tp1"]) / n * 100, 1) if n else None,
        "breakdown":      {
            "stopped":    sum(1 for r in closed if r["status"] == "stopped"),
            "tp1_hit_be": sum(1 for r in closed if r["status"] == "tp1_hit_be"),
            "tp2_hit":    sum(1 for r in closed if r["status"] == "tp2_hit"),
            "time_exit":  sum(1 for r in closed if r["status"] == "time_exit"),
        },
        "equity_curve":   [{"signal_date": str(closed[i]["signal_date"]),
                            "ticker": closed[i]["ticker"],
                            "cum_r": round(equity[i], 2)} for i in range(n)],
    }


if __name__ == "__main__":
    rebuild()
