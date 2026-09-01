"""The season/award surfaces speak the canonical round gate — everywhere.

The weak spelling (`is_valid IS FALSE OR round_status = 'orphan_r2'`)
excluded only orphans, so every OTHER uncounted status (cancelled among
them) flowed into the public all-time numbers: measured 118,416 -> 111,802
kills (-6,614, 5.6%) under the canonical trio+bot gate — found by the
sister session on 2026-09-01 and reproduced here by a second path before a
line changed. The spelling lived inline at twenty sites across three
files, which is the "number on N places" failure: this test pins that the
weak spelling is GONE and the canonical one is everywhere it must be, and
exercises the one real builder behaviourally.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from website.backend.routers.api_helpers import valid_human_rows_gate  # noqa: E402

ROUTERS = REPO / "website" / "backend" / "routers"
FILES = ["records_seasons.py", "records_awards.py", "api_helpers.py"]

# BOTH weak spellings — Copilot on #865 found the second one alive in
# session_query (`COALESCE(round_status, '') <> 'orphan_r2'`) precisely
# because the first version of this test only knew the first spelling:
# a guard that names one spelling of a semantics invites the others.
WEAK_SPELLINGS = ("round_status = 'orphan_r2'", "<> 'orphan_r2'")
CANON = "round_status NOT IN ('completed', 'substitution')"
CANON_POSITIVE = "(round_status IN ('completed', 'substitution') OR round_status IS NULL)"


def test_the_weak_spellings_are_extinct():
    hits = {f: sum((ROUTERS / f).read_text(encoding="utf-8").count(w) for w in WEAK_SPELLINGS) for f in FILES}
    assert hits == {f: 0 for f in FILES}, (
        f"an orphan-only gate is back: {hits} — it admits cancelled rounds "
        "into public numbers (measured -6,614 kills all-time)"
    )


def test_the_canonical_spelling_is_everywhere_it_was():
    # 18 inline sites in seasons, 1 in awards, 1 in the helper — pinned so a
    # new copy-paste of a query without the gate moves this number in review.
    text = {f: (ROUTERS / f).read_text(encoding="utf-8") for f in FILES}
    hits = {f: text[f].count(CANON) for f in FILES}
    positive = {f: text[f].count(CANON_POSITIVE) for f in FILES}
    assert hits == {"records_seasons.py": 18, "records_awards.py": 1, "api_helpers.py": 1}, hits
    # Two positive gates in seasons: the pre-existing round_status_clause
    # builder (:150) and session_query — the second spelling Copilot found,
    # now canonical too.
    assert positive == {"records_seasons.py": 2, "records_awards.py": 0, "api_helpers.py": 0}, positive


def test_the_builder_emits_the_full_trio():
    sql = valid_human_rows_gate("pcs")
    assert "_vr.is_valid IS FALSE" in sql
    assert "_vr.is_bot_round IS TRUE" in sql
    assert "NOT IN ('completed', 'substitution')" in sql
    assert "orphan_r2" not in sql
