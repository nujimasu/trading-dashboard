import { apiFetch } from "../utils/api.js?v=3";

const FILTER_KEY = "ai-news-filter-category";
const FILTER_MARKET_KEY = "ai-news-filter-market";
const MARKET_KEY = "ai-news-market-v1";
const MARKET_ORDER = ["us", "jp"];
const MARKET_LABELS = { us: "🇺🇸 米国", jp: "🇯🇵 日本" };
const SENTIMENT_LABEL = { positive: "ポジティブ", negative: "ネガティブ", neutral: "中立" };
const WEEKDAY_JA = ["日", "月", "火", "水", "木", "金", "土"];

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDateHeader(iso) {
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return escapeHtml(iso);
  const m = d.getUTCMonth() + 1;
  const day = d.getUTCDate();
  const w = WEEKDAY_JA[d.getUTCDay()];
  return `${m}/${day}（${w}）`;
}

function popFilterCategory() {
  try {
    const value = window.sessionStorage.getItem(FILTER_KEY);
    window.sessionStorage.removeItem(FILTER_KEY);
    return value || "all";
  } catch {
    return "all";
  }
}

function popFilterMarket() {
  /** セクターマップから遷移してきた場合はその市場を優先し、無ければ前回選択を使う。 */
  try {
    const handoff = window.sessionStorage.getItem(FILTER_MARKET_KEY);
    window.sessionStorage.removeItem(FILTER_MARKET_KEY);
    if (MARKET_ORDER.includes(handoff)) return handoff;
    const saved = window.localStorage.getItem(MARKET_KEY);
    return MARKET_ORDER.includes(saved) ? saved : "us";
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

function tvUrl(ticker) {
  // 東証銘柄（8035.T）は TradingView の TSE:8035 形式にする
  if (ticker.endsWith(".T")) {
    return `https://www.tradingview.com/chart/?symbol=TSE%3A${encodeURIComponent(ticker.slice(0, -2))}`;
  }
  return `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(ticker)}`;
}

function affectedTickersHtml(entries) {
  if (!entries || !entries.length) return "";
  // entries は [{ticker, reason}]。古いデータは reason が空文字で来る。
  return `
    <div class="ainews-affected">
      <div class="ainews-affected-label" title="この材料が波及しそうな銘柄。AIによる推定であり保証はありません">影響波及先</div>
      <div class="ainews-affected-list">
        ${entries.map(e => `
          <div class="ainews-affected-row">
            <a class="ainews-affected-chip" href="${tvUrl(e.ticker)}" target="_blank" rel="noopener">${escapeHtml(e.ticker)}</a>
            ${e.reason ? `<span class="ainews-affected-reason">${escapeHtml(e.reason)}</span>` : ""}
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

function newsItemHtml(item) {
  return `
    <div class="ainews-item ainews-sent-${escapeHtml(item.sentiment)}" data-category="${escapeHtml(item.category)}">
      <div class="ainews-item-head">
        <span class="ainews-cat-tag">${escapeHtml(item.category_label || item.category)}</span>
        ${item.ticker ? `<span class="ainews-ticker">${escapeHtml(item.ticker)}</span>` : `<span class="ainews-ticker ainews-overview">総括</span>`}
        <span class="ainews-sentiment" title="ニュースの論調">${SENTIMENT_LABEL[item.sentiment] || "中立"}</span>
      </div>
      <div class="ainews-headline">${escapeHtml(item.headline)}</div>
      <div class="ainews-summary">${escapeHtml(item.summary_ja)}</div>
      ${affectedTickersHtml(item.affected_tickers)}
      ${item.source_url ? `<a class="ainews-source" href="${escapeHtml(item.source_url)}" target="_blank" rel="noopener">出典を見る ↗</a>` : ""}
    </div>
  `;
}

function groupByDate(items) {
  const groups = [];
  let current = null;
  for (const item of items) {
    if (!current || current.date !== item.news_date) {
      current = { date: item.news_date, items: [] };
      groups.push(current);
    }
    current.items.push(item);
  }
  return groups;
}

function staleWarningHtml(news) {
  if (!news.items.length) {
    return `<div class="ainews-empty">ニュースはまだありません。毎朝のクラウド実行後に自動で追加されます。</div>`;
  }
  if (news.stale) {
    return `<div class="ainews-warning" role="alert">⚠️ ニュースの更新が止まっている可能性があります（最終更新 ${escapeHtml(news.updated_at || "不明")}）</div>`;
  }
  return "";
}

export async function renderAiNews(container) {
  container.innerHTML = '<div class="loading"><div class="spinner"></div><span>AIニュースを取得中...</span></div>';

  let news;
  try {
    news = await apiFetch("/api/ai-map/news?days=30");
  } catch (error) {
    container.innerHTML = `<div class="empty-state">AIニュースの取得に失敗しました: ${escapeHtml(error.message)}</div>`;
    return;
  }

  const allCategories = news.categories || [];
  const categoryLabel = Object.fromEntries(allCategories.map(c => [c.id, c.short_label || c.label]));
  const categoryMarket = Object.fromEntries(allCategories.map(c => [c.id, c.market || "us"]));
  const items = news.items.map(item => ({
    ...item,
    category_label: categoryLabel[item.category] || item.category,
    market: categoryMarket[item.category] || "us",
  }));

  let activeCategory = popFilterCategory();
  let activeMarket = popFilterMarket();
  // 引き継いだカテゴリーがある場合はその市場に合わせる（市場とカテゴリーの不一致を防ぐ）
  if (activeCategory !== "all" && categoryMarket[activeCategory]) {
    activeMarket = categoryMarket[activeCategory];
  } else if (activeCategory !== "all") {
    activeCategory = "all";
  }
  saveMarketPref(activeMarket);
  let categories = allCategories.filter(c => (c.market || "us") === activeMarket);

  container.innerHTML = `
    <style>${STYLE}</style>
    <div class="ainews-shell">
      <div class="ainews-hero">
        <div class="ainews-kicker">AI NEWS</div>
        <h2 class="ainews-title">AIニュース</h2>
        <div class="ainews-updated">最終更新 ${escapeHtml(news.updated_at ? news.updated_at.slice(0, 16).replace("T", " ") : "―")}</div>
        ${staleWarningHtml(news)}
        <div class="ainews-market-toggle" role="tablist">
          ${MARKET_ORDER.map(m => `<button type="button" class="ainews-market-btn ${m === activeMarket ? "active" : ""}" data-market="${m}" role="tab" aria-selected="${m === activeMarket}">${MARKET_LABELS[m]}</button>`).join("")}
        </div>
      </div>

      <div class="ainews-filters" id="ainews-filters" role="tablist"></div>

      <div id="ainews-list"></div>
    </div>
  `;

  function renderFilters() {
    const wrap = container.querySelector("#ainews-filters");
    wrap.innerHTML = `
      <button type="button" class="ainews-filter-chip ${activeCategory === "all" ? "active" : ""}" data-cat="all">すべて</button>
      ${categories.map(c => `<button type="button" class="ainews-filter-chip ${activeCategory === c.id ? "active" : ""}" data-cat="${escapeHtml(c.id)}">${escapeHtml(c.short_label || c.label)}</button>`).join("")}
    `;
    wrap.querySelectorAll(".ainews-filter-chip").forEach(btn => {
      btn.addEventListener("click", () => {
        activeCategory = btn.dataset.cat;
        wrap.querySelectorAll(".ainews-filter-chip").forEach(b => b.classList.toggle("active", b === btn));
        renderList();
      });
    });
  }

  function renderList() {
    const inMarket = items.filter(i => i.market === activeMarket);
    const filtered = activeCategory === "all" ? inMarket : inMarket.filter(i => i.category === activeCategory);
    const list = container.querySelector("#ainews-list");
    if (!filtered.length) {
      list.innerHTML = `<div class="ainews-empty">該当するニュースがありません。</div>`;
      return;
    }
    const groups = groupByDate(filtered);
    list.innerHTML = groups.map(g => `
      <div class="ainews-date-group">
        <div class="ainews-date-header">${formatDateHeader(g.date)}</div>
        <div class="ainews-date-items">${g.items.map(newsItemHtml).join("")}</div>
      </div>
    `).join("");
  }

  renderFilters();
  renderList();

  container.querySelectorAll(".ainews-market-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      if (btn.dataset.market === activeMarket) return;
      activeMarket = btn.dataset.market;
      activeCategory = "all";
      saveMarketPref(activeMarket);
      categories = allCategories.filter(c => (c.market || "us") === activeMarket);
      container.querySelectorAll(".ainews-market-btn").forEach(b => b.classList.toggle("active", b === btn));
      renderFilters();
      renderList();
    });
  });
}

const STYLE = `
  .ainews-shell { --an-line:#26354d; --an-panel:#111c30; display:grid; gap:16px; }
  .ainews-shell > * { min-width:0; }
  .ainews-hero { position:relative; overflow:hidden; border:1px solid var(--an-line); border-radius:14px; padding:18px 20px; background:linear-gradient(120deg,#101d32 0%,#0e1728 62%,#14243a 100%); }
  .ainews-kicker { color:#c4b5fd; font-size:.68rem; letter-spacing:.18em; text-transform:uppercase; font-weight:800; }
  .ainews-title { margin:3px 0 0; font-size:1.35rem; letter-spacing:.01em; }
  .ainews-updated { margin-top:6px; color:var(--text-muted); font-size:.74rem; font-variant-numeric:tabular-nums; }
  .ainews-warning { position:relative; z-index:1; display:flex; align-items:center; gap:8px; margin-top:12px; padding:9px 11px; border:1px solid rgba(251,146,60,.58); border-radius:8px; background:linear-gradient(90deg,rgba(127,29,29,.42),rgba(120,53,15,.32)); color:#fed7aa; box-shadow:inset 3px 0 0 #f97316; font-size:.76rem; font-weight:750; }

  .ainews-market-toggle { display:flex; gap:6px; margin-top:12px; }
  .ainews-market-btn { min-height:34px; padding:6px 16px; border:1px solid #365071; border-radius:8px; background:#0d1727; color:#cbd5e1; font:inherit; font-size:.8rem; font-weight:800; cursor:pointer; }
  .ainews-market-btn.active { background:#334155; border-color:#64748b; color:#fff; }
  .ainews-filters { display:flex; flex-wrap:wrap; gap:6px; }
  .ainews-filter-chip { min-height:30px; padding:5px 12px; border:1px solid #365071; border-radius:999px; background:#0d1727; color:#93c5fd; font:inherit; font-size:.72rem; font-weight:700; cursor:pointer; }
  .ainews-filter-chip.active { background:#6d28d9; border-color:#6d28d9; color:#fff; }

  .ainews-empty { color:var(--text-muted); font-size:.8rem; padding:24px 4px; text-align:center; }

  .ainews-date-group { display:grid; gap:8px; }
  .ainews-date-header { color:#dbeafe; font-size:.76rem; font-weight:800; padding:4px 2px; border-bottom:1px solid var(--an-line); }
  .ainews-date-items { display:grid; gap:8px; }

  .ainews-item { padding:11px 12px; border-radius:10px; background:var(--an-panel); border-left:3px solid #64748b; border:1px solid var(--an-line); border-left-width:3px; }
  .ainews-item.ainews-sent-positive { border-left-color:#22c55e; }
  .ainews-item.ainews-sent-negative { border-left-color:#ef4444; }
  .ainews-item.ainews-sent-neutral { border-left-color:#64748b; }
  .ainews-item-head { display:flex; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:4px; }
  .ainews-cat-tag { color:#93c5fd; background:rgba(59,130,246,.14); border-radius:999px; padding:2px 8px; font-size:.64rem; font-weight:750; }
  .ainews-ticker { color:#dbeafe; font-weight:800; font-size:.74rem; }
  .ainews-overview { color:#c4b5fd; }
  .ainews-sentiment { margin-left:auto; color:#64748b; font-size:.64rem; }
  .ainews-headline { font-weight:750; font-size:.82rem; }
  .ainews-summary { margin-top:3px; color:#cbd5e1; font-size:.76rem; line-height:1.55; }
  .ainews-affected { margin-top:9px; padding-top:8px; border-top:1px dashed rgba(148,163,184,.22); }
  .ainews-affected-label { color:#64748b; font-size:.66rem; margin-bottom:5px; }
  .ainews-affected-list { display:grid; gap:5px; }
  .ainews-affected-row { display:flex; align-items:baseline; gap:7px; }
  .ainews-affected-chip { flex:none; display:inline-flex; align-items:center; border-radius:999px; padding:2px 8px; font-size:.68rem; font-weight:750; color:#c4b5fd; background:rgba(168,85,247,.14); text-decoration:none; }
  .ainews-affected-chip:hover { background:rgba(168,85,247,.24); }
  .ainews-affected-reason { min-width:0; color:#94a3b8; font-size:.7rem; line-height:1.5; }
  .ainews-source { display:inline-block; margin-top:8px; color:#93c5fd; font-size:.68rem; text-decoration:none; }
  .ainews-source:hover { color:#dbeafe; text-decoration:underline; }

  @media (max-width:720px) {
    .ainews-hero { padding:15px; }
    .ainews-filters, .ainews-market-toggle { width:100%; }
    .ainews-market-btn { flex:1; text-align:center; }
  }
`;
