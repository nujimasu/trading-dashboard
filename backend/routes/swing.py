"""Swing screener picks and on-demand Polygon 15-minute bars."""
from __future__ import annotations

import json
import re
import ssl
import time as time_module
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import certifi
from fastapi import APIRouter, HTTPException, Query

import config
from backend.db import db_cursor
from backend.services import pattern_detect


router = APIRouter()
_NEW_YORK = ZoneInfo("America/New_York")
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
_TICKER_PATTERN = re.compile(r"^[A-Z0-9.\-]{1,15}$")
_intraday_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _as_iso_date(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _parse_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


@router.get("/api/swing/picks")
def swing_picks() -> dict[str, Any]:
    """Return every pick from the latest scan; UI filters remain client-side."""
    columns = (
        "ticker, price, state, touch_days_ago, dow_trend, adx, rs63, rs126, "
        "atr_pct, dollar_vol, ema20_dist, po_weeks, levels, volume"
    )
    with db_cursor() as cursor:
        cursor.execute("SELECT MAX(scan_date) AS scan_date FROM swing_picks")
        latest = cursor.fetchone()
        scan_date_value = latest["scan_date"] if latest else None
        rows: list[dict[str, Any]] = []
        if scan_date_value is not None:
            cursor.execute(
                f"SELECT {columns} FROM swing_picks "
                "WHERE scan_date = ? ORDER BY ticker ASC",
                (scan_date_value,),
            )
            rows = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            """
            SELECT message FROM pipeline_log
            WHERE stage = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            ("SwingScan",),
        )
        log_row = cursor.fetchone()

    for row in rows:
        row["levels"] = _parse_json_object(row.get("levels"))
        row["volume"] = _parse_json_object(row.get("volume"))
    funnel = _parse_json_object(log_row["message"] if log_row else None)
    return {
        "scan_date": _as_iso_date(scan_date_value),
        "funnel": funnel,
        "picks": rows,
    }


def _fetch_polygon_intraday(ticker: str) -> list[dict[str, Any]]:
    now_ny = datetime.now(_NEW_YORK)
    from_date = (now_ny.date() - timedelta(days=config.SWING_INTRADAY_LOOKBACK_DAYS)).isoformat()
    to_date = now_ny.date().isoformat()
    query = urllib.parse.urlencode(
        {
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,
            "apiKey": config.POLYGON_API_KEY,
        }
    )
    safe_ticker = urllib.parse.quote(ticker, safe=".-")
    url = (
        f"{config.POLYGON_BASE_URL}/v2/aggs/ticker/{safe_ticker}/range/15/minute/"
        f"{from_date}/{to_date}?{query}"
    )
    try:
        with urllib.request.urlopen(url, timeout=40, context=_SSL_CONTEXT) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Polygon HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("Polygon intraday request failed") from exc

    if payload.get("status") not in {"OK", "DELAYED"}:
        message = payload.get("error") or payload.get("message") or "Polygon response error"
        raise RuntimeError(str(message))
    return payload.get("results") or []


def _unix_seconds(value: Any) -> int:
    timestamp = int(value)
    return timestamp // 1000 if timestamp > 10_000_000_000 else timestamp


def _format_intraday_bars(
    results: list[dict[str, Any]], extended: bool
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    converted: list[tuple[Any, dict[str, Any], dict[str, Any]]] = []
    session_start = time(9, 30)
    session_end = time(15, 59, 59)
    for result in sorted(results, key=lambda item: item.get("t", 0)):
        if any(result.get(key) is None for key in ("t", "o", "h", "l", "c")):
            continue
        seconds = _unix_seconds(result["t"])
        local = datetime.fromtimestamp(seconds, tz=timezone.utc).astimezone(_NEW_YORK)
        if not extended and not (session_start <= local.time() <= session_end):
            continue
        chart_seconds = seconds + int(local.utcoffset().total_seconds())
        public_bar = {
            "time": chart_seconds,
            "open": float(result["o"]),
            "high": float(result["h"]),
            "low": float(result["l"]),
            "close": float(result["c"]),
            "volume": float(result.get("v") or 0),
        }
        detector_bar = {
            "t": chart_seconds,
            "o": public_bar["open"],
            "h": public_bar["high"],
            "l": public_bar["low"],
            "c": public_bar["close"],
            "v": public_bar["volume"],
        }
        converted.append((local.date(), public_bar, detector_bar))

    latest_dates = sorted({item[0] for item in converted})[-config.SWING_INTRADAY_SESSION_DAYS :]
    selected = [item for item in converted if item[0] in latest_dates]
    return [item[1] for item in selected], [item[2] for item in selected]


def _latest_levels(ticker: str) -> dict[str, Any]:
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT levels FROM swing_picks
            WHERE ticker = ?
            ORDER BY scan_date DESC, id DESC
            LIMIT 1
            """,
            (ticker,),
        )
        row = cursor.fetchone()
    return _parse_json_object(row["levels"] if row else None)


def _append_daily_levels(
    annotations: dict[str, list[dict[str, Any]]],
    levels: dict[str, Any],
    latest_time: int,
) -> None:
    volume_band = levels.get("vol_band")
    level_specs = [
        ("日足EMA20", levels.get("ema20")),
        ("直近スイング高値", levels.get("swing_high")),
        ("直近スイング安値", levels.get("swing_low")),
        (
            "出来高集中帯上端",
            volume_band[1] if isinstance(volume_band, list) and len(volume_band) == 2 else None,
        ),
        (
            "出来高集中帯下端",
            volume_band[0] if isinstance(volume_band, list) and len(volume_band) == 2 else None,
        ),
    ]
    for label, price in level_specs:
        if price is None:
            continue
        try:
            numeric_price = float(price)
        except (TypeError, ValueError):
            continue
        annotations["lines"].append(
            {
                "type": "level",
                "label": label,
                "points": [{"time": latest_time, "price": numeric_price}],
            }
        )


@router.get("/api/swing/intraday/{ticker}")
def swing_intraday(
    ticker: str, extended: bool = Query(False)
) -> dict[str, Any]:
    """Fetch, cache, annotate, and return the latest five intraday sessions."""
    normalized = ticker.strip().upper()
    if not _TICKER_PATTERN.fullmatch(normalized):
        raise HTTPException(status_code=400, detail="invalid ticker")
    if not config.POLYGON_API_KEY:
        raise HTTPException(status_code=503, detail="POLYGON_API_KEY is not configured")

    cache_key = f"{normalized}:{int(extended)}"
    cached = _intraday_cache.get(cache_key)
    now = time_module.monotonic()
    if cached and now - cached[0] < config.SWING_INTRADAY_CACHE_TTL:
        return cached[1]

    try:
        results = _fetch_polygon_intraday(normalized)
        bars, detector_bars = _format_intraday_bars(results, extended=extended)
        annotations = pattern_detect.detect_all(detector_bars)
        if bars:
            latest_time = bars[-1]["time"]
        else:
            current_seconds = int(time_module.time())
            current_local = datetime.fromtimestamp(
                current_seconds, tz=timezone.utc
            ).astimezone(_NEW_YORK)
            latest_time = current_seconds + int(
                current_local.utcoffset().total_seconds()
            )
        _append_daily_levels(annotations, _latest_levels(normalized), latest_time)
    except (RuntimeError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    response = {
        "ticker": normalized,
        "bars": bars,
        "annotations": annotations,
    }
    expired_keys = [
        key
        for key, (cached_at, _) in _intraday_cache.items()
        if now - cached_at >= config.SWING_INTRADAY_CACHE_TTL
    ]
    for key in expired_keys:
        del _intraday_cache[key]
    _intraday_cache[cache_key] = (now, response)
    return response
