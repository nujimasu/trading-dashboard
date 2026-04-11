/**
 * ロジック２（厳選押し目買い・4H厳格トリガー版）の説明ページ
 */
export function renderLogic2StrategyGuide(container) {
  container.innerHTML = `
  <div class="strategy-guide" style="max-width:900px;margin:0 auto;padding:16px;">
    <h2>ロジック２ — 厳選押し目買い（4H厳格トリガー版）</h2>
    <p style="color:var(--text-muted);margin-bottom:20px;">
      ロジック３/４をベースに、<strong>3つの改善</strong>を適用した高確信度バージョン。
      トリガー条件を厳格化し、ノイズを排除して厳選された銘柄のみを表示します。
    </p>

    <!-- ロジック３/４との違い -->
    <div class="card" style="margin-bottom:16px;">
      <h3>ロジック３/４との違い</h3>
      <table class="guide-table">
        <thead><tr><th>改善項目</th><th>ロジック３/４</th><th>ロジック２（本ロジック）</th></tr></thead>
        <tbody>
          <tr>
            <td><strong>A. リスト絞り込み</strong></td>
            <td>トリガー未検出でも「押し目待ち」「サポート接近中」として表示</td>
            <td><span style="color:var(--accent-green)">「押し目待ち」を完全除外</span>。トリガー検出 or サポート接近中のみ表示</td>
          </tr>
          <tr>
            <td><strong>B. 4Hトリガー厳格化</strong></td>
            <td>ピンバー2倍ヒゲ、エンガルフィング実体包み、出来高1.5倍、サポート±5%</td>
            <td><span style="color:var(--accent-green)">ピンバー3倍ヒゲ、エンガルフィング全レンジ包み、出来高2.0倍、サポート±3%</span></td>
          </tr>
          <tr>
            <td><strong>C. 信頼度ボーナス</strong></td>
            <td>トリガーの質は信頼度に反映されない</td>
            <td><span style="color:var(--accent-green)">トリガーの組み合わせに応じて信頼度ボーナスを加算</span></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- フィルタリングフロー -->
    <div class="card" style="margin-bottom:16px;">
      <h3>フィルタリングフロー</h3>
      <div style="display:flex;flex-direction:column;gap:8px;">
        <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:6px;padding:12px;">
          <strong>Step 1: 一次フィルター（ロジック３/４と同一）</strong>
          <ul style="margin:8px 0 0 16px;color:var(--text-muted);">
            <li>週足: 20EMA > 200EMA</li>
            <li>日足: パーフェクトオーダー（株価 > 20EMA > 50EMA > 200EMA）</li>
            <li>3ヶ月騰落率 > 0%</li>
            <li>20日平均出来高 >= 50万株</li>
          </ul>
        </div>
        <div style="text-align:center;font-size:20px;">↓</div>
        <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:6px;padding:12px;">
          <strong>Step 2: 二次フィルター（ロジック３/４と同一）</strong>
          <ul style="margin:8px 0 0 16px;color:var(--text-muted);">
            <li>ダウ理論: broken以外（strong / early）</li>
            <li>サポートライン: コンフルエンス >= 1</li>
            <li>R:R >= 1.5</li>
          </ul>
        </div>
        <div style="text-align:center;font-size:20px;">↓</div>
        <div style="background:var(--bg-card);border:1px solid var(--accent-green);border-radius:6px;padding:12px;">
          <strong>Step 3: 厳格4Hトリガー検出（改善B）</strong>
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
        </div>
        <div style="text-align:center;font-size:20px;">↓</div>
        <div style="background:var(--bg-card);border:1px solid var(--accent-green);border-radius:6px;padding:12px;">
          <strong>Step 4: リスト絞り込み（改善A）</strong>
          <ul style="margin:8px 0 0 16px;">
            <li><strong style="color:var(--accent-green)">最優先候補</strong>: 4Hトリガー検出 + サポート接近（3%以内）</li>
            <li><strong style="color:var(--accent-yellow)">サポート接近中</strong>: トリガー未検出だがサポート3%以内（もうすぐトリガー発生の可能性）</li>
            <li><span style="color:var(--text-muted);text-decoration:line-through">押し目待ち: 除外（リストに表示しない）</span></li>
          </ul>
        </div>
      </div>
    </div>

    <!-- 信頼度ボーナス -->
    <div class="card" style="margin-bottom:16px;">
      <h3>信頼度ボーナス（改善C）</h3>
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
        ※ ベースの信頼度はロジック３/４と同一の算出ロジック。ボーナスは上限0.99まで。
      </p>
    </div>

    <!-- 4Hトリガー比較表 -->
    <div class="card" style="margin-bottom:16px;">
      <h3>4Hトリガー パラメータ比較</h3>
      <table class="guide-table">
        <thead><tr><th>パラメータ</th><th>ロジック２（厳格）</th><th>ロジック３（標準4H）</th><th>ロジック４（1H）</th></tr></thead>
        <tbody>
          <tr>
            <td>ピンバー下ヒゲ比率</td>
            <td style="color:var(--accent-green)">>=3倍</td>
            <td>>=2倍</td>
            <td>>=2倍</td>
          </tr>
          <tr>
            <td>エンガルフィング条件</td>
            <td style="color:var(--accent-green)">全レンジ包み（H-L）</td>
            <td>実体包み（O-C）</td>
            <td>実体包み（O-C）</td>
          </tr>
          <tr>
            <td>出来高閾値</td>
            <td style="color:var(--accent-green)">2.0倍</td>
            <td>1.5倍</td>
            <td>1.5倍</td>
          </tr>
          <tr>
            <td>サポート近傍範囲</td>
            <td style="color:var(--accent-green)">±3%</td>
            <td>±5%</td>
            <td>±5%</td>
          </tr>
          <tr>
            <td>逆ハンマー上ヒゲ比率</td>
            <td style="color:var(--accent-green)">>=3倍、下ヒゲ極小</td>
            <td>>=2倍</td>
            <td>>=2倍</td>
          </tr>
          <tr>
            <td>切り込み線 戻し水準</td>
            <td style="color:var(--accent-green)">61.8%以上</td>
            <td>50%以上</td>
            <td>50%以上</td>
          </tr>
          <tr>
            <td>明けの明星 b2実体/b3戻し</td>
            <td style="color:var(--accent-green)">30%未満/60%以上</td>
            <td>40%未満/50%以上</td>
            <td>40%未満/50%以上</td>
          </tr>
          <tr>
            <td>赤三兵 実体条件</td>
            <td style="color:var(--accent-green)">レンジの50%以上</td>
            <td>条件なし</td>
            <td>条件なし</td>
          </tr>
          <tr>
            <td>ダブルボトム tolerance</td>
            <td>1.5%</td>
            <td>1.5%</td>
            <td>1.0%</td>
          </tr>
          <tr>
            <td>信頼度ボーナス</td>
            <td style="color:var(--accent-green)">あり（最大+0.15）</td>
            <td>なし</td>
            <td>なし</td>
          </tr>
          <tr>
            <td>「押し目待ち」表示</td>
            <td style="color:var(--accent-green)">除外</td>
            <td>表示する</td>
            <td>表示する</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 使い分けガイド -->
    <div class="card" style="margin-bottom:16px;">
      <h3>ロジック２/３/４ 使い分けガイド</h3>
      <table class="guide-table">
        <thead><tr><th>ロジック</th><th>特徴</th><th>向いているシーン</th></tr></thead>
        <tbody>
          <tr>
            <td><strong>ロジック２（厳選4H）</strong></td>
            <td>厳格なトリガー条件 + ノイズ除外。少数精鋭のリスト</td>
            <td>ポジション集中度が高い時、高確信度エントリーに絞りたい時</td>
          </tr>
          <tr>
            <td><strong>ロジック３（標準4H）</strong></td>
            <td>4Hトリガーで検出。監視リストとしても使える幅広いリスト</td>
            <td>来週の候補を広く探したい時、ウォッチリスト構築時</td>
          </tr>
          <tr>
            <td><strong>ロジック４（1H）</strong></td>
            <td>1Hトリガーで検出。最も検出感度が高い</td>
            <td>短期エントリーの即時判断、日中のトリガー確認</td>
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
        ※「押し目待ち」はこのロジックでは表示されません（改善A）。
        幅広い候補はロジック３/４で確認してください。
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
              <strong>＋ トリガー品質ボーナス（改善C）</strong>: 上記ベースに加算。最大+0.15。全体上限0.99
            </td>
          </tr>
        </tbody>
      </table>
    </div>

  </div>
  `;
}
