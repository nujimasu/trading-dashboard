/**
 * Pick normalizer — モード別に異なる pick オブジェクトを統一形に変換する。
 *
 * 入力モード:
 *   weekly        : picks-table 経由（週次 weekly_picks）
 *   daily         : picks-table 経由（日次 daily_picks）
 *   take-profit   : picks-table 経由（利確シグナル）
 *   hybrid-entry  : picks-table 経由（ロジック1: weekly + daily マージ）
 *   logic2        : tech-picks-table 経由
 *   logic3        : tech-picks-table 経由
 *   logic4        : tech-picks-table 経由
 *
 * 出力 (NormalizedPick):
 *   ticker, direction, confidence(0-100), rr, primarySignals[], sector,
 *   holdingDays, verdict, prices{entry,stop,tp1,target,current?}, raw
 */

const TECH_MODES = new Set(["logic2", "logic3", "logic4"]);

export function normalizePick(p, mode) {
  const isTech = TECH_MODES.has(mode);

  // ── confidence ─────────────────────────────────────────────
  // Tech 系は 0〜1 の小数、Funda 系は 0〜100 のスコア
  let confidence;
  if (isTech) {
    confidence = (p.confidence ?? 0) * 100;
  } else {
    confidence = p.composite_score ?? 0;
  }
  confidence = Math.max(0, Math.min(100, confidence));

  // ── primary signals (上位3つ) ───────────────────────────────
  let primarySignals = [];
  if (isTech) {
    if (Array.isArray(p.active_signals)) {
      primarySignals = p.active_signals.slice(0, 3);
    } else if (Array.isArray(p.signals)) {
      primarySignals = p.signals.slice(0, 3).map(s => s.label || s);
    }
  } else {
    // Funda 系: technical_summary.entry_reasons の先頭3つ
    const reasons = p.technical_summary?.entry_reasons || [];
    primarySignals = reasons.slice(0, 3);
  }

  // ── verdict ────────────────────────────────────────────────
  let verdict;
  if (mode === "take-profit") {
    verdict = p.take_profit_verdict || "HOLD";
  } else if (mode === "daily" || mode === "hybrid-entry") {
    verdict = p.daily_verdict || p.verdict;
  } else if (isTech) {
    verdict = p.daily_verdict;
  } else {
    verdict = p.verdict;
  }

  // ── RR ──────────────────────────────────────────────────────
  let rr;
  if (mode === "daily" || mode === "hybrid-entry" || mode === "take-profit") {
    rr = p.adjusted_rr ?? p.weekly_rr ?? p.risk_reward;
  } else {
    rr = p.risk_reward;
  }

  return {
    ticker:        p.ticker,
    direction:     p.direction || "LONG",
    confidence,
    primarySignals,
    rr:            rr ?? null,
    sector:        p.sector || p.fundamental_summary?.sector || null,
    holdingDays:   p.holding_days_est ?? null,
    verdict:       verdict ?? null,
    tier:          p.tier || null,
    prices: {
      entry:   p.entry_price ?? null,
      stop:    p.stop_price ?? null,
      tp1:     p.tp1_price ?? null,
      target:  p.target_price ?? null,
      current: p.current_price ?? null,
    },
    raw: p,
  };
}

// ── 共通 helpers ─────────────────────────────────────────────────
export function holdingBucket(days) {
  if (!days) return { label: "—", css: "hold-unknown" };
  if (days <= 10) return { label: "短期", css: "hold-short", note: "1〜2週間" };
  if (days <= 25) return { label: "中期", css: "hold-mid",   note: "2〜5週間" };
  return            { label: "長期", css: "hold-long",  note: "1ヶ月以上" };
}

export function confidenceTier(pct) {
  if (pct >= 75) return { label: "高", css: "conf-high" };
  if (pct >= 60) return { label: "中", css: "conf-mid"  };
  return            { label: "低", css: "conf-low"  };
}

export function verdictMeta(v) {
  const map = {
    BUY:          { label: "買い",          css: "verdict-buy" },
    WATCH:        { label: "様子見",        css: "verdict-watch" },
    "NO-BUY":     { label: "見送り",        css: "verdict-nobuy" },
    ENTRY_NOW:    { label: "今日エントリー", css: "verdict-entry" },
    WAIT:         { label: "待機",          css: "verdict-wait" },
    PASSED:       { label: "通過済",        css: "verdict-passed" },
    SHORT_SELL:   { label: "売り",          css: "verdict-short" },
    SHORT_WATCH:  { label: "ショート様子見", css: "verdict-short-watch" },
    TAKE_PROFIT:  { label: "利確推奨",      css: "verdict-short" },
    REDUCE:       { label: "一部利確",      css: "verdict-short-watch" },
    WATCH_EXIT:   { label: "出口注視",      css: "verdict-watch" },
    HOLD:         { label: "継続保有",      css: "verdict-buy" },
  };
  return map[v] || (v ? { label: v, css: "" } : null);
}
