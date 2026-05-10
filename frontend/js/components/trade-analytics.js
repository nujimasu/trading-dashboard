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
  filter: {
    search: "",
    result: "all",   // all | win | loss
    type:   "all",   // all | stock | lev_etf
    bucket: "all",   // all | low | mid | high | unknown
    sort:   "exit_date_desc",
  },
};

export async function renderTradeAnalytics(container) {
  container.innerHTML = `
    <div class="section-title">📈 取引分析</div>
    <div class="ta-content"><div class="loading"><div class="spinner"></div></div></div>`;
  const root = container.querySelector(".ta-content");

  try {
    const [summary, insights, hold, scatter, byType, trades] = await Promise.all([
      apiFetch("/api/trade-analytics/summary"),
      apiFetch("/api/trade-analytics/insights"),
      apiFetch("/api/trade-analytics/holding-buckets"),
      apiFetch("/api/trade-analytics/scatter"),
      apiFetch("/api/trade-analytics/by-type"),
      apiFetch("/api/trade-analytics/trades"),
    ]);
    _state.trades = trades;

    if (!summary || !summary.trades) {
      root.innerHTML = `
        <div class="empty-state">決済済みトレードがまだありません。<br>
        「💼 保有ポジション」から決済すると、ここに分析が表示されます。</div>`;
      return;
    }

    root.innerHTML = `
      ${_renderSummary(summary)}
      ${_renderInsights(insights.cards)}
      ${_renderHolding(hold.buckets)}
      ${_renderScatter(scatter.points)}
      ${_renderByType(byType)}
      ${_renderTradesTable()}
    `;
    _bindFilterControls(root);
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

// ── ② 自動インサイト ──────────────────────────────────────
function _renderInsights(cards) {
  if (!cards || !cards.length) return "";
  return `
    <h3 class="ta-h">💡 自動インサイト</h3>
    <div class="ta-insight-grid">
      ${cards.map(c => `
        <div class="ta-insight ta-insight-${_esc(c.severity)}">
          <div class="ta-insight-head">
            <span class="ta-insight-icon">${_esc(c.icon || "💡")}</span>
            <span class="ta-insight-title">${_esc(c.title)}</span>
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
        </div>
      `).join("")}
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

// ── ⑥ 全トレードテーブル ─────────────────────────────────
function _renderTradesTable() {
  return `
    <h3 class="ta-h">🔍 全トレード <span class="ta-h-sub">（フィルタ・ソート・CSV出力）</span></h3>
    <div class="ta-trades-controls">
      <input type="search" class="ta-tt-search" placeholder="銘柄/メモ検索..." />
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
            <th>P/L $</th><th>P/L %</th><th>注釈</th>
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
    sort:   root.querySelector(".ta-tt-sort"),
  };
  Object.entries(els).forEach(([key, el]) => {
    if (!el) return;
    const evt = el.tagName === "INPUT" ? "input" : "change";
    el.addEventListener(evt, () => { _state.filter[key] = el.value; _renderTradesTbody(root); });
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
      (t.notes || "").toLowerCase().includes(q));
  }
  if (f.result === "win")  view = view.filter(t => t.pnl > 0);
  if (f.result === "loss") view = view.filter(t => t.pnl <= 0);
  if (f.type !== "all")    view = view.filter(t => t.type === f.type);
  if (f.bucket !== "all")  view = view.filter(t => t.price_bucket === f.bucket);

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
        <td style="color:var(--text-muted);font-size:.74rem">${_esc(t.notes || "")}</td>
      </tr>`;
  }).join("");
}

function _bindCsvExport(root) {
  const btn = root.querySelector(".ta-tt-csv");
  if (!btn) return;
  btn.addEventListener("click", () => {
    const rows = _state.trades.closed;
    if (!rows.length) return;
    const headers = ["entry_date","exit_date","ticker","type","price_bucket",
                     "entry_price","exit_price","shares","hold_days","pnl","pct","notes"];
    const csv = [headers.join(",")].concat(rows.map(r =>
      headers.map(h => _csvEscape(r[h])).join(",")
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
