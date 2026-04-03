"""GET /api/daily-picks"""
import json
from datetime import date, datetime, timezone, timedelta
from fastapi import APIRouter
from backend.db import get_connection

router = APIRouter()


def _get_jst_date():
    """Get today's date in JST (Asia/Tokyo)"""
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).date().isoformat()


@router.get("/api/daily-picks")
def get_daily_picks():
    today = _get_jst_date()
    conn  = get_connection()
    cur   = conn.cursor()

    # Join daily_picks with weekly_picks for full context
    cur.execute("""
        SELECT
            d.ticker,
            d.date,
            d.current_price,
            d.adjusted_rr,
            d.breakout_triggered,
            d.volume_confirmation,
            d.daily_verdict,
            d.notes,
            w.composite_score,
            w.tier,
            w.sector,
            w.themes,
            w.entry_price,
            w.stop_price,
            w.tp1_price,
            w.target_price,
            w.risk_reward        AS weekly_rr,
            w.holding_days_est,
            w.direction,
            w.verdict            AS weekly_verdict,
            w.fundamental_verdict,
            w.technical_summary,
            w.fundamental_summary
        FROM daily_picks d
        LEFT JOIN weekly_picks w ON w.ticker = d.ticker
        WHERE d.date = ?
        ORDER BY
            CASE d.daily_verdict
                WHEN 'ENTRY_NOW' THEN 1
                WHEN 'WATCH'     THEN 2
                WHEN 'WAIT'      THEN 3
                ELSE 4
            END,
            w.composite_score DESC
    """, (today,))

    rows = cur.fetchall()
    conn.close()

    return [
        {
            "ticker":              r["ticker"],
            "date":                r["date"],
            "current_price":       r["current_price"],
            "adjusted_rr":         r["adjusted_rr"],
            "breakout_triggered":  bool(r["breakout_triggered"]),
            "volume_confirmation": bool(r["volume_confirmation"]),
            "daily_verdict":       r["daily_verdict"],
            "notes":               r["notes"],
            "composite_score":     r["composite_score"],
            "tier":                r["tier"],
            "sector":              r["sector"],
            "themes":              json.loads(r["themes"] or "[]"),
            "entry_price":         r["entry_price"],
            "stop_price":          r["stop_price"],
            "tp1_price":           r["tp1_price"],
            "target_price":        r["target_price"],
            "weekly_rr":           r["weekly_rr"],
            "holding_days_est":    r["holding_days_est"],
            "direction":           r["direction"] or "LONG",
            "fundamental_verdict": r["fundamental_verdict"] or "データなし",
            "technical_summary":   json.loads(r["technical_summary"]  or "{}"),
            "fundamental_summary": json.loads(r["fundamental_summary"] or "{}"),
        }
        for r in rows
    ]
