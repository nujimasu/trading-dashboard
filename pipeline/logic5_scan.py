"""
ロジック５スキャンエンジン — 押し目リバーサル

「押し目にいる」だけでは足りない。**押し目が止まって上に向いた証拠**が
何個そろったかで採否を決める。10年 × 630銘柄のバックテストで、
2017-2023 を学習期間として条件を選び、2024-2026 を検証期間として答え合わせした。

検証期間(2024-2026・アウトオブサンプル)の実績:
  勝率 56.8% / 期待値 +0.161R / PF 1.46 / 最大DD -11R
10年通算(3,597トレード):
  勝率 55.4% / 期待値 +0.126R / PF 1.35 / 累積 +452.7R / 最大DD -34.1R
  ⚠️ 2018年(-16.9R)と2022年(-33.3R)はマイナス。ロング専用の押し目買いなので
     弱気相場では負ける。地合いフィルター(ブレッドス>50%)は検証したが、
     この2年を救わないどころか勝ちトレードを削って通算を悪化させたため採用しない。

母集団（押し目の「場所」にいるか）:
  - トレンド: 株価 > 200EMA かつ 50EMA > 200EMA
  - 3ヶ月騰落率 > 0%
  - 流動性: 20日平均出来高 >= 100万株
  - 20日 or 50日EMA から ±5% 以内

採用条件（押し目が「止まった」証拠）:
  - プライスアクション 7種のうち **4つ以上**
  - オシレーター 3種のうち **1つ以上**
  ※ 条件を増やしても勝率は 54% → 58% で頭打ちになることを実測済み。
     条件の価値は勝率ではなく「期待値 +40% / 最大DD 半減」にある。

リスク設計:
  - 損切り: 直近20日の押し安値 - 0.1×ATR（= 1R）
  - 第1利確: +1.0R で半分 → 残りのストップを建値へ
  - 残り半分: +4R ターゲット
  - 見直し期限: 30営業日
  - 同一銘柄は30営業日クールダウン（バックテストと同じポートフォリオ運用）

logic4（厳選押し目買いv2）との違い:
  logic4 は「EMAタッチ + 出来高枯れ」で場所を厳しく絞る。logic5 は場所を広く取り
  （±5%圏）、代わりに反転の証拠の数で絞る。バックテストでは
  「SL幅≤5%」「EMAタッチ」は単独ではむしろマイナスだった。
"""

import json
from datetime import date, timedelta

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
TP1_R         = 1.0   # 第1利確 = +1.0R で半分
TARGET_R      = 4.0   # 残り半分のターゲット = +4R
MAX_HOLD_DAYS = 30    # 見直し期限（評価器のタイムアウトと同一）
HOLDING_EST   = 10    # 保有日数の目安（表示用）
COOLDOWN_DAYS = 30    # 同一銘柄の再エントリー禁止期間（営業日）

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


# ── メイン ────────────────────────────────────────────────────────────────

def run():
    print("[Logic5] 押し目リバーサル スキャン開始")
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("SELECT ticker, sector FROM universe")
    universe = {r["ticker"]: r["sector"] for r in cur.fetchall()}

    on_cooldown = _cooldown_tickers(conn)
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
            tp1_price    = round(entry + TP1_R * r_value, 2)
            target_price = round(entry + TARGET_R * r_value, 2)

            # ── 反転の証拠 ────────────────────────────────────────────
            rsi_arr = _rsi(C)
            k, d    = _stoch(H, L, C)
            hist    = _macd_hist(C)

            pa_hits,  pa_n  = _price_action(O, H, L, C, i)
            osc_hits, osc_n = _oscillators(rsi_arr, k, d, hist, i)
            qualified = pa_n >= PA_REQUIRED and osc_n >= OSC_REQUIRED
            cooling   = ticker in on_cooldown

            reasons = [f"{ema_label}から{ema_dist:+.1f}%（押し目圏）"] + pa_hits + osc_hits
            if qualified:
                verdict    = "最優先候補"
                confidence = min(0.95, 0.60 + 0.05 * (pa_n - PA_REQUIRED) + 0.05 * (osc_n - OSC_REQUIRED))
            else:
                verdict    = "ウォッチ（条件待ち）"
                confidence = min(0.45, 0.20 + 0.05 * pa_n)
                if pa_n < PA_REQUIRED:
                    reasons.append(f"反転の証拠が {pa_n}個（{PA_REQUIRED}個以上で採用）")
                if osc_n < OSC_REQUIRED:
                    reasons.append("オシレーターの上向き確認なし")

            if cooling and qualified:
                verdict    = "クールダウン中"
                confidence = min(confidence, 0.40)
                reasons.append(f"直近{COOLDOWN_DAYS}営業日にシグナル済み（重複エントリー回避）")

            rules = [
                f"損切り: ${sl_price}（1R = {r_value:.2f} / 株価比 {r_value / entry * 100:.1f}%）",
                f"第1利確: ${tp1_price}（+{TP1_R}R）で半分 → 残りのストップを建値へ",
                f"ターゲット: ${target_price}（+{TARGET_R:.0f}R）",
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
                "risk_reward":     round(TARGET_R, 2),
                "ema_label":       ema_label,
                "ema_dist_pct":    round(ema_dist, 2),
                "support_price":   round(e20 if ema_label == "20日EMA" else e50, 2),
                "pa_count":        pa_n,
                "osc_count":       osc_n,
                "perf_3m":         round(perf_3m, 1),
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
            if qualified and not cooling:
                signal_picks.append(picks[-1])

        except Exception as e:
            print(f"[Logic5] {ticker} エラー: {e}")

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

    order = {"最優先候補": 0, "クールダウン中": 1, "ウォッチ（条件待ち）": 2}
    picks.sort(key=lambda x: (order.get(x["verdict"], 3), -x["confidence"]))
    print(f"[Logic5] 完了 — 押し目圏:{zone_count} 採用:{len(picks)}"
          f"（うちシグナル:{len(signal_picks)} / クールダウン除外:{len(on_cooldown)}銘柄）")
    for p in picks[:5]:
        print(f"  {p['ticker']:8s} {p['verdict']} PA={p['pa_count']}/7 OSC={p['osc_count']}/3 "
              f"conf={p['confidence']:.2f}")
    return picks


if __name__ == "__main__":
    run()
