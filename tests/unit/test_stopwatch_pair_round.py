"""StopwatchScoringService._pair_round — match_id-canonical R1<->R2 pairing.

Owner rule (2026-07-05): EVERY finished map is its own map — a repeated map
name within one session is a separate match. Only match_id keys that correctly
when abandoned R1s or orphan R2s interleave; the old sequential same-map
pairing mispaired those (root of the bot-vs-BOX session score divergence).
"""
from __future__ import annotations

from bot.services.stopwatch_scoring_service import StopwatchScoringService


def _pair(rows):
    """rows: (match_id, gsid, map_name, round_num, tag)"""
    maps_dict, pending, counts = {}, {}, {}
    for match_id, gsid, map_name, rn, tag in rows:
        StopwatchScoringService._pair_round(
            maps_dict, pending, counts,
            match_id=match_id, gaming_session_id=gsid,
            map_name=map_name, round_num=rn, round_data={'tag': tag},
        )
    return maps_dict


def _complete(maps_dict):
    return [m for m in maps_dict.values() if m['round1'] and m['round2']]


def test_repeated_map_is_two_separate_matches():
    maps = _pair([
        ("m1", 9, "et_brewdog", 1, "a1"), ("m1", 9, "et_brewdog", 2, "a2"),
        ("m2", 9, "et_brewdog", 1, "b1"), ("m2", 9, "et_brewdog", 2, "b2"),
    ])
    done = _complete(maps)
    assert len(done) == 2
    assert {m['round1']['tag'] for m in done} == {"a1", "b1"}


def test_abandoned_r1_does_not_steal_the_next_matches_r2():
    # Old sequential pairing: the abandoned R1 (mX) would swallow m2's R2.
    maps = _pair([
        ("mX", 9, "supply", 1, "abandoned"),
        ("m2", 9, "supply", 1, "real1"), ("m2", 9, "supply", 2, "real2"),
    ])
    done = _complete(maps)
    assert len(done) == 1
    assert done[0]['round1']['tag'] == "real1"
    assert done[0]['round2']['tag'] == "real2"


def test_orphan_r2_with_match_id_never_completes():
    maps = _pair([("mZ", 9, "etl_adlernest", 2, "orphan")])
    assert _complete(maps) == []


def test_duplicate_round_number_keeps_first():
    maps = _pair([
        ("m1", 9, "supply", 1, "first"), ("m1", 9, "supply", 1, "dup"),
        ("m1", 9, "supply", 2, "r2"),
    ])
    done = _complete(maps)
    assert len(done) == 1
    assert done[0]['round1']['tag'] == "first"


def test_legacy_rows_without_match_id_fall_back_sequentially():
    maps = _pair([
        (None, 9, "supply", 1, "l1"), ("", 9, "supply", 2, "l2"),
        (None, 9, "supply", 1, "l3"), (None, 9, "supply", 2, "l4"),
    ])
    done = _complete(maps)
    assert len(done) == 2
    assert {(m['round1']['tag'], m['round2']['tag']) for m in done} == {("l1", "l2"), ("l3", "l4")}


def test_mixed_match_id_and_legacy_do_not_cross_pair():
    maps = _pair([
        ("m1", 9, "supply", 1, "k1"),
        (None, 9, "supply", 1, "legacy1"),
        ("m1", 9, "supply", 2, "k2"),
        (None, 9, "supply", 2, "legacy2"),
    ])
    done = _complete(maps)
    assert {(m['round1']['tag'], m['round2']['tag']) for m in done} == {("k1", "k2"), ("legacy1", "legacy2")}
