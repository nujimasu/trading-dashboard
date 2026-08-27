import { renderSwingScreener } from "./components/swing-screener.js?v=1";
import { renderMarketHealth } from "./components/market-health.js?v=7";
import { renderEconomicDashboard } from "./components/economic-dashboard.js?v=2";
import { renderSearchUI } from "./components/stock-search.js?v=2";
import { renderLogicGuide } from "./components/logic-guide.js?v=1";
import { renderAiSectorMap } from "./components/ai-sector-map.js?v=3";
import { renderAiNews } from "./components/ai-news.js?v=2";
import { apiFetch } from "./utils/api.js?v=3";

const SECTIONS = [
  { id: "swing", label: "押し目スクリーナー", icon: "🎯", load: loadSwing },
  { id: "ai-map", label: "AIセクターマップ", icon: "🤖", load: loadAiSectorMap },
  { id: "ai-news", label: "AIニュース", icon: "📰", load: loadAiNews },
  { id: "market-health", label: "市場ヘルス", icon: "📊", load: loadMarketHealth },
  { id: "economic", label: "経済指標", icon: "📈", load: loadEconomic },
  { id: "search", label: "銘柄検索", icon: "🔍", load: loadSearch },
  { id: "logic-guide", label: "ロジック解説", icon: "📖", load: loadLogicGuide },
];

let currentSection = null;

document.addEventListener("DOMContentLoaded", () => {
  buildSidebar();
  buildSections();
  loadPipelineStatus();
  navigate("swing");

  const toggle = document.getElementById("menu-toggle");
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("sidebar-overlay");

  function openMenu() {
    sidebar.classList.add("open");
    overlay.classList.add("visible");
  }

  function closeMenu() {
    sidebar.classList.remove("open");
    overlay.classList.remove("visible");
  }

  toggle.addEventListener("click", () =>
    sidebar.classList.contains("open") ? closeMenu() : openMenu()
  );
  overlay.addEventListener("click", closeMenu);
});

function buildSidebar() {
  const sidebar = document.getElementById("sidebar");
  sidebar.innerHTML = SECTIONS.map(section => `
    <div class="nav-item" data-section="${section.id}">
      <span class="icon">${section.icon}</span>
      <span>${section.label}</span>
    </div>
  `).join("");

  sidebar.querySelectorAll(".nav-item").forEach(element => {
    element.addEventListener("click", () => {
      navigate(element.dataset.section);
      sidebar.classList.remove("open");
      document.getElementById("sidebar-overlay").classList.remove("visible");
    });
  });
}

function buildSections() {
  const main = document.getElementById("main");
  main.innerHTML = SECTIONS.map(section =>
    `<div class="section" id="sec-${section.id}"></div>`
  ).join("");
}

function navigate(id) {
  if (currentSection === id) return;
  currentSection = id;

  document.querySelectorAll(".nav-item").forEach(element => {
    element.classList.toggle("active", element.dataset.section === id);
  });
  document.querySelectorAll(".section").forEach(element => {
    element.classList.toggle("active", element.id === `sec-${id}`);
  });

  const section = SECTIONS.find(item => item.id === id);
  if (section) {
    section.load(document.getElementById(`sec-${id}`));
  }
}

async function loadSwing(container) {
  await renderSwingScreener(container);
}

async function loadAiSectorMap(container) {
  await renderAiSectorMap(container);
}

async function loadAiNews(container) {
  await renderAiNews(container);
}

async function loadMarketHealth(container) {
  await renderMarketHealth(container);
}

async function loadEconomic(container) {
  await renderEconomicDashboard(container);
}

function loadSearch(container) {
  renderSearchUI(container);
}

function loadLogicGuide(container) {
  renderLogicGuide(container);
}

async function loadPipelineStatus() {
  await Promise.all([
    (async () => {
      try {
        const marketHealth = await apiFetch("/api/market-health");
        _setMarketBadge(marketHealth.overall_signal || "No Data");
      } catch {
        _setMarketBadge("No Data");
      }
    })(),
    (async () => {
      try {
        const swingPicks = await apiFetch("/api/swing/picks");
        const picksStat = document.getElementById("hs-picks");
        if (picksStat) picksStat.textContent = swingPicks.picks.length;
      } catch {
        // Keep the placeholder when swing picks are unavailable.
      }
    })(),
    (async () => {
      try {
        const pipelineStatus = await apiFetch("/api/pipeline/status");
        const tickersStat = document.getElementById("hs-tickers");
        if (tickersStat) tickersStat.textContent = pipelineStatus.price_data_tickers;
      } catch {
        // Keep the placeholder when pipeline status is unavailable.
      }
    })(),
  ]);
}

function _setMarketBadge(signal) {
  const badge = document.getElementById("market-badge");
  if (!badge) return;

  const normalized = String(signal || "").toLowerCase();
  let cssClass;
  let icon;
  let label;
  if (normalized.includes("bull")) {
    cssClass = "market-bullish"; icon = "✓"; label = "Bullish";
  } else if (normalized.includes("bear")) {
    cssClass = "market-bearish"; icon = "⚠"; label = "Bearish";
  } else if (normalized.includes("neutral")) {
    cssClass = "market-neutral"; icon = "—"; label = "Neutral";
  } else {
    cssClass = "market-no-data"; icon = "?"; label = "No Data";
  }

  badge.className = `market-badge ${cssClass}`;
  badge.innerHTML = `<span class="market-icon">${icon}</span><span class="market-label">${label}</span>`;
}
