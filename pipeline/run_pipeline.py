"""
Full pipeline orchestrator.
Run: python pipeline/run_pipeline.py [options]

Options:
  --daily-only     Only run daily_adjustment (fast, for market hours)
  --skip-download  Skip Stage 2 download (use existing price data)
  --tech-weekly    Run pure-technical scan (signal-scanner logic)
  --tech-daily     Run tech daily adjustment only
"""
import os
import sys
import time
import argparse
from datetime import datetime, date, timedelta
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
    # 既存universeが十分新しければ再構築をスキップする。
    # 理由: FMP /stock/list は現プランで404のため Stage1 は実質 static_universe
    # (コード内固定リスト)依存で、再構築は membership を更新せず sector補完(yfinance)
    # のみが長時間化し pooler 切断→FATAL を招く。週次自動更新を完走させるための堅牢化。
    UNIVERSE_MAX_AGE_DAYS = 14
    t0 = time.time()
    existing, last_upd = [], None
    try:
        from backend.db import get_connection
        _c = get_connection(); _cur = _c.cursor()
        _cur.execute("SELECT ticker FROM universe")
        existing = [r["ticker"] for r in _cur.fetchall()]
        _cur.execute("SELECT MAX(updated_at) AS mx FROM universe")
        _row = _cur.fetchone()
        last_upd = _row["mx"] if _row else None
        _c.close()
    except Exception:
        pass

    fresh = False
    if existing and len(existing) >= 400 and last_upd:
        try:
            fresh = date.fromisoformat(str(last_upd)[:10]) >= date.today() - timedelta(days=UNIVERSE_MAX_AGE_DAYS)
        except Exception:
            fresh = True  # 日付パース不能でも既存が十分あれば使う

    if fresh:
        tickers = existing
        log_stage("Stage1", "SKIP", f"既存universe {len(tickers)}銘柄が新鮮(再構築不要)", time.time() - t0)
    else:
        try:
            from pipeline.stage1_universe import run as stage1_run
            tickers = stage1_run()
            log_stage("Stage1", "OK", f"{len(tickers)} tickers in universe", time.time() - t0)
        except Exception as e:
            if existing:  # 再構築失敗 → 既存universeで続行(週次をFATALさせない)
                tickers = existing
                log_stage("Stage1", "WARN", f"再構築失敗→既存{len(tickers)}銘柄を使用: {str(e)[:120]}", time.time() - t0)
            else:
                log_stage("Stage1", "ERROR", str(e), time.time() - t0)
                print(f"[FATAL] Stage 1 failed: {e}")
                return

    # ── Stage 2: Price download ────────────────────────────────────────────
    # POLYGON_API_KEY があれば grouped daily(1コール/営業日)で直近を全銘柄一括前進。
    # price_data は日次 grouped で最新化済みのため gap-fill は軽量で済みタイムアウトしない。
    # キーが無ければ従来の yfinance 全銘柄DLにフォールバック。
    if not skip_download:
        t0 = time.time()
        try:
            if os.getenv("POLYGON_API_KEY"):
                from pipeline.stage2_price_data import run_grouped
                downloaded = run_grouped(tickers, lookback_days=15)
                log_stage("Stage2", "OK", f"{len(downloaded)} tickers (Polygon grouped)", time.time() - t0)
            else:
                from pipeline.stage2_price_data import run as stage2_run
                downloaded = stage2_run(tickers)
                log_stage("Stage2", "OK", f"{len(downloaded)} tickers (yfinance)", time.time() - t0)
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

    # ── Logic2 scan ───────────────────────────────────────────────────────
    t0 = time.time()
    try:
        from pipeline.logic2_scan import run as logic2_run
        logic2_run()
        log_stage("Logic2", "OK", "Logic2 picks generated", time.time() - t0)
    except Exception as e:
        log_stage("Logic2", "ERROR", str(e), time.time() - t0)
        print(f"[WARN] Logic2 scan failed: {e}")

    # ── Logic3 scan ───────────────────────────────────────────────────────
    t0 = time.time()
    try:
        from pipeline.logic3_scan import run as logic3_run
        logic3_run()
        log_stage("Logic3", "OK", "Logic3 picks generated", time.time() - t0)
    except Exception as e:
        log_stage("Logic3", "ERROR", str(e), time.time() - t0)
        print(f"[WARN] Logic3 scan failed: {e}")

    # ── Logic4 scan (押し目買い v3) ─────────────────────────────────────────
    t0 = time.time()
    try:
        from pipeline.logic4_scan import run as logic4_run
        logic4_run()
        log_stage("Logic4", "OK", "Logic4 (押し目買いv3) picks generated", time.time() - t0)
    except Exception as e:
        log_stage("Logic4", "ERROR", str(e), time.time() - t0)
        print(f"[WARN] Logic4 scan failed: {e}")

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


def run_daily_full():
    """日次フルフィルタ: 差分DL → Stage3〜6再実行 → weekly_picks/tech_picks を毎日更新。"""
    print(f"[DailyFull] 日次フルフィルタ — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    init_db()

    # ── ユニバース取得（DBから、FMP呼び出しなし）──────────────────────────────
    from backend.db import get_connection
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT ticker FROM universe")
    tickers = [r["ticker"] for r in cur.fetchall()]
    conn.close()

    if not tickers:
        print("[DailyFull] universe が空。先に週次パイプラインを実行してください。")
        return

    # ── Stage 2: 差分DL（直近10日分）─────────────────────────────────────────
    t0 = time.time()
    try:
        from pipeline.stage2_price_data import run_incremental
        run_incremental(tickers, days=10)
        log_stage("DailyFull-Stage2", "OK", f"{len(tickers)} tickers incremental update", time.time() - t0)
    except Exception as e:
        log_stage("DailyFull-Stage2", "ERROR", str(e), time.time() - t0)
        print(f"[WARN] 差分DL失敗: {e}、既存データで続行...")

    # ── Stage 3: テクニカルフィルター ─────────────────────────────────────────
    t0 = time.time()
    try:
        from pipeline.stage3_technical_filter import run as stage3_run
        survivors_s3 = stage3_run(tickers)
        longs  = len(survivors_s3.get("longs",  []))
        shorts = len(survivors_s3.get("shorts", []))
        log_stage("DailyFull-Stage3", "OK", f"{longs} long + {shorts} short", time.time() - t0)
    except Exception as e:
        log_stage("DailyFull-Stage3", "ERROR", str(e), time.time() - t0)
        print(f"[FATAL] Stage3 失敗: {e}")
        return

    if not longs and not shorts:
        print("[DailyFull] Stage3通過銘柄なし。終了。")
        return

    # ── Stage 4: RR計算 ───────────────────────────────────────────────────────
    t0 = time.time()
    try:
        from pipeline.stage4_detailed_analysis import run as stage4_run
        survivors_s4 = stage4_run(survivors_s3)
        log_stage("DailyFull-Stage4", "OK", f"{len(survivors_s4)} passed RR filter", time.time() - t0)
    except Exception as e:
        log_stage("DailyFull-Stage4", "ERROR", str(e), time.time() - t0)
        print(f"[FATAL] Stage4 失敗: {e}")
        return

    # ── Stage 5: ファンダメンタルズ（キャッシュ優先・API追加呼び出し最小）─────
    t0 = time.time()
    try:
        from pipeline.stage5_fundamentals import run as stage5_run
        enriched = stage5_run(survivors_s4)
        log_stage("DailyFull-Stage5", "OK", f"{len(enriched)} enriched", time.time() - t0)
    except Exception as e:
        log_stage("DailyFull-Stage5", "ERROR", str(e), time.time() - t0)
        enriched = survivors_s4

    # ── Stage 6: スコアリング → weekly_picks 更新 ─────────────────────────────
    t0 = time.time()
    try:
        from pipeline.stage6_scoring import run as stage6_run
        final_picks = stage6_run(enriched)
        log_stage("DailyFull-Stage6", "OK", f"{len(final_picks)} picks updated", time.time() - t0)
    except Exception as e:
        log_stage("DailyFull-Stage6", "ERROR", str(e), time.time() - t0)
        print(f"[FATAL] Stage6 失敗: {e}")
        return

    # ── 日次調整（当日価格・verdict 更新）────────────────────────────────────
    t0 = time.time()
    try:
        from pipeline.daily_adjustment import run as daily_run
        daily_run()
        log_stage("DailyFull-Daily", "OK", "daily_picks updated", time.time() - t0)
    except Exception as e:
        log_stage("DailyFull-Daily", "ERROR", str(e), time.time() - t0)

    # ── ロジック２スキャン（日次）────────────────────────────────────────────
    t0 = time.time()
    try:
        from pipeline.logic2_scan import run as logic2_run
        logic2_run()
        log_stage("DailyFull-Logic2", "OK", "logic2_picks updated", time.time() - t0)
    except Exception as e:
        log_stage("DailyFull-Logic2", "ERROR", str(e), time.time() - t0)
        print(f"[WARN] Logic2 scan failed: {e}")

    # ── ロジック３スキャン（日次）────────────────────────────────────────────
    t0 = time.time()
    try:
        from pipeline.logic3_scan import run as logic3_run
        logic3_run()
        log_stage("DailyFull-Logic3", "OK", "logic3_picks updated", time.time() - t0)
    except Exception as e:
        log_stage("DailyFull-Logic3", "ERROR", str(e), time.time() - t0)
        print(f"[WARN] Logic3 scan failed: {e}")

    # ── テクニカルスキャン（日次）────────────────────────────────────────────
    t0 = time.time()
    try:
        from pipeline.tech_scan import run_daily as tech_daily_run
        tech_daily_run()
        log_stage("DailyFull-TechDaily", "OK", "tech daily updated", time.time() - t0)
    except Exception as e:
        log_stage("DailyFull-TechDaily", "ERROR", str(e), time.time() - t0)

    print(f"[DailyFull] 完了。{len(final_picks)} picks、daily_picks 更新済み。")


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


def run_daily_light():
    """
    日次軽量モード — GH Actions 分数節約のため Stage 3-6 を省く。
    やること:
      1. 価格データ差分DL (オープンポジ + オープンシグナル銘柄に絞る)
      2. シグナル評価 (signal_tracker.evaluate_open_signals)
    Stage 3-6 (フィルタ再計算) は週次に任せる。
    """
    print(f"[DailyLight] 日次軽量モード — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    init_db()

    from backend.db import get_connection

    # ── 全universe を Polygon grouped で前進(1コール/営業日, キーがある時のみ) ──
    # これで週次フル実行時に重い価格DLが不要になりタイムアウトを回避する。
    if os.getenv("POLYGON_API_KEY"):
        t0 = time.time()
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT ticker FROM universe")
            uni = [r["ticker"] for r in cur.fetchall()]
            conn.close()
            from pipeline.stage2_price_data import run_grouped
            grouped_saved = run_grouped(uni, lookback_days=6)
            log_stage("DailyLight-Grouped", "OK" if grouped_saved else "WARN",
                      f"{len(grouped_saved)}/{len(uni)} tickers (Polygon grouped)", time.time() - t0)
        except Exception as e:
            log_stage("DailyLight-Grouped", "ERROR", str(e), time.time() - t0)
            print(f"[WARN] grouped前進失敗: {e} — 続行")

    # オープンポジ + オープンシグナルの ticker を抽出
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT DISTINCT ticker FROM positions WHERE status = 'open'
        UNION
        SELECT DISTINCT ticker FROM signal_log WHERE status = 'open'
    """)
    tickers = [r["ticker"] for r in cur.fetchall()]
    conn.close()

    print(f"[DailyLight] 価格更新対象: {len(tickers)} tickers")

    if tickers:
        t0 = time.time()
        try:
            from pipeline.stage2_price_data import run_incremental
            run_incremental(tickers, days=10)
            log_stage("DailyLight-Stage2", "OK", f"{len(tickers)} tickers", time.time() - t0)
        except Exception as e:
            log_stage("DailyLight-Stage2", "ERROR", str(e), time.time() - t0)
            print(f"[WARN] 差分DL失敗: {e} — 評価は続行")

    # シグナル評価
    t0 = time.time()
    try:
        from backend.services.signal_tracker import evaluate_open_signals
        stats = evaluate_open_signals()
        log_stage("DailyLight-Eval", "OK", str(stats), time.time() - t0)
    except Exception as e:
        log_stage("DailyLight-Eval", "ERROR", str(e), time.time() - t0)
        print(f"[ERROR] シグナル評価失敗: {e}")

    print(f"[DailyLight] 完了")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trading Dashboard Pipeline")
    parser.add_argument("--daily-only",    action="store_true", help="Run daily adjustment only")
    parser.add_argument("--daily-full",    action="store_true", help="Run incremental DL + full Stage3-6 re-filter daily")
    parser.add_argument("--daily-light",   action="store_true", help="Light daily: incremental DL for open positions/signals + signal evaluation only")
    parser.add_argument("--skip-download", action="store_true", help="Skip price data download")
    parser.add_argument("--tech-weekly",   action="store_true", help="Run pure-technical weekly scan")
    parser.add_argument("--tech-daily",    action="store_true", help="Run tech daily adjustment only")
    parser.add_argument("--backfill",      action="store_true", help="Polygon grouped で全universeの履歴を一括バックフィル(初回用)")
    parser.add_argument("--backfill-days", type=int, default=320, help="バックフィルする営業日数(既定320≒300取引日)")
    args = parser.parse_args()

    if args.backfill:
        init_db()
        from backend.db import get_connection as _gc
        _conn = _gc(); _cur = _conn.cursor()
        _cur.execute("SELECT ticker FROM universe")
        _uni = [r["ticker"] for r in _cur.fetchall()]
        _conn.close()
        from pipeline.stage2_price_data import run_grouped_backfill
        t0 = time.time()
        saved = run_grouped_backfill(_uni, lookback_days=args.backfill_days)
        log_stage("Backfill-Grouped", "OK" if saved else "WARN",
                  f"{len(saved)}/{len(_uni)} tickers (Polygon grouped backfill)", time.time() - t0)
    elif args.daily_only:
        run_daily()
    elif args.daily_full:
        run_daily_full()
    elif args.daily_light:
        run_daily_light()
    elif args.tech_weekly:
        run_tech_weekly()
    elif args.tech_daily:
        init_db()
        from pipeline.tech_scan import run_daily as tech_daily_run
        tech_daily_run()
    else:
        run_full(skip_download=args.skip_download)
