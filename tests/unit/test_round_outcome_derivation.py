"""round_outcome derived from winner/defender at the source (audit 2026-08-14).

The stored round_outcome used to be a pure time heuristic (map_time −
actual_time ≤ 30 s → "Fullhold"), mislabeling every objective completed in the
final 30 seconds — 31% of stored 'Fullhold' rows contradicted their own
winner_team (e.g. supply 2026-08-02 R1: header ``\\1\\2\\12:00\\11:57`` =
attackers completed with 3 s to spare, labeled "Fullhold"). The canonical rule
now lives in round_contract.derive_round_outcome: winner==defender when the
parsed sides are trusted; the time heuristic only as fallback.
"""
from bot.community_stats_parser import C0RNP0RN3StatsParser
from bot.core.round_contract import (
    TRUSTED_SCORE_CONFIDENCE,
    derive_round_outcome,
)


# -- winner-based rule (sides trusted) --------------------------------------

def test_attacker_win_in_final_30s_is_completed():
    # The gsid-141 supply case: winner=2, defender=1, 11:57 of 12:00.
    assert derive_round_outcome(2, 1, "12:00", "11:57", 1, sides_trusted=True) == "Completed"


def test_defender_hold_is_fullhold_even_with_time_left():
    # Defenders can win via attacker surrender well before the limit.
    assert derive_round_outcome(1, 1, "12:00", "10:43", 2, sides_trusted=True) == "Fullhold"


def test_untrusted_sides_fall_back_to_time_heuristic():
    # Same numbers as the supply case, but sides untrusted → heuristic says
    # Fullhold (3 s margin). This is the documented legacy fallback.
    assert derive_round_outcome(2, 1, "12:00", "11:57", 1, sides_trusted=False) == "Fullhold"


def test_unknown_winner_falls_back_even_when_trusted_flag_set():
    # winner=0 → the winner rule cannot apply regardless of the flag.
    assert derive_round_outcome(0, 1, "12:00", "5:00", 1, sides_trusted=True) == "Completed"


# -- fallback heuristic keeps exact legacy semantics ------------------------

def test_fallback_r2_zero_actual_is_unknown():
    assert derive_round_outcome(0, 0, "10:00", "0:00", 2, sides_trusted=False) == "Unknown"


def test_fallback_r1_zero_actual_gets_no_carveout():
    assert derive_round_outcome(0, 0, "10:00", "0:00", 1, sides_trusted=False) == "Completed"


def test_fallback_unparseable_time_is_unknown():
    assert derive_round_outcome(0, 0, "garbage", "5:00", 1, sides_trusted=False) == "Unknown"


def test_parser_method_delegates_to_shared_fallback():
    p = C0RNP0RN3StatsParser()
    assert p.determine_round_outcome("10:00", "9:35", 1) == "Fullhold"
    assert p.determine_round_outcome("10:00", "5:00", 1) == "Completed"
    assert p.determine_round_outcome("10:00", "0:00", 2) == "Unknown"


# -- trust gate constant -----------------------------------------------------

def test_trusted_states_are_the_two_side_resolving_ones():
    assert set(TRUSTED_SCORE_CONFIDENCE) == {"verified_header", "time_fallback"}
