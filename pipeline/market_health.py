from __future__ import annotations

"""Market-health calculation extracted from the legacy scoring stage."""

import json
from datetime import date

import numpy as np
import pandas as pd

from backend.services.indicators import calculate_indicators
from config import (
    HEALTH_BEARISH_THRESHOLD,
    HEALTH_BULLISH_THRESHOLD,
    PCT_FROM_HIGH_MAX,
    PRICE_RANGE_TIGHTEN_DAYS,
    RSI_MAX,
    RSI_MIN,
    SECTOR_DISPLAY,
    THEME_MAP,
)


def _is_stage2_uptrend(df: pd.DataFrame) -> bool:
    """Apply the legacy Stage 3 ``_screen_long`` conditions unchanged."""
    if len(df) < 200:
        return False

    try:
        enriched = calculate_indicators(df)
        latest = enriched.iloc[-1]

        price = float(latest["Close"])
        sma50 = float(latest["SMA50"]) if not np.isnan(latest["SMA50"]) else None
        sma200 = float(latest["SMA200"]) if not np.isnan(latest["SMA200"]) else None
        rsi = float(latest["RSI"]) if not np.isnan(latest["RSI"]) else None
        macd = float(latest["MACD"])
        macd_signal = float(latest["MACDSig"])
        volume = float(latest["Volume"])
        volume_sma50 = (
            float(latest["VolSMA50"])
            if not np.isnan(latest["VolSMA50"])
            else 0
        )

        high_52w = float(enriched["High"].iloc[-252:].max())
        pct_from_high = (price / high_52w - 1) if high_52w > 0 else -1

        if sma50 is None or sma200 is None or not (price > sma50 > sma200):
            return False
        if rsi is None or not (RSI_MIN <= rsi <= RSI_MAX):
            return False
        if macd <= macd_signal:
            return False
        if pct_from_high < -PCT_FROM_HIGH_MAX:
            return False

        volume_contraction = volume_sma50 > 0 and volume < volume_sma50
        if len(enriched) >= PRICE_RANGE_TIGHTEN_DAYS * 2:
            recent_range = float(
                enriched["High"].iloc[-PRICE_RANGE_TIGHTEN_DAYS:].max()
                - enriched["Low"].iloc[-PRICE_RANGE_TIGHTEN_DAYS:].min()
            )
            prior_range = float(
                enriched["High"].iloc[
                    -PRICE_RANGE_TIGHTEN_DAYS * 2:-PRICE_RANGE_TIGHTEN_DAYS
                ].max()
                - enriched["Low"].iloc[
                    -PRICE_RANGE_TIGHTEN_DAYS * 2:-PRICE_RANGE_TIGHTEN_DAYS
                ].min()
            )
            range_tightening = recent_range < prior_range
        else:
            range_tightening = False

        return volume_contraction or range_tightening
    except (KeyError, TypeError, ValueError, IndexError):
        return False


def _load_stage2_flags(cur) -> dict[str, bool]:
    # 日本AIマップ用の東証銘柄（".T" サフィックス）は price_data に同居しているが、
    # 市場ヘルスは米国市場のスコアなので除外する。
    cur.execute("""
        SELECT ticker, date, open, high, low, close, volume
        FROM price_data
        WHERE ticker NOT LIKE '%.T'
        ORDER BY ticker, date
    """)
    rows = cur.fetchall()
    columns = ["ticker", "date", "open", "high", "low", "close", "volume"]
    by_ticker: dict[str, list[dict]] = {}
    for row in rows:
        item = dict(row)
        if item["ticker"] is None:
            continue
        by_ticker.setdefault(item["ticker"], []).append(item)

    flags = {}
    for ticker, ticker_rows in by_ticker.items():
        if len(ticker_rows) < 200:
            flags[ticker] = False
            continue
        frame = pd.DataFrame(ticker_rows, columns=columns)
        frame = frame.rename(columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        })
        for column in ("Open", "High", "Low", "Close", "Volume"):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        flags[ticker] = _is_stage2_uptrend(frame)
    return flags


def compute_market_health(conn):
    """Compute sector + theme health scores and update market_health table.

    基準日は実行日ではなく price_data の最新日を使う。Polygon 無料枠の EOD は
    配信が遅れるため、実行日を使うと「当日の日付が付いた前営業日のスコア」になる。
    """
    cur = conn.cursor()
    cur.execute("SELECT MAX(date) AS latest FROM price_data")
    row = cur.fetchone()
    as_of = str(row["latest"])[:10] if row and row["latest"] else date.today().isoformat()
    stage2_flags = _load_stage2_flags(cur)
    total_screened = len(stage2_flags)
    stage2_count = sum(stage2_flags.values())

    overall_score = round((stage2_count / total_screened * 100), 1) if total_screened > 0 else 0
    if overall_score >= HEALTH_BULLISH_THRESHOLD:
        signal = "Bullish"
    elif overall_score >= HEALTH_BEARISH_THRESHOLD:
        signal = "Neutral"
    else:
        signal = "Bearish"

    cur.execute("""
        SELECT ticker, sector
        FROM universe
        WHERE sector != '' AND sector IS NOT NULL
    """)
    sector_totals = {}
    sector_bullish = {}
    for row in cur.fetchall():
        sector = row["sector"]
        sector_totals[sector] = sector_totals.get(sector, 0) + 1
        if stage2_flags.get(row["ticker"], False):
            sector_bullish[sector] = sector_bullish.get(sector, 0) + 1

    sector_scores = {}
    for sector, total in sector_totals.items():
        bullish = sector_bullish.get(sector, 0)
        if total > 0:
            display = SECTOR_DISPLAY.get(sector, sector)
            sector_scores[display] = round(bullish / total * 100, 1)

    theme_scores = {}
    for theme, members in THEME_MAP.items():
        if not members:
            continue
        scanned_members = [ticker for ticker in members if ticker in stage2_flags]
        total = len(scanned_members)
        bullish = sum(stage2_flags[ticker] for ticker in scanned_members)
        if total > 0:
            theme_scores[theme] = round(bullish / total * 100, 1)

    cur.execute("""
        INSERT INTO market_health
            (date, overall_score, overall_signal, sector_scores, theme_scores, total_screened, stage2_count)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (date) DO UPDATE SET
            overall_score=EXCLUDED.overall_score, overall_signal=EXCLUDED.overall_signal,
            sector_scores=EXCLUDED.sector_scores, theme_scores=EXCLUDED.theme_scores,
            total_screened=EXCLUDED.total_screened, stage2_count=EXCLUDED.stage2_count
    """, (as_of, overall_score, signal,
          json.dumps(sector_scores, ensure_ascii=False),
          json.dumps(theme_scores, ensure_ascii=False),
          total_screened, stage2_count))
    conn.commit()

    print(f"[MarketHealth] as-of={as_of} (price_data 最新日), score={overall_score}%, signal={signal}")
    print(f"[MarketHealth] Sector scores: {sector_scores}")
    print(f"[MarketHealth] Theme scores:  {theme_scores}")
