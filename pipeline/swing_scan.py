"""Daily batch for the weekly perfect-order / daily pullback screener."""
from __future__ import annotations

import argparse
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, time as datetime_time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import certifi
import pandas as pd
from pandas.tseries.offsets import BDay

from backend.db import db_cursor, init_db
from backend.services.swing_screener import screen_universe
import config


_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
_NEW_YORK = ZoneInfo("America/New_York")


def _save_store(store: dict[str, pd.DataFrame]) -> None:
    config.SWING_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = config.SWING_STORE_PATH.with_suffix(".tmp")
    pd.to_pickle(store, temporary)
    temporary.replace(config.SWING_STORE_PATH)


def _build_store() -> dict[str, pd.DataFrame]:
    shard_paths = sorted(config.SWING_UNIVERSE_DIR.glob("shard_*.pkl"))
    if not shard_paths:
        raise FileNotFoundError(
            f"swing universe shards not found: {config.SWING_UNIVERSE_DIR}"
        )

    store: dict[str, pd.DataFrame] = {}
    for shard_path in shard_paths:
        shard = pd.read_pickle(shard_path)
        if not isinstance(shard, dict):
            raise TypeError(f"invalid shard payload: {shard_path.name}")
        for ticker, frame in shard.items():
            if not isinstance(frame, pd.DataFrame) or frame.empty:
                continue
            ordered = frame.sort_index()
            cutoff = ordered.index.max() - pd.DateOffset(years=config.SWING_STORE_YEARS)
            store[str(ticker).upper()] = ordered.loc[ordered.index >= cutoff].copy()
        print(f"[SwingScan] store build: {shard_path.name} ({len(store)} tickers)")

    _save_store(store)
    print(f"[SwingScan] store saved: {config.SWING_STORE_PATH} ({len(store)} tickers)")
    return store


def load_store() -> dict[str, pd.DataFrame]:
    """Load the compact store, building it from read-only shards when absent."""
    if not config.SWING_STORE_PATH.exists():
        return _build_store()
    store = pd.read_pickle(config.SWING_STORE_PATH)
    if not isinstance(store, dict):
        raise TypeError(f"invalid swing store payload: {config.SWING_STORE_PATH}")
    print(f"[SwingScan] store loaded: {len(store)} tickers")
    return store


def _store_max_date(store: dict[str, pd.DataFrame]) -> pd.Timestamp:
    dates = [frame.index.max() for frame in store.values() if not frame.empty]
    if not dates:
        raise ValueError("swing store is empty")
    return pd.Timestamp(max(dates)).tz_localize(None).normalize()


def _fetch_grouped_day(day: str, retries: int = 3) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {"adjusted": "true", "apiKey": config.POLYGON_API_KEY}
    )
    url = (
        f"{config.POLYGON_BASE_URL}/v2/aggs/grouped/locale/us/market/stocks/{day}"
        f"?{query}"
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(
                url, timeout=40, context=_SSL_CONTEXT
            ) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < retries - 1:
                print(f"[SwingScan] Polygon {day}: HTTP 429, retrying")
                time.sleep(config.SWING_POLYGON_RATE_SLEEP * 1.5)
                continue
            raise RuntimeError(f"Polygon HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt < retries - 1:
                time.sleep(2)
                continue
            raise RuntimeError("Polygon grouped daily request failed") from exc

        status = payload.get("status")
        if status not in {"OK", "DELAYED"}:
            message = payload.get("error") or payload.get("message") or "no message"
            raise RuntimeError(f"Polygon status={status!r}: {message}")
        return payload.get("results") or []
    raise RuntimeError("Polygon grouped daily retries exhausted")


def _append_grouped_results(
    store: dict[str, pd.DataFrame], results: list[dict[str, Any]], day: str
) -> int:
    appended = 0
    timestamp = pd.Timestamp(day)
    for result in results:
        ticker = str(result.get("T") or "").strip().upper()
        if ticker not in store or result.get("c") is None:
            continue
        row = pd.DataFrame(
            {
                "Open": [result.get("o")],
                "High": [result.get("h")],
                "Low": [result.get("l")],
                "Close": [result.get("c")],
                "Volume": [result.get("v", 0)],
            },
            index=pd.DatetimeIndex([timestamp]),
        )
        combined = pd.concat([store[ticker], row])
        store[ticker] = combined[~combined.index.duplicated(keep="last")].sort_index()
        appended += 1
    return appended


def _pending_update_days(
    latest: pd.Timestamp, now_ny: datetime | None = None
) -> pd.DatetimeIndex:
    now_ny = now_ny or datetime.now(_NEW_YORK)
    if now_ny.tzinfo is None:
        now_ny = now_ny.replace(tzinfo=_NEW_YORK)
    else:
        now_ny = now_ny.astimezone(_NEW_YORK)
    end = pd.Timestamp(now_ny.date())
    if now_ny.time() <= datetime_time(16, 15):
        end -= BDay(1)
    return pd.bdate_range(latest, end)


def update_store(
    store: dict[str, pd.DataFrame], now_ny: datetime | None = None
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """Advance existing symbols with one Polygon grouped-daily call per weekday."""
    if not config.POLYGON_API_KEY:
        print("[SwingScan] WARNING: POLYGON_API_KEY 未設定のため日足更新をスキップ")
        return store, []

    latest = _store_max_date(store)
    pending = _pending_update_days(latest, now_ny=now_ny)
    failed_days: list[str] = []
    for index, timestamp in enumerate(pending):
        day = timestamp.date().isoformat()
        try:
            results = _fetch_grouped_day(day)
            count = _append_grouped_results(store, results, day)
            print(f"[SwingScan] Polygon {day}: {count} tickers appended")
        except RuntimeError as exc:
            print(f"[SwingScan] WARNING: {day} update skipped ({exc})")
            failed_days.append(day)
        if index < len(pending) - 1:
            time.sleep(config.SWING_POLYGON_RATE_SLEEP)

    _save_store(store)
    return store, failed_days


def _database_rows(
    scan_date: str,
    rows: list[dict[str, Any]],
    *,
    include_volume: bool = True,
) -> list[tuple[Any, ...]]:
    return [
        (
            scan_date,
            row["ticker"],
            row["price"],
            row["state"],
            row["touch_days_ago"],
            row["dow_trend"],
            row["adx"],
            row["rs63"],
            row["rs126"],
            row["atr_pct"],
            row["dollar_vol"],
            row["ema20_dist"],
            row["po_weeks"],
            json.dumps(row["levels"], ensure_ascii=False, allow_nan=False),
            *(
                (json.dumps(row["volume"], ensure_ascii=False, allow_nan=False),)
                if include_volume
                else ()
            ),
        )
        for row in rows
    ]


def _replace_picks(cursor: Any, scan_date: str, rows: list[dict[str, Any]]) -> None:
    """Atomically replace one scan date's picks using the caller's transaction."""
    cursor.execute("DELETE FROM swing_picks WHERE scan_date = ?", (scan_date,))
    include_volume = all("volume" in row for row in rows)
    values = _database_rows(scan_date, rows, include_volume=include_volume)
    if values:
        if include_volume:
            cursor.executemany(
                """
            INSERT INTO swing_picks (
                scan_date, ticker, price, state, touch_days_ago, dow_trend,
                adx, rs63, rs126, atr_pct, dollar_vol, ema20_dist, po_weeks,
                levels, volume
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
        else:
            cursor.executemany(
                """
                INSERT INTO swing_picks (
                    scan_date, ticker, price, state, touch_days_ago, dow_trend,
                    adx, rs63, rs126, atr_pct, dollar_vol, ema20_dist, po_weeks,
                    levels
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )


def run() -> None:
    """Update data, screen the universe, and persist picks plus funnel metrics."""
    started = time.perf_counter()
    store, failed_days = update_store(load_store())
    spy = store.get("SPY")
    if spy is None or spy.empty:
        raise RuntimeError("SPY is missing from the swing store")
    scan_timestamp = _store_max_date(store)
    rows, funnel = screen_universe(store, spy, scan_date=scan_timestamp)
    scan_date = scan_timestamp.date().isoformat()
    init_db()

    with db_cursor() as cursor:
        _replace_picks(cursor, scan_date, rows)

    duration = time.perf_counter() - started
    message = dict(funnel)
    if failed_days:
        message["failed_days"] = failed_days
    funnel_json = json.dumps(message, ensure_ascii=False)
    status = "WARN" if failed_days else "OK"
    with db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO pipeline_log (run_at, stage, status, message, duration_s)
            VALUES (?, ?, ?, ?, ?)
            """,
            (datetime.now().isoformat(), "SwingScan", status, funnel_json, duration),
        )
    print(
        f"[SwingScan] {scan_date}: {len(rows)} picks, funnel={funnel_json} "
        f"({duration:.1f}s)"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the daily swing pullback scan")
    parser.add_argument(
        "--rebuild-store",
        action="store_true",
        help="rebuild data/swing_store.pkl from data/universe15y shards",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = _parse_args()
    if arguments.rebuild_store:
        _build_store()
    run()
