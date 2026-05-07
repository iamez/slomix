"""Tests for the graduated reinforcement multiplier in KIS.

`_graduated_reinf_mult` is a pure function that maps the victim's
`victim_reinf_seconds` (how long the victim would have to wait for
their next reinforcement after dying) to a multiplier in [0.70, 1.40].

Per docs/CHANGELOG and the inline ADR comment in base.py, this lookup
is "first tier whose inclusive upper bound is ≥ wait wins" — so r=10.0
maps to the ≤10 tier (1.00), NOT the >10 tier (1.10). Pin every
boundary so the inclusive-upper-bound semantics can't drift.

These constants drive every Smart Stats user-visible number that
includes the REINF multiplier — KIS leaderboard, narrative, momentum.
A silent off-by-one would be a wide-blast-radius regression.
"""
from __future__ import annotations

import pytest

from website.backend.services.storytelling.base import REINF_MULT_TIERS
from website.backend.services.storytelling.kis import _graduated_reinf_mult


# ---------------------------------------------------------------------------
# Inclusive upper-bound semantics — the load-bearing rule
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "wait_seconds, expected",
    [
        # Tier boundaries — each `upper` value must map to that tier's mult,
        # NOT the next tier's. This is the inclusive upper-bound contract.
        (2.0, 0.70),
        (5.0, 0.85),
        (10.0, 1.00),
        (15.0, 1.10),
        (20.0, 1.20),
        (25.0, 1.30),
    ],
)
def test_inclusive_upper_bound_at_each_tier(wait_seconds, expected):
    assert _graduated_reinf_mult(wait_seconds) == expected


@pytest.mark.parametrize(
    "wait_seconds, expected",
    [
        # Just-above values fall into the NEXT tier
        (2.0001, 0.85),
        (5.0001, 1.00),
        (10.0001, 1.10),
        (15.0001, 1.20),
        (20.0001, 1.30),
        (25.0001, 1.40),
    ],
)
def test_just_above_boundary_drops_into_next_tier(wait_seconds, expected):
    assert _graduated_reinf_mult(wait_seconds) == expected


# ---------------------------------------------------------------------------
# Edge cases that pre-date the graduated migration (UTRO inspiration)
# ---------------------------------------------------------------------------


def test_zero_wait_falls_into_shortest_tier():
    """A 0-second wait (shouldn't happen in practice but possible from
    a parser glitch) maps to the shortest tier (lowest mult)."""
    assert _graduated_reinf_mult(0.0) == 0.70


def test_negative_wait_treated_as_zero():
    """Negative inputs are nonsense but must not crash; lowest tier."""
    assert _graduated_reinf_mult(-5.0) == 0.70


def test_none_wait_falls_into_shortest_tier():
    """The compute path can pass None when reinf is unset; treated as 0."""
    assert _graduated_reinf_mult(None) == 0.70


def test_extremely_large_wait_caps_at_top_tier():
    """Anything beyond the highest finite bound goes to the (inf, 1.40) tier."""
    assert _graduated_reinf_mult(60.0) == 1.40
    assert _graduated_reinf_mult(1_000_000.0) == 1.40


def test_int_input_works_same_as_float():
    """Production code passes int sometimes; behaviour must match float."""
    assert _graduated_reinf_mult(10) == 1.00
    assert _graduated_reinf_mult(15) == 1.10


# ---------------------------------------------------------------------------
# Tier table sanity (decoupled from the function under test)
# ---------------------------------------------------------------------------


def test_tier_table_is_monotonically_non_decreasing():
    """Multipliers across tiers must never decrease as wait grows —
    a longer wait should always be at least as rewarding."""
    mults = [m for _upper, m in REINF_MULT_TIERS]
    for prev, curr in zip(mults, mults[1:]):
        assert curr >= prev, f"REINF_MULT_TIERS regresses: {mults}"


def test_tier_table_upper_bounds_strictly_increase():
    """Upper bounds must form a strictly increasing sequence so
    `if r <= upper` short-circuits at the right tier."""
    uppers = [u for u, _m in REINF_MULT_TIERS]
    for prev, curr in zip(uppers, uppers[1:]):
        assert curr > prev, f"REINF_MULT_TIERS bounds not strict: {uppers}"


def test_tier_table_terminates_with_infinite_upper():
    """The final tier must catch every wait — bound must be float('inf')."""
    last_upper, _last_mult = REINF_MULT_TIERS[-1]
    assert last_upper == float("inf")


def test_tier_count_matches_design():
    """7 tiers (UTRO-inspired graduation, see base.py inline doc).

    If you change this, also update docs/CHANGELOG and re-verify the
    reinf_mult column distribution in storytelling_kill_impact —
    historical KIS values silently re-bin into different tiers when
    the table changes shape.
    """
    assert len(REINF_MULT_TIERS) == 7
