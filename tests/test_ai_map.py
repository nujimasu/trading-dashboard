from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from backend.routes import ai_map
from backend.routes.ai_map import build_category_results


@pytest.fixture(autouse=True)
def small_category_map(monkeypatch):
    """本番の8分類ではなくテスト専用の小さいマップに差し替える。
    ai_map.py は `from config import AI_CATEGORY_MAP` で値をモジュール名前空間に
    束縛済みのため、config 側ではなく ai_map モジュールの属性をパッチする。
    """
    monkeypatch.setattr(ai_map, "AI_CATEGORY_MAP", {
        "cat_up": {"label": "上昇カテゴリー", "tickers": ["UP1", "UP2"]},
        "cat_down": {"label": "下降カテゴリー", "tickers": ["DN1", "DN2"]},
        "cat_short_history": {"label": "短期履歴カテゴリー", "tickers": ["SHORT1", "MISSING1"]},
    })
    monkeypatch.setattr(ai_map, "AI_MAP_RS_RANK_ARROW_THRESHOLD", 1)
    yield


def _wide(n_days: int = 80, short_history_days: int = 10) -> pd.DataFrame:
    """80営業日ぶんの合成価格データ。UP系は右肩上がり、DN系は右肩下がり、SPYは横ばい。
    SHORT1 は直近 short_history_days 日ぶんしか値が無い（新規上場を模す）。
    MISSING1 は列自体が存在しない（バックフィル未実施の銘柄を模す）。
    """
    idx = pd.bdate_range("2026-01-01", periods=n_days)
    data = {
        "SPY": np.full(n_days, 500.0),
        "UP1": np.linspace(100.0, 150.0, n_days),   # +50%
        "UP2": np.linspace(100.0, 140.0, n_days),   # +40%
        "DN1": np.linspace(100.0, 70.0, n_days),    # -30%
        "DN2": np.linspace(100.0, 80.0, n_days),    # -20%
    }
    short = np.full(n_days, np.nan)
    short[-short_history_days:] = np.linspace(90.0, 99.0, short_history_days)
    data["SHORT1"] = short
    return pd.DataFrame(data, index=idx)


def test_category_return_is_equal_weight_mean_of_tickers():
    wide = _wide()
    result = build_category_results(wide, None, set(), {}, {}, today=date(2026, 4, 20))
    up = next(c for c in result["1m"]["categories"] if c["id"] == "cat_up")
    # UP1/UP2 は単調な線形推移なので 21営業日リターンはほぼ等ウェイト平均になる
    assert up["return_pct"] is not None
    assert up["n_calc"] == 2 and up["n_total"] == 2


def test_rs_uses_benchmark_return_as_percentage_points():
    wide = _wide()
    result = build_category_results(wide, None, set(), {}, {}, today=date(2026, 4, 20))
    r1m = result["1m"]
    assert r1m["benchmark"]["return_pct"] == 0.0  # SPYは横ばいに設定
    up = next(c for c in r1m["categories"] if c["id"] == "cat_up")
    down = next(c for c in r1m["categories"] if c["id"] == "cat_down")
    assert up["rs_pt"] == pytest.approx(up["return_pct"], abs=0.01)
    assert down["return_pct"] < 0
    assert down["rs_pt"] == pytest.approx(down["return_pct"], abs=0.01)


def test_categories_sorted_by_return_descending():
    wide = _wide()
    result = build_category_results(wide, None, set(), {}, {}, today=date(2026, 4, 20))
    returns = [c["return_pct"] for c in result["1m"]["categories"] if c["return_pct"] is not None]
    assert returns == sorted(returns, reverse=True)


def test_missing_column_ticker_flagged_no_data():
    wide = _wide()
    result = build_category_results(wide, None, set(), {}, {}, today=date(2026, 4, 20))
    short_cat = next(c for c in result["1m"]["categories"] if c["id"] == "cat_short_history")
    missing = next(t for t in short_cat["tickers"] if t["ticker"] == "MISSING1")
    assert missing.get("no_data") is True


def test_insufficient_history_excluded_from_period_but_counted_when_available():
    """SHORT1は10日分しか値が無い。1週間(5日)は計算できるが1ヶ月(21日)は計算できない。"""
    wide = _wide(n_days=80, short_history_days=10)
    result = build_category_results(wide, None, set(), {}, {}, today=date(2026, 4, 20))
    short_cat_1w = next(c for c in result["1w"]["categories"] if c["id"] == "cat_short_history")
    short_cat_1m = next(c for c in result["1m"]["categories"] if c["id"] == "cat_short_history")
    short1_1w = next(t for t in short_cat_1w["tickers"] if t["ticker"] == "SHORT1")
    short1_1m = next(t for t in short_cat_1m["tickers"] if t["ticker"] == "SHORT1")
    assert short1_1w["return_pct"] is not None
    assert short1_1m["return_pct"] is None
    # n_total は MISSING1(列なし)を除いた1(SHORT1のみ)。n_calcは期間により変わる
    assert short_cat_1w["n_total"] == 1
    assert short_cat_1w["n_calc"] == 1
    assert short_cat_1m["n_calc"] == 0


def test_breadth_counts_tickers_above_ema20():
    wide = _wide()
    result = build_category_results(wide, None, set(), {}, {}, today=date(2026, 4, 20))
    up = next(c for c in result["1m"]["categories"] if c["id"] == "cat_up")
    down = next(c for c in result["1m"]["categories"] if c["id"] == "cat_down")
    # 一貫して上昇/下降しているので、上昇カテゴリーは終値がEMA20を上回り、下降カテゴリーは下回るはず
    assert up["breadth_n"] == up["breadth_total"] == 2
    assert down["breadth_n"] == 0


def test_overheat_flag_triggers_on_large_5d_return():
    idx = pd.bdate_range("2026-01-01", periods=40)
    prices = np.full(40, 100.0)
    prices[-5:] = [100.0, 105.0, 110.0, 116.0, 125.0]  # 直近5日で+25%
    wide = pd.DataFrame({"SPY": np.full(40, 500.0), "UP1": prices, "UP2": prices}, index=idx)
    result = build_category_results(wide, None, set(), {}, {}, today=idx[-1].date())
    up = next(c for c in result["1w"]["categories"] if c["id"] == "cat_up")
    assert up["overheat"] is True


def test_overheat_flag_false_when_below_threshold():
    idx = pd.bdate_range("2026-01-01", periods=40)
    prices = np.full(40, 100.0)
    prices[-5:] = [100.0, 100.5, 101.0, 101.5, 102.0]  # 直近5日で+2%
    wide = pd.DataFrame({"SPY": np.full(40, 500.0), "UP1": prices, "UP2": prices}, index=idx)
    result = build_category_results(wide, None, set(), {}, {}, today=idx[-1].date())
    up = next(c for c in result["1w"]["categories"] if c["id"] == "cat_up")
    assert up["overheat"] is False


def test_rs_momentum_arrow_improving_when_1w_rank_beats_1m_rank():
    """cat_down は1ヶ月では下落（最下位）だが、直近1週間だけ急反発して1位に浮上する。
    1m順位2位→1w順位1位の改善なので rs_trend は improving になるはず。
    """
    idx = pd.bdate_range("2026-01-01", periods=30)
    dn = np.linspace(100.0, 40.0, 30)         # 月を通じてずっと下落基調
    dn[-5:] = [55.0, 60.0, 65.0, 70.0, 75.0]  # 直近5日だけ急反発（直前1週間の起点=50.3付近より明確に上）
    up = np.linspace(100.0, 105.0, 30)        # 1ヶ月を通じて緩やかに上昇し続ける
    wide = pd.DataFrame(
        {"SPY": np.full(30, 500.0), "UP1": up, "UP2": up, "DN1": dn, "DN2": dn},
        index=idx,
    )
    result = build_category_results(wide, None, set(), {}, {}, today=idx[-1].date())
    down_1m = next(c for c in result["1m"]["categories"] if c["id"] == "cat_down")
    down_1w = next(c for c in result["1w"]["categories"] if c["id"] == "cat_down")
    assert down_1m["return_pct"] < 0
    assert down_1w["return_pct"] > down_1m["return_pct"]
    assert down_1m["rs_trend"] == "improving"


def test_swing_picks_and_earnings_are_attached_per_category_and_ticker():
    wide = _wide()
    swing_picks = {"UP1"}
    earnings = {"UP2": {"date": "2026-04-22", "timing": "amc"}}
    result = build_category_results(
        wide, "2026-04-19", swing_picks, earnings, {"UP1": "Up One Inc."},
        today=date(2026, 4, 20),
    )
    up = next(c for c in result["1m"]["categories"] if c["id"] == "cat_up")
    assert up["swing_pick_count"] == 1
    assert up["earnings_this_week"] == 1
    up1 = next(t for t in up["tickers"] if t["ticker"] == "UP1")
    up2 = next(t for t in up["tickers"] if t["ticker"] == "UP2")
    assert up1["in_swing_picks"] is True
    assert up1["name"] == "Up One Inc."
    assert up2["earnings_date"] == "2026-04-22"
    assert up2["earnings_timing"] == "amc"
    assert result["1m"]["swing_scan_date"] == "2026-04-19"


def test_price_stale_flag_true_when_as_of_far_behind_today():
    wide = _wide()
    # today を as_of から5営業日以上先にずらす
    stale_today = wide.index[-1].date() + pd.tseries.offsets.BDay(5)
    result = build_category_results(wide, None, set(), {}, {}, today=stale_today.date())
    assert result["1m"]["price_stale"] is True


def test_empty_wide_returns_empty_dict():
    assert build_category_results(pd.DataFrame(), None, set(), {}, {}) == {}


def test_missing_benchmark_column_returns_empty_dict():
    idx = pd.bdate_range("2026-01-01", periods=30)
    wide = pd.DataFrame({"UP1": np.linspace(100, 110, 30)}, index=idx)
    assert build_category_results(wide, None, set(), {}, {}) == {}
