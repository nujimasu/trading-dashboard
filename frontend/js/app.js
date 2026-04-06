import { renderMarketHealth }       from "./components/market-health.js?v=7";
import { renderEconomicDashboard }  from "./components/economic-dashboard.js?v=2";
import { renderPicksTable }         from "./components/picks-table.js?v=10";
import { renderTechPicksTable }    from "./components/tech-picks-table.js?v=3";
import { renderSearchUI }          from "./components/stock-search.js?v=2";
import { renderStrategyGuide }     from "./components/strategy-guide.js?v=3";
import { renderTechStrategyGuide }  from "./components/tech-strategy-guide.js?v=2";
import { apiFetch }                from "./utils/api.js?v=2";

// ── Navigation config ─────────────────────────────────────────────────────
const SECTIONS = [
  { id: "market-health", label: "市場ヘルス", icon: "📊", load: loadMarketHealth },
  { id: "economic",      label: "経済指標",   icon: "📈", load: loadEconomic },
  // ── リスト ───────────────────────────────────────────────────────────────
  { id: "logic1", label: "ロジック１（ファンダ考慮）", icon: "🎯", load: loadLogic1, group: "list" },
  { id: "logic2", label: "ロジック２",                 icon: "🔬", load: loadLogic2, group: "list" },
  { id: "logic3", label: "ロジック３",                 icon: "⚡", load: loadLogic3, group: "list" },
  // ── ロジック説明 ──────────────────────────────────────────────────────────
  { id: "strategy-guide",      label: "ロジック１の説明", icon: "📖", load: loadStrategyGuide,    group: "guide" },
  { id: "tech-strategy-guide", label: "ロジック２の説明", icon: "🧪", load: loadTechStrategyGuide, group: "guide" },
  // ─────────────────────────────────────────────────────────────────────────
  { id: "search", label: "銘柄検索", icon: "🔍", load: loadSearch },
];

let currentSection = null;

// ── Bootstrap ─────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  buildSidebar();
  buildSections();
  loadPipelineStatus();
  navigate("market-health");

  // ── ハンバーガーメニュー ───────────────────────────────────────────────
  const toggle  = document.getElementById("menu-toggle");
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("sidebar-overlay");

  function openMenu()  { sidebar.classList.add("open");  overlay.classList.add("visible"); }
  function closeMenu() { sidebar.classList.remove("open"); overlay.classList.remove("visible"); }

  toggle.addEventListener("click", () =>
    sidebar.classList.contains("open") ? closeMenu() : openMenu()
  );
  overlay.addEventListener("click", closeMenu);
});

function buildSidebar() {
  const sidebar = document.getElementById("sidebar");
  let html = "";
  let lastGroup = null;
  SECTIONS.forEach(s => {
    if (s.group && s.group !== lastGroup) {
      const groupLabel = s.group === "list" ? "リスト" : "ロジック説明";
      html += `<div class="nav-group-label">${groupLabel}</div>`;
      lastGroup = s.group;
    } else if (!s.group && lastGroup) {
      html += `<div class="nav-separator"></div>`;
      lastGroup = null;
    }
    html += `
      <div class="nav-item${s.group ? ` nav-item--${s.group}` : ""}" data-section="${s.id}">
        <span class="icon">${s.icon}</span>
        <span>${s.label}</span>
      </div>`;
  });
  sidebar.innerHTML = html;
  sidebar.querySelectorAll(".nav-item").forEach(el => {
    el.addEventListener("click", () => {
      navigate(el.dataset.section);
      // モバイルではメニューを閉じる
      sidebar.classList.remove("open");
      document.getElementById("sidebar-overlay").classList.remove("visible");
    });
  });
}

function buildSections() {
  const main = document.getElementById("main");
  main.innerHTML = SECTIONS.map(s =>
    `<div class="section" id="sec-${s.id}"></div>`
  ).join("");
}

function navigate(id) {
  if (currentSection === id) return;
  currentSection = id;

  // Update nav
  document.querySelectorAll(".nav-item").forEach(el => {
    el.classList.toggle("active", el.dataset.section === id);
  });

  // Show/hide sections
  document.querySelectorAll(".section").forEach(el => {
    el.classList.toggle("active", el.id === `sec-${id}`);
  });

  // Load content
  const section = SECTIONS.find(s => s.id === id);
  if (section) {
    const container = document.getElementById(`sec-${id}`);
    section.load(container);
  }
}

// ── Section loaders ───────────────────────────────────────────────────────
async function loadMarketHealth(container) {
  await renderMarketHealth(container);
}

async function loadEconomic(container) {
  await renderEconomicDashboard(container);
}

// ロジック１（ファンダ考慮）: 旧ハイブリッドエントリー
async function loadLogic1(container) {
  container.innerHTML = `<div class="loading"><div class="spinner"></div><span>候補取得中...</span></div>`;
  try {
    const [weekly, daily] = await Promise.all([
      apiFetch("/api/weekly-picks"),
      apiFetch("/api/daily-picks"),
    ]);
    const merged = _mergeWeeklyDaily(weekly, daily);
    const entries = merged.filter(p => p.daily_verdict !== "PASSED" && p.direction !== "SHORT");
    renderPicksTable(container, entries, "🎯 ロジック１（ファンダ考慮）", "hybrid-entry");
  } catch (e) {
    container.innerHTML = `<div class="empty-state">取得失敗: ${e.message}</div>`;
  }
}

function _mergeWeeklyDaily(weekly, daily) {
  const map = {};
  weekly.forEach(w => { map[w.ticker] = { ...w }; });
  daily.forEach(d => {
    if (map[d.ticker]) {
      const score = map[d.ticker].composite_score;
      map[d.ticker] = { ...map[d.ticker], ...d, composite_score: score };
    } else {
      map[d.ticker] = { ...d };
    }
  });
  return Object.values(map).sort((a, b) => (b.composite_score || 0) - (a.composite_score || 0));
}

// ロジック３: signal-scanner-v5 エンジン（28シグナル, 勝率65%+, 信頼度70%+）
async function loadLogic3(container) {
  container.innerHTML = `<div class="loading"><div class="spinner"></div><span>候補取得中...</span></div>`;
  try {
    const picks = await apiFetch("/api/logic3-picks");
    renderTechPicksTable(container, picks, "⚡ ロジック３", "daily");
  } catch (e) {
    container.innerHTML = `<div class="empty-state">取得失敗: ${e.message}</div>`;
  }
}

// ロジック２: 旧日次（テクニカル重視）
async function loadLogic2(container) {
  container.innerHTML = `<div class="loading"><div class="spinner"></div><span>候補取得中...</span></div>`;
  try {
    const picks = await apiFetch("/api/tech-daily-picks");
    renderTechPicksTable(container, picks, "🔬 ロジック２", "daily");
  } catch (e) {
    container.innerHTML = `<div class="empty-state">取得失敗: ${e.message}</div>`;
  }
}

function loadStrategyGuide(container) {
  renderStrategyGuide(container);
}

function loadTechStrategyGuide(container) {
  renderTechStrategyGuide(container);
}

function loadSearch(container) {
  renderSearchUI(container);
}

// ── Pipeline status (header) ──────────────────────────────────────────────
async function loadPipelineStatus() {
  try {
    const status = await apiFetch("/api/pipeline/status");
    const el     = document.getElementById("pipeline-status");
    const mh     = status.market_health;
    const signal = mh ? mh.overall_signal : "No Data";
    const picks  = status.weekly_picks_count;
    const tickers = status.price_data_tickers;

    el.innerHTML = `
      市場: <span>${signal}</span> &nbsp;|&nbsp;
      週次ピック: <span>${picks}</span> &nbsp;|&nbsp;
      価格DB: <span>${tickers}</span> 銘柄`;
  } catch (e) {
    // silently ignore
  }
}
