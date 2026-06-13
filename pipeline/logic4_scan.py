"""
ロジック４スキャンエンジン — 厳選押し目買いv2

実トレード 1,713 件の分析から導いた押し目買いスイング戦略。
仕様: 押し目買いロジックv3.md

勝ち筋: 4〜7日保有のスイング（デイトレ禁止）。
負けの正体は勝率ではなく RR（利大損小）。フィルターで勝率を上げ、
分割決済（+1.5R 半分→残り 20日EMA トレーリング）で 1勝を大きくする。

スキャンの役割:
  「地合い → トレンド → EMAタッチ/接近 → 出来高枯れ」までを自動抽出し、
  ウォッチリスト化する。最後の引き金（反発足の確認）は本人が当日に行う前提
  （v3 C項: 夜、米国寄り付き後の数時間で反発足を確認してエントリー）。

一次フィルター:
  A. 地合い: SP500(^GSPC) または QQQ が 200日EMA の上（割れていれば「休む」）
  B. トレンド: 株価 > 200EMA かつ 50EMA > 200EMA、3ヶ月騰落率 > 0%
  C. 流動性: 20日平均出来高 >= 100万株
  D. 除外: 決算7日以内 / 高額レバETF / 暗号資産マイニング関連小型株

エントリー圏判定:
  - 20日 or 50日EMA への タッチ（±2%）/ 接近（±5%）
  - 出来高枯れ（直近3日平均 < 20日平均 × 0.8 ＝ 売り枯れ）

リスク設計（各銘柄に提示）:
  - 損切り: 直近20日押し安値の少し下に固定（= 1R）
  - 第1利確: +1.5R で半分
  - 残り半分: 20日EMA 終値割れまで保有（トレーリング）
  - 保有上限: 8営業日（含み損なら全決済）
"""

import json
from datetime import date, datetime, timedelta
from backend.db import get_connection
from config import SECTOR_DISPLAY

try:
    import yfinance as yf
    _YF_AVAILABLE = True
except ImportError:
    _YF_AVAILABLE = False

# ── 定数（v3.md 準拠・コメントの数値が根拠）─────────────────────────────────
MIN_BARS_DAILY  = 250        # 200日EMA を計算するのに必要な日足バー数
MIN_AVG_VOLUME  = 1_000_000  # v3: 20日平均出来高 >= 100万株
PERF_3M_DAYS    = 63         # 約3ヶ月
PERF_6M_DAYS    = 126        # 約6ヶ月
EMA_NEAR_PCT    = 5.0        # EMA 接近圏（±5%）= サポート接近中
EMA_TOUCH_PCT   = 2.0        # EMA タッチ（±2%）= 押し目到達
VOL_DRYUP_RATIO = 0.8        # 出来高枯れ: 直近3日平均 < 20日平均 × 0.8
STOP_LOOKBACK   = 20         # 損切り基準の押し安値ルックバック（日）
HOLDING_LIMIT   = 8          # 保有上限（営業日）
TP1_R           = 1.5        # 第1利確 = +1.5R
REGIME_SYMBOLS  = ("^GSPC", "QQQ")  # 地合い判定に使う指数/ETF

LEVERAGED_ETF = {
    "TSLL", "MSTU", "MSTX", "NVDL", "TQQQ", "SOXL", "TSLT", "CONL", "FNGU", "BULZ",
    "SPXL", "UPRO", "TECL", "FAS", "LABU", "TNA", "UDOW", "QLD", "SSO", "ROM",
    "USD", "WEBL", "YINN", "BOIL", "TMF", "ERX", "DPST", "HIBL", "AMZU", "AAPU",
    "MSFU", "GGLL", "METU",
}

# 暗号資産マイニング・関連小型株は固定除外を維持。
EXCLUDE_TICKERS = {
    "MARA", "BITF", "BTBT", "RIOT", "HUT", "CIFR", "WULF", "IREN", "CLSK", "BTDR",
}


# ── 指標ユーティリティ ───────────────────────────────────────────────────────

def _ema(arr, period):
    k = 2 / (period + 1)
    result = [None] * len(arr)
    init = False
    s = 0.0
    for i, v in enumerate(arr):
        if not init:
            s += v
            if i == period - 1:
                result[i] = s / period
                init = True
        else:
            result[i] = v * k + result[i - 1] * (1 - k)
    return result


def _sma(arr, period):
    out = [None] * len(arr)
    if len(arr) < period:
        return out
    run_sum = sum(arr[:period])
    out[period - 1] = run_sum / period
    for i in range(period, len(arr)):
        run_sum += arr[i] - arr[i - period]
        out[i] = run_sum / period
    return out


def _atr(H, L, C, period=14):
    """Wilder's ATR。"""
    out = [None] * len(C)
    if len(C) <= period:
        return out
    trs = [0.0]
    for i in range(1, len(C)):
        trs.append(max(H[i] - L[i], abs(H[i] - C[i - 1]), abs(L[i] - C[i - 1])))
    first = sum(trs[1:period + 1]) / period
    out[period] = first
    for i in range(period + 1, len(C)):
        out[i] = (out[i - 1] * (period - 1) + trs[i]) / period
    return out


def _rsi(C, period=14):
    out = [None] * len(C)
    if len(C) <= period:
        return out
    gains = losses = 0.0
    for i in range(1, period + 1):
        ch = C[i] - C[i - 1]
        gains += max(ch, 0.0)
        losses += max(-ch, 0.0)
    avg_g = gains / period
    avg_l = losses / period
    rs = avg_g / avg_l if avg_l else 999.0
    out[period] = 100 - 100 / (1 + rs)
    for i in range(period + 1, len(C)):
        ch = C[i] - C[i - 1]
        avg_g = (avg_g * (period - 1) + max(ch, 0.0)) / period
        avg_l = (avg_l * (period - 1) + max(-ch, 0.0)) / period
        rs = avg_g / avg_l if avg_l else 999.0
        out[i] = 100 - 100 / (1 + rs)
    return out


# ── A. 地合いフィルター ──────────────────────────────────────────────────────

def _check_market_regime():
    """SP500(^GSPC) または QQQ が 200日EMA の上なら地合い OK（v3 A項）。

    返り値: (regime_ok: bool, note: str, vix_caution: bool, vix_note: str)
    yfinance 不可・取得失敗時は保守的に OK 扱い（候補は出すが警告は付かない）。
    """
    if not _YF_AVAILABLE:
        return True, "地合い判定スキップ（yfinance不可）", False, ""
    try:
        results = {}
        for sym in REGIME_SYMBOLS:
            df = yf.download(sym, period="1y", interval="1d",
                             progress=False, auto_adjust=True)
            if df is None or df.empty:
                continue
            close_col = df["Close"]
            if hasattr(close_col, "columns"):       # multiindex DataFrame
                close_col = close_col.iloc[:, 0]
            closes = [float(x) for x in close_col.dropna().tolist()]
            if len(closes) < 200:
                continue
            ema200 = _ema(closes, 200)
            if ema200[-1] is None:
                continue
            results[sym] = closes[-1] > ema200[-1]
        if not results:
            return True, "地合い判定データ取得不可（保守的にOK扱い）", False, ""
        note = ", ".join(
            f"{k.replace('^', '')}:{'>200EMA' if v else '<200EMA'}"
            for k, v in results.items()
        )
        vix_caution, vix_note = _check_vix_caution()
        # v3: SP500 または QQQ が上なら可（OR 条件）
        return (sum(1 for v in results.values() if v) >= 1), note, vix_caution, vix_note
    except Exception as e:
        return True, f"地合い判定エラー（保守的にOK扱い）: {e}", False, ""


def _check_vix_caution():
    if not _YF_AVAILABLE:
        return False, ""
    try:
        df = yf.download("^VIX", period="1mo", interval="1d",
                         progress=False, auto_adjust=False)
        if df is None or df.empty:
            return False, ""
        close_col = df["Close"]
        if hasattr(close_col, "columns"):
            close_col = close_col.iloc[:, 0]
        closes = [float(x) for x in close_col.dropna().tolist()]
        if not closes:
            return False, ""
        latest = closes[-1]
        five_day_change = None
        if len(closes) >= 6 and closes[-6] > 0:
            five_day_change = (latest - closes[-6]) / closes[-6] * 100
        caution = latest > 25 or (five_day_change is not None and five_day_change >= 30)
        if not caution:
            return False, f"VIX {latest:.1f}"
        if five_day_change is not None:
            return True, f"VIX {latest:.1f} / 5営業日 {five_day_change:+.0f}%"
        return True, f"VIX {latest:.1f}"
    except Exception:
        return False, ""


# ── セクター（fundamentals テーブルから・FMP は呼ばない）─────────────────────

def _build_sector_map(cur):
    smap = {}
    try:
        cur.execute("SELECT ticker, sector FROM fundamentals")
        for r in cur.fetchall():
            sec = r["sector"]
            if sec:
                smap[r["ticker"]] = SECTOR_DISPLAY.get(sec, sec)
    except Exception:
        pass
    return smap


def _is_excluded(ticker):
    return ticker.upper() in EXCLUDE_TICKERS


def _leveraged_etf_adjustment(ticker, price):
    if ticker.upper() not in LEVERAGED_ETF:
        return "normal", 0.0, None
    if price > 100:
        return "exclude", 0.0, "高額レバETF（$100超）のため除外"
    if price < 30:
        return "allow", 0.0, "レバETFだが$30未満のため許容"
    return "penalty", 0.05, "レバETF $30-$100帯のため信頼度を微減"


def _normalize_earnings_date(value):
    if value is None:
        return None
    try:
        if isinstance(value, (list, tuple)):
            value = value[0] if value else None
        if value is None:
            return None
        if hasattr(value, "to_pydatetime"):
            value = value.to_pydatetime()
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return datetime.fromisoformat(str(value)[:10]).date()
    except Exception:
        return None


def _next_earnings_date(ticker):
    if not _YF_AVAILABLE:
        return None
    try:
        yf_ticker = yf.Ticker(ticker)
        cal = yf_ticker.calendar
        if isinstance(cal, dict):
            for key in ("Earnings Date", "EarningsDate", "earningsDate"):
                d = _normalize_earnings_date(cal.get(key))
                if d and d >= date.today():
                    return d
        elif cal is not None and hasattr(cal, "empty") and not cal.empty:
            for key in ("Earnings Date", "EarningsDate", "earningsDate"):
                if key in cal.index:
                    d = _normalize_earnings_date(cal.loc[key].iloc[0] if hasattr(cal.loc[key], "iloc") else cal.loc[key])
                    if d and d >= date.today():
                        return d
                if key in cal.columns:
                    d = _normalize_earnings_date(cal[key].iloc[0])
                    if d and d >= date.today():
                        return d
        if hasattr(yf_ticker, "get_earnings_dates"):
            df = yf_ticker.get_earnings_dates(limit=8)
            if df is not None and not df.empty:
                dates = []
                for idx in df.index:
                    d = _normalize_earnings_date(idx)
                    if d and d >= date.today():
                        dates.append(d)
                if dates:
                    return min(dates)
    except Exception:
        return None
    return None


def _earnings_within_days(ticker, days=7):
    next_date = _next_earnings_date(ticker)
    if not next_date:
        return False, None
    return date.today() <= next_date <= date.today() + timedelta(days=days), next_date


def _find_swing_highs(values, lookback=3):
    highs = []
    for i in range(lookback, len(values) - lookback):
        window = values[i - lookback:i + lookback + 1]
        if values[i] == max(window):
            highs.append(i)
    return highs


def _detect_reji_sapo_near_ema(H, C, i, ema_price, lookback=120):
    if ema_price is None or ema_price <= 0:
        return None
    start = max(0, i - lookback)
    highs = H[start:i]
    if len(highs) < 10:
        return None
    swing_highs = _find_swing_highs(highs, lookback=3)
    current = C[i]
    matches = []
    for idx in swing_highs:
        price = highs[idx]
        if current > price and abs(price - ema_price) / ema_price <= 0.02:
            matches.append(price)
    if not matches:
        return None
    return min(matches, key=lambda p: abs(p - ema_price))


# ── メイン ───────────────────────────────────────────────────────────────────

def run():
    print("[Logic4] 厳選押し目買いv2 スクリーニング開始...")
    conn = get_connection()
    cur = conn.cursor()

    # A. 地合いフィルター（全体で1回）
    regime_ok, regime_note, vix_caution, vix_note = _check_market_regime()
    print(f"[Logic4] 地合い: {'OK' if regime_ok else 'NG（休む推奨）'} — {regime_note}")
    if vix_caution:
        print(f"[Logic4] VIX慎重フラグ: {vix_note}")

    cur.execute("""
        SELECT ticker, COUNT(*) as cnt
        FROM price_data
        GROUP BY ticker
        HAVING COUNT(*) >= ?
    """, (MIN_BARS_DAILY,))
    tickers = [r["ticker"] for r in cur.fetchall()]
    print(f"[Logic4] 対象銘柄数: {len(tickers)}")

    sector_map = _build_sector_map(cur)

    picks = []
    trend_pass = entry_zone = 0

    for ticker in tickers:
        try:
            # D. 除外リスト
            if _is_excluded(ticker):
                continue

            cur.execute("""
                SELECT date, open, high, low, close, volume
                FROM price_data WHERE ticker = ?
                ORDER BY date ASC
            """, (ticker,))
            rows = cur.fetchall()
            if len(rows) < MIN_BARS_DAILY:
                continue

            C = [r["close"]  for r in rows]
            H = [r["high"]   for r in rows]
            L = [r["low"]    for r in rows]
            V = [r["volume"] for r in rows]
            i = len(C) - 1

            ema20  = _ema(C, 20)
            ema50  = _ema(C, 50)
            ema200 = _ema(C, 200)
            atr_arr  = _atr(H, L, C)
            rsi_arr  = _rsi(C)
            vol_ma20 = _sma(V, 20)

            e20, e50, e200 = ema20[i], ema50[i], ema200[i]
            if any(v is None for v in (e20, e50, e200)):
                continue

            # B. トレンド: 株価 > 200EMA かつ 50EMA > 200EMA
            if not (C[i] > e200 and e50 > e200):
                continue
            perfect_order = "full" if (C[i] > e20 > e50 > e200) else "quasi"

            # B. 3ヶ月騰落率 > 0%
            if i < PERF_3M_DAYS:
                continue
            perf_3m = (C[i] - C[i - PERF_3M_DAYS]) / C[i - PERF_3M_DAYS] * 100
            if perf_3m <= 0:
                continue
            perf_6m = ((C[i] - C[i - PERF_6M_DAYS]) / C[i - PERF_6M_DAYS] * 100
                       if i >= PERF_6M_DAYS else None)

            # C. 流動性: 20日平均出来高 >= 100万株
            avg_vol = vol_ma20[i]
            if avg_vol is None or avg_vol < MIN_AVG_VOLUME:
                continue

            trend_pass += 1

            leverage_status, leverage_penalty, leverage_note = _leveraged_etf_adjustment(ticker, C[i])
            if leverage_status == "exclude":
                print(f"[Logic4] {ticker} 除外: {leverage_note} price=${C[i]:.2f}")
                continue

            # エントリー圏: 20 or 50日EMA タッチ/接近（近い方を採用）
            touch_ema = touch_label = touch_dist = None
            for lbl, ev in (("20日EMA", e20), ("50日EMA", e50)):
                dv = (C[i] - ev) / ev * 100
                if abs(dv) <= EMA_NEAR_PCT:
                    if touch_dist is None or abs(dv) < abs(touch_dist):
                        touch_ema, touch_label, touch_dist = ev, lbl, dv
            if touch_ema is None:
                continue  # EMA 圏外＝まだ押し目になっていない
            touched = abs(touch_dist) <= EMA_TOUCH_PCT

            # 決算7日以内は除外（エントリー圏の銘柄だけ yfinance 照会＝API負荷を半減）
            earnings_block, earnings_date = _earnings_within_days(ticker, days=7)
            if earnings_block:
                print(f"[Logic4] {ticker} 除外: 決算7日以内 ({earnings_date})")
                continue

            # 出来高枯れ（売り枯れ）
            recent_vol = sum(V[i - 2:i + 1]) / 3 if i >= 2 else V[i]
            vol_dryup = bool(avg_vol and recent_vol < avg_vol * VOL_DRYUP_RATIO)

            entry_zone += 1

            # D/E. SL（押し安値の少し下＝1R）/ TP1（+1.5R）
            swing_low = min(L[max(0, i - STOP_LOOKBACK + 1):i + 1])
            atr_v = atr_arr[i] or 0.0
            sl_price = round(swing_low - 0.1 * atr_v, 2)
            entry = C[i]
            r_value = entry - sl_price
            if r_value <= 0:
                continue
            tp1_price    = round(entry + TP1_R * r_value, 2)   # +1.5R 半分利確
            target_price = round(entry + 3.0 * r_value, 2)     # 参考（トレーリングで伸ばす）
            rr = round((tp1_price - entry) / r_value, 2)       # = 1.5

            rsi_now  = rsi_arr[i]
            rsi_flag = rsi_now is not None and 30 <= rsi_now <= 50

            # 判定
            reasons = [f"{touch_label}{'タッチ' if touched else '接近'}（乖離{touch_dist:+.1f}%）"]
            if vol_dryup:
                reasons.append("出来高枯れ（売り枯れ＝押し目良好）")
            if rsi_flag:
                reasons.append(f"RSI {rsi_now:.0f}（押し目ゾーン30-50）")

            confluence = (1 if touched else 0) + (1 if vol_dryup else 0) + (1 if rsi_flag else 0)
            reji_sapo = "none"
            reji_sapo_price = _detect_reji_sapo_near_ema(H, C, i, touch_ema)
            if reji_sapo_price is not None:
                reji_sapo = "confirmed"
                confluence += 1
                reasons.append(f"レジサポ転換の節目と重なり（${reji_sapo_price:.2f}）")

            # v3 C項: 出来高枯れ（売り枯れ）を最優先の必須条件にする。
            # 「下げに大きな出来高を伴う」タッチ（＝出来高枯れなし）は売り圧が残るため格下げ。
            if touched and vol_dryup:
                verdict = "最優先候補"
                confidence = 0.72 + (0.10 if rsi_flag else 0.0) + (0.05 if perfect_order == "full" else 0.0)
            elif touched:
                verdict = "サポート接近中"   # タッチ済みだが売り枯れ未確認＝引き金前の様子見
                confidence = 0.55 + (0.05 if rsi_flag else 0.0)
            else:
                verdict = "サポート接近中"
                confidence = 0.50

            if reji_sapo == "confirmed":
                confidence += 0.05
            if leverage_penalty:
                confidence -= leverage_penalty
            confidence = max(0.0, min(0.99, confidence))

            # 地合い NG: 候補は見せるが「休む」警告で減点（v3 A項）
            v3_signals = []
            if regime_ok:
                v3_signals.append(f"地合いOK: {regime_note}")
            else:
                verdict = "地合いNG（休む推奨）"
                confidence = min(confidence, 0.30)
                v3_signals.append(f"⚠️地合いNG: {regime_note} → 指数が200日EMA割れ。v3は無理に買わず休む")
            if vix_caution:
                v3_signals.append(
                    f"⚠️VIX急騰週: {vix_note}。反発足は『陽線＋翌日も前日高値超え』までダマシ確認を厚く"
                )
            if leverage_note and leverage_status != "exclude":
                v3_signals.append(leverage_note)

            v3_signals += [
                "引き金（当日確認）: 反発足を確認（陽線確定 or 前日高値超え）してからエントリー。落下中は掴まない",
                f"損切り: ${sl_price}（1R = {r_value:.2f}）に固定・裁量で動かさない",
                f"第1利確: +1.5R = ${tp1_price} で半分を確定",
                "残り半分: 20日EMA を終値で割るまで保有（トレーリング）",
                f"保有上限: {HOLDING_LIMIT}営業日経過で含み損なら全決済",
            ]

            picks.append({
                "ticker":           ticker,
                "scan_date":        date.today().isoformat(),
                "perfect_order":    perfect_order,
                "perf_3m":          round(perf_3m, 2),
                "perf_6m":          round(perf_6m, 2) if perf_6m is not None else None,
                "avg_vol_20d":      round(avg_vol),
                "dow_trend":        "up",
                "support_price":    round(touch_ema, 2),
                "confluence":       confluence,
                "support_reasons":  json.dumps(reasons, ensure_ascii=False),
                "reji_sapo":        reji_sapo,
                "risk_reward":      rr,
                "entry_price":      round(entry, 2),
                "stop_price":       sl_price,
                "tp1_price":        tp1_price,
                "target_price":     target_price,
                "rsi":              round(rsi_now, 1) if rsi_now else None,
                "rsi_flag":         1 if rsi_flag else 0,
                "macd_div_flag":    0,
                "fib_confluence":   None,
                "atr":              round(atr_v, 4) if atr_v else None,
                "verdict":          verdict,
                "confidence":       round(confidence, 3),
                "composite_score":  round(confidence * 100, 1),
                "sector":           sector_map.get(ticker),
                "current_price":    round(entry, 2),
                "holding_days_est": HOLDING_LIMIT,
                "signals_json":     json.dumps(v3_signals, ensure_ascii=False),
                "price_to_support_pct": round(touch_dist, 1),
                "h1_trigger":       None,
                "h4_structure":     "neutral",
            })

        except Exception as e:
            print(f"[Logic4] {ticker} エラー: {e}")

    # ── 保存 ────────────────────────────────────────────────────────────────
    cur.execute("DELETE FROM logic4_picks")
    for p in picks:
        cur.execute("""
            INSERT INTO logic4_picks
                (ticker, scan_date, perfect_order, perf_3m, perf_6m, avg_vol_20d,
                 dow_trend, support_price, confluence, support_reasons, reji_sapo,
                 risk_reward, entry_price, stop_price, tp1_price, target_price,
                 rsi, rsi_flag, macd_div_flag, fib_confluence, atr,
                 verdict, confidence, composite_score, sector, current_price,
                 holding_days_est, signals_json,
                 price_to_support_pct, h1_trigger, h4_structure)
            VALUES
                (:ticker, :scan_date, :perfect_order, :perf_3m, :perf_6m, :avg_vol_20d,
                 :dow_trend, :support_price, :confluence, :support_reasons, :reji_sapo,
                 :risk_reward, :entry_price, :stop_price, :tp1_price, :target_price,
                 :rsi, :rsi_flag, :macd_div_flag, :fib_confluence, :atr,
                 :verdict, :confidence, :composite_score, :sector, :current_price,
                 :holding_days_est, :signals_json,
                 :price_to_support_pct, :h1_trigger, :h4_structure)
        """, p)
    conn.commit()
    conn.close()

    order = {"最優先候補": 0, "サポート接近中": 1, "地合いNG（休む推奨）": 2}
    picks.sort(key=lambda x: (order.get(x["verdict"], 3), -x["confidence"]))
    print(f"[Logic4] 完了 — トレンド通過:{trend_pass} エントリー圏:{entry_zone} 採用:{len(picks)}")
    for p in picks[:5]:
        print(f"  {p['ticker']:8s} {p['verdict']} RR={p['risk_reward']:.2f} "
              f"乖離={p['price_to_support_pct']:+.1f}% conf={p['confidence']:.2f}")
    return picks


if __name__ == "__main__":
    run()
