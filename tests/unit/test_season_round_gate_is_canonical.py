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

WEAK = "round_status = 'orphan_r2'"
CANON = "round_status NOT IN ('completed', 'substitution')"


def test_the_weak_spelling_is_extinct():
    hits = {f: (ROUTERS / f).read_text(encoding="utf-8").count(WEAK) for f in FILES}
    assert hits == {f: 0 for f in FILES}, (
        f"the orphan-only gate is back: {hits} — it admits cancelled rounds "
        "into public numbers (measured -6,614 kills all-time)"
    )


def test_the_canonical_spelling_is_everywhere_it_was():
    # 18 inline sites in seasons, 1 in awards, 1 in the helper — pinned so a
    # new copy-paste of a query without the gate moves this number in review.
    hits = {f: (ROUTERS / f).read_text(encoding="utf-8").count(CANON) for f in FILES}
    assert hits == {"records_seasons.py": 18, "records_awards.py": 1, "api_helpers.py": 1}, hits


def test_the_builder_emits_the_full_trio():
    sql = valid_human_rows_gate("pcs")
    assert "_vr.is_valid IS FALSE" in sql
    assert "_vr.is_bot_round IS TRUE" in sql
    assert "NOT IN ('completed', 'substitution')" in sql
    assert "orphan_r2" not in sql
