/**
 * Logic4 Strategy Guide — 押し目買いスクリーニングの説明ページ
 */

export function renderLogic4StrategyGuide(container) {
  container.innerHTML = `
    <div class="section-title">🎯 ロジック４ — ロジック説明（押し目買い）</div>

    <!-- 判定凡例 -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:12px">📋 判定の見方（リスト画面）</h3>
      <div style="display:flex;flex-wrap:wrap;gap:10px">
        <div style="display:flex;align-items:center;gap:8px;background:rgba(16,185,129,.1);border:1px solid rgba(16,185,129,.4);border-radius:6px;padding:8px 14px">
          <span style="font-weight:700;color:#10b981">最優先候補</span>
          <span style="font-size:.75rem;color:#94a3b8">サポートから≤3% かつ 1Hトリガー確認済み → 即エントリー検討</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px;background:rgba(245,158,11,.1);border:1px solid rgba(245,158,11,.4);border-radius:6px;padding:8px 14px">
          <span style="font-weight:700;color:#f59e0b">サポート接近中</span>
          <span style="font-size:.75rem;color:#94a3b8">サポートから≤3% だがトリガー未確認 → 1Hシグナル出るまで待機</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px;background:rgba(100,116,139,.1);border:1px solid rgba(100,116,139,.4);border-radius:6px;padding:8px 14px">
          <span style="font-weight:700;color:#94a3b8">押し目待ち</span>
          <span style="font-size:.75rem;color:#94a3b8">サポートまで>3% → まだ押し目途中、監視継続</span>
        </div>
      </div>
    </div>

    <!-- 概要バナー -->
    <div style="background:rgba(16,185,129,.08);border:1px solid rgba(16,185,129,.3);border-radius:8px;padding:18px 22px;margin-bottom:20px">
      <div style="font-size:.95rem;font-weight:700;color:#6ee7b7;margin-bottom:8px">押し目買い戦略とは？</div>
      <div style="font-size:.82rem;color:#94a3b8;line-height:1.7">
        <strong style="color:#e2e8f0">上昇トレンド中の一時的な下落（押し目）からの反発</strong>を狙うスイングトレード戦略。<br>
        ブレイクアウト直後の高値追いは行わず、必ず<strong style="color:#e2e8f0">戻り（サポートへの接近）</strong>を確認してからエントリー候補として提示。<br>
        週足・日足の<strong style="color:#e2e8f0">複数時間軸でのトレンド確認</strong>と、<strong style="color:#e2e8f0">サポートラインのコンフルエンス</strong>（根拠の重なり）を重視する。
      </div>
    </div>

    <!-- 一次フィルター -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:14px">① 一次フィルター（機械的スクリーニング）— すべて満たす必要あり</h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px">
        ${filter("週足トレンド", "週足 20EMA > 200EMA", "#10b981", "中長期的に上昇トレンドが継続していること。週足でデッドクロス中の銘柄は全除外。")}
        ${filter("日足パーフェクトオーダー", "株価 > 20EMA > 50EMA > 200EMA", "#3b82f6", "短・中・長期の移動平均が上から順に並び、トレンドの勢いが強い状態。準成立（株価>20EMA>200EMA）は別途フラグ付き。")}
        ${filter("3ヶ月パフォーマンス", "過去3ヶ月の騰落率 > 0%", "#8b5cf6", "直近3ヶ月でプラスの銘柄のみ対象。例: +5〜15%が安定候補。+30%超はモメンタムは強いが押し目が浅い傾向。+1〜3%は上昇初期で反発余地が大きい場合も。")}
        ${filter("流動性", "20日平均出来高 ≥ 50万株", "#f59e0b", "出来高が低いとテクニカル分析が機能しにくく、スリッページも発生しやすいため除外。")}
      </div>
    </div>

    <!-- 二次フィルター -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:14px">② 二次フィルター（チャート分析・スコアリング）</h3>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        <div>
          <div style="font-size:.8rem;font-weight:700;color:#e2e8f0;margin-bottom:8px">ダウ理論（日足）</div>
          <div style="font-size:.78rem;color:#94a3b8;line-height:1.7">
            スイングハイ・ローを検出し、<strong style="color:#e2e8f0">高値の切り上げ（HH）と安値の切り上げ（HL）</strong>が直近で確認できるかを判定。
            <div style="margin-top:8px">
              ${badge("strong", "#10b981")} 直近2回以上のHH/HL → 上昇トレンドが明確に継続中<br>
              ${badge("early", "#f59e0b")} 直近1回のHH/HL → 上昇トレンドの初期段階 or スイング数が不足<br>
              ${badge("broken", "#ef4444")} HH/HLの連続が崩れた → <strong style="color:#fca5a5">除外</strong>
            </div>
            <div style="margin-top:8px;padding:8px;background:rgba(30,41,59,.5);border-radius:4px;font-size:.74rem;color:#64748b">
              ※ <strong style="color:#94a3b8">early</strong> はスイングポイントが直近60日間で2つ未満の場合にもデフォルトで表示されます。上昇トレンド初期の銘柄や、レンジから抜け出したばかりの銘柄に多いです。
            </div>
          </div>
        </div>
        <div>
          <div style="font-size:.8rem;font-weight:700;color:#e2e8f0;margin-bottom:8px">サポートライン（コンフルエンス）</div>
          <div style="font-size:.78rem;color:#94a3b8;line-height:1.7">
            以下の根拠が<strong style="color:#e2e8f0">同じ価格帯に重なる</strong>ほど高優先度：
            <ul style="margin:6px 0 0 16px;line-height:1.9">
              <li>水平サポート（過去の高値・安値が複数回反応）</li>
              <li>20EMA・50EMAへの接触・反発</li>
              <li>上昇トレンドラインとの交差</li>
            </ul>
            根拠2つ以上 → <span style="color:#10b981">高優先度</span> / 1つ → 通常 / 0 → <span style="color:#ef4444">除外</span>
          </div>
        </div>
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px">
        <div>
          <div style="font-size:.8rem;font-weight:700;color:#e2e8f0;margin-bottom:8px">レジサポ転換</div>
          <div style="font-size:.78rem;color:#94a3b8;line-height:1.7">
            抵抗線を上方ブレイク後、その価格帯まで戻ってきて<strong style="color:#e2e8f0">サポートとして機能し始めている</strong>かを確認。
            <div style="margin-top:8px">
              ${badge("確認済み", "#10b981")} <strong style="color:#6ee7b7">最高優先度エントリー候補</strong><br>
              ${badge("監視中", "#f59e0b")} ブレイクアウト直後（戻り待ち）<br>
              ${badge("なし", "#64748b")} 通常のサポート押し目
            </div>
          </div>
        </div>
        <div>
          <div style="font-size:.8rem;font-weight:700;color:#e2e8f0;margin-bottom:8px">R:R計算</div>
          <div style="font-size:.78rem;color:#94a3b8;line-height:1.7">
            <div style="display:grid;grid-template-columns:auto 1fr;gap:3px 10px;margin-bottom:8px">
              <span style="color:#10b981">TP</span><span>直近高値 × 0.99</span>
              <span style="color:#ef4444">SL</span><span>サポート × 0.99 または サポート − ATR</span>
              <span style="color:#3b82f6">R:R</span><span>（TP − 現在値）÷（現在値 − SL）</span>
            </div>
            ${badge("R:R ≥ 2.0", "#10b981")} 優良候補<br>
            ${badge("R:R 1.5〜2.0", "#f59e0b")} エントリー可<br>
            ${badge("R:R < 1.5", "#ef4444")} 見送り（より深い押し目を待つ）
          </div>
        </div>
      </div>
    </div>

    <!-- ボーナスフラグ -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:14px">③ ボーナスフラグ（信頼度向上）</h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px">
        ${bonus("RSI 30〜50", "#3b82f6", "売られすぎゾーンからの反転が期待できる押し目ゾーン。RSI<30は売られすぎ、RSI>50は押し目と言えない。")}
        ${bonus("MACDダイバージェンス", "#8b5cf6", "株価が安値切り下げにもかかわらずMACDヒストが切り上げ → 強気ダイバージェンス。反発の信頼度が大幅向上。")}
        ${bonus("フィボナッチコンフルエンス", "#f59e0b", "直近高値・安値からの38.2%/50%/61.8%水準がEMAやサポートと±2%以内で重なる場合に付与。")}
      </div>
    </div>

    <!-- 信頼度算出ロジック -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:14px">📊 信頼度（リスト列）の算出ロジック</h3>
      <div style="font-size:.8rem;color:#94a3b8;line-height:1.7;margin-bottom:12px">
        信頼度スコアは<strong style="color:#e2e8f0">レジサポ転換・R:R・コンフルエンス・ボーナスフラグ</strong>の4要素で決定:
      </div>
      <div style="overflow-x:auto">
        <table style="width:100%;font-size:.78rem;border-collapse:collapse">
          <thead>
            <tr style="background:rgba(30,41,59,.6);color:#94a3b8">
              <th style="padding:8px 12px;text-align:left">条件</th>
              <th style="padding:8px 12px;text-align:center">ベーススコア</th>
              <th style="padding:8px 12px;text-align:center">ボーナス加算</th>
              <th style="padding:8px 12px;text-align:center">上限</th>
            </tr>
          </thead>
          <tbody>
            <tr style="border-bottom:1px solid rgba(30,41,59,.8)">
              <td style="padding:7px 12px;color:#10b981;font-weight:600">レジサポ転換確認 + R:R≥1.5 + ボーナス1件以上</td>
              <td style="padding:7px 12px;text-align:center;color:#e2e8f0">70%</td>
              <td style="padding:7px 12px;text-align:center;color:#e2e8f0">+5% / ボーナスフラグ1件 + R:R≥2.0で+5%</td>
              <td style="padding:7px 12px;text-align:center;color:#e2e8f0">95%</td>
            </tr>
            <tr style="border-bottom:1px solid rgba(30,41,59,.8)">
              <td style="padding:7px 12px;color:#3b82f6;font-weight:600">R:R≥1.5 + コンフルエンス≥2件</td>
              <td style="padding:7px 12px;text-align:center;color:#e2e8f0">55%</td>
              <td style="padding:7px 12px;text-align:center;color:#e2e8f0">+5% / ボーナスフラグ1件 + R:R≥2.0で+5%</td>
              <td style="padding:7px 12px;text-align:center;color:#e2e8f0">80%</td>
            </tr>
            <tr style="border-bottom:1px solid rgba(30,41,59,.8)">
              <td style="padding:7px 12px;color:#f59e0b;font-weight:600">R:R≥1.5 + コンフルエンス1件</td>
              <td style="padding:7px 12px;text-align:center;color:#e2e8f0">50%</td>
              <td style="padding:7px 12px;text-align:center;color:#e2e8f0">+3% / ボーナスフラグ1件</td>
              <td style="padding:7px 12px;text-align:center;color:#e2e8f0">—</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div style="margin-top:10px;padding:8px;background:rgba(30,41,59,.5);border-radius:4px;font-size:.74rem;color:#64748b">
        ボーナスフラグ = RSI 30〜50 / MACDダイバージェンス / フィボナッチコンフルエンス（各+1件）<br>
        例: レジサポ確認 + ボーナス2件 + R:R 2.5 → 70% + 10% + 5% = 85%
      </div>
    </div>

    <!-- イントラデイ確認（4H/1H） -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:14px">④ イントラデイ確認（4H/1H トリガー）</h3>
      <div style="font-size:.8rem;color:#94a3b8;line-height:1.7;margin-bottom:12px">
        日足フィルターを通過した後、<strong style="color:#e2e8f0">4時間足・1時間足</strong>でサポートからの実際の反発シグナルを確認する。<br>
        これにより「まだ押し目中」「そろそろエントリー」「今が反発点」を区別できる。
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        <div>
          <div style="font-size:.8rem;font-weight:700;color:#e2e8f0;margin-bottom:8px">4時間足 構造チェック</div>
          <div style="font-size:.78rem;color:#94a3b8;line-height:1.7">
            直近の4Hスイングハイ・ローを確認し、4H EMA20との位置関係を判定:
            <div style="margin-top:6px">
              ${badge("bullish", "#10b981")} HH/HL継続 または EMA20上<br>
              ${badge("neutral", "#f59e0b")} 構造不明確<br>
              ${badge("bearish", "#ef4444")} LH/LLパターン（ロングは保留）
            </div>
          </div>
        </div>
        <div>
          <div style="font-size:.8rem;font-weight:700;color:#e2e8f0;margin-bottom:8px">1時間足 トリガーシグナル</div>
          <div style="font-size:.78rem;color:#94a3b8;line-height:1.7">
            サポート近傍（±5%）での反発シグナルを検出:
            <ul style="margin:6px 0 0 16px;line-height:1.9">
              <li><strong style="color:#6ee7b7">ピンバー(1H)</strong> — 下ヒゲ ≥ 実体×2、陽線</li>
              <li><strong style="color:#6ee7b7">逆ハンマー(1H)</strong> — 上ヒゲ ≥ 実体×2、下ヒゲ小</li>
              <li><strong style="color:#6ee7b7">強気エンガルフィング(1H)</strong> — 陰線を包む陽線</li>
              <li><strong style="color:#6ee7b7">切り込み線(1H)</strong> — 陰線→陽線が前足中間以上まで戻す</li>
              <li><strong style="color:#6ee7b7">出来高急増(1H)</strong> — 20本平均×1.5倍以上の陽線</li>
              <li><strong style="color:#6ee7b7">明けの明星(1H)</strong> — 大陰線→小実体→大陽線の3本反転</li>
              <li><strong style="color:#6ee7b7">赤三兵(1H)</strong> — 3本連続陽線、各足が切り上がり</li>
              <li><strong style="color:#6ee7b7">ダブルボトム(1H)</strong> — 1%以内の二底形成</li>
            </ul>
            <div style="margin-top:14px;padding-top:10px;border-top:1px solid #334155">
              <div style="font-size:.78rem;font-weight:700;color:#60a5fa;margin-bottom:6px">📊 日足チャートパターン（NEW）</div>
              <ul style="margin:6px 0 0 16px;line-height:1.9">
                <li><strong style="color:#60a5fa">カップウィズハンドル</strong> — U字底＋小さな戻り→ブレイクアウト（60日）</li>
                <li><strong style="color:#60a5fa">アセンディングトライアングル</strong> — 水平レジスタンス＋切り上がるサポート（30日）</li>
                <li><strong style="color:#60a5fa">逆ヘッドアンドショルダー</strong> — 3つの谷（中央最深）→ネックライン突破（50日）</li>
                <li><strong style="color:#60a5fa">ブルペナント</strong> — 急騰後の三角持ち合い→上放れ（30日）</li>
                <li><strong style="color:#60a5fa">フォーリングウェッジ</strong> — 下降ウェッジ収束→上方ブレイク（30日）</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ローソクパターン図鑑 -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:14px">🕯️ ローソクパターン図鑑（1Hトリガー: 8パターン）</h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px">
        ${candleCard("ピンバー", "1本足・強気", "#10b981", candleSvg_hammer())}
        ${candleCard("逆ハンマー", "1本足・強気", "#10b981", candleSvg_inverseHammer())}
        ${candleCard("強気エンガルフィング", "2本足・強気", "#3b82f6", candleSvg_engulfing())}
        ${candleCard("切り込み線", "2本足・強気", "#3b82f6", candleSvg_piercing())}
        ${candleCard("明けの明星", "3本足・強気", "#8b5cf6", candleSvg_morningStar())}
        ${candleCard("赤三兵", "3本足・強気", "#8b5cf6", candleSvg_threeWhite())}
        ${candleCard("出来高急増", "1本足+出来高", "#f59e0b", candleSvg_volumeSurge())}
        ${candleCard("ダブルボトム", "複数足・反転", "#f59e0b", candleSvg_doubleBottom())}
      </div>
    </div>

    <!-- 日足チャートパターン図鑑 -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:14px">📊 日足チャートパターン図鑑（5パターン — NEW）</h3>
      <div style="font-size:.78rem;color:#94a3b8;margin-bottom:12px">日足データ（60〜250日）を使用して構造的な強気パターンを検出。ローソク足パターンより長期の価格構造を捉えます。</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px">
        ${candleCard("カップウィズハンドル", "U字底→ブレイク", "#60a5fa", chartSvg_cupHandle())}
        ${candleCard("アセンディング△", "水平抵抗+上昇支持", "#60a5fa", chartSvg_ascTriangle())}
        ${candleCard("逆ヘッド&ショルダー", "3谷反転パターン", "#60a5fa", chartSvg_invHS())}
        ${candleCard("ブルペナント", "急騰後の収束→上放れ", "#60a5fa", chartSvg_pennant())}
        ${candleCard("フォーリングウェッジ", "下降収束→上方ブレイク", "#60a5fa", chartSvg_fallingWedge())}
      </div>
    </div>

    <!-- 総合判定基準 -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:14px">⑤ 総合判定基準</h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px">
        ${verdict("最優先候補", "#10b981", ["一次フィルター全通過", "R:R ≥ 1.5", "サポートから≤3%", "1Hトリガーシグナル確認済み"])}
        ${verdict("サポート接近中", "#f59e0b", ["一次フィルター全通過", "R:R ≥ 1.5", "サポートから≤3%（トリガー未確認）"])}
        ${verdict("押し目待ち", "#64748b", ["一次フィルター全通過", "R:R ≥ 1.5", "サポートまで>3%（押し目継続中）"])}
      </div>
    </div>

    <!-- 注意事項 -->
    <div class="card">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:12px">⚠️ 重要な注意事項</h3>
      <div style="font-size:.8rem;color:#94a3b8;line-height:2">
        <div>🚫 <strong style="color:#e2e8f0">ブレイクアウト直後のエントリー禁止</strong> — 必ず「戻り」を待ち、レジサポ転換が確定してからエントリー候補として提示</div>
        <div>🚫 <strong style="color:#e2e8f0">R:R 1.5未満は推奨しない</strong> — チャート形状が良くてもR:R未達は候補から除外</div>
        <div>🚫 <strong style="color:#e2e8f0">低流動性銘柄は除外</strong> — 20日平均出来高50万株未満は一切推奨しない</div>
        <div>✅ <strong style="color:#e2e8f0">コンフルエンス重視</strong> — サポートは複数の根拠が重なるポイントを優先提示</div>
        <div>✅ <strong style="color:#e2e8f0">1Hトリガー待ち</strong> — 「サポート接近中」でも1Hシグナルが出るまでエントリーは見送り</div>
      </div>
    </div>
  `;
}

// ── ヘルパー ─────────────────────────────────────────────────────────────────

function filter(title, cond, color, desc) {
  return `
    <div style="background:rgba(30,41,59,.7);border-left:3px solid ${color};border-radius:6px;padding:12px 14px">
      <div style="font-size:.78rem;font-weight:700;color:${color};margin-bottom:4px">${title}</div>
      <div style="font-size:.8rem;color:#e2e8f0;font-weight:600;margin-bottom:5px">${cond}</div>
      <div style="font-size:.74rem;color:#64748b;line-height:1.5">${desc}</div>
    </div>`;
}

function bonus(title, color, desc) {
  return `
    <div style="background:rgba(30,41,59,.7);border:1px solid ${color}44;border-radius:6px;padding:12px 14px">
      <div style="font-size:.78rem;font-weight:700;color:${color};margin-bottom:5px">★ ${title}</div>
      <div style="font-size:.74rem;color:#64748b;line-height:1.5">${desc}</div>
    </div>`;
}

function verdict(label, color, items) {
  return `
    <div style="background:rgba(30,41,59,.7);border:1px solid ${color}55;border-radius:8px;padding:14px 16px">
      <div style="font-size:.88rem;font-weight:800;color:${color};margin-bottom:8px">${label}</div>
      <ul style="margin:0;padding-left:16px;font-size:.76rem;color:#94a3b8;line-height:1.9">
        ${items.map(i => `<li>${i}</li>`).join("")}
      </ul>
    </div>`;
}

function badge(text, color) {
  return `<span style="display:inline-block;padding:1px 7px;border-radius:4px;font-size:.72rem;font-weight:700;background:${color}22;color:${color};border:1px solid ${color}44;margin-right:4px">${text}</span>`;
}

// ── ローソクSVGヘルパー ──────────────────────────────────────────────────────
function _candle(x, o, h, l, c, w=14) {
  const bull = c >= o;
  const top = Math.min(o,c), bot = Math.max(o,c);
  const fill = bull ? "#22c55e" : "#ef4444";
  const cx = x + w/2;
  return `<line x1="${cx}" y1="${h}" x2="${cx}" y2="${l}" stroke="${fill}" stroke-width="1.5"/>
          <rect x="${x}" y="${top}" width="${w}" height="${Math.max(bot-top,1)}" fill="${fill}" rx="1"/>`;
}

function candleCard(title, subtitle, color, svg) {
  return `<div style="background:rgba(30,41,59,.7);border:1px solid ${color}44;border-radius:8px;padding:10px;text-align:center">
    <div style="height:80px;display:flex;align-items:center;justify-content:center">${svg}</div>
    <div style="font-size:.78rem;font-weight:700;color:${color};margin-top:6px">${title}</div>
    <div style="font-size:.68rem;color:#64748b">${subtitle}</div>
  </div>`;
}

function candleSvg_hammer() {
  return `<svg width="40" height="70" viewBox="0 0 40 70">
    ${_candle(13, 50, 20, 65, 25)}
    <line x1="0" y1="58" x2="40" y2="58" stroke="#475569" stroke-width="0.5" stroke-dasharray="2"/>
  </svg>`;
}
function candleSvg_inverseHammer() {
  return `<svg width="40" height="70" viewBox="0 0 40 70">
    ${_candle(13, 55, 10, 62, 50)}
  </svg>`;
}
function candleSvg_engulfing() {
  return `<svg width="60" height="70" viewBox="0 0 60 70">
    ${_candle(8, 25, 18, 50, 45, 12)}
    ${_candle(28, 50, 12, 55, 20, 18)}
  </svg>`;
}
function candleSvg_piercing() {
  return `<svg width="60" height="70" viewBox="0 0 60 70">
    ${_candle(8, 20, 15, 55, 48, 14)}
    ${_candle(30, 52, 22, 58, 30, 14)}
    <line x1="0" y1="34" x2="60" y2="34" stroke="#f59e0b" stroke-width="0.5" stroke-dasharray="2"/>
  </svg>`;
}
function candleSvg_morningStar() {
  return `<svg width="76" height="70" viewBox="0 0 76 70">
    ${_candle(4, 15, 10, 55, 50, 14)}
    ${_candle(26, 52, 48, 58, 54, 10)}
    ${_candle(44, 48, 12, 52, 18, 14)}
  </svg>`;
}
function candleSvg_threeWhite() {
  return `<svg width="76" height="70" viewBox="0 0 76 70">
    ${_candle(4, 50, 42, 60, 45, 14)}
    ${_candle(26, 42, 30, 48, 34, 14)}
    ${_candle(48, 32, 18, 38, 22, 14)}
  </svg>`;
}
function candleSvg_volumeSurge() {
  return `<svg width="60" height="70" viewBox="0 0 60 70">
    <rect x="5" y="50" width="10" height="15" fill="#475569" rx="1"/>
    <rect x="20" y="48" width="10" height="17" fill="#475569" rx="1"/>
    <rect x="35" y="30" width="14" height="35" fill="#22c55e55" rx="1"/>
    ${_candle(37, 35, 15, 50, 20, 10)}
  </svg>`;
}
function candleSvg_doubleBottom() {
  return `<svg width="80" height="70" viewBox="0 0 80 70">
    <path d="M5 20 Q20 55 35 30 Q50 55 65 20" fill="none" stroke="#f59e0b" stroke-width="2"/>
    <line x1="0" y1="52" x2="80" y2="52" stroke="#ef4444" stroke-width="0.5" stroke-dasharray="3"/>
    <circle cx="20" cy="52" r="3" fill="none" stroke="#f59e0b" stroke-width="1.5"/>
    <circle cx="50" cy="52" r="3" fill="none" stroke="#f59e0b" stroke-width="1.5"/>
  </svg>`;
}
// ── 日足チャートパターンSVG ──
function chartSvg_cupHandle() {
  return `<svg width="90" height="70" viewBox="0 0 90 70">
    <path d="M5 18 Q15 18 25 45 Q40 62 55 18 L62 18 Q65 28 70 22" fill="none" stroke="#60a5fa" stroke-width="2"/>
    <line x1="55" y1="18" x2="75" y2="18" stroke="#60a5fa" stroke-width="0.5" stroke-dasharray="2"/>
    <path d="M70 22 L80 12" stroke="#22c55e" stroke-width="2" stroke-dasharray="3"/>
    <text x="80" y="10" font-size="8" fill="#22c55e">↑</text>
  </svg>`;
}
function chartSvg_ascTriangle() {
  return `<svg width="90" height="70" viewBox="0 0 90 70">
    <line x1="10" y1="18" x2="80" y2="18" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="3"/>
    <path d="M10 60 L30 40 L50 30 L70 22" fill="none" stroke="#60a5fa" stroke-width="2"/>
    <path d="M10 20 L30 20 L50 19 L70 18" fill="none" stroke="#60a5fa" stroke-width="1.5"/>
    <path d="M70 18 L85 8" stroke="#22c55e" stroke-width="2" stroke-dasharray="3"/>
    <text x="10" y="64" font-size="7" fill="#94a3b8">支持↑</text>
    <text x="60" y="14" font-size="7" fill="#ef4444">抵抗—</text>
  </svg>`;
}
function chartSvg_invHS() {
  return `<svg width="90" height="70" viewBox="0 0 90 70">
    <path d="M5 20 L20 42 L30 25 L45 58 L55 25 L65 42 L80 15" fill="none" stroke="#60a5fa" stroke-width="2"/>
    <line x1="20" y1="25" x2="65" y2="25" stroke="#f59e0b" stroke-width="1" stroke-dasharray="2"/>
    <text x="32" y="22" font-size="7" fill="#f59e0b">NL</text>
    <circle cx="20" cy="42" r="2" fill="#94a3b8"/>
    <circle cx="45" cy="58" r="2.5" fill="#60a5fa"/>
    <circle cx="65" cy="42" r="2" fill="#94a3b8"/>
  </svg>`;
}
function chartSvg_pennant() {
  return `<svg width="90" height="70" viewBox="0 0 90 70">
    <path d="M5 60 L25 15" stroke="#22c55e" stroke-width="2.5"/>
    <path d="M25 15 L50 22 L65 25" fill="none" stroke="#60a5fa" stroke-width="1.5"/>
    <path d="M25 25 L50 22 L65 25" fill="none" stroke="#60a5fa" stroke-width="1.5"/>
    <polygon points="25,15 65,25 25,25" fill="#60a5fa22" stroke="none"/>
    <path d="M65 25 L80 10" stroke="#22c55e" stroke-width="2" stroke-dasharray="3"/>
    <text x="7" y="42" font-size="7" fill="#22c55e" transform="rotate(-65,12,42)">pole</text>
  </svg>`;
}
function chartSvg_fallingWedge() {
  return `<svg width="90" height="70" viewBox="0 0 90 70">
    <path d="M10 10 L60 40" fill="none" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="3"/>
    <path d="M10 30 L60 45" fill="none" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="3"/>
    <path d="M10 12 L25 22 L40 30 L55 38 L65 25" fill="none" stroke="#60a5fa" stroke-width="2"/>
    <path d="M65 25 L80 12" stroke="#22c55e" stroke-width="2" stroke-dasharray="3"/>
    <text x="70" y="10" font-size="8" fill="#22c55e">↑</text>
  </svg>`;
}
