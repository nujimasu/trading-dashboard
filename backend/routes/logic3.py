"""
GET /api/logic3-picks — ロジック３（signal-scanner-v5 エンジン）

signal-scanner-v5 の Supabase scan_results テーブルからデータを取得し、
trading-dashboard の picks フォーマットに変換して返す。

エンジン仕様（signal-scanner-v5）:
  - 28シグナル（14 UP / 14 DOWN）: EMA, RSI, BB, MACD, 一目, VCP, チャートパターン等
  - バックテスト: ATR×2 SL / ATR×4 TP, 最低サンプル10件
  - スコア: 勝率60% + RR25% + 合流点10% + ステージ5% × サンプル補正
  - 採用閾値: CONFIDENCE >= 0.70, WIN_RATE >= 0.65, RR >= 2.0, netDir = UP のみ
"""
import os
import requests
from fastapi import APIRouter

router = APIRouter()

# ── Supabase 接続設定（signal-scanner-v5 専用） ─────────────────────────────
SCANNER_SUPABASE_URL = os.environ.get(
    "SCANNER_SUPABASE_URL",
    "https://aqzdvlwzieegnanrlplj.supabase.co"
)
SCANNER_SUPABASE_KEY = os.environ.get(
    "SCANNER_SUPABASE_KEY",
    # service_role key — server-side read only
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFxemR2bHd6aWVlZ25hbnJscGxqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDQ3MTIwNSwiZXhwIjoyMDkwMDQ3MjA1fQ.GEHltKnzFv_rlqwkNIGfLXhO3zfSk081wM45xW7h1GA"
)

# ── 定数 ────────────────────────────────────────────────────────────────────
CONFIDENCE_MIN = 0.70
RR_MIN         = 2.0

VERDICT_MAP = {
    "STRONG_BUY": "今日エントリー★",
    "BUY":        "エントリー",
    "WATCH":      "様子見",
}


def _holding_days(entry, target, atr_pct):
    if not entry or not target or not atr_pct:
        return 20
    atr = entry * atr_pct / 100
    if atr <= 0:
        return 20
    return max(3, round(abs(target - entry) / (atr * 0.5)))


def _map_row(sym: str, result: dict, scanned_at: str) -> dict | None:
    """scan_results.result JSON → picks フォーマット に変換"""
    net_dir    = result.get("netDir", "NEUTRAL")
    confidence = result.get("confidence", 0)
    rr_result  = result.get("rrResult") or {}
    rr         = rr_result.get("rr", 0)

    # ロジック３は UP のみ
    if net_dir != "UP":
        return None
    if confidence < CONFIDENCE_MIN:
        return None
    if rr < RR_MIN:
        return None

    entry    = rr_result.get("entry")
    stop     = rr_result.get("stop")
    target   = rr_result.get("target")
    atr_pct  = result.get("atrPct")
    stage    = result.get("stage", 0)
    hits     = result.get("hits", [])
    sector   = result.get("sector", "—")
    rsi_now  = result.get("rsiNow")
    close    = result.get("close")
    avg_wr   = result.get("avgWR", 0)
    vol_ratio = result.get("volRatio", 1)

    # シグナル名リスト（上位5件）
    signal_names = [h.get("name", h.get("id", "")) for h in hits[:5]]

    # 確信度からverdictを決定
    if confidence >= 0.78:
        verdict = "STRONG_BUY"
    elif confidence >= 0.70:
        verdict = "BUY"
    else:
        verdict = "WATCH"

    return {
        "ticker":          sym,
        "current_price":   close,
        "direction":       "LONG",
        "stage":           stage,
        "confidence":      confidence,
        "avg_win_rate":    avg_wr,
        "composite_score": round(confidence * 100, 1),
        "risk_reward":     rr,
        "adjusted_rr":     rr,
        "entry_price":     entry,
        "stop_price":      stop,
        "tp1_price":       round(entry + (entry - stop) * 1.5, 2) if entry and stop else None,
        "target_price":    target,
        "atr_pct":         atr_pct,
        "rsi":             rsi_now,
        "sector":          sector,
        "scanned_at":      scanned_at,
        "vol_ratio":       vol_ratio,
        # picks-table / tech-picks-table 互換フィールド
        "verdict":         verdict,
        "daily_verdict":   verdict,
        "verdict_label":   VERDICT_MAP.get(verdict, verdict),
        "tier":            "Tier1" if confidence >= 0.75 else "Tier2",
        "holding_days_est": _holding_days(entry, target, atr_pct),
        "active_signals":  signal_names,
        "signals":         signal_names,
        "technical_summary": {
            "rsi":               rsi_now,
            "macd_above_sig":    None,
            "pct_from_high":     None,
            "vcp_score":         None,
            "short_momentum":    None,
            "contraction_count": None,
            "volume_ratio":      vol_ratio,
            "stage2_uptrend":    stage == 2,
            "entry_reasons":     signal_names,
            "risk_factors":      [],
        },
        "fundamental_summary": {"available": False},
        "fundamental_verdict": "テクニカルのみ（v5エンジン）",
    }


@router.get("/api/logic3-picks")
def get_logic3_picks():
    """signal-scanner-v5 Supabase から scan_results を取得して返す"""
    if not SCANNER_SUPABASE_KEY:
        return []

    try:
        url = f"{SCANNER_SUPABASE_URL}/rest/v1/scan_results"
        headers = {
            "apikey":        SCANNER_SUPABASE_KEY,
            "Authorization": f"Bearer {SCANNER_SUPABASE_KEY}",
        }
        params = {
            "select":  "sym,result,scanned_at",
            "order":   "scanned_at.desc",
            "limit":   "500",
        }
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        rows = resp.json()
    except Exception as e:
        print(f"[Logic3] Supabase fetch error: {e}")
        return []

    picks = []
    for row in rows:
        sym        = row.get("sym", "")
        result     = row.get("result") or {}
        scanned_at = row.get("scanned_at", "")
        mapped = _map_row(sym, result, scanned_at)
        if mapped:
            picks.append(mapped)

    # confidence 降順
    picks.sort(key=lambda x: -(x["confidence"] or 0))
    return picks
