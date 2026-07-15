"""Unit tests for the Slomix Museum memory card signature-map picker.

The signature map is the one where a player most overperforms their OWN career
average — this is the load-bearing idea (raw most-played is te_escape2 for the
whole group and carries no information). Tests cover the pure picker so the
selection rule is pinned without a DB.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.routers.players_profile_router import (
    _MEMORY_SIG_MIN_LIFT,
    _pick_signature_map,
)


class TestPickSignatureMap:
    def test_picks_highest_lift(self):
        # career avg 10. goldrush avg 16 (+60%) beats supply avg 12 (+20%).
        rows = [("supply", 200, 12.0), ("sw_goldrush_te", 150, 16.0)]
        sig = _pick_signature_map(rows, career_avg=10.0)
        assert sig["map_name"] == "sw_goldrush_te"
        assert sig["lift_pct"] == 60
        assert sig["rounds"] == 150

    def test_none_when_no_map_clears_min_lift(self):
        # Every map is within +7% of the career avg -> below the 8% floor.
        rows = [("supply", 200, 10.5), ("radar", 90, 10.7)]
        assert _pick_signature_map(rows, career_avg=10.0) is None

    def test_min_lift_boundary_is_inclusive(self):
        rows = [("supply", 50, 10.0 * _MEMORY_SIG_MIN_LIFT)]
        sig = _pick_signature_map(rows, career_avg=10.0)
        assert sig is not None
        assert sig["map_name"] == "supply"

    def test_zero_career_avg_returns_none(self):
        # No career average yet (brand-new player) -> no signature, no ZeroDivision.
        assert _pick_signature_map([("supply", 8, 5.0)], career_avg=0.0) is None

    def test_empty_rows_returns_none(self):
        assert _pick_signature_map([], career_avg=10.0) is None

    def test_handles_null_avg_kills(self):
        # A map row with a NULL avg (shouldn't happen post-filter, but be safe).
        assert _pick_signature_map([("supply", 8, None)], career_avg=10.0) is None
