"""Tests for StorytellingService._score_kill — the KIS scoring core.

This is the function that produces every per-kill row in
storytelling_kill_impact. Every Smart Stats user-visible number
(KIS leaderboard, narrative, momentum) ultimately derives from a
sum or aggregation of `total_impact` values produced here.

Until now the function had ZERO unit tests despite carrying the
multiplicative product of 11 multipliers, a soft cap at 5.0,
carrier-chain detection, outnumbered/clutch logic, and 5-vs-4-tuple
backward compat for spawn_timings. A silent change to any of those
would re-shape the leaderboard for every recomputed session.

Pin the contract in machine-checkable form.
"""
from __future__ import annotations

from datetime import date

import pytest

from website.backend.services.storytelling.base import (
    CARRIER_CHAIN_MULTIPLIER,
    CARRIER_KILL_MULTIPLIER,
    CARRIER_RETURN_WINDOW_MS,
    CROSSFIRE_MULTIPLIER,
    LOW_HEALTH_MULTIPLIER,
    OUTCOME_GIBBED,
    OUTCOME_REVIVED,
    OUTNUMBERED_MULTIPLIER,
    SOLO_CLUTCH_MULTIPLIER,
)
from website.backend.services.storytelling.service import StorytellingService


# Build a minimal kill tuple. Schema (per kis.py:150-160):
# (ko_id, session_date, round_number, round_start_unix, map_name,
#  killer_guid, killer_name, victim_guid, victim_name, outcome, kill_time_ms)
def _kill(*, outcome="tapped_out", kill_time=10_000, killer_guid="K", victim_guid="V"):
    return (
        1,
        date(2026, 4, 21),
        1,
        1_700_000_000,
        "supply",
        killer_guid, "killer-name",
        victim_guid, "victim-name",
        outcome, kill_time,
    )


@pytest.fixture
def svc():
    """A bare StorytellingService — the scoring helper doesn't touch self.db."""
    return StorytellingService(db=None)


# ---------------------------------------------------------------------------
# Happy path: no context dicts → all multipliers default to 1.0
# ---------------------------------------------------------------------------


def test_baseline_kill_with_no_context_returns_total_1(svc):
    result = svc._score_kill(
        kill=_kill(),
        carrier_kills={}, carrier_returns={}, pushes={}, crossfires={},
        spawn_timings={}, victim_classes={}, combat_positions={},
    )
    assert result["total_impact"] == 1.0
    assert result["carrier_multiplier"] == 1.0
    assert result["push_multiplier"] == 1.0
    assert result["crossfire_multiplier"] == 1.0
    assert result["outcome_multiplier"] == 1.0
    assert result["health_multiplier"] == 1.0
    assert result["alive_multiplier"] == 1.0
    assert result["reinf_multiplier"] == 1.0


# ---------------------------------------------------------------------------
# Outcome multiplier
# ---------------------------------------------------------------------------


def test_gibbed_kill_applies_gibbed_multiplier(svc):
    result = svc._score_kill(
        kill=_kill(outcome="gibbed"),
        carrier_kills={}, carrier_returns={}, pushes={}, crossfires={},
        spawn_timings={}, victim_classes={}, combat_positions={},
    )
    assert result["outcome_multiplier"] == OUTCOME_GIBBED
    assert result["total_impact"] == OUTCOME_GIBBED


def test_revived_kill_applies_revived_multiplier(svc):
    """Revived kills score LESS than 1.0 — a kill that got medic'd back
    is reduced impact, not amplified."""
    result = svc._score_kill(
        kill=_kill(outcome="revived"),
        carrier_kills={}, carrier_returns={}, pushes={}, crossfires={},
        spawn_timings={}, victim_classes={}, combat_positions={},
    )
    assert result["outcome_multiplier"] == OUTCOME_REVIVED
    assert result["total_impact"] == OUTCOME_REVIVED  # base 1.0 * 0.5


# ---------------------------------------------------------------------------
# Carrier kill: chain vs single
# ---------------------------------------------------------------------------


def test_carrier_kill_with_no_return_uses_kill_multiplier(svc):
    kt = 10_000
    result = svc._score_kill(
        kill=_kill(kill_time=kt),
        carrier_kills={("K", 1_700_000_000, 1): {kt}},
        carrier_returns={},  # no return → not a chain
        pushes={}, crossfires={}, spawn_timings={},
        victim_classes={}, combat_positions={},
    )
    assert result["carrier_multiplier"] == CARRIER_KILL_MULTIPLIER
    assert result["is_carrier_kill"] is True


def test_carrier_kill_with_quick_return_uses_chain_multiplier(svc):
    kt = 10_000
    return_time = kt + 5000  # 5s after kill, well within CARRIER_RETURN_WINDOW_MS=10000
    assert return_time - kt <= CARRIER_RETURN_WINDOW_MS  # sanity
    result = svc._score_kill(
        kill=_kill(kill_time=kt),
        carrier_kills={("K", 1_700_000_000, 1): {kt}},
        carrier_returns={(1_700_000_000, 1): [return_time]},
        pushes={}, crossfires={}, spawn_timings={},
        victim_classes={}, combat_positions={},
    )
    assert result["carrier_multiplier"] == CARRIER_CHAIN_MULTIPLIER
    assert result["is_carrier_kill"] is True


def test_carrier_kill_with_late_return_does_not_chain(svc):
    """Return arrives 11s later — outside CARRIER_RETURN_WINDOW_MS=10000."""
    kt = 10_000
    return_time = kt + CARRIER_RETURN_WINDOW_MS + 1
    result = svc._score_kill(
        kill=_kill(kill_time=kt),
        carrier_kills={("K", 1_700_000_000, 1): {kt}},
        carrier_returns={(1_700_000_000, 1): [return_time]},
        pushes={}, crossfires={}, spawn_timings={},
        victim_classes={}, combat_positions={},
    )
    assert result["carrier_multiplier"] == CARRIER_KILL_MULTIPLIER  # not chain


# ---------------------------------------------------------------------------
# Crossfire timing window
# ---------------------------------------------------------------------------


def test_crossfire_within_3s_window_applies_multiplier(svc):
    kt = 10_000
    result = svc._score_kill(
        kill=_kill(kill_time=kt),
        carrier_kills={}, carrier_returns={}, pushes={},
        crossfires={(1_700_000_000, 1): [kt + 1500]},  # 1.5s away → in window
        spawn_timings={}, victim_classes={}, combat_positions={},
    )
    assert result["crossfire_multiplier"] == CROSSFIRE_MULTIPLIER
    assert result["is_crossfire"] is True


def test_crossfire_outside_3s_window_skipped(svc):
    kt = 10_000
    result = svc._score_kill(
        kill=_kill(kill_time=kt),
        carrier_kills={}, carrier_returns={}, pushes={},
        crossfires={(1_700_000_000, 1): [kt + 4000]},  # 4s away → outside
        spawn_timings={}, victim_classes={}, combat_positions={},
    )
    assert result["crossfire_multiplier"] == 1.0
    assert result["is_crossfire"] is False


# ---------------------------------------------------------------------------
# Class multiplier
# ---------------------------------------------------------------------------


def test_medic_kill_uses_class_weight():
    svc = StorytellingService(db=None)
    result = svc._score_kill(
        kill=_kill(),
        carrier_kills={}, carrier_returns={}, pushes={}, crossfires={},
        spawn_timings={},
        victim_classes={("V", 1_700_000_000, 1): "medic"},
        combat_positions={},
    )
    assert result["class_multiplier"] == 1.5  # CLASS_WEIGHTS["MEDIC"]


def test_unknown_class_falls_back_to_1_0(svc):
    result = svc._score_kill(
        kill=_kill(),
        carrier_kills={}, carrier_returns={}, pushes={}, crossfires={},
        spawn_timings={},
        victim_classes={("V", 1_700_000_000, 1): "alien_class"},
        combat_positions={},
    )
    assert result["class_multiplier"] == 1.0


# ---------------------------------------------------------------------------
# Combat-position multipliers (Oksii adoption)
# ---------------------------------------------------------------------------


def _cp(*, killer_health=100, attacker_team="AXIS", axis_alive=3, allies_alive=3):
    return {
        "killer_health": killer_health,
        "attacker_team": attacker_team,
        "axis_alive": axis_alive,
        "allies_alive": allies_alive,
    }


def test_low_health_kill_applies_health_multiplier(svc):
    kt = 10_000
    result = svc._score_kill(
        kill=_kill(kill_time=kt),
        carrier_kills={}, carrier_returns={}, pushes={}, crossfires={},
        spawn_timings={}, victim_classes={},
        combat_positions={("K", 1_700_000_000, 1, kt): _cp(killer_health=20)},
    )
    assert result["health_multiplier"] == LOW_HEALTH_MULTIPLIER


def test_high_health_kill_no_health_multiplier(svc):
    kt = 10_000
    result = svc._score_kill(
        kill=_kill(kill_time=kt),
        carrier_kills={}, carrier_returns={}, pushes={}, crossfires={},
        spawn_timings={}, victim_classes={},
        combat_positions={("K", 1_700_000_000, 1, kt): _cp(killer_health=80)},
    )
    assert result["health_multiplier"] == 1.0


def test_solo_clutch_one_vs_three_uses_clutch_multiplier(svc):
    kt = 10_000
    cp = _cp(attacker_team="AXIS", axis_alive=1, allies_alive=3)
    result = svc._score_kill(
        kill=_kill(kill_time=kt),
        carrier_kills={}, carrier_returns={}, pushes={}, crossfires={},
        spawn_timings={}, victim_classes={},
        combat_positions={("K", 1_700_000_000, 1, kt): cp},
    )
    assert result["alive_multiplier"] == SOLO_CLUTCH_MULTIPLIER


def test_outnumbered_kill_uses_outnumbered_multiplier(svc):
    """3v6 → enemy 3 ahead, threshold = max(1, 9//3) = 3 → outnumbered."""
    kt = 10_000
    cp = _cp(attacker_team="AXIS", axis_alive=3, allies_alive=6)
    result = svc._score_kill(
        kill=_kill(kill_time=kt),
        carrier_kills={}, carrier_returns={}, pushes={}, crossfires={},
        spawn_timings={}, victim_classes={},
        combat_positions={("K", 1_700_000_000, 1, kt): cp},
    )
    assert result["alive_multiplier"] == OUTNUMBERED_MULTIPLIER


def test_even_team_count_no_alive_multiplier(svc):
    kt = 10_000
    cp = _cp(attacker_team="AXIS", axis_alive=3, allies_alive=3)
    result = svc._score_kill(
        kill=_kill(kill_time=kt),
        carrier_kills={}, carrier_returns={}, pushes={}, crossfires={},
        spawn_timings={}, victim_classes={},
        combat_positions={("K", 1_700_000_000, 1, kt): cp},
    )
    assert result["alive_multiplier"] == 1.0


# ---------------------------------------------------------------------------
# Soft cap at 5.0
# ---------------------------------------------------------------------------


def test_soft_cap_below_5_passes_raw(svc):
    """raw=4.5 → total=4.5 (below cap, no compression)."""
    kt = 10_000
    # Build raw 4.5: gibbed (1.3) * crossfire (1.5) * outnumbered (1.5) * carrier kill (3.0/2 ≈ ...)
    # Easier: gibbed * carrier_kill = 1.3 * 3.0 = 3.9, well below 5.0 cap.
    result = svc._score_kill(
        kill=_kill(outcome="gibbed", kill_time=kt),
        carrier_kills={("K", 1_700_000_000, 1): {kt}},
        carrier_returns={},
        pushes={}, crossfires={}, spawn_timings={},
        victim_classes={}, combat_positions={},
    )
    raw = OUTCOME_GIBBED * CARRIER_KILL_MULTIPLIER
    assert raw < 5.0
    assert result["total_impact"] == round(raw, 2)


def test_soft_cap_above_5_compresses_linearly(svc):
    """raw=10 → total = 5.0 + (10-5) * 0.25 = 6.25.

    The soft cap intentionally compresses extreme values so a single
    god-tier multi-modifier kill doesn't dominate the leaderboard,
    but ordering is preserved (raw=20 still scores higher than raw=10).
    """
    kt = 10_000
    # Build raw ≈ 9.75: gibbed (1.3) * carrier_chain (5.0) * crossfire (1.5) = 9.75
    return_time = kt + 5000  # within window → chain
    result = svc._score_kill(
        kill=_kill(outcome="gibbed", kill_time=kt),
        carrier_kills={("K", 1_700_000_000, 1): {kt}},
        carrier_returns={(1_700_000_000, 1): [return_time]},
        pushes={},
        crossfires={(1_700_000_000, 1): [kt + 100]},
        spawn_timings={}, victim_classes={}, combat_positions={},
    )
    raw = OUTCOME_GIBBED * CARRIER_CHAIN_MULTIPLIER * CROSSFIRE_MULTIPLIER
    expected = 5.0 + (raw - 5.0) * 0.25
    assert raw > 5.0
    assert result["total_impact"] == round(expected, 2)


def test_soft_cap_preserves_ordering(svc):
    """Two kills with raw=8 and raw=12 must still order correctly after compression."""
    kt = 10_000

    # Lower raw: outcome=gibbed * carrier_kill * crossfire = 1.3 * 3.0 * 1.5 = 5.85
    low = svc._score_kill(
        kill=_kill(outcome="gibbed", kill_time=kt),
        carrier_kills={("K", 1_700_000_000, 1): {kt}},
        carrier_returns={}, pushes={},
        crossfires={(1_700_000_000, 1): [kt + 100]},
        spawn_timings={}, victim_classes={}, combat_positions={},
    )
    # Higher raw: outcome=gibbed * carrier_chain * crossfire * medic class = 9.75 * 1.5 ≈ 14.625
    high = svc._score_kill(
        kill=_kill(outcome="gibbed", kill_time=kt),
        carrier_kills={("K", 1_700_000_000, 1): {kt}},
        carrier_returns={(1_700_000_000, 1): [kt + 5000]},
        pushes={},
        crossfires={(1_700_000_000, 1): [kt + 100]},
        spawn_timings={},
        victim_classes={("V", 1_700_000_000, 1): "MEDIC"},
        combat_positions={},
    )
    assert high["total_impact"] > low["total_impact"]


# ---------------------------------------------------------------------------
# Spawn-timings 4-tuple vs 5-tuple backward compat
# ---------------------------------------------------------------------------


def test_spawn_timing_5_tuple_uses_index_4_for_reinf(svc):
    """Production format post-F6: (guid, time, score, _, victim_reinf)."""
    kt = 10_000
    # 5-tuple: index 4 = 25.0 → top reinf tier (mult 1.30, since <= 25.0 in tier table)
    result = svc._score_kill(
        kill=_kill(kill_time=kt),
        carrier_kills={}, carrier_returns={}, pushes={}, crossfires={},
        spawn_timings={(1_700_000_000, 1): [("K", kt, 0.0, "ignored", 25.0)]},
        victim_classes={}, combat_positions={},
    )
    assert result["reinf_multiplier"] == 1.30


def test_spawn_timing_4_tuple_uses_index_3_for_reinf(svc):
    """Backward-compat format: (guid, time, score, victim_reinf)."""
    kt = 10_000
    result = svc._score_kill(
        kill=_kill(kill_time=kt),
        carrier_kills={}, carrier_returns={}, pushes={}, crossfires={},
        spawn_timings={(1_700_000_000, 1): [("K", kt, 0.0, 15.0)]},
        victim_classes={}, combat_positions={},
    )
    assert result["reinf_multiplier"] == 1.10  # 15.0 → ≤15 tier


def test_spawn_timing_other_player_does_not_affect_score(svc):
    """spawn_timings entry for a different killer must NOT be picked up."""
    kt = 10_000
    result = svc._score_kill(
        kill=_kill(killer_guid="K", kill_time=kt),
        carrier_kills={}, carrier_returns={}, pushes={}, crossfires={},
        spawn_timings={(1_700_000_000, 1): [("OTHER", kt, 0.0, 25.0)]},
        victim_classes={}, combat_positions={},
    )
    assert result["reinf_multiplier"] == 1.0  # default — no spawn_timing applied
