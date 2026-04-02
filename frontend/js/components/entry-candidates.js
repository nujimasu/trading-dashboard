/**
 * 今すぐエントリー — 全4ソース統合テーブル
 * 列: 銘柄 / 方向 / ソース / RR / セクター / スコア
 * スコア降順ソート、行クリックで詳細展開
 */
import { apiFetch } from "../utils/api.js?v=2";
import { renderCandlestick } from "../utils/chart.js?v=1";

const SOURCE_META = {
  daily_funda:  { label: "日次FA", color: "#3b82f6" },
  daily_tech:   { label: "日次TE", color: "#8b5cf6" },
  weekly_funda: { label: "週次FA", color: "#10b981" },
  weekly_tech:  { label: "週次TE", color: "#f59e0b" },
};

let _cachedPicks = [];

export async function renderEntryCandidates(container) {
  container.innerHTML = `<div class="loading"><div class="spinner"></div><span>エントリー候補を集計中...</span></div>`;

  let picks;
  try {
    picks = await apiFetch("/api/entry-candidates");
  } catch (e) {
    container.innerHTML = `<div class="empty-state">取得失敗: ${e.message}</div>`;
    return;
  }
  _cachedPicks = picks;

  if (!picks.length) {
    container.innerHTML = `
      <div class="section-header"><h2>🚀 今すぐエントリー</h2></div>
      <div class="empty-state">現在エントリー候補はありません</div>`;
    return;
  }

  const rows = picks.map((p, i) => _row(p, i)).join("");

  container.innerHTML = `
    <div class="ec-header">
      <h2>🚀 今すぐエントリー</h2>
      <span class="ec-count">${picks.length}銘柄 — スコア順</span>
    </div>

    <div class="ec-table-wrap">
      <table class="ec-table">
        <thead>
          <tr>
            <th>銘柄</th>
            <th>方向</th>
            <th>ソース</th>
            <th>RR</th>
            <th>セクター</th>
            <th>スコア</th>
          </tr>
        </thead>
        <tbody id="ec-tbody">${rows}</tbody>
      </table>
    </div>`;

  // 行クリック → 詳細展開
  container.querySelectorAll(".ec-row").forEach(row => {
    row.addEventListener("click", () => {
      const idx    = parseInt(row.dataset.idx, 10);
      const detail = container.querySelector(`#ec-detail-${idx}`);
      const isOpen = detail.style.display !== "none";

      // 他を閉じる
      container.querySelectorAll(".ec-detail-row").forEach(r => r.style.display = "none");
      container.querySelectorAll(".ec-row").forEach(r => r.classList.remove("ec-row--open"));

      if (!isOpen) {
        detail.style.display = "table-row";
        row.classList.add("ec-row--open");

        // チャート非同期描画
        const pick = _cachedPicks[idx];
        apiFetch(`/api/chart/${pick.ticker}?days=180`).then(resp => {
          if (resp && resp.data && resp.data.length > 0) {
            renderCandlestick(`ec-chart-${idx}`, resp.data, {
              entry:  pick.entry_price,
              stop:   pick.stop_price,
              tp1:    pick.tp1_price,
              target: pick.target_price,
            });
          }
        }).catch(() => {});
      }
    });
  });
}

// ── メイン行 ────────────────────────────────────────────────────────────────
function _row(p, i) {
  const dir      = p.direction || "LONG";
  const dirLabel = dir === "SHORT" ? "↓ SHORT" : "↑ LONG";
  const dirCss   = dir === "SHORT" ? "ec-dir--short" : "ec-dir--long";
  const rr       = p.best_rr != null ? p.best_rr.toFixed(2) : "—";
  const sector   = p.sector  || "—";

  const sourceBadges = p.sources.map(s => {
    const m = SOURCE_META[s] || { label: s, color: "#888" };
    return `<span class="ec-badge" style="background:${m.color}20;color:${m.color};border-color:${m.color}40">${m.label}</span>`;
  }).join(" ");

  const score     = p.unified_score ?? 0;
  const scoreColor = score >= 70 ? "var(--green)" : score >= 45 ? "var(--yellow)" : "var(--red)";
  const scoreBar   = `<div class="ec-score-bar" style="width:${score}%;background:${scoreColor}20;"></div>`;
  const scoreHtml  = `
    <div class="ec-score-wrap">
      ${scoreBar}
      <span class="ec-score-num" style="color:${scoreColor}">${score}</span>
    </div>`;

  return `
    <tr class="ec-row" data-idx="${i}" title="クリックして詳細を表示">
      <td class="ec-ticker">${p.ticker}</td>
      <td><span class="ec-dir ${dirCss}">${dirLabel}</span></td>
      <td class="ec-sources">${sourceBadges}</td>
      <td class="ec-rr">${rr}</td>
      <td class="ec-sector">${_escHtml(sector)}</td>
      <td class="ec-score-cell">${scoreHtml}</td>
    </tr>
    <tr class="ec-detail-row" id="ec-detail-${i}" style="display:none">
      <td colspan="6">${_detailPanel(p, i)}</td>
    </tr>`;
}

// ── 詳細パネル ──────────────────────────────────────────────────────────────
function _detailPanel(p, idx) {
  const ts = p.technical_summary   || {};
  const fs = p.fundamental_summary || {};
  const dir     = p.direction || "LONG";
  const isShort = dir === "SHORT";

  // ソース別 verdict
  const verdictRows = Object.entries(p.verdicts || {}).map(([src, v]) => {
    const m = SOURCE_META[src] || { label: src, color: "#888" };
    return `<div class="ec-kv">
      <span class="ec-badge" style="background:${m.color}20;color:${m.color};border-color:${m.color}40">${m.label}</span>
      <span class="ec-kv-val">${_escHtml(String(v))}</span>
    </div>`;
  }).join("");

  // トレードプラン
  const hasPlan = p.entry_price && p.stop_price;
  const rr1 = hasPlan && p.tp1_price
    ? Math.abs((p.tp1_price - p.entry_price) / (p.entry_price - p.stop_price) * (isShort ? -1 : 1)).toFixed(2)
    : "—";
  const rr2 = p.best_rr ? Number(p.best_rr).toFixed(2) : "—";

  const tradePlan = hasPlan ? `
    <div class="ec-trade-plan">
      <div class="ec-tp-box ec-tp-entry">
        <div class="ec-tp-label">エントリー</div>
        <div class="ec-tp-val">$${_fmt(p.entry_price)}</div>
      </div>
      <div class="ec-tp-arrow">${isShort ? "▼" : "▲"}</div>
      <div class="ec-tp-box ec-tp-sl">
        <div class="ec-tp-label">SL</div>
        <div class="ec-tp-val" style="color:var(--red)">$${_fmt(p.stop_price)}</div>
      </div>
      <div class="ec-tp-arrow">→</div>
      <div class="ec-tp-box ec-tp-tp1">
        <div class="ec-tp-label">TP1</div>
        <div class="ec-tp-val" style="color:var(--green)">$${_fmt(p.tp1_price)}</div>
        <div class="ec-tp-sub">RR ${rr1}R</div>
      </div>
      <div class="ec-tp-arrow">→</div>
      <div class="ec-tp-box ec-tp-tp2">
        <div class="ec-tp-label">TP2</div>
        <div class="ec-tp-val" style="color:var(--green)">$${_fmt(p.target_price)}</div>
        <div class="ec-tp-sub">RR ${rr2}R</div>
      </div>
    </div>` : "";

  // テクニカル
  const techBlock = Object.keys(ts).length ? `
    <div class="ec-detail-block">
      <h4>テクニカル指標</h4>
      ${_kv("RSI",       ts.rsi        ? ts.rsi.toFixed(1) : "—")}
      ${_kv("MACD",      ts.macd_above_sig ? "✅ Signal上" : "❌")}
      ${_kv("出来高比率", ts.volume_ratio ? `${ts.volume_ratio.toFixed(2)}x` : "—")}
      ${_kv("52w高値比", ts.pct_from_high != null ? `${ts.pct_from_high.toFixed(1)}%` : "—")}
      ${_kv("Stage2",    ts.stage2_uptrend ? "✅" : "❌")}
    </div>` : "";

  // ファンダメンタル
  const fundBlock = fs.available ? `
    <div class="ec-detail-block">
      <h4>ファンダメンタル</h4>
      ${_kv("時価総額",     fs.market_cap_b ? `$${fs.market_cap_b}B` : "—")}
      ${_kv("P/E",          fs.pe_ratio ? fs.pe_ratio.toFixed(1) : "—")}
      ${_kv("EPS成長(YoY)", fs.eps_growth_yoy != null ? `${fs.eps_growth_yoy}%` : "—")}
      ${_kv("売上成長(YoY)", fs.revenue_growth_yoy != null ? `${fs.revenue_growth_yoy}%` : "—")}
    </div>` : "";

  return `
    <div class="ec-detail-panel">
      <div class="ec-detail-top">
        <div class="ec-detail-block">
          <h4>シグナル詳細</h4>
          ${verdictRows}
        </div>
        ${techBlock}
        ${fundBlock}
      </div>
      ${tradePlan}
      <div id="ec-chart-${idx}" class="ec-chart-container"></div>
    </div>`;
}

// ── helpers ─────────────────────────────────────────────────────────────────
function _fmt(v) { return v != null ? Number(v).toFixed(2) : "—"; }
function _escHtml(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}
function _kv(label, val) {
  return `<div class="ec-kv"><span class="ec-kv-key">${label}</span><span class="ec-kv-val">${val}</span></div>`;
}
