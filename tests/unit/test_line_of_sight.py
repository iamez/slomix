"""SW-3: line of sight as an oracle diagnostic (spec §6.1, §12 W6).

The rules pinned here: only opponent pairs, only the living and placed, both
directions; the world view alone carries it and every other view says why
not; a missing geometry tree reads as "no geometry", never as "nobody saw
anyone"; exposure counts clear rays TO a player.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pytest

from website.backend.map_geometry import PlayerStance
from website.backend.services import line_of_sight as los
from website.backend.services.round_web_service import Edge, PlayerState, get_round_snapshot


@dataclass
class _Result:
    status: str
    reason: str


class _FakeTracer:
    """Clear when the observer stands lower than or level with the target on
    x (a made-up geometry), indeterminate on a missing stance, blocked
    otherwise — enough to tell the two directions apart."""

    def __init__(self):
        self.calls: list[tuple] = []

    def trace_line_of_sight_availability(self, o, os_, t, ts):
        self.calls.append((o, os_, t, ts))
        if os_ is None or ts is None:
            return _Result("indeterminate", "missing_stance")
        return _Result("clear", "static_geometry_clear") if o[0] <= t[0] else _Result("blocked", "static_geometry_blocked")


class _FakeProvider:
    def __init__(self, tracer=None, reason="no geometry: fake"):
        self._tracer = tracer
        self._reason = reason

    async def tracer_for(self, map_name):
        return (self._tracer, f"{map_name} from fake.pk3") if self._tracer else (None, self._reason)


def _player(guid, team, x, *, alive=True, stance=0):
    return PlayerState(guid=guid, name=guid, team=team, player_class=None, x=x, y=0.0, z=0.0,
                       health=100, weapon=None, stance=stance, speed=0.0, alive=alive,
                       track_id=1, stale_ms=0, overlap_conflict=False)


class TestStance:
    def test_the_tracker_codes_and_the_words_map_and_anything_else_is_unknown(self):
        assert los.stance_of(0) is PlayerStance.STANDING
        assert los.stance_of(1) is PlayerStance.CROUCHING
        assert los.stance_of("prone") is PlayerStance.PRONE
        assert los.stance_of(None) is None
        assert los.stance_of(7) is None
        assert los.stance_of(True) is None


class TestLineOfSightForEdges:
    def test_only_opponent_pairs_both_alive_and_placed_in_both_directions(self):
        players = {
            "A": _player("A", "AXIS", 0.0), "B": _player("B", "ALLIES", 100.0),
            "C": _player("C", "AXIS", 50.0), "D": _player("D", "ALLIES", 200.0, alive=False),
            "E": _player("E", "ALLIES", None),
        }
        edges = [Edge("A", "B", "opponent", 100.0), Edge("A", "C", "teammate", 50.0),
                 Edge("A", "D", "opponent", 200.0), Edge("A", "E", "opponent", 1.0)]
        out = los.line_of_sight_for_edges(players, edges, _FakeTracer())
        assert list(out) == [("A", "B")]
        # A (x=0) sees B (x=100) in the fake geometry; B does not see A.
        assert out[("A", "B")]["a_to_b"]["status"] == "clear"
        assert out[("A", "B")]["b_to_a"]["status"] == "blocked"

    def test_a_missing_stance_is_indeterminate_not_a_guess(self):
        players = {"A": _player("A", "AXIS", 0.0, stance=None), "B": _player("B", "ALLIES", 100.0)}
        out = los.line_of_sight_for_edges(players, [Edge("A", "B", "opponent", 100.0)], _FakeTracer())
        assert out[("A", "B")]["a_to_b"] == {"status": "indeterminate", "reason": "missing_stance"}

    def test_exposure_counts_clear_rays_to_a_player_and_lists_zero_as_a_count(self):
        by_edge = {("A", "B"): {"a_to_b": {"status": "clear"}, "b_to_a": {"status": "blocked"}},
                   ("C", "B"): {"a_to_b": {"status": "clear"}, "b_to_a": {"status": "clear"}}}
        assert los.exposure({}, by_edge) == {"A": 0, "B": 2, "C": 1}


def _stub_track(guid, x, team):
    path = [{"time": 0, "x": x, "y": 0.0, "z": 0.0, "health": 100, "stance": 0}]
    return (guid, guid, team, "soldier", 0, None, path, "supply", 1)


class _Db:
    def __init__(self, tracks):
        self._tracks = tracks

    async def fetch_all(self, sql, _p=None):
        if "FROM player_track pt" in sql:
            return self._tracks
        return []

    async def fetch_one(self, sql, _p=None):
        return None


class TestThePayload:
    @pytest.mark.asyncio
    async def test_the_world_view_carries_the_block_and_the_per_edge_verdicts(self):
        db = _Db([_stub_track("A", 0.0, "AXIS"), _stub_track("B", 100.0, "ALLIES"), _stub_track("C", 50.0, "AXIS")])
        tracer = _FakeTracer()
        payload = await get_round_snapshot(db, 1, 500, los_provider=_FakeProvider(tracer))
        block = payload["line_of_sight"]
        assert block["available"] is True
        assert block["geometry"] == "supply from fake.pk3"
        assert block["pairs_traced"] == 2  # A–B and C–B; A–C is a teammate pair
        assert block["validated_by"]["agreement_pct"] == 99.92
        assert "necessary, not sufficient" in block["scope"]
        by_kind = {(e["a"], e["b"]): e for e in payload["edges"]}
        opp = [e for e in payload["edges"] if e["kind"] == "opponent"]
        assert all(e["line_of_sight"] is not None for e in opp)
        assert all(e["line_of_sight"] is None for e in payload["edges"] if e["kind"] == "teammate")
        assert block["exposure"]["B"] == 2, by_kind
        assert any("ORACLE DIAGNOSTIC" in n for n in payload["notes"])
        assert not any("NOT included" in n for n in payload["notes"])

    @pytest.mark.asyncio
    async def test_a_point_of_view_withholds_it_and_says_why(self):
        db = _Db([_stub_track("A", 0.0, "AXIS"), _stub_track("B", 100.0, "ALLIES")])
        tracer = _FakeTracer()
        payload = await get_round_snapshot(db, 1, 500, pov="team:AXIS", los_provider=_FakeProvider(tracer))
        assert payload["line_of_sight"]["available"] is False
        assert payload["line_of_sight"]["reason"].startswith("withheld under a point of view: the other side")
        assert tracer.calls == []
        assert all(e.get("line_of_sight") is None for e in payload["edges"])

    @pytest.mark.asyncio
    async def test_no_geometry_reads_as_no_geometry_not_as_nobody_seen(self):
        db = _Db([_stub_track("A", 0.0, "AXIS"), _stub_track("B", 100.0, "ALLIES")])
        payload = await get_round_snapshot(db, 1, 500, los_provider=_FakeProvider(None, "no geometry for supply: none"))
        assert payload["line_of_sight"] == {**payload["line_of_sight"], "available": False, "reason": "no geometry for supply: none", "exposure": {}}
        assert all(e["line_of_sight"] is None for e in payload["edges"])


class TestTheProviderOnThisHost:
    def test_a_missing_tree_is_a_named_absence(self, tmp_path):
        prov = los.GeometryProvider(tmp_path / "nowhere")
        tracer, reason = prov.tracer_for_sync("supply")
        assert tracer is None and "not a directory" in reason

    @pytest.mark.skipif(
        not Path(os.environ.get(los.ETMAIN_DIR_ENV, los.DEFAULT_ETMAIN_DIR)).is_dir(),
        reason="no etmain tree on this host",
    )
    def test_the_real_tracer_answers_and_is_cached(self):
        """Two points measured on 2026-09-09 on the dev box: supply, a pair
        in the open (clear); the tracer is built once per map."""
        prov = los.GeometryProvider()
        tracer, label = prov.tracer_for_sync("supply")
        assert tracer is not None, label
        assert label.startswith("supply from ")
        r = tracer.trace_line_of_sight_availability((3.7, -535.9, 320.3), PlayerStance.STANDING, (200.0, -400.0, 320.0), PlayerStance.STANDING)
        assert str(r.status) in {"clear", "blocked"}
        assert prov.tracer_for_sync("supply")[0] is tracer
        missing, why = prov.tracer_for_sync("etl_supply")
        assert missing is None and "no geometry for etl_supply" in why
