from __future__ import annotations
"""
Tech Scan Pipeline — Pure Technical Analysis
signal-scanner-v5 のロジックをPythonに移植。
16シグナルをバックテストで検証し、信頼度スコアで銘柄をランキング。
"""
import json
import sys
import numpy as np
import pandas as pd
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.db import get_connection

# ── パラメータ ────────────────────────────────────────────────────────────────
MIN_BARS          = 150      # 最低限必要なバー数
MIN_BACKTEST_HITS = 20       # バックテスト最低サンプル数（10→20: 統計的信頼性向上）
WIN_RATE_THRESH   = 0.58     # シグナル採用の最低勝率（0.52→0.58: 手数料後エッジ確保）
CONFIDENCE_THRESH = 0.62     # picks に載せる最低信頼度（0.58→0.62: 新confidence式対応）
RR_MIN            = 1.5      # 最低 Risk/Reward（好条件が揃えば1.5も可）
ATR_STOP_MULT     = 2.0      # ストップ = ATR × 2.0
ATR_TARGET_MULT   = 4.0      # ターゲット = ATR × 4.0
HOLD_SHORT        = 10       # 短期シグナルの保有日数
HOLD_MID          = 20       # 中期シグナルの保有日数（スウィング前提）

# ── シグナル定義 [id, 日本語ラベル, 方向, ウェイト, 保有日数] ───────────────
SIGNALS = [
    ("ema_cross_up",        "EMAゴールデンクロス",       "UP",   3, HOLD_SHORT),
    ("ema_cross_dn",        "EMAデッドクロス",           "DOWN", 3, HOLD_SHORT),
    ("rsi_bounce",          "RSI売られ過ぎ反転",          "UP",   3, HOLD_SHORT),
    ("rsi_rejection",       "RSI買われ過ぎ反落",          "DOWN", 3, HOLD_SHORT),
    ("rsi_div_bull",        "RSI強気ダイバージェンス",    "UP",   4, HOLD_MID),
    ("rsi_div_bear",        "RSI弱気ダイバージェンス",    "DOWN", 4, HOLD_MID),
    ("macd_cross_up",       "MACDゴールデンクロス",       "UP",   3, HOLD_SHORT),
    ("macd_cross_dn",       "MACDデッドクロス",           "DOWN", 3, HOLD_SHORT),
    ("bb_squeeze_up",       "BBスクイーズ上抜け",         "UP",   4, HOLD_SHORT),
    ("bb_squeeze_dn",       "BBスクイーズ下抜け",         "DOWN", 4, HOLD_SHORT),
    ("vol_bull",            "出来高急増陽線",              "UP",   3, HOLD_SHORT),
    ("vol_bear",            "出来高急増陰線",              "DOWN", 3, HOLD_SHORT),
    ("vcp_breakout",        "VCPブレイクアウト",           "UP",   6, HOLD_MID),
    ("bull_flag",           "ブルフラッグ",                "UP",   5, HOLD_MID),
    ("double_bottom",       "ダブルボトム",                "UP",   5, HOLD_MID),
    ("double_top",          "ダブルトップ",                "DOWN", 5, HOLD_MID),
]
SIG_MAP = {s[0]: s for s in SIGNALS}


# ── 指標計算 ──────────────────────────────────────────────────────────────────
def _compute_indicators(df: pd.DataFrame) -> dict | None:
    if len(df) < MIN_BARS:
        return None
    c = df["close"].astype(float)
    h = df["high"].astype(float)
    l = df["low"].astype(float)
    o = df["open"].astype(float)
    v = df["volume"].astype(float)

    ema10  = c.ewm(span=10,  adjust=False).mean()
    ema21  = c.ewm(span=21,  adjust=False).mean()
    ema50  = c.ewm(span=50,  adjust=False).mean()
    ema150 = c.ewm(span=150, adjust=False).mean()
    ema200 = c.ewm(span=200, adjust=False).mean()

    delta  = c.diff()
    avg_g  = delta.clip(lower=0).ewm(span=14, adjust=False).mean()
    avg_l  = (-delta.clip(upper=0)).ewm(span=14, adjust=False).mean()
    rsi    = 100 - 100 / (1 + avg_g / avg_l.replace(0, np.nan))

    ema12  = c.ewm(span=12, adjust=False).mean()
    ema26  = c.ewm(span=26, adjust=False).mean()
    macd   = ema12 - ema26
    macd_s = macd.ewm(span=9, adjust=False).mean()

    bb_m   = c.rolling(20).mean()
    bb_s   = c.rolling(20).std()
    bb_up  = bb_m + 2 * bb_s
    bb_dn  = bb_m - 2 * bb_s
    bb_bw  = (bb_up - bb_dn) / bb_m

    tr     = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr    = tr.ewm(span=14, adjust=False).mean()
    vol_ma = v.rolling(20).mean()

    # numpy arrays for fast inner loop
    return {
        "c": c.to_numpy(), "h": h.to_numpy(), "l": l.to_numpy(),
        "o": o.to_numpy(), "v": v.to_numpy(),
        "e10": ema10.to_numpy(), "e21": ema21.to_numpy(),
        "e50": ema50.to_numpy(), "e150": ema150.to_numpy(), "e200": ema200.to_numpy(),
        "rsi": rsi.to_numpy(), "macd": macd.to_numpy(), "macd_s": macd_s.to_numpy(),
        "bb_up": bb_up.to_numpy(), "bb_dn": bb_dn.to_numpy(), "bb_bw": bb_bw.to_numpy(),
        "atr": atr.to_numpy(), "vol_ma": vol_ma.to_numpy(),
    }


# ── Stage分類（Minervini） ─────────────────────────────────────────────────────
def _classify_stage(ind: dict, i: int) -> int:
    c, e50, e150, e200 = ind["c"][i], ind["e50"][i], ind["e150"][i], ind["e200"][i]
    if any(np.isnan([c, e50, e150, e200])):
        return 0
    prev = max(0, i - 21)
    e200_up = e200 > ind["e200"][prev]
    e200_dn = e200 < ind["e200"][prev]
    w = min(252, i + 1)
    high52 = float(np.max(ind["h"][max(0, i - w + 1):i + 1]))
    low52  = float(np.min(ind["l"][max(0, i - w + 1):i + 1]))
    if c > e50 > e150 > e200 and e200_up and c >= low52 * 1.25 and c >= high52 * 0.72:
        return 2
    if c < e50 < e150 < e200 and e200_dn and c <= high52 * 0.72:
        return 4
    if c > e200 and not e200_up and not e200_dn:
        return 3
    if c < e50 and c > e200 * 0.95:
        return 1
    return 0


# ── シグナル検出（1バーで判定） ────────────────────────────────────────────────
def _fire(sig_id: str, ind: dict, i: int) -> bool:
    if i < 55:
        return False
    c, h, l, o, v = ind["c"], ind["h"], ind["l"], ind["o"], ind["v"]
    vm = ind["vol_ma"][i]
    if np.isnan(vm) or vm == 0:
        vm = 1.0

    def safe(arr, idx):
        v = arr[idx]
        return float(v) if not np.isnan(v) else None

    if sig_id == "ema_cross_up":
        e10n, e21n = safe(ind["e10"], i), safe(ind["e21"], i)
        e10p, e21p = safe(ind["e10"], i-1), safe(ind["e21"], i-1)
        return None not in (e10n,e21n,e10p,e21p) and e10p <= e21p and e10n > e21n

    if sig_id == "ema_cross_dn":
        e10n, e21n = safe(ind["e10"], i), safe(ind["e21"], i)
        e10p, e21p = safe(ind["e10"], i-1), safe(ind["e21"], i-1)
        return None not in (e10n,e21n,e10p,e21p) and e10p >= e21p and e10n < e21n

    if sig_id == "rsi_bounce":
        rp, rn = safe(ind["rsi"], i-1), safe(ind["rsi"], i)
        return rp is not None and rn is not None and rp < 35 and rn > rp

    if sig_id == "rsi_rejection":
        rp, rn = safe(ind["rsi"], i-1), safe(ind["rsi"], i)
        return rp is not None and rn is not None and rp > 70 and rn < rp

    if sig_id == "rsi_div_bull":
        if i < 20:
            return False
        c_sl  = c[i-20:i+1]
        r_sl  = ind["rsi"][i-20:i+1]
        m_idx = int(np.nanargmin(c_sl))
        if m_idx >= len(c_sl) - 2:
            return False
        prev_low_c, cur_low_c = c_sl[m_idx], c[i]
        prev_low_r, cur_rsi   = r_sl[m_idx], ind["rsi"][i]
        return (not np.isnan(cur_rsi) and cur_low_c < prev_low_c and cur_rsi > prev_low_r)

    if sig_id == "rsi_div_bear":
        if i < 20:
            return False
        c_sl  = c[i-20:i+1]
        r_sl  = ind["rsi"][i-20:i+1]
        m_idx = int(np.nanargmax(c_sl))
        if m_idx >= len(c_sl) - 2:
            return False
        prev_hi_c, cur_hi_c = c_sl[m_idx], c[i]
        prev_hi_r, cur_rsi  = r_sl[m_idx], ind["rsi"][i]
        return (not np.isnan(cur_rsi) and cur_hi_c > prev_hi_c and cur_rsi < prev_hi_r)

    if sig_id == "macd_cross_up":
        mn, sn = safe(ind["macd"], i), safe(ind["macd_s"], i)
        mp, sp = safe(ind["macd"], i-1), safe(ind["macd_s"], i-1)
        return None not in (mn,sn,mp,sp) and mp <= sp and mn > sn

    if sig_id == "macd_cross_dn":
        mn, sn = safe(ind["macd"], i), safe(ind["macd_s"], i)
        mp, sp = safe(ind["macd"], i-1), safe(ind["macd_s"], i-1)
        return None not in (mn,sn,mp,sp) and mp >= sp and mn < sn

    if sig_id == "bb_squeeze_up":
        bw_sl = ind["bb_bw"][max(0,i-5):i]
        bbu   = safe(ind["bb_up"], i)
        vol_ratio = v[i] / vm if vm > 0 else 0
        return (not np.isnan(bw_sl).all() and np.nanmin(bw_sl) < 0.10
                and bbu is not None and c[i] > bbu
                and vol_ratio >= 1.4)  # Phase4: 出来高確認

    if sig_id == "bb_squeeze_dn":
        bw_sl = ind["bb_bw"][max(0,i-5):i]
        bbd   = safe(ind["bb_dn"], i)
        vol_ratio = v[i] / vm if vm > 0 else 0
        return (not np.isnan(bw_sl).all() and np.nanmin(bw_sl) < 0.10
                and bbd is not None and c[i] < bbd
                and vol_ratio >= 1.4)  # Phase4: 出来高確認

    if sig_id == "vol_bull":
        body = c[i] - c[i-1]
        rng  = h[i] - l[i] if h[i] > l[i] else 1
        return v[i] > vm * 2.0 and body > 0 and body / rng > 0.55

    if sig_id == "vol_bear":
        body = c[i-1] - c[i]
        rng  = h[i] - l[i] if h[i] > l[i] else 1
        return v[i] > vm * 2.0 and body > 0 and body / rng > 0.55

    if sig_id == "vcp_breakout":
        e50, e200 = safe(ind["e50"], i), safe(ind["e200"], i)
        if None in (e50, e200) or c[i] <= e50 or c[i] <= e200:
            return False
        # Phase5: 強化VCPスコアで品質確認（60点以上のみ採用）
        vcp_s = _enhanced_vcp_score(
            c[max(0,i-60):i+1], v[max(0,i-60):i+1],
            h[max(0,i-60):i+1], l[max(0,i-60):i+1]
        )
        if vcp_s < 60:
            return False
        high20 = float(np.max(h[max(0,i-20):i+1]))
        near   = c[i] >= high20 * 0.95
        vol_ratio = v[i] / vm if vm > 0 else 0
        return near and vol_ratio >= 1.3  # Phase4: 出来高確認統合

    if sig_id == "bull_flag":
        if i < 30:
            return False
        pole_c  = c[i-15:i-4]
        pole_lo = float(np.min(pole_c))
        pole_hi = float(np.max(pole_c))
        if pole_lo == 0 or (pole_hi - pole_lo) / pole_lo < 0.10:
            return False
        consol  = c[i-5:i+1]
        clo, chi = float(np.min(consol)), float(np.max(consol))
        if clo == 0 or (chi - clo) / clo > 0.06:
            return False
        return c[i] > pole_hi * 0.995 and v[i] > vm * 1.4

    if sig_id == "double_bottom":
        if i < 40:
            return False
        sl    = l[i-40:i]
        m1    = int(np.argmin(sl))
        if m1 >= len(sl) - 8 or m1 < 5:
            return False
        low1  = sl[m1]
        sl2   = sl[m1+5:]
        if len(sl2) == 0:
            return False
        low2  = float(np.min(sl2))
        if abs(low1 - low2) / low1 > 0.025:
            return False
        neck  = float(np.max(c[i-40:i]))
        return c[i] > neck * 0.995 and v[i] > vm * 1.3

    if sig_id == "double_top":
        if i < 40:
            return False
        sl    = h[i-40:i]
        m1    = int(np.argmax(sl))
        if m1 >= len(sl) - 8 or m1 < 5:
            return False
        hi1   = sl[m1]
        sl2   = sl[m1+5:]
        if len(sl2) == 0:
            return False
        hi2   = float(np.max(sl2))
        if abs(hi1 - hi2) / hi1 > 0.025:
            return False
        neck  = float(np.min(c[i-40:i]))
        return c[i] < neck * 1.005 and v[i] > vm * 1.3

    return False


# ── Stage B: 転換確認シグナル ─────────────────────────────────────────────────
# Stage A（準備）があった銘柄に対し、当日の価格データで「転換確定」を判断する。
# LONG系: 陽線包み足, ハンマー, 三川明けの明星, 高値3日切り上げ, リテスト完了
# SHORT系: 陰線包み足, シューティングスター, 三川宵の明星, 安値3日切り下げ, リテスト完了
# 共通: 出来高急増（確認パターンと同時に出た場合のみ追加）

STAGE_B_LABELS = {
    "BULLISH_ENGULFING": "陽線包み足",
    "HAMMER":            "ハンマー足",
    "MORNING_STAR":      "三川明けの明星",
    "HIGHER_HIGHS_3D":   "高値3日切り上げ",
    "RETEST_COMPLETE":   "リテスト完了",
    "BEARISH_ENGULFING": "陰線包み足",
    "SHOOTING_STAR":     "シューティングスター",
    "EVENING_STAR":      "三川宵の明星",
    "LOWER_LOWS_3D":     "安値3日切り下げ",
    "VOLUME_SURGE":      "出来高急増",
}


def _detect_stage_b(ind: dict, i: int, direction: str, orig_entry: float) -> list:
    """Stage B 転換確認シグナルを検出。direction は 'LONG' or 'SHORT'。"""
    if i < 3:
        return []

    confirmed = []
    c, h, l, o, v = ind["c"], ind["h"], ind["l"], ind["o"], ind["v"]
    vm = ind["vol_ma"][i]
    if np.isnan(vm) or vm == 0:
        vm = float(np.nanmean(v[max(0, i-20):i])) or 1.0

    if direction == "LONG":
        # ① Bullish Engulfing（陽線包み足）
        if (c[i-1] < o[i-1]             # 前日陰線
                and c[i] > o[i]          # 当日陽線
                and c[i] > o[i-1]        # 当日終値 > 前日始値
                and o[i] < c[i-1]):      # 当日始値 < 前日終値
            confirmed.append("BULLISH_ENGULFING")

        # ② Hammer（ハンマー足）- 下ヒゲが実体の2倍以上、上ヒゲ小さい
        body = abs(c[i] - o[i])
        rng  = h[i] - l[i]
        if rng > 0:
            lower_shadow = min(c[i], o[i]) - l[i]
            upper_shadow = h[i] - max(c[i], o[i])
            if (lower_shadow / rng > 0.55
                    and body / rng < 0.35
                    and upper_shadow / rng < 0.15
                    and c[i] >= o[i]):
                confirmed.append("HAMMER")

        # ③ Morning Star（三川明けの明星）
        pp, mid = i - 2, i - 1
        pp_body  = abs(c[pp]  - o[pp])
        pp_rng   = (h[pp]  - l[pp])  or 1
        mid_body = abs(c[mid] - o[mid])
        mid_rng  = (h[mid] - l[mid]) or 1
        if (c[pp] < o[pp]                           # 1本目 大陰線
                and pp_body / pp_rng > 0.50          # 実体大きい
                and mid_body / mid_rng < 0.25        # 2本目 小実体（コマ/十字）
                and c[i] > o[i]                      # 3本目 陽線
                and c[i] > (o[pp] + c[pp]) / 2):     # 1本目中値超え
            confirmed.append("MORNING_STAR")

        # ④ 高値3日連続切り上げ
        if h[i] > h[i-1] > h[i-2]:
            confirmed.append("HIGHER_HIGHS_3D")

        # ⑤ リテスト完了（orig_entry ±2% まで引き付け、当日再上昇）
        if orig_entry > 0:
            touched_low = any(
                abs(l[j] / orig_entry - 1) < 0.025
                for j in range(max(0, i - 4), i)
            )
            if touched_low and c[i] > orig_entry * 0.990:
                confirmed.append("RETEST_COMPLETE")

    elif direction == "SHORT":
        # ① Bearish Engulfing（陰線包み足）
        if (c[i-1] > o[i-1]
                and c[i] < o[i]
                and c[i] < o[i-1]
                and o[i] > c[i-1]):
            confirmed.append("BEARISH_ENGULFING")

        # ② Shooting Star（シューティングスター）
        body = abs(c[i] - o[i])
        rng  = h[i] - l[i]
        if rng > 0:
            upper_shadow = h[i] - max(c[i], o[i])
            lower_shadow = min(c[i], o[i]) - l[i]
            if (upper_shadow / rng > 0.55
                    and body / rng < 0.35
                    and lower_shadow / rng < 0.15
                    and c[i] <= o[i]):
                confirmed.append("SHOOTING_STAR")

        # ③ Evening Star（三川宵の明星）
        pp, mid = i - 2, i - 1
        pp_body  = abs(c[pp]  - o[pp])
        pp_rng   = (h[pp]  - l[pp])  or 1
        mid_body = abs(c[mid] - o[mid])
        mid_rng  = (h[mid] - l[mid]) or 1
        if (c[pp] > o[pp]
                and pp_body / pp_rng > 0.50
                and mid_body / mid_rng < 0.25
                and c[i] < o[i]
                and c[i] < (o[pp] + c[pp]) / 2):
            confirmed.append("EVENING_STAR")

        # ④ 安値3日連続切り下げ
        if l[i] < l[i-1] < l[i-2]:
            confirmed.append("LOWER_LOWS_3D")

        # ⑤ リテスト完了（ショート: orig_entry まで戻り再下落）
        if orig_entry > 0:
            touched_hi = any(
                abs(h[j] / orig_entry - 1) < 0.025
                for j in range(max(0, i - 4), i)
            )
            if touched_hi and c[i] < orig_entry * 1.010:
                confirmed.append("RETEST_COMPLETE")

    # 共通: 出来高急増（他の確認パターンと同時発生のみ）
    if confirmed and v[i] >= vm * 1.5:
        confirmed.append("VOLUME_SURGE")

    return confirmed


# ── 強化VCPスコア（Phase5） ────────────────────────────────────────────────────
def _enhanced_vcp_score(closes: np.ndarray, volumes: np.ndarray,
                        highs: np.ndarray, lows: np.ndarray) -> int:
    """
    改善VCPスコア (0-100):
    - 収縮回数: 最低2回、3回以上でボーナス (0-30pt)
    - 各収縮の深さ: 前回比で浅くなっているか (0-25pt)
    - 出来高ドライアップ: ベース右端で最低出来高か (0-25pt)
    - ピボットラインの明確さ: 高値が水平に収束しているか (0-20pt)
    """
    n = len(closes)
    if n < 60:
        return 0

    score = 0

    # 収縮回数チェック: 3×20バー区間で range を計測
    ranges = []
    for period_start in range(n - 60, n, 20):
        period_end = min(period_start + 20, n)
        if period_end - period_start < 5:
            continue
        h_sl = highs[period_start:period_end]
        l_sl = lows[period_start:period_end]
        rng_pct = (float(np.max(h_sl)) - float(np.min(l_sl))) / float(np.mean(closes[period_start:period_end]))
        ranges.append(rng_pct)

    if len(ranges) >= 2:
        contractions = sum(1 for i in range(1, len(ranges)) if ranges[i] < ranges[i-1] * 0.85)
        if contractions >= 2:
            score += 30
        elif contractions == 1:
            score += 15

        # 収縮深さが浅くなっているか
        if len(ranges) >= 3 and ranges[-1] < ranges[-2] < ranges[-3]:
            score += 25
        elif len(ranges) >= 2 and ranges[-1] < ranges[-2]:
            score += 12

    # 出来高ドライアップ: 直近5日の平均が過去30日の平均の70%以下
    if n >= 35:
        vol_recent = float(np.mean(volumes[n-5:n]))
        vol_base   = float(np.mean(volumes[n-35:n-5]))
        if vol_base > 0:
            vol_ratio = vol_recent / vol_base
            if vol_ratio <= 0.50:
                score += 25
            elif vol_ratio <= 0.70:
                score += 15
            elif vol_ratio <= 0.85:
                score += 5

    # ピボットラインの明確さ: 直近20バーの高値の標準偏差が小さい
    if n >= 20:
        hi_sl = highs[n-20:n]
        hi_std = float(np.std(hi_sl)) / float(np.mean(hi_sl)) if np.mean(hi_sl) > 0 else 1.0
        if hi_std < 0.02:
            score += 20
        elif hi_std < 0.04:
            score += 12
        elif hi_std < 0.06:
            score += 5

    return min(score, 100)


# ── バックテスト（Phase9: スリッページ・次バー・保有上限改善） ─────────────────
def _backtest(sig_id: str, ind: dict, direction: str, hold_days: int) -> dict | None:
    n        = len(ind["c"])
    c, h, l  = ind["c"], ind["h"], ind["l"]
    o_arr    = ind["o"]  # Phase9: 翌日始値エントリー用
    atr_arr  = ind["atr"]
    wins = losses = 0
    win_profits = []  # Phase9: 勝ちトレードの利益率追跡
    MAX_HOLD = 20     # Phase9: スウィング前提の最大保有バー数

    for i in range(55, n - MAX_HOLD - 2):
        if not _fire(sig_id, ind, i):
            continue

        # Phase9: 翌日始値 + スリッページ0.1%でエントリー
        if i + 1 >= n:
            continue
        if direction == "UP":
            entry = o_arr[i + 1] * 1.001  # 翌日始値 + 0.1% スリッページ
        else:
            entry = o_arr[i + 1] * 0.999  # 翌日始値 - 0.1% スリッページ

        atr_i = atr_arr[i] if not np.isnan(atr_arr[i]) else entry * 0.02
        if direction == "UP":
            stop   = entry - ATR_STOP_MULT * atr_i
            target = entry + ATR_TARGET_MULT * atr_i
        else:
            stop   = entry + ATR_STOP_MULT * atr_i
            target = entry - ATR_TARGET_MULT * atr_i

        outcome = None
        for j in range(i + 2, min(i + MAX_HOLD + 2, n)):
            lo, hi = l[j], h[j]
            if direction == "UP":
                if lo <= stop:   outcome = "LOSS"; break
                if hi >= target: outcome = "WIN";  break
            else:
                if hi >= stop:   outcome = "LOSS"; break
                if lo <= target: outcome = "WIN";  break

        # Phase9: 最大保有バー超過で強制決済
        if outcome is None:
            exit_c = c[min(i + MAX_HOLD + 1, n - 1)]
            if direction == "UP":
                profit_r = (exit_c - entry) / (entry - stop) if entry > stop else 0
                outcome = "WIN" if exit_c > entry * 1.01 else "LOSS"
            else:
                profit_r = (entry - exit_c) / (stop - entry) if stop > entry else 0
                outcome = "WIN" if exit_c < entry * 0.99 else "LOSS"
        else:
            if outcome == "WIN":
                if direction == "UP":
                    profit_r = (target - entry) / (entry - stop) if entry > stop else 2.0
                else:
                    profit_r = (entry - target) / (stop - entry) if stop > entry else 2.0
            else:
                profit_r = -1.0

        if outcome == "WIN":
            wins += 1
            win_profits.append(profit_r)
        else:
            losses += 1

    total = wins + losses
    if total < MIN_BACKTEST_HITS:
        return None

    win_rate = wins / total

    # Phase9: 勝ちトレードの平均利益が0.5R未満なら勝率を0.9倍に調整
    if win_profits:
        avg_win_r = float(np.mean(win_profits))
        if avg_win_r < 0.5:
            win_rate = win_rate * 0.90

    return {"win_rate": win_rate, "n": total, "wins": wins, "losses": losses}


# ── RR計算（市場構造ベース） ────────────────────────────────────────────────────
def _calc_rr(ind: dict, direction: str) -> dict | None:
    """
    市場構造（スウィング高値/安値）に基づいてSL・TPを設定し、実際のRRを計算する。
    RRを強制的に2.0にするのではなく、構造的なSL/TPから自然なRRを導く。
    """
    i     = len(ind["c"]) - 1
    entry = ind["c"][i]
    atr_i = ind["atr"][i]
    if np.isnan(atr_i) or atr_i == 0:
        return None

    c, h, l = ind["c"], ind["h"], ind["l"]

    if direction == "UP":
        # ── SL: 直近20バーのスウィング安値の0.5%下 ──
        swing_low = float(np.min(l[max(0, i - 20):i + 1]))
        stop = swing_low * 0.995
        risk = entry - stop

        # 最小リスク下限 = ATR × 0.75（タイトなベースでRRが爆発するのを防ぐ）
        min_risk = atr_i * 0.75
        if risk < min_risk:
            stop = entry - min_risk
            risk = min_risk

        if risk <= 0 or risk > entry * 0.20:  # 20%超は異常値として除外
            return None

        # ── TP: 直近30バーの最高値の2%手前（スウィング現実的範囲内に限定）──
        # 上限はentry × 1.30（スウィングトレードで30%超は非現実的）
        max_target = entry * 1.30
        lookback_high = float(np.max(h[max(0, i - 30):i]))  # 当日を含めない
        if entry * 1.02 < lookback_high <= max_target:
            # エントリーより2%以上上で30%以内の直近高値 → その2%手前をTP
            target = lookback_high * 0.98
        else:
            # 新高値更新中 or 近くに適切な抵抗なし → ATR×3（上限30%）
            target = min(entry + atr_i * 3.0, max_target)

        # TP1: エントリー + リスク × 1.5
        tp1 = entry + risk * 1.5

        # TPがTP1以下（抵抗が近すぎる）→ ATR×3にフォールバック
        if target <= tp1:
            target = min(entry + atr_i * 3.0, max_target)

        rr = (target - entry) / risk

    else:  # SHORT
        # ── SL: 直近20バーのスウィング高値の0.5%上 ──
        swing_high = float(np.max(h[max(0, i - 20):i + 1]))
        stop = swing_high * 1.005
        risk = stop - entry

        min_risk = atr_i * 0.75
        if risk < min_risk:
            stop = entry + min_risk
            risk = min_risk

        if risk <= 0 or risk > entry * 0.20:
            return None

        # ── TP: 直近30バーの最安値の2%手前（30%下限内に限定）──
        min_target = entry * 0.70
        lookback_low = float(np.min(l[max(0, i - 30):i]))
        if min_target <= lookback_low < entry * 0.98:
            target = lookback_low * 1.02
        else:
            target = max(entry - atr_i * 3.0, min_target)

        tp1 = entry - risk * 1.5
        if target >= tp1:
            target = max(entry - atr_i * 3.0, min_target)

        rr = (entry - target) / risk

    return {
        "entry": round(entry, 2), "stop": round(stop, 2),
        "tp1": round(tp1, 2), "target": round(target, 2),
        "rr": round(rr, 2), "atr_pct": round(atr_i / entry * 100, 2),
    }


# ── 信頼度スコア（Phase8: 配分改善） ─────────────────────────────────────────
def _confidence(hits: list, rr: float, stage: int, direction: str,
                market_score: int = 50) -> float:
    """
    hits: list of {weight, win_rate, n}
    Phase8 新配分:
      win_rate   40% (過剰適合リスク低減)
      stage      20% (Stage2/4の質を重視)
      convergence 15% (複数シグナル一致)
      rr         15% (RR品質)
      market_ctx 10% (市場コンテキスト)
    """
    if not hits:
        return 0.0
    avg_wr = np.mean([h["win_rate"] for h in hits])
    avg_n  = np.mean([h["n"] for h in hits])

    # 合流スコア (0-1)
    n_hit = len(hits)
    convergence = 0.50 if n_hit == 1 else 0.75 if n_hit == 2 else 1.0

    # Stage スコア (0-1) — Phase8: 詳細化
    if direction == "UP":
        # Stage 2初期（遷移直後）が最高評価
        stage_f = {2: 1.0, 1: 0.40, 3: 0.20, 0: 0.15, 4: 0.05}.get(stage, 0.15)
    else:
        stage_f = {4: 1.0, 3: 0.50, 1: 0.20, 0: 0.15, 2: 0.05}.get(stage, 0.15)

    # 市場スコア正規化 (0-1)
    market_f = min(market_score / 100.0, 1.0)

    raw = (0.40 * avg_wr
           + 0.20 * stage_f
           + 0.15 * convergence
           + 0.15 * min(rr / 3.0, 1.0)
           + 0.10 * market_f)

    # サンプルサイズ割引
    if avg_n < 10:
        sample_adj = 0.50
    elif avg_n < 20:
        sample_adj = 0.70 + 0.245 * (avg_n - 10) / 10
    else:
        sample_adj = 0.70 + 0.30 * np.sqrt(min(avg_n, 30) / 30)

    return round(float(raw * sample_adj), 4)


# ── シグナル矛盾検出（Phase3） ────────────────────────────────────────────────
def _check_signal_conflicts(up_hits: list, dn_hits: list) -> tuple:
    """
    LONGとSHORTシグナルが同時発火している場合に矛盾を検出・除去。
    Returns: (filtered_up_hits, filtered_dn_hits, conflict_note)
    """
    if not up_hits or not dn_hits:
        return up_hits, dn_hits, None

    up_score = sum(h["weight"] * h["win_rate"] for h in up_hits)
    dn_score = sum(h["weight"] * h["win_rate"] for h in dn_hits)
    total = up_score + dn_score
    if total == 0:
        return [], [], "CONFLICT_NEUTRAL"

    diff_pct = abs(up_score - dn_score) / max(up_score, dn_score)

    if diff_pct <= 0.10:
        # 差が10%以内 → 方向性不明、両方除去
        return [], [], "CONFLICT_NEUTRAL"
    elif up_score > dn_score:
        # UP優勢 → DNを除去
        return up_hits, [], "CONFLICT_RESOLVED_UP"
    else:
        # DOWN優勢 → UPを除去
        return [], dn_hits, "CONFLICT_RESOLVED_DOWN"


# ── Stage遷移検出 ─────────────────────────────────────────────────────────────
def _has_stage_transition(ind: dict, direction: str) -> bool:
    """Stage 1→2 or 4→3 への遷移を検出"""
    i = len(ind["c"]) - 1
    if i < 30:
        return False

    current_stage = _classify_stage(ind, i)

    # UP方向: Stage 2（上昇トレンド）への遷移を検出
    if direction == "UP" and current_stage == 2:
        # 過去21バー以内でステージが低かったかチェック
        for j in range(max(0, i - 20), i):
            if _classify_stage(ind, j) < 2:
                return True

    # DOWN方向: Stage 4（下降トレンド）への遷移を検出
    elif direction == "DOWN" and current_stage == 4:
        for j in range(max(0, i - 20), i):
            if _classify_stage(ind, j) > 2:
                return True

    return False


# ── メイン分析 ─────────────────────────────────────────────────────────────────
def _analyze_ticker(ticker: str, df: pd.DataFrame,
                    market_score: int = 50,
                    earnings_near: bool = False) -> dict | None:
    ind = _compute_indicators(df)
    if ind is None:
        return None

    i     = len(ind["c"]) - 1
    stage = _classify_stage(ind, i)

    up_hits, dn_hits = [], []

    for sig_id, label, direction, weight, hold_days in SIGNALS:
        if not _fire(sig_id, ind, i):
            continue
        bt = _backtest(sig_id, ind, direction, hold_days)
        if bt is None or bt["win_rate"] < WIN_RATE_THRESH:
            continue
        entry = {"id": sig_id, "label": label, "weight": weight,
                 "win_rate": bt["win_rate"], "n": bt["n"]}
        if direction == "UP":
            up_hits.append(entry)
        else:
            dn_hits.append(entry)

    # Phase3: シグナル矛盾検出
    up_hits, dn_hits, conflict_note = _check_signal_conflicts(up_hits, dn_hits)

    up_score = sum(h["weight"] * h["win_rate"] for h in up_hits)
    dn_score = sum(h["weight"] * h["win_rate"] for h in dn_hits)

    if up_score > dn_score and up_hits:
        direction, hits = "UP", up_hits
    elif dn_score > up_score and dn_hits:
        direction, hits = "DOWN", dn_hits
    else:
        return None  # NEUTRAL — skip

    # Phase6: 市場環境が非常に悪い場合はLONGシグナルを却下
    if market_score < 20 and direction == "UP":
        return None

    rr_result = _calc_rr(ind, direction)
    if rr_result is None or rr_result["rr"] < RR_MIN:
        return None

    conf = _confidence(hits, rr_result["rr"], stage, direction, market_score)

    # Stage遷移ボーナス：より信頼度の高い状況を加点
    if _has_stage_transition(ind, direction):
        conf = round(conf + 0.05, 4)

    # Phase7: 決算接近時は信頼度を半減
    if earnings_near:
        conf = round(conf * 0.5, 4)

    if conf < CONFIDENCE_THRESH:
        return None

    avg_wr  = round(float(np.mean([h["win_rate"] for h in hits])), 4)
    rsi_now = float(ind["rsi"][i]) if not np.isnan(ind["rsi"][i]) else None
    atr_pct = rr_result["atr_pct"]

    return {
        "ticker":       ticker,
        "direction":    "LONG" if direction == "UP" else "SHORT",
        "stage":        stage,
        "confidence":   conf,
        "avg_win_rate": avg_wr,
        "risk_reward":  rr_result["rr"],
        "entry_price":  rr_result["entry"],
        "stop_price":   rr_result["stop"],
        "tp1_price":    rr_result["tp1"],
        "target_price": rr_result["target"],
        "atr_pct":      atr_pct,
        "rsi":          round(rsi_now, 1) if rsi_now else None,
        "signals":      hits,
        "earnings_near": earnings_near,
        "conflict_note": conflict_note,
    }


# ── 市場コンテキスト取得（Phase6） ────────────────────────────────────────────
def _fetch_market_score() -> int:
    """
    TraderMonty breadth CSV から市場スコア(0-100)を算出。
    取得失敗時は50（中立）を返す。
    """
    try:
        import requests
        url = "https://raw.githubusercontent.com/tradermonty/market-breadth-data/main/breadth.csv"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return 50
        import io
        df = pd.read_csv(io.StringIO(resp.text))
        if df.empty:
            return 50

        latest = df.iloc[-1]
        score = 0

        # % Above 200MA > 60%
        pct_200 = None
        for col in ["pct_above_200ma", "PCT_ABOVE_200MA", "above_200ma_pct", "%_above_200ma"]:
            if col in df.columns:
                pct_200 = float(latest[col])
                break
        if pct_200 is not None and pct_200 > 60:
            score += 25

        # AD Line: 直近5日で上昇トレンド
        for col in ["ad_line", "AD_LINE", "ad_line_value"]:
            if col in df.columns and len(df) >= 5:
                ad_vals = df[col].tail(5).dropna().astype(float)
                if len(ad_vals) >= 2 and ad_vals.iloc[-1] > ad_vals.iloc[0]:
                    score += 25
                break

        # New Highs / New Lows > 2
        nh, nl = None, None
        for col in ["new_highs", "NEW_HIGHS", "new_high"]:
            if col in df.columns:
                nh = float(latest[col])
                break
        for col in ["new_lows", "NEW_LOWS", "new_low"]:
            if col in df.columns:
                nl = float(latest[col])
                break
        if nh is not None and nl is not None and nl > 0 and nh / nl > 2:
            score += 25

        # McClellan Oscillator > 0
        for col in ["mcclellan", "MCCLELLAN", "mcclellan_oscillator", "mco"]:
            if col in df.columns:
                mco = float(latest[col])
                if mco > 0:
                    score += 25
                break

        print(f"[TechScan] 市場スコア: {score}/100 (breadth CSV 取得成功)")
        return score

    except Exception as e:
        print(f"[TechScan] 市場スコア取得失敗（中立50を使用）: {e}")
        return 50


# ── 決算回避フィルター（Phase7） ──────────────────────────────────────────────
def _fetch_earnings_near_tickers(tickers: list) -> set:
    """
    FMP API から直近の決算日を取得し、±3営業日以内の銘柄セットを返す。
    API取得失敗時は空セット（フィルターしない）。
    """
    import os
    fmp_key = os.environ.get("FMP_API_KEY", "")
    if not fmp_key:
        return set()
    try:
        import requests
        from datetime import date, timedelta
        today = date.today()
        from_dt = (today - timedelta(days=4)).isoformat()
        to_dt   = (today + timedelta(days=4)).isoformat()
        url = (f"https://financialmodelingprep.com/api/v3/earning_calendar"
               f"?from={from_dt}&to={to_dt}&apikey={fmp_key}")
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return set()
        data = resp.json()
        near = set()
        ticker_set = set(tickers)
        for item in data:
            t = item.get("symbol", "")
            if t in ticker_set:
                near.add(t)
        print(f"[TechScan] 決算接近銘柄: {len(near)}件")
        return near
    except Exception as e:
        print(f"[TechScan] 決算情報取得失敗（フィルターなし）: {e}")
        return set()


# ── DB からデータ読み込み ──────────────────────────────────────────────────────
def _load_price_df(ticker: str, conn) -> pd.DataFrame | None:
    cur = conn.cursor()
    cur.execute("""
        SELECT date, open, high, low, close, volume
        FROM price_data
        WHERE ticker = ?
        ORDER BY date ASC
    """, (ticker,))
    rows = cur.fetchall()
    if len(rows) < MIN_BARS:
        return None
    df = pd.DataFrame(rows, columns=["date","open","high","low","close","volume"])
    return df


# ── エントリーポイント ─────────────────────────────────────────────────────────
def run():
    print("[TechScan] 純テクニカル分析スキャン開始...")
    today   = date.today().isoformat()
    week_of = datetime.now().strftime("%Y-W%W")
    conn    = get_connection()
    cur     = conn.cursor()

    # スキャン対象: price_data に十分なデータがある銘柄
    cur.execute("""
        SELECT ticker, COUNT(*) as cnt
        FROM price_data
        GROUP BY ticker
        HAVING COUNT(*) >= ?
        ORDER BY ticker
    """, (MIN_BARS,))
    tickers = [r["ticker"] for r in cur.fetchall()]
    print(f"[TechScan] 対象銘柄数: {len(tickers)}")

    # Phase6: 市場コンテキスト取得
    market_score = _fetch_market_score()

    # Phase6: 市場スコアに応じて confidence 閾値を調整
    effective_thresh = CONFIDENCE_THRESH
    if market_score >= 70:
        effective_thresh = CONFIDENCE_THRESH - 0.02  # 好地合い: 少し緩める
    elif market_score < 40:
        effective_thresh = CONFIDENCE_THRESH + 0.03  # 悪地合い: 厳しくする
    print(f"[TechScan] 市場スコア={market_score} → 有効信頼度閾値={effective_thresh:.2f}")

    # Phase7: 決算接近銘柄を取得
    earnings_near_set = _fetch_earnings_near_tickers(tickers)

    results = []
    for idx, ticker in enumerate(tickers):
        if idx % 50 == 0:
            print(f"[TechScan] 進捗: {idx}/{len(tickers)} ({ticker})")
        df = _load_price_df(ticker, conn)
        if df is None:
            continue
        try:
            earnings_near = ticker in earnings_near_set
            res = _analyze_ticker(ticker, df, market_score=market_score,
                                  earnings_near=earnings_near)
            if res and res["confidence"] >= effective_thresh:
                results.append(res)
        except Exception as e:
            print(f"[TechScan] {ticker} エラー: {e}")

    # スコア降順でソート（LONG優先）
    results.sort(key=lambda x: (x["direction"] == "SHORT", -x["confidence"]))

    # DB保存
    cur.execute("DELETE FROM tech_weekly_picks")
    for r in results:
        cur.execute("""
            INSERT INTO tech_weekly_picks
                (ticker, week_of, scan_date, direction, stage,
                 confidence, avg_win_rate, risk_reward,
                 entry_price, stop_price, tp1_price, target_price,
                 atr_pct, rsi, signals_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT (ticker) DO UPDATE SET
                week_of=EXCLUDED.week_of, scan_date=EXCLUDED.scan_date,
                direction=EXCLUDED.direction, stage=EXCLUDED.stage,
                confidence=EXCLUDED.confidence, avg_win_rate=EXCLUDED.avg_win_rate,
                risk_reward=EXCLUDED.risk_reward, entry_price=EXCLUDED.entry_price,
                stop_price=EXCLUDED.stop_price, tp1_price=EXCLUDED.tp1_price,
                target_price=EXCLUDED.target_price, atr_pct=EXCLUDED.atr_pct,
                rsi=EXCLUDED.rsi, signals_json=EXCLUDED.signals_json
        """, (
            r["ticker"], week_of, today,
            r["direction"], r["stage"],
            r["confidence"], r["avg_win_rate"], r["risk_reward"],
            r["entry_price"], r["stop_price"], r["tp1_price"], r["target_price"],
            r["atr_pct"], r["rsi"],
            json.dumps(r["signals"], ensure_ascii=False),
        ))

    conn.commit()
    conn.close()

    longs  = [r for r in results if r["direction"] == "LONG"]
    shorts = [r for r in results if r["direction"] == "SHORT"]
    print(f"\n[TechScan] 完了 — LONG {len(longs)}件, SHORT {len(shorts)}件 (合計 {len(results)}件)")
    for r in results[:10]:
        icon = "📈" if r["direction"] == "LONG" else "📉"
        sigs = " | ".join(s["label"] for s in r["signals"])
        print(f"  {icon} {r['ticker']:6s} | Stage{r['stage']} | 信頼度={r['confidence']:.2f} "
              f"| WR={r['avg_win_rate']:.0%} | RR={r['risk_reward']:.1f} | {sigs}")

    return results


# ── JST 日付取得 ─────────────────────────────────────────────────────────────────
def _get_jst_date():
    """Get today's date in JST (Asia/Tokyo)"""
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).date().isoformat()


# ── 日次調整（tech_weekly_picks → tech_daily_picks） ────────────────────────────
def run_daily():
    """既存のtech_weekly_picksに対して当日の最新価格で再チェック。"""
    print("[TechDaily] 日次テクニカル調整開始...")
    today = _get_jst_date()
    conn  = get_connection()
    cur   = conn.cursor()

    cur.execute("SELECT * FROM tech_weekly_picks")
    picks = [dict(r) for r in cur.fetchall()]
    if not picks:
        print("[TechDaily] tech_weekly_picksが空です。--tech-weekly を先に実行してください。")
        conn.close()
        return

    tickers = [p["ticker"] for p in picks]
    pick_map = {p["ticker"]: p for p in picks}

    # Phase6: 市場コンテキスト取得
    market_score = _fetch_market_score()

    # Phase7: 決算接近銘柄取得
    earnings_near_set = _fetch_earnings_near_tickers(tickers)

    cur.execute("DELETE FROM tech_daily_picks WHERE date = ?", (today,))

    for ticker in tickers:
        df = _load_price_df(ticker, conn)
        if df is None:
            continue
        try:
            ind  = _compute_indicators(df)
            if ind is None:
                continue
            i    = len(ind["c"]) - 1
            p    = pick_map[ticker]
            price = float(ind["c"][i])

            # ── Stage A: 当日アクティブなシグナルを再チェック ──
            active = []
            for sig_id, label, direction, _, _ in SIGNALS:
                if _fire(sig_id, ind, i):
                    active.append(label)

            # 当日RR再計算
            direction = "UP" if p["direction"] == "LONG" else "DOWN"
            orig_stop   = float(p["stop_price"])
            orig_target = float(p["target_price"])
            orig_entry  = float(p["entry_price"])
            if direction == "UP":
                risk   = price - orig_stop
                reward = orig_target - price
            else:
                risk   = orig_stop - price
                reward = price - orig_target
            adj_rr = round(reward / risk, 2) if risk > 0 else 0

            # ── Stage B: 転換確認シグナル検出 ──
            stage_b = _detect_stage_b(ind, i, p["direction"], orig_entry)

            has_stage_a = len(active) > 0
            has_stage_b = len(stage_b) > 0

            # Phase6: 市場スコア < 20 の場合 LONG は却下
            earnings_near = ticker in earnings_near_set
            if market_score < 20 and p["direction"] == "LONG":
                verdict = "PASSED"
            else:
                # ── 2段階判定 ──
                # Stage A + Stage B 両方あり → エントリー
                if has_stage_a and has_stage_b:
                    if adj_rr >= 2.0 and p["confidence"] >= 0.70:
                        verdict = "STRONG_BUY" if p["direction"] == "LONG" else "STRONG_SELL"
                    elif adj_rr >= 1.5:
                        verdict = "BUY" if p["direction"] == "LONG" else "SELL"
                    else:
                        verdict = "WATCH"  # RR不足

                # Stage A のみ（確認待ち） → 様子見
                elif has_stage_a and not has_stage_b:
                    verdict = "WATCH"

                # Stage B のみ（準備シグナルなし） → 待機
                elif not has_stage_a and has_stage_b and adj_rr >= 1.5:
                    verdict = "WATCH"  # B単独はWATCH扱い

                # どちらもなし
                elif adj_rr >= 1.0:
                    verdict = "WAIT"
                else:
                    verdict = "PASSED"

                # Phase7: 決算接近でエントリー系を格下げ
                if earnings_near and verdict in ("STRONG_BUY", "STRONG_SELL", "BUY", "SELL"):
                    verdict = "WATCH"  # 決算前は WATCH に格下げ

            cur.execute("""
                INSERT INTO tech_daily_picks
                    (ticker, date, current_price, adjusted_rr, daily_verdict,
                     active_signals_json, stage_b_signals_json)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT (ticker, date) DO UPDATE SET
                    current_price=EXCLUDED.current_price,
                    adjusted_rr=EXCLUDED.adjusted_rr,
                    daily_verdict=EXCLUDED.daily_verdict,
                    active_signals_json=EXCLUDED.active_signals_json,
                    stage_b_signals_json=EXCLUDED.stage_b_signals_json
            """, (ticker, today, price, adj_rr, verdict,
                  json.dumps(active, ensure_ascii=False),
                  json.dumps(stage_b, ensure_ascii=False)))
        except Exception as e:
            print(f"[TechDaily] {ticker} エラー: {e}")

    conn.commit()
    conn.close()
    print(f"[TechDaily] 完了 — {len(tickers)}件処理")


if __name__ == "__main__":
    from backend.db import init_db
    init_db()
    run()
