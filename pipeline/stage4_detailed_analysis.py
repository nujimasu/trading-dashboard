"""
Stage 4: Detailed technical analysis — LONG and SHORT candidates.

LONG:  entry=price, stop=below (swing low), target=above (swing high)
SHORT: entry=price, stop=above (swing high + buffer), target=below (52w low or ATR×3)
"""
import sys
import json
from datetime import date
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    STOP_WINDOW, ATR_PERIOD, ATR_MULT, TARGET_WINDOW,
    MIN_RR_TIER1, MIN_RR_TIER2, PRICE_RANGE_TIGHTEN_DAYS,
)
from backend.db import get_connection, db_cursor
from backend.services.indicators import (
    calculate_indicators, build_entry_reasons, build_risk_factors,
)


def load_price_df(ticker: str, conn) -> pd.DataFrame | None:
    df = pd.read_sql_query(
        "SELECT date, open, high, low, close, volume FROM price_data WHERE ticker = ? ORDER BY date",
        conn,
        params=(ticker,),
        parse_dates=["date"],
        index_col="date",
    )
    df.columns = [c.capitalize() for c in df.columns]
    return df if len(df) >= 60 else None


def compute_vcp_score(df: pd.DataFrame) -> tuple[float, int]:
    highs = df["High"].values
    lows  = df["Low"].values
    n     = len(highs)
    if n < 60:
        return 50.0, 0
    periods = [20, 20, 20]
    ranges  = []
    for i, p in enumerate(periods):
        start = n - sum(periods) + sum(periods[:i])
        end   = start + p
        ranges.append(float(highs[start:end].max() - lows[start:end].min()))
    score       = 0.0
    contractions = 0
    for i in range(1, len(ranges)):
        if ranges[i] < ranges[i-1] and ranges[i-1] > 0:
            score += (ranges[i-1] - ranges[i]) / ranges[i-1] * 100
            contractions += 1
    vols = []
    for i, p in enumerate(periods):
        start = n - sum(periods) + sum(periods[:i])
        end   = start + p
        vols.append(float(df["Volume"].values[start:end].mean()))
    if all(vols[i] <= vols[i-1] for i in range(1, len(vols))):
        score += 20
    return min(round(score, 1), 100.0), contractions


# ── Long analysis ───────────────────────────────────────────────────────────

def _analyze_long(ticker: str, df: pd.DataFrame, today: str) -> dict | None:
    df   = calculate_indicators(df)
    last = df.iloc[-1]

    price = float(last["Close"])
    atr   = float(last["ATR"]) if not np.isnan(last["ATR"]) else 0

    entry    = price
    stop_raw = float(df["Low"].iloc[-STOP_WINDOW:].min())
    max_risk = atr * ATR_MULT
    min_risk = atr * 1.0
    stop     = max(stop_raw, entry - max_risk)
    stop     = min(stop, entry - min_risk)
    risk     = entry - stop
    if risk <= 0:
        return None

    target_raw = float(df["High"].iloc[-TARGET_WINDOW:].max())
    if target_raw <= entry:
        target = entry + atr * 3.0
    else:
        target = target_raw
    rr = (target - entry) / risk
    if rr < MIN_RR_TIER2:
        return None

    # TP1 = entry + 1.5R (partial take / move stop to BE)
    # TP2 = target (runner target)
    tp1  = round(entry + risk * 1.5, 2)
    tp2  = round(target, 2)
    # Estimated holding days: distance to TP2 ÷ 0.5 ATR/day (trend assumption)
    holding_days_est = max(3, round((tp2 - entry) / (atr * 0.5))) if atr > 0 else 20

    tier       = "Tier1" if rr >= MIN_RR_TIER1 else "Tier2"
    vcp_score, contraction_count = compute_vcp_score(df)

    sma50  = float(last["SMA50"])  if not np.isnan(last["SMA50"])  else None
    sma200 = float(last["SMA200"]) if not np.isnan(last["SMA200"]) else None
    rsi    = float(last["RSI"])    if not np.isnan(last["RSI"])    else None
    macd   = float(last["MACD"])
    macd_s = float(last["MACDSig"])
    vol    = float(last["Volume"])
    vol50  = float(last["VolSMA50"]) if not np.isnan(last["VolSMA50"]) else 0

    tech_score = 5.0
    if sma50 and sma200 and price > sma50 > sma200:
        tech_score += 1.0
    if rsi and 45 <= rsi <= 65:
        tech_score += 0.5
    if macd > macd_s:
        tech_score += 0.5
    if vcp_score >= 60:
        tech_score += 1.0
    if contraction_count >= 2:
        tech_score += 0.5
    if vol < vol50 and vol50 > 0:
        tech_score += 0.5
    if rr >= 2.0:
        tech_score += 0.5
    tech_score = min(round(tech_score, 1), 10.0)

    summary = {
        "stage2_uptrend":  sma50 and sma200 and price > sma50 > sma200,
        "rsi":             rsi,
        "macd":            macd,
        "macd_signal":     macd_s,
        "pct_from_high":   ((price / df["High"].iloc[-252:].max() - 1) * 100) if len(df) >= 252 else 0,
        "vcp_tightening":  vcp_score > 30,
        "vol_contraction": vol < vol50 if vol50 > 0 else False,
        "vol_ratio":       vol / vol50 if vol50 > 0 else 0,
        "risk_reward":     rr,
        "target":          target,
        "stop":            stop,
    }
    return {
        "ticker":            ticker,
        "scan_date":         today,
        "vcp_score":         vcp_score,
        "contraction_count": contraction_count,
        "pivot_price":       round(entry, 2),
        "stop_price":        round(stop, 2),
        "tp1_price":         tp1,
        "target_price":      tp2,
        "risk_reward":       round(rr, 2),
        "tier":              tier,
        "technical_score":   tech_score,
        "holding_days_est":  holding_days_est,
        "entry_reasons":     json.dumps(build_entry_reasons(summary),  ensure_ascii=False),
        "risk_factors":      json.dumps(build_risk_factors(summary),   ensure_ascii=False),
        "direction":         "LONG",
    }


# ── Short momentum score (replaces VCP for short setups) ────────────────────

def compute_short_momentum_score(df: pd.DataFrame, price: float,
                                  sma50: float | None, sma200: float | None,
                                  vol: float, vol50: float) -> float:
    """
    Short momentum score (0-100) — measures downtrend strength.
    Replaces VCP score (long-specific) for short setups.

    Components:
    - 52w high distance  (0-40pts): deeper fall → stronger downtrend
    - MA separation      (0-30pts): price far below SMA50 < SMA200
    - Volume expansion   (0-30pts): distribution selling confirmation
    """
    score = 0.0

    # 1. Distance from 52-week high (0-40pts)
    window = min(252, len(df))
    high_52w = float(df["High"].iloc[-window:].max())
    pct_below_high = abs((price / high_52w - 1) * 100) if high_52w > 0 else 0
    # 10% below → 0pts, 60% below → 40pts (linear)
    score += min(40.0, max(0.0, (pct_below_high - 10) / 50 * 40))

    # 2. Moving average separation (0-30pts)
    if sma50 and sma200 and sma50 > 0 and sma200 > 0:
        gap_price_sma50  = (sma50  - price) / sma50  * 100   # % price below SMA50
        gap_sma50_sma200 = (sma200 - sma50) / sma200 * 100   # % SMA50 below SMA200
        score += min(30.0, max(0.0, (gap_price_sma50 + gap_sma50_sma200) * 2.0))

    # 3. Volume expansion — distribution selling (0-30pts)
    if vol50 > 0:
        vol_ratio = vol / vol50
        if   vol_ratio >= 2.0: score += 30.0
        elif vol_ratio >= 1.5: score += 20.0
        elif vol_ratio >= 1.2: score += 10.0
        elif vol_ratio >= 1.0: score +=  5.0

    return round(min(score, 100.0), 1)


# ── Short analysis ──────────────────────────────────────────────────────────

def _analyze_short(ticker: str, df: pd.DataFrame, today: str) -> dict | None:
    df   = calculate_indicators(df)
    last = df.iloc[-1]

    price = float(last["Close"])
    atr   = float(last["ATR"]) if not np.isnan(last["ATR"]) else 0
    if atr <= 0:
        return None

    entry = price

    # Stop: recent swing HIGH + ATR buffer (stop is ABOVE entry for shorts)
    swing_high = float(df["High"].iloc[-STOP_WINDOW:].max())
    min_risk   = atr * 1.0
    max_risk   = atr * ATR_MULT
    stop       = min(swing_high + atr * 0.3, entry + max_risk)
    stop       = max(stop, entry + min_risk)
    risk       = stop - entry  # positive: stop above entry
    if risk <= 0:
        return None

    # Target: 52w low or ATR×3 below entry
    low_52w = float(df["Low"].iloc[-252:].min())
    if low_52w < entry * 0.80:          # meaningful downside to 52w low
        target = low_52w
    else:
        target = entry - atr * 3.0
    if target >= entry:                 # target must be below entry
        return None

    reward = entry - target             # positive
    rr     = reward / risk
    if rr < MIN_RR_TIER2:
        return None

    # TP1 = entry - 1.5R (partial cover / move stop to BE)
    # TP2 = target (full downside target / runner)
    tp1  = round(entry - risk * 1.5, 2)
    tp2  = round(target, 2)
    holding_days_est = max(3, round((entry - tp2) / (atr * 0.5))) if atr > 0 else 20

    tier = "Tier1" if rr >= MIN_RR_TIER1 else "Tier2"

    sma50  = float(last["SMA50"])  if not np.isnan(last["SMA50"])  else None
    sma200 = float(last["SMA200"]) if not np.isnan(last["SMA200"]) else None
    rsi    = float(last["RSI"])    if not np.isnan(last["RSI"])    else None
    macd   = float(last["MACD"])
    macd_s = float(last["MACDSig"])
    vol    = float(last["Volume"])
    vol50  = float(last["VolSMA50"]) if not np.isnan(last["VolSMA50"]) else 0

    # Short momentum score — replaces VCP (long-specific) in composite scoring
    short_momentum = compute_short_momentum_score(df, price, sma50, sma200, vol, vol50)

    tech_score = 5.0
    if sma50 and sma200 and price < sma50 < sma200:
        tech_score += 1.0                           # Stage 4 confirmed
    if rsi and 35 <= rsi <= 55:
        tech_score += 0.5                           # ideal short RSI zone
    if macd < macd_s:
        tech_score += 0.5
    if vol > vol50 > 0:
        tech_score += 0.5                           # distribution volume
    if rr >= 2.0:
        tech_score += 0.5
    tech_score = min(round(tech_score, 1), 10.0)

    entry_reasons = []
    if sma50 and sma200 and price < sma50 < sma200:
        entry_reasons.append("Stage 4下降トレンド確認（価格 < SMA50 < SMA200）")
    if macd < macd_s:
        entry_reasons.append("MACDが下向きモメンタムを示す")
    if rsi and rsi < 50:
        entry_reasons.append(f"RSI {rsi:.0f} — 弱気領域")
    if rr >= 2.0:
        entry_reasons.append(f"RR {rr:.2f} — 優良ショートセットアップ")

    risk_factors = []
    if rsi and rsi < 35:
        risk_factors.append("RSI過売り圏 — 短期反発リスクあり")
    if vol < vol50 and vol50 > 0:
        risk_factors.append("出来高低下 — 動きが鈍い可能性")
    risk_factors.append("ショートスクイーズリスクに注意（決算・催促ニュース確認）")

    high_52w = float(df["High"].iloc[-252:].max())
    pct_from_high = (price / high_52w - 1) * 100 if high_52w > 0 else 0

    # Build a summary compatible with technical_summary structure
    summary_obj = {
        "stage2_uptrend":    False,
        "rsi":               rsi,
        "macd_above_sig":    False,
        "pct_from_high":     pct_from_high,
        "vcp_score":         0,
        "contraction_count": 0,
        "volume_ratio":      vol / vol50 if vol50 > 0 else 0,
        "entry_reasons":     entry_reasons,
        "risk_factors":      risk_factors,
    }

    return {
        "ticker":            ticker,
        "scan_date":         today,
        "vcp_score":         short_momentum,   # short momentum replaces VCP
        "contraction_count": 0,
        "pivot_price":       round(entry, 2),
        "stop_price":        round(stop, 2),
        "tp1_price":         tp1,
        "target_price":      tp2,
        "risk_reward":       round(rr, 2),
        "tier":              tier,
        "holding_days_est":  holding_days_est,
        "technical_score":   tech_score,
        "entry_reasons":     json.dumps(entry_reasons, ensure_ascii=False),
        "risk_factors":      json.dumps(risk_factors,  ensure_ascii=False),
        "direction":         "SHORT",
        "_tech_summary_obj": summary_obj,  # for stage6 use
    }


# ── DB save ─────────────────────────────────────────────────────────────────

def save_results(results: list[dict]):
    today = date.today().isoformat()
    with db_cursor() as cur:
        cur.execute("DELETE FROM detailed_analysis WHERE scan_date = ?", (today,))
        for r in results:
            cur.execute("""
                INSERT INTO detailed_analysis
                    (ticker, scan_date, vcp_score, contraction_count, pivot_price,
                     stop_price, tp1_price, target_price, risk_reward, tier,
                     technical_score, holding_days_est, entry_reasons, risk_factors, direction)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT (ticker) DO UPDATE SET
                    scan_date=EXCLUDED.scan_date, vcp_score=EXCLUDED.vcp_score,
                    contraction_count=EXCLUDED.contraction_count, pivot_price=EXCLUDED.pivot_price,
                    stop_price=EXCLUDED.stop_price, tp1_price=EXCLUDED.tp1_price,
                    target_price=EXCLUDED.target_price, risk_reward=EXCLUDED.risk_reward,
                    tier=EXCLUDED.tier, technical_score=EXCLUDED.technical_score,
                    holding_days_est=EXCLUDED.holding_days_est, entry_reasons=EXCLUDED.entry_reasons,
                    risk_factors=EXCLUDED.risk_factors, direction=EXCLUDED.direction
            """, (
                r["ticker"], r["scan_date"], r["vcp_score"], r["contraction_count"],
                r["pivot_price"], r["stop_price"], r.get("tp1_price"),
                r["target_price"], r["risk_reward"], r["tier"],
                r["technical_score"], r.get("holding_days_est", 20),
                r["entry_reasons"], r["risk_factors"], r.get("direction", "LONG"),
            ))


# ── Main ─────────────────────────────────────────────────────────────────────

def run(survivors) -> list[str]:
    """
    Accept either:
    - dict {"longs": list[str], "shorts": list[str]}  (new format from stage3)
    - list[str]  (legacy / stage5 passthrough)
    Returns flat list of approved tickers.
    """
    if isinstance(survivors, dict):
        long_tickers  = survivors.get("longs",  [])
        short_tickers = survivors.get("shorts", [])
    else:
        long_tickers  = list(survivors)
        short_tickers = []

    all_tickers = long_tickers + short_tickers
    print(f"[Stage4] Analyzing {len(long_tickers)} longs + {len(short_tickers)} shorts...")

    conn    = get_connection()
    results = []

    for ticker in long_tickers:
        try:
            df = load_price_df(ticker, conn)
            if df is None:
                continue
            r = _analyze_long(ticker, df, date.today().isoformat())
            if r:
                results.append(r)
                print(f"  📈 LONG  {ticker}: RR={r['risk_reward']:.2f}, {r['tier']}")
            else:
                print(f"  ❌ LONG  {ticker}: RR<{MIN_RR_TIER2}")
        except Exception as e:
            print(f"  [ERR] {ticker}: {e}")

    for ticker in short_tickers:
        try:
            df = load_price_df(ticker, conn)
            if df is None:
                continue
            r = _analyze_short(ticker, df, date.today().isoformat())
            if r:
                results.append(r)
                print(f"  📉 SHORT {ticker}: RR={r['risk_reward']:.2f}, {r['tier']}")
            else:
                print(f"  ❌ SHORT {ticker}: RR<{MIN_RR_TIER2}")
        except Exception as e:
            print(f"  [ERR] {ticker}: {e}")

    conn.close()
    save_results(results)

    longs_ok  = sum(1 for r in results if r.get("direction") == "LONG")
    shorts_ok = sum(1 for r in results if r.get("direction") == "SHORT")
    print(f"[Stage4] Done — {longs_ok} long + {shorts_ok} short approved.")
    return [r["ticker"] for r in results]


if __name__ == "__main__":
    from backend.db import init_db
    init_db()
    run({"longs": ["AAPL", "MSFT"], "shorts": ["INTC", "BA"]})
