"""Unit tests for Objective Pressure (Good Night plan rank 6, §F).

Cover the pure geometry (_zone_index — 3D) and the per-round credit rule
(_accumulate_round — contested + teammate-supported, the §F.1/§F.2 refinements),
which is where the metric's meaning lives. The DB glue in
compute_objective_pressure is exercised by the backtest against real data.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.services.objective_pressure_service import (
    _CACHE,
    BUCKET_MS,
    _accumulate_round,
    _load_zones,
    _zone_index,
    compute_objective_pressure,
)

# One objective sphere at the origin, radius 500.
ZONES = [(0.0, 0.0, 0.0, 500.0)]


class TestZoneIndex:
    def test_inside_sphere(self):
        assert _zone_index(100, 100, 0, ZONES) == 0

    def test_outside_in_2d(self):
        assert _zone_index(600, 0, 0, ZONES) == -1

    def test_outside_in_z_only(self):
        # Within the 2D footprint but on a different floor -> not on the objective.
        assert _zone_index(0, 0, 600, ZONES) == -1

    def test_picks_first_matching(self):
        zones = [(0.0, 0.0, 0.0, 500.0), (100.0, 0.0, 0.0, 500.0)]
        assert _zone_index(50, 0, 0, zones) == 0

    def test_no_zones(self):
        assert _zone_index(0, 0, 0, []) == -1


def _samples(*times):
    """Samples all sitting at the origin (inside ZONES) at the given times."""
    return [(t, 0.0, 0.0, 0.0) for t in times]


class TestAccumulateRound:
    def test_contested_and_supported_credits(self):
        # Two ALLIES + one AXIS all in the objective across t=0..200 -> the ALLIES
        # pair is contested (enemy present) and supported (>=2 distinct mates) ->
        # each gets the forward gap (200ms) credited once.
        pressure: dict = defaultdict(float)
        rtracks = [
            ("ALLIES", "a1", _samples(0, 200)),
            ("ALLIES", "a2", _samples(0, 200)),
            ("AXIS", "x1", _samples(0, 200)),
        ]
        _accumulate_round(rtracks, ZONES, pressure)
        assert pressure["a1"] == BUCKET_MS / 1000.0
        assert pressure["a2"] == BUCKET_MS / 1000.0

    def test_empty_pressure_no_teammate_support(self):
        # One ALLIES + one AXIS: contested but NOT supported (mates < 2) -> no
        # credit (empty pressure, §F.2).
        pressure: dict = defaultdict(float)
        rtracks = [
            ("ALLIES", "a1", _samples(0, 200)),
            ("AXIS", "x1", _samples(0, 200)),
        ]
        _accumulate_round(rtracks, ZONES, pressure)
        assert pressure["a1"] == 0

    def test_duplicate_samples_do_not_fake_support(self):
        # A single ALLIES player with TWO records in the same 200ms bucket must
        # NOT satisfy the >=2 support rule (distinct players, not samples).
        pressure: dict = defaultdict(float)
        rtracks = [
            ("ALLIES", "a1", _samples(0, 50, 200)),  # two records in bucket 0
            ("AXIS", "x1", _samples(0, 200)),
        ]
        _accumulate_round(rtracks, ZONES, pressure)
        assert pressure["a1"] == 0

    def test_uncontested_no_enemy(self):
        # Two ALLIES in the objective, no enemy -> not contested -> no credit.
        pressure: dict = defaultdict(float)
        rtracks = [
            ("ALLIES", "a1", _samples(0, 200)),
            ("ALLIES", "a2", _samples(0, 200)),
        ]
        _accumulate_round(rtracks, ZONES, pressure)
        assert pressure["a1"] == 0

    def test_sample_outside_zone_ignored(self):
        pressure: dict = defaultdict(float)
        rtracks = [
            ("ALLIES", "a1", [(0, 600.0, 0.0, 0.0), (200, 600.0, 0.0, 0.0)]),  # outside 2D
            ("ALLIES", "a2", _samples(0, 200)),
            ("AXIS", "x1", _samples(0, 200)),
        ]
        _accumulate_round(rtracks, ZONES, pressure)
        assert pressure["a1"] == 0

    def test_terminal_sample_awards_no_forward_time(self):
        # Single-sample track (a life that only ever registered one record on the
        # point) has no forward duration -> zero credit, no phantom 200ms.
        pressure: dict = defaultdict(float)
        rtracks = [
            ("ALLIES", "a1", _samples(0)),
            ("ALLIES", "a2", _samples(0)),
            ("AXIS", "x1", _samples(0)),
        ]
        _accumulate_round(rtracks, ZONES, pressure)
        assert pressure["a1"] == 0

    def test_duration_from_gaps_and_cap(self):
        # a1 has samples at 0, 200, 1400 (a 1200ms gap). Forward-gap credits:
        #   i=0 -> 200ms, i=1 -> 1200ms capped to 400ms; the last sample (i=2)
        #   awards nothing. = 0.2 + 0.4 = 0.6s. Support+contest at every bucket.
        pressure: dict = defaultdict(float)
        rtracks = [
            ("ALLIES", "a1", _samples(0, 200, 1400)),
            ("ALLIES", "a2", _samples(0, 200, 1400)),
            ("AXIS", "x1", _samples(0, 200, 1400)),
        ]
        _accumulate_round(rtracks, ZONES, pressure)
        assert round(pressure["a1"], 2) == 0.6


class _FakeRow(dict):
    """dict that also supports r["col"] access like an asyncpg Record."""


class _FakeDB:
    """Routes the two compute queries: player_track vs combat_position."""

    def __init__(self, tracks, kills):
        self._tracks = tracks
        self._kills = kills

    async def fetch_all(self, query, params=()):
        return self._tracks if "FROM player_track" in query else self._kills


def _track(guid, team, name, coord):
    # Two samples 200ms apart at the objective coord so forward-gap credit applies.
    x, y, z = coord
    path = [{"time": 0, "x": x, "y": y, "z": z}, {"time": 200, "x": x, "y": y, "z": z}]
    return _FakeRow(round_start_unix=1000, round_number=1, map_name="supply",
                    player_guid=guid, player_name=name, team=team, path=json.dumps(path))


class TestComputeReturnsShortGuids:
    @pytest.mark.asyncio
    async def test_profile_routable_short_guids(self):
        # Two ALLIES (supported) + one AXIS (contesting) on a real 'supply'
        # objective coord so the ALLIES pair earns pressure; verify the emitted
        # GUIDs are the 8-char profile-routable form, not the 32-char one.
        _CACHE.clear()
        zones = _load_zones()["supply"]
        coord = (zones[0][0], zones[0][1], zones[0][2])  # inside the first objective
        g1 = "1C747DF1A037D2AFECCB6ED063DF44E7"
        g2 = "AABBCCDD00112233445566778899AABB"
        g_axis = "D8423F90112233445566778899AABBCC"
        tracks = [
            _track(g1, "ALLIES", "vid", coord),
            _track(g2, "ALLIES", "olz", coord),
            _track(g_axis, "AXIS", "kanii", coord),
        ]
        kills = [_FakeRow(guid=g1, kills=5), _FakeRow(guid=g_axis, kills=9)]
        out = await compute_objective_pressure(_FakeDB(tracks, kills), "2099-01-01", limit=5)

        assert out["players"], "expected the supported ALLIES pair to earn pressure"
        for p in out["players"]:
            assert len(p["guid"]) == 8  # short_guid, profile-routable
        assert all(len(g) == 8 for g in out["top_fragger_guids"])
        # the 32-char guid is shortened to its 8-char prefix
        assert any(p["guid"] == "1C747DF1" for p in out["players"])
        _CACHE.clear()
