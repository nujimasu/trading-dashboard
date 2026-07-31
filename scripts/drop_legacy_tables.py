"""Inspect and optionally remove legacy dashboard tables.

Without ``--execute`` this script only prints row counts.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.db import get_connection


TABLES = [
    "logic2_picks",
    "logic4_picks",
    "logic5_picks",
    "daily_picks",
    "weekly_picks",
    "tech_daily_picks",
    "tech_weekly_picks",
    "technical_screen",
    "detailed_analysis",
    "signal_log_intraday",
    "signal_log",
    "journal_entries",
    "positions",
    "custom_insights",
]


def row_count(table: str) -> int | None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) AS count FROM {table}")
        row = cur.fetchone()
        return int(row["count"])
    except Exception:
        conn.rollback()
        return None
    finally:
        conn.close()


def drop_tables() -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        for table in TABLES:
            cur.execute(f"DROP TABLE IF EXISTS {table}")
            print(f"DROP: {table}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Drop legacy trading-dashboard tables")
    parser.add_argument("--execute", action="store_true", help="actually drop the tables")
    args = parser.parse_args()

    print("Legacy table row counts:")
    for table in TABLES:
        count = row_count(table)
        print(f"  {table}: {count if count is not None else 'not found'}")

    if not args.execute:
        print("DRY RUN: no tables were dropped. Re-run with --execute to drop them.")
        return

    drop_tables()
    print("Legacy tables dropped.")


if __name__ == "__main__":
    main()
