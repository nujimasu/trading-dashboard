"""
positions_service — 保有ポジションとトレード日誌の CRUD。

- positions: ユーザーが「実際に買った」ポジションを記録。
  シグナル(signal_log)とは独立で、シグナルから派生して作ることも、
  自由入力で作ることも可能。

- journal_entries: ポジションに紐付くメモ。エントリー時の判断、保有中の管理、
  決済時の振り返りなどを蓄積する。
"""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Optional

from backend.db import db_cursor


# ────────────────────────────────────────────────────────────────────
# Positions CRUD
# ────────────────────────────────────────────────────────────────────

def list_positions(status: Optional[str] = None, limit: int = 200) -> list[dict]:
    where_parts: list = []
    params: list = []
    if status in ("open", "closed"):
        where_parts.append("status = ?")
        params.append(status)
    where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    with db_cursor() as cur:
        cur.execute(f"""
            SELECT * FROM positions
            {where_sql}
            ORDER BY
                CASE WHEN status = 'open' THEN 0 ELSE 1 END,
                entry_date DESC,
                id DESC
            LIMIT ?
        """, tuple(params) + (limit,))
        rows = [_normalize_row(dict(r)) for r in cur.fetchall()]

    # Attach realized P/L for closed; unrealized for open (with current price)
    tickers = list({r["ticker"] for r in rows})
    last_prices = _fetch_last_prices(tickers) if tickers else {}
    for r in rows:
        r["last_price"] = last_prices.get(r["ticker"])
        r.update(_compute_pnl(r))
    return rows


def get_position(position_id: int) -> Optional[dict]:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM positions WHERE id = ?", (position_id,))
        row = cur.fetchone()
        if not row:
            return None
        d = _normalize_row(dict(row))
    last = _fetch_last_prices([d["ticker"]]).get(d["ticker"])
    d["last_price"] = last
    d.update(_compute_pnl(d))
    return d


def create_position(payload: dict) -> dict:
    """
    Required: ticker, entry_date, entry_price, shares
    Optional: direction (default LONG), stop_price, tp1_price, target_price,
              source_logic, source_signal_id, notes
    """
    ticker      = (payload.get("ticker") or "").strip().upper()
    entry_date  = payload.get("entry_date") or date.today().isoformat()
    entry_price = _f(payload.get("entry_price"))
    shares      = _f(payload.get("shares"))
    if not ticker or entry_price is None or shares is None or shares <= 0:
        raise ValueError("ticker / entry_price / shares (>0) は必須です")

    direction   = payload.get("direction") or "LONG"
    stop_price  = _f(payload.get("stop_price"))
    tp1_price   = _f(payload.get("tp1_price"))
    target_price = _f(payload.get("target_price"))
    source_logic = payload.get("source_logic")
    source_signal_id = payload.get("source_signal_id")
    notes = payload.get("notes")

    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO positions
                (ticker, direction, entry_date, entry_price, shares,
                 stop_price, tp1_price, target_price,
                 source_logic, source_signal_id, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)
        """, (ticker, direction, entry_date, entry_price, shares,
              stop_price, tp1_price, target_price,
              source_logic, source_signal_id, notes))
        new_id = _last_insert_id(cur)

    pos = get_position(new_id)
    return pos


def update_position(position_id: int, payload: dict) -> Optional[dict]:
    """SL / TP1 / TP2 / notes / tags を更新。決済は close_position を使う。"""
    allowed = {"stop_price", "tp1_price", "target_price", "notes", "tags"}
    sets: list = []
    params: list = []
    for k, v in payload.items():
        if k not in allowed:
            continue
        if k == "tags":
            sets.append("tags = ?")
            params.append(json.dumps(_normalize_tag_list(v), ensure_ascii=False))
        elif k == "notes":
            sets.append("notes = ?")
            params.append(v)
        else:
            sets.append(f"{k} = ?")
            params.append(_f(v))
    if not sets:
        return get_position(position_id)
    sets.append("updated_at = CURRENT_TIMESTAMP")
    params.append(position_id)

    with db_cursor() as cur:
        cur.execute(f"UPDATE positions SET {', '.join(sets)} WHERE id = ?", tuple(params))
    return get_position(position_id)


def close_position(position_id: int, payload: dict) -> Optional[dict]:
    """ポジションを決済。exit_date / exit_price / exit_reason / tags を記録。"""
    exit_date   = payload.get("exit_date") or date.today().isoformat()
    exit_price  = _f(payload.get("exit_price"))
    exit_reason = payload.get("exit_reason") or ""
    if exit_price is None:
        raise ValueError("exit_price は必須です")

    sets = ["status = 'closed'", "exit_date = ?", "exit_price = ?",
            "exit_reason = ?", "updated_at = CURRENT_TIMESTAMP"]
    params: list = [exit_date, exit_price, exit_reason]
    if "tags" in payload:
        sets.append("tags = ?")
        params.append(json.dumps(_normalize_tag_list(payload["tags"]), ensure_ascii=False))
    params.append(position_id)

    with db_cursor() as cur:
        cur.execute(f"UPDATE positions SET {', '.join(sets)} WHERE id = ?", tuple(params))
    return get_position(position_id)


def _normalize_tag_list(v) -> list[str]:
    """tags 入力（list / カンマ区切り str / None）を整列済みリストに正規化。"""
    if v is None:
        return []
    if isinstance(v, str):
        items = [s.strip() for s in v.split(",")]
    elif isinstance(v, (list, tuple)):
        items = [str(s).strip() for s in v]
    else:
        return []
    seen, out = set(), []
    for s in items:
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def delete_position(position_id: int) -> bool:
    with db_cursor() as cur:
        cur.execute("DELETE FROM positions WHERE id = ?", (position_id,))
    return True


# ────────────────────────────────────────────────────────────────────
# Journal
# ────────────────────────────────────────────────────────────────────

def list_journal(position_id: int) -> list[dict]:
    with db_cursor() as cur:
        cur.execute("""
            SELECT id, position_id, entry_type, body, created_at
            FROM journal_entries
            WHERE position_id = ?
            ORDER BY created_at DESC, id DESC
        """, (position_id,))
        return [_normalize_row(dict(r)) for r in cur.fetchall()]


def add_journal(position_id: int, payload: dict) -> dict:
    body = (payload.get("body") or "").strip()
    if not body:
        raise ValueError("body は必須です")
    entry_type = payload.get("entry_type") or "note"

    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO journal_entries (position_id, entry_type, body)
            VALUES (?, ?, ?)
        """, (position_id, entry_type, body))
        new_id = _last_insert_id(cur)
        cur.execute("""
            SELECT id, position_id, entry_type, body, created_at
            FROM journal_entries WHERE id = ?
        """, (new_id,))
        return _normalize_row(dict(cur.fetchone()))


def delete_journal(entry_id: int) -> bool:
    with db_cursor() as cur:
        cur.execute("DELETE FROM journal_entries WHERE id = ?", (entry_id,))
    return True


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────

def _fetch_last_prices(tickers: list[str]) -> dict[str, float]:
    """price_data から各 ticker の最新終値を取得。"""
    if not tickers:
        return {}
    out: dict[str, float] = {}
    with db_cursor() as cur:
        for t in tickers:
            cur.execute("""
                SELECT close FROM price_data
                WHERE ticker = ?
                ORDER BY date DESC LIMIT 1
            """, (t,))
            row = cur.fetchone()
            if row and row.get("close") is not None:
                out[t] = float(row["close"])
    return out


def _compute_pnl(p: dict) -> dict:
    """ポジション dict に realized/unrealized P/L 関連フィールドを足す。"""
    entry  = _f(p.get("entry_price"))
    shares = _f(p.get("shares"))
    direction = p.get("direction") or "LONG"
    sign = 1 if direction == "LONG" else -1

    if p.get("status") == "closed":
        exit_p = _f(p.get("exit_price"))
        if entry is not None and exit_p is not None and shares is not None:
            realized_pnl = sign * (exit_p - entry) * shares
            realized_pct = sign * (exit_p - entry) / entry * 100 if entry != 0 else None
            return {
                "realized_pnl": realized_pnl,
                "realized_pct": realized_pct,
                "unrealized_pnl": None,
                "unrealized_pct": None,
            }
        return {"realized_pnl": None, "realized_pct": None,
                "unrealized_pnl": None, "unrealized_pct": None}

    # open
    last = _f(p.get("last_price"))
    if entry is not None and last is not None and shares is not None:
        unrealized_pnl = sign * (last - entry) * shares
        unrealized_pct = sign * (last - entry) / entry * 100 if entry != 0 else None
        return {
            "realized_pnl": None,
            "realized_pct": None,
            "unrealized_pnl": unrealized_pnl,
            "unrealized_pct": unrealized_pct,
        }
    return {"realized_pnl": None, "realized_pct": None,
            "unrealized_pnl": None, "unrealized_pct": None}


def _normalize_row(d: dict) -> dict:
    """日付/タイムスタンプを ISO 文字列化。tags は list に。"""
    for k, v in list(d.items()):
        if v is None:
            continue
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        elif isinstance(v, date):
            d[k] = v.isoformat()
    # tags: SQLite は文字列で返るので JSON parse、Postgres はすでに list
    raw = d.get("tags")
    if raw is None:
        d["tags"] = []
    elif isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            d["tags"] = parsed if isinstance(parsed, list) else []
        except (ValueError, TypeError):
            d["tags"] = []
    elif not isinstance(raw, list):
        d["tags"] = []
    return d


def _last_insert_id(cur) -> int:
    """SQLite/Postgres どちらでも動く、最後に INSERT した行の id を返す。"""
    # PostgreSQL: RETURNING は使わず、currval / lastval で取る
    try:
        cur.execute("SELECT lastval()")
        row = cur.fetchone()
        if row:
            v = list(row.values())[0] if isinstance(row, dict) else row[0]
            return int(v)
    except Exception:
        pass
    # SQLite
    try:
        cur.execute("SELECT last_insert_rowid() AS id")
        row = cur.fetchone()
        if row:
            return int(row["id"] if hasattr(row, "__getitem__") else row[0])
    except Exception:
        pass
    raise RuntimeError("last_insert_id failed")


def _f(v) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        f = float(v)
        if f != f:
            return None
        return f
    except (TypeError, ValueError):
        return None
