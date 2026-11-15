# ruff: noqa: SLF001 - observe the task's bounded retry and cursor state
"""Bounded retry progress and fair request opportunities, without content identity."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.services.monitor_tasks_mixin import _MonitorTasksMixin

pytestmark = pytest.mark.asyncio


def row(gsid=184, source=458, scored=0):
    return (gsid, "2026-11-12", source, scored)


def bot(rows, *, result=True, error=None):
    instance = _MonitorTasksMixin()
    instance.db_adapter = SimpleNamespace(fetch_all=AsyncMock(return_value=rows))
    instance.voice_session_service = SimpleNamespace(
        warm_kis_cache=AsyncMock(return_value=result, side_effect=error),
    )
    return instance


async def tick(instance, count=1):
    for _ in range(count):
        await _MonitorTasksMixin.kis_coverage_reconcile.coro(instance)


async def exhaust(instance):
    await tick(instance, _MonitorTasksMixin._KIS_RECONCILE_MAX_ATTEMPTS + 1)


async def test_source_arriving_during_each_warm_converges_after_it_settles():
    instance = bot([row(source=68)])
    arrivals = iter([210, 333, 458, None])
    computed = []

    async def warm(*_args, **_kwargs):
        current = instance.db_adapter.fetch_all.return_value[0][2]
        computed.append(current)
        next_count = next(arrivals)
        # The current calculation covers its snapshot; another import commits
        # before the request returns. Each poll must re-observe actual coverage.
        instance.db_adapter.fetch_all.return_value = (
            [row(source=next_count, scored=current)] if next_count else []
        )
        return True

    instance.voice_session_service.warm_kis_cache.side_effect = warm
    await tick(instance, 5)
    assert computed == [68, 210, 333, 458]
    assert instance.db_adapter.fetch_all.return_value == []
    assert not instance._kis_reconcile_attempts


async def test_score_progress_on_unchanged_source_is_not_a_lifetime_attempt_budget():
    instance = bot([row()])
    progress = iter([68, 210, 333, 458])

    async def warm(*_args, **_kwargs):
        scored = next(progress)
        instance.db_adapter.fetch_all.return_value = [row(scored=scored)] if scored < 458 else []
        return True

    instance.voice_session_service.warm_kis_cache.side_effect = warm
    await tick(instance, 5)
    assert instance.voice_session_service.warm_kis_cache.await_count == 4
    assert not instance._kis_reconcile_attempts


@pytest.mark.parametrize("new_source", [99, 101])
async def test_changed_source_count_revives_an_exhausted_gap(new_source):
    instance = bot([row(source=100, scored=40)])
    await exhaust(instance)
    spent = instance.voice_session_service.warm_kis_cache.await_count
    instance.db_adapter.fetch_all.return_value = [row(source=new_source, scored=40)]
    await tick(instance)
    assert instance.voice_session_service.warm_kis_cache.await_count == spent + 1
    assert instance._kis_reconcile_attempts[184] == 1
    assert 184 not in instance._kis_reconcile_abandoned


async def test_observed_score_progress_revives_an_exhausted_gap():
    instance = bot([row(source=100, scored=40)])
    await exhaust(instance)
    spent = instance.voice_session_service.warm_kis_cache.await_count
    instance.db_adapter.fetch_all.return_value = [row(source=100, scored=41)]
    await tick(instance)
    assert instance.voice_session_service.warm_kis_cache.await_count == spent + 1


async def test_score_regression_alone_is_not_progress():
    instance = bot([row(source=100, scored=40)])
    await exhaust(instance)
    spent = instance.voice_session_service.warm_kis_cache.await_count
    instance.db_adapter.fetch_all.return_value = [row(source=100, scored=39)]
    await tick(instance)
    assert instance.voice_session_service.warm_kis_cache.await_count == spent


async def test_verified_completion_alone_does_not_reset_budget(caplog):
    # R1 maps these verified statuses to True. Only a later gap observation
    # establishes progress, irrespective of the response's success vocabulary.
    instance = bot([row()])
    with caplog.at_level("WARNING"):
        await tick(instance, 8)
    assert instance.voice_session_service.warm_kis_cache.await_count == 3
    assert len([record for record in caplog.records if "giving up" in record.message]) == 1


@pytest.mark.parametrize("failure", [False, RuntimeError("fixture unavailable")])
async def test_unconfirmed_or_raised_requests_do_not_starve_older_sessions(failure):
    rows = [row(gsid) for gsid in range(210, 200, -1)]
    instance = bot(rows, result=False, error=failure if isinstance(failure, Exception) else None)
    for _ in range(4):
        before = instance.voice_session_service.warm_kis_cache.await_count
        await tick(instance)
        assert instance.voice_session_service.warm_kis_cache.await_count - before == 3
    ids = [call.kwargs["gaming_session_id"] for call in instance.voice_session_service.warm_kis_cache.await_args_list]
    assert ids == list(range(210, 200, -1)) + [210, 209]
    assert not instance._kis_reconcile_attempts
    assert not instance._kis_reconcile_abandoned


async def test_cursor_survives_disappearing_sessions_and_newer_arrivals():
    instance = bot([row(gsid) for gsid in range(210, 200, -1)], result=False)
    await tick(instance)
    instance.db_adapter.fetch_all.return_value = [row(gsid) for gsid in [212, 211, 207, 206, 205]]
    await tick(instance)
    ids = [call.kwargs["gaming_session_id"] for call in instance.voice_session_service.warm_kis_cache.await_args_list]
    assert ids == [210, 209, 208, 207, 206, 205]
    await tick(instance)
    assert [call.kwargs["gaming_session_id"] for call in instance.voice_session_service.warm_kis_cache.await_args_list][-3:] == [212, 211, 207]


async def test_query_failure_does_not_reset_budget_or_rotation():
    instance = bot([row(gsid) for gsid in range(210, 205, -1)])
    await tick(instance)
    before = dict(instance._kis_reconcile_attempts)
    instance.db_adapter.fetch_all.side_effect = RuntimeError("fixture query failure")
    await tick(instance)
    assert instance._kis_reconcile_attempts == before
    instance.db_adapter.fetch_all.side_effect = None
    await tick(instance)
    assert [call.kwargs["gaming_session_id"] for call in instance.voice_session_service.warm_kis_cache.await_args_list][3:5] == [207, 206]


async def test_empty_gap_observation_forgets_progress_state_before_later_gap():
    instance = bot([row()])
    await exhaust(instance)
    instance.db_adapter.fetch_all.return_value = []
    await tick(instance)
    assert not instance._kis_reconcile_attempts
    assert not instance._kis_reconcile_abandoned
    assert not instance._kis_reconcile_observed_counts
    instance.db_adapter.fetch_all.return_value = [row()]
    await tick(instance)
    assert instance._kis_reconcile_attempts[184] == 1


async def test_restart_retains_existing_fresh_process_budget_semantics():
    previous = bot([row()])
    await exhaust(previous)
    restarted = bot([row()])
    await tick(restarted)
    assert restarted.voice_session_service.warm_kis_cache.await_count == 1
