"""Scheduling/admission contracts; native SELECT semantics have separate proofs."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from shared.runtime_team_consumer import CONSUMER
from shared.runtime_team_discovery import TeamScanHint, discover_team_events


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    monkeypatch.setenv('EVENT_STREAM_ENABLED', 'true')
    monkeypatch.setenv('RUNTIME_TEAM_EVENTS_ENABLED', 'true')


def row(event_id=1, through_id=5, **changes):
    return dict(id=event_id, through_id=through_id,
                **(dict(event_type='round_stats_imported', schema_version=1,
                        round_number=1, validation_passed=True) | changes))


@pytest.mark.parametrize('flag', ['EVENT_STREAM_ENABLED', 'RUNTIME_TEAM_EVENTS_ENABLED'])
@pytest.mark.parametrize('value', [None, '', 'false', '1', 'yes'])
async def test_disabled_never_touches_a_connection(monkeypatch, flag, value):
    if value is None:
        monkeypatch.delenv(flag)
    else:
        monkeypatch.setenv(flag, value)
    result = await discover_team_events(None, batch_size='invalid', hint='invalid')
    assert (result.status, result.candidates, result.next_hint) == ('disabled', (), None)


@pytest.mark.parametrize('value', [True, False, 0, -1, 1001, '1', 1.5, None])
async def test_bad_limit_rejected_before_connection(value):
    with pytest.raises(ValueError, match='batch size'):
        await discover_team_events(None, batch_size=value)


@pytest.mark.parametrize('after,through', [(True, 4), (0, True), (-1, 3), (3, 3),
                                        (4, 3), (0, 2**63), ('0', 4), (0, 1.5)])
def test_hint_has_strict_bigint_order(after, through):
    with pytest.raises(ValueError, match='ordered'):
        TeamScanHint(after, through)


async def test_wrong_hint_type_rejected_before_connection():
    with pytest.raises(ValueError, match='explicit scan hint'):
        await discover_team_events(None, hint=5)


async def test_page_uses_consumer_receipt_identity_and_frozen_sweep():
    conn = AsyncMock()
    conn.fetch.return_value = [row(3), row(4)]
    result = await discover_team_events(conn, batch_size=2, hint=TeamScanHint(2, 5))
    assert conn.fetch.await_args.args[1:] == (CONSUMER, 2, 5, 2)
    assert [c.event_id for c in result.candidates] == [3, 4]
    assert all(c.eligible for c in result.candidates)
    assert result.next_hint == TeamScanHint(4, 5)
    conn.execute.assert_not_awaited()


async def test_pending_metadata_does_not_pin_scheduling_position():
    conn = AsyncMock()
    conn.fetch.return_value = [row(1, event_type='future_event'), row(2, schema_version=2),
                              row(3, round_number=2), row(4, validation_passed=False)]
    result = await discover_team_events(conn, batch_size=4)
    assert [c.reason for c in result.candidates] == [
        'unsupported_event', 'unsupported_event', 'not_round_one', 'validation_unavailable']
    assert not any(c.eligible for c in result.candidates)
    assert result.next_hint == TeamScanHint(4, 5)
    conn.execute.assert_not_awaited()


@pytest.mark.parametrize('rows,batch', [([row(5)], 1), ([row(3)], 2),
                                     ([row(None)], 2), ([row(None, 0)], 2)])
async def test_exhaustion_resets_instead_of_persisting_a_max_id_cursor(rows, batch):
    conn = AsyncMock()
    conn.fetch.return_value = rows
    result = await discover_team_events(conn, batch_size=batch)
    assert result.next_hint is None
    assert result.status == ('idle' if rows[0]['id'] is None else 'page')
    await discover_team_events(conn, batch_size=batch, hint=result.next_hint)
    assert conn.fetch.await_args.args[1:] == (CONSUMER, 0, None, batch)


@pytest.mark.parametrize('failure', [RuntimeError('unavailable'), asyncio.CancelledError()])
async def test_failure_or_cancel_does_not_manufacture_progress(failure):
    conn = AsyncMock()
    conn.fetch.side_effect = failure
    with pytest.raises(type(failure)):
        await discover_team_events(conn, hint=TeamScanHint(3, 9))


async def test_missing_fence_is_not_misreported_as_idle():
    conn = AsyncMock()
    conn.fetch.return_value = []
    with pytest.raises(RuntimeError, match='sweep fence'):
        await discover_team_events(conn)
