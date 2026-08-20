"""A dated working note earns its place in the repo by being cited.

docs/ carried 217 tracked files on 2026-08-20. 121 of them were audits, RCAs,
sprint reports and handoffs that nothing in the codebase referred to — they
described states of the system that no longer existed, and every reader paid
for them before finding that out. They now live in git history and on the
machines that need them (see docs/REPO_BOUNDARY.md).

Prose alone would drift back within a month, so the boundary is a test:

  * docs/research/ and docs/archive/ are gitignored — a file lands there only
    via `git add -f`, which is the deliberate act of promoting a note. This
    test holds that set to what was deliberately promoted.
  * a dated document at docs/ root must be reachable: some comment, test,
    workflow or living document names it. That citation is what makes it an
    answer to "why is this number what it is" rather than sediment.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Promoted on 2026-08-20 because live code cites them. Adding to this list is
# fine — it means something started pointing at the document. Removing an entry
# means retiring the document, which belongs in the same commit as removing the
# citation.
PROMOTED_RESEARCH = {
    "docs/research/DEEP_AUDIT_2026-06-27/WAVE2_MASTER.md",
    "docs/research/DUAL_FRONTEND_DEPLOY_PLAN_2026-06-29.md",
    "docs/research/ENVIRONMENT_IDENTITY_RCA_2026-08-08.md",
    "docs/research/FULL_PROJECT_AUDIT_COVERAGE_2026-07-14.csv",
    "docs/research/MEGA_AUDIT_V6_2026-05-10.md",
    "docs/research/PROXIMITY_IDEAS_2026-07.md",
    "docs/research/WEBSITE_APP_AUDIT_2026-08-05.md",
    # The W5b contract. `stage_scheduler.py` is 3,100 lines behind a one-line
    # docstring and `stage_measurement.py` implements that document's Definition
    # of Done, so both module docstrings now name it — which is what earns these
    # two their place here rather than an exception. S6 is still open; the next
    # agent needs them in the repository, not on one machine.
    "docs/research/W5B_SUSPENDED_SCHEDULER_TAKEOFF_HANDOFF_2026-08-11.md",
    "docs/research/W5B_SEMANTIC_MAPPING_TAKEOFF_HANDOFF_2026-08-10.md",
    "docs/archive/FEATURE_ROADMAP_2026.md",
    "docs/archive/PLANNING_ROOM.md",
    "docs/archive/SYSTEM_ARCHITECTURE.md",
}

# A date in the filename is the signal that a document describes a moment
# rather than the system: RCA_2026-04-21_..., W2_..._2026-07-29.md.
_DATED = re.compile(r"20\d\d-\d\d")

# docs/CHANGELOG.md is a frozen historical log; a mention there is a record of
# what happened, not a live pointer, so it does not keep a document published.
# .gitignore lists the retired documents by path, which would make every one of
# them look cited and quietly turn the check below into a no-op — it caught
# itself doing exactly that on 2026-08-20, before this line existed.
_NOT_A_CITATION = {"docs/CHANGELOG.md", ".gitignore"}

# Named in this test, not in the codebase — excluding it keeps the test from
# citing the very documents it is checking.
_NOT_A_CITATION_SUFFIX = ("tests/unit/test_repo_docs_boundary.py",)


def _tracked() -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(_REPO_ROOT), "ls-files"],
        capture_output=True, text=True, check=True,
    ).stdout
    return out.split("\n")


@pytest.fixture(scope="module")
def tracked() -> list[str]:
    files = [f for f in _tracked() if f]
    assert files, "git ls-files returned nothing — this test would pass vacuously"
    return files


def test_research_and_archive_stay_local(tracked: list[str]):
    """Only deliberately promoted notes may be tracked under these two trees."""
    unexpected = sorted(
        f for f in tracked
        if f.startswith(("docs/research/", "docs/archive/"))
        and f not in PROMOTED_RESEARCH
    )
    assert not unexpected, (
        "these are gitignored trees — a file here was force-added:\n  "
        + "\n  ".join(unexpected)
        + "\n\nIf code now cites it, add it to PROMOTED_RESEARCH in this test "
        "and say what points at it. If not, it belongs on your machine only "
        "(see docs/REPO_BOUNDARY.md)."
    )


def test_dated_root_documents_are_cited(tracked: list[str]):
    """A dated doc at docs/ root must be reachable from something living."""
    dated = [
        f for f in tracked
        if f.startswith("docs/") and f.count("/") == 1 and _DATED.search(f)
    ]
    if not dated:
        pytest.skip("no dated root documents tracked")

    searchable = [
        f for f in tracked
        if f not in _NOT_A_CITATION
        and not f.endswith(_NOT_A_CITATION_SUFFIX)
        and f not in dated
    ]
    names = {Path(f).name: f for f in dated}
    found = subprocess.run(
        ["grep", "-rIhoF"] + [x for n in names for x in ("-e", n)] + searchable,
        cwd=_REPO_ROOT, capture_output=True, text=True,
    ).stdout
    cited = {line.strip() for line in found.split("\n")}

    orphans = sorted(path for name, path in names.items() if name not in cited)
    assert not orphans, (
        "dated documents nothing refers to:\n  " + "\n  ".join(orphans)
        + "\n\nEither cite it from the code it explains, or retire it: move it "
        "to docs/research/ (gitignored) and `git rm --cached` the tracked copy. "
        "It stays in history either way — docs/REPO_BOUNDARY.md has the recipe."
    )
