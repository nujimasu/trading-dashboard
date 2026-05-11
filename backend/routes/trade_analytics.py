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
