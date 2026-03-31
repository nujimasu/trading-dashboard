/**
 * Candlestick chart renderer using lightweight-charts (TradingView OSS).
 * Loaded via CDN in index.html.
 */

export function renderCandlestick(containerId, chartData, levels = {}) {
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

  const chart = LightweightCharts.createChart(container, {
    width:  container.clientWidth,
    height: container.clientHeight || 280,
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

  // Candlestick series
  const candleSeries = chart.addCandlestickSeries({
    upColor:   "#22c55e",
    downColor: "#ef4444",
    borderUpColor:   "#22c55e",
    borderDownColor: "#ef4444",
    wickUpColor:   "#22c55e",
    wickDownColor: "#ef4444",
  });
  candleSeries.setData(chartData);

  // Horizontal lines for entry / stop / target
  if (levels.entry) {
    const series = chart.addLineSeries({ color: "#3b82f6", lineWidth: 1, lineStyle: 1 });
    series.setData(chartData.map(d => ({ time: d.time, value: levels.entry })));
  }
  if (levels.stop) {
    const series = chart.addLineSeries({ color: "#ef4444", lineWidth: 1, lineStyle: 2 });
    series.setData(chartData.map(d => ({ time: d.time, value: levels.stop })));
  }
  if (levels.target) {
    const series = chart.addLineSeries({ color: "#22c55e", lineWidth: 1, lineStyle: 2 });
    series.setData(chartData.map(d => ({ time: d.time, value: levels.target })));
  }

  chart.timeScale().fitContent();

  // Responsive resize
  const ro = new ResizeObserver(() => {
    chart.applyOptions({ width: container.clientWidth });
  });
  ro.observe(container);
}
