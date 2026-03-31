"""GET /api/economic-indicators"""
import json
from fastapi import APIRouter
from backend.db import get_connection

router = APIRouter()


@router.get("/api/economic-indicators")
def get_economic_indicators(limit: int = 20):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, date, title, description, impact,
               affected_sectors, affected_tickers, source
        FROM news_events
        WHERE category = 'economic'
        ORDER BY date DESC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "id":               r["id"],
            "date":             r["date"],
            "title":            r["title"],
            "description":      r["description"],
            "impact":           r["impact"],
            "affected_sectors": json.loads(r["affected_sectors"] or "[]"),
            "affected_tickers": json.loads(r["affected_tickers"] or "[]"),
            "source":           r["source"],
        }
        for r in rows
    ]
