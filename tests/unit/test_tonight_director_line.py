"""Unit tests for the Tonight live director line (Good Night plan rank 8, §A).

The director line is a pure, deterministic summary of the already-computed
tonight payload (maps/rounds score, momentum swing, current R2 chase). These
tests pin the sentence for the scenarios a real night actually produces.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.routers.players_router import (
    _fmt_mmss,
    _tonight_director_line,
)


def _mom(a):
    return [{"a": a, "b": 100 - a}]


def _score(am, bm, ar, br, mc):
    return {"a_maps": am, "b_maps": bm, "a_rounds": ar, "b_rounds": br,
            "maps_completed": mc}


NO_CHASE = {"map": "supply", "round": 2, "r2_pending": False, "beat_seconds": None}


class TestFmtMmss:
    def test_basic(self):
        assert _fmt_mmss(252) == "4:12"

    def test_zero_pad(self):
        assert _fmt_mmss(65) == "1:05"

    def test_none_and_negative(self):
        assert _fmt_mmss(None) == ""
        assert _fmt_mmss(-5) == ""


class TestDirectorLine:
    def test_nothing_to_say_returns_none(self):
        assert _tonight_director_line(_score(0, 0, 0, 0, 0), [], NO_CHASE, "Team A", "Team B") is None

    def test_map_lead_with_momentum(self):
        line = _tonight_director_line(_score(3, 1, 6, 3, 4), _mom(80), NO_CHASE, "Team A", "Team B")
        assert line == "Team A lead the night 3–1 on maps, and they hold the momentum."

    def test_map_lead_but_momentum_swung_to_other(self):
        line = _tonight_director_line(_score(2, 1, 4, 4, 3), _mom(20), NO_CHASE, "Team A", "Team B")
        assert line == "Team A lead the night 2–1 on maps, but Team B have swung the last few rounds."

    def test_level_maps_momentum_names_the_pusher(self):
        line = _tonight_director_line(_score(2, 2, 5, 4, 4), _mom(25), NO_CHASE, "Alpha", "Bravo")
        assert line == "All square at 2–2 on maps, but Bravo are pushing."

    def test_opening_map_leans_on_rounds(self):
        # No map decided yet; one round landed for A.
        line = _tonight_director_line(_score(0, 0, 1, 0, 0), _mom(70), NO_CHASE, "Team A", "Team B")
        assert line == "Opening map on the clock — Team A up 1–0 on rounds."

    def test_live_r2_chase_clause_appended(self):
        chase = {"map": "sw_goldrush_te", "round": 1, "r2_pending": True, "beat_seconds": 252}
        line = _tonight_director_line(_score(1, 1, 3, 3, 2), _mom(50), chase, "Team A", "Team B")
        assert line == "All square at 1–1 on maps · sw goldrush te: R2 chasing 4:12."

    def test_r2_pending_without_beat_time(self):
        chase = {"map": "supply", "round": 1, "r2_pending": True, "beat_seconds": None}
        line = _tonight_director_line(_score(1, 0, 2, 2, 1), _mom(50), chase, "Team A", "Team B")
        assert line.endswith("supply: R2 to play.")
