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


def volume_assessment(
    df: pd.DataFrame,
    *,
    bounced: bool | None = None,
    range_window: int = 60,
    volume_sma_window: int = 50,
    week_sessions: int = 5,
    atr_period: int = 14,
    high_zone_threshold: float = 0.70,
    low_zone_threshold: float = 0.30,
    climax_body_atr_ratio: float = 1.0,
    climax_volume_ratio: float = 2.0,
    accumulation_volume_ratio: float = 1.5,
    distribution_volume_ratio: float = 1.2,
    distribution_max_price_change: float = 0.01,
    selling_pressure_price_change: float = -0.02,
    selling_pressure_volume_ratio: float = 1.2,
    bounce_confirmed_volume_ratio: float = 1.2,
    weak_bounce_volume_ratio: float = 0.8,
    healthy_pullback_max_price_change: float = 0.0,
    contraction_volume_ratio: float = 0.8,
    range_contraction_ratio: float = 1.0,
) -> dict[str, Any] | None:
    """Assess recent daily volume/price behavior without external state."""
    if len(df) < range_window or any(column not in df.columns for column in OHLCV_COLUMNS):
        return None

    volume_sma = df["Volume"].rolling(volume_sma_window, min_periods=volume_sma_window).mean()
    latest_sma = float(volume_sma.iloc[-1])
    if not np.isfinite(latest_sma) or latest_sma <= 0:
        return None

    recent_close = df["Close"].tail(range_window)
    range_low = float(recent_close.min())
    range_high = float(recent_close.max())
    latest_close = float(df["Close"].iloc[-1])
    if not all(np.isfinite(value) for value in (range_low, range_high, latest_close)):
        return None
    zone_pct = (
        float(np.clip((latest_close - range_low) / (range_high - range_low), 0.0, 1.0))
        if range_high > range_low
        else 0.5
    )
    price_zone = (
        "high" if zone_pct >= high_zone_threshold
        else "low" if zone_pct <= low_zone_threshold
        else "mid"
    )

    latest_volume = float(df["Volume"].iloc[-1])
    vol_ratio_today = latest_volume / latest_sma
    recent_volume = float(df["Volume"].iloc[-week_sessions:].mean())
    previous_volume = float(df["Volume"].iloc[-2 * week_sessions:-week_sessions].mean())
    week_vol_ratio = recent_volume / previous_volume if previous_volume > 0 else float("nan")
    previous_week_close = float(df["Close"].iloc[-week_sessions - 1])
    week_price_chg = latest_close / previous_week_close - 1.0 if previous_week_close else float("nan")
    required = (vol_ratio_today, week_vol_ratio, week_price_chg)
    if not all(np.isfinite(value) for value in required):
        return None

    week_frame = df.tail(week_sessions)
    week_sma = volume_sma.tail(week_sessions)
    if week_sma.isna().any() or (week_sma <= 0).any():
        return None
    week_bars = [
        {
            "date": pd.Timestamp(index).date().isoformat(),
            "vol_ratio": float(row["Volume"] / week_sma.loc[index]),
            "up": bool(row["Close"] > row["Open"]),
        }
        for index, row in week_frame.iterrows()
    ]

    latest = df.iloc[-1]
    latest_up = bool(latest["Close"] > latest["Open"])
    latest_down = bool(latest["Close"] < latest["Open"])
    body = abs(float(latest["Close"] - latest["Open"]))
    atr = float(
        _true_range(df).ewm(alpha=1.0 / atr_period, adjust=False).mean().iloc[-1]
    )
    current_ranges = (df["High"] - df["Low"]).iloc[-week_sessions:].mean()
    previous_ranges = (df["High"] - df["Low"]).iloc[-2 * week_sessions:-week_sessions].mean()
    x_today = f"{vol_ratio_today:.1f}"
    x_week = f"{week_vol_ratio:.1f}"
    y_price = f"{week_price_chg * 100:.1f}"

    if (
        price_zone == "low"
        and latest_down
        and np.isfinite(atr)
        and body >= atr * climax_body_atr_ratio
        and vol_ratio_today >= climax_volume_ratio
    ):
        verdict = "selling_climax"
        comment = f"安値圏で出来高{x_today}倍の大陰線。投げ売り一巡ならセリングクライマックス＝反転点になりやすい"
    elif price_zone == "low" and latest_up and vol_ratio_today >= accumulation_volume_ratio:
        verdict = "accumulation"
        comment = f"安値圏での出来高{x_today}倍を伴う反発。買い集めの兆候"
    elif (
        price_zone == "high"
        and week_vol_ratio >= distribution_volume_ratio
        and week_price_chg <= distribution_max_price_change
    ):
        verdict = "distribution"
        comment = f"高値圏で出来高が増えている（前週比{x_week}倍）のに株価が上がらない（{y_price}%）。利確売り優勢＝分配の疑い"
    elif (
        week_price_chg <= selling_pressure_price_change
        and week_vol_ratio >= selling_pressure_volume_ratio
    ):
        verdict = "selling_pressure"
        comment = f"1週間で株価{y_price}%の下落に出来高増（前週比{x_week}倍）が伴う。押し目ではなく下落転換の可能性"
    elif bounced is True and vol_ratio_today >= bounce_confirmed_volume_ratio:
        verdict = "bounce_confirmed"
        comment = f"20EMAからの反発を出来高{x_today}倍が支持。押し目買いが入っている"
    elif bounced is True and vol_ratio_today < weak_bounce_volume_ratio:
        verdict = "weak_bounce"
        comment = f"反発しているが当日出来高は{x_today}倍と薄い。買いの勢いが確認できず、だましの可能性"
    elif (
        week_price_chg < healthy_pullback_max_price_change
        and week_vol_ratio <= contraction_volume_ratio
    ):
        verdict = "healthy_pullback"
        comment = f"株価{y_price}%の押しに対し出来高は前週比{x_week}倍に収縮。売り物が枯れつつある健全な押し目"
    elif (
        week_vol_ratio <= contraction_volume_ratio
        and current_ranges < previous_ranges * range_contraction_ratio
    ):
        verdict = "quiet_setup"
        comment = "出来高・値幅ともに収縮。エネルギー溜め込み中＝動き出しの出来高増を待つ"
    elif bounced is False and vol_ratio_today <= weak_bounce_volume_ratio:
        verdict = "healthy_pullback"
        comment = f"押し目進行中で当日出来高は{x_today}倍に収縮。売り急ぎがなく健全"
    else:
        verdict = "neutral"
        comment = f"特筆すべき出来高シグナルなし（当日{x_today}倍・前週比{x_week}倍）"

    return {
        "price_zone": price_zone,
        "zone_pct": zone_pct,
        "vol_ratio_today": float(vol_ratio_today),
        "week_price_chg": float(week_price_chg),
        "week_vol_ratio": float(week_vol_ratio),
        "week_bars": week_bars,
        "verdict": verdict,
        "comment": comment,
    }


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
                "volume": volume_assessment(df, bounced=dip["bounced"]),
                "levels": {
                    "ema20": dip["ema20"],
                    "swing_high": high_pivots[-1][1] if high_pivots else None,
                    "swing_low": low_pivots[-1][1] if low_pivots else None,
                    "vol_band": _volume_band(df),
                },
            }
        )
    return rows, funnel
