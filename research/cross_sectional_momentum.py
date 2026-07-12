"""Portfolio-level cross-sectional momentum swing research.

Signals are formed at the close and filled at the next open.  Selection is
cross-sectional, position capacity is enforced chronologically, and exits use
market structure (swing stop + EMA close trailing) rather than a fixed R target.
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.swing_strategy_research import CACHE, indicators


@dataclass(frozen=True)
class Config:
    formation: int
    skip: int
    breakout: int
    stop_lookback: int
    atr_buffer: float
    trail_ema: int
    max_hold: int
    rank_pct: float

    @property
    def name(self) -> str:
        return (f"xmom_f{self.formation}_skip{self.skip}_b{self.breakout}_"
                f"s{self.stop_lookback}_atr{self.atr_buffer}_ema{self.trail_ema}")


def load_data() -> dict[str, pd.DataFrame]:
    with CACHE.open("rb") as f:
        raw = pickle.load(f)
    out = {}
    for t, d in raw.items():
        needed = {"ema10", "ema20", "ema50", "ema200", "atr", "vol20"}
        x = d[["Open", "High", "Low", "Close", "Volume"]].copy()
        x = indicators(x)
        x["ema10"] = x.Close.ewm(span=10, adjust=False, min_periods=10).mean()
        if len(x) >= 300 and needed.issubset(x.columns):
            out[t] = x
    return out


def aligned_panels(data: dict[str, pd.DataFrame]):
    closes = pd.concat({t: d.Close for t, d in data.items()}, axis=1).sort_index()
    return closes


def regime_series(data: dict[str, pd.DataFrame], dates: pd.Index) -> tuple[pd.Series, pd.Series]:
    flags = []
    for t in ("SPY", "QQQ"):
        d = data[t]
        flags.append((d.Close > d.ema200).rename(t))
    r = pd.concat(flags, axis=1).reindex(dates).ffill()
    bull = r.any(axis=1).fillna(False)
    bear = (~r.any(axis=1)).fillna(False)
    return bull, bear


def exit_trade(d: pd.DataFrame, signal_i: int, side: str, stop: float,
               trail_col: str, max_hold: int, cost_bps: float) -> dict | None:
    e = signal_i + 1
    if e >= len(d):
        return None
    entry = float(d.Open.iloc[e])
    risk = entry - stop if side == "long" else stop - entry
    if risk <= 0 or risk / entry > .15:
        return None
    exit_px = None
    status = "time"
    j = e
    pending_trail = False
    mfe_r = 0.0
    for j in range(e, min(e + max_hold, len(d))):
        o, h, l, c = map(float, (d.Open.iloc[j], d.High.iloc[j], d.Low.iloc[j], d.Close.iloc[j]))
        if pending_trail:
            exit_px, status = o, "ema_trail"
            break
        if side == "long":
            mfe_r = max(mfe_r, (h - entry) / risk)
            if o <= stop: exit_px, status = o, "gap_stop"
            elif l <= stop: exit_px, status = stop, "stop"
            elif c < float(d[trail_col].iloc[j]): pending_trail = True
        else:
            mfe_r = max(mfe_r, (entry - l) / risk)
            if o >= stop: exit_px, status = o, "gap_stop"
            elif h >= stop: exit_px, status = stop, "stop"
            elif c > float(d[trail_col].iloc[j]): pending_trail = True
        if exit_px is not None:
            break
    if exit_px is None:
        exit_px = float(d.Close.iloc[j])
    gross_r = ((exit_px - entry) if side == "long" else (entry - exit_px)) / risk
    net_r = gross_r - 2 * cost_bps / 10_000 * entry / risk
    return {"entry_date": d.index[e], "exit_date": d.index[j], "entry": entry,
            "exit": exit_px, "risk": risk, "r": net_r, "mfe_r": mfe_r,
            "status": status, "days": j - e + 1}


def candidates(data: dict[str, pd.DataFrame], closes: pd.DataFrame, cfg: Config,
               cost_bps: float) -> pd.DataFrame:
    momentum = closes.shift(cfg.skip) / closes.shift(cfg.formation) - 1
    ranks = momentum.rank(axis=1, pct=True)
    ranks = ranks.where(momentum.count(axis=1).ge(100), np.nan)
    bull, bear = regime_series(data, closes.index)
    trades = []
    trail_col = f"ema{cfg.trail_ema}"
    for ticker, d in data.items():
        if ticker in ("SPY", "QQQ"):
            continue
        rank = ranks[ticker].reindex(d.index)
        bup = bull.reindex(d.index).ffill().fillna(False)
        bdn = bear.reindex(d.index).ffill().fillna(False)
        C = d.Close.to_numpy(float); H = d.High.to_numpy(float); L = d.Low.to_numpy(float)
        E50 = d.ema50.to_numpy(float); E200 = d.ema200.to_numpy(float)
        ATR = d.atr.to_numpy(float); VOL20 = d.vol20.to_numpy(float); V = d.Volume.to_numpy(float)
        start = max(205, cfg.formation + 1, cfg.breakout + 1, cfg.stop_lookback + 1)
        for i in range(start, len(d) - 1):
            q = rank.iloc[i]
            if not np.isfinite(q) or VOL20[i] < 1_000_000 or C[i] * VOL20[i] < 20_000_000:
                continue
            vol_confirm = V[i] >= .8 * VOL20[i]
            side = None
            if (q >= 1 - cfg.rank_pct and bup.iloc[i] and C[i] > E200[i] and E50[i] > E200[i]
                    and C[i] > np.max(H[i-cfg.breakout:i]) and vol_confirm):
                side = "long"
                stop = float(np.min(L[i-cfg.stop_lookback+1:i+1]) - cfg.atr_buffer * ATR[i])
            elif (q <= cfg.rank_pct and bdn.iloc[i] and C[i] < E200[i] and E50[i] < E200[i]
                    and C[i] < np.min(L[i-cfg.breakout:i]) and vol_confirm):
                side = "short"
                stop = float(np.max(H[i-cfg.stop_lookback+1:i+1]) + cfg.atr_buffer * ATR[i])
            if side is None:
                continue
            tr = exit_trade(d, i, side, stop, trail_col, cfg.max_hold, cost_bps)
            if tr:
                tr.update(ticker=ticker, side=side, signal_date=d.index[i], rank=float(q),
                          momentum=float(momentum[ticker].reindex(d.index).iloc[i]), config=cfg.name)
                trades.append(tr)
    return pd.DataFrame(trades)


def portfolio(trades: pd.DataFrame, max_positions: int, risk_fraction: float,
              split: str) -> dict:
    if trades.empty:
        return {"n": 0}
    # Strongest longs and weakest shorts first.  Momentum magnitude breaks ties.
    x = trades.copy()
    x["priority"] = np.where(x.side.eq("long"), x["rank"], 1 - x["rank"])
    x = x.sort_values(["entry_date", "priority", "momentum"], ascending=[True, False, False])
    active = []
    accepted = []
    for z in x.itertuples():
        active = [a for a in active if a[0] > z.entry_date]
        active_tickers = {a[1] for a in active}
        if len(active) >= max_positions or z.ticker in active_tickers:
            continue
        active.append((z.exit_date, z.ticker))
        accepted.append(z)
    a = pd.DataFrame(accepted)
    if a.empty:
        return {"n": 0}
    def stats(part):
        if part.empty: return {"n": 0}
        rets = risk_fraction * part.r.to_numpy(float)
        eq = np.cumprod(np.maximum(.01, 1 + rets))
        dd = eq / np.maximum.accumulate(eq) - 1
        years = max((part.exit_date.max() - part.entry_date.min()).days / 365.25, .25)
        return {"n": len(part), "win_rate": float((part.r > 0).mean()),
                "avg_r": float(part.r.mean()), "pf": float(part.loc[part.r>0,"r"].sum() / -part.loc[part.r<0,"r"].sum()),
                "cagr": float(eq[-1] ** (1/years) - 1), "max_dd": float(dd.min()),
                "ending_equity": float(eq[-1])}
    cut = pd.Timestamp(split)
    return {"all": stats(a), "is": stats(a[a.entry_date < cut]),
            "oos": stats(a[a.entry_date >= cut])}


def configs():
    for formation in (126, 252):
        for breakout in (20, 55):
            for stop_n in (20, 40):
                for trail in (10, 20):
                    yield Config(formation, 21, breakout, stop_n, .5, trail, 40, .10)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="2025-01-01")
    ap.add_argument("--cost-bps", type=float, default=10)
    ap.add_argument("--max-positions", type=int, default=10)
    ap.add_argument("--risk", type=float, default=.005)
    args = ap.parse_args()
    data = load_data(); closes = aligned_panels(data)
    rows = []
    outdir = Path("research/results/xmom"); outdir.mkdir(parents=True, exist_ok=True)
    for n, cfg in enumerate(configs(), 1):
        tr = candidates(data, closes, cfg, args.cost_bps)
        result = portfolio(tr, args.max_positions, args.risk, args.split)
        row = {**asdict(cfg), "name": cfg.name, "raw_candidates": len(tr)}
        for part in ("all", "is", "oos"):
            for k, v in result.get(part, {}).items(): row[f"{part}_{k}"] = v
        rows.append(row)
        tr.to_csv(outdir / f"{cfg.name}.csv", index=False)
        print(n, cfg.name, result.get("is"), result.get("oos"))
    summary = pd.DataFrame(rows).sort_values(["oos_cagr", "is_cagr"], ascending=False)
    summary.to_csv(outdir / "summary.csv", index=False)
    (outdir / "metadata.json").write_text(json.dumps(vars(args), indent=2), encoding="utf-8")
    print(summary.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
