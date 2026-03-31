/**
 * Tech picks table — signal-scanner-v5 ロジック由来のテクニカル重視ビュー
 */
import { renderCandlestick } from "../utils/charts.js";

const STAGE_LABEL = {
  0: { text: "不明",               css: "stage-0" },
  1: { text: "S1 ベース形成",       css: "stage-1" },
  2: { text: "S2 上昇トレンド",     css: "stage-2" },
  3: { text: "S3 天井圏",           css: "stage-3" },
  4: { text: "S4 下降トレンド",     css: "stage-4" },
};

export function renderTechPicksTable(container, picks, title, mode = "weekly") {
  const infoBanner = mode === "weekly" ? `
    <div class="picks-info-banner picks-info-banner--tech">
      <div class="pib-item">
        <span class="pib-icon">📡</span>
        <div>
          <div class="pib-label">週次テクニカルスキャンとは</div>
          <div class="pib-desc">16種のテクニカルシグナルをバックテストで検証し、<strong>勝率×信頼度</strong>でランキング。
          ファンダは考慮せず純粋な値動き・パターンのみで判定。</div>
        </div>
      </div>
      <div class="pib-divider"></div>
      <div class="pib-item">
        <span class="pib-icon">🔢</span>
        <div>
          <div class="pib-label">スコアの見方</div>
          <div class="pib-desc">
            <strong>信頼度</strong> = 勝率60% + RR25% + シグナル合流10% + Stage整合5%<br>
            <strong>平均勝率</strong> = 過去シグナルのバックテスト実績
          </div>
        </div>
      </div>
      <div class="pib-divider"></div>
      <div class="pib-item">
        <span class="pib-icon">🔄</span>
        <div>
          <div class="pib-label">更新タイミング</div>
          <div class="pib-desc">手動実行: <code>python3 pipeline/run_pipeline.py --tech-weekly</code><br>
          既存の価格データを使用（追加API不要・約5〜10分）</div>
        </div>
      </div>
    </div>` : `
    <div class="picks-info-banner picks-info-banner--tech-daily">
      <div class="pib-item">
        <span class="pib-icon">🔬</span>
        <div>
          <div class="pib-label">日次テクニカルとは</div>
          <div class="pib-desc">週次テクニカルピックの銘柄について<strong>当日の最新価格</strong>でシグナルを再確認。
          アクティブなシグナルが継続しているかを毎朝チェック。</div>
        </div>
      </div>
      <div class="pib-divider"></div>
      <div class="pib-item">
        <span class="pib-icon">📋</span>
        <div>
          <div class="pib-label">判定の見方</div>
          <div class="pib-desc">
            <span class="verdict-entry pib-badge">今日エントリー★</span> シグナル継続+RR≥2.0+信頼度高 &nbsp;
            <span class="verdict-buy pib-badge">エントリー</span> シグナル継続+RR≥1.5 &nbsp;
            <span class="verdict-watch pib-badge">様子見</span> RR維持だが当日シグナルなし
          </div>
        </div>
      </div>
      <div class="pib-divider"></div>
      <div class="pib-item">
        <span class="pib-icon">🔄</span>
        <div>
          <div class="pib-label">更新タイミング</div>
          <div class="pib-desc">毎朝7:00自動更新（--daily-only と同時実行）<br>
          手動: <code>python3 pipeline/run_pipeline.py --tech-daily</code></div>
        </div>
      </div>
    </div>`;

  if (!picks.length) {
    const msg = mode === "weekly"
      ? `テクニカルスキャン未実行 — <code>python3 pipeline/run_pipeline.py --tech-weekly</code> を実行してください`
      : `本日のテクニカルデータなし — 毎朝7:00に自動更新されます`;
    container.innerHTML = `
      <div class="section-title">${title}</div>
      ${infoBanner}
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

    // シグナルタグ（上位3件）
    const sigList  = (p.signals || []).slice(0, 3).map(s =>
      `<span class="sig-tag">${s.label}</span>`).join("");

    // 日次モード用の判定列
    const verdictCell = mode === "daily" ? `
      <td>$${fmt(p.current_price)}</td>
      <td class="${_verdictCss(p.daily_verdict)}">${_verdictLabel(p.daily_verdict)}</td>
      <td>${fmt(p.adjusted_rr)}</td>` : ``;

    return `
      <tr data-idx="${i}" class="pick-row">
        <td class="ticker-cell">${p.ticker}</td>
        <td>${dirBadge}</td>
        <td><span class="stage-badge ${stageMeta.css}">${stageMeta.text}</span></td>
        <td>
          <div class="conf-bar-wrap">
            <div class="conf-bar ${confCls}" style="width:${confPct}%"></div>
          </div>
          <span class="conf-val">${confPct}%</span>
        </td>
        <td class="wr-cell">${wrPct}%</td>
        <td>${fmt(p.risk_reward)}</td>
        <td>$${fmt(p.entry_price)}</td>
        <td>$${fmt(p.stop_price)}</td>
        <td>$${fmt(p.tp1_price)}</td>
        <td>$${fmt(p.target_price)}</td>
        <td class="sig-tags-cell">${sigList}</td>
        ${verdictCell}
      </tr>
      <tr class="detail-row" id="tdetail-${i}" style="display:none">
        <td colspan="100">${_buildDetailPanel(p, i)}</td>
      </tr>`;
  }).join("");

  const dailyHeaders = mode === "daily"
    ? `<th>現在値</th><th>判定</th><th>現RR</th>` : ``;

  container.innerHTML = `
    <div class="section-title">${title}
      <span class="tech-count-badge">${picks.length}件</span>
    </div>
    ${infoBanner}
    <div class="picks-table-wrap">
      <table>
        <thead>
          <tr>
            <th>銘柄</th><th>方向</th><th>Stage</th>
            <th>信頼度</th><th>勝率</th><th>RR</th>
            <th>エントリー</th><th>SL</th><th>TP1</th><th>TP2</th>
            <th>シグナル</th>
            ${dailyHeaders}
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
        if (picks[idx].chart_data) {
          const p = picks[idx];
          setTimeout(() => renderCandlestick(`tchart-${idx}`, p.chart_data,
            { entry: p.entry_price, stop: p.stop_price, target: p.target_price }), 50);
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

  const chartDiv = p.chart_data
    ? `<div id="tchart-${idx}" style="height:280px;background:#0f172a;border-radius:6px;margin-top:12px"></div>`
    : "";

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
      <h4>検出シグナル（バックテスト勝率付き）</h4>
      ${sigRows || "<div style='color:var(--text-muted)'>シグナルなし</div>"}
      ${p.active_signals ? `
      <h4 style="margin-top:14px">本日アクティブなシグナル</h4>
      <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:6px">${activeSignals}</div>` : ""}
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


// ── helpers ────────────────────────────────────────────────

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
function kv(label, value) {
  return `<div class="kv-row"><span class="kv-key">${label}</span><span class="kv-val">${value ?? "—"}</span></div>`;
}
function fmt(v) { return v != null ? Number(v).toFixed(2) : "—"; }
