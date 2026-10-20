"""Page composition contracts; transaction durability belongs to native PG proof."""

import asyncio
from unittest.mock import AsyncMock, Mock, call

import pytest

from shared import runtime_team_batch as module
from shared.runtime_team_consumer import TeamConsumption
from shared.runtime_team_discovery import TeamCandidate, TeamDiscovery, TeamScanHint
from shared.team_write_guard import TeamWriteBusy


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv('EVENT_STREAM_ENABLED', 'true')
    monkeypatch.setenv('RUNTIME_TEAM_EVENTS_ENABLED', 'true')
    conn = Mock()
    conn.is_in_transaction.return_value = False
    discover = AsyncMock(return_value=TeamDiscovery('page', (
        TeamCandidate(2, 'validation_unavailable'), TeamCandidate(3, None),
        TeamCandidate(4, None)), TeamScanHint(4, 8)))
    consume = AsyncMock(return_value=TeamConsumption('processed'))
    monkeypatch.setattr(module, 'discover_team_events', discover)
    monkeypatch.setattr(module, 'consume_team_event', consume)
    return conn, discover, consume


@pytest.mark.parametrize('flag', ['EVENT_STREAM_ENABLED', 'RUNTIME_TEAM_EVENTS_ENABLED'])
async def test_disabled_touches_nothing(setup, monkeypatch, flag):
    conn, discover, consume = setup
    monkeypatch.delenv(flag)
    hint = TeamScanHint(1, 8)
    result = await module.consume_team_page(conn, batch_size=False, hint=hint)
    assert result == module.TeamBatch('disabled', (), hint)
    conn.is_in_transaction.assert_not_called()
    discover.assert_not_awaited()
    consume.assert_not_awaited()


async def test_caller_transaction_rejected_before_discovery(setup):
    conn, discover, consume = setup
    conn.is_in_transaction.return_value = True
    with pytest.raises(RuntimeError, match='own consumer transactions'):
        await module.consume_team_page(conn)
    discover.assert_not_awaited()
    consume.assert_not_awaited()


async def test_metadata_pending_and_consumer_pending_both_advance(setup):
    conn, discover, consume = setup
    consume.side_effect = [TeamConsumption('pending', 'already_assigned'),
                           TeamConsumption('already_processed')]
    hint = TeamScanHint(1, 8)
    result = await module.consume_team_page(conn, batch_size=3, hint=hint)
    discover.assert_awaited_once_with(conn, batch_size=3, hint=hint)
    assert consume.await_args_list == [call(conn, event_id=3), call(conn, event_id=4)]
    assert [(i.event_id, i.outcome.status, i.outcome.reason) for i in result.items] == [
        (2, 'pending', 'validation_unavailable'), (3, 'pending', 'already_assigned'),
        (4, 'already_processed', None)]
    assert result.next_hint == TeamScanHint(4, 8)


@pytest.mark.parametrize('status', ['idle', 'disabled'])
async def test_empty_or_disabled_discovery(setup, status):
    conn, discover, consume = setup
    hint = TeamScanHint(1, 8)
    discover.return_value = TeamDiscovery(status, (), None)
    result = await module.consume_team_page(conn, hint=hint)
    assert result == module.TeamBatch(status, (), hint if status == 'disabled' else None)
    consume.assert_not_awaited()


@pytest.mark.parametrize('failure', [RuntimeError('db unavailable'), asyncio.CancelledError()])
async def test_discovery_failure_propagates_without_writes(setup, failure):
    conn, discover, consume = setup
    discover.side_effect = failure
    with pytest.raises(type(failure)):
        await module.consume_team_page(conn)
    consume.assert_not_awaited()


@pytest.mark.parametrize('failure', [RuntimeError('receipt failed'), TeamWriteBusy('busy'),
                                     asyncio.CancelledError()])
async def test_partial_failure_stops_and_retry_uses_receipts(setup, failure):
    conn, discover, consume = setup
    consume.side_effect = [TeamConsumption('processed'), failure]
    hint = TeamScanHint(1, 8)
    with pytest.raises(type(failure)):
        await module.consume_team_page(conn, hint=hint)
    assert consume.await_count == 2
    consume.reset_mock()
    # Existing consumer recognises the first committed receipt on retry.
    consume.side_effect = [TeamConsumption('already_processed'), TeamConsumption('processed')]
    result = await module.consume_team_page(conn, hint=hint)
    assert result.next_hint == TeamScanHint(4, 8)
    assert [i.outcome.status for i in result.items] == ['pending', 'already_processed', 'processed']
    assert discover.await_args_list == [call(conn, batch_size=100, hint=hint)] * 2


async def test_no_parallel_consumer_tasks(setup):
    conn, _, consume = setup
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def effect(connection, *, event_id):
        calls.append(event_id)
        if event_id == 3:
            entered.set()
            await release.wait()
        return TeamConsumption('processed')

    consume.side_effect = effect
    task = asyncio.create_task(module.consume_team_page(conn))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        assert calls == [3]
        release.set()
        await asyncio.wait_for(task, 1)
        assert calls == [3, 4]
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_gate_closes_between_effects_preserves_original_hint(setup, monkeypatch):
    conn, _, consume = setup
    hint = TeamScanHint(1, 8)

    async def effect(*args, **kwargs):
        monkeypatch.setenv('RUNTIME_TEAM_EVENTS_ENABLED', 'false')
        return TeamConsumption('processed')

    consume.side_effect = effect
    result = await module.consume_team_page(conn, hint=hint)
    assert result.status == 'disabled' and result.next_hint == hint
    assert [i.event_id for i in result.items] == [2, 3]
    consume.assert_awaited_once_with(conn, event_id=3)


async def test_consumer_disabled_is_not_progress(setup):
    conn, _, consume = setup
    consume.return_value = TeamConsumption('disabled')
    hint = TeamScanHint(1, 8)
    result = await module.consume_team_page(conn, hint=hint)
    assert result.status == 'disabled' and result.next_hint == hint
    assert [i.event_id for i in result.items] == [2]
    consume.assert_awaited_once_with(conn, event_id=3)
