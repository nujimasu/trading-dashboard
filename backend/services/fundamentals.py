from __future__ import annotations
"""
yfinance を使ったファンダメンタルズ取得（FMP不要・APIキー不要）
"""
import sys
from pathlib import Path
from datetime import datetime, date

import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from backend.db import db_cursor


def _fetch_from_yfinance(ticker: str) -> dict | None:
    """yfinance から基本ファンダメンタルズを取得。"""
    try:
        info = yf.Ticker(ticker).info
        if not info or info.get("quoteType") not in ("EQUITY", "equity"):
            # quoteType がない場合も続行
            if not info:
                return None

        # 決算サプライズ（直近の実績 vs 予想EPS）
        earnings_surprise_pct = None
        try:
            t = yf.Ticker(ticker)
            hist = t.earnings_history
            if hist is not None and not hist.empty:
                latest = hist.iloc[0]
                surprise = latest.get("surprisePercent")
                if surprise is not None:
                    earnings_surprise_pct = round(float(surprise) * 100, 1)
        except Exception:
            pass

        # EPS成長率: yfinanceは小数（0.956 = 95.6%）
        eps_g = info.get("earningsGrowth")
        rev_g = info.get("revenueGrowth")
        roe   = info.get("returnOnEquity")

        return {
            "ticker":                ticker,
            "sector":                info.get("sector", ""),
            "industry":              info.get("industry", ""),
            "market_cap":            info.get("marketCap", 0) or 0,
            "pe_ratio":              info.get("trailingPE"),
            "eps_growth_yoy":        round(eps_g * 100, 1) if eps_g is not None else None,
            "revenue_growth_yoy":    round(rev_g * 100, 1) if rev_g is not None else None,
            "earnings_surprise_pct": earnings_surprise_pct,
            "roe":                   round(roe  * 100, 1) if roe  is not None else None,
            "description":           info.get("longBusinessSummary", ""),
            "updated_at":            datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"[Fundamentals] yfinance error {ticker}: {e}")
        return None


def get_or_fetch_fundamentals(ticker: str) -> dict | None:
    """キャッシュ（7日有効）があれば返し、なければyfinanceから取得・保存。"""
    with db_cursor() as cur:
        cur.execute("SELECT * FROM fundamentals WHERE ticker = ?", (ticker,))
        row = cur.fetchone()

    if row:
        row = dict(row)
        try:
            days_old = (datetime.now() - datetime.fromisoformat(row["updated_at"])).days
            if days_old < 7:
                return row
        except Exception:
            pass

    data = _fetch_from_yfinance(ticker)
    if not data:
        return dict(row) if row else None

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


# ── 後方互換（news_collector等から呼ばれる可能性があるため残す） ───────────────
def fetch_economic_calendar() -> list[dict]: return []
def fetch_market_news(limit: int = 30)    -> list[dict]: return []
def fetch_sector_performance()            -> list[dict]: return []
