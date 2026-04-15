import { apiFetch } from "../utils/api.js";
import { renderCandlestick } from "../utils/charts.js?v=2";

export function renderSearchUI(container) {
  container.innerHTML = `
    <div class="section-title">🔍 銘柄検索</div>
    <div class="search-bar">
      <input id="search-input" class="search-input" type="text"
             placeholder="ティッカー入力 (例: NVDA)" autocomplete="off" />
      <button id="search-btn" class="btn btn-primary">分析</button>
    </div>
    <div id="search-result"></div>`;

  const input  = container.querySelector("#search-input");
  const btn    = container.querySelector("#search-btn");
  const result = container.querySelector("#search-result");

  const doSearch = () => {
    const t = input.value.trim().toUpperCase();
    if (!t) return;
    runSearch(t, result);
  };

  btn.addEventListener("click", doSearch);
  input.addEventListener("keydown", e => { if (e.key === "Enter") doSearch(); });
}

async function runSearch(ticker, resultEl) {
  resultEl.innerHTML = `<div class="loading"><div class="spinner"></div><span>${ticker} を分析中...</span></div>`;

  let data;
  try {
    data = await apiFetch(`/api/search/${ticker}`);
  } catch (e) {
    resultEl.innerHTML = `<div class="empty-state">エラー: ${e.message}</div>`;
    return;
  }

  const bannerClass = data.verdict === "BUY"   ? "buy"
                    : data.verdict === "WATCH"  ? "watch"
                    : "nobuy";
  const verdictJa   = data.verdict === "BUY"   ? "買い推奨"
                    : data.verdict === "WATCH"  ? "様子見 (Tier 2)"
                    : "見送り";

  const fs = data.fundamental_summary || {};
  const indic = data.indicators || {};
  const trade = data.trade || {};

  const reasons = (data.entry_reasons || []).map(r => `<li>${escHtml(r)}</li>`).join("");
  const risks   = (data.risk_factors  || []).map(r => `<li>${escHtml(r)}</li>`).join("");

  const fundBlock = fs.available ? `
    ${kv("セクター",       fs.sector)}
    ${kv("時価総額",       fs.market_cap_b ? `$${fs.market_cap_b}B` : "—")}
    ${kv("P/E",            fs.pe_ratio != null ? fs.pe_ratio.toFixed(1) : "—")}
    ${kv("EPS成長(YoY)",   fs.eps_growth_yoy != null ? `${fs.eps_growth_yoy}%` : "—")}
    ${kv("売上成長(YoY)",  fs.revenue_growth_yoy != null ? `${fs.revenue_growth_yoy}%` : "—")}
    ${kv("決算サプライズ", fs.earnings_surprise_pct != null ? `${fs.earnings_surprise_pct}%` : "—")}
    ${fs.description ? `<div style="font-size:.75rem;color:var(--text-muted);margin-top:8px">${escHtml(fs.description)}</div>` : ""}
  ` : `<div style="color:var(--text-muted);font-size:.8rem">ファンダデータなし（FMP APIキー必要）</div>`;

  const themes = (data.themes || []).map(t => `<span class="badge badge-blue">${t}</span>`).join(" ");

  resultEl.innerHTML = `
    <div class="verdict-banner ${bannerClass}">
      ${data.verdict === "BUY" ? "✅" : data.verdict === "WATCH" ? "⚠️" : "❌"}
      ${data.ticker} — ${verdictJa}
    </div>
    <div style="color:var(--text-muted);font-size:.85rem;margin-bottom:16px">
      ${escHtml(data.verdict_reason)}
    </div>

    <div class="detail-grid">
      <div class="detail-block card">
        <h4>価格・指標</h4>
        ${kv("現在値",       `$${fmt(data.price)} (${data.change_pct >= 0 ? "+" : ""}${fmt(data.change_pct)}%)`)}
        ${kv("RSI",          indic.rsi        ? indic.rsi.toFixed(1) : "—")}
        ${kv("MACD>Signal",  indic.macd != null && indic.macd_signal != null ? (indic.macd > indic.macd_signal ? "✅" : "❌") : "—")}
        ${kv("出来高比",     indic.vol_ratio  ? `${indic.vol_ratio.toFixed(2)}x` : "—")}
        ${kv("52w高値比",    trade.pct_from_high != null ? `${trade.pct_from_high.toFixed(1)}%` : "—")}
        ${themes ? `<div style="margin-top:8px">${themes}</div>` : ""}
      </div>

      <div class="detail-block card">
        <h4>トレードプラン</h4>
        ${kv("エントリー",   `$${fmt(trade.entry)}`)}
        ${kv("ストップ",     `$${fmt(trade.stop)}`)}
        ${kv("目標",         `$${fmt(trade.target)}`)}
        ${kv("リスク",       `$${fmt(trade.risk)}`)}
        ${kv("リワード",     `$${fmt(trade.reward)}`)}
        ${kv("RR",           fmt(trade.risk_reward))}
        ${kv("Tier",         data.tier)}
      </div>

      <div class="detail-block card">
        <h4>ファンダメンタル</h4>
        ${fundBlock}
      </div>
    </div>

    <div class="detail-grid" style="margin-top:16px">
      <div class="detail-block card">
        <h4>エントリー根拠</h4>
        <ul class="reason-list">${reasons || "<li>なし</li>"}</ul>
      </div>
      <div class="detail-block card">
        <h4>リスク要因</h4>
        <ul class="reason-list risks">${risks || "<li>特になし</li>"}</ul>
      </div>
    </div>

    <div class="card" style="margin-top:16px;padding:0;overflow:hidden">
      <div id="search-chart" style="height:300px"></div>
    </div>`;

  // Render chart
  if (data.chart_data && data.chart_data.length) {
    setTimeout(() => renderCandlestick(
      "search-chart",
      data.chart_data,
      { entry: trade.entry, stop: trade.stop, target: trade.target }
    ), 50);
  }
}

function kv(label, value) {
  return `<div class="kv-row"><span class="kv-key">${label}</span><span class="kv-val">${value ?? "—"}</span></div>`;
}
function fmt(v) { return v != null ? Number(v).toFixed(2) : "—"; }
function escHtml(s) { return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
