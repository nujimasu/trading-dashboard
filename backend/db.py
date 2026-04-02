"""
Database connection and schema management.
環境変数 DATABASE_URL が設定されている場合は PostgreSQL (Supabase) を使用。
未設定の場合はローカル SQLite にフォールバック。
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── PostgreSQL / SQLite 切り替え ─────────────────────────────────────────────
if os.getenv("DATABASE_URL"):
    from backend.db_postgres import (
        get_connection, db_cursor, init_db,
        get_fmp_call_count, increment_fmp_call_count,
    )
else:
    # ── ローカル SQLite 実装 ──────────────────────────────────────────────────
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
        """Create all tables if they don't exist."""
        conn = get_connection()
        cur = conn.cursor()

        cur.executescript("""
        CREATE TABLE IF NOT EXISTS universe (
            ticker      TEXT PRIMARY KEY,
            name        TEXT,
            sector      TEXT,
            industry    TEXT,
            market_cap  REAL,
            exchange    TEXT,
            updated_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS price_data (
            ticker  TEXT,
            date    TEXT,
            open    REAL,
            high    REAL,
            low     REAL,
            close   REAL,
            volume  INTEGER,
            PRIMARY KEY (ticker, date)
        );
        CREATE TABLE IF NOT EXISTS technical_screen (
            ticker          TEXT PRIMARY KEY,
            scan_date       TEXT,
            price           REAL,
            sma20           REAL,
            sma50           REAL,
            sma200          REAL,
            ema10           REAL,
            ema21           REAL,
            rsi             REAL,
            macd            REAL,
            macd_signal     REAL,
            volume_ratio    REAL,
            high_52w        REAL,
            low_52w         REAL,
            pct_from_high   REAL,
            atr             REAL,
            stage2_uptrend  INTEGER,
            vcp_tightening  INTEGER,
            passed_filter   INTEGER
        );
        CREATE TABLE IF NOT EXISTS detailed_analysis (
            ticker              TEXT PRIMARY KEY,
            scan_date           TEXT,
            vcp_score           REAL,
            contraction_count   INTEGER,
            pivot_price         REAL,
            stop_price          REAL,
            tp1_price           REAL,
            target_price        REAL,
            risk_reward         REAL,
            tier                TEXT,
            technical_score     REAL,
            holding_days_est    INTEGER DEFAULT 20,
            entry_reasons       TEXT,
            risk_factors        TEXT,
            direction           TEXT DEFAULT 'LONG'
        );
        CREATE TABLE IF NOT EXISTS fundamentals (
            ticker                  TEXT PRIMARY KEY,
            sector                  TEXT,
            industry                TEXT,
            market_cap              REAL,
            pe_ratio                REAL,
            eps_growth_yoy          REAL,
            revenue_growth_yoy      REAL,
            earnings_surprise_pct   REAL,
            roe                     REAL,
            description             TEXT,
            updated_at              TEXT
        );
        CREATE TABLE IF NOT EXISTS weekly_picks (
            ticker                  TEXT PRIMARY KEY,
            week_of                 TEXT,
            composite_score         REAL,
            tier                    TEXT,
            sector                  TEXT,
            themes                  TEXT,
            entry_price             REAL,
            stop_price              REAL,
            tp1_price               REAL,
            target_price            REAL,
            risk_reward             REAL,
            technical_summary       TEXT,
            fundamental_summary     TEXT,
            fundamental_verdict     TEXT DEFAULT 'データなし',
            verdict                 TEXT,
            direction               TEXT DEFAULT 'LONG',
            holding_days_est        INTEGER DEFAULT 20
        );
        CREATE TABLE IF NOT EXISTS daily_picks (
            ticker                  TEXT,
            date                    TEXT,
            current_price           REAL,
            adjusted_rr             REAL,
            breakout_triggered      INTEGER,
            volume_confirmation     INTEGER,
            daily_verdict           TEXT,
            notes                   TEXT,
            PRIMARY KEY (ticker, date)
        );
        CREATE TABLE IF NOT EXISTS market_health (
            date            TEXT PRIMARY KEY,
            overall_score   REAL,
            overall_signal  TEXT,
            sector_scores   TEXT,
            theme_scores    TEXT,
            total_screened  INTEGER,
            stage2_count    INTEGER
        );
        CREATE TABLE IF NOT EXISTS news_events (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            date                TEXT,
            category            TEXT,
            title               TEXT,
            description         TEXT,
            impact              TEXT,
            affected_sectors    TEXT,
            affected_tickers    TEXT,
            source              TEXT
        );
        CREATE TABLE IF NOT EXISTS pipeline_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at      TEXT,
            stage       TEXT,
            status      TEXT,
            message     TEXT,
            duration_s  REAL
        );
        CREATE TABLE IF NOT EXISTS api_usage (
            date        TEXT PRIMARY KEY,
            fmp_calls   INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS tech_weekly_picks (
            ticker          TEXT PRIMARY KEY,
            week_of         TEXT,
            scan_date       TEXT,
            direction       TEXT DEFAULT 'LONG',
            stage           INTEGER DEFAULT 0,
            confidence      REAL,
            avg_win_rate    REAL,
            risk_reward     REAL,
            entry_price     REAL,
            stop_price      REAL,
            tp1_price       REAL,
            target_price    REAL,
            atr_pct         REAL,
            rsi             REAL,
            signals_json    TEXT DEFAULT '[]'
        );
        CREATE TABLE IF NOT EXISTS tech_daily_picks (
            ticker              TEXT,
            date                TEXT,
            current_price       REAL,
            adjusted_rr         REAL,
            daily_verdict       TEXT,
            active_signals_json TEXT DEFAULT '[]',
            PRIMARY KEY (ticker, date)
        );
        """)

        conn.commit()

        # Migrations
        migrations = [
            ("detailed_analysis", "direction TEXT DEFAULT 'LONG'"),
            ("detailed_analysis", "tp1_price REAL"),
            ("detailed_analysis", "holding_days_est INTEGER DEFAULT 20"),
            ("weekly_picks",      "direction TEXT DEFAULT 'LONG'"),
            ("weekly_picks",      "fundamental_verdict TEXT DEFAULT 'データなし'"),
            ("weekly_picks",      "tp1_price REAL"),
            ("weekly_picks",      "holding_days_est INTEGER DEFAULT 20"),
            ("news_events",       "url TEXT DEFAULT ''"),
            ("news_events",       "next_release TEXT DEFAULT ''"),
            ("tech_daily_picks",  "stage_b_signals_json TEXT DEFAULT '[]'"),
        ]
        for tbl, col_def in migrations:
            try:
                cur.execute(f"ALTER TABLE {tbl} ADD COLUMN {col_def}")
                conn.commit()
            except sqlite3.OperationalError:
                pass

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
