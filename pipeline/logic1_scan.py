from __future__ import annotations
"""
Logic 1: ファンダ重視（グロース）スキャン。

全ユニバースを成長ファンダだけで順位付けし、テクニカルは押し目タイミング
注記と執行プランの有無にだけ使う。
"""
import json
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.db import get_connection
from backend.services.fundamentals import get_or_fetch_fundamentals
from config import THEME_MAP, SECTOR_DISPLAY


MIN_BARS_DAILY = 200
MAX_WEEKLY_PICKS = 60
MIN_MARKET_CAP = 1_000_000_000
HOLDING_DAYS_EST = 45

_PRICE_SQL = """
    SELECT date, open, high, low, close, volume
    FROM price_data
    WHERE ticker = ?
    ORDER BY date ASC
"""


def _safe_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _ema(values, period):
    out = [None] * len(values)
    if len(values) < period:
        return out
    k = 2 / (period + 1)
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    for i in range(period, len(values)):
        out[i] = values[i] * k + out[i - 1] * (1 - k)
    return out


def _atr(highs, lows, closes, period=14):
    out = [None] * len(closes)
    if len(closes) <= period:
        return out
    trs = [0.0]
    for i in range(1, len(closes)):
        trs.append(max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        ))
    out[period] = sum(trs[1:period + 1]) / period
    for i in range(period + 1, len(closes)):
        out[i] = (out[i - 1] * (period - 1) + trs[i]) / period
    return out


def _themes(ticker: str) -> list[str]:
    return [theme for theme, members in THEME_MAP.items() if ticker in members]


def _score_eps(value):
    if value is None or value <= 0:
        return 0
    if value >= 50:
        return 30
    if value >= 30:
        return 24
    if value >= 18:
        return 18
    if value >= 8:
        return 12
    return 6


def _score_revenue(value):
    if value is None or value < 0:
        return 0
    if value >= 30:
        return 15
    if value >= 20:
        return 12
    if value >= 10:
        return 9
    if value > 0:
        return 4
    return 0


def _score_surprise(value):
    if value is None:
        return 7
    if value > 10:
        return 15
    if value >= 5:
        return 11
    if value >= 0:
        return 7
    return 0


def _score_roe(value):
    if value is None or value < 0:
        return 0
    if value >= 30:
        return 15
    if value >= 20:
        return 12
    if value >= 15:
        return 9
    return round(min(value / 15 * 9, 9), 1)


def _score_margin(value):
    if value is None:
        return 7
    if value >= 25:
        return 15
    if value >= 15:
        return 11
    if value >= 5:
        return 7
    if value >= 0:
        return 3
    return 0


def _score_inst_own(value):
    if value is None:
        return 5
    if 30 <= value <= 70:
        return 10
    if 20 <= value < 30 or 70 < value <= 85:
        return 7
    return 4


def _growth_inputs(f: dict) -> dict:
    eps = _safe_float(f.get("eps_growth_q"))
    if eps is None:
        eps = _safe_float(f.get("eps_growth_yoy"))
    op_margin = _safe_float(f.get("operating_margin"))
    margin = op_margin if op_margin is not None else _safe_float(f.get("profit_margin"))
    return {
        "eps_growth": eps,
        "revenue_growth_yoy": _safe_float(f.get("revenue_growth_yoy")),
        "earnings_surprise_pct": _safe_float(f.get("earnings_surprise_pct")),
        "roe": _safe_float(f.get("roe")),
        "margin": margin,
        "inst_own_pct": _safe_float(f.get("inst_own_pct")),
        "debt_to_equity": _safe_float(f.get("debt_to_equity")),
    }


def _passes_growth_gate(f: dict, inputs: dict) -> tuple[bool, list[str]]:
    reasons = []
    if not (inputs["eps_growth"] is not None and inputs["eps_growth"] > 0):
        reasons.append("EPS成長が0%以下")
    if not (inputs["revenue_growth_yoy"] is not None and inputs["revenue_growth_yoy"] > 0):
        reasons.append("売上成長が0%以下")

    pe = _safe_float(f.get("pe_ratio"))
    profit_margin = _safe_float(f.get("profit_margin"))
    profitable = (pe is not None and pe > 0) or (profit_margin is not None and profit_margin > 0)
    if not profitable:
        reasons.append("黒字確認なし")

    market_cap = _safe_float(f.get("market_cap")) or 0
    if market_cap < MIN_MARKET_CAP:
        reasons.append("時価総額$1B未満")

    if not f.get("sector"):
        reasons.append("ファンダデータ不足")

    return not reasons, reasons


def _growth_score(f: dict) -> tuple[float, dict]:
    inputs = _growth_inputs(f)
    breakdown = {
        "eps_growth": _score_eps(inputs["eps_growth"]),
        "revenue_growth": _score_revenue(inputs["revenue_growth_yoy"]),
        "earnings_surprise": _score_surprise(inputs["earnings_surprise_pct"]),
        "roe": _score_roe(inputs["roe"]),
        "margin": _score_margin(inputs["margin"]),
        "institutional_ownership": _score_inst_own(inputs["inst_own_pct"]),
        "debt_penalty": -5 if inputs["debt_to_equity"] is not None and inputs["debt_to_equity"] > 200 else 0,
    }
    total = sum(breakdown.values())
    return round(max(0, min(total, 100)), 1), breakdown


def _fundamental_verdict(score: float) -> str:
    if score >= 80:
        return "強い成長"
    if score >= 65:
        return "良好"
    if score >= 50:
        return "平均的成長"
    return "成長やや弱め"


def _tier(score: float) -> str:
    if score >= 80:
        return "Tier1"
    if score >= 65:
        return "Tier2"
    return "Tier3"


def _build_timing(rows, cross_tag: list[str], breakdown: dict) -> dict:
    closes = [r["close"] for r in rows]
    highs = [r["high"] for r in rows]
    lows = [r["low"] for r in rows]
    i = len(closes) - 1

    ema20 = _ema(closes, 20)
    ema50 = _ema(closes, 50)
    ema200 = _ema(closes, 200)
    atr_arr = _atr(highs, lows, closes)

    current = closes[i]
    e20, e50, e200 = ema20[i], ema50[i], ema200[i]
    above_ema200 = bool(e200 is not None and current > e200)
    uptrend = bool(e200 is not None and e50 is not None and current > e200 and e50 > e200)
    ema20_dist = (current - e20) / e20 * 100 if e20 else None
    ema50_dist = (current - e50) / e50 * 100 if e50 else None
    near_20 = ema20_dist is not None and abs(ema20_dist) <= 3
    near_50 = ema50_dist is not None and abs(ema50_dist) <= 3
    in_pullback = bool(uptrend and (near_20 or near_50))

    if in_pullback:
        zone_flag = "押し目圏内"
    elif uptrend:
        zone_flag = "やや高所（押し目待ち）"
    else:
        zone_flag = "トレンド外（様子見）"

    plan = {
        "entry_price": None,
        "stop_price": None,
        "tp1_price": None,
        "target_price": None,
        "risk_reward": None,
    }
    risk_factors = []

    if in_pullback:
        atr_v = atr_arr[i] or 0
        swing_low = min(lows[max(0, i - 19):i + 1])
        stop = swing_low - 0.1 * atr_v
        risk = current - stop
        if risk > 0:
            plan = {
                "entry_price": round(current, 2),
                "stop_price": round(stop, 2),
                "tp1_price": round(current + 1.5 * risk, 2),
                "target_price": round(current + 3.0 * risk, 2),
                "risk_reward": 1.5,
            }
        else:
            risk_factors.append("押し安値が現在値以上のためSL/TP未提示")
    else:
        risk_factors.append(f"{zone_flag}: 押し目圏外のためSL/TP未提示")

    entry_reasons = [zone_flag]
    if in_pullback:
        entry_reasons.append("上昇トレンド内で20/50EMA±3%以内")
    entry_reasons.extend(cross_tag)

    return {
        **plan,
        "technical_summary": {
            "ema20_dist": round(ema20_dist, 2) if ema20_dist is not None else None,
            "ema50_dist": round(ema50_dist, 2) if ema50_dist is not None else None,
            "above_ema200": above_ema200,
            "zone_flag": zone_flag,
            "in_pullback": in_pullback,
            "cross_tag": cross_tag,
            "growth_breakdown": breakdown,
            "entry_reasons": entry_reasons,
            "risk_factors": risk_factors,
            "stage2_uptrend": uptrend,
        },
    }


def _fundamental_summary(f: dict, score: float) -> dict:
    return {
        "available": True,
        "sector": f.get("sector", ""),
        "industry": f.get("industry", ""),
        "market_cap_b": round((_safe_float(f.get("market_cap")) or 0) / 1e9, 1),
        "pe_ratio": _safe_float(f.get("pe_ratio")),
        "eps_growth_yoy": _safe_float(f.get("eps_growth_yoy")),
        "eps_growth_q": _safe_float(f.get("eps_growth_q")),
        "revenue_growth_yoy": _safe_float(f.get("revenue_growth_yoy")),
        "earnings_surprise_pct": _safe_float(f.get("earnings_surprise_pct")),
        "roe": _safe_float(f.get("roe")),
        "operating_margin": _safe_float(f.get("operating_margin")),
        "profit_margin": _safe_float(f.get("profit_margin")),
        "inst_own_pct": _safe_float(f.get("inst_own_pct")),
        "debt_to_equity": _safe_float(f.get("debt_to_equity")),
        "growth_score": score,
        "description": (f.get("description") or "")[:400],
    }


def _cross_tags(cur, today: str) -> dict[str, list[str]]:
    tags: dict[str, list[str]] = {}
    for table, label in (("logic2_picks", "v1にも出現（買い場一致）"),
                         ("logic4_picks", "v2にも出現（買い場一致）")):
        try:
            cur.execute(f"SELECT ticker FROM {table} WHERE scan_date = ?", (today,))
            for row in cur.fetchall():
                tags.setdefault(row["ticker"], []).append(label)
        except Exception:
            continue
    return tags


def run() -> list[dict]:
    print("[Logic1] ファンダ重視（グロース）スクリーニング開始...")
    today = date.today().isoformat()
    week_of = datetime.now().strftime("%Y-W%W")
    # universe と cross_map は短命接続で取得して即クローズ（長時間接続を保持しない）
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.ticker
        FROM universe u
        JOIN price_data p ON p.ticker = u.ticker
        GROUP BY u.ticker
        HAVING COUNT(p.date) >= ?
        ORDER BY u.ticker
    """, (MIN_BARS_DAILY,))
    tickers = [r["ticker"] for r in cur.fetchall()]
    print(f"[Logic1] 対象銘柄数: {len(tickers)}")
    cross_map = _cross_tags(cur, today)

    # ループは単一接続で price_data を読む（銘柄ごとに新規接続すると pooler の
    # クライアント上限を圧迫して固まるため）。万一ドロップしたら都度再接続する。
    # yfinance は _fetch_with_timeout で 25 秒上限のため接続が長時間 idle にならない。
    candidates = []
    gate_pass = 0

    for ticker in tickers:
        try:
            f = get_or_fetch_fundamentals(ticker)
            if not f:
                continue
            inputs = _growth_inputs(f)
            passed, _ = _passes_growth_gate(f, inputs)
            if not passed:
                continue
            gate_pass += 1

            score, breakdown = _growth_score(f)
            try:
                cur.execute(_PRICE_SQL, (ticker,))
                rows = [dict(r) for r in cur.fetchall()]
            except Exception:
                conn = get_connection(); cur = conn.cursor()   # ドロップ時は再接続
                cur.execute(_PRICE_SQL, (ticker,))
                rows = [dict(r) for r in cur.fetchall()]
            if len(rows) < MIN_BARS_DAILY:
                continue

            timing = _build_timing(rows, cross_map.get(ticker, []), breakdown)
            sector = SECTOR_DISPLAY.get(f.get("sector"), f.get("sector", ""))
            fundamental_verdict = _fundamental_verdict(score)
            in_pullback = timing["technical_summary"]["in_pullback"]

            candidates.append({
                "ticker": ticker,
                "week_of": week_of,
                "composite_score": score,
                "tier": _tier(score),
                "sector": sector,
                "themes": json.dumps(_themes(ticker), ensure_ascii=False),
                "entry_price": timing["entry_price"],
                "stop_price": timing["stop_price"],
                "tp1_price": timing["tp1_price"],
                "target_price": timing["target_price"],
                "risk_reward": timing["risk_reward"],
                "holding_days_est": HOLDING_DAYS_EST,
                "technical_summary": json.dumps(timing["technical_summary"], ensure_ascii=False),
                "fundamental_summary": json.dumps(_fundamental_summary(f, score), ensure_ascii=False),
                "fundamental_verdict": fundamental_verdict,
                "verdict": "BUY" if in_pullback and score >= 65 else "WATCH",
                "direction": "LONG",
            })
        except Exception as e:
            print(f"[Logic1] {ticker} エラー: {e}")

    try:
        conn.close()   # ループ用接続を閉じる
    except Exception:
        pass

    candidates.sort(key=lambda p: -p["composite_score"])
    picks = candidates[:MAX_WEEKLY_PICKS]

    # 最終書き込みは新しい接続で（長時間ループ中に接続が切れても確実に書く）
    wconn = get_connection()
    wcur = wconn.cursor()
    wcur.execute("DELETE FROM weekly_picks")
    for p in picks:
        wcur.execute("""
            INSERT INTO weekly_picks
                (ticker, week_of, composite_score, tier, sector, themes,
                 entry_price, stop_price, tp1_price, target_price, risk_reward,
                 holding_days_est, technical_summary, fundamental_summary,
                 fundamental_verdict, verdict, direction)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            p["ticker"], p["week_of"], p["composite_score"], p["tier"],
            p["sector"], p["themes"], p["entry_price"], p["stop_price"],
            p["tp1_price"], p["target_price"], p["risk_reward"],
            p["holding_days_est"], p["technical_summary"], p["fundamental_summary"],
            p["fundamental_verdict"], p["verdict"], p["direction"],
        ))
    wconn.commit()
    wconn.close()

    try:
        from backend.services.signal_tracker import log_signals
        signal_picks = [
            {**p, "confidence": round((p["composite_score"] or 0) / 100, 3)}
            for p in picks
            if p.get("entry_price") is not None and p.get("stop_price") is not None
        ]
        log_signals("logic1", signal_picks)
    except Exception as e:
        print(f"[Logic1] signal_log 記録エラー: {e}")

    print(f"[Logic1] 完了 — ゲート通過:{gate_pass} 採用:{len(picks)}")
    for p in picks[:10]:
        zone = json.loads(p["technical_summary"]).get("zone_flag")
        print(f"  {p['ticker']:8s} Score={p['composite_score']:5.1f} {p['tier']} {p['verdict']} {zone}")
    return picks


if __name__ == "__main__":
    from backend.db import init_db
    init_db()
    run()
