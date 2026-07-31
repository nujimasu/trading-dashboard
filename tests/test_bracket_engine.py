"""Behavioural tests for the pure TP/SL bracket walk.

These pin the exit semantics that every downstream number depends on: which
leg wins on an ambiguous bar, how opening gaps are priced, and that no third
exit path exists.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.bracket_engine import (Bracket, Costs, MAX_WALK, RANK_FEATURES,
                                     portfolio, run_trades, walk_bracket)

_STATUSES = ("target", "gap_target", "stop", "gap_stop", "unresolved")


def bars(rows):
    a = np.array(rows, dtype=float)
    return a[:, 0], a[:, 1], a[:, 2], a[:, 3]


def test_target_hit_fills_at_limit_price():
    o, h, l, c = bars([[100, 100, 100, 100], [100, 112, 99, 110]])
    assert walk_bracket(o, h, l, c, 1, sl=95, tp=110) == (1, 110, "target")


def test_stop_hit_fills_at_stop_price():
    o, h, l, c = bars([[100, 100, 100, 100], [100, 102, 94, 96]])
    assert walk_bracket(o, h, l, c, 1, sl=95, tp=110) == (1, 95, "stop")


def test_stop_wins_when_one_bar_touches_both_legs():
    o, h, l, c = bars([[100, 100, 100, 100], [100, 115, 90, 105]])
    j, px, status = walk_bracket(o, h, l, c, 1, sl=95, tp=110)
    assert (j, px, status) == (1, 95, "stop")


def test_gap_below_stop_fills_at_open_not_at_stop():
    o, h, l, c = bars([[100, 100, 100, 100],
                       [100, 101, 99, 100],
                       [88, 89, 87, 88]])
    j, px, status = walk_bracket(o, h, l, c, 1, sl=95, tp=110)
    assert status == "gap_stop" and px == 88 and j == 2


def test_gap_above_target_gives_back_part_of_the_gap():
    # A resting limit does not join the opening cross, so booking the whole
    # auction print would pay the strategy for liquidity it never had.
    o, h, l, c = bars([[100, 100, 100, 100],
                       [100, 101, 99, 100],
                       [120, 121, 119, 120]])
    j, px, status = walk_bracket(o, h, l, c, 1, sl=95, tp=110,
                                 gap_target_giveback=0.5)
    assert status == "gap_target" and px == 115 and j == 2
    full = walk_bracket(o, h, l, c, 1, sl=95, tp=110, gap_target_giveback=1.0)
    assert full[1] == 120


def test_target_needs_the_print_to_clear_the_queue():
    # High tags the limit exactly: the queue ahead absorbs it, so no fill.
    o, h, l, c = bars([[100, 100, 100, 100], [100, 110, 99, 105],
                       [105, 106, 104, 105]])
    assert walk_bracket(o, h, l, c, 1, sl=95, tp=110,
                        tp_queue_bps=10.0)[2] == "unresolved"
    assert walk_bracket(o, h, l, c, 1, sl=95, tp=110,
                        tp_queue_bps=0.0)[2] == "target"


def test_fill_bar_is_not_gap_checked_against_its_own_open():
    # Entry fills at 100 and the same bar trades up to the target: this is a
    # target hit, not a "gap through the target" at the fill price itself.
    o, h, l, c = bars([[100, 100, 100, 100], [100, 111, 100, 111]])
    assert walk_bracket(o, h, l, c, 1, sl=95, tp=110)[2] == "target"


def test_unresolved_when_neither_leg_is_reached():
    n = MAX_WALK + 5
    o, h, l, c = bars([[100, 101, 99, 100]] * n)
    j, px, status = walk_bracket(o, h, l, c, 1, sl=95, tp=110)
    assert status == "unresolved" and j == 1 + MAX_WALK - 1


def _store(o, h, l, c, atr, ll10=None):
    n = len(c)
    f = {"open": o, "high": h, "low": l, "close": c, "atr": atr,
         "dates": np.arange("2020-01-01", np.datetime64("2020-01-01") + n,
                            dtype="datetime64[D]")}
    f["ll10"] = ll10 if ll10 is not None else np.full(n, np.nan)
    for k in RANK_FEATURES:
        f.setdefault(k, np.zeros(n))
    return {"AAA": f}


def test_run_trades_enters_at_next_open_and_reports_r():
    o, h, l, c = bars([[100, 100, 100, 100],
                       [100, 100, 100, 100],
                       [100, 121, 100, 120]])
    atr = np.full(3, 10.0)
    sig = np.array([False, True, False])
    tr = run_trades(_store(o, h, l, c, atr), {"AAA": sig},
                    Bracket(sl_atr=1.0, rr=2.0), costs=Costs(entry_tiers=((np.inf, 0.0),), exit_bps=tuple((k, 0.0) for k in _STATUSES), tp_queue_bps=0.0, gap_target_giveback=0.0))
    row = tr.iloc[0]
    # Signal on bar 1, fill at bar 2 open = 100, stop 90, target 120 => +2R.
    assert row.entry == 100 and row.sl == 90 and row.tp == 120
    assert row.r == pytest.approx(2.0)
    assert row.entry_date == np.datetime64("2020-01-03")


def test_costs_are_charged_in_r_units():
    o, h, l, c = bars([[100, 100, 100, 100],
                       [100, 100, 100, 100],
                       [100, 121, 100, 120]])
    tr = run_trades(_store(o, h, l, c, np.full(3, 10.0)), {"AAA": np.array([False, True, False])},
                    Bracket(sl_atr=1.0, rr=2.0), costs=Costs(entry_tiers=((np.inf, 10.0),), exit_bps=tuple((k, 10.0) for k in _STATUSES), tp_queue_bps=0.0, gap_target_giveback=0.0))
    # 10bp in at 100 and 10bp out at 120 costs 0.22 in price; risk is 10.
    assert tr.iloc[0].r == pytest.approx((120 - 100 - 0.22) / 10)


def test_risk_cap_rejects_signals_with_a_far_stop():
    o, h, l, c = bars([[100, 100, 100, 100],
                       [100, 100, 100, 100],
                       [100, 200, 100, 200]])
    tr = run_trades(_store(o, h, l, c, np.full(3, 40.0)), {"AAA": np.array([False, True, False])},
                    Bracket(sl_atr=1.0, rr=2.0), max_risk_pct=0.15)
    assert tr.empty


def _book(tickers, days=200):
    """Flat-priced calendar and price matrix so mark-to-market is a no-op."""
    cal = np.arange(np.datetime64("2020-01-01"), np.datetime64("2020-01-01") + days,
                    dtype="datetime64[D]")
    rows = {t: k for k, t in enumerate(tickers)}
    return cal, rows, np.full((len(rows), days), 100.0)


def test_portfolio_respects_concurrency_limit():
    cal, rows, px = _book(["A", "B", "C"])
    t = pd.DataFrame({
        "ticker": ["A", "B", "C"],
        "entry_date": pd.to_datetime(["2020-01-02"] * 3),
        "exit_date": pd.to_datetime(["2020-06-01"] * 3),
        "entry": [100.0] * 3,
        "risk_pct": [0.05] * 3, "ddv": 1e12, "r": [1.0] * 3, "score": [3.0, 2.0, 1.0],
    })
    taken, _, _ = portfolio(t, cal, rows, px, risk_pct=0.01, max_positions=2,
                         rank_col="score")
    assert len(taken) == 2 and set(taken.ticker) == {"A", "B"}


def test_portfolio_never_holds_the_same_ticker_twice():
    cal, rows, px = _book(["A"])
    t = pd.DataFrame({
        "ticker": ["A", "A"],
        "entry_date": pd.to_datetime(["2020-01-02", "2020-01-02"]),
        "exit_date": pd.to_datetime(["2020-06-01", "2020-06-01"]),
        "entry": [100.0, 100.0],
        "risk_pct": [0.05, 0.05], "ddv": 1e12, "r": [1.0, 1.0], "score": [2.0, 1.0],
    })
    taken, _, _ = portfolio(t, cal, rows, px, risk_pct=0.01, max_positions=5,
                         rank_col="score")
    assert len(taken) == 1


def test_portfolio_caps_gross_exposure():
    # A 1% risk with a 1% stop distance implies 100% of equity in one name;
    # the gross cap must cut it to max_gross / max_positions.
    cal, rows, px = _book(["A"])
    t = pd.DataFrame({
        "ticker": ["A"], "entry_date": pd.to_datetime(["2020-01-02"]),
        "exit_date": pd.to_datetime(["2020-06-01"]),
        "entry": [100.0],
        "risk_pct": [0.01], "ddv": 1e12, "r": [1.0], "score": [1.0],
    })
    _, eq, _ = portfolio(t, cal, rows, px, risk_pct=0.01, max_positions=10,
                      max_gross=1.0, start_equity=100_000.0)
    # notional capped at 10_000 => pnl = 1R * 10_000 * 1% = 100.
    assert eq.iloc[-1] == pytest.approx(100_100.0)


def test_same_day_exit_frees_its_slot_for_the_next_session():
    # A bracket that resolves on its own fill bar must not hold a slot forever.
    cal, rows, px = _book(["A", "B"], days=30)
    t = pd.DataFrame({
        "ticker": ["A", "B"],
        "entry_date": pd.to_datetime(["2020-01-01", "2020-01-03"]),
        "exit_date": pd.to_datetime(["2020-01-01", "2020-01-03"]),
        "entry": [100.0, 100.0], "risk_pct": [0.10, 0.10], "ddv": 1e12,
        "r": [1.0, 1.0], "score": [1.0, 1.0],
    })
    taken, eq, _ = portfolio(t, cal, rows, px, risk_pct=0.10, max_positions=1,
                          rank_col="score", start_equity=100_000.0)
    assert len(taken) == 2                      # the second trade still fits
    # +10% on 100k, then +10% on the compounded 110k.
    assert eq.iloc[-1] == pytest.approx(121_000.0)


def test_margin_allows_gross_above_one_and_charges_interest():
    cal, rows, px = _book(["A", "B"], days=60)
    t = pd.DataFrame({
        "ticker": ["A", "B"],
        "entry_date": pd.to_datetime(["2020-01-02"] * 2),
        "exit_date": pd.to_datetime(["2020-02-20"] * 2),
        "entry": [100.0, 100.0], "risk_pct": [0.10, 0.10], "ddv": 1e12,
        "r": [0.0, 0.0], "score": [2.0, 1.0],
    })
    _, flat, _ = portfolio(t, cal, rows, px, risk_pct=0.10, max_positions=2,
                        rank_col="score", max_gross=2.0, margin_rate=0.0)
    _, charged, _ = portfolio(t, cal, rows, px, risk_pct=0.10, max_positions=2,
                           rank_col="score", max_gross=2.0, margin_rate=0.06)
    # Both trades sized at equity (2.0 gross / 2 slots) => 100% borrowed.
    assert flat.iloc[-1] == pytest.approx(100_000.0)
    assert charged.iloc[-1] < flat.iloc[-1]


def test_equity_curve_marks_open_positions_to_market():
    # Price halves while the position is open; the curve must show the dip
    # before the trade closes, not only the realised result at the exit.
    days = 200
    cal = np.arange(np.datetime64("2020-01-01"), np.datetime64("2020-01-01") + days,
                    dtype="datetime64[D]")
    px = np.full((1, days), 100.0)
    px[0, 5:50] = 50.0
    t = pd.DataFrame({
        "ticker": ["A"], "entry_date": pd.to_datetime(["2020-01-02"]),
        "exit_date": pd.to_datetime(["2020-06-01"]),
        "entry": [100.0], "risk_pct": [0.10], "ddv": 1e12, "r": [1.0], "score": [1.0],
    })
    _, eq, _ = portfolio(t, cal, {"A": 0}, px, risk_pct=0.10, max_positions=1,
                      max_gross=1.0, start_equity=100_000.0)
    assert (eq / eq.cummax() - 1).min() < -0.4
    assert eq.iloc[-1] == pytest.approx(110_000.0)


def test_position_is_capped_by_auction_capacity():
    # 0.2% of a $1M-a-day name is $2k, far below the $10k the slot allows.
    cal, rows, px = _book(["A"])
    t = pd.DataFrame({
        "ticker": ["A"], "entry_date": pd.to_datetime(["2020-01-02"]),
        "exit_date": pd.to_datetime(["2020-06-01"]), "entry": [100.0],
        "risk_pct": [0.10], "ddv": [1e6], "r": [1.0], "score": [1.0],
    })
    _, eq, _ = portfolio(t, cal, rows, px, risk_pct=0.10, max_positions=10,
                         participation=0.002, start_equity=100_000.0)
    assert eq.iloc[-1] == pytest.approx(100_000.0 + 2_000 * 0.10)


def test_stop_viability_is_judged_on_the_signal_close_not_the_fill():
    # ATR is 14% of the signal close, so a 1-ATR stop is inside the 15% cap and
    # the trade must be taken even though the next open gaps down.
    o, h, l, c = bars([[100, 100, 100, 100],
                       [100, 100, 100, 100],
                       [80, 200, 80, 200]])
    tr = run_trades(_store(o, h, l, c, np.full(3, 14.0)),
                    {"AAA": np.array([False, True, False])},
                    Bracket(sl_atr=1.0, rr=2.0), max_risk_pct=0.15)
    assert len(tr) == 1
    # Judged on the fill (14/80 = 17.5%) it would have been wrongly rejected.
    assert tr.iloc[0].risk_pct > 0.15


def test_eval_end_drops_signals_too_late_to_resolve():
    o, h, l, c = bars([[100, 100, 100, 100]] * 4)
    store = _store(o, h, l, c, np.full(4, 5.0))
    sig = np.array([False, True, True, False])
    assert len(run_trades(store, {"AAA": sig}, Bracket())) == 2
    late = run_trades(store, {"AAA": sig}, Bracket(),
                      eval_end=np.datetime64("2020-01-02"))
    assert len(late) == 1


def test_intraday_curve_is_never_above_the_close_curve():
    days = 60
    cal = np.arange(np.datetime64("2020-01-01"), np.datetime64("2020-01-01") + days,
                    dtype="datetime64[D]")
    close = np.full((1, days), 100.0)
    low = np.full((1, days), 80.0)
    t = pd.DataFrame({
        "ticker": ["A"], "entry_date": pd.to_datetime(["2020-01-02"]),
        "exit_date": pd.to_datetime(["2020-02-20"]), "entry": [100.0],
        "risk_pct": [0.10], "ddv": [1e12], "r": [1.0], "score": [1.0],
    })
    _, eq, worst = portfolio(t, cal, {"A": 0}, close, risk_pct=0.10,
                             max_positions=1, lows=low, start_equity=100_000.0)
    assert (worst <= eq + 1e-9).all()
    assert (worst / worst.cummax() - 1).min() < (eq / eq.cummax() - 1).min()


def test_degenerate_stop_distance_is_rejected():
    # A near-zero ATR (stale or halted bar) would divide a normal price move by
    # almost nothing and report an absurd R.
    o, h, l, c = bars([[100, 100, 100, 100],
                       [100, 100, 100, 100],
                       [100, 130, 100, 130]])
    tr = run_trades(_store(o, h, l, c, np.full(3, 0.01)),
                    {"AAA": np.array([False, True, False])},
                    Bracket(sl_atr=1.0, rr=2.0), min_risk_pct=0.005)
    assert tr.empty
    loose = run_trades(_store(o, h, l, c, np.full(3, 0.01)),
                       {"AAA": np.array([False, True, False])},
                       Bracket(sl_atr=1.0, rr=2.0), min_risk_pct=0.0)
    # Without the floor the same bar reports an R an order of magnitude beyond
    # anything the bracket can actually produce.
    assert len(loose) == 1 and abs(loose.iloc[0].r) > 20
