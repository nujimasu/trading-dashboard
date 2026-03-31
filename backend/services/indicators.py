"""
Technical indicator calculations.
Extracted and extended from scripts/fetch_trading_data.py and analyze_rr.py.
"""
import numpy as np
import pandas as pd
from config import (
    ATR_PERIOD, ATR_MULT, STOP_WINDOW, TARGET_WINDOW,
    RSI_MIN, RSI_MAX, PCT_FROM_HIGH_MAX,
    MIN_RR_TIER1, MIN_RR_TIER2, PRICE_RANGE_TIGHTEN_DAYS,
)


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add all technical indicators to an OHLCV DataFrame."""
    df = df.copy()
    close  = df["Close"]
    high   = df["High"]
    low    = df["Low"]
    volume = df["Volume"]

    # Moving averages
    df["EMA10"]  = close.ewm(span=10, adjust=False).mean()
    df["EMA21"]  = close.ewm(span=21, adjust=False).mean()
    df["SMA20"]  = close.rolling(20).mean()
    df["SMA50"]  = close.rolling(50).mean()
    df["SMA200"] = close.rolling(200).mean()

    # RSI(14)
    delta = close.diff()
    gain  = delta.where(delta > 0, 0).rolling(14).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs    = gain / loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    # MACD (12/26/9)
    exp12       = close.ewm(span=12, adjust=False).mean()
    exp26       = close.ewm(span=26, adjust=False).mean()
    df["MACD"]  = exp12 - exp26
    df["MACDSig"] = df["MACD"].ewm(span=9, adjust=False).mean()

    # ATR(14)
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    df["ATR"] = tr.rolling(ATR_PERIOD).mean()

    # Volume MA
    df["VolSMA50"] = volume.rolling(50).mean()
    df["VolSMA20"] = volume.rolling(20).mean()

    return df


def compute_stock_summary(ticker: str, df: pd.DataFrame) -> dict | None:
    """
    Compute a full analysis summary for one ticker.
    Returns None if data is insufficient or risk is zero.
    """
    if len(df) < 60:
        return None

    df = calculate_indicators(df)
    latest = df.iloc[-1]
    prev   = df.iloc[-2]

    close_price = float(latest["Close"])
    sma20  = float(latest["SMA20"])  if not np.isnan(latest["SMA20"])  else None
    sma50  = float(latest["SMA50"])  if not np.isnan(latest["SMA50"])  else None
    sma200 = float(latest["SMA200"]) if not np.isnan(latest["SMA200"]) else None
    ema10  = float(latest["EMA10"])
    ema21  = float(latest["EMA21"])
    rsi    = float(latest["RSI"])    if not np.isnan(latest["RSI"])    else None
    macd   = float(latest["MACD"])
    macd_sig = float(latest["MACDSig"])
    atr    = float(latest["ATR"])    if not np.isnan(latest["ATR"])    else 0
    vol    = float(latest["Volume"])
    vol_sma50 = float(latest["VolSMA50"]) if not np.isnan(latest["VolSMA50"]) else 0
    vol_sma20 = float(latest["VolSMA20"]) if not np.isnan(latest["VolSMA20"]) else 0

    # 52-week high/low
    high_52w = float(df["High"].iloc[-252:].max())
    low_52w  = float(df["Low"].iloc[-252:].min())
    pct_from_high = (close_price / high_52w - 1) if high_52w > 0 else -1

    # Stage 2 uptrend: Close > SMA50 > SMA200
    stage2 = (
        sma50  is not None
        and sma200 is not None
        and close_price > sma50 > sma200
    )

    # VCP tightening: recent 10d range < prior 10d range
    if len(df) >= PRICE_RANGE_TIGHTEN_DAYS * 2:
        recent_range = float(
            df["High"].iloc[-PRICE_RANGE_TIGHTEN_DAYS:].max()
            - df["Low"].iloc[-PRICE_RANGE_TIGHTEN_DAYS:].min()
        )
        prior_range = float(
            df["High"].iloc[-PRICE_RANGE_TIGHTEN_DAYS*2:-PRICE_RANGE_TIGHTEN_DAYS].max()
            - df["Low"].iloc[-PRICE_RANGE_TIGHTEN_DAYS*2:-PRICE_RANGE_TIGHTEN_DAYS].min()
        )
        vcp_tightening = recent_range < prior_range
    else:
        vcp_tightening = False

    # Volume contraction
    vol_contraction = (vol_sma50 > 0 and vol < vol_sma50)

    # Volume ratio vs 20d avg
    vol_ratio = (vol / vol_sma20) if vol_sma20 > 0 else 0

    # Entry / Stop / Target (from analyze_rr.py logic)
    entry = close_price
    stop_raw = float(df["Low"].iloc[-STOP_WINDOW:].min())
    max_risk = atr * ATR_MULT
    min_risk = atr * 1.0  # require at least 1 ATR of risk (avoid tiny stops)
    stop = max(stop_raw, entry - max_risk)
    stop = min(stop, entry - min_risk)  # enforce minimum distance
    risk = entry - stop

    if risk <= 0:
        return None

    target_raw = float(df["High"].iloc[-TARGET_WINDOW:].max())
    if target_raw <= entry:
        target = entry + atr * 3.0
        target_source = "ATR×3（仮）"
    else:
        target = target_raw
        target_source = f"{TARGET_WINDOW}日高値"

    reward = target - entry
    rr     = reward / risk if risk > 0 else 0

    # Tier determination
    if rr >= MIN_RR_TIER1:
        tier = "Tier1"
    elif rr >= MIN_RR_TIER2:
        tier = "Tier2"
    else:
        tier = "REJECTED"

    # Change pct from previous day
    change_pct = ((close_price - float(prev["Close"])) / float(prev["Close"])) * 100

    return {
        "ticker":          ticker,
        "price":           round(close_price, 2),
        "change_pct":      round(change_pct, 2),
        "volume":          int(vol),
        "vol_ratio":       round(vol_ratio, 2),
        "sma20":           round(sma20, 2)  if sma20  else None,
        "sma50":           round(sma50, 2)  if sma50  else None,
        "sma200":          round(sma200, 2) if sma200 else None,
        "ema10":           round(ema10, 2),
        "ema21":           round(ema21, 2),
        "rsi":             round(rsi, 2) if rsi else None,
        "macd":            round(macd, 4),
        "macd_signal":     round(macd_sig, 4),
        "atr":             round(atr, 2),
        "high_52w":        round(high_52w, 2),
        "low_52w":         round(low_52w, 2),
        "pct_from_high":   round(pct_from_high * 100, 2),
        "stage2_uptrend":  stage2,
        "vcp_tightening":  vcp_tightening,
        "vol_contraction": vol_contraction,
        "entry":           round(entry, 2),
        "stop":            round(stop, 2),
        "target":          round(target, 2),
        "target_source":   target_source,
        "risk":            round(risk, 2),
        "reward":          round(reward, 2),
        "risk_reward":     round(rr, 2),
        "tier":            tier,
    }


def build_entry_reasons(summary: dict) -> list[str]:
    """Generate human-readable entry reasons from a summary dict."""
    reasons = []
    if summary.get("stage2_uptrend"):
        reasons.append(f"Stage 2アップトレンド（Close > SMA50 > SMA200）")
    if summary.get("rsi") and RSI_MIN <= summary["rsi"] <= RSI_MAX:
        reasons.append(f"RSI {summary['rsi']:.1f}（過熱感なし、モメンタム良好）")
    if summary.get("macd") and summary.get("macd_signal") and summary["macd"] > summary["macd_signal"]:
        reasons.append(f"MACD > Signal（上昇モメンタム継続）")
    if summary.get("pct_from_high") and abs(summary["pct_from_high"]) <= PCT_FROM_HIGH_MAX * 100:
        reasons.append(f"52週高値から{abs(summary['pct_from_high']):.1f}%以内（ブレイクアウト圏内）")
    if summary.get("vcp_tightening"):
        reasons.append("価格レンジ縮小（VCPパターン形成中）")
    if summary.get("vol_contraction"):
        reasons.append("出来高収縮（VCPの典型的な特徴）")
    if summary.get("vol_ratio") and summary["vol_ratio"] >= 1.5:
        reasons.append(f"出来高急増（平均の{summary['vol_ratio']:.1f}倍、ブレイクアウト確認）")
    reasons.append(f"RR {summary['risk_reward']:.2f}（目標: ${summary['target']:.2f}, ストップ: ${summary['stop']:.2f}）")
    return reasons


def build_risk_factors(summary: dict) -> list[str]:
    """Generate risk warnings from a summary dict."""
    risks = []
    if summary.get("rsi") and summary["rsi"] > 65:
        risks.append(f"RSI {summary['rsi']:.1f}（やや過熱気味）")
    if summary.get("pct_from_high") and abs(summary["pct_from_high"]) > 10:
        risks.append(f"52週高値から{abs(summary['pct_from_high']):.1f}%下（エクステンションリスク）")
    if not summary.get("vcp_tightening"):
        risks.append("価格レンジ縮小なし（ベース形成が不明確）")
    if summary.get("vol_ratio") and summary["vol_ratio"] < 0.5:
        risks.append("出来高が低水準（流動性リスク）")
    if summary.get("risk_reward") < MIN_RR_TIER1:
        risks.append(f"RR {summary['risk_reward']:.2f}（Tier1基準{MIN_RR_TIER1}未満→ハーフサイズ）")
    return risks
