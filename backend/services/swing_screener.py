"""Pure calculations for the weekly-PO / daily-dip swing screener."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from config import SWING_MIN_DOLLAR_VOLUME, SWING_MIN_HISTORY, SWING_MIN_PRICE


OHLCV_COLUMNS = ("Open", "High", "Low", "Close", "Volume")


def weekly_po(df: pd.DataFrame) -> dict[str, int] | None:
    """Return the current weekly perfect-order streak, including this week."""
    weekly_close = df["Close"].resample("W-FRI").last().dropna()
    if len(weekly_close) < 210:
        return None

    sma20 = weekly_close.rolling(20).mean()
    sma50 = weekly_close.rolling(50).mean()
    sma200 = weekly_close.rolling(200).mean()
    condition = (
        (weekly_close > sma20)
        & (sma20 > sma50)
        & (sma50 > sma200)
        & (sma20 > sma20.shift(4))
        & (sma50 > sma50.shift(4))
        & (sma200 > sma200.shift(4))
    ).fillna(False)
    if not bool(condition.iloc[-1]):
        return None

    values = condition.to_numpy(dtype=bool)
    streak = 0
    for active in values[::-1]:
        if not active:
            break
        streak += 1
    return {"po_weeks": int(streak)}


def dip_check(df: pd.DataFrame) -> dict[str, Any] | None:
    """Check for an EMA20 touch in the last three sessions and a close above it."""
    if df.empty:
        return None
    ema20 = df["Close"].ewm(span=20, adjust=False).mean()
    latest_ema = float(ema20.iloc[-1])
    latest_close = float(df["Close"].iloc[-1])
    if not np.isfinite(latest_ema) or latest_close <= latest_ema:
        return None

    touch = (df["Low"] <= ema20 * 1.02).tail(3).to_numpy(dtype=bool)
    touched_positions = np.flatnonzero(touch)
    if touched_positions.size == 0:
        return None
    touch_days_ago = len(touch) - int(touched_positions[-1])
    return {
        "touch_days_ago": int(touch_days_ago),
        "bounced": bool(latest_close > float(df["Open"].iloc[-1])),
        "ema20": latest_ema,
        "ema20_dist": float(latest_close / latest_ema - 1.0),
    }


def _confirmed_pivots(
    df: pd.DataFrame, k: int = 5, lookback: int | None = 300
) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Return confirmed high/low pivot positions and values."""
    frame = df.tail(lookback) if lookback is not None else df
    highs = frame["High"].to_numpy(dtype=float)
    lows = frame["Low"].to_numpy(dtype=float)
    high_pivots: list[tuple[int, float]] = []
    low_pivots: list[tuple[int, float]] = []
    if k < 1 or len(frame) < 2 * k + 1:
        return high_pivots, low_pivots

    for i in range(k, len(frame) - k):
        high_window = highs[i - k : i + k + 1]
        low_window = lows[i - k : i + k + 1]
        if np.isfinite(highs[i]) and highs[i] == np.nanmax(high_window):
            high_pivots.append((i, float(highs[i])))
        if np.isfinite(lows[i]) and lows[i] == np.nanmin(low_window):
            low_pivots.append((i, float(lows[i])))
    return high_pivots, low_pivots


def dow_trend(df: pd.DataFrame, k: int = 5, lookback: int = 300) -> str:
    """Classify the latest confirmed two highs and two lows using Dow theory."""
    highs, lows = _confirmed_pivots(df, k=k, lookback=lookback)
    if len(highs) < 2 or len(lows) < 2:
        return "unknown"
    h1, h2 = highs[-2][1], highs[-1][1]
    l1, l2 = lows[-2][1], lows[-1][1]
    if h2 > h1 and l2 > l1:
        return "up"
    if h2 < h1 and l2 < l1:
        return "down"
    return "neutral"


def _true_range(df: pd.DataFrame) -> pd.Series:
    previous_close = df["Close"].shift(1)
    return pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - previous_close).abs(),
            (df["Low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def adx14(df: pd.DataFrame) -> float:
    """Return the latest Wilder-smoothed ADX(14)."""
    if df.empty:
        return float("nan")
    up_move = df["High"].diff()
    down_move = -df["Low"].diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=df.index,
        dtype=float,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=df.index,
        dtype=float,
    )
    alpha = 1.0 / 14.0
    atr = _true_range(df).ewm(alpha=alpha, adjust=False).mean()
    plus_di = 100.0 * plus_dm.ewm(alpha=alpha, adjust=False).mean() / atr
    minus_di = 100.0 * minus_dm.ewm(alpha=alpha, adjust=False).mean() / atr
    denominator = plus_di + minus_di
    dx = (100.0 * (plus_di - minus_di).abs() / denominator).where(
        denominator != 0, 0.0
    )
    return float(dx.fillna(0.0).ewm(alpha=alpha, adjust=False).mean().iloc[-1])


def _atr14(df: pd.DataFrame) -> float:
    if df.empty:
        return float("nan")
    return float(_true_range(df).ewm(alpha=1.0 / 14.0, adjust=False).mean().iloc[-1])


def _period_return(close: pd.Series, period: int) -> float | None:
    clean = close.dropna()
    if len(clean) <= period:
        return None
    value = float(clean.iloc[-1] / clean.iloc[-period - 1] - 1.0)
    return value if np.isfinite(value) else None


def _relative_strength(
    close: pd.Series, spy_close: pd.Series, period: int
) -> float | None:
    own_return = _period_return(close, period)
    spy_return = _period_return(spy_close, period)
    if own_return is None or spy_return is None:
        return None
    return float(own_return - spy_return)


def _volume_band(df: pd.DataFrame, bins: int = 20, window: int = 60) -> list[float | None]:
    recent = df[["Close", "Volume"]].tail(window).dropna()
    if recent.empty:
        return [None, None]
    prices = recent["Close"].to_numpy(dtype=float)
    volumes = recent["Volume"].to_numpy(dtype=float)
    lo, hi = float(np.min(prices)), float(np.max(prices))
    if not np.isfinite(lo) or not np.isfinite(hi):
        return [None, None]
    if lo == hi:
        return [lo, hi]
    totals, edges = np.histogram(prices, bins=bins, range=(lo, hi), weights=volumes)
    best = int(np.argmax(totals))
    return [float(edges[best]), float(edges[best + 1])]


def _finite_or_none(value: Any) -> float | None:
    if value is None:
        return None
    number = float(value)
    return number if np.isfinite(number) else None


def screen_universe(
    store: dict[str, pd.DataFrame],
    spy: pd.DataFrame,
    scan_date: pd.Timestamp | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Apply the hard funnel and attach the display-only trend metrics."""
    funnel = {"universe": 0, "liquid": 0, "po": 0, "dip": 0}
    rows: list[dict[str, Any]] = []
    spy_close = spy["Close"] if not spy.empty else pd.Series(dtype=float)
    if scan_date is None:
        dates = [df.index.max() for df in store.values() if not df.empty]
        scan_date = pd.Timestamp(max(dates)).tz_localize(None).normalize() if dates else None

    for ticker in sorted(store):
        df = store[ticker]
        if len(df) < SWING_MIN_HISTORY or any(
            column not in df.columns for column in OHLCV_COLUMNS
        ):
            continue
        latest_date = pd.Timestamp(df.index.max()).tz_localize(None).normalize()
        if scan_date is not None and latest_date != scan_date:
            continue
        funnel["universe"] += 1

        close = df["Close"]
        dollar_volume = (close * df["Volume"]).tail(60).median()
        price = float(close.iloc[-1])
        if (
            not np.isfinite(dollar_volume)
            or dollar_volume < SWING_MIN_DOLLAR_VOLUME
            or price < SWING_MIN_PRICE
        ):
            continue
        funnel["liquid"] += 1

        po = weekly_po(df)
        if po is None:
            continue
        funnel["po"] += 1

        dip = dip_check(df)
        if dip is None:
            continue
        funnel["dip"] += 1

        high_pivots, low_pivots = _confirmed_pivots(df, k=5, lookback=300)
        atr = _atr14(df)
        rows.append(
            {
                "ticker": str(ticker).upper(),
                "price": price,
                "state": "bounced" if dip["bounced"] else "pulling",
                "touch_days_ago": dip["touch_days_ago"],
                "dow_trend": dow_trend(df),
                "adx": _finite_or_none(adx14(df)),
                "rs63": _relative_strength(close, spy_close, 63),
                "rs126": _relative_strength(close, spy_close, 126),
                "atr_pct": _finite_or_none(atr / price if price else None),
                "dollar_vol": _finite_or_none(dollar_volume),
                "ema20_dist": dip["ema20_dist"],
                "po_weeks": po["po_weeks"],
                "levels": {
                    "ema20": dip["ema20"],
                    "swing_high": high_pivots[-1][1] if high_pivots else None,
                    "swing_low": low_pivots[-1][1] if low_pivots else None,
                    "vol_band": _volume_band(df),
                },
            }
        )
    return rows, funnel
