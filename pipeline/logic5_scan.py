"""
ロジック５スキャンエンジン — 押し目リバーサル

「押し目にいる」だけでは足りない。**押し目が止まって上に向いた証拠**が
何個そろったかで採否を決める。10年 × 630銘柄のバックテストで、
2017-2023 を学習期間として条件を選び、2024-2026 を検証期間として答え合わせした。

独立再検証（翌日寄り・往復各10bp・同日SL優先）の採用版:
  - SPY/QQQ双方の完全上昇トレンド時だけ稼働
  - 30銘柄上限、オシレーター数降順・PA数昇順
  - 2025年以降OOS: 勝率55.6% / 期待値+0.480R / PF2.28
  - 2026最終ホールドアウト: 勝率50.0% / 期待値+0.421R / PF2.20

母集団（押し目の「場所」にいるか）:
  - トレンド: 株価 > 200EMA かつ 50EMA > 200EMA
  - 3ヶ月騰落率 > 0%
  - 流動性: 20日平均出来高 >= 100万株
  - 20日 or 50日EMA から ±5% 以内

採用条件（押し目が「止まった」証拠）:
  - プライスアクション 7種のうち **4つ以上**
  - オシレーター 3種のうち **1つ以上**
  - 21日騰落率 <= -3%、50EMA乖離 >= -1%、出来高比 >= 0.8
  - 60日レジスタンスまでの構造RRが 1.5〜2.0
  ※ 条件を増やしても勝率は 54% → 58% で頭打ちになることを実測済み。
     条件の価値は勝率ではなく「期待値 +40% / 最大DD 半減」にある。

リスク設計:
  - 損切り: 直近20日の押し安値 - 0.1×ATR（= 1R）
  - 利確: 60日高値の0.5%手前で全量決済
  - 見直し期限: 30営業日
  - 同一銘柄は30営業日クールダウン（バックテストと同じポートフォリオ運用）

logic4（厳選押し目買いv2）との違い:
  logic4 は「EMAタッチ + 出来高枯れ」で場所を厳しく絞る。logic5 は場所を広く取り
  （±5%圏）、代わりに反転の証拠の数で絞る。バックテストでは
  「SL幅≤5%」「EMAタッチ」は単独ではむしろマイナスだった。
"""

import json
from datetime import date, datetime, timedelta

from backend.db import get_connection
from config import SECTOR_DISPLAY
from pipeline.logic4_scan import (
    _ema, _sma, _atr, _rsi, _is_excluded,
    MIN_BARS_DAILY, MIN_AVG_VOLUME, PERF_3M_DAYS, PERF_6M_DAYS,
    EMA_NEAR_PCT, STOP_LOOKBACK,
)

# ── 定数（すべてバックテストで検証した値）────────────────────────────────
PA_REQUIRED   = 4     # プライスアクションの証拠（7種）のうち必要数
OSC_REQUIRED  = 1     # オシレーターの証拠（3種）のうち必要数
RESISTANCE_LOOKBACK = 60
MIN_RESISTANCE_RR = 1.50
MAX_RESISTANCE_RR = 2.00
RESISTANCE_BUFFER = 0.995
MAX_HOLD_DAYS = 30    # 見直し期限（評価器のタイムアウトと同一）
HOLDING_EST   = 10    # 保有日数の目安（表示用）
COOLDOWN_DAYS = 30    # 同一銘柄の再エントリー禁止期間（営業日）
MAX_SIGNALS   = 30    # 独立検証で用いた同時保有上限

LOWER_WICK_RATIO = 0.40   # 「下ヒゲが長い」= 下ヒゲがレンジの40%以上
CLOSE_HIGH_RATIO = 0.70   # 「終値が高値圏」= 終値がレンジの上位30%


# ── オシレーター（logic4 に無いものだけ実装）──────────────────────────────

def _stoch(H, L, C, period=14, smooth=3):
    """ストキャスティクス %K と %D（%K の3日移動平均）。"""
    k = [None] * len(C)
    for i in range(period - 1, len(C)):
        hh = max(H[i - period + 1:i + 1])
        ll = min(L[i - period + 1:i + 1])
        k[i] = (C[i] - ll) / (hh - ll) * 100 if hh > ll else 50.0
    d = [None] * len(C)
    for i in range(len(C)):
        w = [k[j] for j in range(max(0, i - smooth + 1), i + 1) if k[j] is not None]
        if len(w) == smooth:
            d[i] = sum(w) / smooth
    return k, d


def _macd_hist(C, fast=12, slow=26, signal=9):
    """MACD ヒストグラム（MACD線 - シグナル線）。"""
    ef, es = _ema(C, fast), _ema(C, slow)
    line = [(ef[i] - es[i]) if (ef[i] is not None and es[i] is not None) else None
            for i in range(len(C))]
    vals = [x for x in line if x is not None]
    if len(vals) < signal:
        return [None] * len(C)
    sig = [None] * (len(C) - len(vals)) + _ema(vals, signal)
    return [(line[i] - sig[i]) if (line[i] is not None and sig[i] is not None) else None
            for i in range(len(C))]


# ── 証拠の判定 ────────────────────────────────────────────────────────────

def _price_action(O, H, L, C, i):
    """プライスアクションの証拠 7種。(該当リスト, 件数) を返す。"""
    rng  = (H[i] - L[i]) or 1e-9
    body = abs(C[i] - O[i])
    lower_wick = min(O[i], C[i]) - L[i]

    checks = [
        (C[i] > O[i],                                   "陽線で確定"),
        (lower_wick / rng >= LOWER_WICK_RATIO,          f"下ヒゲが長い（レンジの{lower_wick / rng * 100:.0f}%）"),
        ((C[i] - L[i]) / rng >= CLOSE_HIGH_RATIO,       "終値が高値圏（上位30%）"),
        (L[i] > L[i - 1] > L[i - 2],                    "安値切り上げ2連（下げ止まり）"),
        (C[i] > H[i - 1],                               "前日高値を超えて確定"),
        (H[i - 1] <= H[i - 2] and L[i - 1] >= L[i - 2] and C[i] > H[i - 1],
                                                        "インサイドバー上抜け"),
        (C[i] > O[i - 1] and O[i] < C[i - 1] and C[i] > O[i],
                                                        "包み足（強気エンガルフィング）"),
    ]
    hits = [label for ok, label in checks if ok]
    return hits, len(hits)


def _oscillators(rsi_arr, k, d, hist, i):
    """オシレーターの証拠 3種。(該当リスト, 件数) を返す。"""
    checks = [
        (rsi_arr[i] is not None and rsi_arr[i - 1] is not None and rsi_arr[i] > rsi_arr[i - 1],
         f"RSIが上向き（{rsi_arr[i]:.0f}）" if rsi_arr[i] is not None else "RSIが上向き"),
        (None not in (k[i], k[i - 1], d[i], d[i - 1]) and k[i - 1] <= d[i - 1] and k[i] > d[i],
         "ストキャス %K が %D を上抜け"),
        (hist[i] is not None and hist[i - 1] is not None and hist[i] > hist[i - 1],
         "MACDヒストグラムが上向き"),
    ]
    hits = [label for ok, label in checks if ok]
    return hits, len(hits)


# ── クールダウン ──────────────────────────────────────────────────────────

def _cooldown_tickers(conn) -> set:
    """直近 COOLDOWN_DAYS 営業日以内に logic5 のシグナルを出した銘柄。

    バックテストは「同一銘柄の建玉が閉じるまで再エントリーしない」前提で
    検証しているため、ライブでも同じ制約を課す。
    """
    cutoff = (date.today() - timedelta(days=int(COOLDOWN_DAYS * 1.5))).isoformat()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT ticker FROM signal_log
            WHERE logic_name = 'logic5' AND signal_date >= ?
        """, (cutoff,))
        return {r["ticker"] for r in cur.fetchall()}
    except Exception as e:
        print(f"[Logic5] クールダウン取得エラー: {e} — 制約なしで続行")
        return set()


def _open_signal_count(conn) -> int:
    """現在未決着のlogic5建玉数。新規枠をMAX_SIGNALS以内に抑える。"""
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) AS cnt FROM signal_log
            WHERE logic_name = 'logic5' AND status = 'open'
        """)
        row = cur.fetchone()
        return int(row["cnt"] if row else 0)
    except Exception as e:
        print(f"[Logic5] オープン件数取得エラー: {e} — 安全側で新規枠なし")
        return MAX_SIGNALS


def _strict_market_regime(cur):
    """SPY/QQQ双方が完全上昇トレンドの時だけ新規エントリーを許可。"""
    states = []
    for ticker in ("SPY", "QQQ"):
        cur.execute("SELECT date, close FROM price_data WHERE ticker = ? ORDER BY date ASC", (ticker,))
        rows = [r for r in cur.fetchall() if r["close"] is not None]
        closes = [r["close"] for r in rows]
        if len(closes) < 200:
            return False, f"{ticker}:データ不足"
        try:
            latest = datetime.fromisoformat(str(rows[-1]["date"])[:10]).date()
        except (TypeError, ValueError):
            return False, f"{ticker}:最終日不明"
        if (date.today() - latest).days > 7:
            return False, f"{ticker}:データ古い({latest})"
        e50 = _ema(closes, 50)[-1]
        e200 = _ema(closes, 200)[-1]
        ok = e50 is not None and e200 is not None and closes[-1] > e200 and e50 > e200
        states.append((ticker, ok))
    return all(ok for _, ok in states), ", ".join(
        f"{ticker}:{'OK' if ok else 'NG'}" for ticker, ok in states
    )


# ── メイン ────────────────────────────────────────────────────────────────

def run():
    print("[Logic5] 押し目リバーサル スキャン開始")
    conn = get_connection()
    cur  = conn.cursor()

    regime_ok, regime_note = _strict_market_regime(cur)
    print(f"[Logic5] 厳格地合い: {'稼働' if regime_ok else '休止'} — {regime_note}")
    if not regime_ok:
        cur.execute("DELETE FROM logic5_picks")
        conn.commit()
        conn.close()
        print("[Logic5] SPY/QQQの完全上昇トレンド不成立につき新規エントリーなし")
        return []

    cur.execute("SELECT ticker, sector FROM universe")
    universe = {r["ticker"]: r["sector"] for r in cur.fetchall()}

    on_cooldown = _cooldown_tickers(conn)
    open_count = _open_signal_count(conn)
    available_slots = max(0, MAX_SIGNALS - open_count)
    scan_date = date.today().isoformat()

    picks, signal_picks = [], []
    zone_count = 0

    for ticker, sector in universe.items():
        try:
            if _is_excluded(ticker):
                continue

            cur.execute("""
                SELECT date, open, high, low, close, volume
                FROM price_data WHERE ticker = ?
                ORDER BY date ASC
            """, (ticker,))
            rows = cur.fetchall()
            if len(rows) < MIN_BARS_DAILY:
                continue

            O = [r["open"]   for r in rows]
            H = [r["high"]   for r in rows]
            L = [r["low"]    for r in rows]
            C = [r["close"]  for r in rows]
            V = [r["volume"] for r in rows]
            i = len(C) - 1

            ema20, ema50, ema200 = _ema(C, 20), _ema(C, 50), _ema(C, 200)
            e20, e50, e200 = ema20[i], ema50[i], ema200[i]
            if any(v is None for v in (e20, e50, e200)):
                continue

            # ── 母集団: 押し目の「場所」にいるか ────────────────────────
            if not (C[i] > e200 and e50 > e200):
                continue
            if i < PERF_3M_DAYS:
                continue
            perf_3m = (C[i] - C[i - PERF_3M_DAYS]) / C[i - PERF_3M_DAYS] * 100
            if perf_3m <= 0:
                continue
            avg_vol = _sma(V, 20)[i]
            if avg_vol is None or avg_vol < MIN_AVG_VOLUME:
                continue
            # RR1.5-2.0探索で安定した「深いが崩れていない押し」。
            mom21 = (C[i] - C[i - 21]) / C[i - 21]
            ema50_dist_raw = (C[i] - e50) / e50
            volume_ratio = V[i] / avg_vol if avg_vol else 0.0
            quality_pullback = (
                ema50_dist_raw >= -0.01
                and mom21 <= -0.03
                and volume_ratio >= 0.80
            )

            d20 = (C[i] - e20) / e20 * 100
            d50 = (C[i] - e50) / e50 * 100
            if abs(d20) <= abs(d50):
                ema_label, ema_dist = "20日EMA", d20
            else:
                ema_label, ema_dist = "50日EMA", d50
            if abs(ema_dist) > EMA_NEAR_PCT:
                continue

            zone_count += 1

            # ── リスク設計 ────────────────────────────────────────────
            atr_arr  = _atr(H, L, C)
            atr_v    = atr_arr[i] or 0.0
            swing_low = min(L[max(0, i - STOP_LOOKBACK + 1):i + 1])
            sl_price = round(swing_low - 0.1 * atr_v, 2)
            entry    = C[i]
            r_value  = entry - sl_price
            if r_value <= 0:
                continue
            # 構造出口: 直近60日レジスタンスの0.5%手前。
            resistance = max(H[max(0, i - RESISTANCE_LOOKBACK):i])
            tp1_price = round(resistance * RESISTANCE_BUFFER, 2)
            resistance_rr = (tp1_price - entry) / r_value
            target_price = tp1_price  # DB互換。残りは固定価格でなくEMA20トレール。

            # ── 反転の証拠 ────────────────────────────────────────────
            rsi_arr = _rsi(C)
            k, d    = _stoch(H, L, C)
            hist    = _macd_hist(C)

            pa_hits,  pa_n  = _price_action(O, H, L, C, i)
            osc_hits, osc_n = _oscillators(rsi_arr, k, d, hist, i)
            qualified = (pa_n >= PA_REQUIRED and osc_n >= OSC_REQUIRED
                         and quality_pullback)
            cooling   = ticker in on_cooldown

            reasons = [
                f"{ema_label}から{ema_dist:+.1f}%（押し目圏）",
                f"21日騰落率 {mom21*100:+.1f}%",
                f"50EMA乖離 {ema50_dist_raw*100:+.1f}%",
                f"当日/20日平均出来高 {volume_ratio:.2f}倍",
            ] + pa_hits + osc_hits
            if qualified:
                verdict    = "最優先候補"
                # OOSで安定した順位: オシレーター数を優先。PAは4個で十分で、
                # 追加確認を待つほど反転初動から遅れるため加点しない。
                confidence = min(0.95, 0.60 + 0.08 * osc_n - 0.02 * (pa_n - PA_REQUIRED))
            else:
                verdict    = "ウォッチ（条件待ち）"
                confidence = min(0.45, 0.20 + 0.05 * pa_n)
                if pa_n < PA_REQUIRED:
                    reasons.append(f"反転の証拠が {pa_n}個（{PA_REQUIRED}個以上で採用）")
                if osc_n < OSC_REQUIRED:
                    reasons.append("オシレーターの上向き確認なし")
                if ema50_dist_raw < -0.01:
                    reasons.append(f"50EMAから{ema50_dist_raw*100:+.1f}%（−1%未満は崩れ過ぎ）")
                if mom21 > -0.03:
                    reasons.append(f"21日騰落率{mom21*100:+.1f}%（−3%以下の明確な押し待ち）")
                if volume_ratio < 0.80:
                    reasons.append(f"出来高比{volume_ratio:.2f}（20日平均の80%以上待ち）")

            if cooling and qualified:
                verdict    = "クールダウン中"
                confidence = min(confidence, 0.40)
                reasons.append(f"直近{COOLDOWN_DAYS}営業日にシグナル済み（重複エントリー回避）")

            rules = [
                f"損切り: ${sl_price}（1R = {r_value:.2f} / 株価比 {r_value / entry * 100:.1f}%）",
                f"翌日寄りでRR再計算: {MIN_RESISTANCE_RR:.1f}〜{MAX_RESISTANCE_RR:.1f}のみ成行エントリー",
                f"全量利確: 60日レジスタンス手前 ${tp1_price}（終値基準は{resistance_rr:.2f}R）",
                f"見直し期限: {MAX_HOLD_DAYS}営業日",
                f"反転の証拠: プライスアクション {pa_n}/7 ・ オシレーター {osc_n}/3",
            ]

            picks.append({
                "ticker":          ticker,
                "scan_date":       scan_date,
                "sector":          SECTOR_DISPLAY.get(sector, sector or "その他"),
                "current_price":   round(C[i], 2),
                "entry_price":     round(entry, 2),
                "stop_price":      sl_price,
                "tp1_price":       tp1_price,
                "target_price":    target_price,
                "risk_reward":     round(resistance_rr, 2),
                "exit_mode":       "resistance_target",
                "exit_fraction":   1.0,
                "cost_bps":        10,
                "min_entry_rr":    MIN_RESISTANCE_RR,
                "max_entry_rr":    MAX_RESISTANCE_RR,
                "ema_label":       ema_label,
                "ema_dist_pct":    round(ema_dist, 2),
                "support_price":   round(e20 if ema_label == "20日EMA" else e50, 2),
                "pa_count":        pa_n,
                "osc_count":       osc_n,
                "perf_3m":         round(perf_3m, 1),
                "mom21":           round(mom21 * 100, 2),
                "volume_ratio":    round(volume_ratio, 3),
                "perf_6m":         (round((C[i] - C[i - PERF_6M_DAYS]) / C[i - PERF_6M_DAYS] * 100, 1)
                                    if i >= PERF_6M_DAYS else None),
                "avg_vol_20d":     round(avg_vol),
                "rsi":             round(rsi_arr[i], 1) if rsi_arr[i] is not None else None,
                "atr":             round(atr_v, 2),
                "verdict":         verdict,
                "confidence":      round(confidence, 2),
                "composite_score": round(confidence * 100, 1),
                "holding_days_est": HOLDING_EST,
                "reasons_json":    json.dumps(reasons, ensure_ascii=False),
                "rules_json":      json.dumps(rules, ensure_ascii=False),
            })
            # signal_picks は走査完了後に横断ランキングで上位だけ選ぶ。

        except Exception as e:
            print(f"[Logic5] {ticker} エラー: {e}")

    qualified_picks = [p for p in picks if p["verdict"] == "最優先候補"]
    qualified_picks.sort(key=lambda p: (
        -p["osc_count"], p["pa_count"], -p["confidence"], p["ticker"]
    ))
    signal_picks = qualified_picks[:available_slots]
    for p in qualified_picks[available_slots:]:
        p["verdict"] = "順位上限外"
        p["confidence"] = min(p["confidence"], 0.49)
        reasons = json.loads(p["reasons_json"])
        reasons.append(f"同時保有上限{MAX_SIGNALS}件（現在open {open_count}件）のため見送り")
        p["reasons_json"] = json.dumps(reasons, ensure_ascii=False)

    # ── 保存 ────────────────────────────────────────────────────────────
    cur.execute("DELETE FROM logic5_picks")
    for p in picks:
        cur.execute("""
            INSERT INTO logic5_picks
                (ticker, scan_date, sector, current_price, entry_price, stop_price,
                 tp1_price, target_price, risk_reward, ema_label, ema_dist_pct,
                 support_price, pa_count, osc_count, perf_3m, perf_6m, avg_vol_20d,
                 rsi, atr, verdict, confidence, composite_score, holding_days_est,
                 reasons_json, rules_json)
            VALUES
                (:ticker, :scan_date, :sector, :current_price, :entry_price, :stop_price,
                 :tp1_price, :target_price, :risk_reward, :ema_label, :ema_dist_pct,
                 :support_price, :pa_count, :osc_count, :perf_3m, :perf_6m, :avg_vol_20d,
                 :rsi, :atr, :verdict, :confidence, :composite_score, :holding_days_est,
                 :reasons_json, :rules_json)
        """, p)
    conn.commit()
    conn.close()

    try:
        from backend.services.signal_tracker import log_signals
        log_signals("logic5", [{**p, "direction": "LONG"} for p in signal_picks])
    except Exception as e:
        print(f"[Logic5] signal_log 記録エラー: {e}")

    order = {"最優先候補": 0, "クールダウン中": 1,
             "順位上限外": 2, "ウォッチ（条件待ち）": 3}
    picks.sort(key=lambda x: (order.get(x["verdict"], 3), -x["confidence"]))
    print(f"[Logic5] 完了 — 押し目圏:{zone_count} 採用:{len(picks)}"
          f"（新規シグナル:{len(signal_picks)} / open:{open_count}/{MAX_SIGNALS}"
          f" / クールダウン除外:{len(on_cooldown)}銘柄）")
    for p in picks[:5]:
        print(f"  {p['ticker']:8s} {p['verdict']} PA={p['pa_count']}/7 OSC={p['osc_count']}/3 "
              f"conf={p['confidence']:.2f}")
    return picks


if __name__ == "__main__":
    run()
