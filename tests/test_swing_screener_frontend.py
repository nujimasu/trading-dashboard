import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "frontend/js/components/swing-screener.js"


def test_frontend_filter_sort_and_preferences(tmp_path):
    module = tmp_path / "swing-screener.mjs"
    source = COMPONENT.read_text(encoding="utf-8")
    module.write_text(source.replace('import { apiFetch } from "../utils/api.js?v=3";', "const apiFetch = null;"), encoding="utf-8")
    script = tmp_path / "verify.mjs"
    script.write_text(
        f"""
import assert from "node:assert/strict";
import {{ filterSwingPicks, loadSwingPrefs, sanitizeSwingPrefs, sortSwingPicks }} from {module.as_uri()!r};

const defaults = sanitizeSwingPrefs(null);
const picks = [
  {{ ticker: "A", adx: 30, state: "bounced", dow_trend: "up", rs126: 0.1, volume: {{ verdict: "healthy_pullback", price_zone: "high" }} }},
  {{ ticker: "B", adx: 30, state: "pulling", dow_trend: "down", rs126: 0.3, volume: {{ verdict: "bounce_confirmed", price_zone: "low" }} }},
  {{ ticker: "C", adx: 30, state: "bounced", dow_trend: "up", rs126: 0.2, volume: {{ verdict: "bounce_confirmed", price_zone: "mid" }} }},
  {{ ticker: "D", adx: 30, state: "bounced", dow_trend: "up", rs126: 0.4 }},
];

const noVolumeFilter = structuredClone(defaults);
const allVolumeCount = filterSwingPicks(picks, noVolumeFilter).length;
noVolumeFilter.filters.volumeVerdicts = [];
assert.equal(filterSwingPicks(picks, noVolumeFilter).length, allVolumeCount);
noVolumeFilter.filters.volumeVerdicts = ["bounce_confirmed"];
noVolumeFilter.filters.priceZones = ["high"];
assert.equal(filterSwingPicks(picks, noVolumeFilter).some(pick => pick.ticker === "D"), true);

const sorted = sortSwingPicks(picks, [{{ key: "volume", direction: -1 }}, {{ key: "rs126", direction: -1 }}, {{ key: null, direction: -1 }}]);
assert.deepEqual(sorted.slice(0, 2).map(pick => pick.ticker), ["B", "C"]);
const fallback = sortSwingPicks(picks, [{{ key: null, direction: 1 }}, {{ key: "ticker", direction: 1 }}, {{ key: null, direction: -1 }}]);
assert.deepEqual(fallback.map(pick => pick.ticker), ["D", "B", "C", "A"]);

assert.doesNotThrow(() => loadSwingPrefs({{ getItem: () => "not-json" }}));
assert.deepEqual(loadSwingPrefs({{ getItem: () => "not-json" }}), defaults);
assert.deepEqual(sanitizeSwingPrefs({{ sorts: "bad", filters: [] }}), defaults);
""",
        encoding="utf-8",
    )
    subprocess.run(["node", str(script)], check=True, cwd=ROOT)
