"""auto_resolve_predictions — B4 phase 2 groundwork.

Predictions must resolve against session_results WITHOUT the manual admin
command: roster orientation detection (prediction A may be results team 2),
BOX-canon map-win tally, draws net-zero, and a real-match guard so a
coincidental one-player overlap never resolves a prediction.
"""
from __future__ import annotations

import json

import pytest

from bot.services.prediction_engine import PredictionEngine

A = ["AAAA1111x", "BBBB2222x", "CCCC3333x"]
B = ["DDDD4444x", "EEEE5555x", "FFFF6666x"]


class FakeDB:
    def __init__(self, results):
        self.results = results
        self.updates = []

    async def fetch_all(self, query, params=()):
        if "FROM match_predictions" in query:
            # (id, team_a_guids, team_b_guids, prediction_time)
            return [(7, json.dumps(A), json.dumps(B), None)]
        if "FROM session_results" in query:
            return self.results
        # rounds gaming-session windows query → single/untagged path
        return []

    async def fetch_one(self, query, params=()):
        if "team_a_win_probability" in query:
            return (0.62, 0.38)  # engine predicted A
        return None

    async def execute(self, query, params=()):
        if "UPDATE match_predictions" in query:
            self.updates.append(params)


def _row(t1, t2, winner, gsid=None):
    # (team_1_guids, team_2_guids, winning_team, gaming_session_id)
    return (json.dumps(t1), json.dumps(t2), winner, gsid)


@pytest.mark.asyncio
async def test_resolves_with_orientation_flip_and_draws():
    # map1: straight orientation, team1(=A) wins; map2: FLIPPED, team1(=B)
    # wins -> B map; map3 draw -> net zero. A 1 : 1 B -> toss-up (0).
    db = FakeDB([
        _row(A, B, 1),
        _row(B, A, 1),
        _row(A, B, 0),
    ])
    n = await PredictionEngine(db).auto_resolve_predictions("2026-07-07")
    assert n == 1
    (actual, a_score, b_score, correct, _acc, brier, pred_id) = db.updates[0]
    assert pred_id == 7
    assert (actual, a_score, b_score) == (0, 1, 1)
    assert correct is False  # engine leaned A, session was a tie
    assert brier is None  # draws are excluded from binary calibration


@pytest.mark.asyncio
async def test_clear_winner_marks_correct():
    db = FakeDB([_row(A, B, 1), _row(B, A, 2)])  # A wins both orientations
    n = await PredictionEngine(db).auto_resolve_predictions("2026-07-07")
    assert n == 1
    (actual, a_score, b_score, correct, _acc, brier, _id) = db.updates[0]
    assert (actual, a_score, b_score, correct) == (1, 2, 0, True)
    assert brier == pytest.approx((1.0 - 0.62) ** 2)


@pytest.mark.asyncio
async def test_coincidental_overlap_does_not_resolve():
    stranger_map = _row(["AAAA1111x", "XXXX0000x", "YYYY0000x"],
                        ["ZZZZ0000x", "QQQQ0000x", "WWWW0000x"], 1)
    db = FakeDB([stranger_map])
    n = await PredictionEngine(db).auto_resolve_predictions("2026-07-07")
    assert n == 0 and db.updates == []


@pytest.mark.asyncio
async def test_no_results_yet_is_a_noop():
    db = FakeDB([])
    assert await PredictionEngine(db).auto_resolve_predictions("2026-07-07") == 0


class _Ts:
    """Minimal prediction_time stand-in with .timestamp() (tz-safe for tests)."""
    def __init__(self, ts: float):
        self._ts = ts
    def timestamp(self) -> float:
        return self._ts


@pytest.mark.asyncio
async def test_multi_session_resolves_per_gaming_session():
    """Two gaming sessions on one date → each prediction resolves against ITS
    session's tagged results, not the whole-date aggregate (Codex P1 #511)."""
    class MultiDB:
        def __init__(self):
            self.updates = []

        async def fetch_all(self, query, params=()):
            if "FROM match_predictions" in query:
                return [
                    (1, json.dumps(A), json.dumps(B), _Ts(1000)),   # in session 101
                    (2, json.dumps(A), json.dumps(B), _Ts(5000)),   # in session 102
                ]
            if "FROM rounds" in query:
                return [(101, 900, 1100), (102, 4900, 5100)]  # two session windows
            if "FROM session_results" in query:
                return [
                    (json.dumps(A), json.dumps(B), 1, 101),  # session 101: A wins
                    (json.dumps(A), json.dumps(B), 2, 102),  # session 102: B wins
                ]
            return []

        async def fetch_one(self, query, params=()):
            if "team_a_win_probability" in query:
                return (0.6, 0.4)
            return None

        async def execute(self, query, params=()):
            if "UPDATE match_predictions" in query and "actual_winner" in query:
                self.updates.append(params)

    db = MultiDB()
    n = await PredictionEngine(db).auto_resolve_predictions("2026-07-07")
    assert n == 2
    actual_by_id = {p[-1]: p[0] for p in db.updates}
    assert actual_by_id[1] == 1  # session 101 → Team A won
    assert actual_by_id[2] == 2  # session 102 → Team B won (NOT the aggregate)
