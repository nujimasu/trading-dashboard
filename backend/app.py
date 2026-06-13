"""
FastAPI application factory.
Serves the API and static frontend files.
"""
import os
import sys
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
from backend.routes.logic4             import router as logic4_router
from backend.routes.backtest           import router as backtest_router
from backend.routes.positions          import router as positions_router
from backend.routes.trade_analytics    import router as trade_analytics_router
from backend.db import init_db

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


def create_app() -> FastAPI:
    # Vercel (サーバーレス) ではテーブルは既存前提のため、コールドスタート毎の
    # init_db をスキップする。スキーマは GitHub Actions の cron / 既存 DB が管理。
    # ローカル / Render では起動時にテーブルを作成する。
    if not os.getenv("VERCEL"):
        init_db()

    app = FastAPI(
        title="Trading Dashboard",
        description="Local swing-trading analysis dashboard",
        version="1.0.0",
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
        logic4_router,
        backtest_router,
        positions_router,
        trade_analytics_router,
    ]:
        app.include_router(router)

    # Serve frontend static files
    if (FRONTEND_DIR / "css").exists():
        app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    if (FRONTEND_DIR / "js").exists():
        app.mount("/js",  StaticFiles(directory=str(FRONTEND_DIR / "js")),  name="js")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        resp = FileResponse(str(FRONTEND_DIR / "index.html"))
        resp.headers["Cache-Control"] = "no-store"
        return resp

    return app


app = create_app()
