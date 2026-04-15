"""GET /api/chart/{ticker} — OHLCV data for candlestick chart rendering."""
from fastapi import APIRouter
from backend.db import get_connection

router = APIRouter()


@router.get("/api/chart/{ticker}")
def get_chart(ticker: str, days: int = 180):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT date, open, high, low, close, volume
        FROM price_data
        WHERE ticker = ?
        ORDER BY date DESC
        LIMIT ?
    """, (ticker.upper(), days))
    rows = cur.fetchall()
    conn.close()

    # Reverse to ascending time order for chart
    data = [
        {
            "time":   r["date"],
            "open":   r["open"],
            "high":   r["high"],
            "low":    r["low"],
            "close":  r["close"],
            "volume": r["volume"],
        }
        for r in reversed(rows)
    ]
    return {"ticker": ticker.upper(), "data": data}
