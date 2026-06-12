"""
Stage 2: Bulk OHLCV download.
主データソース = Polygon.io grouped daily bars（1コールで全米株のEODを一括取得）。
POLYGON_API_KEY 未設定時は従来の yfinance 個別DLにフォールバック。
"""
import os
import sys
import json
import time
import sqlite3
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timedelta

import yfinance as yf
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DOWNLOAD_BATCH_SIZE, PRICE_HISTORY_PERIOD
from backend.db import get_connection


def save_price_batch(df: pd.DataFrame, tickers: list[str]) -> list[str]:
    """Save a multi-ticker yfinance download to price_data table."""
    conn = get_connection()
    cur  = conn.cursor()
    saved_tickers = []

    for ticker in tickers:
        try:
            # yfinance multi-download has MultiIndex columns: (field, ticker)
            if isinstance(df.columns, pd.MultiIndex):
                t_df = df.xs(ticker, axis=1, level=1, drop_level=True)
            else:
                t_df = df

            t_df = t_df.dropna(subset=["Close"])

            rows = [
                (
                    ticker,
                    str(idx.date()),
                    float(row["Open"])   if not pd.isna(row["Open"])   else None,
                    float(row["High"])   if not pd.isna(row["High"])   else None,
                    float(row["Low"])    if not pd.isna(row["Low"])    else None,
                    float(row["Close"])  if not pd.isna(row["Close"])  else None,
                    int(row["Volume"])   if not pd.isna(row["Volume"]) else 0,
                )
                for idx, row in t_df.iterrows()
            ]

            if not rows:
                continue

            cur.executemany("""
                INSERT INTO price_data (ticker, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (ticker, date) DO UPDATE SET
                    open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                    close=EXCLUDED.close, volume=EXCLUDED.volume
            """, rows)
            saved_tickers.append(ticker)
        except Exception as e:
            pass  # ticker not in this batch's data

    conn.commit()
    conn.close()
    return saved_tickers


def run(tickers: list[str]) -> list[str]:
    """Download price data for all tickers. Returns list of successfully downloaded tickers."""
    print(f"[Stage2] Downloading price data for {len(tickers)} tickers...")
    successful = []
    batches    = [tickers[i:i + DOWNLOAD_BATCH_SIZE] for i in range(0, len(tickers), DOWNLOAD_BATCH_SIZE)]

    for i, batch in enumerate(batches):
        batch_str = " ".join(batch)
        print(f"[Stage2] Batch {i+1}/{len(batches)} ({len(batch)} tickers)...", end=" ", flush=True)
        try:
            df = yf.download(
                batch_str,
                period=PRICE_HISTORY_PERIOD,
                auto_adjust=True,
                progress=False,
                threads=True,
            )
            if df.empty:
                print("empty")
                continue

            saved = save_price_batch(df, batch)
            successful.extend(saved)
            print(f"saved {len(saved)}")
        except Exception as e:
            print(f"error: {e}")

        # Small pause to avoid overwhelming yfinance
        if i < len(batches) - 1:
            time.sleep(0.5)

    print(f"[Stage2] Done. {len(successful)}/{len(tickers)} tickers downloaded.")
    return successful


def run_incremental(tickers: list[str], days: int = 10) -> list[str]:
    """直近N日分のみ差分ダウンロードしてprice_dataを更新。日次フルフィルタ用。"""
    period = f"{days}d"
    print(f"[Stage2] Incremental download ({period}) for {len(tickers)} tickers...")
    successful = []
    batches = [tickers[i:i + DOWNLOAD_BATCH_SIZE] for i in range(0, len(tickers), DOWNLOAD_BATCH_SIZE)]

    for i, batch in enumerate(batches):
        batch_str = " ".join(batch)
        print(f"[Stage2] Batch {i+1}/{len(batches)} ({len(batch)} tickers)...", end=" ", flush=True)
        try:
            df = yf.download(
                batch_str,
                period=period,
                auto_adjust=True,
                progress=False,
                threads=True,
            )
            if df.empty:
                print("empty")
                continue
            saved = save_price_batch(df, batch)
            successful.extend(saved)
            print(f"saved {len(saved)}")
        except Exception as e:
            print(f"error: {e}")

        if i < len(batches) - 1:
            time.sleep(0.3)

    print(f"[Stage2] Incremental done. {len(successful)}/{len(tickers)} tickers updated.")
    return successful


# ─────────────────────────────────────────────────────────────────────────────
# Polygon.io grouped daily bars — 1コール/日で全米株EODを一括取得
# 無料プラン: 5コール/分・EOD(前営業日まで)・約2年履歴
# ─────────────────────────────────────────────────────────────────────────────
POLYGON_GROUPED_URL = (
    "https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{date}"
    "?adjusted=true&apiKey={key}"
)
# 無料枠5コール/分 → 13秒間隔（約4.6/分）で安全側
POLYGON_RATE_SLEEP = 13.0


def _polygon_grouped_day(date_str: str, key: str, retries: int = 3) -> list[dict] | None:
    """指定日のgrouped daily barsを取得。営業日でない/未確定なら None。"""
    url = POLYGON_GROUPED_URL.format(date=date_str, key=key)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=40) as resp:
                d = json.load(resp)
            status = d.get("status")
            if status in ("OK", "DELAYED") and d.get("results"):
                return d["results"]
            # NOT_AUTHORIZED(当日未確定) / resultsCount 0(週末・祝日) → データ無し
            return None
        except urllib.error.HTTPError as e:
            if e.code == 429:  # レート超過 → 待って再試行
                time.sleep(POLYGON_RATE_SLEEP * 1.5)
                continue
            if e.code in (403, 404):
                return None
            if attempt == retries - 1:
                raise
            time.sleep(2)
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2)
    return None


def _save_grouped_rows(results: list[dict], date_str: str, universe: set[str]) -> int:
    """grouped結果のうちuniverse該当銘柄をprice_dataへupsert。保存銘柄数を返す。"""
    rows = []
    for r in results:
        t = (r.get("T") or "").strip().upper()
        if t not in universe:
            continue
        c = r.get("c")
        if c is None:
            continue
        rows.append((
            t, date_str,
            float(r["o"]) if r.get("o") is not None else None,
            float(r["h"]) if r.get("h") is not None else None,
            float(r["l"]) if r.get("l") is not None else None,
            float(c),
            int(r["v"]) if r.get("v") is not None else 0,
        ))
    if not rows:
        return 0
    conn = get_connection()
    cur  = conn.cursor()
    cur.executemany("""
        INSERT INTO price_data (ticker, date, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (ticker, date) DO UPDATE SET
            open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
            close=EXCLUDED.close, volume=EXCLUDED.volume
    """, rows)
    conn.commit()
    conn.close()
    return len(rows)


def run_grouped(tickers: list[str], lookback_days: int = 10) -> list[str]:
    """
    Polygon grouped daily で直近 lookback_days 営業日分のEODを全universe一括取得・upsert。
    price_data を全銘柄ぶん前進させる。冪等(再実行で重複しない)。
    戻り値 = 価格が1件以上保存できた ticker のリスト。
    """
    key = os.getenv("POLYGON_API_KEY", "")
    if not key:
        raise RuntimeError("POLYGON_API_KEY 未設定")

    universe = {t.strip().upper() for t in tickers}
    saved_tickers: set[str] = set()

    # 当日から遡って weekday を lookback_days 営業日ぶん収集（祝日/未確定はAPIが弾く）
    dates: list[str] = []
    d = datetime.utcnow().date()
    while len(dates) < lookback_days:
        if d.weekday() < 5:  # Mon-Fri
            dates.append(d.isoformat())
        d -= timedelta(days=1)

    print(f"[Stage2/Polygon] grouped EOD 取得: 最大{len(dates)}営業日 × universe {len(universe)}銘柄")
    fetched_days = 0
    for i, ds in enumerate(dates):
        results = _polygon_grouped_day(ds, key)
        if results:
            n = _save_grouped_rows(results, ds, universe)
            if n:
                fetched_days += 1
                # 当該日に保存できた銘柄を記録
                for r in results:
                    t = (r.get("T") or "").strip().upper()
                    if t in universe:
                        saved_tickers.add(t)
            print(f"[Stage2/Polygon] {ds}: {n}銘柄 upsert")
        else:
            print(f"[Stage2/Polygon] {ds}: データ無し(週末/祝日/未確定)")
        if i < len(dates) - 1:
            time.sleep(POLYGON_RATE_SLEEP)

    print(f"[Stage2/Polygon] 完了: {fetched_days}営業日 / 価格更新 {len(saved_tickers)}/{len(universe)}銘柄")
    return sorted(saved_tickers)


def run_grouped_backfill(tickers: list[str], lookback_days: int = 320) -> list[str]:
    """初回バックフィル: lookback_days 営業日ぶん(≈300取引日, 200EMA用)を遡って一括取得。"""
    return run_grouped(tickers, lookback_days=lookback_days)


if __name__ == "__main__":
    from backend.db import init_db, get_connection as gc
    init_db()
    conn = gc()
    cur  = conn.cursor()
    cur.execute("SELECT ticker FROM universe LIMIT 20")
    tickers = [row["ticker"] for row in cur.fetchall()]
    conn.close()
    run(tickers)
