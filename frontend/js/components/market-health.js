import { apiFetch } from "../utils/api.js?v=2";

let _chart       = null;
let _allHistory  = [];
let _period      = 90;
let _freq        = "daily";
let _data        = null;

export async function renderMarketHealth(container) {
  container.innerHTML = `<div class="loading"><div class="spinner"></div><span>市場データ取得中...</span></div>`;

  try {
    _data = await apiFetch("/api/market-health");
  } catch (e) {
    container.innerHTML = `<div class="empty-state">データ取得失敗: ${e.message}</div>`;
    return;
  }

  // Fetch sentiment in parallel (non-blocking — fills in after layout renders)
  apiFetch("/api/market-sentiment").then(s => {
    const vixEl = document.getElementById("mh-sentiment-section");
    if (vixEl) vixEl.outerHTML = _buildSentimentSection(s);
  }).catch(() => {});

  // Fetch sector ETF performance in parallel (non-blocking)
  apiFetch("/api/economic-dashboard").then(econ => {
    const el = document.getElementById("mh-sector-etf-section");
    if (el && econ.sector_performance) {
      el.outerHTML = _buildSectorETFSection(econ.sector_performance);
    }
  }).catch(() => {});

  if (!_data.date) {
    container.innerHTML = `<div class="empty-state">📊 データなし<br><br><code>python pipeline/run_pipeline.py</code> を実行してください。</div>`;
    return;
  }

  _allHistory = _data.history || [];
  container.innerHTML = _buildLayout(_data);
  _bindControls(container);

  // Destroy old chart before rendering new one
  if (_chart) { _chart.remove(); _chart = null; }
  _renderChart(_allHistory, _period, _freq);
}

// ── Layout ──────────────────────────────────────────────────────────────────

function _buildLayout(d) {
  const score     = d.overall_score;
  const signal    = d.overall_signal;
  const signalCls = signal === "Bullish" ? "bullish" : signal === "Bearish" ? "bearish" : "neutral";
  const signalJa  = signal === "Bullish" ? "強気ゾーン" : signal === "Bearish" ? "弱気ゾーン" : "中立ゾーン";

  const diff5d = d.change_5d;
  let trendJa = "→ 横ばい";
  if (diff5d !== null && diff5d !== undefined) {
    if (diff5d > 0.2)  trendJa = "↑ 上昇トレンド";
    if (diff5d < -0.2) trendJa = "↓ 下落トレンド";
  }

  return `
<div class="mh-wrapper">

  <!-- Titlebar -->
  <div class="mh-titlebar">
    <div>
      <div class="mh-title">市場環境ダッシュボード</div>
      <div class="mh-subtitle">データ更新日: ${d.date}（パイプラインデータ）</div>
    </div>
    <button class="mh-refresh-btn" id="mh-refresh">🔄 更新</button>
  </div>

  <!-- Universe stats bar -->
  <div class="mh-stats-bar">
    <div class="mh-stat">
      <span class="mh-stat-label">スクリーニング対象</span>
      <span class="mh-stat-val">${d.total_screened.toLocaleString()} 銘柄</span>
    </div>
    <div class="mh-stat-sep"></div>
    <div class="mh-stat">
      <span class="mh-stat-label">Stage2 上昇トレンド</span>
      <span class="mh-stat-val">${d.stage2_count.toLocaleString()} 銘柄</span>
    </div>
    <div class="mh-stat-sep"></div>
    <div class="mh-stat">
      <span class="mh-stat-label">SHORT候補含む総ピック</span>
      <span class="mh-stat-val">${d.overall_score.toFixed(1)}% がアップトレンド</span>
    </div>
    <div class="mh-stat-sep"></div>
    <div class="mh-stat">
      <span class="mh-stat-label">最終更新</span>
      <span class="mh-stat-val">${d.date}</span>
    </div>
  </div>

  <!-- Section 1: Overall score -->
  <div class="mh-sec-label">全体アップトレンド比率
    <span class="mh-def-tooltip" title="スクリーニング対象銘柄のうち「Close &gt; SMA50 &gt; SMA200（Stage2上昇トレンド）」を満たす銘柄の割合。65%以上でフルエクスポージャー、35%未満でディフェンシブ推奨。">
      <span class="mh-def-icon">?</span>
    </span>
  </div>
  <div class="mh-top-grid">

    <div class="mh-score-card card">
      <div class="mh-score-row">
        <span class="mh-score-num ${signalCls}">${score.toFixed(1)}%</span>
        ${_changeHtml(diff5d)}
      </div>
      <div class="mh-score-meta">
        <span class="mh-sig-badge ${signalCls}">${signalJa}</span>
        <span class="mh-trend-lbl">${trendJa}</span>
      </div>
    </div>

    <div class="mh-exp-card card">
      ${_exposureHtml(score)}
    </div>
  </div>

  <!-- Comparison strip -->
  <div class="mh-strip">${_stripHtml(d.recent5_avg, d.prev5_avg)}</div>

  <!-- Section 2: Trend chart -->
  <div class="mh-sec-label">アップトレンド比率の推移</div>
  ${_allHistory.length < 5 ? `
  <div class="chart-insufficient">
    データ蓄積中（現在 ${_allHistory.length} 回分）— パイプラインを5回以上実行するとグラフが表示されます
  </div>` : `
  <div class="mh-chart-controls">
    <div class="mh-btn-grp">
      ${[30, 90, 180].map(days =>
        `<button class="mh-period-btn mh-ctrl${days === 90 ? " active" : ""}" data-days="${days}">${days}日</button>`
      ).join("")}
    </div>
    <div class="mh-btn-grp">
      <button class="mh-freq-btn mh-ctrl active" data-freq="daily">日次</button>
      <button class="mh-freq-btn mh-ctrl" data-freq="weekly">週次</button>
    </div>
  </div>
  <div id="mh-chart-container"></div>
  <div class="mh-chart-legend">
    <span class="mh-leg leg-green">● 65%+ フルエクスポージャー</span>
    <span class="mh-leg leg-yellow">● 35〜65% 中立</span>
    <span class="mh-leg leg-orange">● 35%未満 ディフェンシブ</span>
  </div>`}

  <!-- Section 3: Major indices -->
  <div class="mh-sec-label">主要指数（直近30日）</div>
  <div class="mh-index-row">
    ${_indexCards(d.indices || {})}
  </div>

  <!-- Section 4: Sentiment (VIX + Fear & Greed) — filled async -->
  <div id="mh-sentiment-section">
    <div class="mh-sec-label">マーケットセンチメント</div>
    <div class="mh-sentiment-row">
      <div class="mh-sent-loading">センチメントデータ取得中...</div>
    </div>
  </div>

  <!-- Section 6: Sector grid -->
  <div class="mh-sec-label">セクター別アップトレンド比率（現在）</div>
  <div class="mh-sector-grid">
    ${_sectorCards(d.sector_scores || {}, d.sector_ma || {}, d.prev_sector_scores || {}, d.sector_history || {}, d.sector_etf_sparkline || {})}
  </div>

  <!-- Section 7: Sector ETF performance (loaded async) -->
  <div id="mh-sector-etf-section">
    <div class="mh-sec-label">セクターETF 騰落率（前日比 / 年初来）</div>
    <div class="mh-sent-loading">セクターETFデータ取得中...</div>
  </div>

</div>`;
}

// ── Exposure guidance panel ─────────────────────────────────────────────────

const TIERS = [
  { label: "フルエクスポージャー",  range: "65%+",    test: s => s >= 65 },
  { label: "通常運用（新規許可）",  range: "50〜65%", test: s => s >= 50 && s < 65 },
  { label: "縮小・様子見",          range: "35〜50%", test: s => s >= 35 && s < 50 },
  { label: "ディフェンシブ",        range: "35%未満", test: s => s < 35  },
];

function _exposureHtml(score) {
  const activeIdx = TIERS.findIndex(t => t.test(score));
  const rows = TIERS.map((t, i) => {
    const active = i === activeIdx;
    return `<div class="mh-exp-row${active ? " active" : ""}">
      <span class="mh-exp-dot"></span>
      <span class="mh-exp-lbl">${t.label}</span>
      <span class="mh-exp-range">${t.range}</span>
    </div>`;
  }).join("");
  return `<div class="mh-exp-title">エクスポージャーガイダンス</div>${rows}`;
}

// ── Comparison strip ────────────────────────────────────────────────────────

function _stripHtml(r5, p5) {
  if (p5 === null || p5 === undefined) {
    const avgStr = r5 !== null && r5 !== undefined ? `直近平均: <strong>${r5.toFixed(1)}%</strong>` : "";
    return `<span class="mh-cmp-note">データ蓄積中（パイプラインを継続実行すると比較が表示されます）</span>${avgStr ? `<span class="mh-cmp-sep">|</span><span>${avgStr}</span>` : ""}`;
  }
  const diff = Math.round((r5 - p5) * 10) / 10;
  const cls  = diff > 0 ? "up" : diff < 0 ? "dn" : "";
  const sign = diff > 0 ? "+" : "";
  return `
    <span>近近5日 vs 前週5日</span>
    <strong class="${cls}">${sign}${diff}pp</strong>
    <span class="mh-cmp-sep">|</span>
    <span>直近平均: <strong>${r5.toFixed(1)}%</strong></span>`;
}

// ── Score change badge ──────────────────────────────────────────────────────

function _changeHtml(diff) {
  if (diff === null || diff === undefined) return "";
  const cls  = diff > 0 ? "up" : diff < 0 ? "dn" : "flat";
  const sign = diff > 0 ? "+" : "";
  return `<span class="mh-change ${cls}">${sign}${diff.toFixed(1)}pp 5日前比</span>`;
}

// ── Sparkline (inline SVG) ──────────────────────────────────────────────────

function _sparkline(values, width = 90, height = 32) {
  if (!values || values.length < 2) return '';
  const min   = Math.min(...values);
  const max   = Math.max(...values);
  const range = max - min || 1;
  const pts   = values.map((v, i) => {
    const x = ((i / (values.length - 1)) * (width - 4) + 2).toFixed(1);
    const y = (height - 4 - ((v - min) / range) * (height - 8) + 2).toFixed(1);
    return `${x},${y}`;
  }).join(' ');
  const rising = values[values.length - 1] >= values[0];
  const color  = rising ? '#22c55e' : '#ef4444';
  return `<svg class="mh-spark" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
}

// ── Index cards ─────────────────────────────────────────────────────────────

function _indexCards(indices) {
  const order = ["SPY", "QQQ", "IWM"];
  const items = order.map(t => indices[t]).filter(Boolean);
  if (!items.length) {
    return `<div class="mh-idx-empty">指数データなし（パイプライン実行後に表示されます）</div>`;
  }
  return items.map(d => {
    const cls1d  = d.change_1d  >= 0 ? 'up' : 'dn';
    const cls30d = d.change_30d >= 0 ? 'up' : 'dn';
    const sign1d  = d.change_1d  >= 0 ? '+' : '';
    const sign30d = d.change_30d >= 0 ? '+' : '';
    const prices  = d.history.map(h => h.close);
    const spark   = _sparkline(prices);
    const priceStr = d.price >= 1000
      ? d.price.toLocaleString('en-US', { maximumFractionDigits: 2 })
      : d.price.toFixed(2);
    return `
<div class="mh-idx-card card">
  <div class="mh-idx-header">
    <span class="mh-idx-label">${d.label}</span>
    <span class="mh-idx-chg ${cls1d}">${sign1d}${d.change_1d.toFixed(2)}%</span>
  </div>
  <div class="mh-idx-price">$${priceStr}</div>
  <div class="mh-idx-spark-wrap">${spark}</div>
  <div class="mh-idx-30d ${cls30d}">${sign30d}${d.change_30d.toFixed(2)}% 30日</div>
</div>`;
  }).join('');
}

// ── Sector cards ────────────────────────────────────────────────────────────

function _sectorCards(scores, maMap, prevScores, sectorHistory, etfSparklines = {}) {
  const sorted = Object.entries(scores).sort((a, b) => b[1] - a[1]);
  if (sorted.length === 0) return `<div class="gauge-label" style="padding:20px">セクターデータなし</div>`;

  return sorted.map(([sector, score]) => {
    const ma      = maMap[sector];
    const prev    = prevScores[sector];
    const history = sectorHistory ? sectorHistory[sector] : null;

    // Arrow
    let arrowHtml = "";
    if (prev !== undefined && prev !== null) {
      const delta = score - prev;
      if      (delta > 0.1)  arrowHtml = `<span class="mh-sarrow up">↑</span>`;
      else if (delta < -0.1) arrowHtml = `<span class="mh-sarrow dn">↓</span>`;
      else                   arrowHtml = `<span class="mh-sarrow flat">→</span>`;
    }

    // MA line
    const maHtml = ma !== undefined
      ? `<div class="mh-sma">MA ${ma.toFixed(1)}%</div>`
      : `<div class="mh-sma mh-sma--empty">MA --</div>`;

    // Status
    let statusHtml = "";
    let borderColor = "transparent";
    if (ma !== undefined) {
      const diff = score - ma;
      if (diff > 5) {
        statusHtml   = `<span class="mh-sstatus overbought">Overbought</span>`;
        borderColor  = "#f97316";
      } else if (diff < -3) {
        statusHtml   = `<span class="mh-sstatus oversold">Oversold</span>`;
        borderColor  = "#ef4444";
      } else {
        statusHtml   = `<span class="mh-sstatus normal">Normal</span>`;
      }
    }

    const scoreColor = score >= 50 ? "var(--green)"
                     : score >= 20 ? "var(--yellow)"
                     : "var(--red)";

    // Sparkline: prefer pipeline score history, fall back to ETF price history
    const sparkVals = history && history.length >= 2
      ? history.map(h => h.score)
      : (etfSparklines[sector] || null);
    const sparkHtml = sparkVals
      ? `<div class="mh-sspark">${_sparkline(sparkVals, 120, 48)}</div>`
      : `<div class="mh-sspark mh-sspark--empty" style="font-size:.65rem;color:var(--text-muted);padding:4px 0">スパークライン蓄積中</div>`;

    return `
<div class="mh-scard" style="--sc:${borderColor}">
  <div class="mh-sname">${sector}</div>
  <div class="mh-sscore-row">
    <span class="mh-sscore" style="color:${scoreColor}">${score.toFixed(1)}%</span>
    ${arrowHtml}
  </div>
  ${maHtml}
  ${statusHtml}
  ${sparkHtml}
</div>`;
  }).join("");
}

// ── Sentiment section (VIX + Fear & Greed) ─────────────────────────────────

function _buildSentimentSection(s) {
  return `
<div id="mh-sentiment-section">
  <div class="mh-sec-label">マーケットセンチメント</div>
  <div class="mh-sentiment-row">
    ${_vixCard(s.vix)}
    ${_fgCard(s.fear_greed)}
    ${_sentimentSummary(s.vix, s.fear_greed)}
  </div>
</div>`;
}

function _vixCard(vix) {
  if (!vix || vix.current == null) {
    return `<div class="mh-sent-card card"><div class="mh-sent-title">VIX（恐怖指数）</div><div class="mh-sent-na">取得失敗</div></div>`;
  }
  const cls    = vix.css || "neutral";
  const sign1d = vix.change_1d >= 0 ? "+" : "";
  const sign5d = vix.change_5d >= 0 ? "+" : "";
  const spark  = _sparkline(vix.history.map(h => h.value), 110, 36);

  const zones = [
    { label: "低水準（楽観）",    range: "< 15",  active: vix.current < 15 },
    { label: "通常",              range: "15〜20", active: vix.current >= 15 && vix.current < 20 },
    { label: "警戒ゾーン",        range: "20〜30", active: vix.current >= 20 && vix.current < 30 },
    { label: "恐怖ゾーン",        range: "≥ 30",  active: vix.current >= 30 },
  ];
  const zoneHtml = zones.map(z =>
    `<div class="mh-vix-zone${z.active ? " active" : ""}">
      <span class="mh-vix-zdot"></span>
      <span class="mh-vix-zlabel">${z.label}</span>
      <span class="mh-vix-zrange">${z.range}</span>
    </div>`
  ).join("");

  return `
<div class="mh-sent-card card">
  <div class="mh-sent-title">VIX（恐怖指数）</div>
  <div class="mh-vix-row">
    <div>
      <div class="mh-vix-val ${cls}">${vix.current.toFixed(2)}</div>
      <div class="mh-vix-label">${vix.label}</div>
      <div class="mh-vix-changes">
        <span class="${vix.change_1d >= 0 ? 'up' : 'dn'}">${sign1d}${vix.change_1d.toFixed(2)} 前日比</span>
        <span class="mh-cmp-sep">|</span>
        <span class="${vix.change_5d >= 0 ? 'up' : 'dn'}">${sign5d}${vix.change_5d.toFixed(2)} 5日比</span>
      </div>
    </div>
    <div class="mh-vix-spark-wrap">${spark}</div>
  </div>
  <div class="mh-vix-zones">${zoneHtml}</div>
</div>`;
}

function _fgCard(fg) {
  if (!fg || fg.score == null) {
    return `<div class="mh-sent-card card"><div class="mh-sent-title">Fear & Greed Index</div><div class="mh-sent-na">取得失敗</div></div>`;
  }
  const score   = fg.score;
  const rating  = fg.rating;
  const ratingJa = {
    "Extreme Fear": "極度の恐怖",
    "Fear":         "恐怖",
    "Neutral":      "中立",
    "Greed":        "強欲",
    "Extreme Greed":"極度の強欲",
  }[rating] || rating;

  const cls = score < 25 ? "extreme-fear"
            : score < 45 ? "fear"
            : score < 55 ? "neutral"
            : score < 75 ? "greed"
            :               "extreme-greed";

  // Arc gauge SVG (semicircle, 0=left, 100=right)
  const R   = 54;
  const cx  = 70, cy = 70;
  const startDeg = 180, endDeg = 0;
  const angle = startDeg - (score / 100) * 180;
  const rad   = angle * Math.PI / 180;
  const nx    = cx + R * Math.cos(rad);
  const ny    = cy - R * Math.sin(rad);
  const gaugeColors = ["#ef4444","#f97316","#eab308","#22c55e","#16a34a"];
  const segW  = 180 / 5;
  const arcSegs = gaugeColors.map((c, i) => {
    const a1 = (180 - i * segW) * Math.PI / 180;
    const a2 = (180 - (i + 1) * segW) * Math.PI / 180;
    const x1 = cx + R * Math.cos(a1), y1 = cy - R * Math.sin(a1);
    const x2 = cx + R * Math.cos(a2), y2 = cy - R * Math.sin(a2);
    return `<path d="M ${x1.toFixed(1)} ${y1.toFixed(1)} A ${R} ${R} 0 0 1 ${x2.toFixed(1)} ${y2.toFixed(1)}" fill="none" stroke="${c}" stroke-width="10" stroke-linecap="butt"/>`;
  }).join("");

  const spark = _sparkline(fg.history.map(h => h.value), 110, 36);

  return `
<div class="mh-sent-card card">
  <div class="mh-sent-title">Fear &amp; Greed Index <span style="font-size:.65rem;color:var(--text-muted)">CNN</span></div>
  <div class="mh-fg-row">
    <svg viewBox="0 0 140 80" class="mh-fg-gauge">
      ${arcSegs}
      <!-- Needle -->
      <line x1="${cx}" y1="${cy}" x2="${nx.toFixed(1)}" y2="${ny.toFixed(1)}"
            stroke="white" stroke-width="2" stroke-linecap="round"/>
      <circle cx="${cx}" cy="${cy}" r="4" fill="white"/>
      <!-- Score text -->
      <text x="${cx}" y="${cy + 18}" text-anchor="middle" fill="white"
            font-size="16" font-weight="bold">${score.toFixed(0)}</text>
    </svg>
    <div class="mh-fg-meta">
      <div class="mh-fg-rating ${cls}">${ratingJa}</div>
      <div class="mh-fg-rating-en">${rating}</div>
      <div class="mh-fg-spark-wrap">${spark}</div>
      <div style="font-size:.68rem;color:var(--text-muted);margin-top:4px">直近30日</div>
    </div>
  </div>
</div>`;
}

function _sentimentSummary(vix, fg) {
  const lines = [];
  if (vix && vix.current != null) {
    if (vix.current >= 30)      lines.push("⚠️ VIX≥30: 高ボラ環境。ポジションサイズ縮小推奨。");
    else if (vix.current >= 20) lines.push("⚡ VIX 20〜30: 警戒水準。新規エントリーは慎重に。");
    else if (vix.current < 15)  lines.push("😌 VIX<15: 市場は楽観ムード。過剰な強気に注意。");
    else                         lines.push("✅ VIX 15〜20: 通常水準。トレンドフォロー有効。");
  }
  if (fg && fg.score != null) {
    if (fg.score < 25)      lines.push("🔴 極度の恐怖: 底値圏の可能性。逆張り機会を探す局面。");
    else if (fg.score < 45) lines.push("🟠 恐怖: センチメント悪化中。ロングは高RR銘柄のみ。");
    else if (fg.score > 75) lines.push("🟢 極度の強欲: 相場過熱。利確・ストップ引き上げを検討。");
    else if (fg.score > 55) lines.push("🟡 強欲: モメンタム良好。週次ピックに積極参加可。");
    else                     lines.push("⚪ 中立: センチメントニュートラル。テクニカルに集中。");
  }
  if (!lines.length) return "";

  return `
<div class="mh-sent-card mh-sent-summary card">
  <div class="mh-sent-title">センチメント解釈</div>
  <ul class="mh-sent-list">
    ${lines.map(l => `<li>${l}</li>`).join("")}
  </ul>
</div>`;
}

// ── Sector ETF performance section ──────────────────────────────────────────

function _buildSectorETFSection(sectors) {
  const entries = Object.entries(sectors).sort((a, b) => b[1].change_ytd - a[1].change_ytd);
  if (!entries.length) return `<div id="mh-sector-etf-section"></div>`;

  const max1d = Math.max(...entries.map(([, v]) => Math.abs(v.change_1d)), 3);

  const rows = entries.map(([name, v]) => {
    const cls1d  = v.change_1d  >= 0 ? "econ-pos" : "econ-neg";
    const clsYtd = v.change_ytd >= 0 ? "econ-pos" : "econ-neg";
    const sign1d  = v.change_1d  >= 0 ? "+" : "";
    const signYtd = v.change_ytd >= 0 ? "+" : "";
    const barPct  = Math.min(Math.abs(v.change_1d) / max1d * 100, 100).toFixed(1);
    const barCls  = v.change_1d >= 0 ? "econ-bar-pos" : "econ-bar-neg";

    return `
      <div class="econ-sector-row">
        <div class="econ-sector-name">
          <span class="econ-sector-lbl">${_esc(name)}</span>
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
<div id="mh-sector-etf-section">
  <div class="mh-sec-label">セクターETF 騰落率（前日比 / 年初来）</div>
  <div class="econ-sector-list">${rows}</div>
</div>`;
}

function _esc(s) {
  return (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// ── Trend chart (lightweight-charts) ───────────────────────────────────────

function _renderChart(history, period, freq) {
  const el = document.getElementById("mh-chart-container");
  if (!el) return;

  if (_chart) { _chart.remove(); _chart = null; }

  // Filter to period
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - period);
  const cutoffStr = cutoff.toISOString().slice(0, 10);
  let pts = history.filter(h => h.date >= cutoffStr);
  if (pts.length === 0) pts = history;                 // fallback: show all

  // Weekly aggregation
  if (freq === "weekly") pts = _weeklyAggregate(pts);

  const rawScores = pts.map(h => h.score);
  const ma10      = _rollingMA(rawScores, 10);

  const chart = LightweightCharts.createChart(el, {
    width:  el.clientWidth,
    height: 260,
    layout: { background: { color: "#0f172a" }, textColor: "#94a3b8" },
    grid:   { vertLines: { color: "#1e293b" }, horzLines: { color: "#1e293b" } },
    rightPriceScale: { borderColor: "#334155" },
    timeScale: { borderColor: "#334155" },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
  });

  // Uptrend ratio line
  const uptrendLine = chart.addLineSeries({
    color: "#3b82f6", lineWidth: 2,
    lastValueVisible: true, priceLineVisible: false,
  });
  uptrendLine.setData(pts.map(h => ({ time: h.date, value: h.score })));

  // 10-day MA (dashed, yellow)
  const maLine = chart.addLineSeries({
    color: "#eab308", lineWidth: 1,
    lineStyle: LightweightCharts.LineStyle.Dashed,
    lastValueVisible: false, priceLineVisible: false,
  });
  maLine.setData(
    pts.map((h, i) => ({ time: h.date, value: ma10[i] }))
       .filter(d => d.value !== null)
  );

  // Zone threshold lines
  uptrendLine.createPriceLine({
    price: 65, color: "#22c55e", lineWidth: 1,
    lineStyle: LightweightCharts.LineStyle.Dashed,
    axisLabelVisible: true, title: "65%",
  });
  uptrendLine.createPriceLine({
    price: 35, color: "#f97316", lineWidth: 1,
    lineStyle: LightweightCharts.LineStyle.Dashed,
    axisLabelVisible: true, title: "35%",
  });

  chart.timeScale().fitContent();
  _chart = chart;

  // Responsive resize
  const ro = new ResizeObserver(() => {
    if (_chart) _chart.applyOptions({ width: el.clientWidth });
  });
  ro.observe(el);
}

function _updateChart() {
  if (_data && _allHistory.length > 0) {
    _renderChart(_allHistory, _period, _freq);
  }
}

// ── Event binding ───────────────────────────────────────────────────────────

function _bindControls(container) {
  container.querySelectorAll(".mh-period-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      container.querySelectorAll(".mh-period-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      _period = parseInt(btn.dataset.days);
      _updateChart();
    });
  });

  container.querySelectorAll(".mh-freq-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      container.querySelectorAll(".mh-freq-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      _freq = btn.dataset.freq;
      _updateChart();
    });
  });

  container.querySelector("#mh-refresh")?.addEventListener("click", () => {
    if (_chart) { _chart.remove(); _chart = null; }
    renderMarketHealth(container);
  });
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function _rollingMA(values, window) {
  return values.map((_, i) => {
    if (i < window - 1) return null;
    const slice = values.slice(i - window + 1, i + 1);
    return Math.round(slice.reduce((s, v) => s + v, 0) / window * 10) / 10;
  });
}

function _weeklyAggregate(data) {
  const map = new Map();
  for (const h of data) {
    const d    = new Date(h.date);
    const day  = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1);
    d.setDate(diff);
    const key = d.toISOString().slice(0, 10);
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(h.score);
  }
  return [...map.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([date, arr]) => ({
      date,
      score: Math.round(arr.reduce((s, v) => s + v, 0) / arr.length * 10) / 10,
    }));
}
