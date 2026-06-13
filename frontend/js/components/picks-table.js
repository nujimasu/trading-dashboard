/**
 * Shared picks table renderer — used by weekly-picks and daily-picks.
 */
import { renderCandlestick } from "../utils/charts.js?v=2";
import { apiFetch } from "../utils/api.js";

// ── Market health cache (shared across all detail panels) ───────────────────
let _mhCache = null;
export async function _getMarketHealth() {
  if (!_mhCache) {
    try { _mhCache = await apiFetch("/api/market-health"); } catch { _mhCache = {}; }
  }
  return _mhCache;
}

let openDetailRow = null;  // track currently expanded row

export function renderPicksTable(container, picks, title, mode = "weekly") {
  const isDaily = mode === "daily";
  const isTP    = mode === "take-profit";
  const isHybridEntry = mode === "hybrid-entry";

  if (!picks.length) {
    const emptyMsg = isTP
      ? "利確シグナルなし — 全銘柄「継続保有」の判定です。"
      : isDaily
        ? "本日の候補なし — 毎朝7:00に自動更新されます（手動: <code>python3 pipeline/run_pipeline.py --daily-only</code>）"
        : "候補銘柄なし — パイプラインを実行してください。";
    container.innerHTML = `
      <div class="section-title">${title}</div>
      <div class="empty-state">${emptyMsg}</div>`;
    return;
  }

  const rows = picks.map((p, i) => {
    // Determine which verdict to show
    let vKey;
    if (isTP)         vKey = p.take_profit_verdict || "HOLD";
    else if (isDaily) vKey = p.daily_verdict;
    else              vKey = p.daily_verdict || p.verdict;

    const verdictText  = verdictLabel(vKey);
    const verdictClass = verdictCss(vKey);
    const tierBadge    = p.tier === "Tier1"
      ? `<span class="tier-badge tier-t1">T1</span>`
      : `<span class="tier-badge tier-t2">T2</span>`;
    const dirBadge = p.direction === "SHORT"
      ? `<span class="dir-badge dir-short">▼SHORT</span>`
      : `<span class="dir-badge dir-long">▲LONG</span>`;

    const rr = (isDaily || isHybridEntry || isTP) ? (p.adjusted_rr ?? p.weekly_rr ?? p.risk_reward) : p.risk_reward;

    const score = p.composite_score ?? "—";
    const holdBadge = _holdingBadge(p.holding_days_est);

    // Daily-specific columns
    const dailyBreakout = isDaily ? `<td>${p.breakout_triggered ? "✅" : "—"}</td>` : ``;
    const dailyVolume   = isDaily ? `<td>${p.volume_confirmation ? "✅" : "—"}</td>` : ``;
    const dailyPrice    = (isDaily || isHybridEntry || isTP) && p.current_price
      ? `<td>$${fmt(p.current_price)}</td>` : (isDaily || isHybridEntry || isTP) ? `<td>—</td>` : ``;

    // ハイブリッドモード: エントリー/利確理由を表示
    const hybridReasonCol = (isHybridEntry || isTP) ? `<td style="font-size:.76rem;color:var(--text-muted);max-width:220px">${_hybridReason(p, isTP)}</td>` : "";

    return `
      <tr data-idx="${i}" class="pick-row">
        <td class="ticker-cell">${p.ticker}</td>
        ${!(isHybridEntry || isTP) ? `<td>${tierBadge}</td>` : ""}
        <td>${score}</td>
        <td class="${verdictClass}">${verdictText}</td>
        ${hybridReasonCol}
        ${dailyBreakout}
        ${dailyVolume}
        <td>${holdBadge}</td>
        <td>${dirBadge}</td>
        ${!(isHybridEntry || isTP) ? `<td>${fmt(rr)}</td><td>$${fmt(p.entry_price)}</td><td>$${fmt(p.stop_price)}</td><td>$${fmt(p.tp1_price)}</td><td>$${fmt(p.target_price)}</td>` : `<td>${fmt(rr)}</td>`}
        <td>${p.sector || "—"}</td>
        ${dailyPrice}
      </tr>
      <tr class="detail-row" id="detail-${i}" style="display:none">
        <td colspan="100">${buildDetailPanel(p, i, mode)}</td>
      </tr>`;
  }).join("");

  container.innerHTML = `
    <div class="section-title">${title}</div>
    <div class="picks-table-wrap">
      <table>
        <thead>
          <tr>
            <th>銘柄</th>${!(isHybridEntry || isTP) ? "<th>Tier</th>" : ""}<th>スコア</th><th>判定</th>
            ${isTP ? "<th>利確理由</th>" : ""}
            ${isDaily ? "<th>ブレイク</th><th>出来高</th>" : ""}
            ${(isHybridEntry || isTP) ? "<th>理由</th>" : ""}
            <th>保有期間</th><th>方向</th>
            ${!(isHybridEntry || isTP) ? "<th>RR</th><th>エントリー</th><th>SL</th><th>TP1</th><th>TP2</th>" : "<th>RR</th>"}
            <th>セクター</th>
            ${(isDaily || isHybridEntry || isTP) ? "<th>現在値</th>" : ""}
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;

  // Row click → expand/collapse detail
  container.querySelectorAll(".pick-row").forEach(row => {
    row.addEventListener("click", () => {
      const idx    = row.dataset.idx;
      const detail = container.querySelector(`#detail-${idx}`);
      const isOpen = detail.style.display !== "none";

      // Close any open panel
      container.querySelectorAll(".detail-row").forEach(r => r.style.display = "none");

      if (!isOpen) {
        detail.style.display = "table-row";
        const pick = picks[idx];

        // Render chart from /api/chart endpoint
        apiFetch(`/api/chart/${pick.ticker}?days=180`).then(chartResp => {
          if (chartResp && chartResp.data && chartResp.data.length > 0) {
            const patternData = (pick.base_pattern && pick.pivot_price) ? {
              pivot:          pick.pivot_price,
              base_low:       pick.stop_price,
              base_length:    pick.base_length || 30,
              base_pattern:   pick.base_pattern,
              base_depth_pct: pick.base_depth_pct,
              breakout_confirmed: pick.breakout_confirmed,
              breakout_volume_ratio: pick.breakout_volume_ratio,
            } : null;
            renderCandlestick(`chart-${idx}`, chartResp.data, {
              entry:  pick.entry_price,
              stop:   pick.stop_price,
              tp1:    pick.tp1_price,
              target: pick.target_price,
            }, patternData);
          }
        }).catch(() => {});

        // Inject sector trend block asynchronously
        const sectorSlot = detail.querySelector(`#sector-slot-${idx}`);
        if (sectorSlot) {
          _getMarketHealth().then(mh => {
            const sectorName = (pick.fundamental_summary?.sector) || pick.sector;
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
            sectorSlot.innerHTML = `
              <div class="kv-row">
                <span class="kv-key">アップトレンド比率</span>
                <span class="kv-val" style="color:${color}">${score.toFixed(1)}%</span>
              </div>
              ${maDiff != null ? `<div class="kv-row"><span class="kv-key">20日MA比</span><span class="kv-val">${maHtml}</span></div>` : ""}
              ${spark ? `<div style="margin-top:6px">${spark}</div>` : ""}`;
          });
        }
      }
    });
  });
}

export function buildDetailPanel(p, idx, mode = "weekly") {
  const ts = p.technical_summary   || {};
  const fs = p.fundamental_summary || {};

  const reasons = (ts.entry_reasons || []).map(r =>
    `<li>${escHtml(r)}</li>`).join("");
  const risks   = (ts.risk_factors  || []).map(r =>
    `<li>${escHtml(r)}</li>`).join("");

  const fvClass = { "強気": "verdict-buy", "やや強気": "verdict-watch",
                    "中立": "verdict-passed", "やや弱気": "verdict-short-watch",
                    "弱気": "verdict-short", "データなし": "" }[p.fundamental_verdict] || "";
  const fvBadge = p.fundamental_verdict
    ? `<span class="${fvClass}" style="font-size:.8rem;font-weight:700">${p.fundamental_verdict}</span>`
    : "";

  const sectorName = fs.sector || p.sector || null;
  const sectorBlock = sectorName ? `
    <div class="detail-block">
      <h4>セクター動向 — ${escHtml(sectorName)}</h4>
      <div id="sector-slot-${idx}" style="min-height:40px">
        <div style="color:var(--text-muted);font-size:.78rem">読み込み中...</div>
      </div>
    </div>
  ` : "";

  const fundBlock = fs.available ? `
    <div class="detail-block">
      <h4>ファンダメンタル ${fvBadge}</h4>
      ${kv("セクター",      fs.sector)}
      ${kv("時価総額",      fs.market_cap_b ? `$${fs.market_cap_b}B` : "—")}
      ${kv("P/E",           fs.pe_ratio     ? fs.pe_ratio.toFixed(1) : "—")}
      ${kv("EPS成長(四半期)", fs.eps_growth_q != null ? `${fs.eps_growth_q}%` : "—")}
      ${kv("EPS成長(YoY)",  fs.eps_growth_yoy != null ? `${fs.eps_growth_yoy}%` : "—")}
      ${kv("売上成長(YoY)", fs.revenue_growth_yoy != null ? `${fs.revenue_growth_yoy}%` : "—")}
      ${kv("決算サプライズ", fs.earnings_surprise_pct != null ? `${fs.earnings_surprise_pct}%` : "—")}
      ${kv("ROE",           fs.roe != null ? `${fs.roe}%` : "—")}
      ${kv("営業利益率",     fs.operating_margin != null ? `${fs.operating_margin}%` : "—")}
      ${kv("利益率",        fs.profit_margin != null ? `${fs.profit_margin}%` : "—")}
      ${kv("機関投資家保有", fs.inst_own_pct != null ? `${fs.inst_own_pct}%` : "—")}
      ${kv("D/E",           fs.debt_to_equity != null ? fs.debt_to_equity : "—")}
      ${kv("成長スコア",     fs.growth_score != null ? `${fs.growth_score}/100` : "—")}
      ${fs.description ? `<div style="font-size:.75rem;color:var(--text-muted);margin-top:8px">${escHtml(fs.description)}</div>` : ""}
    </div>
  ` : `<div class="detail-block"><h4>ファンダメンタル</h4><div style="color:var(--text-muted);font-size:.8rem">データなし</div></div>`;

  const chartDiv = `<div id="chart-${idx}" class="pick-chart-container"></div>`;

  const dir    = p.direction || "LONG";
  const isShort = dir === "SHORT";
  const rr1   = p.entry_price && p.stop_price && p.tp1_price
    ? Math.abs((p.tp1_price - p.entry_price) / (p.entry_price - p.stop_price) * (isShort ? -1 : 1)).toFixed(2)
    : "1.50";
  const rr2   = p.risk_reward ? Number(p.risk_reward).toFixed(2) : "—";
  const hasTradePlan = p.entry_price != null && p.stop_price != null && p.tp1_price != null && p.target_price != null;
  const tradePlanHtml = hasTradePlan ? `
      <div class="trade-plan-row">
        <div class="tp-box tp-entry">
          <div class="tp-label">エントリー</div>
          <div class="tp-val">$${fmt(p.entry_price)}</div>
        </div>
        <div class="tp-arrow">${isShort ? "▼" : "▲"}</div>
        <div class="tp-box tp-sl">
          <div class="tp-label">SL（損切り）</div>
          <div class="tp-val tp-val-red">$${fmt(p.stop_price)}</div>
          <div class="tp-sub">${isShort ? "+" : "-"}${p.entry_price && p.stop_price ? Math.abs(p.entry_price - p.stop_price).toFixed(2) : "—"}</div>
        </div>
        <div class="tp-arrow">→</div>
        <div class="tp-box tp-tp1">
          <div class="tp-label">TP1（半決済）</div>
          <div class="tp-val tp-val-green">$${fmt(p.tp1_price)}</div>
          <div class="tp-sub">RR ${rr1}R</div>
        </div>
        <div class="tp-arrow">→</div>
        <div class="tp-box tp-tp2">
          <div class="tp-label">TP2（ランナー）</div>
          <div class="tp-val tp-val-green">$${fmt(p.target_price)}</div>
          <div class="tp-sub">RR ${rr2}R</div>
        </div>
        <div class="tp-sep"></div>
        <div class="tp-box tp-hold">
          <div class="tp-label">推定保有期間</div>
          <div class="tp-val">${_holdingBadge(p.holding_days_est)}</div>
          <div class="tp-sub">${_holdingNote(p.holding_days_est)}</div>
        </div>
      </div>` : "";

  return `
    <div class="detail-panel">
      ${tradePlanHtml}

      <div class="detail-grid detail-grid-4">
        <div class="detail-block">
          <h4>テクニカル指標</h4>
          ${kv("RSI",           ts.rsi        ? ts.rsi.toFixed(1) : "—")}
          ${kv("MACD>Signal",   ts.macd_above_sig ? "✅" : "❌")}
          ${kv("52w高値比",     ts.pct_from_high != null ? `${ts.pct_from_high.toFixed(1)}%` : "—")}
          ${p.direction === "SHORT"
            ? kv("ショート勢い指標", ts.short_momentum != null ? `${ts.short_momentum}/100` : "—")
            : kv("VCPスコア",       ts.vcp_score != null ? ts.vcp_score : "—")}
          ${p.direction !== "SHORT" ? kv("収縮ウェーブ", ts.contraction_count ?? "—") : ""}
          ${kv("出来高比率",    ts.volume_ratio ? `${ts.volume_ratio.toFixed(2)}x` : "—")}
          ${kv("Stage2",        ts.stage2_uptrend ? "✅" : "❌")}
        </div>

        <div class="detail-block">
          <h4>エントリー根拠</h4>
          <ul class="reason-list">${reasons || "<li>データなし</li>"}</ul>
          <h4 style="margin-top:12px">リスク要因</h4>
          <ul class="reason-list risks">${risks || "<li>特になし</li>"}</ul>
        </div>

        ${fundBlock}
        ${sectorBlock}
        ${_buildTakeProfitBlock(p)}
      </div>
      ${chartDiv}
      </div>
    </div>`;
}

// ── helpers ────────────────────────────────────────────────

function _hybridReason(p, isTP) {
  if (isTP) {
    // 利確モード: take_profit_signals を表示
    const signals = p.take_profit_signals || (p.technical_summary?.take_profit?.signals || []).join("、");
    return escHtml(signals) || "—";
  }
  // エントリーモード: entry_reasons の先頭2件を表示
  const reasons = p.technical_summary?.entry_reasons || [];
  if (reasons.length === 0) return "—";
  return reasons.slice(0, 2).map(r => escHtml(r)).join("　/　");
}

function _buildTakeProfitBlock(p) {
  const tpVerdict  = p.take_profit_verdict || (p.technical_summary?.take_profit?.verdict);
  const tpSignals  = p.take_profit_signals || (p.technical_summary?.take_profit?.signals || []).join("、");
  if (!tpVerdict || tpVerdict === "HOLD") return "";
  const label = verdictLabel(tpVerdict);
  const css   = verdictCss(tpVerdict);
  return `
    <div class="detail-block">
      <h4>利確シグナル</h4>
      ${kv("判定", `<span class="${css}" style="font-weight:700">${label}</span>`)}
      ${kv("理由", escHtml(tpSignals) || "—")}
    </div>`;
}

function _holdingBadge(days) {
  if (!days) return '<span class="hold-badge hold-unknown">—</span>';
  if (days <= 10) return `<span class="hold-badge hold-short">短期 ~${days}日</span>`;
  if (days <= 25) return `<span class="hold-badge hold-mid">中期 ~${days}日</span>`;
  return `<span class="hold-badge hold-long">ポジション ~${days}日</span>`;
}

function _holdingNote(days) {
  if (!days) return "";
  if (days <= 10) return "1〜2週間スウィング";
  if (days <= 25) return "2〜5週間スウィング";
  return "1〜2ヶ月ポジション";
}

function kv(label, value) {
  return `<div class="kv-row"><span class="kv-key">${label}</span><span class="kv-val">${value ?? "—"}</span></div>`;
}
function fmt(v) { return v != null ? Number(v).toFixed(2) : "—"; }
function escHtml(s) { return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

function verdictLabel(v) {
  const map = {
    BUY: "買い", WATCH: "様子見", "NO-BUY": "見送り",
    ENTRY_NOW: "今日エントリー", WAIT: "待機", PASSED: "通過済",
    SHORT_SELL: "売り", SHORT_WATCH: "ショート様子見",
    TAKE_PROFIT: "利確推奨", REDUCE: "一部利確",
    WATCH_EXIT: "出口注視", HOLD: "継続保有",
  };
  return map[v] || v || "—";
}
function verdictCss(v) {
  const map = {
    BUY: "verdict-buy", WATCH: "verdict-watch", "NO-BUY": "verdict-nobuy",
    ENTRY_NOW: "verdict-entry", WAIT: "verdict-wait", PASSED: "verdict-passed",
    SHORT_SELL: "verdict-short", SHORT_WATCH: "verdict-short-watch",
    TAKE_PROFIT: "verdict-short", REDUCE: "verdict-short-watch",
    WATCH_EXIT: "verdict-watch", HOLD: "verdict-buy",
  };
  return map[v] || "";
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
