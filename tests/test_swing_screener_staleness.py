import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "frontend/js/components/swing-screener.js"


def test_us_session_dates_and_stale_warning(tmp_path):
    module = tmp_path / "swing-screener.mjs"
    source = COMPONENT.read_text(encoding="utf-8")
    module.write_text(source.replace('import { apiFetch } from "../utils/api.js?v=3";', "const apiFetch = null;"), encoding="utf-8")
    script = tmp_path / "verify-staleness.mjs"
    script.write_text(
        f"""
import assert from "node:assert/strict";
import {{ businessDaysBetween, latestUsSessionDate, swingDataWarningHtml }} from {module.as_uri()!r};

// 2026年8月は1日が土曜、2日が日曜。どちらも直前の金曜を返す。
assert.equal(latestUsSessionDate(new Date("2026-08-01T16:00:00Z")), "2026-07-31");
assert.equal(latestUsSessionDate(new Date("2026-08-02T16:00:00Z")), "2026-07-31");

// 夏時間の月曜: 19:00 UTC = 15:00 ET、20:30 UTC = 16:30 ET。
const beforeClose = new Date("2026-08-03T19:00:00Z");
const afterClose = new Date("2026-08-03T20:30:00Z");
assert.equal(latestUsSessionDate(beforeClose), "2026-07-31");
assert.equal(latestUsSessionDate(afterClose), "2026-08-03");

assert.equal(swingDataWarningHtml("2026-08-03", afterClose), "");
const oneDayOld = swingDataWarningHtml("2026-07-31", afterClose);
assert.match(oneDayOld, /データが 1 営業日古いです/);
assert.ok(oneDayOld.includes("最終更新 2026-07-31 / 直近の営業日 2026-08-03"));

assert.equal(businessDaysBetween("2026-07-29", "2026-08-03"), 3);
assert.match(swingDataWarningHtml("2026-07-29", afterClose), /データが 3 営業日古いです/);
""",
        encoding="utf-8",
    )
    subprocess.run(["node", str(script)], check=True, cwd=ROOT)
