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


def _row(t1, t2, winner, gsid=None, map_name="ALL", round_details=None):
    # (team_1_guids, team_2_guids, winning_team, gaming_session_id,
    #  map_name, round_details) — mirrors the production SELECT.
    return (json.dumps(t1), json.dumps(t2), winner, gsid, map_name, round_details)


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
                    (1, json.dumps(A), json.dumps(B), _Ts(1000)),   # inside session 101
                    # BETWEEN sessions → must match the FOLLOWING session (102),
                    # not the nearest-by-distance previous one (Codex #511).
                    (2, json.dumps(A), json.dumps(B), _Ts(2000)),
                ]
            if "FROM rounds" in query:
                return [(101, 900, 1100), (102, 4900, 5100)]  # two session windows
            if "FROM session_results" in query:
                return [
                    _row(A, B, 1, gsid=101),  # session 101: A wins
                    _row(A, B, 2, gsid=102),  # session 102: B wins
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


# ── intra-session rematch split via round_details (IMP-002) ──────────


def _details_v2(entries):
    return json.dumps({"round_details_version": 2, "maps": entries})


class RematchDB:
    """One gaming session, TWO same-roster predictions, one ALL summary row."""

    def __init__(self, results, preds=None, rounds_rows=None):
        self.results = results
        self.preds = preds or [
            (1, json.dumps(A), json.dumps(B), _Ts(1000)),
            (2, json.dumps(A), json.dumps(B), _Ts(4000)),
        ]
        self.rounds_rows = rounds_rows or []
        self.updates = []

    async def fetch_all(self, query, params=()):
        if "FROM match_predictions" in query:
            return self.preds
        if "MIN(round_start_unix)" in query:
            return [(101, 900, 6000)]  # session window
        if "round_number, round_start_unix, match_id" in query:
            return self.rounds_rows  # _session_match_starts alignment query
        if "FROM session_results" in query:
            return self.results
        return []

    async def fetch_one(self, query, params=()):
        if "team_a_win_probability" in query:
            return (0.6, 0.4)
        return None

    async def execute(self, query, params=()):
        if "UPDATE match_predictions" in query and "actual_winner" in query:
            self.updates.append(params)


@pytest.mark.asyncio
async def test_rematch_split_v2_details_straight():
    """Codex repro (IMP-002): two rematches in ONE gaming session — first won
    by A, second by B — must resolve to DIFFERENT outcomes via the per-map
    round_details, never the session aggregate (which would make both 2:2)."""
    details = _details_v2([
        {"map": "supply", "team_a_points": 2, "team_b_points": 0,
         "counted": True, "round_start_unix": 1500},
        {"map": "radar", "team_a_points": 0, "team_b_points": 2,
         "counted": True, "round_start_unix": 4500},
    ])
    db = RematchDB([_row(A, B, 0, gsid=101, round_details=details)])
    n = await PredictionEngine(db).auto_resolve_predictions("2026-07-07")
    assert n == 2
    actual_by_id = {p[-1]: (p[0], p[1], p[2]) for p in db.updates}
    assert actual_by_id[1] == (1, 1, 0)  # first match → A
    assert actual_by_id[2] == (2, 0, 1)  # second match → B (not a shared tie)


@pytest.mark.asyncio
async def test_rematch_split_flipped_orientation():
    """team_1 of the summary row is prediction-B → per-map points must be
    re-oriented before the tally."""
    details = _details_v2([
        {"map": "supply", "team1_points": 2, "team2_points": 0,
         "counted": True, "round_start_unix": 1500},
        {"map": "radar", "team1_points": 2, "team2_points": 0,
         "counted": True, "round_start_unix": 4500},
    ])
    # Row stores B as team_1 → team1_points belong to prediction-B.
    db = RematchDB([_row(B, A, 0, gsid=101, round_details=details)])
    n = await PredictionEngine(db).auto_resolve_predictions("2026-07-07")
    assert n == 2
    actual_by_id = {p[-1]: p[0] for p in db.updates}
    assert actual_by_id[1] == 2 and actual_by_id[2] == 2  # B won both matches


@pytest.mark.asyncio
async def test_rematch_defers_on_missing_points():
    details = _details_v2([
        {"map": "supply", "counted": True, "round_start_unix": 1500},  # no points
        {"map": "radar", "team_a_points": 2, "team_b_points": 0,
         "counted": True, "round_start_unix": 4500},
    ])
    db = RematchDB([_row(A, B, 0, gsid=101, round_details=details)])
    assert await PredictionEngine(db).auto_resolve_predictions("2026-07-07") == 0
    assert db.updates == []  # whole group deferred, nothing written


@pytest.mark.asyncio
async def test_rematch_defers_on_map_before_first_prediction():
    details = _details_v2([
        {"map": "supply", "team_a_points": 2, "team_b_points": 0,
         "counted": True, "round_start_unix": 500},  # BEFORE pred 1 (t=1000)
        {"map": "radar", "team_a_points": 0, "team_b_points": 2,
         "counted": True, "round_start_unix": 4500},
    ])
    db = RematchDB([_row(A, B, 0, gsid=101, round_details=details)])
    assert await PredictionEngine(db).auto_resolve_predictions("2026-07-07") == 0
    assert db.updates == []


@pytest.mark.asyncio
async def test_rematch_v1_details_align_against_rounds():
    """Legacy v1 details (bare list, no times) align exactly against the
    session's complete round pairs; order+names must match, times come from
    rounds — then the split works."""
    details = json.dumps([  # v1: bare list, team1/team2 keys, no times
        {"map": "supply", "team1_points": 2, "team2_points": 0},
        {"map": "radar", "team1_points": 0, "team2_points": 2},
    ])
    rounds_rows = [
        ("supply", 1, 1500, "m1"), ("supply", 2, 1600, "m1"),
        ("radar", 1, 4500, "m2"), ("radar", 2, 4600, "m2"),
    ]
    # Untagged second result forces results_tagged with 2 gsids → multi-session
    # path assigns target_gsid=101 via the window; alignment then uses rounds.
    other = _row(["XXXX0000x"], ["YYYY0000x"], 1, gsid=202)
    db = RematchDB(
        [_row(A, B, 0, gsid=101, round_details=details), other],
        rounds_rows=rounds_rows,
    )
    n = await PredictionEngine(db).auto_resolve_predictions("2026-07-07")
    assert n == 2
    actual_by_id = {p[-1]: p[0] for p in db.updates}
    assert actual_by_id[1] == 1 and actual_by_id[2] == 2


@pytest.mark.asyncio
async def test_rematch_v1_defers_on_alignment_mismatch():
    details = json.dumps([
        {"map": "supply", "team1_points": 2, "team2_points": 0},
        {"map": "goldrush", "team1_points": 0, "team2_points": 2},  # ≠ rounds
    ])
    rounds_rows = [
        ("supply", 1, 1500, "m1"), ("supply", 2, 1600, "m1"),
        ("radar", 1, 4500, "m2"), ("radar", 2, 4600, "m2"),
    ]
    other = _row(["XXXX0000x"], ["YYYY0000x"], 1, gsid=202)
    db = RematchDB(
        [_row(A, B, 0, gsid=101, round_details=details), other],
        rounds_rows=rounds_rows,
    )
    assert await PredictionEngine(db).auto_resolve_predictions("2026-07-07") == 0
    assert db.updates == []


@pytest.mark.asyncio
async def test_rematch_flipped_prediction_row_gets_reoriented_outcome():
    """The group key is orientation-independent, so a second prediction row may
    store the same rosters with A/B SWAPPED (voice ordering). Its outcome must
    be re-oriented to its own A/B — not inherit the first row's orientation
    (Codex on #517)."""
    details = _details_v2([
        {"map": "supply", "team_a_points": 2, "team_b_points": 0,
         "counted": True, "round_start_unix": 1500},
        {"map": "radar", "team_a_points": 2, "team_b_points": 0,
         "counted": True, "round_start_unix": 4500},
    ])
    preds = [
        (1, json.dumps(A), json.dumps(B), _Ts(1000)),
        (2, json.dumps(B), json.dumps(A), _Ts(4000)),  # SWAPPED orientation
    ]
    db = RematchDB([_row(A, B, 0, gsid=101, round_details=details)], preds=preds)
    n = await PredictionEngine(db).auto_resolve_predictions("2026-07-07")
    assert n == 2
    by_id = {p[-1]: (p[0], p[1], p[2]) for p in db.updates}
    assert by_id[1] == (1, 1, 0)  # roster-A won match 1; row 1's A IS roster-A
    assert by_id[2] == (2, 0, 1)  # roster-A won match 2 → row 2's OWN A lost


@pytest.mark.asyncio
async def test_rematch_single_session_adopts_gsid_for_v1_alignment():
    """A single-session date never sets target_gsid, but the matched ALL row
    carries the session id — the v1 alignment path must adopt it instead of
    deferring the common one-session rematch (Codex on #517)."""
    details = json.dumps([  # v1: no times → needs alignment
        {"map": "supply", "team1_points": 2, "team2_points": 0},
        {"map": "radar", "team1_points": 0, "team2_points": 2},
    ])
    rounds_rows = [
        ("supply", 1, 1500, "m1"), ("supply", 2, 1600, "m1"),
        ("radar", 1, 4500, "m2"), ("radar", 2, 4600, "m2"),
    ]
    # ONLY one session's results → multi_session is False, target_gsid None.
    db = RematchDB(
        [_row(A, B, 0, gsid=101, round_details=details)],
        rounds_rows=rounds_rows,
    )
    n = await PredictionEngine(db).auto_resolve_predictions("2026-07-07")
    assert n == 2
    by_id = {p[-1]: p[0] for p in db.updates}
    assert by_id[1] == 1 and by_id[2] == 2


@pytest.mark.asyncio
async def test_rematch_zero_start_sentinel_falls_back_to_alignment():
    """round_start_unix=0 is this codebase's missing-timestamp sentinel — a v2
    entry carrying it must be treated as timeless (alignment path), never
    compared against real prediction timestamps (Copilot on #517)."""
    details = _details_v2([
        {"map": "supply", "team_a_points": 2, "team_b_points": 0,
         "counted": True, "round_start_unix": 0},  # sentinel, NOT a real time
        {"map": "radar", "team_a_points": 0, "team_b_points": 2,
         "counted": True, "round_start_unix": 4500},
    ])
    rounds_rows = [
        ("supply", 1, 1500, "m1"), ("supply", 2, 1600, "m1"),
        ("radar", 1, 4500, "m2"), ("radar", 2, 4600, "m2"),
    ]
    db = RematchDB(
        [_row(A, B, 0, gsid=101, round_details=details)],
        rounds_rows=rounds_rows,
    )
    n = await PredictionEngine(db).auto_resolve_predictions("2026-07-07")
    assert n == 2
    by_id = {p[-1]: p[0] for p in db.updates}
    assert by_id[1] == 1 and by_id[2] == 2  # times came from rounds, not the 0


@pytest.mark.asyncio
async def test_rematch_defers_when_pair_start_partially_missing():
    """A complete R1/R2 pair where only ONE round has a usable start must
    defer: with a rematch beginning between R1 and R2, the surviving timestamp
    could place the map in the wrong prediction window (Codex/Copilot #517)."""
    details = json.dumps([
        {"map": "supply", "team1_points": 2, "team2_points": 0},
        {"map": "radar", "team1_points": 0, "team2_points": 2},
    ])
    rounds_rows = [
        ("supply", 1, 0, "m1"), ("supply", 2, 1600, "m1"),  # R1 start missing
        ("radar", 1, 4500, "m2"), ("radar", 2, 4600, "m2"),
    ]
    db = RematchDB(
        [_row(A, B, 0, gsid=101, round_details=details)],
        rounds_rows=rounds_rows,
    )
    assert await PredictionEngine(db).auto_resolve_predictions("2026-07-07") == 0
    assert db.updates == []
