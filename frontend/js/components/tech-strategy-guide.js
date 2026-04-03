/**
 * Tech Strategy Guide — テクニカル重視ロジックの説明ページ
 * 2段階シグナルモデル（Stage A: 準備 + Stage B: 転換確認）
 */

export function renderTechStrategyGuide(container) {
  container.innerHTML = `
    <div class="section-title">🔬 テクニカル重視 — ロジック説明</div>

    <!-- 概要バナー -->
    <div style="background:rgba(99,102,241,.1);border:1px solid rgba(99,102,241,.3);border-radius:8px;padding:18px 22px;margin-bottom:20px">
      <div style="font-size:.95rem;font-weight:700;color:#a5b4fc;margin-bottom:8px">2段階シグナルモデルとは？</div>
      <div style="font-size:.82rem;color:#94a3b8;line-height:1.7">
        ファンダメンタルズを一切使わず、<strong style="color:#e2e8f0">値動きのパターン・モメンタムのみ</strong>でエントリーを判断する純テクニカルエンジン。<br>
        「準備ができている」と「転換が確定した」を<strong style="color:#e2e8f0">2段階に分けて判定</strong>することで、ダマシを減らし精度を高める。<br>
        各シグナルは過去データで<strong style="color:#e2e8f0">バックテスト済み</strong>。統計的に勝率52%以上のシグナルのみ採用。
      </div>
    </div>

    <!-- 2段階フロー図 -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:16px">🔄 エントリー判定フロー</h3>
      <div style="display:flex;align-items:stretch;gap:0;flex-wrap:wrap">
        ${flowBox("① 週次スキャン", "#6366f1",
          "毎週日曜夜に全銘柄をスキャン",
          ["16種のテクニカルシグナルを検出", "各シグナルをバックテストで検証", "信頼度スコア 0.58 以上のみ採用", "tech_weekly_picks として保存"])}
        <div style="display:flex;align-items:center;padding:0 8px;font-size:1.5rem;color:#475569;align-self:center">→</div>
        ${flowBox("② 日次 Stage A 確認", "#3b82f6",
          "毎朝、週次ピック銘柄を再チェック",
          ["週次で検出したシグナルが今日も継続しているか", "当日の価格でRRを再計算", "Stage A アクティブ → 「WATCH（様子見）」", "Stage A 消滅 → 「WAIT / PASSED」"])}
        <div style="display:flex;align-items:center;padding:0 8px;font-size:1.5rem;color:#475569;align-self:center">→</div>
        ${flowBox("③ 日次 Stage B 確認", "#10b981",
          "当日のローソク足・価格行動を分析",
          ["転換確認パターンを検出（9種）", "Stage A + Stage B 両方あり → エントリー可", "Stage B のみ → WATCH（Stage A が必要）", "Stage B なし → WATCH（確認待ち継続）"])}
        <div style="display:flex;align-items:center;padding:0 8px;font-size:1.5rem;color:#475569;align-self:center">→</div>
        ${flowBox("④ 最終判定", "#f59e0b",
          "verdict を確定",
          ["A+B+RR≥2.0+信頼度≥0.70 → 今日エントリー★", "A+B+RR≥1.5 → エントリー", "A のみ → 様子見（確認待ち）", "A なし → 待機 / 通過済"])}
      </div>
      <div style="margin-top:14px;padding:10px 14px;background:rgba(16,185,129,.08);border-radius:6px;font-size:.78rem;color:#6ee7b7;line-height:1.6">
        💡 <strong>ポイント</strong>: Stage A（準備）だけでは「様子見」にとどまる。リテスト完了・転換ローソク足など Stage B が確認されて初めて「エントリー」になる。ダマシを大幅に削減できる設計。
      </div>
    </div>

    <!-- 判定カード -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:16px">🎯 判定の見方</h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px">
        ${vcard("今日エントリー★", "#22c55e", "Stage A + B ✅  RR≥2.0  信頼度≥0.70",
          ["Stage A シグナルが継続中", "Stage B 転換確認パターンあり", "現在RR ≥ 2.0", "信頼度スコア ≥ 0.70"])}
        ${vcard("エントリー", "#60a5fa", "Stage A + B ✅  RR≥1.5",
          ["Stage A シグナルが継続中", "Stage B 転換確認パターンあり", "現在RR ≥ 1.5"])}
        ${vcard("様子見", "#eab308", "Stage A ✅  Stage B ❌（確認待ち）",
          ["Stage A シグナルは継続中", "転換確認パターンが未検出", "リテスト完了・ローソク転換を待つ"])}
        ${vcard("待機", "#f97316", "シグナル停止  RR 1.0〜1.5",
          ["今日は Stage A も消えた", "RRはまだ一定以上を維持", "来週の週次スキャンで再評価"])}
        ${vcard("通過済", "#ef4444", "RR < 1.0",
          ["現在値でRRが著しく低下", "既にブレイクアウト完了後", "新規エントリーには不適"])}
      </div>
    </div>

    <!-- Stage A シグナル一覧 -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:4px">📡 Stage A — 準備シグナル（16種）</h3>
      <div style="font-size:.78rem;color:#94a3b8;margin-bottom:16px">週次スキャンで検出。バックテスト勝率 52% 以上のみ採用。シグナルが重なるほど信頼度UP。</div>
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
        </div>
      </div>
    </div>

    <!-- Stage B シグナル一覧 -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:4px">✅ Stage B — 転換確認パターン（9種）</h3>
      <div style="font-size:.78rem;color:#94a3b8;margin-bottom:16px">日次チェックで検出。Stage A がある銘柄に対してのみ適用。これが出たときにエントリーシグナルへ昇格。</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        <div>
          <div style="font-size:.75rem;font-weight:700;color:#34d399;text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px">▲ ロング確認パターン</div>
          ${stageBRow("陽線包み足", "BULLISH_ENGULFING", "#34d399",
            "前日陰線を当日陽線が完全に包む。売り方の撤退と買い方の勢力交代を示す。最も信頼性の高い転換シグナル。")}
          ${stageBRow("ハンマー足", "HAMMER", "#34d399",
            "下ヒゲが実体の2倍以上・上ヒゲ小さい陽線。安値圏で売り方の攻撃を買い方が押し返した証拠。")}
          ${stageBRow("三川明けの明星", "MORNING_STAR", "#34d399",
            "大陰線 → 小実体（迷い）→ 大陽線の3本足パターン。下落から上昇への完全な転換を示す。")}
          ${stageBRow("高値3日切り上げ", "HIGHER_HIGHS_3D", "#34d399",
            "3日連続で高値が切り上がる。じわじわと買い優勢が続いていることを確認。")}
          ${stageBRow("リテスト完了", "RETEST_COMPLETE", "#60a5fa",
            "ブレイクアウト後に旧レジスタンス（±2.5%）まで引き戻し、当日終値で再び上回る。レジサポ転換の確認。最高精度の確認シグナル。")}
        </div>
        <div>
          <div style="font-size:.75rem;font-weight:700;color:#f87171;text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px">▼ ショート確認パターン</div>
          ${stageBRow("陰線包み足", "BEARISH_ENGULFING", "#f87171",
            "前日陽線を当日陰線が完全に包む。買い方の敗退を示す。ショートの最も強い転換確認。")}
          ${stageBRow("シューティングスター", "SHOOTING_STAR", "#f87171",
            "上ヒゲが実体の2倍以上・下ヒゲ小さい陰線。高値圏で買い方の攻撃を売り方が跳ね返した証拠。")}
          ${stageBRow("三川宵の明星", "EVENING_STAR", "#f87171",
            "大陽線 → 小実体 → 大陰線の3本足パターン。上昇から下落への転換を示す。")}
          ${stageBRow("安値3日切り下げ", "LOWER_LOWS_3D", "#f87171",
            "3日連続で安値が切り下がる。売り優勢の継続を確認。")}
          <div style="margin-top:10px;padding:10px;background:rgba(255,255,255,.04);border-radius:6px;font-size:.75rem;color:#94a3b8">
            💡 <strong style="color:#e2e8f0">出来高急増（VOLUME_SURGE）</strong> は共通ボーナス。他の確認パターンと同時に出来高が平均の1.5倍以上あった場合のみ追加される補強シグナル。
          </div>
        </div>
      </div>
    </div>

    <!-- 信頼度スコア算出 -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:16px">🔢 信頼度スコアの計算式（Stage A）</h3>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
        <div>
          <div style="font-family:monospace;background:#0f172a;border-radius:6px;padding:14px;font-size:.78rem;line-height:2;color:#e2e8f0">
            <span style="color:#94a3b8">// Raw Score</span><br>
            raw = <span style="color:#60a5fa">0.60</span> × 平均勝率<br>
            &nbsp;&nbsp;&nbsp;&nbsp;+ <span style="color:#60a5fa">0.25</span> × min(RR / 3.0, 1.0)<br>
            &nbsp;&nbsp;&nbsp;&nbsp;+ <span style="color:#60a5fa">0.10</span> × 合流ボーナス<br>
            &nbsp;&nbsp;&nbsp;&nbsp;+ <span style="color:#60a5fa">0.05</span> × Stage整合係数<br><br>
            <span style="color:#94a3b8">// Stage遷移ボーナス（新規）</span><br>
            if (Stage 1→2 転換) conf += <span style="color:#34d399">0.05</span><br><br>
            <span style="color:#94a3b8">// サンプル数補正（厳格化）</span><br>
            if (N < 10) adj = 0.50<br>
            else if (N < 20) adj = 0.70 + 0.245 × (N-10) / 10<br>
            else adj = 0.70 + 0.30 × √(N / 30)<br><br>
            <span style="color:#22c55e">信頼度 = raw × adj</span>
          </div>
        </div>
        <div style="display:flex;flex-direction:column;gap:10px">
          ${scoreRow("平均勝率（60%）", "過去のバックテストで算出した勝率の平均。最低52%以上のシグナルのみ採用。", "#60a5fa")}
          ${scoreRow("RR品質（25%）", "動的RR計算：直近20バーのサポート/レジスタンスレベルを基準に計算。市場環境に応じてRRは1.8～2.5で変動。", "#60a5fa")}
          ${scoreRow("合流ボーナス（10%）", "1シグナル=50pt / 2シグナル=75pt / 3以上=100pt。複数シグナルが同時に発火するほど信頼度UP。", "#a78bfa")}
          ${scoreRow("Stage整合（5%）", "LONG×Stage2=1.0 / SHORT×Stage4=1.0。逆方向は0.1〜0.4。 + Stage遷移で+0.05ボーナス。", "#34d399")}
          ${scoreRow("サンプル補正（乗数）", "N<10で50%割引（非常に保守的） / 10≤N<20で線形遷移 / N≥20でsqrt補正。小サンプルに厳しいペナルティ。", "#f97316")}
        </div>
      </div>
    </div>

    <!-- バックテストの仕組み -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:16px">⚗️ バックテストの仕組み（Stage A）</h3>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px">
        ${btCard("① シグナル検出", "過去データ（150バー以上）を全て走査し、各バーでシグナルが発火したかを記録。")}
        ${btCard("② エントリー想定", "シグナル発火バーの終値をエントリー価格とする。直近20バーのサポート/レジスタンスレベルを基準にストップロス・ターゲットを計算。")}
        ${btCard("③ 勝敗判定", "エントリー後10〜20日間、日中にストップ価格をタッチ → 負け / 目標価格をタッチ → 勝ち。期限内未決着は終値で判定。")}
        ${btCard("④ 勝率計算", "ヒット数が5件以上のシグナルのみ採用。勝率 = 勝ち数 ÷ 総ヒット数。52%未満は採用なし。ただしサンプル数が少ない場合は信頼度で大幅割引。")}
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
          "終値 > EMA200 だが EMA200 がフラット。上昇勢いが鈍化し天井形成中の可能性。Stage整合係数 = 0.4。")}
        ${stageRow(4, "ステージ4 — 下降トレンド（SHORTの理想ステージ）", "#ef4444",
          "終値 < EMA50 < EMA150 < EMA200 の逆整列 + EMA200が下向き。ショートに最適。Stage整合係数（SHORT）= 1.0。")}
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
            ${compareRow("エントリー確認", "日次でブレイクアウト条件を再チェック", "Stage A（準備） + Stage B（転換確認）の2段階")}
            ${compareRow("ダマシ対策", "出来高・ブレイクアウト条件", "リテスト完了・ローソク転換パターンで確認")}
            ${compareRow("ファンダデータ", "EPS成長・売上・決算サプライズ（参考）", "不使用（値動きのみ）")}
            ${compareRow("スコア算出", "テクニカル50% + RR30% + VCP20%", "勝率60% + RR25% + 合流10% + Stage5%")}
            ${compareRow("銘柄数", "10〜20件（厳選）", "5〜30件（信頼度閾値で変動）")}
            ${compareRow("向いている相場", "トレンド相場（一方向）", "あらゆる相場（ショートにも対応）")}
            ${compareRow("理想の使い方", "ベース銘柄をじっくり選定", "シグナル発火タイミングを捉える")}
          </tbody>
        </table>
      </div>
      <div style="margin-top:14px;padding:12px;background:rgba(16,185,129,.08);border:1px solid rgba(16,185,129,.2);border-radius:6px;font-size:.8rem;color:#6ee7b7">
        💡 <strong>推奨</strong>: ファンダ考慮で質の高い銘柄を絞り込み → テクニカルの Stage B 確認でエントリータイミングを合わせる、という組み合わせが最強。
        両方のリストに登場 + Stage B 確認済みの銘柄は最優先エントリー候補。
      </div>
    </div>

    <!-- コマンドリファレンス -->
    <div class="card">
      <h3 style="font-size:.9rem;font-weight:700;margin-bottom:14px">💻 コマンドリファレンス</h3>
      <div style="display:flex;flex-direction:column;gap:8px">
        ${cmdRow("週次テクニカルスキャン（Stage A 検出）",
          "python3 pipeline/run_pipeline.py --tech-weekly",
          "全銘柄に対して16シグナルを検出・バックテスト。信頼度でランキング。既存の価格データを再利用するため API 不要で 5〜15分。")}
        ${cmdRow("日次テクニカル調整（Stage A + B 判定）",
          "python3 pipeline/run_pipeline.py --tech-daily",
          "週次ピック銘柄について Stage A 継続確認 + Stage B 転換パターン検出を実行。BUY / STRONG_BUY / WATCH を判定して tech_daily_picks を更新。")}
        ${cmdRow("フルパイプライン日次更新（推奨）",
          "python3 pipeline/run_pipeline.py --daily-full",
          "価格データの差分取得 → ファンダ日次 + テクニカル日次を一括実行。毎朝 GitHub Actions で自動実行済み（JST 7:30）。")}
      </div>
    </div>
  `;
}

// ── helpers ───────────────────────────────────────────────────────────────────

function flowBox(title, color, sub, items) {
  const li = items.map(t =>
    `<li style="font-size:.73rem;color:#94a3b8;padding:2px 0 2px 12px;position:relative">
       <span style="position:absolute;left:0;color:${color}">•</span>${t}</li>`
  ).join("");
  return `
    <div style="flex:1;min-width:160px;background:#1e293b;border:1px solid ${color}44;border-top:3px solid ${color};border-radius:8px;padding:14px">
      <div style="font-size:.82rem;font-weight:700;color:${color};margin-bottom:3px">${title}</div>
      <div style="font-size:.72rem;color:#64748b;margin-bottom:8px">${sub}</div>
      <ul style="list-style:none">${li}</ul>
    </div>`;
}

function vcard(label, color, sub, conditions) {
  const items = conditions.map(c =>
    `<li style="font-size:.75rem;color:#94a3b8;padding:2px 0 2px 12px;position:relative">
       <span style="position:absolute;left:0;color:${color}">•</span>${c}</li>`
  ).join("");
  return `
    <div style="background:#1e293b;border:1px solid ${color};border-radius:8px;padding:14px">
      <div style="font-size:.85rem;font-weight:700;color:${color};margin-bottom:4px">${label}</div>
      <div style="font-size:.73rem;color:#64748b;margin-bottom:8px">${sub}</div>
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

function stageBRow(name, key, color, desc) {
  return `
    <div style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,.05)">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:3px">
        <span style="font-size:.78rem;font-weight:700">${name}</span>
        <span style="font-size:.65rem;font-weight:700;padding:1px 6px;border-radius:3px;
              background:${color}18;color:${color};border:1px solid ${color}44">${key}</span>
      </div>
      <div style="font-size:.72rem;color:#94a3b8;line-height:1.5">${desc}</div>
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
