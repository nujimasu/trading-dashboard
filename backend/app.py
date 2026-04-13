"""
FastAPI application factory.
Serves the API and static frontend files.
"""
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.market_health import router as market_health_router
from backend.routes.economic      import router as economic_router
from backend.routes.news          import router as news_router
from backend.routes.weekly        import router as weekly_router
from backend.routes.daily         import router as daily_router
from backend.routes.search        import router as search_router
from backend.routes.sentiment     import router as sentiment_router
from backend.routes.tech_weekly   import router as tech_weekly_router
from backend.routes.chart              import router as chart_router
from backend.routes.entry_candidates   import router as entry_candidates_router
from backend.routes.logic2             import router as logic2_router
from backend.db import init_db

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


def _run_daily_in_background():
    """サーバー起動時にバックグラウンドで日次調整を実行する。"""
    try:
        from pipeline.daily_adjustment import run as daily_run
        print("[Startup] 日次調整をバックグラウンドで実行中...")
        daily_run()
    except Exception as e:
        print(f"[Startup] 日次調整エラー: {e}")


_pipeline_running = {"logic2": False, "logic3": False, "logic4": False}

def _run_logic_pipeline(logic_name):
    """指定ロジックのパイプラインをバックグラウンド実行。"""
    try:
        _pipeline_running[logic_name] = True
        if logic_name == "logic2":
            from pipeline.logic2_scan import run as logic_run
        elif logic_name == "logic3":
            from pipeline.logic3_scan import run as logic_run
        elif logic_name == "logic4":
            from pipeline.logic4_scan import run as logic_run
        else:
            return
        print(f"[Pipeline] {logic_name} 手動実行開始...")
        logic_run()
        print(f"[Pipeline] {logic_name} 手動実行完了")
    except Exception as e:
        print(f"[Pipeline] {logic_name} エラー: {e}")
    finally:
        _pipeline_running[logic_name] = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    # サーバー起動時: weekly_picks があれば日次調整を非同期実行
    from backend.db import get_connection
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM weekly_picks")
        count = cur.fetchone()["cnt"]
        conn.close()
        if count > 0:
            t = threading.Thread(target=_run_daily_in_background, daemon=True)
            t.start()
        else:
            print("[Startup] weekly_picks が空のため日次調整をスキップ")
    except Exception:
        pass
    yield


def create_app() -> FastAPI:
    init_db()

    app = FastAPI(
        title="Trading Dashboard",
        description="Local swing-trading analysis dashboard",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes
    for router in [
        market_health_router,
        economic_router,
        news_router,
        weekly_router,
        daily_router,
        search_router,
        sentiment_router,
        tech_weekly_router,
        chart_router,
        entry_candidates_router,
        logic2_router,
    ]:
        app.include_router(router)

    # Serve frontend static files
    if (FRONTEND_DIR / "css").exists():
        app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    if (FRONTEND_DIR / "js").exists():
        app.mount("/js",  StaticFiles(directory=str(FRONTEND_DIR / "js")),  name="js")

    @app.post("/api/pipeline/trigger/{logic_name}")
    async def trigger_pipeline(logic_name: str):
        if logic_name not in ("logic2", "logic3", "logic4"):
            return {"error": f"Unknown logic: {logic_name}"}
        if _pipeline_running.get(logic_name):
            return {"status": "already_running", "logic": logic_name}
        t = threading.Thread(target=_run_logic_pipeline, args=(logic_name,), daemon=True)
        t.start()
        return {"status": "started", "logic": logic_name}

    @app.get("/", include_in_schema=False)
    async def serve_index():
        resp = FileResponse(str(FRONTEND_DIR / "index.html"))
        resp.headers["Cache-Control"] = "no-store"
        return resp

    return app


app = create_app()
