"""日本AIマップ用の東証銘柄の日足を yfinance で取得し price_data へ upsert する。

Polygon は米国株専用のため、日本株はこのモジュールが担当する。
東証は15:00に引けるので、米国株のような EOD 配信遅延の問題は起きない。

price_data テーブルは米国株と共用し、東証銘柄は ".T" サフィックスで区別する
（market_health は '%.T' を除外して米国市場のスコアを保つ）。
"""

import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import JP_AI_CATEGORY_MAP, JP_AI_MAP_BENCHMARK_TICKER
from backend.db import get_connection


def jp_tickers() -> list[str]:
    """対象の東証銘柄（カテゴリー所属の全銘柄＋ベンチマーク）。"""
    tickers = {t for cat in JP_AI_CATEGORY_MAP.values() for t in cat["tickers"]}
    tickers.add(JP_AI_MAP_BENCHMARK_TICKER)
    return sorted(tickers)


def _rows_from_frame(ticker: str, frame: pd.DataFrame) -> list[tuple]:
    frame = frame.dropna(subset=["Close"])
    rows = []
    for index, row in frame.iterrows():
        rows.append((
            ticker,
            str(index.date()),
            float(row["Open"]) if pd.notna(row["Open"]) else None,
            float(row["High"]) if pd.notna(row["High"]) else None,
            float(row["Low"]) if pd.notna(row["Low"]) else None,
            float(row["Close"]),
            int(row["Volume"]) if pd.notna(row["Volume"]) else 0,
        ))
    return rows


def run_jp_prices(period: str = "6mo") -> list[str]:
    """東証銘柄の日足を取得して upsert する。保存できた ticker のリストを返す。

    period は yfinance の指定（"6mo" / "2y" など）。冪等（再実行で重複しない）。
    """
    tickers = jp_tickers()
    frame = yf.download(
        tickers, period=period, interval="1d",
        progress=False, group_by="ticker", auto_adjust=False, threads=True,
    )
    if frame is None or frame.empty:
        print("[JPPrices] yfinance からデータを取得できませんでした")
        return []

    conn = get_connection()
    cur = conn.cursor()
    saved = []
    for ticker in tickers:
        try:
            sub = frame[ticker] if isinstance(frame.columns, pd.MultiIndex) else frame
        except KeyError:
            print(f"[JPPrices] {ticker}: データなし（上場廃止/コード変更の可能性）")
            continue
        rows = _rows_from_frame(ticker, sub)
        if not rows:
            print(f"[JPPrices] {ticker}: 有効な終値なし")
            continue
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
        saved.append(ticker)
        print(f"[JPPrices] {ticker}: {len(rows)}日ぶん upsert")
    conn.close()
    print(f"[JPPrices] 完了: {len(saved)}/{len(tickers)}銘柄")
    return saved


if __name__ == "__main__":
    # 引数で期間を指定できる（初回バックフィルは "2y" 等を渡す）
    run_jp_prices(sys.argv[1] if len(sys.argv) > 1 else "6mo")
