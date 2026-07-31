"""Build a broad US common-stock universe and cache 15 years of daily OHLCV.

The symbol directory only lists currently-listed securities, so delisted names
are absent and survivorship bias remains.  Liquidity is deliberately *not*
filtered here; the backtest applies it point-in-time so that a stock which was
liquid in 2015 and illiquid today still trades in 2015.
"""
from __future__ import annotations

import io
import pickle
import re
import sys
import urllib.request
from pathlib import Path

import pandas as pd
import yfinance as yf

SHARDS = Path("data/universe15y")
SYMBOLS = Path("data/universe_symbols.csv")

# Non-operating shells and non-common structures add noise without adding edge.
EXCLUDE_NAME = re.compile(
    r"acquisition corp|acquisition inc|acquisition compan|"
    r"warrant|right|unit|preferred|depositary|notes? due|"
    r"trust preferred|%|etf|etn|fund\b|closed end",
    re.I,
)
KEEP_NAME = re.compile(r"common stock|ordinary shares?|common shares?|class [a-c]", re.I)


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=30).read().decode()


def symbol_list() -> list[str]:
    nas = pd.read_csv(io.StringIO(_fetch(
        "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt")), sep="|")
    oth = pd.read_csv(io.StringIO(_fetch(
        "https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt")), sep="|")
    nas = nas.rename(columns={"Symbol": "sym", "Security Name": "name"})
    oth = oth.rename(columns={"NASDAQ Symbol": "sym", "Security Name": "name"})
    df = pd.concat([nas[["sym", "name", "ETF", "Test Issue"]],
                    oth[["sym", "name", "ETF", "Test Issue"]]], ignore_index=True)
    df = df.dropna(subset=["sym", "name"])
    df = df[(df.ETF == "N") & (df["Test Issue"] == "N")]
    df = df[df.name.str.contains(KEEP_NAME) & ~df.name.str.contains(EXCLUDE_NAME)]
    # Five-character NASDAQ symbols ending in W/R/U/P are warrants/rights/units/preferred.
    df = df[~df.sym.str.match(r"^[A-Z]{4}[WRUPZ]$")]
    df = df[df.sym.str.match(r"^[A-Z]{1,5}$")]
    syms = sorted(set(df.sym) | {"SPY", "QQQ", "IWM"})
    SYMBOLS.parent.mkdir(parents=True, exist_ok=True)
    pd.Series(syms, name="symbol").to_csv(SYMBOLS, index=False)
    return syms


def main() -> None:
    syms = symbol_list()
    print(f"universe candidates: {len(syms)}", flush=True)
    SHARDS.mkdir(parents=True, exist_ok=True)
    batch = 60
    for start in range(0, len(syms), batch):
        shard = SHARDS / f"shard_{start:05d}.pkl"
        if shard.exists():
            continue
        chunk = syms[start:start + batch]
        try:
            raw = yf.download(chunk, period="15y", auto_adjust=True, progress=False,
                              threads=False, group_by="ticker", timeout=45)
        except Exception as exc:  # network flakiness must not abort a 90-batch run
            print(f"batch {start} failed: {exc}", flush=True)
            continue
        out = {}
        for t in chunk:
            try:
                x = raw[t] if isinstance(raw.columns, pd.MultiIndex) else raw
                x = x[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
                if len(x) < 400:
                    continue
                x.index = pd.to_datetime(x.index).tz_localize(None)
                out[t] = x.astype("float32")
            except (KeyError, TypeError, ValueError):
                continue
        with shard.open("wb") as f:
            pickle.dump(out, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"{min(start + batch, len(syms))}/{len(syms)} usable={len(out)}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
