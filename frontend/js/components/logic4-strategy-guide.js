/**
 * 厳選押し目買いv2（v3確定版）の説明ページ
 * 実トレード 1,713 件の分析から導いた「現時点で最も勝てる確率の高い形」。
 */
export function renderLogic4StrategyGuide(container) {
  container.innerHTML = `
  <div class="strategy-guide" style="max-width:900px;margin:0 auto;padding:16px;">
    <h2 style="margin-bottom:6px">厳選押し目買いv2 — v3確定版</h2>
    <p style="color:var(--text-muted);margin-bottom:20px;">
      実トレード <strong>1,713 件</strong> のデータ分析から導いた押し目買いスイング戦略。
      頭で作った理想論ではなく、過去データが「これなら勝てた」と示した方向に沿っています。
      <strong>勝ち筋は 4〜7 日保有のスイング</strong>。デイトレは構造的に負けるため禁止します。
      v1よりも<strong>利大損小で伸ばす</strong>ことを優先するウォッチ型です。
    </p>

    <!-- 診断サマリー -->
    <div class="card" style="margin-bottom:16px;">
      <h3>出発点となった事実（自分の戦績診断）</h3>
      <table class="guide-table">
        <thead><tr><th>指標</th><th>数値</th><th>意味</th></tr></thead>
        <tbody>
          <tr><td>累計P/L</td><td>−$8,819</td><td>トータル負け越し</td></tr>
          <tr><td>勝率</td><td>46.5%</td><td>勝率自体は悪くない</td></tr>
          <tr><td>PF</td><td>0.76</td><td>1未満＝負ける形</td></tr>
          <tr><td>RR比</td><td>1.1</td><td><span style="color:#f87171">利大損小ができていない＝負けの正体</span></td></tr>
          <tr><td>期待値/件</td><td>−$5.15</td><td>1トレードごとに損している</td></tr>
        </tbody>
      </table>
      <p style="margin-top:10px;">
        <strong>結論：負けているのは「勝率」ではなく「RR（利大損小）」。</strong>
        フィルターで勝率を底上げし、<strong>分割決済（+1.5R 半分 → 残りトレーリング）</strong>で
        1勝を大きくする。この両輪で勝ちます。
      </p>
      <ul style="margin:10px 0 0 16px;color:var(--text-muted);font-size:.9em;">
        <li>当日決済（デイトレ）が最大の出血源（−$4,057／勝率37.5%）→ <strong>禁止</strong></li>
        <li><span style="color:var(--accent-green)">4〜7日保有だけが唯一のプラス（+$656／勝率54.1%／平均+1.27%）→ 狙う土俵</span></li>
        <li>8〜14日保有は急悪化ゾーン（−$3,643／平均−3.98%）→ <strong>8日上限ルール</strong>で回避</li>
        <li>高額レバETF・暗号資産関連小型株が地雷（レバETF&gt;$100で−$2,473）→ <strong>除外</strong></li>
      </ul>
    </div>

    <div class="card" style="margin-bottom:16px;">
      <h3>v2で追加した4フィルタ</h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px;">
        <div style="background:var(--bg-card);border-left:3px solid #f87171;border-radius:6px;padding:12px;">
          <div style="font-weight:700;color:#f87171;font-size:.86rem">決算7日以内を除外</div>
          <div style="font-size:.78rem;color:var(--text-muted);margin-top:4px">決算ギャンブルを避けるため、取得できた次回決算日が7日以内なら候補から外します。</div>
        </div>
        <div style="background:var(--bg-card);border-left:3px solid var(--accent-green);border-radius:6px;padding:12px;">
          <div style="font-weight:700;color:var(--accent-green);font-size:.86rem">レジサポ転換を加点</div>
          <div style="font-size:.78rem;color:var(--text-muted);margin-top:4px">採用EMAの±2%以内に過去スイング高値が重なる場合、節目の重なりとして信頼度を加算します。</div>
        </div>
        <div style="background:var(--bg-card);border-left:3px solid #f59e0b;border-radius:6px;padding:12px;">
          <div style="font-weight:700;color:#f59e0b;font-size:.86rem">VIX慎重フラグ</div>
          <div style="font-size:.78rem;color:var(--text-muted);margin-top:4px">VIXが25超または5営業日で30%以上急騰した週は、反発足の確認を厚くする注意を表示します。</div>
        </div>
        <div style="background:var(--bg-card);border-left:3px solid #60a5fa;border-radius:6px;padding:12px;">
          <div style="font-weight:700;color:#60a5fa;font-size:.86rem">レバETF動的除外</div>
          <div style="font-size:.78rem;color:var(--text-muted);margin-top:4px">レバETFは$100超を除外、$30未満は許容、$30〜$100は信頼度を微減します。</div>
        </div>
      </div>
      <p style="color:var(--text-muted);margin-top:10px;font-size:.85em">
        v1は直近高値手前で2/3を早めに利確する高勝率型。v2は+1.5Rで半分だけ確定し、残りを20日EMAトレールで伸ばす型です。
      </p>
    </div>

    <!-- フィルタリングフロー -->
    <div class="card" style="margin-bottom:16px;">
      <h3>エントリー判定フロー（このダッシュボードの自動抽出範囲）</h3>
      <div style="display:flex;flex-direction:column;gap:8px;">
        <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:6px;padding:12px;">
          <strong>① 地合いフィルター</strong>
          <p style="color:var(--text-muted);margin:6px 0 0 0;font-size:.88em">
            S&amp;P500 または QQQ が <strong>200日EMA の上</strong>にある時だけ押し目買い可。
            割れている局面は「休む」（候補に⚠️警告を表示し減点）。
          </p>
        </div>
        <div style="text-align:center;font-size:20px;">↓</div>
        <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:6px;padding:12px;">
          <strong>② トレンド＋流動性フィルター</strong>
          <ul style="margin:8px 0 0 16px;color:var(--text-muted);font-size:.88em">
            <li>株価 &gt; 200EMA かつ 50EMA &gt; 200EMA（上昇トレンド確定）</li>
            <li>過去3ヶ月騰落率 &gt; 0%</li>
            <li>20日平均出来高 ≥ 100万株</li>
            <li>除外：決算7日以内、高額レバETF、暗号マイニング小型株（MARA/BITF等）</li>
          </ul>
        </div>
        <div style="text-align:center;font-size:20px;">↓</div>
        <div style="background:var(--bg-card);border:1px solid #60a5fa;border-radius:6px;padding:12px;">
          <strong>③ 押し目到達＋売り枯れ</strong>
          <ul style="margin:8px 0 0 16px;color:var(--text-muted);font-size:.88em">
            <li>株価が <strong>20日 or 50日EMA にタッチ（±2%）／接近（±5%）</strong></li>
            <li>下げの局面で<strong>出来高が細っている（売り枯れ）</strong>＝直近3日平均 &lt; 20日平均×0.8</li>
          </ul>
        </div>
        <div style="text-align:center;font-size:20px;">↓</div>
        <div style="background:var(--bg-card);border:1px solid var(--accent-green);border-radius:6px;padding:12px;">
          <strong>④ 引き金（反発足）＝ あなたが当日に確認 🔔</strong>
          <p style="color:var(--text-muted);margin:6px 0 0 0;font-size:.88em">
            ダッシュボードは③までを自動抽出して<strong>ウォッチリスト</strong>にします。最後の引き金は
            <strong>夜、米国寄り付き後の数時間で反発足（陽線確定 or 前日高値超え）を自分で確認</strong>して引きます。
            <span style="color:#f87171">落下中は絶対に掴まない。</span>
          </p>
        </div>
      </div>
      <p style="color:var(--text-muted);margin-top:10px;font-size:.82em;">
        ※ 反発足はリアルタイム判断が本質のため自動化しません（週末スクリーニング時点の反発足は、平日エントリー時には古くなるため）。
      </p>
    </div>

    <!-- リスク設計 -->
    <div class="card" style="margin-bottom:16px;">
      <h3>リスク設計（各候補に自動計算して表示）</h3>
      <table class="guide-table">
        <thead><tr><th>項目</th><th>ルール</th></tr></thead>
        <tbody>
          <tr><td><strong>損切り（1R）</strong></td><td>直近20日の押し安値の少し下に<span style="color:#f87171">固定・裁量で動かさない</span>。エントリー〜損切りの値幅＝1R</td></tr>
          <tr><td><strong>第1利確</strong></td><td><span style="color:var(--accent-green)">+1.5R で半分を確定</span>（負けトレードの損失をほぼ相殺＝メンタルが軽くなる）</td></tr>
          <tr><td><strong>残り半分</strong></td><td>20日EMA を<strong>終値で割るまで保有</strong>（トレーリングでトレンドに乗せ続ける）。感情でなく機械的に</td></tr>
          <tr><td><strong>保有上限</strong></td><td><span style="color:#f87171">8営業日経過で含み損なら問答無用で全決済</span>。8日超で持つのは含み益が伸びる強トレンド時のみ</td></tr>
          <tr><td><strong>ポジションサイズ</strong></td><td>1トレードの損失上限＝口座の1〜2%。株数＝（口座資金 × リスク%）÷ 1Rの値幅</td></tr>
        </tbody>
      </table>
    </div>

    <!-- 判定ラベル -->
    <div class="card" style="margin-bottom:16px;">
      <h3>候補リストの判定ラベル</h3>
      <ul style="margin:0 0 0 16px;color:var(--text-muted);">
        <li><strong style="color:var(--accent-green)">最優先候補</strong>：EMAタッチ（±2%）済み。反発足を当日確認すれば引き金。出来高枯れ併発ならさらに優先</li>
        <li><strong>サポート接近中</strong>：EMAに接近（±5%）。タッチ待ちのウォッチ対象</li>
        <li><strong style="color:#f87171">地合いNG（休む推奨）</strong>：指数が200日EMA割れ。v3では無理に買わず休む局面</li>
      </ul>
    </div>

    <!-- 期待値 -->
    <div class="card">
      <h3>現実的な期待値の置き方</h3>
      <ul style="margin:0 0 0 16px;color:var(--text-muted);">
        <li>押し目買いはフィルターを足しても勝率の上限は <strong>55〜60%台</strong>。100%見抜く方法はない。</li>
        <li>月次10%は「毎月のノルマ」ではなく「良い月に結果として出る上限イメージ」。</li>
        <li>ノルマ化すると「早すぎる利確」「無理なトレード増」を誘発し、RRを自分で削ってしまう。</li>
      </ul>
    </div>
  </div>`;
}
