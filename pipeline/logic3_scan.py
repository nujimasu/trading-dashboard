"""
ロジック３スキャンエンジン — 押し目買い戦略（4Hトリガー版）

ロジック４と同一の一次・二次フィルター＋ボーナスフラグを使用。
違い: 1Hトリガーの代わりに4Hバーでプライスアクション（ピンバー、
エンガルフィング、出来高急増、ダブルボトム）を検出する。

戦略の前提:
  - スイングトレード（数日〜数週間）
  - ロング（買い）のみ
  - 基本戦略: 押し目買い（上昇トレンド中の一時的下落からの反発）

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
  4. R:R計算（TP=直近高値×0.99, SL=サポート×0.99またはサポート−ATR）

ボーナスフラグ:
  - RSI 30〜50
  - MACDダイバージェンス（強気）
  - フィボナッチコンフルエンス（38.2/50/61.8%）

判定:
  - 最優先候補: 一次全通過 + レジサポ転換確認 + R:R≥1.5 + ボーナス1件以上
  - 監視リスト入り: 一次全通過 + R:R≥1.5 + サポート明確
  - 見送り: R:R<1.5 または条件未達
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
    """日足OHLCVを週足に変換（各週の最終営業日終値を使用）"""
    weeks = defaultdict(list)
    for r in rows:
        d = date.fromisoformat(r["date"])
        # ISO週番号をキーに
        iso = d.isocalendar()
        key = (iso[0], iso[1])  # (year, week)
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
    """スイングハイのインデックスリストを返す"""
    highs = []
    for i in range(lookback, len(H) - lookback):
        if H[i] == max(H[i-lookback:i+lookback+1]):
            highs.append(i)
    return highs

def _find_swing_lows(L, lookback=3):
    """スイングローのインデックスリストを返す"""
    lows = []
    for i in range(lookback, len(L) - lookback):
        if L[i] == min(L[i-lookback:i+lookback+1]):
            lows.append(i)
    return lows

# ── 日足チャートパターン検出 ──────────────────────────────────────────────────

def _detect_cup_and_handle(H, L, C, i, lookback=60):
    """
    カップウィズハンドル: U字型の底 + 小さな戻り → ブレイクアウト
    lookback バー内でカップ形成を検出。
    """
    if i < lookback:
        return False
    start = i - lookback

    # カップの左リム（開始点の高値）
    left_rim_idx = start
    left_rim = H[start]
    for j in range(start, start + lookback // 4):
        if H[j] > left_rim:
            left_rim = H[j]
            left_rim_idx = j

    # カップの底（中央付近の安値）
    cup_mid_start = start + lookback // 4
    cup_mid_end = start + lookback * 3 // 4
    if cup_mid_end > i:
        cup_mid_end = i
    cup_bottom = min(L[cup_mid_start:cup_mid_end]) if cup_mid_start < cup_mid_end else L[i]
    cup_bottom_idx = cup_mid_start + L[cup_mid_start:cup_mid_end].index(cup_bottom) if cup_mid_start < cup_mid_end else i

    # カップの深さ: 左リムから10〜35%の下落
    depth = (left_rim - cup_bottom) / left_rim if left_rim > 0 else 0
    if depth < 0.08 or depth > 0.40:
        return False

    # 右リム: カップ底以降の高値が左リムの95%以上まで回復
    right_section = H[cup_bottom_idx:i + 1]
    if not right_section:
        return False
    right_rim = max(right_section)
    if right_rim < left_rim * 0.93:
        return False

    # ハンドル: 直近5〜15バーで小さな下落（右リムから3〜12%）
    handle_bars = min(15, i - cup_bottom_idx)
    if handle_bars < 3:
        return False
    handle_low = min(L[i - handle_bars:i + 1])
    handle_depth = (right_rim - handle_low) / right_rim if right_rim > 0 else 0
    if handle_depth < 0.02 or handle_depth > 0.15:
        return False

    # 現在値がハンドルの高値付近（ブレイクアウト圏）
    handle_high = max(H[i - handle_bars:i + 1])
    if C[i] >= handle_high * 0.98:
        return True

    return False


def _detect_ascending_triangle(H, L, C, i, lookback=30):
    """
    アセンディングトライアングル: 水平レジスタンス + 切り上がるサポート
    """
    if i < lookback:
        return False
    start = i - lookback

    # レジスタンス: 直近の高値が水平（±1.5%以内）
    swing_highs = _find_swing_highs(H[start:i + 1], lookback=2)
    if len(swing_highs) < 2:
        return False

    high_vals = [H[start + idx] for idx in swing_highs[-3:]]
    avg_high = sum(high_vals) / len(high_vals)
    if any(abs(h - avg_high) / avg_high > 0.02 for h in high_vals):
        return False

    # サポート: スイングローが切り上がっている
    swing_lows = _find_swing_lows(L[start:i + 1], lookback=2)
    if len(swing_lows) < 2:
        return False

    low_vals = [L[start + idx] for idx in swing_lows[-3:]]
    ascending = all(low_vals[j] <= low_vals[j + 1] for j in range(len(low_vals) - 1))
    if not ascending:
        return False

    # 現在値がレジスタンス付近（±2%）
    if C[i] >= avg_high * 0.97:
        return True

    return False


def _detect_inverse_head_shoulders(H, L, C, i, lookback=50):
    """
    逆ヘッドアンドショルダー: 3つの谷（中央が最深）→ ネックラインブレイク
    """
    if i < lookback:
        return False
    start = i - lookback

    swing_lows = _find_swing_lows(L[start:i + 1], lookback=3)
    if len(swing_lows) < 3:
        return False

    # 直近3つのスイングロー
    s1_idx, s2_idx, s3_idx = swing_lows[-3], swing_lows[-2], swing_lows[-1]
    s1 = L[start + s1_idx]
    s2 = L[start + s2_idx]  # ヘッド（最深）
    s3 = L[start + s3_idx]

    # ヘッド（中央）が両肩より深い
    if not (s2 < s1 and s2 < s3):
        return False

    # 両肩がほぼ同じ高さ（±5%）
    shoulder_avg = (s1 + s3) / 2
    if abs(s1 - s3) / shoulder_avg > 0.06:
        return False

    # ネックライン: 左肩と右肩の間の高値を結ぶ
    between_1_2 = H[start + s1_idx:start + s2_idx + 1]
    between_2_3 = H[start + s2_idx:start + s3_idx + 1]
    if not between_1_2 or not between_2_3:
        return False
    neckline_l = max(between_1_2)
    neckline_r = max(between_2_3)
    neckline = min(neckline_l, neckline_r)

    # 現在値がネックライン付近またはブレイク
    if C[i] >= neckline * 0.98:
        return True

    return False


def _detect_bull_pennant(H, L, C, i, lookback=30):
    """
    ブルペナント: 急騰（ポール）後の三角持ち合い → 上放れ
    """
    if i < lookback:
        return False

    # ポール: lookback〜lookback//2前に大きな上昇（10%以上）
    pole_start = i - lookback
    pole_end = i - lookback // 2
    pole_low = min(L[pole_start:pole_end + 1])
    pole_high = max(H[pole_start:pole_end + 1])

    pole_gain = (pole_high - pole_low) / pole_low if pole_low > 0 else 0
    if pole_gain < 0.08:
        return False

    # ペナント: ポール後のバーで高値が切り下がり、安値が切り上がる（収束）
    pennant_start = pole_end
    pennant_bars = i - pennant_start
    if pennant_bars < 4:
        return False

    pennant_highs = [H[j] for j in range(pennant_start, i + 1)]
    pennant_lows = [L[j] for j in range(pennant_start, i + 1)]

    # 高値が全体的に下降傾向
    high_declining = pennant_highs[-1] < pennant_highs[0]
    # 安値が全体的に上昇傾向
    low_rising = pennant_lows[-1] > pennant_lows[0]

    if not (high_declining and low_rising):
        return False

    # レンジが縮小している
    early_range = pennant_highs[0] - pennant_lows[0]
    late_range = pennant_highs[-1] - pennant_lows[-1]
    if early_range <= 0 or late_range / early_range > 0.7:
        return False

    # 現在値がペナント上限付近
    if C[i] >= pennant_highs[-1] * 0.99:
        return True

    return False


def _detect_falling_wedge(H, L, C, i, lookback=30):
    """
    フォーリングウェッジ（強気）: 高値・安値ともに下降するが収束 → 上方ブレイク
    """
    if i < lookback:
        return False
    start = i - lookback

    # スイングハイ・ローを検出
    swing_highs = _find_swing_highs(H[start:i + 1], lookback=2)
    swing_lows = _find_swing_lows(L[start:i + 1], lookback=2)

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return False

    # 高値が切り下がっている
    sh_vals = [H[start + idx] for idx in swing_highs[-3:]]
    highs_declining = all(sh_vals[j] > sh_vals[j + 1] for j in range(len(sh_vals) - 1))

    # 安値も切り下がっている
    sl_vals = [L[start + idx] for idx in swing_lows[-3:]]
    lows_declining = all(sl_vals[j] > sl_vals[j + 1] for j in range(len(sl_vals) - 1))

    if not (highs_declining and lows_declining):
        return False

    # ウェッジの収束: 高値と安値の差が縮小
    early_spread = sh_vals[0] - sl_vals[0] if sl_vals[0] < sh_vals[0] else 0
    late_spread = sh_vals[-1] - sl_vals[-1] if sl_vals[-1] < sh_vals[-1] else 0
    if early_spread <= 0 or late_spread / early_spread > 0.6:
        return False

    # 現在値がウェッジ上限をブレイク（直近スイングハイを上回る）
    if C[i] > sh_vals[-1] * 0.99:
        return True

    return False


def _detect_daily_chart_patterns(H, L, C, i):
    """
    日足チャートパターンを検出。複数パターンのリストを返す。
    """
    patterns = []
    if _detect_cup_and_handle(H, L, C, i):
        patterns.append("カップウィズハンドル")
    if _detect_ascending_triangle(H, L, C, i):
        patterns.append("アセンディングトライアングル")
    if _detect_inverse_head_shoulders(H, L, C, i):
        patterns.append("逆ヘッドアンドショルダー")
    if _detect_bull_pennant(H, L, C, i):
        patterns.append("ブルペナント")
    if _detect_falling_wedge(H, L, C, i):
        patterns.append("フォーリングウェッジ")
    return patterns


# ── ダウ理論判定 ─────────────────────────────────────────────────────────────

def _dow_theory(H, L, C, i, lookback=60):
    """
    Returns: ('strong', 'early', 'broken')
    """
    start = max(0, i - lookback)
    sh = _find_swing_highs(H[start:i+1])
    sl = _find_swing_lows(L[start:i+1])

    if len(sh) < 2 or len(sl) < 2:
        return "early"

    # 直近2つのスイングハイ・ロー
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
    """
    サポートレベルと根拠の数（コンフルエンス）を返す。
    Returns: (support_price, confluence_count, support_reasons[])
    """
    current = C[i]
    candidates = []  # (price, reason)

    # 1. EMA20サポート
    if ema20[i] is not None and ema20[i] < current * 1.05:
        candidates.append((ema20[i], "20EMA"))

    # 2. EMA50サポート
    if ema50[i] is not None and ema50[i] < current * 1.08:
        candidates.append((ema50[i], "50EMA"))

    # 3. 直近スイングロー（過去60バー）
    start = max(0, i - 60)
    sl_idxs = _find_swing_lows(L[start:i+1])
    if sl_idxs:
        # 直近3つのスイングローから現在値より下のものを採用
        for idx in reversed(sl_idxs[-3:]):
            sl_price = L[start + idx]
            if sl_price < current * 0.99:
                candidates.append((sl_price, f"スイングロー${sl_price:.2f}"))
                break

    # 4. 直近水平サポート（過去20〜60バー内で複数回反応した価格帯）
    recent_lows = sorted([L[j] for j in range(start, i)], reverse=True)
    if recent_lows:
        # 現在値の3〜15%下の価格帯クラスタリング
        for low in recent_lows:
            pct = (current - low) / current
            if 0.02 < pct < 0.15:
                # 同じ価格帯（±1%）に複数本集まっているかチェック
                cluster = [l for l in recent_lows if abs(l - low) / low < 0.01]
                if len(cluster) >= 3:
                    candidates.append((low, f"水平サポート${low:.2f}"))
                    break

    if not candidates:
        return None, 0, []

    # 最も近い（現在値に近い）サポートを選択
    below = [(p, r) for p, r in candidates if p < current]
    if not below:
        return None, 0, []

    below.sort(key=lambda x: -(x[0]))  # 現在値に最も近いものを優先
    best_price = below[0][0]

    # コンフルエンス: best_priceの±2%以内にある根拠数
    confluent = [(p, r) for p, r in candidates if abs(p - best_price) / best_price < 0.02]
    reasons = [r for _, r in confluent]

    return best_price, len(confluent), reasons

# ── レジサポ転換検出 ─────────────────────────────────────────────────────────

def _detect_reji_sapo(H, L, C, i, lookback=90):
    """
    Returns: ('confirmed', 'watching', 'none')
    confirmed: 抵抗線ブレイク後、その水準まで戻ってきてサポートとして機能
    watching:  ブレイクアウト直後（まだ戻りを確認できていない）
    """
    if i < lookback + 10:
        return "none"

    current = C[i]

    # 1. 過去の抵抗帯を特定（30〜90バー前の高値）
    old_highs_window = H[max(0, i-lookback):max(0, i-20)]
    if not old_highs_window:
        return "none"

    resistance = max(old_highs_window)

    # 抵抗帯が現在値の1〜20%下にある場合のみ有効
    if not (current * 0.80 < resistance < current * 0.99):
        return "none"

    # 2. 直近20バーでブレイクアウト（その抵抗帯を上抜けた）があるか
    recent_window = H[max(0, i-20):i+1]
    broke_out = any(h > resistance * 1.01 for h in recent_window)
    if not broke_out:
        return "none"

    # 3. 現在値が抵抗帯（転換サポート）に接近しているか（±3%以内）
    near_resistance = abs(current - resistance) / resistance < SUPPORT_TOLERANCE

    if near_resistance:
        return "confirmed"

    # ブレイクアウトしたがまだ戻っていない
    if current > resistance * 1.03:
        return "watching"

    return "none"

# ── R:R計算 ─────────────────────────────────────────────────────────────────

def _calc_rr(C, H, L, atr_arr, ema20, ema50, support_price, i, lookback=60):
    """
    TP = 直近高値 × 0.99
    SL = サポート × 0.99 または サポート − ATR
    R:R = (TP - 現在値) / (現在値 - SL)
    """
    current = C[i]
    atr_v = atr_arr[i]
    if atr_v is None or atr_v <= 0:
        return None, None, None, None

    # TP: 直近高値（過去60バー）の少し手前
    recent_high = max(H[max(0, i-lookback):i+1])
    tp = recent_high * 0.99

    # TP が現在値より下なら計算不可
    if tp <= current:
        return None, None, None, None

    # SL: サポートラインを使用
    if support_price and support_price < current:
        sl_base = support_price
        sl = min(sl_base * 0.99, sl_base - atr_v)
    else:
        # フォールバック: ATR×1.5
        sl = current - atr_v * 1.5

    risk   = current - sl
    reward = tp - current

    if risk <= 0:
        return None, None, None, None

    rr = reward / risk
    return round(rr, 2), round(tp, 2), round(sl, 2), round(atr_v, 4)

# ── フィボナッチコンフルエンス ────────────────────────────────────────────────

def _fib_confluence(H, L, C, ema20, ema50, i, lookback=120):
    """
    主要スイング高値・安値からフィボ水準を算出し、EMAやサポートとのコンフルエンスを確認。
    Returns: (fib_level_pct, fib_price) or None
    """
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
        # 現在値がフィボ水準の±2%以内
        if abs(current - fib_price) / fib_price > 0.02:
            continue
        # フィボ水準がEMAと一致（±2%）
        for ema, ema_name in [(ema20[i], "20EMA"), (ema50[i], "50EMA")]:
            if ema is not None and abs(ema - fib_price) / fib_price < 0.02:
                return label, round(fib_price, 2)
        # フィボ水準付近に実際にいるだけでも有効
        return label, round(fib_price, 2)

    return None

# ── イントラデイ（1H/4H）ヘルパー ───────────────────────────────────────────────

def _fetch_intraday_batch(tickers):
    """yfinanceで1時間足データを一括取得（期間=7日）。Dict[ticker→df]を返す。"""
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
        # yfinance multi-ticker returns MultiIndex or grouped DataFrame
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
        print(f"[Logic3] 1H data fetch error: {e}")
        return None


def _extract_ticker_1h(data_dict, ticker):
    """dict から1銘柄のOHLCVリストを取得する。"""
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
    """1Hバーを4Hバーにリサンプル（4本ずつグループ化）。"""
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


def _is_pin_bar(bar):
    """ハンマー型ピンバー（下ヒゲ ≥ 実体の2倍、陽線）。"""
    body = abs(bar["close"] - bar["open"])
    lower_wick = min(bar["close"], bar["open"]) - bar["low"]
    upper_wick = bar["high"] - max(bar["close"], bar["open"])
    if body < 1e-8:
        body = (bar["high"] - bar["low"]) * 0.1
    return (bar["close"] > bar["open"] and
            lower_wick >= 2 * body and
            lower_wick >= 2 * (upper_wick + 1e-8))


def _is_bull_engulfing(prev, curr):
    """強気エンガルフィング。"""
    if prev is None:
        return False
    return (prev["close"] < prev["open"] and       # 前足: 陰線
            curr["close"] > curr["open"] and        # 当足: 陽線
            curr["open"]  <= prev["close"] and
            curr["close"] >= prev["open"])


def _is_inverse_hammer(bar):
    """逆ハンマー（上ヒゲ ≥ 実体の2倍、下ヒゲ小、小実体）。"""
    body = abs(bar["close"] - bar["open"])
    upper_wick = bar["high"] - max(bar["close"], bar["open"])
    lower_wick = min(bar["close"], bar["open"]) - bar["low"]
    if body < 1e-8:
        body = (bar["high"] - bar["low"]) * 0.1
    return (upper_wick >= 2 * body and
            lower_wick <= body * 0.5)


def _is_piercing_line(prev, curr):
    """切り込み線: 陰線→陽線が前足の中間以上まで戻す（エンガルフィング未満）。"""
    if prev is None:
        return False
    prev_mid = (prev["open"] + prev["close"]) / 2
    return (prev["close"] < prev["open"] and            # 前足: 陰線
            curr["close"] > curr["open"] and             # 当足: 陽線
            curr["open"]  < prev["close"] and            # 前足終値より下で寄り付き
            curr["close"] >= prev_mid and                # 前足中間以上まで戻す
            curr["close"] < prev["open"])                # エンガルフィングにはならない


def _is_three_white_soldiers(b1, b2, b3):
    """赤三兵: 3本連続陽線、各足が前足の高値を超えて引ける。"""
    if b1 is None or b2 is None or b3 is None:
        return False
    # 全て陽線
    if not (b1["close"] > b1["open"] and
            b2["close"] > b2["open"] and
            b3["close"] > b3["open"]):
        return False
    # 各足が前足の高値を超えて引ける
    if not (b2["close"] > b1["close"] and b3["close"] > b2["close"]):
        return False
    # 各足がギャップダウンせず前足の実体内で寄り付く
    if not (b2["open"] >= b1["open"] and b3["open"] >= b2["open"]):
        return False
    return True


def _is_morning_star(b1, b2, b3):
    """明けの明星: 大陰線→小実体（十字線含む）→大陽線。"""
    if b1 is None or b2 is None or b3 is None:
        return False
    b1_body = abs(b1["close"] - b1["open"])
    b2_body = abs(b2["close"] - b2["open"])
    b3_body = abs(b3["close"] - b3["open"])
    b1_range = b1["high"] - b1["low"]
    if b1_range < 1e-8:
        return False
    # b1: 大陰線、b2: 小実体、b3: 大陽線
    return (b1["close"] < b1["open"] and                 # b1: 陰線
            b2_body < b1_body * 0.4 and                  # b2: 小実体（b1の40%未満）
            b3["close"] > b3["open"] and                 # b3: 陽線
            b3_body > b1_body * 0.5 and                  # b3: b1の50%以上の実体
            b3["close"] > (b1["open"] + b1["close"]) / 2)  # b3がb1の中間以上まで戻す


def _detect_4h_trigger(rows_4h, support_price):
    """
    4時間足の直近バーでトリガーシグナルを検出。
    サポート価格の ±5% 以内で発生したもののみ対象。
    Returns: シグナル名 (str) or None
    """
    if not rows_4h or len(rows_4h) < 4:
        return None

    vols = [r["volume"] for r in rows_4h]
    vol_ma = sum(vols) / len(vols) if vols else 1

    # 直近バーを新しい順にチェック（4Hは本数が少ないので全バーチェック）
    recent = rows_4h[-6:] if len(rows_4h) >= 6 else rows_4h

    # ダブルボトム検出（全4Hバーのスイングロー）
    lows_all = [r["low"] for r in rows_4h]
    sl_idxs = _find_swing_lows(lows_all, lookback=1)
    double_bottom = False
    if len(sl_idxs) >= 2:
        l1, l2 = lows_all[sl_idxs[-2]], lows_all[sl_idxs[-1]]
        if l1 > 0 and abs(l1 - l2) / l1 < 0.015:
            double_bottom = True

    for j in range(len(recent) - 1, -1, -1):
        bar  = recent[j]
        prev = recent[j - 1] if j > 0 else None
        prev2 = recent[j - 2] if j >= 2 else None

        # サポート近傍チェック（±5%）
        mid = (bar["high"] + bar["low"]) / 2
        if support_price > 0 and abs(mid - support_price) / support_price > 0.05:
            continue

        # 1本足パターン
        if _is_pin_bar(bar):
            return "ピンバー(4H)"
        if _is_inverse_hammer(bar):
            return "逆ハンマー(4H)"

        # 2本足パターン
        if prev and _is_bull_engulfing(prev, bar):
            return "強気エンガルフィング(4H)"
        if prev and _is_piercing_line(prev, bar):
            return "切り込み線(4H)"

        # 出来高急増
        if bar["volume"] >= vol_ma * 1.5 and bar["close"] > bar["open"]:
            return "出来高急増(4H)"

        # 3本足パターン
        if prev and prev2 and _is_morning_star(prev2, prev, bar):
            return "明けの明星(4H)"
        if prev and prev2 and _is_three_white_soldiers(prev2, prev, bar):
            return "赤三兵(4H)"

    if double_bottom:
        return "ダブルボトム(4H)"

    return None


def _detect_4h_structure(rows_4h, support_price):
    """
    4時間足の構造を判定（7日≒8本向けの簡略版）。

    直近4本の終値の傾き（線形回帰）で判断:
      bullish : 傾きが終値平均の+0.1%/本以上 かつ 最終足が陽線
      bearish : 傾きが終値平均の-0.1%/本以下 かつ 最終足が陰線
      neutral : それ以外

    Returns: 'bullish' | 'neutral' | 'bearish'
    """
    if not rows_4h or len(rows_4h) < 4:
        return "neutral"

    # 直近4本を使用
    recent = rows_4h[-4:]
    closes = [b["close"] for b in recent]
    n = len(closes)

    # 線形回帰の傾きを計算（最小二乗法）
    xs = list(range(n))
    x_mean = sum(xs) / n
    c_mean = sum(closes) / n
    num   = sum((xs[i] - x_mean) * (closes[i] - c_mean) for i in range(n))
    denom = sum((xs[i] - x_mean) ** 2 for i in range(n))
    slope = num / denom if denom != 0 else 0

    # 傾きを終値平均で正規化（1本あたり何%動いているか）
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
    """
    株価が安値切り下げ・MACDヒストグラムが切り上げ → 強気ダイバージェンス
    """
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

    # FMP APIで不足分を補完
    if tickers and FMP_API_KEY:
        missing = [t for t in tickers if t not in sector_map]
        if missing:
            print(f"[Logic3] FMP APIでセクター補完: {len(missing)}銘柄")
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
                    print(f"[Logic3] FMP sector fetch error: {e}")

    return sector_map


def run():
    print("[Logic3] 押し目買いスクリーニング開始...")
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

    # セクターマッピングを一括取得（不足分はFMP APIで補完）
    sector_map = _build_sector_map(cur, tickers)
    print(f"[Logic3] セクターマッピング: {len(sector_map)}銘柄")

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
                continue  # 最低条件（準成立）すら満たさない
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
            rr, tp_price, sl_price, atr_v = _calc_rr(C, H, L, atr_arr, ema20, ema50, support_price, i)
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
                continue  # 見送り

            adopted += 1

            # 日足チャートパターン検出
            chart_patterns = _detect_daily_chart_patterns(H, L, C, i)
            chart_pattern = ", ".join(chart_patterns) if chart_patterns else None

            # セクター（起動時に一括取得済み）
            sector = sector_map.get(ticker)

            # 保有日数推定
            if atr_v and atr_v > 0 and tp_price and C[i]:
                holding_days = max(3, round(abs(tp_price - C[i]) / (atr_v * 0.5)))
            else:
                holding_days = 14

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
                "tp1_price":       round(C[i] + (tp_price - C[i]) * 0.5, 2),
                "target_price":    tp_price,
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
                "signals_json":    json.dumps(support_reasons[:3], ensure_ascii=False),
                "chart_pattern":   chart_pattern,
            })

        except Exception as e:
            print(f"[Logic3] {ticker} エラー: {e}")

    # ── イントラデイ（1H/4H）分析 ─────────────────────────────────────────────
    if picks:
        candidate_tickers = [p["ticker"] for p in picks]
        print(f"[Logic3] 4Hデータ取得中... {len(candidate_tickers)}銘柄")
        intraday_dict = _fetch_intraday_batch(candidate_tickers)

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

            # 4Hトリガー（ロジック３の特徴: 4H足でプライスアクション検出）
            p["h4_trigger"] = _detect_4h_trigger(rows_4h, p["support_price"]) if rows_4h else None

            # 判定をインデイタイムフレームで更新
            near_support = price_to_support is not None and price_to_support <= 3.0
            has_trigger  = p["h4_trigger"] is not None
            has_chart_pattern = bool(p.get("chart_pattern"))

            if (has_trigger or has_chart_pattern) and near_support:
                p["verdict"] = "最優先候補"
            elif has_chart_pattern:
                p["verdict"] = "最優先候補"  # 日足チャートパターンは強力なシグナル
            elif near_support:
                p["verdict"] = "サポート接近中"
            else:
                p["verdict"] = "押し目待ち"
    else:
        for p in picks:
            p["price_to_support_pct"] = None
            p["h4_structure"]         = "neutral"
            p["h4_trigger"]           = None

    # ── 保存 ────────────────────────────────────────────────────────────────
    cur.execute("DELETE FROM logic3_picks")
    for p in picks:
        cur.execute("""
            INSERT INTO logic3_picks
                (ticker, scan_date, perfect_order, perf_3m, perf_6m, avg_vol_20d,
                 dow_trend, support_price, confluence, support_reasons, reji_sapo,
                 risk_reward, entry_price, stop_price, tp1_price, target_price,
                 rsi, rsi_flag, macd_div_flag, fib_confluence, atr,
                 verdict, confidence, composite_score, sector, current_price,
                 holding_days_est, signals_json,
                 price_to_support_pct, h4_trigger, h4_structure,
                 chart_pattern)
            VALUES
                (:ticker, :scan_date, :perfect_order, :perf_3m, :perf_6m, :avg_vol_20d,
                 :dow_trend, :support_price, :confluence, :support_reasons, :reji_sapo,
                 :risk_reward, :entry_price, :stop_price, :tp1_price, :target_price,
                 :rsi, :rsi_flag, :macd_div_flag, :fib_confluence, :atr,
                 :verdict, :confidence, :composite_score, :sector, :current_price,
                 :holding_days_est, :signals_json,
                 :price_to_support_pct, :h4_trigger, :h4_structure,
                 :chart_pattern)
        """, p)
    conn.commit()
    conn.close()

    verdict_order = {"最優先候補": 0, "サポート接近中": 1, "押し目待ち": 2}
    picks.sort(key=lambda x: (
        verdict_order.get(x["verdict"], 3),
        -x["risk_reward"]
    ))
    print(f"[Logic3] 完了 — 一次通過:{first_pass} 二次通過:{second_pass} 採用:{adopted}")
    for p in picks[:5]:
        trigger = p.get("h4_trigger") or "-"
        dist    = p.get("price_to_support_pct")
        dist_s  = f"{dist:.1f}%" if dist is not None else "N/A"
        print(f"  {p['ticker']:8s} {p['verdict']} RR={p['risk_reward']:.2f} dist={dist_s} trigger={trigger}")
