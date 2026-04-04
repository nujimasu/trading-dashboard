/**
 * Strategy Guide — ハイブリッド（テクニカル50% + ファンダ50%）のロジック説明ページ
 */

export function renderStrategyGuide(container) {
  container.innerHTML = `
    <div class="section-title">📖 ハイブリッド判断基準・ロジック説明</div>

    <!-- ハイブリッドスコア概要 -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:12px">🔀 ハイブリッドスコア = テクニカル50% + ファンダメンタル50%</h3>
      <div style="font-size:.82rem;color:#94a3b8;margin-bottom:16px">
        従来のテクニカル偏重スコアから、ファンダメンタルを50%組み込んだハイブリッド方式に変更。<br>
        長期保有を前提とし、エントリーだけでなく<strong style="color:#f59e0b">ファンダベースの利確シグナル</strong>も出力します。
      </div>
      <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px">
        <div style="background:#0f172a; border-radius:8px; padding:14px; border-left:3px solid #3b82f6">
          <div style="font-size:.85rem; font-weight:700; color:#3b82f6; margin-bottom:10px">テクニカル（50点満点）</div>
          ${scoreRow("トレンド & モメンタム", "25pt", "Stage2・RSI・MACD → tech_score(1-10)を正規化")}
          ${scoreRow("パターン品質", "15pt", "VCPスコア(0-100)を正規化")}
          ${scoreRow("RR品質", "10pt", "リスクリワード比（3.0で満点）")}
        </div>
        <div style="background:#0f172a; border-radius:8px; padding:14px; border-left:3px solid #22c55e">
          <div style="font-size:.85rem; font-weight:700; color:#22c55e; margin-bottom:10px">ファンダメンタル（50点満点）</div>
          ${scoreRow("決算品質", "20pt", "EPS成長率(0-50%→12pt) + 売上成長率(0-30%→8pt)")}
          ${scoreRow("バリュエーション", "15pt", "PE≤15→満点、PE25→10pt、PE40→3pt、PE>60→0pt")}
          ${scoreRow("成長持続性", "15pt", "決算サプライズ(0-15%→8pt) + ROE(0-30%→7pt)")}
        </div>
      </div>
      <div style="font-size:.78rem; color:#64748b; margin-top:10px">
        ※ファンダメンタルデータ取得不可の場合はファンダ成分 = 25pt（中立）として計算
      </div>
    </div>

    <!-- 判定サマリーカード -->
    <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:16px; margin-bottom:24px">
      ${verdictCard("✅ 買い推奨（Tier 1）", "buy",
        "RR ≥ 2.0 + 高スコア",
        "テクニカル・ファンダ両面で高確度。長期ポジションとしてフルサイズ可。",
        ["Stage 2アップトレンド + RSI良好", "RR（リスクリワード比）≥ 2.0", "ハイブリッドスコア上位", "ファンダ：EPS成長 + バリュエーション良好"]
      )}
      ${verdictCard("⚠️ 様子見（Tier 2）", "watch",
        "RR ≥ 1.5",
        "条件はほぼ満たすが一部不足。ハーフサイズで慎重にエントリー。",
        ["テクニカル条件は概ね満たす", "RR ≥ 1.5（Tier 1には届かず）", "ファンダ：中立以上", "モメンタム継続中"]
      )}
      ${verdictCard("❌ 見送り", "nobuy",
        "RR < 1.5 or 条件未達",
        "テクニカルまたはファンダが基準を満たさない場合はスキップ。",
        ["RR < 1.5（リスクに見合わない）", "Stage 2崩壊 or RSI過熱", "ファンダ：弱気判定", "PE割高 + 成長鈍化の複合"]
      )}
    </div>

    <!-- 利確シグナル -->
    <div class="card" style="margin-bottom:20px; border:1px solid #f59e0b">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:14px; color:#f59e0b">💰 ファンダベース利確シグナル</h3>
      <div style="font-size:.82rem;color:#94a3b8;margin-bottom:14px">
        長期保有ポジションのファンダメンタル劣化を検出し、利確タイミングを提示します。
      </div>
      <div style="display:grid; grid-template-columns: repeat(2, 1fr); gap:12px; margin-bottom:16px">
        ${tpSignalCard("PE過熱", "PE > 30", "+1（≤40）/ +2（>40）", "バリュエーションが割高水準に到達")}
        ${tpSignalCard("EPS成長鈍化", "EPS成長率 < 0%", "+1（>-10%）/ +2（≤-10%）", "利益成長が減速・反転")}
        ${tpSignalCard("売上成長停滞", "売上成長率 < 0%", "+1", "トップラインが減少に転じた")}
        ${tpSignalCard("RSI過熱", "RSI > 75", "+1", "テクニカル的に買われすぎ")}
      </div>
      <h4 style="font-size:.85rem; font-weight:700; margin-bottom:10px">重篤度 → 判定</h4>
      <div style="display:flex; gap:12px; flex-wrap:wrap">
        ${tpVerdictBadge("利確推奨", "≥3", "#ef4444")}
        ${tpVerdictBadge("一部利確", "2", "#f97316")}
        ${tpVerdictBadge("出口注視", "1", "#eab308")}
        ${tpVerdictBadge("継続保有", "0", "#22c55e")}
      </div>
    </div>

    <!-- フィルタリングの流れ -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:16px">🔽 スクリーニングの流れ（全銘柄 → 推奨候補）</h3>
      <div style="display:flex; flex-direction:column; gap:0">
        ${funnelStep("Stage 1", "ユニバース構築", "約600銘柄", "#3b82f6",
          "FMP APIまたは静的リストから米国主要銘柄を取得。時価総額・上場市場でフィルタ。")}
        ${funnelStep("Stage 2", "価格データ取得", "全銘柄", "#3b82f6",
          "yfinanceから1年分の日次OHLCV（始値・高値・安値・終値・出来高）を取得。APIコスト: ゼロ。")}
        ${funnelStep("Stage 3", "テクニカルフィルタ", "〜20%通過", "#8b5cf6",
          "Stage 2アップトレンド + RSI 40-70 + MACD > Signal + 52週高値15%以内 + VCPプレチェック。")}
        ${funnelStep("Stage 4", "RR計算・詳細分析", "RR ≥ 1.5 のみ", "#f59e0b",
          "VCPスコア、ピボット価格、SL（ATR基準）、目標値を計算。RR < 1.5 は無条件除外。")}
        ${funnelStep("Stage 5", "ファンダメンタル取得", "全サバイバー", "#22c55e",
          "yfinanceでPE・EPS成長率・売上成長率・決算サプライズ・ROEを取得（7日間キャッシュ）。")}
        ${funnelStep("Stage 6", "ハイブリッドスコア算出", "10〜20銘柄", "#22c55e",
          "テクニカル50%（トレンド25+パターン15+RR10）+ ファンダ50%（決算品質20+バリュエーション15+成長持続15）= 0〜100。利確シグナルも同時検出。")}
      </div>
    </div>

    <!-- 各指標の説明 -->
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px; margin-bottom:20px">
      <div class="card">
        <h3 style="font-size:.9rem;font-weight:700;margin-bottom:14px">📐 テクニカル指標</h3>
        ${indicatorRow("Stage 2アップトレンド",
          "終値 > 50日移動平均 > 200日移動平均 の3点整列。上昇トレンドの基本条件。")}
        ${indicatorRow("RSI（相対力指数）",
          "40〜70が理想ゾーン。30以下 = 売られすぎ、70超 = 買われすぎ。")}
        ${indicatorRow("MACD",
          "MACDがシグナルラインを上回ると上昇モメンタム継続のサイン。")}
        ${indicatorRow("VCP（ボラティリティ収縮パターン）",
          "出来高が減りながら価格レンジが縮小。ブレイクアウト寸前の状態。")}
        ${indicatorRow("ATR（平均真の値動き幅）",
          "直近14日の平均値動き幅。SL設定の基準（1〜2 ATR）。")}
        ${indicatorRow("RR（リスクリワード比）",
          "（目標価格 − エントリー）÷（エントリー − SL）。1.5以上が最低基準。")}
      </div>

      <div class="card">
        <h3 style="font-size:.9rem;font-weight:700;margin-bottom:14px">📊 ファンダメンタル指標</h3>
        ${indicatorRow("EPS成長率（YoY）",
          "前年同期比の1株利益成長率。20%超 = 強気。マイナス = 利確シグナル候補。")}
        ${indicatorRow("売上成長率（YoY）",
          "前年同期比の売上高成長率。10%超で加点。マイナス = 利確シグナル候補。")}
        ${indicatorRow("PE（株価収益率）",
          "15以下 = 割安（満点）、25 = 適正、30超 = 過熱（利確シグナル候補）。")}
        ${indicatorRow("決算サプライズ（%）",
          "アナリスト予想と実績の乖離。5%超の上振れ = ポジティブ。")}
        ${indicatorRow("ROE（自己資本利益率）",
          "自己資本に対するリターン。15%超 = 効率的な経営。30%で満点。")}
        ${indicatorRow("ファンダ判定（5段階）",
          "強気 / やや強気 / 中立 / やや弱気 / 弱気。スコアとは別の参考表示。")}
      </div>
    </div>

    <!-- リスク管理ルール -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.9rem;font-weight:700;margin-bottom:14px">🛡️ リスク管理ルール</h3>
      <div style="display:grid; grid-template-columns: repeat(3,1fr); gap:12px">
        ${ruleCard("RR < 1.5 は例外なしにスキップ", "どんなに好材料があっても、RRが1.5未満ならエントリーしない。")}
        ${ruleCard("1トレードのリスクは口座の1〜2%", "SLに引っかかった際の損失がこの範囲に収まるようサイズ調整。")}
        ${ruleCard("セクター集中禁止", "同一セクター3銘柄未満・口座の30%まで。")}
        ${ruleCard("3連敗 → 翌週サイズ半減", "感情的な取り返し売買を防止。")}
        ${ruleCard("5連敗 → 2週間新規停止", "相場との相性が悪い時期は休む。")}
        ${ruleCard("月次-5%で防御モード", "残り期間は新規エントリー禁止。")}
      </div>
    </div>

    <!-- 更新頻度 -->
    <div class="card">
      <h3 style="font-size:.9rem;font-weight:700;margin-bottom:14px">🔄 データ更新タイミング</h3>
      <div style="display:flex; flex-direction:column; gap:8px">
        ${updateRow("週次フルスキャン（月曜朝）",
          "python3 pipeline/run_pipeline.py",
          "全銘柄を再スクリーニング → ハイブリッドスコア算出 → エントリー候補更新。")}
        ${updateRow("日次調整（平日毎日）",
          "python3 pipeline/run_pipeline.py --daily-full",
          "差分DL + Stage3-6再フィルタ + 利確シグナル検出。エントリー判定・利確判定を毎日更新。")}
        ${updateRow("銘柄検索（随時）",
          "ダッシュボードの「銘柄検索」から実行",
          "任意の銘柄をリアルタイムで分析。全指標・RR・判定を表示。")}
      </div>
    </div>
  `;
}

// ── helper functions ──────────────────────────────────────────────────────

function scoreRow(label, pts, desc) {
  return `
    <div style="display:flex; justify-content:space-between; align-items:baseline; padding:5px 0; border-bottom:1px solid #1e293b">
      <span style="font-size:.8rem; font-weight:600">${label}</span>
      <span style="font-size:.78rem; color:#f59e0b; font-weight:700">${pts}</span>
    </div>
    <div style="font-size:.73rem; color:#64748b; padding:2px 0 6px 0">${desc}</div>`;
}

function tpSignalCard(name, condition, severity, desc) {
  return `
    <div style="background:#1c1917; border-radius:6px; padding:10px">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px">
        <span style="font-size:.82rem; font-weight:700; color:#fbbf24">${name}</span>
        <span style="font-size:.72rem; color:#f97316; background:#431407; padding:2px 6px; border-radius:3px">${severity}</span>
      </div>
      <div style="font-size:.78rem; color:#d4d4d8; margin-bottom:3px">${condition}</div>
      <div style="font-size:.73rem; color:#71717a">${desc}</div>
    </div>`;
}

function tpVerdictBadge(label, threshold, color) {
  return `
    <div style="display:flex; align-items:center; gap:6px; background:${color}15; border:1px solid ${color}; border-radius:6px; padding:6px 12px">
      <span style="font-size:.82rem; font-weight:700; color:${color}">${label}</span>
      <span style="font-size:.72rem; color:#94a3b8">重篤度 ${threshold}</span>
    </div>`;
}

function verdictCard(title, type, rrLabel, desc, conditions) {
  const colors = { buy: "#22c55e", watch: "#eab308", nobuy: "#ef4444" };
  const color  = colors[type];
  const items  = conditions.map(c => `
    <li style="font-size:.78rem; color:#94a3b8; padding:3px 0 3px 14px; position:relative">
      <span style="position:absolute;left:0;color:${color}">•</span>${c}
    </li>`).join("");
  return `
    <div style="background:#1e293b; border:1px solid ${color}; border-radius:8px; padding:16px">
      <div style="font-size:.95rem; font-weight:700; color:${color}; margin-bottom:6px">${title}</div>
      <div style="font-size:1.4rem; font-weight:800; color:${color}; margin-bottom:8px">${rrLabel}</div>
      <div style="font-size:.8rem; color:#94a3b8; margin-bottom:10px">${desc}</div>
      <ul style="list-style:none">${items}</ul>
    </div>`;
}

function funnelStep(stage, title, throughput, color, desc) {
  return `
    <div style="display:flex; gap:14px; padding:10px 0; border-bottom:1px solid #334155">
      <div style="flex-shrink:0; width:72px; text-align:center">
        <div style="font-size:.7rem; font-weight:700; color:${color}; background:${color}22; border-radius:4px; padding:2px 6px">${stage}</div>
      </div>
      <div style="flex:1">
        <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:3px">
          <span style="font-size:.85rem; font-weight:600">${title}</span>
          <span style="font-size:.75rem; color:${color}; font-weight:600">${throughput}</span>
        </div>
        <div style="font-size:.78rem; color:#94a3b8">${desc}</div>
      </div>
    </div>`;
}

function indicatorRow(name, desc) {
  return `
    <div style="padding:8px 0; border-bottom:1px solid #334155">
      <div style="font-size:.82rem; font-weight:600; margin-bottom:3px">${name}</div>
      <div style="font-size:.78rem; color:#94a3b8">${desc}</div>
    </div>`;
}

function ruleCard(title, desc) {
  return `
    <div style="background:#0f172a; border-radius:6px; padding:12px">
      <div style="font-size:.82rem; font-weight:600; color:#f1f5f9; margin-bottom:6px">${title}</div>
      <div style="font-size:.77rem; color:#94a3b8">${desc}</div>
    </div>`;
}

function updateRow(label, cmd, desc) {
  return `
    <div style="padding:10px; background:#0f172a; border-radius:6px">
      <div style="font-size:.85rem; font-weight:600; margin-bottom:4px">${label}</div>
      <code style="font-size:.78rem; color:#3b82f6; background:#1e3a5f; padding:2px 8px; border-radius:4px">${cmd}</code>
      <div style="font-size:.78rem; color:#94a3b8; margin-top:5px">${desc}</div>
    </div>`;
}
