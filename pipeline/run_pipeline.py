"""Trading dashboard pipeline orchestrator."""

import argparse
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.db import db_cursor, init_db


def log_stage(stage: str, status: str, message: str, duration: float = 0):
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO pipeline_log (run_at, stage, status, message, duration_s)
            VALUES (?, ?, ?, ?, ?)
        """, (datetime.now().isoformat(), stage, status, message, duration))
    print(f"[{stage}] {status}: {message} ({duration:.1f}s)")


def _load_universe() -> list[str]:
    from backend.db import get_connection

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT ticker FROM universe")
        return [row["ticker"] for row in cur.fetchall()]
    finally:
        conn.close()


def _run_market_health(stage: str = "MarketHealth") -> None:
    from backend.db import get_connection
    from pipeline.market_health import compute_market_health

    started = time.time()
    conn = get_connection()
    try:
        compute_market_health(conn)
        log_stage(stage, "OK", "market_health updated", time.time() - started)
    except Exception as exc:
        log_stage(stage, "ERROR", str(exc), time.time() - started)
        print(f"[WARN] market_health computation failed: {exc}")
    finally:
        conn.close()


def _run_news(stage: str = "News") -> None:
    started = time.time()
    try:
        from pipeline.news_collector import run as news_run

        news_run()
        log_stage(stage, "OK", "Economic + news events saved", time.time() - started)
    except Exception as exc:
        log_stage(stage, "ERROR", str(exc), time.time() - started)
        print(f"[WARN] News collection failed: {exc}")


def run_full(skip_download: bool = False) -> None:
    print("=" * 60)
    print(f"Trading Dashboard Pipeline — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    init_db()
    total_start = time.time()

    max_age_days = 14
    started = time.time()
    existing = _load_universe()
    last_updated = None
    if existing:
        try:
            from backend.db import get_connection

            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT MAX(updated_at) AS mx FROM universe")
            row = cur.fetchone()
            last_updated = row["mx"] if row else None
            conn.close()
        except Exception:
            pass

    fresh = False
    if len(existing) >= 400 and last_updated:
        try:
            fresh = date.fromisoformat(str(last_updated)[:10]) >= date.today() - timedelta(days=max_age_days)
        except Exception:
            fresh = True

    if fresh:
        tickers = existing
        log_stage("Stage1", "SKIP", f"既存universe {len(tickers)}銘柄が新鮮(再構築不要)", time.time() - started)
    else:
        try:
            from pipeline.stage1_universe import run as stage1_run

            tickers = stage1_run()
            log_stage("Stage1", "OK", f"{len(tickers)} tickers in universe", time.time() - started)
        except Exception as exc:
            if existing:
                tickers = existing
                log_stage("Stage1", "WARN", f"再構築失敗→既存{len(tickers)}銘柄を使用: {str(exc)[:120]}", time.time() - started)
            else:
                log_stage("Stage1", "ERROR", str(exc), time.time() - started)
                print(f"[FATAL] Stage 1 failed: {exc}")
                return

    if skip_download:
        log_stage("Stage2", "SKIP", "--skip-download specified", 0)
    else:
        started = time.time()
        try:
            if os.getenv("POLYGON_API_KEY"):
                from pipeline.stage2_price_data import run_grouped

                downloaded = run_grouped(tickers, lookback_days=15)
                message = f"{len(downloaded)} tickers (Polygon grouped)"
            else:
                from pipeline.stage2_price_data import run as stage2_run

                downloaded = stage2_run(tickers)
                message = f"{len(downloaded)} tickers (yfinance)"
            log_stage("Stage2", "OK", message, time.time() - started)
        except Exception as exc:
            log_stage("Stage2", "ERROR", str(exc), time.time() - started)
            print(f"[WARN] Stage 2 failed: {exc}, continuing with existing data...")

    _run_market_health()
    _run_news()

    started = time.time()
    try:
        from pipeline.swing_scan import run as swing_run

        swing_run()
        log_stage("SwingScan", "OK", "swing picks updated", time.time() - started)
    except Exception as exc:
        log_stage("SwingScan", "ERROR", str(exc), time.time() - started)
        print(f"[WARN] Swing scan failed: {exc}")

    print("=" * 60)
    print(f"Pipeline complete in {time.time() - total_start:.0f}s.")
    print("Start dashboard: python run.py")
    print("=" * 60)


def run_daily_light() -> None:
    """Light update: Stage 2, market health, and news (no swing scan)."""
    print(f"[DailyLight] 日次軽量モード — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    init_db()
    tickers = _load_universe()
    started = time.time()
    try:
        if os.getenv("POLYGON_API_KEY"):
            from pipeline.stage2_price_data import run_grouped

            updated = run_grouped(tickers, lookback_days=6)
            message = f"{len(updated)}/{len(tickers)} tickers (Polygon grouped)"
        else:
            from pipeline.stage2_price_data import run_incremental

            updated = run_incremental(tickers, days=10) if tickers else []
            message = f"{len(updated)}/{len(tickers)} tickers (yfinance incremental)"
        status = "OK" if updated else "WARN"
        log_stage("DailyLight-Stage2", status, message, time.time() - started)
    except Exception as exc:
        log_stage("DailyLight-Stage2", "ERROR", str(exc), time.time() - started)
        print(f"[WARN] Stage 2 light update failed: {exc}")

    _run_market_health("DailyLight-MarketHealth")
    _run_news("DailyLight-News")
    print("[DailyLight] 完了")


def run_backfill(days: int) -> None:
    init_db()
    tickers = _load_universe()
    from pipeline.stage2_price_data import run_grouped_backfill

    started = time.time()
    saved = run_grouped_backfill(tickers, lookback_days=days)
    log_stage("Backfill-Grouped", "OK" if saved else "WARN", f"{len(saved)}/{len(tickers)} tickers", time.time() - started)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trading Dashboard Pipeline")
    parser.add_argument("--daily-light", action="store_true", help="Run light Stage 2 + market health + news")
    parser.add_argument("--skip-download", action="store_true", help="Skip full-pipeline price download")
    parser.add_argument("--backfill", action="store_true", help="Backfill Polygon grouped price data")
    parser.add_argument("--backfill-days", type=int, default=320, help="Business days to backfill")
    args = parser.parse_args()

    if args.backfill:
        run_backfill(args.backfill_days)
    elif args.daily_light:
        run_daily_light()
    else:
        run_full(skip_download=args.skip_download)
