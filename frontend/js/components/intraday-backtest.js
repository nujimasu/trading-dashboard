/**
 * Intraday 戦績ビュー（5分足・指値タッチ約定）
 *
 * 既存の「戦績」タブは日足ベース（翌日始値で成行・日足H/Lで判定・負けは-1R固定）。
 * こちらは5分足で
 *   - entry_price に置いた買い指値へ実際にタッチしたか（届かなければ「見送り」）
 *   - SL / TP1 / ターゲットにタッチした瞬間の決済
 *   - ギャップでSLを飛び越えた日は寄り値で約定（負けが -1R を超えうる）
 * をシミュレートした結果を表示し、ロジック別の勝率を比較する。
 */
import { apiFetch } from "../utils/api.js";

const FILL_MODES = [
  { id: "limit", label: "指値タッチ約定", hint: "シグナル日の終値まで押したら買う（追いかけない）" },
  { id: "open",  label: "翌日始値で成行", hint: "対照群：指値ルールが効いているかの切り分け用" },
];

const LOGIC_LABEL = {
  logic1: "ファンダ重視",
  logic2: "厳選押し目買いv1",
  logic4: "厳選押し目買いv2",
};

let _state = { fillMode: "limit" };

export async function renderIntradayBacktest(container) {
  container.innerHTML = `
    <div class="section-title">⏱ Intraday戦績（5分足）</div>
    <div class="bt-controls">
      <div class="bt-control-group">
        <span class="bt-control-label">約定方式</span>
        <div class="bt-tabs" id="itd-mode-tabs">
          ${FILL_MODES.map(m => `<button class="bt-tab" data-mode="${m.id}" title="${m.hint}">${m.label}</button>`).join("")}
        </div>
      </div>
    </div>
    <div class="bt-content" id="itd-content">
      <div class="loading"><div class="spinner"></div><span>読み込み中...</span></div>
    </div>`;

  container.querySelectorAll("#itd-mode-tabs .bt-tab").forEach(btn => {
    btn.addEventListener("click", () => {
      _state.fillMode = btn.dataset.mode;
      _refreshTabs(container);
      _load(container);
    });
  });

  _refreshTabs(container);
  await _load(container);
}

function _refreshTabs(container) {
  container.querySelectorAll("#itd-mode-tabs .bt-tab").forEach(b => {
    b.classList.toggle("active", b.dataset.mode === _state.fillMode);
  });
}

async function _load(container) {
  const content = container.querySelector("#itd-content");
  content.innerHTML = `<div class="loading"><div class="spinner"></div><span>読み込み中...</span></div>`;

  try {
    const [stats, recent] = await Promise.all([
      apiFetch(`/api/intraday/stats?fill_mode=${_state.fillMode}`),
      apiFetch(`/api/intraday/trades?fill_mode=${_state.fillMode}&limit=60`),
    ]);

    if (!stats.total) {
      content.innerHTML = `
        <div class="empty-state">
          Intradayシミュレーションの結果がまだありません。<br>
          <span style="color:var(--text-muted);font-size:.78rem;">
            日次パイプラインが5分足を取得して再計算します（yfinanceの5分足は直近60日のみ）。
          </span>
        </div>`;
      return;
    }

    content.innerHTML = `
      ${_renderNote()}
      ${_renderSummary(stats.summary)}
      ${_renderByLogic(stats.by_logic)}
      ${_renderByVerdict(stats.by_verdict)}
      ${_renderEquity(stats.by_logic)}
      ${_renderTrades(recent.trades)}
    `;
  } catch (e) {
    content.innerHTML = `<div class="empty-state">読み込み失敗: ${e.message}</div>`;
  }
}

function _renderNote() {
  return `
    <div class="bt-note-card">
      <strong>この画面の前提</strong>
      <ul>
        <li><strong>約定</strong>: シグナル日の終値に買い指値を置き、5分足でそこまで押したら約定。
            5営業日タッチしなければ<strong>見送り</strong>（トレードしない）。</li>
        <li><strong>決済</strong>: SL / +1.5R半分利確 → 建値ストップ / +3Rターゲット を5分足で判定。上限30営業日。</li>
        <li><strong>ギャップ</strong>: 寄りがSLを飛び越えた日は寄り値で損切り（負けが −1R を超える）。
            日足版の「負けは一律 −1R」より厳しく、実運用に近い。</li>
        <li><strong>比較軸は「合算R ÷ 約定」</strong>: 負けは数日で確定する一方、勝ちは建値ストップのまま保有継続になるため、
            決済済みだけの勝率・期待値は<strong>構造的に悲観へ偏る</strong>。含み評価を足した1トレードあたりRで見ること。</li>
      </ul>
    </div>`;
}

function _renderSummary(s) {
  const cards = [
    { label: "シグナル数",        value: s.signals },
    { label: "約定",              value: `${s.filled} (${s.fill_rate ?? "—"}%)` },
    { label: "決済済み",          value: s.closed },
    { label: "勝率 (決済済み)",   value: s.win_rate != null ? `${s.win_rate}%` : "—", color: _winColor(s.win_rate) },
    { label: "期待値 (決済済み)", value: `${_r(s.expectancy_r)}R/件`, color: _rc(s.expectancy_r) },
    { label: "Profit Factor",     value: s.profit_factor != null ? s.profit_factor.toFixed(2) : "—", color: _pfColor(s.profit_factor) },
    { label: "確定R",             value: `${_r(s.total_r)}R`, color: _rc(s.total_r) },
    { label: `含みR (open ${s.open}件)`, value: `${_r(s.open_mtm_r)}R`, color: _rc(s.open_mtm_r) },
    { label: "合算R",             value: `${_r(s.combined_r)}R`, color: _rc(s.combined_r) },
    { label: "合算R ÷ 約定",      value: `${_r(s.combined_r_per_fill)}R/件`, color: _rc(s.combined_r_per_fill) },
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
  const entries = Object.entries(byLogic || {});
  if (!entries.length) return "";

  // 「合算R ÷ 約定」の降順 = 実力順
  entries.sort((a, b) => (b[1].combined_r_per_fill ?? -99) - (a[1].combined_r_per_fill ?? -99));

  const rows = entries.map(([name, s], i) => `
    <tr>
      <td>${i === 0 ? "🥇 " : ""}<strong>${LOGIC_LABEL[name] || name}</strong>
          <span style="color:var(--text-muted);font-size:.75rem">${name}</span></td>
      <td>${s.signals}</td>
      <td>${s.filled}<span style="color:var(--text-muted);font-size:.75rem"> (${s.fill_rate ?? "—"}%)</span></td>
      <td>${s.closed}</td>
      <td style="color:${_winColor(s.win_rate)}">${s.win_rate != null ? s.win_rate + "%" : "—"}</td>
      <td style="color:${_rc(s.expectancy_r)}">${_r(s.expectancy_r)}R</td>
      <td>${s.profit_factor != null ? s.profit_factor.toFixed(2) : "—"}</td>
      <td style="color:${_rc(s.total_r)}">${_r(s.total_r)}R</td>
      <td style="color:${_rc(s.open_mtm_r)}">${_r(s.open_mtm_r)}R</td>
      <td style="color:${_rc(s.combined_r_per_fill)};font-weight:700">${_r(s.combined_r_per_fill)}R</td>
      <td style="color:var(--red)">−${s.max_dd_r.toFixed(1)}R</td>
    </tr>`).join("");

  return `
    <h3 class="bt-section-h">ロジック別（実力順 = 合算R ÷ 約定）</h3>
    <div class="bt-table-wrap">
      <table class="bt-table">
        <thead>
          <tr>
            <th>ロジック</th><th>ｼｸﾞﾅﾙ</th><th>約定</th><th>決済済</th><th>勝率</th>
            <th>期待値</th><th>PF</th><th>確定R</th><th>含みR</th><th>合算R/件</th><th>最大DD</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

function _renderByVerdict(byVerdict) {
  const entries = Object.entries(byVerdict || {}).filter(([, s]) => s.signals >= 15);
  if (!entries.length) return "";

  entries.sort((a, b) => (b[1].combined_r_per_fill ?? -99) - (a[1].combined_r_per_fill ?? -99));

  const rows = entries.map(([key, s]) => {
    const [logic, verdict] = key.split(" / ");
    return `
    <tr>
      <td>${LOGIC_LABEL[logic] || logic}</td>
      <td><span class="sig-tag">${_esc(verdict)}</span></td>
      <td>${s.filled}</td>
      <td>${s.closed}</td>
      <td style="color:${_winColor(s.win_rate)}">${s.win_rate != null ? s.win_rate + "%" : "—"}</td>
      <td style="color:${_rc(s.expectancy_r)}">${_r(s.expectancy_r)}R</td>
      <td style="color:${_rc(s.combined_r_per_fill)};font-weight:700">${_r(s.combined_r_per_fill)}R</td>
    </tr>`;
  }).join("");

  return `
    <h3 class="bt-section-h">ロジック × 判定 <span style="color:var(--text-muted);font-weight:400;font-size:.8rem">（15件以上）</span></h3>
    <div class="bt-table-wrap">
      <table class="bt-table">
        <thead>
          <tr><th>ロジック</th><th>判定</th><th>約定</th><th>決済済</th><th>勝率</th><th>期待値</th><th>合算R/件</th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

function _renderEquity(byLogic) {
  const series = Object.entries(byLogic || {})
    .map(([name, s]) => ({ name, pts: (s.equity_curve || []).map(p => p.cum_r) }))
    .filter(s => s.pts.length >= 2);
  if (!series.length) return "";

  const w = 620, h = 180, pad = 28;
  const allY = series.flatMap(s => s.pts);
  const yMin = Math.min(0, ...allY);
  const yMax = Math.max(0, ...allY);
  const yRange = (yMax - yMin) || 1;
  const maxLen = Math.max(...series.map(s => s.pts.length));

  const colors = { logic1: "var(--yellow)", logic2: "var(--green)", logic4: "var(--blue, #5b9cf8)" };
  const x = i => pad + (i / Math.max(1, maxLen - 1)) * (w - 2 * pad);
  const y = v => h - pad - (v - yMin) / yRange * (h - 2 * pad);

  const paths = series.map(s => {
    const d = s.pts.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
    return `<path d="${d}" fill="none" stroke="${colors[s.name] || "var(--text-muted)"}" stroke-width="2" stroke-linejoin="round"/>`;
  }).join("");

  const legend = series.map(s =>
    `<span style="margin-right:14px;font-size:.78rem">
       <span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${colors[s.name] || "var(--text-muted)"};margin-right:4px"></span>
       ${LOGIC_LABEL[s.name] || s.name}
     </span>`).join("");

  return `
    <h3 class="bt-section-h">エクイティカーブ（決済済みの累積R・ロジック別）</h3>
    <div class="bt-equity-wrap">
      <div style="margin-bottom:6px">${legend}</div>
      <svg viewBox="0 0 ${w} ${h}" style="width:100%;height:auto;display:block">
        <line x1="${pad}" y1="${y(0)}" x2="${w - pad}" y2="${y(0)}" stroke="var(--border)" stroke-width="1" stroke-dasharray="4,4"/>
        ${paths}
        <text x="${pad}" y="14" fill="var(--text-muted)" font-size="11">${yMax.toFixed(1)}R</text>
        <text x="${pad}" y="${h - 6}" fill="var(--text-muted)" font-size="11">${yMin.toFixed(1)}R</text>
      </svg>
    </div>`;
}

function _renderTrades(trades) {
  if (!trades || !trades.length) return "";
  const rows = trades.map(t => {
    const r = t.realized_r != null ? t.realized_r : t.mtm_r;
    const isMtm = t.realized_r == null && t.mtm_r != null;
    return `
      <tr>
        <td>${_fmtDate(t.signal_date)}</td>
        <td><strong>${t.ticker}</strong></td>
        <td>${LOGIC_LABEL[t.logic_name] || t.logic_name}</td>
        <td>${_badge(t.status)}</td>
        <td>${t.fill_price != null ? "$" + Number(t.fill_price).toFixed(2) : "—"}</td>
        <td style="color:${_rc(r)};font-weight:700">${r != null ? _r(r) + "R" : "—"}${isMtm ? '<span style="color:var(--text-muted);font-weight:400;font-size:.7rem"> 含み</span>' : ""}</td>
        <td>${t.days_held ?? "—"}</td>
      </tr>`;
  }).join("");

  return `
    <h3 class="bt-section-h">直近のシミュレーション結果 ${trades.length}件</h3>
    <div class="bt-table-wrap">
      <table class="bt-table">
        <thead>
          <tr><th>日付</th><th>銘柄</th><th>ロジック</th><th>結果</th><th>約定値</th><th>R</th><th>日数</th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

// ── helpers ────────────────────────────────────────────────────────
function _r(v) {
  if (v == null) return "—";
  const n = Number(v);
  return (n >= 0 ? "+" : "") + n.toFixed(2);
}
function _rc(v) {
  if (v == null) return "var(--text-muted)";
  return v > 0 ? "var(--green)" : v < 0 ? "var(--red)" : "var(--text-muted)";
}
function _winColor(p) {
  if (p == null) return "var(--text-muted)";
  if (p >= 55) return "var(--green)";
  if (p >= 45) return "var(--yellow)";
  return "var(--red)";
}
function _pfColor(pf) {
  if (pf == null) return "var(--text-muted)";
  if (pf >= 1.5) return "var(--green)";
  if (pf >= 1.0) return "var(--yellow)";
  return "var(--red)";
}
function _badge(status) {
  const map = {
    open:       { label: "保有中",     css: "bt-status-open" },
    stopped:    { label: "損切り",     css: "bt-status-loss" },
    tp1_hit_be: { label: "TP1+建値",   css: "bt-status-flat" },
    tp2_hit:    { label: "ターゲット", css: "bt-status-win" },
    time_exit:  { label: "時間切れ",   css: "bt-status-flat" },
    no_fill:    { label: "見送り",     css: "bt-status-na" },
    gap_void:   { label: "ギャップ消滅", css: "bt-status-na" },
    invalid:    { label: "データ不良", css: "bt-status-na" },
  };
  const m = map[status] || { label: status, css: "" };
  return `<span class="bt-status-badge ${m.css}">${m.label}</span>`;
}
function _fmtDate(s) { return s ? String(s).slice(5) : "—"; }
function _esc(s) {
  return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
