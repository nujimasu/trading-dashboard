/**
 * ファンダ重視（グロース）の説明ページ
 */
export function renderStrategyGuide(container) {
  container.innerHTML = `
    <div class="section-title">📖 ファンダ重視（グロース）</div>

    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:12px">100%ファンダの成長ランキング</h3>
      <div style="font-size:.84rem;color:#94a3b8;line-height:1.7">
        全ユニバースをテクニカルで事前足切りせず、成長ファンダだけで0〜100点に採点します。
        押し目判定はスコアに加えず、買い場かどうかの注記と売買プランの有無だけに使います。
      </div>
    </div>

    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:14px">グロース・スコアカード</h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px">
        ${scoreCard("当期EPS成長", "30pt", "四半期EPS成長を優先。50%以上で満点、0%以下はゲート落ち。")}
        ${scoreCard("売上成長", "15pt", "売上成長30%以上で満点。0%以下はゲート落ち。")}
        ${scoreCard("決算サプライズ", "15pt", "10%超で満点。データなしは中立7pt。")}
        ${scoreCard("ROE", "15pt", "30%以上で満点。15%未満は線形加点。")}
        ${scoreCard("利益率", "15pt", "営業利益率を優先。25%以上で満点、データなしは中立7pt。")}
        ${scoreCard("機関投資家保有率", "10pt", "30〜70%を満点。データなしは中立5pt。")}
      </div>
      <div style="font-size:.78rem;color:#94a3b8;margin-top:12px">
        D/Eが200を超える場合は財務健全性ガードとして5点減点します。
      </div>
    </div>

    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:14px">最低ゲート</h3>
      <ul style="margin:0 0 0 18px;color:#94a3b8;line-height:1.8">
        <li>EPS成長率が0%超</li>
        <li>売上成長率が0%超</li>
        <li>黒字が確認できる</li>
        <li>時価総額が10億ドル以上</li>
        <li>ファンダデータが取得済み</li>
      </ul>
    </div>

    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:14px">判定帯と表示</h3>
      <table class="guide-table">
        <thead><tr><th>スコア</th><th>判定</th><th>Tier</th><th>売買表示</th></tr></thead>
        <tbody>
          <tr><td>80以上</td><td>強い成長</td><td>Tier1</td><td>押し目圏内ならBUY</td></tr>
          <tr><td>65〜79</td><td>良好</td><td>Tier2</td><td>押し目圏内ならBUY</td></tr>
          <tr><td>50〜64</td><td>平均的成長</td><td>Tier3</td><td>WATCH</td></tr>
          <tr><td>50未満</td><td>成長やや弱め</td><td>Tier3</td><td>WATCH</td></tr>
        </tbody>
      </table>
    </div>

    <div class="card">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:14px">押し目タイミング注記</h3>
      <ul style="margin:0 0 0 18px;color:#94a3b8;line-height:1.8">
        <li>上昇トレンド: 終値が200EMA上、かつ50EMAが200EMA上</li>
        <li>押し目圏内: 上昇トレンド内で20EMAまたは50EMAの±3%以内</li>
        <li>押し目圏内だけ、エントリー・SL・TP1(+1.5R)・参考ターゲット(+3R)を表示</li>
        <li>押し目圏外は「押し目待ち」または「トレンド外」として、SL/TPは表示しません</li>
        <li>同じ銘柄がv1/v2にも出ている場合は買い場一致タグを表示します</li>
      </ul>
    </div>
  `;
}

function scoreCard(name, pts, desc) {
  return `
    <div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:12px">
      <div style="display:flex;justify-content:space-between;gap:8px;margin-bottom:6px">
        <strong style="font-size:.86rem">${name}</strong>
        <span style="color:#22c55e;font-weight:700;font-size:.82rem">${pts}</span>
      </div>
      <div style="font-size:.78rem;color:#94a3b8;line-height:1.5">${desc}</div>
    </div>`;
}
