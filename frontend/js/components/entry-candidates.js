/**
 * エントリー候補一覧 — 全4ソースを統合表示
 */
import { apiFetch } from "../utils/api.js?v=2";

const SOURCE_META = {
  daily_funda:  { label: "日次FA", color: "#3b82f6" },
  daily_tech:   { label: "日次TE", color: "#8b5cf6" },
  weekly_funda: { label: "週次FA", color: "#10b981" },
  weekly_tech:  { label: "週次TE", color: "#f59e0b" },
};

const DIRECTION_ICON = { LONG: "↑", SHORT: "↓" };
const DIRECTION_CSS  = { LONG: "dir-long", SHORT: "dir-short" };

export async function renderEntryCandidates(container) {
  container.innerHTML = `<div class="loading"><div class="spinner"></div><span>エントリー候補を集計中...</span></div>`;

  let picks;
  try {
    picks = await apiFetch("/api/entry-candidates");
  } catch (e) {
    container.innerHTML = `<div class="empty-state">取得失敗: ${e.message}</div>`;
    return;
  }

  if (!picks.length) {
    container.innerHTML = `
      <div class="section-header"><h2>🚀 今すぐエントリー候補</h2></div>
      <div class="empty-state">現在エントリー候補はありません</div>`;
    return;
  }

  // 複数ソースと単一ソースに分類
  const multi  = picks.filter(p => p.source_count >= 2);
  const single = picks.filter(p => p.source_count === 1);

  container.innerHTML = `
    <div class="section-header">
      <h2>🚀 今すぐエントリー候補</h2>
      <p class="section-desc">4つのスクリーニングソースを統合。複数ソースに登場する銘柄はシグナルが強い。</p>
    </div>

    ${multi.length ? `
    <div class="ec-group-label">
      <span class="ec-multi-badge">複数ソース一致</span>
      <span class="ec-group-count">${multi.length}銘柄 — より強いシグナル</span>
    </div>
    <div class="ec-table-wrap">
      <table class="ec-table">
        <thead><tr>
          <th>銘柄</th>
          <th>方向</th>
          <th>ソース</th>
          <th>RR</th>
          <th>Tier</th>
          <th>セクター</th>
          <th>現在値</th>
        </tr></thead>
        <tbody>${multi.map(p => _row(p)).join("")}</tbody>
      </table>
    </div>` : ""}

    <div class="ec-group-label" style="margin-top:28px">
      <span class="ec-single-label">単一ソース</span>
      <span class="ec-group-count">${single.length}銘柄</span>
    </div>
    <div class="ec-table-wrap">
      <table class="ec-table">
        <thead><tr>
          <th>銘柄</th>
          <th>方向</th>
          <th>ソース</th>
          <th>RR</th>
          <th>Tier</th>
          <th>セクター</th>
          <th>現在値</th>
        </tr></thead>
        <tbody>${single.map(p => _row(p)).join("")}</tbody>
      </table>
    </div>

    <div class="ec-legend">
      ${Object.entries(SOURCE_META).map(([k, v]) =>
        `<span class="ec-badge" style="background:${v.color}20;color:${v.color};border-color:${v.color}40">${v.label}</span>
         <span class="ec-legend-desc">${_sourceDesc(k)}</span>`
      ).join("")}
    </div>`;
}

function _row(p) {
  const dir     = p.direction || "LONG";
  const dirIcon = DIRECTION_ICON[dir] || "↑";
  const dirCss  = DIRECTION_CSS[dir]  || "dir-long";
  const rr      = p.best_rr != null ? p.best_rr.toFixed(2) : "—";
  const price   = p.current_price != null ? `$${p.current_price.toFixed(2)}` : "—";
  const tier    = p.tier || "—";
  const sector  = p.sector || "—";

  const sourceBadges = p.sources.map(s => {
    const m = SOURCE_META[s] || { label: s, color: "#888" };
    return `<span class="ec-badge" style="background:${m.color}20;color:${m.color};border-color:${m.color}40">${m.label}</span>`;
  }).join(" ");

  const tierCss = tier === "Tier1" ? "tier1" : tier === "Tier2" ? "tier2" : "";

  return `
    <tr>
      <td class="ec-ticker">${p.ticker}</td>
      <td><span class="ec-dir ${dirCss}">${dirIcon} ${dir}</span></td>
      <td class="ec-sources">${sourceBadges}</td>
      <td class="ec-rr">${rr}</td>
      <td><span class="ec-tier ${tierCss}">${tier}</span></td>
      <td class="ec-sector">${sector}</td>
      <td class="ec-price">${price}</td>
    </tr>`;
}

function _sourceDesc(key) {
  return {
    daily_funda:  "日次ファンダ考慮（ENTRY_NOW / WATCH）",
    daily_tech:   "日次テクニカル重視（BUY / WATCH）",
    weekly_funda: "週次ファンダ考慮（全ピック）",
    weekly_tech:  "週次テクニカル重視（confidence 55%↑）",
  }[key] || key;
}
