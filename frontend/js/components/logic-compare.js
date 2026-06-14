/**
 * 厳選押し目買い v1 / v2 比較ページ
 * 同じ「押し目買い」だが “出口の思想” が逆。違いを価格チャート図で可視化する。
 */
export function renderLogicCompare(container) {
  container.innerHTML = `
  <style>
    .lc-cap{font-size:.85rem;color:var(--text-muted);margin:10px 2px 0;line-height:1.55}
    .lc-cap b{color:var(--text-primary)}
    .lc-tablewrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
    @media (max-width:560px){
      .strategy-guide h2{font-size:1.12rem;line-height:1.4}
      .strategy-guide .guide-table{font-size:.8rem;min-width:520px}
      .strategy-guide .guide-table th,.strategy-guide .guide-table td{padding:6px 7px}
    }
  </style>
  <div class="strategy-guide" style="max-width:980px;margin:0 auto;padding:16px;">
    <h2 style="margin-bottom:6px">⚖️ 厳選押し目買い v1 vs v2 — 違いの早わかり</h2>
    <p style="color:var(--text-muted);margin-bottom:18px;">
      どちらも「上昇トレンドの押し目を買う」戦略ですが、<strong>出口（利確）の思想が正反対</strong>です。
      <strong style="color:#34d399">v1＝高値手前で早めに確定して“高勝率”</strong>、
      <strong style="color:#60a5fa">v2＝半分だけ確定して残りを伸ばし“利大損小”</strong>。
      入口（トリガーの取り方）も異なります。
    </p>

    <!-- ひとことサマリー -->
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px;margin-bottom:18px;">
      <div class="card" style="border-top:3px solid #34d399;">
        <div style="font-weight:800;color:#34d399;font-size:1.05rem">厳選押し目買い v1</div>
        <div style="color:var(--text-muted);font-size:.86rem;margin-top:4px">高勝率・利確早めタイプ（4H厳格トリガー）</div>
        <div style="margin-top:8px;font-size:.92rem;line-height:1.6">
          直近の<strong>高値手前で 2/3 を利確</strong>。残り 1/3 だけ 20日EMA でトレール。
          「<strong>近い高値で確実に取りにいく</strong>」ので勝率が高い一方、<strong>利益は高値で頭打ち</strong>。
        </div>
      </div>
      <div class="card" style="border-top:3px solid #60a5fa;">
        <div style="font-weight:800;color:#60a5fa;font-size:1.05rem">厳選押し目買い v2</div>
        <div style="color:var(--text-muted);font-size:.86rem;margin-top:4px">利大損小・伸ばすタイプ（v3確定版・実トレード1,713件分析）</div>
        <div style="margin-top:8px;font-size:.92rem;line-height:1.6">
          <strong>+1.5R で半分だけ利確</strong>し、残り半分を 20日EMA でトレールして伸ばす。
          勝率はやや落ちても <strong>1勝を大きく</strong>する。トレンド継続ランナー向け。
        </div>
      </div>
    </div>

    <!-- ★ 図：出口の違い（価格チャート2枚） -->
    <div class="card" style="margin-bottom:18px;">
      <h3>図解：同じ押し目エントリーでも “出口” がこう違う</h3>
      <p style="color:var(--text-muted);font-size:.85rem;margin:2px 0 12px 0;">
        どちらも損切りは同じ <strong style="color:#f87171">1R（エントリー〜SL）</strong>。
        利確の取り方だけが違います。
      </p>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px;">

        <!-- v1 panel -->
        <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:10px;">
          <div style="font-weight:700;color:#34d399;font-size:.92rem;margin-bottom:6px">v1：高値手前で 2/3 利確</div>
          ${_chart({
            target: { y: 55, label: '直近高値', color: '#9ca3af' },
            path: '40,92 78,118 110,151 150,120 190,82 218,58 255,78 300,112',
            entry: { x: 110, y: 151 },
            tp:    { x: 218, y: 58,  label: '③ 2/3利確' },
            exit:  { x: 300, y: 112, label: '残り1/3 手仕舞い' },
            capLine: 55,
          })}
          <div class="lc-cap">→ 直近高値で <b>2/3 を確定</b>。利益はこの高値で<b>頭打ち</b>になる代わりに <b>よく当たる</b>（高勝率）。</div>
        </div>

        <!-- v2 panel -->
        <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:10px;">
          <div style="font-weight:700;color:#60a5fa;font-size:.92rem;margin-bottom:6px">v2：+1.5Rで半分→残りを伸ばす</div>
          ${_chart({
            target: { y: 98, label: '+1.5R', color: '#34d399' },
            path: '40,120 80,140 105,152 140,128 175,98 215,80 270,55 330,40',
            entry: { x: 105, y: 152 },
            tp:    { x: 175, y: 98,  label: '③ 半分利確' },
            exit:  { x: 334, y: 40,  label: '残り半分を伸ばす ↑', up: true, anchor: 'end' },
            capLine: null,
          })}
          <div class="lc-cap">→ <b>+1.5Rで半分</b>を確定し、残り半分を 20日EMA トレールで <b>青天井に伸ばす</b>（1勝を大きく）。</div>
        </div>
      </div>
      <p style="color:var(--text-muted);margin-top:10px;font-size:.82rem;">
        ※ 図はイメージ。<span style="color:#60a5fa">青=エントリー</span> /
        <span style="color:#f87171">赤=損切り(1R)</span> /
        <span style="color:#34d399">緑=利確</span> /
        <span style="color:#f59e0b">橙=20日EMA</span>。
      </p>
    </div>

    <!-- 出口比較イメージ（勝率 vs 1勝の大きさ） -->
    <div class="card" style="margin-bottom:18px;">
      <h3>狙う形のイメージ：勝率 × 1勝の大きさ</h3>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;align-items:center;">
        <div>
          <div style="font-size:.82rem;color:var(--text-muted);margin-bottom:6px">勝ちやすさ（勝率）</div>
          ${_bar('v1', 86, '#34d399')}
          ${_bar('v2', 62, '#60a5fa')}
        </div>
        <div>
          <div style="font-size:.82rem;color:var(--text-muted);margin-bottom:6px">1勝の大きさ（平均R）</div>
          ${_bar('v1', 46, '#34d399')}
          ${_bar('v2', 92, '#60a5fa')}
        </div>
      </div>
      <p style="color:var(--text-muted);margin-top:10px;font-size:.82rem;">
        ↑ あくまで<strong>狙う形のイメージ</strong>（実数ではありません）。
        v1は「よく当たるが小さく取る」、v2は「当たりはやや減るが大きく取る」設計。
        <strong>実際の勝率・平均Rは「戦績」タブで signal_log から蓄積中</strong>です。
      </p>
    </div>

    <!-- 比較表 -->
    <div class="card" style="margin-bottom:18px;">
      <h3>項目別の違い</h3>
      <div class="lc-tablewrap">
      <table class="guide-table">
        <thead><tr><th>項目</th><th style="color:#34d399">v1（高勝率型）</th><th style="color:#60a5fa">v2（利大損小型）</th></tr></thead>
        <tbody>
          <tr><td><strong>入口トリガー</strong></td>
            <td>4H足の<strong>厳格トリガー</strong>（ダブルボトム/ピンバー等が発火、または押し目接近中のみ表示）</td>
            <td>日足フィルタで抽出→<strong>当日に反発足を自分で確認</strong>して引く（ウォッチ型）</td></tr>
          <tr><td><strong>利確（メイン）</strong></td>
            <td><span style="color:#34d399">直近高値手前で <strong>2/3</strong> を利確</span>（早め）</td>
            <td><span style="color:#60a5fa"><strong>+1.5R</strong> で半分を利確</span></td></tr>
          <tr><td><strong>残り玉</strong></td>
            <td>1/3 を 20日EMA 終値割れまでトレール</td>
            <td>半分を 20日EMA 終値割れまでトレール（<strong>大きく伸ばす</strong>）</td></tr>
          <tr><td><strong>損切り</strong></td>
            <td>サポートの少し下に固定＝<span style="color:#f87171">1R</span></td>
            <td>直近20日押し安値の少し下に固定＝<span style="color:#f87171">1R</span></td></tr>
          <tr><td><strong>RRの扱い</strong></td>
            <td>TP1まで <strong>RR≥1.5</strong> のみ採用・<strong>上限6.0</strong>でクランプ</td>
            <td>SL=1R 前提、<strong>+1.5R</strong> 基準（伸びれば青天井）</td></tr>
          <tr><td><strong>保有上限</strong></td>
            <td>8営業日（含み損なら撤退）</td>
            <td>8営業日（含み損なら撤退）</td></tr>
          <tr><td><strong>追加フィルタ</strong></td>
            <td>4Hトリガーの厳格さで質を担保</td>
            <td>決算7日除外 / レジサポ加点 / VIX慎重 / レバETF動的除外</td></tr>
          <tr><td><strong>性格</strong></td>
            <td>高勝率・利確早め・<strong>利益は頭打ち</strong></td>
            <td>勝率はやや低め・<strong>利大損小</strong>・伸ばす</td></tr>
          <tr><td><strong>向く局面</strong></td>
            <td>レジスタンスが明確な<strong>レンジ気味のスイング</strong></td>
            <td><strong>トレンド継続のランナー</strong>を取りにいく時</td></tr>
        </tbody>
      </table>
      </div>
    </div>

    <!-- 使い分け -->
    <div class="card">
      <h3>どちらを使う？（使い分けの目安）</h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px;">
        <div style="background:var(--bg-card);border-left:3px solid #34d399;border-radius:6px;padding:12px;">
          <div style="font-weight:700;color:#34d399">v1 を選ぶ時</div>
          <ul style="margin:8px 0 0 16px;color:var(--text-muted);font-size:.88rem;line-height:1.6">
            <li>直近高値（レジスタンス）が近く、そこまでで十分なRRが取れる</li>
            <li>地合いが横ばい〜やや弱く、<strong>確実に小さく取りたい</strong></li>
            <li>4H足でトリガーが既に発火している</li>
          </ul>
        </div>
        <div style="background:var(--bg-card);border-left:3px solid #60a5fa;border-radius:6px;padding:12px;">
          <div style="font-weight:700;color:#60a5fa">v2 を選ぶ時</div>
          <ul style="margin:8px 0 0 16px;color:var(--text-muted);font-size:.88rem;line-height:1.6">
            <li>強いトレンドが続いていて<strong>上に余地が大きい</strong></li>
            <li>1勝を大きくして<strong>RR（利大損小）を底上げ</strong>したい</li>
            <li>当日に反発足（陽線確定/前日高値超え）を自分で確認できる</li>
          </ul>
        </div>
      </div>
      <p style="color:var(--text-muted);margin-top:12px;font-size:.84rem;">
        💡 同じ銘柄が両方に出たら「買い場一致」の強いサイン（ファンダ重視ページの <code>cross_tag</code> でも表示）。
        その場合は地合い・上値余地で v1（確定重視）か v2（伸ばす）かを選びます。
      </p>
    </div>
  </div>`;
}

/* ── 横棒（イメージ用） ───────────────────────────────────────── */
function _bar(label, pct, color) {
  return `
    <div style="display:flex;align-items:center;gap:8px;margin:5px 0;">
      <span style="width:24px;font-size:.8rem;color:var(--text-muted)">${label}</span>
      <div style="flex:1;background:var(--bg-secondary,#0f172a);border-radius:5px;height:14px;overflow:hidden;border:1px solid var(--border)">
        <div style="width:${pct}%;height:100%;background:${color};opacity:.85"></div>
      </div>
    </div>`;
}

/* ── 出口の違いを描く価格チャートSVG（スマホでも読めるよう大きめラベル） ──── */
function _chart(o) {
  const ENTRY_Y = o.entry.y, SL_Y = 186, X0 = 38, X1 = 384;
  // v1: 利益が頭打ちになる帯をうっすら塗る
  const capRect = o.capLine
    ? `<rect x="${o.tp.x}" y="${o.capLine}" width="${X1 - o.tp.x}" height="${ENTRY_Y - o.capLine}" fill="#9ca3af" opacity="0.05"/>`
    : '';
  const exitAnchor = o.exit.anchor || 'middle';
  return `
  <svg viewBox="0 0 400 248" width="100%" style="display:block" font-family="sans-serif">
    <rect x="${X0}" y="14" width="${X1 - X0}" height="200" fill="none" stroke="var(--border)" stroke-width="1" rx="4"/>

    <!-- 20日EMA -->
    <path d="M ${X0},178 C 130,168 230,150 ${X1},120" fill="none" stroke="#f59e0b" stroke-width="1.8" opacity="0.65"/>
    <text x="${X1 - 5}" y="115" text-anchor="end" font-size="11" fill="#f59e0b">20EMA</text>

    <!-- ターゲット水平線（高値 / +1.5R） -->
    <line x1="${X0}" y1="${o.target.y}" x2="${X1}" y2="${o.target.y}" stroke="${o.target.color}" stroke-width="1.3" stroke-dasharray="5 3" opacity="0.9"/>
    <text x="${X0 + 5}" y="${o.target.y - 5}" font-size="12.5" font-weight="700" fill="${o.target.color}">${o.target.label}</text>

    <!-- エントリー水平線 -->
    <line x1="${X0}" y1="${ENTRY_Y}" x2="${X1}" y2="${ENTRY_Y}" stroke="#60a5fa" stroke-width="1.2" stroke-dasharray="3 3" opacity="0.7"/>
    <text x="${X1 - 5}" y="${ENTRY_Y - 5}" text-anchor="end" font-size="11" fill="#60a5fa">エントリー</text>

    <!-- 損切り(1R) -->
    <line x1="${X0}" y1="${SL_Y}" x2="${X1}" y2="${SL_Y}" stroke="#f87171" stroke-width="1.3" stroke-dasharray="5 3" opacity="0.9"/>
    <text x="${X0 + 5}" y="${SL_Y + 15}" font-size="12.5" font-weight="700" fill="#f87171">損切り（1R）</text>

    <!-- 1R 値幅 -->
    <line x1="${X0 + 8}" y1="${ENTRY_Y}" x2="${X0 + 8}" y2="${SL_Y}" stroke="#f87171" stroke-width="1.3" opacity="0.8"/>
    <text x="${X0 + 13}" y="${(ENTRY_Y + SL_Y) / 2 + 4}" font-size="11" fill="#f87171">1R</text>

    ${capRect}

    <!-- 価格の道のり -->
    <polyline points="${o.path}" fill="none" stroke="#e5e7eb" stroke-width="2.8"/>

    <!-- エントリー点 -->
    <circle cx="${o.entry.x}" cy="${o.entry.y}" r="5.5" fill="#60a5fa" stroke="#0b1220" stroke-width="1.5"/>

    <!-- 利確（メイン）点 -->
    <circle cx="${o.tp.x}" cy="${o.tp.y}" r="6" fill="#34d399" stroke="#0b1220" stroke-width="1.5"/>
    <text x="${o.tp.x}" y="${o.tp.y - 11}" text-anchor="middle" font-size="13" font-weight="800" fill="#34d399">${o.tp.label}</text>

    <!-- 最終手仕舞い点 -->
    <circle cx="${o.exit.x}" cy="${o.exit.y}" r="5.5" fill="none" stroke="#34d399" stroke-width="2.4"/>
    <text x="${o.exit.x}" y="${o.exit.up ? o.exit.y - 12 : o.exit.y + 18}" text-anchor="${exitAnchor}" font-size="12" font-weight="700" fill="#34d399">${o.exit.label}</text>
  </svg>`;
}
