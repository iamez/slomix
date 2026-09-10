"""A control that cannot fail is decoration. This is the test that proves it can.

W6 compares the offline tracer against the engine segment by segment. The whole
verdict rests on the capture being sound, and the way we know it is sound is two
controls whose answer is known before the engine is asked: DOWN traces 10,000
units down from a point a player occupied — they were standing on something, so
it must block — and TINY traces one unit sideways inside the space they already
filled, so it must be clear.

⛔ The first version checked only that the two SIDES AGREED. Two sides that agree
DOWN is clear is precisely the breakage a control exists to catch, and an
agreement test passes it. Worse, it computed an `expected` value from the
measured fraction — so the expectation was derived from the observation — and
then deleted the variable without ever comparing. Codacy reported an unused
local (F841); the defect underneath was a check that could not fail.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
COMPARE = ROOT / "scripts" / "compare_w6_engine_vs_offline.py"

FIXTURE_HEADER = (
    "# w6 trace fixture map=test\n"
    "# idx kind ax ay az bx by bz offline_status offline_startsolid\n"
)


def _fixture(down: str, tiny: str) -> str:
    return FIXTURE_HEADER + (
        "0 blocked 0 0 0 100 0 0 blocked 0\n"
        "1 clear 0 0 0 100 0 0 clear 0\n"
        f"2 control_down 0 0 56 0 0 -9944 {down} 0\n"
        f"3 control_tiny 0 0 56 1 0 56 {tiny} 0\n"
    )


def _capture(down_frac: str, tiny_frac: str) -> str:
    return (
        "# us_per_trace=11 batches=1\n"
        "0 0.5 0 0 1022 0 1\n"
        "1 1.0 0 0 1023 0 0\n"
        f"2 {down_frac} 0 0 1022 0 1\n"
        f"3 {tiny_frac} 0 0 1023 0 0\n"
    )


def run_compare(tmp_path: Path, fixture: str, capture: str):
    fix = tmp_path / "fix.txt"
    cap = tmp_path / "cap.txt"
    fix.write_text(fixture)
    cap.write_text(capture)
    return subprocess.run(
        [sys.executable, str(COMPARE), "--fixture", str(fix), "--capture", str(cap)],
        capture_output=True, text=True,
    )


def test_sound_controls_pass(tmp_path: Path) -> None:
    result = run_compare(tmp_path, _fixture("blocked", "clear"), _capture("0.5", "1.0"))
    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize("down,tiny,down_frac,tiny_frac,why", [
    ("clear", "clear", "1.0", "1.0",
     "⭐ both sides agree DOWN is clear — the exact case an agreement test passes"),
    ("blocked", "blocked", "0.5", "0.5",
     "both sides agree TINY is blocked"),
    ("blocked", "clear", "1.0", "1.0",
     "engine disagrees with the design on DOWN, offline is right"),
    ("clear", "clear", "0.5", "1.0",
     "offline disagrees with the design on DOWN, engine is right"),
])
def test_a_wrong_control_fails_the_run(
    tmp_path: Path, down: str, tiny: str, down_frac: str, tiny_frac: str, why: str
) -> None:
    """Each side is checked against the control's DESIGN, never against the
    other side. Otherwise a shared error reads as a clean run."""
    result = run_compare(tmp_path, _fixture(down, tiny), _capture(down_frac, tiny_frac))
    assert result.returncode == 1, f"{why}\n{result.stdout}"
    assert "must be" in result.stdout


def test_the_failure_names_the_control_and_the_expected_answer(tmp_path: Path) -> None:
    result = run_compare(tmp_path, _fixture("clear", "clear"), _capture("1.0", "1.0"))
    assert "control_down" in result.stdout
    assert "must be blocked" in result.stdout


def test_an_expectation_exists_for_every_control_kind() -> None:
    """A control kind the comparator does not know about would be silently
    treated as an ordinary segment — measured, never enforced."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import importlib.util

    spec = importlib.util.spec_from_file_location("cmp_w6", COMPARE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    builder = (ROOT / "scripts" / "build_w6_trace_fixtures.py").read_text()
    written = {
        line.split('add("')[1].split('"')[0]
        for line in builder.splitlines()
        if 'writer.add("control' in line
    }
    assert written, "the builder writes no controls"
    assert written <= set(module.CONTROL_EXPECTATIONS), (
        f"builder writes {written - set(module.CONTROL_EXPECTATIONS)}, "
        f"which the comparator would not enforce"
    )


# --- a truncated capture must not report a clean rate over the survivors ----


def test_a_truncated_capture_fails_the_run(tmp_path: Path) -> None:
    """⭐ The controls are written LAST so a truncation loses them — which made
    the one thing designed to catch a broken capture the first casualty of one.

    Missing rows were only printed, and they drop out of the denominator, so the
    run reported 100% agreement over whatever survived and exited 0.
    """
    capture = "\n".join(_capture("0.5", "1.0").splitlines()[:3]) + "\n"
    result = run_compare(tmp_path, _fixture("blocked", "clear"), capture)
    assert result.returncode == 1, result.stdout
    assert "manjka" in result.stdout
    assert "control_down" in result.stdout, "the report must name what went missing"


def test_an_unexpected_extra_row_fails_the_run(tmp_path: Path) -> None:
    """A capture carrying rows the fixture never asked for is not the capture we
    asked for, whatever the rows say."""
    capture = _capture("0.5", "1.0") + "99 1.0 0 0 1023 0 0\n"
    result = run_compare(tmp_path, _fixture("blocked", "clear"), capture)
    assert result.returncode == 1, result.stdout


def test_a_complete_capture_still_passes(tmp_path: Path) -> None:
    """The half that keeps the guard usable."""
    result = run_compare(tmp_path, _fixture("blocked", "clear"), _capture("0.5", "1.0"))
    assert result.returncode == 0, result.stdout


# --- presence, not only value ----------------------------------------------


def test_a_run_with_no_controls_has_no_falsifier_and_fails(tmp_path: Path) -> None:
    """⭐ Both sides enforce what a control must ANSWER. Nothing required one to
    BE THERE — so a fixture built from a map with no recorded tracks produced a
    file that looked complete, agreed with itself perfectly, and proved nothing.
    """
    fixture = FIXTURE_HEADER + (
        "0 blocked 0 0 0 100 0 0 blocked 0\n"
        "1 clear 0 0 0 100 0 0 clear 0\n"
    )
    capture = "# us_per_trace=11\n0 0.5 0 0 1022 0 1\n1 1.0 0 0 1023 0 0\n"
    result = run_compare(tmp_path, fixture, capture)
    assert result.returncode == 1, result.stdout
    assert "no falsifier" in result.stdout
    for kind in ("control_down", "control_tiny"):
        assert kind in result.stdout, "the report must name which control is absent"


def test_one_control_present_is_still_not_enough(tmp_path: Path) -> None:
    """DOWN alone cannot show the probe reports `clear` correctly, and TINY
    alone cannot show it reports `blocked`. Both or neither."""
    fixture = FIXTURE_HEADER + "2 control_down 0 0 56 0 0 -9944 blocked 0\n"
    capture = "# us_per_trace=11\n2 0.5 0 0 1022 0 1\n"
    result = run_compare(tmp_path, fixture, capture)
    assert result.returncode == 1, result.stdout
    assert "control_tiny" in result.stdout
