import { renderMarketHealth }       from "./components/market-health.js?v=7";
import { renderEconomicDashboard }  from "./components/economic-dashboard.js?v=2";
import { renderPickList }          from "./components/pick-list.js?v=3";
import { renderSearchUI }          from "./components/stock-search.js?v=2";
import { renderStrategyGuide }        from "./components/strategy-guide.js?v=4";
import { renderLogic2StrategyGuide }  from "./components/logic2-strategy-guide.js?v=3";
import { renderLogic4StrategyGuide }  from "./components/logic4-strategy-guide.js?v=2";
import { renderLogicCompare }         from "./components/logic-compare.js?v=2";
import { renderBacktest }          from "./components/backtest.js?v=3";
import { renderPositions }         from "./components/positions.js?v=2";
import { renderTradeAnalytics }    from "./components/trade-analytics.js?v=9";
import { apiFetch }                from "./utils/api.js?v=3";

// ── Navigation config ─────────────────────────────────────────────────────
const SECTIONS = [
  { id: "market-health", label: "市場ヘルス", icon: "📊", load: loadMarketHealth },
  { id: "economic",      label: "経済指標",   icon: "📈", load: loadEconomic },
  { id: "logic1",        label: "ファンダ重視", icon: "🎯", load: loadLogic1 },
  { id: "logic2",        label: "厳選押し目買いv1", icon: "🔥", load: loadLogic2 },
  { id: "logic4",        label: "厳選押し目買いv2", icon: "💎", load: loadLogic4 },
  { id: "logic-compare", label: "v1 vs v2 比較", icon: "⚖️", load: loadLogicCompare },
  { id: "positions",     label: "保有ポジション", icon: "💼", load: loadPositions },
  { id: "trade-analytics", label: "取引分析", icon: "📈", load: loadTradeAnalytics },
  { id: "backtest",      label: "戦績", icon: "📊", load: loadBacktest },
  { id: "search",        label: "銘柄検索", icon: "🔍", load: loadSearch },
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
  sidebar.innerHTML = SECTIONS.map(s => `
    <div class="nav-item" data-section="${s.id}">
      <span class="icon">${s.icon}</span>
      <span>${s.label}</span>
    </div>
  `).join("");
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

// ── Tabbed section helper ─────────────────────────────────────────────────
// 各ロジック画面の中で「候補リスト / 説明」をタブ切替するためのヘルパー。
// tabs: [{ id, label, icon?, render: (el) => void | Promise<void> }]
function renderTabbedSection(container, tabs, defaultTabId) {
  const initialId = defaultTabId || tabs[0].id;

  const tabsHtml = tabs.map(t => `
    <button class="section-tab${t.id === initialId ? " active" : ""}" data-tab="${t.id}" type="button" role="tab" aria-selected="${t.id === initialId}">
      ${t.icon ? `<span class="section-tab-icon">${t.icon}</span>` : ""}
      <span>${t.label}</span>
    </button>
  `).join("");

  const contentsHtml = tabs.map(t => `
    <div class="section-tab-content${t.id === initialId ? " active" : ""}" data-tab-content="${t.id}" role="tabpanel"></div>
  `).join("");

  container.innerHTML = `
    <div class="section-tabs" role="tablist">${tabsHtml}</div>
    ${contentsHtml}
  `;

  const rendered = new Set();

  function activate(id) {
    container.querySelectorAll(".section-tab").forEach(b => {
      const isActive = b.dataset.tab === id;
      b.classList.toggle("active", isActive);
      b.setAttribute("aria-selected", isActive);
    });
    container.querySelectorAll(".section-tab-content").forEach(c =>
      c.classList.toggle("active", c.dataset.tabContent === id)
    );
    if (!rendered.has(id)) {
      const tab = tabs.find(t => t.id === id);
      const el = container.querySelector(`[data-tab-content="${id}"]`);
      tab.render(el);
      rendered.add(id);
    }
  }

  container.querySelectorAll(".section-tab").forEach(btn => {
    btn.addEventListener("click", () => activate(btn.dataset.tab));
  });

  activate(initialId);
}

// ── Section loaders ───────────────────────────────────────────────────────
async function loadMarketHealth(container) {
  await renderMarketHealth(container);
}

async function loadEconomic(container) {
  await renderEconomicDashboard(container);
}

// ファンダ重視: 候補 + 説明をタブ切替
function loadLogic1(container) {
  renderTabbedSection(container, [
    {
      id: "picks", label: "候補リスト", icon: "📋",
      render: async (el) => {
        el.innerHTML = `<div class="loading"><div class="spinner"></div><span>候補取得中...</span></div>`;
        try {
          const [weekly, daily] = await Promise.all([
            apiFetch("/api/weekly-picks"),
            apiFetch("/api/daily-picks"),
          ]);
          const merged = _mergeWeeklyDaily(weekly, daily);
          const entries = merged.filter(p => p.daily_verdict !== "PASSED" && p.direction !== "SHORT");
          renderPickList(el, entries, "🎯 ファンダ重視（グロース）", "hybrid-entry");
        } catch (e) {
          el.innerHTML = `<div class="empty-state">取得失敗: ${e.message}</div>`;
        }
      },
    },
    {
      id: "guide", label: "説明", icon: "📖",
      render: (el) => renderStrategyGuide(el),
    },
  ]);
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

// 厳選押し目買いv1
function loadLogic2(container) {
  renderTabbedSection(container, [
    {
      id: "picks", label: "候補リスト", icon: "📋",
      render: async (el) => {
        el.innerHTML = `<div class="loading"><div class="spinner"></div><span>候補取得中...</span></div>`;
        try {
          const picks = await apiFetch("/api/logic2-picks");
          renderPickList(el, picks, "🔥 厳選押し目買いv1", "logic2");
        } catch (e) {
          el.innerHTML = `<div class="empty-state">取得失敗: ${e.message}</div>`;
        }
      },
    },
    {
      id: "guide", label: "説明", icon: "🔥",
      render: (el) => renderLogic2StrategyGuide(el),
    },
  ]);
}

// 厳選押し目買いv2
function loadLogic4(container) {
  renderTabbedSection(container, [
    {
      id: "picks", label: "候補リスト", icon: "📋",
      render: async (el) => {
        el.innerHTML = `<div class="loading"><div class="spinner"></div><span>候補取得中...</span></div>`;
        try {
          const picks = await apiFetch("/api/logic4-picks");
          renderPickList(el, picks, "💎 厳選押し目買いv2", "logic4");
        } catch (e) {
          el.innerHTML = `<div class="empty-state">取得失敗: ${e.message}</div>`;
        }
      },
    },
    {
      id: "guide", label: "説明", icon: "💎",
      render: (el) => renderLogic4StrategyGuide(el),
    },
  ]);
}

function loadLogicCompare(container) {
  renderLogicCompare(container);
}

function loadSearch(container) {
  renderSearchUI(container);
}

async function loadBacktest(container) {
  await renderBacktest(container);
}

async function loadPositions(container) {
  await renderPositions(container);
}

async function loadTradeAnalytics(container) {
  await renderTradeAnalytics(container);
}

// ── Pipeline status (header) ──────────────────────────────────────────────
async function loadPipelineStatus() {
  try {
    const status = await apiFetch("/api/pipeline/status");
    const mh     = status.market_health;
    const signal = mh ? mh.overall_signal : "No Data";

    _setMarketBadge(signal);

    const picksEl   = document.getElementById("hs-picks");
    const tickersEl = document.getElementById("hs-tickers");
    if (picksEl)   picksEl.textContent   = status.weekly_picks_count ?? "—";
    if (tickersEl) tickersEl.textContent = status.price_data_tickers ?? "—";
  } catch {
    _setMarketBadge("No Data");
  }
}

function _setMarketBadge(signal) {
  const badge = document.getElementById("market-badge");
  if (!badge) return;

  const norm = String(signal || "").toLowerCase();
  let cls, icon, label;
  if (norm.includes("bull"))      { cls = "market-bullish"; icon = "✓"; label = "Bullish"; }
  else if (norm.includes("bear")) { cls = "market-bearish"; icon = "⚠"; label = "Bearish"; }
  else if (norm.includes("neutral")) { cls = "market-neutral"; icon = "—"; label = "Neutral"; }
  else                            { cls = "market-no-data"; icon = "?"; label = "No Data"; }

  badge.className = "market-badge " + cls;
  badge.innerHTML = `<span class="market-icon">${icon}</span><span class="market-label">${label}</span>`;
}
