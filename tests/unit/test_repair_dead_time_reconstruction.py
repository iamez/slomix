"""scripts/repair_dead_time_reconstruction.py — the arithmetic and the guards.

The repair rewrites 8,721 historical rows, so the parts that decide WHAT it
touches and WHAT it can undo are tested here without a database. The parts
that need one (scope, postcondition) are asserted by the script itself and
roll the transaction back.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.repair_dead_time_reconstruction import (  # noqa: E402
    DEFAULT_CUTOFF,
    REPAIRED_COLUMNS,
    SCOPE_SQL,
    Change,
    _artifacts,
    fingerprint,
    reconstruct,
)


def _change(**kw):
    base = dict(row_id=1, round_date="2025-02-01", round_number=1, player_name="p",
                played_minutes=10.0, old_dead=4.5, old_ratio=45.0,
                new_dead=2.0, new_ratio=20.0)
    base.update(kw)
    return Change(**base)


def test_the_arithmetic_is_playtime_times_one_minus_alive():
    dead, ratio = reconstruct(600, 80.0)
    assert dead == pytest.approx(2.0)
    assert ratio == pytest.approx(20.0)


def test_the_ratio_is_the_complement_of_alive_not_a_second_derivation():
    """100 - alive% and dead/played x 100 are the same number in exact
    arithmetic and drift apart in floating point. Deriving the ratio the second
    way would let a row's two dead-time fields disagree by rounding -- which is
    how `pcs_time_dead_inconsistent_with_ratio` gets something to report."""
    # These inputs are chosen because the two derivations DISAGREE on them.
    # The first draft of this test used (457, 63.7) and friends, where the
    # rounding happens to absorb the difference -- and a mutation that derived
    # the ratio from the minutes passed it. A fixture cannot fail on a value it
    # does not contain.
    for tps, tpp, expected in ((61, 63.7, 36.3), (75, 0.5, 99.5), (75, 78.9, 21.1)):
        dead, ratio = reconstruct(tps, tpp)
        assert ratio == expected, "the ratio IS the complement of alive%"
        back_derived = round(dead / (tps / 60.0) * 100.0, 4)
        assert back_derived != expected, (
            f"tps={tps} tpp={tpp} no longer distinguishes the two derivations; "
            f"pick another input rather than weakening the assertion")
        assert abs(back_derived - expected) < 0.01


def test_a_full_alive_round_reconstructs_to_zero_dead_time():
    assert reconstruct(600, 100.0) == (0.0, 0.0)


def test_the_reconstruction_can_never_exceed_the_round():
    """The invariant 80 stored rows break today, held by construction rather
    than by a clamp: alive% is non-negative, so dead <= played always."""
    for tpp in (0.1, 25.0, 50.0, 99.9):
        dead, _ = reconstruct(900, tpp)
        assert dead <= 900 / 60.0 + 1e-9


def test_the_repair_names_exactly_the_columns_it_may_touch():
    """A repair that can grow its own blast radius silently is not a repair."""
    assert REPAIRED_COLUMNS == (
        "time_dead_minutes", "time_dead_ratio",
        "time_dead_minutes_original", "time_dead_reconstructed")


def test_the_scope_excludes_everything_it_must():
    assert "pcs.round_date < %(cutoff)s" in SCOPE_SQL          # post-fix rows
    assert "pcs.time_played_percent > 0" in SCOPE_SQL          # no input, no repair
    assert "pcs.time_dead_reconstructed IS NULL" in SCOPE_SQL  # idempotent
    assert "pcs.round_number IN (1, 2)" in SCOPE_SQL           # never R0
    assert "rr.is_valid IS FALSE" in SCOPE_SQL and "orphan_r2" in SCOPE_SQL


def test_the_cutoff_is_the_day_the_fixed_lua_took_over():
    assert DEFAULT_CUTOFF == "2026-03-24"


def test_the_repair_statement_refuses_a_row_that_was_already_repaired():
    _, repair = _artifacts([_change()], "S")
    stmt = next(s for s in repair if s.startswith("UPDATE"))
    assert "time_dead_reconstructed IS NULL" in stmt, (
        "without this guard a second run would overwrite "
        "time_dead_minutes_original with the reconstruction itself, and the "
        "original would be gone")
    assert "time_dead_minutes_original = 4.5" in stmt


def test_the_rollback_restores_both_values_and_clears_the_stamp():
    rollback, _ = _artifacts([_change()], "S")
    stmt = next(s for s in rollback if s.startswith("UPDATE"))
    assert "time_dead_minutes = 4.5" in stmt and "time_dead_ratio = 45.0" in stmt
    assert "time_dead_minutes_original = NULL" in stmt
    assert "time_dead_reconstructed = NULL" in stmt
    assert "time_dead_reconstructed IS TRUE" in stmt, (
        "the rollback must only undo rows THIS repair stamped")


def test_both_artifacts_are_wrapped_in_one_transaction():
    for statements in _artifacts([_change(), _change(row_id=2)], "S"):
        assert statements[1] == "BEGIN;" and statements[-1] == "COMMIT;"


def test_was_impossible_sees_both_shapes_of_the_defect():
    assert _change(old_dead=12.0, played_minutes=10.0).was_impossible
    assert _change(old_dead=1.0, old_ratio=3690.8).was_impossible
    assert not _change(old_dead=4.5, played_minutes=10.0, old_ratio=45.0).was_impossible


def test_the_fingerprint_moves_when_any_value_moves():
    a = [_change(), _change(row_id=2)]
    assert fingerprint(a) == fingerprint(list(reversed(a))), "order must not matter"
    assert fingerprint(a) != fingerprint([_change(new_dead=2.01), _change(row_id=2)])
    assert fingerprint(a) != fingerprint([_change(old_dead=4.6), _change(row_id=2)])
