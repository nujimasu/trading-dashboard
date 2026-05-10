"""
signal_tracker — シグナル記録・評価・統計サービス。

Forward tracking:
  - パイプラインが pick を生成した直後に log_signals() を呼び、signal_log に記録。
  - 同じ (logic_name, ticker, signal_date) の重複は黙ってスキップ。

Outcome evaluator:
  - evaluate_open_signals() を毎晩のcronで呼ぶ。
  - 'open' なシグナルについて、シグナル日以降の price_data を順に見て status を確定。
  - 翌日始値エントリー、TP1で半決済+残りトレール(BE)、30営業日でタイムアウト。

Stats:
  - get_logic_stats() で各ロジックの勝率・期待値・最大DD・PF を集計。
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Optional

from backend.db import db_cursor

DEFAULT_MAX_HOLDING_DAYS = 30


# ────────────────────────────────────────────────────────────────────
# Logging
# ────────────────────────────────────────────────────────────────────

def log_signals(logic_name: str, picks: list[dict], signal_date: Optional[str] = None) -> int:
    """
    picks のリストから signal_log にレコードを追加する。

    picks の各 dict は最低限以下のキーを持つことを想定:
      ticker, direction, entry_price, stop_price, tp1_price, target_price, confidence
    余ったキーは meta カラムに JSON で保存する。

    重複（同一 logic_name + ticker + signal_date）は無視。
    Returns: 挿入した件数
    """
    if not picks:
        return 0

    if signal_date is None:
        signal_date = date.today().isoformat()

    inserted = 0
    with db_cursor() as cur:
        for p in picks:
            ticker = p.get("ticker")
            if not ticker:
                continue

            entry  = _safe_float(p.get("entry_price"))
            stop   = _safe_float(p.get("stop_price"))
            tp1    = _safe_float(p.get("tp1_price"))
            target = _safe_float(p.get("target_price"))
            conf   = _safe_float(p.get("confidence"))
            direction = p.get("direction") or "LONG"

            # 必須: entry, stop, target がないとR評価できないのでスキップ
            if entry is None or stop is None or target is None:
                continue
            # 異常: SLとエントリーが等しい/逆向きはスキップ
            if direction == "LONG" and stop >= entry:
                continue
            if direction == "SHORT" and stop <= entry:
                continue

            meta_json = json.dumps(_strip_for_meta(p), default=str, ensure_ascii=False)

            try:
                cur.execute("""
                    INSERT INTO signal_log
                        (logic_name, ticker, signal_date, direction,
                         entry_price, stop_price, tp1_price, target_price,
                         confidence, meta, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')
                    ON CONFLICT (logic_name, ticker, signal_date) DO NOTHING
                """, (logic_name, ticker, signal_date, direction,
                      entry, stop, tp1, target, conf, meta_json))
                inserted += 1
            except Exception as e:
                print(f"[signal_log] insert error {logic_name}/{ticker}: {e}")

    print(f"[signal_log] {logic_name}: {inserted} signals logged for {signal_date}")
    return inserted


# ────────────────────────────────────────────────────────────────────
# Evaluator
# ────────────────────────────────────────────────────────────────────

def evaluate_open_signals(today: Optional[str] = None,
                           max_holding_days: int = DEFAULT_MAX_HOLDING_DAYS) -> dict:
    """
    'open' な全シグナルを price_data でシミュレートして status を確定。

    ルール:
      - エントリー価格は signal_date の翌日始値（無ければ翌日close）
      - 各日の (low, high, close) で SL/TP1/TP2 のヒットを判定
      - SL ヒット → status='stopped', realized_r = -1.0
      - TP1 ヒット → hit_tp1=True、SL を BE (= entry) に上げる
      - TP1 後 TP2 → status='tp2_hit', realized_r = 0.5*1 + 0.5*targetR
      - TP1 後 BE 戻り → status='tp1_hit_be', realized_r = 0.5*1 + 0.5*0 = 0.5
      - max_holding_days 経過で強制手仕舞い → status='time_exit'
      - signal_date 翌日が price_data に無い場合 → status='invalid'

    MAE/MFE は最大逆行・順行率（エントリー比%）として保存。
    """
    if today is None:
        today = date.today().isoformat()

    stats = {"evaluated": 0, "stopped": 0, "tp1_hit_be": 0, "tp2_hit": 0,
             "time_exit": 0, "still_open": 0, "invalid": 0}

    with db_cursor() as cur:
        # 'open' シグナルを取得
        cur.execute("""
            SELECT id, logic_name, ticker, signal_date, direction,
                   entry_price, stop_price, tp1_price, target_price
            FROM signal_log
            WHERE status = 'open'
        """)
        opens = cur.fetchall()

    for row in opens:
        result = _evaluate_one(dict(row), today, max_holding_days)
        if result is None:
            stats["still_open"] += 1
            continue
        # DB 更新
        _save_eval_result(row["id"], result)
        status = result["status"]
        stats["evaluated"] += 1
        if status == "stopped":      stats["stopped"] += 1
        elif status == "tp2_hit":    stats["tp2_hit"] += 1
        elif status == "tp1_hit_be": stats["tp1_hit_be"] += 1
        elif status == "time_exit":  stats["time_exit"] += 1
        elif status == "invalid":    stats["invalid"] += 1

    print(f"[evaluator] {today}: {stats}")
    return stats


def _evaluate_one(sig: dict, today_iso: str, max_holding_days: int) -> Optional[dict]:
    """単一シグナルを評価。確定したら結果dictを返す。確定しなければ None。"""
    ticker     = sig["ticker"]
    sig_date   = str(sig["signal_date"])
    direction  = sig["direction"]
    entry_plan = float(sig["entry_price"])
    stop_plan  = float(sig["stop_price"])
    tp1_plan   = float(sig["tp1_price"]) if sig.get("tp1_price") is not None else None
    target     = float(sig["target_price"])

    # signal_date 以降の price_data を取得
    with db_cursor() as cur:
        cur.execute("""
            SELECT date, open, high, low, close
            FROM price_data
            WHERE ticker = ? AND date > ?
            ORDER BY date ASC
            LIMIT ?
        """, (ticker, sig_date, max_holding_days + 5))
        bars = cur.fetchall()

    bars = [dict(b) for b in bars]
    if len(bars) == 0:
        # まだ翌日データが無い → still open
        return None

    # エントリー: 翌日始値
    entry_bar = bars[0]
    entry_price = _safe_float(entry_bar.get("open")) or _safe_float(entry_bar.get("close"))
    if entry_price is None:
        return {"status": "invalid", "exit_date": entry_bar["date"], "exit_price": None,
                "realized_r": None, "days_held": 0, "mae_pct": None, "mfe_pct": None,
                "hit_tp1": False}

    # R計算用の risk
    risk = entry_price - stop_plan if direction == "LONG" else stop_plan - entry_price
    if risk <= 0:
        return {"status": "invalid", "exit_date": entry_bar["date"], "exit_price": entry_price,
                "realized_r": None, "days_held": 0, "mae_pct": None, "mfe_pct": None,
                "hit_tp1": False}

    # 順次バーをチェック
    hit_tp1 = False
    current_stop = stop_plan
    mae_pct = 0.0
    mfe_pct = 0.0
    days_held = 0

    for i, bar in enumerate(bars[:max_holding_days]):
        days_held = i + 1
        h = _safe_float(bar.get("high"))
        l = _safe_float(bar.get("low"))
        c = _safe_float(bar.get("close"))
        if h is None or l is None:
            continue

        # MAE/MFE 更新（エントリー比%）
        if direction == "LONG":
            mae_pct = min(mae_pct, (l - entry_price) / entry_price * 100)
            mfe_pct = max(mfe_pct, (h - entry_price) / entry_price * 100)
        else:
            mae_pct = min(mae_pct, (entry_price - h) / entry_price * 100)
            mfe_pct = max(mfe_pct, (entry_price - l) / entry_price * 100)

        # 同一バーで先に SL or TP のどちらをヒットしたかは判定不能。
        # 保守的に: LONG ならSLを先にチェック（不利想定）、SHORT も同様。
        sl_hit = (direction == "LONG" and l <= current_stop) or (direction == "SHORT" and h >= current_stop)
        target_hit = (direction == "LONG" and h >= target) or (direction == "SHORT" and l <= target)
        tp1_hit_now = tp1_plan is not None and (
            (direction == "LONG" and h >= tp1_plan) or (direction == "SHORT" and l <= tp1_plan)
        )

        if sl_hit:
            # ストップ確定。BE移動後なら 0R, 元のSLなら -1R（半分は1R確保済み）
            if hit_tp1:
                realized_r = 0.5 * 1.0 + 0.5 * 0.0  # = 0.5R
                return {"status": "tp1_hit_be", "exit_date": str(bar["date"]),
                        "exit_price": current_stop, "realized_r": realized_r,
                        "days_held": days_held, "mae_pct": mae_pct, "mfe_pct": mfe_pct,
                        "hit_tp1": True}
            else:
                return {"status": "stopped", "exit_date": str(bar["date"]),
                        "exit_price": current_stop, "realized_r": -1.0,
                        "days_held": days_held, "mae_pct": mae_pct, "mfe_pct": mfe_pct,
                        "hit_tp1": False}

        if target_hit:
            # TP2 (=target) 到達 → ターミナル
            target_r = (target - entry_price) / risk if direction == "LONG" else (entry_price - target) / risk
            if hit_tp1:
                realized_r = 0.5 * 1.0 + 0.5 * target_r
            else:
                # TP1 を経由せず TP2 だけ届いた稀ケース → 全量 target_r とみなす
                realized_r = target_r
            return {"status": "tp2_hit", "exit_date": str(bar["date"]),
                    "exit_price": target, "realized_r": realized_r,
                    "days_held": days_held, "mae_pct": mae_pct, "mfe_pct": mfe_pct,
                    "hit_tp1": True}

        if tp1_hit_now and not hit_tp1:
            hit_tp1 = True
            # SL を BE (=entry) に移動
            current_stop = entry_price
            # 同一バーで TP2 にも届いている可能性は target_hit ブロックで処理済み

    # ループ抜け = タイムアウト / バー不足
    if days_held >= max_holding_days:
        last = bars[max_holding_days - 1] if max_holding_days <= len(bars) else bars[-1]
        last_close = _safe_float(last.get("close")) or entry_price
        if direction == "LONG":
            close_r = (last_close - entry_price) / risk
        else:
            close_r = (entry_price - last_close) / risk
        if hit_tp1:
            realized_r = 0.5 * 1.0 + 0.5 * close_r
        else:
            realized_r = close_r
        return {"status": "time_exit", "exit_date": str(last["date"]),
                "exit_price": last_close, "realized_r": realized_r,
                "days_held": days_held, "mae_pct": mae_pct, "mfe_pct": mfe_pct,
                "hit_tp1": hit_tp1}

    # まだ手仕舞いに至らず（バー不足）
    return None


def _save_eval_result(signal_id: int, r: dict):
    with db_cursor() as cur:
        cur.execute("""
            UPDATE signal_log
            SET status = ?, exit_date = ?, exit_price = ?, realized_r = ?,
                days_held = ?, mae_pct = ?, mfe_pct = ?, hit_tp1 = ?,
                evaluated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (r["status"], r.get("exit_date"), r.get("exit_price"), r.get("realized_r"),
              r.get("days_held"), r.get("mae_pct"), r.get("mfe_pct"),
              1 if r.get("hit_tp1") else 0, signal_id))


# ────────────────────────────────────────────────────────────────────
# Stats
# ────────────────────────────────────────────────────────────────────

def get_logic_stats(logic_name: Optional[str] = None,
                     since_days: Optional[int] = None) -> dict:
    """
    全ロジック or 指定ロジックの戦績を集計して返す。
    """
    where_parts = ["status NOT IN ('open', 'invalid')"]
    params: list = []
    if logic_name:
        where_parts.append("logic_name = ?")
        params.append(logic_name)
    if since_days is not None:
        cutoff = (date.today() - timedelta(days=since_days)).isoformat()
        where_parts.append("signal_date >= ?")
        params.append(cutoff)
    where_sql = " AND ".join(where_parts)

    with db_cursor() as cur:
        cur.execute(f"""
            SELECT logic_name, status, realized_r, days_held, signal_date, ticker
            FROM signal_log
            WHERE {where_sql}
            ORDER BY signal_date ASC, id ASC
        """, tuple(params))
        rows = [dict(r) for r in cur.fetchall()]

    if not rows:
        return {"trades": 0, "summary": {}, "by_logic": {}}

    by_logic: dict[str, list] = {}
    for r in rows:
        by_logic.setdefault(r["logic_name"], []).append(r)

    summary = _compute_stats(rows)
    by_logic_stats = {ln: _compute_stats(rs) for ln, rs in by_logic.items()}

    return {
        "trades": len(rows),
        "summary": summary,
        "by_logic": by_logic_stats,
    }


def get_tag_stats(logic_name: Optional[str] = None,
                   since_days: Optional[int] = None,
                   min_count: int = 3) -> dict:
    """
    シグナルに含まれていたタグ（active_signals / entry_reasons）ごとの戦績を集計。
    各シグナルは複数タグを持ちうるため、1シグナルが複数行に展開される。

    Returns:
      [{ tag, count, win_rate, expectancy_r, total_r, profit_factor }, ...]
    """
    where_parts = ["status NOT IN ('open', 'invalid')"]
    params: list = []
    if logic_name:
        where_parts.append("logic_name = ?")
        params.append(logic_name)
    if since_days is not None:
        cutoff = (date.today() - timedelta(days=since_days)).isoformat()
        where_parts.append("signal_date >= ?")
        params.append(cutoff)
    where_sql = " AND ".join(where_parts)

    with db_cursor() as cur:
        cur.execute(f"""
            SELECT logic_name, meta, realized_r
            FROM signal_log
            WHERE {where_sql}
        """, tuple(params))
        rows = [dict(r) for r in cur.fetchall()]

    by_tag: dict[str, list[float]] = {}
    for r in rows:
        meta = _parse_meta(r.get("meta"))
        tags = _extract_tags(meta)
        rr = float(r["realized_r"]) if r.get("realized_r") is not None else None
        if rr is None:
            continue
        for t in tags:
            by_tag.setdefault(t, []).append(rr)

    out = []
    for tag, rs in by_tag.items():
        n = len(rs)
        if n < min_count:
            continue
        wins   = [r for r in rs if r > 0]
        losses = [r for r in rs if r <= 0]
        total_r = sum(rs)
        avg_r   = total_r / n
        win_rate = len(wins) / n * 100
        win_sum  = sum(wins)
        loss_sum = abs(sum(losses))
        pf = (win_sum / loss_sum) if loss_sum > 0 else None
        out.append({
            "tag":           tag,
            "count":         n,
            "win_rate":      round(win_rate, 1),
            "expectancy_r":  round(avg_r, 3),
            "total_r":       round(total_r, 2),
            "profit_factor": round(pf, 2) if pf is not None else None,
        })
    out.sort(key=lambda x: -x["expectancy_r"])
    return {"tags": out, "total_signals": len(rows)}


def _parse_meta(meta) -> dict:
    if meta is None:
        return {}
    if isinstance(meta, dict):
        return meta
    if isinstance(meta, str):
        try:
            return json.loads(meta)
        except (TypeError, ValueError):
            return {}
    return {}


def _extract_tags(meta: dict) -> list[str]:
    """meta から関連タグを抽出する。重複は除去。"""
    tags: set[str] = set()
    # tech 系: active_signals (string array)
    for key in ("active_signals",):
        v = meta.get(key)
        if isinstance(v, list):
            for item in v:
                if isinstance(item, str) and item.strip():
                    tags.add(item.strip())
    # tech 系: signals (object array, 各 obj は {label: ..., win_rate: ..., ...})
    sigs = meta.get("signals")
    if isinstance(sigs, list):
        for s in sigs:
            if isinstance(s, dict) and s.get("label"):
                tags.add(str(s["label"]).strip())
    # funda 系: technical_summary.entry_reasons
    ts = meta.get("technical_summary")
    if isinstance(ts, dict):
        reasons = ts.get("entry_reasons")
        if isinstance(reasons, list):
            for r in reasons:
                if isinstance(r, str) and r.strip():
                    tags.add(r.strip())
    return list(tags)


def _compute_stats(rows: list[dict]) -> dict:
    n = len(rows)
    if n == 0:
        return {"trades": 0}
    wins   = [r for r in rows if (r.get("realized_r") or 0) > 0]
    losses = [r for r in rows if (r.get("realized_r") or 0) <= 0]
    rs     = [float(r["realized_r"]) for r in rows if r.get("realized_r") is not None]

    total_r   = sum(rs)
    avg_r     = total_r / n if n > 0 else 0
    win_rate  = len(wins) / n * 100 if n > 0 else 0
    avg_win   = sum((r.get("realized_r") or 0) for r in wins) / len(wins) if wins else 0
    avg_loss  = sum((r.get("realized_r") or 0) for r in losses) / len(losses) if losses else 0

    win_sum  = sum((r.get("realized_r") or 0) for r in wins)
    loss_sum = abs(sum((r.get("realized_r") or 0) for r in losses))
    pf = (win_sum / loss_sum) if loss_sum > 0 else None

    # Equity curve & max drawdown
    equity = []
    cum = 0
    for r in rs:
        cum += r
        equity.append(cum)
    peak = float("-inf")
    max_dd = 0
    for v in equity:
        peak = max(peak, v)
        dd = peak - v
        max_dd = max(max_dd, dd)

    return {
        "trades":         n,
        "win_rate":       round(win_rate, 1),
        "avg_r":          round(avg_r, 3),
        "expectancy_r":   round(avg_r, 3),
        "avg_win_r":      round(avg_win, 3),
        "avg_loss_r":     round(avg_loss, 3),
        "profit_factor":  round(pf, 2) if pf is not None else None,
        "total_r":        round(total_r, 2),
        "max_dd_r":       round(max_dd, 2),
        "equity_curve":   [{"signal_date": r["signal_date"] if not hasattr(r["signal_date"], "isoformat") else r["signal_date"].isoformat(),
                            "ticker": r["ticker"],
                            "cum_r": round(equity[i], 2)}
                           for i, r in enumerate(rows)],
    }


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────

def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        if f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError):
        return None


def _strip_for_meta(p: dict) -> dict:
    """meta カラム保存用に重い/冗長なキーを除外。"""
    drop_keys = {"meta", "ticker", "direction",
                 "entry_price", "stop_price", "tp1_price", "target_price"}
    return {k: v for k, v in p.items() if k not in drop_keys}
