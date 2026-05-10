from __future__ import annotations
"""
Stage 6: Composite scoring and weekly_picks generation.
Combines technical + fundamental signals into a final ranked list.
"""
import sys
import json
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import THEME_MAP, SECTOR_DISPLAY, HEALTH_BULLISH_THRESHOLD, HEALTH_BEARISH_THRESHOLD
from backend.db import db_cursor, get_connection


def get_themes(ticker: str) -> list[str]:
    """Return which themes a ticker belongs to."""
    themes = [theme for theme, members in THEME_MAP.items() if ticker in members]
    return themes


def compute_composite_score(tech_score: float, rr: float, vcp_score: float, fundamentals: dict | None = None) -> float:
    """
    Hybrid composite score (0-100) — 50% Technical + 50% Fundamental.

    Technical (50 pts):
      - Trend & Momentum (25): tech_score 1-10 → 0-25
      - Pattern Quality  (15): vcp_score 0-100 → 0-15
      - RR Quality       (10): rr capped at 3.0 → 0-10

    Fundamental (50 pts):
      - Earnings Quality     (20): EPS growth + revenue growth
      - Valuation Health     (15): PE ratio reasonableness
      - Growth Sustainability(15): earnings surprise + ROE
    """
    # === TECHNICAL (0-50) ===
    trend_momentum  = (tech_score / 10) * 25
    pattern_quality = (vcp_score / 100) * 15
    rr_quality      = min(rr / 3.0, 1.0) * 10
    tech_total = trend_momentum + pattern_quality + rr_quality

    # === FUNDAMENTAL (0-50) ===
    if fundamentals:
        # Earnings Quality (0-20): EPS growth 0-50%→12pts + Revenue growth 0-30%→8pts
        eps_g = fundamentals.get("eps_growth_yoy") or 0
        rev_g = fundamentals.get("revenue_growth_yoy") or 0
        eps_pts = min(max(eps_g, 0) / 50, 1.0) * 12
        rev_pts = min(max(rev_g, 0) / 30, 1.0) * 8
        earnings_quality = eps_pts + rev_pts

        # Valuation Health (0-15): PE ratio scoring
        pe = fundamentals.get("pe_ratio")
        if pe is not None and pe > 0:
            if pe <= 15:
                val_pts = 15.0
            elif pe <= 25:
                val_pts = 15.0 - ((pe - 15) / 10) * 5
            elif pe <= 40:
                val_pts = 10.0 - ((pe - 25) / 15) * 7
            else:
                val_pts = max(3.0 - ((pe - 40) / 20) * 3, 0)
        else:
            val_pts = 7.5  # neutral when data unavailable

        # Growth Sustainability (0-15): Earnings surprise 0-15%→8pts + ROE 0-30%→7pts
        surprise = fundamentals.get("earnings_surprise_pct") or 0
        roe = fundamentals.get("roe") or 0
        surprise_pts = min(max(surprise, 0) / 15, 1.0) * 8
        roe_pts = min(max(roe, 0) / 30, 1.0) * 7
        sustainability = surprise_pts + roe_pts

        funda_total = earnings_quality + val_pts + sustainability
    else:
        funda_total = 25.0  # neutral default

    total = tech_total + funda_total
    return round(min(total, 100.0), 1)


def compute_fundamental_verdict(f: dict | None) -> str:
    """Standalone fundamental judgment (reference only, does not affect composite score)."""
    if not f:
        return "データなし"
    eps_g    = f.get("eps_growth_yoy")    or 0
    surprise = f.get("earnings_surprise_pct") or 0
    rev_g    = f.get("revenue_growth_yoy") or 0

    score = 0
    # EPS growth
    if eps_g > 20:   score += 2
    elif eps_g > 0:  score += 1
    elif eps_g < -10: score -= 2
    elif eps_g < 0:  score -= 1
    # Earnings surprise
    if surprise > 5:   score += 2
    elif surprise > 0: score += 1
    elif surprise < -5: score -= 2
    elif surprise < 0: score -= 1
    # Revenue growth
    if rev_g > 10:  score += 1
    elif rev_g < 0: score -= 1

    if score >= 4:   return "強気"
    elif score >= 2: return "やや強気"
    elif score >= 0: return "中立"
    elif score >= -2: return "やや弱気"
    else:            return "弱気"


def compute_take_profit_signals(f: dict | None, ts: dict | None) -> dict:
    """Detect fundamental overvaluation / take-profit signals."""
    signals = []
    severity = 0

    if f:
        pe = f.get("pe_ratio")
        if pe is not None and pe > 30:
            signals.append(f"PE過熱({pe:.1f})")
            severity += 1 if pe <= 40 else 2

        eps_g = f.get("eps_growth_yoy") or 0
        if eps_g < 0:
            signals.append(f"EPS成長鈍化({eps_g:.1f}%)")
            severity += 1 if eps_g > -10 else 2

        rev_g = f.get("revenue_growth_yoy") or 0
        if rev_g < 0:
            signals.append(f"売上成長停滞({rev_g:.1f}%)")
            severity += 1

    if ts:
        rsi = ts.get("rsi")
        if rsi is not None and rsi > 75:
            signals.append(f"RSI過熱({rsi:.1f})")
            severity += 1

    if severity >= 3:
        verdict = "TAKE_PROFIT"
    elif severity >= 2:
        verdict = "REDUCE"
    elif severity >= 1:
        verdict = "WATCH_EXIT"
    else:
        verdict = "HOLD"

    return {"verdict": verdict, "signals": signals, "severity": severity}


def build_technical_summary(da: dict, ts: dict) -> dict:
    """Build a human-readable technical summary JSON."""
    direction = da.get("direction", "LONG")
    return {
        "rsi":               ts.get("rsi"),
        "macd_above_sig":    (ts.get("macd", 0) or 0) > (ts.get("macd_signal", 0) or 0),
        "pct_from_high":     ts.get("pct_from_high"),
        "vcp_score":         da.get("vcp_score"),          # VCP for longs, short momentum for shorts
        "short_momentum":    da.get("vcp_score") if direction == "SHORT" else None,
        "contraction_count": da.get("contraction_count"),
        "volume_ratio":      ts.get("volume_ratio"),
        "stage2_uptrend":    bool(ts.get("stage2_uptrend")),
        "entry_reasons":     json.loads(da.get("entry_reasons") or "[]"),
        "risk_factors":      json.loads(da.get("risk_factors") or "[]"),
    }


def build_fundamental_summary(f: dict | None) -> dict:
    if not f:
        return {"available": False}
    return {
        "available":             True,
        "sector":                f.get("sector", ""),
        "industry":              f.get("industry", ""),
        "market_cap_b":          round((f.get("market_cap") or 0) / 1e9, 1),
        "pe_ratio":              f.get("pe_ratio"),
        "eps_growth_yoy":        f.get("eps_growth_yoy"),
        "revenue_growth_yoy":    f.get("revenue_growth_yoy"),
        "earnings_surprise_pct": f.get("earnings_surprise_pct"),
        "description":           (f.get("description") or "")[:400],
    }


def compute_market_health(conn, today: str):
    """Compute sector + theme health scores and update market_health table."""
    # Count universe tickers with price data
    cur = conn.cursor()
    cur.execute("SELECT COUNT(DISTINCT ticker) as cnt FROM price_data")
    total_screened = cur.fetchone()["cnt"]

    # Stage 2 uptrend count from today's technical screen
    cur.execute("""
        SELECT COUNT(*) as cnt FROM technical_screen
        WHERE scan_date = ? AND stage2_uptrend = 1
    """, (today,))
    stage2_count = cur.fetchone()["cnt"]

    overall_score  = round((stage2_count / total_screened * 100), 1) if total_screened > 0 else 0
    if overall_score >= HEALTH_BULLISH_THRESHOLD:
        signal = "Bullish"
    elif overall_score >= HEALTH_BEARISH_THRESHOLD:
        signal = "Neutral"
    else:
        signal = "Bearish"

    # Sector scores from universe + technical_screen join
    cur.execute("""
        SELECT u.sector, COUNT(*) as total,
               SUM(CASE WHEN ts.stage2_uptrend = 1 THEN 1 ELSE 0 END) as bullish
        FROM universe u
        LEFT JOIN technical_screen ts
            ON ts.ticker = u.ticker AND ts.scan_date = ?
        WHERE u.sector != '' AND u.sector IS NOT NULL
        GROUP BY u.sector
    """, (today,))
    sector_scores = {}
    for row in cur.fetchall():
        sector  = row["sector"]
        total   = row["total"]
        bullish = row["bullish"] or 0
        if total > 0:
            display = SECTOR_DISPLAY.get(sector, sector)
            sector_scores[display] = round(bullish / total * 100, 1)

    # Theme scores from THEME_MAP
    theme_scores = {}
    for theme, members in THEME_MAP.items():
        if not members:
            continue
        placeholders = ",".join("?" * len(members))
        cur.execute(f"""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN stage2_uptrend = 1 THEN 1 ELSE 0 END) as bullish
            FROM technical_screen
            WHERE scan_date = ? AND ticker IN ({placeholders})
        """, (today, *members))
        row = cur.fetchone()
        total   = row["total"] or 0
        bullish = row["bullish"] or 0
        if total > 0:
            theme_scores[theme] = round(bullish / total * 100, 1)

    cur.execute("""
        INSERT INTO market_health
            (date, overall_score, overall_signal, sector_scores, theme_scores, total_screened, stage2_count)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (date) DO UPDATE SET
            overall_score=EXCLUDED.overall_score, overall_signal=EXCLUDED.overall_signal,
            sector_scores=EXCLUDED.sector_scores, theme_scores=EXCLUDED.theme_scores,
            total_screened=EXCLUDED.total_screened, stage2_count=EXCLUDED.stage2_count
    """, (today, overall_score, signal,
          json.dumps(sector_scores, ensure_ascii=False),
          json.dumps(theme_scores,  ensure_ascii=False),
          total_screened, stage2_count))
    conn.commit()

    print(f"[Stage6] Market Health: score={overall_score}%, signal={signal}")
    print(f"[Stage6] Sector scores: {sector_scores}")
    print(f"[Stage6] Theme scores:  {theme_scores}")


def run(tickers: list[str]) -> list[str]:
    print(f"[Stage6] Scoring and ranking {len(tickers)} tickers...")
    today    = date.today().isoformat()
    week_of  = datetime.now().strftime("%Y-W%W")
    conn     = get_connection()
    cur      = conn.cursor()
    picks    = []

    for ticker in tickers:
        # Load detailed_analysis
        cur.execute("SELECT * FROM detailed_analysis WHERE ticker = ?", (ticker,))
        da = cur.fetchone()
        if not da:
            continue

        # Load technical_screen
        cur.execute("SELECT * FROM technical_screen WHERE ticker = ?", (ticker,))
        ts = cur.fetchone()

        # Load fundamentals (may be None)
        cur.execute("SELECT * FROM fundamentals WHERE ticker = ?", (ticker,))
        f  = cur.fetchone()

        da = dict(da)
        ts = dict(ts) if ts else {}
        f  = dict(f)  if f  else None

        # Hybrid composite score (50% technical + 50% fundamental)
        score = compute_composite_score(
            tech_score=da.get("technical_score", 5),
            rr=da.get("risk_reward", 0),
            vcp_score=da.get("vcp_score", 0),
            fundamentals=f,
        )
        fundamental_verdict = compute_fundamental_verdict(f)

        sector = f["sector"] if f else ts.get("sector", "")
        themes = get_themes(ticker)

        direction     = da.get("direction", "LONG")

        # ハイブリッドパイプラインはLONGのみ（ファンダスコアはロング優位の指標のため）
        if direction == "SHORT":
            continue

        tech_summary  = build_technical_summary(da, ts)
        fund_summary  = build_fundamental_summary(f)

        # Take-profit signals
        tp_info = compute_take_profit_signals(f, ts)
        tech_summary["take_profit"] = tp_info

        verdict = "BUY" if da.get("tier") == "Tier1" else "WATCH"

        pick = {
            "ticker":               ticker,
            "week_of":              week_of,
            "composite_score":      score,
            "tier":                 da.get("tier", "Tier2"),
            "sector":               sector,
            "themes":               json.dumps(themes, ensure_ascii=False),
            "entry_price":          da.get("pivot_price"),
            "stop_price":           da.get("stop_price"),
            "tp1_price":            da.get("tp1_price"),
            "target_price":         da.get("target_price"),
            "risk_reward":          da.get("risk_reward"),
            "holding_days_est":     da.get("holding_days_est", 30),
            "technical_summary":    json.dumps(tech_summary,  ensure_ascii=False),
            "fundamental_summary":  json.dumps(fund_summary,  ensure_ascii=False),
            "fundamental_verdict":  fundamental_verdict,
            "verdict":              verdict,
            "direction":            direction,
        }
        picks.append(pick)

    # Sort by score desc (LONGのみ)
    picks.sort(key=lambda x: -x["composite_score"])

    # Save weekly picks
    cur.execute("DELETE FROM weekly_picks")
    for p in picks:
        cur.execute("""
            INSERT INTO weekly_picks
                (ticker, week_of, composite_score, tier, sector, themes,
                 entry_price, stop_price, tp1_price, target_price, risk_reward,
                 holding_days_est, technical_summary, fundamental_summary,
                 fundamental_verdict, verdict, direction)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT (ticker) DO UPDATE SET
                week_of=EXCLUDED.week_of, composite_score=EXCLUDED.composite_score,
                tier=EXCLUDED.tier, sector=EXCLUDED.sector, themes=EXCLUDED.themes,
                entry_price=EXCLUDED.entry_price, stop_price=EXCLUDED.stop_price,
                tp1_price=EXCLUDED.tp1_price, target_price=EXCLUDED.target_price,
                risk_reward=EXCLUDED.risk_reward, holding_days_est=EXCLUDED.holding_days_est,
                technical_summary=EXCLUDED.technical_summary,
                fundamental_summary=EXCLUDED.fundamental_summary,
                fundamental_verdict=EXCLUDED.fundamental_verdict,
                verdict=EXCLUDED.verdict, direction=EXCLUDED.direction
        """, (
            p["ticker"], p["week_of"], p["composite_score"], p["tier"],
            p["sector"], p["themes"], p["entry_price"], p["stop_price"],
            p["tp1_price"], p["target_price"], p["risk_reward"],
            p["holding_days_est"],
            p["technical_summary"], p["fundamental_summary"],
            p["fundamental_verdict"], p["verdict"], p["direction"],
        ))

    conn.commit()

    # Compute market health
    compute_market_health(conn, today)
    conn.close()

    # ── バックテスト用シグナルログ（Logic 1: weekly_picks ベース）──────────────
    try:
        from backend.services.signal_tracker import log_signals
        log_signals("logic1", picks)
    except Exception as e:
        print(f"[Stage6] signal_log 記録エラー: {e}")

    print(f"\n[Stage6] Weekly Picks — {len(picks)} long (SHORTは除外):")
    for p in picks[:12]:
        print(f"  📈 {p['ticker']:6s} | Score={p['composite_score']:5.1f} | {p['tier']} | RR={p['risk_reward']:.2f} | {p['verdict']}")

    return [p["ticker"] for p in picks]


if __name__ == "__main__":
    from backend.db import init_db
    init_db()
    run(["NVDA", "AAPL", "MSFT"])
