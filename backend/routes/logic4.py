"""GET /api/logic4-picks — 厳選押し目買いv2"""
import json
from typing import Annotated
from fastapi import APIRouter, Query
from backend.db import get_connection

router = APIRouter()


@router.get("/api/logic4-picks")
def get_logic4_picks(
    include_watchlist: Annotated[bool, Query(description="Include lower-confidence support-watchlist names")] = False,
    limit: Annotated[int, Query(ge=1, le=200, description="Maximum number of picks to return")] = 50,
):
    conn = get_connection()
    cur  = conn.cursor()
    where = "" if include_watchlist else "WHERE verdict = '最優先候補'"
    cur.execute(f"""
        SELECT ticker, scan_date, perfect_order, perf_3m, perf_6m, avg_vol_20d,
               dow_trend, support_price, confluence, support_reasons, reji_sapo,
               risk_reward, entry_price, stop_price, tp1_price, target_price,
               rsi, rsi_flag, macd_div_flag, fib_confluence, atr,
               verdict, confidence, composite_score, sector, current_price,
               holding_days_est, signals_json, price_to_support_pct
        FROM logic4_picks
        {where}
        ORDER BY
            CASE verdict
                WHEN '最優先候補'         THEN 0
                WHEN 'サポート接近中'      THEN 1
                WHEN '地合いNG（休む推奨）' THEN 2
                ELSE 3
            END,
            confidence DESC,
            risk_reward DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    result = []
    for r in rows:
        reasons  = json.loads(r.get("support_reasons") or "[]")
        v3_rules = json.loads(r.get("signals_json") or "[]")
        confidence = r["confidence"] or 0
        verdict  = r["verdict"] or "サポート接近中"
        price_to_support_pct = r.get("price_to_support_pct")

        # 押し目要因（reasons）＋ v3 の運用ルール（地合い/引き金/SL/TP/保有上限）
        entry_reasons = reasons + v3_rules

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
            "support_price":   r["support_price"],
            "confluence":      r["confluence"],
            "reji_sapo":       r["reji_sapo"],
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
            "fib_confluence":  r["fib_confluence"],
            "sector":          r["sector"],
            "holding_days_est": r["holding_days_est"],
            "price_to_support_pct": price_to_support_pct,
            "verdict":         verdict,
            "daily_verdict":   verdict,
            "tier":            "Tier1" if verdict == "最優先候補" else "Tier2",
            "active_signals":  entry_reasons,
            "signals":         [],
            "technical_summary": {
                "rsi":               r["rsi"],
                "macd_above_sig":    bool(r.get("macd_div_flag")),
                "pct_from_high":     price_to_support_pct,
                "vcp_score":         None,
                "short_momentum":    None,
                "contraction_count": None,
                "volume_ratio":      (r["avg_vol_20d"] / 1_000_000) if r["avg_vol_20d"] else None,
                "stage2_uptrend":    r["perfect_order"] == "full",
                "entry_reasons":     entry_reasons,
                "risk_factors":      [
                    f"押し目EMA: ${r['support_price']:.2f}" if r["support_price"] else None,
                    f"EMAまでの乖離: {price_to_support_pct:+.1f}%" if price_to_support_pct is not None else None,
                    f"3ヶ月騰落率: {r['perf_3m']:+.1f}%" if r["perf_3m"] is not None else None,
                    f"想定保有: 最大{r['holding_days_est']}営業日（8日含み損なら全決済）",
                ],
            },
            "fundamental_summary": {"available": False},
            "fundamental_verdict": "テクニカルのみ（厳選押し目買いv2）",
        })

        result[-1]["technical_summary"]["risk_factors"] = [
            f for f in result[-1]["technical_summary"]["risk_factors"] if f is not None
        ]

    return result
