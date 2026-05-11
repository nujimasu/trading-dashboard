"""取引分析（実取引ポジションベース）API"""
from typing import Optional

from fastapi import APIRouter, Query

from backend.services import trade_analytics as ta

router = APIRouter()


@router.get("/api/trade-analytics/summary")
def summary():
    return ta.get_summary()


@router.get("/api/trade-analytics/insights")
def insights():
    return ta.get_insights()


@router.post("/api/trade-analytics/insights")
def add_insight(payload: dict):
    try:
        return ta.add_custom_insight(payload)
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(400, str(e))


@router.delete("/api/trade-analytics/insights/{insight_id}")
def dismiss_insight(insight_id: int):
    return ta.dismiss_custom_insight(insight_id)


@router.post("/api/trade-analytics/insights/{insight_id}/pin")
def pin_insight(insight_id: int):
    try:
        return ta.toggle_pin_custom_insight(insight_id)
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(404, str(e))


@router.get("/api/trade-analytics/monthly")
def monthly():
    return ta.get_monthly_breakdown()


@router.get("/api/trade-analytics/compare")
def compare(
    a_start: Optional[str] = Query(None, description="YYYY-MM"),
    a_end:   Optional[str] = Query(None, description="YYYY-MM"),
    b_start: Optional[str] = Query(None, description="YYYY-MM"),
    b_end:   Optional[str] = Query(None, description="YYYY-MM"),
):
    return ta.get_period_comparison(a_start, a_end, b_start, b_end)


@router.get("/api/trade-analytics/holding-buckets")
def holding_buckets():
    return ta.get_holding_buckets()


@router.get("/api/trade-analytics/scatter")
def scatter():
    return ta.get_scatter_data()


@router.get("/api/trade-analytics/by-type")
def by_type():
    return ta.get_by_type()


@router.get("/api/trade-analytics/trades")
def all_trades():
    return ta.get_all_trades()
