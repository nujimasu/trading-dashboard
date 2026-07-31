from __future__ import annotations

import numpy as np

from backend.services.pattern_detect import (
    detect_all,
    detect_double_bottom,
    detect_flag,
    detect_trendline,
)


def _bars(anchors: list[tuple[int, float]], count: int) -> list[dict]:
    x, y = zip(*anchors)
    close = np.interp(np.arange(count), np.asarray(x), np.asarray(y))
    return [
        {
            "t": 1_700_000_000 + i * 900,
            "o": float(value - 0.1),
            "h": float(value + 0.4),
            "l": float(value - 0.4),
            "c": float(value),
            "v": 10_000.0,
        }
        for i, value in enumerate(close)
    ]


def test_detect_trendline_returns_latest_descending_pivots():
    bars = _bars([(0, 100), (5, 120), (10, 100), (15, 115), (20, 100), (24, 105)], 25)
    lines = detect_trendline(bars, k=2)
    assert len(lines) == 1
    assert lines[0]["type"] == "trendline"
    assert [point["time"] for point in lines[0]["points"]] == [bars[5]["t"], bars[15]["t"]]


def test_detect_all_marks_latest_trendline_break():
    bars = _bars([(0, 100), (5, 120), (10, 100), (15, 115), (20, 100), (24, 120)], 25)
    annotations = detect_all(bars)
    assert annotations["markers"] == [{"time": bars[-1]["t"], "text": "ブレイク"}]


def test_detect_double_bottom_returns_neckline():
    bars = _bars([(0, 110), (5, 100), (10, 112), (15, 100.8), (20, 110), (24, 108)], 25)
    lines = detect_double_bottom(bars, k=2)
    assert len(lines) == 1
    assert lines[0]["type"] == "neckline"
    assert lines[0]["label"] == "ダブルボトム ネックライン"


def test_detect_double_bottom_labels_inverse_head_and_shoulders():
    bars = _bars(
        [(0, 110), (5, 100), (10, 108), (15, 95), (20, 109), (25, 100.5), (30, 110)],
        31,
    )
    lines = detect_double_bottom(bars, k=2)
    assert len(lines) == 1
    assert lines[0]["label"] == "逆三尊 ネックライン"


def test_detect_flag_returns_contracting_triangle_rails():
    bars = _bars(
        [(0, 100), (5, 120), (10, 90), (15, 116), (20, 94), (25, 112), (30, 98), (35, 105)],
        36,
    )
    assert {line["type"] for line in detect_flag(bars, k=2)} == {"tri_upper", "tri_lower"}


def test_detect_flag_returns_parallel_descending_rails():
    bars = _bars(
        [(0, 115), (5, 120), (10, 110), (15, 117), (20, 107), (25, 114), (30, 104), (35, 108)],
        36,
    )
    assert {line["type"] for line in detect_flag(bars, k=2)} == {"flag_upper", "flag_lower"}
