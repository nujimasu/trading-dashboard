/**
 * Backtest 戦績ビュー
 *
 * シグナル評価結果（signal_log）から各ロジックの:
 *   トレード数 / 勝率 / 期待値R / Profit Factor / 最大DD / 累積エクイティ
 * を表示する。
 */
import { apiFetch } from "../utils/api.js";

const PERIODS = [
  { label: "30日",  days: 30  },
  { label: "90日",  days: 90  },
  { label: "全期間", days: null },
];

const LOGIC_TABS = [
  { id: null,      label: "全ロジック" },
  { id: "logic1",  label: "ロジック１" },
  { id: "logic2",  label: "ロジック２" },
  { id: "logic3",  label: "ロジック３" },
];

let _state = { period: 90, logic: null };

export async function renderBacktest(container) {
  container.innerHTML = `
    <div class="section-title">📊 戦績</div>
    <div class="bt-controls">
      <div class="bt-control-group">
        <span class="bt-control-label">ロジック</span>
        <div class="bt-tabs" id="bt-logic-tabs">
          ${LOGIC_TABS.map(t => `<button class="bt-tab" data-logic="${t.id || ''}">${t.label}</button>`).join("")}
        </div>
      </div>
      <div class="bt-control-group">
        <span class="bt-control-label">期間</span>
        <div class="bt-tabs" id="bt-period-tabs">
          ${PERIODS.map(p => `<button class="bt-tab" data-days="${p.days || ''}">${p.label}</button>`).join("")}
        </div>
      </div>
    </div>
    <div class="bt-content" id="bt-content">
      <div class="loading"><div class="spinner"></div><span>読み込み中...</span></div>
    </div>`;

  // タブハンドラ
  container.querySelectorAll("#bt-logic-tabs .bt-tab").forEach(btn => {
    btn.addEventListener("click", () => {
      _state.logic = btn.dataset.logic || null;
      _refreshTabs(container);
      _loadStats(container);
    });
  });
  container.querySelectorAll("#bt-period-tabs .bt-tab").forEach(btn => {
    btn.addEventListener("click", () => {
      _state.period = btn.dataset.days ? +btn.dataset.days : null;
      _refreshTabs(container);
      _loadStats(container);
    });
  });

  _refreshTabs(container);
  await _loadStats(container);
}

function _refreshTabs(container) {
  container.querySelectorAll("#bt-logic-tabs .bt-tab").forEach(b => {
    const id = b.dataset.logic || null;
    b.classList.toggle("active", id === _state.logic);
  });
  container.querySelectorAll("#bt-period-tabs .bt-tab").forEach(b => {
    const days = b.dataset.days ? +b.dataset.days : null;
    b.classList.toggle("active", days === _state.period);
  });
}

async function _loadStats(container) {
  const content = container.querySelector("#bt-content");
  content.innerHTML = `<div class="loading"><div class="spinner"></div><span>読み込み中...</span></div>`;

  try {
    const params = new URLSearchParams();
    if (_state.logic)  params.set("logic", _state.logic);
    if (_state.period) params.set("days",  _state.period);

    const [stats, recent] = await Promise.all([
      apiFetch(`/api/backtest/stats?${params.toString()}`),
      apiFetch(`/api/backtest/recent?${params.toString()}&limit=50`),
    ]);

    if (stats.trades === 0) {
      content.innerHTML = `
        <div class="empty-state">
          まだ評価済みのシグナルがありません。<br>
          シグナルが発生してから30営業日経過すると評価されます。<br>
          <span style="color:var(--text-muted);font-size:.78rem;margin-top:8px;display:inline-block;">
            （未評価のシグナルが${recent.signals.filter(s=>s.status==='open').length}件あります）
          </span>
        </div>`;
      return;
    }

    content.innerHTML = `
      ${_renderSummary(stats.summary)}
      ${_state.logic === null ? _renderByLogic(stats.by_logic) : ""}
      ${_renderEquityCurve(stats.summary.equity_curve || [])}
      ${_renderRecentSignals(recent.signals)}
    `;
  } catch (e) {
    content.innerHTML = `<div class="empty-state">読み込み失敗: ${e.message}</div>`;
  }
}

function _renderSummary(s) {
  const cards = [
    { label: "トレード数",  value: s.trades, color: "" },
    { label: "勝率",         value: `${s.win_rate}%`, color: _winRateColor(s.win_rate) },
    { label: "期待値",       value: `${_signR(s.expectancy_r)}R/件`, color: _rColor(s.expectancy_r) },
    { label: "Profit Factor", value: s.profit_factor != null ? s.profit_factor.toFixed(2) : "—", color: _pfColor(s.profit_factor) },
    { label: "累積R",        value: _signR(s.total_r), color: _rColor(s.total_r) },
    { label: "最大DD",       value: `${(-s.max_dd_r).toFixed(2)}R`, color: "var(--red)" },
    { label: "平均勝ち",     value: `${_signR(s.avg_win_r)}R`, color: "var(--green)" },
    { label: "平均負け",     value: `${_signR(s.avg_loss_r)}R`, color: "var(--red)" },
  ];

  return `
    <div class="bt-summary-grid">
      ${cards.map(c => `
        <div class="bt-stat-card">
          <div class="bt-stat-label">${c.label}</div>
          <div class="bt-stat-value" ${c.color ? `style="color:${c.color}"` : ""}>${c.value}</div>
        </div>`).join("")}
    </div>`;
}

function _renderByLogic(byLogic) {
  const entries = Object.entries(byLogic);
  if (!entries.length) return "";

  const rows = entries.map(([name, s]) => `
    <tr>
      <td><strong>${name}</strong></td>
      <td>${s.trades}</td>
      <td style="color:${_winRateColor(s.win_rate)}">${s.win_rate}%</td>
      <td style="color:${_rColor(s.expectancy_r)}">${_signR(s.expectancy_r)}R</td>
      <td>${s.profit_factor != null ? s.profit_factor.toFixed(2) : "—"}</td>
      <td style="color:${_rColor(s.total_r)}">${_signR(s.total_r)}R</td>
      <td style="color:var(--red)">${(-s.max_dd_r).toFixed(2)}R</td>
    </tr>`).join("");

  return `
    <h3 class="bt-section-h">ロジック別</h3>
    <div class="bt-table-wrap">
      <table class="bt-table">
        <thead>
          <tr>
            <th>ロジック</th><th>件数</th><th>勝率</th><th>期待値</th>
            <th>PF</th><th>累積R</th><th>最大DD</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

function _renderEquityCurve(points) {
  if (points.length < 2) return "";

  const w = 600, h = 160, pad = 24;
  const ys = points.map(p => p.cum_r);
  const xMin = 0, xMax = points.length - 1;
  const yMin = Math.min(0, ...ys);
  const yMax = Math.max(0, ...ys);
  const yRange = (yMax - yMin) || 1;

  const x = i => pad + (i - xMin) / Math.max(1, xMax - xMin) * (w - 2 * pad);
  const y = v => h - pad - (v - yMin) / yRange * (h - 2 * pad);
  const zeroY = y(0);

  const path = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.cum_r).toFixed(1)}`).join(" ");
  const lastColor = ys[ys.length - 1] >= 0 ? "var(--green)" : "var(--red)";

  return `
    <h3 class="bt-section-h">エクイティカーブ（累積R）</h3>
    <div class="bt-equity-wrap">
      <svg viewBox="0 0 ${w} ${h}" style="width:100%;height:auto;display:block">
        <line x1="${pad}" y1="${zeroY}" x2="${w - pad}" y2="${zeroY}" stroke="var(--border)" stroke-width="1" stroke-dasharray="4,4"/>
        <path d="${path}" fill="none" stroke="${lastColor}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
        <text x="${pad}" y="14" fill="var(--text-muted)" font-size="11">最大: ${yMax.toFixed(2)}R</text>
        <text x="${pad}" y="${h - 6}" fill="var(--text-muted)" font-size="11">最小: ${yMin.toFixed(2)}R</text>
      </svg>
    </div>`;
}

function _renderRecentSignals(signals) {
  if (!signals.length) return "";

  const rows = signals.map(s => {
    const statusBadge = _statusBadge(s.status);
    const r = s.realized_r != null ? _signR(s.realized_r) + "R" : "—";
    const rColor = s.realized_r != null ? _rColor(s.realized_r) : "var(--text-muted)";
    return `
      <tr>
        <td>${_fmtDate(s.signal_date)}</td>
        <td><strong>${s.ticker}</strong></td>
        <td>${s.logic_name}</td>
        <td>${statusBadge}</td>
        <td style="color:${rColor};font-weight:700">${r}</td>
        <td>${s.days_held ?? "—"}</td>
      </tr>`;
  }).join("");

  return `
    <h3 class="bt-section-h">最新シグナル ${signals.length}件</h3>
    <div class="bt-table-wrap">
      <table class="bt-table">
        <thead>
          <tr><th>日付</th><th>銘柄</th><th>ロジック</th><th>結果</th><th>R</th><th>日数</th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

// ── helpers ────────────────────────────────────────────────────────
function _signR(v) {
  if (v == null) return "—";
  const n = Number(v);
  return (n >= 0 ? "+" : "") + n.toFixed(2);
}
function _winRateColor(p) {
  if (p >= 55) return "var(--green)";
  if (p >= 45) return "var(--yellow)";
  return "var(--red)";
}
function _rColor(r) {
  if (r == null) return "var(--text-muted)";
  return r > 0 ? "var(--green)" : r < 0 ? "var(--red)" : "var(--text-muted)";
}
function _pfColor(pf) {
  if (pf == null) return "var(--text-muted)";
  if (pf >= 1.5) return "var(--green)";
  if (pf >= 1.0) return "var(--yellow)";
  return "var(--red)";
}
function _statusBadge(status) {
  const map = {
    "open":       { label: "観察中",   css: "bt-status-open" },
    "stopped":    { label: "SL",       css: "bt-status-loss" },
    "tp1_hit_be": { label: "TP1+BE",   css: "bt-status-flat" },
    "tp2_hit":    { label: "TP2",      css: "bt-status-win" },
    "time_exit":  { label: "時間切れ", css: "bt-status-flat" },
    "invalid":    { label: "無効",     css: "bt-status-na" },
  };
  const m = map[status] || { label: status, css: "" };
  return `<span class="bt-status-badge ${m.css}">${m.label}</span>`;
}
function _fmtDate(s) {
  if (!s) return "—";
  return String(s).slice(5); // MM-DD
}
