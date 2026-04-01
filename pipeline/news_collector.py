"""
News & Economic Data Collector
- 経済指標: FRED API（米連邦準備制度、完全無料）
- 市場ニュース: Polygon.io + yfinance ハイブリッド
- セクター騰落率: yfinance（セクターETF）
"""
import sys
import json
import requests
from datetime import date, datetime, timedelta
from pathlib import Path

import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import FRED_API_KEY, FRED_BASE_URL, POLYGON_API_KEY, POLYGON_BASE_URL
from backend.db import db_cursor

# ─── セクターETF マップ ───────────────────────────────────────────────────
SECTOR_ETFS = {
    "XLK":  "テクノロジー",
    "XLF":  "金融",
    "XLE":  "エネルギー",
    "XLV":  "ヘルスケア",
    "XLI":  "資本財",
    "XLY":  "一般消費財",
    "XLP":  "生活必需品",
    "XLU":  "公益",
    "XLRE": "不動産",
    "XLB":  "素材",
    "XLC":  "通信・メディア",
}

# ─── 経済指標 FRED series 定義 ────────────────────────────────────────────
FRED_SERIES = {
    "CPIAUCSL": {
        "name": "CPI（消費者物価指数）",
        "unit": "指数",
        "category": "インフレ",
        "positive_direction": "down",   # 下がると株式にポジティブ
        "affected_sectors": ["一般消費財", "生活必需品", "エネルギー"],
    },
    "UNRATE": {
        "name": "失業率",
        "unit": "%",
        "category": "雇用",
        "positive_direction": "down",
        "affected_sectors": ["一般消費財", "金融"],
    },
    "FEDFUNDS": {
        "name": "FF金利（政策金利）",
        "unit": "%",
        "category": "金融政策",
        "positive_direction": "down",
        "affected_sectors": ["金融", "不動産", "テクノロジー"],
    },
    "DGS10": {
        "name": "10年国債利回り",
        "unit": "%",
        "category": "金利",
        "positive_direction": "down",
        "affected_sectors": ["不動産", "公益", "金融"],
    },
    "T10YIE": {
        "name": "期待インフレ率（10年）",
        "unit": "%",
        "category": "インフレ期待",
        "positive_direction": "down",
        "affected_sectors": ["公益", "生活必需品"],
    },
    "PAYEMS": {
        "name": "非農業部門雇用者数（NFP）",
        "unit": "千人",
        "category": "雇用",
        "positive_direction": "up",
        "affected_sectors": ["一般消費財", "金融"],
    },
    "GDP": {
        "name": "GDP（名目・季節調整済み年率）",
        "unit": "十億ドル",
        "category": "景気",
        "positive_direction": "up",
        "affected_sectors": [],
    },
}

# ─── キーワード → セクター/影響度マッピング（Polygon ニュース用） ─────────
NEWS_KEYWORD_MAP = {
    "fed":          ("neutral",  ["金融"]),
    "rate":         ("neutral",  ["金融", "不動産"]),
    "rate hike":    ("negative", ["金融", "不動産", "テクノロジー"]),
    "rate cut":     ("positive", ["金融", "不動産", "テクノロジー"]),
    "inflation":    ("negative", ["一般消費財", "エネルギー"]),
    "cpi":          ("negative", ["一般消費財", "エネルギー"]),
    "tariff":       ("negative", ["素材", "一般消費財"]),
    "sanction":     ("negative", ["エネルギー"]),
    "earnings":     ("positive", []),
    "beat":         ("positive", []),
    "miss":         ("negative", []),
    "layoff":       ("negative", ["テクノロジー"]),
    "ai":           ("positive", ["テクノロジー"]),
    "chip":         ("positive", ["テクノロジー"]),
    "oil":          ("neutral",  ["エネルギー"]),
    "jobs":         ("positive", ["一般消費財"]),
    "gdp":          ("positive", []),
    "recession":    ("negative", []),
    "rally":        ("positive", []),
    "selloff":      ("negative", []),
    "crash":        ("negative", []),
}


# ──────────────────────────────────────────────────────────────────────────
# FRED: 経済指標
# ──────────────────────────────────────────────────────────────────────────

def _fred_get(endpoint: str, params: dict) -> dict | None:
    if not FRED_API_KEY:
        return None
    try:
        r = requests.get(
            f"{FRED_BASE_URL}{endpoint}",
            params={"api_key": FRED_API_KEY, "file_type": "json", **params},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
        return None
    except Exception as e:
        print(f"[FRED] Error {endpoint}: {e}")
        return None


def _fred_get_csv(series_id: str) -> list[dict]:
    """FRED 公開 CSV（APIキー不要）から最新2件を取得。"""
    try:
        r = requests.get(
            "https://fred.stlouisfed.org/graph/fredgraph.csv",
            params={"id": series_id},
            timeout=10,
        )
        if r.status_code != 200:
            return []
        lines = r.text.strip().split("\n")[1:]   # ヘッダー除去
        valid = []
        for line in lines:
            parts = line.strip().split(",")
            if len(parts) == 2 and parts[1].strip() not in (".", ""):
                valid.append({"date": parts[0].strip(), "value": parts[1].strip()})
        # 最新2件を「最新が先頭」で返す（APIと同じ順序）
        return list(reversed(valid[-2:])) if valid else []
    except Exception as e:
        print(f"[FRED CSV] {series_id}: {e}")
        return []


def _fetch_fmp_next_releases() -> dict[str, str]:
    """FMP /stable/economic-calendar から今後60日の経済指標発表日を取得。
    Returns dict mapping FRED indicator name → next release date string."""
    from config import FMP_API_KEY, FMP_BASE_URL
    if not FMP_API_KEY:
        return {}

    # FRED指標名 → FMP event名のマッピング
    FMP_EVENT_MAP = {
        "CPI（消費者物価指数）":          "CPI",
        "失業率":                          "Unemployment Rate",
        "FF金利（政策金利）":              "Fed Interest Rate Decision",
        "10年国債利回り":                  None,  # FMPカレンダーなし
        "期待インフレ率（10年）":          None,
        "非農業部門雇用者数（NFP）":       "Nonfarm Payrolls",
        "GDP（名目・季節調整済み年率）":   "GDP",
    }

    try:
        from_date = date.today().isoformat()
        to_date   = (date.today() + timedelta(days=60)).isoformat()
        r = requests.get(
            f"{FMP_BASE_URL}/economic-calendar",
            params={"from": from_date, "to": to_date, "apikey": FMP_API_KEY},
            timeout=10,
        )
        if r.status_code != 200:
            return {}
        events = r.json()
    except Exception as e:
        print(f"[FMP calendar] error: {e}")
        return {}

    # Build lookup: fmp_event_name → earliest upcoming date
    fmp_lookup: dict[str, str] = {}
    for ev in events:
        event_name = ev.get("event", "")
        event_date = ev.get("date", "")[:10]
        if not event_name or not event_date:
            continue
        if event_name not in fmp_lookup:
            fmp_lookup[event_name] = event_date

    result: dict[str, str] = {}
    for fred_name, fmp_name in FMP_EVENT_MAP.items():
        if fmp_name and fmp_name in fmp_lookup:
            result[fred_name] = fmp_lookup[fmp_name]

    return result


def fetch_fred_indicators() -> list[dict]:
    rows = []
    next_releases = _fetch_fmp_next_releases()

    for series_id, meta in FRED_SERIES.items():
        # APIキーあり → JSON API、なし → 公開CSVフォールバック
        obs = []
        if FRED_API_KEY:
            data = _fred_get("/series/observations", {
                "series_id": series_id, "limit": 2, "sort_order": "desc",
            })
            if data:
                obs = data.get("observations", [])
        if not obs:
            obs = _fred_get_csv(series_id)
        if not obs:
            continue

        latest = obs[0]
        prev   = obs[1] if len(obs) > 1 else None

        val       = latest["value"]
        val_date  = latest["date"]
        prev_val  = prev["value"] if prev else None

        # 変化方向で impact を判定
        impact = "neutral"
        if prev_val and val != "." and prev_val != ".":
            try:
                diff = float(val) - float(prev_val)
                if meta["positive_direction"] == "up":
                    impact = "positive" if diff > 0 else "negative"
                else:
                    impact = "positive" if diff < 0 else "negative"
            except ValueError:
                pass

        # 説明文
        if val == ".":
            desc = "最新データ未公表"
        else:
            prev_str = f"（前回: {prev_val} {meta['unit']}）" if prev_val and prev_val != "." else ""
            desc = f"最新値: {val} {meta['unit']}{prev_str}"

        rows.append({
            "date":             val_date,
            "category":         "economic",
            "title":            meta["name"],
            "description":      desc,
            "impact":           impact,
            "affected_sectors": json.dumps(meta["affected_sectors"], ensure_ascii=False),
            "affected_tickers": "[]",
            "source":           f"FRED ({series_id})",
            "url":          "",
            "next_release": next_releases.get(meta["name"], ""),
        })

    print(f"[FRED] {len(rows)} indicators fetched.")
    return rows


# ──────────────────────────────────────────────────────────────────────────
# Polygon.io: 市場ニュース
# ──────────────────────────────────────────────────────────────────────────

def _classify_news(title: str, description: str = "") -> tuple[str, list[str]]:
    text = (title + " " + description).lower()
    for kw, (impact, sectors) in NEWS_KEYWORD_MAP.items():
        if kw in text:
            return impact, sectors
    return "neutral", []


def fetch_polygon_news(limit: int = 20) -> list[dict]:
    if not POLYGON_API_KEY:
        return []
    try:
        r = requests.get(
            f"{POLYGON_BASE_URL}/v2/reference/news",
            params={"apiKey": POLYGON_API_KEY, "limit": limit, "order": "desc"},
            timeout=10,
        )
        if r.status_code != 200:
            print(f"[Polygon] News error: {r.status_code}")
            return []

        rows = []
        for item in r.json().get("results", []):
            title     = item.get("title", "")
            desc      = item.get("description", "") or ""
            pub_date  = (item.get("published_utc") or "")[:10]
            tickers   = item.get("tickers", [])
            publisher = item.get("publisher", {}).get("name", "Polygon")
            impact, sectors = _classify_news(title, desc)

            rows.append({
                "date":             pub_date or date.today().isoformat(),
                "category":         "news",
                "title":            title,
                "description":      desc[:300],
                "impact":           impact,
                "affected_sectors": json.dumps(sectors, ensure_ascii=False),
                "affected_tickers": json.dumps(tickers[:5], ensure_ascii=False),
                "source":           publisher,
                "url":              item.get("article_url", ""),
            })
        print(f"[Polygon] {len(rows)} news fetched.")
        return rows
    except Exception as e:
        print(f"[Polygon] Error: {e}")
        return []


def fetch_yfinance_news(limit: int = 15) -> list[dict]:
    """SPY・QQQ・主要セクターETFのニュースを収集。"""
    tickers_for_news = ["SPY", "QQQ", "XLK", "XLE", "XLF", "XLV"]
    seen_titles = set()
    rows = []

    for sym in tickers_for_news:
        try:
            news_items = yf.Ticker(sym).news or []
            for item in news_items:
                c = item.get("content", {})
                title    = c.get("title", "")
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)

                pub_raw  = c.get("pubDate", "")
                pub_date = pub_raw[:10] if pub_raw else date.today().isoformat()
                provider = c.get("provider", {}).get("displayName", "Yahoo Finance")
                url      = c.get("canonicalUrl", {}).get("url", "") if isinstance(c.get("canonicalUrl"), dict) else ""
                impact, sectors = _classify_news(title)

                rows.append({
                    "date":             pub_date,
                    "category":         "news",
                    "title":            title,
                    "description":      "",
                    "impact":           impact,
                    "affected_sectors": json.dumps(sectors, ensure_ascii=False),
                    "affected_tickers": json.dumps([sym]),
                    "source":           provider,
                    "url":              url,
                })

                if len(rows) >= limit:
                    break
        except Exception:
            continue
        if len(rows) >= limit:
            break

    print(f"[yfinance] {len(rows)} news fetched.")
    return rows


def fetch_market_news_hybrid(limit: int = 30) -> list[dict]:
    """Polygon + yfinance を結合・重複排除してニュースを返す。"""
    polygon_news  = fetch_polygon_news(limit)
    yfinance_news = fetch_yfinance_news(limit // 2)

    # タイトルで重複排除（Polygon優先）
    seen = {r["title"] for r in polygon_news}
    deduped_yf = [r for r in yfinance_news if r["title"] not in seen]

    combined = polygon_news + deduped_yf
    # 日付降順でソート
    combined.sort(key=lambda x: x["date"], reverse=True)
    return combined[:limit]


# ──────────────────────────────────────────────────────────────────────────
# yfinance: セクター騰落率
# ──────────────────────────────────────────────────────────────────────────

def fetch_sector_performance() -> dict[str, float]:
    """セクターETFの前日比騰落率（%）を返す。"""
    try:
        syms = list(SECTOR_ETFS.keys())
        df   = yf.download(" ".join(syms), period="5d", auto_adjust=True, progress=False)
        closes = df["Close"]

        result = {}
        for sym, name in SECTOR_ETFS.items():
            try:
                series = closes[sym].dropna()
                if len(series) >= 2:
                    chg = (series.iloc[-1] - series.iloc[-2]) / series.iloc[-2] * 100
                    result[name] = round(float(chg), 2)
            except Exception:
                continue
        print(f"[Sector] {len(result)} sectors fetched.")
        return result
    except Exception as e:
        print(f"[Sector] Error: {e}")
        return {}


def fetch_sector_ytd() -> dict[str, float]:
    """セクターETFのYTD（年初来）リターン（%）を返す。"""
    try:
        syms  = list(SECTOR_ETFS.keys())
        df    = yf.download(" ".join(syms), period="ytd", auto_adjust=True, progress=False)
        closes = df["Close"]
        result = {}
        for sym, name in SECTOR_ETFS.items():
            try:
                series = closes[sym].dropna()
                if len(series) >= 2:
                    ytd = (series.iloc[-1] - series.iloc[0]) / series.iloc[0] * 100
                    result[name] = round(float(ytd), 2)
            except Exception:
                continue
        return result
    except Exception as e:
        print(f"[Sector YTD] Error: {e}")
        return {}


# ──────────────────────────────────────────────────────────────────────────
# メイン実行
# ──────────────────────────────────────────────────────────────────────────

def run():
    today = date.today().isoformat()
    print("[News Collector] Starting...")
    all_rows = []

    # 経済指標（FRED）
    all_rows.extend(fetch_fred_indicators())

    # ニュース（Polygon + yfinance）
    all_rows.extend(fetch_market_news_hybrid(limit=30))

    if not all_rows:
        print("[News Collector] No data collected.")
        return

    # DB保存（当日分を上書き）
    with db_cursor() as cur:
        cur.execute("DELETE FROM news_events WHERE date = ?", (today,))
        for r in all_rows:
            cur.execute("""
                INSERT INTO news_events
                    (date, category, title, description, impact,
                     affected_sectors, affected_tickers, source, url, next_release)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                r["date"], r["category"], r["title"], r["description"],
                r["impact"], r["affected_sectors"], r["affected_tickers"], r["source"],
                r.get("url", ""), r.get("next_release", ""),
            ))

    eco   = sum(1 for r in all_rows if r["category"] == "economic")
    news  = sum(1 for r in all_rows if r["category"] == "news")
    print(f"[News Collector] Saved: {eco} economic indicators + {news} news items.")


if __name__ == "__main__":
    from backend.db import init_db
    init_db()
    run()
