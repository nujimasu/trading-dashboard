"""Walk-forward research for next-open US equity swing strategies.

This module is intentionally separate from the production signal tables.  It
downloads adjusted daily OHLCV into a local cache, generates signals using only
information known at each close, and fills them at the next session's open.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import pickle
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.static_universe import UNIQUE_TICKERS

CACHE = Path("data/research_ohlcv_5y.pkl")
_WORKER_DATA = None
_WORKER_REGIME = None


@dataclass(frozen=True)
class Variant:
    name: str
    strategy: str
    side: str
    ema_zone: float
    rsi_lo: float
    rsi_hi: float
    volume_ratio: float
    stop_lookback: int
    atr_buffer: float
    target_lookback: int
    min_rr: float
    max_hold: int
    require_reversal: bool = True
    momentum_min: float = 0.0


def indicators(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    c, h, l = d.Close, d.High, d.Low
    for n in (5, 20, 50, 200):
        d[f"ema{n}"] = c.ewm(span=n, adjust=False, min_periods=n).mean()
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    d["rsi"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    gain2 = delta.clip(lower=0).ewm(alpha=1 / 2, adjust=False, min_periods=2).mean()
    loss2 = (-delta.clip(upper=0)).ewm(alpha=1 / 2, adjust=False, min_periods=2).mean()
    d["rsi2"] = 100 - 100 / (1 + gain2 / loss2.replace(0, np.nan))
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    d["atr"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    d["vol20"] = d.Volume.rolling(20).mean()
    d["vol3"] = d.Volume.rolling(3).mean()
    return d


def download(period: str, limit: int | None = None, refresh: bool = False) -> dict[str, pd.DataFrame]:
    if CACHE.exists() and not refresh:
        with CACHE.open("rb") as f:
            return pickle.load(f)
    tickers = list(dict.fromkeys(["SPY", "QQQ"] + UNIQUE_TICKERS))
    if limit:
        tickers = tickers[: max(limit, 2)]
    out: dict[str, pd.DataFrame] = {}
    batch_size = 40
    for start in range(0, len(tickers), batch_size):
        batch = tickers[start:start + batch_size]
        raw = yf.download(batch, period=period, auto_adjust=True, progress=False,
                          threads=False, group_by="ticker", timeout=30)
        for t in batch:
            try:
                x = raw[t] if isinstance(raw.columns, pd.MultiIndex) else raw
                x = x[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
                if len(x) >= 300:
                    x.index = pd.to_datetime(x.index).tz_localize(None)
                    out[t] = indicators(x.astype(float))
            except (KeyError, TypeError, ValueError):
                continue
        print(f"downloaded {min(start + batch_size, len(tickers))}/{len(tickers)}; usable={len(out)}")
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with CACHE.open("wb") as f:
        pickle.dump(out, f, protocol=pickle.HIGHEST_PROTOCOL)
    return out


def market_regime(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames = []
    for t in ("SPY", "QQQ"):
        d = data[t]
        frames.append((d.Close > d.ema200).rename(t))
    r = pd.concat(frames, axis=1).ffill()
    r["bull"] = r.any(axis=1)
    r["bear"] = ~r.any(axis=1)
    return r


def simulate_one(d: pd.DataFrame, i: int, side: str, stop: float, target: float,
                 max_hold: int, cost_bps: float) -> dict | None:
    if i + 1 >= len(d):
        return None
    entry_i = i + 1
    entry = float(d.Open.iloc[entry_i])
    # A gap through the planned stop is not a valid new trade.
    risk = entry - stop if side == "long" else stop - entry
    reward = target - entry if side == "long" else entry - target
    if not np.isfinite(risk) or risk <= 0 or reward <= 0:
        return None
    rr = reward / risk
    exit_px, status, held = None, "time", 0
    for j in range(entry_i, min(entry_i + max_hold, len(d))):
        held = j - entry_i + 1
        o, h, l = map(float, (d.Open.iloc[j], d.High.iloc[j], d.Low.iloc[j]))
        if side == "long":
            if o <= stop: exit_px, status = o, "gap_stop"
            elif l <= stop: exit_px, status = stop, "stop"
            elif o >= target: exit_px, status = o, "gap_target"
            elif h >= target: exit_px, status = target, "target"
        else:
            if o >= stop: exit_px, status = o, "gap_stop"
            elif h >= stop: exit_px, status = stop, "stop"
            elif o <= target: exit_px, status = o, "gap_target"
            elif l <= target: exit_px, status = target, "target"
        if exit_px is not None:
            break
    if exit_px is None:
        j = min(entry_i + max_hold - 1, len(d) - 1)
        exit_px = float(d.Close.iloc[j])
        held = j - entry_i + 1
    gross_r = ((exit_px - entry) if side == "long" else (entry - exit_px)) / risk
    # Round-trip friction expressed in R; default 10 bps per side.
    net_r = gross_r - (2 * cost_bps / 10_000 * entry / risk)
    return {"entry_date": d.index[entry_i], "exit_date": d.index[j], "entry": entry,
            "exit": exit_px, "risk": risk, "planned_rr": rr, "r": net_r,
            "status": status, "held": held}


def simulate_reversion(d: pd.DataFrame, i: int, side: str, stop: float,
                       max_hold: int, cost_bps: float) -> dict | None:
    if i + 1 >= len(d):
        return None
    entry_i = i + 1
    entry = float(d.Open.iloc[entry_i])
    risk = entry - stop if side == "long" else stop - entry
    if risk <= 0:
        return None
    exit_px = None
    status, j = "time", entry_i
    for j in range(entry_i, min(entry_i + max_hold, len(d))):
        o, h, l, c, e5 = map(float, (d.Open.iloc[j], d.High.iloc[j], d.Low.iloc[j],
                                      d.Close.iloc[j], d.ema5.iloc[j]))
        if side == "long":
            if o <= stop: exit_px, status = o, "gap_stop"
            elif l <= stop: exit_px, status = stop, "stop"
        else:
            if o >= stop: exit_px, status = o, "gap_stop"
            elif h >= stop: exit_px, status = stop, "stop"
        if exit_px is not None:
            break
        recovered = c > e5 if side == "long" else c < e5
        if recovered and j + 1 < len(d):
            j += 1
            exit_px, status = float(d.Open.iloc[j]), "ema5_recovery"
            break
    if exit_px is None:
        exit_px = float(d.Close.iloc[j])
    gross_r = ((exit_px - entry) if side == "long" else (entry - exit_px)) / risk
    net_r = gross_r - (2 * cost_bps / 10_000 * entry / risk)
    return {"entry_date": d.index[entry_i], "exit_date": d.index[j], "entry": entry,
            "exit": exit_px, "risk": risk, "planned_rr": np.nan, "r": net_r,
            "status": status, "held": j - entry_i + 1}


def run_variant(data: dict[str, pd.DataFrame], regime: pd.DataFrame, v: Variant,
                cost_bps: float) -> pd.DataFrame:
    trades = []
    for ticker, d in data.items():
        if ticker in ("SPY", "QQQ"):
            continue
        reg = regime.reindex(d.index).ffill()
        O = d["Open"].to_numpy(dtype=float)
        H = d["High"].to_numpy(dtype=float)
        L = d["Low"].to_numpy(dtype=float)
        C = d["Close"].to_numpy(dtype=float)
        E20 = d["ema20"].to_numpy(dtype=float)
        E50 = d["ema50"].to_numpy(dtype=float)
        E200 = d["ema200"].to_numpy(dtype=float)
        RSI = d["rsi"].to_numpy(dtype=float)
        RSI2 = d["rsi2"].to_numpy(dtype=float)
        ATR = d["atr"].to_numpy(dtype=float)
        VOL20 = d["vol20"].to_numpy(dtype=float)
        VOL3 = d["vol3"].to_numpy(dtype=float)
        BULL = reg["bull"].fillna(False).to_numpy(dtype=bool)
        BEAR = reg["bear"].fillna(False).to_numpy(dtype=bool)
        start = max(201, v.target_lookback + 1, v.stop_lookback + 1)
        next_free = start
        for i in range(start, len(d) - 1):
            if i < next_free or not np.isfinite(E200[i]):
                continue
            c, o, h, l = C[i], O[i], H[i], L[i]
            e20, e50, e200 = E20[i], E50[i], E200[i]
            rsi, atr = RSI[i], ATR[i]
            if not np.isfinite(rsi + atr) or VOL20[i] < 1_000_000:
                continue
            vol_ok = (VOL3[i] <= VOL20[i] * v.volume_ratio if v.strategy == "pullback"
                      else VOL3[i] >= VOL20[i] * v.volume_ratio)
            reversal_long = c > o and c > H[i - 1]
            reversal_short = c < o and c < L[i - 1]
            if v.strategy == "reversion":
                if v.side == "long":
                    signal = (c > e200 and e50 > e200 and BULL[i]
                              and RSI2[i] <= v.rsi_lo and c < C[i - 1])
                    stop = float(np.min(L[i - v.stop_lookback + 1:i + 1]) - v.atr_buffer * atr)
                else:
                    signal = (c < e200 and e50 < e200 and BEAR[i]
                              and RSI2[i] >= v.rsi_hi and c > C[i - 1])
                    stop = float(np.max(H[i - v.stop_lookback + 1:i + 1]) + v.atr_buffer * atr)
                target = e20
            elif v.strategy == "retest":
                recent = range(max(v.target_lookback, i - 5), i)
                if v.side == "long":
                    breaks = [(k, float(np.max(H[k - v.target_lookback:k]))) for k in recent
                              if C[k] > np.max(H[k - v.target_lookback:k])]
                    if not breaks:
                        continue
                    k, level = breaks[-1]
                    mom = C[k] / C[k - 126] - 1 if k >= 126 else 0.0
                    retest = L[i] <= level * (1 + v.ema_zone) and c >= level * (1 - v.ema_zone)
                    signal = (c > e200 and e50 > e200 and BULL[i] and vol_ok and retest
                              and c > o and c > C[i - 1] and mom >= v.momentum_min)
                    base_low = float(np.min(L[k - v.stop_lookback:k]))
                    stop = float(np.min(L[i - v.stop_lookback + 1:i + 1]) - v.atr_buffer * atr)
                    target = float(level + (level - base_low))
                else:
                    breaks = [(k, float(np.min(L[k - v.target_lookback:k]))) for k in recent
                              if C[k] < np.min(L[k - v.target_lookback:k])]
                    if not breaks:
                        continue
                    k, level = breaks[-1]
                    mom = C[k] / C[k - 126] - 1 if k >= 126 else 0.0
                    retest = H[i] >= level * (1 - v.ema_zone) and c <= level * (1 + v.ema_zone)
                    signal = (c < e200 and e50 < e200 and BEAR[i] and vol_ok and retest
                              and c < o and c < C[i - 1] and mom <= -v.momentum_min)
                    base_high = float(np.max(H[k - v.stop_lookback:k]))
                    stop = float(np.max(H[i - v.stop_lookback + 1:i + 1]) + v.atr_buffer * atr)
                    target = float(level - (base_high - level))
            elif v.strategy == "breakout":
                prior_high = float(np.max(H[i - v.target_lookback:i]))
                prior_low = float(np.min(L[i - v.stop_lookback:i]))
                mom = C[i] / C[i - 126] - 1 if i >= 126 else 0.0
                if v.side == "long":
                    signal = (c > e200 and e50 > e200 and BULL[i] and vol_ok
                              and c > prior_high and mom >= v.momentum_min)
                    stop = float(prior_low - v.atr_buffer * atr)
                    target = float(prior_high + (prior_high - prior_low))
                else:
                    prior_high = float(np.max(H[i - v.stop_lookback:i]))
                    prior_low = float(np.min(L[i - v.target_lookback:i]))
                    signal = (c < e200 and e50 < e200 and BEAR[i] and vol_ok
                              and c < prior_low and mom <= -v.momentum_min)
                    stop = float(prior_high + v.atr_buffer * atr)
                    target = float(prior_low - (prior_high - prior_low))
            elif v.side == "long":
                trend = c > e200 and e50 > e200 and BULL[i]
                zone = min(abs(c / e20 - 1), abs(c / e50 - 1)) <= v.ema_zone
                signal = trend and zone and vol_ok and v.rsi_lo <= rsi <= v.rsi_hi
                signal &= reversal_long if v.require_reversal else True
                stop = float(np.min(L[i - v.stop_lookback + 1:i + 1]) - v.atr_buffer * atr)
                # Prior resistance excludes the signal bar to avoid defining a target with future data.
                target = float(np.max(H[i - v.target_lookback:i]))
            else:
                trend = c < e200 and e50 < e200 and BEAR[i]
                zone = min(abs(c / e20 - 1), abs(c / e50 - 1)) <= v.ema_zone
                signal = trend and zone and vol_ok and v.rsi_lo <= rsi <= v.rsi_hi
                signal &= reversal_short if v.require_reversal else True
                stop = float(np.max(H[i - v.stop_lookback + 1:i + 1]) + v.atr_buffer * atr)
                target = float(np.min(L[i - v.target_lookback:i]))
            if not signal:
                continue
            tr = (simulate_reversion(d, i, v.side, stop, v.max_hold, cost_bps)
                  if v.strategy == "reversion"
                  else simulate_one(d, i, v.side, stop, target, v.max_hold, cost_bps))
            if tr and (v.strategy == "reversion" or tr["planned_rr"] >= v.min_rr):
                tr.update(ticker=ticker, side=v.side, signal_date=d.index[i], variant=v.name,
                          signal_rsi2=float(RSI2[i]),
                          momentum_126=float(C[i] / C[i - 126] - 1) if i >= 126 else np.nan,
                          dollar_volume=float(C[i] * VOL20[i]))
                trades.append(tr)
                next_free = i + tr["held"] + 1
    return pd.DataFrame(trades)


def summarize(trades: pd.DataFrame, split: str) -> dict:
    x = trades[trades.entry_date >= pd.Timestamp(split)] if len(trades) else trades
    if not len(x):
        return {"n": 0}
    r = x.r.astype(float)
    eq = r.cumsum()
    dd = eq - eq.cummax()
    return {"n": len(x), "win_rate": round(float((r > 0).mean()), 4),
            "avg_r": round(float(r.mean()), 4), "median_r": round(float(r.median()), 4),
            "profit_factor": round(float(r[r > 0].sum() / -r[r < 0].sum()), 3),
            "max_dd_r": round(float(dd.min()), 2), "avg_hold": round(float(x.held.mean()), 1),
            "avg_planned_rr": round(float(x.planned_rr.mean()), 2)}


def _init_worker() -> None:
    global _WORKER_DATA, _WORKER_REGIME
    with CACHE.open("rb") as f:
        _WORKER_DATA = pickle.load(f)
    # Cached OHLCV may have been produced by an older indicator schema.
    for ticker, frame in list(_WORKER_DATA.items()):
        if "rsi2" not in frame.columns or "ema5" not in frame.columns:
            _WORKER_DATA[ticker] = indicators(frame[["Open", "High", "Low", "Close", "Volume"]])
    _WORKER_REGIME = market_regime(_WORKER_DATA)


def _test_variant(payload: tuple[Variant, float, str]) -> tuple[dict, pd.DataFrame]:
    v, cost_bps, split = payload
    tr = run_variant(_WORKER_DATA, _WORKER_REGIME, v, cost_bps)
    ins = tr[tr.entry_date < pd.Timestamp(split)] if len(tr) else tr
    oos = tr[tr.entry_date >= pd.Timestamp(split)] if len(tr) else tr
    row = {**asdict(v),
           **{f"is_{k}": val for k, val in summarize(ins, "1900-01-01").items()},
           **{f"oos_{k}": val for k, val in summarize(oos, "1900-01-01").items()}}
    return row, tr


def variants() -> list[Variant]:
    out = []
    for side in ("long", "short"):
        thresholds = (2, 5, 10)
        for threshold in thresholds:
            for atr_buffer in (.5, 1.0, 1.5):
                for max_hold in (5, 10):
                    stop_n = 20
                    name = f"reversion_{side}_rsi2_{threshold}_stop{stop_n}_atr{atr_buffer}_hold{max_hold}"
                    out.append(Variant(name, "reversion", side, 0, threshold, 100-threshold,
                                       1.0, stop_n, atr_buffer, 20, 0, max_hold, False, 0))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", default="5y")
    ap.add_argument("--split", default="2025-01-01")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--cost-bps", type=float, default=10.0)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    data = download(args.period, args.limit, args.refresh)
    rows, all_trades = [], []
    vs = variants()
    payloads = [(v, args.cost_bps, args.split) for v in vs]
    with ProcessPoolExecutor(max_workers=args.workers, initializer=_init_worker) as pool:
      for n, (row, tr) in enumerate(pool.map(_test_variant, payloads), 1):
        rows.append(row)
        if len(tr): all_trades.append(tr)
        if n % 8 == 0: print(f"tested {n}/{len(vs)}")
    results = pd.DataFrame(rows)
    results["oos_score"] = results.oos_avg_r.fillna(-9) * np.sqrt(results.oos_n.fillna(0).clip(lower=1))
    results = results.sort_values(["oos_score", "oos_avg_r"], ascending=False)
    Path("research/results").mkdir(parents=True, exist_ok=True)
    results.to_csv("research/results/variant_summary.csv", index=False)
    if all_trades:
        pd.concat(all_trades, ignore_index=True).to_csv("research/results/all_trades.csv", index=False)
    meta = {"split": args.split, "cost_bps_per_side": args.cost_bps,
            "symbols": len(data), "variants": len(results)}
    Path("research/results/run_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(results.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
