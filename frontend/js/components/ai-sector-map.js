import { apiFetch } from "../utils/api.js?v=3";

const PERIOD_LABELS = { "1w": "1週間", "1m": "1ヶ月", "3m": "3ヶ月" };
const PERIOD_ORDER = ["1w", "1m", "3m"];
const PREFS_KEY = "ai-sector-map-period-v1";
const MARKET_KEY = "ai-sector-map-market-v1";
const MARKET_ORDER = ["us", "jp"];
const MARKET_LABELS = { us: "🇺🇸 米国", jp: "🇯🇵 日本" };
const RS_TREND_ICON = { improving: "↗", worsening: "↘", flat: "→" };
const RS_TREND_LABEL = { improving: "改善中", worsening: "悪化中", flat: "横ばい" };

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function fixed(value, digits = 1) {
  return Number.isFinite(value) ? value.toFixed(digits) : "―";
}

function signed(value, digits = 1) {
  if (!Number.isFinite(value)) return "―";
  const s = value.toFixed(digits);
  return value > 0 ? `+${s}` : s;
}

function toneClass(value) {
  if (!Number.isFinite(value)) return "aimap-flat";
  if (value > 0) return "aimap-positive";
  if (value < 0) return "aimap-negative";
  return "aimap-flat";
}

function loadPeriodPref() {
  try {
    const value = window.localStorage.getItem(PREFS_KEY);
    return PERIOD_ORDER.includes(value) ? value : "1m";
  } catch {
    return "1m";
  }
}

function savePeriodPref(period) {
  try {
    window.localStorage.setItem(PREFS_KEY, period);
  } catch {
    /* localStorageが使えない環境は無視 */
  }
}

function loadMarketPref() {
  try {
    const value = window.localStorage.getItem(MARKET_KEY);
    return MARKET_ORDER.includes(value) ? value : "us";
  } catch {
    return "us";
  }
}

function saveMarketPref(market) {
  try {
    window.localStorage.setItem(MARKET_KEY, market);
  } catch {
    /* localStorageが使えない環境は無視 */
  }
}

function sparklinePath(values, width = 100, height = 32) {
  if (!values || values.length < 2) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const pts = values.map((v, i) => {
    const x = ((i / (values.length - 1)) * (width - 4) + 2).toFixed(1);
    const y = (height - 4 - ((v - min) / range) * (height - 8) + 2).toFixed(1);
    return `${x},${y}`;
  }).join(" ");
  const rising = values[values.length - 1] >= values[0];
  const color = rising ? "#22c55e" : "#ef4444";
  return `<svg class="aimap-spark" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
}

function businessDaysBetween(fromIso, toIso) {
  if (!fromIso || !toIso) return 0;
  const from = new Date(`${fromIso}T00:00:00Z`);
  const to = new Date(`${toIso}T00:00:00Z`);
  let count = 0;
  const cursor = new Date(from.getTime());
  while (cursor.getTime() < to.getTime()) {
    cursor.setUTCDate(cursor.getUTCDate() + 1);
    const day = cursor.getUTCDay();
    if (day !== 0 && day !== 6) count += 1;
  }
  return count;
}

function categoryBadges(cat) {
  const badges = [];
  if (cat.swing_pick_count > 0) {
    badges.push(`<span class="aimap-badge aimap-badge-swing" title="押し目スクリーナーの本日の候補 ${cat.swing_pick_count}件（スキャン対象外の銘柄は含まれません）">🎯${cat.swing_pick_count}</span>`);
  }
  if (cat.earnings_this_week > 0) {
    badges.push(`<span class="aimap-badge aimap-badge-earnings" title="7日以内に決算発表を控えている銘柄 ${cat.earnings_this_week}件">📅${cat.earnings_this_week}</span>`);
  }
  if (cat.overheat) {
    badges.push(`<span class="aimap-badge aimap-badge-overheat" title="直近5営業日で+10%以上上昇。追いかけ買いは過熱リスクに注意">⚠</span>`);
  }
  return badges.join("");
}

function categoryCardHtml(cat, index, benchmarkLabel) {
  const ret = cat.return_pct;
  const trend = cat.rs_trend || "flat";
  const breadthPct = cat.breadth_pct;
  return `
    <button type="button" class="aimap-card ${toneClass(ret)}" data-cat="${escapeHtml(cat.id)}" aria-expanded="false">
      <div class="aimap-card-rank">${index + 1}</div>
      <div class="aimap-card-main">
        <div class="aimap-card-head">
          <span class="aimap-card-label"><span class="aimap-label-full">${escapeHtml(cat.label)}</span><span class="aimap-label-short">${escapeHtml(cat.short_label || cat.label)}</span></span>
          <span class="aimap-card-ret-group">
            <span class="aimap-card-ret ${toneClass(ret)}">${signed(ret)}%</span>
            <span class="aimap-rs-trend-mini aimap-rs-${trend}">${RS_TREND_ICON[trend]}</span>
          </span>
        </div>
        <div class="aimap-card-sub">
          <span title="${escapeHtml(benchmarkLabel)}比の相対強度（パーセントポイント差）">RS ${signed(cat.rs_pt)}pt</span>
          <span class="aimap-rs-trend aimap-rs-${trend}" title="1週間RSと1ヶ月RSの順位を比較したモメンタム（${RS_TREND_LABEL[trend]}）">${RS_TREND_ICON[trend]} ${RS_TREND_LABEL[trend]}</span>
        </div>
        <div class="aimap-card-chart">${sparklinePath(cat.index_series.map(p => p.value))}</div>
        <div class="aimap-card-breadth" title="20EMAより上にある銘柄の比率（一部の銘柄だけの見せかけの強さではないかを確認）">
          <div class="aimap-breadth-bar"><div class="aimap-breadth-fill" style="width:${breadthPct ?? 0}%"></div></div>
          <span class="aimap-breadth-label">参加率 ${breadthPct == null ? "―" : `${fixed(breadthPct, 0)}%`}<span class="aimap-breadth-frac"> (${cat.breadth_n}/${cat.breadth_total})</span></span>
        </div>
        <div class="aimap-card-badges">${categoryBadges(cat)}</div>
        ${cat.n_calc < cat.n_total ? `<div class="aimap-card-note">データ不足の銘柄を除いて算出（${cat.n_calc}/${cat.n_total}銘柄）</div>` : ""}
      </div>
      <div class="aimap-card-chevron">▾</div>
    </button>
  `;
}

function tickerRowHtml(t) {
  if (t.no_data) {
    return `<tr class="aimap-ticker-row"><td>${escapeHtml(t.ticker)}</td><td colspan="6" class="aimap-no-data">価格データ未取得</td></tr>`;
  }
  const earn = t.earnings_date
    ? `<span class="aimap-earn-badge" title="決算発表予定日">📅 ${escapeHtml(t.earnings_date)}${t.earnings_timing ? ` (${escapeHtml(t.earnings_timing)})` : ""}</span>`
    : "";
  const swing = t.in_swing_picks ? `<span class="aimap-earn-badge aimap-swing-badge" title="本日の押し目スクリーナー候補">🎯</span>` : "";
  return `
    <tr class="aimap-ticker-row">
      <td class="aimap-ticker-name">
        <a class="aimap-tv" href="${t.tv_url}" target="_blank" rel="noopener">${escapeHtml(t.ticker)}</a>
        ${t.name ? `<span class="aimap-company-name">${escapeHtml(t.name)}</span>` : ""}
      </td>
      <td class="aimap-num">${t.close != null ? fixed(t.close, 2) : "―"}</td>
      <td class="aimap-num ${toneClass(t.chg_1d_pct)}">${signed(t.chg_1d_pct)}%</td>
      <td class="aimap-num ${toneClass(t.return_pct)}">${signed(t.return_pct)}%</td>
      <td class="aimap-spark-cell">${sparklinePath(t.spark || [], 84, 26)}</td>
      <td class="aimap-badges-cell">${swing}${earn}</td>
    </tr>
  `;
}

function categoryDetailHtml(cat) {
  return `
    <div class="aimap-detail" data-cat-detail="${escapeHtml(cat.id)}" hidden>
      <div class="aimap-detail-actions">
        <button type="button" class="aimap-news-link" data-news-cat="${escapeHtml(cat.id)}">📰 ${escapeHtml(cat.short_label || cat.label)}のニュースを見る</button>
      </div>
      <div class="aimap-table-wrap">
        <table class="aimap-table">
          <thead>
            <tr><th>銘柄</th><th>株価</th><th>前日比</th><th>期間リターン</th><th>推移</th><th></th></tr>
          </thead>
          <tbody>
            ${cat.tickers.map(tickerRowHtml).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function priceStaleWarningHtml(summary) {
  if (!summary.price_stale) return "";
  const days = businessDaysBetween(summary.as_of, new Date().toISOString().slice(0, 10));
  return `<div class="aimap-warning" role="alert">⚠️ 価格データが${days > 0 ? `約${days}営業日` : ""}古い可能性があります（最終更新 ${escapeHtml(summary.as_of)}）</div>`;
}

let chartInstance = null;
let resizeObserver = null;
const CHART_COLORS = ["#3b82f6", "#22c55e", "#f97316", "#a855f7", "#eab308", "#ec4899", "#14b8a6", "#f43f5e"];

function renderComparisonChart(container, categories) {
  chartInstance?.remove();
  resizeObserver?.disconnect();
  chartInstance = null;

  if (!window.LightweightCharts) {
    container.innerHTML = '<div class="aimap-chart-error">チャートライブラリを読み込めませんでした</div>';
    return;
  }
  const withSeries = categories.filter(c => c.index_series && c.index_series.length >= 2);
  if (!withSeries.length) {
    container.innerHTML = '<div class="aimap-chart-error">比較チャート用のデータがありません</div>';
    return;
  }

  container.innerHTML = `
    <div class="aimap-chart-legend">${withSeries.map((c, i) => `<span><i class="aimap-legend-dot" style="background:${CHART_COLORS[i % CHART_COLORS.length]}"></i>${escapeHtml(c.short_label || c.label)}</span>`).join("")}</div>
    <div class="aimap-chart"></div>
  `;
  const chartEl = container.querySelector(".aimap-chart");
  const chart = window.LightweightCharts.createChart(chartEl, {
    width: chartEl.clientWidth,
    height: 320,
    layout: { background: { color: "#0d1727" }, textColor: "#94a3b8" },
    grid: { vertLines: { color: "#1e293b" }, horzLines: { color: "#1e293b" } },
    crosshair: { mode: window.LightweightCharts.CrosshairMode.Normal },
    rightPriceScale: { borderColor: "#334155" },
    timeScale: { borderColor: "#334155" },
  });
  chartInstance = chart;

  withSeries.forEach((cat, i) => {
    const series = chart.addLineSeries({
      color: CHART_COLORS[i % CHART_COLORS.length],
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    series.setData(cat.index_series.map(p => ({ time: p.date, value: p.value })));
  });
  chart.timeScale().fitContent();

  resizeObserver = new ResizeObserver(() => {
    if (chartEl.clientWidth > 0) chart.applyOptions({ width: chartEl.clientWidth });
  });
  resizeObserver.observe(chartEl);
}

function goToNewsPage(categoryId, market) {
  try {
    window.sessionStorage.setItem("ai-news-filter-category", categoryId);
    window.sessionStorage.setItem("ai-news-filter-market", market);
  } catch {
    /* sessionStorageが使えない環境は無視（フィルタ無しでニュースページが開く） */
  }
  document.querySelector('.nav-item[data-section="ai-news"]')?.click();
}

export async function renderAiSectorMap(container) {
  container.innerHTML = '<div class="loading"><div class="spinner"></div><span>AIセクターマップを集計中...</span></div>';

  let period = loadPeriodPref();
  const market = loadMarketPref();
  let summary;
  try {
    summary = await apiFetch(`/api/ai-map/summary?period=${period}&market=${market}`);
  } catch (error) {
    container.innerHTML = `<div class="empty-state">AIセクターマップの取得に失敗しました: ${escapeHtml(error.message)}</div>`;
    return;
  }

  container.innerHTML = `
    <style>${STYLE}</style>
    <div class="aimap-shell">
      <div class="aimap-hero">
        <div class="aimap-kicker">AI SECTOR MAP</div>
        <div class="aimap-title-row">
          <h2 class="aimap-title">AIセクターマップ</h2>
          <span class="aimap-date">基準日 ${escapeHtml(summary.as_of || "―")}　ベンチマーク ${escapeHtml(summary.benchmark?.label || summary.benchmark?.ticker || "―")} ${signed(summary.benchmark?.return_pct)}%</span>
        </div>
        <div class="aimap-market-toggle" role="tablist">
          ${MARKET_ORDER.map(m => `<button type="button" class="aimap-market-btn ${m === market ? "active" : ""}" data-market="${m}" role="tab" aria-selected="${m === market}">${MARKET_LABELS[m]}</button>`).join("")}
        </div>
        <div class="aimap-period-toggle" role="tablist">
          ${PERIOD_ORDER.map(p => `<button type="button" class="aimap-period-btn ${p === period ? "active" : ""}" data-period="${p}" role="tab" aria-selected="${p === period}">${PERIOD_LABELS[p]}</button>`).join("")}
        </div>
        ${priceStaleWarningHtml(summary)}
      </div>

      <div class="aimap-cards" id="aimap-cards">
        ${summary.categories.map((c, i) => categoryCardHtml(c, i, summary.benchmark?.label || summary.benchmark?.ticker || "指数")).join("")}
      </div>

      <div class="aimap-panel">
        <div class="aimap-panel-title">カテゴリー比較（起点=100）</div>
        <div id="aimap-chart-container"></div>
      </div>

      <div id="aimap-details">
        ${summary.categories.map(categoryDetailHtml).join("")}
      </div>
    </div>
  `;

  renderComparisonChart(container.querySelector("#aimap-chart-container"), summary.categories);

  container.querySelectorAll(".aimap-market-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      if (btn.dataset.market === market) return;
      saveMarketPref(btn.dataset.market);
      await renderAiSectorMap(container);
    });
  });

  container.querySelectorAll(".aimap-period-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      period = btn.dataset.period;
      savePeriodPref(period);
      await renderAiSectorMap(container);
    });
  });

  container.querySelectorAll(".aimap-card").forEach(card => {
    card.addEventListener("click", () => {
      const catId = card.dataset.cat;
      const detail = container.querySelector(`[data-cat-detail="${CSS.escape(catId)}"]`);
      const isOpen = !detail.hidden;
      container.querySelectorAll(".aimap-detail").forEach(d => { d.hidden = true; });
      container.querySelectorAll(".aimap-card").forEach(c => { c.setAttribute("aria-expanded", "false"); c.classList.remove("aimap-card-open"); });
      if (!isOpen) {
        detail.hidden = false;
        card.setAttribute("aria-expanded", "true");
        card.classList.add("aimap-card-open");
        detail.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    });
  });

  container.querySelectorAll(".aimap-news-link").forEach(btn => {
    btn.addEventListener("click", () => goToNewsPage(btn.dataset.newsCat, market));
  });
}

const STYLE = `
  .aimap-shell { --am-line:#26354d; --am-panel:#111c30; display:grid; gap:16px; }
  .aimap-shell > * { min-width:0; }
  .aimap-hero { position:relative; overflow:hidden; border:1px solid var(--am-line); border-radius:14px; padding:18px 20px; background:linear-gradient(120deg,#101d32 0%,#0e1728 62%,#14243a 100%); }
  .aimap-kicker { color:#60a5fa; font-size:.68rem; letter-spacing:.18em; text-transform:uppercase; font-weight:800; }
  .aimap-title-row { display:flex; align-items:baseline; flex-wrap:wrap; gap:10px; margin-top:3px; }
  .aimap-title { margin:0; font-size:1.35rem; letter-spacing:.01em; }
  .aimap-date { color:var(--text-muted); font-size:.76rem; font-variant-numeric:tabular-nums; }
  .aimap-market-toggle { display:flex; gap:6px; margin-top:14px; }
  .aimap-market-btn { min-height:34px; padding:6px 16px; border:1px solid #365071; border-radius:8px; background:#0d1727; color:#cbd5e1; font:inherit; font-size:.8rem; font-weight:800; cursor:pointer; }
  .aimap-market-btn.active { background:#334155; border-color:#64748b; color:#fff; }
  .aimap-period-toggle { display:flex; gap:6px; margin-top:10px; }
  .aimap-period-btn { min-height:32px; padding:5px 14px; border:1px solid #365071; border-radius:999px; background:#0d1727; color:#93c5fd; font:inherit; font-size:.76rem; font-weight:700; cursor:pointer; }
  .aimap-period-btn.active { background:#1d4ed8; border-color:#1d4ed8; color:#fff; }
  .aimap-warning { position:relative; z-index:1; display:flex; align-items:center; gap:8px; margin-top:12px; padding:9px 11px; border:1px solid rgba(251,146,60,.58); border-radius:8px; background:linear-gradient(90deg,rgba(127,29,29,.42),rgba(120,53,15,.32)); color:#fed7aa; box-shadow:inset 3px 0 0 #f97316; font-size:.76rem; font-weight:750; }

  .aimap-cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:12px; }
  .aimap-card { display:flex; align-items:flex-start; gap:10px; width:100%; padding:14px; border:1px solid var(--am-line); border-radius:12px; background:var(--am-panel); color:inherit; font:inherit; text-align:left; cursor:pointer; transition:border-color .14s ease, background .14s ease; }
  .aimap-card:hover { border-color:#46617f; }
  .aimap-card.aimap-card-open { border-color:#3b82f6; background:#132038; }
  .aimap-card-rank { min-width:22px; color:#47617f; font-weight:900; font-variant-numeric:tabular-nums; }
  .aimap-card-main { flex:1; min-width:0; }
  .aimap-card-head { display:flex; align-items:baseline; justify-content:space-between; gap:8px; }
  .aimap-card-label { font-weight:800; font-size:.86rem; }
  .aimap-label-short { display:none; }
  .aimap-card-ret-group { display:inline-flex; align-items:baseline; gap:4px; white-space:nowrap; }
  .aimap-card-ret { font-weight:900; font-size:1.05rem; font-variant-numeric:tabular-nums; }
  .aimap-rs-trend-mini { display:none; font-weight:900; font-size:.82rem; }
  .aimap-card-sub { display:flex; align-items:center; gap:10px; margin-top:3px; color:var(--text-muted); font-size:.72rem; }
  .aimap-rs-trend { font-weight:800; }
  .aimap-rs-improving { color:#22c55e; }
  .aimap-rs-worsening { color:#ef4444; }
  .aimap-rs-flat { color:#94a3b8; }
  .aimap-card-chart { margin-top:8px; height:32px; }
  .aimap-spark { width:100%; height:100%; }
  .aimap-card-breadth { display:flex; align-items:center; gap:8px; margin-top:8px; }
  .aimap-breadth-bar { flex:1; height:5px; border-radius:3px; background:#1e293b; overflow:hidden; }
  .aimap-breadth-fill { height:100%; background:#3b82f6; }
  .aimap-breadth-label { color:var(--text-muted); font-size:.66rem; white-space:nowrap; }
  .aimap-card-badges { display:flex; flex-wrap:wrap; gap:5px; margin-top:8px; }
  .aimap-badge { display:inline-flex; align-items:center; border-radius:999px; padding:2px 7px; font-size:.64rem; font-weight:750; }
  .aimap-badge-swing { color:#93c5fd; background:rgba(59,130,246,.14); }
  .aimap-badge-earnings { color:#fde68a; background:rgba(234,179,8,.14); }
  .aimap-badge-overheat { color:#fca5a5; background:rgba(239,68,68,.14); }
  .aimap-card-note { margin-top:7px; color:#64748b; font-size:.64rem; }
  .aimap-card-chevron { color:#47617f; font-weight:900; }
  .aimap-card[aria-expanded="true"] .aimap-card-chevron { color:#93c5fd; }

  .aimap-positive { color:#86efac; }
  .aimap-negative { color:#fca5a5; }
  .aimap-flat { color:#cbd5e1; }
  .aimap-card.aimap-positive { box-shadow:inset 3px 0 0 #22c55e; }
  .aimap-card.aimap-negative { box-shadow:inset 3px 0 0 #ef4444; }

  .aimap-panel { border:1px solid var(--am-line); border-radius:12px; background:var(--am-panel); padding:14px; }
  .aimap-panel-title { color:#dbeafe; font-size:.78rem; font-weight:800; margin-bottom:10px; }
  .aimap-chart-legend { display:flex; flex-wrap:wrap; gap:7px 14px; margin-bottom:8px; color:var(--text-muted); font-size:.68rem; }
  .aimap-legend-dot { display:inline-block; width:12px; height:2px; margin-right:5px; vertical-align:middle; }
  .aimap-chart { width:100%; height:320px; }
  .aimap-chart-error { min-height:200px; display:grid; place-items:center; color:#fca5a5; }

  .aimap-detail { margin-top:-4px; border:1px solid #314563; border-radius:12px; padding:12px; background:#0a1322; }
  .aimap-detail[hidden] { display:none; }
  .aimap-detail-actions { margin-bottom:10px; }
  .aimap-news-link { min-height:32px; padding:6px 12px; border:1px solid #4c3a7a; border-radius:999px; background:rgba(168,85,247,.12); color:#d8b4fe; font:inherit; font-size:.74rem; font-weight:750; cursor:pointer; }
  .aimap-news-link:hover { background:rgba(168,85,247,.2); }
  .aimap-table-wrap { min-width:0; overflow-x:auto; }
  .aimap-table { width:100%; min-width:560px; border-collapse:collapse; font-variant-numeric:tabular-nums; }
  .aimap-table th { padding:7px 9px; text-align:left; color:var(--text-muted); font-size:.68rem; border-bottom:1px solid var(--am-line); white-space:nowrap; }
  .aimap-table td { padding:8px 9px; border-bottom:1px solid rgba(51,65,85,.4); white-space:nowrap; }
  .aimap-num { text-align:right; }
  .aimap-spark-cell { width:90px; }
  .aimap-badges-cell { display:flex; gap:5px; }
  .aimap-ticker-name { display:flex; flex-direction:column; gap:1px; }
  .aimap-tv { color:#93c5fd; font-weight:850; text-decoration:none; }
  .aimap-tv:hover { color:#dbeafe; text-decoration:underline; }
  .aimap-company-name { color:#64748b; font-size:.64rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:140px; }
  .aimap-no-data { color:#64748b; font-size:.72rem; }
  .aimap-earn-badge { display:inline-flex; align-items:center; border-radius:999px; padding:2px 6px; font-size:.62rem; background:rgba(148,163,184,.12); color:#cbd5e1; white-space:nowrap; }
  .aimap-swing-badge { background:rgba(59,130,246,.14); color:#93c5fd; }

  @media (max-width:720px) {
    .aimap-hero { padding:15px; }
    .aimap-market-toggle, .aimap-period-toggle { width:100%; }
    .aimap-market-btn, .aimap-period-btn { flex:1; text-align:center; }

    /* カードを1行2列のコンパクト表示に切り替える */
    .aimap-cards { grid-template-columns:repeat(2,1fr); gap:8px; }
    .aimap-card { flex-direction:column; padding:10px; gap:0; }
    .aimap-card-rank, .aimap-card-chevron, .aimap-card-sub, .aimap-card-note, .aimap-breadth-frac { display:none; }
    .aimap-label-full { display:none; }
    .aimap-label-short { display:inline; }
    .aimap-card-label { font-size:.74rem; }
    .aimap-card-ret { font-size:.9rem; }
    .aimap-rs-trend-mini { display:inline; }
    .aimap-card-chart { height:22px; margin-top:5px; }
    .aimap-card-breadth { margin-top:5px; gap:5px; }
    .aimap-breadth-label { font-size:.6rem; }
    .aimap-card-badges { margin-top:5px; gap:4px; }
    .aimap-badge { padding:1px 5px; font-size:.62rem; }
  }
`;
