/**
 * 押し目リバーサル（logic5）の説明ページ
 *
 * 数字はすべて 10年 × 630銘柄のバックテスト実測。
 * 2017-2023 を学習期間として条件を選び、2024-2026 を検証期間として答え合わせしている
 * （＝検証期間の数字は、条件を決めるときに一度も見ていない）。
 */
export function renderLogic5StrategyGuide(container) {
  const muted = "color:var(--text-muted);";
  const g = "color:var(--accent-green,#34d399);";
  const r = "color:#f87171;";

  container.innerHTML = `
  <div class="strategy-guide" style="max-width:900px;margin:0 auto;padding:16px;">
    <h2 style="margin-bottom:6px">押し目リバーサル</h2>
    <p style="${muted}margin-bottom:20px;">
      <strong>「押し目にいる」だけでは買いません。「押し目が止まって上に向いた証拠」が
      何個そろったかで買います。</strong>
      上昇トレンドの銘柄が20日／50日EMAまで押してきたとき、そこで反転したことを示す独立した根拠
      （プライスアクション7種・オシレーター3種）を数え、
      <strong>4つ以上＋オシレーター1つ以上</strong>そろったものだけをシグナルにします。
    </p>

    <div class="card" style="margin-bottom:16px;border-left:3px solid var(--blue);">
      <h3>実測でわかったこと（これが設計の根拠）</h3>
      <ul style="margin:10px 0 0 16px;line-height:1.9;">
        <li>
          <strong>条件をいくら積んでも勝率は 54% → 58% で頭打ちだった。</strong>
          プライスアクションもオシレーターも、増やすほど勝てるという関係にはならない。
          「勝率を上げる魔法の条件」は存在しなかった。
        </li>
        <li>
          <strong>条件の価値は勝率ではなく「負けの質」にある。</strong>
          反転の証拠を要求すると、勝率はわずかしか上がらないのに
          期待値が <span style="${g}">+0.115R → +0.161R（+40%）</span>、
          Profit Factor が <span style="${g}">1.30 → 1.46</span>、
          最大ドローダウンが <span style="${g}">−27R → −11R（半分以下）</span>になる。
        </li>
        <li>
          <strong>勝率60%超えを狙うなら、条件ではなく利確幅を下げるしかない。</strong>
          勝率は実質「+1.0Rに到達した割合」なので、利確を +0.75R にすれば約60%、
          +0.5R にすれば約67%になる。ただし1回の勝ちは薄くなる。
          このロジックは<strong>期待値を優先して +1.0R</strong> を採用している。
        </li>
        <li>
          <strong>地合いフィルターは採用しなかった。</strong>
          「200日EMA超えの銘柄比率 &gt; 50%」を試したが、弱気相場の年を救わないどころか
          勝ちトレードを削って通算を悪化させた（マイナスの年が2→3に増加）。
        </li>
      </ul>
    </div>

    <div class="card" style="margin-bottom:16px;">
      <h3>① 押し目の「場所」にいるか（すべて必須）</h3>
      <table class="guide-table">
        <thead><tr><th>項目</th><th>条件</th></tr></thead>
        <tbody>
          <tr><td>トレンド</td><td>株価 &gt; 200日EMA <strong>かつ</strong> 50日EMA &gt; 200日EMA</td></tr>
          <tr><td>モメンタム</td><td>3ヶ月騰落率 &gt; 0%</td></tr>
          <tr><td>流動性</td><td>20日平均出来高 ≥ 100万株</td></tr>
          <tr><td>押し目</td><td>20日 or 50日EMA から <strong>±5%以内</strong></td></tr>
        </tbody>
      </table>
    </div>

    <div class="card" style="margin-bottom:16px;">
      <h3>② 反転の証拠 — プライスアクション（7つのうち <span style="${g}">4つ以上</span>）</h3>
      <table class="guide-table">
        <thead><tr><th>条件</th><th>意味</th></tr></thead>
        <tbody>
          <tr><td>陽線で確定</td><td>その日を買いで終えた</td></tr>
          <tr><td>下ヒゲが長い（値幅の40%以上）</td><td>安値で買い支えが入った</td></tr>
          <tr><td>終値が高値圏（値幅の上位30%）</td><td>引けにかけて買われた</td></tr>
          <tr><td>安値切り上げ2連</td><td>3日で安値が上がり続けている＝下げ止まり</td></tr>
          <tr><td>前日高値を超えて確定</td><td>前日の売り手を飲み込んだ</td></tr>
          <tr><td>インサイドバー上抜け</td><td>収縮 → 上放れ</td></tr>
          <tr><td>包み足（強気エンガルフィング）</td><td>前日の陰線を丸ごと包んだ</td></tr>
        </tbody>
      </table>

      <h3 style="margin-top:18px;">③ 反転の証拠 — オシレーター（3つのうち <span style="${g}">1つ以上</span>）</h3>
      <table class="guide-table">
        <tbody>
          <tr><td>RSIが上向き</td><td>前日より上を向いた</td></tr>
          <tr><td>ストキャスティクス %K が %D を上抜け</td><td>短期の売り圧が反転</td></tr>
          <tr><td>MACDヒストグラムが上向き</td><td>下落の勢いが減衰</td></tr>
        </tbody>
      </table>
      <p style="${muted}margin-top:10px;font-size:.9em;">
        同一銘柄は<strong>30営業日クールダウン</strong>（同じ銘柄で建玉を重ねない。バックテストと同条件）。
      </p>
    </div>

    <div class="card" style="margin-bottom:16px;">
      <h3>出口（1R = エントリー − 損切り）</h3>
      <table class="guide-table">
        <thead><tr><th>項目</th><th>ルール</th></tr></thead>
        <tbody>
          <tr><td>損切り</td><td>直近20日の押し安値 − 0.1×ATR に固定。<strong>裁量で動かさない</strong></td></tr>
          <tr><td>第1利確</td><td><strong>+1.0R で半分</strong>を利確</td></tr>
          <tr><td>残り半分</td><td>ストップを<strong>建値</strong>へ切り上げ → <strong>+4R</strong> ターゲット</td></tr>
          <tr><td>見直し期限</td><td>30営業日</td></tr>
        </tbody>
      </table>
    </div>

    <div class="card" style="margin-bottom:16px;">
      <h3>バックテスト実績（10年 × 630銘柄・3,597トレード）</h3>
      <table class="guide-table">
        <thead>
          <tr><th>年</th><th>件数</th><th>勝率</th><th>期待値</th><th>PF</th><th>累積R</th><th>最大DD</th><th></th></tr>
        </thead>
        <tbody>
          <tr><td>2017</td><td>295</td><td>65.4%</td><td style="${g}">+0.375R</td><td>2.36</td><td style="${g}">+110.6R</td><td style="${r}">−6.7R</td><td style="${muted}">学習</td></tr>
          <tr><td>2018</td><td>437</td><td style="${r}">48.7%</td><td style="${r}">−0.039R</td><td>0.91</td><td style="${r}">−16.9R</td><td style="${r}">−25.8R</td><td style="${muted}">学習</td></tr>
          <tr><td>2019</td><td>404</td><td>65.3%</td><td style="${g}">+0.325R</td><td>2.25</td><td style="${g}">+131.3R</td><td style="${r}">−5.8R</td><td style="${muted}">学習</td></tr>
          <tr><td>2020</td><td>249</td><td>53.4%</td><td style="${g}">+0.100R</td><td>1.25</td><td style="${g}">+24.8R</td><td style="${r}">−10.1R</td><td style="${muted}">学習</td></tr>
          <tr><td>2021</td><td>536</td><td>53.2%</td><td style="${g}">+0.092R</td><td>1.25</td><td style="${g}">+49.5R</td><td style="${r}">−14.0R</td><td style="${muted}">学習</td></tr>
          <tr><td>2022</td><td>269</td><td style="${r}">45.0%</td><td style="${r}">−0.124R</td><td>0.73</td><td style="${r}">−33.3R</td><td style="${r}">−40.5R</td><td style="${muted}">学習</td></tr>
          <tr><td>2023</td><td>313</td><td>51.8%</td><td style="${g}">+0.033R</td><td>1.08</td><td style="${g}">+10.4R</td><td style="${r}">−18.8R</td><td style="${muted}">学習</td></tr>
          <tr style="background:rgba(59,130,246,.08)"><td><strong>2024</strong></td><td>453</td><td><strong>59.8%</strong></td><td style="${g}"><strong>+0.198R</strong></td><td>1.59</td><td style="${g}"><strong>+89.5R</strong></td><td style="${r}">−7.5R</td><td style="color:var(--blue)"><strong>検証</strong></td></tr>
          <tr style="background:rgba(59,130,246,.08)"><td><strong>2025</strong></td><td>452</td><td><strong>52.7%</strong></td><td style="${g}"><strong>+0.099R</strong></td><td>1.26</td><td style="${g}"><strong>+44.7R</strong></td><td style="${r}">−13.5R</td><td style="color:var(--blue)"><strong>検証</strong></td></tr>
          <tr style="background:rgba(59,130,246,.08)"><td><strong>2026</strong></td><td>189</td><td><strong>59.3%</strong></td><td style="${g}"><strong>+0.222R</strong></td><td>1.71</td><td style="${g}"><strong>+42.0R</strong></td><td style="${r}">−6.0R</td><td style="color:var(--blue)"><strong>検証</strong></td></tr>
          <tr><td><strong>通算</strong></td><td><strong>3,597</strong></td><td><strong>55.4%</strong></td><td style="${g}"><strong>+0.126R</strong></td><td><strong>1.35</strong></td><td style="${g}"><strong>+452.7R</strong></td><td style="${r}"><strong>−34.1R</strong></td><td></td></tr>
        </tbody>
      </table>
      <p style="${muted}margin-top:10px;font-size:.9em;">
        「検証」の3年は、条件を決めるときに<strong>一度も見ていない</strong>期間です。
        学習期間と同等以上の成績が出ているので、単なる過去へのカーブフィットではありません。
      </p>
    </div>

    <div class="card" style="margin-bottom:16px;border-left:3px solid #f87171;">
      <h3>⚠️ 正直な弱点</h3>
      <ul style="margin:10px 0 0 16px;line-height:1.9;">
        <li>
          <strong>弱気相場では負ける。</strong>
          2018年（−16.9R）と2022年（−33.3R）はマイナス。ロング専用の押し目買いなので当然で、
          <strong>10年のうち2年は負ける前提</strong>で使うこと。地合いフィルターでは救えないことを確認済み。
        </li>
        <li>
          <strong>1回の勝ちは大きくない。</strong>
          勝率55%だが、平均勝ちより平均負けの方が金額は大きい。
          エッジは「+0.126R × 回数」で積み上がるタイプで、1発逆転はない。
        </li>
        <li>
          <strong>生存バイアスがある。</strong>
          ユニバースは現在の銘柄リストなので、過去に上場廃止・指数除外された銘柄が含まれていない。
          実際の成績はこれより多少悪くなる可能性がある。
        </li>
        <li>
          <strong>決算跨ぎを除外していない。</strong>
          バックテストが決算日を考慮していないため、それに合わせてある。
          決算発表直前の銘柄は自分の判断で見送ること。
        </li>
      </ul>
    </div>

    <div class="card">
      <h3>厳選押し目買いv2（logic4）との違い</h3>
      <table class="guide-table">
        <thead><tr><th></th><th>厳選押し目買いv2</th><th>押し目リバーサル</th></tr></thead>
        <tbody>
          <tr><td>押し目の場所</td><td>EMAタッチ（±2%）＋出来高枯れ<br>＝場所を厳しく絞る</td><td>EMA ±5%圏<br>＝場所は広く取る</td></tr>
          <tr><td>採用の決め手</td><td>反発足確認 ＋ SL幅≤5%</td><td><strong>反転の証拠の数</strong><br>（PA 4/7 ＋ OSC 1/3）</td></tr>
          <tr><td>第1利確</td><td>+1.5R で半分</td><td><strong>+1.0R</strong> で半分</td></tr>
          <tr><td>ターゲット</td><td>+3R</td><td><strong>+4R</strong></td></tr>
        </tbody>
      </table>
      <p style="${muted}margin-top:10px;font-size:.9em;">
        バックテストでは v2 の「SL幅≤5%」「EMAタッチ」は<strong>単独ではむしろマイナス</strong>でした。
        どちらが本当に優れているかは両方を並走させ、「⏱ Intraday戦績」タブで
        フォワードの実データで判定します。
      </p>
    </div>
  </div>
  `;
}
