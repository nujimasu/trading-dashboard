"""
Full pipeline orchestrator.
Run: python pipeline/run_pipeline.py [options]

Options:
  --daily-only     Only run daily_adjustment (fast, for market hours)
  --skip-download  Skip Stage 2 download (use existing price data)
  --tech-weekly    Run pure-technical scan (signal-scanner logic)
  --tech-daily     Run tech daily adjustment only
"""
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.db import init_db, db_cursor


def log_stage(stage: str, status: str, message: str, duration: float = 0):
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO pipeline_log (run_at, stage, status, message, duration_s)
            VALUES (?, ?, ?, ?, ?)
        """, (datetime.now().isoformat(), stage, status, message, duration))
    print(f"[{stage}] {status}: {message} ({duration:.1f}s)")


def run_full(skip_download: bool = False):
    print("=" * 60)
    print(f"Trading Dashboard Pipeline — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Ensure DB is initialized
    init_db()

    total_start = time.time()

    # ── Stage 1: Universe ──────────────────────────────────────────────────
    t0 = time.time()
    try:
        from pipeline.stage1_universe import run as stage1_run
        tickers = stage1_run()
        log_stage("Stage1", "OK", f"{len(tickers)} tickers in universe", time.time() - t0)
    except Exception as e:
        log_stage("Stage1", "ERROR", str(e), time.time() - t0)
        print(f"[FATAL] Stage 1 failed: {e}")
        return

    # ── Stage 2: Price download ────────────────────────────────────────────
    if not skip_download:
        t0 = time.time()
        try:
            from pipeline.stage2_price_data import run as stage2_run
            downloaded = stage2_run(tickers)
            log_stage("Stage2", "OK", f"{len(downloaded)} tickers downloaded", time.time() - t0)
        except Exception as e:
            log_stage("Stage2", "ERROR", str(e), time.time() - t0)
            print(f"[WARN] Stage 2 failed: {e}, continuing with existing data...")
    else:
        print("[Stage2] Skipped (--skip-download)")

    # ── Stage 3: Technical filter ─────────────────────────────────────────
    t0 = time.time()
    try:
        from pipeline.stage3_technical_filter import run as stage3_run
        survivors_s3 = stage3_run(tickers)
        longs_s3  = len(survivors_s3.get("longs",  []))
        shorts_s3 = len(survivors_s3.get("shorts", []))
        log_stage("Stage3", "OK", f"{longs_s3} long + {shorts_s3} short passed filter", time.time() - t0)
    except Exception as e:
        log_stage("Stage3", "ERROR", str(e), time.time() - t0)
        print(f"[FATAL] Stage 3 failed: {e}")
        return

    if not longs_s3 and not shorts_s3:
        print("[Pipeline] No stocks passed Stage 3 filter. Done.")
        return

    # ── Stage 4: Detailed analysis ────────────────────────────────────────
    t0 = time.time()
    try:
        from pipeline.stage4_detailed_analysis import run as stage4_run
        survivors_s4 = stage4_run(survivors_s3)
        log_stage("Stage4", "OK", f"{len(survivors_s4)} passed RR filter", time.time() - t0)
    except Exception as e:
        log_stage("Stage4", "ERROR", str(e), time.time() - t0)
        print(f"[FATAL] Stage 4 failed: {e}")
        return

    # ── Stage 5: Fundamentals ─────────────────────────────────────────────
    t0 = time.time()
    try:
        from pipeline.stage5_fundamentals import run as stage5_run
        enriched = stage5_run(survivors_s4)
        log_stage("Stage5", "OK", f"{len(enriched)} tickers enriched", time.time() - t0)
    except Exception as e:
        log_stage("Stage5", "ERROR", str(e), time.time() - t0)
        enriched = survivors_s4
        print(f"[WARN] Stage 5 failed: {e}, continuing without fundamentals...")

    # ── Stage 6: Scoring ──────────────────────────────────────────────────
    t0 = time.time()
    try:
        from pipeline.stage6_scoring import run as stage6_run
        final_picks = stage6_run(enriched)
        log_stage("Stage6", "OK", f"{len(final_picks)} weekly picks generated", time.time() - t0)
    except Exception as e:
        log_stage("Stage6", "ERROR", str(e), time.time() - t0)
        print(f"[FATAL] Stage 6 failed: {e}")
        return

    # ── News collection ───────────────────────────────────────────────────
    t0 = time.time()
    try:
        from pipeline.news_collector import run as news_run
        news_run()
        log_stage("News", "OK", "Economic + news events saved", time.time() - t0)
    except Exception as e:
        log_stage("News", "ERROR", str(e), time.time() - t0)
        print(f"[WARN] News collection failed: {e}")

    total = time.time() - total_start
    print("=" * 60)
    print(f"Pipeline complete in {total:.0f}s. {len(final_picks)} picks ready.")
    print("Start dashboard: python run.py")
    print("=" * 60)


def run_daily():
    print(f"[Daily] Running daily adjustment — {datetime.now().strftime('%H:%M')}")
    init_db()
    t0 = time.time()
    try:
        from pipeline.daily_adjustment import run as daily_run
        daily_run()
        log_stage("Daily", "OK", "Daily picks updated", time.time() - t0)
    except Exception as e:
        log_stage("Daily", "ERROR", str(e), time.time() - t0)
        print(f"[ERROR] Daily adjustment failed: {e}")
    # テクニカル日次も同時実行
    t0 = time.time()
    try:
        from pipeline.tech_scan import run_daily as tech_daily_run
        tech_daily_run()
        log_stage("TechDaily", "OK", "Tech daily picks updated", time.time() - t0)
    except Exception as e:
        log_stage("TechDaily", "ERROR", str(e), time.time() - t0)
        print(f"[WARN] Tech daily adjustment failed: {e}")


def run_tech_weekly():
    print(f"[TechWeekly] Pure technical scan — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    init_db()
    t0 = time.time()
    try:
        from pipeline.tech_scan import run as tech_run
        results = tech_run()
        log_stage("TechWeekly", "OK", f"{len(results)} tech picks generated", time.time() - t0)
    except Exception as e:
        log_stage("TechWeekly", "ERROR", str(e), time.time() - t0)
        print(f"[ERROR] Tech weekly scan failed: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trading Dashboard Pipeline")
    parser.add_argument("--daily-only",    action="store_true", help="Run daily adjustment only")
    parser.add_argument("--skip-download", action="store_true", help="Skip price data download")
    parser.add_argument("--tech-weekly",   action="store_true", help="Run pure-technical weekly scan")
    parser.add_argument("--tech-daily",    action="store_true", help="Run tech daily adjustment only")
    args = parser.parse_args()

    if args.daily_only:
        run_daily()
    elif args.tech_weekly:
        run_tech_weekly()
    elif args.tech_daily:
        init_db()
        from pipeline.tech_scan import run_daily as tech_daily_run
        tech_daily_run()
    else:
        run_full(skip_download=args.skip_download)
