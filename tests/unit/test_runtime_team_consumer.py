"""Single-event admission contracts; DB transaction behavior needs PG proofs."""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock

import pytest

from shared import runtime_team_consumer as module
from shared.import_team_assignment import TeamAssignment


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv('EVENT_STREAM_ENABLED', 'true')
    monkeypatch.setenv('RUNTIME_TEAM_EVENTS_ENABLED', 'true')
    conn = Mock()
    conn.is_in_transaction.return_value = False
    conn.fetchval = AsyncMock(side_effect=lambda query, *args: 'information_schema' in query)
    conn.execute = AsyncMock()
    event = dict(event_type='round_stats_imported', schema_version=1, round_number=1,
                 gaming_session_id=7, round_id=3, validation_passed=True)
    round_row = dict(round_number=1, gaming_session_id=7, round_date='2026-09-27')
    conn.fetchrow = AsyncMock(side_effect=lambda query, *args: event if 'runtime_events' in query else round_row)

    @asynccontextmanager
    async def guard(connection):
        assert connection is conn
        yield connection

    assign = AsyncMock(return_value=TeamAssignment.ASSIGNED)
    monkeypatch.setattr(module, 'team_write_transaction', guard)
    monkeypatch.setattr(module, 'assign_round_teams', assign)
    return conn, event, round_row, assign


@pytest.mark.parametrize('flag', ['EVENT_STREAM_ENABLED', 'RUNTIME_TEAM_EVENTS_ENABLED'])
async def test_disabled_does_not_touch_connection(setup, monkeypatch, flag):
    conn, _, _, assign = setup
    monkeypatch.delenv(flag)
    assert (await module.consume_team_event(conn, event_id=1)).status == 'disabled'
    conn.is_in_transaction.assert_not_called()
    conn.fetchval.assert_not_awaited()
    assign.assert_not_awaited()


@pytest.mark.parametrize('value', [True, False, None, 0, -1, 1.5, '1', 2**63])
async def test_invalid_event_id_rejected(setup, value):
    conn, *_ = setup
    with pytest.raises(ValueError):
        await module.consume_team_event(conn, event_id=value)
    conn.fetchval.assert_not_awaited()


async def test_caller_transaction_refused(setup):
    conn, *_ = setup
    conn.is_in_transaction.return_value = True
    with pytest.raises(RuntimeError, match='own transaction'):
        await module.consume_team_event(conn, event_id=1)


@pytest.mark.parametrize('field,value,reason', [
    ('event_type', 'round_lua_corrected', 'unsupported_event'),
    ('schema_version', 2, 'unsupported_event'),
    ('round_number', 2, 'not_round_one'),
    ('validation_passed', False, 'validation_unavailable'),
    ('gaming_session_id', None, 'identity_mismatch'),
    ('gaming_session_id', 8, 'identity_mismatch'),
])
async def test_event_admission_does_not_ack(setup, field, value, reason):
    conn, event, _, assign = setup
    event[field] = value
    result = await module.consume_team_event(conn, event_id=1)
    assert (result.status, result.reason) == ('pending', reason)
    assign.assert_not_awaited()
    conn.execute.assert_not_awaited()


@pytest.mark.parametrize('value', [None, '', '2026-02-30', '20260927', '2026-09-27T00:00:00'])
async def test_invalid_round_date_stays_pending(setup, value):
    conn, _, round_row, assign = setup
    round_row['round_date'] = value
    assert (await module.consume_team_event(conn, event_id=1)).reason == 'date_unavailable'
    assign.assert_not_awaited()


@pytest.mark.parametrize('outcome', [item for item in TeamAssignment if item is not TeamAssignment.ASSIGNED])
async def test_noop_is_never_receipt(setup, outcome):
    conn, _, _, assign = setup
    assign.return_value = outcome
    assert (await module.consume_team_event(conn, event_id=1)).status == 'pending'
    conn.execute.assert_not_awaited()


async def test_assignment_records_distinct_receipt(setup):
    conn, _, _, assign = setup
    assert (await module.consume_team_event(conn, event_id=1)).status == 'processed'
    assign.assert_awaited_once_with(conn, round_id=3, session_date='2026-09-27')
    assert conn.execute.await_args.args[1:] == (module.CONSUMER, 1)


async def test_existing_receipt_skips_assignment(setup):
    conn, _, _, assign = setup
    conn.fetchval.side_effect = None
    conn.fetchval.return_value = True
    assert (await module.consume_team_event(conn, event_id=1)).status == 'already_processed'
    assign.assert_not_awaited()
    conn.execute.assert_not_awaited()


@pytest.mark.parametrize('missing,reason', [('event', 'event_missing'), ('round', 'round_missing')])
async def test_missing_identity_never_assigns(setup, missing, reason):
    conn, event, _, assign = setup
    conn.fetchrow.side_effect = [None] if missing == 'event' else [event, None]
    assert (await module.consume_team_event(conn, event_id=1)).reason == reason
    assign.assert_not_awaited()
    conn.execute.assert_not_awaited()


@pytest.mark.parametrize('failure', [RuntimeError('unavailable'), asyncio.CancelledError()])
async def test_assignment_error_or_cancel_never_receipts(setup, failure):
    conn, _, _, assign = setup
    assign.side_effect = failure
    with pytest.raises(type(failure)):
        await module.consume_team_event(conn, event_id=1)
    conn.execute.assert_not_awaited()


async def test_receipt_error_is_not_success(setup):
    conn, *_ = setup
    conn.execute.side_effect = RuntimeError('receipt failed')
    with pytest.raises(RuntimeError, match='receipt failed'):
        await module.consume_team_event(conn, event_id=1)


@pytest.mark.parametrize('available', [False, None, 0, 1, 'true'])
async def test_modern_identity_required_before_assignment(setup, available):
    conn, _, _, assign = setup
    conn.fetchval.side_effect = [False, available]
    assert (await module.consume_team_event(conn, event_id=1)).reason == 'schema_unavailable'
    conn.fetchrow.assert_not_awaited()
    assign.assert_not_awaited()
    conn.execute.assert_not_awaited()
