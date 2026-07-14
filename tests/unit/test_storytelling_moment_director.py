"""Unit tests for the Moment Director cut (Good Night plan B1).

`_select_director_cut` picks the top-N highlight moments. The Phase-0 backtest
showed a typical night saturates the 5★ ceiling (hundreds of team-wipes +
multikills all at 5★), so the pre-B1 selection left the tie-break to chronology
and could show one player's five 5★ wipes. The director keeps stars as the
primary signal but breaks equal-star ties by cinematic type priority and
spreads the spotlight across players.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.services.storytelling.moments import (
    _TYPE_PRIORITY,
    _director_rank,
    _select_director_cut,
)


def _m(mtype, stars, player, t=0):
    return {"type": mtype, "impact_stars": stars, "player": player, "time_ms": t}


class TestDirectorRank:
    def test_stars_dominate_type_priority(self):
        # A 5★ kill_streak (lowest priority) still outranks a 4★ carrier_chain
        # (highest priority) — stars are the primary signal.
        hi_star = _m("kill_streak", 5, "A")
        hi_prio = _m("carrier_chain", 4, "B")
        assert _director_rank(hi_star) < _director_rank(hi_prio)

    def test_type_priority_breaks_star_ties(self):
        # Equal stars → the rarer, more cinematic type ranks first.
        assert _director_rank(_m("carrier_chain", 5, "A")) < _director_rank(_m("team_wipe", 5, "B"))

    def test_priority_table_ranks_rare_over_common(self):
        # team_wipe (251 in pool) and kill_streak must sit below the decisive plays.
        assert _TYPE_PRIORITY["carrier_chain"] > _TYPE_PRIORITY["team_wipe"]
        assert _TYPE_PRIORITY["objective_secured"] > _TYPE_PRIORITY["team_wipe"]
        assert _TYPE_PRIORITY["team_wipe"] > _TYPE_PRIORITY["kill_streak"]


class TestSelectDirectorCut:
    def test_empty_input(self):
        assert _select_director_cut([], 5) == []

    def test_truncates_to_limit(self):
        moments = [_m("multikill", 5, f"P{i}", t=i) for i in range(10)]
        assert len(_select_director_cut(moments, 3)) == 3

    def test_stars_still_primary_across_tiers(self):
        # A single 5★ beats any number of 4★ regardless of type priority.
        moments = [
            _m("carrier_chain", 4, "A"),   # high priority but only 4★
            _m("kill_streak", 5, "B"),     # low priority but 5★
        ]
        cut = _select_director_cut(moments, 1)
        assert cut[0]["type"] == "kill_streak"

    def test_equal_star_headline_is_most_cinematic(self):
        # Among all-5★ moments the carrier-chain game-winner headlines, not the
        # common team wipe.
        moments = [
            _m("team_wipe", 5, "A", t=10),
            _m("carrier_chain", 5, "B", t=20),
            _m("push_success", 5, "C", t=30),
        ]
        cut = _select_director_cut(moments, 3)
        assert cut[0]["type"] == "carrier_chain"

    def test_spreads_players_over_repeat_spotlight(self):
        # One player has three 5★ moments; two others have one each. The pre-B1
        # star-then-time cut would show all three of player A's — the director
        # must spread across the three players instead.
        moments = [
            _m("team_wipe", 5, "A", t=1),
            _m("multikill", 5, "A", t=2),
            _m("kill_streak", 5, "A", t=3),
            _m("objective_secured", 5, "B", t=4),
            _m("push_success", 5, "C", t=5),
        ]
        cut = _select_director_cut(moments, 3)
        assert len({m["player"] for m in cut}) == 3

    def test_preserves_type_diversity(self):
        # Distinct types available → the cut should not repeat a type while a
        # fresh one is still unused.
        moments = [
            _m("team_wipe", 5, "A", t=1),
            _m("team_wipe", 5, "B", t=2),
            _m("multikill", 5, "C", t=3),
            _m("carrier_chain", 5, "D", t=4),
        ]
        cut = _select_director_cut(moments, 3)
        assert len({m["type"] for m in cut}) == 3

    def test_fills_to_limit_when_one_type_only(self):
        # Only team_wipes exist — relaxation still fills the cut and spreads
        # across the distinct players.
        moments = [_m("team_wipe", 5, f"P{i}", t=i) for i in range(4)]
        cut = _select_director_cut(moments, 3)
        assert len(cut) == 3
        assert len({m["player"] for m in cut}) == 3

    def test_missing_player_key_does_not_crash(self):
        moments = [
            {"type": "team_wipe", "impact_stars": 5, "time_ms": 1},
            {"type": "multikill", "impact_stars": 5, "time_ms": 2},
        ]
        cut = _select_director_cut(moments, 2)
        assert len(cut) == 2
