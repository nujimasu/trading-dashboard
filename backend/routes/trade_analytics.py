"""取引分析（実取引ポジションベース）API"""
from fastapi import APIRouter

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
