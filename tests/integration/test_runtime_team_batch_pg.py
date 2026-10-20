"""Opt-in native composition proof; no application DB fallback or server startup."""

import asyncpg
import pytest

from bot.runtime_completed_import import import_completed_round
from shared import runtime_team_batch as batch_module
from shared.runtime_team_batch import consume_team_page
from shared.runtime_team_consumer import CONSUMER, consume_team_event
from shared.runtime_team_discovery import TeamScanHint
from tests.integration.test_runtime_full_import_pg import completed_pair
from tests.integration.test_runtime_full_import_pg import full_import_db as _full_import_db
from tests.integration.test_runtime_team_discovery_pg import SyntheticJournal

full_import_db = _full_import_db


async def exercise_readonly_page(conn):
    """Actual discovery SQL and batch code, metadata-pending rows only; no writer."""
    assert await conn.fetchval('SHOW transaction_read_only') == 'on'
    journal = SyntheticJournal(conn)
    # Model the connection ownership precondition without opening a write path.
    journal.is_in_transaction = lambda: False
    journal.add(1, round_number=2)
    journal.add(2, validation_passed=False)
    journal.add(3, schema_version=2)
    first = await consume_team_page(journal, batch_size=2)
    assert first.next_hint == TeamScanHint(2, 3)
    assert [(item.event_id, item.outcome.status, item.outcome.reason) for item in first.items] == [
        (1, 'pending', 'not_round_one'), (2, 'pending', 'validation_unavailable')]
    final = await consume_team_page(journal, batch_size=2, hint=first.next_hint)
    assert final.next_hint is None
    assert final.items[0].outcome.reason == 'unsupported_event'
    # Passing the actual enclosing read-only transaction must fail before SQL.
    assert conn.is_in_transaction()
    with pytest.raises(RuntimeError, match='own consumer transactions'):
        await consume_team_page(conn)
    return {'pending_rows': len(first.items) + len(final.items),
            'sweep_exhausted': True, 'outer_transaction_rejected': True,
            'scope': 'native SELECT and metadata exclusions; no effect or receipt'}


@pytest.mark.timeout(120)
async def test_native_page_preserves_roster_then_replays_partial_commit(full_import_db, tmp_path, monkeypatch):
    importer, conn = full_import_db
    monkeypatch.setenv('EVENT_STREAM_ENABLED', 'true')
    monkeypatch.setenv('RUNTIME_TEAM_EVENTS_ENABLED', 'true')
    first, _ = completed_pair(tmp_path, balanced=True)
    assert (await import_completed_round(importer, first))[0] is True
    event_id = await conn.fetchval('SELECT id FROM runtime_events WHERE round_number=1')
    rosters = await conn.fetch('SELECT * FROM session_teams ORDER BY id')
    pending = await consume_team_page(conn)
    assert [(i.event_id, i.outcome.reason) for i in pending.items] == [(event_id, 'already_assigned')]
    assert await conn.fetch('SELECT * FROM session_teams ORDER BY id') == rosters
    assert await conn.fetchval('SELECT count(*) FROM runtime_consumer_receipts') == 0
    # Synthetic isolated fixture only: permit this consumer to create the roster.
    await conn.execute('DELETE FROM session_teams')

    async def committed_then_connection_lost(connection, *, event_id):
        result = await consume_team_event(connection, event_id=event_id)
        assert result.status == 'processed'
        raise ConnectionError('synthetic loss after commit, before page result')

    monkeypatch.setattr(batch_module, 'consume_team_event', committed_then_connection_lost)
    with pytest.raises(ConnectionError, match='synthetic loss after commit'):
        await consume_team_page(conn)
    assert await conn.fetchval('SELECT count(*) FROM session_teams') == 2
    assert await conn.fetchval('SELECT count(*) FROM runtime_consumer_receipts WHERE consumer_name=$1', CONSUMER) == 1
    assigned = await conn.fetch('SELECT * FROM session_teams ORDER BY id')
    monkeypatch.setattr(batch_module, 'consume_team_event', consume_team_event)
    replay = await consume_team_page(conn)
    assert replay.status == 'idle' and replay.items == ()
    assert await conn.fetch('SELECT * FROM session_teams ORDER BY id') == assigned
    assert await conn.fetchval('SELECT count(*) FROM runtime_consumer_receipts WHERE consumer_name=$1', CONSUMER) == 1


async def test_readonly_page_native(monkeypatch):
    from tests.integration.test_runtime_events_pg import connection_options

    options = connection_options()
    options['server_settings'] = {'default_transaction_read_only': 'on'}
    monkeypatch.setenv('EVENT_STREAM_ENABLED', 'true')
    monkeypatch.setenv('RUNTIME_TEAM_EVENTS_ENABLED', 'true')
    conn = await asyncpg.connect(**options)
    try:
        async with conn.transaction(readonly=True):
            await exercise_readonly_page(conn)
    finally:
        await conn.close(timeout=5)
