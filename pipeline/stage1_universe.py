"""
Stage 1: Build/refresh ticker universe.
Uses FMP /stock/list (1 API call) filtered by exchange + market cap,
or falls back to a static S&P 500 + NASDAQ 100 list from Wikipedia.
"""
import sys
import json
import sqlite3
import requests
import concurrent.futures
from datetime import datetime
from pathlib import Path

import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import FMP_API_KEY, FMP_BASE_URL, MIN_MARKET_CAP_M, SECTOR_DISPLAY
from backend.db import db_cursor, get_connection, increment_fmp_call_count


VALID_EXCHANGES = {"NYSE", "NASDAQ", "AMEX", "NYSE American"}


def fetch_from_fmp() -> list[dict]:
    """Fetch full US stock list from FMP (1 API call). Returns [] if unavailable."""
    if not FMP_API_KEY:
        return []
    url = f"{FMP_BASE_URL}/stock/list"
    try:
        resp = requests.get(url, params={"apikey": FMP_API_KEY}, timeout=30)
        if resp.status_code == 403:
            # /stock/list is not available on the free FMP plan — skip silently
            return []
        resp.raise_for_status()
        increment_fmp_call_count(datetime.now().date().isoformat())
        data = resp.json()
        return [
            {
                "ticker":     s["symbol"],
                "name":       s.get("name", ""),
                "sector":     "",
                "industry":   "",
                "market_cap": 0,
                "exchange":   s.get("exchangeShortName", ""),
            }
            for s in data
            if s.get("exchangeShortName") in VALID_EXCHANGES
            and s.get("type") == "stock"
            and s.get("symbol")
            and "." not in s["symbol"]
            and len(s["symbol"]) <= 5
        ]
    except Exception as e:
        print(f"[Stage1] FMP error: {e}")
        return []


def fetch_from_static() -> list[dict]:
    """Fallback: use bundled static ticker list (~600 major US stocks)."""
    from pipeline.static_universe import UNIQUE_TICKERS
    return [
        {"ticker": t, "name": "", "sector": "", "industry": "", "market_cap": 0, "exchange": ""}
        for t in UNIQUE_TICKERS
    ]


def save_universe(stocks: list[dict]):
    now = datetime.now().isoformat()
    conn = get_connection()
    cur  = conn.cursor()
    for s in stocks:
        cur.execute("""
            INSERT INTO universe (ticker, name, sector, industry, market_cap, exchange, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                name=excluded.name,
                exchange=excluded.exchange,
                updated_at=excluded.updated_at
        """, (s["ticker"], s["name"], s["sector"], s["industry"], s["market_cap"], s["exchange"], now))
    conn.commit()
    conn.close()


def _fetch_sector_yf(ticker: str) -> tuple[str, str]:
    """Fetch sector for a single ticker from yfinance. Returns (ticker, sector_jp)."""
    try:
        info = yf.Ticker(ticker).info
        sector_en = info.get("sector", "") or ""
        sector_jp = SECTOR_DISPLAY.get(sector_en, sector_en)
        return ticker, sector_jp
    except Exception:
        return ticker, ""


def enrich_sectors(tickers: list[str], max_workers: int = 15):
    """Fetch sector info from yfinance for tickers with empty sector in universe table."""
    # Find tickers that still need sector data
    conn = get_connection()
    cur  = conn.cursor()
    placeholders = ",".join("?" * len(tickers))
    cur.execute(
        f"SELECT ticker FROM universe WHERE ticker IN ({placeholders}) AND (sector = '' OR sector IS NULL)",
        tickers,
    )
    missing = [r["ticker"] for r in cur.fetchall()]
    conn.close()

    if not missing:
        return

    print(f"[Stage1] Fetching sector info for {len(missing)} tickers via yfinance...")
    updates = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        for ticker, sector_jp in executor.map(_fetch_sector_yf, missing):
            if sector_jp:
                updates.append((sector_jp, ticker))

    if updates:
        conn = get_connection()
        cur  = conn.cursor()
        cur.executemany("UPDATE universe SET sector = ? WHERE ticker = ?", updates)
        conn.commit()
        conn.close()
        print(f"[Stage1] Sector updated for {len(updates)}/{len(missing)} tickers.")
    else:
        print("[Stage1] No sector data fetched.")


def run() -> list[str]:
    print("[Stage1] Building ticker universe...")
    stocks = fetch_from_fmp()

    if len(stocks) < 100:
        stocks = fetch_from_static()

    if not stocks:
        raise RuntimeError("[Stage1] Failed to build universe from any source.")

    save_universe(stocks)
    tickers = [s["ticker"] for s in stocks]
    print(f"[Stage1] Universe: {len(tickers)} tickers saved.")

    # Enrich missing sector data via yfinance (cached in DB, only runs for empty entries)
    enrich_sectors(tickers)

    return tickers


if __name__ == "__main__":
    from backend.db import init_db
    init_db()
    tickers = run()
    print(f"Sample: {tickers[:10]}")
