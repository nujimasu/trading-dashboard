/**
 * 保有ポジション管理ビュー（💼 保有）
 *
 * - オープン/クローズ済みのタブ切替
 * - 新規追加フォーム
 * - 各ポジションの詳細展開（決済 / 編集 / 日誌）
 */
import { apiFetch } from "../utils/api.js";

const POST_OPTS    = (body) => ({ method: "POST",   headers: {"Content-Type":"application/json"}, body: JSON.stringify(body) });
const PATCH_OPTS   = (body) => ({ method: "PATCH",  headers: {"Content-Type":"application/json"}, body: JSON.stringify(body) });
const DELETE_OPTS  = ()     => ({ method: "DELETE" });

let _state = { tab: "open", positions: [] };

export async function renderPositions(container) {
  container.innerHTML = `
    <div class="section-title">💼 保有ポジション</div>
    <div class="pos-controls">
      <div class="bt-tabs">
        <button class="bt-tab active" data-tab="open">オープン</button>
        <button class="bt-tab" data-tab="closed">決済済み</button>
      </div>
      <button class="pos-add-btn">＋ 新規追加</button>
    </div>
    <div class="pos-content" id="pos-content">
      <div class="loading"><div class="spinner"></div></div>
    </div>`;

  container.querySelectorAll(".bt-tab").forEach(btn => {
    btn.addEventListener("click", () => {
      _state.tab = btn.dataset.tab;
      container.querySelectorAll(".bt-tab").forEach(b =>
        b.classList.toggle("active", b.dataset.tab === _state.tab));
      _loadList(container);
    });
  });

  container.querySelector(".pos-add-btn").addEventListener("click", () => _openAddDialog(container));

  await _loadList(container);
}

async function _loadList(container) {
  const content = container.querySelector("#pos-content");
  content.innerHTML = `<div class="loading"><div class="spinner"></div></div>`;
  try {
    const resp = await apiFetch(`/api/positions?status=${_state.tab}`);
    _state.positions = resp.positions || [];
    if (_state.positions.length === 0) {
      content.innerHTML = `<div class="empty-state">${_state.tab === "open"
        ? "オープンポジションなし — 「＋新規追加」から記録できます"
        : "決済済みポジションはまだありません"}</div>`;
      return;
    }
    content.innerHTML = _state.positions.map((p, i) => _renderPosCard(p, i)).join("");
    _bindCardClicks(container);
  } catch (e) {
    content.innerHTML = `<div class="empty-state">読み込み失敗: ${e.message}</div>`;
  }
}

function _renderPosCard(p, idx) {
  const dirCss  = p.direction === "SHORT" ? "dir-short" : "dir-long";
  const dirText = p.direction === "SHORT" ? "▼SHORT"   : "▲LONG";

  let pnlBadge = "";
  if (p.status === "open") {
    const pnl = p.unrealized_pnl, pct = p.unrealized_pct;
    if (pnl != null && pct != null) {
      const cls = pnl >= 0 ? "pos-pnl-pos" : "pos-pnl-neg";
      pnlBadge = `<span class="pos-pnl ${cls}">${pnl >= 0 ? "+" : ""}$${pnl.toFixed(0)} (${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%)</span>`;
    } else {
      pnlBadge = `<span class="pos-pnl">未取得</span>`;
    }
  } else {
    const pnl = p.realized_pnl, pct = p.realized_pct;
    if (pnl != null && pct != null) {
      const cls = pnl >= 0 ? "pos-pnl-pos" : "pos-pnl-neg";
      pnlBadge = `<span class="pos-pnl ${cls}">${pnl >= 0 ? "+" : ""}$${pnl.toFixed(0)} (${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%)</span>`;
    }
  }

  const last = p.last_price != null ? `現値 $${(+p.last_price).toFixed(2)}` : "";
  const entry = p.entry_price != null ? `IN $${(+p.entry_price).toFixed(2)}` : "";
  const stop  = p.stop_price  != null ? `SL $${(+p.stop_price).toFixed(2)}`  : "";
  const tp1   = p.tp1_price   != null ? `TP1 $${(+p.tp1_price).toFixed(2)}`  : "";
  const tp2   = p.target_price!= null ? `TP2 $${(+p.target_price).toFixed(2)}` : "";

  return `
    <div class="pos-card" data-id="${p.id}" data-idx="${idx}">
      <div class="pos-card-main">
        <div class="pos-card-head">
          <span class="pick-ticker">${_esc(p.ticker)}</span>
          <span class="dir-badge ${dirCss}">${dirText}</span>
          ${p.source_logic ? `<span class="pos-source">${_esc(p.source_logic)}</span>` : ""}
        </div>
        ${pnlBadge}
      </div>
      <div class="pos-card-meta">
        <span>📅 ${_fmtDate(p.entry_date)}</span>
        <span>🪙 ${p.shares} 株</span>
        ${entry ? `<span>${entry}</span>` : ""}
        ${last ? `<span>${last}</span>` : ""}
        ${stop ? `<span class="pos-meta-sl">${stop}</span>` : ""}
        ${tp1 ? `<span class="pos-meta-tp">${tp1}</span>` : ""}
        ${tp2 ? `<span class="pos-meta-tp">${tp2}</span>` : ""}
      </div>
    </div>`;
}

function _bindCardClicks(container) {
  container.querySelectorAll(".pos-card").forEach(card => {
    card.addEventListener("click", (e) => {
      if (e.target.closest(".pos-detail")) return;
      _toggleDetail(container, card);
    });
  });
}

async function _toggleDetail(container, card) {
  const existing = card.nextElementSibling;
  const isOpen = existing && existing.classList.contains("pos-detail");
  container.querySelectorAll(".pos-detail").forEach(el => el.remove());
  container.querySelectorAll(".pos-card.expanded").forEach(el => el.classList.remove("expanded"));
  if (isOpen) return;

  const id = +card.dataset.id;
  card.classList.add("expanded");
  const detailEl = document.createElement("div");
  detailEl.className = "pos-detail";
  detailEl.innerHTML = `<div class="loading"><div class="spinner"></div></div>`;
  card.insertAdjacentElement("afterend", detailEl);

  const pos = _state.positions.find(p => p.id === id);
  let journal = [];
  try {
    const resp = await apiFetch(`/api/positions/${id}/journal`);
    journal = resp.entries || [];
  } catch (_) { journal = []; }

  detailEl.innerHTML = _renderDetail(pos, journal);
  _bindDetailActions(container, detailEl, pos);
}

function _renderDetail(p, journal) {
  const isOpen = p.status === "open";
  return `
    <div class="pos-detail-grid">
      <div class="pos-detail-block">
        <h4>ポジション詳細</h4>
        <div class="kv-row"><span class="kv-key">エントリー日</span><span class="kv-val">${_fmtDate(p.entry_date)}</span></div>
        <div class="kv-row"><span class="kv-key">エントリー価格</span><span class="kv-val">$${(+p.entry_price).toFixed(2)}</span></div>
        <div class="kv-row"><span class="kv-key">株数</span><span class="kv-val">${p.shares}</span></div>
        ${p.stop_price != null  ? `<div class="kv-row"><span class="kv-key">SL</span><span class="kv-val">$${(+p.stop_price).toFixed(2)}</span></div>` : ""}
        ${p.tp1_price != null   ? `<div class="kv-row"><span class="kv-key">TP1</span><span class="kv-val">$${(+p.tp1_price).toFixed(2)}</span></div>` : ""}
        ${p.target_price != null? `<div class="kv-row"><span class="kv-key">TP2</span><span class="kv-val">$${(+p.target_price).toFixed(2)}</span></div>` : ""}
        ${p.last_price != null  ? `<div class="kv-row"><span class="kv-key">最新終値</span><span class="kv-val">$${(+p.last_price).toFixed(2)}</span></div>` : ""}
        ${!isOpen ? `
          <div class="kv-row"><span class="kv-key">決済日</span><span class="kv-val">${_fmtDate(p.exit_date)}</span></div>
          <div class="kv-row"><span class="kv-key">決済価格</span><span class="kv-val">$${(+p.exit_price).toFixed(2)}</span></div>
          ${p.exit_reason ? `<div class="kv-row"><span class="kv-key">理由</span><span class="kv-val">${_esc(p.exit_reason)}</span></div>` : ""}
        ` : ""}
      </div>

      <div class="pos-detail-block">
        <h4>アクション</h4>
        ${isOpen ? `
          <div class="pos-actions">
            <button class="pos-btn pos-btn-edit"  data-action="edit">📝 SL/TP編集</button>
            <button class="pos-btn pos-btn-close" data-action="close">💰 決済</button>
            <button class="pos-btn pos-btn-del"   data-action="delete">🗑 取消</button>
          </div>` : `
          <div class="pos-actions">
            <button class="pos-btn pos-btn-del"   data-action="delete">🗑 削除</button>
          </div>`}
      </div>

      <div class="pos-detail-block pos-journal-block">
        <h4>📔 トレード日誌 (${journal.length})</h4>
        <div class="pos-journal-list">
          ${journal.length === 0 ? `<div style="color:var(--text-muted);font-size:.8rem">まだ記録がありません</div>` : ""}
          ${journal.map(j => `
            <div class="pos-journal-item">
              <div class="pos-journal-meta">
                <span class="pos-journal-type">${_esc(_journalTypeLabel(j.entry_type))}</span>
                <span class="pos-journal-date">${_fmtDateTime(j.created_at)}</span>
                <button class="pos-journal-del" data-jid="${j.id}" title="削除">×</button>
              </div>
              <div class="pos-journal-body">${_esc(j.body)}</div>
            </div>
          `).join("")}
        </div>
        <div class="pos-journal-add">
          <select class="pos-journal-type-sel">
            <option value="entry">エントリー時</option>
            <option value="management">保有中</option>
            <option value="exit">決済時</option>
            <option value="reflection">振り返り</option>
            <option value="note" selected>メモ</option>
          </select>
          <textarea class="pos-journal-textarea" rows="2" placeholder="メモを入力..."></textarea>
          <button class="pos-btn pos-btn-add">追加</button>
        </div>
      </div>
    </div>`;
}

function _bindDetailActions(container, detailEl, pos) {
  detailEl.querySelectorAll("[data-action]").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const action = btn.dataset.action;
      if (action === "edit")   await _onEdit(container, pos);
      else if (action === "close")  await _onClose(container, pos);
      else if (action === "delete") await _onDelete(container, pos);
    });
  });

  // 日誌追加
  const addBtn = detailEl.querySelector(".pos-btn-add");
  if (addBtn) {
    addBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const ta = detailEl.querySelector(".pos-journal-textarea");
      const sel = detailEl.querySelector(".pos-journal-type-sel");
      const body = (ta.value || "").trim();
      if (!body) return;
      try {
        await apiFetch(`/api/positions/${pos.id}/journal`, POST_OPTS({ body, entry_type: sel.value }));
        ta.value = "";
        await _refreshDetailOnly(container, pos.id);
      } catch (err) { alert("日誌追加失敗: " + err.message); }
    });
  }
  // 日誌削除
  detailEl.querySelectorAll(".pos-journal-del").forEach(b => {
    b.addEventListener("click", async (e) => {
      e.stopPropagation();
      const jid = +b.dataset.jid;
      if (!confirm("この日誌を削除しますか?")) return;
      try {
        await apiFetch(`/api/journal/${jid}`, DELETE_OPTS());
        await _refreshDetailOnly(container, pos.id);
      } catch (err) { alert("削除失敗: " + err.message); }
    });
  });
}

async function _refreshDetailOnly(container, posId) {
  const card = container.querySelector(`.pos-card[data-id="${posId}"]`);
  if (!card) return;
  // 一旦閉じて開き直す
  const detailEl = card.nextElementSibling;
  if (detailEl && detailEl.classList.contains("pos-detail")) detailEl.remove();
  card.classList.remove("expanded");
  await _toggleDetail(container, card);
}

// ── ダイアログ操作 ─────────────────────────────────────────────────
async function _onEdit(container, pos) {
  const sl  = prompt("新しい SL（空白でクリア）:", pos.stop_price ?? "");
  if (sl === null) return;
  const tp1 = prompt("新しい TP1（空白でクリア）:", pos.tp1_price ?? "");
  if (tp1 === null) return;
  const tp2 = prompt("新しい TP2（空白でクリア）:", pos.target_price ?? "");
  if (tp2 === null) return;
  try {
    await apiFetch(`/api/positions/${pos.id}`, PATCH_OPTS({
      stop_price:  sl  === "" ? null : +sl,
      tp1_price:   tp1 === "" ? null : +tp1,
      target_price: tp2 === "" ? null : +tp2,
    }));
    await _loadList(container);
  } catch (e) { alert("更新失敗: " + e.message); }
}

async function _onClose(container, pos) {
  const exitPrice = prompt(`決済価格を入力（${pos.ticker}）`, pos.last_price || "");
  if (exitPrice === null || exitPrice === "") return;
  const reason = prompt("決済理由（任意）:", "") || "";
  const presetHint = "ブレイクアウト, 押し目買い, スイング, デイトレ, オーバーナイト, レンジ, ニュース, 決算前, モメンタム追従, 逆張り";
  const existing = (pos.tags || []).join(", ");
  const tagsRaw = prompt(
    `タグ（カンマ区切り、空欄OK）\n例: ${presetHint}`,
    existing
  );
  const payload = {
    exit_price: +exitPrice,
    exit_reason: reason,
  };
  if (tagsRaw !== null) payload.tags = tagsRaw;  // null=キャンセル時は送らない
  try {
    await apiFetch(`/api/positions/${pos.id}/close`, POST_OPTS(payload));
    await _loadList(container);
  } catch (e) { alert("決済失敗: " + e.message); }
}

async function _onDelete(container, pos) {
  if (!confirm(`${pos.ticker} の記録を削除しますか?（取り戻せません）`)) return;
  try {
    await apiFetch(`/api/positions/${pos.id}`, DELETE_OPTS());
    await _loadList(container);
  } catch (e) { alert("削除失敗: " + e.message); }
}

function _openAddDialog(container) {
  const ticker = prompt("銘柄ティッカー (例: AAPL):", "");
  if (!ticker) return;
  const entry  = prompt("エントリー価格:", "");
  if (!entry) return;
  const shares = prompt("株数:", "");
  if (!shares) return;
  const stop   = prompt("SL（任意）:", "");
  const tp1    = prompt("TP1（任意）:", "");
  const tp2    = prompt("TP2（任意）:", "");

  apiFetch("/api/positions", POST_OPTS({
    ticker: ticker.trim().toUpperCase(),
    entry_price: +entry,
    shares: +shares,
    stop_price:  stop ? +stop : null,
    tp1_price:   tp1  ? +tp1  : null,
    target_price: tp2 ? +tp2  : null,
    direction: "LONG",
  })).then(() => _loadList(container))
    .catch(e => alert("追加失敗: " + e.message));
}

// ── helpers ────────────────────────────────────────────────────────
function _journalTypeLabel(t) {
  return ({
    entry: "エントリー", management: "保有中", exit: "決済",
    reflection: "振り返り", note: "メモ"
  })[t] || t;
}
function _fmtDate(s) {
  if (!s) return "—";
  return String(s).slice(0, 10);
}
function _fmtDateTime(s) {
  if (!s) return "—";
  return String(s).slice(0, 16).replace("T", " ");
}
function _esc(s) { return String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
