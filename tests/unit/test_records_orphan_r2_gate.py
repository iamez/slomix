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
from pathlib import Path

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


def test_match_records_gate_lives_in_the_view():
    """The six per-match record categories no longer spell the gate out — they
    read player_match_stats (migration 078). The gate must therefore exist in
    the view, or moving the query there would have quietly dropped it.
    """
    src = inspect.getsource(records_awards.get_records)
    assert "player_match_stats" in src, (
        "match records stopped using the view — check where their gate went"
    )

    migration = (
        Path(__file__).resolve().parents[2]
        / "migrations"
        / "078_player_match_stats_view.sql"
    ).read_text(encoding="utf-8")
    assert "r.round_status IS DISTINCT FROM 'orphan_r2'" in migration, (
        "player_match_stats lost the orphan_r2 exclusion — cumulative R2 rows "
        "would re-enter the match record book"
    )
    assert "r.is_valid IS DISTINCT FROM FALSE" in migration, (
        "player_match_stats lost the is_valid gate — bot rounds would re-enter"
    )
