"""⛔ A CHECKER NOBODY RUNS IS A CHECK THAT CANNOT FAIL.

`scripts/check_manual_types_against_openapi.py` was written for #830 to catch
the hand-written SPA types drifting from what the API actually returns. It was
never wired to anything: not CI, not pre-commit, not pre-push, not an npm
script. A repo-wide grep for its name finds three mentions and zero invocations,
so for as long as it existed it reported to nobody.

That is the same defect it was built to detect, one level up. This test is its
caller. It is a ratchet, not a gate: the six disagreements that exist today are
recorded, and it fails when a NEW one appears — or when a recorded one is fixed
and its line is left behind.

⚠️ It reads the checker's `--json` output, not its prose. Grepping sentences is
how a guard ends up agreeing with the comment that explains the code.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check_manual_types_against_openapi.py"
BASELINE = ROOT / "tests/data/manual_type_drift.txt"


def _report() -> dict:
    out = subprocess.run([sys.executable, str(SCRIPT), "--json"],
                         capture_output=True, text=True, cwd=ROOT)
    assert out.stdout.strip(), f"checker produced no output:\n{out.stderr}"
    return json.loads(out.stdout)


def _recorded() -> set[str]:
    return {ln.strip() for ln in BASELINE.read_text().splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")}


def _measured(report: dict) -> set[str]:
    return {f"{f['schema']}.{f['field']}: {f['why']}" for f in report["findings"]}


def test_the_checker_actually_compared_something():
    """⛔ FIRST, AND THE WHOLE REASON THIS FILE EXISTS.

    Zero comparisons and zero disagreements have the same shape. The script's
    own history records three separate occasions where it reported agreement
    while comparing nothing, so the count travels in the JSON and is asserted
    before anything is concluded from an empty finding list.
    """
    report = _report()
    assert report["compared"] > 20, (
        f"only {report['compared']} schemas compared — an empty comparison is "
        f"not a clean one")


def test_no_new_disagreement_between_the_hand_written_types_and_the_api():
    new = sorted(_measured(_report()) - _recorded())
    assert not new, (
        "the hand-written SPA types no longer describe what the API returns:\n  "
        + "\n  ".join(new)
        + "\n\nFix types.ts, or record the line in tests/data/manual_type_drift.txt "
          "with the reason it stands.")


def test_a_fixed_disagreement_does_not_stay_recorded():
    stale = sorted(_recorded() - _measured(_report()))
    assert not stale, (
        "these are recorded as known drift but the checker no longer reports "
        "them — delete their lines from tests/data/manual_type_drift.txt in the "
        "commit that fixed them:\n  " + "\n  ".join(stale))
