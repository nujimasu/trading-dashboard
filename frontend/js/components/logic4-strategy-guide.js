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
        ${filter("3ヶ月パフォーマンス", "過去3ヶ月の騰落率 > 0%", "#8b5cf6", "ダウ理論の高値・安値切り上げを数値で代替。6ヶ月もプラスなら信頼度向上。")}
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
              ${badge("強い上昇", "#10b981")} 直近2回以上のHH/HL<br>
              ${badge("上昇初期", "#f59e0b")} 直近1回のHH/HL<br>
              ${badge("除外", "#ef4444")} HH/HLが崩れている
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
              <li><strong style="color:#6ee7b7">強気エンガルフィング(1H)</strong> — 陰線を包む陽線</li>
              <li><strong style="color:#6ee7b7">出来高急増(1H)</strong> — 20本平均×1.5倍以上の陽線</li>
              <li><strong style="color:#6ee7b7">ダブルボトム(1H)</strong> — 1%以内の二底形成</li>
            </ul>
          </div>
        </div>
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
