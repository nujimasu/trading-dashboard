import { apiFetch } from "../utils/api.js?v=3";

const COLUMNS = [
  { key: "ticker", label: "ティッカー", kind: "text" },
  { key: "state", label: "状態", kind: "text" },
  { key: "volume", label: "出来高", kind: "verdict" },
  { key: "dow_trend", label: "ダウ理論", kind: "text" },
  { key: "touch_days_ago", label: "タッチ", kind: "number" },
  { key: "price", label: "株価", kind: "number" },
  { key: "ema20_dist", label: "20EMA乖離%", kind: "number" },
  { key: "adx", label: "ADX", kind: "number" },
  { key: "rs63", label: "RS3M%", kind: "number" },
  { key: "rs126", label: "RS6M%", kind: "number" },
  { key: "atr_pct", label: "ATR%", kind: "number" },
  { key: "dollar_vol", label: "売買代金($M)", kind: "number" },
  { key: "po_weeks", label: "PO継続週", kind: "number" },
];

const VOLUME_VERDICTS = Object.freeze({
  bounce_confirmed: { label: "✅ 出来高を伴う反発", icon: "✅", tone: "green", weight: 3 },
  healthy_pullback: { label: "✅ 健全な押し目", icon: "✅", tone: "green", weight: 2 },
  accumulation: { label: "✅ 買い意欲", icon: "✅", tone: "green", weight: 2 },
  selling_climax: { label: "🔄 セリクラの可能性", icon: "🔄", tone: "yellow", weight: 1 },
  quiet_setup: { label: "💤 ブレイク待ち", icon: "💤", tone: "gray", weight: 0 },
  neutral: { label: "―", icon: "―", tone: "gray", weight: 0 },
  weak_bounce: { label: "⚠️ 出来高薄い反発", icon: "⚠️", tone: "yellow", weight: -1 },
  distribution: { label: "⚠️ 分配の疑い", icon: "⚠️", tone: "red", weight: -2 },
  selling_pressure: { label: "⚠️ 売り圧力", icon: "⚠️", tone: "red", weight: -2 },
});

const PREFS_KEY = "swing-screener-prefs-v1";
const FILTER_GROUPS = Object.freeze({
  volumeVerdicts: {
    label: "出来高判定",
    values: Object.keys(VOLUME_VERDICTS),
    labels: Object.fromEntries(Object.entries(VOLUME_VERDICTS).map(([key, meta]) => [key, meta.label])),
  },
  dowTrends: {
    label: "ダウ理論",
    values: ["up", "neutral", "down"],
    labels: { up: "上昇", neutral: "中立", down: "下降" },
  },
  pickStates: {
    label: "状態",
    values: ["bounced", "pulling"],
    labels: { bounced: "✅ 反発確認済", pulling: "⏳ 押し目進行中" },
  },
  priceZones: {
    label: "価格位置",
    values: ["high", "mid", "low"],
    labels: { high: "高値圏", mid: "中間", low: "安値圏" },
  },
});

const DEFAULT_PREFS = Object.freeze({
  adxEnabled: true,
  adxMin: 25,
  filters: {
    volumeVerdicts: [...FILTER_GROUPS.volumeVerdicts.values],
    dowTrends: ["up", "neutral"],
    pickStates: [...FILTER_GROUPS.pickStates.values],
    priceZones: [...FILTER_GROUPS.priceZones.values],
  },
  sorts: [
    { key: "rs126", direction: -1 },
    { key: null, direction: -1 },
    { key: null, direction: -1 },
  ],
});

function defaultPrefs() {
  return JSON.parse(JSON.stringify(DEFAULT_PREFS));
}

export function sanitizeSwingPrefs(value) {
  const fallback = defaultPrefs();
  if (!value || typeof value !== "object" || Array.isArray(value)) return fallback;
  const validColumnKeys = new Set(COLUMNS.map(column => column.key));
  const result = defaultPrefs();
  if (typeof value.adxEnabled === "boolean") result.adxEnabled = value.adxEnabled;
  if (Number.isFinite(value.adxMin) && value.adxMin >= 15 && value.adxMin <= 35) result.adxMin = value.adxMin;
  if (value.filters && typeof value.filters === "object" && !Array.isArray(value.filters)) {
    for (const [groupKey, group] of Object.entries(FILTER_GROUPS)) {
      const selected = value.filters[groupKey];
      if (Array.isArray(selected) && selected.every(item => typeof item === "string")) {
        result.filters[groupKey] = [...new Set(selected.filter(item => group.values.includes(item)))];
      }
    }
  }
  if (Array.isArray(value.sorts) && value.sorts.length === 3) {
    result.sorts = value.sorts.map((sort, index) => {
      if (!sort || typeof sort !== "object" || Array.isArray(sort)) return fallback.sorts[index];
      const key = sort.key === null || sort.key === "" ? null : sort.key;
      if (key !== null && !validColumnKeys.has(key)) return fallback.sorts[index];
      return { key, direction: sort.direction === 1 ? 1 : -1 };
    });
  }
  return result;
}

export function loadSwingPrefs(storage) {
  try {
    const target = storage === undefined ? globalThis.localStorage : storage;
    const raw = target?.getItem(PREFS_KEY);
    return raw ? sanitizeSwingPrefs(JSON.parse(raw)) : defaultPrefs();
  } catch {
    return defaultPrefs();
  }
}

function saveSwingPrefs(prefs, storage) {
  try {
    const target = storage === undefined ? globalThis.localStorage : storage;
    target?.setItem(PREFS_KEY, JSON.stringify(sanitizeSwingPrefs(prefs)));
  } catch {
    // Storage can be unavailable (privacy mode or quota); rendering must continue.
  }
}

function pickGroupValue(pick, groupKey) {
  if (groupKey === "volumeVerdicts") return pick.volume?.verdict;
  if (groupKey === "dowTrends") return pick.dow_trend;
  if (groupKey === "pickStates") return pick.state;
  if (groupKey === "priceZones") return pick.volume?.price_zone;
  return undefined;
}

export function filterSwingPicks(picks, prefs, omittedGroup = null) {
  const safePrefs = sanitizeSwingPrefs(prefs);
  return picks.filter(pick => {
    if (safePrefs.adxEnabled && (!finite(pick.adx) || Number(pick.adx) < safePrefs.adxMin)) return false;
    for (const groupKey of Object.keys(FILTER_GROUPS)) {
      if (groupKey === omittedGroup) continue;
      const selected = safePrefs.filters[groupKey];
      if (!selected.length) continue;
      if ((groupKey === "volumeVerdicts" || groupKey === "priceZones") && !pick.volume) continue;
      if (!selected.includes(pickGroupValue(pick, groupKey))) return false;
    }
    return true;
  });
}

const LINE_COLORS = {
  trendline: "#f59e0b",
  neckline: "#22d3ee",
  flag_upper: "#60a5fa",
  flag_lower: "#60a5fa",
  tri_upper: "#fb923c",
  tri_lower: "#fb923c",
};

const LEVEL_COLORS = {
  "日足EMA20": "#facc15",
  "直近スイング高値": "#ef4444",
  "直近スイング安値": "#22c55e",
  "出来高集中帯上端": "#a78bfa",
  "出来高集中帯下端": "#a78bfa",
};

const STYLE = `
  .swing-shell { --sw-line:#26354d; --sw-panel:#111c30; display:grid; gap:16px; }
  .swing-shell > * { min-width:0; }
  .swing-hero { position:relative; overflow:hidden; border:1px solid var(--sw-line); border-radius:14px; padding:18px 20px; background:linear-gradient(120deg,#101d32 0%,#0e1728 62%,#14243a 100%); }
  .swing-hero::after { content:"W1 × D1"; position:absolute; right:16px; top:2px; color:rgba(96,165,250,.08); font-size:4.4rem; font-weight:900; letter-spacing:-.08em; pointer-events:none; }
  .swing-kicker { color:#60a5fa; font-size:.68rem; letter-spacing:.18em; text-transform:uppercase; font-weight:800; }
  .swing-title-row { display:flex; align-items:baseline; flex-wrap:wrap; gap:10px; margin-top:3px; }
  .swing-title { margin:0; font-size:1.35rem; letter-spacing:.01em; }
  .swing-date { color:var(--text-muted); font-size:.78rem; font-variant-numeric:tabular-nums; }
  .swing-funnel { display:flex; align-items:stretch; flex-wrap:wrap; gap:7px; margin-top:15px; }
  .swing-funnel-node { min-width:94px; padding:8px 10px; border:1px solid #2b3d59; border-radius:8px; background:rgba(15,23,42,.74); }
  .swing-funnel-node span { display:block; color:var(--text-muted); font-size:.62rem; letter-spacing:.06em; }
  .swing-funnel-node strong { display:block; margin-top:2px; color:#e2e8f0; font-size:1.05rem; font-variant-numeric:tabular-nums; }
  .swing-funnel-arrow { align-self:center; color:#47617f; font-weight:900; }
  .swing-note { margin-top:10px; color:#fbbf24; font-size:.72rem; }
  .swing-controls { display:grid; gap:12px; padding:12px; border:1px solid var(--sw-line); border-radius:12px; background:var(--sw-panel); }
  .swing-control-top { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px; }
  .swing-control { display:flex; align-items:center; gap:8px; min-height:34px; padding:5px 9px; border:1px solid #2a3a54; border-radius:8px; background:#0d1727; font-size:.76rem; color:#cbd5e1; }
  .swing-control input[type="checkbox"] { accent-color:#3b82f6; }
  .swing-adx-range { width:116px; accent-color:#3b82f6; }
  .swing-adx-value { min-width:24px; color:#93c5fd; font-weight:800; font-variant-numeric:tabular-nums; }
  .swing-reset, .swing-mini { border:1px solid #365071; border-radius:6px; background:#16253a; color:#bfdbfe; font:inherit; cursor:pointer; }
  .swing-reset { min-height:32px; padding:5px 10px; font-size:.72rem; }
  .swing-guide-link { margin-left:auto; color:#93c5fd; font-size:.69rem; text-underline-offset:3px; }
  .swing-guide-link:hover { color:#dbeafe; }
  .swing-mini { padding:2px 6px; font-size:.62rem; }
  .swing-filter-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }
  .swing-filter-group { min-width:0; padding:9px; border:1px solid #2a3a54; border-radius:9px; background:#0d1727; }
  .swing-filter-group.unfiltered { border-style:dashed; opacity:.72; }
  .swing-filter-head { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:7px; }
  .swing-filter-title { color:#dbeafe; font-size:.72rem; font-weight:800; }
  .swing-filter-actions { display:flex; align-items:center; gap:5px; }
  .swing-unfiltered { color:#93c5fd; font-size:.61rem; }
  .swing-filter-options { display:flex; flex-wrap:wrap; gap:6px; }
  .swing-filter-chip { display:inline-flex; align-items:center; gap:5px; min-height:27px; padding:3px 7px; border:1px solid #30435e; border-radius:999px; color:#cbd5e1; font-size:.67rem; cursor:pointer; }
  .swing-filter-chip:has(input:checked) { border-color:#4775aa; background:#1a3150; color:#eaf2ff; }
  .swing-filter-chip input { margin:0; accent-color:#3b82f6; }
  .swing-option-count { color:#8294aa; font-variant-numeric:tabular-nums; }
  .swing-sort-panel { display:grid; gap:7px; padding-top:10px; border-top:1px solid #26354d; }
  .swing-sort-row { display:grid; grid-template-columns:76px minmax(130px,220px) minmax(92px,130px); align-items:center; gap:7px; }
  .swing-sort-label { color:var(--text-muted); font-size:.69rem; font-weight:700; }
  .swing-select { width:100%; min-height:31px; border:1px solid #30435e; border-radius:6px; padding:4px 7px; background:#0d1727; color:#dbeafe; font:inherit; font-size:.71rem; }
  .swing-results { border:1px solid var(--sw-line); border-radius:12px; background:#0d1727; overflow:hidden; }
  .swing-results-bar { display:flex; justify-content:space-between; gap:12px; padding:10px 13px; border-bottom:1px solid var(--sw-line); color:var(--text-muted); font-size:.74rem; }
  .swing-count { color:#dbeafe; font-weight:800; }
  .swing-table-wrap { min-width:0; overflow-x:auto; overflow-y:auto; max-height:620px; }
  .swing-table { min-width:1180px; font-variant-numeric:tabular-nums; }
  .swing-table thead { position:sticky; top:0; z-index:2; background:#111c30; }
  .swing-table th { padding:0; white-space:nowrap; }
  .swing-sort { width:100%; padding:10px 9px; border:0; background:transparent; color:var(--text-muted); text-align:left; font:inherit; font-weight:700; cursor:pointer; }
  .swing-sort:hover, .swing-sort.active { color:#bfdbfe; }
  .swing-table td { padding:9px; white-space:nowrap; border-bottom:1px solid rgba(51,65,85,.52); }
  .swing-row { cursor:pointer; transition:background .14s ease; }
  .swing-row:hover, .swing-row.selected { background:rgba(59,130,246,.09); }
  .swing-tv { color:#93c5fd; font-weight:850; letter-spacing:.025em; text-decoration:none; }
  .swing-tv:hover { color:#dbeafe; text-decoration:underline; }
  .swing-badge { display:inline-flex; align-items:center; border-radius:999px; padding:3px 8px; font-size:.68rem; font-weight:800; }
  .swing-state-bounced { color:#86efac; background:rgba(34,197,94,.14); border:1px solid rgba(34,197,94,.28); }
  .swing-state-pulling { color:#fde68a; background:rgba(245,158,11,.13); border:1px solid rgba(245,158,11,.27); }
  .swing-dow-up { color:#86efac; background:rgba(34,197,94,.13); }
  .swing-dow-neutral, .swing-dow-unknown { color:#cbd5e1; background:rgba(148,163,184,.13); }
  .swing-dow-down { color:#fca5a5; background:rgba(239,68,68,.13); }
  .swing-volume-icon { display:inline-grid; min-width:24px; place-items:center; font-size:.84rem; }
  .swing-positive { color:#86efac; }
  .swing-negative { color:#fca5a5; }
  .swing-empty { padding:34px 16px; color:var(--text-muted); text-align:center; }
  .swing-detail { border:1px solid #314563; border-radius:12px; overflow:hidden; background:#0a1322; box-shadow:0 18px 45px rgba(0,0,0,.24); }
  .swing-detail[hidden] { display:none; }
  .swing-detail-head { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px; padding:11px 14px; border-bottom:1px solid #263750; background:#111d31; }
  .swing-detail-title { display:flex; align-items:baseline; gap:10px; font-weight:850; }
  .swing-detail-sub { color:var(--text-muted); font-size:.7rem; font-weight:500; }
  .swing-volume-card { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:14px; padding:14px; border-bottom:1px solid #263750; background:linear-gradient(110deg,#0f1b2d,#101827); }
  .swing-volume-copy { min-width:0; }
  .swing-volume-lead { display:flex; align-items:center; flex-wrap:wrap; gap:9px; }
  .swing-volume-badge { display:inline-flex; align-items:center; border:1px solid; border-radius:999px; padding:4px 9px; font-size:.72rem; font-weight:850; }
  .swing-volume-green { color:#86efac; border-color:rgba(34,197,94,.36); background:rgba(34,197,94,.13); }
  .swing-volume-yellow { color:#fde68a; border-color:rgba(245,158,11,.38); background:rgba(245,158,11,.13); }
  .swing-volume-gray { color:#cbd5e1; border-color:rgba(148,163,184,.28); background:rgba(148,163,184,.10); }
  .swing-volume-red { color:#fca5a5; border-color:rgba(239,68,68,.38); background:rgba(239,68,68,.13); }
  .swing-volume-comment { margin-top:7px; overflow:hidden; color:#dbe5f3; font-size:.77rem; text-overflow:ellipsis; white-space:nowrap; }
  .swing-volume-stats { display:flex; flex-wrap:wrap; gap:7px 16px; margin-top:10px; color:var(--text-muted); font-size:.68rem; }
  .swing-volume-stats strong { margin-left:4px; color:#e2e8f0; font-size:.76rem; font-variant-numeric:tabular-nums; }
  .swing-week-bars { display:flex; align-items:flex-end; gap:6px; height:76px; padding:3px 2px 0; }
  .swing-week-bar { display:grid; grid-template-rows:54px 14px; align-items:end; justify-items:center; width:20px; color:#718198; font-size:.56rem; }
  .swing-week-stick { width:10px; min-height:3px; border-radius:3px 3px 1px 1px; box-shadow:0 0 10px currentColor; }
  .swing-week-stick.up { color:#22c55e; background:#22c55e; }
  .swing-week-stick.down { color:#ef4444; background:#ef4444; }
  .swing-chart-slot { min-height:440px; padding:12px; }
  .swing-chart { width:100%; height:410px; }
  .swing-chart-legend { display:flex; flex-wrap:wrap; gap:7px 12px; padding:0 4px 8px; color:var(--text-muted); font-size:.68rem; }
  .swing-legend-dot { display:inline-block; width:12px; height:2px; margin-right:5px; vertical-align:middle; }
  .swing-loading { min-height:400px; display:grid; place-items:center; color:var(--text-muted); }
  .swing-chart-error { min-height:400px; display:grid; place-items:center; color:#fca5a5; }
  @media (max-width:720px) {
    .swing-hero { padding:15px; }
    .swing-hero::after { font-size:2.8rem; }
    .swing-control-top, .swing-control { width:100%; }
    .swing-control { justify-content:space-between; }
    .swing-filter-grid { grid-template-columns:1fr; }
    .swing-volume-card { grid-template-columns:1fr; }
    .swing-week-bars { justify-content:flex-start; }
    .swing-chart-slot { padding:5px; }
  }
  @media (max-width:480px) {
    .swing-controls { padding:9px; }
    .swing-adx-range { min-width:70px; width:34vw; }
    .swing-filter-chip { max-width:100%; }
    .swing-sort-row { grid-template-columns:68px minmax(0,1fr) 90px; }
  }
`;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function finite(value) {
  return value != null && Number.isFinite(Number(value));
}

function fixed(value, digits = 1) {
  return finite(value) ? Number(value).toFixed(digits) : "—";
}

function percent(value, digits = 1) {
  return finite(value) ? `${(Number(value) * 100).toFixed(digits)}%` : "—";
}

function signedClass(value) {
  if (!finite(value) || Number(value) === 0) return "";
  return Number(value) > 0 ? "swing-positive" : "swing-negative";
}

function stateBadge(state) {
  return state === "bounced"
    ? '<span class="swing-badge swing-state-bounced">✅ 反発確認済</span>'
    : '<span class="swing-badge swing-state-pulling">⏳ 押し目進行中</span>';
}

function dowBadge(trend) {
  const meta = {
    up: ["上昇", "up"],
    neutral: ["中立", "neutral"],
    down: ["下降", "down"],
    unknown: ["不明", "unknown"],
  }[trend] || ["不明", "unknown"];
  return `<span class="swing-badge swing-dow-${meta[1]}">${meta[0]}</span>`;
}

function volumeMeta(verdict) {
  return VOLUME_VERDICTS[verdict] || VOLUME_VERDICTS.neutral;
}

function volumeIcon(volume) {
  const meta = volumeMeta(volume?.verdict);
  return `<span class="swing-volume-icon" title="${escapeHtml(meta.label)}">${meta.icon}</span>`;
}

function volumeCard(volume) {
  const safeVolume = volume && typeof volume === "object" ? volume : {};
  const meta = volumeMeta(safeVolume.verdict);
  const zones = { high: "高値圏", mid: "中間", low: "安値圏" };
  const zone = zones[safeVolume.price_zone] || "—";
  const bars = Array.isArray(safeVolume.week_bars) ? safeVolume.week_bars.slice(-5) : [];
  return `
    <div class="swing-volume-card">
      <div class="swing-volume-copy">
        <div class="swing-volume-lead"><span class="swing-volume-badge swing-volume-${meta.tone}">${meta.label}</span><span class="swing-detail-sub">日次出来高の評価</span></div>
        <div class="swing-volume-comment" title="${escapeHtml(safeVolume.comment || "")}">${escapeHtml(safeVolume.comment || "評価データなし")}</div>
        <div class="swing-volume-stats">
          <span>当日出来高<strong>${fixed(safeVolume.vol_ratio_today, 1)}倍</strong></span>
          <span>価格位置<strong>${zone} ${percent(safeVolume.zone_pct, 0)}</strong></span>
          <span>1週間<strong class="${signedClass(safeVolume.week_price_chg)}">${percent(safeVolume.week_price_chg)}</strong></span>
        </div>
      </div>
      <div class="swing-week-bars" aria-label="直近5営業日の出来高倍率">
        ${bars.map(bar => {
          const ratio = finite(bar?.vol_ratio) ? Math.max(0, Number(bar.vol_ratio)) : 0;
          const height = Math.max(3, Math.min(ratio, 3) / 3 * 54);
          const dateLabel = /^\d{4}-\d{2}-\d{2}$/.test(bar?.date || "") ? `${bar.date.slice(8)}日` : "—";
          return `<span class="swing-week-bar" title="${escapeHtml(bar?.date || "")} ${fixed(ratio, 1)}倍"><i class="swing-week-stick ${bar?.up === true ? "up" : "down"}" style="height:${height.toFixed(1)}px"></i><small>${dateLabel}</small></span>`;
        }).join("")}
      </div>
    </div>`;
}

function funnelNode(label, value) {
  const display = finite(value) ? Number(value).toLocaleString("ja-JP") : "—";
  return `<div class="swing-funnel-node"><span>${label}</span><strong>${display}</strong></div>`;
}

function rowHtml(pick) {
  const ticker = escapeHtml(pick.ticker);
  const tvUrl = `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(pick.ticker || "")}`;
  return `
    <tr class="swing-row" data-ticker="${ticker}">
      <td><a class="swing-tv" href="${tvUrl}" target="_blank" rel="noopener noreferrer">${ticker} ↗</a></td>
      <td>${stateBadge(pick.state)}</td>
      <td>${volumeIcon(pick.volume)}</td>
      <td>${dowBadge(pick.dow_trend)}</td>
      <td>${finite(pick.touch_days_ago) ? `${Number(pick.touch_days_ago)}日目` : "—"}</td>
      <td>$${fixed(pick.price, 2)}</td>
      <td class="${signedClass(pick.ema20_dist)}">${percent(pick.ema20_dist)}</td>
      <td>${fixed(pick.adx, 1)}</td>
      <td class="${signedClass(pick.rs63)}">${percent(pick.rs63)}</td>
      <td class="${signedClass(pick.rs126)}">${percent(pick.rs126)}</td>
      <td>${percent(pick.atr_pct)}</td>
      <td>${finite(pick.dollar_vol) ? fixed(Number(pick.dollar_vol) / 1e6, 1) : "—"}</td>
      <td>${finite(pick.po_weeks) ? `${Number(pick.po_weeks)}週` : "—"}</td>
    </tr>`;
}

function comparePicks(left, right, key, direction) {
  const column = COLUMNS.find(item => item.key === key);
  const a = column?.kind === "verdict" ? volumeMeta(left.volume?.verdict).weight : left[key];
  const b = column?.kind === "verdict" ? volumeMeta(right.volume?.verdict).weight : right[key];
  const aMissing = a == null || (column?.kind === "number" && !finite(a));
  const bMissing = b == null || (column?.kind === "number" && !finite(b));
  if (aMissing || bMissing) {
    if (aMissing && bMissing) return 0;
    return aMissing ? 1 : -1;
  }
  const result = column?.kind === "number"
    ? Number(a) - Number(b)
    : column?.kind === "verdict"
      ? Number(a) - Number(b)
    : String(a).localeCompare(String(b), "ja");
  return result * direction;
}

export function sortSwingPicks(picks, sorts) {
  const safeSorts = sanitizeSwingPrefs({ sorts, filters: defaultPrefs().filters }).sorts;
  const effective = safeSorts[0].key ? safeSorts.filter(sort => sort.key) : [{ key: "rs126", direction: -1 }];
  return picks.map((pick, index) => ({ pick, index })).sort((left, right) => {
    for (const sort of effective) {
      const result = comparePicks(left.pick, right.pick, sort.key, sort.direction);
      if (result !== 0) return result;
    }
    return left.index - right.index;
  }).map(item => item.pick);
}

function filterGroupHtml(groupKey, group) {
  return `<fieldset class="swing-filter-group" data-filter-group="${groupKey}">
    <div class="swing-filter-head">
      <span class="swing-filter-title">${group.label}</span>
      <span class="swing-filter-actions"><span class="swing-unfiltered" hidden>全件表示中</span><button class="swing-mini" type="button" data-filter-all="${groupKey}">全選択</button><button class="swing-mini" type="button" data-filter-none="${groupKey}">全解除</button></span>
    </div>
    <div class="swing-filter-options">${group.values.map(value => `<label class="swing-filter-chip"><input type="checkbox" data-filter="${groupKey}" value="${value}"><span>${group.labels[value]}</span><span class="swing-option-count" data-count="${groupKey}:${value}">(0)</span></label>`).join("")}</div>
  </fieldset>`;
}

function sortOptions() {
  return `<option value="">なし</option>${COLUMNS.map(column => `<option value="${column.key}">${column.label}</option>`).join("")}`;
}

function lineColor(line) {
  return line.type === "level"
    ? (LEVEL_COLORS[line.label] || "#94a3b8")
    : (LINE_COLORS[line.type] || "#94a3b8");
}

function drawIntradayChart(slot, payload, chartState) {
  chartState.chart?.remove();
  chartState.resizeObserver?.disconnect();
  chartState.chart = null;
  chartState.resizeObserver = null;

  if (!window.LightweightCharts) {
    slot.innerHTML = '<div class="swing-chart-error">チャートライブラリを読み込めませんでした</div>';
    return;
  }
  if (!payload.bars?.length) {
    slot.innerHTML = '<div class="swing-chart-error">15分足データがありません</div>';
    return;
  }

  const labels = [...new Set((payload.annotations?.lines || []).map(line => line.label))];
  slot.innerHTML = `
    <div class="swing-chart"></div>
    <div class="swing-chart-legend">${labels.map(label => {
      const line = payload.annotations.lines.find(item => item.label === label);
      return `<span><i class="swing-legend-dot" style="background:${lineColor(line)}"></i>${escapeHtml(label)}</span>`;
    }).join("")}</div>`;
  const chartElement = slot.querySelector(".swing-chart");
  const chart = window.LightweightCharts.createChart(chartElement, {
    width: chartElement.clientWidth,
    height: 410,
    layout: { background: { color: "#0a1322" }, textColor: "#94a3b8" },
    grid: { vertLines: { color: "#17243a" }, horzLines: { color: "#17243a" } },
    crosshair: { mode: window.LightweightCharts.CrosshairMode.Normal },
    rightPriceScale: { borderColor: "#2b3c55", scaleMargins: { top: 0.08, bottom: 0.2 } },
    timeScale: { borderColor: "#2b3c55", timeVisible: true, secondsVisible: false },
  });
  chartState.chart = chart;

  const candles = chart.addCandlestickSeries({
    upColor: "#22c55e",
    downColor: "#ef4444",
    borderUpColor: "#22c55e",
    borderDownColor: "#ef4444",
    wickUpColor: "#4ade80",
    wickDownColor: "#f87171",
  });
  candles.setData(payload.bars);

  const volume = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "volume" });
  chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
  volume.setData(payload.bars.map(bar => ({
    time: bar.time,
    value: bar.volume || 0,
    color: bar.close >= bar.open ? "rgba(34,197,94,.24)" : "rgba(239,68,68,.24)",
  })));

  for (const line of payload.annotations?.lines || []) {
    const points = line.points || [];
    if (line.type === "level" && points[0] && finite(points[0].price)) {
      candles.createPriceLine({
        price: Number(points[0].price),
        color: lineColor(line),
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: line.label,
      });
    } else if (points.length >= 2) {
      const series = chart.addLineSeries({
        color: lineColor(line),
        lineWidth: line.type === "trendline" || line.type === "neckline" ? 2 : 1,
        priceLineVisible: false,
        lastValueVisible: false,
        title: line.label,
      });
      series.setData(points.slice(0, 2).map(point => ({ time: point.time, value: point.price })));
    }
  }

  const markers = (payload.annotations?.markers || []).map(marker => ({
    time: marker.time,
    position: "aboveBar",
    color: "#facc15",
    shape: "arrowDown",
    text: marker.text,
  }));
  if (markers.length) candles.setMarkers(markers);
  chart.timeScale().fitContent();

  chartState.resizeObserver = new ResizeObserver(() => {
    if (chartElement.clientWidth > 0) chart.applyOptions({ width: chartElement.clientWidth });
  });
  chartState.resizeObserver.observe(chartElement);
}

export async function renderSwingScreener(container) {
  container.innerHTML = '<div class="loading"><div class="spinner"></div><span>押し目候補を集計中...</span></div>';
  let payload;
  try {
    payload = await apiFetch("/api/swing/picks");
  } catch (error) {
    container.innerHTML = `<div class="empty-state">スクリーナーの取得に失敗しました: ${escapeHtml(error.message)}</div>`;
    return;
  }

  const picks = Array.isArray(payload.picks) ? payload.picks : [];
  const funnel = payload.funnel || {};
  const state = {
    ...loadSwingPrefs(),
    activeTicker: null,
    extended: false,
    requestId: 0,
  };
  const chartState = { chart: null, resizeObserver: null };

  container.innerHTML = `
    <style>${STYLE}</style>
    <div class="swing-shell">
      <section class="swing-hero">
        <div class="swing-kicker">Swing Pullback Radar</div>
        <div class="swing-title-row">
          <h2 class="swing-title">押し目スクリーナー</h2>
          <span class="swing-date">基準日 ${escapeHtml(payload.scan_date || "未実行")}</span>
        </div>
        <div class="swing-funnel">
          ${funnelNode("データ十分", funnel.universe)}<span class="swing-funnel-arrow">→</span>
          ${funnelNode("流動性", funnel.liquid)}<span class="swing-funnel-arrow">→</span>
          ${funnelNode("W1 PO", funnel.po)}<span class="swing-funnel-arrow">→</span>
          ${funnelNode("D1 押し目", funnel.dip)}
        </div>
        <div class="swing-note">※ 今週のW1判定は未確定週を含むため、週内に入れ替わることがあります。</div>
      </section>

      <section class="swing-controls" aria-label="スクリーナーフィルタ">
        <div class="swing-control-top">
          <label class="swing-control">
            <input type="checkbox" data-control="adx-enabled">
            <span>ADXで絞る</span>
            <input class="swing-adx-range" data-control="adx-min" type="range" min="15" max="35" aria-label="ADX下限">
            <output class="swing-adx-value"></output>
          </label>
          <a class="swing-guide-link" href="#logic-guide" data-logic-guide>ロジック解説を見る</a>
          <button class="swing-reset" data-reset-prefs type="button">デフォルトに戻す</button>
        </div>
        <div class="swing-filter-grid">${Object.entries(FILTER_GROUPS).map(([key, group]) => filterGroupHtml(key, group)).join("")}</div>
        <div class="swing-sort-panel" aria-label="複数ソート">
          ${[0, 1, 2].map(index => `<label class="swing-sort-row"><span class="swing-sort-label">第${index + 1}ソート</span><select class="swing-select" data-sort-key="${index}">${sortOptions()}</select><select class="swing-select" data-sort-direction="${index}"><option value="-1">降順</option><option value="1">昇順</option></select></label>`).join("")}
        </div>
      </section>

      <section class="swing-results">
        <div class="swing-results-bar">
          <span><strong class="swing-count">0件</strong> を表示</span>
          <span>行を選択すると15分足を表示</span>
        </div>
        <div class="swing-table-wrap">
          <table class="swing-table">
            <thead><tr>${COLUMNS.map(column => `
              <th aria-sort="none"><button type="button" class="swing-sort" data-sort="${column.key}">${column.label}</button></th>
            `).join("")}</tr></thead>
            <tbody></tbody>
          </table>
        </div>
      </section>

      <section class="swing-detail" hidden></section>
    </div>`;

  container.querySelector("[data-logic-guide]").addEventListener("click", event => {
    event.preventDefault();
    document.querySelector('[data-section="logic-guide"]')?.click();
  });

  const body = container.querySelector(".swing-table tbody");
  const detail = container.querySelector(".swing-detail");
  const count = container.querySelector(".swing-count");

  function persistPrefs() {
    saveSwingPrefs(state);
  }

  function syncControls() {
    container.querySelector('[data-control="adx-enabled"]').checked = state.adxEnabled;
    container.querySelector('[data-control="adx-min"]').value = state.adxMin;
    container.querySelector(".swing-adx-value").textContent = state.adxMin;
    for (const [groupKey, group] of Object.entries(FILTER_GROUPS)) {
      const selected = state.filters[groupKey];
      const fieldset = container.querySelector(`[data-filter-group="${groupKey}"]`);
      fieldset.classList.toggle("unfiltered", selected.length === 0);
      fieldset.querySelector(".swing-unfiltered").hidden = selected.length !== 0;
      for (const input of fieldset.querySelectorAll(`[data-filter="${groupKey}"]`)) {
        input.checked = group.values.includes(input.value) && selected.includes(input.value);
      }
    }
    state.sorts.forEach((sort, index) => {
      container.querySelector(`[data-sort-key="${index}"]`).value = sort.key || "";
      container.querySelector(`[data-sort-direction="${index}"]`).value = String(sort.direction);
    });
    const primary = state.sorts[0].key ? state.sorts[0] : { key: "rs126", direction: -1 };
    container.querySelectorAll(".swing-sort").forEach(button => {
      const active = button.dataset.sort === primary.key;
      button.classList.toggle("active", active);
      button.textContent = COLUMNS.find(column => column.key === button.dataset.sort).label + (active ? (primary.direction > 0 ? " ↑" : " ↓") : "");
      button.parentElement.setAttribute("aria-sort", active ? (primary.direction > 0 ? "ascending" : "descending") : "none");
    });
  }

  function updateFacetCounts() {
    for (const [groupKey, group] of Object.entries(FILTER_GROUPS)) {
      const candidates = filterSwingPicks(picks, state, groupKey);
      for (const value of group.values) {
        const matches = candidates.filter(pick => pickGroupValue(pick, groupKey) === value).length;
        container.querySelector(`[data-count="${groupKey}:${value}"]`).textContent = `(${matches.toLocaleString("ja-JP")})`;
      }
    }
  }

  function closeDetail() {
    state.activeTicker = null;
    state.requestId += 1;
    detail.hidden = true;
    detail.innerHTML = "";
    chartState.chart?.remove();
    chartState.resizeObserver?.disconnect();
    chartState.chart = null;
    chartState.resizeObserver = null;
  }

  async function loadIntraday(ticker) {
    const requestId = ++state.requestId;
    const slot = detail.querySelector(".swing-chart-slot");
    slot.innerHTML = '<div class="swing-loading"><div>15分足を取得中...</div></div>';
    try {
      const response = await apiFetch(`/api/swing/intraday/${encodeURIComponent(ticker)}?extended=${state.extended}`);
      if (requestId !== state.requestId) return;
      drawIntradayChart(slot, response, chartState);
    } catch {
      if (requestId !== state.requestId) return;
      slot.innerHTML = '<div class="swing-chart-error">15分足の取得に失敗しました</div>';
    }
  }

  function openDetail(ticker) {
    if (state.activeTicker === ticker) {
      closeDetail();
      renderRows();
      return;
    }
    state.activeTicker = ticker;
    state.extended = false;
    const pick = picks.find(item => item.ticker === ticker);
    detail.hidden = false;
    detail.innerHTML = `
      <div class="swing-detail-head">
        <div class="swing-detail-title">${escapeHtml(ticker)} <span class="swing-detail-sub">15分足・直近5営業日</span></div>
        <label class="swing-control"><input type="checkbox" data-extended> 時間外も表示</label>
      </div>
      ${volumeCard(pick?.volume)}
      <div class="swing-chart-slot"></div>`;
    detail.querySelector("[data-extended]").addEventListener("change", event => {
      state.extended = event.currentTarget.checked;
      loadIntraday(ticker);
    });
    renderRows();
    loadIntraday(ticker);
    detail.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function renderRows() {
    const filtered = sortSwingPicks(filterSwingPicks(picks, state), state.sorts);

    if (state.activeTicker && !filtered.some(pick => pick.ticker === state.activeTicker)) closeDetail();
    syncControls();
    updateFacetCounts();
    count.textContent = `${filtered.length.toLocaleString("ja-JP")}件`;
    body.innerHTML = filtered.length
      ? filtered.map(rowHtml).join("")
      : `<tr><td class="swing-empty" colspan="${COLUMNS.length}">条件に一致する銘柄がありません</td></tr>`;
    body.querySelectorAll(".swing-row").forEach(row => {
      row.classList.toggle("selected", row.dataset.ticker === state.activeTicker);
      row.addEventListener("click", () => openDetail(row.dataset.ticker));
    });
    body.querySelectorAll(".swing-tv").forEach(link => {
      link.addEventListener("click", event => event.stopPropagation());
    });
  }

  container.querySelector('[data-control="adx-enabled"]').addEventListener("change", event => {
    state.adxEnabled = event.currentTarget.checked;
    persistPrefs();
    renderRows();
  });
  container.querySelector('[data-control="adx-min"]').addEventListener("input", event => {
    state.adxMin = Number(event.currentTarget.value);
    persistPrefs();
    renderRows();
  });
  container.querySelectorAll("[data-filter]").forEach(input => {
    input.addEventListener("change", () => {
      const groupKey = input.dataset.filter;
      const group = FILTER_GROUPS[groupKey];
      if (!group || !group.values.includes(input.value)) return;
      state.filters[groupKey] = group.values.filter(value => container.querySelector(`[data-filter="${groupKey}"][value="${value}"]`).checked);
      persistPrefs();
      renderRows();
    });
  });
  container.querySelectorAll("[data-filter-all], [data-filter-none]").forEach(button => {
    button.addEventListener("click", () => {
      const groupKey = button.dataset.filterAll || button.dataset.filterNone;
      const group = FILTER_GROUPS[groupKey];
      if (!group) return;
      state.filters[groupKey] = button.dataset.filterAll ? [...group.values] : [];
      persistPrefs();
      renderRows();
    });
  });
  container.querySelectorAll("[data-sort-key], [data-sort-direction]").forEach(select => {
    select.addEventListener("change", () => {
      const index = Number(select.dataset.sortKey ?? select.dataset.sortDirection);
      if (!Number.isInteger(index) || index < 0 || index > 2) return;
      if (select.dataset.sortKey != null) state.sorts[index].key = select.value || null;
      else state.sorts[index].direction = Number(select.value) === 1 ? 1 : -1;
      persistPrefs();
      renderRows();
    });
  });
  container.querySelectorAll(".swing-sort").forEach(button => {
    button.addEventListener("click", () => {
      const key = button.dataset.sort;
      state.sorts[0].direction = state.sorts[0].key === key ? state.sorts[0].direction * -1 : (key === "ticker" ? 1 : -1);
      state.sorts[0].key = key;
      persistPrefs();
      renderRows();
    });
  });
  container.querySelector("[data-reset-prefs]").addEventListener("click", () => {
    try { globalThis.localStorage?.removeItem(PREFS_KEY); } catch { /* Ignore unavailable storage. */ }
    const reset = defaultPrefs();
    state.adxEnabled = reset.adxEnabled;
    state.adxMin = reset.adxMin;
    state.filters = reset.filters;
    state.sorts = reset.sorts;
    renderRows();
  });

  renderRows();
}
