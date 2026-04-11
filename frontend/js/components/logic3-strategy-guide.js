/**
 * Logic3 Strategy Guide — 押し目買い（4Hトリガー版）の説明ページ
 */

export function renderLogic3StrategyGuide(container) {
  container.innerHTML = `
    <div class="section-title">⚡ ロジック３ — ロジック説明（押し目買い・4Hトリガー版）</div>

    <!-- ロジック３ vs ロジック４ の違い -->
    <div style="background:rgba(99,102,241,.08);border:1px solid rgba(99,102,241,.3);border-radius:8px;padding:18px 22px;margin-bottom:20px">
      <div style="font-size:.95rem;font-weight:700;color:#a5b4fc;margin-bottom:8px">ロジック３とロジック４の違い</div>
      <div style="font-size:.82rem;color:#94a3b8;line-height:1.7">
        一次フィルター・二次フィルター・ボーナスフラグは<strong style="color:#e2e8f0">完全に同じ</strong>。<br>
        違いは<strong style="color:#e2e8f0">エントリートリガーの時間軸</strong>のみ：
        <div style="display:flex;gap:16px;margin-top:10px">
          <div style="flex:1;background:rgba(30,41,59,.7);border:1px solid rgba(139,92,246,.3);border-radius:6px;padding:10px 14px">
            <div style="font-weight:700;color:#a5b4fc;font-size:.82rem">ロジック３（4Hトリガー）</div>
            <div style="font-size:.75rem;color:#94a3b8;margin-top:4px">4時間足でプライスアクションを検出。ノイズが少なく、確度が高い反面、シグナル発生頻度は低い。</div>
          </div>
          <div style="flex:1;background:rgba(30,41,59,.7);border:1px solid rgba(16,185,129,.3);border-radius:6px;padding:10px 14px">
            <div style="font-weight:700;color:#6ee7b7;font-size:.82rem">ロジック４（1Hトリガー）</div>
            <div style="font-size:.75rem;color:#94a3b8;margin-top:4px">1時間足でプライスアクションを検出。感度が高く、シグナルは多いが、ダマシも増える。</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 判定凡例 -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:12px">📋 判定の見方（リスト画面）</h3>
      <div style="display:flex;flex-wrap:wrap;gap:10px">
        <div style="display:flex;align-items:center;gap:8px;background:rgba(16,185,129,.1);border:1px solid rgba(16,185,129,.4);border-radius:6px;padding:8px 14px">
          <span style="font-weight:700;color:#10b981">最優先候補</span>
          <span style="font-size:.75rem;color:#94a3b8">サポートから≤3% かつ 4Hトリガー確認済み → 即エントリー検討</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px;background:rgba(245,158,11,.1);border:1px solid rgba(245,158,11,.4);border-radius:6px;padding:8px 14px">
          <span style="font-weight:700;color:#f59e0b">サポート接近中</span>
          <span style="font-size:.75rem;color:#94a3b8">サポートから≤3% だがトリガー未確認 → 4Hシグナル出るまで待機</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px;background:rgba(100,116,139,.1);border:1px solid rgba(100,116,139,.4);border-radius:6px;padding:8px 14px">
          <span style="font-weight:700;color:#94a3b8">押し目待ち</span>
          <span style="font-size:.75rem;color:#94a3b8">サポートまで>3% → まだ押し目途中、監視継続</span>
        </div>
      </div>
    </div>

    <!-- 一次フィルター -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:14px">① 一次フィルター — ロジック４と同一</h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px">
        ${filter("週足トレンド", "週足 20EMA > 200EMA", "#10b981", "中長期的に上昇トレンドが継続していること。")}
        ${filter("日足パーフェクトオーダー", "株価 > 20EMA > 50EMA > 200EMA", "#3b82f6", "短・中・長期の移動平均が上から順に並んでいる状態。")}
        ${filter("3ヶ月パフォーマンス", "過去3ヶ月の騰落率 > 0%", "#8b5cf6", "直近の値動きがプラスであること。")}
        ${filter("流動性", "20日平均出来高 ≥ 50万株", "#f59e0b", "出来高が低いとテクニカル分析が機能しにくいため除外。")}
      </div>
    </div>

    <!-- 二次フィルター（簡略） -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:14px">② 二次フィルター — ロジック４と同一</h3>
      <div style="font-size:.8rem;color:#94a3b8;line-height:1.7">
        ダウ理論、サポートラインのコンフルエンス、レジサポ転換、R:R計算 — いずれもロジック４と同一のロジック。<br>
        詳細は<strong style="color:#e2e8f0">ロジック４の説明</strong>を参照してください。
      </div>
    </div>

    <!-- 4Hトリガー（ロジック３固有） -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:14px">③ 4Hトリガー（ロジック３の特徴）</h3>
      <div style="font-size:.8rem;color:#94a3b8;line-height:1.7;margin-bottom:12px">
        日足フィルターを通過した後、<strong style="color:#a5b4fc">4時間足</strong>でサポートからの反発シグナルを確認する。<br>
        1Hよりもノイズが少なく、確度の高いシグナルが得られる。
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        <div>
          <div style="font-size:.8rem;font-weight:700;color:#e2e8f0;margin-bottom:8px">4時間足 構造チェック</div>
          <div style="font-size:.78rem;color:#94a3b8;line-height:1.7">
            直近4Hバーの線形回帰で方向性を判定:
            <div style="margin-top:6px">
              ${badge("bullish", "#10b981")} 上昇傾き＋陽線 → 反発の兆し<br>
              ${badge("neutral", "#f59e0b")} 方向不明確<br>
              ${badge("bearish", "#ef4444")} 下降傾き＋陰線 → まだ下落中
            </div>
          </div>
        </div>
        <div>
          <div style="font-size:.8rem;font-weight:700;color:#a5b4fc;margin-bottom:8px">4時間足 トリガーシグナル</div>
          <div style="font-size:.78rem;color:#94a3b8;line-height:1.7">
            サポート近傍（±5%）で以下を4H足で検出:
            <ul style="margin:6px 0 0 16px;line-height:1.9">
              <li><strong style="color:#a5b4fc">ピンバー(4H)</strong> — 下ヒゲ ≥ 実体×2、陽線</li>
              <li><strong style="color:#a5b4fc">逆ハンマー(4H)</strong> — 上ヒゲ ≥ 実体×2、下ヒゲ小</li>
              <li><strong style="color:#a5b4fc">強気エンガルフィング(4H)</strong> — 陰線を包む陽線</li>
              <li><strong style="color:#a5b4fc">切り込み線(4H)</strong> — 陰線→陽線が前足中間以上まで戻す</li>
              <li><strong style="color:#a5b4fc">出来高急増(4H)</strong> — 全4H平均×1.5倍以上の陽線</li>
              <li><strong style="color:#a5b4fc">明けの明星(4H)</strong> — 大陰線→小実体→大陽線の3本反転</li>
              <li><strong style="color:#a5b4fc">赤三兵(4H)</strong> — 3本連続陽線、各足が切り上がり</li>
              <li><strong style="color:#a5b4fc">ダブルボトム(4H)</strong> — 1.5%以内の二底形成</li>
            </ul>
          </div>
        </div>
      </div>
    </div>

    <!-- ローソクパターン図鑑 -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:14px">🕯️ ローソクパターン図鑑（検出対象8パターン）</h3>
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

    <!-- 注意事項 -->
    <div class="card">
      <h3 style="font-size:.95rem;font-weight:700;margin-bottom:12px">⚠️ 重要な注意事項</h3>
      <div style="font-size:.8rem;color:#94a3b8;line-height:2">
        <div>🚫 <strong style="color:#e2e8f0">R:R 1.5未満は推奨しない</strong></div>
        <div>🚫 <strong style="color:#e2e8f0">低流動性銘柄は除外</strong></div>
        <div>✅ <strong style="color:#e2e8f0">4Hトリガー待ち</strong> — 「サポート接近中」でも4Hシグナルが出るまでエントリーは見送り</div>
        <div>✅ <strong style="color:#e2e8f0">ロジック４と比較</strong> — 両方で「最優先候補」ならエントリー確度が非常に高い</div>
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
  return `<svg width="40" height="70" viewBox="0 0 40 70"><${_candle(13, 50, 20, 65, 25)}><line x1="0" y1="58" x2="40" y2="58" stroke="#475569" stroke-width="0.5" stroke-dasharray="2"/></svg>`;
}
function candleSvg_inverseHammer() {
  return `<svg width="40" height="70" viewBox="0 0 40 70">${_candle(13, 55, 10, 62, 50)}</svg>`;
}
function candleSvg_engulfing() {
  return `<svg width="60" height="70" viewBox="0 0 60 70">${_candle(8, 25, 18, 50, 45, 12)}${_candle(28, 50, 12, 55, 20, 18)}</svg>`;
}
function candleSvg_piercing() {
  return `<svg width="60" height="70" viewBox="0 0 60 70">${_candle(8, 20, 15, 55, 48, 14)}${_candle(30, 52, 22, 58, 30, 14)}<line x1="0" y1="34" x2="60" y2="34" stroke="#f59e0b" stroke-width="0.5" stroke-dasharray="2"/></svg>`;
}
function candleSvg_morningStar() {
  return `<svg width="76" height="70" viewBox="0 0 76 70">${_candle(4, 15, 10, 55, 50, 14)}${_candle(26, 52, 48, 58, 54, 10)}${_candle(44, 48, 12, 52, 18, 14)}</svg>`;
}
function candleSvg_threeWhite() {
  return `<svg width="76" height="70" viewBox="0 0 76 70">${_candle(4, 50, 42, 60, 45, 14)}${_candle(26, 42, 30, 48, 34, 14)}${_candle(48, 32, 18, 38, 22, 14)}</svg>`;
}
function candleSvg_volumeSurge() {
  return `<svg width="60" height="70" viewBox="0 0 60 70"><rect x="5" y="50" width="10" height="15" fill="#475569" rx="1"/><rect x="20" y="48" width="10" height="17" fill="#475569" rx="1"/><rect x="35" y="30" width="14" height="35" fill="#22c55e55" rx="1"/>${_candle(37, 35, 15, 50, 20, 10)}</svg>`;
}
function candleSvg_doubleBottom() {
  return `<svg width="80" height="70" viewBox="0 0 80 70"><path d="M5 20 Q20 55 35 30 Q50 55 65 20" fill="none" stroke="#f59e0b" stroke-width="2"/><line x1="0" y1="52" x2="80" y2="52" stroke="#ef4444" stroke-width="0.5" stroke-dasharray="3"/><circle cx="20" cy="52" r="3" fill="none" stroke="#f59e0b" stroke-width="1.5"/><circle cx="50" cy="52" r="3" fill="none" stroke="#f59e0b" stroke-width="1.5"/></svg>`;
}
