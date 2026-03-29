"""Unit tests for BOXScoringService — pure scoring logic.

Tests get_expected_alpha_side and score_map with RoundResult dataclass.
No database required.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.services.box_scoring_service import (
    BOXScoringService,
    RoundResult,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_round(
    map_number=1,
    round_number=1,
    map_name="goldrush",
    winner_team=1,
    defender_team=2,
    is_fullhold=False,
    actual_time_seconds=300,
    time_limit_seconds=600,
    round_id=None,
) -> RoundResult:
    return RoundResult(
        map_number=map_number,
        round_number=round_number,
        map_name=map_name,
        winner_team=winner_team,
        defender_team=defender_team,
        is_fullhold=is_fullhold,
        actual_time_seconds=actual_time_seconds,
        time_limit_seconds=time_limit_seconds,
        round_id=round_id,
    )


def _service():
    return BOXScoringService(db_adapter=AsyncMock())


# ===========================================================================
# get_expected_alpha_side
# ===========================================================================

class TestGetExpectedAlphaSide:
    """Side alternation: odd maps alpha=axis R1, even maps alpha=allies R1."""

    def test_odd_map_r1_axis(self):
        svc = _service()
        assert svc.get_expected_alpha_side(1, 1) == 1  # axis

    def test_odd_map_r2_allies(self):
        svc = _service()
        assert svc.get_expected_alpha_side(1, 2) == 2  # allies

    def test_even_map_r1_allies(self):
        svc = _service()
        assert svc.get_expected_alpha_side(2, 1) == 2  # allies

    def test_even_map_r2_axis(self):
        svc = _service()
        assert svc.get_expected_alpha_side(2, 2) == 1  # axis

    def test_map3_r1(self):
        svc = _service()
        assert svc.get_expected_alpha_side(3, 1) == 1

    def test_map3_r2(self):
        svc = _service()
        assert svc.get_expected_alpha_side(3, 2) == 2

    def test_map4_r1(self):
        svc = _service()
        assert svc.get_expected_alpha_side(4, 1) == 2

    def test_map4_r2(self):
        svc = _service()
        assert svc.get_expected_alpha_side(4, 2) == 1

    def test_map5_r1(self):
        svc = _service()
        assert svc.get_expected_alpha_side(5, 1) == 1

    def test_map6_r2(self):
        svc = _service()
        assert svc.get_expected_alpha_side(6, 2) == 1


# ===========================================================================
# score_map
# ===========================================================================

class TestScoreMapR2Winner:
    """R2 winner takes the map — 2 points."""

    def test_alpha_wins_r2(self):
        """Alpha wins R2 => alpha gets 2 points."""
        svc = _service()
        r1 = _make_round(map_number=1, round_number=1, winner_team=2)  # beta wins r1
        r2 = _make_round(map_number=1, round_number=2, winner_team=2)  # alpha side in R2 is allies(2)
        # For map 1: alpha_side_r1=1(axis), alpha_side_r2=2(allies)
        ms = svc.score_map(r1, r2, alpha_side_r1=1, alpha_side_r2=2)
        assert ms.alpha_points == 2
        assert ms.beta_points == 0
        assert ms.winner == "alpha"

    def test_beta_wins_r2(self):
        """Beta wins R2 => beta gets 2 points."""
        svc = _service()
        r1 = _make_round(map_number=1, round_number=1, winner_team=1)
        r2 = _make_round(map_number=1, round_number=2, winner_team=1)  # winner=axis(1), alpha_side_r2=2 => beta won
        ms = svc.score_map(r1, r2, alpha_side_r1=1, alpha_side_r2=2)
        assert ms.alpha_points == 0
        assert ms.beta_points == 2
        assert ms.winner == "beta"


class TestScoreMapFullhold:
    """Double fullhold => draw, 1 pt each."""

    def test_double_fullhold_draw(self):
        svc = _service()
        r1 = _make_round(map_number=1, round_number=1, winner_team=2, is_fullhold=True)
        r2 = _make_round(map_number=1, round_number=2, winner_team=1, is_fullhold=True)
        ms = svc.score_map(r1, r2, alpha_side_r1=1, alpha_side_r2=2)
        assert ms.alpha_points == 1
        assert ms.beta_points == 1
        assert ms.winner == "draw"
        assert ms.is_fullhold_draw is True

    def test_r1_fullhold_r2_normal(self):
        """Only R1 is fullhold, R2 has a winner => R2 winner takes 2 pts."""
        svc = _service()
        r1 = _make_round(map_number=1, round_number=1, winner_team=2, is_fullhold=True)
        r2 = _make_round(map_number=1, round_number=2, winner_team=2, is_fullhold=False)
        ms = svc.score_map(r1, r2, alpha_side_r1=1, alpha_side_r2=2)
        assert ms.alpha_points == 2
        assert ms.beta_points == 0
        assert ms.winner == "alpha"


class TestScoreMapR1Only:
    """R1 only (no R2) — provisional or pending."""

    def test_r1_only_fullhold_alpha_defender_wins(self):
        """R1 fullhold, alpha is the winner => provisional 1pt for alpha."""
        svc = _service()
        r1 = _make_round(map_number=1, round_number=1, winner_team=1, is_fullhold=True)
        # alpha_side_r1 = 1 (axis), winner_team = 1 => alpha won R1
        ms = svc.score_map(r1, None, alpha_side_r1=1, alpha_side_r2=2)
        assert ms.alpha_points == 1
        assert ms.beta_points == 0
        assert ms.winner == "provisional"

    def test_r1_only_fullhold_beta_defender_wins(self):
        """R1 fullhold, beta is the winner => provisional 1pt for beta."""
        svc = _service()
        r1 = _make_round(map_number=1, round_number=1, winner_team=2, is_fullhold=True)
        # alpha_side_r1 = 1, winner_team = 2 => beta won R1
        ms = svc.score_map(r1, None, alpha_side_r1=1, alpha_side_r2=2)
        assert ms.alpha_points == 0
        assert ms.beta_points == 1
        assert ms.winner == "provisional"

    def test_r1_only_no_fullhold_pending(self):
        """R1 without fullhold and no R2 => pending, no points."""
        svc = _service()
        r1 = _make_round(map_number=1, round_number=1, winner_team=1, is_fullhold=False)
        ms = svc.score_map(r1, None, alpha_side_r1=1, alpha_side_r2=2)
        assert ms.alpha_points == 0
        assert ms.beta_points == 0
        assert ms.winner == "pending"


class TestScoreMapUnknownWinner:
    """R2 winner_team=0 (unknown) => 1pt each."""

    def test_unknown_r2_winner_split(self):
        svc = _service()
        r1 = _make_round(map_number=1, round_number=1, winner_team=1)
        r2 = _make_round(map_number=1, round_number=2, winner_team=0)  # unknown
        ms = svc.score_map(r1, r2, alpha_side_r1=1, alpha_side_r2=2)
        assert ms.alpha_points == 1
        assert ms.beta_points == 1
        assert ms.winner == "draw"

    def test_both_unknown_winners_split(self):
        svc = _service()
        r1 = _make_round(map_number=1, round_number=1, winner_team=0)
        r2 = _make_round(map_number=1, round_number=2, winner_team=0)
        ms = svc.score_map(r1, r2, alpha_side_r1=1, alpha_side_r2=2)
        assert ms.alpha_points == 1
        assert ms.beta_points == 1
        assert ms.winner == "draw"


class TestScoreMapTimingFields:
    """r1_time and r2_time are populated from rounds."""

    def test_times_populated(self):
        svc = _service()
        r1 = _make_round(actual_time_seconds=300)
        r2 = _make_round(round_number=2, actual_time_seconds=450)
        ms = svc.score_map(r1, r2, alpha_side_r1=1, alpha_side_r2=2)
        assert ms.r1_time == 300
        assert ms.r2_time == 450

    def test_r1_only_r2_time_zero(self):
        svc = _service()
        r1 = _make_round(actual_time_seconds=300)
        ms = svc.score_map(r1, None, alpha_side_r1=1, alpha_side_r2=2)
        assert ms.r1_time == 300
        assert ms.r2_time == 0


class TestScoreMapMapNameAndNumber:
    """MapScore inherits map_name and map_number from R1."""

    def test_map_fields(self):
        svc = _service()
        r1 = _make_round(map_number=3, map_name="oasis")
        r2 = _make_round(map_number=3, round_number=2, map_name="oasis", winner_team=1)
        ms = svc.score_map(r1, r2, alpha_side_r1=1, alpha_side_r2=2)
        assert ms.map_number == 3
        assert ms.map_name == "oasis"
