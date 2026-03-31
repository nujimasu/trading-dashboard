"""
FMP API wrapper — stable/ endpoint (v3 legacy endpoints廃止対応済み)
"""
import requests
from datetime import date, datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import FMP_API_KEY, FMP_DAILY_LIMIT
from backend.db import db_cursor, get_fmp_call_count, increment_fmp_call_count

# v3廃止により stable/ に統一
FMP_STABLE = "https://financialmodelingprep.com/stable"


def _today() -> str:
    return date.today().isoformat()


def _can_call(n: int = 1) -> bool:
    used = get_fmp_call_count(_today())
    return used + n <= FMP_DAILY_LIMIT


def _get(path: str, params: dict = None) -> dict | list | None:
    """stable/ APIへGETリクエスト。403/404は黙って None を返す。"""
    if not FMP_API_KEY:
        return None
    if not _can_call():
        return None

    url = f"{FMP_STABLE}{path}"
    p   = {"apikey": FMP_API_KEY, **(params or {})}
    try:
        resp = requests.get(url, params=p, timeout=10)
        if resp.status_code in (403, 404):
            return None          # プラン制限 or 廃止エンドポイント — 静かにスキップ
        resp.raise_for_status()
        increment_fmp_call_count(_today())
        data = resp.json()
        return data if data else None
    except requests.HTTPError:
        return None
    except Exception as e:
        print(f"[FMP] Error {path}: {e}")
        return None


# ─── 個別エンドポイント ────────────────────────────────────────────────────

def fetch_stock_profile(ticker: str) -> dict | None:
    data = _get("/profile", {"symbol": ticker})
    if not data or not isinstance(data, list) or len(data) == 0:
        return None
    p = data[0]
    return {
        "ticker":      ticker,
        "sector":      p.get("sector", ""),
        "industry":    p.get("industry", ""),
        "market_cap":  p.get("marketCap", 0),
        "pe_ratio":    p.get("pe", None),
        "description": p.get("description", ""),
    }


def fetch_income_growth(ticker: str) -> dict | None:
    """直近2期のYoY EPS・売上成長率を返す。"""
    data = _get("/income-statement", {"symbol": ticker, "limit": 5, "period": "annual"})
    if not data or not isinstance(data, list) or len(data) < 2:
        return None
    latest, prev = data[0], data[1]

    def pct(new, old):
        if old and old != 0:
            return round((new - old) / abs(old) * 100, 1)
        return None

    return {
        "eps_growth_yoy":     pct(latest.get("eps", 0),     prev.get("eps", 0)),
        "revenue_growth_yoy": pct(latest.get("revenue", 0), prev.get("revenue", 0)),
    }


def fetch_earnings_surprise(ticker: str) -> float | None:
    """最新の決算サプライズ%（stable/ では現状404 → None）。"""
    # 現在の無料プランでは未対応のため None を返す
    return None


def get_or_fetch_fundamentals(ticker: str) -> dict | None:
    """キャッシュ（7日有効）があれば返し、なければFMPから取得・保存。"""
    with db_cursor() as cur:
        cur.execute("SELECT *, updated_at FROM fundamentals WHERE ticker = ?", (ticker,))
        row = cur.fetchone()

    if row:
        days_old = (datetime.now() - datetime.fromisoformat(row["updated_at"])).days
        if days_old < 7:
            return dict(row)

    if not _can_call(1):
        return dict(row) if row else None

    profile = fetch_stock_profile(ticker)
    growth  = fetch_income_growth(ticker)

    if not profile:
        return None

    data = {
        "ticker":                ticker,
        "sector":                profile.get("sector", ""),
        "industry":              profile.get("industry", ""),
        "market_cap":            profile.get("market_cap", 0),
        "pe_ratio":              profile.get("pe_ratio"),
        "eps_growth_yoy":        growth.get("eps_growth_yoy")     if growth else None,
        "revenue_growth_yoy":    growth.get("revenue_growth_yoy") if growth else None,
        "earnings_surprise_pct": None,
        "roe":                   None,
        "description":           profile.get("description", ""),
        "updated_at":            datetime.now().isoformat(),
    }

    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO fundamentals
                (ticker, sector, industry, market_cap, pe_ratio,
                 eps_growth_yoy, revenue_growth_yoy, earnings_surprise_pct,
                 roe, description, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(ticker) DO UPDATE SET
                sector=excluded.sector, industry=excluded.industry,
                market_cap=excluded.market_cap, pe_ratio=excluded.pe_ratio,
                eps_growth_yoy=excluded.eps_growth_yoy,
                revenue_growth_yoy=excluded.revenue_growth_yoy,
                earnings_surprise_pct=excluded.earnings_surprise_pct,
                roe=excluded.roe, description=excluded.description,
                updated_at=excluded.updated_at
        """, (
            data["ticker"], data["sector"], data["industry"],
            data["market_cap"], data["pe_ratio"],
            data["eps_growth_yoy"], data["revenue_growth_yoy"],
            data["earnings_surprise_pct"], data["roe"],
            data["description"], data["updated_at"],
        ))
    return data


# ─── ニュース・経済指標（現在の無料プランでは取得不可） ─────────────────────

def fetch_economic_calendar() -> list[dict]:
    """経済カレンダー（stable/ では現状未対応）。"""
    return []


def fetch_market_news(limit: int = 30) -> list[dict]:
    """市場ニュース（stable/ では現状未対応）。"""
    return []


def fetch_sector_performance() -> list[dict]:
    """セクターパフォーマンス（stable/ では現状未対応）。"""
    return []
