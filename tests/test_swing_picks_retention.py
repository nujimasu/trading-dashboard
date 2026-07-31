from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

import pipeline.swing_scan as swing_scan
from pipeline.swing_scan import _prune_old_picks


def _database_with_scan_dates(count: int) -> tuple[sqlite3.Connection, sqlite3.Cursor, list[str]]:
    connection = sqlite3.connect(":memory:")
    cursor = connection.cursor()
    cursor.execute(
        "CREATE TABLE swing_picks (scan_date TEXT NOT NULL, ticker TEXT NOT NULL)"
    )
    dates = [(date(2026, 1, 1) + timedelta(days=index)).isoformat() for index in range(count)]
    cursor.executemany(
        "INSERT INTO swing_picks (scan_date, ticker) VALUES (?, ?)",
        [(scan_date, f"T{index:02d}") for index, scan_date in enumerate(dates)],
    )
    return connection, cursor, dates


def test_prune_keeps_newest_sixty_distinct_scan_dates():
    connection, cursor, dates = _database_with_scan_dates(65)

    pruned = _prune_old_picks(cursor, 60)
    remaining = [
        row[0]
        for row in cursor.execute(
            "SELECT DISTINCT scan_date FROM swing_picks ORDER BY scan_date"
        ).fetchall()
    ]

    assert pruned == 5
    assert remaining == dates[-60:]
    connection.close()


def test_prune_does_nothing_with_sixty_or_fewer_scan_dates():
    connection, cursor, dates = _database_with_scan_dates(60)

    pruned = _prune_old_picks(cursor, 60)
    remaining = cursor.execute("SELECT COUNT(*) FROM swing_picks").fetchone()[0]

    assert pruned == 0
    assert remaining == len(dates)
    connection.close()


def test_save_failure_prevents_pruning(monkeypatch):
    prune_called = False

    def fail_save(*_args, **_kwargs):
        raise RuntimeError("save failed")

    def record_prune(*_args, **_kwargs):
        nonlocal prune_called
        prune_called = True
        return 0

    monkeypatch.setattr(swing_scan, "_replace_picks", fail_save)
    monkeypatch.setattr(swing_scan, "_prune_old_picks", record_prune)

    with pytest.raises(RuntimeError, match="save failed"):
        swing_scan._save_and_prune_picks(object(), "2026-04-01", [], 60)

    assert prune_called is False
