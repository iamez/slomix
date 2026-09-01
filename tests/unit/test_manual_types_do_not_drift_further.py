"""⛔ A CHECKER NOBODY RUNS IS A CHECK THAT CANNOT FAIL.

`scripts/check_manual_types_against_openapi.py` was written for #830 to catch
the hand-written SPA types drifting from what the API actually returns. It was
never wired to anything: not CI, not pre-commit, not pre-push, not an npm
script. A repo-wide grep for its name finds three mentions and zero invocations,
so for as long as it existed it reported to nobody.

That is the same defect it was built to detect, one level up. This test is its
caller. It is a ratchet, not a gate: known disagreements are recorded and it fails when
a NEW one appears — or when a recorded one is fixed and its line is left behind.

⭐ Both directions fired within a day of being written. The six entries it was
seeded with were fixed at the source by the parallel session (`7e381f45`, #861)
the moment the checker had a caller, and this test then failed as "stale" —
from a merge with `main` that the branch itself did not contain, because CI runs
a pull request against the merge result. The baseline is empty now, on purpose:
the guard is the point, not the list.

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
    # ⛔ PARSED WITHOUT MERCY. Any diagnostic that leaks onto stdout puts a
    # warning line in front of the JSON, and the honest failure is right here
    # rather than a lenient reader that strips it — a channel that tolerates
    # noise stops being machine-readable one line at a time. Codex on #860.
    return json.loads(out.stdout)


def _schemas_that_left(not_compared) -> list[str]:
    """The rule, as a function, so a test can drive it with inputs the live tree
    does not currently produce.

    ⛔ Asserting it against today's report alone proves nothing: `not_compared`
    equals `KNOWN_NOT_COMPARED` right now, so the assertion holds whether the
    rule works or not. A mutation replacing it with `[]` survived exactly there.
    """
    return sorted(set(not_compared) - set(KNOWN_NOT_COMPARED))


def test_a_schema_leaving_the_comparison_is_named():
    assert _schemas_that_left(["StatsRecords"]) == []
    assert _schemas_that_left(["StatsRecords", "RoundViz"]) == ["RoundViz"]
    assert _schemas_that_left([]) == []


def test_the_import_diagnostic_goes_to_stderr():
    """⛔ THE BRANCH NO CURRENT TREE REACHES.

    Every router imports today, so the diagnostic never fires and a test driving
    the real script cannot tell stdout from stderr for it — a mutation moving
    the print back to stdout survived exactly there.

    Read from the SOURCE instead, with comments stripped and the stripping
    asserted, because the comment above that line explains the fix using the
    same words the check looks for.
    """
    src = SCRIPT.read_text(encoding="utf-8")
    src = "\n".join(ln.split("#")[0] for ln in src.splitlines())
    assert "could not import" in src, "the diagnostic itself is gone"
    line = next(ln for ln in src.splitlines() if "could not import" in ln)
    assert "sys.stderr" in line, (
        f"the import diagnostic writes to stdout, which puts a warning line in "
        f"front of the JSON: {line.strip()}")
    assert "stdout" not in src.replace("sys.stdout", ""), "unexpected stdout use"


def test_the_json_channel_carries_only_json():
    """CONTROL for the channel itself: stdout must parse with nothing removed,
    even though the tool has diagnostics to emit."""
    out = subprocess.run([sys.executable, str(SCRIPT), "--json"],
                         capture_output=True, text=True, cwd=ROOT)
    assert out.stdout.lstrip().startswith("{"), (
        f"stdout does not begin with JSON:\n{out.stdout[:200]}")
    json.loads(out.stdout)


def _recorded() -> set[str]:
    return {ln.strip() for ln in BASELINE.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")}


def _measured(report: dict) -> set[str]:
    return {f"{f['schema']}.{f['field']}: {f['why']}" for f in report["findings"]}


COMPARED_FLOOR = 36

#: Schemas the parser cannot read, BY NAME. `StatsRecords` is declared on the
#: client as `export type StatsRecords = Record<string, RecordEntry[]>` — a type
#: ALIAS, and this parser reads `interface` declarations only. Recorded here so
#: that a schema silently JOINING this list fails the test instead of quietly
#: taking its findings with it.
KNOWN_NOT_COMPARED = {"StatsRecords"}


def test_the_set_of_compared_schemas_does_not_shrink():
    """⛔ A SHRINKING COMPARISON LOOKS EXACTLY LIKE A CLEANER ONE.

    `compared > 20` only rules out the empty case. If a hand-written interface
    is renamed, or turned into a `type X = …` alias — which this parser cannot
    read at all — it silently leaves the comparison and every finding about it
    disappears with it. The count that mattered would fall while the ratchet
    reported peace. Codex on #860.

    ⚠️ Raise this only in a commit that explains what was added, and never to
    make a red run go green.
    """
    report = _report()
    assert report["compared"] >= COMPARED_FLOOR, (
        f"only {report['compared']} schemas compared, down from {COMPARED_FLOOR} "
        f"— a schema left the comparison, so any finding about it vanished "
        f"rather than being fixed. Not compared: {report['not_compared']}")
    # ⛔ AND THE COUNT ALONE IS NOT ENOUGH. If one interface becomes
    # parser-invisible in the same change that makes another comparable, the
    # total stays 36 and this passes while every finding about the removed one
    # disappears. A scalar floor cannot see a swap; the identities can.
    # Codex on #860.
    gone = _schemas_that_left(report["not_compared"])
    assert not gone, (
        f"these schemas left the comparison: {gone}\n"
        f"Every drift finding about them disappeared with them. Fix the parser, "
        f"restore the interface, or record the name in KNOWN_NOT_COMPARED with "
        f"the reason it cannot be read.")


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
