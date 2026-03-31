/**
 * Tech Strategy Guide — テクニカル重視ロジックの説明ページ
 * signal-scanner-v5 ベース
 */

export function renderTechStrategyGuide(container) {
  container.innerHTML = `
    <div class="section-title">🔬 テクニカル重視 — ロジック説明</div>

    <!-- 概要バナー -->
    <div style="background:rgba(99,102,241,.1);border:1px solid rgba(99,102,241,.3);border-radius:8px;padding:18px 22px;margin-bottom:20px">
      <div style="font-size:.95rem;font-weight:700;color:#a5b4fc;margin-bottom:8px">このアプローチとは？</div>
      <div style="font-size:.82rem;color:#94a3b8;line-height:1.7">
        <strong style="color:#e2e8f0">signal-scanner-v5</strong> のロジックをPythonに移植した純テクニカル分析エンジン。
        ファンダメンタルズ（業績・財務）は一切考慮せず、<strong style="color:#e2e8f0">値動きのパターン・モメンタム</strong>だけで判断する。<br>
        各シグナルを過去データで<strong style="color:#e2e8f0">バックテスト</strong>し、統計的に勝率の高いシグナルのみを採用。
        複数シグナルが重なるほど（合流）、信頼度スコアが上がる。
      </div>
    </div>

    <!-- 判定カード -->
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin-bottom:24px">
      ${vcard("今日エントリー★", "#22c55e", "信頼度70%+・シグナル継続・RR≥2.0", ["当日シグナルが1件以上アクティブ", "信頼度スコア ≥ 0.70", "現在値でのRR ≥ 2.0"])}
      ${vcard("エントリー", "#60a5fa", "信頼度58%+・シグナル継続・RR≥1.5", ["当日シグナルが1件以上アクティブ", "信頼度スコア ≥ 0.58", "現在値でのRR ≥ 1.5"])}
      ${vcard("様子見", "#eab308", "RR維持・シグナル一時停止", ["RR ≥ 1.5 を維持", "当日は新規シグナルなし", "週次では検出済みの銘柄"])}
      ${vcard("待機", "#f97316", "RR 1.0〜1.5", ["RRが低下しているが一定以上", "ポジション調整後に再評価", "エントリーは見送り"])}
      ${vcard("通過済", "#ef4444", "RR < 1.0", ["現在値でRRが著しく低下", "既にブレイクアウト完了", "新規エントリーは不適"])}
    </div>

    <!-- スコア算出式 -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:16px">🔢 信頼度スコアの計算式</h3>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
        <div>
          <div style="font-family:monospace;background:#0f172a;border-radius:6px;padding:14px;font-size:.78rem;line-height:2;color:#e2e8f0">
            <span style="color:#94a3b8">// Raw Score</span><br>
            raw = <span style="color:#60a5fa">0.60</span> × 平均勝率<br>
            &nbsp;&nbsp;&nbsp;&nbsp;+ <span style="color:#60a5fa">0.25</span> × min(RR / 3.0, 1.0)<br>
            &nbsp;&nbsp;&nbsp;&nbsp;+ <span style="color:#60a5fa">0.10</span> × 合流ボーナス<br>
            &nbsp;&nbsp;&nbsp;&nbsp;+ <span style="color:#60a5fa">0.05</span> × Stage整合係数<br><br>
            <span style="color:#94a3b8">// サンプル数補正</span><br>
            adj = 0.70 + 0.30 × √(N / 30)<br><br>
            <span style="color:#22c55e">信頼度 = raw × adj</span>
          </div>
        </div>
        <div style="display:flex;flex-direction:column;gap:10px">
          ${scoreRow("平均勝率（60%）", "過去のバックテストで算出した勝率の平均。最低52%以上のシグナルのみ採用。", "#60a5fa")}
          ${scoreRow("RR品質（25%）", "ATRベースのRR（目標4×ATR / ストップ2×ATR = 2.0固定）。最大3.0で満点。", "#60a5fa")}
          ${scoreRow("合流ボーナス（10%）", "1シグナル=50pt / 2シグナル=75pt / 3以上=100pt。複数シグナルが同時に発火するほど信頼度UP。", "#a78bfa")}
          ${scoreRow("Stage整合（5%）", "Minerviniステージとシグナル方向の整合性。LONG×Stage2=100% / SHORT×Stage4=100%。逆方向は10〜40%。", "#34d399")}
          ${scoreRow("サンプル補正（乗数）", "バックテストのサンプル数が少ないほど割引。N≥30で補正なし（×1.0）、N=5で×0.82。", "#f97316")}
        </div>
      </div>
    </div>

    <!-- 16シグナル一覧 -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:16px">📡 検出シグナル一覧（16種）</h3>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        <div>
          <div style="font-size:.75rem;font-weight:700;color:#34d399;text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px">▲ ロング（UP）シグナル</div>
          ${sigRow("EMAゴールデンクロス", 3, "EMA10がEMA21を下から上に抜ける。短期モメンタムの転換点。")}
          ${sigRow("RSI売られ過ぎ反転", 3, "RSI < 35 から反転上昇。売られすぎからの回復。")}
          ${sigRow("RSI強気ダイバージェンス", 4, "価格が安値更新もRSIは高値更新。下落モメンタムの弱まり。")}
          ${sigRow("MACDゴールデンクロス", 3, "MACDラインがシグナルラインを上抜け。中期モメンタム転換。")}
          ${sigRow("BBスクイーズ上抜け", 4, "BB幅が極度に収縮後、上バンドをブレイクアウト。大きな動きの初動。")}
          ${sigRow("出来高急増陽線", 3, "出来高が20日平均の2倍超 + ボディが大きい陽線。機関投資家の買い。")}
          ${sigRow("VCPブレイクアウト", 6, "EMA50/200上で出来高が枯渇後に急増し52週高値圏をブレイク。最高ウェイト。")}
          ${sigRow("ブルフラッグ", 5, "急騰（ポール10%以上）後のタイトな横ばい収縮からのブレイク。")}
          ${sigRow("ダブルボトム", 5, "2つの同程度の安値（2.5%以内）を経てネックラインを突破。")}
        </div>
        <div>
          <div style="font-size:.75rem;font-weight:700;color:#f87171;text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px">▼ ショート（DOWN）シグナル</div>
          ${sigRow("EMAデッドクロス", 3, "EMA10がEMA21を上から下に抜ける。下落トレンドへの転換。")}
          ${sigRow("RSI買われ過ぎ反落", 3, "RSI > 70 から反転下落。過熱からの調整。")}
          ${sigRow("RSI弱気ダイバージェンス", 4, "価格が高値更新もRSIは低値更新。上昇モメンタムの弱まり。")}
          ${sigRow("MACDデッドクロス", 3, "MACDラインがシグナルラインを下抜け。下落加速のサイン。")}
          ${sigRow("BBスクイーズ下抜け", 4, "BB収縮後に下バンドをブレイクダウン。下落の初動。")}
          ${sigRow("出来高急増陰線", 3, "出来高急増 + 大きなボディの陰線。機関投資家の売り。")}
          ${sigRow("ダブルトップ", 5, "2つの同程度の高値（2.5%以内）からのネックライン割れ。")}
          <div style="margin-top:16px;padding:10px;background:rgba(255,255,255,.04);border-radius:6px;font-size:.75rem;color:#94a3b8">
            💡 ショートは7シグナル（ロングより少ない）。現在の売られ過ぎ市場では
            ショートシグナルはほぼ発火しない。相場が強気に転じた際に有効になる。
          </div>
        </div>
      </div>
    </div>

    <!-- バックテストの仕組み -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:16px">⚗️ バックテストの仕組み</h3>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px">
        ${btCard("① シグナル検出", "過去データ（150バー以上）を全て走査し、各バーでシグナルが発火したかを記録。")}
        ${btCard("② エントリー想定", "シグナル発火バーの終値をエントリー価格とする。ATR×2.0をストップロス、ATR×4.0を目標価格に設定。")}
        ${btCard("③ 勝敗判定", "エントリー後10日間（または20日間）、日中に損切り価格をタッチ → 負け / 目標価格をタッチ → 勝ち。期限内に決着しない場合は終値で判定。")}
        ${btCard("④ 勝率計算", "ヒット数が5件以上のシグナルのみ採用。勝率 = 勝ち数 ÷ 総ヒット数。52%未満は採用なし。")}
        ${btCard("⑤ ウェイト付け", "VCP・ブルフラッグ・ダブル系はウェイト5〜6（重要度高）、クロス系はウェイト3〜4。")}
        ${btCard("⑥ 方向決定", "UPシグナルの加重合計 vs DOWNシグナルの加重合計を比較。大きい方向を採用。引き分けは除外。")}
      </div>
    </div>

    <!-- Minerviniステージ -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:16px">📊 Minervini ステージ分類</h3>
      <div style="display:flex;flex-direction:column;gap:0">
        ${stageRow(2, "ステージ2 — 上昇トレンド（LONGの理想ステージ）", "#34d399",
          "終値 > EMA50 > EMA150 > EMA200 の整列 + EMA200が上向き + 52週安値から25%以上上昇。スウィングトレードで最も勝率が高い。Stage整合係数 = 1.0（最高）。")}
        ${stageRow(1, "ステージ1 — ベース形成（LONGの候補ステージ）", "#fbbf24",
          "終値がEMA50を下回るが、EMA200付近でサポートされている。ブレイクアウト前の準備期間。RSI反転系シグナルが発火しやすい。Stage整合係数 = 0.5。")}
        ${stageRow(3, "ステージ3 — 天井圏（LONGは慎重に）", "#f97316",
          "終値 > EMA200 だが EMA200 がフラット（上でも下でもない）。上昇勢いが鈍化し天井形成中の可能性。Stage整合係数 = 0.4。")}
        ${stageRow(4, "ステージ4 — 下降トレンド（SHORTの理想ステージ）", "#ef4444",
          "終値 < EMA50 < EMA150 < EMA200 の逆整列 + EMA200が下向き。ショートトレードに最適。Stage整合係数（SHORT）= 1.0。")}
        ${stageRow(0, "ステージ0 — 不明（推奨なし）", "#64748b",
          "上記のいずれにも当てはまらない混沌とした状態。エントリーは避けるのが無難。Stage整合係数 = 0.3。")}
      </div>
    </div>

    <!-- ファンダ考慮との違い -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:16px">🔀 ファンダ考慮 vs テクニカル重視 — 使い分け</h3>
      <div style="overflow-x:auto">
        <table style="width:100%;border-collapse:collapse;font-size:.8rem">
          <thead>
            <tr style="background:rgba(255,255,255,.05)">
              <th style="padding:10px 12px;text-align:left;color:#94a3b8;font-weight:600;border-bottom:1px solid #334155">項目</th>
              <th style="padding:10px 12px;text-align:center;color:#34d399;font-weight:700;border-bottom:1px solid #334155">📊 ファンダ考慮</th>
              <th style="padding:10px 12px;text-align:center;color:#a5b4fc;font-weight:700;border-bottom:1px solid #334155">📡 テクニカル重視</th>
            </tr>
          </thead>
          <tbody>
            ${compareRow("スクリーニング基準", "VCP + Stage2 + RR + 業績", "16シグナルのバックテスト勝率")}
            ${compareRow("ファンダデータ", "EPS成長・売上・決算サプライズ（参考）", "不使用（値動きのみ）")}
            ${compareRow("スコア算出", "テクニカル50% + RR30% + VCP20%", "勝率60% + RR25% + 合流10% + Stage5%")}
            ${compareRow("更新頻度", "週1回（フルパイプライン）", "週1〜3回（--tech-weekly）")}
            ${compareRow("所要時間", "20〜30分（FMP API取得あり）", "5〜15分（既存価格データを再利用）")}
            ${compareRow("銘柄数", "10〜20件（厳選）", "5〜30件（信頼度閾値で変動）")}
            ${compareRow("向いている相場", "トレンド相場（一方向）", "あらゆる相場（ショートにも対応）")}
            ${compareRow("データ依存", "FMP APIキー推奨", "APIキー不要")}
            ${compareRow("理想の使い方", "ベース銘柄をじっくり選定", "シグナル発火タイミングを捉える")}
          </tbody>
        </table>
      </div>
      <div style="margin-top:14px;padding:12px;background:rgba(16,185,129,.08);border:1px solid rgba(16,185,129,.2);border-radius:6px;font-size:.8rem;color:#6ee7b7">
        💡 <strong>推奨</strong>: ファンダ考慮で質の高い銘柄を絞り込み → テクニカル重視でエントリータイミングを確認、という組み合わせが最も強力。
        両方のリストに登場する銘柄はダブル確認済みで特に注目度が高い。
      </div>
    </div>

    <!-- コマンドリファレンス -->
    <div class="card">
      <h3 style="font-size:.9rem;font-weight:700;margin-bottom:14px">💻 コマンドリファレンス</h3>
      <div style="display:flex;flex-direction:column;gap:8px">
        ${cmdRow("週次テクニカルスキャン（週1〜3回）",
          "python3 pipeline/run_pipeline.py --tech-weekly",
          "676銘柄に対して16シグナルを検出、バックテストで勝率を計算し、信頼度でランキング。既存の価格データを再利用するためAPI不要で5〜15分。")}
        ${cmdRow("日次テクニカル調整（毎朝自動）",
          "python3 pipeline/run_pipeline.py --tech-daily",
          "週次テクニカルピックの銘柄について当日の最新価格でシグナルを再確認。「日次（テクニカル重視）」タブに反映。--daily-only と同時実行。")}
        ${cmdRow("ファンダ＋テクニカル両方を日次更新",
          "python3 pipeline/run_pipeline.py --daily-only",
          "ファンダ考慮の日次調整 + テクニカル重視の日次調整を同時実行。毎朝7:00にLaunchAgentで自動実行済み。")}
      </div>
    </div>
  `;
}

// ── helpers ───────────────────────────────────────────────────────────────────

function vcard(label, color, sub, conditions) {
  const items = conditions.map(c =>
    `<li style="font-size:.75rem;color:#94a3b8;padding:2px 0 2px 12px;position:relative">
       <span style="position:absolute;left:0;color:${color}">•</span>${c}</li>`
  ).join("");
  return `
    <div style="background:#1e293b;border:1px solid ${color};border-radius:8px;padding:14px">
      <div style="font-size:.85rem;font-weight:700;color:${color};margin-bottom:4px">${label}</div>
      <div style="font-size:.75rem;color:#64748b;margin-bottom:8px">${sub}</div>
      <ul style="list-style:none">${items}</ul>
    </div>`;
}

function scoreRow(label, desc, color) {
  return `
    <div style="padding:8px 10px;background:rgba(255,255,255,.04);border-radius:6px;border-left:3px solid ${color}">
      <div style="font-size:.78rem;font-weight:700;color:${color};margin-bottom:3px">${label}</div>
      <div style="font-size:.73rem;color:#94a3b8">${desc}</div>
    </div>`;
}

function sigRow(name, weight, desc) {
  const bars = "█".repeat(weight) + "░".repeat(6 - weight);
  return `
    <div style="padding:6px 0;border-bottom:1px solid rgba(255,255,255,.05)">
      <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:2px">
        <span style="font-size:.78rem;font-weight:600">${name}</span>
        <span style="font-size:.65rem;color:#a78bfa;font-family:monospace">${bars} w=${weight}</span>
      </div>
      <div style="font-size:.72rem;color:#94a3b8">${desc}</div>
    </div>`;
}

function btCard(title, desc) {
  return `
    <div style="background:#0f172a;border-radius:6px;padding:12px">
      <div style="font-size:.82rem;font-weight:600;color:#a5b4fc;margin-bottom:5px">${title}</div>
      <div style="font-size:.75rem;color:#94a3b8;line-height:1.5">${desc}</div>
    </div>`;
}

function stageRow(n, label, color, desc) {
  return `
    <div style="display:flex;gap:14px;padding:10px 0;border-bottom:1px solid #334155">
      <div style="flex-shrink:0;width:80px;text-align:center;padding-top:2px">
        <span style="font-size:.75rem;font-weight:700;color:${color};background:${color}22;
              border-radius:4px;padding:3px 8px">Stage ${n}</span>
      </div>
      <div style="flex:1">
        <div style="font-size:.84rem;font-weight:600;color:${color};margin-bottom:3px">${label}</div>
        <div style="font-size:.76rem;color:#94a3b8;line-height:1.5">${desc}</div>
      </div>
    </div>`;
}

function compareRow(label, funda, tech) {
  return `
    <tr style="border-bottom:1px solid #1e293b">
      <td style="padding:9px 12px;color:#94a3b8;font-weight:600">${label}</td>
      <td style="padding:9px 12px;text-align:center;color:#e2e8f0">${funda}</td>
      <td style="padding:9px 12px;text-align:center;color:#e2e8f0">${tech}</td>
    </tr>`;
}

function cmdRow(label, cmd, desc) {
  return `
    <div style="padding:10px;background:#0f172a;border-radius:6px">
      <div style="font-size:.82rem;font-weight:600;margin-bottom:4px">${label}</div>
      <code style="font-size:.76rem;color:#3b82f6;background:#1e3a5f;padding:2px 8px;border-radius:4px">${cmd}</code>
      <div style="font-size:.76rem;color:#94a3b8;margin-top:5px">${desc}</div>
    </div>`;
}
