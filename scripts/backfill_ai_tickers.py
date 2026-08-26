"""AIセクターマップ用に追加した14銘柄を universe / price_data に投入する。

対象: config.AI_CATEGORY_MAP の全銘柄のうち price_data に無いもの
（VRT, COHR, CRDO, ALAB, FN, ASML, TSM, ARM, CRWV, NBIS, IREN, APLD, INTC, TER）。

1. universe テーブルへ upsert（sector は yfinance から軽く補完）
2. Polygon per-ticker aggs (1銘柄1コール) で price_data の既存期間に揃えてバックフィル

再実行しても冪等（ON CONFLICT upsert）。1回限りの手動実行を想定。
"""

import argparse
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

import certifi
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import AI_CATEGORY_MAP, POLYGON_API_KEY, POLYGON_BASE_URL, SECTOR_DISPLAY
from backend.db import get_connection

_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
BACKFILL_START = "2025-03-31"  # 既存 price_data の最古日に合わせる


def target_tickers() -> list[str]:
    all_tickers = sorted({t for cat in AI_CATEGORY_MAP.values() for t in cat["tickers"]})
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT ticker FROM price_data")
    have = {row["ticker"] for row in cur.fetchall()}
    conn.close()
    return [t for t in all_tickers if t not in have]


def upsert_universe(tickers: list[str]) -> None:
    now = datetime.now().isoformat()
    conn = get_connection()
    cur = conn.cursor()
    for ticker in tickers:
        name, sector_jp, exchange = "", "", ""
        try:
            info = yf.Ticker(ticker).info
            name = info.get("shortName") or info.get("longName") or ""
            sector_en = info.get("sector", "") or ""
            sector_jp = SECTOR_DISPLAY.get(sector_en, sector_en)
            exchange = info.get("exchange", "") or ""
        except Exception as exc:
            print(f"[Universe] {ticker}: yfinance info取得失敗 ({exc}) — sector空で登録")
        cur.execute(
            """
            INSERT INTO universe (ticker, name, sector, industry, market_cap, exchange, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                name=excluded.name, sector=excluded.sector,
                exchange=excluded.exchange, updated_at=excluded.updated_at
            """,
            (ticker, name, sector_jp, "", 0, exchange, now),
        )
        conn.commit()
        print(f"[Universe] {ticker}: name={name!r} sector={sector_jp!r}")
    conn.close()


def _fetch_polygon_aggs(ticker: str, start: str, end: str, retries: int = 3) -> list[dict]:
    url = (
        f"{POLYGON_BASE_URL}/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}"
        f"?adjusted=true&sort=asc&limit=50000&apiKey={POLYGON_API_KEY}"
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=40, context=_SSL_CONTEXT) as resp:
                payload = json.load(resp)
            if payload.get("status") in ("OK", "DELAYED"):
                return payload.get("results") or []
            print(f"[Backfill] {ticker}: status={payload.get('status')} — スキップ")
            return []
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                time.sleep(13)
                continue
            print(f"[Backfill] {ticker}: HTTP {exc.code} — スキップ")
            return []
        except Exception as exc:
            if attempt == retries - 1:
                print(f"[Backfill] {ticker}: 失敗 ({exc})")
                return []
            time.sleep(2)
    return []


def backfill_price_data(tickers: list[str]) -> None:
    end = date.today().isoformat()
    conn = get_connection()
    cur = conn.cursor()
    for i, ticker in enumerate(tickers):
        results = _fetch_polygon_aggs(ticker, BACKFILL_START, end)
        rows = []
        for r in results:
            c = r.get("c")
            if c is None:
                continue
            ts = datetime.utcfromtimestamp(r["t"] / 1000).date().isoformat()
            rows.append((
                ticker, ts,
                float(r["o"]) if r.get("o") is not None else None,
                float(r["h"]) if r.get("h") is not None else None,
                float(r["l"]) if r.get("l") is not None else None,
                float(c),
                int(r["v"]) if r.get("v") is not None else 0,
            ))
        if rows:
            cur.executemany(
                """
                INSERT INTO price_data (ticker, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (ticker, date) DO UPDATE SET
                    open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                    close=EXCLUDED.close, volume=EXCLUDED.volume
                """,
                rows,
            )
            conn.commit()
        print(f"[Backfill] {ticker}: {len(rows)}日ぶん upsert")
        # Polygon 無料枠 5コール/分。最後の1件では待たない。
        if i < len(tickers) - 1:
            time.sleep(13)
    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="対象銘柄の表示のみ")
    args = parser.parse_args()

    tickers = target_tickers()
    print(f"対象: {len(tickers)}銘柄 {tickers}")
    if not tickers:
        print("追加すべき銘柄はありません")
        return
    if args.dry_run:
        return

    upsert_universe(tickers)
    backfill_price_data(tickers)
    print("完了")


if __name__ == "__main__":
    main()
