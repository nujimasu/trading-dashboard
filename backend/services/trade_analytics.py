"""
trade_analytics — 実取引（positions テーブル）を多角的に分析するサービス。

提供する API（routes/trade_analytics.py から呼ばれる）:
  - get_summary()           : 累計サマリー
  - get_insights()          : ルールベース自動インサイトカード
  - get_holding_buckets()   : 保有期間別の集計
  - get_scatter_data()      : 散布図用 raw データ
  - get_by_type()           : 銘柄タイプ別集計
  - get_all_trades()        : 全トレード（フィルタ・ソート可）
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from backend.db import db_cursor


# ── レバレッジETFティッカー辞書 ───────────────────────────────
# 主要な Direxion / GraniteShares / T-REX / ProShares 系の銘柄
LEV_ETF_TICKERS = {
    # Direxion 2X (個別株Bull/Bear)
    "AAPU", "AAPD", "AMZU", "AMZD", "TSLL", "TSLS",
    "NVDU", "NVDD", "NVDL", "NVDS",
    "MSFU", "MSFD", "GGLL", "GGLS", "METU", "METD",
    "NFXL", "NFXS", "BABX",
    "PLTU", "PLTD", "TSMU", "TSMD",
    # GraniteShares 2X
    "CONL", "CONI", "PTIR", "PTIS",
    "MSTU", "MSTZ",  # MSTR 2X
    # T-REX 2X
    "CRWU", "CRWS",
    "ROBN", "ROBS",
    # 3X 系（広く使われてる Direxion / ProShares）
    "TQQQ", "SQQQ", "SOXL", "SOXS", "UPRO", "SPXU", "SPXL", "SPXS",
    "TNA", "TZA", "FAS", "FAZ", "ERX", "ERY", "DRN", "DRV",
    "LABU", "LABD", "TECL", "TECS", "RETL", "DPST",
    # ProShares Ultra 2X
    "QLD", "DDM", "SSO",
    # その他常見
    "URTY", "SRTY", "BOIL", "KOLD", "GUSH", "DRIP",
}


def is_leverage_etf(ticker: str) -> bool:
    """ティッカーがレバレッジETFか判定。"""
    return (ticker or "").upper() in LEV_ETF_TICKERS


def price_bucket(price: float) -> str:
    """エントリー価格を 3 区分のラベルに。"""
    if price is None:
        return "unknown"
    if price < 30:    return "low"     # <$30
    if price < 100:   return "mid"     # $30-100
    return "high"                      # >$100


PRICE_BUCKET_LABEL = {
    "low":  "<$30",
    "mid":  "$30-100",
    "high": ">$100",
    "unknown": "不明",
}


# ── データ取得 ──────────────────────────────────────────────
def _fetch_closed() -> list[dict]:
    """status='closed' の全ポジションを正規化済みで返す。"""
    with db_cursor() as cur:
        cur.execute("""
            SELECT id, ticker, direction, entry_date, exit_date,
                   entry_price, exit_price, shares,
                   stop_price, source_logic, exit_reason, notes
            FROM positions
            WHERE status = 'closed'
              AND exit_price IS NOT NULL
            ORDER BY entry_date ASC, id ASC
        """)
        rows = [dict(r) for r in cur.fetchall()]

    out = []
    for r in rows:
        ep = float(r["entry_price"]) if r["entry_price"] is not None else None
        xp = float(r["exit_price"])  if r["exit_price"]  is not None else None
        sh = float(r["shares"])      if r["shares"]      is not None else None
        if ep is None or xp is None or sh is None:
            continue
        sign = 1 if (r.get("direction") or "LONG") == "LONG" else -1
        pnl  = sign * (xp - ep) * sh
        pct  = sign * (xp - ep) / ep * 100 if ep != 0 else 0.0
        ed   = _to_date(r["entry_date"])
        xd   = _to_date(r["exit_date"])
        hold = (xd - ed).days if (ed and xd) else None
        out.append({
            **r,
            "entry_price": ep,
            "exit_price":  xp,
            "shares":      sh,
            "entry_date":  ed.isoformat() if ed else None,
            "exit_date":   xd.isoformat() if xd else None,
            "pnl":         round(pnl, 2),
            "pct":         round(pct, 2),
            "hold_days":   hold,
            "is_lev":      is_leverage_etf(r["ticker"]),
            "type":        "lev_etf" if is_leverage_etf(r["ticker"]) else "stock",
            "price_bucket": price_bucket(ep),
            "entry_value": round(ep * sh, 2),
        })
    return out


def _fetch_open() -> list[dict]:
    with db_cursor() as cur:
        cur.execute("""
            SELECT id, ticker, direction, entry_date,
                   entry_price, shares, stop_price, source_logic, notes
            FROM positions
            WHERE status = 'open'
        """)
        rows = [dict(r) for r in cur.fetchall()]
    out = []
    today = date.today()
    for r in rows:
        ep = float(r["entry_price"]) if r["entry_price"] is not None else None
        sh = float(r["shares"])      if r["shares"]      is not None else None
        if ep is None or sh is None:
            continue
        ed = _to_date(r["entry_date"])
        hold = (today - ed).days if ed else None
        last = _last_close(r["ticker"])
        sign = 1 if (r.get("direction") or "LONG") == "LONG" else -1
        unrealized = sign * (last - ep) * sh if last is not None else None
        unrealized_pct = sign * (last - ep) / ep * 100 if (last is not None and ep != 0) else None
        out.append({
            **r,
            "entry_price":  ep,
            "shares":       sh,
            "entry_date":   ed.isoformat() if ed else None,
            "hold_days":    hold,
            "last_price":   last,
            "unrealized_pnl": round(unrealized, 2) if unrealized is not None else None,
            "unrealized_pct": round(unrealized_pct, 2) if unrealized_pct is not None else None,
            "is_lev":       is_leverage_etf(r["ticker"]),
            "type":         "lev_etf" if is_leverage_etf(r["ticker"]) else "stock",
            "price_bucket": price_bucket(ep),
            "entry_value":  round(ep * sh, 2),
        })
    return out


# ── 集計 API ────────────────────────────────────────────────

def get_summary() -> dict:
    closed = _fetch_closed()
    open_ = _fetch_open()
    if not closed:
        return {"trades": 0, "open_count": len(open_)}
    pnls   = [t["pnl"] for t in closed]
    wins   = [t for t in closed if t["pnl"] > 0]
    losses = [t for t in closed if t["pnl"] <= 0]
    win_sum  = sum(t["pnl"] for t in wins)
    loss_sum = abs(sum(t["pnl"] for t in losses))
    avg_win_pct  = sum(t["pct"] for t in wins)   / len(wins)   if wins   else 0
    avg_loss_pct = sum(t["pct"] for t in losses) / len(losses) if losses else 0
    pf = (win_sum / loss_sum) if loss_sum > 0 else None
    rr = (avg_win_pct / abs(avg_loss_pct)) if avg_loss_pct != 0 else None
    expectancy = sum(pnls) / len(pnls)
    biggest_win  = max(pnls)
    biggest_loss = min(pnls)
    streak = _current_streak(closed)
    return {
        "trades":         len(closed),
        "wins":           len(wins),
        "losses":         len(losses),
        "win_rate":       round(len(wins) / len(closed) * 100, 1),
        "total_pnl":      round(sum(pnls), 2),
        "expectancy":     round(expectancy, 2),
        "avg_win_pct":    round(avg_win_pct, 2),
        "avg_loss_pct":   round(avg_loss_pct, 2),
        "rr":             round(rr, 2) if rr is not None else None,
        "profit_factor":  round(pf, 2) if pf is not None else None,
        "biggest_win":    round(biggest_win, 2),
        "biggest_loss":   round(biggest_loss, 2),
        "open_count":     len(open_),
        "current_streak": streak,
        "first_trade":    closed[0]["entry_date"]   if closed else None,
        "last_trade":     closed[-1]["exit_date"]   if closed else None,
    }


def get_holding_buckets() -> dict:
    closed = _fetch_closed()
    buckets = [
        ("当日決済",  lambda d: d == 0),
        ("1日(O/N)", lambda d: d == 1),
        ("2-3日",    lambda d: 2 <= d <= 3),
        ("4-7日",    lambda d: 4 <= d <= 7),
        ("8-14日",   lambda d: 8 <= d <= 14),
        ("15日以上", lambda d: d >= 15),
    ]
    out = []
    for label, cond in buckets:
        items = [t for t in closed if t["hold_days"] is not None and cond(t["hold_days"])]
        if not items:
            out.append({"bucket": label, "count": 0, "win_rate": None,
                        "total_pnl": 0, "avg_pct": 0})
            continue
        wins = [t for t in items if t["pnl"] > 0]
        out.append({
            "bucket":    label,
            "count":     len(items),
            "win_rate":  round(len(wins) / len(items) * 100, 1),
            "total_pnl": round(sum(t["pnl"] for t in items), 2),
            "avg_pct":   round(sum(t["pct"] for t in items) / len(items), 2),
        })
    return {"buckets": out}


def get_scatter_data() -> dict:
    """各クローズドトレードの (hold_days, pct, ticker, type) を返す。"""
    closed = _fetch_closed()
    points = [{
        "ticker":     t["ticker"],
        "hold_days":  t["hold_days"] if t["hold_days"] is not None else 0,
        "pct":        t["pct"],
        "pnl":        t["pnl"],
        "type":       t["type"],
        "bucket":     t["price_bucket"],
        "entry_date": t["entry_date"],
        "shares":     t["shares"],
        "entry_price": t["entry_price"],
        "exit_price": t["exit_price"],
    } for t in closed]
    return {"points": points, "count": len(points)}


def get_by_type() -> dict:
    closed = _fetch_closed()
    open_  = _fetch_open()
    # 6 グループ: (lev_etf|stock) × (low|mid|high)
    keys = []
    for typ in ("stock", "lev_etf"):
        for b in ("low", "mid", "high"):
            keys.append((typ, b))
    out = []
    for typ, b in keys:
        items = [t for t in closed if t["type"] == typ and t["price_bucket"] == b]
        if not items:
            continue
        wins = [t for t in items if t["pnl"] > 0]
        out.append({
            "type":         typ,
            "type_label":   "レバETF" if typ == "lev_etf" else "個別株",
            "bucket":       b,
            "bucket_label": PRICE_BUCKET_LABEL[b],
            "count":        len(items),
            "win_rate":     round(len(wins) / len(items) * 100, 1),
            "total_pnl":    round(sum(t["pnl"] for t in items), 2),
            "avg_pct":      round(sum(t["pct"] for t in items) / len(items), 2),
            "avg_hold":     round(sum(t["hold_days"] or 0 for t in items) / len(items), 1),
        })
    # 開いてるポジションの内訳もあると便利
    open_summary = {}
    for t in open_:
        k = f"{t['type']}_{t['price_bucket']}"
        open_summary.setdefault(k, 0)
        open_summary[k] += 1
    return {"groups": out, "open_breakdown": open_summary}


def get_all_trades() -> dict:
    closed = _fetch_closed()
    open_  = _fetch_open()
    return {
        "closed": closed,
        "open":   open_,
    }


# ── インサイトカード（ルールベース） ─────────────────────────

def get_insights() -> dict:
    """
    実取引データから「気づき」を抽出。各カードは:
      { id, severity, icon, title, body, metrics }
    severity: 'warn' | 'good' | 'info'
    """
    closed = _fetch_closed()
    open_  = _fetch_open()
    cards: list[dict] = []

    if not closed:
        return {"cards": [{
            "id": "empty", "severity": "info", "icon": "💡",
            "title": "まだトレード履歴がありません",
            "body":  "決済済みトレードが集まるとここに自動分析が表示されます",
            "metrics": [],
        }]}

    # ── ① 当日決済 vs 翌日以降の勝率乖離 ─────────────────
    intraday  = [t for t in closed if t["hold_days"] == 0]
    overnight = [t for t in closed if t["hold_days"] and t["hold_days"] >= 1]
    if len(intraday) >= 5 and len(overnight) >= 3:
        wr_in  = sum(1 for t in intraday  if t["pnl"] > 0) / len(intraday)  * 100
        wr_on  = sum(1 for t in overnight if t["pnl"] > 0) / len(overnight) * 100
        pl_in  = sum(t["pnl"] for t in intraday)
        if wr_in < 45 and wr_on - wr_in >= 15:
            cards.append({
                "id": "intraday_weak",
                "severity": "warn",
                "icon": "⏱️",
                "title": "当日決済の勝率が低い",
                "body": (f"当日決済 {len(intraday)}件 の勝率は {wr_in:.0f}% (累計 ${pl_in:+.0f})。"
                         f"一方、翌日以降まで保有した {len(overnight)}件 は勝率 {wr_on:.0f}%。"
                         f"焦って利確/損切りせず、もう少し保有を伸ばす検討を。"),
                "metrics": [
                    {"label": "当日勝率", "value": f"{wr_in:.0f}%"},
                    {"label": "翌日以降勝率", "value": f"{wr_on:.0f}%"},
                    {"label": "勝率差", "value": f"+{wr_on - wr_in:.0f}pt"},
                ],
            })

    # ── ② リスクリワード比 ─────────────────────────────
    wins   = [t for t in closed if t["pnl"] > 0]
    losses = [t for t in closed if t["pnl"] <= 0]
    if wins and losses:
        avg_win  = sum(t["pct"] for t in wins) / len(wins)
        avg_loss = sum(t["pct"] for t in losses) / len(losses)
        rr = avg_win / abs(avg_loss) if avg_loss != 0 else None
        if rr is not None:
            if rr < 1.5:
                cards.append({
                    "id": "rr_poor",
                    "severity": "warn",
                    "icon": "⚖️",
                    "title": f"リスクリワードが {rr:.2f}",
                    "body": (f"勝ち平均 +{avg_win:.1f}% に対して負け平均 {avg_loss:.1f}%。"
                             f"勝率を 1/(1+RR)={1/(1+rr)*100:.0f}% 超で維持しないと収支トントン。"
                             f"利確を遅らせるか、SLをタイトに。"),
                    "metrics": [
                        {"label": "RR比", "value": f"{rr:.2f}"},
                        {"label": "勝ち平均", "value": f"+{avg_win:.1f}%"},
                        {"label": "負け平均", "value": f"{avg_loss:.1f}%"},
                    ],
                })
            elif rr >= 2.0:
                cards.append({
                    "id": "rr_good",
                    "severity": "good",
                    "icon": "✨",
                    "title": f"リスクリワードが良好 ({rr:.2f})",
                    "body": (f"勝ち平均 +{avg_win:.1f}% / 負け平均 {avg_loss:.1f}%。"
                             f"勝率を {1/(1+rr)*100:.0f}% 以上維持すれば収支プラス。"),
                    "metrics": [
                        {"label": "RR比", "value": f"{rr:.2f}"},
                        {"label": "勝ち平均", "value": f"+{avg_win:.1f}%"},
                        {"label": "負け平均", "value": f"{avg_loss:.1f}%"},
                    ],
                })

    # ── ③ レバETF パフォーマンス ────────────────────────
    lev = [t for t in closed if t["is_lev"]]
    if len(lev) >= 3:
        lev_wr  = sum(1 for t in lev if t["pnl"] > 0) / len(lev) * 100
        lev_pl  = sum(t["pnl"] for t in lev)
        if lev_wr < 40 or lev_pl < 0:
            cards.append({
                "id": "lev_etf_weak",
                "severity": "warn",
                "icon": "🎰",
                "title": "レバレッジETFが足を引っ張っている",
                "body": (f"レバETF {len(lev)}件 の勝率は {lev_wr:.0f}%、累計 ${lev_pl:+.0f}。"
                         f"ボラ高銘柄を短期で扱うのは難易度が高い。"
                         f"頻度を下げるか保有期間を延ばす検討を。"),
                "metrics": [
                    {"label": "件数", "value": f"{len(lev)}"},
                    {"label": "勝率", "value": f"{lev_wr:.0f}%"},
                    {"label": "累計P/L", "value": f"${lev_pl:+.0f}"},
                ],
            })

    # ── ④ 大損トレード警告（平均損失×3超） ───────────────
    if losses:
        avg_loss_usd = sum(t["pnl"] for t in losses) / len(losses)
        worst = min(losses, key=lambda t: t["pnl"])
        if avg_loss_usd != 0 and worst["pnl"] / avg_loss_usd >= 3:
            cards.append({
                "id": "outlier_loss",
                "severity": "warn",
                "icon": "💥",
                "title": "突出した大損トレードあり",
                "body": (f"{worst['ticker']} ({worst['entry_date']}) で ${worst['pnl']:+.0f} ({worst['pct']:+.1f}%)。"
                         f"平均損失 ${avg_loss_usd:.0f} の {worst['pnl']/avg_loss_usd:.1f}倍。"
                         f"ストップロスを事前に決めて機械的に執行する習慣を。"),
                "metrics": [
                    {"label": "最悪トレード", "value": f"${worst['pnl']:+.0f}"},
                    {"label": "平均損失", "value": f"${avg_loss_usd:.0f}"},
                    {"label": "倍率", "value": f"{worst['pnl']/avg_loss_usd:.1f}x"},
                ],
            })

    # ── ⑤ 塩漬け検出（オープンで保有30日超 & 含み損） ────
    stale = [t for t in open_
             if (t.get("hold_days") or 0) >= 30
             and (t.get("unrealized_pct") is not None and t["unrealized_pct"] < 0)]
    if stale:
        worst_stale = min(stale, key=lambda t: t["unrealized_pct"])
        cards.append({
            "id": "stale_position",
            "severity": "warn",
            "icon": "🧊",
            "title": f"塩漬け候補が {len(stale)}件",
            "body": (f"30日以上保有して含み損のオープンポジションが {len(stale)}件。"
                     f"最も古いのは {worst_stale['ticker']} "
                     f"({worst_stale['hold_days']}日保有, "
                     f"{worst_stale['unrealized_pct']:+.1f}%)。"
                     f"投資判断を再評価する時期では？"),
            "metrics": [
                {"label": "塩漬け数", "value": f"{len(stale)}"},
                {"label": "最古保有日数", "value": f"{worst_stale['hold_days']}日"},
                {"label": "含み損率", "value": f"{worst_stale['unrealized_pct']:+.1f}%"},
            ],
        })

    # ── ⑥ 連敗・連勝ストリーク ───────────────────────────
    streak = _current_streak(closed)
    if streak["count"] >= 3:
        if streak["type"] == "loss":
            cards.append({
                "id": "losing_streak",
                "severity": "warn",
                "icon": "📉",
                "title": f"直近 {streak['count']}連敗中",
                "body": (f"直近の {streak['count']}トレード連続で負け、"
                         f"累計 ${streak['pnl']:+.0f}。"
                         f"一旦ポジションを軽くして相場/自分の状態を見直すタイミング。"),
                "metrics": [
                    {"label": "連敗数", "value": f"{streak['count']}"},
                    {"label": "累計", "value": f"${streak['pnl']:+.0f}"},
                ],
            })
        else:
            cards.append({
                "id": "winning_streak",
                "severity": "good",
                "icon": "🔥",
                "title": f"直近 {streak['count']}連勝中",
                "body": (f"直近 {streak['count']}トレード連続で勝ち、累計 ${streak['pnl']:+.0f}。"
                         f"波に乗ってる時こそルールを守る・ポジションを大きくし過ぎない。"),
                "metrics": [
                    {"label": "連勝数", "value": f"{streak['count']}"},
                    {"label": "累計", "value": f"${streak['pnl']:+.0f}"},
                ],
            })

    # ── ⑦ ポジションサイズの均一性 ─────────────────────
    sizes = [t["entry_value"] for t in closed if t.get("entry_value")]
    if len(sizes) >= 5:
        avg_size = sum(sizes) / len(sizes)
        var = sum((s - avg_size) ** 2 for s in sizes) / len(sizes)
        std = var ** 0.5
        cv = (std / avg_size) if avg_size > 0 else 0
        if cv > 0.8:
            cards.append({
                "id": "inconsistent_sizing",
                "severity": "info",
                "icon": "📏",
                "title": "ポジションサイズのばらつき大",
                "body": (f"エントリー金額の標準偏差は ${std:.0f} (平均 ${avg_size:.0f}, CV={cv:.2f})。"
                         f"勝てる場面で小さく、負ける場面で大きくしていないか確認を。"
                         f"均一サイジングが期待値を素直に反映する。"),
                "metrics": [
                    {"label": "平均サイズ", "value": f"${avg_size:.0f}"},
                    {"label": "σ", "value": f"${std:.0f}"},
                    {"label": "CV", "value": f"{cv:.2f}"},
                ],
            })

    # ── ⑧ 最強パターン抽出 ──────────────────────────────
    # 銘柄タイプ × 価格帯のうち件数3以上の中で最も期待値高いもの
    groups = {}
    for t in closed:
        k = (t["type"], t["price_bucket"])
        groups.setdefault(k, []).append(t)
    best = None
    for (typ, b), items in groups.items():
        if len(items) < 3:
            continue
        avg_pct = sum(t["pct"] for t in items) / len(items)
        wr = sum(1 for t in items if t["pnl"] > 0) / len(items) * 100
        total = sum(t["pnl"] for t in items)
        if total > 0 and (best is None or avg_pct > best["avg_pct"]):
            best = {"type": typ, "bucket": b, "items": items,
                    "avg_pct": avg_pct, "wr": wr, "total": total}
    if best:
        type_lbl   = "レバETF" if best["type"] == "lev_etf" else "個別株"
        bucket_lbl = PRICE_BUCKET_LABEL[best["bucket"]]
        cards.append({
            "id": "strongest_pattern",
            "severity": "good",
            "icon": "🎯",
            "title": f"最も勝てているパターン: {type_lbl} × {bucket_lbl}",
            "body": (f"{type_lbl} の {bucket_lbl} 価格帯 {len(best['items'])}件 で "
                     f"勝率 {best['wr']:.0f}%、累計 ${best['total']:+.0f}、"
                     f"平均 {best['avg_pct']:+.1f}%。このパターンを多めに取りに行く戦略も。"),
            "metrics": [
                {"label": "件数", "value": f"{len(best['items'])}"},
                {"label": "勝率", "value": f"{best['wr']:.0f}%"},
                {"label": "平均%", "value": f"{best['avg_pct']:+.1f}%"},
            ],
        })

    if not cards:
        cards.append({
            "id": "all_clear", "severity": "good", "icon": "✅",
            "title": "目立った警告なし",
            "body": "現状の取引パターンに大きな歪みは見られません。継続して記録を。",
            "metrics": [],
        })
    return {"cards": cards}


# ── 補助関数 ───────────────────────────────────────────────

def _current_streak(closed: list[dict]) -> dict:
    """直近の連勝/連敗を計算。closed は entry_date 昇順想定。"""
    if not closed:
        return {"type": None, "count": 0, "pnl": 0.0}
    # 直近順にする (exit_date 降順)
    sorted_ = sorted(closed, key=lambda t: (t.get("exit_date") or "", t.get("id") or 0), reverse=True)
    latest_type = "win" if sorted_[0]["pnl"] > 0 else "loss"
    cnt = 0
    pnl = 0.0
    for t in sorted_:
        is_win = t["pnl"] > 0
        if (latest_type == "win" and is_win) or (latest_type == "loss" and not is_win):
            cnt += 1
            pnl += t["pnl"]
        else:
            break
    return {"type": latest_type, "count": cnt, "pnl": round(pnl, 2)}


def _last_close(ticker: str) -> Optional[float]:
    with db_cursor() as cur:
        cur.execute("""
            SELECT close FROM price_data
            WHERE ticker = ?
            ORDER BY date DESC LIMIT 1
        """, (ticker,))
        row = cur.fetchone()
        if row and row.get("close") is not None:
            return float(row["close"])
    return None


def _to_date(v):
    if v is None:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str):
        try:
            return date.fromisoformat(v[:10])
        except (ValueError, TypeError):
            return None
    return None
