/**
 * 厳選押し目買いv1（4H厳格トリガー版）の説明ページ
 */
export function renderLogic2StrategyGuide(container) {
  container.innerHTML = `
  <div class="strategy-guide" style="max-width:900px;margin:0 auto;padding:16px;">
    <h2 style="margin-bottom:6px">厳選押し目買いv1 — 4H厳格トリガー版</h2>
    <p style="color:var(--text-muted);margin-bottom:20px;">
      上昇トレンド中の銘柄がサポートに押した際、<strong>4時間足の厳格なローソク足パターン</strong>で反発を確認してエントリーする戦略。
      ノイズを徹底排除し、高確信度の候補のみを表示します。
      出口は<strong>直近高値手前で2/3利確し、残りを20日EMAでトレール</strong>する高勝率型です。
    </p>

    <!-- 戦略の特徴 -->
    <div class="card" style="margin-bottom:16px;">
      <h3>戦略の特徴</h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;">
        <div style="background:var(--bg-card);border-left:3px solid var(--accent-green);border-radius:6px;padding:12px;">
          <div style="font-size:.85rem;font-weight:700;color:var(--accent-green)">厳格なトリガー条件</div>
          <div style="font-size:.78rem;color:var(--text-muted);margin-top:4px">ピンバー3倍ヒゲ、エンガルフィング全レンジ包み、出来高2.0倍など標準より厳しい閾値</div>
        </div>
        <div style="background:var(--bg-card);border-left:3px solid #60a5fa;border-radius:6px;padding:12px;">
          <div style="font-size:.85rem;font-weight:700;color:#60a5fa">ノイズ除外</div>
          <div style="font-size:.78rem;color:var(--text-muted);margin-top:4px">「押し目待ち」銘柄を完全除外。トリガー検出 or サポート接近中のみ表示</div>
        </div>
        <div style="background:var(--bg-card);border-left:3px solid #8b5cf6;border-radius:6px;padding:12px;">
          <div style="font-size:.85rem;font-weight:700;color:#8b5cf6">信頼度ボーナス</div>
          <div style="font-size:.78rem;color:var(--text-muted);margin-top:4px">トリガーの組み合わせに応じて信頼度を加算。質の高いシグナルを優先表示</div>
        </div>
      </div>
    </div>

    <div class="card" style="margin-bottom:16px;">
      <h3>出口ルール（v1確定版）</h3>
      <table class="guide-table">
        <thead><tr><th>項目</th><th>ルール</th></tr></thead>
        <tbody>
          <tr><td>SL</td><td>サポートまたは押し安値の少し下に固定。エントリーから損切りまでを1Rとして扱います。</td></tr>
          <tr><td>TP1</td><td>直近スイング高値の手前（高値×0.99）で2/3を利確します。</td></tr>
          <tr><td>残り1/3</td><td>20日EMAを終値で割るまでトレールします。</td></tr>
          <tr><td>RRゲート</td><td>TP1までのRRが1.5未満なら候補に採用しません。</td></tr>
          <tr><td>保有上限</td><td>8営業日経過で含み損なら全決済します。</td></tr>
        </tbody>
      </table>
      <p style="color:var(--text-muted);margin-top:10px;font-size:.85em">
        v1はレジスタンスが明確なレンジ気味スイング向きです。v2は+1.5Rで半分利確し、残りを伸ばすトレンド継続ランナー向きです。
      </p>
    </div>

    <!-- フィルタリングフロー -->
    <div class="card" style="margin-bottom:16px;">
      <h3>フィルタリングフロー</h3>
      <div style="display:flex;flex-direction:column;gap:8px;">
        <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:6px;padding:12px;">
          <strong>Step 1: 一次フィルター</strong>
          <ul style="margin:8px 0 0 16px;color:var(--text-muted);">
            <li>週足: 20EMA > 200EMA</li>
            <li>日足: パーフェクトオーダー（株価 > 20EMA > 50EMA > 200EMA）</li>
            <li>3ヶ月騰落率 > 0%</li>
            <li>20日平均出来高 >= 50万株</li>
          </ul>
        </div>
        <div style="text-align:center;font-size:20px;">↓</div>
        <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:6px;padding:12px;">
          <strong>Step 2: 二次フィルター</strong>
          <ul style="margin:8px 0 0 16px;color:var(--text-muted);">
            <li>ダウ理論: broken以外（strong / early）</li>
            <li>サポートライン: コンフルエンス >= 1</li>
            <li>TP1（直近高値×0.99）までのR:R >= 1.5</li>
          </ul>
        </div>
        <div style="text-align:center;font-size:20px;">↓</div>
        <div style="background:var(--bg-card);border:1px solid var(--accent-green);border-radius:6px;padding:12px;">
          <strong>Step 3: 厳格4Hトリガー検出</strong>
          <ul style="margin:8px 0 0 16px;">
            <li><strong>ピンバー(4H厳選)</strong>: 下ヒゲ >= 実体の<span style="color:var(--accent-green)">3倍</span>、陽線</li>
            <li><strong>逆ハンマー(4H厳選)</strong>: 上ヒゲ >= 実体の<span style="color:var(--accent-green)">3倍</span>、下ヒゲ極小</li>
            <li><strong>強気エンガルフィング(4H厳選)</strong>: 前足の<span style="color:var(--accent-green)">全レンジ（高値〜安値）</span>を包み込む</li>
            <li><strong>切り込み線(4H厳選)</strong>: 陰線→陽線が前足の<span style="color:var(--accent-green)">61.8%以上</span>まで戻す</li>
            <li><strong>出来高急増(4H厳選)</strong>: 平均出来高の<span style="color:var(--accent-green)">2.0倍</span>以上 + 陽線</li>
            <li><strong>明けの明星(4H厳選)</strong>: 大陰線→<span style="color:var(--accent-green)">実体30%未満</span>→<span style="color:var(--accent-green)">60%以上戻す</span>大陽線</li>
            <li><strong>赤三兵(4H厳選)</strong>: 3本連続陽線、各足の<span style="color:var(--accent-green)">実体がレンジの50%以上</span></li>
            <li><strong>ダブルボトム(4H厳選)</strong>: スイングロー2点の乖離 < 1.5%</li>
            <li>全パターン: サポート価格の<span style="color:var(--accent-green)">±3%以内</span>で発生したもののみ</li>
          </ul>
          <div style="margin-top:12px;padding-top:10px;border-top:1px solid var(--border)">
            <div style="font-weight:700;color:#60a5fa;margin-bottom:6px">日足チャートパターン（厳格版）</div>
            <ul style="margin:6px 0 0 16px;">
              <li><strong style="color:#60a5fa">カップウィズハンドル(厳選)</strong>: 深さ10〜30%、右リム97%回復、ハンドル最大10%</li>
              <li><strong style="color:#60a5fa">アセンディングトライアングル(厳選)</strong>: レジスタンス±1.5%、スイング3点以上</li>
              <li><strong style="color:#60a5fa">逆ヘッドアンドショルダー(厳選)</strong>: 両肩±4%、ネックライン99%突破</li>
              <li><strong style="color:#60a5fa">ブルペナント(厳選)</strong>: ポール上昇12%以上、レンジ縮小60%以下</li>
              <li><strong style="color:#60a5fa">フォーリングウェッジ(厳選)</strong>: 収束50%以下、完全ブレイク確認</li>
            </ul>
          </div>
        </div>
        <div style="text-align:center;font-size:20px;">↓</div>
        <div style="background:var(--bg-card);border:1px solid var(--accent-green);border-radius:6px;padding:12px;">
          <strong>Step 4: リスト絞り込み</strong>
          <ul style="margin:8px 0 0 16px;">
            <li><strong style="color:var(--accent-green)">最優先候補</strong>: 4Hトリガー検出 + サポート接近（3%以内）</li>
            <li><strong style="color:var(--accent-yellow)">サポート接近中</strong>: トリガー未検出だがサポート3%以内（もうすぐトリガー発生の可能性）</li>
            <li><span style="color:var(--text-muted);text-decoration:line-through">押し目待ち: 除外（リストに表示しない）</span></li>
          </ul>
        </div>
      </div>
    </div>

    <!-- ローソクパターン図鑑 -->
    <div class="card" style="margin-bottom:16px;">
      <h3>ローソクパターン図鑑（厳格版 — 検出対象8パターン）</h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px">
        ${_candleCard("ピンバー", "下ヒゲ≥3倍", "var(--accent-green)")}
        ${_candleCard("逆ハンマー", "上ヒゲ≥3倍", "var(--accent-green)")}
        ${_candleCard("強気エンガルフィング", "全レンジ包み", "var(--accent-green)")}
        ${_candleCard("切り込み線", "61.8%以上戻し", "var(--accent-green)")}
        ${_candleCard("出来高急増", "平均の2.0倍", "var(--accent-green)")}
        ${_candleCard("明けの明星", "b2<30%/b3>60%", "var(--accent-green)")}
        ${_candleCard("赤三兵", "実体≥レンジ50%", "var(--accent-green)")}
        ${_candleCard("ダブルボトム", "乖離<1.5%", "var(--accent-green)")}
      </div>
    </div>

    <!-- 日足チャートパターン図鑑 -->
    <div class="card" style="margin-bottom:16px;">
      <h3>日足チャートパターン図鑑（厳格版 — 5パターン）</h3>
      <p style="color:var(--text-muted);margin-bottom:12px;font-size:.85em">
        日足データ（60〜250日）を使用した構造的な強気パターン検出。
      </p>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px">
        ${_candleCard("カップウィズハンドル", "深さ10-30%/回復97%", "#60a5fa")}
        ${_candleCard("アセンディング△", "レジ±1.5%/3点以上", "#60a5fa")}
        ${_candleCard("逆H&S", "両肩±4%/NL99%", "#60a5fa")}
        ${_candleCard("ブルペナント", "ポール12%↑/縮小60%", "#60a5fa")}
        ${_candleCard("フォーリングウェッジ", "収束50%/完全ブレイク", "#60a5fa")}
      </div>
    </div>

    <!-- 信頼度ボーナス -->
    <div class="card" style="margin-bottom:16px;">
      <h3>信頼度ボーナス</h3>
      <p style="color:var(--text-muted);margin-bottom:12px;">
        トリガーの質が高い場合、信頼度スコアにボーナスを加算します。
        同じ「最優先候補」内でもトリガーの組み合わせで優先順位が変わります。
      </p>
      <table class="guide-table">
        <thead><tr><th>条件</th><th>ボーナス</th><th>根拠</th></tr></thead>
        <tbody>
          <tr>
            <td>ピンバー + 出来高急増</td>
            <td style="color:var(--accent-green)">+0.10</td>
            <td>価格拒否と機関投資家の参入が同時に確認 = 強い反転シグナル</td>
          </tr>
          <tr>
            <td>強気エンガルフィング + RSI < 40</td>
            <td style="color:var(--accent-green)">+0.10</td>
            <td>売られ過ぎゾーンでの力強い買い転換 = オーバーソールドリバーサル</td>
          </tr>
          <tr>
            <td>ダブルボトム（サポート乖離 < 1%）</td>
            <td style="color:var(--accent-green)">+0.15</td>
            <td>サポートラインと正確に一致するダブルボトム = 最も信頼性の高い反転パターン</td>
          </tr>
        </tbody>
      </table>
      <p style="color:var(--text-muted);margin-top:8px;font-size:0.85em;">
        ※ ボーナスは上限0.99まで。
      </p>
    </div>

    <!-- 4Hトリガー パラメータ詳細 -->
    <div class="card" style="margin-bottom:16px;">
      <h3>4Hトリガー パラメータ詳細</h3>
      <table class="guide-table">
        <thead><tr><th>パラメータ</th><th>設定値</th><th>理由</th></tr></thead>
        <tbody>
          <tr>
            <td>ピンバー下ヒゲ比率</td>
            <td style="color:var(--accent-green)">>=3倍</td>
            <td>強い買い圧力の確認</td>
          </tr>
          <tr>
            <td>逆ハンマー上ヒゲ比率</td>
            <td style="color:var(--accent-green)">>=3倍、下ヒゲ極小</td>
            <td>高値試しの後の支持確認</td>
          </tr>
          <tr>
            <td>エンガルフィング条件</td>
            <td style="color:var(--accent-green)">全レンジ包み（H-L）</td>
            <td>完全な逆転パターン</td>
          </tr>
          <tr>
            <td>切り込み線 戻し水準</td>
            <td style="color:var(--accent-green)">61.8%以上</td>
            <td>フィボナッチ水準での反転確認</td>
          </tr>
          <tr>
            <td>出来高閾値</td>
            <td style="color:var(--accent-green)">2.0倍</td>
            <td>機関投資家の参入確認</td>
          </tr>
          <tr>
            <td>明けの明星 b2実体/b3戻し</td>
            <td style="color:var(--accent-green)">30%未満/60%以上</td>
            <td>強い3本足反転パターン</td>
          </tr>
          <tr>
            <td>赤三兵 実体条件</td>
            <td style="color:var(--accent-green)">レンジの50%以上</td>
            <td>ヒゲが小さく実体が大きい=強い買い</td>
          </tr>
          <tr>
            <td>ダブルボトム tolerance</td>
            <td>1.5%</td>
            <td>精度の高い二底形成</td>
          </tr>
          <tr>
            <td>サポート近傍範囲</td>
            <td style="color:var(--accent-green)">±3%</td>
            <td>サポートに十分近い位置のみ採用</td>
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
            <td>厳格4Hトリガー検出 + サポート3%以内</td>
            <td>エントリー検討可。RR、ダウ理論、信頼度ボーナスを確認してサイジング</td>
          </tr>
          <tr>
            <td><span class="verdict-badge" style="background:var(--accent-yellow);color:#000;padding:2px 8px;border-radius:4px;">サポート接近中</span></td>
            <td>サポート3%以内だが厳格トリガー未検出</td>
            <td>ウォッチリストに追加。次の4H足でトリガーが出るか監視</td>
          </tr>
        </tbody>
      </table>
      <p style="color:var(--text-muted);margin-top:8px;font-size:0.85em;">
        ※「押し目待ち」はこのロジックでは表示されません。
      </p>
    </div>

    <!-- 信頼度算出ロジック -->
    <div class="card" style="margin-bottom:16px;">
      <h3>信頼度算出ロジック</h3>
      <table class="guide-table">
        <thead><tr><th>条件</th><th>ベーススコア</th><th>ボーナス</th><th>上限</th></tr></thead>
        <tbody>
          <tr>
            <td>レジサポ確認 + RR>=1.5 + ボーナス1件以上</td>
            <td>0.70</td>
            <td>+0.05/ボーナス + RR>=2.0で+0.05</td>
            <td>0.95</td>
          </tr>
          <tr>
            <td>RR>=1.5 + コンフルエンス>=2</td>
            <td>0.55</td>
            <td>+0.05/ボーナス + RR>=2.0で+0.05</td>
            <td>0.80</td>
          </tr>
          <tr>
            <td>RR>=1.5（最低条件）</td>
            <td>0.50</td>
            <td>+0.03/ボーナス</td>
            <td>-</td>
          </tr>
          <tr>
            <td colspan="4" style="border-top:2px solid var(--accent-green);">
              <strong>＋ トリガー品質ボーナス</strong>: 上記ベースに加算。最大+0.15。全体上限0.99
            </td>
          </tr>
        </tbody>
      </table>
    </div>

  </div>
  `;
}

// ── ヘルパー ─────────────────────────────────────────────────────────────────
function _candleCard(title, param, color) {
  return `<div style="background:var(--bg-card);border:1px solid ${color}44;border-radius:6px;padding:10px;text-align:center">
    <div style="font-size:.8rem;font-weight:700;color:${color}">${title}</div>
    <div style="font-size:.7rem;color:var(--text-muted);margin-top:4px">${param}</div>
  </div>`;
}
