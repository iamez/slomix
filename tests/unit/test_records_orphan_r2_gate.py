"""Per-round records must exclude orphan-R2 rows.

An R2 round imported without its R1 (round_status='orphan_r2') keeps the stats
file's raw CUMULATIVE values — R1+R2 combined — so any per-round record built
on it is roughly doubled. The 2026-01-09 erdenberg "damage record" (6,588) and
the 2026-02-06 delivery one before it (7,849 = 4,644 + 3,205) were exactly
this. scripts/repair_inverted_r2_cumulative_rounds.py heals the rows whose
original files still exist and stamps the rest 'orphan_r2'; this gate is what
makes the stamp effective on the records surface.
"""
from __future__ import annotations

import inspect

from website.backend.routers import records_awards


def test_records_gate_excludes_orphan_r2_rounds():
    src = inspect.getsource(records_awards.get_records)
    # Assert the SQL fragment itself, not just the word: the explanatory
    # comment above base_where also says "orphan_r2", so a plain substring
    # check would keep passing after the actual gate clause was deleted.
    assert "OR r.round_status = 'orphan_r2'" in src, (
        "records base_where lost the orphan_r2 exclusion — cumulative R2 rows "
        "would re-enter the record book"
    )
