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


@router.get("/api/trade-analytics/equity-curve")
def equity_curve():
    return ta.get_equity_curve()


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


@router.get("/api/trade-analytics/by-tags")
def by_tags():
    return ta.get_by_tags()


@router.get("/api/trade-analytics/cut-loss")
def cut_loss():
    return ta.get_cut_loss_analysis()


@router.get("/api/trade-analytics/weekly-coaching")
def weekly_coaching(week_offset: int = 0):
    from backend.services import weekly_coaching as wc
    return wc.get_weekly_coaching(week_offset=week_offset)


@router.get("/api/trade-analytics/trades")
def all_trades():
    return ta.get_all_trades()


# ────────────────────────────────────────────────────────────────────
# ロジック検証 (ペーパートレード) — ユーザー判断と独立した戦績
# 既存の backend.services.signal_tracker (毎晩 GitHub Actions cron で評価)
# をHTTPから手動トリガー / 集計参照できるように露出する。
# ────────────────────────────────────────────────────────────────────

@router.post("/api/signals/evaluate")
def evaluate_signals(max_holding_days: int = Query(30, ge=1, le=90)):
    """status='open' の全シグナルを price_data で評価。バッチ手動トリガー用。"""
    from backend.services import signal_tracker as st
    return st.evaluate_open_signals(max_holding_days=max_holding_days)


@router.get("/api/logic-performance")
def logic_performance(
    logic_name: Optional[str] = Query(None),
    since_days: Optional[int] = Query(None, ge=1, le=730),
):
    """ロジック別のペーパートレード戦績 (勝率・期待値R・PF・最大DD)。"""
    from backend.services import signal_tracker as st
    return st.get_logic_stats(logic_name=logic_name, since_days=since_days)
