import { renderMarketHealth }     from "./components/market-health.js?v=5";
import { renderEvents }            from "./components/events.js?v=2";
import { renderPicksTable }        from "./components/picks-table.js?v=7";
import { renderTechPicksTable }    from "./components/tech-picks-table.js?v=1";
import { renderSearchUI }          from "./components/stock-search.js?v=2";
import { renderStrategyGuide }     from "./components/strategy-guide.js?v=3";
import { renderTechStrategyGuide } from "./components/tech-strategy-guide.js?v=1";
import { apiFetch }                from "./utils/api.js?v=2";

// ── Navigation config ─────────────────────────────────────────────────────
const SECTIONS = [
  { id: "market-health",    label: "市場ヘルス",             icon: "📊", load: loadMarketHealth },
  { id: "economic",         label: "経済指標",               icon: "📈", load: loadEconomic },
  { id: "news",             label: "ビッグニュース",         icon: "📰", load: loadNews },
  // ── ファンダ考慮 ──────────────────────────────────────────────────────
  { id: "weekly-picks",     label: "週次（ファンダ考慮）",   icon: "🎯", load: loadWeekly,     group: "funda" },
  { id: "daily-picks",      label: "日次（ファンダ考慮）",   icon: "⚡", load: loadDaily,      group: "funda" },
  // ── テクニカル重視 ────────────────────────────────────────────────────
  { id: "tech-weekly",      label: "週次（テクニカル重視）", icon: "📡", load: loadTechWeekly, group: "tech" },
  { id: "tech-daily",       label: "日次（テクニカル重視）", icon: "🔬", load: loadTechDaily,  group: "tech" },
  // ── ガイド ────────────────────────────────────────────────────────────
  { id: "strategy-guide",      label: "ロジック（ファンダ）",   icon: "📖", load: loadStrategyGuide,    group: "guide" },
  { id: "tech-strategy-guide", label: "ロジック（テクニカル）", icon: "🧪", load: loadTechStrategyGuide, group: "guide" },
  // ─────────────────────────────────────────────────────────────────────
  { id: "search",              label: "銘柄検索",               icon: "🔍", load: loadSearch },
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
      const groupLabel = s.group === "funda" ? "ファンダ考慮"
                       : s.group === "tech"  ? "テクニカル重視"
                       : "ロジック説明";
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
  await renderEvents(container, "/api/economic-indicators", "📈 経済指標");
}

async function loadNews(container) {
  await renderEvents(container, "/api/news", "📰 ビッグニュース");
}

async function loadWeekly(container) {
  container.innerHTML = `<div class="loading"><div class="spinner"></div><span>週次ピック取得中...</span></div>`;
  try {
    const picks = await apiFetch("/api/weekly-picks");
    renderPicksTable(container, picks, "🎯 今週のエントリー推奨銘柄", "weekly");
  } catch (e) {
    container.innerHTML = `<div class="empty-state">取得失敗: ${e.message}</div>`;
  }
}

async function loadDaily(container) {
  container.innerHTML = `<div class="loading"><div class="spinner"></div><span>本日の推奨取得中...</span></div>`;
  try {
    const picks = await apiFetch("/api/daily-picks");
    renderPicksTable(container, picks, "⚡ 本日のエントリー候補", "daily");
  } catch (e) {
    container.innerHTML = `<div class="empty-state">取得失敗: ${e.message}</div>`;
  }
}

async function loadTechWeekly(container) {
  container.innerHTML = `<div class="loading"><div class="spinner"></div><span>テクニカルスキャン取得中...</span></div>`;
  try {
    const picks = await apiFetch("/api/tech-weekly-picks");
    renderTechPicksTable(container, picks, "📡 週次テクニカルスキャン結果", "weekly");
  } catch (e) {
    container.innerHTML = `<div class="empty-state">取得失敗: ${e.message}</div>`;
  }
}

async function loadTechDaily(container) {
  container.innerHTML = `<div class="loading"><div class="spinner"></div><span>本日のテクニカル推奨取得中...</span></div>`;
  try {
    const picks = await apiFetch("/api/tech-daily-picks");
    renderTechPicksTable(container, picks, "🔬 本日のテクニカルエントリー候補", "daily");
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
