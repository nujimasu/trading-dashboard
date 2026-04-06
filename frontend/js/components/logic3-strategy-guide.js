/**
 * Logic3 Strategy Guide — ロジック３エンジンの説明ページ
 * signal-scanner-v5 の 28シグナルエンジン（信頼度スコアリングモデル）
 */

export function renderLogic3StrategyGuide(container) {
  container.innerHTML = `
    <div class="section-title">⚡ ロジック３ — ロジック説明</div>

    <!-- 概要バナー -->
    <div style="background:rgba(234,179,8,.08);border:1px solid rgba(234,179,8,.3);border-radius:8px;padding:18px 22px;margin-bottom:20px">
      <div style="font-size:.95rem;font-weight:700;color:#fde047;margin-bottom:8px">28シグナル × 信頼度スコアリングエンジンとは？</div>
      <div style="font-size:.82rem;color:#94a3b8;line-height:1.7">
        ロジック２と同じ <strong style="color:#e2e8f0">price_data（日足OHLCVデータ）</strong> を使いながら、<strong style="color:#e2e8f0">全く異なるスコアリング式とシグナル定義</strong>でエントリー候補を算出する独立エンジン。<br>
        <strong style="color:#e2e8f0">28種のシグナル</strong>（EMA/RSI/BB/MACD/一目均衡表/VCP/チャートパターン/ローソク足）を検出し、各シグナルを個別バックテストして<strong style="color:#e2e8f0">勝率65%以上</strong>のもののみを採用。<br>
        複数シグナルの合流点・RR品質・ステージ整合性を組み合わせた<strong style="color:#e2e8f0">4要素スコアリング</strong>で信頼度を算出し、<strong style="color:#e2e8f0">0.70以上かつRR≥2.0</strong>のみリストに表示。
      </div>
    </div>

    <!-- スコア構成カード -->
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin-bottom:20px">
      ${card("60%", "勝率 (Win Rate)", "#10b981", "各シグナルのバックテスト勝率を平均。最重要指標。")}
      ${card("25%", "RR品質", "#3b82f6", "RR=2.0→67%点、RR=3.0→100%点。リスクリワードの質を重視。")}
      ${card("10%", "合流点", "#8b5cf6", "1シグナル=50%、2シグナル=75%、3+シグナル=100%。複数シグナルが重なるほど高得点。")}
      ${card("5%", "ステージ整合", "#f59e0b", "Stage2（アップトレンド）でのLONGが100%点。反対ステージは大幅減点。")}
      ${card("×補正", "サンプル補正", "#ef4444", "√(N/50) で補正。サンプル50件以上なら補正なし、少ないほど最大30%減点。")}
    </div>

    <!-- シグナル一覧 -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:16px">📡 28シグナル定義</h3>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">

        <!-- UPシグナル -->
        <div>
          <div style="font-size:.8rem;font-weight:700;color:#10b981;margin-bottom:10px">▲ UP シグナル（14種）</div>
          <table style="width:100%;font-size:.76rem;border-collapse:collapse">
            <thead>
              <tr style="color:#64748b;border-bottom:1px solid #1e293b">
                <th style="text-align:left;padding:4px 6px">シグナル</th>
                <th style="text-align:center;padding:4px 6px">TF</th>
                <th style="text-align:center;padding:4px 6px">重み</th>
              </tr>
            </thead>
            <tbody>
              ${sigRow("EMAゴールデンクロス",     "short", 4)}
              ${sigRow("RSI底打ち反発",           "short", 3)}
              ${sigRow("RSI強気ダイバージェンス", "mid",   4)}
              ${sigRow("BBスクイーズ上抜け",      "short", 3)}
              ${sigRow("出来高急増+大陽線",       "short", 3)}
              ${sigRow("MACDゴールデンクロス",    "short", 3)}
              ${sigRow("MACDヒスト底打ち",        "mid",   3)}
              ${sigRow("一目雲上抜け",            "mid",   4)}
              ${sigRow("EMA200サポート反発",      "mid",   4)}
              ${sigRow("ダブルボトム",            "mid",   5)}
              ${sigRow("VCPブレイクアウト",       "mid",   6)}
              ${sigRow("ブルフラッグ",            "short", 5)}
              ${sigRow("カップ&ハンドル",         "mid",   5)}
              ${sigRow("ハンマー / 強気包み足 / 明けの明星", "short", 3)}
            </tbody>
          </table>
        </div>

        <!-- DOWNシグナル（参考） -->
        <div>
          <div style="font-size:.8rem;font-weight:700;color:#94a3b8;margin-bottom:10px">▼ DOWN シグナル（14種・ロジック３では不使用）</div>
          <div style="font-size:.76rem;color:#475569;line-height:1.8;padding:8px">
            EMAデッドクロス、RSI天井反落、RSI弱気ダイバージェンス、BBスクイーズ下抜け、
            出来高急増+大陰線、MACDデッドクロス、MACDヒスト天井、一目雲下抜け、
            EMA200レジスタンス反落、ダブルトップ、シューティングスター、弱気包み足、宵の明星
            <div style="margin-top:10px;padding:8px;background:rgba(71,85,105,.15);border-radius:4px;color:#64748b">
              ロジック３は <strong style="color:#94a3b8">LONG（買い）のみ</strong>を対象とするため、
              DOWNシグナルは採用しない。
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- バックテスト仕様 -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:16px">🧪 バックテスト仕様</h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;font-size:.82rem">
        ${specBox("エントリー", "シグナル当日の終値")}
        ${specBox("SL（損切り）", "エントリー − ATR × 2.0")}
        ${specBox("TP（利確）", "エントリー + ATR × 4.0")}
        ${specBox("保有期間", "short TF: 10日 / mid TF: 30日")}
        ${specBox("最低サンプル", "10件未満のシグナルは除外")}
        ${specBox("採用基準", "勝率 ≥ 65%")}
        ${specBox("最終利確", "保有期間内にSL/TPに達しない場合は終値で判定（+1%超→WIN）")}
        ${specBox("期待RR", "ATR比 = 4.0 ÷ 2.0 = 2.0")}
      </div>
    </div>

    <!-- RR計算 -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:16px">📐 エントリー時のRR計算（表示用）</h3>
      <div style="font-size:.82rem;color:#94a3b8;line-height:1.9">
        <div style="display:grid;grid-template-columns:auto 1fr;gap:4px 16px;align-items:start">
          <span style="color:#fde047;white-space:nowrap">エントリー</span><span>当日終値</span>
          <span style="color:#ef4444;white-space:nowrap">SL</span><span>max( 終値 − ATR×2, 直近10日安値 − ATR×0.3 )</span>
          <span style="color:#10b981;white-space:nowrap">TP</span><span>min( 終値 + ATR×4, 直近60日高値×1.002 )</span>
          <span style="color:#3b82f6;white-space:nowrap">RR</span><span>( TP − エントリー ) ÷ ( エントリー − SL )</span>
        </div>
        <div style="margin-top:12px;padding:10px;background:rgba(99,102,241,.08);border-radius:6px;color:#a5b4fc;font-size:.78rem">
          TP は直近の抵抗帯（60日高値）を優先的に使用。ない場合は ATR×4 のデフォルト目標を採用。<br>
          RR ≥ 2.0 を満たさない場合はリストに表示しない。
        </div>
      </div>
    </div>

    <!-- 採用フロー -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:16px">🔄 採用フロー</h3>
      <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;font-size:.8rem">
        ${step("①", "全銘柄をスキャン\n(price_data)", "#6366f1")}
        <span style="color:#475569">→</span>
        ${step("②", "28シグナル検出\n(各シグナル独立判定)", "#3b82f6")}
        <span style="color:#475569">→</span>
        ${step("③", "シグナルごと\nバックテスト", "#8b5cf6")}
        <span style="color:#475569">→</span>
        ${step("④", "勝率65%未満\nを除外", "#ef4444")}
        <span style="color:#475569">→</span>
        ${step("⑤", "UP優勢か判定\n(UP加重スコア > DN)", "#f59e0b")}
        <span style="color:#475569">→</span>
        ${step("⑥", "RR計算\n≥2.0 のみ通過", "#10b981")}
        <span style="color:#475569">→</span>
        ${step("⑦", "信頼度スコア算出\n≥0.70 のみ採用", "#fde047")}
      </div>
    </div>

    <!-- ロジック２との比較 -->
    <div class="card">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:16px">🔍 ロジック２との比較</h3>
      <div style="overflow-x:auto">
        <table style="width:100%;font-size:.78rem;border-collapse:collapse">
          <thead>
            <tr style="background:rgba(30,41,59,.6);color:#94a3b8">
              <th style="padding:8px 12px;text-align:left">項目</th>
              <th style="padding:8px 12px;text-align:center">ロジック２</th>
              <th style="padding:8px 12px;text-align:center">ロジック３</th>
            </tr>
          </thead>
          <tbody>
            ${cmpRow("シグナル数",      "16種",                  "28種")}
            ${cmpRow("一目均衡表",      "なし",                  "あり（雲上下抜け）")}
            ${cmpRow("チャートパターン","VCP のみ",               "VCP + ブルフラッグ + カップ&ハンドル + ダブルボトム")}
            ${cmpRow("ローソク足パターン","ハンマー等 基本",      "8種（明けの明星・包み足等 拡張）")}
            ${cmpRow("スコア式",        "勝率40%+Stage20%+収束15%+RR15%+市場10%", "勝率60%+RR25%+合流点10%+Stage5%")}
            ${cmpRow("勝率閾値",        "52%",                   "65%")}
            ${cmpRow("信頼度閾値",      "0.45",                  "0.70")}
            ${cmpRow("RR下限",          "1.5",                   "2.0")}
            ${cmpRow("SL設定",          "構造的安値（30bar）",   "ATR×2.0")}
            ${cmpRow("市場文脈フィルター","あり（ブレッドス）",   "なし（個別銘柄シグナル重視）")}
            ${cmpRow("SHORT対応",       "なし（除外済み）",      "なし（設計上UPのみ）")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// ── ヘルパー ────────────────────────────────────────────────────────────────

function card(pct, label, color, desc) {
  return `
    <div style="background:rgba(30,41,59,.6);border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:14px 16px">
      <div style="font-size:1.4rem;font-weight:800;color:${color}">${pct}</div>
      <div style="font-size:.78rem;font-weight:700;color:#e2e8f0;margin:4px 0">${label}</div>
      <div style="font-size:.74rem;color:#64748b;line-height:1.5">${desc}</div>
    </div>`;
}

function sigRow(name, tf, w) {
  const tfColor = tf === "short" ? "#3b82f6" : "#8b5cf6";
  const tfLabel = tf === "short" ? "短" : "中";
  return `
    <tr style="border-bottom:1px solid rgba(30,41,59,.8)">
      <td style="padding:4px 6px;color:#cbd5e1">${name}</td>
      <td style="padding:4px 6px;text-align:center"><span style="color:${tfColor};font-size:.72rem">${tfLabel}</span></td>
      <td style="padding:4px 6px;text-align:center;color:#94a3b8">${w}</td>
    </tr>`;
}

function specBox(label, value) {
  return `
    <div style="background:rgba(30,41,59,.6);border-radius:6px;padding:10px 12px">
      <div style="font-size:.72rem;color:#64748b;margin-bottom:3px">${label}</div>
      <div style="color:#e2e8f0;font-weight:600">${value}</div>
    </div>`;
}

function step(num, text, color) {
  return `
    <div style="background:rgba(30,41,59,.8);border:1px solid ${color}33;border-radius:8px;padding:10px 12px;min-width:100px;text-align:center">
      <div style="color:${color};font-weight:800;font-size:.9rem">${num}</div>
      <div style="color:#94a3b8;font-size:.72rem;margin-top:4px;white-space:pre-line">${text}</div>
    </div>`;
}

function cmpRow(label, v2, v3) {
  return `
    <tr style="border-bottom:1px solid rgba(30,41,59,.8)">
      <td style="padding:7px 12px;color:#94a3b8">${label}</td>
      <td style="padding:7px 12px;text-align:center;color:#7dd3fc">${v2}</td>
      <td style="padding:7px 12px;text-align:center;color:#fde047">${v3}</td>
    </tr>`;
}
