"""Layer 1 contract tests.

Each test here pins a rule that a replay slider can violate without anyone
noticing and a relational layer cannot. They are written against the rules in
spec §4.3–4.5 rather than against the current output, so a future refactor that
"still looks right" cannot quietly reintroduce the defect.
"""

from __future__ import annotations

import json

import pytest

from website.backend.services import replay_service
from website.backend.services.reconstruction_accuracy import position_error
from website.backend.services.round_web_service import (
    AUDIBLE_GUNFIRE_RADIUS,
    VELOCITY_SANITY_CAP_UPS,
    CapturePolicy,
    Edge,
    PlayerState,
    Snapshot,
    _contested_guids,
    _ensure_attackers,
    build_edges,
    build_snapshot,
    derive_velocity,
    find_position_floor,
    get_round_snapshot,
    load_capture_policy,
    load_round_clock,
    load_round_information_state,
    make_locator,
    nearest_teammate_separation,
    select_life,
)


# Rows are (guid, name, team, class, spawn_ms, death_ms, path, map, id) — the
# shape load_round_tracks returns.
def _track(spawn, death, track_id, path=None):
    return ("G1", "p", "AXIS", "soldier", spawn, death, path or [], "supply", track_id)


class TestTheAudibleRadiusComesFromTheEngine:
    def test_it_is_the_distance_at_which_the_volume_reaches_zero(self):
        """⭐ The derivation, not the number.

        `src/client/snd_dma.c`: SOUND_RANGE_DEFAULT 1250, SOUND_FULLVOLUME 80.
        `S_SpatializeOrigin` computes dist_fullvol = range * 0.064, then
        dist = (d - dist_fullvol) / range, and scales volume by (1 - dist).
        Volume is zero once dist >= 1.

        Written this way the test fails if someone restores the invented 1,500,
        and it also fails if the engine's own constants are ever mis-copied —
        which a bare `== 1330.0` would not catch.
        """
        sound_range, full_volume = 1250.0, 1250.0 * 0.064
        assert full_volume == 80.0, "SOUND_FULLVOLUME in the engine"
        inaudible_at = full_volume + sound_range  # dist == 1 => volume 0
        assert inaudible_at == AUDIBLE_GUNFIRE_RADIUS


class TestMakeLocator:
    """The seam that turns "he knows WHO" into "he knows who and roughly where".

    Before it existed, `contact_hit` and `aim_lock` carried a subject and no
    region, so `nearest_known_enemy_distance` — which needs both — was
    structurally incapable of a value: None in 110 of 110 holder samples across
    three rounds. Every test here pins a property that measurement caught and
    the hand-built fixtures of the belief tests could not.
    """

    PATH = [
        {"x": 0.0, "y": 0.0, "z": 0.0, "time": 1000},
        {"x": 100.0, "y": 0.0, "z": 0.0, "time": 2000},
        {"x": 900.0, "y": 0.0, "z": 0.0, "time": 3000},
    ]

    def test_a_guid_not_in_the_round_has_no_position(self):
        assert make_locator({})("NOBODY", 1500) is None

    def test_the_path_may_arrive_as_json_text(self):
        """⭐ The defect runtime found and 133 unit tests did not.

        Fixtures hand `path` over as a list; some drivers return the same
        column as text, and `find_position_floor` then called `.get` on a
        string. Every belief in every round raised AttributeError.
        """
        region = make_locator(
            {"G1": [_track(0, None, 1, json.dumps(self.PATH))]})("G1", 2000)
        assert region is not None
        assert (region.x, region.y) == (100.0, 0.0)

    def test_the_position_never_comes_from_the_future(self):
        """FLOOR, not nearest: at 2,100 ms the answer is the 2,000 ms sample,
        even though 3,000 ms is only 900 ms away and would be picked by a
        nearest-neighbour lookup."""
        region = make_locator({"G1": [_track(0, None, 1, self.PATH)]})("G1", 2100)
        assert region.x == 100.0

    def test_before_the_first_sample_there_is_no_position(self):
        assert make_locator({"G1": [_track(0, None, 1, self.PATH)]})("G1", 500) is None

    def test_the_radius_is_the_measured_error_not_a_constant(self):
        """A stale sample must widen the region. If the radius were a chosen
        constant the two would match, and the page would draw a 60-second-old
        position as confidently as a fresh one."""
        locate = make_locator({"G1": [_track(0, None, 1, self.PATH)]})
        fresh = locate("G1", 2000)
        stale = locate("G1", 60_000)
        assert stale.radius > fresh.radius
        assert fresh.radius == position_error(0).p90

    def test_a_path_without_coordinates_yields_no_region(self):
        """A sample missing x/y/z must not become a region at the origin."""
        broken = [{"time": 1000, "event": "spawn"}]
        assert make_locator({"G1": [_track(0, None, 1, broken)]})("G1", 1500) is None


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
        path = [{"time": 0, "x": 0, "y": 0, "z": 0}, {"time": 100, "x": far, "y": 0, "z": 0}]
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
            {"time": 0, "x": 0, "y": 0, "z": 0},
            {"time": 1000, "x": 50, "y": 0, "z": 0},
            {"time": 1000, "x": 100, "y": 0, "z": 0},   # duplicate of the one before
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

    def test_missing_height_does_not_fabricate_vertical_velocity(self):
        """`z` is required, not defaulted to 0 — the same substitution that was
        removed from build_edges and missed here on the first pass."""
        path = [{"time": 0, "x": 0, "y": 0, "z": 0}, {"time": 1000, "x": 10, "y": 0}]
        vx, _, vz, _, reason = derive_velocity(path, 1, None)
        assert vx is None and vz is None
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


class _StubDb:
    """Returns one fixed result set; the query text is irrelevant here."""

    def __init__(self, rows):
        self.rows = rows

    async def fetch_all(self, _sql, _params=None):
        return self.rows


class TestLoadCapturePolicy:
    """What the round says it was able to record — and what it refuses to say."""

    @staticmethod
    def _manifest(source="sections_observed", **caps):
        base = {"shot_fired": "unknown", "aim_lock": "enabled"}
        base.update(caps)
        return {
            "manifest_version": 1,
            "source": source,
            "capabilities": base,
            "position_sample_interval_ms": 200,
        }

    @pytest.mark.asyncio
    async def test_no_manifest_stays_unknown(self):
        policy = await load_capture_policy(_StubDb([]), 1)
        assert policy.mode == "unknown"
        assert policy.source == "absent"
        assert policy.observation_interval_ms is None
        assert policy.capabilities == {}

    @pytest.mark.asyncio
    async def test_cadence_comes_from_the_manifest(self):
        policy = await load_capture_policy(_StubDb([(self._manifest(),)]), 1)
        assert policy.mode == "fixed"
        assert policy.observation_interval_ms == 200
        assert policy.source == "sections_observed"

    @pytest.mark.asyncio
    async def test_missing_capture_is_unknown_not_false(self):
        """The whole reason the manifest exists. A consumer reading `unknown`
        as `false` would report "no gunfire this round" about a round where
        gunfire was simply never recorded."""
        policy = await load_capture_policy(_StubDb([(self._manifest(),)]), 1)
        assert policy.capabilities["shot_fired"] == "unknown"
        assert policy.capabilities["shot_fired"] is not False

    @pytest.mark.asyncio
    async def test_json_string_rows_are_accepted(self):
        """Some adapters hand jsonb back as text rather than a dict."""
        policy = await load_capture_policy(
            _StubDb([(json.dumps(self._manifest()),)]), 1
        )
        assert policy.capabilities["aim_lock"] == "enabled"

    @pytest.mark.asyncio
    async def test_disagreeing_files_collapse_to_unknown(self):
        """One round, two files, two answers: we cannot tell which file the
        rows came from, so the disputed flag is unknown and the disagreement is
        counted rather than hidden behind whichever row sorted first."""
        rows = [
            (self._manifest(shot_fired="enabled"),),
            (self._manifest(shot_fired="disabled"),),
        ]
        policy = await load_capture_policy(_StubDb(rows), 1)
        assert policy.capabilities["shot_fired"] == "unknown"
        assert policy.conflicting_flags == 1
        assert policy.manifest_count == 2
        # Flags they agree on survive intact.
        assert policy.capabilities["aim_lock"] == "enabled"

    @pytest.mark.asyncio
    async def test_agreeing_files_are_not_a_conflict(self):
        rows = [(self._manifest(),), (self._manifest(),)]
        policy = await load_capture_policy(_StubDb(rows), 1)
        assert policy.conflicting_flags == 0
        assert policy.manifest_count == 2
        assert policy.capabilities["aim_lock"] == "enabled"

    @pytest.mark.asyncio
    async def test_malformed_manifest_is_ignored_not_crashed(self):
        policy = await load_capture_policy(_StubDb([("not a manifest",), (None,)]), 1)
        assert policy.source == "absent"


class TestCapturePolicyWithSeveralManifests:
    """One round, more than one processed file. Rare, and every branch here is
    a place where picking a winner would be a guess (CodeRabbit, PR #795)."""

    @staticmethod
    def _m(source="sections_observed", interval=200, **caps):
        base = {"shot_fired": "unknown", "aim_lock": "enabled"}
        base.update(caps)
        return {
            "manifest_version": 1,
            "source": source,
            "capabilities": base,
            "position_sample_interval_ms": interval,
        }

    @pytest.mark.asyncio
    async def test_a_declared_manifest_leads_regardless_of_order(self):
        """Exact beats inferred, whichever row the database returned first."""
        inferred = self._m(source="sections_observed", shot_fired="unknown")
        declared = self._m(source="declared", shot_fired="disabled")
        for rows in ([(inferred,), (declared,)], [(declared,), (inferred,)]):
            policy = await load_capture_policy(_StubDb(rows), 1)
            assert policy.capabilities["shot_fired"] == "unknown"  # they disagree
            assert policy.policy_version == "1"  # both are manifest_version 1
            assert policy.source == "conflicting"

    @pytest.mark.asyncio
    async def test_disagreeing_manifest_version_is_dropped_too(self):
        """Every scalar follows one rule: one answer or none. Reporting this one
        from an arbitrary file while the rest fall back would leave a single
        field describing one file and the others describing the round."""
        a = self._m()
        b = dict(self._m(), manifest_version=2)
        policy = await load_capture_policy(_StubDb([(a,), (b,)]), 1)
        assert policy.policy_version is None

    @pytest.mark.asyncio
    async def test_disagreeing_cadence_is_unknown(self):
        """The cadence is a fact about the file. Two answers means we have none."""
        rows = [(self._m(interval=200),), (self._m(interval=50),)]
        policy = await load_capture_policy(_StubDb(rows), 1)
        assert policy.observation_interval_ms is None
        assert policy.mode == "unknown"

    @pytest.mark.asyncio
    async def test_agreeing_cadence_survives(self):
        rows = [(self._m(interval=200),), (self._m(interval=200),)]
        policy = await load_capture_policy(_StubDb(rows), 1)
        assert policy.observation_interval_ms == 200
        assert policy.mode == "fixed"

    @pytest.mark.asyncio
    async def test_a_flag_only_one_file_knows_is_kept(self):
        rows = [(self._m(),), (self._m(comm_events="enabled"),)]
        policy = await load_capture_policy(_StubDb(rows), 1)
        assert policy.capabilities["comm_events"] == "enabled"
        assert policy.conflicting_flags == 0

    @pytest.mark.asyncio
    async def test_a_flag_disputed_by_three_files_counts_once(self):
        """Once unknown, a flag stays unknown; further disagreement about the
        same flag is the same conflict, not a new one."""
        rows = [
            (self._m(shot_fired="enabled"),),
            (self._m(shot_fired="disabled"),),
            (self._m(shot_fired="unknown"),),
        ]
        policy = await load_capture_policy(_StubDb(rows), 1)
        assert policy.capabilities["shot_fired"] == "unknown"
        assert policy.conflicting_flags == 1
        assert policy.manifest_count == 3


class _ClockStubDb:
    """Answers `fetch_timing_observations`, then tracks, then revives."""

    def __init__(self, timing, tracks=(), revives=()):
        self._queue = [list(timing), list(tracks), list(revives)]

    async def fetch_all(self, _sql, _params=None):
        return self._queue.pop(0) if self._queue else []


#: Fixtures are written in terms of LANDINGS, the thing that physically
#: happens, and the offset is derived from them — never the other way round.
#: `offset_ms` is the negated phase (a landing L satisfies
#: `(L + offset) % interval == 0`), and building a fixture from a guessed offset
#: is how a wrong convention gets baked into both the code and its test.
def _offset_for(landing_ms: int, interval: int) -> int:
    return (-landing_ms) % interval


def _wave_kills(team: str, interval: int, landing: int, n: int = 12):
    """Kills whose `time_to_next_spawn` points at the next real landing.

    Column order matches `fetch_timing_observations`: victim_team, kill_time,
    enemy_spawn_interval, time_to_next_spawn, score, killer_guid, killer_name.
    """
    rows = []
    for i in range(n):
        kill_time = landing + i * 1700 + 300
        time_to_next = (landing - kill_time) % interval or interval
        rows.append((team, kill_time, interval, time_to_next,
                     0.5, f"GUID{i}", f"player{i}"))
    return rows


def _wave_lives(team: str, interval: int, landing: int, waves: int = 6):
    """Two players landing on every wave, so clusters can form.

    Column order matches `fetch_clock_lives_and_revives`.
    """
    rows = []
    row_id = 0
    for wave in range(waves):
        spawn = landing + wave * interval
        for player in range(2):
            row_id += 1
            rows.append((row_id, f"P{player}", f"player{player}", team,
                         spawn, spawn + 900, "killed"))
    return rows


class TestLoadRoundClock:
    """§5's clock, as the snapshot publishes it."""

    @pytest.mark.asyncio
    async def test_both_teams_always_appear(self):
        """A missing key would read as "no clock here" when the truth is "we
        could not verify one" — the distinction §5.2 exists to draw."""
        clock = await load_round_clock(_ClockStubDb([]), 1, 0)
        assert set(clock) == {"AXIS", "ALLIES"}
        assert all(entry["status"] == "unavailable" for entry in clock.values())
        assert all(entry["reason"] for entry in clock.values())

    @pytest.mark.asyncio
    async def test_a_validated_clock_carries_the_moment(self):
        interval, landing = 20_000, 5_000
        db = _ClockStubDb(
            _wave_kills("AXIS", interval, landing),
            _wave_lives("AXIS", interval, landing),
        )
        clock = await load_round_clock(db, 1, landing + 12_000)
        axis = clock["AXIS"]
        assert axis["status"] == "validated"
        assert axis["offset_ms"] == _offset_for(landing, interval)
        # 12 s past a landing on a 20 s wheel: 8 s until the next one.
        assert axis["phase_ms"] == 12_000
        assert axis["time_to_next_wave_ms"] == 8_000

    @pytest.mark.asyncio
    async def test_a_team_without_observations_is_unavailable_not_absent(self):
        interval, landing = 20_000, 5_000
        db = _ClockStubDb(
            _wave_kills("AXIS", interval, landing),
            _wave_lives("AXIS", interval, landing),
        )
        clock = await load_round_clock(db, 1, 0)
        assert clock["ALLIES"]["status"] == "unavailable"
        assert "ALLIES" in clock

    @pytest.mark.asyncio
    async def test_an_unvalidated_clock_publishes_no_phase(self):
        """`phase_ms` is computed from the offset, and an unvalidated offset is
        one the protocol refuses to stand behind — so the moment cannot be
        derived from it either."""
        db = _ClockStubDb(_wave_kills("AXIS", 20_000, 5_000), [])
        axis = (await load_round_clock(db, 1, 9_000))["AXIS"]
        assert axis["status"] != "validated"
        assert axis["offset_ms"] is None
        assert "phase_ms" not in axis
        assert "time_to_next_wave_ms" not in axis


class _InfoStubDb:
    """Answers the four Layer 3 queries in the order the loader issues them."""

    def __init__(self, deaths=(), engagements=(), shots=(), locks=()):
        self._queue = [list(deaths), list(engagements), list(shots), list(locks)]

    async def fetch_all(self, _sql, _params=None):
        return self._queue.pop(0) if self._queue else []


def _snapshot_of(*guids: str) -> Snapshot:
    players = {
        g: PlayerState(guid=g, name=g, team="AXIS" if i % 2 else "ALLIES",
                       player_class=None, x=float(i * 100), y=0.0, z=0.0,
                       health=100, weapon=None, stance=None, speed=0.0, alive=True,
                       track_id=i, stale_ms=0, overlap_conflict=False)
        for i, g in enumerate(guids)
    }
    return Snapshot(t_ms=0, players=players, edges=[], overlap_conflicts=0, gaps={})


class _SnapshotStubDb:
    """Answers by what the query ASKS FOR, not by call order.

    `get_round_snapshot` issues a dozen queries through five loaders, and their
    order is an implementation detail that a positional stub would freeze into
    the tests — reordering two independent loads would then break tests that
    have nothing to do with ordering.
    """

    def __init__(self, tracks=(), duration_s=None):
        self._tracks = list(tracks)
        self._duration_s = duration_s

    async def fetch_all(self, sql, _params=None):
        if "death_time_ms IS NOT NULL" in sql:
            return []                       # Layer 3 deaths
        if "FROM player_track pt" in sql:
            return self._tracks
        if "FROM rounds r" in sql:
            return [(self._duration_s,)] if self._duration_s else []
        return []


def _stub_track(guid: str, x: float) -> tuple:
    """One life, in `load_round_tracks` column order."""
    path = [{"x": x, "y": 0.0, "z": 0.0, "time": 0},
            {"x": x, "y": 0.0, "z": 0.0, "time": 10_000}]
    return (guid, guid, "AXIS", "soldier", 0, None, path, "supply", hash(guid) % 1000)


class TestPointOfView:
    """`pov` decides WHOSE picture is returned — 82 lines that had no test.

    Every path here was exercised only by throwaway scripts during development.
    The oracle view is the dangerous one: §6.4 makes `world` a named diagnostic,
    so it has to be asked for rather than arrived at by accident.
    """

    async def _snapshot(self, **kw):
        db = _SnapshotStubDb(tracks=[_stub_track("A", 0.0), _stub_track("B", 500.0)])
        return await get_round_snapshot(db, 1, 5_000, **kw)

    @pytest.mark.asyncio
    async def test_no_pov_is_the_world_view_and_says_so(self):
        info = (await self._snapshot())["information_state"]
        assert info["pov"] == "world"
        assert set(info["holders"]) == {"A", "B"}

    @pytest.mark.asyncio
    async def test_world_is_spelled_out_not_arrived_at(self):
        info = (await self._snapshot(pov="world"))["information_state"]
        assert info["pov"] == "world"
        assert set(info["holders"]) == {"A", "B"}
        assert "pov_unavailable" not in info

    @pytest.mark.asyncio
    async def test_a_player_pov_returns_only_that_player(self):
        info = (await self._snapshot(pov="A"))["information_state"]
        assert set(info["holders"]) == {"A"}
        assert info["pov"] == "A"
        assert info["pov_unavailable"] is None

    @pytest.mark.asyncio
    async def test_an_unknown_pov_explains_itself_instead_of_falling_back(self):
        """⛔ Never silently the world view: a typo in a GUID would then hand
        back omniscience labelled as one player's knowledge."""
        info = (await self._snapshot(pov="GHOST"))["information_state"]
        assert info["holders"] == {}
        assert "GHOST" in info["pov_unavailable"]
        assert info["pov"] == "GHOST"


class TestAnEmptyRoundKeepsTheContract:
    @pytest.mark.asyncio
    async def test_every_key_survives_a_round_with_no_tracks(self):
        """A thin round used to take a shortcut with a different shape, so a
        consumer reading `capture_policy` hit a KeyError exactly when the data
        was thinnest (CodeRabbit, PR #792)."""
        payload = await get_round_snapshot(_SnapshotStubDb(), 1, 5_000)
        for key in ("capture_policy", "clock", "information_state", "player_count",
                    "gaps", "players", "edges", "reconstruction_accuracy"):
            assert key in payload, key
        assert payload["unavailable"]


class TestEnsureAttackers:
    """`attackers` is a list from asyncpg and text from other drivers."""

    def test_a_list_passes_through(self):
        assert _ensure_attackers([{"guid": "X"}]) == [{"guid": "X"}]

    def test_json_text_is_parsed(self):
        assert _ensure_attackers('[{"guid": "X"}]') == [{"guid": "X"}]

    def test_broken_json_is_empty_not_an_exception(self):
        """⚠️ One malformed row must not take down the whole snapshot."""
        assert _ensure_attackers("{not json") == []

    def test_null_is_empty(self):
        assert _ensure_attackers(None) == []


class TestInformationStateLoader:
    """§6 Layer 3 as the snapshot serves it."""

    @pytest.mark.asyncio
    async def test_every_player_gets_an_entry_even_with_no_beliefs(self):
        """⛔ Otherwise a player who learned nothing and a player we could not
        model look identical in the payload."""
        result = await load_round_information_state(
            _InfoStubDb(), 1, 1000, _snapshot_of("A", "B"), {},
            CapturePolicy(capabilities={"shot_fired": "enabled", "aim_lock": "enabled"}))
        assert set(result["holders"]) == {"A", "B"}
        assert all(h["known_enemy_count"] == 0 for h in result["holders"].values())

    @pytest.mark.asyncio
    async def test_an_unproven_channel_is_named_for_every_holder(self):
        result = await load_round_information_state(
            _InfoStubDb(), 1, 1000, _snapshot_of("A", "B"), {}, CapturePolicy())
        for holder in result["holders"].values():
            assert set(holder["unavailable"]) == {"gunfire", "aim_lock"}

    @pytest.mark.asyncio
    async def test_a_death_reaches_the_other_players(self):
        result = await load_round_information_state(
            _InfoStubDb(deaths=[("V", "AXIS", 500)]), 1, 1000,
            _snapshot_of("A", "V"), {"AXIS": {"interval_ms": 20000, "offset_ms": 0}},
            CapturePolicy(capabilities={"shot_fired": "enabled", "aim_lock": "enabled"}))
        assert result["holders"]["A"]["beliefs"], "the death was not announced"
        assert result["holders"]["V"]["beliefs"] == [], "the victim told themselves"

    @pytest.mark.asyncio
    async def test_the_audible_radius_is_published_not_buried(self):
        """§6.3: the radius and localisation error are named model parameters."""
        result = await load_round_information_state(
            _InfoStubDb(), 1, 0, _snapshot_of("A"), {}, CapturePolicy())
        assert result["audible_gunfire_radius"] > 0

    @pytest.mark.asyncio
    async def test_an_empty_round_returns_the_same_shape(self):
        result = await load_round_information_state(
            _InfoStubDb(), 1, 0, _snapshot_of(), {}, CapturePolicy())
        assert result["holders"] == {}
        assert "audible_gunfire_radius" in result
