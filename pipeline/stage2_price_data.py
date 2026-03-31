"""
Stage 2: Bulk OHLCV download via yfinance.
Downloads 1 year of daily data for all universe tickers in batches.
"""
import sys
import time
import sqlite3
from pathlib import Path
from datetime import datetime

import yfinance as yf
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DOWNLOAD_BATCH_SIZE, PRICE_HISTORY_PERIOD
from backend.db import get_connection


def save_price_batch(df: pd.DataFrame, tickers: list[str]):
    """Save a multi-ticker yfinance download to price_data table."""
    conn = get_connection()
    cur  = conn.cursor()
    saved = 0

    for ticker in tickers:
        try:
            # yfinance multi-download has MultiIndex columns: (field, ticker)
            if isinstance(df.columns, pd.MultiIndex):
                t_df = df.xs(ticker, axis=1, level=1, drop_level=True)
            else:
                t_df = df

            t_df = t_df.dropna(subset=["Close"])

            rows = [
                (
                    ticker,
                    str(idx.date()),
                    float(row["Open"])   if not pd.isna(row["Open"])   else None,
                    float(row["High"])   if not pd.isna(row["High"])   else None,
                    float(row["Low"])    if not pd.isna(row["Low"])    else None,
                    float(row["Close"])  if not pd.isna(row["Close"])  else None,
                    int(row["Volume"])   if not pd.isna(row["Volume"]) else 0,
                )
                for idx, row in t_df.iterrows()
            ]

            cur.executemany("""
                INSERT INTO price_data (ticker, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (ticker, date) DO UPDATE SET
                    open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                    close=EXCLUDED.close, volume=EXCLUDED.volume
            """, rows)
            saved += 1
        except Exception as e:
            pass  # ticker not in this batch's data

    conn.commit()
    conn.close()
    return saved


def run(tickers: list[str]) -> list[str]:
    """Download price data for all tickers. Returns list of successfully downloaded tickers."""
    print(f"[Stage2] Downloading price data for {len(tickers)} tickers...")
    successful = []
    batches    = [tickers[i:i + DOWNLOAD_BATCH_SIZE] for i in range(0, len(tickers), DOWNLOAD_BATCH_SIZE)]

    for i, batch in enumerate(batches):
        batch_str = " ".join(batch)
        print(f"[Stage2] Batch {i+1}/{len(batches)} ({len(batch)} tickers)...", end=" ", flush=True)
        try:
            df = yf.download(
                batch_str,
                period=PRICE_HISTORY_PERIOD,
                auto_adjust=True,
                progress=False,
                threads=True,
            )
            if df.empty:
                print("empty")
                continue

            n = save_price_batch(df, batch)
            successful.extend(batch)
            print(f"saved {n}")
        except Exception as e:
            print(f"error: {e}")

        # Small pause to avoid overwhelming yfinance
        if i < len(batches) - 1:
            time.sleep(0.5)

    print(f"[Stage2] Done. {len(successful)}/{len(tickers)} tickers downloaded.")
    return successful


if __name__ == "__main__":
    from backend.db import init_db, get_connection as gc
    init_db()
    conn = gc()
    cur  = conn.cursor()
    cur.execute("SELECT ticker FROM universe LIMIT 20")
    tickers = [row["ticker"] for row in cur.fetchall()]
    conn.close()
    run(tickers)
