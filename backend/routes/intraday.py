"""GET /api/intraday/* — 5分足シミュレーション（指値タッチ約定）の戦績"""
from typing import Optional

from fastapi import APIRouter, Query

from backend.services.intraday_tracker import get_intraday_stats

router = APIRouter()


@router.get("/api/intraday/stats")
def intraday_stats(
    fill_mode: str            = Query("limit", pattern="^(limit|open)$"),
    days:      Optional[int]  = Query(None, ge=1, le=365),
    verdict:   Optional[str]  = Query(None),
):
    """ロジック別の勝率・期待値（5分足・指値タッチ約定ベース）。"""
    return get_intraday_stats(fill_mode=fill_mode, since_days=days, verdict=verdict)


@router.get("/api/intraday/trades")
def intraday_trades(
    fill_mode: str           = Query("limit", pattern="^(limit|open)$"),
    logic:     Optional[str] = Query(None),
    limit:     int           = Query(60, ge=1, le=500),
):
    """直近のシミュレーション結果一覧。"""
    from backend.db import db_cursor

    where = ["fill_mode = ?"]
    params: list = [fill_mode]
    if logic:
        where.append("logic_name = ?")
        params.append(logic)

    with db_cursor() as cur:
        cur.execute(f"""
            SELECT logic_name, ticker, signal_date, status, verdict,
                   entry_plan, fill_price, fill_at, exit_price, exit_at, exit_reason,
                   realized_r, mtm_r, hit_tp1, days_held, mae_pct, mfe_pct
            FROM signal_log_intraday
            WHERE {' AND '.join(where)}
            ORDER BY signal_date DESC, id DESC
            LIMIT ?
        """, tuple(params) + (limit,))
        rows = [dict(r) for r in cur.fetchall()]

    for r in rows:
        for k in ("signal_date", "fill_at", "exit_at"):
            v = r.get(k)
            if v is not None and not isinstance(v, str):
                r[k] = v.isoformat() if hasattr(v, "isoformat") else str(v)

    return {"trades": rows, "count": len(rows)}
