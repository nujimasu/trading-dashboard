/** 独立再検証済みの押し目リバーサル（logic5）ガイド。 */
export function renderLogic5StrategyGuide(container) {
  const muted = "color:var(--text-muted);";
  const green = "color:var(--accent-green,#34d399);";
  container.innerHTML = `
  <div class="strategy-guide" style="max-width:900px;margin:0 auto;padding:16px;">
    <h2>押し目リバーサル — 厳格地合い版</h2>
    <p style="${muted}">
      日足確定後に反転を判定し、翌営業日の寄り付きで入るロング戦略です。
      <strong>SPYとQQQの双方が完全上昇トレンドでない日は、新規取引を休止します。</strong>
    </p>

    <div class="card" style="margin:16px 0;border-left:3px solid var(--blue);">
      <h3>地合いゲート（すべて必須）</h3>
      <ul>
        <li>SPY：終値 &gt; 200EMA、50EMA &gt; 200EMA</li>
        <li>QQQ：終値 &gt; 200EMA、50EMA &gt; 200EMA</li>
        <li>不成立時はショートで無理に補わず、現金待機</li>
      </ul>
    </div>

    <div class="card" style="margin-bottom:16px;">
      <h3>エントリー条件</h3>
      <table class="guide-table"><tbody>
        <tr><td>個別トレンド</td><td>終値 &gt; 200EMA、50EMA &gt; 200EMA、3か月騰落率プラス</td></tr>
        <tr><td>流動性</td><td>20日平均出来高100万株以上</td></tr>
        <tr><td>押し目</td><td>21日騰落率−3%以下、かつ50EMAの−1%以上</td></tr>
        <tr><td>出来高</td><td>当日出来高が20日平均の80%以上</td></tr>
        <tr><td>反転確認</td><td>PA 7種中4個以上 ＋ オシレーター3種中1個以上</td></tr>
        <tr><td>約定</td><td>シグナル翌営業日の寄り付き</td></tr>
      </tbody></table>
      <p style="${muted}">同時候補は最大30件。オシレーター証拠数が多い順、同数ならPA証拠数が少ない順です。PAは4個で十分で、追加確認を待ちすぎない設計です。</p>
    </div>

    <div class="card" style="margin-bottom:16px;">
      <h3>根拠に使う反転サイン</h3>
      <p><strong>PA：</strong>陽線、長い下ヒゲ、高値圏引け、安値切り上げ、前日高値超え、インサイドバー上抜け、強気包み足。</p>
      <p><strong>オシレーター：</strong>RSI上向き、ストキャス%Kの%D上抜け、MACDヒストグラム上向き。</p>
    </div>

    <div class="card" style="margin-bottom:16px;">
      <h3>テクニカルに基づく出口</h3>
      <table class="guide-table"><tbody>
        <tr><td>損切り</td><td>直近20日押し安値 − 0.1ATR</td></tr>
        <tr><td>採用ゲート</td><td>直近60日高値まで1.5〜2.0Rの余地があること</td></tr>
        <tr><td>利確</td><td>60日高値の0.5%手前で全量決済</td></tr>
        <tr><td>時間切れ</td><td>30営業日</td></tr>
      </tbody></table>
    </div>

    <div class="card" style="margin-bottom:16px;">
      <h3>独立バックテスト</h3>
      <p style="${muted}">628銘柄・調整済み日足。翌日寄り、往復各10bp、同一日SL優先。30銘柄上限。</p>
      <table class="guide-table">
        <thead><tr><th>期間</th><th>件数</th><th>勝率</th><th>平均R</th><th>PF</th></tr></thead>
        <tbody>
          <tr><td>2023–2024 学習</td><td>62</td><td>54.8%</td><td style="${green}">+0.378R</td><td>1.83</td></tr>
          <tr><td>2025 検証</td><td>27</td><td>59.3%</td><td style="${green}">+0.519R</td><td>2.32</td></tr>
          <tr><td>2026 最終ホールドアウト</td><td>18</td><td>50.0%</td><td style="${green}">+0.421R</td><td>2.20</td></tr>
          <tr><td><strong>2025以降OOS</strong></td><td><strong>45</strong></td><td><strong>55.6%</strong></td><td style="${green}"><strong>+0.480R</strong></td><td><strong>2.28</strong></td></tr>
        </tbody>
      </table>
    </div>

    <div class="card" style="border-left:3px solid #f59e0b;">
      <h3>リスク上の注意</h3>
      <ul>
        <li>2022年は厳格地合いゲートにより新規シグナルゼロ。弱気相場の利益源ではなく、防御策です。</li>
        <li>OOSは45件、2026ホールドアウトは18件とまだ少ないため、フォワード100件までは暫定候補です。</li>
        <li>現在の銘柄集合を過去へ遡及しているため、生存バイアスがあります。</li>
        <li>決算発表日のポイントインタイム除外は未実装です。</li>
        <li>推奨する口座リスクは1取引0.25〜0.5%。年率300%を狙う過大リスクは最大DDを危険域へ押し上げます。</li>
      </ul>
    </div>
  </div>`;
}
