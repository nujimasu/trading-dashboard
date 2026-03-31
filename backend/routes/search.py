"""GET /api/search/{ticker}  — on-demand single-ticker analysis"""
import json
from fastapi import APIRouter, HTTPException
from backend.db import get_connection
from backend.services.indicators import compute_stock_summary, build_entry_reasons, build_risk_factors
from backend.services.fundamentals import get_or_fetch_fundamentals
from config import THEME_MAP, MIN_RR_TIER2, MIN_RR_TIER1

import yfinance as yf

router = APIRouter()


def _get_themes(ticker: str) -> list[str]:
    return [theme for theme, members in THEME_MAP.items() if ticker in members]


@router.get("/api/search/{ticker}")
def search_ticker(ticker: str):
    ticker = ticker.upper().strip()

    # Fetch fresh price data
    try:
        yf_ticker = yf.Ticker(ticker)
        df = yf_ticker.history(period="1y", auto_adjust=True)
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No price data found for {ticker}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"yfinance error: {e}")

    # Compute technical summary
    summary = compute_stock_summary(ticker, df)
    if not summary:
        raise HTTPException(status_code=422, detail=f"Insufficient data or zero risk for {ticker}")

    rr    = summary["risk_reward"]
    tier  = summary["tier"]

    entry_reasons = build_entry_reasons(summary)
    risk_factors  = build_risk_factors(summary)

    # Verdict
    if rr < MIN_RR_TIER2:
        verdict = "NO-BUY"
        verdict_reason = f"RR {rr:.2f} < {MIN_RR_TIER2}（最低基準未達）"
    elif not summary.get("stage2_uptrend"):
        verdict = "NO-BUY"
        verdict_reason = "Stage 2アップトレンド条件未達（Close > SMA50 > SMA200 不成立）"
    elif tier == "Tier1":
        verdict = "BUY"
        verdict_reason = f"Tier 1 — RR {rr:.2f} ≥ {MIN_RR_TIER1}, Stage 2アップトレンド確認済"
    elif tier == "Tier2":
        verdict = "WATCH"
        verdict_reason = f"Tier 2 — RR {rr:.2f} ≥ {MIN_RR_TIER2}, ハーフサイズ推奨"
    else:
        verdict = "NO-BUY"
        verdict_reason = "条件未達"

    # Try to get fundamentals (cached or fresh FMP)
    fundamentals = None
    try:
        fundamentals = get_or_fetch_fundamentals(ticker)
    except Exception:
        pass

    fund_summary = {}
    if fundamentals:
        fund_summary = {
            "available":             True,
            "sector":                fundamentals.get("sector", ""),
            "industry":              fundamentals.get("industry", ""),
            "market_cap_b":          round((fundamentals.get("market_cap") or 0) / 1e9, 1),
            "pe_ratio":              fundamentals.get("pe_ratio"),
            "eps_growth_yoy":        fundamentals.get("eps_growth_yoy"),
            "revenue_growth_yoy":    fundamentals.get("revenue_growth_yoy"),
            "earnings_surprise_pct": fundamentals.get("earnings_surprise_pct"),
            "description":           (fundamentals.get("description") or "")[:400],
        }

    # Price history for chart (last 6 months, weekly OHLCV)
    chart_data = []
    try:
        hist = yf_ticker.history(period="6mo", interval="1d", auto_adjust=True)
        for dt, row in hist.iterrows():
            chart_data.append({
                "time":   dt.strftime("%Y-%m-%d"),
                "open":   round(float(row["Open"]),  2),
                "high":   round(float(row["High"]),  2),
                "low":    round(float(row["Low"]),   2),
                "close":  round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })
    except Exception:
        pass

    return {
        "ticker":          ticker,
        "verdict":         verdict,
        "verdict_reason":  verdict_reason,
        "tier":            tier,
        "themes":          _get_themes(ticker),
        "price":           summary["price"],
        "change_pct":      summary["change_pct"],
        "volume":          summary["volume"],
        "indicators": {
            "sma50":       summary.get("sma50"),
            "sma200":      summary.get("sma200"),
            "rsi":         summary.get("rsi"),
            "macd":        summary.get("macd"),
            "macd_signal": summary.get("macd_signal"),
            "atr":         summary.get("atr"),
            "vol_ratio":   summary.get("vol_ratio"),
        },
        "trade": {
            "entry":       summary["entry"],
            "stop":        summary["stop"],
            "target":      summary["target"],
            "risk":        summary["risk"],
            "reward":      summary["reward"],
            "risk_reward": rr,
            "high_52w":    summary["high_52w"],
            "low_52w":     summary["low_52w"],
            "pct_from_high": summary["pct_from_high"],
        },
        "entry_reasons":   entry_reasons,
        "risk_factors":    risk_factors,
        "fundamental_summary": fund_summary,
        "chart_data":      chart_data,
    }


@router.get("/api/pipeline/status")
def get_pipeline_status():
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        SELECT stage, status, run_at, duration_s, message
        FROM pipeline_log
        ORDER BY id DESC
        LIMIT 20
    """)
    logs = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT COUNT(*) FROM weekly_picks")
    picks_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT ticker) FROM price_data")
    price_count = cur.fetchone()[0]

    cur.execute("SELECT date, overall_signal FROM market_health ORDER BY date DESC LIMIT 1")
    mh = cur.fetchone()

    conn.close()

    return {
        "weekly_picks_count": picks_count,
        "price_data_tickers": price_count,
        "market_health":      dict(mh) if mh else None,
        "recent_logs":        logs,
    }
