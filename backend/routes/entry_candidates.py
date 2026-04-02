"""GET /api/entry-candidates — 全4ソースのエントリー候補を統合"""
import json
from datetime import date
from fastapi import APIRouter
from backend.db import get_connection

router = APIRouter()

# エントリー対象とする verdict
DAILY_FUNDA_OK  = {"ENTRY_NOW", "WATCH"}
DAILY_TECH_OK   = {"STRONG_BUY", "STRONG_SELL", "BUY", "SELL", "WATCH"}
WEEKLY_TECH_MIN_CONFIDENCE = 0.55  # 55% 以上

SOURCE_LABEL = {
    "daily_funda":  "日次FA",
    "daily_tech":   "日次TE",
    "weekly_funda": "週次FA",
    "weekly_tech":  "週次TE",
}


@router.get("/api/entry-candidates")
def get_entry_candidates():
    today = date.today().isoformat()
    conn  = get_connection()
    cur   = conn.cursor()
    candidates: dict[str, dict] = {}

    def _get(ticker: str) -> dict:
        if ticker not in candidates:
            candidates[ticker] = {
                "ticker":        ticker,
                "sources":       [],
                "direction":     "LONG",
                "current_price": None,
                "best_rr":       None,
                "tier":          None,
                "sector":        None,
                "verdicts":      {},
            }
        return candidates[ticker]

    # ── 日次ファンダ ──────────────────────────────────────────────────────────
    cur.execute("""
        SELECT d.ticker, d.current_price, d.adjusted_rr, d.daily_verdict,
               w.tier, w.sector, w.direction, w.composite_score
        FROM daily_picks d
        LEFT JOIN weekly_picks w ON w.ticker = d.ticker
        WHERE d.date = ?
    """, (today,))
    for r in cur.fetchall():
        if r["daily_verdict"] in DAILY_FUNDA_OK:
            c = _get(r["ticker"])
            c["sources"].append("daily_funda")
            c["current_price"] = r["current_price"]
            c["best_rr"]       = r["adjusted_rr"]
            c["tier"]          = r["tier"]
            c["sector"]        = r["sector"]
            c["direction"]     = r["direction"] or "LONG"
            c["verdicts"]["daily_funda"] = r["daily_verdict"]

    # ── 日次テクニカル ────────────────────────────────────────────────────────
    cur.execute("""
        SELECT d.ticker, d.current_price, d.adjusted_rr, d.daily_verdict,
               w.direction, w.confidence, w.stage
        FROM tech_daily_picks d
        LEFT JOIN tech_weekly_picks w ON w.ticker = d.ticker
        WHERE d.date = ?
    """, (today,))
    for r in cur.fetchall():
        if r["daily_verdict"] in DAILY_TECH_OK:
            c = _get(r["ticker"])
            c["sources"].append("daily_tech")
            if c["current_price"] is None:
                c["current_price"] = r["current_price"]
            if c["best_rr"] is None or (r["adjusted_rr"] or 0) > (c["best_rr"] or 0):
                c["best_rr"] = r["adjusted_rr"]
            if r["direction"]:
                c["direction"] = r["direction"]
            c["verdicts"]["daily_tech"] = r["daily_verdict"]

    # ── 週次ファンダ ──────────────────────────────────────────────────────────
    cur.execute("""
        SELECT ticker, entry_price, risk_reward, verdict, tier, sector, direction, composite_score
        FROM weekly_picks
    """)
    for r in cur.fetchall():
        c = _get(r["ticker"])
        c["sources"].append("weekly_funda")
        if c["current_price"] is None:
            c["current_price"] = r["entry_price"]
        if c["best_rr"] is None or (r["risk_reward"] or 0) > (c["best_rr"] or 0):
            c["best_rr"] = r["risk_reward"]
        if c["tier"] is None:
            c["tier"] = r["tier"]
        if c["sector"] is None:
            c["sector"] = r["sector"]
        c["direction"] = r["direction"] or "LONG"
        c["verdicts"]["weekly_funda"] = r["verdict"]

    # ── 週次テクニカル ────────────────────────────────────────────────────────
    cur.execute("""
        SELECT ticker, entry_price, risk_reward, direction, confidence, stage
        FROM tech_weekly_picks
        WHERE confidence >= ?
    """, (WEEKLY_TECH_MIN_CONFIDENCE,))
    for r in cur.fetchall():
        c = _get(r["ticker"])
        c["sources"].append("weekly_tech")
        if c["current_price"] is None:
            c["current_price"] = r["entry_price"]
        if c["best_rr"] is None or (r["risk_reward"] or 0) > (c["best_rr"] or 0):
            c["best_rr"] = r["risk_reward"]
        if r["direction"]:
            c["direction"] = r["direction"]
        conf_pct = round((r["confidence"] or 0) * 100)
        c["verdicts"]["weekly_tech"] = f"confidence {conf_pct}%"

    conn.close()

    # ソート: ソース数降順 → RR降順
    result = sorted(
        candidates.values(),
        key=lambda x: (-len(x["sources"]), -(x["best_rr"] or 0))
    )

    # source_count を追加
    for c in result:
        c["source_count"] = len(c["sources"])

    return result
