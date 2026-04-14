/**
 * Tech picks table — signal-scanner-v5 ロジック由来のテクニカル重視ビュー
 */
import { renderCandlestick } from "../utils/charts.js";
import { apiFetch } from "../utils/api.js";

// market health cache（セクター動向表示用）
let _mhCache = null;
function _getMarketHealth() {
  if (!_mhCache) _mhCache = apiFetch("/api/market-health");
  return _mhCache;
}

const STAGE_LABEL = {
  0: { text: "不明",               css: "stage-0" },
  1: { text: "S1 ベース形成",       css: "stage-1" },
  2: { text: "S2 上昇トレンド",     css: "stage-2" },
  3: { text: "S3 天井圏",           css: "stage-3" },
  4: { text: "S4 下降トレンド",     css: "stage-4" },
};

export function renderTechPicksTable(container, picks, title, mode = "weekly") {
  const isLogic4 = mode === "logic4" || mode === "logic2";
  const isBreakout = mode === "logic3";
  const isDailyMode = mode === "daily" || isLogic4 || isBreakout;

  if (!picks.length) {
    const msg = mode === "weekly"
      ? `テクニカルスキャン未実行 — <code>python3 pipeline/run_pipeline.py --tech-weekly</code> を実行してください`
      : `本日のテクニカルデータなし — 毎朝7:00に自動更新されます`;
    container.innerHTML = `
      <div class="section-title">${title}</div>
      <div class="empty-state">${msg}</div>`;
    return;
  }

  const rows = picks.map((p, i) => {
    const stageMeta = STAGE_LABEL[p.stage] || STAGE_LABEL[0];
    const dirBadge  = p.direction === "SHORT"
      ? `<span class="dir-badge dir-short">▼SHORT</span>`
      : `<span class="dir-badge dir-long">▲LONG</span>`;
    const confPct  = ((p.confidence || 0) * 100).toFixed(0);
    const confCls  = (p.confidence || 0) >= 0.72 ? "conf-high"
                   : (p.confidence || 0) >= 0.62 ? "conf-mid" : "conf-low";
    const wrPct    = ((p.avg_win_rate || 0) * 100).toFixed(0);

    // シグナルタグ: ロジック４はactive_signals（文字列配列）、他はsignals（オブジェクト配列）
    const sigList = (isLogic4 || isBreakout)
      ? (p.active_signals || []).slice(0, 3).map(s => `<span class="sig-tag">${s}</span>`).join("")
      : (p.signals || []).slice(0, 3).map(s => `<span class="sig-tag">${s.label}</span>`).join("");

    const holdBadge = _holdingBadge(p.holding_days_est);

    const verdictCell = isDailyMode ? `
      <td class="${(isLogic4 || isBreakout) ? _verdictCssLogic4(p.daily_verdict) : _verdictCss(p.daily_verdict)}">${p.daily_verdict || "—"}</td>` : ``;

    // ロジック４はSTAGE・勝率列を非表示
    const stageCell = (isLogic4 || isBreakout) ? `` : `<td><span class="stage-badge ${stageMeta.css}">${stageMeta.text}</span></td>`;
    const wrCell    = (isLogic4 || isBreakout) ? `` : `<td class="wr-cell">${wrPct}%</td>`;

    return `
      <tr data-idx="${i}" class="pick-row">
        <td class="ticker-cell">${p.ticker}</td>
        <td>${dirBadge}</td>
        ${verdictCell}
        <td>${holdBadge}</td>
        ${stageCell}
        <td>
          <div class="conf-bar-wrap">
            <div class="conf-bar ${confCls}" style="width:${confPct}%"></div>
          </div>
          <span class="conf-val">${confPct}%</span>
        </td>
        ${wrCell}
        <td>${fmt(p.risk_reward)}</td>
        <td class="sig-tags-cell">${sigList}</td>
        ${(isLogic4 || isBreakout) ? `<td>${p.sector || "—"}</td>` : ""}
      </tr>
      <tr class="detail-row" id="tdetail-${i}" style="display:none">
        <td colspan="100">${isBreakout ? _buildDetailPanelBreakout(p, i) : isLogic4 ? _buildDetailPanelLogic4(p, i) : _buildDetailPanel(p, i)}</td>
      </tr>`;
  }).join("");

  const verdictHeader = isDailyMode ? `<th>判定</th>` : ``;
  const stageHeader   = (isLogic4 || isBreakout) ? `` : `<th>Stage</th>`;
  const wrHeader      = (isLogic4 || isBreakout) ? `` : `<th>勝率</th>`;

  container.innerHTML = `
    <div class="section-title">${title}
      <span class="tech-count-badge">${picks.length}件</span>
    </div>
    <div class="picks-table-wrap">
      <table>
        <thead>
          <tr>
            <th>銘柄</th><th>方向</th>${verdictHeader}<th>保有期間</th>${stageHeader}
            <th>信頼度</th>${wrHeader}<th>RR</th>
            <th>シグナル</th>${(isLogic4 || isBreakout) ? "<th>セクター</th>" : ""}
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;

  container.querySelectorAll(".pick-row").forEach(row => {
    row.addEventListener("click", () => {
      const idx    = row.dataset.idx;
      const detail = container.querySelector(`#tdetail-${idx}`);
      const isOpen = detail.style.display !== "none";
      container.querySelectorAll(".detail-row").forEach(r => r.style.display = "none");
      if (!isOpen) {
        detail.style.display = "table-row";
        const p = picks[idx];

        // チャート
        apiFetch(`/api/chart/${p.ticker}?days=180`).then(chartResp => {
          if (chartResp && chartResp.data && chartResp.data.length > 0) {
            renderCandlestick(`tchart-${idx}`, chartResp.data, {
              entry:  p.entry_price,
              stop:   p.stop_price,
              tp1:    p.tp1_price,
              target: p.target_price,
            });
          }
        }).catch(() => {});

        // セクター動向
        const sectorSlot = detail.querySelector(`#tsector-slot-${idx}`);
        if (sectorSlot && p.sector) {
          _getMarketHealth().then(mh => {
            if (!mh.sector_scores) return;
            const score   = mh.sector_scores[p.sector];
            const history = mh.sector_history?.[p.sector] || [];
            const ma      = mh.sector_ma?.[p.sector];
            if (score == null) return;
            const color  = score >= 50 ? "var(--green)" : score >= 20 ? "var(--yellow)" : "var(--red)";
            const maDiff = ma != null ? (score - ma).toFixed(1) : null;
            const spark  = _sectorSparkline(history.map(h => h.score));
            const maHtml = maDiff != null
              ? `<div class="kv-row"><span class="kv-key">20日MA比</span><span class="kv-val" style="color:${parseFloat(maDiff)>=0?'var(--green)':'var(--red)'}">${parseFloat(maDiff)>=0?"+":""}${maDiff}pp</span></div>`
              : "";
            sectorSlot.innerHTML = `
              <div class="kv-row"><span class="kv-key">アップトレンド比率</span><span class="kv-val" style="color:${color}">${score.toFixed(1)}%</span></div>
              ${maHtml}
              ${spark ? `<div style="margin-top:6px">${spark}</div>` : ""}`;
          }).catch(() => {});
        }
      }
    });
  });
}


function _buildDetailPanel(p, idx) {
  const stageMeta = STAGE_LABEL[p.stage] || STAGE_LABEL[0];
  const isShort   = p.direction === "SHORT";
  const rr1 = p.entry_price && p.stop_price && p.tp1_price
    ? Math.abs((p.tp1_price - p.entry_price) / (p.entry_price - p.stop_price)).toFixed(2)
    : "1.50";

  const sigRows = (p.signals || []).map(s => `
    <div class="tech-sig-row">
      <span class="sig-tag sig-tag--lg">${s.label}</span>
      <span class="tech-sig-wr">勝率 ${((s.win_rate || 0)*100).toFixed(0)}%</span>
      <span class="tech-sig-n">N=${s.n || "?"}</span>
      <div class="tech-sig-bar-wrap">
        <div class="tech-sig-bar" style="width:${((s.win_rate||0)*100).toFixed(0)}%"></div>
      </div>
    </div>`).join("");

  const activeSignals = (p.active_signals || []).map(s =>
    `<span class="sig-tag sig-tag--active">${s}</span>`).join("") || "—";

  const chartDiv = `<div id="tchart-${idx}" class="pick-chart-container"></div>`;

  return `
<div class="detail-panel">
  <!-- トレードプラン -->
  <div class="trade-plan-row">
    <div class="tp-box tp-entry">
      <div class="tp-label">エントリー</div>
      <div class="tp-val">$${fmt(p.entry_price)}</div>
    </div>
    <div class="tp-arrow">${isShort ? "▼" : "▲"}</div>
    <div class="tp-box tp-sl">
      <div class="tp-label">SL（損切り）</div>
      <div class="tp-val tp-val-red">$${fmt(p.stop_price)}</div>
      <div class="tp-sub">ATR×2.0</div>
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
      <div class="tp-sub">RR ${fmt(p.risk_reward)}R</div>
    </div>
    <div class="tp-sep"></div>
    <div class="tp-box" style="border-color:rgba(99,102,241,.3)">
      <div class="tp-label">ATRボラ</div>
      <div class="tp-val" style="font-size:1.2rem">${p.atr_pct ? p.atr_pct.toFixed(1)+"%" : "—"}</div>
      <div class="tp-sub">日次 ATR / 価格</div>
    </div>
  </div>

  <div class="detail-grid">
    <!-- シグナル詳細 -->
    <div class="detail-block" style="flex:2;min-width:260px">
      <h4>Stage A — 準備シグナル（バックテスト勝率付き）</h4>
      ${sigRows || "<div style='color:var(--text-muted)'>シグナルなし</div>"}
      ${p.active_signals && p.active_signals.length ? `
      <h4 style="margin-top:14px">本日アクティブ <span style="font-size:.75rem;color:var(--text-muted)">（Stage A継続中）</span></h4>
      <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:6px">${activeSignals}</div>` : `
      <div style="margin-top:10px;font-size:.78rem;color:var(--text-muted)">本日 Stage A シグナルなし（様子見）</div>`}

      ${(() => {
        const stageB = p.stage_b_signals || [];
        if (!stageB.length) return `
          <h4 style="margin-top:14px">Stage B — 転換確認 <span style="font-size:.75rem;color:var(--text-muted)">（待機中）</span></h4>
          <div style="font-size:.78rem;color:var(--text-muted);margin-top:6px">確認シグナル未検出 — リテスト完了・ローソク転換パターン待ち</div>`;
        const STAGE_B_LABELS = {
          BULLISH_ENGULFING: "陽線包み足", HAMMER: "ハンマー足",
          MORNING_STAR: "三川明けの明星", HIGHER_HIGHS_3D: "高値3日切り上げ",
          RETEST_COMPLETE: "リテスト完了", BEARISH_ENGULFING: "陰線包み足",
          SHOOTING_STAR: "シューティングスター", EVENING_STAR: "三川宵の明星",
          LOWER_LOWS_3D: "安値3日切り下げ", VOLUME_SURGE: "出来高急増",
        };
        const badges = stageB.map(s => {
          const lbl = STAGE_B_LABELS[s] || s;
          const isConfirm = s !== "VOLUME_SURGE";
          return `<span class="sig-tag sig-tag--stageb${isConfirm ? ' sig-tag--stageb-confirm' : ''}">${lbl}</span>`;
        }).join("");
        return `
          <h4 style="margin-top:14px">Stage B — 転換確認 ✅ <span style="font-size:.75rem;color:var(--green)">（エントリー条件充足）</span></h4>
          <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:6px">${badges}</div>`;
      })()}
    </div>

    <!-- テクニカル指標 -->
    <div class="detail-block">
      <h4>テクニカル指標</h4>
      ${kv("RSI",       p.rsi ? p.rsi.toFixed(1) : "—")}
      ${kv("RR",        p.risk_reward ? p.risk_reward.toFixed(2) : "—")}
      ${kv("平均勝率",  p.avg_win_rate ? ((p.avg_win_rate)*100).toFixed(1)+"%" : "—")}
      ${kv("信頼度スコア", p.confidence ? ((p.confidence)*100).toFixed(1)+"%" : "—")}
      ${kv("Minervini Stage", `<span class="stage-badge ${(STAGE_LABEL[p.stage]||STAGE_LABEL[0]).css}">${(STAGE_LABEL[p.stage]||STAGE_LABEL[0]).text}</span>`)}
      ${kv("ATRボラ",   p.atr_pct ? p.atr_pct.toFixed(2)+"%" : "—")}
    </div>

    <!-- セクター動向 -->
    ${p.sector ? `
    <div class="detail-block">
      <h4>セクター動向 — ${p.sector}</h4>
      <div id="tsector-slot-${idx}" style="min-height:40px">
        <div style="color:var(--text-muted);font-size:.78rem">読み込み中...</div>
      </div>
    </div>` : ""}

    <!-- スコア説明 -->
    <div class="detail-block">
      <h4>スコア算出ロジック</h4>
      <div class="tech-formula">
        <div class="tf-row"><span class="tf-k">勝率（60%）</span><span class="tf-v">${p.avg_win_rate ? ((p.avg_win_rate)*100).toFixed(0)+"%" : "—"}</span></div>
        <div class="tf-row"><span class="tf-k">RR品質（25%）</span><span class="tf-v">${p.risk_reward ? (Math.min(p.risk_reward/3,1)*100).toFixed(0)+"pt" : "—"}</span></div>
        <div class="tf-row"><span class="tf-k">シグナル合流（10%）</span><span class="tf-v">${(p.signals||[]).length}件</span></div>
        <div class="tf-row"><span class="tf-k">Stage整合（5%）</span><span class="tf-v">${(STAGE_LABEL[p.stage]||STAGE_LABEL[0]).text}</span></div>
        <div class="tf-total">信頼度 = <strong>${p.confidence ? ((p.confidence)*100).toFixed(1)+"%" : "—"}</strong></div>
      </div>
      <div style="font-size:.7rem;color:var(--text-muted);margin-top:8px;line-height:1.5">
        ※ファンダメンタルは考慮しない純テクニカル判定<br>
        ※SL/TP は ATR×2.0 / ATR×4.0 で自動計算
      </div>
    </div>
  </div>
  ${chartDiv}
</div>`;
}


// ── ロジック４専用 詳細パネル ─────────────────────────────────

function _buildDetailPanelBreakout(p, idx) {
  const rr1 = p.entry_price && p.stop_price && p.tp1_price
    ? Math.abs((p.tp1_price - p.entry_price) / (p.entry_price - p.stop_price)).toFixed(2)
    : "2.00";

  const activeSignals = (p.active_signals || []).map(s =>
    `<span class="sig-tag sig-tag--active">${s}</span>`).join("") || "—";

  const chartDiv = `<div id="tchart-${idx}" class="pick-chart-container"></div>`;

  const boConfirmed = p.breakout_confirmed;
  const volRatio = p.breakout_volume_ratio || 0;
  const dist = p.distance_from_pivot_pct;
  const distBadge = dist != null
    ? (dist > 0 ? `<span style="color:var(--accent-green)">+${dist.toFixed(1)}% (ブレイクアウト済)</span>`
                 : `<span style="color:var(--accent-yellow)">${Math.abs(dist).toFixed(1)}% 手前</span>`)
    : "N/A";

  const volBadge = volRatio >= 2.0 ? `<span style="color:var(--accent-green);font-weight:bold">${volRatio.toFixed(1)}x</span>`
    : volRatio >= 1.5 ? `<span style="color:var(--accent-green)">${volRatio.toFixed(1)}x</span>`
    : volRatio > 0 ? `<span style="color:var(--text-muted)">${volRatio.toFixed(1)}x</span>`
    : `<span style="color:var(--text-muted)">未確認</span>`;

  return `
  <div class="detail-panel" style="display:flex;flex-wrap:wrap;gap:16px;padding:10px 6px">
    ${chartDiv}
    <div class="detail-block" style="flex:1;min-width:180px">
      <h4>ベースパターン</h4>
      <div class="kv-row"><span class="kv-key">パターン</span><span class="kv-val"><span class="sig-tag sig-tag--active">${p.base_pattern || "—"}</span></span></div>
      <div class="kv-row"><span class="kv-key">ベース期間</span><span class="kv-val">${p.base_length || "—"}日</span></div>
      <div class="kv-row"><span class="kv-key">ベース深さ</span><span class="kv-val">${p.base_depth_pct != null ? p.base_depth_pct.toFixed(1) + "%" : "—"}</span></div>
      <div class="kv-row"><span class="kv-key">ピボット</span><span class="kv-val">$${p.pivot_price || "—"}</span></div>

      <h4 style="margin-top:10px">ブレイクアウト状況</h4>
      <div class="kv-row"><span class="kv-key">ピボットからの距離</span><span class="kv-val">${distBadge}</span></div>
      <div class="kv-row"><span class="kv-key">出来高倍率</span><span class="kv-val">${volBadge}</span></div>
      <div class="kv-row"><span class="kv-key">確認</span><span class="kv-val">${boConfirmed ? '<span style="color:var(--accent-green);font-weight:bold">確認済</span>' : '<span style="color:var(--accent-yellow)">未確認</span>'}</span></div>
    </div>

    <div class="detail-block" style="flex:2;min-width:260px">
      <h4>エントリー根拠</h4>
      <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:14px">${activeSignals}</div>

      <h4>テクニカル指標</h4>
      <div class="kv-row"><span class="kv-key">RSI</span><span class="kv-val">${p.rsi != null ? p.rsi.toFixed(0) : "—"}</span></div>
      <div class="kv-row"><span class="kv-key">ATR</span><span class="kv-val">${p.atr != null ? "$" + p.atr.toFixed(2) : "—"}</span></div>
      <div class="kv-row"><span class="kv-key">パーフェクトオーダー</span><span class="kv-val">${p.perfect_order === "full" ? '<span style="color:var(--accent-green)">完全成立</span>' : '<span style="color:var(--accent-yellow)">準成立</span>'}</span></div>
      <div class="kv-row"><span class="kv-key">ダウ理論</span><span class="kv-val">${p.dow_trend || "—"}</span></div>
    </div>

    <div class="detail-block" style="flex:1;min-width:180px">
      <h4>R:R プロファイル</h4>
      <div class="kv-row"><span class="kv-key">エントリー</span><span class="kv-val">$${p.entry_price}</span></div>
      <div class="kv-row"><span class="kv-key">ストップ</span><span class="kv-val err-text">$${p.stop_price}</span></div>
      <div class="kv-row"><span class="kv-key">TP1 (メジャードムーブ)</span><span class="kv-val ok-text">$${p.tp1_price}</span></div>
      <div class="kv-row"><span class="kv-key">TP2 (1.5倍)</span><span class="kv-val ok-text">$${p.target_price}</span></div>
      <div class="kv-row"><span class="kv-key">R:R (TP1)</span><span class="kv-val">${rr1}</span></div>
      <div class="kv-row"><span class="kv-key">想定保有</span><span class="kv-val">${p.holding_days_est || "—"}日</span></div>
    </div>
  </div>`;
}

function _buildDetailPanelLogic4(p, idx) {
  const isShort = p.direction === "SHORT";
  const rr1 = p.entry_price && p.stop_price && p.tp1_price
    ? Math.abs((p.tp1_price - p.entry_price) / (p.entry_price - p.stop_price)).toFixed(2)
    : "1.50";

  const activeSignals = (p.active_signals || []).map(s =>
    `<span class="sig-tag sig-tag--active">${s}</span>`).join("") || "—";

  const chartDiv = `<div id="tchart-${idx}" class="pick-chart-container"></div>`;

  // サポートまでの距離バッジ
  const distBadge = p.price_to_support_pct != null
    ? `<span style="padding:2px 8px;border-radius:4px;font-size:.75rem;font-weight:700;background:${p.price_to_support_pct<=3?'rgba(16,185,129,.2)':'rgba(245,158,11,.2)'};color:${p.price_to_support_pct<=3?'#6ee7b7':'#fbbf24'}">${p.price_to_support_pct.toFixed(1)}% above support</span>`
    : "—";

  const h4Badge = p.h4_structure
    ? `<span style="padding:2px 8px;border-radius:4px;font-size:.75rem;font-weight:700;background:${p.h4_structure==='bullish'?'rgba(16,185,129,.2)':p.h4_structure==='bearish'?'rgba(239,68,68,.2)':'rgba(100,116,139,.2)'};color:${p.h4_structure==='bullish'?'#6ee7b7':p.h4_structure==='bearish'?'#fca5a5':'#94a3b8'}">${p.h4_structure}</span>`
    : "—";

  return `
<div class="detail-panel">
  <!-- トレードプラン -->
  <div class="trade-plan-row">
    <div class="tp-box tp-entry">
      <div class="tp-label">エントリー</div>
      <div class="tp-val">$${fmt(p.entry_price)}</div>
    </div>
    <div class="tp-arrow">${isShort ? "▼" : "▲"}</div>
    <div class="tp-box tp-sl">
      <div class="tp-label">SL（損切り）</div>
      <div class="tp-val tp-val-red">$${fmt(p.stop_price)}</div>
      <div class="tp-sub">ATR×2.0</div>
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
      <div class="tp-sub">RR ${fmt(p.risk_reward)}R</div>
    </div>
    <div class="tp-sep"></div>
    <div class="tp-box" style="border-color:rgba(99,102,241,.3)">
      <div class="tp-label">ATRボラ</div>
      <div class="tp-val" style="font-size:1.2rem">${p.atr ? (p.atr / (p.entry_price||1) * 100).toFixed(1)+"%" : "—"}</div>
      <div class="tp-sub">日次 ATR / 価格</div>
    </div>
  </div>

  <div class="detail-grid">
    <!-- エントリー根拠 -->
    <div class="detail-block" style="flex:2;min-width:260px">
      <h4>エントリー根拠（サポート分析）</h4>
      <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:14px">${activeSignals}</div>

      <h4 style="margin-top:4px">${p.h4_trigger !== undefined ? '4H インデイタイム確認' : '4H/1H インデイタイム確認'}</h4>
      <div class="kv-row"><span class="kv-key">サポートまでの距離</span><span class="kv-val">${distBadge}</span></div>
      <div class="kv-row"><span class="kv-key">4H構造</span><span class="kv-val">${h4Badge}</span></div>
      ${p.h4_trigger !== undefined
        ? `<div class="kv-row"><span class="kv-key">4Hトリガー</span><span class="kv-val">${p.h4_trigger ? `<span class="sig-tag sig-tag--active">${p.h4_trigger}</span>` : '<span style="color:var(--text-muted)">未検出（サポート接近待ち）</span>'}</span></div>`
        : `<div class="kv-row"><span class="kv-key">1Hトリガー</span><span class="kv-val">${p.h1_trigger ? `<span class="sig-tag sig-tag--active">${p.h1_trigger}</span>` : '<span style="color:var(--text-muted)">未検出（サポート接近待ち）</span>'}</span></div>`
      }
      ${p.trigger_bonus > 0 ? `<div class="kv-row"><span class="kv-key">トリガーボーナス</span><span class="kv-val"><span style="color:var(--accent-green);font-weight:bold">+${(p.trigger_bonus * 100).toFixed(0)}%</span></span></div>` : ''}
      ${p.h4_triggers_all && p.h4_triggers_all.length > 1 ? `<div class="kv-row"><span class="kv-key">検出トリガー(全)</span><span class="kv-val">${p.h4_triggers_all.map(t => `<span class="sig-tag sig-tag--active">${t}</span>`).join(' ')}</span></div>` : ''}
      ${p.chart_pattern ? `<div class="kv-row"><span class="kv-key">チャートパターン</span><span class="kv-val">${p.chart_pattern.split(', ').map(cp => `<span class="sig-tag sig-tag--active" style="background:var(--accent-blue,#3b82f6);color:#fff">${cp}</span>`).join(' ')}</span></div>` : ''}
    </div>

    <!-- テクニカル指標 -->
    <div class="detail-block">
      <h4>テクニカル指標</h4>
      ${kv("セクター",      p.sector || "—")}
      ${kv("RSI",          p.rsi ? p.rsi.toFixed(1) : "—")}
      ${kv("RR",           p.risk_reward ? p.risk_reward.toFixed(2) : "—")}
      ${kv("サポート価格",  p.support_price ? "$"+fmt(p.support_price) : "—")}
      ${kv("コンフルエンス", p.confluence ? p.confluence+"件" : "—")}
      ${kv("レジサポ転換",  p.reji_sapo || "—")}
      ${kv("ダウ理論",      p.dow_trend || "—")}
      ${kv("3ヶ月騰落率",   p.perf_3m != null ? (p.perf_3m > 0 ? "+" : "")+p.perf_3m.toFixed(1)+"%" : "—")}
    </div>

    <!-- セクター動向 -->
    ${p.sector ? `
    <div class="detail-block">
      <h4>セクター動向 — ${p.sector}</h4>
      <div id="tsector-slot-${idx}" style="min-height:40px">
        <div style="color:var(--text-muted);font-size:.78rem">読み込み中...</div>
      </div>
    </div>` : ""}

    <!-- スコア説明 -->
    <div class="detail-block">
      <h4>信頼度の根拠</h4>
      <div class="tech-formula">
        <div class="tf-row"><span class="tf-k">基本スコア</span><span class="tf-v">${p.reji_sapo==="confirmed"?"レジサポ確認（+25pt）":"通常押し目"}</span></div>
        <div class="tf-row"><span class="tf-k">RR品質</span><span class="tf-v">${p.risk_reward ? p.risk_reward.toFixed(2)+"R" : "—"}</span></div>
        <div class="tf-row"><span class="tf-k">ボーナスフラグ</span><span class="tf-v">${[p.rsi_flag?"RSI":"", p.macd_div_flag?"MACDダイバ":"", p.fib_confluence?"Fib":""].filter(Boolean).join(", ") || "なし"}</span></div>
        <div class="tf-total">信頼度 = <strong>${p.confidence ? ((p.confidence)*100).toFixed(1)+"%" : "—"}</strong></div>
      </div>
      <div style="font-size:.7rem;color:var(--text-muted);margin-top:8px;line-height:1.5">
        ※ファンダメンタルは考慮しない純テクニカル判定<br>
        ※SL = サポート×0.99 または サポート−ATR
      </div>
    </div>
  </div>
  ${chartDiv}
</div>`;
}


// ── helpers ────────────────────────────────────────────────

function _holdingBadge(days) {
  if (!days) return '<span class="hold-badge hold-unknown">—</span>';
  if (days <= 10) return `<span class="hold-badge hold-short">短期 ~${days}日</span>`;
  if (days <= 25) return `<span class="hold-badge hold-mid">中期 ~${days}日</span>`;
  return `<span class="hold-badge hold-long">ポジション ~${days}日</span>`;
}

function _sectorSparkline(scores) {
  if (!scores || scores.length < 2) return "";
  const w = 120, h = 28;
  const min = Math.min(...scores), max = Math.max(...scores);
  const range = max - min || 1;
  const pts = scores.map((v, i) => {
    const x = (i / (scores.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return `<svg width="${w}" height="${h}" style="display:block">
    <polyline points="${pts}" fill="none" stroke="var(--blue)" stroke-width="1.5" opacity=".7"/>
  </svg>`;
}

function _verdictLabel(v) {
  const map = {
    STRONG_BUY: "今日エントリー★", STRONG_SELL: "今日ショート★",
    BUY: "エントリー", SELL: "ショートエントリー",
    WATCH: "様子見", WAIT: "待機", PASSED: "通過済",
  };
  return map[v] || v || "—";
}
function _verdictCss(v) {
  const map = {
    STRONG_BUY: "verdict-entry", STRONG_SELL: "verdict-short",
    BUY: "verdict-buy", SELL: "verdict-short-watch",
    WATCH: "verdict-watch", WAIT: "verdict-wait", PASSED: "verdict-passed",
  };
  return map[v] || "";
}
function _verdictCssLogic4(v) {
  if (v === "最優先候補")    return "verdict-entry";
  if (v === "サポート接近中") return "verdict-buy";
  if (v === "押し目待ち")    return "verdict-passed";
  return "";
}
function kv(label, value) {
  return `<div class="kv-row"><span class="kv-key">${label}</span><span class="kv-val">${value ?? "—"}</span></div>`;
}
function fmt(v) { return v != null ? Number(v).toFixed(2) : "—"; }
