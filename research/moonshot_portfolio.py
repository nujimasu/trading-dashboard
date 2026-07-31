"""Push concentration and leverage toward a 300%/yr target and price the cost.

At this end of the risk curve a single realised CAGR is close to meaningless:
the same edge can produce a tenfold account or a wipeout depending on the order
the trades arrive in.  So every configuration is also resampled -- stationary
blocks of daily returns, which preserve the clustering of losses -- to report
the spread of outcomes and the probability of ruin alongside the point estimate.
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
from research.bracket_engine import (Bracket, RANK_FEATURES, portfolio,
                                     price_matrix, run_trades)
from research.strategy_search import Rule, generate

RESULTS = Path("research/results/moonshot")
RUIN = 0.10          # equity below a tenth of its start is not recoverable


def resample_paths(eq: pd.Series, iters: int = 1500, block: int = 40,
                   seed: int = 0) -> dict:
    """Stationary block bootstrap -> spread of outcomes, not a single path."""
    r = eq.pct_change().dropna().to_numpy()
    r = r[np.isfinite(r)]
    if len(r) < block * 3:
        return {}
    rng = np.random.default_rng(seed)
    n = len(r)
    years = len(r) / 252.0
    finals, dds, ruined = np.empty(iters), np.empty(iters), 0
    for k in range(iters):
        parts, need = [], n
        while need > 0:
            start = rng.integers(0, n)
            length = min(int(rng.geometric(1 / block)), need)
            parts.append(r.take(range(start, start + length), mode="wrap"))
            need -= length
        path = np.cumprod(1 + np.concatenate(parts))
        finals[k] = path[-1]
        dds[k] = (path / np.maximum.accumulate(path) - 1).min()
        if path.min() <= RUIN:
            ruined += 1
    cagr = finals ** (1 / years) - 1
    return dict(
        boot_cagr_p05=float(np.percentile(cagr, 5)),
        boot_cagr_p50=float(np.percentile(cagr, 50)),
        boot_cagr_p95=float(np.percentile(cagr, 95)),
        boot_dd_p50=float(np.percentile(dds, 50)),
        boot_dd_p05=float(np.percentile(dds, 5)),
        p_ruin=ruined / iters,
        p_hit_300=float((cagr >= 3.0).mean()),
        p_hit_50=float((cagr >= 0.5).mean()),
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rule", required=True)
    ap.add_argument("--sl-atr", type=float, required=True)
    ap.add_argument("--rr", type=float, required=True)
    ap.add_argument("--features", default="data/features15y.pkl")
    ap.add_argument("--shards", default="")
    ap.add_argument("--out", default="moonshot_portfolio.csv")
    ap.add_argument("--slots", default="1,2,3,5,10")
    ap.add_argument("--risks", default="0.02,0.05,0.10,0.20,0.30")
    ap.add_argument("--gross", default="1.0,2.0,3.0,4.0")
    ap.add_argument("--participation", type=float, default=0.002)
    ap.add_argument("--eval-buffer-days", type=int, default=120)
    ap.add_argument("--bootstrap-top", type=int, default=12)
    args = ap.parse_args()

    if args.shards:
        import research.bracket_engine as be
        from research.bracket_engine import build_features, load_shards
        be.SHARDS = Path(args.shards)
        store = build_features(load_shards(min_dollar_volume=1e7))
    else:
        with open(args.features, "rb") as f:
            store = pickle.load(f)
    rule = Rule(**json.loads(args.rule))
    end = max(f["dates"][-1] for f in store.values())
    trades = run_trades(store, generate(store, rule),
                        Bracket(sl_atr=args.sl_atr, rr=args.rr),
                        eval_end=end - np.timedelta64(args.eval_buffer_days, "D"))
    print(f"trades={len(trades)}", flush=True)
    if trades.empty:
        return

    cal = store["SPY"]["dates"] if "SPY" in store else max(
        (f["dates"] for f in store.values()), key=len)
    rows_idx, px = price_matrix(store, cal)
    _, lows = price_matrix(store, cal, field="low")

    out = []
    ranks = [(None, False)] + [(c, a) for c in ("ret126", "ret252", "atr_pct",
                                                "rsi2", "dist_hh60")
                               for a in (False, True)]
    for rank_col, asc in ranks:
        for slots in [int(x) for x in args.slots.split(",")]:
            for risk in [float(x) for x in args.risks.split(",")]:
                for gross in [float(x) for x in args.gross.split(",")]:
                    taken, eq, worst = portfolio(
                        trades, cal, rows_idx, px, risk_pct=risk,
                        max_positions=slots, rank_col=rank_col, ascending=asc,
                        max_gross=gross, lows=lows,
                        participation=args.participation)
                    if eq.empty or len(taken) < 30:
                        continue
                    eq = eq[eq.index >= pd.Timestamp("2012-01-03")]
                    if len(eq) < 500 or eq.iloc[0] <= 0:
                        continue
                    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
                    survived = eq.iloc[-1] > 0
                    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1 if survived else -1.0
                    w = worst[worst.index >= pd.Timestamp("2012-01-03")]
                    out.append(dict(
                        rank=rank_col or "none", asc=asc, slots=slots,
                        risk=risk, gross=gross, n=len(taken), cagr=cagr,
                        dd=float((eq / eq.cummax() - 1).min()),
                        dd_intraday=float((w / w.cummax() - 1).min()),
                        final_x=float(eq.iloc[-1] / eq.iloc[0]),
                        wiped=bool(eq.min() <= eq.iloc[0] * RUIN)))
        print(f"rank={rank_col} asc={asc} ({len(out)} rows)", flush=True)

    d = pd.DataFrame(out)
    RESULTS.mkdir(parents=True, exist_ok=True)
    d.to_csv(RESULTS / args.out, index=False)
    print(f"wrote {RESULTS / args.out} ({len(d)} rows)")
    if d.empty:
        return

    # Re-run the strongest survivors to attach an outcome distribution.
    top = d[~d.wiped].sort_values("cagr", ascending=False).head(args.bootstrap_top)
    boots = []
    for z in top.itertuples():
        _, eq, _ = portfolio(trades, cal, rows_idx, px, risk_pct=z.risk,
                             max_positions=z.slots,
                             rank_col=None if z.rank == "none" else z.rank,
                             ascending=z.asc, max_gross=z.gross, lows=lows,
                             participation=args.participation)
        eq = eq[eq.index >= pd.Timestamp("2012-01-03")]
        b = resample_paths(eq)
        if b:
            boots.append({**{k: getattr(z, k) for k in
                             ("rank", "asc", "slots", "risk", "gross", "cagr",
                              "dd_intraday", "final_x")}, **b})
    bd = pd.DataFrame(boots)
    bd.to_csv(RESULTS / args.out.replace(".csv", "_boot.csv"), index=False)
    print(f"wrote bootstrap ({len(bd)} rows)")


if __name__ == "__main__":
    main()
