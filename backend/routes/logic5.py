"""GET /api/logic5-picks — 押し目リバーサル"""
import json
from typing import Annotated

from fastapi import APIRouter, Query

from backend.db import get_connection

router = APIRouter()


@router.get("/api/logic5-picks")
def get_logic5_picks(
    include_watchlist: Annotated[bool, Query(description="条件待ちのウォッチも含める")] = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    conn = get_connection()
    cur  = conn.cursor()
    # 標準画面は実際に検討可能な構造RRだけを表示する。ウォッチ一覧では
    # RR範囲外も含め、どの条件が未達かを診断できるようにする。
    where = ("" if include_watchlist else
             "WHERE verdict IN ('最優先候補', 'クールダウン中') "
             "AND risk_reward BETWEEN 1.5 AND 2.0")
    cur.execute(f"""
        SELECT ticker, scan_date, sector, current_price, entry_price, stop_price,
               tp1_price, target_price, risk_reward, ema_label, ema_dist_pct,
               support_price, pa_count, osc_count, perf_3m, perf_6m, avg_vol_20d,
               rsi, atr, verdict, confidence, composite_score, holding_days_est,
               reasons_json, rules_json
        FROM logic5_picks
        {where}
        ORDER BY
            CASE verdict
                WHEN '最優先候補'         THEN 0
                WHEN 'クールダウン中'      THEN 1
                ELSE 2
            END,
            confidence DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    result = []
    for r in rows:
        reasons = json.loads(r.get("reasons_json") or "[]")
        rules   = json.loads(r.get("rules_json") or "[]")
        verdict = r["verdict"] or "ウォッチ（条件待ち）"

        result.append({
            "ticker":          r["ticker"],
            "scan_date":       r["scan_date"],
            "current_price":   r["current_price"],
            "direction":       "LONG",
            "sector":          r["sector"],
            "confidence":      r["confidence"] or 0,
            "composite_score": r["composite_score"],
            "risk_reward":     r["risk_reward"],
            "adjusted_rr":     r["risk_reward"],
            "entry_price":     r["entry_price"],
            "stop_price":      r["stop_price"],
            "tp1_price":       r["tp1_price"],
            "target_price":    r["target_price"],
            "support_price":   r["support_price"],
            "price_to_support_pct": r["ema_dist_pct"],
            "perf_3m":         r["perf_3m"],
            "perf_6m":         r["perf_6m"],
            "avg_vol_20d":     r["avg_vol_20d"],
            "rsi":             r["rsi"],
            "atr":             r["atr"],
            "perfect_order":   None,
            "confluence":      (r["pa_count"] or 0) + (r["osc_count"] or 0),
            "reji_sapo":       "none",
            "fib_confluence":  None,
            "holding_days_est": r["holding_days_est"],
            "verdict":         verdict,
            "daily_verdict":   verdict,
            "tier":            "Tier1" if verdict == "最優先候補" else "Tier2",
            "active_signals":  reasons + rules,
            "signals":         [],
            "technical_summary": {
                "rsi":               r["rsi"],
                "macd_above_sig":    None,
                "pct_from_high":     r["ema_dist_pct"],
                "vcp_score":         None,
                "short_momentum":    None,
                "contraction_count": None,
                "volume_ratio":      (r["avg_vol_20d"] / 1_000_000) if r["avg_vol_20d"] else None,
                "stage2_uptrend":    True,
                "entry_reasons":     reasons + rules,
                "risk_factors":      [
                    f"反転の証拠: プライスアクション {r['pa_count']}/7 ・ オシレーター {r['osc_count']}/3",
                    f"押し目EMA: ${r['support_price']:.2f}（{r['ema_label']}）" if r["support_price"] else None,
                    f"3ヶ月騰落率: {r['perf_3m']:+.1f}%" if r["perf_3m"] is not None else None,
                    f"想定保有: 最大{r['holding_days_est']}営業日（見直し期限30営業日）",
                ],
            },
            "fundamental_summary": {"available": False},
            "fundamental_verdict": "テクニカルのみ（押し目リバーサル）",
        })
        result[-1]["technical_summary"]["risk_factors"] = [
            f for f in result[-1]["technical_summary"]["risk_factors"] if f is not None
        ]

    return result
