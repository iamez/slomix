"""Tests for BOXScoringService — Oksii-style stopwatch session scoring.

This service decides who won a multi-map best-of-N session. A regression
in any of:

- side alternation (`get_expected_alpha_side`),
- per-map point allocation (`score_map`),
- session aggregation + winner pick (`calculate_session_score`),

silently corrupts the headline number on the BOX leaderboard. Pin the
contract for all three.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from website.backend.services.box_scoring_service import (
    BOXScoringService,
    RoundResult,
    SessionScore,
)


def _r(map_num=1, round_num=1, winner=1, defender=2,
       fullhold=False, time=300, limit=600, map_name="oasis"):
    """Build a minimal RoundResult with safe defaults."""
    return RoundResult(
        map_number=map_num, round_number=round_num,
        map_name=map_name, winner_team=winner, defender_team=defender,
        is_fullhold=fullhold,
        actual_time_seconds=time, time_limit_seconds=limit,
    )


@pytest.fixture
def svc():
    return BOXScoringService(db_adapter=AsyncMock())


# ---------------------------------------------------------------------------
# get_expected_alpha_side — side alternation table
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("map_num, round_num, expected", [
    # Odd maps (1, 3, 5): R1 alpha=axis(1), R2 alpha=allies(2)
    (1, 1, 1),
    (1, 2, 2),
    (3, 1, 1),
    (3, 2, 2),
    (5, 1, 1),
    (5, 2, 2),
    # Even maps (2, 4, 6): R1 alpha=allies(2), R2 alpha=axis(1)
    (2, 1, 2),
    (2, 2, 1),
    (4, 1, 2),
    (4, 2, 1),
    (6, 1, 2),
    (6, 2, 1),
])
def test_alpha_side_alternates_per_map_and_round(svc, map_num, round_num, expected):
    """Pin the full odd/even × R1/R2 truth table.

    A regression here (e.g., flipping odd/even or R1/R2) would silently
    award R1 fullholds to the wrong team for half of all maps."""
    assert svc.get_expected_alpha_side(map_num, round_num) == expected


# ---------------------------------------------------------------------------
# score_map — single-map scoring
# ---------------------------------------------------------------------------


def test_score_map_r1_only_fullhold_alpha_gets_provisional_point(svc):
    """R1 only + alpha defended (won as defender via fullhold) → +1 alpha
    provisional. Pin so the "match still in progress" case never zeroes
    out the leaderboard for R1-only data."""
    # alpha_side_r1 = 1 (axis); winner=1 means alpha won R1
    r1 = _r(round_num=1, winner=1, fullhold=True)
    ms = svc.score_map(r1, None, alpha_side_r1=1, alpha_side_r2=2)
    assert ms.alpha_points == 1
    assert ms.beta_points == 0
    assert ms.winner == "provisional"


def test_score_map_r1_only_fullhold_beta_gets_provisional_point(svc):
    """Same case with beta defending."""
    r1 = _r(winner=2, fullhold=True)  # alpha_side_r1=1 → beta won
    ms = svc.score_map(r1, None, alpha_side_r1=1, alpha_side_r2=2)
    assert ms.alpha_points == 0
    assert ms.beta_points == 1
    assert ms.winner == "provisional"


def test_score_map_r1_only_no_fullhold_zero_points(svc):
    """R1 only without fullhold → 0/0 (no provisional points; the map
    is still in progress, not a defended win)."""
    r1 = _r(winner=1, fullhold=False)
    ms = svc.score_map(r1, None, alpha_side_r1=1, alpha_side_r2=2)
    assert ms.alpha_points == 0
    assert ms.beta_points == 0
    assert ms.winner == "pending"


def test_score_map_r1_only_unknown_winner_no_points(svc):
    """winner_team=0 (unknown) → no provisional pts, even with fullhold."""
    r1 = _r(winner=0, fullhold=True)
    ms = svc.score_map(r1, None, alpha_side_r1=1, alpha_side_r2=2)
    assert ms.alpha_points == 0
    assert ms.beta_points == 0
    assert ms.winner == "pending"


def test_score_map_double_fullhold_is_a_draw_one_each(svc):
    """Both R1 and R2 are fullholds → 1 pt each. Pinned because the
    "draw" sentinel changes downstream UI badge color and a regression
    that drops it would let the better fullhold defender pull ahead."""
    r1 = _r(map_num=1, round_num=1, winner=1, fullhold=True)  # alpha defended
    r2 = _r(map_num=1, round_num=2, winner=2, fullhold=True)  # alpha-on-allies side, beta defended
    ms = svc.score_map(r1, r2, alpha_side_r1=1, alpha_side_r2=2)
    assert ms.alpha_points == 1
    assert ms.beta_points == 1
    assert ms.winner == "draw"
    assert ms.is_fullhold_draw is True


def test_score_map_alpha_wins_r2_takes_two_points(svc):
    """R2 winner takes the map → +2 to that team."""
    r1 = _r(round_num=1, winner=1, fullhold=False)
    r2 = _r(round_num=2, winner=2, fullhold=False)
    # alpha_side_r2=2 means alpha plays as allies in R2; winner=2 → alpha won
    ms = svc.score_map(r1, r2, alpha_side_r1=1, alpha_side_r2=2)
    assert ms.alpha_points == 2
    assert ms.beta_points == 0
    assert ms.winner == "alpha"


def test_score_map_beta_wins_r2_takes_two_points(svc):
    r1 = _r(round_num=1, winner=1, fullhold=False)
    r2 = _r(round_num=2, winner=1, fullhold=False)
    # alpha_side_r2=2; winner=1 → beta won R2
    ms = svc.score_map(r1, r2, alpha_side_r1=1, alpha_side_r2=2)
    assert ms.alpha_points == 0
    assert ms.beta_points == 2
    assert ms.winner == "beta"


def test_score_map_r2_unknown_winner_splits_points(svc):
    """winner_team=0 in R2 (data missing) → 1/1 split. Pinned fail-safe
    so a missing winner field doesn't zero out a played map."""
    r1 = _r(round_num=1, winner=1, fullhold=False)
    r2 = _r(round_num=2, winner=0, fullhold=False)
    ms = svc.score_map(r1, r2, alpha_side_r1=1, alpha_side_r2=2)
    assert ms.alpha_points == 1
    assert ms.beta_points == 1
    assert ms.winner == "draw"


def test_score_map_r2_only_fullhold_does_not_trigger_double_fullhold(svc):
    """Only R2 was a fullhold (R1 not) → not a draw; standard R2 winner
    picks the map. Pin so the `r1.is_fullhold AND r2.is_fullhold` guard
    is never accidentally relaxed."""
    r1 = _r(round_num=1, winner=1, fullhold=False)
    r2 = _r(round_num=2, winner=2, fullhold=True)
    ms = svc.score_map(r1, r2, alpha_side_r1=1, alpha_side_r2=2)
    # alpha_side_r2=2, winner=2 → alpha wins map
    assert ms.alpha_points == 2
    assert ms.winner == "alpha"
    assert ms.is_fullhold_draw is False


def test_score_map_records_round_times(svc):
    """r1_time and r2_time fields are populated for downstream UI."""
    r1 = _r(round_num=1, winner=1, time=400)
    r2 = _r(round_num=2, winner=2, time=350)
    ms = svc.score_map(r1, r2, alpha_side_r1=1, alpha_side_r2=2)
    assert ms.r1_time == 400
    assert ms.r2_time == 350


# ---------------------------------------------------------------------------
# to_api_response — JSON serialisation contract
# ---------------------------------------------------------------------------


def test_api_response_pins_field_names(svc):
    """The frontend (BOX leaderboard) reads exact field names. A typo
    in any of them would silently zero out the displayed number."""
    score = SessionScore(
        gaming_session_id=42,
        alpha_score=5,
        beta_score=3,
        maps_completed=3,
        alpha_team_name="puran",
        beta_team_name="sWat",
        winner="alpha",
    )
    out = svc.to_api_response(score)
    assert out["status"] == "ok"
    assert out["gaming_session_id"] == 42
    assert out["alpha_team"] == "puran"
    assert out["beta_team"] == "sWat"
    assert out["alpha_score"] == 5
    assert out["beta_score"] == 3
    assert out["maps_completed"] == 3
    assert out["winner"] == "alpha"
    assert out["winner_name"] == "puran"  # resolved from alpha_team_name
    assert out["maps"] == []  # default empty


def test_api_response_winner_name_resolves_to_beta(svc):
    score = SessionScore(
        gaming_session_id=1, beta_team_name="Beta-FC", winner="beta",
    )
    out = svc.to_api_response(score)
    assert out["winner_name"] == "Beta-FC"


def test_api_response_winner_name_is_draw_string():
    svc = BOXScoringService(db_adapter=AsyncMock())
    score = SessionScore(gaming_session_id=1, winner="draw")
    out = svc.to_api_response(score)
    assert out["winner_name"] == "Draw"


def test_api_response_winner_name_is_none_when_no_winner(svc):
    """winner=None (session in progress) → winner_name=None — UI uses
    this to render "Pending" badge instead of a team name."""
    score = SessionScore(gaming_session_id=1, winner=None)
    out = svc.to_api_response(score)
    assert out["winner_name"] is None


# ---------------------------------------------------------------------------
# calculate_session_score — full end-to-end against fake DB
# ---------------------------------------------------------------------------


class _FakeDb:
    """Minimal fake exposing fetch_all to return canned rows."""
    def __init__(self, team_rows=None, round_rows=None):
        self.team_rows = team_rows or []
        self.round_rows = round_rows or []
        self.calls = 0

    async def fetch_all(self, query, params=None):
        self.calls += 1
        if "session_teams" in query:
            return self.team_rows
        return self.round_rows


@pytest.mark.asyncio
async def test_calculate_session_returns_default_when_no_rounds():
    """Empty session → SessionScore with zero score and no winner."""
    svc = BOXScoringService(_FakeDb())
    out = await svc.calculate_session_score(99)
    assert out.alpha_score == 0
    assert out.beta_score == 0
    assert out.winner is None  # no maps_completed → no winner pick
    assert out.maps_completed == 0
    assert out.maps == []


@pytest.mark.asyncio
async def test_calculate_session_uses_team_names_from_db():
    db = _FakeDb(team_rows=[("Team Foo",), ("Team Bar",)])
    svc = BOXScoringService(db)
    out = await svc.calculate_session_score(99)
    assert out.alpha_team_name == "Team Foo"
    assert out.beta_team_name == "Team Bar"


@pytest.mark.asyncio
async def test_calculate_session_keeps_defaults_when_only_one_team_name():
    """One team name from DB → only alpha overridden, beta stays default."""
    db = _FakeDb(team_rows=[("LonelyTeam",)])
    svc = BOXScoringService(db)
    out = await svc.calculate_session_score(99)
    assert out.alpha_team_name == "LonelyTeam"
    assert out.beta_team_name == "Team B"  # default


@pytest.mark.asyncio
async def test_calculate_session_picks_winner_alpha_when_score_higher():
    """alpha_score > beta_score AND maps_completed > 0 → winner='alpha'."""
    # 1 complete map: R1 + R2; alpha wins R2
    rows = [
        # id, map_name, round_number, winner, defender, outcome, duration, time_to_beat
        (1, "oasis", 1, 1, 2, "Stopwatch", 300, 600),
        (2, "oasis", 2, 2, 1, "Stopwatch", 280, 600),  # alpha (allies in R2) wins
    ]
    svc = BOXScoringService(_FakeDb(round_rows=rows))
    out = await svc.calculate_session_score(99)
    # Map 1: odd → alpha=axis in R1, alpha=allies in R2; winner=2 → alpha gets 2 pts
    assert out.alpha_score == 2
    assert out.beta_score == 0
    assert out.maps_completed == 1
    assert out.winner == "alpha"


@pytest.mark.asyncio
async def test_calculate_session_picks_winner_beta_when_higher():
    rows = [
        (1, "oasis", 1, 1, 2, "Stopwatch", 300, 600),
        (2, "oasis", 2, 1, 2, "Stopwatch", 280, 600),  # beta wins R2
    ]
    svc = BOXScoringService(_FakeDb(round_rows=rows))
    out = await svc.calculate_session_score(99)
    assert out.beta_score == 2
    assert out.alpha_score == 0
    assert out.winner == "beta"


@pytest.mark.asyncio
async def test_orphan_r2_does_not_overwrite_previous_map():
    """A dangling/duplicate R2 (no R1 between) must start a fresh map bucket, not
    collapse into and silently overwrite the previous map's real R2."""
    rows = [
        (1, "oasis", 1, 1, 2, "Stopwatch", 300, 600),   # map1 R1
        (2, "oasis", 2, 2, 1, "Stopwatch", 280, 600),   # map1 R2 → alpha takes map (2 pts)
        (3, "supply", 2, 1, 2, "Stopwatch", 290, 600),  # orphan R2, no R1
    ]
    out = await BOXScoringService(_FakeDb(round_rows=rows)).calculate_session_score(99)
    # map1 preserved (alpha 2 pts); orphan R2 lands in its own R1-less bucket and
    # is skipped, so it neither overwrites map1's R2 nor inflates the score.
    assert out.alpha_score == 2
    assert out.beta_score == 0
    assert out.maps_completed == 1


@pytest.mark.asyncio
async def test_calculate_session_winner_is_draw_when_scores_tie():
    """Equal scores AND maps_completed > 0 → winner='draw'.
    Pinned because a regression that drops the explicit 'draw' string
    would let the UI render an empty winner."""
    # Double fullhold scenario gives 1/1
    rows = [
        (1, "oasis", 1, 1, 2, "Fullhold", 600, 600),
        (2, "oasis", 2, 2, 1, "Fullhold", 600, 600),
    ]
    svc = BOXScoringService(_FakeDb(round_rows=rows))
    out = await svc.calculate_session_score(99)
    assert out.alpha_score == 1
    assert out.beta_score == 1
    assert out.maps_completed == 1
    assert out.winner == "draw"


@pytest.mark.asyncio
async def test_calculate_session_provisional_points_dont_count_toward_completion():
    """R1-only fullhold → provisional point but maps_completed stays 0
    → winner stays None. Pin: a session with ONLY R1 data must not
    declare a winner."""
    rows = [
        (1, "oasis", 1, 1, 2, "Fullhold", 600, 600),  # R1 fullhold only
    ]
    svc = BOXScoringService(_FakeDb(round_rows=rows))
    out = await svc.calculate_session_score(99)
    assert out.alpha_score == 1  # provisional
    assert out.maps_completed == 0  # R2 missing
    assert out.winner is None  # no winner declared


@pytest.mark.asyncio
async def test_calculate_session_assigns_sequential_map_numbers_for_repeated_map():
    """Same map_name appearing twice in a session → 2 separate maps.

    Pin: map_number is determined by R1 boundaries, NOT map_name. A
    regression that grouped by map_name would conflate two plays of
    'oasis' into one map score."""
    rows = [
        # First oasis: R1+R2, alpha wins R2
        (1, "oasis", 1, 1, 2, "Stopwatch", 300, 600),
        (2, "oasis", 2, 2, 1, "Stopwatch", 280, 600),
        # Second oasis: R1+R2, beta wins R2
        (3, "oasis", 1, 1, 2, "Stopwatch", 300, 600),
        (4, "oasis", 2, 1, 2, "Stopwatch", 280, 600),
    ]
    svc = BOXScoringService(_FakeDb(round_rows=rows))
    out = await svc.calculate_session_score(99)
    assert out.maps_completed == 2
    assert len(out.maps) == 2
    # Map 1 (odd): alpha won R2; Map 2 (even): alpha is allies in R1, axis in R2
    # Map 2 R2 winner=1 (axis) → alpha wins → 2 pts each
    assert out.alpha_score == 4
    assert out.beta_score == 0
