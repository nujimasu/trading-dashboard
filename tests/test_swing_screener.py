from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.services.swing_screener import (
    adx14,
    dip_check,
    dow_trend,
    screen_universe,
    volume_assessment,
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
        "volume",
        "levels",
    }
    assert set(rows[0]["levels"]) == {"ema20", "swing_high", "swing_low", "vol_band"}
    assert rows[0]["volume"]["verdict"] in {
        "selling_climax", "accumulation", "distribution", "selling_pressure",
        "healthy_pullback", "quiet_setup", "neutral",
    }


def _volume_frame(verdict: str) -> pd.DataFrame:
    index = pd.bdate_range("2026-01-01", periods=70)
    close = np.linspace(90.0, 100.0, len(index))
    df = _frame(index, close, volume=100.0)

    if verdict == "selling_climax":
        df.iloc[-1, df.columns.get_loc("Open")] = 91.0
        df.iloc[-1, df.columns.get_loc("Close")] = 80.0
        df.iloc[-1, df.columns.get_loc("High")] = 92.0
        df.iloc[-1, df.columns.get_loc("Low")] = 79.0
        df.iloc[-1, df.columns.get_loc("Volume")] = 300.0
    elif verdict == "accumulation":
        df.iloc[-1, df.columns.get_loc("Open")] = 79.0
        df.iloc[-1, df.columns.get_loc("Close")] = 80.0
        df.iloc[-1, df.columns.get_loc("High")] = 81.0
        df.iloc[-1, df.columns.get_loc("Low")] = 78.0
        df.iloc[-1, df.columns.get_loc("Volume")] = 200.0
    elif verdict == "distribution":
        df.iloc[-6:, df.columns.get_loc("Close")] = 100.0
        df.iloc[-5:, df.columns.get_loc("Volume")] = 150.0
    elif verdict == "selling_pressure":
        df.iloc[-6, df.columns.get_loc("Close")] = 100.0
        df.iloc[-5:, df.columns.get_loc("Close")] = np.linspace(98.0, 90.0, 5)
        df.iloc[-5:, df.columns.get_loc("Open")] = df["Close"].iloc[-5:] - 0.2
        df.iloc[-5:, df.columns.get_loc("Volume")] = 150.0
    elif verdict == "healthy_pullback":
        df.iloc[-6, df.columns.get_loc("Close")] = 100.0
        df.iloc[-5:, df.columns.get_loc("Close")] = np.linspace(99.0, 95.0, 5)
        df.iloc[-5:, df.columns.get_loc("Open")] = df["Close"].iloc[-5:] - 0.2
        df.iloc[-5:, df.columns.get_loc("Volume")] = 70.0
    elif verdict == "quiet_setup":
        df.iloc[-6:, df.columns.get_loc("Close")] = 100.0
        df.iloc[-10:-5, df.columns.get_loc("High")] = df["Close"].iloc[-10:-5] + 2.0
        df.iloc[-10:-5, df.columns.get_loc("Low")] = df["Close"].iloc[-10:-5] - 2.0
        df.iloc[-5:, df.columns.get_loc("High")] = 100.5
        df.iloc[-5:, df.columns.get_loc("Low")] = 99.5
        df.iloc[-5:, df.columns.get_loc("Volume")] = 70.0
    elif verdict == "neutral":
        pass
    else:
        raise ValueError(verdict)
    return df


@pytest.mark.parametrize(
    "expected",
    [
        "selling_climax",
        "accumulation",
        "distribution",
        "selling_pressure",
        "healthy_pullback",
        "quiet_setup",
        "neutral",
    ],
)
def test_volume_assessment_verdicts(expected):
    result = volume_assessment(_volume_frame(expected))
    assert result is not None
    assert result["verdict"] == expected
    assert result["comment"]
    assert len(result["week_bars"]) == 5
    assert all(bar["date"].startswith("2026-") for bar in result["week_bars"])
    assert result["week_bars"][-1]["vol_ratio"] == pytest.approx(
        result["vol_ratio_today"]
    )


def test_volume_assessment_embeds_measured_values_and_bar_ratio():
    result = volume_assessment(_volume_frame("selling_pressure"))
    assert result is not None
    assert f"{result['week_price_chg'] * 100:.1f}%" in result["comment"]
    assert f"{result['week_vol_ratio']:.1f}倍" in result["comment"]
    expected_ratio = 150.0 / ((45 * 100.0 + 5 * 150.0) / 50.0)
    assert result["week_bars"][-1]["vol_ratio"] == pytest.approx(expected_ratio)


def test_volume_assessment_returns_none_for_insufficient_data():
    short = _frame(pd.bdate_range("2026-01-01", periods=59), np.arange(59) + 100.0)
    assert volume_assessment(short) is None


def _bounce_volume_frame(latest_volume: float) -> pd.DataFrame:
    df = _volume_frame("neutral")
    df.iloc[-1, df.columns.get_loc("Volume")] = latest_volume
    return df


@pytest.mark.parametrize(
    ("bounced", "latest_volume", "expected", "comment_fragment"),
    [
        (True, 130.0, "bounce_confirmed", "押し目買いが入っている"),
        (True, 50.0, "weak_bounce", "だましの可能性"),
    ],
)
def test_volume_assessment_bounce_verdicts(
    bounced, latest_volume, expected, comment_fragment
):
    result = volume_assessment(
        _bounce_volume_frame(latest_volume), bounced=bounced
    )
    assert result is not None
    assert result["verdict"] == expected
    assert f"{result['vol_ratio_today']:.1f}倍" in result["comment"]
    assert comment_fragment in result["comment"]


def test_volume_assessment_pulling_low_volume_is_healthy():
    df = _bounce_volume_frame(70.0)
    df.iloc[-1, df.columns.get_loc("Open")] = df["Close"].iloc[-1] + 0.2
    result = volume_assessment(df, bounced=False)
    assert result is not None
    assert result["verdict"] == "healthy_pullback"
    assert result["comment"] == (
        f"押し目進行中で当日出来高は{result['vol_ratio_today']:.1f}倍に収縮。"
        "売り急ぎがなく健全"
    )


def test_volume_assessment_accumulation_precedes_bounce_confirmed():
    result = volume_assessment(_volume_frame("accumulation"), bounced=True)
    assert result is not None
    assert result["verdict"] == "accumulation"


def test_volume_assessment_none_bounced_skips_new_rules():
    result = volume_assessment(_bounce_volume_frame(130.0), bounced=None)
    assert result is not None
    assert result["verdict"] == "neutral"
