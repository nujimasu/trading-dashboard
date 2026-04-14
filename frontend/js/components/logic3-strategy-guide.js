/**
 * ロジック３（ブレイクアウト・モメンタム戦略）の説明ページ
 */
export function renderLogic3StrategyGuide(container) {
  container.innerHTML = `
  <div class="strategy-guide" style="max-width:900px;margin:0 auto;padding:16px;">
    <h2 style="margin-bottom:6px">ロジック３ — ブレイクアウト・モメンタム戦略</h2>
    <p style="color:var(--text-muted);margin-bottom:20px;">
      保ち合い（ベース）からの上抜けを狙うモメンタム戦略。
      ロジック２（押し目買い）と正反対のタイミングで、<strong>レジスタンス突破後の加速</strong>を買います。
    </p>

    <!-- ロジック２との違い -->
    <div class="card" style="margin-bottom:16px;">
      <h3>ロジック２（押し目買い）との違い</h3>
      <table class="guide-table">
        <thead><tr><th>項目</th><th>ロジック２（押し目買い）</th><th>ロジック３（ブレイクアウト）</th></tr></thead>
        <tbody>
          <tr>
            <td><strong>タイミング</strong></td>
            <td>サポートに接近 → 反発を買う</td>
            <td><span style="color:var(--accent-green)">レジスタンス突破 → 加速を買う</span></td>
          </tr>
          <tr>
            <td><strong>価格の動き</strong></td>
            <td>下がっている時に買う</td>
            <td><span style="color:var(--accent-green)">上がっている時に買う</span></td>
          </tr>
          <tr>
            <td><strong>検出パターン</strong></td>
            <td>4Hローソク足パターン（ピンバー等）</td>
            <td><span style="color:var(--accent-green)">ベースパターン（VCP、フラットベース等）</span></td>
          </tr>
          <tr>
            <td><strong>出来高の役割</strong></td>
            <td>急増をトリガーとして使用</td>
            <td><span style="color:var(--accent-green)">ブレイクアウト確認の必須条件（1.5倍以上）</span></td>
          </tr>
          <tr>
            <td><strong>最低R:R</strong></td>
            <td>1.5</td>
            <td><span style="color:var(--accent-green)">2.0（ダマシリスク対策で厳格化）</span></td>
          </tr>
        </tbody>
      </table>
      <p style="color:var(--text-muted);margin-top:8px;font-size:0.85em;">
        構造上、同じ銘柄が両方のリストに同時に出ることはほぼありません（押し目=下落中、ブレイクアウト=上昇中）。
      </p>
    </div>

    <!-- フィルタリングフロー -->
    <div class="card" style="margin-bottom:16px;">
      <h3>フィルタリングフロー</h3>
      <div style="display:flex;flex-direction:column;gap:8px;">
        <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:6px;padding:12px;">
          <strong>Step 1: 一次フィルター（トレンド確認）</strong>
          <ul style="margin:8px 0 0 16px;color:var(--text-muted);">
            <li>週足: 20EMA > 200EMA（上昇トレンド確認）</li>
            <li>日足: 株価 > 20EMA > 200EMA（準パーフェクトオーダー以上）</li>
            <li>3ヶ月騰落率 > 0%</li>
            <li>20日平均出来高 >= 50万株</li>
          </ul>
        </div>
        <div style="text-align:center;font-size:20px;">↓</div>
        <div style="background:var(--bg-card);border:1px solid #60a5fa;border-radius:6px;padding:12px;">
          <strong>Step 2: ベースパターン検出</strong>
          <p style="color:var(--text-muted);margin:6px 0 0 0;font-size:.85em">
            4つのパターンを並列検出。複数該当時はR:Rが最も高いものを採用。
          </p>
          <ul style="margin:8px 0 0 16px;">
            <li><strong style="color:#60a5fa">フラットベース</strong>: 15〜45日の値幅 &lt; ATR×3、深さ15%以内</li>
            <li><strong style="color:#60a5fa">VCP</strong>: 2段階以上の値幅縮小（各70%以下に収縮）、深さ35%以内</li>
            <li><strong style="color:#60a5fa">アセンディング△</strong>: 水平レジスタンス（±1.5%）に3回以上タッチ + 切り上がりロー</li>
            <li><strong style="color:#60a5fa">カップ&ハンドル</strong>: 深さ10〜30%のU字回復、右リム97%回復、ハンドル最大10%</li>
          </ul>
        </div>
        <div style="text-align:center;font-size:20px;">↓</div>
        <div style="background:var(--bg-card);border:1px solid var(--accent-green);border-radius:6px;padding:12px;">
          <strong>Step 3: ブレイクアウト確認</strong>
          <ul style="margin:8px 0 0 16px;">
            <li><strong style="color:var(--accent-green)">確認済み（最優先候補）</strong>: 終値 > ピボット + 出来高 >= 平均の1.5倍 + ピボットからの距離 0.3〜5%</li>
            <li><strong style="color:var(--accent-yellow)">接近中</strong>: ピボットまで2%以内（まだ抜けていない）</li>
            <li><span style="color:var(--text-muted);text-decoration:line-through">ベース形成中: リストに表示しない（ノイズ排除）</span></li>
          </ul>
        </div>
        <div style="text-align:center;font-size:20px;">↓</div>
        <div style="background:var(--bg-card);border:1px solid var(--accent-green);border-radius:6px;padding:12px;">
          <strong>Step 4: R:R計算 + 最終判定</strong>
          <ul style="margin:8px 0 0 16px;">
            <li><strong>エントリー</strong>: 現在価格（ブレイクアウト直後）</li>
            <li><strong>TP1</strong>: メジャードムーブ（ピボット + ベース深さ分の上昇）</li>
            <li><strong>TP2</strong>: メジャードムーブ × 1.5</li>
            <li><strong>SL</strong>: max(ベース下限×0.99, ピボット−ATR)（浅い方を採用）</li>
            <li><strong style="color:var(--accent-green)">R:R >= 2.0 必須</strong>（ブレイクアウト確認済みの場合）</li>
          </ul>
        </div>
      </div>
    </div>

    <!-- ベースパターン図鑑 -->
    <div class="card" style="margin-bottom:16px;">
      <h3>ベースパターン図鑑（検出対象4パターン）</h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px">
        ${_patternCard("フラットベース", _svgFlatBase(), "値幅 < ATR×3", "深さ15%以内 / 15-45日", "#60a5fa")}
        ${_patternCard("VCP", _svgVcp(), "2段階以上の収縮", "各段70%以下 / 深さ35%以内", "#60a5fa")}
        ${_patternCard("アセンディング△", _svgAscTriangle(), "水平レジ3回タッチ", "切り上がりスイングロー", "#60a5fa")}
        ${_patternCard("カップ&ハンドル", _svgCupHandle(), "U字回復97%以上", "ハンドル深さ10%以内", "#60a5fa")}
      </div>
    </div>

    <!-- 信頼度スコアリング -->
    <div class="card" style="margin-bottom:16px;">
      <h3>信頼度スコアリング</h3>
      <table class="guide-table">
        <thead><tr><th>判定</th><th>ベーススコア</th><th>ボーナス条件</th><th>上限</th></tr></thead>
        <tbody>
          <tr>
            <td><span style="color:var(--accent-green);font-weight:700">最優先候補</span></td>
            <td>0.70</td>
            <td>
              出来高超過分: +0.05/0.5x（最大+0.10）<br>
              R:R >= 3.0: +0.05<br>
              VCP or カップ&ハンドル: +0.05
            </td>
            <td>0.95</td>
          </tr>
          <tr>
            <td><span style="color:var(--accent-yellow);font-weight:700">ブレイクアウト接近</span></td>
            <td>0.50</td>
            <td>R:R >= 3.0: +0.05</td>
            <td>0.65</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 判定凡例 -->
    <div class="card" style="margin-bottom:16px;">
      <h3>判定凡例</h3>
      <table class="guide-table">
        <thead><tr><th>判定</th><th>条件</th><th>推奨アクション</th></tr></thead>
        <tbody>
          <tr>
            <td><span class="verdict-badge" style="background:var(--accent-green);color:#000;padding:2px 8px;border-radius:4px;">最優先候補</span></td>
            <td>ブレイクアウト確認 + 出来高1.5倍以上 + R:R>=2.0</td>
            <td>エントリー検討可。出来高倍率・ベースパターンの質を確認してサイジング</td>
          </tr>
          <tr>
            <td><span class="verdict-badge" style="background:var(--accent-yellow);color:#000;padding:2px 8px;border-radius:4px;">ブレイクアウト接近</span></td>
            <td>ピボットまで2%以内、まだ抜けていない</td>
            <td>ウォッチリストに追加。出来高を伴う上抜けを待つ</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- エグジットルール -->
    <div class="card" style="margin-bottom:16px;">
      <h3>推奨エグジットルール</h3>
      <table class="guide-table">
        <thead><tr><th>条件</th><th>アクション</th></tr></thead>
        <tbody>
          <tr>
            <td>終値がSL（ストップ）を下回った</td>
            <td>翌寄りで全決済</td>
          </tr>
          <tr>
            <td>TP1（メジャードムーブ）到達</td>
            <td>半分利確、残りトレーリングストップ</td>
          </tr>
          <tr>
            <td>TP2（1.5倍ムーブ）到達</td>
            <td>全決済</td>
          </tr>
          <tr>
            <td>ブレイクアウト後3日以内にピボット下に戻った</td>
            <td>ダマシ判定、即全決済</td>
          </tr>
          <tr>
            <td>出来高が急減（平均以下に低下）</td>
            <td>モメンタム喪失、ストップを切り上げ</td>
          </tr>
        </tbody>
      </table>
    </div>

  </div>
  `;
}

// ── SVG ヘルパー ─────────────────────────────────────────────────────────────

function _patternCard(title, svg, line1, line2, color) {
  return `<div style="background:var(--bg-card);border:1px solid ${color}44;border-radius:8px;padding:10px;text-align:center">
    <div style="height:70px;display:flex;align-items:center;justify-content:center">${svg}</div>
    <div style="font-size:.85rem;font-weight:700;color:${color};margin-top:6px">${title}</div>
    <div style="font-size:.7rem;color:var(--text-muted);margin-top:4px">${line1}</div>
    <div style="font-size:.7rem;color:var(--text-muted);margin-top:2px">${line2}</div>
  </div>`;
}

function _svgFlatBase() {
  return `<svg width="90" height="60" viewBox="0 0 90 60">
    <path d="M5 25 L15 22 L25 28 L35 24 L45 26 L55 23 L65 27 L75 24" fill="none" stroke="#60a5fa" stroke-width="2"/>
    <line x1="5" y1="20" x2="75" y2="20" stroke="#f59e0b" stroke-width="1" stroke-dasharray="2"/>
    <line x1="5" y1="30" x2="75" y2="30" stroke="#94a3b8" stroke-width="0.5" stroke-dasharray="2"/>
    <path d="M75 24 L85 14" stroke="#22c55e" stroke-width="2" stroke-dasharray="3"/>
    <text x="78" y="12" font-size="8" fill="#22c55e">↑</text>
    <text x="30" y="42" font-size="7" fill="#94a3b8">tight range</text>
  </svg>`;
}

function _svgVcp() {
  return `<svg width="90" height="60" viewBox="0 0 90 60">
    <path d="M5 10 L12 40 L22 15 L30 35 L40 18 L48 30 L55 20 L62 27 L68 22" fill="none" stroke="#60a5fa" stroke-width="2"/>
    <line x1="5" y1="10" x2="68" y2="10" stroke="#f59e0b" stroke-width="0.5" stroke-dasharray="2"/>
    <path d="M68 22 L80 8" stroke="#22c55e" stroke-width="2" stroke-dasharray="3"/>
    <text x="10" y="50" font-size="6" fill="#94a3b8">wide</text>
    <text x="42" y="38" font-size="6" fill="#94a3b8">tight</text>
  </svg>`;
}

function _svgAscTriangle() {
  return `<svg width="90" height="60" viewBox="0 0 90 60">
    <line x1="10" y1="15" x2="75" y2="15" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="3"/>
    <path d="M10 50 L25 15 L35 40 L50 16 L55 30 L70 15" fill="none" stroke="#60a5fa" stroke-width="2"/>
    <path d="M70 15 L82 6" stroke="#22c55e" stroke-width="2" stroke-dasharray="3"/>
    <text x="2" y="54" font-size="6" fill="#94a3b8">HL</text>
    <text x="60" y="12" font-size="6" fill="#ef4444">R</text>
  </svg>`;
}

function _svgCupHandle() {
  return `<svg width="90" height="60" viewBox="0 0 90 60">
    <path d="M5 15 Q15 15 25 40 Q38 55 50 15 L58 15 Q62 25 66 20" fill="none" stroke="#60a5fa" stroke-width="2"/>
    <line x1="50" y1="15" x2="70" y2="15" stroke="#f59e0b" stroke-width="0.5" stroke-dasharray="2"/>
    <path d="M66 20 L78 8" stroke="#22c55e" stroke-width="2" stroke-dasharray="3"/>
    <text x="72" y="7" font-size="8" fill="#22c55e">↑</text>
  </svg>`;
}
