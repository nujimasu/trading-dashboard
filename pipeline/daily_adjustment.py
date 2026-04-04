"""
Daily adjustment: Re-fetch latest prices for weekly picks and update daily_picks.
Runs in < 1 minute. No FMP calls needed.
"""
import sys
import json
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

import yfinance as yf
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.db import get_connection, db_cursor
from backend.services.indicators import calculate_indicators
from config import ATR_MULT, STOP_WINDOW, TARGET_WINDOW, MIN_RR_TIER2


def _get_jst_date():
    """Get today's date in JST (Asia/Tokyo)"""
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).date().isoformat()


def run():
    today = _get_jst_date()
    print(f"[Daily] Adjusting picks for {today}...")

    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT ticker, stop_price, target_price, direction FROM weekly_picks")
    picks = [dict(r) for r in cur.fetchall()]

    # Load fundamentals and technical_screen for take-profit detection
    funda_map, ts_map = {}, {}
    for p in picks:
        t = p["ticker"]
        cur.execute("SELECT * FROM fundamentals WHERE ticker = ?", (t,))
        row = cur.fetchone()
        if row:
            funda_map[t] = dict(row)
        cur.execute("SELECT * FROM technical_screen WHERE ticker = ?", (t,))
        row = cur.fetchone()
        if row:
            ts_map[t] = dict(row)
    conn.close()

    if not picks:
        print("[Daily] No weekly picks found. Run full pipeline first.")
        return

    tickers = [p["ticker"] for p in picks]
    ticker_map = {p["ticker"]: p for p in picks}

    # Fetch latest day only
    try:
        df_all = yf.download(
            " ".join(tickers),
            period="5d",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
    except Exception as e:
        print(f"[Daily] yfinance error: {e}")
        return

    daily_rows = []
    for ticker in tickers:
        try:
            if isinstance(df_all.columns, pd.MultiIndex):
                df = df_all.xs(ticker, axis=1, level=1, drop_level=True).dropna()
            else:
                df = df_all.dropna()

            if df.empty:
                continue

            latest   = df.iloc[-1]
            price    = float(latest["Close"])
            volume   = float(latest["Volume"])

            # Avg volume from last 5 days
            vol_avg  = float(df["Volume"].mean())
            vol_conf = volume > vol_avg * 1.5

            original_stop   = ticker_map[ticker]["stop_price"]  or 0
            original_target = ticker_map[ticker]["target_price"] or 0
            direction       = ticker_map[ticker].get("direction", "LONG")

            # Adjusted RR based on current price (direction-aware)
            if direction == "SHORT":
                risk   = original_stop - price  if original_stop  > 0 else 0
                reward = price - original_target if original_target > 0 else 0
            else:
                risk   = price - original_stop   if original_stop  > 0 else 0
                reward = original_target - price  if original_target > 0 else 0
            adj_rr = (reward / risk) if risk > 0 else 0

            # Check breakout: price vs weekly entry price
            conn2 = get_connection()
            cur2 = conn2.cursor()
            cur2.execute("SELECT entry_price FROM weekly_picks WHERE ticker = ?", (ticker,))
            row = cur2.fetchone()
            pivot = float(row["entry_price"]) if row else price
            conn2.close()

            # LONG: price breaks above pivot / SHORT: price breaks below pivot
            if direction == "SHORT":
                breakout = price < pivot * 0.995  # 0.5% below entry
            else:
                breakout = price > pivot * 1.005  # 0.5% above entry

            if adj_rr >= 2.0 and breakout and vol_conf:
                verdict = "ENTRY_NOW"
            elif adj_rr >= MIN_RR_TIER2 and not breakout:
                verdict = "WAIT"
            elif adj_rr < MIN_RR_TIER2:
                verdict = "PASSED"
            else:
                verdict = "WATCH"

            notes = []
            if breakout:
                notes.append("ピボット突破")
            if vol_conf:
                notes.append(f"出来高急増({volume/vol_avg:.1f}x)")
            if adj_rr < MIN_RR_TIER2:
                notes.append(f"RR低下({adj_rr:.2f})")

            # Take-profit detection
            from pipeline.stage6_scoring import compute_take_profit_signals
            tp = compute_take_profit_signals(funda_map.get(ticker), ts_map.get(ticker))

            daily_rows.append({
                "ticker":               ticker,
                "date":                 today,
                "current_price":        round(price, 2),
                "adjusted_rr":          round(adj_rr, 2),
                "breakout_triggered":   1 if breakout else 0,
                "volume_confirmation":  1 if vol_conf else 0,
                "daily_verdict":        verdict,
                "notes":                "、".join(notes),
                "take_profit_verdict":  tp["verdict"],
                "take_profit_signals":  "、".join(tp["signals"]),
            })
            print(f"  {ticker:6s} | ${price:.2f} | RR={adj_rr:.2f} | {verdict}")

        except Exception as e:
            print(f"  [ERR] {ticker}: {e}")

    # Save
    with db_cursor() as cur:
        for row in daily_rows:
            cur.execute("""
                INSERT INTO daily_picks
                    (ticker, date, current_price, adjusted_rr,
                     breakout_triggered, volume_confirmation, daily_verdict, notes,
                     take_profit_verdict, take_profit_signals)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT (ticker, date) DO UPDATE SET
                    current_price=EXCLUDED.current_price, adjusted_rr=EXCLUDED.adjusted_rr,
                    breakout_triggered=EXCLUDED.breakout_triggered,
                    volume_confirmation=EXCLUDED.volume_confirmation,
                    daily_verdict=EXCLUDED.daily_verdict, notes=EXCLUDED.notes,
                    take_profit_verdict=EXCLUDED.take_profit_verdict,
                    take_profit_signals=EXCLUDED.take_profit_signals
            """, (
                row["ticker"], row["date"], row["current_price"], row["adjusted_rr"],
                row["breakout_triggered"], row["volume_confirmation"],
                row["daily_verdict"], row["notes"],
                row["take_profit_verdict"], row["take_profit_signals"],
            ))

    print(f"[Daily] Done. {len(daily_rows)} tickers updated.")


if __name__ == "__main__":
    from backend.db import init_db
    init_db()
    run()
