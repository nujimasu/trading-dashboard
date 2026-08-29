import { apiFetch } from "../utils/api.js?v=3";

const MARKET_KEY = "ai-profiles-market-v1";
const MARKET_ORDER = ["us", "jp"];
const MARKET_LABELS = { us: "🇺🇸 米国", jp: "🇯🇵 日本" };
const OPEN_TICKER_KEY = "ai-profiles-open-ticker";

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
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

function popOpenTicker() {
  /** セクターマップ等から特定銘柄を指定して開かれた場合に受け取る。 */
  try {
    const value = window.sessionStorage.getItem(OPEN_TICKER_KEY);
    window.sessionStorage.removeItem(OPEN_TICKER_KEY);
    return value || null;
  } catch {
    return null;
  }
}

function tvUrl(ticker) {
  if (ticker.endsWith(".T")) {
    return `https://www.tradingview.com/chart/?symbol=TSE%3A${encodeURIComponent(ticker.slice(0, -2))}`;
  }
  return `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(ticker)}`;
}

function relatedTickersHtml(entries) {
  if (!entries || !entries.length) return "";
  return `
    <div class="aiprof-field">
      <div class="aiprof-field-label">関連の深い銘柄</div>
      <div class="aiprof-related-list">
        ${entries.map(e => `
          <div class="aiprof-related-row">
            <a class="aiprof-related-chip" href="${tvUrl(e.ticker)}" target="_blank" rel="noopener" title="${escapeHtml(e.ticker)}">${escapeHtml(e.name || e.ticker)}</a>
            ${e.reason ? `<span class="aiprof-related-reason">${escapeHtml(e.reason)}</span>` : ""}
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

function fieldHtml(label, value) {
  if (!value) return "";
  return `
    <div class="aiprof-field">
      <div class="aiprof-field-label">${escapeHtml(label)}</div>
      <div class="aiprof-field-body">${escapeHtml(value)}</div>
    </div>
  `;
}

function tickerCardHtml(entry) {
  const title = entry.name
    ? `${escapeHtml(entry.name)}<span class="aiprof-code">${escapeHtml(entry.ticker)}</span>`
    : escapeHtml(entry.ticker);

  if (entry.pending) {
    return `
      <div class="aiprof-card aiprof-pending">
        <div class="aiprof-card-head">
          <span class="aiprof-card-title">${title}</span>
          <span class="aiprof-pending-tag">準備中</span>
        </div>
      </div>
    `;
  }

  return `
    <div class="aiprof-card" data-ticker="${escapeHtml(entry.ticker)}">
      <button type="button" class="aiprof-card-head" aria-expanded="false">
        <span class="aiprof-card-title">${title}</span>
        <span class="aiprof-chevron">▾</span>
      </button>
      <div class="aiprof-card-body" hidden>
        ${fieldHtml("事業概要", entry.business)}
        ${fieldHtml("収益構造", entry.revenue)}
        ${fieldHtml("強み・特徴", entry.strengths)}
        ${fieldHtml("影響を受けやすい要因", entry.sensitivities)}
        ${relatedTickersHtml(entry.related_tickers)}
        <div class="aiprof-card-links">
          <a href="${entry.tv_url}" target="_blank" rel="noopener">TradingViewで見る ↗</a>
          ${entry.source_url ? `<a href="${escapeHtml(entry.source_url)}" target="_blank" rel="noopener">出典 ↗</a>` : ""}
        </div>
      </div>
    </div>
  `;
}

export async function renderAiProfiles(container) {
  container.innerHTML = '<div class="loading"><div class="spinner"></div><span>銘柄解説を読み込み中...</span></div>';

  let data;
  try {
    data = await apiFetch("/api/ai-map/profiles");
  } catch (error) {
    container.innerHTML = `<div class="empty-state">銘柄解説の取得に失敗しました: ${escapeHtml(error.message)}</div>`;
    return;
  }

  let activeMarket = loadMarketPref();
  const openTicker = popOpenTicker();
  if (openTicker) {
    // 指定銘柄が属する市場に自動で合わせる
    const owner = data.categories.find(c => c.tickers.some(t => t.ticker === openTicker));
    if (owner) activeMarket = owner.market;
  }
  saveMarketPref(activeMarket);

  container.innerHTML = `
    <style>${STYLE}</style>
    <div class="aiprof-shell">
      <div class="aiprof-hero">
        <div class="aiprof-kicker">STOCK PROFILES</div>
        <h2 class="aiprof-title">銘柄解説</h2>
        <div class="aiprof-note">AIセクターマップで扱う全銘柄の事業内容・収益構造・影響を受けやすい要因をまとめています。四半期ごとに更新。</div>
        <div class="aiprof-updated">最終更新 ${escapeHtml(data.updated_at ? data.updated_at.slice(0, 10) : "―")}　収録 ${data.total}銘柄</div>
        <div class="aiprof-market-toggle" role="tablist">
          ${MARKET_ORDER.map(m => `<button type="button" class="aiprof-market-btn ${m === activeMarket ? "active" : ""}" data-market="${m}" role="tab" aria-selected="${m === activeMarket}">${MARKET_LABELS[m]}</button>`).join("")}
        </div>
      </div>
      <div id="aiprof-list"></div>
    </div>
  `;

  function renderList() {
    const list = container.querySelector("#aiprof-list");
    const cats = data.categories.filter(c => c.market === activeMarket);
    list.innerHTML = cats.map(c => `
      <div class="aiprof-category">
        <div class="aiprof-cat-head">
          <span class="aiprof-cat-label">${escapeHtml(c.label)}</span>
          <span class="aiprof-cat-count">${c.tickers.length}銘柄</span>
        </div>
        <div class="aiprof-cards">${c.tickers.map(tickerCardHtml).join("")}</div>
      </div>
    `).join("");

    list.querySelectorAll(".aiprof-card-head").forEach(head => {
      if (head.tagName !== "BUTTON") return;
      head.addEventListener("click", () => {
        const body = head.nextElementSibling;
        const isOpen = !body.hidden;
        body.hidden = isOpen;
        head.setAttribute("aria-expanded", isOpen ? "false" : "true");
        head.parentElement.classList.toggle("aiprof-card-open", !isOpen);
      });
    });

    if (openTicker) {
      const card = list.querySelector(`.aiprof-card[data-ticker="${CSS.escape(openTicker)}"]`);
      const head = card?.querySelector(".aiprof-card-head");
      if (head) {
        head.click();
        card.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  }

  renderList();

  container.querySelectorAll(".aiprof-market-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      if (btn.dataset.market === activeMarket) return;
      activeMarket = btn.dataset.market;
      saveMarketPref(activeMarket);
      container.querySelectorAll(".aiprof-market-btn").forEach(b => b.classList.toggle("active", b === btn));
      renderList();
    });
  });
}

const STYLE = `
  .aiprof-shell { --ap-line:#26354d; --ap-panel:#111c30; display:grid; gap:16px; }
  .aiprof-shell > * { min-width:0; }
  .aiprof-hero { position:relative; overflow:hidden; border:1px solid var(--ap-line); border-radius:14px; padding:18px 20px; background:linear-gradient(120deg,#101d32 0%,#0e1728 62%,#14243a 100%); }
  .aiprof-kicker { color:#7dd3fc; font-size:.68rem; letter-spacing:.18em; text-transform:uppercase; font-weight:800; }
  .aiprof-title { margin:3px 0 0; font-size:1.35rem; letter-spacing:.01em; }
  .aiprof-note { margin-top:7px; color:#cbd5e1; font-size:.75rem; line-height:1.6; }
  .aiprof-updated { margin-top:6px; color:var(--text-muted); font-size:.72rem; font-variant-numeric:tabular-nums; }
  .aiprof-market-toggle { display:flex; gap:6px; margin-top:12px; }
  .aiprof-market-btn { min-height:34px; padding:6px 16px; border:1px solid #365071; border-radius:8px; background:#0d1727; color:#cbd5e1; font:inherit; font-size:.8rem; font-weight:800; cursor:pointer; }
  .aiprof-market-btn.active { background:#334155; border-color:#64748b; color:#fff; }

  .aiprof-category { display:grid; gap:8px; margin-bottom:18px; }
  .aiprof-cat-head { display:flex; align-items:baseline; gap:9px; padding:4px 2px; border-bottom:1px solid var(--ap-line); }
  .aiprof-cat-label { color:#dbeafe; font-size:.82rem; font-weight:800; }
  .aiprof-cat-count { color:#64748b; font-size:.66rem; }
  .aiprof-cards { display:grid; gap:7px; }

  .aiprof-card { border:1px solid var(--ap-line); border-radius:10px; background:var(--ap-panel); overflow:hidden; }
  .aiprof-card.aiprof-card-open { border-color:#3b82f6; }
  .aiprof-card-head { display:flex; align-items:center; justify-content:space-between; gap:10px; width:100%; padding:11px 13px; border:0; background:transparent; color:inherit; font:inherit; text-align:left; cursor:pointer; }
  .aiprof-card-title { font-weight:800; font-size:.82rem; }
  .aiprof-code { margin-left:7px; color:#64748b; font-weight:600; font-size:.66rem; }
  .aiprof-chevron { color:#47617f; font-weight:900; }
  .aiprof-card-open .aiprof-chevron { color:#93c5fd; }
  .aiprof-card-body { padding:2px 13px 13px; display:grid; gap:11px; }
  .aiprof-card-body[hidden] { display:none; }

  .aiprof-field-label { color:#7dd3fc; font-size:.68rem; font-weight:800; margin-bottom:3px; }
  .aiprof-field-body { color:#cbd5e1; font-size:.76rem; line-height:1.65; }
  .aiprof-related-list { display:grid; gap:5px; }
  .aiprof-related-row { display:flex; align-items:baseline; gap:7px; }
  .aiprof-related-chip { flex:none; display:inline-flex; align-items:center; border-radius:999px; padding:2px 8px; font-size:.68rem; font-weight:750; color:#c4b5fd; background:rgba(168,85,247,.14); text-decoration:none; }
  .aiprof-related-chip:hover { background:rgba(168,85,247,.24); }
  .aiprof-related-reason { min-width:0; color:#94a3b8; font-size:.7rem; line-height:1.5; }
  .aiprof-card-links { display:flex; flex-wrap:wrap; gap:14px; padding-top:3px; }
  .aiprof-card-links a { color:#93c5fd; font-size:.7rem; text-decoration:none; }
  .aiprof-card-links a:hover { color:#dbeafe; text-decoration:underline; }

  .aiprof-pending { opacity:.55; }
  .aiprof-pending .aiprof-card-head { cursor:default; }
  .aiprof-pending-tag { color:#64748b; font-size:.66rem; }

  @media (max-width:720px) {
    .aiprof-hero { padding:15px; }
    .aiprof-market-toggle { width:100%; }
    .aiprof-market-btn { flex:1; text-align:center; }
  }
`;
