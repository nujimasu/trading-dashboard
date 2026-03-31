"""GET /api/weekly-picks  and  GET /api/weekly-picks/{ticker}"""
import json
from fastapi import APIRouter, HTTPException
from backend.db import get_connection

router = APIRouter()


def _format_pick(row) -> dict:
    return {
        "ticker":              row["ticker"],
        "week_of":             row["week_of"],
        "composite_score":     row["composite_score"],
        "tier":                row["tier"],
        "sector":              row["sector"],
        "themes":              json.loads(row["themes"] or "[]"),
        "entry_price":         row["entry_price"],
        "stop_price":          row["stop_price"],
        "tp1_price":           row["tp1_price"],
        "target_price":        row["target_price"],
        "risk_reward":         row["risk_reward"],
        "holding_days_est":    row["holding_days_est"] if row["holding_days_est"] else 20,
        "verdict":              row["verdict"],
        "direction":            row["direction"] if row["direction"] else "LONG",
        "fundamental_verdict":  row["fundamental_verdict"] if row["fundamental_verdict"] else "データなし",
        "technical_summary":    json.loads(row["technical_summary"]  or "{}"),
        "fundamental_summary":  json.loads(row["fundamental_summary"] or "{}"),
    }


@router.get("/api/weekly-picks")
def get_weekly_picks():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT * FROM weekly_picks
        ORDER BY composite_score DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [_format_pick(r) for r in rows]


@router.get("/api/weekly-picks/{ticker}")
def get_weekly_pick_detail(ticker: str):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM weekly_picks WHERE ticker = ?", (ticker.upper(),))
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail=f"{ticker} not found in weekly picks")

    return _format_pick(row)
