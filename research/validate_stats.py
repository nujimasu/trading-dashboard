"""Statistical gates that a grid search result has to clear to be believed.

Three questions, three tests:

1. Is the winning edge bigger than what searching this many configurations
   produces from noise alone?  Circularly shifting each ticker's signal array
   destroys the signal-to-return alignment while preserving signal count,
   autocorrelation and calendar clustering, which gives the null spread of
   average R directly.  The expected maximum of M draws from that null is the
   bar the observed best has to clear.
2. How wide is the edge's own confidence interval once trades are treated as
   the clustered, overlapping sample they are rather than as N independent
   draws?  Monthly block bootstrap answers that.
3. Is the drawdown budget actually met?  A realised max drawdown is one draw
   from a wide distribution, so the equity path is resampled and the budget is
   checked against the 95th percentile of the bad tail.
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.bracket_engine import Bracket, run_trades
from research.strategy_search import Rule, generate

RESULTS = Path("research/results/bracket")


def cluster_tstat(trades: pd.DataFrame, by: str = "M") -> dict:
    """Cluster-robust mean and t for average R, clustering on entry month.

    Trades opened in the same month share a market, so treating them as
    independent overstates precision by the square root of the design effect.
    """
    if trades.empty:
        return {}
    g = trades.assign(cl=trades.entry_date.values.astype(f"datetime64[{by}]"))
    grp = g.groupby("cl").r
    n, m = grp.size().to_numpy(float), grp.mean().to_numpy(float)
    mean = float(g.r.mean())
    G = len(n)
    if G < 3:
        return dict(avg_r=mean, n=len(g), clusters=G)
    var = float((n ** 2 * (m - mean) ** 2).sum()) / (n.sum() ** 2) * G / (G - 1)
    se = np.sqrt(var)
    naive = float(g.r.std(ddof=1) / np.sqrt(len(g)))
    return dict(avg_r=mean, n=len(g), clusters=G, se_cluster=se, se_naive=naive,
                design_effect=(se / naive) ** 2 if naive else np.nan,
                eff_n=len(g) / ((se / naive) ** 2) if naive and se else np.nan,
                t_cluster=mean / se if se else np.nan)


def block_bootstrap_ci(trades: pd.DataFrame, iters: int = 2000,
                       seed: int = 0) -> dict:
    """Percentile CI for average R, resampling whole entry months."""
    if trades.empty:
        return {}
    g = trades.assign(cl=trades.entry_date.values.astype("datetime64[M]"))
    blocks = [x.r.to_numpy() for _, x in g.groupby("cl")]
    if len(blocks) < 5:
        return {}
    rng = np.random.default_rng(seed)
    out = np.empty(iters)
    idx = np.arange(len(blocks))
    for k in range(iters):
        pick = rng.choice(idx, size=len(blocks), replace=True)
        out[k] = np.concatenate([blocks[i] for i in pick]).mean()
    return dict(ci_lo=float(np.percentile(out, 2.5)),
                ci_hi=float(np.percentile(out, 97.5)),
                p_le_zero=float((out <= 0).mean()))


def permutation_null(store: dict, rule: Rule, br: Bracket, iters: int = 200,
                     seed: int = 0, eval_end=None) -> np.ndarray:
    """Null distribution of average R from circularly shifted signals."""
    base = generate(store, rule)
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(iters):
        shifted = {}
        for t, s in base.items():
            if not s.any():
                continue
            k = int(rng.integers(260, len(s) - 260)) if len(s) > 600 else 0
            shifted[t] = np.roll(s, k)
        tr = run_trades(store, shifted, br, eval_end=eval_end)
        if len(tr):
            out.append(float(tr.r.mean()))
    return np.array(out)


def selection_threshold(null_sd: float, n_configs: int) -> float:
    """Expected best-of-M average R when every config is pure noise."""
    return null_sd * np.sqrt(2 * np.log(max(n_configs, 2)))


def dd_distribution(equity: pd.Series, iters: int = 2000, block: int = 40,
                    seed: int = 0) -> dict:
    """Stationary block bootstrap of daily returns -> drawdown percentiles."""
    r = equity.pct_change().dropna().to_numpy()
    if len(r) < block * 3:
        return {}
    rng = np.random.default_rng(seed)
    n = len(r)
    dds = np.empty(iters)
    for k in range(iters):
        path, need = [], n
        while need > 0:
            start = rng.integers(0, n)
            length = min(rng.geometric(1 / block), need)
            path.append(r.take(range(start, start + length), mode="wrap"))
            need -= length
        eq = np.cumprod(1 + np.concatenate(path))
        dds[k] = (eq / np.maximum.accumulate(eq) - 1).min()
    return dict(dd_realised=float((equity / equity.cummax() - 1).min()),
                dd_p50=float(np.percentile(dds, 50)),
                dd_p95=float(np.percentile(dds, 5)),   # 5th pct = bad tail
                p_within_30=float((dds > -0.30).mean()))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rule", required=True)
    ap.add_argument("--sl-atr", type=float, required=True)
    ap.add_argument("--rr", type=float, required=True)
    ap.add_argument("--features", default="data/features15y.pkl")
    ap.add_argument("--n-configs", type=int, required=True,
                    help="how many configurations the winner was selected from")
    ap.add_argument("--iters", type=int, default=200)
    ap.add_argument("--eval-buffer-days", type=int, default=120)
    ap.add_argument("--out", default="validation.json")
    args = ap.parse_args()

    with Path(args.features).open("rb") as f:
        store = pickle.load(f)
    rule = Rule(**json.loads(args.rule))
    br = Bracket(sl_atr=args.sl_atr, rr=args.rr)
    end = max(f["dates"][-1] for f in store.values())
    eval_end = end - np.timedelta64(args.eval_buffer_days, "D")

    trades = run_trades(store, generate(store, rule), br, eval_end=eval_end)
    train = trades[trades.entry_date < np.datetime64("2019-01-01")]
    report: dict = {"rule": json.loads(args.rule), "sl_atr": args.sl_atr,
                    "rr": args.rr, "n_configs": args.n_configs,
                    "trades_total": len(trades)}
    report["cluster_all"] = cluster_tstat(trades)
    report["cluster_train"] = cluster_tstat(train)
    report["bootstrap_all"] = block_bootstrap_ci(trades)

    null = permutation_null(store, rule, br, iters=args.iters, eval_end=eval_end)
    sd = float(null.std(ddof=1)) if len(null) > 2 else np.nan
    thr = selection_threshold(sd, args.n_configs)
    obs = float(trades.r.mean())
    # Shifted signals keep the bracket, the universe and the regime gate, so the
    # null mean is what the *geometry* earns on random dates.  Only the excess
    # over it is attributable to the entry rule, and only that excess has to
    # clear the selection bar.
    excess = obs - float(null.mean())
    report["null"] = dict(iters=len(null), mean=float(null.mean()), sd=sd,
                          p95=float(np.percentile(null, 95)), observed=obs,
                          excess_over_null=excess,
                          selection_threshold=float(thr),
                          clears_threshold=bool(excess > thr),
                          share_of_edge_from_timing=excess / obs if obs else np.nan)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / args.out).write_text(json.dumps(report, indent=2, default=float))
    print(json.dumps(report, indent=2, default=float))


if __name__ == "__main__":
    main()
