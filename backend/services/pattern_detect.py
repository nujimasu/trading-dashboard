"""Deterministic pattern annotations for 15-minute OHLCV bars."""
from __future__ import annotations

from typing import Any

import numpy as np


DEFAULT_PIVOT_K = 3


def _pivots(
    bars: list[dict[str, Any]], k: int
) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    highs = np.asarray([bar["h"] for bar in bars], dtype=float)
    lows = np.asarray([bar["l"] for bar in bars], dtype=float)
    high_pivots: list[tuple[int, float]] = []
    low_pivots: list[tuple[int, float]] = []
    if k < 1 or len(bars) < 2 * k + 1:
        return high_pivots, low_pivots
    for i in range(k, len(bars) - k):
        if highs[i] == np.max(highs[i - k : i + k + 1]):
            high_pivots.append((i, float(highs[i])))
        if lows[i] == np.min(lows[i - k : i + k + 1]):
            low_pivots.append((i, float(lows[i])))
    return high_pivots, low_pivots


def _point(bars: list[dict[str, Any]], index: int, price: float) -> dict[str, Any]:
    return {"time": int(bars[index]["t"]), "price": float(price)}


def _latest_descending_high_pair(
    bars: list[dict[str, Any]], k: int
) -> tuple[tuple[int, float], tuple[int, float]] | None:
    highs, _ = _pivots(bars, k)
    for old, new in zip(highs[-2::-1], highs[:0:-1]):
        if new[1] < old[1]:
            return old, new
    return None


def detect_trendline(
    bars: list[dict[str, Any]], k: int = DEFAULT_PIVOT_K
) -> list[dict[str, Any]]:
    """Return the latest descending line joining two confirmed pivot highs."""
    pair = _latest_descending_high_pair(bars, k)
    if pair is None:
        return []
    old, new = pair
    return [
        {
            "type": "trendline",
            "label": "下降トレンドライン",
            "points": [_point(bars, *old), _point(bars, *new)],
        }
    ]


def _trendline_break_marker(
    bars: list[dict[str, Any]], k: int
) -> dict[str, Any] | None:
    pair = _latest_descending_high_pair(bars, k)
    if pair is None or not bars:
        return None
    old, new = pair
    slope = (new[1] - old[1]) / (new[0] - old[0])
    projected = new[1] + slope * (len(bars) - 1 - new[0])
    if float(bars[-1]["c"]) <= projected:
        return None
    return {"time": int(bars[-1]["t"]), "text": "ブレイク"}


def detect_double_bottom(
    bars: list[dict[str, Any]], k: int = DEFAULT_PIVOT_K, tol: float = 0.015
) -> list[dict[str, Any]]:
    """Return the latest confirmed double-bottom or inverse-H&S neckline."""
    highs, lows = _pivots(bars, k)
    if len(lows) < 2:
        return []

    for start in range(len(lows) - 3, -1, -1):
        left, head, right = lows[start : start + 3]
        shoulder_scale = max(abs(left[1]), abs(right[1]), np.finfo(float).eps)
        left_necks = [pivot for pivot in highs if left[0] < pivot[0] < head[0]]
        right_necks = [pivot for pivot in highs if head[0] < pivot[0] < right[0]]
        if (
            head[1] < left[1]
            and head[1] < right[1]
            and abs(left[1] - right[1]) / shoulder_scale <= tol
            and left_necks
            and right_necks
        ):
            neck_price = (
                max(left_necks, key=lambda pivot: pivot[1])[1]
                + max(right_necks, key=lambda pivot: pivot[1])[1]
            ) / 2.0
            return [
                {
                    "type": "neckline",
                    "label": "逆三尊 ネックライン",
                    "points": [
                        _point(bars, left[0], neck_price),
                        _point(bars, right[0], neck_price),
                    ],
                }
            ]

    for pair_index in range(len(lows) - 2, -1, -1):
        first, second = lows[pair_index], lows[pair_index + 1]
        scale = max(abs(first[1]), abs(second[1]), np.finfo(float).eps)
        if abs(first[1] - second[1]) / scale > tol:
            continue
        between_highs = [pivot for pivot in highs if first[0] < pivot[0] < second[0]]
        if not between_highs:
            continue
        neck = max(between_highs, key=lambda pivot: pivot[1])
        return [
            {
                "type": "neckline",
                "label": "ダブルボトム ネックライン",
                "points": [
                    _point(bars, first[0], neck[1]),
                    _point(bars, second[0], neck[1]),
                ],
            }
        ]
    return []


def _fit_line(
    pivots: list[tuple[int, float]], bars: list[dict[str, Any]]
) -> tuple[float, float, list[dict[str, Any]], float]:
    x = np.asarray([pivot[0] for pivot in pivots], dtype=float)
    y = np.asarray([pivot[1] for pivot in pivots], dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    points = [
        _point(bars, int(x[0]), float(slope * x[0] + intercept)),
        _point(bars, int(x[-1]), float(slope * x[-1] + intercept)),
    ]
    normalized_slope = float(slope / max(abs(float(np.mean(y))), np.finfo(float).eps))
    return float(slope), float(intercept), points, normalized_slope


def detect_flag(
    bars: list[dict[str, Any]],
    k: int = DEFAULT_PIVOT_K,
    pivot_count: int = 3,
    near_horizontal: float = 0.0005,
    parallel_tolerance: float = 0.0015,
    max_abs_slope: float = 0.02,
) -> list[dict[str, Any]]:
    """Fit recent pivot rails and classify a bull flag or contracting triangle."""
    highs, lows = _pivots(bars, k)
    if len(highs) < pivot_count or len(lows) < pivot_count:
        return []
    recent_highs = highs[-pivot_count:]
    recent_lows = lows[-pivot_count:]
    _, _, upper_points, upper_norm = _fit_line(recent_highs, bars)
    _, _, lower_points, lower_norm = _fit_line(recent_lows, bars)

    if upper_norm < 0 and lower_norm > 0:
        return [
            {"type": "tri_upper", "label": "三角収束 上辺", "points": upper_points},
            {"type": "tri_lower", "label": "三角収束 下辺", "points": lower_points},
        ]

    flag_slopes = (
        -max_abs_slope <= upper_norm <= near_horizontal
        and -max_abs_slope <= lower_norm <= near_horizontal
        and abs(upper_norm - lower_norm) <= parallel_tolerance
    )
    if flag_slopes:
        return [
            {"type": "flag_upper", "label": "上昇フラッグ 上辺", "points": upper_points},
            {"type": "flag_lower", "label": "上昇フラッグ 下辺", "points": lower_points},
        ]
    return []


def detect_all(bars: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Combine every detector into the public annotations schema."""
    lines = detect_trendline(bars) + detect_double_bottom(bars) + detect_flag(bars)
    marker = _trendline_break_marker(bars, k=DEFAULT_PIVOT_K)
    return {"lines": lines, "markers": [marker] if marker else []}
