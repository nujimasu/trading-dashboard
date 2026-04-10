"""
PostgreSQL互換レイヤー — Supabase接続
既存のSQLite コード（? プレースホルダー・sqlite3.Row アクセス）を
そのまま動かすためのラッパー。
DATABASE_URL 環境変数が設定された場合のみ使用される。
"""
import os
import re
import json
import time
from contextlib import contextmanager
from typing import Optional
import psycopg2
import psycopg2.extras


DATABASE_URL = os.environ["DATABASE_URL"]

# sslmode が未指定なら require を付加（Supabase pooler 必須）
if "sslmode" not in DATABASE_URL:
    DATABASE_URL += "?sslmode=require" if "?" not in DATABASE_URL else "&sslmode=require"


class CompatRow(dict):
    """sqlite3.Row 互換の dict。row["col"] でも row.get("col") でもアクセス可能。"""
    pass


def _sanitize_params(params):
    """numpy スカラー型を Python ネイティブ型に変換（psycopg2 が np.float64 等を扱えないため）。"""
    if params is None:
        return None
    import numpy as np
    def _fix(v):
        if isinstance(v, (np.integer,)):  return int(v)
        if isinstance(v, (np.floating,)): return float(v)
        if isinstance(v, (np.bool_,)):    return bool(v)
        return v
    if isinstance(params, dict):
        return {k: _fix(v) for k, v in params.items()}
    return tuple(_fix(v) for v in params)


class CompatCursor:
    """`?` を `%s`、`:name` を `%(name)s` に自動変換するカーソルラッパー。"""

    def __init__(self, cursor):
        self._cur = cursor

    def _convert(self, sql: str, params=None) -> str:
        if isinstance(params, dict):
            # SQLite named params (:name) → psycopg2 named params (%(name)s)
            sql = re.sub(r':(\w+)', r'%(\1)s', sql)
        else:
            # SQLite positional params (?) → psycopg2 positional params (%s)
            sql = sql.replace("?", "%s")
        return sql

    def execute(self, sql: str, params=None):
        sql = self._convert(sql, params)
        self._cur.execute(sql, _sanitize_params(params))
        return self

    def executemany(self, sql: str, seq):
        sql = self._convert(sql)
        self._cur.executemany(sql, [_sanitize_params(p) for p in seq])
        return self

    def _make_row(self, raw_row) -> Optional[CompatRow]:
        if raw_row is None:
            return None
        cols = [desc[0] for desc in self._cur.description]
        return CompatRow(zip(cols, raw_row))

    def fetchone(self) -> Optional[CompatRow]:
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


def get_connection(retries: int = 3) -> CompatConnection:
    for attempt in range(retries):
        try:
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
            return CompatConnection(conn)
        except psycopg2.OperationalError:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # 1s, 2s
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
            source              TEXT,
            url                 TEXT DEFAULT '',
            next_release        TEXT DEFAULT ''
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
        """
        CREATE TABLE IF NOT EXISTS logic3_picks (
            ticker               TEXT PRIMARY KEY,
            scan_date            TEXT,
            perfect_order        TEXT,
            perf_3m              REAL,
            perf_6m              REAL,
            avg_vol_20d          REAL,
            dow_trend            TEXT,
            support_price        REAL,
            confluence           INTEGER DEFAULT 0,
            support_reasons      TEXT DEFAULT '[]',
            reji_sapo            TEXT DEFAULT 'none',
            risk_reward          REAL,
            entry_price          REAL,
            stop_price           REAL,
            tp1_price            REAL,
            target_price         REAL,
            rsi                  REAL,
            rsi_flag             INTEGER DEFAULT 0,
            macd_div_flag        INTEGER DEFAULT 0,
            fib_confluence       TEXT,
            atr                  REAL,
            verdict              TEXT,
            confidence           REAL,
            composite_score      REAL,
            sector               TEXT,
            current_price        REAL,
            holding_days_est     INTEGER DEFAULT 14,
            signals_json         TEXT DEFAULT '[]',
            price_to_support_pct REAL,
            h4_trigger           TEXT,
            h4_structure         TEXT DEFAULT 'neutral'
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS logic4_picks (
            ticker               TEXT PRIMARY KEY,
            scan_date            TEXT,
            perfect_order        TEXT,
            perf_3m              REAL,
            perf_6m              REAL,
            avg_vol_20d          REAL,
            dow_trend            TEXT,
            support_price        REAL,
            confluence           INTEGER DEFAULT 0,
            support_reasons      TEXT DEFAULT '[]',
            reji_sapo            TEXT DEFAULT 'none',
            risk_reward          REAL,
            entry_price          REAL,
            stop_price           REAL,
            tp1_price            REAL,
            target_price         REAL,
            rsi                  REAL,
            rsi_flag             INTEGER DEFAULT 0,
            macd_div_flag        INTEGER DEFAULT 0,
            fib_confluence       TEXT,
            atr                  REAL,
            verdict              TEXT,
            confidence           REAL,
            composite_score      REAL,
            sector               TEXT,
            current_price        REAL,
            holding_days_est     INTEGER DEFAULT 14,
            signals_json         TEXT DEFAULT '[]',
            price_to_support_pct REAL,
            h1_trigger           TEXT,
            h4_structure         TEXT DEFAULT 'neutral'
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS logic2_picks (
            ticker               TEXT PRIMARY KEY,
            scan_date            TEXT,
            perfect_order        TEXT,
            perf_3m              REAL,
            perf_6m              REAL,
            avg_vol_20d          REAL,
            dow_trend            TEXT,
            support_price        REAL,
            confluence           INTEGER DEFAULT 0,
            support_reasons      TEXT DEFAULT '[]',
            reji_sapo            TEXT DEFAULT 'none',
            risk_reward          REAL,
            entry_price          REAL,
            stop_price           REAL,
            tp1_price            REAL,
            target_price         REAL,
            rsi                  REAL,
            rsi_flag             INTEGER DEFAULT 0,
            macd_div_flag        INTEGER DEFAULT 0,
            fib_confluence       TEXT,
            atr                  REAL,
            verdict              TEXT,
            confidence           REAL,
            composite_score      REAL,
            sector               TEXT,
            current_price        REAL,
            holding_days_est     INTEGER DEFAULT 14,
            signals_json         TEXT DEFAULT '[]',
            price_to_support_pct REAL,
            h4_trigger           TEXT,
            h4_structure         TEXT DEFAULT 'neutral',
            h4_triggers_all      TEXT DEFAULT '[]',
            trigger_bonus        REAL DEFAULT 0
        )
        """,
    ]

    for stmt in statements:
        cur.execute(stmt)

    # Column migrations for existing tables
    # logic3_picks のスキーマが旧28シグナル版から押し目買い4H版に変更
    # 旧テーブルを削除して新スキーマで再作成
    try:
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'logic3_picks' AND column_name = 'h4_trigger'
        """)
        if not cur.fetchone():
            cur.execute("DROP TABLE IF EXISTS logic3_picks")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS logic3_picks (
                    ticker               TEXT PRIMARY KEY,
                    scan_date            TEXT,
                    perfect_order        TEXT,
                    perf_3m              REAL,
                    perf_6m              REAL,
                    avg_vol_20d          REAL,
                    dow_trend            TEXT,
                    support_price        REAL,
                    confluence           INTEGER DEFAULT 0,
                    support_reasons      TEXT DEFAULT '[]',
                    reji_sapo            TEXT DEFAULT 'none',
                    risk_reward          REAL,
                    entry_price          REAL,
                    stop_price           REAL,
                    tp1_price            REAL,
                    target_price         REAL,
                    rsi                  REAL,
                    rsi_flag             INTEGER DEFAULT 0,
                    macd_div_flag        INTEGER DEFAULT 0,
                    fib_confluence       TEXT,
                    atr                  REAL,
                    verdict              TEXT,
                    confidence           REAL,
                    composite_score      REAL,
                    sector               TEXT,
                    current_price        REAL,
                    holding_days_est     INTEGER DEFAULT 14,
                    signals_json         TEXT DEFAULT '[]',
                    price_to_support_pct REAL,
                    h4_trigger           TEXT,
                    h4_structure         TEXT DEFAULT 'neutral'
                )
            """)
            conn.commit()
            print("[DB] logic3_picks table recreated with new schema (4H trigger)")
    except Exception as e:
        conn.rollback()
        print(f"[DB] logic3_picks migration error: {e}")

    pg_migrations = [
        "ALTER TABLE news_events ADD COLUMN IF NOT EXISTS url TEXT DEFAULT ''",
        "ALTER TABLE news_events ADD COLUMN IF NOT EXISTS next_release TEXT DEFAULT ''",
        "ALTER TABLE tech_daily_picks ADD COLUMN IF NOT EXISTS stage_b_signals_json TEXT DEFAULT '[]'",
        "ALTER TABLE daily_picks ADD COLUMN IF NOT EXISTS take_profit_verdict TEXT DEFAULT 'HOLD'",
        "ALTER TABLE daily_picks ADD COLUMN IF NOT EXISTS take_profit_signals TEXT DEFAULT ''",
        "ALTER TABLE logic4_picks ADD COLUMN IF NOT EXISTS price_to_support_pct REAL",
        "ALTER TABLE logic4_picks ADD COLUMN IF NOT EXISTS h1_trigger TEXT",
        "ALTER TABLE logic4_picks ADD COLUMN IF NOT EXISTS h4_structure TEXT DEFAULT 'neutral'",
    ]
    for m in pg_migrations:
        try:
            cur.execute(m)
        except Exception:
            conn.rollback()

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
