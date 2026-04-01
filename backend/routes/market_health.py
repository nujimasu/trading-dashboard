"""GET /api/market-health — market health with full history and sector MA"""
import json
from fastapi import APIRouter
from backend.db import get_connection

router = APIRouter()


def _avg(lst):
    return round(sum(lst) / len(lst), 1) if lst else None


@router.get("/api/market-health")
def get_market_health():
    conn = get_connection()
    cur  = conn.cursor()

    # Full history sorted ascending
    cur.execute("""
        SELECT date, overall_score, overall_signal,
               sector_scores, theme_scores, total_screened, stage2_count
        FROM market_health
        ORDER BY date ASC
    """)
    rows = [dict(r) for r in cur.fetchall()]

    if not rows:
        conn.close()
        return {
            "date": None, "overall_score": 0, "overall_signal": "No Data",
            "sector_scores": {}, "theme_scores": {}, "total_screened": 0,
            "stage2_count": 0, "history": [], "sector_ma": {},
            "sector_history": {}, "prev_sector_scores": {},
            "change_5d": None, "recent5_avg": None, "prev5_avg": None,
            "indices": {},
        }

    latest  = rows[-1]
    n       = len(rows)
    scores  = [r["overall_score"] for r in rows]

    sector_scores = json.loads(latest["sector_scores"] or "{}")
    theme_scores  = json.loads(latest["theme_scores"]  or "{}")

    # Compact history for chart: [{date, score}]
    history = [{"date": r["date"], "score": r["overall_score"]} for r in rows]

    # 5-day change
    change_5d = round(scores[-1] - scores[-6], 1) if n >= 6 else None

    # Rolling 5-day averages for comparison strip
    recent5   = scores[-5:]
    prev5     = scores[-10:-5] if n >= 10 else (scores[:-5] if n > 5 else None)
    recent5_avg = _avg(recent5)
    prev5_avg   = _avg(prev5) if prev5 else None

    # Sector MA + sparkline history (last 20 data points)
    sector_ma      = {}
    sector_history = {}
    last20 = rows[-20:]
    for sector in sector_scores:
        vals = []
        pts  = []
        for r in last20:
            v = json.loads(r["sector_scores"] or "{}").get(sector)
            if v is not None:
                vals.append(v)
                pts.append({"date": r["date"], "score": v})
        if len(vals) >= 2:
            sector_ma[sector] = _avg(vals)
        if pts:
            sector_history[sector] = pts

    # Previous sector scores (for arrow direction)
    prev_sector_scores = json.loads(rows[-2]["sector_scores"] or "{}") if n >= 2 else {}

    # Sector ETF price sparklines (last 30 days from price_data)
    SECTOR_ETF_MAP = {
        "テクノロジー":   "XLK",
        "金融":           "XLF",
        "エネルギー":     "XLE",
        "ヘルスケア":     "XLV",
        "資本財":         "XLI",
        "一般消費財":     "XLY",
        "生活必需品":     "XLP",
        "公益":           "XLU",
        "不動産":         "XLRE",
        "素材":           "XLB",
        "通信・メディア": "XLC",
    }
    sector_etf_sparkline = {}
    for sector_name, etf_ticker in SECTOR_ETF_MAP.items():
        cur.execute("""
            SELECT close FROM price_data
            WHERE ticker = ? ORDER BY date ASC
        """, (etf_ticker,))
        etf_rows = cur.fetchall()
        if len(etf_rows) >= 2:
            sector_etf_sparkline[sector_name] = [r["close"] for r in etf_rows[-30:]]

    # Major index ETF data (SPY=S&P500, QQQ=NASDAQ, IWM=Russell2000)
    INDEX_MAP = {"SPY": "S&P 500", "QQQ": "NASDAQ 100", "IWM": "Russell 2000"}
    indices = {}
    for ticker, label in INDEX_MAP.items():
        cur.execute("""
            SELECT date, close FROM price_data
            WHERE ticker = ? ORDER BY date ASC
        """, (ticker,))
        idx_rows = cur.fetchall()
        if idx_rows:
            prices = [{"date": r["date"], "close": r["close"]} for r in idx_rows]
            latest_p = prices[-1]["close"]
            prev1_p  = prices[-2]["close"] if len(prices) >= 2 else latest_p
            first_p  = prices[0]["close"]
            change_1d  = round((latest_p / prev1_p - 1) * 100, 2) if prev1_p > 0 else 0
            change_30d = round((latest_p / first_p - 1) * 100, 2) if first_p > 0 else 0
            indices[ticker] = {
                "label":        label,
                "price":        round(latest_p, 2),
                "change_1d":    change_1d,
                "change_30d":   change_30d,
                "history":      prices[-30:],   # last 30 days for sparkline
            }

    conn.close()

    return {
        "date":               latest["date"],
        "overall_score":      latest["overall_score"],
        "overall_signal":     latest["overall_signal"],
        "sector_scores":      sector_scores,
        "theme_scores":       theme_scores,
        "total_screened":     latest["total_screened"],
        "stage2_count":       latest["stage2_count"],
        "history":            history,
        "sector_ma":          sector_ma,
        "sector_history":     sector_history,
        "prev_sector_scores": prev_sector_scores,
        "change_5d":             change_5d,
        "recent5_avg":           recent5_avg,
        "prev5_avg":             prev5_avg,
        "indices":               indices,
        "sector_etf_sparkline":  sector_etf_sparkline,
    }
