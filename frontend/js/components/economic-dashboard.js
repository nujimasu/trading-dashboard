/**
 * Economic Indicators Dashboard — FRED tiles + Sector ETF bars.
 */
import { apiFetch } from "../utils/api.js";

export async function renderEconomicDashboard(container) {
  container.innerHTML = `<div class="loading"><div class="spinner"></div><span>経済データ取得中...</span></div>`;

  let data;
  try {
    data = await apiFetch("/api/economic-dashboard");
  } catch (e) {
    container.innerHTML = `<div class="empty-state">データ取得失敗: ${e.message}</div>`;
    return;
  }

  const fred = data.fred_indicators || [];

  container.innerHTML = `
    <div class="econ-wrapper">
      <div class="section-title">📈 経済指標ダッシュボード</div>

      ${_fredSection(fred)}
    </div>`;
}

// ── FRED Indicators ─────────────────────────────────────────────────────────

function _fredSection(items) {
  if (!items.length) {
    return `
      <div class="econ-sec-label">主要経済指標（FRED）</div>
      <div class="econ-empty">
        データなし — パイプラインを実行してください:
        <code>python3 pipeline/run_pipeline.py</code>
      </div>`;
  }

  const tiles = items.map(item => {
    // Parse value from description like "最新値: 4.50 %（前回: 5.25 %）"
    const valMatch  = item.description?.match(/最新値:\s*([\d.]+)/);
    const prevMatch = item.description?.match(/前回:\s*([\d.]+)/);
    const val  = valMatch  ? valMatch[1]  : "—";
    const prev = prevMatch ? prevMatch[1] : null;

    const impactCls   = item.impact === "positive" ? "econ-pos"
                      : item.impact === "negative" ? "econ-neg"
                      : "econ-neu";
    const impactLabel = item.impact === "positive" ? "▲ 株式ポジティブ"
                      : item.impact === "negative" ? "▼ 株式ネガティブ"
                      : "→ 中立";
    const dateStr = item.date ? item.date.slice(0, 7) : ""; // YYYY-MM

    const nextStr = item.next_release
      ? `<div class="econ-tile-next">次回: ${esc(item.next_release)}</div>`
      : "";

    return `
      <div class="econ-tile">
        <div class="econ-tile-name">${esc(item.name)}</div>
        <div class="econ-tile-val">${esc(val)}</div>
        ${prev ? `<div class="econ-tile-prev">前回: ${esc(prev)}</div>` : ""}
        <div class="econ-tile-impact ${impactCls}">${impactLabel}</div>
        <div class="econ-tile-date">${dateStr}</div>
        ${nextStr}
      </div>`;
  }).join("");

  return `
    <div class="econ-sec-label">主要経済指標（FRED）</div>
    <div class="econ-tiles-grid">${tiles}</div>`;
}

// ── Sector ETF Performance ───────────────────────────────────────────────────

function _sectorSection(sectors) {
  const entries = Object.entries(sectors).sort((a, b) => b[1].change_ytd - a[1].change_ytd);

  if (!entries.length) {
    return `
      <div class="econ-sec-label">セクターETF 騰落率</div>
      <div class="econ-empty">セクターデータ取得中...</div>`;
  }

  // Max absolute 1d change for bar scaling
  const max1d = Math.max(...entries.map(([, v]) => Math.abs(v.change_1d)), 3);

  const rows = entries.map(([name, v]) => {
    const cls1d  = v.change_1d  >= 0 ? "econ-pos" : "econ-neg";
    const clsYtd = v.change_ytd >= 0 ? "econ-pos" : "econ-neg";
    const sign1d  = v.change_1d  >= 0 ? "+" : "";
    const signYtd = v.change_ytd >= 0 ? "+" : "";

    // Bar width: 0–100% based on max absolute value
    const barPct = Math.min(Math.abs(v.change_1d) / max1d * 100, 100).toFixed(1);
    const barCls = v.change_1d >= 0 ? "econ-bar-pos" : "econ-bar-neg";

    return `
      <div class="econ-sector-row">
        <div class="econ-sector-name">
          <span class="econ-sector-lbl">${esc(name)}</span>
          <span class="econ-sector-ticker">${v.ticker}</span>
        </div>
        <div class="econ-sector-bar-wrap">
          <div class="econ-sector-bar ${barCls}" style="width:${barPct}%"></div>
        </div>
        <div class="econ-sector-nums">
          <span class="econ-sector-1d ${cls1d}">${sign1d}${v.change_1d.toFixed(2)}%</span>
          <span class="econ-sector-sep">|</span>
          <span class="econ-sector-ytd ${clsYtd}">YTD ${signYtd}${v.change_ytd.toFixed(1)}%</span>
          <span class="econ-sector-price">$${v.price.toFixed(2)}</span>
        </div>
      </div>`;
  }).join("");

  return `
    <div class="econ-sec-label">セクターETF 騰落率（前日比 / 年初来）</div>
    <div class="econ-sector-list">${rows}</div>`;
}

function esc(s) {
  return (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
