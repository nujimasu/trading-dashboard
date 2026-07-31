"""Pick a candidate from the grid without picking the luckiest cell.

A single best cell in a 1,000-cell search is mostly selection noise.  What
survives out of sample is a *plateau*: a cell whose grid neighbours also work.
This ranks by the worst neighbour rather than by the cell itself, which
automatically discards isolated spikes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

RESULTS = Path("research/results/bracket")
SL_GRID = (1.0, 1.5, 2.0, 2.5, 3.0)
RR_GRID = (0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0)


def neighbours(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Add the min/mean of ``metric`` over each cell's bracket neighbours."""
    si = {v: k for k, v in enumerate(SL_GRID)}
    ri = {v: k for k, v in enumerate(RR_GRID)}
    out = df.copy()
    key = out.groupby(["rule", "sl_atr", "rr"])[metric].mean()
    lo, mean, cnt = [], [], []
    for z in out.itertuples():
        a, b = si.get(z.sl_atr), ri.get(z.rr)
        vals = []
        if a is not None and b is not None:
            for da in (-1, 0, 1):
                for db in (-1, 0, 1):
                    i, j = a + da, b + db
                    if 0 <= i < len(SL_GRID) and 0 <= j < len(RR_GRID):
                        v = key.get((z.rule, SL_GRID[i], RR_GRID[j]))
                        if v is not None and np.isfinite(v):
                            vals.append(v)
        lo.append(min(vals) if vals else np.nan)
        mean.append(float(np.mean(vals)) if vals else np.nan)
        cnt.append(len(vals))
    out[f"{metric}_neigh_min"] = lo
    out[f"{metric}_neigh_mean"] = mean
    out["neigh_n"] = cnt
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", default=str(RESULTS / "grid.csv"))
    ap.add_argument("--metric", default="ann_est")
    ap.add_argument("--min-train-n", type=int, default=500)
    ap.add_argument("--min-valid-n", type=int, default=250)
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()

    d = pd.read_csv(args.grid)
    tm, vm = f"train_{args.metric}", f"valid_{args.metric}"
    ok = d[(d.train_n >= args.min_train_n) & (d.valid_n >= args.min_valid_n)].copy()
    print(f"grid rows={len(d)}  with enough trades={len(ok)}")
    if ok.empty:
        return
    ok = neighbours(ok, tm)
    ok = neighbours(ok, vm)
    # A candidate has to work on both splits and so do its neighbours, which is
    # a far harder bar than "this one cell was positive twice".
    ok["plateau"] = ok[[f"{tm}_neigh_min", f"{vm}_neigh_min"]].min(axis=1)
    surv = ok[(ok[f"{tm}_neigh_min"] > 0) & (ok[f"{vm}_neigh_min"] > 0)
              & (ok.neigh_n >= 6)]
    print(f"plateau survivors={len(surv)} ({len(surv) / len(ok):.1%} of screened)")
    cols = ["family", "sl_atr", "rr", "train_n", "train_win", "train_avg_r",
            "train_bars", tm, f"{tm}_neigh_min", "valid_n", "valid_win", vm,
            f"{vm}_neigh_min", "plateau"]
    top = (surv if len(surv) else ok).sort_values("plateau", ascending=False)
    pd.set_option("display.width", 250)
    print(top[cols].head(args.top).to_string(index=False))
    if len(top):
        best = top.iloc[0]
        (RESULTS / "candidate.json").write_text(json.dumps(
            {"rule": json.loads(best.rule), "sl_atr": float(best.sl_atr),
             "rr": float(best.rr), "n_configs": int(len(d)),
             "plateau": float(best.plateau)}, indent=2))
        print(f"\nwrote {RESULTS / 'candidate.json'}")


if __name__ == "__main__":
    main()
