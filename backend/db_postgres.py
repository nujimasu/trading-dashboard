"""PostgreSQL compatibility layer for the dashboard's SQLite-style queries."""

import os
import re
import time
from contextlib import contextmanager
from typing import Optional

import psycopg2


DATABASE_URL = os.environ["DATABASE_URL"]
if "sslmode" not in DATABASE_URL:
    DATABASE_URL += "?sslmode=require" if "?" not in DATABASE_URL else "&sslmode=require"


class CompatRow(dict):
    pass


def _sanitize_params(params):
    if params is None:
        return None
    import numpy as np

    def fix(value):
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            return float(value)
        if isinstance(value, np.bool_):
            return bool(value)
        return value

    if isinstance(params, dict):
        return {key: fix(value) for key, value in params.items()}
    return tuple(fix(value) for value in params)


class CompatCursor:
    def __init__(self, cursor):
        self._cur = cursor

    def _convert(self, sql: str, params=None) -> str:
        if isinstance(params, dict):
            return re.sub(r":(\w+)", r"%(\1)s", sql)
        return sql.replace("?", "%s")

    def execute(self, sql: str, params=None):
        self._cur.execute(self._convert(sql, params), _sanitize_params(params))
        return self

    def executemany(self, sql: str, seq):
        self._cur.executemany(self._convert(sql), [_sanitize_params(item) for item in seq])
        return self

    def _make_row(self, raw_row) -> Optional[CompatRow]:
        if raw_row is None:
            return None
        columns = [desc[0] for desc in self._cur.description]
        return CompatRow(zip(columns, raw_row))

    def fetchone(self) -> Optional[CompatRow]:
        return self._make_row(self._cur.fetchone())

    def fetchall(self) -> list[CompatRow]:
        rows = self._cur.fetchall()
        columns = [desc[0] for desc in self._cur.description] if self._cur.description else []
        return [CompatRow(zip(columns, row)) for row in rows]

    @property
    def lastrowid(self):
        return self._cur.fetchone()[0] if self._cur.description else None

    @property
    def rowcount(self):
        return self._cur.rowcount


class CompatConnection:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self) -> CompatCursor:
        return CompatCursor(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def execute(self, sql: str, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur


def get_connection(retries: int = 3) -> CompatConnection:
    for attempt in range(retries):
        try:
            return CompatConnection(psycopg2.connect(DATABASE_URL, connect_timeout=10))
        except psycopg2.OperationalError:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise


@contextmanager
def db_cursor():
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create the tables used by retained dashboard features."""
    conn = get_connection()
    cur = conn.cursor()
    statements = [
        """
        CREATE TABLE IF NOT EXISTS universe (
            ticker TEXT PRIMARY KEY, name TEXT, sector TEXT, industry TEXT,
            market_cap REAL, exchange TEXT, updated_at TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS price_data (
            ticker TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL,
            volume BIGINT, PRIMARY KEY (ticker, date)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS market_health (
            date TEXT PRIMARY KEY, overall_score REAL, overall_signal TEXT,
            sector_scores TEXT, theme_scores TEXT, total_screened INTEGER,
            stage2_count INTEGER
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS news_events (
            id BIGSERIAL PRIMARY KEY, date TEXT, category TEXT, title TEXT,
            description TEXT, impact TEXT, affected_sectors TEXT,
            affected_tickers TEXT, source TEXT, url TEXT DEFAULT '',
            next_release TEXT DEFAULT ''
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS fundamentals (
            ticker TEXT PRIMARY KEY, sector TEXT, industry TEXT, market_cap REAL,
            pe_ratio REAL, eps_growth_yoy REAL, eps_growth_q REAL,
            revenue_growth_yoy REAL, earnings_surprise_pct REAL, roe REAL,
            operating_margin REAL, profit_margin REAL, inst_own_pct REAL,
            debt_to_equity REAL, description TEXT, updated_at TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS api_usage (
            date TEXT PRIMARY KEY, fmp_calls INTEGER DEFAULT 0
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS pipeline_log (
            id BIGSERIAL PRIMARY KEY, run_at TEXT, stage TEXT, status TEXT,
            message TEXT, duration_s REAL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS swing_picks (
            id SERIAL PRIMARY KEY, scan_date DATE NOT NULL, ticker TEXT NOT NULL,
            price REAL, state TEXT, touch_days_ago INTEGER, dow_trend TEXT,
            adx REAL, rs63 REAL, rs126 REAL, atr_pct REAL, dollar_vol REAL,
            ema20_dist REAL, po_weeks INTEGER, levels TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(), UNIQUE(scan_date, ticker)
        )
        """,
    ]
    for statement in statements:
        cur.execute(statement)
    conn.commit()
    conn.close()
    print("[DB] PostgreSQL tables initialized (Supabase)")


def get_fmp_call_count(date_str: str) -> int:
    with db_cursor() as cur:
        cur.execute("SELECT fmp_calls FROM api_usage WHERE date = ?", (date_str,))
        row = cur.fetchone()
        return row["fmp_calls"] if row else 0


def increment_fmp_call_count(date_str: str, n: int = 1):
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO api_usage (date, fmp_calls) VALUES (?, ?)
            ON CONFLICT (date) DO UPDATE SET fmp_calls = api_usage.fmp_calls + ?
        """, (date_str, n, n))
