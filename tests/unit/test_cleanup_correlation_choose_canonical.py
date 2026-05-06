"""Tests for tools/cleanup_correlation_duplicates.py choose_canonical guard.

This is the safety guard that prevented the cleanup from destroying
legitimate best-of-3 (multi-match) days. If the guard ever regresses,
re-running the cleanup tool would silently merge separate matches into
each other and lose data — there's no rollback for that.

Pin the contract here so any future "optimisation" of the guard fails
loud in CI rather than in prod data.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Cleanup tool lives under tools/ which isn't a package; import via path.
TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from cleanup_correlation_duplicates import choose_canonical, merge_flags  # noqa: E402


def _crow(*, id, completeness_pct=0, r1=None, r2=None, **flags):
    """Tiny row builder so tests stay readable."""
    base = {
        "id": id,
        "completeness_pct": completeness_pct,
        "r1_round_id": r1,
        "r2_round_id": r2,
        "summary_round_id": None,
        "r1_lua_teams_id": None,
        "r2_lua_teams_id": None,
        "has_r1_stats": False,
        "has_r2_stats": False,
        "has_r1_lua_teams": False,
        "has_r2_lua_teams": False,
        "has_r1_gametime": False,
        "has_r2_gametime": False,
        "has_r1_endstats": False,
        "has_r2_endstats": False,
        "has_r1_proximity": False,
        "has_r2_proximity": False,
    }
    base.update(flags)
    return base


def test_picks_highest_completeness_wins():
    rows = [
        _crow(id=1, completeness_pct=50, r1=10),
        _crow(id=2, completeness_pct=80, r1=10),
        _crow(id=3, completeness_pct=30, r1=10),
    ]
    chosen = choose_canonical(rows)
    assert chosen is not None
    assert chosen["id"] == 2


def test_tie_break_prefers_smallest_id():
    rows = [
        _crow(id=10, completeness_pct=50, r1=10),
        _crow(id=2, completeness_pct=50, r1=10),
        _crow(id=5, completeness_pct=50, r1=10),
    ]
    assert choose_canonical(rows)["id"] == 2


def test_multi_match_day_returns_none_distinct_r1():
    """Same map twice on same day → distinct r1_round_id → SKIP cluster.

    THIS IS THE LOAD-BEARING GUARD. If it regresses, the cleanup tool
    will silently merge two real matches into one row.
    """
    rows = [
        _crow(id=1, completeness_pct=100, r1=100, r2=101),
        _crow(id=2, completeness_pct=100, r1=200, r2=201),  # different r1!
    ]
    assert choose_canonical(rows) is None


def test_multi_match_day_returns_none_distinct_r2():
    rows = [
        _crow(id=1, completeness_pct=100, r1=None, r2=101),
        _crow(id=2, completeness_pct=100, r1=None, r2=201),  # different r2
    ]
    assert choose_canonical(rows) is None


def test_orphan_only_returns_none():
    """If no row has any round_id, there's nothing to merge into.

    Cleanup must NOT pick the highest-completeness orphan as canonical
    because then the un-orphan rows below would all be deleted.
    """
    rows = [
        _crow(id=1, completeness_pct=10, r1=None, r2=None),
        _crow(id=2, completeness_pct=20, r1=None, r2=None),
    ]
    assert choose_canonical(rows) is None


def test_partial_round_id_still_qualifies():
    """A row with only r2_round_id (lone R2 of a half-recovered match)
    is still a valid canonical candidate."""
    rows = [
        _crow(id=1, completeness_pct=50, r1=None, r2=42),
        _crow(id=2, completeness_pct=10, r1=None, r2=None),  # pure orphan
    ]
    chosen = choose_canonical(rows)
    assert chosen is not None
    assert chosen["id"] == 1


def test_merge_flags_collects_set_flags_from_orphans():
    canonical = _crow(id=1, completeness_pct=50, r1=10, has_r1_stats=True)
    others = [
        _crow(id=2, has_r1_lua_teams=True, has_r1_proximity=True),
        _crow(id=3, has_r2_endstats=True),
    ]
    merged = merge_flags(canonical, others)
    assert merged.get("has_r1_lua_teams") is True
    assert merged.get("has_r1_proximity") is True
    assert merged.get("has_r2_endstats") is True
    # has_r1_stats is already true on canonical → not in merged dict
    assert "has_r1_stats" not in merged


def test_merge_flags_picks_first_non_null_id_when_canonical_is_null():
    canonical = _crow(id=1, r1=10)  # r1_lua_teams_id is None on canonical
    others = [
        _crow(id=2, r1_lua_teams_id=100),
        _crow(id=3, r1_lua_teams_id=200),  # would never be picked
    ]
    merged = merge_flags(canonical, others)
    assert merged.get("r1_lua_teams_id") == 100


def test_merge_flags_does_not_overwrite_existing_id():
    canonical = _crow(id=1, r1=10, r1_lua_teams_id=999)  # already set
    others = [_crow(id=2, r1_lua_teams_id=100)]
    merged = merge_flags(canonical, others)
    assert "r1_lua_teams_id" not in merged  # canonical keeps 999
