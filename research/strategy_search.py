"""Grid search over long-only entry rules with pure TP/SL brackets.

Annual return is roughly (trades per year) x (expectancy in R) x (risk per
trade), so the search records frequency and holding time alongside expectancy
rather than ranking on average R alone -- a rule with a huge average R on
twelve trades a year cannot compound.

Selection discipline: parameters are chosen on TRAIN and screened on VALID.
The final holdout is not scored at all unless --with-hold is passed, so a
search cannot quietly condition on the data reserved to judge it.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import pickle
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.bracket_engine import Bracket, build_features, load_shards, run_trades

RESULTS = Path("research/results/bracket")
FEATURES = Path("data/features15y.pkl")

TRAIN = (np.datetime64("2012-01-01"), np.datetime64("2019-01-01"))
VALID = (np.datetime64("2019-01-01"), np.datetime64("2023-01-01"))
HOLD = (np.datetime64("2023-01-01"), np.datetime64("2027-01-01"))
SPLITS = (("train", TRAIN), ("valid", VALID), ("hold", HOLD))


@dataclass(frozen=True)
class Rule:
    family: str
    min_ddv: float = 1e7
    min_price: float = 5.0
    regime: str = "spy200"          # "none" | "spy200" | "spy200_qqq200"
    trend: bool = True
    mom_min: float = -1.0           # minimum 126-day return
    rsi2_max: float = 100.0
    rsi14_max: float = 100.0
    ret21_max: float = 1.0
    dist_ema20_max: float = 1.0     # how far above the 20EMA price may close
    dist_ema50_min: float = -1.0
    dist_hh60_min: float = -1.0
    atr_ratio_max: float = 10.0
    vol_ratio_min: float = 0.0
    atr_pct_min: float = 0.0       # volatility tier: ATR as a share of price
    atr_pct_max: float = 1.0
    up_close: bool = False          # closed above the prior close
    strong_close: bool = False      # closed in the upper half of the day's range


def regime_series(store: dict, mode: str) -> pd.Series | None:
    if mode == "none":
        return None
    frames = []
    for t in (("SPY",) if mode == "spy200" else ("SPY", "QQQ")):
        f = store[t]
        ok = (f["close"] > f["ema200"]) & (f["ema50"] > f["ema200"])
        frames.append(pd.Series(ok, index=pd.DatetimeIndex(f["dates"])))
    return pd.concat(frames, axis=1).all(axis=1)


def _prev(a: np.ndarray) -> np.ndarray:
    """Previous bar's value, NaN at bar 0 -- np.roll would wrap the last bar."""
    out = np.empty_like(a, dtype=np.float64)
    out[0] = np.nan
    out[1:] = a[:-1]
    return out


def signal(f: dict, r: Rule, regime: np.ndarray | None) -> np.ndarray:
    c = f["close"]
    ok = np.isfinite(f["ema200"]) & np.isfinite(f["atr"]) & np.isfinite(f["ddv"])
    ok &= (f["ddv"] >= r.min_ddv) & (c >= r.min_price)
    if regime is not None:
        ok &= regime
    if r.trend:
        ok &= (c > f["ema200"]) & (f["ema50"] > f["ema200"])
    ok &= f["ret126"] >= r.mom_min
    ok &= f["rsi2"] <= r.rsi2_max
    ok &= f["rsi"] <= r.rsi14_max
    ok &= f["ret21"] <= r.ret21_max
    ok &= f["dist_ema20"] <= r.dist_ema20_max
    ok &= f["dist_ema50"] >= r.dist_ema50_min
    ok &= f["dist_hh60"] >= r.dist_hh60_min
    ok &= f["atr_ratio"] <= r.atr_ratio_max
    ok &= f["vol_ratio"] >= r.vol_ratio_min
    ok &= (f["atr_pct"] >= r.atr_pct_min) & (f["atr_pct"] <= r.atr_pct_max)
    if r.up_close:
        ok &= c > _prev(c)
    if r.strong_close:
        ok &= (c - f["low"]) > 0.5 * (f["high"] - f["low"])

    if r.family == "breakout":
        prior = _prev(f["hh20"])
        ok &= np.isfinite(prior) & (c > prior)
    elif r.family == "pullback":
        ok &= c <= f["ema20"]
    elif r.family == "meanrev":
        pass                        # carried entirely by rsi2_max / dist filters
    ok[:250] = False
    ok[-1] = False                  # the last bar has no next open to fill on
    return ok


def generate(store: dict, r: Rule) -> dict[str, np.ndarray]:
    reg = regime_series(store, r.regime)
    idx_cache: dict[tuple, np.ndarray] = {}
    out = {}
    for t, f in store.items():
        if t in ("SPY", "QQQ", "IWM"):
            continue
        rg = None
        if reg is not None:
            key = (f["dates"][0], f["dates"][-1], len(f["dates"]))
            if key not in idx_cache:
                idx_cache[key] = reg.reindex(pd.DatetimeIndex(f["dates"])).ffill().fillna(False).to_numpy()
            rg = idx_cache[key]
        out[t] = signal(f, r, rg)
    return out


def split_stats(tr: pd.DataFrame, splits=SPLITS) -> dict:
    rec: dict = {}
    last = tr.entry_date.max() if len(tr) else None
    for name, (a, b) in splits:
        # Purge: a trade opened inside the split but closed after it prices
        # the next split's data, which is exactly what the split is meant to
        # keep out.
        q = tr[(tr.entry_date >= a) & (tr.entry_date < b) & (tr.exit_date < b)]
        r = q.r
        # Clip to data actually available, or the final split's per-year
        # figures are diluted by months that were never simulated.
        end = min(b, np.datetime64(last)) if last is not None else b
        years = max((end - a) / np.timedelta64(365, "D"), 1e-9)
        rec[f"{name}_n"] = len(q)
        rec[f"{name}_per_year"] = len(q) / years
        rec[f"{name}_win"] = float((r > 0).mean()) if len(r) else np.nan
        rec[f"{name}_avg_r"] = float(r.mean()) if len(r) else np.nan
        rec[f"{name}_pf"] = (float(r[r > 0].sum() / -r[r < 0].sum())
                             if len(r) and (r < 0).any() else np.nan)
        rec[f"{name}_bars"] = float(q.bars.median()) if len(q) else np.nan
        rec[f"{name}_unres"] = float((q.status == "unresolved").mean()) if len(q) else np.nan
        rec[f"{name}_risk_pct"] = float(q.risk_pct.median()) if len(q) else np.nan
        # A fully-invested account earns 252 x (percent gain per trade) / (bars
        # per trade), so this is the number that becomes the annual return --
        # average R alone cannot rank rules that hold for different lengths or
        # risk different fractions of the position.
        gain = q.r * q.risk_pct
        rec[f"{name}_pct_per_trade"] = float(gain.mean()) if len(q) else np.nan
        rec[f"{name}_ann_est"] = (252.0 * rec[f"{name}_pct_per_trade"] / rec[f"{name}_bars"]
                                  if rec[f"{name}_bars"] else np.nan)
    return rec


# Set in the parent before forking; workers inherit the feature store by
# copy-on-write instead of paying to pickle a gigabyte per task.
_STORE: dict = {}
_EVAL_END = None
_SPLITS = SPLITS


def _evaluate_cell(task: tuple) -> dict | None:
    _, rule, br = task
    sigs = generate(_STORE, rule)
    total = sum(int(s.sum()) for s in sigs.values())
    if total < 300:
        return None
    tr = run_trades(_STORE, sigs, br, eval_end=_EVAL_END)
    if len(tr) < 100:
        return None
    return dict(family=rule.family, sl_atr=br.sl_atr, rr=br.rr, signals=total,
                rule=json.dumps(asdict(rule)), **split_stats(tr, _SPLITS))


def rule_grid() -> list[Rule]:
    g: list[Rule] = []
    # Short-term mean reversion inside an uptrend.
    for rsi2 in (5.0, 10.0, 20.0):
        for d50 in (-1.0, -0.05):
            for uc in (False, True):
                g.append(Rule("meanrev", rsi2_max=rsi2, dist_ema20_max=0.0,
                              dist_ema50_min=d50, up_close=uc, mom_min=0.0))
    # Pullback to the 20EMA with a reversal bar.
    for r21 in (1.0, -0.02, -0.05):
        for sc in (False, True):
            for mom in (-1.0, 0.0, 0.15):
                g.append(Rule("pullback", ret21_max=r21, strong_close=sc,
                              mom_min=mom, up_close=True))
    # 20-day breakout, optionally after a volatility squeeze or with volume.
    for ar in (10.0, 0.85):
        for vr in (0.0, 1.3):
            for mom in (-1.0, 0.0, 0.15):
                g.append(Rule("breakout", atr_ratio_max=ar, vol_ratio_min=vr,
                              mom_min=mom))
    # Momentum leaders bought on any shallow dip near highs.
    for hh in (-0.10, -0.05):
        for rsi14 in (100.0, 50.0):
            g.append(Rule("meanrev", dist_hh60_min=hh, rsi14_max=rsi14,
                          mom_min=0.15, dist_ema20_max=0.0, up_close=True))
    return g


def bracket_grid() -> list[Bracket]:
    # Evenly spaced so that "is this a plateau or a spike?" can be answered by
    # looking at grid neighbours.  Wide targets are included because round-trip
    # friction is a fixed fraction of notional: a 0.4% cost is fatal to a trade
    # aiming for 1% and irrelevant to one aiming for 10%.
    return [Bracket(sl_atr=s, rr=rr)
            for s in (1.0, 1.5, 2.0, 2.5, 3.0)
            for rr in (0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-tickers", type=int, default=0)
    ap.add_argument("--out", default="grid.csv")
    ap.add_argument("--features", default=str(FEATURES))
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--regime", default="spy200")
    ap.add_argument("--eval-buffer-days", type=int, default=120)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--with-hold", action="store_true",
                    help="also score the final holdout; off by default so the "
                         "search cannot condition on the data reserved to judge it")
    args = ap.parse_args()

    cache = Path(args.features)
    if cache.exists() and not args.no_cache:
        with cache.open("rb") as f:
            store = pickle.load(f)
    else:
        data = load_shards()
        print(f"loaded {len(data)} tickers", flush=True)
        store = build_features(data)
        if not args.no_cache:
            with cache.open("wb") as f:
                pickle.dump(store, f, protocol=pickle.HIGHEST_PROTOCOL)
    if args.max_tickers:
        keep = ["SPY", "QQQ"] + [t for t in store if t not in ("SPY", "QQQ")][:args.max_tickers]
        store = {t: store[t] for t in keep if t in store}
    print(f"features ready: {len(store)} tickers", flush=True)
    # Signals near the data end cannot resolve, and marking them at a rising
    # last close would pad the most recent split with unearned winners.
    eval_end = (max(f["dates"][-1] for f in store.values())
                - np.timedelta64(args.eval_buffer_days, "D"))

    splits = SPLITS if args.with_hold else SPLITS[:2]
    grid = [replace(r, regime=args.regime) for r in rule_grid()]
    brackets = bracket_grid()
    RESULTS.mkdir(parents=True, exist_ok=True)

    global _STORE, _EVAL_END, _SPLITS
    _STORE, _EVAL_END, _SPLITS = store, eval_end, splits
    tasks = [(k, rule, br) for k, rule in enumerate(grid) for br in brackets]
    print(f"evaluating {len(tasks)} configurations on {len(grid)} rules", flush=True)

    rows = []
    # fork so the feature store is shared rather than pickled to each worker.
    ctx = mp.get_context("fork")
    with ProcessPoolExecutor(max_workers=args.workers, mp_context=ctx) as ex:
        for n, rec in enumerate(ex.map(_evaluate_cell, tasks, chunksize=4), 1):
            if rec:
                rows.append(rec)
            if n % 100 == 0:
                print(f"{n}/{len(tasks)} kept={len(rows)}", flush=True)
                pd.DataFrame(rows).to_csv(RESULTS / args.out, index=False)
    pd.DataFrame(rows).to_csv(RESULTS / args.out, index=False)
    print(f"wrote {RESULTS / args.out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
