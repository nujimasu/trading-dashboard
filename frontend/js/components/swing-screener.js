import { apiFetch } from "../utils/api.js?v=3";

const COLUMNS = [
  { key: "ticker", label: "ティッカー", kind: "text" },
  { key: "state", label: "状態", kind: "text" },
  { key: "dow_trend", label: "ダウ理論", kind: "text" },
  { key: "touch_days_ago", label: "タッチ", kind: "number" },
  { key: "price", label: "株価", kind: "number" },
  { key: "ema20_dist", label: "20EMA乖離%", kind: "number" },
  { key: "adx", label: "ADX", kind: "number" },
  { key: "rs63", label: "RS3M%", kind: "number" },
  { key: "rs126", label: "RS6M%", kind: "number" },
  { key: "atr_pct", label: "ATR%", kind: "number" },
  { key: "dollar_vol", label: "売買代金($M)", kind: "number" },
  { key: "po_weeks", label: "PO継続週", kind: "number" },
];

const LINE_COLORS = {
  trendline: "#f59e0b",
  neckline: "#22d3ee",
  flag_upper: "#60a5fa",
  flag_lower: "#60a5fa",
  tri_upper: "#fb923c",
  tri_lower: "#fb923c",
};

const LEVEL_COLORS = {
  "日足EMA20": "#facc15",
  "直近スイング高値": "#ef4444",
  "直近スイング安値": "#22c55e",
  "出来高集中帯上端": "#a78bfa",
  "出来高集中帯下端": "#a78bfa",
};

const STYLE = `
  .swing-shell { --sw-line:#26354d; --sw-panel:#111c30; display:grid; gap:16px; }
  .swing-hero { position:relative; overflow:hidden; border:1px solid var(--sw-line); border-radius:14px; padding:18px 20px; background:linear-gradient(120deg,#101d32 0%,#0e1728 62%,#14243a 100%); }
  .swing-hero::after { content:"W1 × D1"; position:absolute; right:16px; top:2px; color:rgba(96,165,250,.08); font-size:4.4rem; font-weight:900; letter-spacing:-.08em; pointer-events:none; }
  .swing-kicker { color:#60a5fa; font-size:.68rem; letter-spacing:.18em; text-transform:uppercase; font-weight:800; }
  .swing-title-row { display:flex; align-items:baseline; flex-wrap:wrap; gap:10px; margin-top:3px; }
  .swing-title { margin:0; font-size:1.35rem; letter-spacing:.01em; }
  .swing-date { color:var(--text-muted); font-size:.78rem; font-variant-numeric:tabular-nums; }
  .swing-funnel { display:flex; align-items:stretch; flex-wrap:wrap; gap:7px; margin-top:15px; }
  .swing-funnel-node { min-width:94px; padding:8px 10px; border:1px solid #2b3d59; border-radius:8px; background:rgba(15,23,42,.74); }
  .swing-funnel-node span { display:block; color:var(--text-muted); font-size:.62rem; letter-spacing:.06em; }
  .swing-funnel-node strong { display:block; margin-top:2px; color:#e2e8f0; font-size:1.05rem; font-variant-numeric:tabular-nums; }
  .swing-funnel-arrow { align-self:center; color:#47617f; font-weight:900; }
  .swing-note { margin-top:10px; color:#fbbf24; font-size:.72rem; }
  .swing-controls { display:flex; align-items:center; flex-wrap:wrap; gap:10px; padding:12px; border:1px solid var(--sw-line); border-radius:12px; background:var(--sw-panel); }
  .swing-control { display:flex; align-items:center; gap:8px; min-height:34px; padding:5px 9px; border:1px solid #2a3a54; border-radius:8px; background:#0d1727; font-size:.76rem; color:#cbd5e1; }
  .swing-control input[type="checkbox"] { accent-color:#3b82f6; }
  .swing-adx-range { width:116px; accent-color:#3b82f6; }
  .swing-adx-value { min-width:24px; color:#93c5fd; font-weight:800; font-variant-numeric:tabular-nums; }
  .swing-state-group { display:flex; padding:3px; border:1px solid #2a3a54; border-radius:9px; background:#0d1727; }
  .swing-state-btn { border:0; border-radius:6px; padding:6px 9px; background:transparent; color:var(--text-muted); font:inherit; font-size:.73rem; cursor:pointer; }
  .swing-state-btn.active { color:#eaf2ff; background:#29466e; box-shadow:inset 0 0 0 1px #3c5f8e; }
  .swing-results { border:1px solid var(--sw-line); border-radius:12px; background:#0d1727; overflow:hidden; }
  .swing-results-bar { display:flex; justify-content:space-between; gap:12px; padding:10px 13px; border-bottom:1px solid var(--sw-line); color:var(--text-muted); font-size:.74rem; }
  .swing-count { color:#dbeafe; font-weight:800; }
  .swing-table-wrap { overflow:auto; max-height:620px; }
  .swing-table { min-width:1180px; font-variant-numeric:tabular-nums; }
  .swing-table thead { position:sticky; top:0; z-index:2; background:#111c30; }
  .swing-table th { padding:0; white-space:nowrap; }
  .swing-sort { width:100%; padding:10px 9px; border:0; background:transparent; color:var(--text-muted); text-align:left; font:inherit; font-weight:700; cursor:pointer; }
  .swing-sort:hover, .swing-sort.active { color:#bfdbfe; }
  .swing-table td { padding:9px; white-space:nowrap; border-bottom:1px solid rgba(51,65,85,.52); }
  .swing-row { cursor:pointer; transition:background .14s ease; }
  .swing-row:hover, .swing-row.selected { background:rgba(59,130,246,.09); }
  .swing-tv { color:#93c5fd; font-weight:850; letter-spacing:.025em; text-decoration:none; }
  .swing-tv:hover { color:#dbeafe; text-decoration:underline; }
  .swing-badge { display:inline-flex; align-items:center; border-radius:999px; padding:3px 8px; font-size:.68rem; font-weight:800; }
  .swing-state-bounced { color:#86efac; background:rgba(34,197,94,.14); border:1px solid rgba(34,197,94,.28); }
  .swing-state-pulling { color:#fde68a; background:rgba(245,158,11,.13); border:1px solid rgba(245,158,11,.27); }
  .swing-dow-up { color:#86efac; background:rgba(34,197,94,.13); }
  .swing-dow-neutral, .swing-dow-unknown { color:#cbd5e1; background:rgba(148,163,184,.13); }
  .swing-dow-down { color:#fca5a5; background:rgba(239,68,68,.13); }
  .swing-positive { color:#86efac; }
  .swing-negative { color:#fca5a5; }
  .swing-empty { padding:34px 16px; color:var(--text-muted); text-align:center; }
  .swing-detail { border:1px solid #314563; border-radius:12px; overflow:hidden; background:#0a1322; box-shadow:0 18px 45px rgba(0,0,0,.24); }
  .swing-detail[hidden] { display:none; }
  .swing-detail-head { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px; padding:11px 14px; border-bottom:1px solid #263750; background:#111d31; }
  .swing-detail-title { display:flex; align-items:baseline; gap:10px; font-weight:850; }
  .swing-detail-sub { color:var(--text-muted); font-size:.7rem; font-weight:500; }
  .swing-chart-slot { min-height:440px; padding:12px; }
  .swing-chart { width:100%; height:410px; }
  .swing-chart-legend { display:flex; flex-wrap:wrap; gap:7px 12px; padding:0 4px 8px; color:var(--text-muted); font-size:.68rem; }
  .swing-legend-dot { display:inline-block; width:12px; height:2px; margin-right:5px; vertical-align:middle; }
  .swing-loading { min-height:400px; display:grid; place-items:center; color:var(--text-muted); }
  .swing-chart-error { min-height:400px; display:grid; place-items:center; color:#fca5a5; }
  @media (max-width:720px) {
    .swing-hero { padding:15px; }
    .swing-hero::after { font-size:2.8rem; }
    .swing-control { width:100%; justify-content:space-between; }
    .swing-state-group { width:100%; overflow:auto; }
    .swing-state-btn { flex:1; white-space:nowrap; }
    .swing-chart-slot { padding:5px; }
  }
`;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function finite(value) {
  return value != null && Number.isFinite(Number(value));
}

function fixed(value, digits = 1) {
  return finite(value) ? Number(value).toFixed(digits) : "—";
}

function percent(value, digits = 1) {
  return finite(value) ? `${(Number(value) * 100).toFixed(digits)}%` : "—";
}

function signedClass(value) {
  if (!finite(value) || Number(value) === 0) return "";
  return Number(value) > 0 ? "swing-positive" : "swing-negative";
}

function stateBadge(state) {
  return state === "bounced"
    ? '<span class="swing-badge swing-state-bounced">✅ 反発確認済</span>'
    : '<span class="swing-badge swing-state-pulling">⏳ 押し目進行中</span>';
}

function dowBadge(trend) {
  const meta = {
    up: ["上昇", "up"],
    neutral: ["中立", "neutral"],
    down: ["下降", "down"],
    unknown: ["不明", "unknown"],
  }[trend] || ["不明", "unknown"];
  return `<span class="swing-badge swing-dow-${meta[1]}">${meta[0]}</span>`;
}

function funnelNode(label, value) {
  const display = finite(value) ? Number(value).toLocaleString("ja-JP") : "—";
  return `<div class="swing-funnel-node"><span>${label}</span><strong>${display}</strong></div>`;
}

function rowHtml(pick) {
  const ticker = escapeHtml(pick.ticker);
  const tvUrl = `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(pick.ticker || "")}`;
  return `
    <tr class="swing-row" data-ticker="${ticker}">
      <td><a class="swing-tv" href="${tvUrl}" target="_blank" rel="noopener noreferrer">${ticker} ↗</a></td>
      <td>${stateBadge(pick.state)}</td>
      <td>${dowBadge(pick.dow_trend)}</td>
      <td>${finite(pick.touch_days_ago) ? `${Number(pick.touch_days_ago)}日目` : "—"}</td>
      <td>$${fixed(pick.price, 2)}</td>
      <td class="${signedClass(pick.ema20_dist)}">${percent(pick.ema20_dist)}</td>
      <td>${fixed(pick.adx, 1)}</td>
      <td class="${signedClass(pick.rs63)}">${percent(pick.rs63)}</td>
      <td class="${signedClass(pick.rs126)}">${percent(pick.rs126)}</td>
      <td>${percent(pick.atr_pct)}</td>
      <td>${finite(pick.dollar_vol) ? fixed(Number(pick.dollar_vol) / 1e6, 1) : "—"}</td>
      <td>${finite(pick.po_weeks) ? `${Number(pick.po_weeks)}週` : "—"}</td>
    </tr>`;
}

function comparePicks(left, right, key, direction) {
  const column = COLUMNS.find(item => item.key === key);
  const a = left[key];
  const b = right[key];
  const aMissing = a == null || (column?.kind === "number" && !finite(a));
  const bMissing = b == null || (column?.kind === "number" && !finite(b));
  if (aMissing || bMissing) {
    if (aMissing && bMissing) return String(left.ticker).localeCompare(String(right.ticker));
    return aMissing ? 1 : -1;
  }
  const result = column?.kind === "number"
    ? Number(a) - Number(b)
    : String(a).localeCompare(String(b), "ja");
  return result === 0
    ? String(left.ticker).localeCompare(String(right.ticker))
    : result * direction;
}

function lineColor(line) {
  return line.type === "level"
    ? (LEVEL_COLORS[line.label] || "#94a3b8")
    : (LINE_COLORS[line.type] || "#94a3b8");
}

function drawIntradayChart(slot, payload, chartState) {
  chartState.chart?.remove();
  chartState.resizeObserver?.disconnect();
  chartState.chart = null;
  chartState.resizeObserver = null;

  if (!window.LightweightCharts) {
    slot.innerHTML = '<div class="swing-chart-error">チャートライブラリを読み込めませんでした</div>';
    return;
  }
  if (!payload.bars?.length) {
    slot.innerHTML = '<div class="swing-chart-error">15分足データがありません</div>';
    return;
  }

  const labels = [...new Set((payload.annotations?.lines || []).map(line => line.label))];
  slot.innerHTML = `
    <div class="swing-chart"></div>
    <div class="swing-chart-legend">${labels.map(label => {
      const line = payload.annotations.lines.find(item => item.label === label);
      return `<span><i class="swing-legend-dot" style="background:${lineColor(line)}"></i>${escapeHtml(label)}</span>`;
    }).join("")}</div>`;
  const chartElement = slot.querySelector(".swing-chart");
  const chart = window.LightweightCharts.createChart(chartElement, {
    width: chartElement.clientWidth,
    height: 410,
    layout: { background: { color: "#0a1322" }, textColor: "#94a3b8" },
    grid: { vertLines: { color: "#17243a" }, horzLines: { color: "#17243a" } },
    crosshair: { mode: window.LightweightCharts.CrosshairMode.Normal },
    rightPriceScale: { borderColor: "#2b3c55", scaleMargins: { top: 0.08, bottom: 0.2 } },
    timeScale: { borderColor: "#2b3c55", timeVisible: true, secondsVisible: false },
  });
  chartState.chart = chart;

  const candles = chart.addCandlestickSeries({
    upColor: "#22c55e",
    downColor: "#ef4444",
    borderUpColor: "#22c55e",
    borderDownColor: "#ef4444",
    wickUpColor: "#4ade80",
    wickDownColor: "#f87171",
  });
  candles.setData(payload.bars);

  const volume = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "volume" });
  chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
  volume.setData(payload.bars.map(bar => ({
    time: bar.time,
    value: bar.volume || 0,
    color: bar.close >= bar.open ? "rgba(34,197,94,.24)" : "rgba(239,68,68,.24)",
  })));

  for (const line of payload.annotations?.lines || []) {
    const points = line.points || [];
    if (line.type === "level" && points[0] && finite(points[0].price)) {
      candles.createPriceLine({
        price: Number(points[0].price),
        color: lineColor(line),
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: line.label,
      });
    } else if (points.length >= 2) {
      const series = chart.addLineSeries({
        color: lineColor(line),
        lineWidth: line.type === "trendline" || line.type === "neckline" ? 2 : 1,
        priceLineVisible: false,
        lastValueVisible: false,
        title: line.label,
      });
      series.setData(points.slice(0, 2).map(point => ({ time: point.time, value: point.price })));
    }
  }

  const markers = (payload.annotations?.markers || []).map(marker => ({
    time: marker.time,
    position: "aboveBar",
    color: "#facc15",
    shape: "arrowDown",
    text: marker.text,
  }));
  if (markers.length) candles.setMarkers(markers);
  chart.timeScale().fitContent();

  chartState.resizeObserver = new ResizeObserver(() => {
    if (chartElement.clientWidth > 0) chart.applyOptions({ width: chartElement.clientWidth });
  });
  chartState.resizeObserver.observe(chartElement);
}

export async function renderSwingScreener(container) {
  container.innerHTML = '<div class="loading"><div class="spinner"></div><span>押し目候補を集計中...</span></div>';
  let payload;
  try {
    payload = await apiFetch("/api/swing/picks");
  } catch (error) {
    container.innerHTML = `<div class="empty-state">スクリーナーの取得に失敗しました: ${escapeHtml(error.message)}</div>`;
    return;
  }

  const picks = Array.isArray(payload.picks) ? payload.picks : [];
  const funnel = payload.funnel || {};
  const state = {
    adxEnabled: true,
    adxMin: 25,
    excludeDown: true,
    pickState: "all",
    sortKey: "rs126",
    sortDirection: -1,
    activeTicker: null,
    extended: false,
    requestId: 0,
  };
  const chartState = { chart: null, resizeObserver: null };

  container.innerHTML = `
    <style>${STYLE}</style>
    <div class="swing-shell">
      <section class="swing-hero">
        <div class="swing-kicker">Swing Pullback Radar</div>
        <div class="swing-title-row">
          <h2 class="swing-title">押し目スクリーナー</h2>
          <span class="swing-date">基準日 ${escapeHtml(payload.scan_date || "未実行")}</span>
        </div>
        <div class="swing-funnel">
          ${funnelNode("データ十分", funnel.universe)}<span class="swing-funnel-arrow">→</span>
          ${funnelNode("流動性", funnel.liquid)}<span class="swing-funnel-arrow">→</span>
          ${funnelNode("W1 PO", funnel.po)}<span class="swing-funnel-arrow">→</span>
          ${funnelNode("D1 押し目", funnel.dip)}
        </div>
        <div class="swing-note">※ 今週のW1判定は未確定週を含むため、週内に入れ替わることがあります。</div>
      </section>

      <section class="swing-controls" aria-label="スクリーナーフィルタ">
        <label class="swing-control">
          <input type="checkbox" data-control="adx-enabled" checked>
          <span>ADXで絞る</span>
          <input class="swing-adx-range" data-control="adx-min" type="range" min="15" max="35" value="25" aria-label="ADX下限">
          <output class="swing-adx-value">25</output>
        </label>
        <label class="swing-control">
          <input type="checkbox" data-control="exclude-down" checked>
          <span>ダウ理論「下降」を除外</span>
        </label>
        <div class="swing-state-group" role="group" aria-label="状態フィルタ">
          <button class="swing-state-btn active" data-state="all" type="button">すべて</button>
          <button class="swing-state-btn" data-state="bounced" type="button">✅ 反発確認済</button>
          <button class="swing-state-btn" data-state="pulling" type="button">⏳ 押し目進行中</button>
        </div>
      </section>

      <section class="swing-results">
        <div class="swing-results-bar">
          <span><strong class="swing-count">0件</strong> を表示</span>
          <span>行を選択すると15分足を表示</span>
        </div>
        <div class="swing-table-wrap">
          <table class="swing-table">
            <thead><tr>${COLUMNS.map(column => `
              <th aria-sort="${column.key === "rs126" ? "descending" : "none"}"><button type="button" class="swing-sort${column.key === "rs126" ? " active" : ""}" data-sort="${column.key}">${column.label}${column.key === "rs126" ? " ↓" : ""}</button></th>
            `).join("")}</tr></thead>
            <tbody></tbody>
          </table>
        </div>
      </section>

      <section class="swing-detail" hidden></section>
    </div>`;

  const body = container.querySelector(".swing-table tbody");
  const detail = container.querySelector(".swing-detail");
  const count = container.querySelector(".swing-count");

  function closeDetail() {
    state.activeTicker = null;
    state.requestId += 1;
    detail.hidden = true;
    detail.innerHTML = "";
    chartState.chart?.remove();
    chartState.resizeObserver?.disconnect();
    chartState.chart = null;
    chartState.resizeObserver = null;
  }

  async function loadIntraday(ticker) {
    const requestId = ++state.requestId;
    const slot = detail.querySelector(".swing-chart-slot");
    slot.innerHTML = '<div class="swing-loading"><div>15分足を取得中...</div></div>';
    try {
      const response = await apiFetch(`/api/swing/intraday/${encodeURIComponent(ticker)}?extended=${state.extended}`);
      if (requestId !== state.requestId) return;
      drawIntradayChart(slot, response, chartState);
    } catch {
      if (requestId !== state.requestId) return;
      slot.innerHTML = '<div class="swing-chart-error">15分足の取得に失敗しました</div>';
    }
  }

  function openDetail(ticker) {
    if (state.activeTicker === ticker) {
      closeDetail();
      renderRows();
      return;
    }
    state.activeTicker = ticker;
    state.extended = false;
    detail.hidden = false;
    detail.innerHTML = `
      <div class="swing-detail-head">
        <div class="swing-detail-title">${escapeHtml(ticker)} <span class="swing-detail-sub">15分足・直近5営業日</span></div>
        <label class="swing-control"><input type="checkbox" data-extended> 時間外も表示</label>
      </div>
      <div class="swing-chart-slot"></div>`;
    detail.querySelector("[data-extended]").addEventListener("change", event => {
      state.extended = event.currentTarget.checked;
      loadIntraday(ticker);
    });
    renderRows();
    loadIntraday(ticker);
    detail.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function renderRows() {
    const filtered = picks.filter(pick => {
      if (state.adxEnabled && (!finite(pick.adx) || Number(pick.adx) < state.adxMin)) return false;
      if (state.excludeDown && pick.dow_trend === "down") return false;
      if (state.pickState !== "all" && pick.state !== state.pickState) return false;
      return true;
    }).sort((a, b) => comparePicks(a, b, state.sortKey, state.sortDirection));

    if (state.activeTicker && !filtered.some(pick => pick.ticker === state.activeTicker)) closeDetail();
    count.textContent = `${filtered.length.toLocaleString("ja-JP")}件`;
    body.innerHTML = filtered.length
      ? filtered.map(rowHtml).join("")
      : '<tr><td class="swing-empty" colspan="12">条件に一致する銘柄がありません</td></tr>';
    body.querySelectorAll(".swing-row").forEach(row => {
      row.classList.toggle("selected", row.dataset.ticker === state.activeTicker);
      row.addEventListener("click", () => openDetail(row.dataset.ticker));
    });
    body.querySelectorAll(".swing-tv").forEach(link => {
      link.addEventListener("click", event => event.stopPropagation());
    });
  }

  container.querySelector('[data-control="adx-enabled"]').addEventListener("change", event => {
    state.adxEnabled = event.currentTarget.checked;
    renderRows();
  });
  container.querySelector('[data-control="adx-min"]').addEventListener("input", event => {
    state.adxMin = Number(event.currentTarget.value);
    container.querySelector(".swing-adx-value").textContent = state.adxMin;
    renderRows();
  });
  container.querySelector('[data-control="exclude-down"]').addEventListener("change", event => {
    state.excludeDown = event.currentTarget.checked;
    renderRows();
  });
  container.querySelectorAll(".swing-state-btn").forEach(button => {
    button.addEventListener("click", () => {
      state.pickState = button.dataset.state;
      container.querySelectorAll(".swing-state-btn").forEach(item => item.classList.toggle("active", item === button));
      renderRows();
    });
  });
  container.querySelectorAll(".swing-sort").forEach(button => {
    button.addEventListener("click", () => {
      const key = button.dataset.sort;
      state.sortDirection = state.sortKey === key ? state.sortDirection * -1 : (key === "ticker" ? 1 : -1);
      state.sortKey = key;
      container.querySelectorAll(".swing-sort").forEach(item => {
        const active = item.dataset.sort === key;
        item.classList.toggle("active", active);
        item.textContent = COLUMNS.find(column => column.key === item.dataset.sort).label + (active ? (state.sortDirection > 0 ? " ↑" : " ↓") : "");
        item.parentElement.setAttribute("aria-sort", active ? (state.sortDirection > 0 ? "ascending" : "descending") : "none");
      });
      renderRows();
    });
  });

  renderRows();
}
