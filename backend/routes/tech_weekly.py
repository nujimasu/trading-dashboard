"""GET /api/tech-weekly-picks — テクニカル週次ピック"""
import json
from fastapi import APIRouter
from backend.db import get_connection

router = APIRouter()

STAGE_LABEL = {0: "ステージ不明", 1: "ステージ1 ベース形成",
               2: "ステージ2 上昇トレンド", 3: "ステージ3 天井圏",
               4: "ステージ4 下降トレンド"}


def _fmt(p: dict) -> dict:
    signals = json.loads(p["signals_json"] or "[]")
    return {
        "ticker":        p["ticker"],
        "direction":     p["direction"] or "LONG",
        "stage":         p["stage"] or 0,
        "stage_label":   STAGE_LABEL.get(p["stage"] or 0, ""),
        "confidence":    p["confidence"],
        "avg_win_rate":  p["avg_win_rate"],
        "risk_reward":   p["risk_reward"],
        "entry_price":   p["entry_price"],
        "stop_price":    p["stop_price"],
        "tp1_price":     p["tp1_price"],
        "target_price":  p["target_price"],
        "atr_pct":       p["atr_pct"],
        "rsi":           p["rsi"],
        "signals":       signals,
        "scan_date":     p["scan_date"],
        "week_of":       p["week_of"],
        # picks-table.js との互換フィールド
        "verdict":       "BUY" if p["direction"] == "LONG" else "SHORT_SELL",
        "tier":          "Tier1" if (p["confidence"] or 0) >= 0.72 else "Tier2",
        "composite_score": round((p["confidence"] or 0) * 100, 1),
        "sector":        p.get("sector"),
        "holding_days_est": None,
        "fundamental_verdict": "テクニカルのみ",
        "technical_summary": {
            "rsi":            p["rsi"],
            "entry_reasons":  [s["label"] for s in signals],
            "risk_factors":   [],
            "vcp_score":      None,
            "short_momentum": None,
            "macd_above_sig": None,
            "pct_from_high":  None,
            "contraction_count": None,
            "volume_ratio":   None,
            "stage2_uptrend": (p["stage"] or 0) == 2,
        },
        "fundamental_summary": {"available": False},
    }


@router.get("/api/tech-weekly-picks")
def get_tech_weekly_picks():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT t.*, wp.sector
        FROM tech_weekly_picks t
        LEFT JOIN weekly_picks wp ON wp.ticker = t.ticker
        ORDER BY
            CASE t.direction WHEN 'LONG' THEN 0 ELSE 1 END,
            t.confidence DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return [_fmt(r) for r in rows]
