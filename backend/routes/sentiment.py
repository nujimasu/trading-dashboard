"""GET /api/market-sentiment — VIX + Fear & Greed Index"""
import time
import requests
import yfinance as yf
from fastapi import APIRouter

router = APIRouter()

# Simple in-memory cache (1 hour TTL)
_cache = {"data": None, "ts": 0}
_CACHE_TTL = 3600


def _fetch_vix():
    """yfinance から VIX の直近30日データを取得。"""
    try:
        df = yf.download("^VIX", period="35d", auto_adjust=True, progress=False)
        if df.empty:
            return None
        # yfinance may return MultiIndex columns — flatten
        col = df["Close"]
        if hasattr(col, "squeeze"):
            col = col.squeeze()
        closes = col.dropna()
        if closes.empty:
            return None

        values  = [round(float(v), 2) for v in closes.to_numpy()]
        current = values[-1]
        prev1   = values[-2] if len(values) >= 2 else current
        prev5   = values[-6] if len(values) >= 6 else values[0]
        dates   = [str(d)[:10] for d in closes.index]

        return {
            "current":   current,
            "change_1d": round(current - prev1, 2),
            "change_5d": round(current - prev5, 2),
            "history":   [{"date": d, "value": v} for d, v in zip(dates, values)],
        }
    except Exception as e:
        print(f"[Sentiment] VIX fetch error: {e}")
        return None


def _vix_label(v):
    if v is None:
        return "データなし", "neutral"
    if v < 15:
        return "低水準（楽観）", "greed"
    if v < 20:
        return "通常", "neutral"
    if v < 30:
        return "警戒ゾーン", "fear"
    return "恐怖ゾーン", "extreme-fear"


def _fetch_fear_greed():
    """CNN Fear & Greed Index を取得。"""
    try:
        resp = requests.get(
            "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
            timeout=8,
        )
        resp.raise_for_status()
        raw = resp.json()

        fg     = raw.get("fear_and_greed", {})
        score  = round(float(fg.get("score", 50)), 1)
        rating = fg.get("rating", "Unknown")

        # Historical data (last 30 points)
        hist_raw = raw.get("fear_and_greed_historical", {}).get("data", [])
        history  = []
        for pt in hist_raw[-30:]:
            ts_ms  = pt.get("x", 0)
            val    = pt.get("y")
            if val is None:
                continue
            date_str = time.strftime("%Y-%m-%d", time.gmtime(ts_ms / 1000))
            history.append({"date": date_str, "value": round(float(val), 1)})

        return {
            "score":   score,
            "rating":  rating,
            "history": history,
        }
    except Exception as e:
        print(f"[Sentiment] Fear & Greed fetch error: {e}")
        return None


@router.get("/api/market-sentiment")
def get_market_sentiment():
    now = time.time()
    if _cache["data"] and now - _cache["ts"] < _CACHE_TTL:
        return _cache["data"]

    vix = _fetch_vix()
    fg  = _fetch_fear_greed()

    vix_label, vix_cls = _vix_label(vix["current"] if vix else None)

    result = {
        "vix": {
            **(vix or {}),
            "label": vix_label,
            "css":   vix_cls,
        } if vix else {"current": None, "label": "取得失敗", "css": "neutral", "history": []},
        "fear_greed": fg or {"score": None, "rating": "取得失敗", "history": []},
    }

    _cache["data"] = result
    _cache["ts"]   = now
    return result
