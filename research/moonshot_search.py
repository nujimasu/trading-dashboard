"""Search explicitly aimed at a 300%/yr target, with the drawdown budget lifted.

The arithmetic that governs a fully-invested account is

    annual return  ~  252 / bars_held  x  avg_R  x  stop_distance_as_%_of_price

so the three levers are holding period, expectancy, and *volatility of the
instrument*.  The earlier search capped stop distance at 15% of price, which
silently excluded every high-volatility name once the stop widened past a
couple of ATRs.  This sweep opens that cap and walks the volatility tiers, then
does the same over leveraged ETFs, where the instrument itself supplies 3x.

Nothing here assumes the answer is reachable.  Drawdown is reported, never
constrained, so the cost of each step toward the target stays visible.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import pickle
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.bracket_engine import (Bracket, build_features, load_shards,
                                     run_trades)
from research.strategy_search import Rule, generate, split_stats, SPLITS

RESULTS = Path("research/results/moonshot")

# Volatility tiers by ATR as a share of price, measured at the signal bar.
TIERS = (("t1_calm", 0.000, 0.020), ("t2_normal", 0.020, 0.030),
         ("t3_active", 0.030, 0.045), ("t4_hot", 0.045, 0.070),
         ("t5_wild", 0.070, 0.200))

_STORE: dict = {}
_EVAL_END = None


def _cell(task: tuple) -> dict | None:
    tier, rule, br = task
    sigs = generate(_STORE, rule)
    total = sum(int(s.sum()) for s in sigs.values())
    if total < 200:
        return None
    tr = run_trades(_STORE, sigs, br, eval_end=_EVAL_END)
    if len(tr) < 80:
        return None
    return dict(tier=tier, family=rule.family, sl_atr=br.sl_atr, rr=br.rr,
                signals=total, rule=json.dumps(asdict(rule)),
                **split_stats(tr, SPLITS[:2]))


def families(base: dict) -> list[Rule]:
    """A small, deliberately coarse set: this sweep is about the tiers."""
    return [
        Rule("pullback", up_close=True, strong_close=True, mom_min=0.0, **base),
        Rule("pullback", up_close=True, mom_min=0.15, **base),
        Rule("breakout", mom_min=0.0, **base),
        Rule("breakout", mom_min=0.15, vol_ratio_min=1.3, **base),
        Rule("meanrev", rsi2_max=10.0, dist_ema20_max=0.0, mom_min=0.0, **base),
        Rule("meanrev", dist_hh60_min=-0.10, mom_min=0.15,
             dist_ema20_max=0.0, up_close=True, **base),
    ]


def brackets() -> list[Bracket]:
    return [Bracket(sl_atr=s, rr=rr)
            for s in (1.0, 1.5, 2.0, 3.0)
            for rr in (0.5, 1.0, 2.0, 3.0, 4.0, 6.0)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", default="data/features15y.pkl")
    ap.add_argument("--shards", default="")
    ap.add_argument("--out", default="tiers.csv")
    ap.add_argument("--regime", default="spy200")
    ap.add_argument("--min-ddv", type=float, default=1e7)
    ap.add_argument("--workers", type=int, default=9)
    ap.add_argument("--eval-buffer-days", type=int, default=120)
    ap.add_argument("--no-tiers", action="store_true",
                    help="one pass over the whole universe instead of by tier")
    args = ap.parse_args()

    if args.shards:
        import research.bracket_engine as be
        be.SHARDS = Path(args.shards)
        store = build_features(load_shards(min_dollar_volume=args.min_ddv))
    else:
        with open(args.features, "rb") as f:
            store = pickle.load(f)
    print(f"universe: {len(store)} tickers", flush=True)

    global _STORE, _EVAL_END
    _STORE = store
    _EVAL_END = (max(f["dates"][-1] for f in store.values())
                 - np.timedelta64(args.eval_buffer_days, "D"))

    tiers = (("all", 0.0, 1.0),) if args.no_tiers else TIERS
    tasks = []
    for name, lo, hi in tiers:
        base = dict(regime=args.regime, min_ddv=args.min_ddv,
                    atr_pct_min=lo, atr_pct_max=hi)
        for rule in families(base):
            for br in brackets():
                tasks.append((name, rule, br))
    print(f"{len(tasks)} configurations", flush=True)

    RESULTS.mkdir(parents=True, exist_ok=True)
    rows = []
    with ProcessPoolExecutor(max_workers=args.workers,
                             mp_context=mp.get_context("fork")) as ex:
        for n, rec in enumerate(ex.map(_cell, tasks, chunksize=2), 1):
            if rec:
                rows.append(rec)
            if n % 50 == 0:
                print(f"{n}/{len(tasks)} kept={len(rows)}", flush=True)
                pd.DataFrame(rows).to_csv(RESULTS / args.out, index=False)
    pd.DataFrame(rows).to_csv(RESULTS / args.out, index=False)
    print(f"wrote {RESULTS / args.out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
