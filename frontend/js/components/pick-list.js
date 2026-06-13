/**
 * 統一 Pick リスト — 全ロジックで共通のカードレイアウトを提供する。
 *
 * 既存の picks-table.js / tech-picks-table.js から詳細パネルだけ再利用。
 * サマリービュー (カード) は本ファイルで一元化。
 */
import {
  buildDetailPanel as buildFundaDetailPanel,
  _getMarketHealth,
} from "./picks-table.js?v=12";
import {
  _buildDetailPanel as buildTechDetailPanel,
  _buildDetailPanelLogic4,
} from "./tech-picks-table.js?v=8";
import { renderCandlestick } from "../utils/charts.js?v=3";
import { apiFetch } from "../utils/api.js";
import {
  normalizePick,
  holdingBucket,
  confidenceTier,
  verdictMeta,
} from "../utils/pick-normalizer.js?v=2";

const FUNDA_MODES = new Set(["weekly", "daily", "take-profit", "hybrid-entry"]);
const TECH_MODES = new Set(["logic2", "logic4"]);

export function renderPickList(container, picks, title, mode = "weekly") {
  if (!picks.length) {
    container.innerHTML = `
      <div class="section-title">${title}</div>
      <div class="empty-state">${_emptyMessage(mode)}</div>`;
    return;
  }

  const normalized = picks.map(p => normalizePick(p, mode));
  // ソート/フィルタ用のセクター候補（重複除去）
  const sectors = Array.from(new Set(normalized.map(n => n.sector).filter(Boolean))).sort();

  const state = {
    search: "",
    sort:   "confidence-desc",
    direction: "all",
    sector: "all",
  };

  container.innerHTML = `
    <div class="section-title">${title}
      <span class="tech-count-badge" id="pl-count">${picks.length}件</span>
    </div>
    <div class="pick-controls">
      <input type="search" class="pick-search" placeholder="銘柄/セクター検索..." />
      <select class="pick-sort">
        <option value="confidence-desc">信頼度↓</option>
        <option value="confidence-asc">信頼度↑</option>
        <option value="rr-desc">RR↓</option>
        <option value="ticker-asc">銘柄名↑</option>
      </select>
      <select class="pick-filter-direction">
        <option value="all">全方向</option>
        <option value="LONG">▲ LONG</option>
        <option value="SHORT">▼ SHORT</option>
      </select>
      <select class="pick-filter-sector">
        <option value="all">全セクター</option>
        ${sectors.map(s => `<option value="${_attr(s)}">${_esc(s)}</option>`).join("")}
      </select>
    </div>
    <div class="pick-list" id="pl-list"></div>`;

  const listEl  = container.querySelector("#pl-list");
  const countEl = container.querySelector("#pl-count");
  const searchEl = container.querySelector(".pick-search");
  const sortEl   = container.querySelector(".pick-sort");
  const dirEl    = container.querySelector(".pick-filter-direction");
  const sectorEl = container.querySelector(".pick-filter-sector");

  function rerender() {
    let view = normalized.slice();

    // 検索
    const q = state.search.trim().toLowerCase();
    if (q) {
      view = view.filter(n =>
        (n.ticker || "").toLowerCase().includes(q) ||
        (n.sector || "").toLowerCase().includes(q));
    }
    // 方向
    if (state.direction !== "all") {
      view = view.filter(n => n.direction === state.direction);
    }
    // セクター
    if (state.sector !== "all") {
      view = view.filter(n => n.sector === state.sector);
    }
    // ソート
    const sorters = {
      "confidence-desc": (a, b) => (b.confidence || 0) - (a.confidence || 0),
      "confidence-asc":  (a, b) => (a.confidence || 0) - (b.confidence || 0),
      "rr-desc":         (a, b) => (b.rr || 0) - (a.rr || 0),
      "ticker-asc":      (a, b) => (a.ticker || "").localeCompare(b.ticker || ""),
    };
    view.sort(sorters[state.sort] || sorters["confidence-desc"]);

    countEl.textContent = `${view.length}件 / ${picks.length}件`;
    if (view.length === 0) {
      listEl.innerHTML = `<div class="empty-state">条件に合う銘柄がありません</div>`;
      return;
    }

    // インデックスは「正規化前の picks」配列での位置に合わせる
    const idxMap = view.map(n => normalized.indexOf(n));
    listEl.innerHTML = view.map((n, viewIdx) => _renderCard(n, idxMap[viewIdx])).join("");
    _bindCardClicks(container, picks, mode);
  }

  searchEl.addEventListener("input", () => { state.search = searchEl.value; rerender(); });
  sortEl  .addEventListener("change", () => { state.sort = sortEl.value;     rerender(); });
  dirEl   .addEventListener("change", () => { state.direction = dirEl.value; rerender(); });
  sectorEl.addEventListener("change", () => { state.sector = sectorEl.value; rerender(); });

  rerender();
}

function _bindCardClicks(container, picks, mode) {
  container.querySelectorAll(".pick-card").forEach(card => {
    card.addEventListener("click", (e) => {
      if (e.target.closest(".pick-detail")) return;
      const idx = +card.dataset.idx;
      _toggleDetail(container, card, idx, picks[idx], mode);
    });
  });
}

function _attr(s) { return _esc(s).replace(/"/g, "&quot;"); }

// ── サマリーカードを描画 ─────────────────────────────────────────
function _renderCard(n, idx) {
  const dirCss   = n.direction === "SHORT" ? "dir-short" : "dir-long";
  const dirText  = n.direction === "SHORT" ? "▼SHORT"   : "▲LONG";
  const confTier = confidenceTier(n.confidence);
  const hold     = holdingBucket(n.holdingDays);
  const vMeta    = verdictMeta(n.verdict);

  const tagsHtml = n.primarySignals.map(s =>
    `<span class="sig-tag">${_esc(s)}</span>`
  ).join("");

  const verdictHtml = vMeta
    ? `<span class="pick-verdict ${vMeta.css}">${vMeta.label}</span>`
    : "";

  const rrHtml = n.rr != null
    ? `<span class="pick-meta-item">RR <strong>${Number(n.rr).toFixed(2)}</strong></span>`
    : "";

  const sectorHtml = n.sector
    ? `<span class="pick-meta-item pick-meta-sector">${_esc(n.sector)}</span>`
    : "";

  const holdHtml = `<span class="pick-meta-item hold-badge ${hold.css}">${hold.label}</span>`;
  const growthHtml = n.growthMetrics.length
    ? `<div class="pick-card-signals pick-growth-metrics">${n.growthMetrics.map(m => `<span class="sig-tag">${_esc(m)}</span>`).join("")}</div>`
    : "";

  return `
    <div class="pick-card" data-idx="${idx}">
      <div class="pick-card-main">
        <div class="pick-card-head">
          <span class="pick-ticker">${_esc(n.ticker)}</span>
          <span class="dir-badge ${dirCss}">${dirText}</span>
          ${verdictHtml}
        </div>
        <div class="pick-card-conf">
          <div class="pick-conf-bar-wrap">
            <div class="pick-conf-bar ${confTier.css}" style="width:${n.confidence.toFixed(0)}%"></div>
          </div>
          <span class="pick-conf-pct">${n.confidence.toFixed(0)}%</span>
        </div>
      </div>
      <div class="pick-card-meta">
        ${holdHtml}
        ${rrHtml}
        ${sectorHtml}
        ${n.zoneFlag ? `<span class="pick-meta-item">${_esc(n.zoneFlag)}</span>` : ""}
      </div>
      ${tagsHtml ? `<div class="pick-card-signals">${tagsHtml}</div>` : ""}
      ${growthHtml}
    </div>`;
}

// ── 詳細パネル開閉 ─────────────────────────────────────────────────
function _toggleDetail(container, card, idx, rawPick, mode) {
  const existing = card.nextElementSibling;
  const isDetailOpen = existing && existing.classList.contains("pick-detail");

  // 既に開いている全パネルを閉じる
  container.querySelectorAll(".pick-detail").forEach(el => el.remove());
  container.querySelectorAll(".pick-card.expanded").forEach(el => el.classList.remove("expanded"));

  if (isDetailOpen) return; // 同じカードをクリックした場合は閉じるだけ

  // 新規で詳細を挿入
  const detailHtml = _buildDetail(rawPick, idx, mode);
  card.classList.add("expanded");
  card.insertAdjacentHTML("afterend",
    `<div class="pick-detail" data-idx="${idx}">${detailHtml}</div>`);

  // detail-block の h4 をアコーディオン化
  const detailEl = card.nextElementSibling;
  detailEl.querySelectorAll(".detail-block h4").forEach(h => {
    h.addEventListener("click", (ev) => {
      ev.stopPropagation();
      h.parentElement.classList.toggle("collapsed");
    });
  });

  // セクター動向の「読み込み中…」を 8 秒でフォールバック表示に
  setTimeout(() => {
    detailEl.querySelectorAll('[id^="sector-slot-"], [id^="tsector-slot-"]').forEach(slot => {
      const txt = slot.textContent || "";
      if (txt.includes("読み込み中")) {
        slot.innerHTML = `<div class="sector-loading-failed">— セクターデータ未取得</div>`;
      }
    });
  }, 8000);

  _hydrateDetail(container, idx, rawPick, mode);
}

function _buildDetail(p, idx, mode) {
  if (FUNDA_MODES.has(mode)) {
    return buildFundaDetailPanel(p, idx, mode);
  }
  if (mode === "logic2" || mode === "logic4") {
    return _buildDetailPanelLogic4(p, idx);
  }
  return buildTechDetailPanel(p, idx);
}

// ── 詳細パネル内のチャート / セクター動向を非同期で埋める ─────────────
function _hydrateDetail(container, idx, p, mode) {
  // チャートID は picks-table 系: chart-${idx} / tech-picks-table 系: ?
  // 既存実装に合わせて両方試す
  const chartCandidates = [`chart-${idx}`, `tchart-${idx}`];

  apiFetch(`/api/chart/${p.ticker}?days=180`).then(chartResp => {
    if (!chartResp || !chartResp.data || chartResp.data.length === 0) return;
    const patternData = (p.base_pattern && p.pivot_price) ? {
      pivot:          p.pivot_price,
      base_low:       p.stop_price,
      base_length:    p.base_length || 30,
      base_pattern:   p.base_pattern,
      base_depth_pct: p.base_depth_pct,
      breakout_confirmed: p.breakout_confirmed,
      breakout_volume_ratio: p.breakout_volume_ratio,
    } : null;
    for (const id of chartCandidates) {
      if (document.getElementById(id)) {
        renderCandlestick(id, chartResp.data, {
          entry:  p.entry_price,
          stop:   p.stop_price,
          tp1:    p.tp1_price,
          target: p.target_price,
        }, patternData);
        break;
      }
    }
  }).catch(() => {});

  // Funda 系のみ: セクター動向を後挿し
  if (FUNDA_MODES.has(mode)) {
    const slot = document.getElementById(`sector-slot-${idx}`);
    if (!slot) return;
    _getMarketHealth().then(mh => {
      const sectorName = (p.fundamental_summary?.sector) || p.sector;
      if (!sectorName || !mh.sector_scores) return;
      const score   = mh.sector_scores[sectorName];
      const history = mh.sector_history?.[sectorName] || [];
      const ma      = mh.sector_ma?.[sectorName];
      if (score == null) return;
      const color = score >= 50 ? "var(--green)" : score >= 20 ? "var(--yellow)" : "var(--red)";
      const spark = _sectorSparkline(history.map(h => h.score));
      const maDiff = ma != null ? (score - ma).toFixed(1) : null;
      const maHtml = maDiff != null
        ? `<span style="color:${parseFloat(maDiff) >= 0 ? 'var(--green)' : 'var(--red)'}">MA比 ${parseFloat(maDiff) >= 0 ? "+" : ""}${maDiff}pp</span>`
        : "";
      slot.innerHTML = `
        <div class="kv-row">
          <span class="kv-key">アップトレンド比率</span>
          <span class="kv-val" style="color:${color}">${score.toFixed(1)}%</span>
        </div>
        ${maDiff != null ? `<div class="kv-row"><span class="kv-key">20日MA比</span><span class="kv-val">${maHtml}</span></div>` : ""}
        ${spark ? `<div style="margin-top:6px">${spark}</div>` : ""}`;
    });
  }
}

function _sectorSparkline(values, w = 120, h = 40) {
  if (!values || values.length < 2) return "";
  const min = Math.min(...values), max = Math.max(...values);
  const range = max - min || 1;
  const pts = values.map((v, i) => {
    const x = ((i / (values.length - 1)) * (w - 6) + 3).toFixed(1);
    const y = (h - 4 - ((v - min) / range) * (h - 8) + 2).toFixed(1);
    return `${x},${y}`;
  }).join(" ");
  const rising = values[values.length - 1] >= values[0];
  const color  = rising ? "#22c55e" : "#ef4444";
  return `<svg viewBox="0 0 ${w} ${h}" style="width:100%;height:${h}px;display:block" preserveAspectRatio="none">
    <polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/>
  </svg>`;
}

function _emptyMessage(mode) {
  if (mode === "take-profit") return "利確シグナルなし — 全銘柄「継続保有」の判定です。";
  if (mode === "daily" || mode === "hybrid-entry")
    return "本日の候補なし — 毎朝7:00に自動更新されます";
  if (TECH_MODES.has(mode)) return "本日の候補なし — 毎朝7:00に自動更新されます";
  return "候補銘柄なし — パイプラインを実行してください。";
}

function _esc(s) { return String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
