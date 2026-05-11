/**
 * 📈 取引分析 — 実取引（positions テーブル）の弱点発見ダッシュボード
 *
 * Phase 1 セクション:
 *  ① サマリーカード  ② 自動インサイト
 *  ③ 保有期間×成績  ④ リスクリワード散布図
 *  ⑤ 銘柄タイプ別表  ⑥ 全トレード フィルタテーブル
 */
import { apiFetch } from "../utils/api.js";

const _state = {
  trades: { closed: [], open: [] },
  months: [],
  tagPresets: [],
  filter: {
    search: "",
    result: "all",   // all | win | loss
    type:   "all",   // all | stock | lev_etf
    bucket: "all",   // all | low | mid | high | unknown
    month:  "all",   // all | YYYY-MM
    tag:    "all",   // all | <tag name>
    sort:   "exit_date_desc",
  },
  compare: {
    a_start: null, a_end: null,
    b_start: null, b_end: null,
  },
};

const TABS = [
  { id: "overview", label: "📊 概要" },
  { id: "strategy", label: "🔍 戦略分析" },
  { id: "compare",  label: "⚖️ 期間比較" },
  { id: "trades",   label: "📋 トレード一覧" },
];

function _readActiveTab() {
  const m = (typeof window !== "undefined" && window.location.hash || "").match(/tab=([a-z]+)/);
  const id = m && m[1];
  return TABS.some(t => t.id === id) ? id : "overview";
}

function _renderTabsNav(activeId) {
  return `
    <nav class="ta-tabs" role="tablist">
      ${TABS.map(t => `
        <button class="ta-tab ${t.id === activeId ? "ta-tab-active" : ""}"
                data-tab="${t.id}" role="tab" aria-selected="${t.id === activeId}">
          ${t.label}
        </button>`).join("")}
    </nav>`;
}

function _activateTab(root, id) {
  root.querySelectorAll(".ta-tab").forEach(b => {
    const on = b.dataset.tab === id;
    b.classList.toggle("ta-tab-active", on);
    b.setAttribute("aria-selected", on ? "true" : "false");
  });
  root.querySelectorAll(".ta-tab-panel").forEach(p => {
    p.classList.toggle("ta-tab-panel-active", p.dataset.tab === id);
  });
}

function _bindTabs(root) {
  root.querySelectorAll(".ta-tab").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.tab;
      _activateTab(root, id);
      const newHash = `#tab=${id}`;
      if (window.location.hash !== newHash) {
        history.replaceState(null, "", newHash);
      }
    });
  });
}

export async function renderTradeAnalytics(container) {
  container.innerHTML = `
    <div class="section-title">📈 取引分析</div>
    <div class="ta-content"><div class="loading"><div class="spinner"></div></div></div>`;
  const root = container.querySelector(".ta-content");

  try {
    const [summary, monthly, equity, insights, hold, scatter, byType, byTags, cutLoss, trades] = await Promise.all([
      apiFetch("/api/trade-analytics/summary"),
      apiFetch("/api/trade-analytics/monthly"),
      apiFetch("/api/trade-analytics/equity-curve"),
      apiFetch("/api/trade-analytics/insights"),
      apiFetch("/api/trade-analytics/holding-buckets"),
      apiFetch("/api/trade-analytics/scatter"),
      apiFetch("/api/trade-analytics/by-type"),
      apiFetch("/api/trade-analytics/by-tags"),
      apiFetch("/api/trade-analytics/cut-loss"),
      apiFetch("/api/trade-analytics/trades"),
    ]);
    _state.tagPresets = byTags.presets || [];
    _state.trades = trades;
    _state.months = monthly.months || [];
    // 既定の比較期間: 前半 vs 後半
    if (_state.months.length >= 2) {
      const mid = Math.floor(_state.months.length / 2);
      _state.compare.a_start = _state.months[0].month;
      _state.compare.a_end   = _state.months[mid - 1].month;
      _state.compare.b_start = _state.months[mid].month;
      _state.compare.b_end   = _state.months[_state.months.length - 1].month;
    }

    if (!summary || !summary.trades) {
      root.innerHTML = `
        <div class="empty-state">決済済みトレードがまだありません。<br>
        「💼 保有ポジション」から決済すると、ここに分析が表示されます。</div>`;
      return;
    }

    root.innerHTML = `
      ${_renderTabsNav(_readActiveTab())}
      <section class="ta-tab-panel" data-tab="overview">
        ${_renderSummary(summary)}
        ${_renderMonthly(monthly.months)}
        ${_renderEquityCurve(equity)}
        ${_renderInsights(insights.cards)}
      </section>
      <section class="ta-tab-panel" data-tab="strategy">
        ${_renderCutLoss(cutLoss)}
        ${_renderHolding(hold.buckets)}
        ${_renderScatter(scatter.points)}
        ${_renderByType(byType)}
        ${_renderByTags(byTags)}
      </section>
      <section class="ta-tab-panel" data-tab="compare">
        ${_renderCompareShell()}
      </section>
      <section class="ta-tab-panel" data-tab="trades">
        ${_renderTradesTable(monthly.months)}
      </section>
    `;
    _activateTab(root, _readActiveTab());
    _bindTabs(root);
    _bindFilterControls(root);
    _bindMonthlyClicks(root);
    _bindCompareControls(root);
    _bindInsightActions(root, container);
    await _loadCompare(root);
    _bindCsvExport(root);
  } catch (e) {
    root.innerHTML = `<div class="empty-state">読み込み失敗: ${_esc(e.message)}</div>`;
  }
}

// ── ① サマリー ────────────────────────────────────────────
function _renderSummary(s) {
  const pnlCls = s.total_pnl >= 0 ? "ta-pos" : "ta-neg";
  const expCls = s.expectancy >= 0 ? "ta-pos" : "ta-neg";
  const streakLabel = s.current_streak && s.current_streak.count
    ? `${s.current_streak.type === "win" ? "🔥" : "❄️"} ${s.current_streak.count}${s.current_streak.type === "win" ? "連勝" : "連敗"}`
    : "—";
  return `
    <div class="ta-summary">
      ${_metric("累計P/L", `$${_fmtNum(s.total_pnl)}`, pnlCls)}
      ${_metric("勝率", `${s.win_rate}%`)}
      ${_metric("PF", s.profit_factor != null ? s.profit_factor : "—")}
      ${_metric("RR比", s.rr != null ? s.rr : "—")}
      ${_metric("期待値/件", `$${_fmtNum(s.expectancy)}`, expCls)}
      ${_metric("勝/負", `${s.wins}/${s.losses}`)}
      ${_metric("最大利益", `$${_fmtNum(s.biggest_win)}`, "ta-pos")}
      ${_metric("最大損失", `$${_fmtNum(s.biggest_loss)}`, "ta-neg")}
      ${_metric("ストリーク", streakLabel)}
      ${_metric("保有中", `${s.open_count}件`)}
    </div>`;
}
function _metric(label, value, cls = "") {
  return `
    <div class="ta-metric">
      <div class="ta-metric-label">${label}</div>
      <div class="ta-metric-value ${cls}">${value}</div>
    </div>`;
}

// ── ①.5 月次トレンド ──────────────────────────────────────
function _renderMonthly(months) {
  if (!months || !months.length) return "";

  // バーチャート用 SVG
  const W = 720, H = 200, PADL = 50, PADR = 16, PADT = 12, PADB = 40;
  const innerW = W - PADL - PADR;
  const innerH = H - PADT - PADB;
  const n = months.length;
  const barW = innerW / n * 0.7;
  const gap  = innerW / n * 0.3;
  const maxAbs = Math.max(...months.map(m => Math.abs(m.total_pnl)), 1);
  const yScale = v => PADT + innerH * (1 - (v + maxAbs) / (2 * maxAbs));
  const yZero  = yScale(0);

  // 累計エクイティライン
  const cumMax = Math.max(...months.map(m => Math.abs(m.cumulative_pnl)), 1);
  const yScaleCum = v => PADT + innerH * (1 - (v + cumMax) / (2 * cumMax));
  const linePts = months.map((m, i) => {
    const cx = PADL + (i + 0.5) * (barW + gap);
    return `${cx},${yScaleCum(m.cumulative_pnl)}`;
  }).join(" ");

  const bars = months.map((m, i) => {
    const x = PADL + i * (barW + gap) + gap/2;
    const v = m.total_pnl;
    const fill = v >= 0 ? "var(--green)" : "var(--red)";
    const top = v >= 0 ? yScale(v) : yZero;
    const h   = Math.abs(yScale(v) - yZero);
    const dot = `<circle cx="${x + barW/2}" cy="${yScaleCum(m.cumulative_pnl)}" r="3" fill="#fbbf24" />`;
    return `
      <g class="ta-month-bar" data-month="${m.month}" style="cursor:pointer">
        <rect x="${x}" y="${top}" width="${barW}" height="${h}" fill="${fill}" fill-opacity="0.85" rx="2">
          <title>${m.month}
件数: ${m.trades} (${m.wins}勝/${m.losses}敗)
勝率: ${m.win_rate}%
P/L: ${v >= 0 ? "+" : ""}$${v.toFixed(2)}
累計: ${m.cumulative_pnl >= 0 ? "+" : ""}$${m.cumulative_pnl.toFixed(2)}
ベスト: ${m.best.ticker} +$${m.best.pnl.toFixed(2)}
ワースト: ${m.worst.ticker} $${m.worst.pnl.toFixed(2)}</title>
        </rect>
        ${dot}
        <text x="${x + barW/2}" y="${H - PADB + 16}" fill="var(--text-muted)" font-size="11" text-anchor="middle">${m.month.slice(2)}</text>
        <text x="${x + barW/2}" y="${v >= 0 ? top - 4 : top + h + 12}" fill="${v >= 0 ? 'var(--green)' : 'var(--red)'}" font-size="10" font-weight="700" text-anchor="middle">${v >= 0 ? "+" : ""}$${Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(1)}</text>
      </g>`;
  }).join("");

  // 月別テーブル
  const rows = months.map(m => {
    const pnlCls = m.total_pnl >= 0 ? "ta-pos" : "ta-neg";
    const cumCls = m.cumulative_pnl >= 0 ? "ta-pos" : "ta-neg";
    const wrColor = m.win_rate >= 50 ? "var(--green)"
                  : m.win_rate >= 40 ? "var(--text-primary)"
                  : "var(--red)";
    return `
      <tr class="ta-month-row" data-month="${m.month}" style="cursor:pointer">
        <td><strong>${m.month}</strong></td>
        <td>${m.trades}</td>
        <td style="color:${wrColor};font-weight:700">${m.win_rate}%</td>
        <td>${m.wins}/${m.losses}</td>
        <td class="${pnlCls}">${m.total_pnl >= 0 ? "+" : ""}$${_fmtNum(m.total_pnl)}</td>
        <td class="${cumCls}">${m.cumulative_pnl >= 0 ? "+" : ""}$${_fmtNum(m.cumulative_pnl)}</td>
        <td>${m.avg_pct >= 0 ? "+" : ""}${_fmtNum(m.avg_pct)}%</td>
        <td>${m.profit_factor != null ? m.profit_factor : "—"}</td>
        <td><span class="ta-month-best">${_esc(m.best.ticker)} <span class="ta-pos">+$${_fmtNum(m.best.pnl)}</span></span></td>
        <td><span class="ta-month-worst">${_esc(m.worst.ticker)} <span class="ta-neg">$${_fmtNum(m.worst.pnl)}</span></span></td>
      </tr>`;
  }).join("");

  return `
    <h3 class="ta-h">📅 月次トレンド <span class="ta-h-sub">（バー or 行をクリックで下の全トレードがその月にフィルタされます。黄点=累計エクイティ）</span></h3>
    <div class="ta-monthly-chart">
      <svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto;display:block">
        <line x1="${PADL}" x2="${W-PADR}" y1="${yZero}" y2="${yZero}" stroke="rgba(148,163,184,.5)" stroke-width="1" />
        <text x="${PADL-6}" y="${yZero+4}" fill="var(--text-muted)" font-size="10" text-anchor="end">$0</text>
        ${bars}
        <polyline points="${linePts}" fill="none" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="4,3" opacity="0.7" />
      </svg>
    </div>
    <div class="ta-table-wrap">
      <table class="ta-table">
        <thead>
          <tr>
            <th>月</th><th>件数</th><th>勝率</th><th>勝/負</th>
            <th>累計P/L</th><th>累計エクイティ</th><th>平均%</th><th>PF</th>
            <th>ベスト</th><th>ワースト</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

function _bindMonthlyClicks(root) {
  const select = (month) => {
    _state.filter.month = month;
    const sel = root.querySelector(".ta-tt-month");
    if (sel) sel.value = month;
    // ハイライト更新
    root.querySelectorAll(".ta-month-bar, .ta-month-row").forEach(el => {
      el.classList.toggle("ta-month-active", el.dataset.month === month);
    });
    _renderTradesTbody(root);
    // 全トレードまでスクロール
    const tbl = root.querySelector("#ta-trades-table");
    if (tbl) tbl.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  root.querySelectorAll(".ta-month-bar").forEach(el => {
    el.addEventListener("click", () => select(el.dataset.month));
  });
  root.querySelectorAll(".ta-month-row").forEach(el => {
    el.addEventListener("click", () => select(el.dataset.month));
  });
}

// ── ①.6 日次エクイティ & ドローダウン ─────────────────────
function _renderEquityCurve(eq) {
  const pts = eq && eq.points;
  const st  = eq && eq.stats;
  if (!pts || pts.length < 2) return "";

  const W = 720, PADL = 50, PADR = 16;
  const H_EQ = 180, H_DD = 90, GAP = 24;
  const PADT = 12, PADB = 28;
  const totalH = PADT + H_EQ + GAP + H_DD + PADB;
  const innerW = W - PADL - PADR;
  const n = pts.length;

  const xScale = i => PADL + (i / (n - 1)) * innerW;

  // ── エクイティスケール ───────────────
  const eqMin = Math.min(0, ...pts.map(p => p.equity));
  const eqMax = Math.max(0, ...pts.map(p => p.peak));
  const eqRange = (eqMax - eqMin) || 1;
  const yEq = v => PADT + (1 - (v - eqMin) / eqRange) * H_EQ;
  const yZeroEq = yEq(0);

  // ── DDスケール ───────────────────────
  const ddMin = Math.min(0, ...pts.map(p => p.drawdown));
  const ddRange = Math.abs(ddMin) || 1;
  const ddTop  = PADT + H_EQ + GAP;
  const yDd = v => ddTop + ((-v) / ddRange) * H_DD;     // 0 → 上、ddMin → 下
  const yZeroDd = yDd(0);

  // ── パス生成 ─────────────────────────
  const eqPath  = pts.map((p, i) => `${i ? "L" : "M"}${xScale(i).toFixed(1)},${yEq(p.equity).toFixed(1)}`).join("");
  const peakPath = pts.map((p, i) => `${i ? "L" : "M"}${xScale(i).toFixed(1)},${yEq(p.peak).toFixed(1)}`).join("");
  // DD は塗りつぶしエリア (下向き)
  const ddArea = pts.map((p, i) => `${i ? "L" : "M"}${xScale(i).toFixed(1)},${yDd(p.drawdown).toFixed(1)}`).join("")
                + ` L${xScale(n-1).toFixed(1)},${yZeroDd.toFixed(1)} L${xScale(0).toFixed(1)},${yZeroDd.toFixed(1)} Z`;

  // ── X軸: 月ラベル (月初を見つける) ──
  const monthTicks = [];
  let lastMonth = "";
  pts.forEach((p, i) => {
    const m = p.date.slice(0, 7);
    if (m !== lastMonth) {
      monthTicks.push({ i, label: p.date.slice(2, 7) });  // YY-MM
      lastMonth = m;
    }
  });
  const xLabels = monthTicks.map(t => `
    <text x="${xScale(t.i)}" y="${totalH - 8}" fill="var(--text-muted)" font-size="10" text-anchor="middle">${t.label}</text>
    <line x1="${xScale(t.i)}" x2="${xScale(t.i)}" y1="${PADT}" y2="${ddTop + H_DD}" stroke="rgba(148,163,184,.08)" />
  `).join("");

  // ── マーカー: max_dd 点 / 起点ピーク点 ──
  const idxByDate = d => pts.findIndex(p => p.date === d);
  const iMaxDd  = idxByDate(st.max_dd_date);
  const iPeak   = idxByDate(st.dd_peak_date);
  const iRecov  = st.recovery_date ? idxByDate(st.recovery_date) : -1;

  const marker = (i, color, label, yFn, val) => i < 0 ? "" : `
    <circle cx="${xScale(i)}" cy="${yFn(val)}" r="4" fill="${color}" stroke="#0b1220" stroke-width="2" />
    <text x="${xScale(i)}" y="${yFn(val) - 8}" fill="${color}" font-size="10" font-weight="700" text-anchor="middle">${label}</text>`;

  const markers = `
    ${marker(iPeak,  "#fbbf24", "Peak",  yEq, pts[iPeak]?.peak  || 0)}
    ${marker(iMaxDd, "#ef4444", "Bottom", yEq, pts[iMaxDd]?.equity || 0)}
    ${iRecov >= 0 ? marker(iRecov, "#22c55e", "Recover", yEq, pts[iRecov]?.equity || 0) : ""}
  `;

  // ── 軸: equity Y ────────────────────
  const eqTicks = [eqMin, (eqMin + eqMax) / 2, eqMax].map(v => Math.round(v));
  const ddTicks = [0, ddMin/2, ddMin].map(v => Math.round(v));
  const eqYLabels = eqTicks.map(v => `
    <line x1="${PADL}" x2="${W-PADR}" y1="${yEq(v)}" y2="${yEq(v)}" stroke="${v===0?'rgba(148,163,184,.5)':'rgba(148,163,184,.12)'}" stroke-dasharray="${v===0?'0':'3,3'}" />
    <text x="${PADL-6}" y="${yEq(v)+4}" fill="var(--text-muted)" font-size="10" text-anchor="end">$${_fmtNum(v,0)}</text>
  `).join("");
  const ddYLabels = ddTicks.map(v => `
    <line x1="${PADL}" x2="${W-PADR}" y1="${yDd(v)}" y2="${yDd(v)}" stroke="${v===0?'rgba(148,163,184,.5)':'rgba(148,163,184,.12)'}" stroke-dasharray="${v===0?'0':'3,3'}" />
    <text x="${PADL-6}" y="${yDd(v)+4}" fill="var(--text-muted)" font-size="10" text-anchor="end">$${_fmtNum(v,0)}</text>
  `).join("");

  // ── 統計カード ──────────────────────
  const ddPctOfPeak = st.dd_peak_value > 0
      ? ` (${(st.max_dd / st.dd_peak_value * 100).toFixed(1)}%)`
      : "";
  const recoveryLbl = st.recovery_days != null
      ? `${st.recovery_days}日`
      : `未回復 🔻`;
  const sharpeBadge = st.sharpe_like_daily == null ? "—"
      : (st.sharpe_like_daily >= 0.3 ? `${st.sharpe_like_daily} 👍`
      :  st.sharpe_like_daily >= 0    ? `${st.sharpe_like_daily}`
      :                                 `${st.sharpe_like_daily} ⚠️`);

  const stats = `
    <div class="ta-eq-stats">
      ${_metric("現在エクイティ", `$${_fmtNum(st.current_equity)}`, st.current_equity >= 0 ? "ta-pos" : "ta-neg")}
      ${_metric("ATH",           `$${_fmtNum(st.all_time_high)}`,  "ta-pos")}
      ${_metric("Max DD",        `$${_fmtNum(st.max_dd)}${ddPctOfPeak}`, "ta-neg")}
      ${_metric("DD期間 (ピーク→底)", `${st.dd_duration_days || 0}日`)}
      ${_metric("回復",          recoveryLbl, st.recovery_days != null ? "ta-pos" : "ta-neg")}
      ${_metric("Recovery Factor", st.recovery_factor != null ? st.recovery_factor : "—")}
      ${_metric("現在のDD",      `$${_fmtNum(st.current_dd)}`, st.current_dd < 0 ? "ta-neg" : "")}
      ${_metric("日次Sharpe風",  sharpeBadge)}
    </div>`;

  return `
    <h3 class="ta-h">📉 エクイティ & ドローダウン
      <span class="ta-h-sub">（決済日ベースの日次累計。${st.trading_days}取引日 / ${st.calendar_days}カレンダー日）</span>
    </h3>
    ${stats}
    <div class="ta-eq-chart">
      <svg viewBox="0 0 ${W} ${totalH}" style="width:100%;height:auto;display:block">
        ${xLabels}
        ${eqYLabels}
        ${ddYLabels}
        <!-- equity area fill -->
        <defs>
          <linearGradient id="ta-eq-grad" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%"  stop-color="#22c55e" stop-opacity="0.35" />
            <stop offset="100%" stop-color="#22c55e" stop-opacity="0" />
          </linearGradient>
          <linearGradient id="ta-dd-grad" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%"  stop-color="#ef4444" stop-opacity="0.05" />
            <stop offset="100%" stop-color="#ef4444" stop-opacity="0.45" />
          </linearGradient>
        </defs>
        <!-- equity area -->
        <path d="${eqPath} L${xScale(n-1)},${yZeroEq} L${xScale(0)},${yZeroEq} Z" fill="url(#ta-eq-grad)" />
        <!-- peak (high-water-mark) reference line -->
        <path d="${peakPath}" fill="none" stroke="#fbbf24" stroke-width="1" stroke-dasharray="3,3" opacity="0.7" />
        <!-- equity line -->
        <path d="${eqPath}" fill="none" stroke="#22c55e" stroke-width="2" />
        <!-- markers -->
        ${markers}
        <!-- separator -->
        <line x1="${PADL}" x2="${W-PADR}" y1="${ddTop - GAP/2}" y2="${ddTop - GAP/2}" stroke="rgba(148,163,184,.15)" />
        <text x="${PADL}" y="${ddTop - 6}" fill="var(--text-muted)" font-size="10">Drawdown ($)</text>
        <!-- drawdown filled area -->
        <path d="${ddArea}" fill="url(#ta-dd-grad)" stroke="#ef4444" stroke-width="1.2" />
      </svg>
      <div class="ta-eq-legend">
        <span><span class="ta-line-swatch" style="background:#22c55e"></span>エクイティ</span>
        <span><span class="ta-line-swatch ta-line-dashed" style="background:#fbbf24"></span>HWM (高値水準)</span>
        <span><span class="ta-line-swatch" style="background:#ef4444"></span>ドローダウン</span>
        <span style="margin-left:auto;color:var(--text-muted)">🟡Peak → 🔴Bottom → 🟢Recover</span>
      </div>
    </div>`;
}

// ── ①.7 期間比較 ───────────────────────────────────────────
function _renderCompareShell() {
  const months = _state.months;
  if (months.length < 2) return "";
  const monthOpts = months.map(m => `<option value="${m.month}">${m.month}</option>`).join("");
  const c = _state.compare;
  return `
    <h3 class="ta-h">⚖️ 期間比較 <span class="ta-h-sub">（A と B を選んで「何が変わったか」を比較）</span></h3>
    <div class="ta-cmp-controls">
      <div class="ta-cmp-range">
        <span class="ta-cmp-tag ta-cmp-tag-a">A</span>
        <select class="ta-cmp-a-start">${_optsWithSel(monthOpts, c.a_start)}</select>
        <span class="ta-cmp-sep">〜</span>
        <select class="ta-cmp-a-end">${_optsWithSel(monthOpts, c.a_end)}</select>
      </div>
      <div class="ta-cmp-vs">vs</div>
      <div class="ta-cmp-range">
        <span class="ta-cmp-tag ta-cmp-tag-b">B</span>
        <select class="ta-cmp-b-start">${_optsWithSel(monthOpts, c.b_start)}</select>
        <span class="ta-cmp-sep">〜</span>
        <select class="ta-cmp-b-end">${_optsWithSel(monthOpts, c.b_end)}</select>
      </div>
      <div class="ta-cmp-presets">
        <button class="ta-cmp-preset" data-preset="recent-prev-1">直近1M vs 前1M</button>
        <button class="ta-cmp-preset" data-preset="recent-prev-3">直近3M vs 前3M</button>
        <button class="ta-cmp-preset" data-preset="halves">前半 vs 後半</button>
      </div>
    </div>
    <div id="ta-cmp-body" class="ta-cmp-body">
      <div class="loading"><div class="spinner"></div></div>
    </div>`;
}

function _optsWithSel(opts, selected) {
  if (!selected) return opts;
  return opts.replace(`value="${selected}"`, `value="${selected}" selected`);
}

function _bindCompareControls(root) {
  const els = {
    a_start: root.querySelector(".ta-cmp-a-start"),
    a_end:   root.querySelector(".ta-cmp-a-end"),
    b_start: root.querySelector(".ta-cmp-b-start"),
    b_end:   root.querySelector(".ta-cmp-b-end"),
  };
  Object.entries(els).forEach(([k, el]) => {
    if (!el) return;
    el.addEventListener("change", () => {
      _state.compare[k] = el.value;
      _loadCompare(root);
    });
  });
  root.querySelectorAll(".ta-cmp-preset").forEach(btn => {
    btn.addEventListener("click", () => {
      _applyPreset(btn.dataset.preset, root);
    });
  });
}

function _applyPreset(name, root) {
  const months = _state.months.map(m => m.month);
  const n = months.length;
  if (n < 2) return;
  let a_start, a_end, b_start, b_end;
  if (name === "recent-prev-1") {
    if (n < 2) return;
    b_start = b_end = months[n - 1];
    a_start = a_end = months[n - 2];
  } else if (name === "recent-prev-3") {
    if (n < 4) {
      const half = Math.max(1, Math.floor(n / 2));
      a_start = months[0]; a_end = months[half - 1];
      b_start = months[half]; b_end = months[n - 1];
    } else {
      a_start = months[n - 6] || months[0];
      a_end   = months[n - 4] || months[Math.max(0, n - 4)];
      b_start = months[n - 3];
      b_end   = months[n - 1];
    }
  } else if (name === "halves") {
    const mid = Math.floor(n / 2);
    a_start = months[0]; a_end = months[mid - 1];
    b_start = months[mid]; b_end = months[n - 1];
  }
  _state.compare = { a_start, a_end, b_start, b_end };
  // UI に反映
  ["a_start","a_end","b_start","b_end"].forEach(k => {
    const el = root.querySelector(`.ta-cmp-${k.replace("_","-")}`);
    if (el) el.value = _state.compare[k];
  });
  _loadCompare(root);
}

async function _loadCompare(root) {
  const body = root.querySelector("#ta-cmp-body");
  if (!body) return;
  const { a_start, a_end, b_start, b_end } = _state.compare;
  if (!a_start || !a_end || !b_start || !b_end) {
    body.innerHTML = `<div class="empty-state">期間を選択してください</div>`;
    return;
  }
  body.innerHTML = `<div class="loading"><div class="spinner"></div></div>`;
  try {
    const params = new URLSearchParams({ a_start, a_end, b_start, b_end });
    const data = await apiFetch(`/api/trade-analytics/compare?${params}`);
    body.innerHTML = _renderCompareBody(data);
  } catch (e) {
    body.innerHTML = `<div class="empty-state">読み込み失敗: ${_esc(e.message)}</div>`;
  }
}

function _renderCompareBody(data) {
  const a = data.period_a, b = data.period_b, d = data.delta;
  return `
    ${_cmpSummary(a, b, d)}
    ${_cmpByHolding(a.by_holding, b.by_holding)}
    ${_cmpByType(a.by_type, b.by_type)}
    ${_cmpTickers(a, b)}
  `;
}

function _cmpSummary(a, b, d) {
  const metrics = [
    { key: "trades",        label: "件数",        fmt: v => v },
    { key: "win_rate",      label: "勝率",        fmt: v => v == null ? "—" : v + "%", deltaUnit: "pt" },
    { key: "total_pnl",     label: "累計P/L",     fmt: v => v == null ? "—" : `$${_fmtNum(v)}`, deltaPrefix: "$" },
    { key: "expectancy",    label: "期待値/件",   fmt: v => v == null ? "—" : `$${_fmtNum(v)}`, deltaPrefix: "$" },
    { key: "profit_factor", label: "PF",          fmt: v => v == null ? "—" : v },
    { key: "rr",            label: "RR比",        fmt: v => v == null ? "—" : v },
    { key: "avg_win_pct",   label: "勝ち平均%",   fmt: v => v == null ? "—" : `+${v}%` },
    { key: "avg_loss_pct",  label: "負け平均%",   fmt: v => v == null ? "—" : `${v}%` },
    { key: "avg_hold",      label: "平均保有日",  fmt: v => v == null ? "—" : `${v}日` },
    { key: "lev_etf_pct",   label: "レバETF比率", fmt: v => v == null ? "—" : `${v}%` },
    { key: "intraday_pct",  label: "当日決済率",  fmt: v => v == null ? "—" : `${v}%` },
  ];
  const isImprovement = (key, dv) => {
    if (dv == null || dv === 0) return null;
    const lessIsBetter = ["avg_loss_pct", "lev_etf_pct", "intraday_pct", "biggest_loss"];
    // ※ avg_loss_pct はマイナスの値なので、大きい(=0に近い)方が良い
    if (key === "avg_loss_pct") return dv > 0;
    if (lessIsBetter.includes(key)) return dv < 0;
    return dv > 0;
  };
  const rows = metrics.map(m => {
    const va = a.summary[m.key], vb = b.summary[m.key], dv = d[m.key];
    const imp = isImprovement(m.key, dv);
    const dColor = imp === null ? "var(--text-muted)"
                 : imp           ? "var(--green)"
                 :                 "var(--red)";
    const dArrow = dv == null || dv === 0 ? "" : (dv > 0 ? "▲" : "▼");
    const dStr = dv == null ? "—"
               : `${dArrow} ${dv > 0 ? "+" : ""}${m.deltaPrefix || ""}${_fmtNum(dv)}${m.deltaUnit || ""}`;
    return `
      <tr>
        <td>${m.label}</td>
        <td>${m.fmt(va)}</td>
        <td>${m.fmt(vb)}</td>
        <td style="color:${dColor};font-weight:700">${dStr}</td>
      </tr>`;
  }).join("");
  return `
    <h4 class="ta-cmp-h">サマリー指標</h4>
    <div class="ta-table-wrap">
      <table class="ta-table ta-cmp-table">
        <thead><tr><th>指標</th><th><span class="ta-cmp-tag ta-cmp-tag-a">A</span> ${_esc(a.label)}</th><th><span class="ta-cmp-tag ta-cmp-tag-b">B</span> ${_esc(b.label)}</th><th>Δ (B − A)</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

function _cmpByHolding(aArr, bArr) {
  const labels = aArr.map(x => x.bucket);
  const aMap = Object.fromEntries(aArr.map(x => [x.bucket, x]));
  const bMap = Object.fromEntries(bArr.map(x => [x.bucket, x]));
  const rows = labels.map(lbl => {
    const xa = aMap[lbl] || {}, xb = bMap[lbl] || {};
    const wra = xa.win_rate, wrb = xb.win_rate;
    const dwr = (wra != null && wrb != null) ? (wrb - wra) : null;
    const pla = xa.total_pnl || 0, plb = xb.total_pnl || 0;
    return `
      <tr>
        <td>${_esc(lbl)}</td>
        <td>${xa.count || 0}</td>
        <td>${wra == null ? "—" : wra + "%"}</td>
        <td class="${pla >= 0 ? "ta-pos" : "ta-neg"}">$${_fmtNum(pla)}</td>
        <td>${xb.count || 0}</td>
        <td>${wrb == null ? "—" : wrb + "%"}</td>
        <td class="${plb >= 0 ? "ta-pos" : "ta-neg"}">$${_fmtNum(plb)}</td>
        <td style="color:${dwr == null ? "var(--text-muted)" : dwr > 0 ? "var(--green)" : dwr < 0 ? "var(--red)" : "var(--text-muted)"};font-weight:700">
          ${dwr == null ? "—" : (dwr > 0 ? "+" : "") + dwr.toFixed(1) + "pt"}
        </td>
      </tr>`;
  }).join("");
  return `
    <h4 class="ta-cmp-h">保有期間別</h4>
    <div class="ta-table-wrap">
      <table class="ta-table ta-cmp-table">
        <thead>
          <tr>
            <th rowspan="2">期間</th>
            <th colspan="3" class="ta-cmp-th-a">A</th>
            <th colspan="3" class="ta-cmp-th-b">B</th>
            <th rowspan="2">勝率Δ</th>
          </tr>
          <tr>
            <th>件数</th><th>勝率</th><th>P/L</th>
            <th>件数</th><th>勝率</th><th>P/L</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

function _cmpByType(aArr, bArr) {
  const allKeys = new Set([
    ...aArr.map(x => `${x.type}_${x.bucket}`),
    ...bArr.map(x => `${x.type}_${x.bucket}`),
  ]);
  const aMap = Object.fromEntries(aArr.map(x => [`${x.type}_${x.bucket}`, x]));
  const bMap = Object.fromEntries(bArr.map(x => [`${x.type}_${x.bucket}`, x]));
  const rows = Array.from(allKeys).map(k => {
    const xa = aMap[k] || {}, xb = bMap[k] || {};
    const ref = xa.type_label ? xa : xb;
    return `
      <tr>
        <td>${_esc(ref.type_label || "—")} × ${_esc(ref.bucket_label || "—")}</td>
        <td>${xa.count || 0}</td>
        <td>${xa.win_rate == null ? "—" : xa.win_rate + "%"}</td>
        <td class="${(xa.total_pnl||0) >= 0 ? "ta-pos" : "ta-neg"}">$${_fmtNum(xa.total_pnl || 0)}</td>
        <td>${xb.count || 0}</td>
        <td>${xb.win_rate == null ? "—" : xb.win_rate + "%"}</td>
        <td class="${(xb.total_pnl||0) >= 0 ? "ta-pos" : "ta-neg"}">$${_fmtNum(xb.total_pnl || 0)}</td>
      </tr>`;
  }).join("");
  if (!rows) return "";
  return `
    <h4 class="ta-cmp-h">銘柄タイプ別</h4>
    <div class="ta-table-wrap">
      <table class="ta-table ta-cmp-table">
        <thead>
          <tr>
            <th rowspan="2">タイプ × 価格帯</th>
            <th colspan="3" class="ta-cmp-th-a">A</th>
            <th colspan="3" class="ta-cmp-th-b">B</th>
          </tr>
          <tr>
            <th>件数</th><th>勝率</th><th>P/L</th>
            <th>件数</th><th>勝率</th><th>P/L</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

function _cmpTickers(a, b) {
  const list = (rows, color) => rows.length ? rows.map(r => `
    <li>
      <strong>${_esc(r.ticker)}</strong>
      <span class="${r.total_pnl >= 0 ? "ta-pos" : "ta-neg"}">$${_fmtNum(r.total_pnl)}</span>
      <span style="color:var(--text-muted);font-size:.74rem">(${r.count}件 ${r.win_rate}%)</span>
    </li>`).join("") : `<li style="color:var(--text-muted)">なし</li>`;

  return `
    <h4 class="ta-cmp-h">銘柄別 トップ5 / ワースト5</h4>
    <div class="ta-cmp-tickers-grid">
      <div class="ta-cmp-tickers-card">
        <div class="ta-cmp-tickers-head"><span class="ta-cmp-tag ta-cmp-tag-a">A</span> Top5</div>
        <ul class="ta-cmp-tickers-list">${list(a.top_tickers || [])}</ul>
      </div>
      <div class="ta-cmp-tickers-card">
        <div class="ta-cmp-tickers-head"><span class="ta-cmp-tag ta-cmp-tag-a">A</span> Worst5</div>
        <ul class="ta-cmp-tickers-list">${list(a.bot_tickers || [])}</ul>
      </div>
      <div class="ta-cmp-tickers-card">
        <div class="ta-cmp-tickers-head"><span class="ta-cmp-tag ta-cmp-tag-b">B</span> Top5</div>
        <ul class="ta-cmp-tickers-list">${list(b.top_tickers || [])}</ul>
      </div>
      <div class="ta-cmp-tickers-card">
        <div class="ta-cmp-tickers-head"><span class="ta-cmp-tag ta-cmp-tag-b">B</span> Worst5</div>
        <ul class="ta-cmp-tickers-list">${list(b.bot_tickers || [])}</ul>
      </div>
    </div>`;
}

// ── ② 自動インサイト ──────────────────────────────────────
function _renderInsights(cards) {
  if (!cards || !cards.length) return "";
  return `
    <h3 class="ta-h">💡 インサイト <span class="ta-h-sub">（🤖=自動ルール、✨=Claudeの分析、📌=ピン留め）</span></h3>
    <div class="ta-insight-grid">
      ${cards.map(c => _renderInsightCard(c)).join("")}
    </div>`;
}

function _bindInsightActions(root, container) {
  root.querySelectorAll(".ta-insight-btn-dismiss").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const id = btn.dataset.id;
      if (!confirm("このインサイトを閉じますか？")) return;
      try {
        await apiFetch(`/api/trade-analytics/insights/${id}`, { method: "DELETE" });
        await renderTradeAnalytics(container);
      } catch (err) { alert("失敗: " + err.message); }
    });
  });
  root.querySelectorAll(".ta-insight-btn-pin").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const id = btn.dataset.id;
      try {
        await apiFetch(`/api/trade-analytics/insights/${id}/pin`,
          { method: "POST", headers: {"Content-Type":"application/json"}, body: "{}" });
        await renderTradeAnalytics(container);
      } catch (err) { alert("失敗: " + err.message); }
    });
  });
}

function _renderInsightCard(c) {
  const isCustom = c.source && c.source !== "auto";
  const sourceBadge = isCustom
    ? `<span class="ta-insight-source ta-insight-source-custom" title="${_esc(c.source)}">✨</span>`
    : `<span class="ta-insight-source ta-insight-source-auto" title="自動ルール">🤖</span>`;
  const pinBadge = c.pinned ? `<span class="ta-insight-pin">📌</span>` : "";
  const actions = isCustom && c.db_id ? `
      <div class="ta-insight-actions">
        <button class="ta-insight-btn-pin" data-id="${c.db_id}" data-pinned="${c.pinned}" title="${c.pinned ? "ピン解除" : "ピン留め"}">${c.pinned ? "📌" : "🔘"}</button>
        <button class="ta-insight-btn-dismiss" data-id="${c.db_id}" title="閉じる">✕</button>
      </div>` : "";
  return `
    <div class="ta-insight ta-insight-${_esc(c.severity)} ${c.pinned ? "ta-insight-pinned" : ""}">
      ${actions}
      <div class="ta-insight-head">
        <span class="ta-insight-icon">${_esc(c.icon || "💡")}</span>
        <span class="ta-insight-title">${_esc(c.title)}</span>
        ${pinBadge}
        ${sourceBadge}
      </div>
      <div class="ta-insight-body">${_esc(c.body)}</div>
      ${c.metrics && c.metrics.length ? `
        <div class="ta-insight-metrics">
          ${c.metrics.map(m => `
            <div class="ta-insight-metric">
              <span class="ta-insight-metric-label">${_esc(m.label)}</span>
              <span class="ta-insight-metric-value">${_esc(m.value)}</span>
            </div>
          `).join("")}
        </div>` : ""}
    </div>`;
}

// ── ③ 保有期間×成績 ───────────────────────────────────────
function _renderHolding(buckets) {
  const max = Math.max(...buckets.map(b => Math.abs(b.total_pnl)), 1);
  const rows = buckets.map(b => {
    const wr = b.win_rate;
    const wrColor = wr == null ? "var(--text-muted)"
                  : wr >= 60 ? "var(--green)"
                  : wr >= 45 ? "var(--text-primary)"
                  : "var(--red)";
    const pnlCls = b.total_pnl >= 0 ? "ta-pos" : "ta-neg";
    const barW = Math.abs(b.total_pnl) / max * 100;
    const barColor = b.total_pnl >= 0 ? "var(--green)" : "var(--red)";
    return `
      <tr>
        <td>${_esc(b.bucket)}</td>
        <td>${b.count}</td>
        <td style="color:${wrColor};font-weight:700">${wr == null ? "—" : wr + "%"}</td>
        <td class="${pnlCls}">${b.total_pnl >= 0 ? "+" : ""}$${_fmtNum(b.total_pnl)}</td>
        <td>${b.avg_pct >= 0 ? "+" : ""}${_fmtNum(b.avg_pct)}%</td>
        <td style="width:30%">
          <div class="ta-bar-cell">
            <div class="ta-bar-fill" style="width:${barW}%;background:${barColor}"></div>
          </div>
        </td>
      </tr>`;
  }).join("");
  return `
    <h3 class="ta-h">📊 保有期間別の成績</h3>
    <div class="ta-table-wrap">
      <table class="ta-table">
        <thead>
          <tr><th>期間</th><th>件数</th><th>勝率</th><th>累計P/L</th><th>平均%</th><th>P/L分布</th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

// ── ④ リスクリワード散布図 (SVG) ──────────────────────────
function _renderScatter(points) {
  if (!points.length) return "";

  const W = 720, H = 380;
  const PADL = 50, PADR = 16, PADT = 16, PADB = 36;
  const innerW = W - PADL - PADR;
  const innerH = H - PADT - PADB;

  // X軸: 保有日数 (0..max), 上限 50 でクリップ表示
  const maxDays = Math.min(50, Math.max(...points.map(p => p.hold_days), 1));
  const xScale = d => PADL + (Math.min(d, 50) / maxDays) * innerW;
  // Y軸: 損益% (-maxAbs .. +maxAbs)
  const maxAbs = Math.max(10, ...points.map(p => Math.abs(p.pct)));
  const yScale = pct => PADT + (1 - (pct + maxAbs) / (2 * maxAbs)) * innerH;

  // ゼロライン Y
  const yZero = yScale(0);

  // 軸ラベル
  const xTicks = [0, Math.round(maxDays/4), Math.round(maxDays/2), Math.round(maxDays*3/4), maxDays];
  const yTicks = [-maxAbs, -maxAbs/2, 0, maxAbs/2, maxAbs];

  // 点を描画
  const pts = points.map(p => {
    const cx = xScale(p.hold_days);
    const cy = yScale(p.pct);
    const fill = p.type === "lev_etf" ? "#fb923c" : "#60a5fa";
    const stroke = p.pct >= 0 ? "rgba(34,197,94,.6)" : "rgba(239,68,68,.6)";
    const r = 5 + Math.min(8, Math.log10(Math.abs(p.shares * p.entry_price || 1)) - 1);
    return `
      <circle cx="${cx}" cy="${cy}" r="${r}"
        fill="${fill}" fill-opacity="0.7" stroke="${stroke}" stroke-width="1.5">
        <title>${_esc(p.ticker)}  ${p.entry_date}
保有 ${p.hold_days}日  ${p.pct.toFixed(2)}%
$${(p.entry_price).toFixed(2)} → $${(p.exit_price).toFixed(2)}  (${p.shares}株)
P/L: $${p.pnl.toFixed(2)}</title>
      </circle>`;
  }).join("");

  return `
    <h3 class="ta-h">🎯 リスクリワード散布図 <span class="ta-h-sub">（横=保有日数 / 縦=損益% / ●=個別株 ●=レバETF / 大きさ=エントリー金額）</span></h3>
    <div class="ta-scatter-wrap">
      <svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto;display:block">
        <!-- grid -->
        ${yTicks.map(t => `
          <line x1="${PADL}" x2="${W-PADR}" y1="${yScale(t)}" y2="${yScale(t)}"
                stroke="${t === 0 ? 'rgba(148,163,184,.5)' : 'rgba(148,163,184,.15)'}"
                stroke-dasharray="${t === 0 ? '0' : '3,3'}" />
          <text x="${PADL-6}" y="${yScale(t)+4}" fill="var(--text-muted)" font-size="11" text-anchor="end">${t.toFixed(0)}%</text>
        `).join("")}
        ${xTicks.map(t => `
          <line x1="${xScale(t)}" x2="${xScale(t)}" y1="${PADT}" y2="${H-PADB}"
                stroke="rgba(148,163,184,.1)" stroke-dasharray="3,3" />
          <text x="${xScale(t)}" y="${H-PADB+16}" fill="var(--text-muted)" font-size="11" text-anchor="middle">${t}d</text>
        `).join("")}
        <!-- zero line accent -->
        <line x1="${PADL}" x2="${W-PADR}" y1="${yZero}" y2="${yZero}" stroke="rgba(148,163,184,.5)" stroke-width="1" />
        <!-- axis labels -->
        <text x="${W-PADR}" y="${H-6}" fill="var(--text-muted)" font-size="11" text-anchor="end">保有日数 →</text>
        <text x="${PADL-30}" y="${PADT+10}" fill="var(--text-muted)" font-size="11">損益%</text>
        <!-- points -->
        ${pts}
      </svg>
      <div class="ta-scatter-legend">
        <span><span class="ta-dot" style="background:#60a5fa"></span> 個別株</span>
        <span><span class="ta-dot" style="background:#fb923c"></span> レバETF</span>
        <span style="margin-left:12px;color:var(--text-muted)">点のサイズ ∝ エントリー金額</span>
      </div>
    </div>`;
}

// ── ⑤ 銘柄タイプ別 ────────────────────────────────────────
function _renderByType({ groups, open_breakdown }) {
  if (!groups.length) return "";
  const rows = groups.map(g => {
    const wrColor = g.win_rate >= 60 ? "var(--green)"
                  : g.win_rate >= 45 ? "var(--text-primary)"
                  : "var(--red)";
    const pnlCls = g.total_pnl >= 0 ? "ta-pos" : "ta-neg";
    return `
      <tr>
        <td>${_esc(g.type_label)}</td>
        <td>${_esc(g.bucket_label)}</td>
        <td>${g.count}</td>
        <td style="color:${wrColor};font-weight:700">${g.win_rate}%</td>
        <td class="${pnlCls}">${g.total_pnl >= 0 ? "+" : ""}$${_fmtNum(g.total_pnl)}</td>
        <td>${g.avg_pct >= 0 ? "+" : ""}${_fmtNum(g.avg_pct)}%</td>
        <td>${g.avg_hold}日</td>
      </tr>`;
  }).join("");
  return `
    <h3 class="ta-h">🏷️ 銘柄タイプ別 <span class="ta-h-sub">（タイプ × 価格帯）</span></h3>
    <div class="ta-table-wrap">
      <table class="ta-table">
        <thead><tr><th>タイプ</th><th>価格帯</th><th>件数</th><th>勝率</th><th>累計P/L</th><th>平均%</th><th>平均保有</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

// ── ⑤.3 損切り遅延ドリルダウン ───────────────────────────
function _renderCutLoss(data) {
  const buckets = data.buckets || [];
  const worst   = data.worst || [];
  const s       = data.summary || {};
  if (!buckets.length) return "";

  // KPIカード3つ
  const danger = s.danger_bucket || {};
  const dangerLoss = danger.total_pnl != null ? danger.total_pnl : 0;
  const ws = s.worst_single;

  const cards = `
    <div class="ta-cl-cards">
      <div class="ta-cl-card ta-cl-danger">
        <div class="ta-cl-card-label">⚠️ 持ちすぎゾーン (8-14d)</div>
        <div class="ta-cl-card-value ta-neg">$${_fmtNum(dangerLoss)}</div>
        <div class="ta-cl-card-sub">
          ${danger.count || 0}件 / 勝率${danger.win_rate ?? '—'}%
          ${danger.avg_loss != null ? ` / 負け平均 $${_fmtNum(danger.avg_loss)}` : ''}
        </div>
      </div>
      <div class="ta-cl-card">
        <div class="ta-cl-card-label">💀 ワースト1件</div>
        <div class="ta-cl-card-value ta-neg">${ws ? `$${_fmtNum(ws.pnl)}` : '—'}</div>
        <div class="ta-cl-card-sub">${ws ? `${_esc(ws.ticker)} / ${ws.hold_days}日保有 / ${ws.pct}%` : ''}</div>
      </div>
      <div class="ta-cl-card">
        <div class="ta-cl-card-label">💡 救えた可能性</div>
        <div class="ta-cl-card-value ta-pos">+$${_fmtNum(Math.abs(s.potential_saving || 0))}</div>
        <div class="ta-cl-card-sub">
          8d+負け${s.late_count}件を2-7d水準(平均$${_fmtNum(s.short_avg_loss)})で切れていれば
        </div>
      </div>
    </div>`;

  // バケットチャート (持ちすぎゾーンを赤帯で強調)
  const maxAbs = Math.max(...buckets.map(b => Math.abs(b.total_pnl)), 1);
  const barRows = buckets.map(b => {
    const isDanger = b.is_danger;
    const widthPct = Math.abs(b.total_pnl) / maxAbs * 100;
    const isLoss = b.total_pnl < 0;
    const barCls = isLoss ? (isDanger ? "ta-cl-bar-danger" : "ta-cl-bar-loss") : "ta-cl-bar-win";
    return `
      <div class="ta-cl-row ${isDanger ? 'ta-cl-row-danger' : ''}">
        <div class="ta-cl-row-label">${b.bucket}${isDanger ? ' 🔥' : ''}</div>
        <div class="ta-cl-row-bar-wrap">
          <div class="ta-cl-row-bar ${barCls}" style="width:${widthPct}%"></div>
          <div class="ta-cl-row-bar-value">$${_fmtNum(b.total_pnl)} <span class="ta-cl-row-sub">(${b.count}件・勝${b.wins}/負${b.losses}・負け平均 $${_fmtNum(b.avg_loss || 0)})</span></div>
        </div>
      </div>`;
  }).join("");

  // ワースト15
  const worstRows = worst.slice(0, 15).map(t => `
    <tr class="ta-cl-worst-row" data-id="${t.id}" data-ticker="${_esc(t.ticker)}" style="cursor:pointer" title="クリックで全トレード一覧で確認">
      <td><strong>${_esc(t.ticker)}</strong></td>
      <td>${t.entry_date}</td>
      <td>${t.exit_date}</td>
      <td><strong>${t.hold_days}d</strong></td>
      <td class="ta-neg"><strong>$${_fmtNum(t.pnl)}</strong></td>
      <td class="ta-neg">${t.pct}%</td>
      <td>${t.shares}株 @ $${_fmtNum(t.entry_price)}→$${_fmtNum(t.exit_price)}</td>
    </tr>`).join("");

  return `
    <h3 class="ta-h">⏳ 損切り遅延ドリルダウン
      <span class="ta-h-sub">— 8d以上保有して大負けしたトレードを炙り出す</span>
    </h3>
    ${cards}
    <div class="ta-cl-explainer">
      <strong>💡 読み方:</strong>
      <span class="ta-cl-bar-sample ta-cl-bar-danger"></span> = 持ちすぎゾーン /
      <span class="ta-cl-bar-sample ta-cl-bar-loss"></span> = 通常の負け /
      <span class="ta-cl-bar-sample ta-cl-bar-win"></span> = 勝ち
    </div>
    <div class="ta-cl-bars">${barRows}</div>

    <h4 class="ta-cl-h2">💀 損切り遅延ワースト15 (8d+保有の負けトレード)</h4>
    <div class="ta-table-wrap">
      <table class="ta-table ta-cl-table">
        <thead>
          <tr>
            <th>銘柄</th><th>エントリー</th><th>決済</th><th>保有</th>
            <th>P/L</th><th>%</th><th>詳細</th>
          </tr>
        </thead>
        <tbody>${worstRows}</tbody>
      </table>
    </div>
  `;
}

// ── ⑤.5 タグ別パフォーマンス ─────────────────────────────
function _renderByTags(data) {
  const rows = data.rows || [];
  const presets = data.presets || [];
  const tagged   = data.tagged_count || 0;
  const total    = data.total_count || 0;
  const untagged = data.untagged_count || 0;

  const presetChips = presets.map(p => `<span class="ta-tag ta-tag-preset">${_esc(p)}</span>`).join("");

  if (!rows.length) {
    return `
      <h3 class="ta-h">🏷️ タグ別パフォーマンス
        <span class="ta-h-sub">（決済時 or 全トレード表の 🏷️ から付与。複数タグOK）</span>
      </h3>
      <div class="ta-empty-tags">
        <p>まだタグが付いたトレードがありません。</p>
        <p style="margin-top:6px">プリセット例:</p>
        <div class="ta-tag-row">${presetChips}</div>
        <p style="margin-top:8px;color:var(--text-muted);font-size:.78rem">
          ↓ 全トレード表の 🏷️ ボタンから既存トレードに後付けできます。
        </p>
      </div>`;
  }

  const tableRows = rows.map(r => {
    const wrColor = r.win_rate >= 60 ? "var(--green)"
                  : r.win_rate >= 45 ? "var(--text-primary)"
                  : "var(--red)";
    const pnlCls = r.total_pnl >= 0 ? "ta-pos" : "ta-neg";
    const top = (r.top_tickers || []).map(t =>
      `<span class="ta-tt-mini">${_esc(t.ticker)}<span class="${t.pnl >= 0 ? "ta-pos" : "ta-neg"}">$${_fmtNum(t.pnl, 0)}</span></span>`
    ).join("");
    const tagCls = r.is_preset ? "ta-tag-preset" : "ta-tag-custom";
    return `
      <tr class="ta-tag-row-clk" data-tag="${_esc(r.tag)}" style="cursor:pointer" title="クリックで全トレードをこのタグでフィルタ">
        <td><span class="ta-tag ${tagCls}">${_esc(r.tag)}</span></td>
        <td>${r.count}</td>
        <td style="color:${wrColor};font-weight:700">${r.win_rate}%</td>
        <td>${r.wins}/${r.losses}</td>
        <td class="${pnlCls}">${r.total_pnl >= 0 ? "+" : ""}$${_fmtNum(r.total_pnl)}</td>
        <td class="${r.expectancy >= 0 ? 'ta-pos' : 'ta-neg'}">$${_fmtNum(r.expectancy)}</td>
        <td>${r.avg_pct >= 0 ? "+" : ""}${_fmtNum(r.avg_pct)}%</td>
        <td>${r.profit_factor != null ? r.profit_factor : "—"}</td>
        <td>${r.avg_hold}日</td>
        <td>${top || "—"}</td>
      </tr>`;
  }).join("");

  return `
    <h3 class="ta-h">🏷️ タグ別パフォーマンス
      <span class="ta-h-sub">（${tagged}/${total}件にタグ付け、未タグ ${untagged}件 — 行クリックで全トレードをフィルタ）</span>
    </h3>
    <div class="ta-table-wrap">
      <table class="ta-table">
        <thead>
          <tr>
            <th>タグ</th><th>件数</th><th>勝率</th><th>勝/負</th>
            <th>累計P/L</th><th>期待値/件</th><th>平均%</th><th>PF</th>
            <th>平均保有</th><th>Top銘柄</th>
          </tr>
        </thead>
        <tbody>${tableRows}</tbody>
      </table>
    </div>`;
}

// ── ⑥ 全トレードテーブル ─────────────────────────────────
function _renderTradesTable(months = []) {
  const monthOptions = months
    .slice()
    .reverse()
    .map(m => `<option value="${m.month}">${m.month}</option>`)
    .join("");
  return `
    <h3 class="ta-h">🔍 全トレード <span class="ta-h-sub">（フィルタ・ソート・CSV出力）</span></h3>
    <div class="ta-trades-controls">
      <input type="search" class="ta-tt-search" placeholder="銘柄/メモ検索..." />
      <select class="ta-tt-month">
        <option value="all">全期間</option>
        ${monthOptions}
      </select>
      <select class="ta-tt-result">
        <option value="all">勝/負 すべて</option>
        <option value="win">勝ちのみ</option>
        <option value="loss">負けのみ</option>
      </select>
      <select class="ta-tt-type">
        <option value="all">全タイプ</option>
        <option value="stock">個別株</option>
        <option value="lev_etf">レバETF</option>
      </select>
      <select class="ta-tt-bucket">
        <option value="all">全価格帯</option>
        <option value="low">&lt;$30</option>
        <option value="mid">$30-100</option>
        <option value="high">&gt;$100</option>
      </select>
      <select class="ta-tt-tag">
        <option value="all">全タグ</option>
        <option value="__none__">タグなし</option>
        ${(_state.tagPresets || []).map(p => `<option value="${_esc(p)}">${_esc(p)}</option>`).join("")}
      </select>
      <select class="ta-tt-sort">
        <option value="exit_date_desc">決済日↓</option>
        <option value="exit_date_asc">決済日↑</option>
        <option value="pnl_desc">P/L$↓</option>
        <option value="pnl_asc">P/L$↑</option>
        <option value="pct_desc">P/L%↓</option>
        <option value="pct_asc">P/L%↑</option>
        <option value="hold_desc">保有日数↓</option>
        <option value="ticker_asc">銘柄名↑</option>
      </select>
      <button class="ta-tt-csv">📥 CSV出力</button>
    </div>
    <div class="ta-table-wrap">
      <table class="ta-table" id="ta-trades-table">
        <thead>
          <tr>
            <th>決済日</th><th>銘柄</th><th>タイプ</th>
            <th>IN</th><th>OUT</th><th>株数</th><th>保有日数</th>
            <th>P/L $</th><th>P/L %</th><th>タグ</th><th>注釈</th>
          </tr>
        </thead>
        <tbody id="ta-trades-tbody"></tbody>
      </table>
    </div>
    <div class="ta-tt-count" id="ta-tt-count" style="margin-top:6px;color:var(--text-muted);font-size:.78rem"></div>
  `;
}

function _bindFilterControls(root) {
  const els = {
    search: root.querySelector(".ta-tt-search"),
    result: root.querySelector(".ta-tt-result"),
    type:   root.querySelector(".ta-tt-type"),
    bucket: root.querySelector(".ta-tt-bucket"),
    month:  root.querySelector(".ta-tt-month"),
    tag:    root.querySelector(".ta-tt-tag"),
    sort:   root.querySelector(".ta-tt-sort"),
  };
  Object.entries(els).forEach(([key, el]) => {
    if (!el) return;
    const evt = el.tagName === "INPUT" ? "input" : "change";
    el.addEventListener(evt, () => { _state.filter[key] = el.value; _renderTradesTbody(root); });
  });
  // タグ別パフォーマンス行クリック → 全トレードをそのタグでフィルタ
  root.querySelectorAll(".ta-tag-row-clk").forEach(tr => {
    tr.addEventListener("click", () => {
      const tag = tr.dataset.tag;
      _state.filter.tag = tag;
      const sel = root.querySelector(".ta-tt-tag");
      if (sel) {
        // tag が <option> に存在しなければ追加
        if (!Array.from(sel.options).some(o => o.value === tag)) {
          const opt = document.createElement("option");
          opt.value = tag; opt.textContent = tag; sel.appendChild(opt);
        }
        sel.value = tag;
      }
      _renderTradesTbody(root);
      // 「トレード一覧」タブが別タブにあるので明示的に切替
      _activateTab(root, "trades");
      history.replaceState(null, "", "#tab=trades");
      const tbl = root.querySelector("#ta-trades-table");
      if (tbl) tbl.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
  // 損切り遅延ワースト行クリック → 銘柄でフィルタ + トレード一覧へ
  root.querySelectorAll(".ta-cl-worst-row").forEach(tr => {
    tr.addEventListener("click", () => {
      const ticker = tr.dataset.ticker;
      _state.filter.search = ticker;
      const inp = root.querySelector(".ta-tt-search");
      if (inp) inp.value = ticker;
      _renderTradesTbody(root);
      _activateTab(root, "trades");
      history.replaceState(null, "", "#tab=trades");
      const tbl = root.querySelector("#ta-trades-table");
      if (tbl) tbl.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
  _renderTradesTbody(root);
}

function _renderTradesTbody(root) {
  const tbody = root.querySelector("#ta-trades-tbody");
  const count = root.querySelector("#ta-tt-count");
  const f = _state.filter;
  let view = (_state.trades.closed || []).slice();

  if (f.search) {
    const q = f.search.toLowerCase();
    view = view.filter(t =>
      (t.ticker || "").toLowerCase().includes(q) ||
      (t.notes || "").toLowerCase().includes(q) ||
      (t.tags || []).some(tg => tg.toLowerCase().includes(q)));
  }
  if (f.result === "win")  view = view.filter(t => t.pnl > 0);
  if (f.result === "loss") view = view.filter(t => t.pnl <= 0);
  if (f.type !== "all")    view = view.filter(t => t.type === f.type);
  if (f.bucket !== "all")  view = view.filter(t => t.price_bucket === f.bucket);
  if (f.month !== "all")   view = view.filter(t => (t.entry_date || "").startsWith(f.month));
  if (f.tag === "__none__") view = view.filter(t => !(t.tags || []).length);
  else if (f.tag && f.tag !== "all") view = view.filter(t => (t.tags || []).includes(f.tag));

  const sorters = {
    "exit_date_desc": (a,b) => (b.exit_date||"").localeCompare(a.exit_date||""),
    "exit_date_asc":  (a,b) => (a.exit_date||"").localeCompare(b.exit_date||""),
    "pnl_desc":       (a,b) => b.pnl - a.pnl,
    "pnl_asc":        (a,b) => a.pnl - b.pnl,
    "pct_desc":       (a,b) => b.pct - a.pct,
    "pct_asc":        (a,b) => a.pct - b.pct,
    "hold_desc":      (a,b) => (b.hold_days||0) - (a.hold_days||0),
    "ticker_asc":     (a,b) => (a.ticker||"").localeCompare(b.ticker||""),
  };
  view.sort(sorters[f.sort] || sorters["exit_date_desc"]);

  count.textContent = `${view.length}件 / 全${_state.trades.closed.length}件`;

  tbody.innerHTML = view.map(t => {
    const pnlCls = t.pnl >= 0 ? "ta-pos" : "ta-neg";
    const typeLbl = t.type === "lev_etf" ? "レバ" : "個別";
    const tags = t.tags || [];
    const tagChips = tags.length
      ? tags.map(tg => `<span class="ta-tag ta-tag-mini">${_esc(tg)}</span>`).join(" ")
      : `<span style="color:var(--text-muted);font-size:.72rem">—</span>`;
    return `
      <tr>
        <td>${t.exit_date || "—"}</td>
        <td><strong>${_esc(t.ticker)}</strong></td>
        <td>${typeLbl}</td>
        <td>$${_fmtNum(t.entry_price, 2)}</td>
        <td>$${_fmtNum(t.exit_price, 2)}</td>
        <td>${t.shares}</td>
        <td>${t.hold_days != null ? t.hold_days + "d" : "—"}</td>
        <td class="${pnlCls}">${t.pnl >= 0 ? "+" : ""}$${_fmtNum(t.pnl)}</td>
        <td class="${pnlCls}">${t.pct >= 0 ? "+" : ""}${_fmtNum(t.pct)}%</td>
        <td>
          <button class="ta-tag-edit-btn" data-id="${t.id}" data-tags="${_esc(JSON.stringify(tags))}" title="タグを編集">🏷️</button>
          ${tagChips}
        </td>
        <td style="color:var(--text-muted);font-size:.74rem">${_esc(t.notes || "")}</td>
      </tr>`;
  }).join("");

  // タグ編集ボタンをバインド
  tbody.querySelectorAll(".ta-tag-edit-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const id = btn.dataset.id;
      let current = [];
      try { current = JSON.parse(btn.dataset.tags); } catch {}
      _openTagEditor(root, id, current);
    });
  });
}

// ── タグ編集モーダル ─────────────────────────────────────
function _openTagEditor(root, positionId, current) {
  const presets = _state.tagPresets || [];
  const cur = new Set(current);
  // 既存タグ + プリセット を全て候補に
  const allKnown = new Set([...presets, ...current]);
  // 他トレードの既存タグも収集
  (_state.trades.closed || []).forEach(t => (t.tags || []).forEach(tg => allKnown.add(tg)));
  const knownArr = Array.from(allKnown);

  const overlay = document.createElement("div");
  overlay.className = "ta-modal-overlay";
  overlay.innerHTML = `
    <div class="ta-modal">
      <div class="ta-modal-head">
        <h4>🏷️ タグを編集</h4>
        <button class="ta-modal-close">✕</button>
      </div>
      <div class="ta-modal-body">
        <p style="color:var(--text-muted);font-size:.78rem;margin-bottom:8px">
          チップをクリックで ON/OFF。下の入力で新規タグを追加できます。
        </p>
        <div class="ta-tag-row" id="ta-tag-chips">
          ${knownArr.map(tg => `
            <span class="ta-tag ta-tag-toggle ${cur.has(tg) ? "ta-tag-on" : ""}"
                  data-tag="${_esc(tg)}">${_esc(tg)}</span>
          `).join("")}
        </div>
        <div class="ta-tag-add-row">
          <input type="text" class="ta-tag-add-input" placeholder="新規タグ名..." />
          <button class="ta-tag-add-btn">＋ 追加</button>
        </div>
        <div class="ta-modal-foot">
          <button class="ta-modal-cancel">キャンセル</button>
          <button class="ta-modal-save">保存</button>
        </div>
      </div>
    </div>`;
  document.body.appendChild(overlay);

  const chipsEl = overlay.querySelector("#ta-tag-chips");
  const selected = new Set(cur);

  chipsEl.addEventListener("click", (e) => {
    const chip = e.target.closest(".ta-tag-toggle");
    if (!chip) return;
    const tg = chip.dataset.tag;
    if (selected.has(tg)) { selected.delete(tg); chip.classList.remove("ta-tag-on"); }
    else { selected.add(tg); chip.classList.add("ta-tag-on"); }
  });

  const input = overlay.querySelector(".ta-tag-add-input");
  overlay.querySelector(".ta-tag-add-btn").addEventListener("click", () => {
    const v = input.value.trim();
    if (!v) return;
    selected.add(v);
    if (!chipsEl.querySelector(`[data-tag="${CSS.escape(v)}"]`)) {
      const span = document.createElement("span");
      span.className = "ta-tag ta-tag-toggle ta-tag-on";
      span.dataset.tag = v;
      span.textContent = v;
      chipsEl.appendChild(span);
    } else {
      chipsEl.querySelector(`[data-tag="${CSS.escape(v)}"]`).classList.add("ta-tag-on");
    }
    input.value = "";
    input.focus();
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); overlay.querySelector(".ta-tag-add-btn").click(); }
  });

  const close = () => overlay.remove();
  overlay.querySelector(".ta-modal-close").addEventListener("click", close);
  overlay.querySelector(".ta-modal-cancel").addEventListener("click", close);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });

  overlay.querySelector(".ta-modal-save").addEventListener("click", async () => {
    try {
      await apiFetch(`/api/positions/${positionId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tags: Array.from(selected) }),
      });
      close();
      // 全画面再読み込み（集計も更新するため）
      const container = root.parentElement;
      if (container) await renderTradeAnalytics(container);
    } catch (err) {
      alert("保存失敗: " + err.message);
    }
  });
}

function _bindCsvExport(root) {
  const btn = root.querySelector(".ta-tt-csv");
  if (!btn) return;
  btn.addEventListener("click", () => {
    const rows = _state.trades.closed;
    if (!rows.length) return;
    const headers = ["entry_date","exit_date","ticker","type","price_bucket",
                     "entry_price","exit_price","shares","hold_days","pnl","pct","tags","notes"];
    const csv = [headers.join(",")].concat(rows.map(r =>
      headers.map(h => _csvEscape(h === "tags" ? (r.tags || []).join("|") : r[h])).join(",")
    )).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `trades_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  });
}

function _csvEscape(v) {
  if (v == null) return "";
  const s = String(v);
  if (s.includes(",") || s.includes("\"") || s.includes("\n")) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

// ── helpers ───────────────────────────────────────────────
function _fmtNum(n, dp = 2) {
  if (n == null || isNaN(n)) return "—";
  return Number(n).toLocaleString("en-US", { maximumFractionDigits: dp, minimumFractionDigits: dp });
}
function _esc(s) {
  return String(s ?? "")
    .replace(/&/g,"&amp;")
    .replace(/</g,"&lt;")
    .replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;");
}
