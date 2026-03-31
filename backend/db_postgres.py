"""
PostgreSQL互換レイヤー — Supabase接続
既存のSQLite コード（? プレースホルダー・sqlite3.Row アクセス）を
そのまま動かすためのラッパー。
DATABASE_URL 環境変数が設定された場合のみ使用される。
"""
import os
import re
import json
from contextlib import contextmanager
import psycopg2
import psycopg2.extras


DATABASE_URL = os.environ["DATABASE_URL"]


class CompatRow(dict):
    """sqlite3.Row 互換の dict。row["col"] でも row.get("col") でもアクセス可能。"""
    pass


class CompatCursor:
    """`?` を `%s` に自動変換するカーソルラッパー。"""

    def __init__(self, cursor):
        self._cur = cursor

    def _convert(self, sql: str) -> str:
        return sql.replace("?", "%s")

    def execute(self, sql: str, params=None):
        sql = self._convert(sql)
        self._cur.execute(sql, params)
        return self

    def executemany(self, sql: str, seq):
        sql = self._convert(sql)
        self._cur.executemany(sql, seq)
        return self

    def _make_row(self, raw_row) -> CompatRow | None:
        if raw_row is None:
            return None
        cols = [desc[0] for desc in self._cur.description]
        return CompatRow(zip(cols, raw_row))

    def fetchone(self) -> CompatRow | None:
        return self._make_row(self._cur.fetchone())

    def fetchall(self) -> list[CompatRow]:
        rows = self._cur.fetchall()
        cols = [desc[0] for desc in self._cur.description] if self._cur.description else []
        return [CompatRow(zip(cols, r)) for r in rows]

    @property
    def lastrowid(self):
        return self._cur.fetchone()[0] if self._cur.description else None

    @property
    def rowcount(self):
        return self._cur.rowcount


class CompatConnection:
    """psycopg2 コネクションを sqlite3 互換インターフェースでラップ。"""

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


def get_connection() -> CompatConnection:
    conn = psycopg2.connect(DATABASE_URL)
    return CompatConnection(conn)


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
    """PostgreSQL に全テーブルを作成（存在しない場合のみ）。"""
    conn = get_connection()
    cur = conn.cursor()

    statements = [
        """
        CREATE TABLE IF NOT EXISTS universe (
            ticker      TEXT PRIMARY KEY,
            name        TEXT,
            sector      TEXT,
            industry    TEXT,
            market_cap  REAL,
            exchange    TEXT,
            updated_at  TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS price_data (
            ticker  TEXT,
            date    TEXT,
            open    REAL,
            high    REAL,
            low     REAL,
            close   REAL,
            volume  BIGINT,
            PRIMARY KEY (ticker, date)
        )
        """,
        """
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
        )
        """,
        """
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
        )
        """,
        """
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
        )
        """,
        """
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
        )
        """,
        """
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
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS market_health (
            date            TEXT PRIMARY KEY,
            overall_score   REAL,
            overall_signal  TEXT,
            sector_scores   TEXT,
            theme_scores    TEXT,
            total_screened  INTEGER,
            stage2_count    INTEGER
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS news_events (
            id                  BIGSERIAL PRIMARY KEY,
            date                TEXT,
            category            TEXT,
            title               TEXT,
            description         TEXT,
            impact              TEXT,
            affected_sectors    TEXT,
            affected_tickers    TEXT,
            source              TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS pipeline_log (
            id          BIGSERIAL PRIMARY KEY,
            run_at      TEXT,
            stage       TEXT,
            status      TEXT,
            message     TEXT,
            duration_s  REAL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS api_usage (
            date        TEXT PRIMARY KEY,
            fmp_calls   INTEGER DEFAULT 0
        )
        """,
        """
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
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS tech_daily_picks (
            ticker              TEXT,
            date                TEXT,
            current_price       REAL,
            adjusted_rr         REAL,
            daily_verdict       TEXT,
            active_signals_json TEXT DEFAULT '[]',
            PRIMARY KEY (ticker, date)
        )
        """,
    ]

    for stmt in statements:
        cur.execute(stmt)

    conn.commit()
    conn.close()
    print("[DB] PostgreSQL tables initialized (Supabase)")


def get_fmp_call_count(date_str: str) -> int:
    with db_cursor() as cur:
        cur.execute("SELECT fmp_calls FROM api_usage WHERE date = %s", (date_str,))
        row = cur.fetchone()
        return row["fmp_calls"] if row else 0


def increment_fmp_call_count(date_str: str, n: int = 1):
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO api_usage (date, fmp_calls) VALUES (%s, %s)
            ON CONFLICT (date) DO UPDATE SET fmp_calls = api_usage.fmp_calls + %s
        """, (date_str, n, n))
