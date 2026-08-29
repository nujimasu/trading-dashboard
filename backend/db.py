"""Database connection and schema management."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(Path(__file__).parent.parent / ".env")

if os.getenv("DATABASE_URL"):
    from backend.db_postgres import (
        db_cursor,
        get_connection,
        get_fmp_call_count,
        increment_fmp_call_count,
        init_db,
    )
else:
    import sqlite3
    from contextlib import contextmanager

    from config import DB_PATH

    def get_connection() -> sqlite3.Connection:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

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
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS universe (
            ticker TEXT PRIMARY KEY, name TEXT, sector TEXT, industry TEXT,
            market_cap REAL, exchange TEXT, updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS price_data (
            ticker TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL,
            volume INTEGER, PRIMARY KEY (ticker, date)
        );
        CREATE TABLE IF NOT EXISTS market_health (
            date TEXT PRIMARY KEY, overall_score REAL, overall_signal TEXT,
            sector_scores TEXT, theme_scores TEXT, total_screened INTEGER,
            stage2_count INTEGER
        );
        CREATE TABLE IF NOT EXISTS news_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, category TEXT,
            title TEXT, description TEXT, impact TEXT, affected_sectors TEXT,
            affected_tickers TEXT, source TEXT, url TEXT DEFAULT '',
            next_release TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS fundamentals (
            ticker TEXT PRIMARY KEY, sector TEXT, industry TEXT, market_cap REAL,
            pe_ratio REAL, eps_growth_yoy REAL, eps_growth_q REAL,
            revenue_growth_yoy REAL, earnings_surprise_pct REAL, roe REAL,
            operating_margin REAL, profit_margin REAL, inst_own_pct REAL,
            debt_to_equity REAL, description TEXT, updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS api_usage (
            date TEXT PRIMARY KEY, fmp_calls INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS pipeline_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, run_at TEXT, stage TEXT,
            status TEXT, message TEXT, duration_s REAL
        );
        CREATE TABLE IF NOT EXISTS swing_picks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, scan_date TEXT NOT NULL,
            ticker TEXT NOT NULL, price REAL, state TEXT, touch_days_ago INTEGER,
            dow_trend TEXT, adx REAL, rs63 REAL, rs126 REAL, atr_pct REAL,
            dollar_vol REAL, ema20_dist REAL, po_weeks INTEGER, levels TEXT,
            volume TEXT,
            created_at TEXT DEFAULT (datetime('now')), UNIQUE(scan_date, ticker)
        );
        CREATE TABLE IF NOT EXISTS ai_news (
            id INTEGER PRIMARY KEY AUTOINCREMENT, news_date TEXT NOT NULL,
            category TEXT NOT NULL, ticker TEXT NOT NULL DEFAULT '',
            headline TEXT NOT NULL, summary_ja TEXT NOT NULL,
            sentiment TEXT DEFAULT 'neutral', affected_tickers TEXT DEFAULT '[]',
            source_url TEXT DEFAULT '', created_at TEXT DEFAULT (datetime('now')),
            UNIQUE (news_date, category, ticker)
        );
        CREATE TABLE IF NOT EXISTS earnings_dates (
            ticker TEXT PRIMARY KEY, earnings_date TEXT NOT NULL,
            timing TEXT DEFAULT '', updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS ai_profiles (
            ticker TEXT PRIMARY KEY, market TEXT NOT NULL DEFAULT 'us',
            category TEXT NOT NULL DEFAULT '', company_name TEXT DEFAULT '',
            business TEXT DEFAULT '', revenue TEXT DEFAULT '',
            strengths TEXT DEFAULT '', sensitivities TEXT DEFAULT '',
            related_tickers TEXT DEFAULT '[]', source_url TEXT DEFAULT '',
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_ai_news_date ON ai_news (news_date DESC);
        """)
        swing_columns = {
            row[1] for row in cur.execute("PRAGMA table_info(swing_picks)").fetchall()
        }
        if "volume" not in swing_columns:
            cur.execute("ALTER TABLE swing_picks ADD COLUMN volume TEXT")
        ai_news_columns = {
            row[1] for row in cur.execute("PRAGMA table_info(ai_news)").fetchall()
        }
        if "affected_tickers" not in ai_news_columns:
            cur.execute("ALTER TABLE ai_news ADD COLUMN affected_tickers TEXT DEFAULT '[]'")
        conn.commit()
        conn.close()
        print(f"[DB] SQLite initialized: {DB_PATH}")

    def get_fmp_call_count(date_str: str) -> int:
        with db_cursor() as cur:
            cur.execute("SELECT fmp_calls FROM api_usage WHERE date = ?", (date_str,))
            row = cur.fetchone()
            return row["fmp_calls"] if row else 0

    def increment_fmp_call_count(date_str: str, n: int = 1):
        with db_cursor() as cur:
            cur.execute("""
                INSERT INTO api_usage (date, fmp_calls) VALUES (?, ?)
                ON CONFLICT(date) DO UPDATE SET fmp_calls = fmp_calls + ?
            """, (date_str, n, n))


if __name__ == "__main__":
    init_db()
