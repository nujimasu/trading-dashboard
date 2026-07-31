"""Turn signal-level edges into a fundable equity curve.

Thousands of signals compete for a handful of slots, so the ranking rule and
the concurrency limit move the result more than the entry rule does.  This
searches ranking x slots x risk-per-trade and reports the drawdown actually
lived through, so a max-DD budget can be enforced instead of assumed.
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.bracket_engine import (Bracket, Costs, RANK_FEATURES, build_features,
                                     load_shards, portfolio, price_matrix, run_trades)
from research.strategy_search import HOLD, Rule, TRAIN, VALID, generate

RESULTS = Path("research/results/bracket")


def curve_stats(eq: pd.Series, label: str) -> dict:
    if len(eq) < 2 or eq.iloc[0] <= 0:
        return {}
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1 if years > 0 else np.nan
    dd = float((eq / eq.cummax() - 1).min())
    return {f"{label}_cagr": cagr, f"{label}_dd": dd,
            f"{label}_mar": cagr / abs(dd) if dd else np.nan}


def yearly(eq: pd.Series) -> pd.Series:
    y = eq.resample("YE").last()
    out = y.pct_change()
    out.iloc[0] = y.iloc[0] / eq.iloc[0] - 1
    return out


def evaluate(trades: pd.DataFrame, cal: np.ndarray, rows: dict, px: np.ndarray,
             rank_col: str | None, ascending: bool, slots: int, risk: float,
             max_gross: float, lows: np.ndarray | None = None) -> dict:
    taken, eq, worst = portfolio(trades, cal, rows, px, risk_pct=risk,
                                 max_positions=slots, rank_col=rank_col,
                                 ascending=ascending, max_gross=max_gross, lows=lows)
    if eq.empty:
        return {}
    rec = dict(rank=rank_col or "none", asc=ascending, slots=slots, risk=risk,
               max_gross=max_gross, n=len(taken))
    rec.update(curve_stats(eq, "all"))
    # The binding constraint is a drawdown budget, so report the one that
    # includes intraday marks rather than the flattering close-only path.
    rec["all_dd_intraday"] = float((worst / worst.cummax() - 1).min())
    for name, (a, b) in (("train", TRAIN), ("valid", VALID), ("hold", HOLD)):
        sl = eq[(eq.index >= a) & (eq.index < b)]
        if len(sl) > 2:
            rec.update(curve_stats(sl, name))
    yr = yearly(eq)
    rec["worst_year"] = float(yr.min())
    rec["neg_years"] = int((yr < 0).sum())
    rec["years"] = json.dumps({str(k.year): round(float(v), 4) for k, v in yr.items()})
    if len(taken):
        rec["avg_r"] = float(taken.r.mean())
        rec["win"] = float((taken.r > 0).mean())
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rule", required=True, help="JSON dict of Rule fields")
    ap.add_argument("--sl-atr", type=float, required=True)
    ap.add_argument("--rr", type=float, required=True)
    ap.add_argument("--features", default="data/features15y.pkl")
    ap.add_argument("--out", default="portfolio.csv")
    ap.add_argument("--eval-buffer-days", type=int, default=120,
                    help="drop signals this close to the data end (censoring)")
    ap.add_argument("--slots", default="5,10,15,20,30")
    ap.add_argument("--risks", default="0.005,0.01,0.02,0.05")
    # Gross above 1.0 needs a Reg-T maintenance call modelled, and a forced
    # liquidation fires precisely when a drawdown budget is already stressed.
    # Until that is simulated, leverage is left out rather than assumed free.
    ap.add_argument("--gross", default="1.0")
    ap.add_argument("--trades-out", default="")
    args = ap.parse_args()

    with Path(args.features).open("rb") as f:
        store = pickle.load(f)
    rule = Rule(**json.loads(args.rule))
    sigs = generate(store, rule)
    end = max(f["dates"][-1] for f in store.values())
    trades = run_trades(store, sigs, Bracket(sl_atr=args.sl_atr, rr=args.rr),
                        eval_end=end - np.timedelta64(args.eval_buffer_days, "D"))
    print(f"signals={sum(int(s.sum()) for s in sigs.values())} trades={len(trades)}",
          flush=True)
    if args.trades_out:
        trades.to_csv(RESULTS / args.trades_out, index=False)

    cal = store["SPY"]["dates"]
    rows, px = price_matrix(store, cal)
    _, lows = price_matrix(store, cal, field="low")
    slots = [int(x) for x in args.slots.split(",")]
    risks = [float(x) for x in args.risks.split(",")]
    grosses = [float(x) for x in args.gross.split(",")]

    ranks: list[tuple[str | None, bool]] = [(None, False)]
    for c in RANK_FEATURES:
        ranks += [(c, False), (c, True)]

    out = []
    for rank_col, asc in ranks:
        for s in slots:
            for r in risks:
                for g in grosses:
                    rec = evaluate(trades, cal, rows, px, rank_col, asc, s, r, g, lows)
                    if rec:
                        out.append(rec)
        print(f"rank={rank_col} asc={asc} done ({len(out)} rows)", flush=True)
        pd.DataFrame(out).to_csv(RESULTS / args.out, index=False)
    pd.DataFrame(out).to_csv(RESULTS / args.out, index=False)
    print(f"wrote {RESULTS / args.out} ({len(out)} rows)")


if __name__ == "__main__":
    main()
