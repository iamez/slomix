# ruff: noqa: SLF001  (testi namenoma sežejo v privatne dele zanke)
"""The safety net for Kill Impact Scores.

KIS used to be computed only as a side effect of a voice session ending. Every
way that trigger can be missed — bot restart, missing INTERNAL_API_SECRET, a
swallowed fire-and-forget exception, nobody in voice, rounds importing after the
warm already ran — left a session with no scores, permanently, because nothing
reconciled afterwards.

Measured on production 2026-08-16: three sessions with kills and ZERO scores
(138 with 1,396 kills, 124 with 542, 127 with 82) plus one partial (144:
490/507). Session 138 rendered the Smart Stats page empty for a 22-round night
while every one of its kills sat in proximity_kill_outcome.

These tests pin the loop's judgement — which sessions it acts on, which it
leaves alone, and that it stops instead of retrying a hopeless one forever.
"""
from __future__ import annotations

import pytest

from bot.services.monitor_tasks_mixin import _MonitorTasksMixin


class FakeVoiceService:
    def __init__(self, fail: bool = False):
        self.calls: list[tuple] = []
        self.fail = fail

    async def warm_kis_cache(self, session_date, gaming_session_id=None):
        self.calls.append((session_date, gaming_session_id))
        if self.fail:
            raise RuntimeError("website unreachable")


class FakeDB:
    def __init__(self, rows):
        self.rows = rows
        self.queries: list[str] = []

    async def fetch_all(self, query, params=()):
        self.queries.append(query)
        return self.rows


class Bot(_MonitorTasksMixin):
    """Just enough bot for the loop: the mixin only touches these two."""

    def __init__(self, rows, fail: bool = False):
        self.db_adapter = FakeDB(rows)
        self.voice_session_service = FakeVoiceService(fail=fail)


async def test_a_session_with_no_scores_is_recomputed():
    bot = Bot([(138, "2026-07-21", 1396, 0)])

    await _MonitorTasksMixin.kis_coverage_reconcile.coro(bot)

    assert bot.voice_session_service.calls == [("2026-07-21", 138)]


async def test_a_partially_scored_session_is_recomputed_too():
    """490 of 507 is not "close enough": the missing 17 kills are 17 kills."""
    bot = Bot([(144, "2026-08-11", 507, 490)])

    await _MonitorTasksMixin.kis_coverage_reconcile.coro(bot)

    assert bot.voice_session_service.calls == [("2026-08-11", 144)]


async def test_nothing_happens_when_every_session_is_complete():
    bot = Bot([])

    await _MonitorTasksMixin.kis_coverage_reconcile.coro(bot)

    assert bot.voice_session_service.calls == []


async def test_one_pass_is_bounded():
    """A backlog must not become one burst of recomputes against the website."""
    rows = [(n, "2026-07-21", 100, 0) for n in range(200, 190, -1)]
    bot = Bot(rows)

    await _MonitorTasksMixin.kis_coverage_reconcile.coro(bot)

    assert len(bot.voice_session_service.calls) == _MonitorTasksMixin._KIS_RECONCILE_MAX_PER_PASS


async def test_a_hopeless_session_is_eventually_left_alone():
    """If recomputing does not close the gap, the loop must stop rather than
    retry the same session every 15 minutes until the logs are useless."""
    bot = Bot([(138, "2026-07-21", 1396, 0)])

    for _ in range(_MonitorTasksMixin._KIS_RECONCILE_MAX_ATTEMPTS + 3):
        await _MonitorTasksMixin.kis_coverage_reconcile.coro(bot)

    assert len(bot.voice_session_service.calls) == _MonitorTasksMixin._KIS_RECONCILE_MAX_ATTEMPTS


async def test_a_failing_recompute_does_not_kill_the_loop():
    """The website being down must not stop the other sessions being tried, and
    must not raise out of a discord.ext task (which would stop the loop)."""
    rows = [(138, "2026-07-21", 1396, 0), (127, "2026-06-21", 82, 0)]
    bot = Bot(rows, fail=True)

    await _MonitorTasksMixin.kis_coverage_reconcile.coro(bot)

    assert len(bot.voice_session_service.calls) == 2


async def test_a_broken_query_does_not_raise_out_of_the_loop():
    class ExplodingDB:
        async def fetch_all(self, *_a, **_k):
            raise RuntimeError("relation does not exist")

    bot = Bot([])
    bot.db_adapter = ExplodingDB()

    await _MonitorTasksMixin.kis_coverage_reconcile.coro(bot)   # must not raise

    assert bot.voice_session_service.calls == []


def test_the_gap_query_uses_the_canonical_round_key():
    """The compute filters by (round_start_unix, map_name, round_number). If the
    detector asked a different question — by round_id, say — it would disagree
    with the thing it triggers: session 138's kills are all round_id NULL yet
    fully present under the canonical key."""
    import inspect

    src = inspect.getsource(_MonitorTasksMixin._find_kis_coverage_gaps)

    for column in ("round_start_unix", "map_name", "round_number"):
        assert column in src
    assert "round_id" not in src


@pytest.mark.parametrize("attr,minimum", [
    ("_KIS_RECONCILE_LOOKBACK_DAYS", 1),
    ("_KIS_RECONCILE_MAX_PER_PASS", 1),
    ("_KIS_RECONCILE_MAX_ATTEMPTS", 1),
])
def test_the_knobs_are_sane(attr, minimum):
    assert getattr(_MonitorTasksMixin, attr) >= minimum
