"""Session story-arc classifier (TOK H Steber B, Val H3).

classify_session_arc turns a BOX-score map progression into the shape the recap
opens with. It's pure, so these pin each shape to a concrete progression and
lock the boundaries between them (the thresholds are the part that drifts).
"""

from __future__ import annotations

import pytest

from website.backend.services.storytelling.arc import (
    COMEBACK,
    DECISIVE,
    NAIL_BITER,
    STATEMENT,
    TRADE_FEST,
    classify_session_arc,
)


def _maps(*pairs: tuple[int, int]) -> list[dict]:
    """Build a maps list from (alpha_points, beta_points) pairs in play order."""
    return [{"alpha_points": a, "beta_points": b} for a, b in pairs]


def _arc(maps, winner_side):
    a = sum(m["alpha_points"] for m in maps)
    b = sum(m["beta_points"] for m in maps)
    winner_score, loser_score = (a, b) if winner_side == "alpha" else (b, a)
    return classify_session_arc(maps, winner_side, winner_score, loser_score)


def test_statement_when_winner_never_trailed_and_wins_big():
    # gsid 144's real progression: +2,0,+2,+4,+6,+4,+6 → 10-4, never behind.
    maps = _maps((2, 0), (0, 2), (2, 0), (2, 0), (2, 0), (0, 2), (2, 0))
    assert _arc(maps, "alpha") == STATEMENT


def test_comeback_when_winner_was_behind():
    # alpha trails 0-4 then storms back to win 6-4.
    maps = _maps((0, 2), (0, 2), (2, 0), (2, 0), (2, 0))
    assert _arc(maps, "alpha") == COMEBACK


def test_trade_fest_when_lead_crosses_twice():
    # alpha ahead, beta ahead, alpha ahead → 2 lead changes, alpha wins.
    maps = _maps((2, 0), (0, 2), (0, 2), (2, 0), (2, 0), (2, 0))
    assert _arc(maps, "alpha") == TRADE_FEST


def test_nail_biter_when_final_margin_within_two():
    # 8-6 finish, alpha never behind (margin +2,+4,+2,0,+2,0,+2) → close, not a
    # statement, no lead change.
    maps = _maps((2, 0), (2, 0), (0, 2), (0, 2), (2, 0), (0, 2), (2, 0))
    assert _arc(maps, "alpha") == NAIL_BITER


def test_decisive_is_the_middle_ground():
    # alpha never behind, wins by exactly 3 (below the statement threshold of
    # max(4, 40% of 9 ≈ 4)) and never within 2 late → decisive, not statement.
    maps = _maps((2, 0), (2, 0), (0, 2), (2, 0), (0, 1))
    result = _arc(maps, "alpha")
    assert result == DECISIVE


@pytest.mark.parametrize("maps,winner,expected", [
    ([], "alpha", ""),                       # no maps
    (_maps((2, 0)), "alpha", ""),            # single map — nothing to shape
    (_maps((2, 0), (0, 2)), "unknown", ""),  # unknown winner side
])
def test_unshapeable_returns_empty(maps, winner, expected):
    a = sum(m["alpha_points"] for m in maps) if maps else 0
    b = sum(m["beta_points"] for m in maps) if maps else 0
    assert classify_session_arc(maps, winner, max(a, b), min(a, b)) == expected


def test_tie_returns_empty():
    maps = _maps((2, 0), (0, 2))
    assert classify_session_arc(maps, "alpha", 2, 2) == ""


def test_beta_winner_perspective_is_symmetric():
    # Mirror of the comeback case from beta's side.
    maps = _maps((2, 0), (2, 0), (0, 2), (0, 2), (0, 2))
    assert _arc(maps, "beta") == COMEBACK
