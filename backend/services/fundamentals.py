from __future__ import annotations
"""
yfinance を使ったファンダメンタルズ取得（FMP不要・APIキー不要）
"""
import sys
import socket
import threading
from pathlib import Path
from datetime import datetime, date

import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from backend.db import db_cursor


def _pct(value):
    if value is None:
        return None
    try:
        return round(float(value) * 100, 1)
    except Exception:
        return None


def _num(value):
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _fetch_from_yfinance(ticker: str) -> dict | None:
    """yfinance から基本ファンダメンタルズを取得。

    yfinance .info はタイムアウトを持たず特定銘柄でハングするため、
    socket デフォルトタイムアウトを一時設定してハングを防ぐ（超過時は None でスキップ）。
    """
    _old_to = socket.getdefaulttimeout()
    socket.setdefaulttimeout(20)
    try:
        info = yf.Ticker(ticker).info
        if not info or info.get("quoteType") not in ("EQUITY", "equity"):
            # quoteType がない場合も続行
            if not info:
                return None

        # 決算サプライズ（直近の実績 vs 予想EPS）
        earnings_surprise_pct = None
        try:
            t = yf.Ticker(ticker)
            hist = t.earnings_history
            if hist is not None and not hist.empty:
                latest = hist.iloc[0]
                surprise = latest.get("surprisePercent")
                if surprise is not None:
                    earnings_surprise_pct = round(float(surprise) * 100, 1)
        except Exception:
            pass

        # EPS成長率: yfinanceは小数（0.956 = 95.6%）
        eps_g = info.get("earningsGrowth")
        eps_q = info.get("earningsQuarterlyGrowth")
        rev_g = info.get("revenueGrowth")
        roe   = info.get("returnOnEquity")
        op_m  = info.get("operatingMargins")
        pm    = info.get("profitMargins")
        inst  = info.get("heldPercentInstitutions")

        return {
            "ticker":                ticker,
            "sector":                info.get("sector", ""),
            "industry":              info.get("industry", ""),
            "market_cap":            info.get("marketCap", 0) or 0,
            "pe_ratio":              info.get("trailingPE"),
            "eps_growth_yoy":        _pct(eps_g),
            "eps_growth_q":          _pct(eps_q),
            "revenue_growth_yoy":    _pct(rev_g),
            "earnings_surprise_pct": earnings_surprise_pct,
            "roe":                   _pct(roe),
            "operating_margin":      _pct(op_m),
            "profit_margin":         _pct(pm),
            "inst_own_pct":          _pct(inst),
            "debt_to_equity":        _num(info.get("debtToEquity")),
            "description":           info.get("longBusinessSummary", ""),
            "updated_at":            datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"[Fundamentals] yfinance error {ticker}: {e}")
        return None
    finally:
        socket.setdefaulttimeout(_old_to)


def _fetch_with_timeout(ticker: str, timeout: float = 25.0) -> dict | None:
    """yfinance 取得をデーモンスレッドで実行し timeout 秒で打ち切る。

    現行 yfinance は curl_cffi(libcurl) を使い socket タイムアウトが効かず
    特定銘柄でハングしうる。join(timeout) で見切り、超過は None でスキップする
    （ハングしたスレッドはデーモンとして放棄＝プロセス終了で消える）。
    """
    result: list = [None]

    def _work():
        result[0] = _fetch_from_yfinance(ticker)

    th = threading.Thread(target=_work, daemon=True)
    th.start()
    th.join(timeout)
    if th.is_alive():
        print(f"[Fundamentals] timeout {ticker} (>{timeout:.0f}s) — スキップ")
        return None
    return result[0]


def get_or_fetch_fundamentals(ticker: str) -> dict | None:
    """キャッシュ（7日有効）があれば返し、なければyfinanceから取得・保存。"""
    with db_cursor() as cur:
        cur.execute("SELECT * FROM fundamentals WHERE ticker = ?", (ticker,))
        row = cur.fetchone()

    if row:
        row = dict(row)
        try:
            days_old = (datetime.now() - datetime.fromisoformat(row["updated_at"])).days
            if days_old < 7:
                return row
        except Exception:
            pass

    data = _fetch_with_timeout(ticker)
    if not data:
        return dict(row) if row else None

    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO fundamentals
                (ticker, sector, industry, market_cap, pe_ratio,
                 eps_growth_yoy, eps_growth_q, revenue_growth_yoy, earnings_surprise_pct,
                 roe, operating_margin, profit_margin, inst_own_pct, debt_to_equity,
                 description, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(ticker) DO UPDATE SET
                sector=excluded.sector, industry=excluded.industry,
                market_cap=excluded.market_cap, pe_ratio=excluded.pe_ratio,
                eps_growth_yoy=excluded.eps_growth_yoy,
                eps_growth_q=excluded.eps_growth_q,
                revenue_growth_yoy=excluded.revenue_growth_yoy,
                earnings_surprise_pct=excluded.earnings_surprise_pct,
                roe=excluded.roe,
                operating_margin=excluded.operating_margin,
                profit_margin=excluded.profit_margin,
                inst_own_pct=excluded.inst_own_pct,
                debt_to_equity=excluded.debt_to_equity,
                description=excluded.description,
                updated_at=excluded.updated_at
        """, (
            data["ticker"], data["sector"], data["industry"],
            data["market_cap"], data["pe_ratio"],
            data["eps_growth_yoy"], data["eps_growth_q"],
            data["revenue_growth_yoy"], data["earnings_surprise_pct"], data["roe"],
            data["operating_margin"], data["profit_margin"],
            data["inst_own_pct"], data["debt_to_equity"],
            data["description"], data["updated_at"],
        ))
    return data


# ── 後方互換（news_collector等から呼ばれる可能性があるため残す） ───────────────
def fetch_economic_calendar() -> list[dict]: return []
def fetch_market_news(limit: int = 30)    -> list[dict]: return []
def fetch_sector_performance()            -> list[dict]: return []
