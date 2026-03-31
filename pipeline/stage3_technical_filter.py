"""
Stage 3: Fast technical screening — both LONG and SHORT candidates.

LONG filter chain (Stage 2 uptrend):
  3a. Stage 2 Uptrend  : Close > SMA50 > SMA200
  3b. RSI 40-70
  3c. MACD > Signal
  3d. Within 15% of 52w high
  3e. VCP pre-check    : volume contraction OR range tightening

SHORT filter chain (Stage 4 decline):
  S1. Stage 4 decline  : Close < SMA50 < SMA200
  S2. RSI 25-60        : not deeply oversold
  S3. MACD < Signal    : downward momentum
  S4. Not >60% off 52w high (avoid terminal/near-zero stocks)
  S5. Not within 5% of 52w low (floor reached → squeeze risk)
"""
import sys
import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import RSI_MIN, RSI_MAX, PCT_FROM_HIGH_MAX, PRICE_RANGE_TIGHTEN_DAYS
from backend.db import get_connection, db_cursor
from backend.services.indicators import calculate_indicators


def load_price_df(ticker: str, conn: sqlite3.Connection) -> pd.DataFrame | None:
    df = pd.read_sql_query(
        "SELECT date, open, high, low, close, volume FROM price_data WHERE ticker = ? ORDER BY date",
        conn,
        params=(ticker,),
        parse_dates=["date"],
        index_col="date",
    )
    df.columns = [c.capitalize() for c in df.columns]
    return df if len(df) >= 60 else None


# ── Long (Stage 2 uptrend) filter ──────────────────────────────────────────

def _screen_long(ticker: str, df: pd.DataFrame, today: str) -> dict | None:
    """Run 5-filter long screen on indicator-enriched df. Returns row or None."""
    latest = df.iloc[-1]

    price  = float(latest["Close"])
    sma50  = float(latest["SMA50"])  if not np.isnan(latest["SMA50"])  else None
    sma200 = float(latest["SMA200"]) if not np.isnan(latest["SMA200"]) else None
    sma20  = float(latest["SMA20"])  if not np.isnan(latest["SMA20"])  else None
    ema10  = float(latest["EMA10"])
    ema21  = float(latest["EMA21"])
    rsi    = float(latest["RSI"])    if not np.isnan(latest["RSI"])    else None
    macd   = float(latest["MACD"])
    macd_s = float(latest["MACDSig"])
    atr    = float(latest["ATR"])    if not np.isnan(latest["ATR"])    else 0
    vol    = float(latest["Volume"])
    vol50  = float(latest["VolSMA50"]) if not np.isnan(latest["VolSMA50"]) else 0
    vol20  = float(latest["VolSMA20"]) if not np.isnan(latest["VolSMA20"]) else 0

    high_52w      = float(df["High"].iloc[-252:].max())
    pct_from_high = (price / high_52w - 1) if high_52w > 0 else -1
    vol_ratio     = (vol / vol20) if vol20 > 0 else 0

    # 3a: Stage 2
    if sma50 is None or sma200 is None or not (price > sma50 > sma200):
        return None
    # 3b: RSI
    if rsi is None or not (RSI_MIN <= rsi <= RSI_MAX):
        return None
    # 3c: MACD
    if macd <= macd_s:
        return None
    # 3d: Near 52w high
    if pct_from_high < -PCT_FROM_HIGH_MAX:
        return None
    # 3e: VCP pre-check
    vol_contraction = vol50 > 0 and vol < vol50
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
    if not vol_contraction and not vcp_tightening:
        return None

    return {
        "ticker":         ticker,
        "scan_date":      today,
        "price":          round(price, 2),
        "sma20":          round(sma20, 2)  if sma20  else None,
        "sma50":          round(sma50, 2),
        "sma200":         round(sma200, 2),
        "ema10":          round(ema10, 2),
        "ema21":          round(ema21, 2),
        "rsi":            round(rsi, 2),
        "macd":           round(macd, 4),
        "macd_signal":    round(macd_s, 4),
        "volume_ratio":   round(vol_ratio, 2),
        "high_52w":       round(high_52w, 2),
        "low_52w":        round(float(df["Low"].iloc[-252:].min()), 2),
        "pct_from_high":  round(pct_from_high * 100, 2),
        "atr":            round(atr, 2),
        "stage2_uptrend": 1,
        "vcp_tightening": 1 if vcp_tightening else 0,
        "passed_filter":  1,
    }


# ── Short (Stage 4 decline) filter ─────────────────────────────────────────

def _screen_short(ticker: str, df: pd.DataFrame, today: str) -> dict | None:
    """Run short screen on indicator-enriched df. Returns row or None."""
    latest = df.iloc[-1]

    price  = float(latest["Close"])
    sma50  = float(latest["SMA50"])  if not np.isnan(latest["SMA50"])  else None
    sma200 = float(latest["SMA200"]) if not np.isnan(latest["SMA200"]) else None
    sma20  = float(latest["SMA20"])  if not np.isnan(latest["SMA20"])  else None
    ema10  = float(latest["EMA10"])
    ema21  = float(latest["EMA21"])
    rsi    = float(latest["RSI"])    if not np.isnan(latest["RSI"])    else None
    macd   = float(latest["MACD"])
    macd_s = float(latest["MACDSig"])
    atr    = float(latest["ATR"])    if not np.isnan(latest["ATR"])    else 0
    vol    = float(latest["Volume"])
    vol20  = float(latest["VolSMA20"]) if not np.isnan(latest["VolSMA20"]) else 0

    high_52w      = float(df["High"].iloc[-252:].max())
    low_52w       = float(df["Low"].iloc[-252:].min())
    pct_from_high = (price / high_52w - 1) if high_52w > 0 else -1
    pct_from_low  = (price / low_52w  - 1) if low_52w  > 0 else 1
    vol_ratio     = (vol / vol20) if vol20 > 0 else 0

    # S1: Stage 4 decline
    if sma50 is None or sma200 is None:
        return None
    if not (price < sma50 and sma50 < sma200):
        return None
    # S2: RSI 25-60 (room to fall, not already crushed)
    if rsi is None or not (25 <= rsi <= 60):
        return None
    # S3: MACD < Signal (downward momentum)
    if macd >= macd_s:
        return None
    # S4: Not more than 60% below 52w high (avoid near-zero stocks)
    if pct_from_high < -0.60:
        return None
    # S5: Not within 5% of 52w low (floor reached → short squeeze risk)
    if pct_from_low < 0.05:
        return None

    return {
        "ticker":         ticker,
        "scan_date":      today,
        "price":          round(price, 2),
        "sma20":          round(sma20, 2)  if sma20  else None,
        "sma50":          round(sma50, 2),
        "sma200":         round(sma200, 2),
        "ema10":          round(ema10, 2),
        "ema21":          round(ema21, 2),
        "rsi":            round(rsi, 2),
        "macd":           round(macd, 4),
        "macd_signal":    round(macd_s, 4),
        "volume_ratio":   round(vol_ratio, 2),
        "high_52w":       round(high_52w, 2),
        "low_52w":        round(low_52w, 2),
        "pct_from_high":  round(pct_from_high * 100, 2),
        "atr":            round(atr, 2),
        "stage2_uptrend": 0,
        "vcp_tightening": 0,
        "passed_filter":  1,
    }


# ── DB save ─────────────────────────────────────────────────────────────────

def save_results(results: list[dict]):
    today = date.today().isoformat()
    with db_cursor() as cur:
        cur.execute("DELETE FROM technical_screen WHERE scan_date = ?", (today,))
        for r in results:
            cur.execute("""
                INSERT INTO technical_screen
                    (ticker, scan_date, price, sma20, sma50, sma200, ema10, ema21,
                     rsi, macd, macd_signal, volume_ratio, high_52w, low_52w,
                     pct_from_high, atr, stage2_uptrend, vcp_tightening, passed_filter)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT (ticker) DO UPDATE SET
                    scan_date=EXCLUDED.scan_date, price=EXCLUDED.price,
                    sma20=EXCLUDED.sma20, sma50=EXCLUDED.sma50, sma200=EXCLUDED.sma200,
                    ema10=EXCLUDED.ema10, ema21=EXCLUDED.ema21, rsi=EXCLUDED.rsi,
                    macd=EXCLUDED.macd, macd_signal=EXCLUDED.macd_signal,
                    volume_ratio=EXCLUDED.volume_ratio, high_52w=EXCLUDED.high_52w,
                    low_52w=EXCLUDED.low_52w, pct_from_high=EXCLUDED.pct_from_high,
                    atr=EXCLUDED.atr, stage2_uptrend=EXCLUDED.stage2_uptrend,
                    vcp_tightening=EXCLUDED.vcp_tightening, passed_filter=EXCLUDED.passed_filter
            """, (
                r["ticker"], r["scan_date"], r["price"],
                r["sma20"], r["sma50"], r["sma200"], r["ema10"], r["ema21"],
                r["rsi"], r["macd"], r["macd_signal"], r["volume_ratio"],
                r["high_52w"], r["low_52w"], r["pct_from_high"], r["atr"],
                r["stage2_uptrend"], r["vcp_tightening"], r["passed_filter"],
            ))

        # market_health の stage2_count は LONG のみ
        cur.execute("SELECT COUNT(*) FROM price_data GROUP BY ticker HAVING COUNT(*) > 0")
        total = len(cur.fetchall())
        long_count = sum(1 for r in results if r["stage2_uptrend"] == 1)
        cur.execute("""
            INSERT INTO market_health
                (date, overall_score, overall_signal, sector_scores, theme_scores, total_screened, stage2_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (date) DO UPDATE SET
                overall_score=EXCLUDED.overall_score, overall_signal=EXCLUDED.overall_signal,
                sector_scores=EXCLUDED.sector_scores, theme_scores=EXCLUDED.theme_scores,
                total_screened=EXCLUDED.total_screened, stage2_count=EXCLUDED.stage2_count
        """, (today, 0, "", "{}", "{}", total, long_count))


# ── Main ─────────────────────────────────────────────────────────────────────

def run(tickers: list[str]) -> dict:
    """
    Returns {"longs": list[str], "shorts": list[str]}.
    Indicators computed once per ticker; mutually exclusive filters applied.
    """
    print(f"[Stage3] Screening {len(tickers)} tickers (long + short)...")
    today        = date.today().isoformat()
    conn         = get_connection()
    long_results  = []
    short_results = []
    skipped       = 0

    for i, ticker in enumerate(tickers):
        if i % 100 == 0 and i > 0:
            print(f"[Stage3] {i}/{len(tickers)} | long={len(long_results)} short={len(short_results)}")
        try:
            df = load_price_df(ticker, conn)
            if df is None:
                skipped += 1
                continue
            df_ind = calculate_indicators(df)   # compute once

            r = _screen_long(ticker, df_ind, today)
            if r:
                long_results.append(r)
                continue  # Stage 2 ↔ Stage 4 は排他

            r = _screen_short(ticker, df_ind, today)
            if r:
                short_results.append(r)
        except Exception:
            skipped += 1

    conn.close()
    save_results(long_results + short_results)

    print(f"[Stage3] Done — long={len(long_results)}, short={len(short_results)}, skipped={skipped}")
    return {
        "longs":  [r["ticker"] for r in long_results],
        "shorts": [r["ticker"] for r in short_results],
    }


if __name__ == "__main__":
    from backend.db import init_db, get_connection as gc
    init_db()
    conn = gc()
    cur  = conn.cursor()
    cur.execute("SELECT DISTINCT ticker FROM price_data LIMIT 200")
    tickers = [row[0] for row in cur.fetchall()]
    conn.close()
    result = run(tickers)
    print(f"Longs: {result['longs'][:5]}  Shorts: {result['shorts'][:5]}")
