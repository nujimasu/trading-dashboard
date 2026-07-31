from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.services.swing_screener import (
    adx14,
    dip_check,
    dow_trend,
    screen_universe,
    weekly_po,
)


def _frame(index: pd.DatetimeIndex, close: np.ndarray, volume: float = 1_000_000) -> pd.DataFrame:
    close = np.asarray(close, dtype=float)
    return pd.DataFrame(
        {
            "Open": close - 0.2,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": np.full(len(close), volume),
        },
        index=index,
    )


def _weekly_growth(weeks: int = 260) -> pd.DataFrame:
    index = pd.date_range("2020-01-03", periods=weeks, freq="W-FRI")
    return _frame(index, np.linspace(20.0, 220.0, weeks))


def test_weekly_po_accepts_rising_perfect_order():
    result = weekly_po(_weekly_growth())
    assert result is not None
    assert result["po_weeks"] > 0


def test_weekly_po_rejects_broken_order():
    df = _weekly_growth()
    df.loc[df.index[-1], "Close"] = 1.0
    assert weekly_po(df) is None


def test_weekly_po_requires_210_weeks():
    assert weekly_po(_weekly_growth(209)) is None


def _dip_frame(touch_days_ago: int, bounced: bool = True) -> pd.DataFrame:
    index = pd.bdate_range("2026-01-01", periods=80)
    close = np.arange(80, dtype=float) + 50.0
    df = _frame(index, close)
    ema = df["Close"].ewm(span=20, adjust=False).mean()
    df["Low"] = df["Close"] - 0.1
    df.iloc[-touch_days_ago, df.columns.get_loc("Low")] = ema.iloc[-touch_days_ago]
    df.iloc[-1, df.columns.get_loc("Open")] = close[-1] - 0.5 if bounced else close[-1] + 0.5
    return df


def test_dip_check_reports_latest_touch_and_bounce():
    result = dip_check(_dip_frame(2, bounced=True))
    assert result is not None
    assert result["touch_days_ago"] == 2
    assert result["bounced"] is True


def test_dip_check_reports_pulling_state():
    result = dip_check(_dip_frame(1, bounced=False))
    assert result is not None
    assert result["touch_days_ago"] == 1
    assert result["bounced"] is False


def test_dip_check_rejects_touch_four_days_ago():
    assert dip_check(_dip_frame(4)) is None


def test_dip_check_rejects_close_below_ema20():
    df = _dip_frame(1)
    df.iloc[-1, df.columns.get_loc("Close")] -= 30.0
    df.iloc[-1, df.columns.get_loc("Low")] = df["Close"].iloc[-1] - 1.0
    assert dip_check(df) is None


def _swing_frame(high_1: float, low_1: float, high_2: float, low_2: float) -> pd.DataFrame:
    anchors_x = np.array([0, 10, 20, 30, 40, 55])
    anchors_y = np.array([100, high_1, low_1, high_2, low_2, (high_2 + low_2) / 2])
    close = np.interp(np.arange(56), anchors_x, anchors_y)
    return _frame(pd.bdate_range("2025-01-01", periods=56), close)


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ((110, 90, 120, 100), "up"),
        ((120, 100, 110, 90), "down"),
        ((110, 100, 120, 90), "neutral"),
    ],
)
def test_dow_trend_classifies_two_swings(values, expected):
    assert dow_trend(_swing_frame(*values), k=3) == expected


def test_adx_directional_trend_exceeds_flat_market():
    index = pd.bdate_range("2025-01-01", periods=120)
    trend = _frame(index, np.linspace(50, 170, len(index)))
    flat = _frame(index, np.full(len(index), 100.0))
    assert adx14(trend) > adx14(flat)


def _screen_frame(mode: str = "pass", rows: int = 1400, volume: float = 1_000_000) -> pd.DataFrame:
    index = pd.bdate_range("2020-01-01", periods=rows)
    if mode == "nopo":
        close = np.full(rows, 100.0)
    else:
        close = np.linspace(30.0, 140.0, rows)
    df = _frame(index, close, volume=volume)
    if mode == "nodip":
        df.loc[df.index[-3:], "Low"] = df.loc[df.index[-3:], "Close"] + 10.0
    return df


def test_screen_universe_funnel_and_row_schema():
    spy = _screen_frame()
    store = {
        "AAA": _screen_frame(),
        "ILLIQ": _screen_frame(volume=1.0),
        "SHORT": _screen_frame(rows=1200),
        "NOPO": _screen_frame(mode="nopo"),
        "NODIP": _screen_frame(mode="nodip"),
    }
    rows, funnel = screen_universe(store, spy)
    assert funnel == {"universe": 4, "liquid": 3, "po": 2, "dip": 1}
    assert len(rows) == 1
    assert set(rows[0]) == {
        "ticker",
        "price",
        "state",
        "touch_days_ago",
        "dow_trend",
        "adx",
        "rs63",
        "rs126",
        "atr_pct",
        "dollar_vol",
        "ema20_dist",
        "po_weeks",
        "levels",
    }
    assert set(rows[0]["levels"]) == {"ema20", "swing_high", "swing_low", "vol_band"}
