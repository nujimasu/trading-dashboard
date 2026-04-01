"""Economic data routes: indicators + sector ETF performance dashboard."""
import json
import time
from fastapi import APIRouter
from backend.db import get_connection

router = APIRouter()

# ── In-memory cache for sector ETF data (30 min TTL) ─────────────────────────
_sector_cache: dict = {"data": None, "ts": 0}
_SECTOR_TTL = 1800  # 30 minutes


def _get_sector_performance() -> dict:
    """Fetch sector ETF 1d / YTD performance. Cached 30 min."""
    global _sector_cache
    if _sector_cache["data"] and time.time() - _sector_cache["ts"] < _SECTOR_TTL:
        return _sector_cache["data"]

    SECTOR_ETFS = {
        "XLK": "テクノロジー", "XLF": "金融",     "XLE": "エネルギー",
        "XLV": "ヘルスケア",   "XLI": "資本財",   "XLY": "一般消費財",
        "XLP": "生活必需品",   "XLU": "公益",      "XLRE": "不動産",
        "XLB": "素材",         "XLC": "通信・メディア",
    }
    result = {}
    try:
        import yfinance as yf
        tickers = list(SECTOR_ETFS.keys())
        df = yf.download(
            " ".join(tickers), period="ytd",
            auto_adjust=True, progress=False, threads=True,
        )
        closes = df["Close"]
        for ticker, name in SECTOR_ETFS.items():
            try:
                s = closes[ticker].dropna()
                if len(s) >= 2:
                    chg_1d  = round((float(s.iloc[-1]) - float(s.iloc[-2])) / float(s.iloc[-2]) * 100, 2)
                    chg_ytd = round((float(s.iloc[-1]) - float(s.iloc[0]))  / float(s.iloc[0])  * 100, 2)
                    result[name] = {
                        "ticker":     ticker,
                        "price":      round(float(s.iloc[-1]), 2),
                        "change_1d":  chg_1d,
                        "change_ytd": chg_ytd,
                    }
            except Exception:
                continue
    except Exception as e:
        print(f"[EconDash] sector ETF error: {e}")

    _sector_cache = {"data": result, "ts": time.time()}
    return result


# ── Routes ────────────────────────────────────────────────────────────────────

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


@router.get("/api/economic-dashboard")
def get_economic_dashboard():
    """Dashboard: FRED indicators + live sector ETF performance."""
    conn = get_connection()
    cur  = conn.cursor()

    # FRED indicators — latest per indicator name
    cur.execute("""
        SELECT title, description, impact, source, date, affected_sectors
        FROM news_events
        WHERE category = 'economic'
        ORDER BY date DESC
    """)
    fred_rows = cur.fetchall()
    conn.close()

    seen: dict = {}
    for r in fred_rows:
        name = r["title"]
        if name not in seen:
            seen[name] = {
                "name":             name,
                "description":      r["description"],
                "impact":           r["impact"],
                "source":           r["source"],
                "date":             r["date"],
                "affected_sectors": json.loads(r["affected_sectors"] or "[]"),
            }

    return {
        "fred_indicators":  list(seen.values()),
        "sector_performance": _get_sector_performance(),
    }
