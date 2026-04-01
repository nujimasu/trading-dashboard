/**
 * Shared renderer for economic indicators AND news (same layout).
 */
import { apiFetch } from "../utils/api.js";

export async function renderEvents(container, endpoint, title) {
  container.innerHTML = `<div class="loading"><div class="spinner"></div><span>取得中...</span></div>`;
  let items;
  try {
    items = await apiFetch(endpoint);
  } catch (e) {
    container.innerHTML = `<div class="empty-state">データ取得失敗: ${e.message}</div>`;
    return;
  }

  if (!items.length) {
    container.innerHTML = `
      <div class="section-title">${title}</div>
      <div class="empty-state">データなし — パイプラインを実行してください。</div>`;
    return;
  }

  const cards = items.map(item => {
    const impactLabel = item.impact === "positive" ? "ポジティブ"
                      : item.impact === "negative" ? "ネガティブ"
                      : "中立";
    const badgeClass = item.impact === "positive" ? "badge-green"
                     : item.impact === "negative" ? "badge-red"
                     : "badge-gray";

    const sectors = (item.affected_sectors || []).map(s =>
      `<span class="badge badge-blue">${s}</span>`).join(" ");
    const tickers = (item.affected_tickers || []).filter(Boolean).map(t =>
      `<span class="badge badge-gray">${t}</span>`).join(" ");

    const titleHtml = item.url
      ? `<a class="event-title event-title--link" href="${escHtml(item.url)}" target="_blank" rel="noopener noreferrer">${escHtml(item.title)}</a>`
      : `<div class="event-title">${escHtml(item.title)}</div>`;

    return `
      <div class="event-card">
        <div class="event-impact ${item.impact}"></div>
        <div class="event-body">
          ${titleHtml}
          ${item.description ? `<div class="event-desc">${escHtml(item.description)}</div>` : ""}
          <div class="event-meta">
            <span class="event-date">${item.date}</span>
            <span class="badge ${badgeClass}">${impactLabel}</span>
            ${sectors}
            ${tickers}
          </div>
        </div>
      </div>`;
  }).join("");

  container.innerHTML = `
    <div class="section-title">${title}</div>
    <div class="event-list">${cards}</div>`;
}

function escHtml(str) {
  return (str || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}
