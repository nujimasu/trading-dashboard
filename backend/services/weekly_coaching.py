"""
📅 週次コーチング — 「今週何が起きたか」を 3カード + 1アクションリストで凝縮表示。

設計方針:
- ルールベース集計が主役 (常に動く)
- LLM言い回しは optional (ANTHROPIC_API_KEY があれば追加で文体を整える)
- 「習慣化のための小さなプッシュ」が目的なので、データ量を絞る
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Optional

from backend.db import db_cursor
from backend.services.trade_analytics import _fetch_closed, _fetch_open


def get_weekly_coaching(week_offset: int = 0) -> dict:
    """
    週次コーチングのフルペイロード。
    week_offset = 0 → 今週(月-日)。負値で過去週(-1 = 先週)。
    """
    today = date.today()
    # 今週の月曜
    week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    week_end   = week_start + timedelta(days=6)
    prev_start = week_start - timedelta(days=7)
    prev_end   = week_start - timedelta(days=1)

    closed = _fetch_closed()
    open_pos = _fetch_open()

    this_week = _trades_in_range(closed, week_start, week_end)
    prev_week = _trades_in_range(closed, prev_start, prev_end)

    return {
        "week": {
            "start": week_start.isoformat(),
            "end":   week_end.isoformat(),
            "label": _week_label(week_start, week_end),
        },
        "numbers": _this_week_numbers(this_week, prev_week),
        "signals": _this_week_signals(this_week, closed, open_pos, week_start),
        "actions": _next_week_actions(this_week, closed, open_pos),
        "trend":   _last_n_weeks_trend(closed, week_end, n=4),
        "llm_summary": _maybe_llm_summary({
            "numbers": _this_week_numbers(this_week, prev_week),
            "signals": _this_week_signals(this_week, closed, open_pos, week_start),
            "actions": _next_week_actions(this_week, closed, open_pos),
        }),
    }


# ────────────────────────────────────────────────────────────────────
# Numbers
# ────────────────────────────────────────────────────────────────────

def _this_week_numbers(this_week: list[dict], prev_week: list[dict]) -> dict:
    n = len(this_week)
    pnl = sum(t["pnl"] for t in this_week)
    wins = sum(1 for t in this_week if t["pnl"] > 0)
    win_rate = (wins / n * 100) if n else 0
    avg_hold = (sum((t.get("hold_days") or 0) for t in this_week) / n) if n else 0

    prev_pnl = sum(t["pnl"] for t in prev_week)
    delta_pnl = pnl - prev_pnl

    return {
        "count":     n,
        "total_pnl": round(pnl, 2),
        "wins":      wins,
        "losses":    n - wins,
        "win_rate":  round(win_rate, 1),
        "avg_hold":  round(avg_hold, 1),
        "prev_count": len(prev_week),
        "prev_pnl":   round(prev_pnl, 2),
        "delta_pnl":  round(delta_pnl, 2),
    }


# ────────────────────────────────────────────────────────────────────
# Signals
# ────────────────────────────────────────────────────────────────────

def _this_week_signals(this_week: list[dict], all_closed: list[dict],
                       open_pos: list[dict], week_start: date) -> list[dict]:
    """
    今週の「見えた事」を箇条書きで返す。最大5件。
    要素: {kind: warn/good/note, icon, text}
    """
    signals: list[dict] = []

    if this_week:
        # タグ別 (今週のみ)
        by_tag = {}
        for t in this_week:
            for tg in (t.get("tags") or []):
                d = by_tag.setdefault(tg, {"n": 0, "wins": 0, "pnl": 0.0})
                d["n"] += 1
                d["pnl"] += t["pnl"]
                if t["pnl"] > 0: d["wins"] += 1
        # 突出した負け筋: 3件以上で勝率<30% かつ pnl < 0
        worst_tag = None
        for tg, d in by_tag.items():
            if d["n"] >= 3 and d["wins"] / d["n"] < 0.30 and d["pnl"] < 0:
                if worst_tag is None or d["pnl"] < by_tag[worst_tag]["pnl"]:
                    worst_tag = tg
        if worst_tag:
            d = by_tag[worst_tag]
            signals.append({
                "kind": "warn", "icon": "⚠️",
                "text": f"{worst_tag} {d['n']}件で{d['wins']}勝{d['n']-d['wins']}敗 (${d['pnl']:+.0f})",
            })

        # 突出した勝ち筋: 2件以上で勝率>=60% かつ pnl > 0
        best_tag = None
        for tg, d in by_tag.items():
            if d["n"] >= 2 and d["wins"] / d["n"] >= 0.60 and d["pnl"] > 0:
                if best_tag is None or d["pnl"] > by_tag[best_tag]["pnl"]:
                    best_tag = tg
        if best_tag:
            d = by_tag[best_tag]
            signals.append({
                "kind": "good", "icon": "✨",
                "text": f"{best_tag} {d['n']}件で${d['pnl']:+.0f} ({d['wins']}/{d['n']}勝)",
            })

        # 今週の最大失血トレード (1件)
        worst_trade = min(this_week, key=lambda t: t["pnl"])
        if worst_trade["pnl"] < -50:
            signals.append({
                "kind": "warn", "icon": "💀",
                "text": f"今週の最大失血: {worst_trade['ticker']} ${worst_trade['pnl']:+.0f} ({worst_trade.get('hold_days', '?')}d保有 / {worst_trade['pct']:+.1f}%)",
            })

    # オープンポジの持ちすぎ警告 (8d以上 or 含み損-10%以下)
    today = date.today()
    risky_open = []
    for p in open_pos:
        try:
            entry_d = datetime.fromisoformat(p["entry_date"]).date()
        except (ValueError, TypeError):
            continue
        hold = (today - entry_d).days
        upct = p.get("unrealized_pct")
        if hold >= 8 or (upct is not None and upct <= -10):
            risky_open.append({
                "ticker":   p["ticker"],
                "hold":     hold,
                "upct":     upct,
                "upnl":     p.get("unrealized_pnl"),
            })
    if risky_open:
        risky_open.sort(key=lambda x: (x["upct"] if x["upct"] is not None else 0))
        top = risky_open[0]
        pct_str = f"{top['upct']:+.1f}%" if top["upct"] is not None else "?"
        pnl_str = f"${top['upnl']:+.0f}" if top["upnl"] is not None else "?"
        signals.append({
            "kind": "warn", "icon": "🔥",
            "text": f"{top['ticker']} 保有{top['hold']}日・含み損 {pct_str} ({pnl_str}) — 要判断",
        })
        if len(risky_open) > 1:
            signals.append({
                "kind": "note", "icon": "📋",
                "text": f"他に持ちすぎ警告 {len(risky_open) - 1} 件 (戦略分析タブで詳細)",
            })

    if not this_week and not risky_open:
        signals.append({
            "kind": "note", "icon": "🌱",
            "text": "今週はトレードがありません。お疲れさまでした。",
        })

    return signals[:5]


# ────────────────────────────────────────────────────────────────────
# Actions
# ────────────────────────────────────────────────────────────────────

def _next_week_actions(this_week: list[dict], all_closed: list[dict],
                       open_pos: list[dict]) -> list[dict]:
    """来週やること: 最大3つ。優先度順。"""
    actions: list[dict] = []

    # 1) オープンポジで持ちすぎ警告があれば、その判断を最優先
    today = date.today()
    risky = []
    for p in open_pos:
        try:
            entry_d = datetime.fromisoformat(p["entry_date"]).date()
        except (ValueError, TypeError):
            continue
        hold = (today - entry_d).days
        upct = p.get("unrealized_pct")
        if hold >= 8 or (upct is not None and upct <= -10):
            risky.append((p, hold, upct))
    if risky:
        risky.sort(key=lambda x: (x[2] if x[2] is not None else 0))
        p, hold, upct = risky[0]
        upct_str = f"含み損 {upct:+.1f}% / " if upct is not None else ""
        actions.append({
            "priority": 1,
            "title": f"月曜寄りで {p['ticker']} を見直す",
            "detail": f"保有{hold}日 / {upct_str}損切り or 継続の判断。",
        })

    # 2) 今週の最大失血タグを来週減らす
    if this_week:
        by_tag_pnl = {}
        for t in this_week:
            for tg in (t.get("tags") or []):
                by_tag_pnl[tg] = by_tag_pnl.get(tg, 0) + t["pnl"]
        if by_tag_pnl:
            worst_tag = min(by_tag_pnl, key=by_tag_pnl.get)
            if by_tag_pnl[worst_tag] < -30:
                tag_n = sum(1 for t in this_week if worst_tag in (t.get("tags") or []))
                target = max(1, tag_n // 2)
                actions.append({
                    "priority": 2,
                    "title": f"{worst_tag}を半減する (今週 {tag_n}件 → 来週 {target}件以下)",
                    "detail": f"今週このタグだけで ${by_tag_pnl[worst_tag]:+.0f}。同じ筋を続ける意味があるか1回問う。",
                })

    # 3) 永続ルール提案: 持ちすぎゾーン警告 (もう一個アクション枠があれば)
    if len(actions) < 3:
        # 全期間で 8-14d 負けが多いなら警告ルール
        late_losses = [t for t in all_closed
                       if (t.get("hold_days") or 0) >= 8 and t["pnl"] < 0]
        if len(late_losses) >= 10:
            actions.append({
                "priority": 3,
                "title": "「7日経過時点で -10% 以下なら強制決済」ルールを実験",
                "detail": f"過去 {len(late_losses)} 件の 8d+ 負けトレード(累計 ${sum(t['pnl'] for t in late_losses):+.0f}) のかなりがこれで救えた可能性。",
            })

    if not actions:
        actions.append({
            "priority": 1,
            "title": "来週は様子見でOK",
            "detail": "急ぐ判断はありません。データ蓄積のフェーズです。",
        })

    return actions[:3]


# ────────────────────────────────────────────────────────────────────
# 4-week trend
# ────────────────────────────────────────────────────────────────────

def _last_n_weeks_trend(closed: list[dict], week_end: date, n: int = 4) -> list[dict]:
    """直近 N 週の P/L (週終わりから逆順)。"""
    out = []
    for i in range(n - 1, -1, -1):
        end = week_end - timedelta(days=7 * i)
        start = end - timedelta(days=6)
        items = _trades_in_range(closed, start, end)
        out.append({
            "label":     f"W{'今週' if i == 0 else f'-{i}'}",
            "start":     start.isoformat(),
            "end":       end.isoformat(),
            "count":     len(items),
            "total_pnl": round(sum(t["pnl"] for t in items), 2),
        })
    return out


# ────────────────────────────────────────────────────────────────────
# LLM phrasing (optional)
# ────────────────────────────────────────────────────────────────────

def _maybe_llm_summary(facts: dict) -> Optional[str]:
    """ANTHROPIC_API_KEY が設定されていれば、LLMで言い回しを整える。"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
    except ImportError:
        return None

    try:
        client = anthropic.Anthropic(api_key=api_key)
        facts_compact = _facts_to_compact_text(facts)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": (
                    "あなたは個人投資家向けのトレードコーチです。"
                    "以下の事実を、温かく・具体的・行動を促す日本語の週次サマリーに要約してください。"
                    "150〜200字、改行は最小、断定的すぎず励まし寄り。\n\n"
                    f"## 今週の事実\n{facts_compact}"
                ),
            }],
        )
        return msg.content[0].text.strip()
    except Exception:
        return None


def _facts_to_compact_text(facts: dict) -> str:
    n = facts["numbers"]
    lines = [
        f"・件数: {n['count']} / P/L: ${n['total_pnl']:+.0f} / 勝率: {n['win_rate']}%",
        f"・先週との差: ${n['delta_pnl']:+.0f}",
    ]
    if facts.get("signals"):
        lines.append("・見えた事:")
        for s in facts["signals"]:
            lines.append(f"  - {s['text']}")
    if facts.get("actions"):
        lines.append("・来週やること:")
        for a in facts["actions"]:
            lines.append(f"  - {a['title']}: {a['detail']}")
    return "\n".join(lines)


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────

def _trades_in_range(closed: list[dict], start: date, end: date) -> list[dict]:
    out = []
    for t in closed:
        d = t.get("exit_date")
        if not d:
            continue
        try:
            ed = datetime.fromisoformat(d).date() if isinstance(d, str) else d
        except ValueError:
            continue
        if start <= ed <= end:
            out.append(t)
    return out


def _week_label(start: date, end: date) -> str:
    return f"{start.month}月{start.day}日(月) 〜 {end.month}月{end.day}日(日)"
