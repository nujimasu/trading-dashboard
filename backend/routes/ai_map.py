"""GET /api/ai-map/summary, /api/ai-map/news — AIセクターマップ"""
from __future__ import annotations

import time as time_module
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Query

from config import (
    AI_CATEGORY_MAP,
    AI_MAP_BENCHMARK_TICKER,
    AI_MAP_CACHE_TTL,
    AI_MAP_OVERHEAT_5D_PCT,
    AI_MAP_PERIODS,
    AI_MAP_RS_RANK_ARROW_THRESHOLD,
)
from backend.db import get_connection

router = APIRouter()
_summary_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _all_tickers() -> list[str]:
    return sorted({t for cat in AI_CATEGORY_MAP.values() for t in cat["tickers"]})


def _load_price_wide() -> pd.DataFrame:
    """全AI銘柄+SPYの終値を pivot(date index, ticker columns) で返す。"""
    tickers = _all_tickers() + [AI_MAP_BENCHMARK_TICKER]
    placeholders = ",".join("?" * len(tickers))
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"SELECT ticker, date, close FROM price_data WHERE ticker IN ({placeholders})",
        tickers,
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    wide = df.pivot(index="date", columns="ticker", values="close").sort_index()
    return wide


def _swing_pick_tickers() -> tuple[str | None, set[str]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT MAX(scan_date) AS latest FROM swing_picks")
    row = cur.fetchone()
    latest = row["latest"] if row else None
    picks: set[str] = set()
    if latest is not None:
        cur.execute("SELECT ticker FROM swing_picks WHERE scan_date = ?", (latest,))
        picks = {r["ticker"] for r in cur.fetchall()}
    conn.close()
    return _iso(latest), picks


def _earnings_map() -> dict[str, dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT ticker, earnings_date, timing FROM earnings_dates")
    rows = cur.fetchall()
    conn.close()
    return {r["ticker"]: {"date": _iso(r["earnings_date"]), "timing": r["timing"] or ""} for r in rows}


def _ticker_names() -> dict[str, str]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT ticker, name FROM universe")
    rows = cur.fetchall()
    conn.close()
    return {r["ticker"]: (r["name"] or "") for r in rows}


def _compute_summary() -> dict[str, dict[str, Any]]:
    """DBから読み込み、計算結果をまとめて返す（period別キャッシュの元データ）。"""
    wide = _load_price_wide()
    if wide.empty or AI_MAP_BENCHMARK_TICKER not in wide.columns:
        return {}
    swing_scan_date, swing_picks = _swing_pick_tickers()
    earnings = _earnings_map()
    names = _ticker_names()
    return build_category_results(wide, swing_scan_date, swing_picks, earnings, names)


def build_category_results(
    wide: pd.DataFrame,
    swing_scan_date: str | None,
    swing_picks: set[str],
    earnings: dict[str, dict[str, Any]],
    names: dict[str, str],
    today: date | None = None,
) -> dict[str, dict[str, Any]]:
    """価格pivotから3期間ぶんの計算結果を組み立てる純粋関数（DB非依存・テスト対象）。"""
    if wide.empty or AI_MAP_BENCHMARK_TICKER not in wide.columns:
        return {}

    # 個別銘柄のバックフィル等で他銘柄より新しい日付が1件だけ pivot に混ざることがある
    # （例: 新規追加銘柄だけ先に翌日分が入る）。基準日は SPY の最終有効日に固定し、
    # それより先の行は切り捨てて全銘柄を同じ「as_of」で揃える。
    spy_last_valid = wide[AI_MAP_BENCHMARK_TICKER].last_valid_index()
    if spy_last_valid is None:
        return {}
    wide = wide.loc[:spy_last_valid]

    as_of = wide.index[-1].date()
    today = today or date.today()
    price_stale = bool(np.busday_count(as_of.isoformat(), today.isoformat()) > 2)

    week_end = today + timedelta(days=7)

    # 期間別の生リターン(全銘柄)をあらかじめ計算
    period_returns: dict[str, pd.Series] = {}
    for pname, n in AI_MAP_PERIODS.items():
        if len(wide) > n:
            period_returns[pname] = wide.iloc[-1] / wide.iloc[-1 - n] - 1
        else:
            period_returns[pname] = pd.Series(dtype=float)

    spy_returns = {
        pname: (float(s[AI_MAP_BENCHMARK_TICKER]) if AI_MAP_BENCHMARK_TICKER in s.index and pd.notna(s.get(AI_MAP_BENCHMARK_TICKER)) else None)
        for pname, s in period_returns.items()
    }

    ema20 = wide.ewm(span=20, adjust=False, min_periods=20).mean().iloc[-1]
    above_ema20 = wide.iloc[-1] > ema20

    # カテゴリー別リターン・RSを算出し、1w/1m の順位差からモメンタム矢印を決める
    cat_return_pct: dict[str, dict[str, float | None]] = {pname: {} for pname in AI_MAP_PERIODS}
    for cid, cat in AI_CATEGORY_MAP.items():
        have = [t for t in cat["tickers"] if t in wide.columns]
        for pname in AI_MAP_PERIODS:
            vals = period_returns[pname].reindex(have).dropna()
            cat_return_pct[pname][cid] = round(float(vals.mean()) * 100, 2) if len(vals) else None

    rs_pt: dict[str, dict[str, float | None]] = {pname: {} for pname in AI_MAP_PERIODS}
    for pname in AI_MAP_PERIODS:
        spy_r = spy_returns[pname]
        for cid, ret in cat_return_pct[pname].items():
            rs_pt[pname][cid] = round(ret - spy_r * 100, 2) if (ret is not None and spy_r is not None) else None

    rank_1w = pd.Series({cid: v for cid, v in rs_pt["1w"].items() if v is not None}).rank(ascending=False)
    rank_1m = pd.Series({cid: v for cid, v in rs_pt["1m"].items() if v is not None}).rank(ascending=False)

    result: dict[str, dict[str, Any]] = {}
    for pname, n in AI_MAP_PERIODS.items():
        categories = []
        for cid, cat in AI_CATEGORY_MAP.items():
            have = [t for t in cat["tickers"] if t in wide.columns]

            rs_trend = "flat"
            if cid in rank_1w.index and cid in rank_1m.index:
                diff = rank_1m[cid] - rank_1w[cid]
                if diff >= AI_MAP_RS_RANK_ARROW_THRESHOLD:
                    rs_trend = "improving"
                elif diff <= -AI_MAP_RS_RANK_ARROW_THRESHOLD:
                    rs_trend = "worsening"

            above = above_ema20[have].dropna()
            breadth_n = int(above.sum())
            breadth_total = len(above)

            heat5d = cat_return_pct["1w"].get(cid)
            overheat = bool(heat5d is not None and heat5d >= AI_MAP_OVERHEAT_5D_PCT)

            swing_count = sum(1 for t in have if t in swing_picks)
            earnings_week_count = sum(
                1 for t in have
                if t in earnings and earnings[t]["date"] and today.isoformat() <= earnings[t]["date"] <= week_end.isoformat()
            )

            window = wide[have].iloc[-1 - n:] if len(wide) > n else wide[have]
            normalized = window / window.iloc[0] * 100
            index_series = [
                {"date": idx.date().isoformat(), "value": round(float(v), 2)}
                for idx, v in normalized.mean(axis=1).items()
                if pd.notna(v)
            ]

            tickers_out = []
            for t in cat["tickers"]:
                if t not in wide.columns:
                    tickers_out.append({"ticker": t, "name": names.get(t, ""), "no_data": True})
                    continue
                close = float(wide[t].iloc[-1])
                prev = float(wide[t].iloc[-2]) if len(wide) >= 2 and pd.notna(wide[t].iloc[-2]) else None
                ret = period_returns[pname].get(t)
                spark = wide[t].tail(30).dropna()
                earn = earnings.get(t)
                tickers_out.append({
                    "ticker": t,
                    "name": names.get(t, ""),
                    "close": round(close, 2),
                    "chg_1d_pct": round((close / prev - 1) * 100, 2) if prev else None,
                    "return_pct": round(float(ret) * 100, 2) if pd.notna(ret) else None,
                    "above_ema20": bool(above_ema20.get(t)) if pd.notna(above_ema20.get(t)) else None,
                    "in_swing_picks": t in swing_picks,
                    "earnings_date": earn["date"] if earn else None,
                    "earnings_timing": earn["timing"] if earn else "",
                    "spark": [round(float(v), 2) for v in spark],
                    "tv_url": f"https://www.tradingview.com/chart/?symbol={t}",
                })

            categories.append({
                "id": cid,
                "label": cat["label"],
                "return_pct": cat_return_pct[pname].get(cid),
                "rs_pt": rs_pt[pname].get(cid),
                "rs_trend": rs_trend,
                "breadth_pct": round(breadth_n / breadth_total * 100, 1) if breadth_total else None,
                "breadth_n": breadth_n,
                "breadth_total": breadth_total,
                "overheat": overheat,
                "swing_pick_count": swing_count,
                "earnings_this_week": earnings_week_count,
                "n_calc": int(period_returns[pname].reindex(have).notna().sum()),
                "n_total": len(have),
                "index_series": index_series,
                "tickers": tickers_out,
            })

        categories.sort(key=lambda c: (c["return_pct"] is None, -(c["return_pct"] or 0)))

        result[pname] = {
            "as_of": as_of.isoformat(),
            "swing_scan_date": swing_scan_date,
            "price_stale": price_stale,
            "period": pname,
            "benchmark": {
                "ticker": AI_MAP_BENCHMARK_TICKER,
                "return_pct": round(spy_returns[pname] * 100, 2) if spy_returns[pname] is not None else None,
            },
            "categories": categories,
        }
    return result


@router.get("/api/ai-map/summary")
def ai_map_summary(period: str = Query("1m")) -> dict[str, Any]:
    if period not in AI_MAP_PERIODS:
        period = "1m"

    now = time_module.monotonic()
    cached = _summary_cache.get("all")
    if cached and now - cached[0] < AI_MAP_CACHE_TTL:
        return cached[1][period]

    computed = _compute_summary()
    if computed:
        _summary_cache["all"] = (now, computed)
    return computed.get(period, {"categories": [], "as_of": None})


@router.get("/api/ai-map/news")
def ai_map_news(days: int = Query(7, ge=1, le=30)) -> dict[str, Any]:
    since = (date.today() - timedelta(days=days)).isoformat()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT news_date, category, ticker, headline, summary_ja, sentiment, source_url, created_at
        FROM ai_news
        WHERE news_date >= ?
        ORDER BY news_date DESC, category ASC, ticker ASC
        """,
        (since,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    items = []
    latest_news_date = None
    latest_created_at = None
    for r in rows:
        nd = _iso(r["news_date"])
        ca = _iso(r["created_at"])
        latest_news_date = nd if latest_news_date is None or nd > latest_news_date else latest_news_date
        latest_created_at = ca if latest_created_at is None or ca > latest_created_at else latest_created_at
        items.append({
            "news_date": nd,
            "category": r["category"],
            "ticker": r["ticker"] or None,
            "headline": r["headline"],
            "summary_ja": r["summary_ja"],
            "sentiment": r["sentiment"] or "neutral",
            "source_url": r["source_url"] or "",
        })

    stale = True
    if latest_news_date:
        stale = bool(np.busday_count(latest_news_date, date.today().isoformat()) > 2)

    return {
        "updated_at": latest_created_at,
        "stale": stale,
        "items": items,
    }
