"""GET /api/logic3-picks — ロジック３（ブレイクアウト・モメンタム）"""
import json
from fastapi import APIRouter
from backend.db import get_connection

router = APIRouter()


@router.get("/api/logic3-picks")
def get_logic3_picks():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT ticker, scan_date, perfect_order, perf_3m, perf_6m, avg_vol_20d,
               dow_trend, base_pattern, base_length, base_depth_pct,
               pivot_price, breakout_confirmed, breakout_volume_ratio,
               distance_from_pivot_pct, risk_reward, entry_price, stop_price,
               tp1_price, target_price, rsi, atr,
               verdict, confidence, composite_score, sector, current_price,
               holding_days_est, signals_json
        FROM logic3_picks
        ORDER BY
            CASE verdict
                WHEN '最優先候補'       THEN 0
                WHEN 'ブレイクアウト接近' THEN 1
                ELSE 2
            END,
            confidence DESC,
            risk_reward DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    result = []
    for r in rows:
        confidence = r["confidence"] or 0
        verdict    = r["verdict"] or "ブレイクアウト接近"
        base_pat   = r.get("base_pattern") or ""
        vol_ratio  = r.get("breakout_volume_ratio") or 0
        dist       = r.get("distance_from_pivot_pct")

        entry_reasons = [base_pat]
        if r.get("breakout_confirmed"):
            entry_reasons.append(f"出来高{vol_ratio:.1f}倍")
        if dist is not None and dist > 0:
            entry_reasons.append(f"ピボット+{dist:.1f}%")
        elif dist is not None and dist < 0:
            entry_reasons.append(f"ピボットまで{abs(dist):.1f}%")

        result.append({
            "ticker":          r["ticker"],
            "scan_date":       r["scan_date"],
            "current_price":   r["current_price"],
            "direction":       "LONG",
            "perfect_order":   r["perfect_order"],
            "perf_3m":         r["perf_3m"],
            "perf_6m":         r["perf_6m"],
            "avg_vol_20d":     r["avg_vol_20d"],
            "dow_trend":       r["dow_trend"],
            "base_pattern":    base_pat,
            "base_length":     r.get("base_length"),
            "base_depth_pct":  r.get("base_depth_pct"),
            "pivot_price":     r.get("pivot_price"),
            "breakout_confirmed": bool(r.get("breakout_confirmed")),
            "breakout_volume_ratio": vol_ratio,
            "distance_from_pivot_pct": dist,
            "confidence":      confidence,
            "composite_score": round(confidence * 100, 1),
            "risk_reward":     r["risk_reward"],
            "adjusted_rr":     r["risk_reward"],
            "entry_price":     r["entry_price"],
            "stop_price":      r["stop_price"],
            "tp1_price":       r["tp1_price"],
            "target_price":    r["target_price"],
            "rsi":             r["rsi"],
            "atr":             r["atr"],
            "sector":          r["sector"],
            "holding_days_est": r["holding_days_est"],
            "verdict":         verdict,
            "daily_verdict":   verdict,
            "tier":            "Tier1" if verdict == "最優先候補" else "Tier2",
            "active_signals":  entry_reasons,
            "signals":         [],
            "technical_summary": {
                "rsi":               r["rsi"],
                "macd_above_sig":    None,
                "pct_from_high":     dist,
                "volume_ratio":      vol_ratio,
                "stage2_uptrend":    r["perfect_order"] == "full",
                "entry_reasons":     entry_reasons,
                "risk_factors":      [
                    f"ベースパターン: {base_pat}",
                    f"ピボット: ${r.get('pivot_price', 0):.2f}",
                    f"ベース深さ: {r.get('base_depth_pct', 0):.1f}%",
                    f"出来高倍率: {vol_ratio:.1f}x" if vol_ratio > 0 else "出来高: 未確認",
                ],
            },
            "fundamental_summary": {"available": False},
            "fundamental_verdict": "テクニカルのみ（ブレイクアウト・モメンタム）",
        })
    return result
