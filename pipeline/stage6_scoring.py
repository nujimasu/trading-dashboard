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
    Composite score (0-100) — pure technical:
    - Technical score (50%): 1-10 scale normalized
    - RR quality (30%): capped at RR=3.0 for max points
    - VCP score (20%): already 0-100
    Fundamentals are reference-only and do NOT affect this score.
    """
    # Technical (0-50)
    tech_component = (tech_score / 10) * 50

    # RR (0-30): 1.5 → 15pts, 2.0 → 20pts, 3.0 → 30pts
    rr_component = min(rr / 3.0, 1.0) * 30

    # VCP (0-20)
    vcp_component = (vcp_score / 100) * 20

    total = tech_component + rr_component + vcp_component
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

        # Composite score (pure technical — fundamentals are reference only)
        score = compute_composite_score(
            tech_score=da.get("technical_score", 5),
            rr=da.get("risk_reward", 0),
            vcp_score=da.get("vcp_score", 0),
        )
        fundamental_verdict = compute_fundamental_verdict(f)

        sector = f["sector"] if f else ts.get("sector", "")
        themes = get_themes(ticker)

        direction     = da.get("direction", "LONG")
        tech_summary  = build_technical_summary(da, ts)
        fund_summary  = build_fundamental_summary(f)

        # Verdict depends on direction
        if direction == "SHORT":
            verdict = "SHORT_SELL" if da.get("tier") == "Tier1" else "SHORT_WATCH"
        else:
            verdict = "BUY"        if da.get("tier") == "Tier1" else "WATCH"

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
            "holding_days_est":     da.get("holding_days_est", 20),
            "technical_summary":    json.dumps(tech_summary,  ensure_ascii=False),
            "fundamental_summary":  json.dumps(fund_summary,  ensure_ascii=False),
            "fundamental_verdict":  fundamental_verdict,
            "verdict":              verdict,
            "direction":            direction,
        }
        picks.append(pick)

    # Sort: longs by score desc, shorts by score desc, longs first
    picks.sort(key=lambda x: (x["direction"] == "SHORT", -x["composite_score"]))

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

    longs_p  = [p for p in picks if p["direction"] == "LONG"]
    shorts_p = [p for p in picks if p["direction"] == "SHORT"]
    print(f"\n[Stage6] Weekly Picks — {len(longs_p)} long, {len(shorts_p)} short:")
    for p in picks[:12]:
        dir_icon = "📈" if p["direction"] == "LONG" else "📉"
        print(f"  {dir_icon} {p['ticker']:6s} | Score={p['composite_score']:5.1f} | {p['tier']} | RR={p['risk_reward']:.2f} | {p['verdict']}")

    return [p["ticker"] for p in picks]


if __name__ == "__main__":
    from backend.db import init_db
    init_db()
    run(["NVDA", "AAPL", "MSFT"])
