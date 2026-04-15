"""
ロジック３スキャンエンジン — ブレイクアウト・モメンタム戦略

ロジック２（押し目買い）と正反対のタイミング:
  - ロジック２: サポートに接近 → 反発を買う（下がっている時に買う）
  - ロジック３: レジスタンス突破 → 加速を買う（上がっている時に買う）

戦略の前提:
  - スイングトレード（数日〜数週間）
  - ロング（買い）のみ
  - 基本戦略: ブレイクアウト（保ち合い上抜け後のモメンタム）

一次フィルター（全通過必須）:
  1. 週足: 20EMA > 200EMA
  2. 日足: 株価 > 20EMA > 50EMA > 200EMA（パーフェクトオーダー）
     準: 株価 > 20EMA かつ 20EMA > 200EMA
  3. 過去3ヶ月騰落率 > 0%
  4. 20日平均出来高 >= 500,000株

ベースパターン検出:
  - フラットベース: 直近15〜45日の値幅 < ATR×3、深さ15%以内
  - VCP: 2段階以上の値幅縮小（各70%以下に収縮）
  - アセンディングトライアングル: 水平レジスタンス(±1.5%) + 切り上がりスイングロー
  - カップウィズハンドル: 深さ10〜30%のU字回復 + 小幅ハンドル(最大10%)

ブレイクアウト検出:
  - 終値 > ピボット（ベース上限）
  - ブレイクアウト出来高 >= 平均の1.5倍
  - ピボットからの距離: +0.3〜5%以内

R:R計算:
  - SL: ベース下限×0.99 or ピボット − ATR (浅い方)
  - TP1: メジャードムーブ（ベース深さ分の上昇）
  - TP2: TP1の1.5倍
  - R:R >= 2.0 必須（ブレイクアウトはダマシリスクが高いため）

判定:
  - 最優先候補: ブレイクアウト確認 + 出来高確認 + R:R>=2.0
  - ブレイクアウト接近: ピボットまで2%以内
  - ベース形成中は除外（リストに含めない）
"""

import json
import math
from datetime import date, timedelta
from collections import defaultdict
from backend.db import get_connection

try:
    import yfinance as yf
    _YF_AVAILABLE = True
except ImportError:
    _YF_AVAILABLE = False

# ── 定数 ───────────────────────────────────────────────────────────────────
MIN_BARS_DAILY   = 250
MIN_AVG_VOLUME   = 500_000
PERF_3M_DAYS     = 63
PERF_6M_DAYS     = 126
RR_MIN           = 2.0   # ブレイクアウトはダマシリスクが高いためRR>=2.0必須
PIVOT_MAX_DIST   = 0.05  # ピボットから最大5%以内
PIVOT_APPROACH   = 0.02  # ピボットまで2%以内 = ブレイクアウト接近
SL_MAX_ATR_MULT  = 3.0   # SLは現在値から最大3×ATR下まで
SL_MAX_PCT       = 0.08  # SLは現在値から最大8%下まで

# ── テクニカル計算 ─────────────────────────────────────────────────────────

def _ema(arr, period):
    k = 2 / (period + 1)
    result = [None] * len(arr)
    init = False
    s = 0.0
    for i, v in enumerate(arr):
        if not init:
            s += v
            if i == period - 1:
                result[i] = s / period
                init = True
        else:
            result[i] = v * k + result[i-1] * (1 - k)
    return result

def _sma(arr, period):
    out = [None] * (period - 1)
    for i in range(period - 1, len(arr)):
        out.append(sum(arr[i-period+1:i+1]) / period)
    return out

def _atr(H, L, C, period=14):
    tr = [H[0] - L[0]]
    for i in range(1, len(H)):
        tr.append(max(H[i]-L[i], abs(H[i]-C[i-1]), abs(L[i]-C[i-1])))
    return _ema(tr, period)

def _rsi(closes, period=14):
    n = len(closes)
    result = [None] * n
    if n < period + 1:
        return result
    changes = [closes[i] - closes[i-1] for i in range(1, n)]
    ag = sum(max(c, 0) for c in changes[:period]) / period
    al = sum(max(-c, 0) for c in changes[:period]) / period
    result[period] = 100 - 100 / (1 + ag / (al or 1e-9))
    for i in range(period, len(changes)):
        ag = (ag * (period-1) + max(changes[i], 0)) / period
        al = (al * (period-1) + max(-changes[i], 0)) / period
        result[i+1] = 100 - 100 / (1 + ag / (al or 1e-9))
    return result

# ── 週足リサンプル ────────────────────────────────────────────────────────────

def _resample_weekly(rows):
    weeks = defaultdict(list)
    for r in rows:
        d = date.fromisoformat(r["date"])
        iso = d.isocalendar()
        key = (iso[0], iso[1])
        weeks[key].append(r)
    weekly = []
    for key in sorted(weeks.keys()):
        wbars = sorted(weeks[key], key=lambda x: x["date"])
        weekly.append({
            "close": wbars[-1]["close"],
            "high":  max(b["high"]   for b in wbars),
            "low":   min(b["low"]    for b in wbars),
            "open":  wbars[0]["open"],
            "volume": sum(b["volume"] for b in wbars),
        })
    return weekly

# ── スイングハイ・ロー ────────────────────────────────────────────────────────

def _find_swing_highs(H, lookback=3):
    highs = []
    for i in range(lookback, len(H) - lookback):
        if H[i] == max(H[i-lookback:i+lookback+1]):
            highs.append(i)
    return highs

def _find_swing_lows(L, lookback=3):
    lows = []
    for i in range(lookback, len(L) - lookback):
        if L[i] == min(L[i-lookback:i+lookback+1]):
            lows.append(i)
    return lows

# ── ダウ理論判定 ─────────────────────────────────────────────────────────────

def _dow_theory(H, L, C, i, lookback=60):
    start = max(0, i - lookback)
    sh = _find_swing_highs(H[start:i+1])
    sl = _find_swing_lows(L[start:i+1])
    if len(sh) < 2 or len(sl) < 2:
        return "early"
    h_vals = [H[start + idx] for idx in sh[-3:]]
    l_vals = [L[start + idx] for idx in sl[-3:]]
    hh_count = sum(1 for j in range(1, len(h_vals)) if h_vals[j] > h_vals[j-1])
    hl_count = sum(1 for j in range(1, len(l_vals)) if l_vals[j] > l_vals[j-1])
    if hh_count >= 2 and hl_count >= 2:
        return "strong"
    if hh_count >= 1 and hl_count >= 1:
        return "early"
    return "broken"

# ── ベースパターン検出 ────────────────────────────────────────────────────────

def _detect_flat_base(H, L, C, atr_arr, i, min_len=15, max_len=45):
    """
    フラットベース: 直近min_len〜max_len日の値幅がATRの3倍以内。
    Returns: (pivot_price, base_low, base_length, base_depth_pct) or None
    """
    atr_v = atr_arr[i]
    if atr_v is None or atr_v <= 0:
        return None

    best = None
    for length in range(min_len, min(max_len + 1, i + 1)):
        start = i - length + 1
        base_high = max(H[start:i+1])
        base_low  = min(L[start:i+1])
        base_range = base_high - base_low

        if base_range <= atr_v * 3.0 and base_range > 0:
            depth_pct = base_range / base_high * 100
            if depth_pct <= 15:
                pivot = base_high
                if best is None or length > best[2]:
                    best = (pivot, base_low, length, round(depth_pct, 1))

    return best


def _detect_vcp(H, L, C, V, atr_arr, i, lookback=60):
    """
    VCP (Volatility Contraction Pattern):
    - 2段階以上の値幅縮小、各段階で70%以下に収縮
    - ピボット = 直近のコントラクション上限
    Returns: (pivot_price, base_low, contractions, base_depth_pct) or None
    """
    if i < lookback:
        return None

    start = max(0, i - lookback)
    segment_len = max(5, lookback // 5)

    ranges = []
    for s in range(start, i - segment_len + 2, segment_len):
        end = min(s + segment_len, i + 1)
        if end <= s:
            continue
        seg_range = max(H[s:end]) - min(L[s:end])
        ranges.append((s, end, seg_range))

    if len(ranges) < 3:
        return None

    contractions = 0
    for j in range(1, len(ranges)):
        if ranges[j-1][2] > 0 and ranges[j][2] / ranges[j-1][2] <= 0.70:
            contractions += 1

    if contractions < 2:
        return None

    recent_high = max(H[max(start, i-20):i+1])
    base_low = min(L[start:i+1])
    depth_pct = (recent_high - base_low) / recent_high * 100 if recent_high > 0 else 0

    if depth_pct > 35:
        return None

    return (recent_high, base_low, contractions, round(depth_pct, 1))


def _detect_ascending_triangle(H, L, C, i, lookback=40):
    """
    アセンディングトライアングル:
    - 水平レジスタンス（±1.5%以内に3回以上タッチ）
    - 切り上がるスイングロー
    Returns: (pivot_price, base_low, touch_count, base_depth_pct) or None
    """
    if i < lookback:
        return None

    start = max(0, i - lookback)
    highs = H[start:i+1]
    lows  = L[start:i+1]

    resistance = max(highs)
    if resistance <= 0:
        return None

    touch_count = 0
    for h in highs:
        if abs(h - resistance) / resistance < 0.015:
            touch_count += 1

    if touch_count < 3:
        return None

    sl_idxs = _find_swing_lows(lows, lookback=2)
    if len(sl_idxs) < 2:
        return None

    ascending = all(
        lows[sl_idxs[j]] > lows[sl_idxs[j-1]]
        for j in range(1, len(sl_idxs))
    )
    if not ascending:
        return None

    base_low = min(lows)
    depth_pct = (resistance - base_low) / resistance * 100

    return (resistance, base_low, touch_count, round(depth_pct, 1))


def _detect_cup_with_handle(H, L, C, i, lookback=120):
    """
    カップウィズハンドル（簡易版）:
    - カップ: 深さ10〜30%のU字型回復（左リムから97%以上回復）
    - ハンドル: 直近10〜25日の小幅調整（最大10%）
    Returns: (pivot_price, base_low, cup_depth_pct, handle_depth_pct) or None
    """
    if i < lookback:
        return None

    start = max(0, i - lookback)
    mid = start + (i - start) // 2
    left_rim = max(H[start:mid])
    if left_rim <= 0:
        return None

    cup_low = min(L[start:i+1])
    cup_depth = (left_rim - cup_low) / left_rim * 100

    if not (10 <= cup_depth <= 30):
        return None

    recent_high = max(H[max(start, i-30):i+1])
    recovery = recent_high / left_rim
    if recovery < 0.97:
        return None

    handle_start = max(start, i - 25)
    handle_high = max(H[handle_start:i+1])
    handle_low  = min(L[handle_start:i+1])
    handle_depth = (handle_high - handle_low) / handle_high * 100

    if handle_depth > 10:
        return None

    pivot = handle_high
    return (pivot, cup_low, round(cup_depth, 1), round(handle_depth, 1))


# ── ブレイクアウト確認 ────────────────────────────────────────────────────────

def _check_breakout(C, V, vol_ma, pivot, i):
    """
    ブレイクアウトを確認する。
    Returns: (confirmed: bool, volume_ratio: float, distance_pct: float)
    """
    current = C[i]
    if pivot <= 0 or current <= pivot:
        return False, 0, 0

    distance_pct = (current - pivot) / pivot * 100

    if distance_pct < 0.3 or distance_pct > 5.0:
        return False, 0, distance_pct

    vol_ratio = V[i] / vol_ma if vol_ma and vol_ma > 0 else 0
    confirmed = vol_ratio >= 1.5
    return confirmed, round(vol_ratio, 2), round(distance_pct, 2)


def _check_approaching(C, pivot, i):
    """ピボットに接近中かチェック。"""
    current = C[i]
    if pivot <= 0:
        return False, 0

    distance_pct = (pivot - current) / pivot * 100
    approaching = 0 < distance_pct <= 2.0
    return approaching, round(distance_pct, 2)


# ── R:R計算 ─────────────────────────────────────────────────────────────────

def _calc_rr_breakout(C, H, atr_arr, pivot, base_low, base_depth_pct, i):
    """
    ブレイクアウト用R:R計算。
    TP = メジャードムーブ（ベース深さ分の上昇）
    SL = ベース下限×0.99 or ピボット − ATR（浅い方）
        ただし現在値から 3×ATR or 8% を超えて離れない（フロア制限）
    """
    current = C[i]
    atr_v = atr_arr[i]
    if atr_v is None or atr_v <= 0:
        return None, None, None, None, None

    # --- SL候補 ---
    sl_from_base = base_low * 0.99
    sl_from_atr  = pivot - atr_v
    sl = max(sl_from_base, sl_from_atr)

    # --- SLフロア: 現在値から離れすぎないよう制限 ---
    sl_floor_atr = current - atr_v * SL_MAX_ATR_MULT   # 現在値 - 3ATR
    sl_floor_pct = current * (1 - SL_MAX_PCT)           # 現在値 × 0.92
    sl_floor = max(sl_floor_atr, sl_floor_pct)           # 高い方をフロアに
    sl = max(sl, sl_floor)

    if sl >= current:
        return None, None, None, None, None

    risk = current - sl

    base_height = pivot - base_low
    tp1 = pivot + base_height
    tp2 = pivot + base_height * 1.5

    reward = tp1 - current
    if reward <= 0 or risk <= 0:
        return None, None, None, None, None

    rr = reward / risk
    return round(rr, 2), round(tp1, 2), round(tp2, 2), round(sl, 2), round(atr_v, 4)


# ── メインスキャン ─────────────────────────────────────────────────────────────

def run():
    print("[Logic3] ブレイクアウト・モメンタムスクリーニング開始...")
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        SELECT ticker, COUNT(*) as cnt
        FROM price_data
        GROUP BY ticker
        HAVING COUNT(*) >= ?
    """, (MIN_BARS_DAILY,))
    tickers = [r["ticker"] for r in cur.fetchall()]
    print(f"[Logic3] 対象銘柄数: {len(tickers)}")

    picks = []
    first_pass = second_pass = adopted = 0

    for ticker in tickers:
        try:
            cur.execute("""
                SELECT date, open, high, low, close, volume
                FROM price_data WHERE ticker = ?
                ORDER BY date ASC
            """, (ticker,))
            rows = cur.fetchall()
            if len(rows) < MIN_BARS_DAILY:
                continue

            C = [r["close"]  for r in rows]
            H = [r["high"]   for r in rows]
            L = [r["low"]    for r in rows]
            V = [r["volume"] for r in rows]
            i = len(C) - 1

            # ── インジケーター計算 ──────────────────────────────────────────
            ema20  = _ema(C, 20)
            ema50  = _ema(C, 50)
            ema200 = _ema(C, 200)
            atr_arr = _atr(H, L, C)
            rsi_arr = _rsi(C)
            vol_ma20 = _sma(V, 20)

            # ── 週足EMA ────────────────────────────────────────────────────
            weekly = _resample_weekly(rows)
            wC = [w["close"] for w in weekly]
            w_ema20  = _ema(wC, 20)
            w_ema200 = _ema(wC, 200) if len(wC) >= 200 else _ema(wC, min(len(wC)//2, 100))
            wi = len(wC) - 1

            # ═══════════════════════════════════════════════════════════════
            # 一次フィルター
            # ═══════════════════════════════════════════════════════════════

            if w_ema20[wi] is None or w_ema200[wi] is None:
                continue
            if w_ema20[wi] <= w_ema200[wi]:
                continue

            e20, e50, e200 = ema20[i], ema50[i], ema200[i]
            if any(v is None for v in [e20, e50, e200]):
                continue
            if not (C[i] > e20 and e20 > e200):
                continue
            perfect_order = "full" if (C[i] > e20 > e50 > e200) else "quasi"

            if i < PERF_3M_DAYS:
                continue
            perf_3m = (C[i] - C[i - PERF_3M_DAYS]) / C[i - PERF_3M_DAYS] * 100
            if perf_3m <= 0:
                continue
            perf_6m = (C[i] - C[i - PERF_6M_DAYS]) / C[i - PERF_6M_DAYS] * 100 if i >= PERF_6M_DAYS else None

            avg_vol = vol_ma20[i]
            if avg_vol is None or avg_vol < MIN_AVG_VOLUME:
                continue

            first_pass += 1

            # ═══════════════════════════════════════════════════════════════
            # ベースパターン検出（複数パターンを試行、最良を採用）
            # ═══════════════════════════════════════════════════════════════

            patterns = []

            fb = _detect_flat_base(H, L, C, atr_arr, i)
            if fb:
                patterns.append(("フラットベース", fb[0], fb[1], fb[2], fb[3]))

            vcp = _detect_vcp(H, L, C, V, atr_arr, i)
            if vcp:
                patterns.append(("VCP", vcp[0], vcp[1], vcp[2], vcp[3]))

            at = _detect_ascending_triangle(H, L, C, i)
            if at:
                patterns.append(("アセンディング△", at[0], at[1], at[2], at[3]))

            cwh = _detect_cup_with_handle(H, L, C, i)
            if cwh:
                patterns.append(("カップ&ハンドル", cwh[0], cwh[1], cwh[2], cwh[3]))

            if not patterns:
                continue

            second_pass += 1

            # ダウ理論
            dow = _dow_theory(H, L, C, i)

            # 各パターンでR:R計算し、最良を選択
            best_pick = None

            for pat_name, pivot, base_low, pat_detail, depth_pct in patterns:
                rr_result = _calc_rr_breakout(C, H, atr_arr, pivot, base_low, depth_pct, i)
                rr, tp1, tp2, sl, atr_v = rr_result

                if rr is None:
                    continue

                # ブレイクアウト確認 or 接近チェック
                confirmed, vol_ratio, bo_dist = _check_breakout(C, V, avg_vol, pivot, i)
                approaching, app_dist = _check_approaching(C, pivot, i)

                if not confirmed and not approaching:
                    continue

                if confirmed and rr < RR_MIN:
                    continue

                # スコアリング
                if confirmed:
                    verdict = "最優先候補"
                    base_conf = 0.70
                    vol_bonus = min(0.10, (vol_ratio - 1.5) * 0.05) if vol_ratio > 1.5 else 0
                    rr_bonus = 0.05 if rr >= 3.0 else 0
                    pat_bonus = 0.05 if pat_name in ("VCP", "カップ&ハンドル") else 0
                    confidence = min(0.95, base_conf + vol_bonus + rr_bonus + pat_bonus)
                else:
                    verdict = "ブレイクアウト接近"
                    confidence = min(0.65, 0.50 + (0.05 if rr >= 3.0 else 0))
                    vol_ratio = 0
                    bo_dist = -app_dist

                if best_pick is None or rr > best_pick["risk_reward"]:
                    best_pick = {
                        "ticker":          ticker,
                        "scan_date":       date.today().isoformat(),
                        "perfect_order":   perfect_order,
                        "perf_3m":         round(perf_3m, 2),
                        "perf_6m":         round(perf_6m, 2) if perf_6m is not None else None,
                        "avg_vol_20d":     round(avg_vol),
                        "dow_trend":       dow,
                        "base_pattern":    pat_name,
                        "base_length":     pat_detail,
                        "base_depth_pct":  depth_pct,
                        "pivot_price":     round(pivot, 2),
                        "breakout_confirmed": 1 if confirmed else 0,
                        "breakout_volume_ratio": vol_ratio,
                        "distance_from_pivot_pct": bo_dist,
                        "risk_reward":     rr,
                        "entry_price":     round(C[i], 2),
                        "stop_price":      sl,
                        "tp1_price":       tp1,
                        "target_price":    tp2,
                        "rsi":             round(rsi_arr[i], 1) if rsi_arr[i] is not None else None,
                        "atr":             atr_v,
                        "verdict":         verdict,
                        "confidence":      round(confidence, 3),
                        "composite_score": round(confidence * 100, 1),
                        "sector":          None,
                        "current_price":   round(C[i], 2),
                        "holding_days_est": max(5, round(abs(tp1 - C[i]) / (atr_v * 0.5))) if atr_v and atr_v > 0 else 14,
                        "signals_json":    json.dumps([pat_name], ensure_ascii=False),
                    }

            if best_pick is None:
                continue

            # セクター
            cur.execute("SELECT sector FROM weekly_picks WHERE ticker = ? LIMIT 1", (best_pick["ticker"],))
            sec_row = cur.fetchone()
            best_pick["sector"] = sec_row["sector"] if sec_row else None

            adopted += 1
            picks.append(best_pick)

        except Exception as e:
            print(f"[Logic3] {ticker} エラー: {e}")

    # ── 保存 ────────────────────────────────────────────────────────────────
    cur.execute("DELETE FROM logic3_picks")
    for p in picks:
        cur.execute("""
            INSERT INTO logic3_picks
                (ticker, scan_date, perfect_order, perf_3m, perf_6m, avg_vol_20d,
                 dow_trend, base_pattern, base_length, base_depth_pct,
                 pivot_price, breakout_confirmed, breakout_volume_ratio,
                 distance_from_pivot_pct, risk_reward, entry_price, stop_price,
                 tp1_price, target_price, rsi, atr,
                 verdict, confidence, composite_score, sector, current_price,
                 holding_days_est, signals_json)
            VALUES
                (:ticker, :scan_date, :perfect_order, :perf_3m, :perf_6m, :avg_vol_20d,
                 :dow_trend, :base_pattern, :base_length, :base_depth_pct,
                 :pivot_price, :breakout_confirmed, :breakout_volume_ratio,
                 :distance_from_pivot_pct, :risk_reward, :entry_price, :stop_price,
                 :tp1_price, :target_price, :rsi, :atr,
                 :verdict, :confidence, :composite_score, :sector, :current_price,
                 :holding_days_est, :signals_json)
        """, p)
    conn.commit()
    conn.close()

    verdict_order = {"最優先候補": 0, "ブレイクアウト接近": 1}
    picks.sort(key=lambda x: (
        verdict_order.get(x["verdict"], 3),
        -x["risk_reward"]
    ))
    print(f"[Logic3] 完了 — 一次通過:{first_pass} パターン検出:{second_pass} 採用:{adopted}")
    for p in picks[:5]:
        pat  = p.get("base_pattern") or "-"
        dist = p.get("distance_from_pivot_pct")
        dist_s = f"{dist:+.1f}%" if dist is not None else "N/A"
        print(f"  {p['ticker']:8s} {p['verdict']} RR={p['risk_reward']:.2f} {pat} dist={dist_s}")
