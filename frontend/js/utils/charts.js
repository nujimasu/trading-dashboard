/**
 * Candlestick chart renderer using lightweight-charts (TradingView OSS).
 * Loaded via CDN in index.html.
 *
 * levels:   { entry, stop, tp1, target }
 * pattern:  { pivot, base_low, base_length, base_pattern, base_depth_pct,
 *             breakout_confirmed, breakout_volume_ratio }
 */

export function renderCandlestick(containerId, chartData, levels = {}, pattern = null) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = "";

  if (!window.LightweightCharts) {
    container.textContent = "チャートライブラリ読み込み中...";
    return;
  }
  if (!chartData || chartData.length === 0) {
    container.textContent = "チャートデータなし";
    return;
  }

  // ── Chart container height — taller when pattern overlay is shown ──────
  const chartHeight = pattern ? 340 : 280;
  const volumeHeight = pattern ? 60 : 0;

  const chart = LightweightCharts.createChart(container, {
    width:  container.clientWidth,
    height: chartHeight + volumeHeight,
    layout: {
      background: { color: "#0f172a" },
      textColor:  "#94a3b8",
    },
    grid: {
      vertLines:   { color: "#1e293b" },
      horzLines:   { color: "#1e293b" },
    },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    rightPriceScale: { borderColor: "#334155" },
    timeScale: {
      borderColor: "#334155",
      timeVisible: true,
    },
  });

  // ── Candlestick series ─────────────────────────────────────────────────
  const candleSeries = chart.addCandlestickSeries({
    upColor:   "#22c55e",
    downColor: "#ef4444",
    borderUpColor:   "#22c55e",
    borderDownColor: "#ef4444",
    wickUpColor:   "#22c55e",
    wickDownColor: "#ef4444",
  });
  candleSeries.setData(chartData);

  // ── Volume histogram (when pattern data is provided) ───────────────────
  if (pattern && chartData[0]?.volume != null) {
    const avgVol = chartData.reduce((s, d) => s + (d.volume || 0), 0) / chartData.length;
    const volSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    });
    chart.priceScale("vol").applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });
    volSeries.setData(chartData.map(d => ({
      time: d.time,
      value: d.volume || 0,
      color: (d.volume || 0) > avgVol * 1.5
        ? "rgba(59,130,246,0.6)"   // high volume = blue
        : d.close >= d.open
          ? "rgba(34,197,94,0.25)"  // up bar
          : "rgba(239,68,68,0.25)", // down bar
    })));
  }

  // ── Trade level lines (entry / stop / tp) ──────────────────────────────
  // createPriceLine は title 表示で値の重複を回避できる。
  const PRICE_LINES = [
    { key: "entry",  price: levels.entry,  color: "#3b82f6", title: "Entry", style: 0 },
    { key: "stop",   price: levels.stop,   color: "#ef4444", title: "SL",    style: 2 },
    { key: "tp1",    price: levels.tp1,    color: "#f97316", title: "TP1",   style: 2 },
    { key: "target", price: levels.target, color: "#22c55e", title: "TP2",   style: 2 },
  ];
  for (const line of PRICE_LINES) {
    if (line.price == null) continue;
    candleSeries.createPriceLine({
      price: Number(line.price),
      color: line.color,
      lineWidth: 1,
      lineStyle: line.style,
      axisLabelVisible: true,
      title: line.title,
    });
  }

  // ── Pattern overlays ───────────────────────────────────────────────────
  if (pattern) {
    _drawPatternOverlay(chart, candleSeries, chartData, pattern);
  }

  chart.timeScale().fitContent();

  // ── 凡例（チャート下の説明） ──────────────────────────────────────────
  const legendItems = [];
  if (levels.entry  != null) legendItems.push(`<span class="chart-legend-item"><span class="chart-legend-swatch" style="background:#3b82f6"></span>Entry $${(+levels.entry).toFixed(2)}</span>`);
  if (levels.stop   != null) legendItems.push(`<span class="chart-legend-item"><span class="chart-legend-swatch" style="background:#ef4444"></span>SL $${(+levels.stop).toFixed(2)}</span>`);
  if (levels.tp1    != null) legendItems.push(`<span class="chart-legend-item"><span class="chart-legend-swatch" style="background:#f97316"></span>TP1 $${(+levels.tp1).toFixed(2)}</span>`);
  if (levels.target != null) legendItems.push(`<span class="chart-legend-item"><span class="chart-legend-swatch" style="background:#22c55e"></span>TP2 $${(+levels.target).toFixed(2)}</span>`);
  if (legendItems.length > 0) {
    const legend = document.createElement("div");
    legend.className = "chart-legend";
    legend.innerHTML = legendItems.join("");
    container.appendChild(legend);
  }

  // Responsive resize
  const ro = new ResizeObserver(() => {
    chart.applyOptions({ width: container.clientWidth });
  });
  ro.observe(container);
}


// ═══════════════════════════════════════════════════════════════════════════
// Pattern overlay drawing
// ═══════════════════════════════════════════════════════════════════════════

function _drawPatternOverlay(chart, candleSeries, chartData, pat) {
  const { pivot, base_low, base_length, base_pattern, breakout_confirmed } = pat;

  if (!pivot || !chartData.length) return;

  const len = chartData.length;
  const baseLen = base_length || 30;
  const baseStartIdx = Math.max(0, len - baseLen - 5);  // 5 bars before current
  const baseData = chartData.slice(baseStartIdx);

  // ── 1. Pivot line (yellow, solid) — the breakout level ─────────────────
  if (pivot) {
    const pivotSeries = chart.addLineSeries({
      color: "#eab308",
      lineWidth: 2,
      lineStyle: 0,  // solid
      lastValueVisible: true,
      priceLineVisible: false,
      title: "Pivot",
    });
    pivotSeries.setData(baseData.map(d => ({ time: d.time, value: pivot })));
  }

  // ── 2. Base range band (shaded area between base_high and base_low) ────
  if (base_low && baseData.length > 0) {
    // Calculate base_high from chart data within the base period
    const baseHigh = Math.max(...baseData.map(d => d.high));

    // Upper boundary (dashed, subtle)
    const upperSeries = chart.addLineSeries({
      color: "rgba(148,163,184,0.4)",
      lineWidth: 1,
      lineStyle: 2,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    upperSeries.setData(baseData.map(d => ({ time: d.time, value: baseHigh })));

    // Lower boundary (dashed, subtle)
    const lowerSeries = chart.addLineSeries({
      color: "rgba(148,163,184,0.4)",
      lineWidth: 1,
      lineStyle: 2,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    lowerSeries.setData(baseData.map(d => ({ time: d.time, value: base_low })));
  }

  // ── 3. Pattern-specific markers ────────────────────────────────────────
  const markers = [];

  if (base_pattern === "カップ&ハンドル" && base_low) {
    // Find the cup bottom (lowest low in the base period)
    let cupBottomIdx = 0;
    let cupBottomVal = Infinity;
    baseData.forEach((d, i) => {
      if (d.low < cupBottomVal) { cupBottomVal = d.low; cupBottomIdx = i; }
    });

    markers.push({
      time: baseData[cupBottomIdx].time,
      position: "belowBar",
      color: "#a78bfa",
      shape: "arrowUp",
      text: "カップ底",
    });

    // Left rim (first bar in base)
    markers.push({
      time: baseData[0].time,
      position: "aboveBar",
      color: "#94a3b8",
      shape: "circle",
      text: "左リム",
    });

    // Handle start — roughly the last 25% of the base
    const handleStartIdx = Math.max(0, baseData.length - Math.floor(baseData.length * 0.25));
    if (handleStartIdx > cupBottomIdx) {
      markers.push({
        time: baseData[handleStartIdx].time,
        position: "aboveBar",
        color: "#94a3b8",
        shape: "circle",
        text: "ハンドル",
      });
    }
  }

  else if (base_pattern === "VCP") {
    // Mark contraction stages — divide base into segments
    const segLen = Math.max(5, Math.floor(baseData.length / 4));
    for (let s = 0; s < baseData.length - segLen; s += segLen) {
      const seg = baseData.slice(s, s + segLen);

      // Find the tightest point in each segment
      let tightIdx = s;
      let tightRange = Infinity;
      seg.forEach((d, i) => {
        const r = d.high - d.low;
        if (r < tightRange) { tightRange = r; tightIdx = s + i; }
      });

      if (tightIdx < baseData.length) {
        markers.push({
          time: baseData[tightIdx].time,
          position: "belowBar",
          color: "#818cf8",
          shape: "arrowUp",
          text: `T${Math.floor(s / segLen) + 1}`,
        });
      }
    }
  }

  else if (base_pattern === "アセンディング△") {
    // Mark ascending swing lows
    const swingLows = _findSwingLows(baseData, 3);
    swingLows.forEach((idx, i) => {
      markers.push({
        time: baseData[idx].time,
        position: "belowBar",
        color: "#22d3ee",
        shape: "arrowUp",
        text: `L${i + 1}`,
      });
    });

    // Draw ascending trendline using line series through swing lows
    if (swingLows.length >= 2) {
      const trendData = swingLows.map(idx => ({
        time: baseData[idx].time,
        value: baseData[idx].low,
      }));
      const trendSeries = chart.addLineSeries({
        color: "#22d3ee",
        lineWidth: 1,
        lineStyle: 2,
        lastValueVisible: false,
        priceLineVisible: false,
      });
      trendSeries.setData(trendData);
    }
  }

  else if (base_pattern === "フラットベース") {
    // Flat base — mark the range boundaries clearly
    // Start marker
    markers.push({
      time: baseData[0].time,
      position: "aboveBar",
      color: "#fb923c",
      shape: "circle",
      text: "ベース開始",
    });

    // End marker
    markers.push({
      time: baseData[baseData.length - 1].time,
      position: "aboveBar",
      color: "#fb923c",
      shape: "circle",
      text: `${baseData.length}日`,
    });
  }

  // ── 4. Breakout confirmation marker ────────────────────────────────────
  if (breakout_confirmed && chartData.length > 0) {
    const last = chartData[chartData.length - 1];
    markers.push({
      time: last.time,
      position: "aboveBar",
      color: "#22c55e",
      shape: "arrowDown",
      text: "ブレイクアウト✓",
    });
  }

  // ── 5. Pattern label marker (at base midpoint) ─────────────────────────
  if (base_pattern && baseData.length > 2) {
    const midIdx = Math.floor(baseData.length / 2);
    markers.push({
      time: baseData[midIdx].time,
      position: "belowBar",
      color: "#64748b",
      shape: "square",
      text: base_pattern,
    });
  }

  // Apply all markers
  if (markers.length > 0) {
    // Sort by time (required by lightweight-charts)
    markers.sort((a, b) => a.time < b.time ? -1 : a.time > b.time ? 1 : 0);
    candleSeries.setMarkers(markers);
  }
}


// ── Swing low detection for trendlines ───────────────────────────────────
function _findSwingLows(data, lookback = 3) {
  const lows = [];
  for (let i = lookback; i < data.length - lookback; i++) {
    const window = data.slice(i - lookback, i + lookback + 1);
    const minLow = Math.min(...window.map(d => d.low));
    if (data[i].low === minLow) {
      lows.push(i);
    }
  }
  return lows;
}
