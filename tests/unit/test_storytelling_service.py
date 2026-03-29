"""Unit tests for StorytellingService._score_kill and _classify_archetype.

Tests pure scoring logic with mocked DB adapter. No database required.
"""

import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.services.storytelling_service import (
    CARRIER_CHAIN_MULTIPLIER,
    CARRIER_KILL_MULTIPLIER,
    CLASS_WEIGHTS,
    CROSSFIRE_MULTIPLIER,
    LOW_HEALTH_MULTIPLIER,
    LOW_HEALTH_THRESHOLD,
    OUTCOME_GIBBED,
    OUTCOME_REVIVED,
    OUTNUMBERED_MULTIPLIER,
    SOLO_CLUTCH_MULTIPLIER,
    SOLO_CLUTCH_THRESHOLD,
    StorytellingService,
)


# ---------------------------------------------------------------------------
# Helpers — build kill tuples and context dicts for _score_kill
# ---------------------------------------------------------------------------

def _make_kill(
    ko_id=1,
    session_date=date(2026, 3, 28),
    round_number=1,
    round_start_unix=1000000,
    map_name="goldrush",
    killer_guid="AAAA",
    killer_name="Alice",
    victim_guid="BBBB",
    victim_name="Bob",
    outcome="tapped_out",
    kill_time=5000,
):
    """Build a kill tuple matching the DB row order used by _score_kill."""
    return (
        ko_id, session_date, round_number, round_start_unix,
        map_name, killer_guid, killer_name,
        victim_guid, victim_name, outcome, kill_time,
    )


def _empty_context():
    """Return all empty context dicts."""
    return {}, {}, {}, {}, {}, {}, {}


def _service():
    """Create a StorytellingService with a mock DB adapter."""
    return StorytellingService(db=AsyncMock())


# ===========================================================================
# Test class: _score_kill
# ===========================================================================

class TestScoreKillBase:
    """Base kill (no context) should produce total ~1.0."""

    def test_base_kill_total(self):
        svc = _service()
        kill = _make_kill()
        ck, cr, pu, cf, st, vc, cp = _empty_context()
        result = svc._score_kill(kill, ck, cr, pu, cf, st, vc, cp)
        assert result["total_impact"] == pytest.approx(1.0, abs=0.01)

    def test_base_kill_multipliers_all_one(self):
        svc = _service()
        kill = _make_kill()
        ck, cr, pu, cf, st, vc, cp = _empty_context()
        result = svc._score_kill(kill, ck, cr, pu, cf, st, vc, cp)
        assert result["carrier_multiplier"] == 1.0
        assert result["push_multiplier"] == 1.0
        assert result["crossfire_multiplier"] == 1.0
        assert result["spawn_multiplier"] == 1.0
        assert result["outcome_multiplier"] == 1.0
        assert result["class_multiplier"] == 1.0
        assert result["health_multiplier"] == 1.0
        assert result["alive_multiplier"] == 1.0

    def test_base_kill_flags_false(self):
        svc = _service()
        kill = _make_kill()
        ck, cr, pu, cf, st, vc, cp = _empty_context()
        result = svc._score_kill(kill, ck, cr, pu, cf, st, vc, cp)
        assert result["is_carrier_kill"] is False
        assert result["is_during_push"] is False
        assert result["is_crossfire"] is False

    def test_base_kill_output_fields(self):
        svc = _service()
        kill = _make_kill(killer_guid="GUID1", victim_guid="GUID2", map_name="oasis")
        ck, cr, pu, cf, st, vc, cp = _empty_context()
        result = svc._score_kill(kill, ck, cr, pu, cf, st, vc, cp)
        assert result["killer_guid"] == "GUID1"
        assert result["victim_guid"] == "GUID2"
        assert result["map_name"] == "oasis"
        assert result["kill_outcome_id"] == 1


class TestScoreKillCarrier:
    """Carrier kill multipliers."""

    def test_carrier_kill_no_return(self):
        svc = _service()
        kill = _make_kill(killer_guid="A", round_start_unix=100, round_number=1, kill_time=5000)
        carrier_kills = {("A", 100, 1): [5000]}
        carrier_returns = {}  # no return
        _, pu, cf, st, vc, cp = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, carrier_kills, carrier_returns, pu, cf, st, vc, cp)
        assert result["carrier_multiplier"] == CARRIER_KILL_MULTIPLIER
        assert result["total_impact"] == pytest.approx(CARRIER_KILL_MULTIPLIER, abs=0.01)
        assert result["is_carrier_kill"] is True

    def test_carrier_chain_with_return(self):
        svc = _service()
        kill = _make_kill(killer_guid="A", round_start_unix=100, round_number=1, kill_time=5000)
        carrier_kills = {("A", 100, 1): [5000]}
        carrier_returns = {(100, 1): [12000]}  # returned 7s after kill (within 10s)
        _, pu, cf, st, vc, cp = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, carrier_kills, carrier_returns, pu, cf, st, vc, cp)
        assert result["carrier_multiplier"] == CARRIER_CHAIN_MULTIPLIER
        assert result["total_impact"] == pytest.approx(CARRIER_CHAIN_MULTIPLIER, abs=0.01)

    def test_carrier_chain_return_too_late(self):
        """Return after 10s should NOT trigger chain multiplier."""
        svc = _service()
        kill = _make_kill(killer_guid="A", round_start_unix=100, round_number=1, kill_time=5000)
        carrier_kills = {("A", 100, 1): [5000]}
        carrier_returns = {(100, 1): [16000]}  # 11s later — too late
        _, pu, cf, st, vc, cp = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, carrier_kills, carrier_returns, pu, cf, st, vc, cp)
        assert result["carrier_multiplier"] == CARRIER_KILL_MULTIPLIER  # falls back to basic

    def test_carrier_return_before_kill_no_chain(self):
        """Return BEFORE kill should not chain."""
        svc = _service()
        kill = _make_kill(killer_guid="A", round_start_unix=100, round_number=1, kill_time=5000)
        carrier_kills = {("A", 100, 1): [5000]}
        carrier_returns = {(100, 1): [3000]}  # returned before kill
        _, pu, cf, st, vc, cp = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, carrier_kills, carrier_returns, pu, cf, st, vc, cp)
        assert result["carrier_multiplier"] == CARRIER_KILL_MULTIPLIER


class TestScoreKillPush:
    """Push context multiplier with quality gating."""

    def test_push_quality_above_threshold(self):
        svc = _service()
        kill = _make_kill(round_start_unix=100, round_number=1, kill_time=5000)
        pushes = {(100, 1): [(4000, 6000, 0.95, "objective")]}
        ck, cr, cf, st, vc, cp = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, ck, cr, pushes, cf, st, vc, cp)
        # push_mult = 1.0 + min(0.95 * 0.5, 1.0) = 1.0 + 0.475 = 1.475
        assert result["push_multiplier"] == pytest.approx(1.475, abs=0.01)
        assert result["is_during_push"] is True

    def test_push_quality_below_threshold(self):
        """Push quality below 0.9 should NOT trigger bonus."""
        svc = _service()
        kill = _make_kill(round_start_unix=100, round_number=1, kill_time=5000)
        pushes = {(100, 1): [(4000, 6000, 0.80, "objective")]}
        ck, cr, cf, st, vc, cp = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, ck, cr, pushes, cf, st, vc, cp)
        assert result["push_multiplier"] == 1.0
        assert result["is_during_push"] is False

    def test_push_excluded_toward_objective(self):
        """Push toward 'NO' is excluded."""
        svc = _service()
        kill = _make_kill(round_start_unix=100, round_number=1, kill_time=5000)
        pushes = {(100, 1): [(4000, 6000, 0.95, "NO")]}
        ck, cr, cf, st, vc, cp = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, ck, cr, pushes, cf, st, vc, cp)
        assert result["push_multiplier"] == 1.0
        assert result["is_during_push"] is False

    def test_push_kill_within_buffer(self):
        """Kill slightly after push end (within 2s buffer) should still match."""
        svc = _service()
        kill = _make_kill(round_start_unix=100, round_number=1, kill_time=7500)
        pushes = {(100, 1): [(4000, 6000, 0.95, "obj")]}  # push ends at 6000, +2000 buffer
        ck, cr, cf, st, vc, cp = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, ck, cr, pushes, cf, st, vc, cp)
        assert result["push_multiplier"] > 1.0

    def test_push_kill_outside_window(self):
        """Kill well after push+buffer should NOT match."""
        svc = _service()
        kill = _make_kill(round_start_unix=100, round_number=1, kill_time=10000)
        pushes = {(100, 1): [(4000, 6000, 0.95, "obj")]}
        ck, cr, cf, st, vc, cp = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, ck, cr, pushes, cf, st, vc, cp)
        assert result["push_multiplier"] == 1.0

    def test_push_perfect_quality(self):
        """Push quality 1.0 => push_mult = 1.0 + min(1.0*0.5, 1.0) = 1.5."""
        svc = _service()
        kill = _make_kill(round_start_unix=100, round_number=1, kill_time=5000)
        pushes = {(100, 1): [(4000, 6000, 1.0, "obj")]}
        ck, cr, cf, st, vc, cp = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, ck, cr, pushes, cf, st, vc, cp)
        assert result["push_multiplier"] == pytest.approx(1.5, abs=0.01)


class TestScoreKillCrossfire:
    """Crossfire multiplier."""

    def test_crossfire_within_3s(self):
        svc = _service()
        kill = _make_kill(round_start_unix=100, round_number=1, kill_time=5000)
        crossfires = {(100, 1): [4000]}  # crossfire 1s before kill
        ck, cr, pu, st, vc, cp = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, ck, cr, pu, crossfires, st, vc, cp)
        assert result["crossfire_multiplier"] == CROSSFIRE_MULTIPLIER
        assert result["is_crossfire"] is True

    def test_crossfire_outside_window(self):
        svc = _service()
        kill = _make_kill(round_start_unix=100, round_number=1, kill_time=5000)
        crossfires = {(100, 1): [1000]}  # 4s gap — too far
        ck, cr, pu, st, vc, cp = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, ck, cr, pu, crossfires, st, vc, cp)
        assert result["crossfire_multiplier"] == 1.0
        assert result["is_crossfire"] is False


class TestScoreKillOutcome:
    """Outcome multipliers: gibbed, revived, tapped_out."""

    def test_gibbed_outcome(self):
        svc = _service()
        kill = _make_kill(outcome="gibbed")
        ck, cr, pu, cf, st, vc, cp = _empty_context()
        result = svc._score_kill(kill, ck, cr, pu, cf, st, vc, cp)
        assert result["outcome_multiplier"] == OUTCOME_GIBBED
        assert result["total_impact"] == pytest.approx(OUTCOME_GIBBED, abs=0.01)

    def test_revived_outcome(self):
        svc = _service()
        kill = _make_kill(outcome="revived")
        ck, cr, pu, cf, st, vc, cp = _empty_context()
        result = svc._score_kill(kill, ck, cr, pu, cf, st, vc, cp)
        assert result["outcome_multiplier"] == OUTCOME_REVIVED
        assert result["total_impact"] == pytest.approx(OUTCOME_REVIVED, abs=0.01)

    def test_tapped_out_outcome(self):
        svc = _service()
        kill = _make_kill(outcome="tapped_out")
        ck, cr, pu, cf, st, vc, cp = _empty_context()
        result = svc._score_kill(kill, ck, cr, pu, cf, st, vc, cp)
        assert result["outcome_multiplier"] == 1.0

    def test_none_outcome_treated_as_tapped(self):
        svc = _service()
        kill = _make_kill(outcome=None)
        ck, cr, pu, cf, st, vc, cp = _empty_context()
        result = svc._score_kill(kill, ck, cr, pu, cf, st, vc, cp)
        assert result["outcome_multiplier"] == 1.0


class TestScoreKillClassWeight:
    """Target class multiplier from victim_classes context."""

    def test_medic_target(self):
        svc = _service()
        kill = _make_kill(victim_guid="VIC", round_start_unix=100, round_number=1)
        victim_classes = {("VIC", 100, 1): "MEDIC"}
        ck, cr, pu, cf, st, cp = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, ck, cr, pu, cf, st, victim_classes, cp)
        assert result["class_multiplier"] == CLASS_WEIGHTS["MEDIC"]
        assert result["total_impact"] == pytest.approx(1.5, abs=0.01)

    def test_engineer_target(self):
        svc = _service()
        kill = _make_kill(victim_guid="VIC", round_start_unix=100, round_number=1)
        victim_classes = {("VIC", 100, 1): "ENGINEER"}
        ck, cr, pu, cf, st, cp = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, ck, cr, pu, cf, st, victim_classes, cp)
        assert result["class_multiplier"] == CLASS_WEIGHTS["ENGINEER"]

    def test_unknown_class_defaults_to_1(self):
        svc = _service()
        kill = _make_kill(victim_guid="VIC", round_start_unix=100, round_number=1)
        victim_classes = {("VIC", 100, 1): "UNKNOWN_CLASS"}
        ck, cr, pu, cf, st, cp = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, ck, cr, pu, cf, st, victim_classes, cp)
        assert result["class_multiplier"] == 1.0

    def test_missing_class_defaults_to_1(self):
        svc = _service()
        kill = _make_kill(victim_guid="VIC", round_start_unix=100, round_number=1)
        victim_classes = {}  # no class data
        ck, cr, pu, cf, st, cp = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, ck, cr, pu, cf, st, victim_classes, cp)
        assert result["class_multiplier"] == 1.0


class TestScoreKillSoftCap:
    """Soft cap: raw <= 5.0 passes through; above 5.0 => 5.0 + (raw-5.0)*0.25."""

    def test_raw_10_soft_capped(self):
        """raw=10 => 5.0 + (10-5)*0.25 = 5.0 + 1.25 = 6.25"""
        svc = _service()
        # Carrier chain (5.0) * crossfire (1.5) * gibbed (1.3) = 9.75 => above 5.0
        kill = _make_kill(
            killer_guid="A", round_start_unix=100, round_number=1,
            kill_time=5000, outcome="gibbed",
        )
        carrier_kills = {("A", 100, 1): [5000]}
        carrier_returns = {(100, 1): [12000]}
        crossfires = {(100, 1): [5000]}
        pu, st, vc, cp = {}, {}, {}, {}
        result = svc._score_kill(kill, carrier_kills, carrier_returns, pu, crossfires, st, vc, cp)
        # raw = 5.0 * 1.5 * 1.3 = 9.75
        expected = 5.0 + (9.75 - 5.0) * 0.25
        assert result["total_impact"] == pytest.approx(expected, abs=0.02)

    def test_below_cap_passes_through(self):
        """raw=3.0 is below cap, passes through."""
        svc = _service()
        kill = _make_kill(
            killer_guid="A", round_start_unix=100, round_number=1,
            kill_time=5000,
        )
        carrier_kills = {("A", 100, 1): [5000]}
        carrier_returns = {}
        pu, cf, st, vc, cp = {}, {}, {}, {}, {}
        result = svc._score_kill(kill, carrier_kills, carrier_returns, pu, cf, st, vc, cp)
        # raw = 3.0 (carrier kill, no chain) — below cap
        assert result["total_impact"] == pytest.approx(3.0, abs=0.01)

    def test_large_raw_compressed(self):
        """Very large raw should be heavily compressed."""
        svc = _service()
        # Carrier chain (5.0) * crossfire (1.5) * medic (1.5) * gibbed (1.3) = 14.625
        kill = _make_kill(
            killer_guid="A", round_start_unix=100, round_number=1,
            kill_time=5000, outcome="gibbed", victim_guid="VIC",
        )
        carrier_kills = {("A", 100, 1): [5000]}
        carrier_returns = {(100, 1): [12000]}
        crossfires = {(100, 1): [5000]}
        victim_classes = {("VIC", 100, 1): "MEDIC"}
        pu, st, cp = {}, {}, {}
        result = svc._score_kill(kill, carrier_kills, carrier_returns, pu, crossfires, st, victim_classes, cp)
        raw = 5.0 * 1.5 * 1.5 * 1.3
        expected = 5.0 + (raw - 5.0) * 0.25
        assert result["total_impact"] == pytest.approx(expected, abs=0.02)


class TestScoreKillHealth:
    """health_multiplier: kill with low HP => LOW_HEALTH_MULTIPLIER."""

    def test_low_health_multiplier(self):
        svc = _service()
        kill = _make_kill(killer_guid="A", round_start_unix=100, round_number=1, kill_time=5000)
        combat_positions = {
            ("A", 100, 1, 5000): {
                "killer_health": 20,
                "axis_alive": 3,
                "allies_alive": 3,
                "attacker_team": "AXIS",
            }
        }
        ck, cr, pu, cf, st, vc = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, ck, cr, pu, cf, st, vc, combat_positions)
        assert result["health_multiplier"] == LOW_HEALTH_MULTIPLIER  # 1.3
        assert result["total_impact"] == pytest.approx(LOW_HEALTH_MULTIPLIER, abs=0.01)

    def test_full_health_no_multiplier(self):
        svc = _service()
        kill = _make_kill(killer_guid="A", round_start_unix=100, round_number=1, kill_time=5000)
        combat_positions = {
            ("A", 100, 1, 5000): {
                "killer_health": 100,
                "axis_alive": 3,
                "allies_alive": 3,
                "attacker_team": "AXIS",
            }
        }
        ck, cr, pu, cf, st, vc = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, ck, cr, pu, cf, st, vc, combat_positions)
        assert result["health_multiplier"] == 1.0

    def test_health_exactly_at_threshold_no_bonus(self):
        """killer_health == LOW_HEALTH_THRESHOLD (30) is NOT < threshold."""
        svc = _service()
        kill = _make_kill(killer_guid="A", round_start_unix=100, round_number=1, kill_time=5000)
        combat_positions = {
            ("A", 100, 1, 5000): {
                "killer_health": LOW_HEALTH_THRESHOLD,
                "axis_alive": 3,
                "allies_alive": 3,
                "attacker_team": "AXIS",
            }
        }
        ck, cr, pu, cf, st, vc = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, ck, cr, pu, cf, st, vc, combat_positions)
        assert result["health_multiplier"] == 1.0


class TestScoreKillAlive:
    """alive_multiplier: 1v3+ solo clutch, or outnumbered."""

    def test_solo_clutch_1v3(self):
        svc = _service()
        kill = _make_kill(killer_guid="A", round_start_unix=100, round_number=1, kill_time=5000)
        combat_positions = {
            ("A", 100, 1, 5000): {
                "killer_health": 80,
                "axis_alive": 1,
                "allies_alive": 3,
                "attacker_team": "AXIS",
            }
        }
        ck, cr, pu, cf, st, vc = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, ck, cr, pu, cf, st, vc, combat_positions)
        assert result["alive_multiplier"] == SOLO_CLUTCH_MULTIPLIER  # 2.0

    def test_solo_clutch_1v2_below_threshold(self):
        """1v2 is NOT 1v3+, so no solo clutch bonus."""
        svc = _service()
        kill = _make_kill(killer_guid="A", round_start_unix=100, round_number=1, kill_time=5000)
        combat_positions = {
            ("A", 100, 1, 5000): {
                "killer_health": 80,
                "axis_alive": 1,
                "allies_alive": 2,
                "attacker_team": "AXIS",
            }
        }
        ck, cr, pu, cf, st, vc = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, ck, cr, pu, cf, st, vc, combat_positions)
        # 1v2: team_size=3, threshold=max(1, 3//3)=1, enemy-my=2-1=1 >= 1 => outnumbered
        assert result["alive_multiplier"] == OUTNUMBERED_MULTIPLIER

    def test_even_numbers_no_bonus(self):
        """3v3 = even, no bonus."""
        svc = _service()
        kill = _make_kill(killer_guid="A", round_start_unix=100, round_number=1, kill_time=5000)
        combat_positions = {
            ("A", 100, 1, 5000): {
                "killer_health": 80,
                "axis_alive": 3,
                "allies_alive": 3,
                "attacker_team": "AXIS",
            }
        }
        ck, cr, pu, cf, st, vc = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, ck, cr, pu, cf, st, vc, combat_positions)
        assert result["alive_multiplier"] == 1.0

    def test_allies_team_1v3(self):
        """Solo clutch works when attacker_team is ALLIES."""
        svc = _service()
        kill = _make_kill(killer_guid="A", round_start_unix=100, round_number=1, kill_time=5000)
        combat_positions = {
            ("A", 100, 1, 5000): {
                "killer_health": 80,
                "axis_alive": 4,
                "allies_alive": 1,
                "attacker_team": "ALLIES",
            }
        }
        ck, cr, pu, cf, st, vc = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, ck, cr, pu, cf, st, vc, combat_positions)
        assert result["alive_multiplier"] == SOLO_CLUTCH_MULTIPLIER


class TestScoreKillSpawnTiming:
    """Spawn timing bonus adds score to 1.0 base."""

    def test_spawn_timing_bonus(self):
        svc = _service()
        kill = _make_kill(killer_guid="A", round_start_unix=100, round_number=1, kill_time=5000)
        spawn_timings = {
            (100, 1): [("A", 5000, 0.8, 0, 0)]  # guid, kill_time, score, interval, reinf
        }
        ck, cr, pu, cf, vc, cp = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, ck, cr, pu, cf, spawn_timings, vc, cp)
        assert result["spawn_multiplier"] == pytest.approx(1.8, abs=0.01)

    def test_spawn_timing_no_match(self):
        svc = _service()
        kill = _make_kill(killer_guid="A", round_start_unix=100, round_number=1, kill_time=5000)
        spawn_timings = {
            (100, 1): [("OTHER", 5000, 0.8, 0, 0)]
        }
        ck, cr, pu, cf, vc, cp = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, ck, cr, pu, cf, spawn_timings, vc, cp)
        assert result["spawn_multiplier"] == 1.0


class TestScoreKillCombined:
    """Combined multipliers with soft cap applied."""

    def test_carrier_plus_gibbed(self):
        """Carrier (3.0) * gibbed (1.3) = 3.9 (below cap)."""
        svc = _service()
        kill = _make_kill(
            killer_guid="A", round_start_unix=100, round_number=1,
            kill_time=5000, outcome="gibbed",
        )
        carrier_kills = {("A", 100, 1): [5000]}
        cr, pu, cf, st, vc, cp = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, carrier_kills, cr, pu, cf, st, vc, cp)
        assert result["total_impact"] == pytest.approx(3.9, abs=0.01)

    def test_carrier_plus_medic_plus_crossfire(self):
        """Carrier (3.0) * medic (1.5) * crossfire (1.5) = 6.75 => soft-capped."""
        svc = _service()
        kill = _make_kill(
            killer_guid="A", round_start_unix=100, round_number=1,
            kill_time=5000, victim_guid="VIC",
        )
        carrier_kills = {("A", 100, 1): [5000]}
        crossfires = {(100, 1): [5000]}
        victim_classes = {("VIC", 100, 1): "MEDIC"}
        cr, pu, st, cp = {}, {}, {}, {}
        result = svc._score_kill(kill, carrier_kills, cr, pu, crossfires, st, victim_classes, cp)
        raw = 3.0 * 1.5 * 1.5
        expected = 5.0 + (raw - 5.0) * 0.25
        assert result["total_impact"] == pytest.approx(expected, abs=0.02)

    def test_null_killer_name_does_not_crash(self):
        svc = _service()
        kill = _make_kill(killer_name=None, victim_name=None)
        ck, cr, pu, cf, st, vc, cp = _empty_context()
        result = svc._score_kill(kill, ck, cr, pu, cf, st, vc, cp)
        assert result["killer_name"] == ""
        assert result["victim_name"] == ""

    def test_zero_kill_time(self):
        svc = _service()
        kill = _make_kill(kill_time=0)
        ck, cr, pu, cf, st, vc, cp = _empty_context()
        result = svc._score_kill(kill, ck, cr, pu, cf, st, vc, cp)
        assert result["kill_time_ms"] == 0
        assert result["total_impact"] == pytest.approx(1.0, abs=0.01)


class TestScoreKillReinfMultiplier:
    """Reinforcement timing multiplier from spawn_timings extended tuple."""

    def test_reinf_bonus_applied(self):
        """victim_reinf > 75% of spawn interval => 1.2x reinf_mult."""
        svc = _service()
        kill = _make_kill(killer_guid="A", round_start_unix=100, round_number=1, kill_time=5000)
        # Extended tuple: (guid, kill_time, score, enemy_spawn_interval_ms, victim_reinf_s)
        # spawn_interval = 30000ms (30s), reinf_penalty threshold = 0.75 * 30 = 22.5s
        # victim_reinf = 25s > 22.5s => bonus
        spawn_timings = {
            (100, 1): [("A", 5000, 0.5, 30000, 25.0)]
        }
        ck, cr, pu, cf, vc, cp = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, ck, cr, pu, cf, spawn_timings, vc, cp)
        assert result["reinf_multiplier"] == 1.2

    def test_reinf_no_bonus_below_threshold(self):
        """victim_reinf < 75% of spawn interval => no bonus."""
        svc = _service()
        kill = _make_kill(killer_guid="A", round_start_unix=100, round_number=1, kill_time=5000)
        spawn_timings = {
            (100, 1): [("A", 5000, 0.5, 30000, 10.0)]  # 10s < 22.5s
        }
        ck, cr, pu, cf, vc, cp = {}, {}, {}, {}, {}, {}
        result = svc._score_kill(kill, ck, cr, pu, cf, spawn_timings, vc, cp)
        assert result["reinf_multiplier"] == 1.0


# ===========================================================================
# Test class: _classify_archetype
# ===========================================================================

class TestClassifyArchetype:
    """Tests for StorytellingService._classify_archetype static method."""

    def test_pressure_engine_high_kills_dpm(self):
        stats = {
            "pcs_kills": 30, "deaths": 10, "dpm": 120,
            "carrier_kills": 0, "revives_given": 5, "trade_kills": 3,
            "crossfire_kills": 1, "push_kills": 2, "headshot_pct": 0.08,
            "denied_time": 50, "time_dead_pct": 0.3,
        }
        session = {
            "avg_kills": 20, "avg_dpm": 100, "avg_kd": 2.0,
            "avg_trades": 3, "avg_revives": 5, "avg_denied": 50,
            "avg_time_dead_pct": 0.3,
        }
        result = StorytellingService._classify_archetype(stats, session)
        assert result == "pressure_engine"

    def test_medic_anchor_high_revives(self):
        stats = {
            "pcs_kills": 15, "deaths": 10, "dpm": 80,
            "carrier_kills": 0, "revives_given": 30, "trade_kills": 2,
            "crossfire_kills": 0, "push_kills": 1, "headshot_pct": 0.05,
            "denied_time": 30, "time_dead_pct": 0.4,
        }
        session = {
            "avg_kills": 15, "avg_dpm": 80, "avg_kd": 1.5,
            "avg_trades": 2, "avg_revives": 18, "avg_denied": 30,
            "avg_time_dead_pct": 0.4,
        }
        result = StorytellingService._classify_archetype(stats, session)
        assert result == "medic_anchor"

    def test_objective_specialist_carrier_kills(self):
        stats = {
            "pcs_kills": 10, "deaths": 8, "dpm": 60,
            "carrier_kills": 4, "revives_given": 3, "trade_kills": 1,
            "crossfire_kills": 0, "push_kills": 0, "headshot_pct": 0.06,
            "denied_time": 20, "time_dead_pct": 0.5,
        }
        result = StorytellingService._classify_archetype(stats)
        assert result == "objective_specialist"

    def test_objective_specialist_carrier_returns(self):
        stats = {
            "pcs_kills": 10, "deaths": 8, "dpm": 60,
            "carrier_kills": 1, "carrier_returns": 3, "revives_given": 3,
            "trade_kills": 1, "crossfire_kills": 0, "push_kills": 0,
            "headshot_pct": 0.06, "denied_time": 20, "time_dead_pct": 0.5,
        }
        result = StorytellingService._classify_archetype(stats)
        assert result == "objective_specialist"

    def test_zero_kills_zero_deaths_no_crash(self):
        """All zeros: 0 >= 0*1.12 is True so it matches pressure_engine first.
        The important thing is it does not crash (no ZeroDivisionError)."""
        stats = {
            "pcs_kills": 0, "deaths": 0, "dpm": 0,
            "carrier_kills": 0, "revives_given": 0, "trade_kills": 0,
            "crossfire_kills": 0, "push_kills": 0, "headshot_pct": 0,
            "denied_time": 0, "time_dead_pct": 0,
        }
        result = StorytellingService._classify_archetype(stats)
        # Should not crash — 0>=0 passes pressure_engine check
        assert result == "pressure_engine"

    def test_silent_assassin_high_headshot_pct(self):
        stats = {
            "pcs_kills": 25, "deaths": 10, "dpm": 90,
            "carrier_kills": 0, "revives_given": 2, "trade_kills": 2,
            "crossfire_kills": 0, "push_kills": 1, "headshot_pct": 0.15,
            "denied_time": 40, "time_dead_pct": 0.3,
        }
        session = {
            "avg_kills": 25, "avg_dpm": 100, "avg_kd": 2.3,
            "avg_trades": 3, "avg_revives": 5, "avg_denied": 40,
            "avg_time_dead_pct": 0.3,
        }
        result = StorytellingService._classify_archetype(stats, session)
        assert result == "silent_assassin"

    def test_chaos_agent_high_dpm_low_kd(self):
        stats = {
            "pcs_kills": 10, "deaths": 20, "dpm": 100,
            "carrier_kills": 0, "revives_given": 2, "trade_kills": 1,
            "crossfire_kills": 0, "push_kills": 1, "headshot_pct": 0.05,
            "denied_time": 30, "time_dead_pct": 0.5,
        }
        session = {
            "avg_kills": 15, "avg_dpm": 100, "avg_kd": 1.5,
            "avg_trades": 3, "avg_revives": 5, "avg_denied": 30,
            "avg_time_dead_pct": 0.4,
        }
        result = StorytellingService._classify_archetype(stats, session)
        # kd=0.5, avg_kd*0.75=1.125, 0.5 < 1.125 => chaos_agent
        assert result == "chaos_agent"

    def test_no_session_stats_fallback(self):
        """Without session_stats, avg_* defaults to player's own values."""
        stats = {
            "pcs_kills": 10, "deaths": 10, "dpm": 50,
            "carrier_kills": 0, "revives_given": 5, "trade_kills": 2,
            "crossfire_kills": 0, "push_kills": 0, "headshot_pct": 0.05,
            "denied_time": 20, "time_dead_pct": 0.4,
        }
        result = StorytellingService._classify_archetype(stats)
        assert isinstance(result, str)

    def test_missing_keys_use_defaults(self):
        """Missing keys in stats dict should default to 0."""
        stats = {"pcs_kills": 5, "deaths": 5}
        result = StorytellingService._classify_archetype(stats)
        assert isinstance(result, str)
