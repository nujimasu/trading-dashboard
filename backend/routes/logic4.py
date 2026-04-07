"""GET /api/logic4-picks — ロジック４（押し目買いスクリーニング）"""
import json
from fastapi import APIRouter
from backend.db import get_connection

router = APIRouter()

VERDICT_CSS = {
    "最優先候補":   "verdict-entry",
    "監視リスト入り": "verdict-buy",
    "見送り":       "verdict-passed",
}


@router.get("/api/logic4-picks")
def get_logic4_picks():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT ticker, scan_date, perfect_order, perf_3m, perf_6m, avg_vol_20d,
               dow_trend, support_price, confluence, support_reasons, reji_sapo,
               risk_reward, entry_price, stop_price, tp1_price, target_price,
               rsi, rsi_flag, macd_div_flag, fib_confluence, atr,
               verdict, confidence, composite_score, sector, current_price,
               holding_days_est, signals_json
        FROM logic4_picks
        ORDER BY
            CASE verdict
                WHEN '最優先候補'   THEN 0
                WHEN '監視リスト入り' THEN 1
                ELSE 2
            END,
            risk_reward DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    result = []
    for r in rows:
        reasons  = json.loads(r.get("support_reasons") or "[]")
        signals  = json.loads(r.get("signals_json") or "[]")
        confidence = r["confidence"] or 0
        verdict  = r["verdict"] or "監視リスト入り"

        # ボーナスフラグ集計
        bonus = []
        if r.get("rsi_flag"):      bonus.append(f"RSI {r['rsi']:.0f}（押し目ゾーン）")
        if r.get("macd_div_flag"): bonus.append("MACD強気ダイバージェンス")
        if r.get("fib_confluence"):bonus.append(f"Fib {r['fib_confluence']}")

        entry_reasons = reasons + bonus

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
            # picks-table 互換
            "verdict":         verdict,
            "daily_verdict":   verdict,
            "tier":            "Tier1" if verdict == "最優先候補" else "Tier2",
            "active_signals":  entry_reasons,
            "signals":         entry_reasons,
            "technical_summary": {
                "rsi":               r["rsi"],
                "macd_above_sig":    bool(r.get("macd_div_flag")),
                "pct_from_high":     None,
                "vcp_score":         None,
                "short_momentum":    None,
                "contraction_count": None,
                "volume_ratio":      (r["avg_vol_20d"] / 500_000) if r["avg_vol_20d"] else None,
                "stage2_uptrend":    r["perfect_order"] == "full",
                "entry_reasons":     entry_reasons,
                "risk_factors":      [
                    f"サポート: ${r['support_price']:.2f}（根拠{r['confluence']}つ）",
                    f"レジサポ転換: {r['reji_sapo']}",
                    f"3ヶ月騰落率: {r['perf_3m']:+.1f}%",
                ],
            },
            "fundamental_summary": {"available": False},
            "fundamental_verdict": "テクニカルのみ（押し目買いエンジン）",
        })
    return result
