"""
GET /api/logic3-picks — ロジック３（signal-scanner-v5 エンジン移植版）

既存の price_data テーブルを使い、signal-scanner-v5 のエンジンで算出した
logic3_picks テーブルからデータを返す。

エンジン仕様:
  - 28 シグナル（EMA, RSI, BB, MACD, 一目, VCP, チャートパターン, ローソク足等）
  - バックテスト: ATR×2 SL / ATR×4 TP, 最低10サンプル
  - 信頼度スコア: 勝率60% + RR品質25% + 合流点10% + ステージ5% × サンプル補正
  - 採用条件: confidence≥0.70 + win_rate≥0.65 + RR≥2.0 + UP のみ
"""
import json
from fastapi import APIRouter
from backend.db import get_connection

router = APIRouter()


@router.get("/api/logic3-picks")
def get_logic3_picks():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT ticker, scan_date, stage, confidence, avg_win_rate,
               risk_reward, entry_price, stop_price, tp1_price, target_price,
               atr_pct, rsi, vol_ratio, current_price, signals_json,
               sector, holding_days_est
        FROM logic3_picks
        ORDER BY confidence DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    result = []
    for r in rows:
        signals = json.loads(r.get("signals_json") or "[]")
        confidence = r["confidence"] or 0

        # verdict
        if confidence >= 0.78:
            verdict = "STRONG_BUY"
        elif confidence >= 0.70:
            verdict = "BUY"
        else:
            verdict = "WATCH"

        result.append({
            "ticker":          r["ticker"],
            "scan_date":       r["scan_date"],
            "current_price":   r["current_price"],
            "direction":       "LONG",
            "stage":           r["stage"],
            "confidence":      confidence,
            "avg_win_rate":    r["avg_win_rate"],
            "composite_score": round(confidence * 100, 1),
            "risk_reward":     r["risk_reward"],
            "adjusted_rr":     r["risk_reward"],
            "entry_price":     r["entry_price"],
            "stop_price":      r["stop_price"],
            "tp1_price":       r["tp1_price"],
            "target_price":    r["target_price"],
            "atr_pct":         r["atr_pct"],
            "rsi":             r["rsi"],
            "vol_ratio":       r["vol_ratio"],
            "sector":          r["sector"],
            "holding_days_est": r["holding_days_est"],
            # picks-table / tech-picks-table 互換
            "verdict":         verdict,
            "daily_verdict":   verdict,
            "tier":            "Tier1" if confidence >= 0.75 else "Tier2",
            "active_signals":  signals,
            "signals":         signals,
            "technical_summary": {
                "rsi":               r["rsi"],
                "macd_above_sig":    None,
                "pct_from_high":     None,
                "vcp_score":         None,
                "short_momentum":    None,
                "contraction_count": None,
                "volume_ratio":      r["vol_ratio"],
                "stage2_uptrend":    r["stage"] == 2,
                "entry_reasons":     signals,
                "risk_factors":      [],
            },
            "fundamental_summary":  {"available": False},
            "fundamental_verdict":  "テクニカルのみ（28シグナルエンジン）",
        })
    return result
