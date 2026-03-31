"""GET /api/tech-daily-picks — テクニカル日次ピック"""
import json
from datetime import date
from fastapi import APIRouter
from backend.db import get_connection

router = APIRouter()

VERDICT_LABEL = {
    "STRONG_BUY":  "今日エントリー★",
    "STRONG_SELL": "今日ショート★",
    "BUY":         "エントリー",
    "SELL":        "ショートエントリー",
    "WATCH":       "様子見",
    "WAIT":        "待機",
    "PASSED":      "通過済",
}
VERDICT_CSS = {
    "STRONG_BUY":  "verdict-entry",
    "STRONG_SELL": "verdict-short",
    "BUY":         "verdict-buy",
    "SELL":        "verdict-short-watch",
    "WATCH":       "verdict-watch",
    "WAIT":        "verdict-wait",
    "PASSED":      "verdict-passed",
}


@router.get("/api/tech-daily-picks")
def get_tech_daily_picks():
    today = date.today().isoformat()
    conn  = get_connection()
    cur   = conn.cursor()

    cur.execute("""
        SELECT
            d.ticker, d.date, d.current_price, d.adjusted_rr,
            d.daily_verdict, d.active_signals_json,
            w.direction, w.stage, w.confidence, w.avg_win_rate,
            w.risk_reward AS weekly_rr,
            w.entry_price, w.stop_price, w.tp1_price, w.target_price,
            w.atr_pct, w.rsi, w.signals_json
        FROM tech_daily_picks d
        LEFT JOIN tech_weekly_picks w ON w.ticker = d.ticker
        WHERE d.date = ?
        ORDER BY
            CASE d.daily_verdict
                WHEN 'STRONG_BUY'  THEN 0
                WHEN 'STRONG_SELL' THEN 1
                WHEN 'BUY'         THEN 2
                WHEN 'SELL'        THEN 3
                WHEN 'WATCH'       THEN 4
                WHEN 'WAIT'        THEN 5
                ELSE 6
            END,
            w.confidence DESC
    """, (today,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    result = []
    for r in rows:
        verdict   = r["daily_verdict"] or "WAIT"
        active    = json.loads(r["active_signals_json"] or "[]")
        all_sigs  = json.loads(r["signals_json"] or "[]")
        result.append({
            "ticker":          r["ticker"],
            "date":            r["date"],
            "current_price":   r["current_price"],
            "adjusted_rr":     r["adjusted_rr"],
            "daily_verdict":   verdict,
            "verdict_label":   VERDICT_LABEL.get(verdict, verdict),
            "verdict_css":     VERDICT_CSS.get(verdict, ""),
            "active_signals":  active,
            "direction":       r["direction"] or "LONG",
            "stage":           r["stage"] or 0,
            "confidence":      r["confidence"],
            "avg_win_rate":    r["avg_win_rate"],
            "weekly_rr":       r["weekly_rr"],
            "entry_price":     r["entry_price"],
            "stop_price":      r["stop_price"],
            "tp1_price":       r["tp1_price"],
            "target_price":    r["target_price"],
            "atr_pct":         r["atr_pct"],
            "rsi":             r["rsi"],
            "signals":         all_sigs,
            # picks-table 互換
            "verdict":         verdict,
            "tier":            "Tier1" if (r["confidence"] or 0) >= 0.72 else "Tier2",
            "composite_score": round((r["confidence"] or 0) * 100, 1),
            "sector":          None,
            "risk_reward":     r["adjusted_rr"],
            "holding_days_est": None,
            "fundamental_verdict": "テクニカルのみ",
            "technical_summary": {
                "rsi":           r["rsi"],
                "entry_reasons": active,
                "risk_factors":  [],
                "vcp_score":     None,
                "short_momentum": None,
                "macd_above_sig": None,
                "pct_from_high": None,
                "contraction_count": None,
                "volume_ratio":  None,
                "stage2_uptrend": (r["stage"] or 0) == 2,
            },
            "fundamental_summary": {"available": False},
        })
    return result
