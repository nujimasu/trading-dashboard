/**
 * Strategy Guide — 買い・様子見・見送りの基準とロジック説明ページ
 */

export function renderStrategyGuide(container) {
  container.innerHTML = `
    <div class="section-title">📖 判断基準・ロジック説明</div>

    <!-- 判定サマリーカード -->
    <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:16px; margin-bottom:24px">
      ${verdictCard("✅ 買い推奨（Tier 1）", "buy",
        "RR ≥ 2.0",
        "全条件を満たした高確度のセットアップ。フルサイズでエントリー可。",
        ["Stage 2アップトレンド確認済み", "RR（リスクリワード比）≥ 2.0", "52週高値から15%以内", "VCPパターン（出来高収縮・レンジ縮小）"]
      )}
      ${verdictCard("⚠️ 様子見（Tier 2）", "watch",
        "RR ≥ 1.5",
        "条件はほぼ満たすが一部不足。ハーフサイズで慎重にエントリー。",
        ["Stage 2アップトレンド確認済み", "RR ≥ 1.5（Tier 1には届かず）", "モメンタム継続中（MACD > Signal）", "出来高収縮またはレンジ縮小"]
      )}
      ${verdictCard("❌ 見送り", "nobuy",
        "RR < 1.5 or 条件未達",
        "どれか1つでも満たさない場合は機械的にスキップ。例外なし。",
        ["Stage 2アップトレンドが崩れている", "RR < 1.5（リスクに見合うリターンが取れない）", "RSIが過熱域（70超）または極端な弱気（40未満）", "52週高値から15%以上下落中"]
      )}
    </div>

    <!-- フィルタリングの流れ -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:16px">🔽 スクリーニングの流れ（全銘柄 → 推奨候補）</h3>
      <div style="display:flex; flex-direction:column; gap:0">
        ${funnelStep("Stage 1", "ユニバース構築", "約600銘柄", "#3b82f6",
          "FMP APIまたは静的リストから米国主要銘柄を取得。時価総額・上場市場でフィルタ。")}
        ${funnelStep("Stage 2", "価格データ取得", "全銘柄", "#3b82f6",
          "yfinanceから1年分の日次OHLCV（始値・高値・安値・終値・出来高）を取得。APIコスト: ゼロ。")}
        ${funnelStep("Stage 3a", "Stage 2アップトレンド", "〜30%通過", "#8b5cf6",
          "終値 > SMA50 > SMA200 の3点が整列。ミナービニのトレンドテンプレート基準。相場全体が弱い時はここで大半が落ちる。")}
        ${funnelStep("Stage 3b", "RSI フィルタ", "〜50%通過", "#8b5cf6",
          "RSI 40〜70の範囲内。40未満 = モメンタムなし、70超 = 過熱しすぎ。いずれも新規エントリー不適。")}
        ${funnelStep("Stage 3c", "MACDフィルタ", "〜60%通過", "#8b5cf6",
          "MACD > Signal Line。上昇モメンタムが継続していることを確認。")}
        ${funnelStep("Stage 3d", "52週高値近接", "〜50%通過", "#8b5cf6",
          "現在値が52週高値の15%以内。ブレイクアウト寸前のポジションにいる銘柄のみを対象にする。")}
        ${funnelStep("Stage 3e", "VCPプレチェック", "〜30%通過", "#8b5cf6",
          "出来高収縮（直近 < 50日平均）またはレンジ縮小（直近10日レンジ < 前10日レンジ）。ベース形成の初期確認。")}
        ${funnelStep("Stage 4", "RR計算・詳細分析", "RR ≥ 1.5 のみ", "#f59e0b",
          "VCPスコア、ピボット価格、ストップロス（ATR基準）、目標値（直近100日高値）を計算。RR < 1.5 は無条件除外。")}
        ${funnelStep("Stage 5", "ファンダメンタル補強", "全サバイバー", "#22c55e",
          "FMP APIでEPS成長率・売上成長率・決算サプライズを取得（約3コール/銘柄）。FMPキーなしでも動作するが情報量が減る。")}
        ${funnelStep("Stage 6", "複合スコア・最終判定", "10〜20銘柄", "#22c55e",
          "テクニカル(50%) + RR(30%) + VCP(20%) で0〜100のスコアを算出。ファンダはスコア外の参考情報（強気/やや強気/中立/やや弱気/弱気）として表示。Tier 1/2を確定。")}
      </div>
    </div>

    <!-- 各指標の説明 -->
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px; margin-bottom:20px">
      <div class="card">
        <h3 style="font-size:.9rem;font-weight:700;margin-bottom:14px">📐 主要指標の説明</h3>
        ${indicatorRow("RR（リスクリワード比）",
          "（目標価格 − エントリー価格）÷ （エントリー価格 − ストップ価格）。1.5以上が最低基準。2.0以上でTier 1。")}
        ${indicatorRow("Stage 2アップトレンド",
          "終値 > 50日移動平均 > 200日移動平均 の3点整列。上昇トレンドの基本条件。")}
        ${indicatorRow("RSI（相対力指数）",
          "0〜100のモメンタム指標。40〜70が理想ゾーン。30以下 = 売られすぎ（まだ下がるかも）、70超 = 買われすぎ（反落リスク）。")}
        ${indicatorRow("MACD",
          "短期と長期の移動平均の乖離。MACDがシグナルラインを上回ると上昇モメンタム継続のサイン。")}
        ${indicatorRow("VCP（ボラティリティ収縮パターン）",
          "ミナービニ考案。出来高が減りながら価格レンジが徐々に縮小するパターン。エネルギーが溜まってブレイクアウト寸前の状態。")}
        ${indicatorRow("ATR（平均真の値動き幅）",
          "直近14日の平均的な1日の値動き幅。ストップロスの設定基準に使用（最低1ATR、最大2ATR）。")}
      </div>

      <div class="card">
        <h3 style="font-size:.9rem;font-weight:700;margin-bottom:14px">🎯 トレードプランの算出方法</h3>
        ${indicatorRow("エントリー価格",
          "現在の終値（スクリーニング実行時点）。ブレイクアウト確認後に実際にエントリー。")}
        ${indicatorRow("ストップロス（損切り価格）",
          "過去20日間の最安値を基準に設定。ただし最低1 ATR、最大2 ATRの範囲に制限（極端なストップを防ぐ）。")}
        ${indicatorRow("目標価格",
          "過去100日間の最高値を次のレジスタンス（抵抗線）として設定。直近高値以上のデータがない場合はATR×3で代用。")}
        ${indicatorRow("ポジションサイズ（目安）",
          "Tier 1（RR≥2.0）→ フルサイズ（口座の最大15%）。Tier 2（RR≥1.5）→ ハーフサイズ（口座の最大7.5%）。")}
        ${indicatorRow("複合スコア（0〜100）",
          "テクニカル指標(50%) + RR品質(30%) + VCPスコア(20%) の加重合計。ファンダメンタルはスコアに含まず「ファンダ判定」として参考表示のみ。上位銘柄ほど優先度が高い。")}
        ${indicatorRow("市場ヘルス（全体スコア）",
          "全スクリーニング対象銘柄のうち「Stage 2アップトレンド」に入っている銘柄の割合。50%以上=強気、30-50%=中立、30%未満=弱気。")}
      </div>
    </div>

    <!-- リスク管理ルール -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.9rem;font-weight:700;margin-bottom:14px">🛡️ リスク管理ルール（market-analyst.md準拠）</h3>
      <div style="display:grid; grid-template-columns: repeat(3,1fr); gap:12px">
        ${ruleCard("RR < 1.5 は例外なしにスキップ", "どんなに好材料があっても、RRが1.5未満ならエントリーしない。これはシステムレベルで強制されている。")}
        ${ruleCard("1トレードのリスクは口座の1〜2%", "例：口座100万円なら1トレード最大2万円の損失。ストップに引っかかった際の損失がこの範囲に収まるようサイズ調整する。")}
        ${ruleCard("セクター集中禁止", "同一セクターへの同時保有は3銘柄未満・口座の30%まで。特定セクターへの過度な集中リスクを避ける。")}
        ${ruleCard("3連敗 → 翌週はサイズ半減", "3回連続で損切りになった場合、翌週は全ポジションをハーフサイズにする。感情的な取り返し売買を防ぐ。")}
        ${ruleCard("5連敗 → 2週間新規停止", "さらに連敗が続く場合は完全に立ち止まる。相場との相性が悪い時期は休むことが最善。")}
        ${ruleCard("月次-5%で防御モード", "月間の損益が-5%に達したら残りの期間は新規エントリー禁止。それ以上の損失を防ぐためのセーフティネット。")}
      </div>
    </div>

    <!-- 更新頻度の説明 -->
    <div class="card">
      <h3 style="font-size:.9rem;font-weight:700;margin-bottom:14px">🔄 データ更新のタイミングと内容</h3>
      <div style="display:flex; flex-direction:column; gap:8px">
        ${updateRow("週次更新（月曜朝・約15〜30分）",
          "python3 pipeline/run_pipeline.py",
          "全銘柄データを取得し直し、スクリーニング全段階を再実行。週次推奨銘柄リストが更新される。")}
        ${updateRow("日次更新（平日毎日・約1〜2分）",
          "python3 pipeline/run_pipeline.py --daily-only",
          "週次推奨銘柄の現在値・RR・ブレイクアウト状況のみを更新。「本日のエントリー」タブに反映される。")}
        ${updateRow("銘柄検索（随時・約10〜30秒）",
          "ダッシュボードの「銘柄検索」から直接実行",
          "任意の銘柄をリアルタイムで分析。yfinanceから最新データを取得し、全指標・RR・判定を表示。")}
      </div>
    </div>
  `;
}

// ── helper functions ──────────────────────────────────────────────────────

function verdictCard(title, type, rrLabel, desc, conditions) {
  const colors = { buy: "#22c55e", watch: "#eab308", nobuy: "#ef4444" };
  const bgs    = { buy: "#166534", watch: "#713f12", nobuy: "#7f1d1d" };
  const color  = colors[type];
  const bg     = bgs[type];
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
