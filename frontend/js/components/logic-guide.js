const STYLE = `
  .logic-guide { --lg-bg:#0d1727; --lg-panel:#111c30; --lg-line:#2a3a54; --lg-blue:#60a5fa; --lg-green:#86efac; --lg-amber:#fbbf24; --lg-red:#fca5a5; display:grid; gap:18px; color:#dbe5f3; line-height:1.8; }
  .logic-guide * { box-sizing:border-box; }
  .logic-guide > * { min-width:0; }
  .lg-hero { position:relative; overflow:hidden; padding:28px; border:1px solid var(--lg-line); border-radius:16px; background:linear-gradient(125deg,#101f36 0%,#0d1727 65%,#152b46 100%); }
  .lg-hero::after { content:"LOGIC"; position:absolute; right:18px; bottom:-25px; color:rgba(96,165,250,.055); font-size:7rem; font-weight:950; letter-spacing:-.08em; pointer-events:none; }
  .lg-kicker { color:var(--lg-blue); font-size:.7rem; font-weight:850; letter-spacing:.18em; text-transform:uppercase; }
  .lg-hero h2 { position:relative; z-index:1; margin:4px 0 6px; color:#f8fafc; font-size:clamp(1.55rem,4vw,2.2rem); letter-spacing:.02em; }
  .lg-hero p { position:relative; z-index:1; max-width:720px; margin:0; color:#aebdd0; font-size:.88rem; }
  .lg-toc { padding:17px 18px; border:1px solid var(--lg-line); border-radius:13px; background:var(--lg-panel); }
  .lg-toc-title { margin:0 0 10px; color:#f1f5f9; font-size:.82rem; font-weight:850; letter-spacing:.08em; }
  .lg-toc ol { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:5px 24px; margin:0; padding-left:1.5rem; }
  .lg-toc li { color:#6f86a2; font-size:.75rem; }
  .lg-toc a { color:#bcd5f4; text-decoration:none; }
  .lg-toc a:hover { color:#fff; text-decoration:underline; }
  .lg-section { scroll-margin-top:76px; padding:22px; border:1px solid var(--lg-line); border-radius:14px; background:var(--lg-panel); }
  .lg-section-head { display:flex; align-items:center; gap:11px; margin-bottom:14px; }
  .lg-section-no { display:grid; flex:0 0 31px; height:31px; place-items:center; border:1px solid #395a80; border-radius:8px; color:#93c5fd; background:#142944; font-size:.7rem; font-weight:900; font-variant-numeric:tabular-nums; }
  .lg-section h3 { margin:0; color:#f1f5f9; font-size:1.05rem; letter-spacing:.02em; }
  .lg-section h4 { margin:18px 0 6px; color:#dbeafe; font-size:.82rem; }
  .lg-section p { margin:8px 0; color:#b4c2d4; font-size:.82rem; overflow-wrap:anywhere; }
  .lg-section ul { margin:8px 0; padding-left:1.35rem; color:#b4c2d4; font-size:.82rem; }
  .lg-section li { overflow-wrap:anywhere; }
  .lg-section li + li { margin-top:6px; }
  .lg-section strong { color:#edf5ff; }
  .lg-lead { padding:11px 13px; border-left:3px solid var(--lg-blue); border-radius:0 8px 8px 0; background:rgba(59,130,246,.075); color:#d5e6fb !important; }
  .lg-strict { margin-top:14px !important; padding:11px 13px; border:1px solid #344762; border-radius:9px; background:#0b1422; color:#9fb0c4 !important; font-size:.75rem !important; }
  .lg-strict strong { color:#c5d8ee; }
  .lg-strict code { overflow-wrap:anywhere; color:#b9dcff; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }
  .lg-callout { margin-top:13px; padding:11px 13px; border:1px solid rgba(251,191,36,.24); border-radius:9px; background:rgba(245,158,11,.075); color:#e8d7a9; font-size:.77rem; }
  .lg-callout strong { color:#fde68a; }
  .lg-funnel { display:grid; grid-template-columns:repeat(7,auto); align-items:center; justify-content:center; gap:10px; margin:19px 0 15px; }
  .lg-funnel-step { min-width:130px; padding:13px 14px; border:1px solid #34506f; border-radius:10px; background:#0c1829; text-align:center; }
  .lg-funnel-step span { display:block; color:#91a4bb; font-size:.68rem; }
  .lg-funnel-step strong { display:block; margin-top:2px; color:#f1f5f9; font-size:1.2rem; font-variant-numeric:tabular-nums; }
  .lg-funnel-arrow { color:#527195; font-weight:900; }
  .lg-metric-row { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:13px; }
  .lg-metric { padding:11px; border:1px solid #30435e; border-radius:9px; background:#0d1727; text-align:center; }
  .lg-metric strong { display:block; color:#dbeafe; font-size:1.05rem; }
  .lg-metric span { color:#8ea1b9; font-size:.67rem; }
  .lg-rule-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:9px; margin:12px 0; }
  .lg-rule { padding:11px; border:1px solid #30435e; border-radius:9px; background:#0d1727; }
  .lg-rule strong { display:block; color:#dbeafe; font-size:.78rem; }
  .lg-rule span { display:block; margin-top:3px; color:#9eafc3; font-size:.71rem; }
  .lg-table-wrap { width:100%; min-width:0; margin-top:13px; overflow-x:auto; border:1px solid #2c3e58; border-radius:10px; }
  .lg-table { width:100%; min-width:680px; border-collapse:collapse; font-size:.72rem; line-height:1.6; }
  .lg-table th { padding:9px 10px; border-bottom:1px solid #39506f; background:#16243a; color:#cde3fb; text-align:left; white-space:nowrap; }
  .lg-table td { padding:9px 10px; border-bottom:1px solid rgba(51,65,85,.65); color:#aebdd0; vertical-align:top; }
  .lg-table tr:last-child td { border-bottom:0; }
  .lg-table td:first-child { color:#eef6ff; font-weight:750; white-space:nowrap; }
  .lg-table tbody tr:hover { background:rgba(59,130,246,.045); }
  .lg-priority { display:inline-grid; min-width:20px; height:20px; margin-right:6px; place-items:center; border-radius:5px; background:#243853; color:#a9c8ec; font-size:.62rem; }
  .lg-tag-up { color:var(--lg-green); }
  .lg-tag-warn { color:#fde68a; }
  .lg-tag-down { color:var(--lg-red); }
  .lg-footnote { color:#8fa2b8 !important; font-size:.73rem !important; }
  .lg-back { display:inline-block; margin-top:14px; color:#8dbcf2; font-size:.7rem; text-decoration:none; }
  .lg-back:hover { color:#dbeafe; }
  @media (max-width:820px) {
    .lg-funnel { grid-template-columns:1fr; gap:6px; }
    .lg-funnel-step { width:100%; }
    .lg-funnel-arrow { transform:rotate(90deg); text-align:center; line-height:1; }
    .lg-rule-grid { grid-template-columns:1fr; }
  }
  @media (max-width:480px) {
    .logic-guide { gap:12px; }
    .lg-hero { padding:20px 16px; }
    .lg-hero::after { font-size:4.2rem; }
    .lg-toc { padding:14px; }
    .lg-toc ol { grid-template-columns:1fr; }
    .lg-section { padding:16px 13px; }
    .lg-section-head { align-items:flex-start; }
    .lg-section h3 { font-size:.98rem; }
    .lg-metric-row { grid-template-columns:1fr; }
    .lg-table { min-width:520px; }
  }
`;

// 他のコンポーネントと同じ安全な文字列挿入パターン。現在は静的テキストのみを扱う。
function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

const TOC = [
  ["flow", "全体の流れ"],
  ["universe", "銘柄の母集団（ユニバース）"],
  ["w1-po", "W1 パーフェクトオーダー"],
  ["d1-pullback", "D1 押し目"],
  ["state-badge", "状態バッジ"],
  ["dow", "ダウ理論"],
  ["adx", "ADX"],
  ["rs", "RS 相対強度"],
  ["volume", "出来高判定"],
  ["price-position", "価格位置"],
  ["columns", "一覧の各列の意味"],
  ["filters", "フィルタの挙動"],
  ["intraday", "銘柄詳細の15分足チャート"],
  ["data-limits", "データと制約"],
];

function sectionHead(number, title) {
  return `<div class="lg-section-head"><span class="lg-section-no">${number}</span><h3>${title}</h3></div>`;
}

export function renderLogicGuide(container) {
  container.innerHTML = `
    <style>${STYLE}</style>
    <article class="logic-guide" id="logic-guide-top">
      <header class="lg-hero">
        <div class="lg-kicker">Screening Field Manual</div>
        <h2>ロジック解説</h2>
        <p>このページでは、押し目スクリーナーが「何を見て、なぜ候補に残すのか」を、トレードの言葉で順番に説明します。まず意味を読み、必要なときだけ各項目末尾の「厳密な条件」を確認してください。</p>
      </header>

      <nav class="lg-toc" aria-label="ロジック解説の目次">
        <div class="lg-toc-title">目次</div>
        <ol>${TOC.map(([id, label]) => `<li><a href="#${id}">${label}</a></li>`).join("")}</ol>
      </nav>

      <section class="lg-section" id="flow">
        ${sectionHead("01", "全体の流れ")}
        <p class="lg-lead">約4,400銘柄を一度に順位付けするのではなく、「十分なデータ」「実際に売買できる流動性」「週足の上昇トレンド」「日足の押し目」の順にふるいへかけます。</p>
        <div class="lg-funnel" aria-label="スクリーニングのファネル">
          <div class="lg-funnel-step"><span>データ十分</span><strong>3,628</strong></div><span class="lg-funnel-arrow">→</span>
          <div class="lg-funnel-step"><span>流動性</span><strong>1,613</strong></div><span class="lg-funnel-arrow">→</span>
          <div class="lg-funnel-step"><span>W1 パーフェクトオーダー</span><strong>509</strong></div><span class="lg-funnel-arrow">→</span>
          <div class="lg-funnel-step"><span>D1 押し目</span><strong>272</strong></div>
        </div>
        <p>上の数字はあるスキャン日の実測例です。相場環境によって件数は変わります。判定は<strong>毎日、取引終了後に自動で再計算</strong>されます。</p>
        <a class="lg-back" href="#logic-guide-top">↑ 目次へ戻る</a>
      </section>

      <section class="lg-section" id="universe">
        ${sectionHead("02", "銘柄の母集団（ユニバース）")}
        <p class="lg-lead">米国株 約4,400銘柄から、データの信頼性と売買のしやすさを確保できる銘柄だけを対象にします。</p>
        <ul>
          <li>直近60日の<strong>1日あたり売買代金の中央値が2,000万ドル以上</strong>。一時的な出来高急増ではなく、普段から実際に売買できる流動性を確保します。</li>
          <li><strong>株価5ドル以上</strong>。値動きが不安定になりやすい低位株のノイズを除きます。</li>
          <li>株価データが<strong>1,300営業日（約5年）以上</strong>あること。長期移動平均を安定して計算するためです。</li>
          <li>最終取引日が最新スキャン日と一致すること。上場廃止や売買停止など、価格が更新されていない銘柄を除きます。</li>
        </ul>
        <p class="lg-strict"><strong>厳密な条件:</strong> 60日売買代金中央値 ≥ $20,000,000、最新終値 ≥ $5、価格データ ≥ 1,300営業日、最終取引日 = 最新スキャン日。</p>
        <a class="lg-back" href="#logic-guide-top">↑ 目次へ戻る</a>
      </section>

      <section class="lg-section" id="w1-po">
        ${sectionHead("03", "W1 パーフェクトオーダー（必須条件）")}
        <p class="lg-lead">週足で「長期から短期まで、上昇の向きがそろっている銘柄」だけを残すための必須条件です。</p>
        <ul>
          <li>週足で<strong>20週・50週・200週の単純移動平均（SMA）</strong>を計算します。</li>
          <li><strong>並び順:</strong> 終値 &gt; 20週線 &gt; 50週線 &gt; 200週線。短期の価格ほど上にある、素直な上昇トレンドです。</li>
          <li><strong>傾き:</strong> 3本の移動平均すべてが4週前より上にあること。上昇トレンドがまだ生きているかを見ます。</li>
        </ul>
        <p>並び順だけを見ると、すでに天井を打って失速し始めた銘柄まで残ることがあります。実測では、並び順だけにすると<strong>194銘柄多く通過</strong>し、その中には20週線が下向きの銘柄も含まれていました。</p>
        <p>200週は約3.85年です。つまり、一時的に上がっただけではなく、長期の上昇基調がある銘柄に限定されます。</p>
        <div class="lg-callout"><strong>注意:</strong> 今週の週足バーは週の途中ではまだ未確定です。そのためW1判定は週内に入れ替わることがあります。</div>
        <p class="lg-strict"><strong>厳密な条件:</strong> <code>Close &gt; SMA20 &gt; SMA50 &gt; SMA200</code> かつ <code>SMA20 &gt; SMA20[4週前]</code> かつ <code>SMA50 &gt; SMA50[4週前]</code> かつ <code>SMA200 &gt; SMA200[4週前]</code></p>
        <a class="lg-back" href="#logic-guide-top">↑ 目次へ戻る</a>
      </section>

      <section class="lg-section" id="d1-pullback">
        ${sectionHead("04", "D1 押し目（必須条件）")}
        <p class="lg-lead">日足の20EMA（指数移動平均）まで価格が近づき、現在はその上で引けている銘柄を探します。</p>
        <ul>
          <li><strong>直近3営業日以内</strong>に、安値が20EMAの2%以内まで下がったことを「タッチ」とします。</li>
          <li>そのうえで、<strong>現在の終値が20EMAより上</strong>にあることが必要です。</li>
          <li>一覧の「タッチ」列は、タッチしてから何営業日目かを1〜3で示します。</li>
        </ul>
        <p>当日のタッチだけにすると、きれいに反発した翌日や翌々日に候補から消えてしまいます。実測では、当日のみなら315銘柄だったのに対し、<strong>3日窓では438銘柄</strong>を拾えました。</p>
        <p class="lg-strict"><strong>厳密な条件:</strong> 直近3営業日のいずれかで <code>Low &lt;= EMA20 * 1.02</code>、かつ最新の <code>Close &gt; EMA20</code></p>
        <a class="lg-back" href="#logic-guide-top">↑ 目次へ戻る</a>
      </section>

      <section class="lg-section" id="state-badge">
        ${sectionHead("05", "状態バッジ（✅反発確認済 / ⏳押し目進行中）")}
        <div class="lg-rule-grid">
          <div class="lg-rule"><strong class="lg-tag-up">✅ 反発確認済</strong><span>当日が陽線、つまり終値が始値より高い状態。</span></div>
          <div class="lg-rule"><strong class="lg-tag-warn">⏳ 押し目進行中</strong><span>陽線以外。まだ押している途中、または当日の反発を確認できていない状態。</span></div>
          <div class="lg-rule"><strong>候補の合否とは別</strong><span>このバッジは絞り込み条件ではなく、現在地を伝える状態表示です。</span></div>
        </div>
        <p>陽線を必須にすると、市場全体が下げた日にリストがほぼ空になります。実測では1日あたりの候補が<strong>47件から25件へ半減</strong>しました。押し目を探したいのはまさに市場が下げている日なので、その日に候補が見えないのは本末転倒です。</p>
        <p class="lg-strict"><strong>厳密な条件:</strong> ✅反発確認済 = <code>Close &gt; Open</code>。それ以外 = ⏳押し目進行中。いずれも必須スクリーニング条件には含めません。</p>
        <a class="lg-back" href="#logic-guide-top">↑ 目次へ戻る</a>
      </section>

      <section class="lg-section" id="dow">
        ${sectionHead("06", "ダウ理論（デフォルトON）")}
        <p>日足で、前後5日の中で最高値または最安値になっている点を探し、確定した「山」と「谷」として扱います。直近2つの山と、直近2つの谷を比べます。</p>
        <div class="lg-rule-grid">
          <div class="lg-rule"><strong class="lg-tag-up">上昇</strong><span>高値切り上げ AND 安値切り上げ。</span></div>
          <div class="lg-rule"><strong class="lg-tag-down">下降</strong><span>高値切り下げ AND 安値切り下げ。</span></div>
          <div class="lg-rule"><strong>中立</strong><span>高値・安値のどちらか片方だけが切り上がっている状態。</span></div>
        </div>
        <p>既定では<strong>「下降」だけを除外</strong>します。「上昇のみ」にしないのは、押し目形成中には直近の安値がまだ確定せず「中立」になりやすいためです。中立まで外すと、狙っている深めの押し目を弾いてしまいます。</p>
        <p class="lg-strict"><strong>厳密な条件:</strong> 前後5日で確定した直近2つのスイング高値・安値を比較。上昇 = 高値切り上げ AND 安値切り上げ、下降 = 高値切り下げ AND 安値切り下げ、その他 = 中立。既定フィルタは下降を除外。</p>
        <a class="lg-back" href="#logic-guide-top">↑ 目次へ戻る</a>
      </section>

      <section class="lg-section" id="adx">
        ${sectionHead("07", "ADX（デフォルトON）")}
        <p class="lg-lead">ADXはトレンドの「方向」ではなく「強さ」を測る指標です。既定では25以上を残し、方向感なく行ったり来たりするレンジ相場を除きます。</p>
        <p>押し目では直前までの勢いがいったん弱まるため、ADXは必ず下がります。「今まさに押している」と「ADXが高い」は構造的に引っ張り合います。このため固定値にはせず、<strong>15〜35のスライダー</strong>で相場に合わせて調整できます。</p>
        <p>実測では292銘柄から、閾値25で117銘柄まで減りました。現在の補助フィルタの中で<strong>最も強く候補を絞り込む</strong>項目です。</p>
        <p class="lg-strict"><strong>厳密な条件:</strong> ADXフィルタON時は最新ADXが選択した下限値以上。初期値は <code>ADX &gt;= 25</code>、変更範囲は15〜35。</p>
        <a class="lg-back" href="#logic-guide-top">↑ 目次へ戻る</a>
      </section>

      <section class="lg-section" id="rs">
        ${sectionHead("08", "RS 相対強度（並び替えのキー）")}
        <p>その銘柄の3ヶ月・6ヶ月リターンから、同じ期間のSPY（S&amp;P 500 ETF）のリターンを引いた値です。プラスなら市場平均より強く、マイナスなら市場平均より弱いことを表します。既定では<strong>RS 6Mの降順</strong>に並びます。</p>
        <p>RSはフィルタにはしていません。実測ではADXの後に適用しても候補を<strong>8%しか削らず</strong>、絞り込みとしてはほとんど効かなかったためです。強い候補から目を通せる並び替えのキーとして使う方が価値があります。</p>
        <p class="lg-strict"><strong>厳密な条件:</strong> <code>RS 3M = 銘柄の3ヶ月リターン − SPYの3ヶ月リターン</code>、<code>RS 6M = 銘柄の6ヶ月リターン − SPYの6ヶ月リターン</code>。合否条件には使用しません。</p>
        <a class="lg-back" href="#logic-guide-top">↑ 目次へ戻る</a>
      </section>

      <section class="lg-section" id="volume">
        ${sectionHead("09", "出来高判定（9パターン）")}
        <p class="lg-lead">価格だけでなく「その動きにどれだけ売買が伴ったか」を見ます。判定には優先順位があり、<strong>表の上から評価して最初に当てはまったもの</strong>が採用されます。</p>
        <div class="lg-table-wrap">
          <table class="lg-table">
            <thead><tr><th>バッジ</th><th>意味</th><th>判定条件（日本語）</th><th>使いどころ</th></tr></thead>
            <tbody>
              <tr><td><span class="lg-priority">1</span>🔄 セリクラの可能性</td><td>投げ売りが一巡した可能性</td><td>安値圏で、実体がATR以上の大陰線、かつ当日出来高が50日平均の2倍以上</td><td>急落の終盤候補。ただし反転確認前のため慎重に見る</td></tr>
              <tr><td><span class="lg-priority">2</span>✅ 買い意欲</td><td>安値圏での買い集め</td><td>安値圏で陽線、かつ当日出来高が1.5倍以上</td><td>安値圏で買い手が現れた初動を探す</td></tr>
              <tr><td><span class="lg-priority">3</span>⚠️ 分配の疑い</td><td>高値で利確売りが出ている</td><td>高値圏で、週の出来高が前週比1.2倍以上なのに株価がほぼ動いていない（+1%以下）</td><td>上値の重さと大口の売り抜けに警戒する</td></tr>
              <tr><td><span class="lg-priority">4</span>⚠️ 売り圧力</td><td>押し目ではなく下落転換の疑い</td><td>週の株価が-2%以下、かつ週の出来高が前週比1.2倍以上</td><td>通常の押し目を超えた強い売りを避ける</td></tr>
              <tr><td><span class="lg-priority">5</span>✅ 出来高を伴う反発</td><td>押し目買いが実際に入っている</td><td>反発済みで、当日出来高が1.2倍以上</td><td>反発の信頼度が高い候補を優先する</td></tr>
              <tr><td><span class="lg-priority">6</span>⚠️ 出来高薄い反発</td><td>買いの勢いが確認できない</td><td>反発済みだが、当日出来高が0.8倍未満</td><td>見た目だけの反発になっていないか注意する</td></tr>
              <tr><td><span class="lg-priority">7</span>✅ 健全な押し目</td><td>売り物が枯れつつある</td><td>週の株価が下落かつ週の出来高が0.8倍以下、または押し目進行中で当日出来高が0.8倍以下</td><td>売り圧力の弱い静かな押し目を探す</td></tr>
              <tr><td><span class="lg-priority">8</span>💤 ブレイク待ち</td><td>エネルギーを溜めている</td><td>週の出来高が0.8倍以下、かつ直近5日の値幅がその前5日より小さい</td><td>値幅収縮後の動き出しを監視する</td></tr>
              <tr><td><span class="lg-priority">9</span>―</td><td>特筆すべきシグナルなし</td><td>上記のいずれにも当てはまらない</td><td>他の指標やチャート形状を中心に判断する</td></tr>
            </tbody>
          </table>
        </div>
        <h4>判定で使う言葉</h4>
        <ul>
          <li>「当日出来高◯倍」はすべて<strong>50日平均出来高との比</strong>です。</li>
          <li>「安値圏／高値圏」は直近60日の値幅の中での位置です。30%以下が安値圏、70%以上が高値圏です。</li>
          <li>上昇トレンドを前提とするスクリーナーのため、実際には<strong>高値圏の銘柄が約8割</strong>を占めます。</li>
        </ul>
        <p class="lg-footnote"><strong>実測の分布例（272銘柄中）:</strong> ― 108 / ⚠️出来高薄い反発 58 / ✅健全な押し目 37 / ✅出来高を伴う反発 35 / 💤ブレイク待ち 18 / ⚠️分配の疑い 12 / その他 4</p>
        <p class="lg-strict"><strong>厳密な条件:</strong> 上表の1から9を順番に判定し、最初に真となった1種類だけを表示します。複数条件に当てはまってもバッジは重複しません。</p>
        <a class="lg-back" href="#logic-guide-top">↑ 目次へ戻る</a>
      </section>

      <section class="lg-section" id="price-position">
        ${sectionHead("10", "価格位置")}
        <p>直近60日の最安値から最高値までをひとつのレンジと考え、その中で現在の終値がどこにあるかを示します。</p>
        <div class="lg-rule-grid">
          <div class="lg-rule"><strong class="lg-tag-up">高値圏</strong><span>レンジの70%以上。直近高値に近い位置。</span></div>
          <div class="lg-rule"><strong>中間</strong><span>30%より上、70%未満。レンジの中央付近。</span></div>
          <div class="lg-rule"><strong class="lg-tag-warn">安値圏</strong><span>レンジの30%以下。直近安値に近い位置。</span></div>
        </div>
        <p class="lg-strict"><strong>厳密な条件:</strong> <code>(終値 − 60日最安値) ÷ (60日最高値 − 60日最安値)</code> の位置が70%以上 = 高値圏、30%以下 = 安値圏、その間 = 中間。</p>
        <a class="lg-back" href="#logic-guide-top">↑ 目次へ戻る</a>
      </section>

      <section class="lg-section" id="columns">
        ${sectionHead("11", "一覧の各列の意味")}
        <div class="lg-table-wrap">
          <table class="lg-table">
            <thead><tr><th>列</th><th>表示しているもの</th></tr></thead>
            <tbody>
              <tr><td>ティッカー</td><td>米国株の銘柄コード。クリックするとTradingViewを開けます。</td></tr>
              <tr><td>状態</td><td>当日が陽線なら「反発確認済」、それ以外なら「押し目進行中」です。</td></tr>
              <tr><td>出来高</td><td>価格と出来高の組み合わせから判定した、9種類の出来高シグナルです。</td></tr>
              <tr><td>ダウ理論</td><td>直近の山と谷が、上昇・下降・中立のどの形かを示します。</td></tr>
              <tr><td>タッチ</td><td>安値が20EMAの2%以内へ近づいてから何営業日目か（1〜3）です。</td></tr>
              <tr><td>株価</td><td>最新営業日の終値です。</td></tr>
              <tr><td>20EMA乖離%</td><td>終値が20EMAから何%離れているか。小さいほど20EMAの近くです。</td></tr>
              <tr><td>ADX</td><td>トレンドの方向ではなく強さ。一般に値が高いほど方向性が強い状態です。</td></tr>
              <tr><td>RS3M%</td><td>過去3ヶ月でSPYを何%上回った／下回ったかを示します。</td></tr>
              <tr><td>RS6M%</td><td>過去6ヶ月でSPYを何%上回った／下回ったかを示します。既定の並び替えキーです。</td></tr>
              <tr><td>ATR%</td><td>1日の平均的な値動き幅が株価の何%か。損切り幅やポジション量を考えるリスク量の目安です。</td></tr>
              <tr><td>売買代金($M)</td><td>直近60日の1日あたり売買代金の中央値を百万ドル単位で表示します。</td></tr>
              <tr><td>PO継続週</td><td>W1パーフェクトオーダーが何週連続で成立しているかを示します。</td></tr>
            </tbody>
          </table>
        </div>
        <a class="lg-back" href="#logic-guide-top">↑ 目次へ戻る</a>
      </section>

      <section class="lg-section" id="filters">
        ${sectionHead("12", "フィルタの挙動について")}
        <ul>
          <li><strong>出来高判定・ダウ理論・状態・価格位置</strong>の4つのフィルタ群は、それぞれ複数選択できます。</li>
          <li>ある群のチェックを全部外すと、その群は<strong>「絞り込みなし」</strong>として扱われます。全解除しても0件にはなりません。</li>
          <li>選んだ条件、ADX、並び順などの設定はブラウザに保存され、次回開いたときに復元されます。</li>
          <li>「デフォルトに戻す」を押すと、保存した設定を初期状態へ戻せます。</li>
        </ul>
        <p class="lg-strict"><strong>厳密な条件:</strong> 同じ群の選択肢はOR（いずれか）、異なる群どうしはAND（すべて）で評価します。選択数0の群は判定を省略します。</p>
        <a class="lg-back" href="#logic-guide-top">↑ 目次へ戻る</a>
      </section>

      <section class="lg-section" id="intraday">
        ${sectionHead("13", "銘柄詳細の15分足チャート")}
        <p>一覧で銘柄をクリックすると、直近5営業日の15分足が表示されます。通常取引時間のみが初期表示で、トグルを使うと時間外取引も表示できます。</p>
        <h4>チャート上に描かれるもの</h4>
        <ul>
          <li>日足の重要価格帯：20EMA、直近スイング高値／安値、出来高集中帯を水平線で表示</li>
          <li>下降トレンドラインと、そのトレンドラインを上抜いたブレイク位置</li>
          <li>ダブルボトム／逆三尊のネックライン</li>
          <li>上昇フラッグ／三角収束の上下ライン</li>
        </ul>
        <div class="lg-callout"><strong>注意:</strong> 15分足データはPolygonの無料枠を使用しているため、リアルタイムではなく15分遅延です。</div>
        <a class="lg-back" href="#logic-guide-top">↑ 目次へ戻る</a>
      </section>

      <section class="lg-section" id="data-limits">
        ${sectionHead("14", "データと制約")}
        <ul>
          <li>株価データは毎営業日の引け後に更新されます。GitHub Actionsが<strong>7:45 JST</strong>に実行されます。</li>
          <li>15分足はリアルタイムではなく<strong>15分遅延</strong>です。</li>
          <li>週足の当週バーは未確定のため、W1判定は週内に変わることがあります。</li>
          <li>このスクリーナーは<strong>ロング（買い）専用</strong>です。弱気相場では候補がゼロになる日があります。実測では11年間の1.1%の日が該当し、2020年4月と2022年7〜10月に集中しました。</li>
        </ul>
        <div class="lg-metric-row" aria-label="候補数の実測分布">
          <div class="lg-metric"><strong>24件</strong><span>候補数の中央値</span></div>
          <div class="lg-metric"><strong>5件</strong><span>下位10%</span></div>
          <div class="lg-metric"><strong>65件</strong><span>上位10%</span></div>
        </div>
        <p class="lg-footnote">候補が少ない日は故障とは限りません。上昇トレンドと押し目が同時に成立する銘柄が少ない、という相場そのものの情報でもあります。</p>
        <a class="lg-back" href="#logic-guide-top">↑ 目次へ戻る</a>
      </section>
    </article>`;

  // 静的ページであることを明示しつつ、安全な挿入パターンをコンポーネント内に保持する。
  void escapeHtml;
}
