"""
ロジック３スキャンエンジン — signal-scanner-v5 の Python 移植版

エンジン仕様:
  - 28 シグナル（14 UP / 14 DOWN）: EMA, RSI, BB, MACD, 一目, EMA200, チャートパターン, ローソク足
  - バックテスト: ATR×2 SL / ATR×4 TP, holdDays=short:10 mid:30, 最低サンプル10件
  - スコア: 勝率60% + RR品質25% + 合流点10% + ステージ整合5% × サンプル補正(√N/50)
  - 採用条件: netDir=UP + confidence≥0.70 + WinRate≥0.65 + RR≥2.0
  - データソース: 既存 price_data テーブル（ロジック１・２と共通）
"""

import json
import math
import numpy as np
from datetime import date
from backend.db import get_connection

# ── 定数 ───────────────────────────────────────────────────────────────────
MIN_BARS           = 200
WIN_RATE_THRESHOLD = 0.65
CONFIDENCE_MIN     = 0.70
RR_MIN             = 2.0
MIN_SAMPLES        = 10
ATR_STOP_MULT      = 2.0
ATR_TARGET_MULT    = 4.0

HOLD = {"short": 10, "mid": 30}

# ── シグナル定義（signal-scanner-v5 の SIGNAL_DEFS と同一） ───────────────
SIGNAL_DEFS = [
    # id,           name,                       dir,    tf,      w
    ("ema_gold",    "EMAゴールデンクロス",       "UP",   "short", 4),
    ("ema_dead",    "EMAデッドクロス",           "DOWN", "short", 4),
    ("rsi_b",       "RSI底打ち反発",             "UP",   "short", 3),
    ("rsi_d",       "RSI天井反落",               "DOWN", "short", 3),
    ("rsi_div_b",   "RSI強気ダイバージェンス",   "UP",   "mid",   4),
    ("rsi_div_d",   "RSI弱気ダイバージェンス",   "DOWN", "mid",   4),
    ("bb_up",       "BBスクイーズ上抜け",        "UP",   "short", 3),
    ("bb_dn",       "BBスクイーズ下抜け",        "DOWN", "short", 3),
    ("vol_b",       "出来高急増+大陽線",         "UP",   "short", 3),
    ("vol_d",       "出来高急増+大陰線",         "DOWN", "short", 3),
    ("macd_up",     "MACDゴールデンクロス",      "UP",   "short", 3),
    ("macd_dn",     "MACDデッドクロス",          "DOWN", "short", 3),
    ("hist_up",     "MACDヒスト底打ち",          "UP",   "mid",   3),
    ("hist_dn",     "MACDヒスト天井",            "DOWN", "mid",   3),
    ("kumu_up",     "一目雲上抜け",              "UP",   "mid",   4),
    ("kumu_dn",     "一目雲下抜け",              "DOWN", "mid",   4),
    ("e200_b",      "EMA200サポート反発",        "UP",   "mid",   4),
    ("e200_r",      "EMA200レジスタンス反落",    "DOWN", "mid",   4),
    ("dbot",        "ダブルボトム",              "UP",   "mid",   5),
    ("dtop",        "ダブルトップ",              "DOWN", "mid",   5),
    ("vcp",         "VCPブレイクアウト",         "UP",   "mid",   6),
    ("bull_flag",   "ブルフラッグ",              "UP",   "short", 5),
    ("cup_handle",  "カップ&ハンドル",           "UP",   "mid",   5),
    ("hammer",      "ハンマー",                  "UP",   "short", 3),
    ("shoot_star",  "シューティングスター",       "DOWN", "short", 3),
    ("engulf_b",    "強気包み足",                "UP",   "short", 3),
    ("engulf_d",    "弱気包み足",                "DOWN", "short", 3),
    ("mstar",       "明けの明星",                "UP",   "short", 4),
    ("estar",       "宵の明星",                  "DOWN", "short", 4),
]

# ── インジケーター計算 ─────────────────────────────────────────────────────

def _ema(arr, period):
    k = 2 / (period + 1)
    result = [None] * len(arr)
    initialized = False
    s = 0.0
    for i, v in enumerate(arr):
        if not initialized:
            s += v
            if i == period - 1:
                result[i] = s / period
                initialized = True
        else:
            result[i] = v * k + result[i - 1] * (1 - k)
    return result

def _sma(arr, period):
    result = [None] * (period - 1)
    for i in range(period - 1, len(arr)):
        result.append(sum(arr[i - period + 1:i + 1]) / period)
    return result

def _rsi(closes, period=14):
    n = len(closes)
    result = [None] * n
    if n < period + 1:
        return result
    changes = [closes[i] - closes[i - 1] for i in range(1, n)]
    ag = sum(max(c, 0) for c in changes[:period]) / period
    al = sum(max(-c, 0) for c in changes[:period]) / period
    result[period] = 100 - 100 / (1 + ag / (al or 1e-9))
    for i in range(period, len(changes)):
        ag = (ag * (period - 1) + max(changes[i], 0)) / period
        al = (al * (period - 1) + max(-changes[i], 0)) / period
        result[i + 1] = 100 - 100 / (1 + ag / (al or 1e-9))
    return result

def _macd(closes, fast=12, slow=26, sig=9):
    ef = _ema(closes, fast)
    es = _ema(closes, slow)
    macd = [ef[i] - es[i] if ef[i] is not None and es[i] is not None else None for i in range(len(closes))]
    macd_vals = [v if v is not None else 0.0 for v in macd]
    signal_raw = _ema(macd_vals, sig)
    signal = [signal_raw[i] if macd[i] is not None else None for i in range(len(macd))]
    histogram = [macd[i] - signal[i] if macd[i] is not None and signal[i] is not None else None for i in range(len(macd))]
    return macd, signal, histogram

def _bb(closes, period=20, mult=2):
    upper, lower, middle, bandwidth = [], [], [], []
    for i in range(len(closes)):
        if i < period - 1:
            upper.append(None); lower.append(None); middle.append(None); bandwidth.append(None)
            continue
        sl = closes[i - period + 1:i + 1]
        mn = sum(sl) / period
        sd = math.sqrt(sum((v - mn) ** 2 for v in sl) / period)
        upper.append(mn + mult * sd)
        lower.append(mn - mult * sd)
        middle.append(mn)
        bandwidth.append(2 * mult * sd / mn if mn else None)
    return upper, lower, bandwidth

def _atr(H, L, C, period=14):
    tr = [H[0] - L[0]]
    for i in range(1, len(H)):
        tr.append(max(H[i] - L[i], abs(H[i] - C[i - 1]), abs(L[i] - C[i - 1])))
    return _ema(tr, period)

def _volma(volumes, period=20):
    return _sma(volumes, period)

def _ichimoku(H, L):
    n = len(H)
    tenkan = [None] * n
    kijun  = [None] * n
    spA    = [None] * n
    spB    = [None] * n
    for i in range(n):
        if i >= 8:
            tenkan[i] = (max(H[i - 8:i + 1]) + min(L[i - 8:i + 1])) / 2
        if i >= 25:
            kijun[i] = (max(H[i - 25:i + 1]) + min(L[i - 25:i + 1])) / 2
        if tenkan[i] is not None and kijun[i] is not None:
            spA[i] = (tenkan[i] + kijun[i]) / 2
        if i >= 51:
            spB[i] = (max(H[i - 51:i + 1]) + min(L[i - 51:i + 1])) / 2
    return spA, spB

def _build_indicators(rows):
    C = [r["close"] for r in rows]
    H = [r["high"]  for r in rows]
    L = [r["low"]   for r in rows]
    O = [r["open"]  for r in rows]
    V = [r["volume"] for r in rows]
    e10  = _ema(C, 10)
    e21  = _ema(C, 21)
    e50  = _ema(C, 50)
    e150 = _ema(C, 150)
    e200 = _ema(C, 200)
    rsi  = _rsi(C)
    macd, macd_sig, histogram = _macd(C)
    bb_upper, bb_lower, bb_bw = _bb(C)
    ich_spA, ich_spB = _ichimoku(H, L)
    atr   = _atr(H, L, C)
    volma = _volma(V)
    return dict(
        C=C, H=H, L=L, O=O, V=V,
        e10=e10, e21=e21, e50=e50, e150=e150, e200=e200,
        rsi=rsi, macd=macd, macd_sig=macd_sig, histogram=histogram,
        bb_upper=bb_upper, bb_lower=bb_lower, bb_bw=bb_bw,
        ich_spA=ich_spA, ich_spB=ich_spB,
        atr=atr, volma=volma,
    )

# ── ステージ分類（Minervini） ────────────────────────────────────────────────

def _classify_stage(ind, i):
    c, e50, e150, e200 = ind["C"][i], ind["e50"][i], ind["e150"][i], ind["e200"][i]
    if any(v is None for v in [c, e50, e150, e200]):
        return 0
    prev = max(0, i - 21)
    e200_up = e200 > ind["e200"][prev] if ind["e200"][prev] else False
    e200_dn = e200 < ind["e200"][prev] if ind["e200"][prev] else False
    w = min(252, i + 1)
    high52 = max(ind["H"][max(0, i - w + 1):i + 1])
    low52  = min(ind["L"][max(0, i - w + 1):i + 1])
    if c > e50 > e150 > e200 and e200_up and c >= low52 * 1.25 and c >= high52 * 0.72:
        return 2
    if c < e50 < e150 < e200 and e200_dn and c <= high52 * 0.72:
        return 4
    if c > e200 and not e200_up and not e200_dn:
        return 3
    if c < e50 and c > e200 * 0.95:
        return 1
    return 0

# ── シグナル検出 ────────────────────────────────────────────────────────────

def _check_signal(ind, i, sig_id):
    C, H, L, O, V = ind["C"], ind["H"], ind["L"], ind["O"], ind["V"]
    e10, e21, e50, e200 = ind["e10"], ind["e21"], ind["e50"], ind["e200"]
    rsi = ind["rsi"]
    macd, macd_sig, histogram = ind["macd"], ind["macd_sig"], ind["histogram"]
    bb_upper, bb_lower, bb_bw = ind["bb_upper"], ind["bb_lower"], ind["bb_bw"]
    spA, spB = ind["ich_spA"], ind["ich_spB"]
    atr, volma = ind["atr"], ind["volma"]

    if i < 2:
        return False

    bull = C[i] > O[i]
    bear = C[i] < O[i]
    body = abs(C[i] - O[i]) / (H[i] - L[i] or 0.001)
    vr   = V[i] / volma[i] if volma[i] else 1.0

    if sig_id == "ema_gold":
        return (i >= 1 and e10[i-1] is not None and e21[i-1] is not None and
                e10[i-1] < e21[i-1] and e10[i] >= e21[i])
    if sig_id == "ema_dead":
        return (i >= 1 and e10[i-1] is not None and e21[i-1] is not None and
                e10[i-1] > e21[i-1] and e10[i] <= e21[i])

    if sig_id == "rsi_b":
        return (rsi[i] is not None and rsi[i-1] is not None and
                rsi[i-1] < 32 and rsi[i] > rsi[i-1] and bull)
    if sig_id == "rsi_d":
        return (rsi[i] is not None and rsi[i-1] is not None and
                rsi[i-1] > 72 and rsi[i] < rsi[i-1] and bear)
    if sig_id == "rsi_div_b":
        return _detect_rsi_div_bull(rsi, C, i)
    if sig_id == "rsi_div_d":
        return _detect_rsi_div_bear(rsi, C, i)

    if sig_id == "bb_up":
        return (i >= 1 and bb_upper[i] is not None and bb_bw[i] is not None and
                bb_bw[i] < 0.08 and C[i-1] <= bb_upper[i-1] and C[i] > bb_upper[i])
    if sig_id == "bb_dn":
        return (i >= 1 and bb_lower[i] is not None and bb_bw[i] is not None and
                bb_bw[i] < 0.08 and C[i-1] >= bb_lower[i-1] and C[i] < bb_lower[i])

    if sig_id == "vol_b": return vr > 2.0 and bull and body > 0.55
    if sig_id == "vol_d": return vr > 2.0 and bear and body > 0.55

    if sig_id == "macd_up":
        return (i >= 1 and macd[i] is not None and
                macd[i-1] < macd_sig[i-1] and macd[i] >= macd_sig[i])
    if sig_id == "macd_dn":
        return (i >= 1 and macd[i] is not None and
                macd[i-1] > macd_sig[i-1] and macd[i] <= macd_sig[i])
    if sig_id == "hist_up":
        return (i >= 2 and histogram[i] is not None and histogram[i-2] < -0.04 and
                histogram[i-2] < histogram[i-1] < histogram[i])
    if sig_id == "hist_dn":
        return (i >= 2 and histogram[i] is not None and histogram[i-2] > 0.04 and
                histogram[i-2] > histogram[i-1] > histogram[i])

    if sig_id == "kumu_up":
        if spA[i] is None or spB[i] is None: return False
        top = max(spA[i], spB[i])
        return i >= 1 and C[i-1] <= top * 1.005 and C[i] > top
    if sig_id == "kumu_dn":
        if spA[i] is None or spB[i] is None: return False
        bot = min(spA[i], spB[i])
        return i >= 1 and C[i-1] >= bot * 0.995 and C[i] < bot

    if sig_id == "e200_b":
        return (e200[i] is not None and i >= 3 and
                min(L[i-3], L[i-2], L[i-1], L[i]) <= e200[i] * 1.018 and
                C[i] > e200[i] and C[i] > C[i-1] and bull)
    if sig_id == "e200_r":
        return (e200[i] is not None and i >= 3 and
                max(H[i-3], H[i-2], H[i-1], H[i]) >= e200[i] * 0.982 and
                C[i] < e200[i] and C[i] < C[i-1] and bear)

    if sig_id == "dbot":
        return _detect_double_bottom(H, L, C, V, volma, i)
    if sig_id == "dtop":
        return _detect_double_top(H, L, C, V, volma, i)
    if sig_id == "vcp":
        return _detect_vcp(ind, i)
    if sig_id == "bull_flag":
        return _detect_bull_flag(ind, i)
    if sig_id == "cup_handle":
        return _detect_cup_handle(ind, i)

    if sig_id == "hammer":     return _is_hammer(O, H, L, C, i)
    if sig_id == "shoot_star": return _is_shooting_star(O, H, L, C, i)
    if sig_id == "engulf_b":   return _is_bullish_engulfing(O, H, L, C, i)
    if sig_id == "engulf_d":   return _is_bearish_engulfing(O, H, L, C, i)
    if sig_id == "mstar":      return _is_morning_star(O, H, L, C, i)
    if sig_id == "estar":      return _is_evening_star(O, H, L, C, i)

    return False

# ── パターン検出 ────────────────────────────────────────────────────────────

def _detect_rsi_div_bull(rsi, C, i):
    if i < 25: return False
    prev_low, prev_low_idx = float("inf"), -1
    for j in range(i - 8, max(i - 25, -1), -1):
        if C[j] < prev_low:
            prev_low = C[j]; prev_low_idx = j
    if prev_low_idx < 0: return False
    curr_low = min(C[i], C[i-1] if i >= 1 else float("inf"), C[i-2] if i >= 2 else float("inf"))
    if curr_low >= prev_low: return False
    rp, rn = rsi[prev_low_idx], rsi[i]
    return rp is not None and rn is not None and rn > rp + 4 and rn < 55

def _detect_rsi_div_bear(rsi, C, i):
    if i < 25: return False
    prev_high, prev_high_idx = float("-inf"), -1
    for j in range(i - 8, max(i - 25, -1), -1):
        if C[j] > prev_high:
            prev_high = C[j]; prev_high_idx = j
    if prev_high_idx < 0: return False
    curr_high = max(C[i], C[i-1] if i >= 1 else float("-inf"), C[i-2] if i >= 2 else float("-inf"))
    if curr_high <= prev_high: return False
    rp, rn = rsi[prev_high_idx], rsi[i]
    return rp is not None and rn is not None and rn < rp - 4 and rn > 45

def _detect_double_bottom(H, L, C, V, volma, i):
    if i < 35: return False
    Ls = L[max(0, i-55):i+1]; Hs = H[max(0, i-55):i+1]
    mn = min(Ls); fi = Ls.index(mn)
    if fi < 5 or fi > len(Ls) - 12: return False
    sl2 = Ls[fi + 5:]; m2 = min(sl2)
    if abs(m2 - mn) / mn > 0.025: return False
    si = fi + 5 + sl2.index(m2)
    neck = max(Hs[fi:si + 1])
    vr = V[i] / volma[i] if volma[i] else 1
    return C[i] >= neck * 0.99 and (i == 0 or C[i-1] < neck) and vr > 1.3

def _detect_double_top(H, L, C, V, volma, i):
    if i < 35: return False
    Hs = H[max(0, i-55):i+1]; Ls = L[max(0, i-55):i+1]
    mx = max(Hs); fi = Hs.index(mx)
    if fi < 5 or fi > len(Hs) - 12: return False
    sl2 = Hs[fi + 5:]; m2 = max(sl2)
    if abs(m2 - mx) / mx > 0.025: return False
    si = fi + 5 + sl2.index(m2)
    neck = min(Ls[fi:si + 1])
    vr = V[i] / volma[i] if volma[i] else 1
    return C[i] <= neck * 1.01 and (i == 0 or C[i-1] > neck) and vr > 1.3

def _detect_vcp(ind, i):
    C, H, L, V, e50, e200, volma = ind["C"], ind["H"], ind["L"], ind["V"], ind["e50"], ind["e200"], ind["volma"]
    if i < 80 or e50[i] is None or e200[i] is None: return False
    if C[i] < e50[i] or C[i] < e200[i]: return False
    lb = min(70, i - 10)
    wH = H[i-lb:i+1]; wL = L[i-lb:i+1]; wV = V[i-lb:i+1]
    t = lb // 3
    if t == 0: return False
    r1 = max(wH[:t]) - min(wL[:t])
    r2 = max(wH[t:t*2]) - min(wL[t:t*2])
    r3 = max(wH[t*2:]) - min(wL[t*2:])
    if r1 <= 0: return False
    if not (r2 < r1 * 0.70 and r3 < r2 * 0.70): return False
    if C[i] < max(wH[-20:]) * 0.94: return False
    base_v = wV[:-5]
    avg_base = sum(base_v) / max(len(base_v), 1)
    vol_dried = avg_base > 0 and sum(wV[-5:]) / 5 < avg_base * 0.85
    vr = V[i] / volma[i] if volma[i] else 1
    return vol_dried and vr >= 1.4

def _detect_bull_flag(ind, i):
    C, H, L, V, volma = ind["C"], ind["H"], ind["L"], ind["V"], ind["volma"]
    if i < 35: return False
    pe = i - 4; ps = max(0, pe - 12)
    if (C[pe] - C[ps]) / C[ps] < 0.10: return False
    cH = max(H[pe:i+1]); cL = min(L[pe:i+1])
    if (cH - cL) / cH > 0.10: return False
    prange = C[pe] - C[ps]
    if (C[pe] - cL) > prange * 0.50: return False
    vr = V[i] / volma[i] if volma[i] else 1
    return C[i] >= cH * 0.99 and vr >= 1.4

def _detect_cup_handle(ind, i):
    C, H, L, V, volma = ind["C"], ind["H"], ind["L"], ind["V"], ind["volma"]
    if i < 70: return False
    hl = 8; cl = min(60, i - hl - 5); cs = i - hl - cl
    if cl < 10: return False
    cH = H[cs:i-hl]; cL = L[cs:i-hl]
    if len(cH) < 16: return False
    left_high = max(cH[:8]); bottom = min(cL[8:max(cl-8, 9)]); right_high = max(cH[-8:])
    depth = (left_high - bottom) / left_high
    if depth < 0.10 or depth > 0.55: return False
    if abs(left_high - right_high) / left_high > 0.08: return False
    hr = max(H[i-hl:i+1]) - min(L[i-hl:i+1])
    if hr / left_high > 0.07: return False
    vr = V[i] / volma[i] if volma[i] else 1
    return C[i] >= right_high * 0.99 and vr >= 1.3

# ── ローソク足パターン ──────────────────────────────────────────────────────

def _is_hammer(O, H, L, C, i):
    body = abs(C[i] - O[i]); rng = H[i] - L[i] or 0.001
    ls = min(O[i], C[i]) - L[i]; us = H[i] - max(O[i], C[i])
    return ls >= body * 2.0 and us <= body * 0.5 and body / rng >= 0.1

def _is_shooting_star(O, H, L, C, i):
    body = abs(C[i] - O[i]); rng = H[i] - L[i] or 0.001
    us = H[i] - max(O[i], C[i]); ls = min(O[i], C[i]) - L[i]
    return us >= body * 2.0 and ls <= body * 0.5 and body / rng >= 0.1 and C[i] < O[i]

def _is_bullish_engulfing(O, H, L, C, i):
    if i < 1: return False
    return (C[i-1] < O[i-1] and C[i] > O[i] and O[i] <= C[i-1] and
            C[i] >= O[i-1] and abs(C[i]-O[i]) > abs(C[i-1]-O[i-1]))

def _is_bearish_engulfing(O, H, L, C, i):
    if i < 1: return False
    return (C[i-1] > O[i-1] and C[i] < O[i] and O[i] >= C[i-1] and
            C[i] <= O[i-1] and abs(C[i]-O[i]) > abs(C[i-1]-O[i-1]))

def _is_morning_star(O, H, L, C, i):
    if i < 2: return False
    b0 = abs(C[i-2]-O[i-2]); b1 = abs(C[i-1]-O[i-1]); b2 = abs(C[i]-O[i])
    return (C[i-2] < O[i-2] and b1 <= b0 * 0.35 and C[i] > O[i] and
            C[i] > (O[i-2] + C[i-2]) / 2 and b2 >= b0 * 0.5)

def _is_evening_star(O, H, L, C, i):
    if i < 2: return False
    b0 = abs(C[i-2]-O[i-2]); b1 = abs(C[i-1]-O[i-1]); b2 = abs(C[i]-O[i])
    return (C[i-2] > O[i-2] and b1 <= b0 * 0.35 and C[i] < O[i] and
            C[i] < (O[i-2] + C[i-2]) / 2 and b2 >= b0 * 0.5)

# ── バックテスト ─────────────────────────────────────────────────────────────

def _run_backtest(ind, check_fn, direction, hold_days):
    C, H, L, atr = ind["C"], ind["H"], ind["L"], ind["atr"]
    n = len(C)
    wins = losses = 0
    total_profit = total_loss = 0.0

    for i in range(55, n - hold_days):
        if not check_fn(i): continue
        entry = C[i]; atr_v = atr[i]
        if not atr_v or entry <= 0: continue

        stop   = entry - atr_v * ATR_STOP_MULT if direction == "UP" else entry + atr_v * ATR_STOP_MULT
        target = entry + atr_v * ATR_TARGET_MULT if direction == "UP" else entry - atr_v * ATR_TARGET_MULT
        end_i  = min(i + hold_days, n - 1)
        outcome = None

        for j in range(i + 1, end_i + 1):
            if direction == "UP":
                if L[j] <= stop:   outcome = "LOSS"; break
                if H[j] >= target: outcome = "WIN";  break
            else:
                if H[j] >= stop:   outcome = "LOSS"; break
                if L[j] <= target: outcome = "WIN";  break

        if outcome is None:
            fc = C[end_i]
            outcome = ("WIN" if fc > entry * 1.01 else "LOSS") if direction == "UP" else ("WIN" if fc < entry * 0.99 else "LOSS")

        if outcome == "WIN":
            wins += 1; total_profit += atr_v * ATR_TARGET_MULT
        else:
            losses += 1; total_loss += atr_v * ATR_STOP_MULT

    total = wins + losses
    if total < MIN_SAMPLES:
        return None
    return {
        "win_rate":      wins / total,
        "profit_factor": total_profit / total_loss if total_loss > 0 else (99 if total_profit > 0 else 0),
        "n":             total,
        "avg_rr":        ATR_TARGET_MULT / ATR_STOP_MULT,
    }

# ── RR計算 ───────────────────────────────────────────────────────────────────

def _calc_rr(ind, i):
    C, H, L, atr = ind["C"], ind["H"], ind["L"], ind["atr"]
    atr_v = atr[i]
    if not atr_v or C[i] <= 0: return None
    entry = C[i]

    # LONG のみ（ロジック３は UP のみ）
    atr_stop   = entry - atr_v * ATR_STOP_MULT
    swing_low  = min(L[max(0, i - 10):i + 1])
    stop       = max(atr_stop, swing_low - atr_v * 0.3)

    atr_target = entry + atr_v * ATR_TARGET_MULT
    lb = min(60, i)
    resistance = max(H[i - lb:i]) * 1.002 if i > 0 else atr_target
    target = min(atr_target, resistance if resistance > entry else atr_target)

    risk   = entry - stop
    reward = target - entry
    if risk <= 0: return None

    return {
        "entry":    round(entry,  2),
        "stop":     round(stop,   2),
        "target":   round(target, 2),
        "rr":       round(reward / risk, 2),
        "risk_pct": round(risk / entry * 100, 2),
    }

# ── スコアリング ─────────────────────────────────────────────────────────────

def _stage_alignment(stage, direction):
    if direction == "UP":
        return {2: 1.0, 1: 0.5, 3: 0.4, 4: 0.1}.get(stage, 0.3)
    return {4: 1.0, 3: 0.6, 1: 0.4, 2: 0.1}.get(stage, 0.3)

def _calc_confidence(hits, stage, rr_result, direction):
    if not hits: return 0.0
    avg_wr = sum(h["win_rate"] for h in hits) / len(hits)
    rr_val = rr_result["rr"] if rr_result else 2.0
    rr_factor = min(rr_val / 3.0, 1.0)
    confluence = min(0.5 + (len(hits) - 1) * 0.25, 1.0)
    stage_f    = _stage_alignment(stage, direction)
    raw = 0.60 * avg_wr + 0.25 * rr_factor + 0.10 * confluence + 0.05 * stage_f
    avg_n = sum(h["n"] for h in hits) / len(hits)
    sample_adj = 0.70 + 0.30 * math.sqrt(min(avg_n, 50) / 50)
    return round(raw * sample_adj, 3)

# ── 保有日数推定 ─────────────────────────────────────────────────────────────

def _holding_days(entry, target, atr_pct):
    if not entry or not target or not atr_pct:
        return 20
    atr = entry * atr_pct / 100
    return max(3, round(abs(target - entry) / (atr * 0.5))) if atr > 0 else 20

# ── メインスキャン ───────────────────────────────────────────────────────────

def run():
    print("[Logic3] スキャン開始...")
    conn = get_connection()
    cur  = conn.cursor()

    # 十分なデータがある銘柄を取得
    cur.execute("""
        SELECT p.ticker, COUNT(*) as cnt
        FROM price_data p
        GROUP BY p.ticker
        HAVING COUNT(*) >= ?
    """, (MIN_BARS,))
    tickers = [r["ticker"] for r in cur.fetchall()]
    print(f"[Logic3] 対象銘柄数: {len(tickers)}")

    picks = []
    scanned = skipped = 0

    for ticker in tickers:
        try:
            cur.execute("""
                SELECT date, open, high, low, close, volume
                FROM price_data WHERE ticker = ?
                ORDER BY date ASC
            """, (ticker,))
            rows = cur.fetchall()
            if len(rows) < MIN_BARS:
                continue

            ind   = _build_indicators(rows)
            i     = len(rows) - 1
            stage = _classify_stage(ind, i)

            C, V = ind["C"], ind["V"]
            volma = ind["volma"]
            vol_ratio = V[i] / volma[i] if volma[i] else 1.0
            atr_pct = (ind["atr"][i] / C[i] * 100) if ind["atr"][i] else None

            up_hits = []
            for sig_id, name, direction, tf, w in SIGNAL_DEFS:
                if direction != "UP":
                    continue
                if not _check_signal(ind, i, sig_id):
                    continue
                bt = _run_backtest(ind, lambda j, s=sig_id: _check_signal(ind, j, s), direction, HOLD[tf])
                if bt is None or bt["win_rate"] < WIN_RATE_THRESHOLD:
                    continue
                up_hits.append({"id": sig_id, "name": name, "tf": tf, "w": w, **bt})

            if not up_hits:
                skipped += 1
                continue

            rr_result = _calc_rr(ind, i)
            if rr_result is None or rr_result["rr"] < RR_MIN:
                skipped += 1
                continue

            confidence = _calc_confidence(up_hits, stage, rr_result, "UP")
            if confidence < CONFIDENCE_MIN:
                skipped += 1
                continue

            avg_wr   = sum(h["win_rate"] for h in up_hits) / len(up_hits)
            entry    = rr_result["entry"]
            stop     = rr_result["stop"]
            target   = rr_result["target"]
            tp1      = round(entry + (entry - stop) * 1.5, 2) if entry and stop else None
            sig_names = [h["name"] for h in up_hits[:5]]

            # sector は weekly_picks から引用
            cur.execute("SELECT sector FROM weekly_picks WHERE ticker = ? LIMIT 1", (ticker,))
            sec_row = cur.fetchone()
            sector = sec_row["sector"] if sec_row else None

            picks.append({
                "ticker":          ticker,
                "scan_date":       date.today().isoformat(),
                "stage":           stage,
                "confidence":      confidence,
                "avg_win_rate":    avg_wr,
                "risk_reward":     rr_result["rr"],
                "entry_price":     entry,
                "stop_price":      stop,
                "tp1_price":       tp1,
                "target_price":    target,
                "atr_pct":         atr_pct,
                "rsi":             ind["rsi"][i],
                "vol_ratio":       round(vol_ratio, 2),
                "current_price":   C[i],
                "signals_json":    json.dumps(sig_names, ensure_ascii=False),
                "sector":          sector,
                "holding_days_est": _holding_days(entry, target, atr_pct),
            })
            scanned += 1

        except Exception as e:
            print(f"[Logic3] {ticker} エラー: {e}")

    # 保存
    cur.execute("DELETE FROM logic3_picks")
    for p in picks:
        cur.execute("""
            INSERT INTO logic3_picks
                (ticker, scan_date, stage, confidence, avg_win_rate, risk_reward,
                 entry_price, stop_price, tp1_price, target_price, atr_pct, rsi,
                 vol_ratio, current_price, signals_json, sector, holding_days_est)
            VALUES
                (:ticker, :scan_date, :stage, :confidence, :avg_win_rate, :risk_reward,
                 :entry_price, :stop_price, :tp1_price, :target_price, :atr_pct, :rsi,
                 :vol_ratio, :current_price, :signals_json, :sector, :holding_days_est)
        """, p)
    conn.commit()
    conn.close()

    picks.sort(key=lambda x: -x["confidence"])
    print(f"[Logic3] 完了 — {scanned}件採用 / {skipped}件除外")
    for p in picks[:5]:
        print(f"  {p['ticker']:8s} conf={p['confidence']:.3f} RR={p['risk_reward']:.2f} stage={p['stage']}")
