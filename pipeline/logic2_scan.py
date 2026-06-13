"""
ロジック２スキャンエンジン — 押し目買い戦略（厳選4Hトリガー版）

日足・週足の一次/二次フィルター＋4H厳格トリガーを使用。
改善点:
  A. トリガー未検出の「押し目待ち」銘柄をリストから完全除外
  B. 4Hトリガーのパラメータを厳格化（ピンバー3倍、エンガルフィング全包み、
     出来高2.0倍、サポート近傍±3%）
  C. トリガー品質に応じた信頼度ボーナスを加算

戦略の前提:
  - スイングトレード（数日〜数週間）
  - ロング（買い）のみ
  - 基本戦略: 押し目買い（上昇トレンド中の一時的下落からの反発）
  - 厳選: 4Hトリガーが確認された高確信度銘柄のみ

一次フィルター（全通過必須）:
  1. 週足: 20EMA > 200EMA
  2. 日足: 株価 > 20EMA > 50EMA > 200EMA（パーフェクトオーダー）
     準: 株価 > 20EMA かつ 20EMA > 200EMA（フラグ付き）
  3. 過去3ヶ月騰落率 > 0%
  4. 20日平均出来高 ≥ 500,000株

二次フィルター（スコアリング）:
  1. ダウ理論: HH/HL判定
  2. サポートラインの明確さ（コンフルエンス）
  3. レジサポ転換の有無
  4. R:R計算（TP1=直近高値×0.99, SL=サポート少し下の1R固定）

ボーナスフラグ:
  - RSI 30〜50
  - MACDダイバージェンス（強気）
  - フィボナッチコンフルエンス（38.2/50/61.8%）

4Hトリガー（厳格版）:
  - ピンバー: 下ヒゲ ≥ 実体の3倍
  - 強気エンガルフィング: 前足レンジ全体を包み込み
  - 出来高急増: 平均の2.0倍以上
  - サポート近傍: ±3%以内

信頼度ボーナス（提案C）:
  - ピンバー + 出来高急増 → +0.10
  - 強気エンガルフィング + RSI < 40 → +0.10
  - ダブルボトム（サポート乖離 < 1%）→ +0.15

判定:
  - 最優先候補: 4Hトリガー検出 + サポート接近（±3%）
  - サポート接近中: トリガー未検出 + サポート接近（±3%）
  - 「押し目待ち」は除外（提案A: リストに含めない）
"""

import json
import math
import os
import requests
from datetime import date, timedelta
from collections import defaultdict
from backend.db import get_connection
from config import FMP_API_KEY, FMP_BASE_URL, SECTOR_DISPLAY

try:
    import yfinance as yf
    _YF_AVAILABLE = True
except ImportError:
    _YF_AVAILABLE = False

# ── 定数 ───────────────────────────────────────────────────────────────────
MIN_BARS_DAILY   = 250   # 週足200EMA計算に必要な日足バー数
MIN_AVG_VOLUME   = 500_000
PERF_3M_DAYS     = 63    # 約3ヶ月
PERF_6M_DAYS     = 126   # 約6ヶ月
RR_MIN           = 1.5
RR_GOOD          = 2.0
RR_CAP           = 6.0   # RRの上限（極端値抑制・現実的なターゲットに収める）
SWING_LOOKBACK   = 30    # 「近いスイング高値」を探す日数（高勝率・近い高値利確）
SWING_WING       = 3     # スイング高値ピボット判定の左右バー数
SUPPORT_TOLERANCE = 0.03  # サポート近傍±3%

# ── EMA計算 ─────────────────────────────────────────────────────────────────

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

def _macd(closes, fast=12, slow=26, sig=9):
    ef = _ema(closes, fast); es = _ema(closes, slow)
    macd = [ef[i]-es[i] if ef[i] is not None and es[i] is not None else None for i in range(len(closes))]
    sig_raw = _ema([v if v is not None else 0 for v in macd], sig)
    signal = [sig_raw[i] if macd[i] is not None else None for i in range(len(macd))]
    hist = [macd[i]-signal[i] if macd[i] is not None and signal[i] is not None else None for i in range(len(macd))]
    return macd, signal, hist

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
            "close":  wbars[-1]["close"],
            "high":   max(b["high"]   for b in wbars),
            "low":    min(b["low"]    for b in wbars),
            "open":   wbars[0]["open"],
            "volume": sum(b["volume"] for b in wbars),
        })
    return weekly

# ── スイングハイ・ロー検出 ────────────────────────────────────────────────────

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

# ── 日足チャートパターン検出（厳格版） ─────────────────────────────────────────

def _detect_cup_and_handle_strict(H, L, C, i, lookback=60):
    """
    カップウィズハンドル（厳格）: 深さ10〜30%、右リムが左リムの97%以上回復。
    """
    if i < lookback:
        return False
    start = i - lookback

    left_rim_idx = start
    left_rim = H[start]
    for j in range(start, start + lookback // 4):
        if H[j] > left_rim:
            left_rim = H[j]
            left_rim_idx = j

    cup_mid_start = start + lookback // 4
    cup_mid_end = start + lookback * 3 // 4
    if cup_mid_end > i:
        cup_mid_end = i
    cup_bottom = min(L[cup_mid_start:cup_mid_end]) if cup_mid_start < cup_mid_end else L[i]
    cup_bottom_idx = cup_mid_start + L[cup_mid_start:cup_mid_end].index(cup_bottom) if cup_mid_start < cup_mid_end else i

    depth = (left_rim - cup_bottom) / left_rim if left_rim > 0 else 0
    if depth < 0.10 or depth > 0.30:  # 厳格: 10〜30%（標準: 8〜40%）
        return False

    right_section = H[cup_bottom_idx:i + 1]
    if not right_section:
        return False
    right_rim = max(right_section)
    if right_rim < left_rim * 0.97:  # 厳格: 97%回復（標準: 93%）
        return False

    handle_bars = min(15, i - cup_bottom_idx)
    if handle_bars < 3:
        return False
    handle_low = min(L[i - handle_bars:i + 1])
    handle_depth = (right_rim - handle_low) / right_rim if right_rim > 0 else 0
    if handle_depth < 0.02 or handle_depth > 0.10:  # 厳格: 最大10%（標準: 15%）
        return False

    handle_high = max(H[i - handle_bars:i + 1])
    if C[i] >= handle_high * 0.99:
        return True
    return False


def _detect_ascending_triangle_strict(H, L, C, i, lookback=30):
    """
    アセンディングトライアングル（厳格）: レジスタンス±1.5%、スイング3点以上。
    """
    if i < lookback:
        return False
    start = i - lookback

    swing_highs = _find_swing_highs(H[start:i + 1], lookback=2)
    if len(swing_highs) < 3:  # 厳格: 3点以上（標準: 2点）
        return False

    high_vals = [H[start + idx] for idx in swing_highs[-4:]]
    avg_high = sum(high_vals) / len(high_vals)
    if any(abs(h - avg_high) / avg_high > 0.015 for h in high_vals):  # 厳格: 1.5%（標準: 2%）
        return False

    swing_lows = _find_swing_lows(L[start:i + 1], lookback=2)
    if len(swing_lows) < 3:  # 厳格: 3点以上
        return False

    low_vals = [L[start + idx] for idx in swing_lows[-4:]]
    ascending = all(low_vals[j] <= low_vals[j + 1] for j in range(len(low_vals) - 1))
    if not ascending:
        return False

    if C[i] >= avg_high * 0.98:
        return True
    return False


def _detect_inverse_head_shoulders_strict(H, L, C, i, lookback=50):
    """
    逆ヘッドアンドショルダー（厳格）: 両肩±4%、ネックライン超え。
    """
    if i < lookback:
        return False
    start = i - lookback

    swing_lows = _find_swing_lows(L[start:i + 1], lookback=3)
    if len(swing_lows) < 3:
        return False

    s1_idx, s2_idx, s3_idx = swing_lows[-3], swing_lows[-2], swing_lows[-1]
    s1 = L[start + s1_idx]
    s2 = L[start + s2_idx]
    s3 = L[start + s3_idx]

    if not (s2 < s1 and s2 < s3):
        return False

    shoulder_avg = (s1 + s3) / 2
    if abs(s1 - s3) / shoulder_avg > 0.04:  # 厳格: 4%（標準: 6%）
        return False

    between_1_2 = H[start + s1_idx:start + s2_idx + 1]
    between_2_3 = H[start + s2_idx:start + s3_idx + 1]
    if not between_1_2 or not between_2_3:
        return False
    neckline_l = max(between_1_2)
    neckline_r = max(between_2_3)
    neckline = min(neckline_l, neckline_r)

    if C[i] >= neckline * 0.99:  # 厳格: 99%（標準: 98%）
        return True
    return False


def _detect_bull_pennant_strict(H, L, C, i, lookback=30):
    """
    ブルペナント（厳格）: ポール上昇12%以上、レンジ縮小60%以下。
    """
    if i < lookback:
        return False

    pole_start = i - lookback
    pole_end = i - lookback // 2
    pole_low = min(L[pole_start:pole_end + 1])
    pole_high = max(H[pole_start:pole_end + 1])

    pole_gain = (pole_high - pole_low) / pole_low if pole_low > 0 else 0
    if pole_gain < 0.12:  # 厳格: 12%（標準: 8%）
        return False

    pennant_start = pole_end
    pennant_bars = i - pennant_start
    if pennant_bars < 5:  # 厳格: 最低5本（標準: 4本）
        return False

    pennant_highs = [H[j] for j in range(pennant_start, i + 1)]
    pennant_lows = [L[j] for j in range(pennant_start, i + 1)]

    high_declining = pennant_highs[-1] < pennant_highs[0]
    low_rising = pennant_lows[-1] > pennant_lows[0]
    if not (high_declining and low_rising):
        return False

    early_range = pennant_highs[0] - pennant_lows[0]
    late_range = pennant_highs[-1] - pennant_lows[-1]
    if early_range <= 0 or late_range / early_range > 0.6:  # 厳格: 60%（標準: 70%）
        return False

    if C[i] >= pennant_highs[-1] * 0.99:
        return True
    return False


def _detect_falling_wedge_strict(H, L, C, i, lookback=30):
    """
    フォーリングウェッジ（厳格）: 収束50%以下、ブレイク確認。
    """
    if i < lookback:
        return False
    start = i - lookback

    swing_highs = _find_swing_highs(H[start:i + 1], lookback=2)
    swing_lows = _find_swing_lows(L[start:i + 1], lookback=2)

    if len(swing_highs) < 3 or len(swing_lows) < 3:  # 厳格: 3点以上
        return False

    sh_vals = [H[start + idx] for idx in swing_highs[-4:]]
    highs_declining = all(sh_vals[j] > sh_vals[j + 1] for j in range(len(sh_vals) - 1))

    sl_vals = [L[start + idx] for idx in swing_lows[-4:]]
    lows_declining = all(sl_vals[j] > sl_vals[j + 1] for j in range(len(sl_vals) - 1))

    if not (highs_declining and lows_declining):
        return False

    early_spread = sh_vals[0] - sl_vals[0] if sl_vals[0] < sh_vals[0] else 0
    late_spread = sh_vals[-1] - sl_vals[-1] if sl_vals[-1] < sh_vals[-1] else 0
    if early_spread <= 0 or late_spread / early_spread > 0.5:  # 厳格: 50%（標準: 60%）
        return False

    if C[i] > sh_vals[-1]:  # 厳格: 完全ブレイク（標準: 99%）
        return True
    return False


def _detect_daily_chart_patterns_strict(H, L, C, i):
    """日足チャートパターンを検出（厳格版）。"""
    patterns = []
    if _detect_cup_and_handle_strict(H, L, C, i):
        patterns.append("カップウィズハンドル(厳選)")
    if _detect_ascending_triangle_strict(H, L, C, i):
        patterns.append("アセンディングトライアングル(厳選)")
    if _detect_inverse_head_shoulders_strict(H, L, C, i):
        patterns.append("逆ヘッドアンドショルダー(厳選)")
    if _detect_bull_pennant_strict(H, L, C, i):
        patterns.append("ブルペナント(厳選)")
    if _detect_falling_wedge_strict(H, L, C, i):
        patterns.append("フォーリングウェッジ(厳選)")
    return patterns


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

# ── サポートレベル特定 ────────────────────────────────────────────────────────

def _find_support_level(H, L, C, ema20, ema50, atr_arr, i):
    current = C[i]
    candidates = []

    if ema20[i] is not None and ema20[i] < current * 1.05:
        candidates.append((ema20[i], "20EMA"))

    if ema50[i] is not None and ema50[i] < current * 1.08:
        candidates.append((ema50[i], "50EMA"))

    start = max(0, i - 60)
    sl_idxs = _find_swing_lows(L[start:i+1])
    if sl_idxs:
        for idx in reversed(sl_idxs[-3:]):
            sl_price = L[start + idx]
            if sl_price < current * 0.99:
                candidates.append((sl_price, f"スイングロー${sl_price:.2f}"))
                break

    recent_lows = sorted([L[j] for j in range(start, i)], reverse=True)
    if recent_lows:
        for low in recent_lows:
            pct = (current - low) / current
            if 0.02 < pct < 0.15:
                cluster = [l for l in recent_lows if abs(l - low) / low < 0.01]
                if len(cluster) >= 3:
                    candidates.append((low, f"水平サポート${low:.2f}"))
                    break

    if not candidates:
        return None, 0, []

    below = [(p, r) for p, r in candidates if p < current]
    if not below:
        return None, 0, []

    below.sort(key=lambda x: -(x[0]))
    best_price = below[0][0]

    confluent = [(p, r) for p, r in candidates if abs(p - best_price) / best_price < 0.02]
    reasons = [r for _, r in confluent]

    return best_price, len(confluent), reasons

# ── レジサポ転換検出 ─────────────────────────────────────────────────────────

def _detect_reji_sapo(H, L, C, i, lookback=90):
    if i < lookback + 10:
        return "none"

    current = C[i]

    old_highs_window = H[max(0, i-lookback):max(0, i-20)]
    if not old_highs_window:
        return "none"

    resistance = max(old_highs_window)

    if not (current * 0.80 < resistance < current * 0.99):
        return "none"

    recent_window = H[max(0, i-20):i+1]
    broke_out = any(h > resistance * 1.01 for h in recent_window)
    if not broke_out:
        return "none"

    near_resistance = abs(current - resistance) / resistance < SUPPORT_TOLERANCE

    if near_resistance:
        return "confirmed"

    if current > resistance * 1.03:
        return "watching"

    return "none"

# ── R:R計算 ─────────────────────────────────────────────────────────────────

def _nearest_swing_high_above(H, i, current, lookback=SWING_LOOKBACK, wing=SWING_WING):
    """直近 lookback 日内のスイング高値(ピボット)のうち、現在値より上で最も近いものを返す。

    「高値付近で高勝率に利確」のエッジに合わせ、遠い60日高値ではなく
    最寄りのレジスタンス（直近スイング高値）をターゲットにする。
    見つからなければ None。
    """
    start = max(wing, i - lookback)
    candidates = []
    for j in range(start, i - wing + 1):
        window = H[j - wing:j + wing + 1]
        if window and H[j] == max(window) and H[j] > current:
            candidates.append(H[j])
    if candidates:
        return min(candidates)          # 現在値より上で最も近い高値
    # フォールバック: 直近 lookback 日の高値が現在値より上ならそれを使う
    recent_high = max(H[max(0, i - lookback):i + 1])
    return recent_high if recent_high > current else None


def _calc_rr(C, H, L, atr_arr, ema20, ema50, support_price, i, lookback=SWING_LOOKBACK):
    current = C[i]
    atr_v = atr_arr[i]
    if atr_v is None or atr_v <= 0:
        return None, None, None, None, None

    target = _nearest_swing_high_above(H, i, current, lookback=lookback)
    if target is None:
        return None, None, None, None, None
    tp1 = target * 0.99

    if tp1 <= current:
        return None, None, None, None, None

    if support_price and support_price < current:
        sl = support_price - 0.1 * atr_v
    else:
        swing_low = min(L[max(0, i-20):i+1])
        sl = swing_low - 0.1 * atr_v

    risk   = current - sl
    reward = tp1 - current

    if risk <= 0:
        return None, None, None, None, None

    rr = min(reward / risk, RR_CAP)   # 極端値を上限でクランプ
    return round(rr, 2), round(tp1, 2), round(sl, 2), round(atr_v, 4), round(target, 2)

# ── フィボナッチコンフルエンス ────────────────────────────────────────────────

def _fib_confluence(H, L, C, ema20, ema50, i, lookback=120):
    start = max(0, i - lookback)
    swing_low  = min(L[start:i+1])
    swing_high = max(H[start:i+1])

    if swing_high <= swing_low:
        return None

    current = C[i]
    fib_levels = {
        "38.2%": swing_high - (swing_high - swing_low) * 0.382,
        "50.0%": swing_high - (swing_high - swing_low) * 0.500,
        "61.8%": swing_high - (swing_high - swing_low) * 0.618,
    }

    for label, fib_price in fib_levels.items():
        if abs(current - fib_price) / fib_price > 0.02:
            continue
        for ema, ema_name in [(ema20[i], "20EMA"), (ema50[i], "50EMA")]:
            if ema is not None and abs(ema - fib_price) / fib_price < 0.02:
                return label, round(fib_price, 2)
        return label, round(fib_price, 2)

    return None

# ── イントラデイ（1H/4H）ヘルパー ───────────────────────────────────────────────

def _fetch_intraday_batch(tickers):
    if not _YF_AVAILABLE or not tickers:
        return None
    try:
        if len(tickers) == 1:
            df = yf.download(tickers[0], period="7d", interval="1h",
                             auto_adjust=True, progress=False)
            return {tickers[0]: df} if not df.empty else None
        raw = yf.download(
            tickers=" ".join(tickers),
            period="7d",
            interval="1h",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        result = {}
        for t in tickers:
            try:
                df = raw[t] if t in raw else None
                if df is not None and not df.empty:
                    result[t] = df
            except Exception:
                pass
        return result if result else None
    except Exception as e:
        print(f"[Logic2] 1H data fetch error: {e}")
        return None


def _extract_ticker_1h(data_dict, ticker):
    if data_dict is None:
        return None
    try:
        df = data_dict.get(ticker)
        if df is None or df.empty:
            return None
        df = df.dropna(subset=["Close"])
        if df.empty:
            return None
        result = []
        for _, row in df.iterrows():
            result.append({
                "open":   float(row["Open"]),
                "high":   float(row["High"]),
                "low":    float(row["Low"]),
                "close":  float(row["Close"]),
                "volume": float(row["Volume"]),
            })
        return result if len(result) >= 8 else None
    except Exception:
        return None


def _resample_4h(rows_1h):
    bars = []
    for i in range(0, len(rows_1h) - 3, 4):
        group = rows_1h[i:i + 4]
        bars.append({
            "open":   group[0]["open"],
            "high":   max(b["high"]   for b in group),
            "low":    min(b["low"]    for b in group),
            "close":  group[-1]["close"],
            "volume": sum(b["volume"] for b in group),
        })
    return bars


def _is_pin_bar_strict(bar):
    """厳格ピンバー: 下ヒゲ ≥ 実体の3倍、陽線。"""
    body = abs(bar["close"] - bar["open"])
    lower_wick = min(bar["close"], bar["open"]) - bar["low"]
    upper_wick = bar["high"] - max(bar["close"], bar["open"])
    if body < 1e-8:
        body = (bar["high"] - bar["low"]) * 0.1
    return (bar["close"] > bar["open"] and
            lower_wick >= 3 * body and
            lower_wick >= 2 * (upper_wick + 1e-8))


def _is_bull_engulfing_strict(prev, curr):
    """厳格エンガルフィング: 前足のレンジ全体（高値〜安値）を包み込む。"""
    if prev is None:
        return False
    return (prev["close"] < prev["open"] and       # 前足: 陰線
            curr["close"] > curr["open"] and        # 当足: 陽線
            curr["open"]  <= prev["low"] and         # 前足安値以下で寄り付き
            curr["close"] >= prev["high"])            # 前足高値以上で引け


def _is_inverse_hammer_strict(bar):
    """厳格逆ハンマー: 上ヒゲ ≥ 実体の3倍（標準は2倍）、下ヒゲ極小。"""
    body = abs(bar["close"] - bar["open"])
    upper_wick = bar["high"] - max(bar["close"], bar["open"])
    lower_wick = min(bar["close"], bar["open"]) - bar["low"]
    if body < 1e-8:
        body = (bar["high"] - bar["low"]) * 0.1
    return (upper_wick >= 3 * body and
            lower_wick <= body * 0.3)


def _is_piercing_line_strict(prev, curr):
    """厳格切り込み線: 前足の61.8%以上まで戻す（標準は50%）。"""
    if prev is None:
        return False
    prev_threshold = prev["open"] - (prev["open"] - prev["close"]) * 0.382
    return (prev["close"] < prev["open"] and
            curr["close"] > curr["open"] and
            curr["open"]  < prev["close"] and
            curr["close"] >= prev_threshold and
            curr["close"] < prev["open"])


def _is_three_white_soldiers_strict(b1, b2, b3):
    """厳格赤三兵: 各足の実体が前足の高値〜安値レンジの50%以上。"""
    if b1 is None or b2 is None or b3 is None:
        return False
    if not (b1["close"] > b1["open"] and
            b2["close"] > b2["open"] and
            b3["close"] > b3["open"]):
        return False
    if not (b2["close"] > b1["close"] and b3["close"] > b2["close"]):
        return False
    if not (b2["open"] >= b1["open"] and b3["open"] >= b2["open"]):
        return False
    # 各足の実体がレンジの50%以上（大きな実体を要求）
    for b in [b1, b2, b3]:
        body = b["close"] - b["open"]
        rng  = b["high"] - b["low"]
        if rng < 1e-8 or body / rng < 0.5:
            return False
    return True


def _is_morning_star_strict(b1, b2, b3):
    """厳格明けの明星: b2の実体がb1の30%未満（標準は40%）、b3がb1の60%以上戻す。"""
    if b1 is None or b2 is None or b3 is None:
        return False
    b1_body = abs(b1["close"] - b1["open"])
    b2_body = abs(b2["close"] - b2["open"])
    b3_body = abs(b3["close"] - b3["open"])
    if b1_body < 1e-8:
        return False
    return (b1["close"] < b1["open"] and
            b2_body < b1_body * 0.3 and              # b2実体がb1の30%未満（厳格化）
            b3["close"] > b3["open"] and
            b3_body > b1_body * 0.6 and              # b3がb1の60%以上（厳格化）
            b3["close"] > (b1["open"] + b1["close"]) / 2)


def _detect_4h_trigger_strict(rows_4h, support_price):
    """
    厳格4Hトリガー検出。
    - サポート価格の ±3% 以内
    - ピンバー: 3倍ヒゲ
    - エンガルフィング: 全レンジ包み込み
    - 出来高: 2.0倍
    - 逆ハンマー: 3倍上ヒゲ
    - 切り込み線: 61.8%戻し
    - 赤三兵: 実体レンジ比50%以上
    - 明けの明星: b2実体30%未満+b3が60%戻し
    Returns: list[str] or None
    """
    if not rows_4h or len(rows_4h) < 4:
        return None

    vols = [r["volume"] for r in rows_4h]
    vol_ma = sum(vols) / len(vols) if vols else 1

    recent = rows_4h[-6:] if len(rows_4h) >= 6 else rows_4h

    # ダブルボトム検出
    lows_all = [r["low"] for r in rows_4h]
    sl_idxs = _find_swing_lows(lows_all, lookback=1)
    double_bottom = False
    if len(sl_idxs) >= 2:
        l1, l2 = lows_all[sl_idxs[-2]], lows_all[sl_idxs[-1]]
        if l1 > 0 and abs(l1 - l2) / l1 < 0.015:
            double_bottom = True

    triggers_found = []  # 複数トリガーを記録（提案C用）

    for j in range(len(recent) - 1, -1, -1):
        bar  = recent[j]
        prev = recent[j - 1] if j > 0 else None
        prev2 = recent[j - 2] if j >= 2 else None

        # サポート近傍チェック（±3% — 厳格化）
        mid = (bar["high"] + bar["low"]) / 2
        if support_price > 0 and abs(mid - support_price) / support_price > 0.03:
            continue

        # 1本足パターン
        if _is_pin_bar_strict(bar):
            triggers_found.append("ピンバー(4H厳選)")
        if _is_inverse_hammer_strict(bar):
            triggers_found.append("逆ハンマー(4H厳選)")

        # 2本足パターン
        if prev and _is_bull_engulfing_strict(prev, bar):
            triggers_found.append("強気エンガルフィング(4H厳選)")
        if prev and _is_piercing_line_strict(prev, bar):
            triggers_found.append("切り込み線(4H厳選)")

        # 出来高急増
        if bar["volume"] >= vol_ma * 2.0 and bar["close"] > bar["open"]:
            triggers_found.append("出来高急増(4H厳選)")

        # 3本足パターン
        if prev and prev2 and _is_morning_star_strict(prev2, prev, bar):
            triggers_found.append("明けの明星(4H厳選)")
        if prev and prev2 and _is_three_white_soldiers_strict(prev2, prev, bar):
            triggers_found.append("赤三兵(4H厳選)")

        if triggers_found:
            break

    if double_bottom:
        # ダブルボトムのサポート近傍チェック
        last_sl_low = lows_all[sl_idxs[-1]]
        if support_price > 0 and abs(last_sl_low - support_price) / support_price <= 0.03:
            triggers_found.append("ダブルボトム(4H厳選)")

    return triggers_found if triggers_found else None


def _detect_4h_structure(rows_4h, support_price):
    if not rows_4h or len(rows_4h) < 4:
        return "neutral"

    recent = rows_4h[-4:]
    closes = [b["close"] for b in recent]
    n = len(closes)

    xs = list(range(n))
    x_mean = sum(xs) / n
    c_mean = sum(closes) / n
    num   = sum((xs[i] - x_mean) * (closes[i] - c_mean) for i in range(n))
    denom = sum((xs[i] - x_mean) ** 2 for i in range(n))
    slope = num / denom if denom != 0 else 0

    slope_pct = slope / c_mean if c_mean != 0 else 0

    last_bar = recent[-1]
    is_bull_candle = last_bar["close"] > last_bar["open"]
    is_bear_candle = last_bar["close"] < last_bar["open"]

    if slope_pct >= 0.001 and is_bull_candle:
        return "bullish"
    if slope_pct <= -0.001 and is_bear_candle:
        return "bearish"
    return "neutral"


# ── MACDダイバージェンス（強気）検出 ─────────────────────────────────────────

def _macd_bull_divergence(hist, C, i, lookback=25):
    if i < lookback + 5:
        return False

    prev_low_idx = max(range(max(0, i-lookback), i-3),
                       key=lambda j: -C[j], default=-1)
    if prev_low_idx < 0:
        return False

    curr_low = min(C[max(0, i-3):i+1])
    if curr_low >= C[prev_low_idx]:
        return False

    if hist[i] is None or hist[prev_low_idx] is None:
        return False

    return hist[i] > hist[prev_low_idx]


# ── 信頼度ボーナス算出（提案C）────────────────────────────────────────────────

def _calc_trigger_confidence_bonus(triggers, rsi_val, support_price, current_price):
    """
    トリガーの質に応じた信頼度ボーナスを算出。
    - ピンバー + 出来高急増 → +0.10
    - 強気エンガルフィング + RSI < 40 → +0.10
    - ダブルボトム（サポート乖離 < 1%）→ +0.15
    Returns: bonus (float)
    """
    if not triggers:
        return 0.0

    bonus = 0.0
    trigger_names = set(triggers)

    # ピンバー + 出来高急増の同時発生
    has_pin = any("ピンバー" in t for t in trigger_names)
    has_vol = any("出来高急増" in t for t in trigger_names)
    if has_pin and has_vol:
        bonus += 0.10

    # 強気エンガルフィング + RSI < 40
    has_engulf = any("エンガルフィング" in t for t in trigger_names)
    if has_engulf and rsi_val is not None and rsi_val < 40:
        bonus += 0.10

    # ダブルボトム + サポート近傍（< 1%）
    has_db = any("ダブルボトム" in t for t in trigger_names)
    if has_db and support_price and current_price:
        dist = abs(current_price - support_price) / current_price
        if dist < 0.01:
            bonus += 0.15

    return bonus


# ── メインスキャン ─────────────────────────────────────────────────────────────

def _build_sector_map(cur, tickers=None):
    """全テーブルからセクター情報を一括取得し、不足分はFMP APIで補完。"""
    sector_map = {}
    for tbl in ["universe", "fundamentals", "weekly_picks"]:
        try:
            cur.execute(f"SELECT ticker, sector FROM {tbl} WHERE sector IS NOT NULL AND sector != ''")
            for r in cur.fetchall():
                sector_map[r["ticker"]] = r["sector"]
        except Exception:
            pass

    if tickers and FMP_API_KEY:
        missing = [t for t in tickers if t not in sector_map]
        if missing:
            print(f"[Logic2] FMP APIでセクター補完: {len(missing)}銘柄")
            for i in range(0, len(missing), 50):
                batch = missing[i:i+50]
                try:
                    url = f"{FMP_BASE_URL}/profile?symbol={','.join(batch)}&apikey={FMP_API_KEY}"
                    resp = requests.get(url, timeout=15)
                    if resp.status_code == 200:
                        for item in resp.json():
                            sym = item.get("symbol", "")
                            sec = item.get("sector", "")
                            if sym and sec:
                                sector_map[sym] = SECTOR_DISPLAY.get(sec, sec)
                except Exception as e:
                    print(f"[Logic2] FMP sector fetch error: {e}")

    return sector_map


def run():
    print("[Logic2] 厳選押し目買いスクリーニング開始...")
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        SELECT ticker, COUNT(*) as cnt
        FROM price_data
        GROUP BY ticker
        HAVING COUNT(*) >= ?
    """, (MIN_BARS_DAILY,))
    tickers = [r["ticker"] for r in cur.fetchall()]
    print(f"[Logic2] 対象銘柄数: {len(tickers)}")

    sector_map = _build_sector_map(cur, tickers)
    print(f"[Logic2] セクターマッピング: {len(sector_map)}銘柄")

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

            # ── インジケーター計算 ──────────────────────────────────────────────
            ema20  = _ema(C, 20)
            ema50  = _ema(C, 50)
            ema200 = _ema(C, 200)
            atr_arr = _atr(H, L, C)
            rsi_arr = _rsi(C)
            _, _, hist_arr = _macd(C)
            vol_ma20 = _sma(V, 20)

            # ── 週足EMA計算 ───────────────────────────────────────────────────
            weekly = _resample_weekly(rows)
            wC = [w["close"] for w in weekly]
            w_ema20  = _ema(wC, 20)
            w_ema200 = _ema(wC, 200) if len(wC) >= 200 else _ema(wC, min(len(wC)//2, 100))
            wi = len(wC) - 1

            # ═══════════════════════════════════════════════════════════════════
            # 一次フィルター
            # ═══════════════════════════════════════════════════════════════════

            # [F1] 週足 20EMA > 200EMA
            if w_ema20[wi] is None or w_ema200[wi] is None:
                continue
            if w_ema20[wi] <= w_ema200[wi]:
                continue

            # [F2] 日足パーフェクトオーダー（または準成立）
            e20, e50, e200 = ema20[i], ema50[i], ema200[i]
            if any(v is None for v in [e20, e50, e200]):
                continue
            if not (C[i] > e20 and e20 > e200):
                continue
            perfect_order = "full" if (C[i] > e20 > e50 > e200) else "quasi"

            # [F3] 過去3ヶ月騰落率 > 0%
            if i < PERF_3M_DAYS:
                continue
            perf_3m = (C[i] - C[i - PERF_3M_DAYS]) / C[i - PERF_3M_DAYS] * 100
            if perf_3m <= 0:
                continue

            perf_6m = (C[i] - C[i - PERF_6M_DAYS]) / C[i - PERF_6M_DAYS] * 100 if i >= PERF_6M_DAYS else None

            # [F4] 20日平均出来高 ≥ 50万株
            avg_vol = vol_ma20[i]
            if avg_vol is None or avg_vol < MIN_AVG_VOLUME:
                continue

            first_pass += 1

            # ═══════════════════════════════════════════════════════════════════
            # 二次フィルター
            # ═══════════════════════════════════════════════════════════════════

            # [S1] ダウ理論
            dow = _dow_theory(H, L, C, i)
            if dow == "broken":
                continue

            # [S2] サポートライン
            support_price, confluence, support_reasons = _find_support_level(
                H, L, C, ema20, ema50, atr_arr, i
            )
            if support_price is None or confluence == 0:
                continue

            # [S3] レジサポ転換
            reji_sapo = _detect_reji_sapo(H, L, C, i)

            # [S4] R:R計算
            rr, tp1_price, sl_price, atr_v, target_price = _calc_rr(C, H, L, atr_arr, ema20, ema50, support_price, i)
            if rr is None or rr < RR_MIN:
                continue

            second_pass += 1

            # ═══════════════════════════════════════════════════════════════════
            # ボーナスフラグ
            # ═══════════════════════════════════════════════════════════════════

            rsi_now = rsi_arr[i]
            rsi_flag = rsi_now is not None and 30 <= rsi_now <= 50

            macd_div = _macd_bull_divergence(hist_arr, C, i)

            fib_result = _fib_confluence(H, L, C, ema20, ema50, i)
            fib_label  = f"{fib_result[0]}/${fib_result[1]}" if fib_result else None

            bonus_count = sum([rsi_flag, macd_div, fib_result is not None])

            # ═══════════════════════════════════════════════════════════════════
            # 総合判定
            # ═══════════════════════════════════════════════════════════════════

            if reji_sapo == "confirmed" and rr >= RR_MIN and bonus_count >= 1:
                verdict = "最優先候補"
                confidence = min(0.95, 0.70 + 0.05 * bonus_count + (0.05 if rr >= RR_GOOD else 0))
            elif rr >= RR_MIN and confluence >= 2:
                verdict = "監視リスト入り"
                confidence = min(0.80, 0.55 + 0.05 * bonus_count + (0.05 if rr >= RR_GOOD else 0))
            elif rr >= RR_MIN:
                verdict = "監視リスト入り"
                confidence = 0.50 + 0.03 * bonus_count
            else:
                continue

            adopted += 1

            # 日足チャートパターン検出（厳格版）
            chart_patterns = _detect_daily_chart_patterns_strict(H, L, C, i)
            chart_pattern = ", ".join(chart_patterns) if chart_patterns else None

            # セクター（起動時に一括取得済み）
            sector = sector_map.get(ticker)

            # 保有日数推定
            if atr_v and atr_v > 0 and tp1_price and C[i]:
                holding_days = min(8, max(3, round(abs(tp1_price - C[i]) / (atr_v * 0.5))))
            else:
                holding_days = 8

            exit_rules = [
                f"SL: ${sl_price}（サポート少し下に固定、エントリーから1R）",
                f"TP1: 直近スイング高値手前 ${tp1_price} で2/3利確",
                "残り1/3: 20日EMAを終値で割るまでトレール",
                "RRゲート: TP1まで1.5R未満は不採用",
                "保有上限: 8営業日経過で含み損なら全決済",
            ]

            picks.append({
                "ticker":          ticker,
                "scan_date":       date.today().isoformat(),
                "perfect_order":   perfect_order,
                "perf_3m":         round(perf_3m, 2),
                "perf_6m":         round(perf_6m, 2) if perf_6m is not None else None,
                "avg_vol_20d":     round(avg_vol),
                "dow_trend":       dow,
                "support_price":   round(support_price, 2),
                "confluence":      confluence,
                "support_reasons": json.dumps(support_reasons, ensure_ascii=False),
                "reji_sapo":       reji_sapo,
                "risk_reward":     rr,
                "entry_price":     round(C[i], 2),
                "stop_price":      sl_price,
                "tp1_price":       tp1_price,
                "target_price":    target_price,
                "rsi":             round(rsi_now, 1) if rsi_now else None,
                "rsi_flag":        1 if rsi_flag else 0,
                "macd_div_flag":   1 if macd_div else 0,
                "fib_confluence":  fib_label,
                "atr":             round(atr_v, 4) if atr_v else None,
                "verdict":         verdict,
                "confidence":      round(confidence, 3),
                "composite_score": round(confidence * 100, 1),
                "sector":          sector,
                "current_price":   round(C[i], 2),
                "holding_days_est": holding_days,
                "signals_json":    json.dumps(exit_rules, ensure_ascii=False),
                "chart_pattern":   chart_pattern,
            })

        except Exception as e:
            print(f"[Logic2] {ticker} エラー: {e}")

    # ── イントラデイ（4H）分析 ─────────────────────────────────────────────
    if picks:
        candidate_tickers = [p["ticker"] for p in picks]
        print(f"[Logic2] 4Hデータ取得中... {len(candidate_tickers)}銘柄")
        intraday_dict = _fetch_intraday_batch(candidate_tickers)

        filtered_picks = []  # 提案A: トリガー or サポート接近のみ残す

        for p in picks:
            rows_1h = _extract_ticker_1h(intraday_dict, p["ticker"])
            rows_4h = _resample_4h(rows_1h) if rows_1h else None

            # サポートまでの距離（%）
            price_to_support = None
            if p["support_price"] and p["current_price"]:
                price_to_support = round(
                    (p["current_price"] - p["support_price"]) / p["current_price"] * 100, 1
                )
            p["price_to_support_pct"] = price_to_support

            # 4H構造
            p["h4_structure"] = _detect_4h_structure(rows_4h, p["support_price"]) if rows_4h else "neutral"

            # 厳格4Hトリガー（提案B）
            triggers = _detect_4h_trigger_strict(rows_4h, p["support_price"]) if rows_4h else None
            p["h4_trigger"] = triggers[0] if triggers else None
            p["h4_triggers_all"] = json.dumps(triggers or [], ensure_ascii=False)

            # 信頼度ボーナス（提案C）
            trigger_bonus = _calc_trigger_confidence_bonus(
                triggers, p.get("rsi"), p["support_price"], p["current_price"]
            )
            p["confidence"] = round(min(0.99, p["confidence"] + trigger_bonus), 3)
            p["composite_score"] = round(p["confidence"] * 100, 1)
            p["trigger_bonus"] = round(trigger_bonus, 3)

            # 判定をインデイタイムフレームで更新
            near_support = price_to_support is not None and price_to_support <= 3.0
            has_trigger  = triggers is not None and len(triggers) > 0
            has_chart_pattern = bool(p.get("chart_pattern"))

            if (has_trigger or has_chart_pattern) and near_support:
                p["verdict"] = "最優先候補"
            elif has_chart_pattern:
                p["verdict"] = "最優先候補"
            elif near_support:
                p["verdict"] = "サポート接近中"
            else:
                # 提案A: 押し目待ち（トリガーなし + サポートから遠い）は除外
                continue

            filtered_picks.append(p)

        picks = filtered_picks
    else:
        picks = []

    # ── 保存 ────────────────────────────────────────────────────────────────
    cur.execute("DELETE FROM logic2_picks")
    for p in picks:
        cur.execute("""
            INSERT INTO logic2_picks
                (ticker, scan_date, perfect_order, perf_3m, perf_6m, avg_vol_20d,
                 dow_trend, support_price, confluence, support_reasons, reji_sapo,
                 risk_reward, entry_price, stop_price, tp1_price, target_price,
                 rsi, rsi_flag, macd_div_flag, fib_confluence, atr,
                 verdict, confidence, composite_score, sector, current_price,
                 holding_days_est, signals_json,
                 price_to_support_pct, h4_trigger, h4_structure,
                 h4_triggers_all, trigger_bonus, chart_pattern)
            VALUES
                (:ticker, :scan_date, :perfect_order, :perf_3m, :perf_6m, :avg_vol_20d,
                 :dow_trend, :support_price, :confluence, :support_reasons, :reji_sapo,
                 :risk_reward, :entry_price, :stop_price, :tp1_price, :target_price,
                 :rsi, :rsi_flag, :macd_div_flag, :fib_confluence, :atr,
                 :verdict, :confidence, :composite_score, :sector, :current_price,
                 :holding_days_est, :signals_json,
                 :price_to_support_pct, :h4_trigger, :h4_structure,
                 :h4_triggers_all, :trigger_bonus, :chart_pattern)
        """, p)
    conn.commit()
    conn.close()

    # ── バックテスト用シグナルログ ──────────────────────────────────────────
    try:
        from backend.services.signal_tracker import log_signals
        log_signals("logic2", [{**p, "direction": "LONG"} for p in picks])
    except Exception as e:
        print(f"[Logic2] signal_log 記録エラー: {e}")

    verdict_order = {"最優先候補": 0, "サポート接近中": 1}
    picks.sort(key=lambda x: (
        verdict_order.get(x["verdict"], 3),
        -x["risk_reward"]
    ))
    print(f"[Logic2] 完了 — 一次通過:{first_pass} 二次通過:{second_pass} 採用:{adopted} 最終:{len(picks)}")
    for p in picks[:5]:
        trigger = p.get("h4_trigger") or "-"
        dist    = p.get("price_to_support_pct")
        dist_s  = f"{dist:.1f}%" if dist is not None else "N/A"
        bonus   = p.get("trigger_bonus", 0)
        print(f"  {p['ticker']:8s} {p['verdict']} RR={p['risk_reward']:.2f} dist={dist_s} trigger={trigger} bonus=+{bonus:.2f}")
