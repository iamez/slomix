"""GoodNightService — Phase 1 of the Good Night Engine plan (family 1).

FakeDB dispatches on query content, per the established unit-test pattern.
"""
from __future__ import annotations

import json

import pytest

from website.backend.services.good_night_service import GoodNightService


class FakeDB:
    def __init__(self, *, rounds=None, details=None, players=5, moments=0,
                 invalid=0, votes=0, bets=0):
        self.rounds = rounds or []
        self.details = details
        self.players = players
        self.moments = moments
        self.invalid = invalid
        self.votes = votes
        self.bets = bets

    async def fetch_all(self, q, params=()):
        assert "FROM rounds" in q
        return self.rounds

    async def fetch_one(self, q, params=()):
        if "round_details" in q:
            return (json.dumps(self.details),) if self.details is not None else None
        if "COUNT(DISTINCT p.player_guid)" in q:
            return (self.players,)
        if "storytelling_kill_impact" in q:
            return (self.moments,)
        if "is_valid IS FALSE" in q:
            return (self.invalid,)
        if "session_mvp_votes" in q:
            return (self.votes,)
        if "parimutuel_bets" in q:
            return (self.bets,)
        raise AssertionError(f"Unexpected fetch_one: {q[:80]}")


def _rounds(n_maps, secs_diff=0, base=1_751_300_000):
    rows = []
    for i in range(n_maps):
        s = base + i * 900
        rows.append((1, f"m{i}", f"map{i}", 300, s))
        rows.append((2, f"m{i}", f"map{i}", 300 + secs_diff, s + 400))
    return rows


@pytest.mark.asyncio
async def test_unavailable_without_complete_matches():
    svc = GoodNightService(FakeDB(rounds=[(1, "m1", "supply", 300, 1_751_300_000)]))
    assert await svc.compute(9) is None


@pytest.mark.asyncio
async def test_close_night_scores_high_with_safe_reasons():
    details = [{"team_a_points": 2, "team_b_points": 0}] * 3 \
        + [{"team_a_points": 0, "team_b_points": 2}] * 3 \
        + [{"team_a_points": 1, "team_b_points": 1}]
    svc = GoodNightService(FakeDB(
        rounds=_rounds(7, secs_diff=10), details=details,
        players=8, moments=120, votes=3, bets=2))
    out = await svc.compute(131)
    assert out["score"] >= 75
    assert out["components"]["balance"] >= 90
    assert out["maps"] == 7 and out["players"] == 8
    assert "close teams" in out["reasons"]
    assert len(out["reasons"]) <= 5
    # friendship-safe: no negative wording in chips
    assert not any(w in " ".join(out["reasons"]).lower() for w in ("worst", "stomp", "bad"))


@pytest.mark.asyncio
async def test_stomp_night_scores_low():
    details = [{"team_a_points": 0, "team_b_points": 2}] * 5
    svc = GoodNightService(FakeDB(
        rounds=_rounds(5, secs_diff=300), details=details, players=6, moments=0))
    out = await svc.compute(124)
    assert out["score"] <= 55
    assert out["components"]["tension"] == 0


@pytest.mark.asyncio
async def test_missing_details_is_neutral_not_perfect():
    svc = GoodNightService(FakeDB(rounds=_rounds(4), details=None, players=6))
    out = await svc.compute(50)
    # neutral balance (50-based blend), decider bonus gated off
    assert out["components"]["balance"] <= 70
    assert "close teams" not in out["reasons"]
