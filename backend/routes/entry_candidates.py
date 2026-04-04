"""GET /api/entry-candidates — 全4ソース（ハイブリッド+テクニカル）のエントリー候補を統合"""
import json
from datetime import date
from fastapi import APIRouter
from backend.db import get_connection

router = APIRouter()

# エントリー対象とする verdict
DAILY_FUNDA_OK  = {"ENTRY_NOW", "WATCH"}
DAILY_TECH_OK   = {"STRONG_BUY", "STRONG_SELL", "BUY", "SELL", "WATCH"}
WEEKLY_TECH_MIN_CONFIDENCE = 0.55  # 55% 以上


@router.get("/api/entry-candidates")
def get_entry_candidates():
    today = date.today().isoformat()
    conn  = get_connection()
    cur   = conn.cursor()
    candidates: dict[str, dict] = {}

    def _get(ticker: str) -> dict:
        if ticker not in candidates:
            candidates[ticker] = {
                "ticker":             ticker,
                "sources":            [],
                "direction":          "LONG",
                "current_price":      None,
                "best_rr":            None,
                "tier":               None,
                "sector":             None,
                "verdicts":           {},
                "composite_score":    None,  # weekly_picks 0-100
                "confidence":         None,  # tech_weekly 0-1
                "unified_score":      None,  # 0-100 統合スコア
                # 詳細パネル用
                "entry_price":        None,
                "stop_price":         None,
                "tp1_price":          None,
                "target_price":       None,
                "holding_days_est":   None,
                "technical_summary":  None,
                "fundamental_summary": None,
                "fundamental_verdict": None,
            }
        return candidates[ticker]

    # ── 日次ファンダ ──────────────────────────────────────────────────────────
    cur.execute("""
        SELECT d.ticker, d.current_price, d.adjusted_rr, d.daily_verdict,
               w.tier, w.sector, w.direction, w.composite_score,
               w.entry_price, w.stop_price, w.tp1_price, w.target_price,
               w.holding_days_est, w.technical_summary, w.fundamental_summary,
               w.fundamental_verdict
        FROM daily_picks d
        LEFT JOIN weekly_picks w ON w.ticker = d.ticker
        WHERE d.date = ?
    """, (today,))
    for r in cur.fetchall():
        if r["daily_verdict"] in DAILY_FUNDA_OK:
            c = _get(r["ticker"])
            c["sources"].append("daily_hybrid")
            c["current_price"]      = r["current_price"]
            c["best_rr"]            = r["adjusted_rr"]
            c["tier"]               = r["tier"]
            c["sector"]             = r["sector"]
            c["direction"]          = r["direction"] or "LONG"
            c["verdicts"]["daily_hybrid"] = r["daily_verdict"]
            if r["composite_score"] is not None:
                c["composite_score"] = r["composite_score"]
            # 詳細データ
            if r["entry_price"]:  c["entry_price"]       = r["entry_price"]
            if r["stop_price"]:   c["stop_price"]        = r["stop_price"]
            if r["tp1_price"]:    c["tp1_price"]         = r["tp1_price"]
            if r["target_price"]: c["target_price"]      = r["target_price"]
            if r["holding_days_est"]: c["holding_days_est"] = r["holding_days_est"]
            if r["technical_summary"]:
                try:
                    c["technical_summary"] = json.loads(r["technical_summary"])
                except Exception:
                    pass
            if r["fundamental_summary"]:
                try:
                    c["fundamental_summary"] = json.loads(r["fundamental_summary"])
                except Exception:
                    pass
            if r["fundamental_verdict"]: c["fundamental_verdict"] = r["fundamental_verdict"]

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
            if r["confidence"] is not None:
                conf_pct = round((r["confidence"] or 0) * 100)
                if c["confidence"] is None or conf_pct > (c["confidence"] or 0):
                    c["confidence"] = conf_pct

    # ── 週次ファンダ ──────────────────────────────────────────────────────────
    cur.execute("""
        SELECT ticker, entry_price, stop_price, tp1_price, target_price,
               risk_reward, verdict, tier, sector, direction, composite_score,
               holding_days_est, technical_summary, fundamental_summary,
               fundamental_verdict
        FROM weekly_picks
    """)
    for r in cur.fetchall():
        c = _get(r["ticker"])
        c["sources"].append("weekly_hybrid")
        if c["current_price"] is None:
            c["current_price"] = r["entry_price"]
        if c["best_rr"] is None or (r["risk_reward"] or 0) > (c["best_rr"] or 0):
            c["best_rr"] = r["risk_reward"]
        if c["tier"] is None:    c["tier"]    = r["tier"]
        if c["sector"] is None:  c["sector"]  = r["sector"]
        c["direction"] = r["direction"] or "LONG"
        c["verdicts"]["weekly_hybrid"] = r["verdict"]
        if r["composite_score"] is not None:
            if c["composite_score"] is None or r["composite_score"] > c["composite_score"]:
                c["composite_score"] = r["composite_score"]
        # 詳細データ（週次が最も充実）
        if r["entry_price"]:  c["entry_price"]  = r["entry_price"]
        if r["stop_price"]:   c["stop_price"]   = r["stop_price"]
        if r["tp1_price"]:    c["tp1_price"]    = r["tp1_price"]
        if r["target_price"]: c["target_price"] = r["target_price"]
        if r["holding_days_est"]: c["holding_days_est"] = r["holding_days_est"]
        if r["technical_summary"] and c["technical_summary"] is None:
            try:
                c["technical_summary"] = json.loads(r["technical_summary"])
            except Exception:
                pass
        if r["fundamental_summary"] and c["fundamental_summary"] is None:
            try:
                c["fundamental_summary"] = json.loads(r["fundamental_summary"])
            except Exception:
                pass
        if r["fundamental_verdict"]: c["fundamental_verdict"] = r["fundamental_verdict"]

    # ── 週次テクニカル ────────────────────────────────────────────────────────
    cur.execute("""
        SELECT ticker, entry_price, stop_price, tp1_price, target_price,
               risk_reward, direction, confidence, stage
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
        c["verdicts"]["weekly_tech"] = f"信頼度 {conf_pct}%"
        if c["confidence"] is None or conf_pct > (c["confidence"] or 0):
            c["confidence"] = conf_pct
        # 詳細データ（週次テクニカル）
        if r["entry_price"] and c["entry_price"] is None:  c["entry_price"]  = r["entry_price"]
        if r["stop_price"]  and c["stop_price"]  is None:  c["stop_price"]   = r["stop_price"]
        if r["tp1_price"]   and c["tp1_price"]   is None:  c["tp1_price"]    = r["tp1_price"]
        if r["target_price"] and c["target_price"] is None: c["target_price"] = r["target_price"]

    conn.close()

    # ── 統合スコア算出 ────────────────────────────────────────────────────────
    for c in candidates.values():
        scores = []
        if c["composite_score"] is not None:
            scores.append(c["composite_score"])
        if c["confidence"] is not None:
            scores.append(c["confidence"])  # already 0-100
        # どちらもなければ RR * 20 でフォールバック
        if not scores and c["best_rr"] is not None:
            scores.append(min(c["best_rr"] * 20, 100))
        c["unified_score"] = round(max(scores)) if scores else 0
        c["source_count"]  = len(c["sources"])

    # ソート: 統合スコア降順 → ソース数降順 → RR降順
    result = sorted(
        candidates.values(),
        key=lambda x: (-x["unified_score"], -x["source_count"], -(x["best_rr"] or 0))
    )

    return result
