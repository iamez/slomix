"""The clock's inputs, and the one pairing that must never drift.

`enemy_spawn_interval` belongs to the VICTIM's team. Pairing it with
`killer_team` does not fail loudly — it builds each team's clock from the other
side's interval, which validates nothing and reads exactly like data that has no
wave structure in it. Measured on 400 rounds: `killer_team` gives 0 validated
clocks out of 800 with residuals spread evenly across the interval;
`victim_team` gives 667, median residual 25 ms.

So the test is on the query text as well as the behaviour. A functional test
alone would pass with a stub that returns whatever the code asked for.
"""

from __future__ import annotations

import pytest

from website.backend.services.clock_inputs import (
    clock_validation_payload,
    fetch_clock_lives_and_revives,
    fetch_timing_observations,
    is_bot_player,
    strict_clock_round_gate_sql,
    wave_position,
)
from website.backend.services.reinforcement_clock import (
    ClockValidation,
    circular_residual_ms,
)


class _StubDb:
    """Records the SQL it is handed, and answers from a fixed queue."""

    def __init__(self, *results):
        self.results = list(results)
        self.queries: list[str] = []

    async def fetch_all(self, sql, params=None):
        self.queries.append(sql)
        return self.results.pop(0) if self.results else []


class TestTeamPairing:
    @pytest.mark.asyncio
    async def test_query_selects_victim_team_not_killer_team(self):
        """⚠️ The whole clock rests on this. See the module docstring."""
        db = _StubDb([])
        await fetch_timing_observations(db, 1)
        sql = db.queries[0]
        assert "SELECT victim_team" in sql
        assert "SELECT killer_team" not in sql

    @pytest.mark.asyncio
    async def test_observation_team_comes_from_the_victim_column(self):
        rows = [("ALLIES", 1000, 20000, 5000, 0.5, "GUID1", "player")]
        db = _StubDb(rows)
        observations = await fetch_timing_observations(db, 1)
        assert [o.team for o in observations] == ["ALLIES"]
        assert observations[0].interval_ms == 20000

    @pytest.mark.asyncio
    async def test_round_gate_is_applied(self):
        db = _StubDb([])
        await fetch_timing_observations(db, 1)
        assert "is_bot_round IS DISTINCT FROM TRUE" in db.queries[0]


class TestBotFilter:
    @pytest.mark.parametrize("guid,name,expected", [
        ("OMNIBOT_1", "anything", True),
        ("ABCDEF", "[BOT]Rifleman", True),
        ("omnibot_lower", "x", True),
        ("ABCDEF", "realplayer", False),
        (None, None, False),
    ])
    def test_recognises_bots(self, guid, name, expected):
        assert is_bot_player(guid, name) is expected

    @pytest.mark.asyncio
    async def test_bots_are_dropped_from_timing_observations(self):
        rows = [
            ("ALLIES", 1000, 20000, 5000, 0.5, "OMNIBOT_3", "[BOT]x"),
            ("AXIS", 2000, 30000, 6000, 0.5, "REALGUID", "human"),
        ]
        observations = await fetch_timing_observations(_StubDb(rows), 1)
        assert [o.team for o in observations] == ["AXIS"]

    @pytest.mark.asyncio
    async def test_bots_are_dropped_from_lives_and_revives(self):
        tracks = [
            (1, "OMNIBOT_1", "[BOT]a", "AXIS", 0, 1000, "killed"),
            (2, "REALGUID", "human", "AXIS", 0, 2000, "killed"),
        ]
        revives = [("OMNIBOT_1", "[BOT]a", 500), ("REALGUID", "human", 900)]
        lives, revived, end = await fetch_clock_lives_and_revives(
            _StubDb(tracks, revives), 1
        )
        assert [life.player_guid for life in lives] == ["REALGUID"]
        assert [r.player_guid for r in revived] == ["REALGUID"]
        assert end == 2000


class TestWavePosition:
    @pytest.mark.parametrize("t,interval,offset,expected", [
        # A landing satisfies (L + offset) % interval == 0, so offset=15000 with
        # interval=20000 puts landings at 5000, 25000, 45000 ...
        (5_000, 20_000, 15_000, (0, 20_000)),      # exactly on a landing
        (10_000, 20_000, 15_000, (5_000, 15_000)),
        (24_000, 20_000, 15_000, (19_000, 1_000)),  # just before the next
        (0, 20_000, 15_000, (15_000, 5_000)),
    ])
    def test_phase_and_remaining(self, t, interval, offset, expected):
        assert wave_position(t, interval, offset) == expected

    @pytest.mark.parametrize("interval,offset", [(20_000, 15_000), (30_000, 7_000)])
    def test_a_landing_reports_zero_elapsed(self, interval, offset):
        """⭐ The convention, stated as a property rather than a comment: the
        moments where `circular_residual_ms` is zero are exactly the moments
        where `wave_position` says a wave just landed. Reading `offset` as a
        landing time breaks this and nothing else would notice."""
        for k in range(5):
            landing = (-offset) % interval + k * interval
            assert circular_residual_ms(landing, offset, interval) == 0
            assert wave_position(landing, interval, offset) == (0, interval)

    def test_the_two_always_sum_to_one_interval(self):
        for t in range(0, 60_000, 137):
            since, until = wave_position(t, 20_000, 7_000)
            assert since + until == 20_000
            assert 0 <= since < 20_000


class TestValidationPayload:
    @staticmethod
    def _validation(status: str) -> ClockValidation:
        return ClockValidation(
            team="AXIS", interval_ms=20_000, offset_ms=5_000,
            timing_observation_count=10, landing_count=6,
            spawn_observation_count=20, post_revive_spawn_count=2,
            status=status, passing_landing_count=6, pass_ratio=1.0,
            residuals_ms=(25, 25),
        )

    def test_offset_is_published_only_when_validated(self):
        assert clock_validation_payload(self._validation("validated"))["offset_ms"] == 5000

    @pytest.mark.parametrize("status", [
        "validation_failed", "internally_consistent_unvalidated", "insufficient",
    ])
    def test_an_unvalidated_offset_is_withheld(self, status):
        """§5.2: internally consistent is not the same as known. Publishing the
        number would let a consumer read one as the other."""
        payload = clock_validation_payload(self._validation(status))
        assert payload["offset_ms"] is None
        assert payload["interval_ms"] == 20_000  # the interval is not in doubt


def test_gate_sql_can_be_prefixed_for_a_joined_query():
    assert "clock_round.id = s.round_id" in strict_clock_round_gate_sql("s.")
    assert "clock_round.id = round_id" in strict_clock_round_gate_sql()
