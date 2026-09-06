"""The plan may not quote an endpoint gap that disagrees with the file.

⛔⛔ WHY THIS EXISTS. On 2026-09-06 `docs/PLAN.md` stated the endpoint gap
twice — as **3** in one table and as **16** in another — while
`tests/data/endpoint_gap.txt` listed **13**. Neither number had been counted;
each was written when it was true and then left behind by the work. A plan
that contradicts itself is worse than one that is merely stale: a reader who
spots only one table cannot tell they are holding the wrong half.

⭐ The fix that lasts is not correcting the numbers — it is making the
document unable to disagree with the measurement. The gap file is the
arbiter; the plan quotes it or the build fails.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GAP_FILE = REPO_ROOT / "tests" / "data" / "endpoint_gap.txt"
PLAN = REPO_ROOT / "docs" / "PLAN.md"

#: Matches a markdown table cell like `| endpoint gap (H1) | **13** — ...`
_GAP_CLAIM = re.compile(r"^\|\s*endpoint gap[^|]*\|\s*(?:⛔\s*)?\*\*(\d+)\*\*", re.MULTILINE)


def _measured_gap() -> int:
    lines = GAP_FILE.read_text(encoding="utf-8").splitlines()
    return len([ln for ln in lines if ln.strip() and not ln.lstrip().startswith("#")])


def test_every_gap_number_in_the_plan_matches_the_file():
    claims = [(int(m.group(1)), m.start()) for m in _GAP_CLAIM.finditer(PLAN.read_text(encoding="utf-8"))]
    assert claims, "no endpoint-gap row found in PLAN.md — did the table format change?"

    measured = _measured_gap()
    wrong = [n for n, _ in claims if n != measured]
    assert not wrong, (
        f"PLAN.md claims endpoint gap {wrong}, but tests/data/endpoint_gap.txt lists "
        f"{measured}. Count the file, do not recall the number:\n"
        f"  grep -vcE '^\\s*(#|$)' tests/data/endpoint_gap.txt"
    )


def test_the_plan_does_not_state_the_gap_twice_with_different_numbers():
    """⛔ The sharper half. A single stale number is a stale document; two
    numbers that disagree is a document that cannot be read at all."""
    claims = {int(m.group(1)) for m in _GAP_CLAIM.finditer(PLAN.read_text(encoding="utf-8"))}
    assert len(claims) <= 1, f"PLAN.md states the endpoint gap as {sorted(claims)} in different places"
