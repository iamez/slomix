"""Unit tests for Objective Pressure (Good Night plan rank 6, §F).

Cover the pure geometry (_zone_index — 3D) and the per-round credit rule
(_accumulate_round — contested + teammate-supported, the §F.1/§F.2 refinements),
which is where the metric's meaning lives. The DB glue in
compute_objective_pressure is exercised by the backtest against real data.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.services.objective_pressure_service import (
    BUCKET_MS,
    _accumulate_round,
    _zone_index,
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
        # Two ALLIES + one AXIS all in the objective at t=0 -> the ALLIES pair is
        # contested (enemy present) and supported (>=2 mates) -> both get credit.
        pressure: dict = defaultdict(float)
        rtracks = [
            ("ALLIES", "a1", _samples(0)),
            ("ALLIES", "a2", _samples(0)),
            ("AXIS", "x1", _samples(0)),
        ]
        _accumulate_round(rtracks, ZONES, pressure)
        assert pressure["a1"] > 0
        assert pressure["a2"] > 0
        # last-sample credit defaults to one bucket (200ms)
        assert pressure["a1"] == BUCKET_MS / 1000.0

    def test_empty_pressure_no_teammate_support(self):
        # One ALLIES + one AXIS: contested but NOT supported (mates < 2) -> no
        # credit (empty pressure, §F.2).
        pressure: dict = defaultdict(float)
        rtracks = [
            ("ALLIES", "a1", _samples(0)),
            ("AXIS", "x1", _samples(0)),
        ]
        _accumulate_round(rtracks, ZONES, pressure)
        assert pressure["a1"] == 0

    def test_uncontested_no_enemy(self):
        # Two ALLIES in the objective, no enemy -> not contested -> no credit.
        pressure: dict = defaultdict(float)
        rtracks = [
            ("ALLIES", "a1", _samples(0)),
            ("ALLIES", "a2", _samples(0)),
        ]
        _accumulate_round(rtracks, ZONES, pressure)
        assert pressure["a1"] == 0

    def test_sample_outside_zone_ignored(self):
        pressure: dict = defaultdict(float)
        rtracks = [
            ("ALLIES", "a1", [(0, 600.0, 0.0, 0.0)]),  # outside 2D
            ("ALLIES", "a2", _samples(0)),
            ("AXIS", "x1", _samples(0)),
        ]
        _accumulate_round(rtracks, ZONES, pressure)
        assert pressure["a1"] == 0

    def test_duration_from_gaps_and_cap(self):
        # a1 has samples at 0, 200, 1400 (a 1200ms gap). Credits:
        #   i=0 -> gap 200ms, i=1 -> gap 1200ms capped to 400ms, i=2 -> last=200ms.
        # = 0.2 + 0.4 + 0.2 = 0.8s. Support+contest present at every bucket.
        pressure: dict = defaultdict(float)
        rtracks = [
            ("ALLIES", "a1", _samples(0, 200, 1400)),
            ("ALLIES", "a2", _samples(0, 200, 1400)),
            ("AXIS", "x1", _samples(0, 200, 1400)),
        ]
        _accumulate_round(rtracks, ZONES, pressure)
        assert round(pressure["a1"], 2) == 0.8
