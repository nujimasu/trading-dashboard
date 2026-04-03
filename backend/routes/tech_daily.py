"""GET /api/tech-daily-picks — テクニカル日次ピック"""
import json
from datetime import date, datetime, timezone, timedelta
from fastapi import APIRouter
from backend.db import get_connection


def _calc_holding_days(entry, target, atr_pct):
    if not entry or not target or not atr_pct:
        return 20
    atr = entry * atr_pct / 100
    if atr <= 0:
        return 20
    return max(3, round(abs(target - entry) / (atr * 0.5)))

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


def _get_jst_date():
    """Get today's date in JST (Asia/Tokyo)"""
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).date().isoformat()


@router.get("/api/tech-daily-picks")
def get_tech_daily_picks():
    today = _get_jst_date()
    conn  = get_connection()
    cur   = conn.cursor()

    # 当日データを優先、なければ最新日のデータを返す
    cur.execute("""
        SELECT MAX(date) as latest_date FROM tech_daily_picks
        WHERE date <= ?
    """, (today,))
    result = cur.fetchone()
    query_date = result["latest_date"] if result and result["latest_date"] else today

    cur.execute("""
        SELECT
            d.ticker, d.date, d.current_price, d.adjusted_rr,
            d.daily_verdict, d.active_signals_json, d.stage_b_signals_json,
            w.direction, w.stage, w.confidence, w.avg_win_rate,
            w.risk_reward AS weekly_rr,
            w.entry_price, w.stop_price, w.tp1_price, w.target_price,
            w.atr_pct, w.rsi, w.signals_json,
            fp.sector
        FROM tech_daily_picks d
        LEFT JOIN tech_weekly_picks w ON w.ticker = d.ticker
        LEFT JOIN weekly_picks fp ON fp.ticker = d.ticker
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
    """, (query_date,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    result = []
    for r in rows:
        verdict   = r["daily_verdict"] or "WAIT"
        active    = json.loads(r["active_signals_json"] or "[]")
        stage_b   = json.loads(r.get("stage_b_signals_json") or "[]")
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
            "stage_b_signals": stage_b,
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
            "sector":          r.get("sector"),
            "risk_reward":     r["adjusted_rr"],
            "holding_days_est": _calc_holding_days(
                r.get("entry_price"), r.get("target_price"), r.get("atr_pct")
            ),
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
