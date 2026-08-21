"""Layer 1 contract tests.

Each test here pins a rule that a replay slider can violate without anyone
noticing and a relational layer cannot. They are written against the rules in
spec §4.3–4.5 rather than against the current output, so a future refactor that
"still looks right" cannot quietly reintroduce the defect.
"""

from __future__ import annotations

import pytest

from website.backend.services import replay_service
from website.backend.services.round_web_service import (
    VELOCITY_SANITY_CAP_UPS,
    Edge,
    PlayerState,
    Snapshot,
    _contested_guids,
    build_edges,
    build_snapshot,
    derive_velocity,
    find_position_floor,
    nearest_teammate_separation,
    select_life,
)


# Rows are (guid, name, team, class, spawn_ms, death_ms, path, map, id) — the
# shape load_round_tracks returns.
def _track(spawn, death, track_id, path=None):
    return ("G1", "p", "AXIS", "soldier", spawn, death, path or [], "supply", track_id)


class TestSelectLife:
    def test_picks_latest_spawn_not_earliest(self):
        """The defect this whole module exists for.

        `get_player_positions` walks lives in ascending spawn order and breaks on
        the first match, so it returns the EARLIEST overlapping life. The later
        spawn is the more recent state.
        """
        early = _track(1000, 9000, 11)
        late = _track(5000, 9000, 22)
        chosen, alive, conflict = select_life([early, late], 6000)
        assert chosen[8] == 22
        assert alive is True
        assert conflict is True

    def test_ties_break_on_greatest_id(self):
        a = _track(1000, 9000, 11)
        b = _track(1000, 9000, 12)
        chosen, _, _ = select_life([a, b], 5000)
        assert chosen[8] == 12

    def test_death_boundary_is_half_open(self):
        """At t == death_time_ms the zero-health sample is corpse data (§4.3).

        A closed interval would report a dead player as alive for one tick, and
        every edge drawn from that tick would be a relationship with a corpse.
        """
        life = _track(1000, 5000, 11)
        _, alive, _ = select_life([life], 4999)
        assert alive is True
        _, alive_at_death, _ = select_life([life], 5000)
        assert alive_at_death is False

    def test_no_conflict_flag_when_single_candidate(self):
        _, _, conflict = select_life([_track(1000, 9000, 11)], 5000)
        assert conflict is False

    def test_falls_back_to_most_recent_ended_life(self):
        first = _track(0, 1000, 11)
        second = _track(2000, 3000, 22)
        chosen, alive, _ = select_life([first, second], 8000)
        assert chosen[8] == 22
        assert alive is False

    def test_returns_nothing_before_first_spawn(self):
        chosen, alive, conflict = select_life([_track(5000, 9000, 11)], 100)
        assert chosen is None and alive is False and conflict is False


class TestFindPositionFloor:
    PATH = [{"time": 0}, {"time": 1000}, {"time": 2000}]

    @pytest.mark.parametrize("target", [900, 1100, 1999, 2000, 5000])
    def test_never_returns_a_sample_from_the_future(self, target):
        sample, stale, idx = find_position_floor(self.PATH, target)
        assert sample["time"] <= target
        assert stale >= 0
        assert self.PATH[idx] is sample

    def test_disagrees_with_nearest_exactly_where_it_matters(self):
        """Pins the behavioural difference, so nobody "simplifies" one into the other."""
        floor_sample, _, _ = find_position_floor(self.PATH, 900)
        nearest = replay_service._find_position_at_time(self.PATH, 900)  # noqa: SLF001
        assert floor_sample["time"] == 0
        assert nearest["time"] == 1000  # from AFTER the moment asked about

    def test_no_state_before_the_first_sample(self):
        sample, stale, idx = find_position_floor(self.PATH, -1)
        assert sample is None and stale == -1 and idx == -1

    def test_empty_path(self):
        assert find_position_floor([], 100) == (None, -1, -1)


class TestDeriveVelocity:
    def test_derives_from_two_causal_samples(self):
        path = [{"time": 0, "x": 0, "y": 0, "z": 0}, {"time": 1000, "x": 100, "y": 0, "z": 0}]
        vx, vy, vz, dt, reason = derive_velocity(path, 1, None)
        assert reason is None
        assert vx == pytest.approx(100.0)
        assert vy == 0.0 and vz == 0.0 and dt == 1000

    def test_first_sample_of_a_life_has_no_predecessor(self):
        path = [{"time": 0, "x": 0, "y": 0}]
        *_, reason = derive_velocity(path, 0, None)
        assert reason == "no_causal_predecessor"

    def test_gap_larger_than_max_dt_is_refused_not_stretched(self):
        path = [{"time": 0, "x": 0, "y": 0}, {"time": 5000, "x": 10, "y": 0}]
        *_, reason = derive_velocity(path, 1, 400)
        assert reason.startswith("gap_exceeds_max_dt")

    def test_teleport_is_refused_not_clamped(self):
        far = VELOCITY_SANITY_CAP_UPS * 10
        path = [{"time": 0, "x": 0, "y": 0}, {"time": 100, "x": far, "y": 0}]
        vx, _, _, _, reason = derive_velocity(path, 1, None)
        assert vx is None
        assert reason.startswith("exceeds_sanity_cap")

    def test_duplicate_timestamps_with_nothing_earlier(self):
        """Both samples share a time and there is nothing behind them."""
        path = [{"time": 1000, "x": 0, "y": 0}, {"time": 1000, "x": 1, "y": 0}]
        *_, reason = derive_velocity(path, 1, None)
        assert reason == "no_strictly_earlier_sample"

    def test_steps_back_over_duplicate_timestamps(self):
        """9.8% of tracks carry duplicate times (measured 2026-08-21).

        Refusing on the twin directly behind the chosen sample would throw away
        a perfectly derivable velocity for a bookkeeping artefact.
        """
        path = [
            {"time": 0, "x": 0, "y": 0},
            {"time": 1000, "x": 50, "y": 0},
            {"time": 1000, "x": 100, "y": 0},   # duplicate of the one before
        ]
        vx, _, _, dt, reason = derive_velocity(path, 2, None)
        assert reason is None
        assert dt == 1000
        assert vx == pytest.approx(100.0)

    def test_step_back_still_respects_max_dt(self):
        """Stepping over duplicates must not become a licence to bridge a gap."""
        path = [
            {"time": 0, "x": 0, "y": 0},
            {"time": 9000, "x": 50, "y": 0},
            {"time": 9000, "x": 60, "y": 0},
        ]
        *_, reason = derive_velocity(path, 2, 400)
        assert reason.startswith("gap_exceeds_max_dt")

    def test_incomplete_coordinates(self):
        path = [{"time": 0, "x": 0}, {"time": 1000, "y": 1}]
        *_, reason = derive_velocity(path, 1, None)
        assert reason == "incomplete_coordinates"


class TestEdges:
    @staticmethod
    def _state(guid, team, x, alive=True):
        return PlayerState(
            guid=guid, name=guid, team=team, player_class=None,
            x=x, y=0.0, z=0.0, health=100, weapon=None, stance=None,
            speed=None, alive=alive, track_id=1, stale_ms=0, overlap_conflict=False,
        )

    def test_classifies_teammate_and_opponent(self):
        players = {
            "a": self._state("a", "AXIS", 0.0),
            "b": self._state("b", "AXIS", 100.0),
            "c": self._state("c", "ALLIES", 300.0),
        }
        edges = build_edges(players, 0, [])
        kinds = {(e.a_guid, e.b_guid): e.kind for e in edges}
        assert kinds[("a", "b")] == "teammate"
        assert kinds[("a", "c")] == "opponent"
        assert len(edges) == 3

    def test_dead_players_have_no_edges(self):
        players = {
            "a": self._state("a", "AXIS", 0.0),
            "b": self._state("b", "AXIS", 100.0, alive=False),
        }
        assert build_edges(players, 0, []) == []

    def test_separation_is_none_for_last_man_standing(self):
        players = {
            "a": self._state("a", "AXIS", 0.0),
            "c": self._state("c", "ALLIES", 300.0),
        }
        snap = Snapshot(0, players, build_edges(players, 0, []), 0)
        assert nearest_teammate_separation(snap)["a"] is None

    def test_separation_takes_the_nearest_teammate(self):
        players = {
            "a": self._state("a", "AXIS", 0.0),
            "b": self._state("b", "AXIS", 100.0),
            "d": self._state("d", "AXIS", 50.0),
        }
        snap = Snapshot(0, players, build_edges(players, 0, []), 0)
        assert nearest_teammate_separation(snap)["a"] == pytest.approx(50.0)


class TestContestedGuids:
    """The per-attacker filter is what stops the past from knowing the future."""

    ENGAGEMENT = (1000, 9000, "victim",
                  [{"guid": "early", "first_hit_ms": 1200},
                   {"guid": "late", "first_hit_ms": 8000}])

    def test_attacker_who_had_not_hit_yet_does_not_count(self):
        """At t=2000 only `early` has hit. The stored attacker list already
        contains `late`, who joins at 8000 — counting them would leak future
        participation into an earlier moment."""
        assert _contested_guids([self.ENGAGEMENT], 2000) == {"victim"}
        # and with only the future attacker present, nothing is contested yet
        future_only = (1000, 9000, "victim", [{"guid": "late", "first_hit_ms": 8000}])
        assert _contested_guids([future_only], 2000) == set()

    def test_outside_the_engagement_window(self):
        assert _contested_guids([self.ENGAGEMENT], 500) == set()
        assert _contested_guids([self.ENGAGEMENT], 9500) == set()

    def test_attackers_as_json_text(self):
        """The adapter hands JSONB back as text; normalisation must not silently
        drop every engagement edge."""
        raw = (1000, 9000, "victim", '[{"guid": "early", "first_hit_ms": 1200}]')
        assert _contested_guids([raw], 2000) == {"victim"}

    def test_missing_first_hit_is_not_treated_as_zero(self):
        """An attacker with no first-hit provenance is unavailable, not "hit at
        the start of time" (§4.5)."""
        no_provenance = (1000, 9000, "victim", [{"guid": "x", "first_hit_ms": None}])
        assert _contested_guids([no_provenance], 2000) == set()


class TestGapsAreNamedNotSilent:
    """§1: "It never fills a missing active player with silence."

    The first version of build_snapshot `continue`d past every player it could
    not place, so a caller could not tell "was not in this round" from "was
    filtered out by the tolerance I passed". These tests exist to make that
    regression impossible to reintroduce quietly.
    """

    @staticmethod
    def _tracks(path, spawn=0, death=None):
        return {"G1": [("G1", "p", "AXIS", "soldier", spawn, death, path, "supply", 1)]}

    def test_player_with_no_life_yet_is_named(self):
        snap = build_snapshot(self._tracks([{"time": 0, "x": 0, "y": 0, "z": 0}], spawn=5000), 100)
        assert snap.players == {}
        assert snap.gaps == {"G1": "no_life_at_or_before_t"}

    def test_player_with_no_sample_before_t_is_named(self):
        # Life starts at 0 but the first sample only arrives at 9000.
        snap = build_snapshot(self._tracks([{"time": 9000, "x": 0, "y": 0, "z": 0}]), 1000)
        assert snap.players == {}
        assert snap.gaps == {"G1": "no_sample_at_or_before_t"}

    def test_tolerance_exclusion_states_the_staleness(self):
        """The caller's own parameter must not make someone disappear."""
        snap = build_snapshot(
            self._tracks([{"time": 0, "x": 0, "y": 0, "z": 0}]), 5000, max_stale_ms=100
        )
        assert snap.players == {}
        assert snap.gaps["G1"].startswith("exceeds_max_stale_")
        assert "5000" in snap.gaps["G1"]

    def test_placed_player_is_not_also_a_gap(self):
        snap = build_snapshot(self._tracks([{"time": 0, "x": 1.0, "y": 2.0, "z": 3.0}]), 100)
        assert set(snap.players) == {"G1"}
        assert snap.gaps == {}


class TestEdgesNeverInventACoordinate:
    @staticmethod
    def _state(guid, z):
        return PlayerState(
            guid=guid, name=guid, team="AXIS", player_class=None,
            x=0.0, y=0.0, z=z, health=100, weapon=None, stance=None,
            speed=None, alive=True, track_id=1, stale_ms=0, overlap_conflict=False,
        )

    def test_missing_height_yields_no_edge_rather_than_ground_level(self):
        """`z or 0.0` would have put a player with no height on the floor, so two
        people on different storeys came out as neighbours."""
        players = {"a": self._state("a", None), "b": self._state("b", 500.0)}
        assert build_edges(players, 0, []) == []

    def test_zero_height_is_a_real_coordinate_not_a_missing_one(self):
        players = {"a": self._state("a", 0.0), "b": self._state("b", 0.0)}
        assert len(build_edges(players, 0, [])) == 1


def test_edge_dataclass_defaults_to_not_contested():
    assert Edge("a", "b", "teammate", 1.0).recently_contested is False
