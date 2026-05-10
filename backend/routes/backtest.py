"""GET /api/backtest/stats — 戦績サマリー"""
from fastapi import APIRouter, Query
from typing import Optional

from backend.services.signal_tracker import get_logic_stats, get_tag_stats

router = APIRouter()


@router.get("/api/backtest/stats")
def get_stats(
    logic: Optional[str] = Query(None, description="logic1|logic2|logic3"),
    days:  Optional[int] = Query(None, ge=1, le=3650, description="集計期間 (日数)"),
):
    """ロジック別戦績の集計を返す。"""
    return get_logic_stats(logic_name=logic, since_days=days)


@router.get("/api/backtest/tag-stats")
def get_tag_stats_route(
    logic:     Optional[str] = Query(None),
    days:      Optional[int] = Query(None, ge=1, le=3650),
    min_count: int            = Query(3, ge=1, le=100),
):
    """シグナルタグ別の戦績集計。最低件数 min_count 未満のタグは除外。"""
    return get_tag_stats(logic_name=logic, since_days=days, min_count=min_count)


@router.get("/api/backtest/recent")
def get_recent_signals(
    logic: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    """最近のシグナル一覧（評価済み・未評価両方）。"""
    from backend.db import db_cursor

    where = []
    params: list = []
    if logic:
        where.append("logic_name = ?")
        params.append(logic)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with db_cursor() as cur:
        cur.execute(f"""
            SELECT id, logic_name, ticker, signal_date, direction,
                   entry_price, stop_price, tp1_price, target_price, confidence,
                   status, exit_date, exit_price, realized_r, days_held,
                   mae_pct, mfe_pct, hit_tp1
            FROM signal_log
            {where_sql}
            ORDER BY signal_date DESC, id DESC
            LIMIT ?
        """, tuple(params) + (limit,))
        rows = [dict(r) for r in cur.fetchall()]

    # 日付を文字列化
    for r in rows:
        for k in ("signal_date", "exit_date"):
            if r.get(k) is not None and not isinstance(r[k], str):
                r[k] = r[k].isoformat() if hasattr(r[k], "isoformat") else str(r[k])

    return {"signals": rows, "count": len(rows)}
