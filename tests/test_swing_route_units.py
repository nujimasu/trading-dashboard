from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from backend.routes.swing import _format_intraday_bars
from backend.services.swing_screener import screen_universe
from pipeline.swing_scan import (
    _append_grouped_results,
    _pending_update_days,
    _replace_picks,
)


NEW_YORK = ZoneInfo("America/New_York")


def _polygon_bar(day: str, hour: int, minute: int, price: float) -> dict[str, float]:
    local = datetime.fromisoformat(f"{day}T{hour:02d}:{minute:02d}:00").replace(
        tzinfo=NEW_YORK
    )
    return {
        "t": int(local.astimezone(timezone.utc).timestamp() * 1000),
        "o": price,
        "h": price + 1,
        "l": price - 1,
        "c": price + 0.5,
        "v": 100,
    }


def test_format_intraday_bars_filters_rth_and_keeps_latest_five_sessions():
    days = ["2026-07-23", "2026-07-24", "2026-07-27", "2026-07-28", "2026-07-29", "2026-07-30"]
    results = []
    for index, day in enumerate(days):
        results.extend(
            [
                _polygon_bar(day, 8, 0, 100 + index),
                _polygon_bar(day, 9, 30, 101 + index),
                _polygon_bar(day, 16, 15, 102 + index),
            ]
        )

    bars, detector = _format_intraday_bars(results, extended=False)

    assert len(bars) == 5
    assert len(detector) == 5
    assert datetime.fromtimestamp(bars[0]["time"], timezone.utc).strftime(
        "%Y-%m-%d %H:%M"
    ) == "2026-07-24 09:30"
    assert detector[0]["t"] == bars[0]["time"]


def test_format_intraday_bars_extended_includes_pre_and_post_market():
    results = [
        _polygon_bar("2026-07-30", 8, 0, 100),
        _polygon_bar("2026-07-30", 9, 30, 101),
        _polygon_bar("2026-07-30", 16, 15, 102),
    ]

    bars, _ = _format_intraday_bars(results, extended=True)

    assert [
        datetime.fromtimestamp(bar["time"], timezone.utc).strftime("%H:%M")
        for bar in bars
    ] == ["08:00", "09:30", "16:15"]


def test_append_grouped_results_is_idempotent_and_does_not_add_unknown_ticker():
    original = pd.DataFrame(
        {"Open": [10], "High": [11], "Low": [9], "Close": [10], "Volume": [100]},
        index=pd.DatetimeIndex(["2026-07-29"]),
    )
    store = {"AAA": original}
    results = [
        {"T": "AAA", "o": 11, "h": 13, "l": 10, "c": 12, "v": 200},
        {"T": "NEW", "o": 20, "h": 21, "l": 19, "c": 20, "v": 300},
    ]

    _append_grouped_results(store, results, "2026-07-30")
    _append_grouped_results(store, results, "2026-07-30")

    assert list(store) == ["AAA"]
    assert store["AAA"].index.is_unique
    assert len(store["AAA"]) == 2
    assert store["AAA"].loc["2026-07-30", "Close"] == 12


def test_pending_days_refetch_latest_and_exclude_unclosed_et_day():
    latest = pd.Timestamp("2026-07-29")

    before_close = _pending_update_days(
        latest, datetime(2026, 7, 30, 16, 14, tzinfo=NEW_YORK)
    )
    after_close = _pending_update_days(
        latest, datetime(2026, 7, 30, 16, 16, tzinfo=NEW_YORK)
    )

    assert list(before_close.strftime("%Y-%m-%d")) == ["2026-07-29"]
    assert list(after_close.strftime("%Y-%m-%d")) == ["2026-07-29", "2026-07-30"]


def _screen_frame(end: str) -> pd.DataFrame:
    index = pd.bdate_range(end=end, periods=1400)
    close = np.linspace(30.0, 140.0, len(index))
    return pd.DataFrame(
        {
            "Open": close - 0.2,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": np.full(len(index), 1_000_000),
        },
        index=index,
    )


def test_screen_universe_excludes_symbol_with_stale_latest_bar():
    scan_date = pd.Timestamp("2026-07-30")
    fresh = _screen_frame("2026-07-30")
    stale = _screen_frame("2026-07-29")

    rows, funnel = screen_universe(
        {"FRESH": fresh, "STALE": stale}, fresh, scan_date=scan_date
    )

    assert [row["ticker"] for row in rows] == ["FRESH"]
    assert funnel["universe"] == 1


def _pick(ticker: str) -> dict[str, object]:
    return {
        "ticker": ticker,
        "price": 100.0,
        "state": "pulling",
        "touch_days_ago": 1,
        "dow_trend": "up",
        "adx": 25.0,
        "rs63": 0.1,
        "rs126": 0.2,
        "atr_pct": 0.03,
        "dollar_vol": 50_000_000.0,
        "ema20_dist": 0.01,
        "po_weeks": 4,
        "levels": {"ema20": 99.0},
    }


def test_replace_picks_removes_obsolete_rows_for_same_scan_date():
    connection = sqlite3.connect(":memory:")
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE swing_picks (
            scan_date TEXT, ticker TEXT, price REAL, state TEXT,
            touch_days_ago INTEGER, dow_trend TEXT, adx REAL, rs63 REAL,
            rs126 REAL, atr_pct REAL, dollar_vol REAL, ema20_dist REAL,
            po_weeks INTEGER, levels TEXT,
            UNIQUE(scan_date, ticker)
        )
        """
    )

    _replace_picks(cursor, "2026-07-30", [_pick("AAA"), _pick("OLD")])
    _replace_picks(cursor, "2026-07-30", [_pick("AAA"), _pick("NEW")])

    tickers = cursor.execute(
        "SELECT ticker FROM swing_picks WHERE scan_date = ? ORDER BY ticker",
        ("2026-07-30",),
    ).fetchall()
    assert tickers == [("AAA",), ("NEW",)]
    connection.close()
