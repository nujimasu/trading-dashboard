"""Pure TP/SL bracket backtester for next-open US equity entries.

Design constraints fixed by the mandate:

* A signal is confirmed on the daily close; the fill is the next session's open.
* There are exactly two exits: a take-profit limit and a stop-loss stop.  No
  partial exits, no trailing, no break-even move, no time stop.

Both bracket legs are derived from the *actual* fill price, which is what a
live bracket order does.  When a single daily bar touches both legs the fill
order is unknowable from daily data, so the stop is assumed to fill first.
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

SHARDS = Path("data/universe15y")
FEATURE_CACHE = Path("data/features15y.pkl")

# A trade with no time stop can in principle never resolve.  The walk is capped
# so the simulation terminates; capped trades are reported separately and are
# marked as still-open rather than being silently counted as wins.
MAX_WALK = 504


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------

def load_shards(min_dollar_volume: float = 1e7,
                max_reverse_split: float = 20.0) -> dict[str, pd.DataFrame]:
    """Load cached OHLCV, dropping names that never traded meaningful size.

    The liquidity threshold is applied to the *maximum* 60-day median dollar
    volume over the whole history, so a stock that was liquid only in 2015 is
    kept and the point-in-time filter in the rule decides tradability.

    Split-adjusted history inflates the pre-split prices of reverse-split
    names, which smuggles former penny stocks past a minimum-price filter as
    if they had been ordinary shares.  A close that collapses by more than
    ``max_reverse_split`` over the sample is treated as that artefact.
    """
    out: dict[str, pd.DataFrame] = {}
    for shard in sorted(SHARDS.glob("shard_*.pkl")):
        with shard.open("rb") as f:
            for t, d in pickle.load(f).items():
                dv = (d.Close * d.Volume).rolling(60).median().max()
                if not (np.isfinite(dv) and dv >= min_dollar_volume):
                    continue
                hi, lo = float(d.Close.max()), float(d.Close.iloc[-1])
                if lo > 0 and hi / lo > max_reverse_split:
                    continue
                out[t] = d
    return out


def features(d: pd.DataFrame) -> dict[str, np.ndarray]:
    c, h, l, v = d.Close, d.High, d.Low, d.Volume
    f: dict[str, np.ndarray] = {
        "open": d.Open.to_numpy(np.float64),
        "high": h.to_numpy(np.float64),
        "low": l.to_numpy(np.float64),
        "close": c.to_numpy(np.float64),
    }
    for n in (10, 20, 50, 200):
        f[f"ema{n}"] = c.ewm(span=n, adjust=False, min_periods=n).mean().to_numpy(np.float64)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    f["atr"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean().to_numpy(np.float64)
    delta = c.diff()
    for span, key in ((14, "rsi"), (2, "rsi2")):
        g = delta.clip(lower=0).ewm(alpha=1 / span, adjust=False, min_periods=span).mean()
        ls = (-delta.clip(upper=0)).ewm(alpha=1 / span, adjust=False, min_periods=span).mean()
        # No down move in the window is RSI 100, not "unknown": leaving it NaN
        # makes every `rsi <= threshold` filter reject the strongest up days
        # even when the threshold was meant to be inert.
        rs = 100 - 100 / (1 + g / ls.replace(0, np.nan))
        f[key] = rs.mask(ls.eq(0) & g.gt(0), 100.0).to_numpy(np.float64)
    f["ddv"] = (c * v).rolling(20).median().to_numpy(np.float64)
    f["hh20"] = h.rolling(20).max().to_numpy(np.float64)
    f["hh60"] = h.rolling(60).max().to_numpy(np.float64)
    f["ll10"] = l.rolling(10).min().to_numpy(np.float64)
    f["ll20"] = l.rolling(20).min().to_numpy(np.float64)
    for n in (21, 63, 126, 252):
        f[f"ret{n}"] = c.pct_change(n).to_numpy(np.float64)
    # Volatility contraction: recent true range relative to its own past.
    f["atr_ratio"] = (tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
                      / tr.ewm(alpha=1 / 50, adjust=False, min_periods=50).mean()).to_numpy(np.float64)
    f["vol_ratio"] = (v.rolling(3).mean() / v.rolling(50).mean()).to_numpy(np.float64)
    # Stop distance as a fraction of price is what converts an R multiple into
    # a percentage return, so the volatility tier is a first-class selector.
    f["atr_pct"] = f["atr"] / f["close"]
    f["dist_ema20"] = (c / pd.Series(f["ema20"], index=c.index) - 1).to_numpy(np.float64)
    f["dist_ema50"] = (c / pd.Series(f["ema50"], index=c.index) - 1).to_numpy(np.float64)
    f["dist_hh60"] = (c / pd.Series(f["hh60"], index=c.index) - 1).to_numpy(np.float64)
    return f


# OHLC drives exit pricing and stays float64; the derived filters only feed
# threshold comparisons, where float32 halves the memory for no loss that matters.
_F64 = ("open", "high", "low", "close", "atr")


def build_features(data: dict[str, pd.DataFrame]) -> dict:
    store = {}
    for t, d in data.items():
        f = features(d)
        for k, v in f.items():
            if k not in _F64:
                f[k] = v.astype(np.float32)
        f["dates"] = d.index.to_numpy("datetime64[D]")
        store[t] = f
    return store


# ---------------------------------------------------------------------------
# bracket simulation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Costs:
    """Friction, split by side and by how the position actually got out.

    A flat round-trip number flatters wide stops (the same basis points are a
    smaller fraction of a larger R) and flatters gaps (a gap through the target
    is booked in full while a gap through the stop is booked at the open as if
    the resting stop had joined the opening auction).  Both are corrected here.
    """
    # Entry is a market-on-open order; the auction is thinner in smaller names.
    entry_tiers: tuple[tuple[float, float], ...] = (
        (25e6, 35.0), (100e6, 22.0), (500e6, 13.0), (np.inf, 8.0))
    exit_bps: tuple[tuple[str, float], ...] = (
        ("target", 3.0),          # resting limit, commission and fees only
        ("gap_target", 12.0),
        ("stop", 18.0),           # stop triggers into a market order
        ("gap_stop", 55.0),       # triggered into the worst book of the day
        ("unresolved", 15.0),
    )
    # A limit only fills once the print clears the queue ahead of it.
    tp_queue_bps: float = 10.0
    # A gap through the target does not fill at the auction print; give back
    # part of the gap rather than booking the whole of it.
    gap_target_giveback: float = 0.5

    def entry(self, ddv: float) -> float:
        for cap, bps in self.entry_tiers:
            if not np.isfinite(ddv) or ddv < cap:
                return bps
        return self.entry_tiers[-1][1]

    def exit(self, status: str) -> float:
        return dict(self.exit_bps)[status]


def walk_bracket(o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray,
                 e: int, sl: float, tp: float, tp_queue_bps: float = 10.0,
                 gap_target_giveback: float = 0.5) -> tuple[int, float, str]:
    """Return (exit index, exit price, status) for a bracket entered at bar ``e``.

    ``e`` is the fill bar; the position is already open at its open, so the
    fill bar is checked intrabar only (no gap test against its own open).
    """
    n = len(c)
    last = min(e + MAX_WALK, n)
    touch = tp * (1 + tp_queue_bps / 10000.0)
    for j in range(e, last):
        if j > e:
            oj = o[j]
            if oj <= sl:
                return j, oj, "gap_stop"
            if oj >= tp:
                return j, tp + gap_target_giveback * (oj - tp), "gap_target"
        if l[j] <= sl:
            return j, sl, "stop"          # stop assumed first when both touch
        if h[j] >= touch:
            return j, tp, "target"
    return last - 1, c[last - 1], "unresolved"


@dataclass(frozen=True)
class Bracket:
    """How the two exit legs are placed, in ATR units off the fill price."""
    sl_atr: float = 2.0
    rr: float = 2.0
    sl_mode: str = "atr"       # "atr" or "swing" (recent low minus a buffer)
    swing_lookback: int = 10
    swing_buffer_atr: float = 0.1


# Values known at the signal close, carried onto the trade so that a portfolio
# can rank competing signals without peeking past the signal bar.
RANK_FEATURES = ("ret252", "ret126", "ret21", "rsi2", "rsi", "atr_ratio",
                 "vol_ratio", "dist_hh60", "dist_ema20", "ddv", "atr_pct")


def run_trades(store: dict, signals: dict[str, np.ndarray], br: Bracket,
               costs: Costs | None = None, max_risk_pct: float = 0.50,
               min_risk_pct: float = 0.005,
               eval_end: np.datetime64 | None = None,
               max_entry_gap_days: int = 4) -> pd.DataFrame:
    """Simulate every signal independently; portfolio limits are applied later.

    ``eval_end`` drops signals too close to the end of the data to have had a
    fair chance of resolving: without it the most recent split is padded with
    unresolved trades marked at a rising last close.
    """
    costs = costs or Costs()
    rows = []
    for t, sig in signals.items():
        f = store[t]
        o, h, l, c, atr = f["open"], f["high"], f["low"], f["close"], f["atr"]
        dates = f["dates"]
        ll = f[f"ll{br.swing_lookback}"] if br.sl_mode == "swing" else None
        for i in np.flatnonzero(sig):
            e = i + 1
            if e >= len(c):
                continue
            if eval_end is not None and dates[i] > eval_end:
                continue
            # A multi-day hole is a halt or a data gap, not "the next session".
            if (dates[e] - dates[i]).astype(int) > max_entry_gap_days:
                continue
            # Sizing viability must be decided from the signal close: the fill
            # price is not known until the market-on-open order has executed.
            if not np.isfinite(atr[i]) or br.sl_mode != "atr":
                stop_frac = np.nan
            else:
                stop_frac = br.sl_atr * atr[i] / c[i]
            # A stop a few basis points from the fill is not a tradable stop --
            # it is a stale or halted bar whose ATR collapsed to nothing, and
            # dividing by it manufactures enormous R values.
            if br.sl_mode == "atr" and (not np.isfinite(stop_frac)
                                        or not min_risk_pct <= stop_frac <= max_risk_pct):
                continue
            entry = o[e]
            if not np.isfinite(entry) or entry <= 0 or not np.isfinite(atr[i]):
                continue
            sl = (entry - br.sl_atr * atr[i] if br.sl_mode == "atr"
                  else ll[i] - br.swing_buffer_atr * atr[i])
            risk = entry - sl
            if risk <= 0:
                continue
            tp = entry + br.rr * risk
            j, px, status = walk_bracket(o, h, l, c, e, sl, tp,
                                         costs.tp_queue_bps, costs.gap_target_giveback)
            fee = (entry * costs.entry(f["ddv"][i]) + px * costs.exit(status)) / 10000.0
            r = (px - entry - fee) / risk
            rows.append((t, dates[i], dates[e], dates[j], entry, sl, tp, risk / entry,
                         r, status, j - e + 1)
                        + tuple(f[k][i] for k in RANK_FEATURES))
    return pd.DataFrame(rows, columns=[
        "ticker", "signal_date", "entry_date", "exit_date", "entry", "sl", "tp",
        "risk_pct", "r", "status", "bars", *RANK_FEATURES])


# ---------------------------------------------------------------------------
# portfolio
# ---------------------------------------------------------------------------

def price_matrix(store: dict, calendar: np.ndarray,
                 field: str = "close") -> tuple[dict[str, int], np.ndarray]:
    """Dense forward-filled prices aligned to a master calendar.

    Marking open positions to market every session needs a price for every
    (ticker, date) pair, including sessions the name did not trade.  Pass
    ``field="low"`` to build the matrix used for intraday-worst drawdown.
    """
    rows = {t: k for k, t in enumerate(store)}
    mat = np.full((len(rows), len(calendar)), np.nan)
    for t, k in rows.items():
        f = store[t]
        pos = np.searchsorted(calendar, f["dates"])
        keep = (pos < len(calendar)) & (calendar[np.clip(pos, 0, len(calendar) - 1)] == f["dates"])
        mat[k, pos[keep]] = f[field][keep]
    mat = pd.DataFrame(mat).ffill(axis=1).to_numpy()
    return rows, mat


def portfolio(trades: pd.DataFrame, calendar: np.ndarray, rows: dict[str, int],
              prices: np.ndarray, risk_pct: float = 0.01, max_positions: int = 10,
              rank_col: str | None = None, ascending: bool = False,
              max_gross: float = 1.0, start_equity: float = 100_000.0,
              margin_rate: float = 0.06, participation: float = 0.002,
              lows: np.ndarray | None = None
              ) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Daily mark-to-market simulation with concurrency and exposure limits.

    Equity is cash plus the market value of open positions, so the drawdown it
    reports is the one actually lived through -- a closed-trade equity curve
    would hide every unrealised dip.  Signals compete for slots on their entry
    date and ``rank_col`` decides priority when there are more than slots.

    ``max_gross`` above 1.0 means a margin account: cash is allowed to go
    negative and the borrowing is charged at ``margin_rate`` per annum, so
    leverage is not free.

    ``participation`` caps each position at a fraction of the name's daily
    dollar volume.  The opening cross is only a few percent of a session's
    volume, so without this the equity curve silently assumes fills that the
    auction could not absorb.  Returns (taken, close-marked equity,
    intraday-worst equity).
    """
    if trades.empty:
        return trades, pd.Series(dtype=float), pd.Series(dtype=float)
    t = trades.copy()
    t["ei"] = np.searchsorted(calendar, t.entry_date.to_numpy("datetime64[D]"))
    t["xi"] = np.searchsorted(calendar, t.exit_date.to_numpy("datetime64[D]"))
    t = t[(t.ei < len(calendar)) & (t.xi < len(calendar))]
    order = ["ei"] + ([rank_col] if rank_col else [])
    t = t.sort_values(order, ascending=[True] + ([ascending] if rank_col else []))
    by_day: dict[int, list] = {}
    for z in t.itertuples():
        by_day.setdefault(z.ei, []).append(z)

    def value(p: dict, day: int, mat: np.ndarray = prices) -> float:
        # A bracket can resolve on its own fill bar, so a position is worth its
        # settled result from its exit day onward, not that day's close.
        if p["xi"] <= day:
            return p["cost"] + p["pnl"]
        v = p["shares"] * mat[p["row"], day]
        return v if np.isfinite(v) else p["cost"]

    cash = start_equity
    open_pos: list[dict] = []
    taken: list = []
    equity = np.empty(len(calendar))
    worst = np.empty(len(calendar))
    daily_rate = margin_rate / 252.0
    for d in range(len(calendar)):
        if cash < 0:
            cash += cash * daily_rate          # interest on the margin loan
        # Capital is released the session *after* the exit: an intraday fill is
        # not spendable at that same session's open.
        still = []
        for p in open_pos:
            if p["xi"] < d:
                cash += p["cost"] + p["pnl"]
            else:
                still.append(p)
        open_pos = still
        held = {p["ticker"] for p in open_pos}
        gross = sum(value(p, d) for p in open_pos)
        eq_now = cash + gross
        if eq_now <= 0:                          # account wiped out
            equity[d:] = 0.0
            worst[d:] = 0.0
            break
        for z in by_day.get(d, ()):
            if len(open_pos) >= max_positions or z.ticker in held or z.ticker not in rows:
                continue
            budget = min(eq_now * risk_pct / z.risk_pct, eq_now * max_gross / max_positions)
            budget = min(budget, participation * z.ddv)   # auction capacity
            if budget <= 0 or gross + budget > eq_now * max_gross:
                continue
            open_pos.append(dict(ticker=z.ticker, row=rows[z.ticker], xi=z.xi,
                                 shares=budget / z.entry, cost=budget,
                                 pnl=z.r * budget * z.risk_pct))
            held.add(z.ticker)
            gross += budget
            cash -= budget
            taken.append(z)
        equity[d] = cash + sum(value(p, d) for p in open_pos)
        worst[d] = (equity[d] if lows is None
                    else cash + sum(value(p, d, lows) for p in open_pos))
    idx = pd.DatetimeIndex(calendar)
    return (pd.DataFrame(taken), pd.Series(equity, index=idx, name="equity"),
            pd.Series(worst, index=idx, name="worst"))


def stats(eq: pd.Series, taken: pd.DataFrame) -> dict:
    if eq.empty or len(eq) < 2:
        return {}
    e = eq
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (e.iloc[-1] / e.iloc[0]) ** (1 / years) - 1 if years > 0 else np.nan
    dd = (e / e.cummax() - 1).min()
    yearly = e.resample("YE").last().pct_change()
    yearly.iloc[0] = e.resample("YE").last().iloc[0] / e.iloc[0] - 1
    r = taken.r if "r" in taken else pd.Series(dtype=float)
    return dict(
        n=len(taken), cagr=cagr, max_dd=dd, mar=cagr / abs(dd) if dd else np.nan,
        final=e.iloc[-1], win_rate=(r > 0).mean() if len(r) else np.nan,
        avg_r=r.mean() if len(r) else np.nan,
        pf=r[r > 0].sum() / -r[r < 0].sum() if len(r) and (r < 0).any() else np.nan,
        worst_year=yearly.min(), neg_years=int((yearly < 0).sum()),
        yearly={str(k.year): round(float(v), 4) for k, v in yearly.items()},
    )
