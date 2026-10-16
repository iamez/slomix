"""Native SELECT-only discovery semantics over synthetic statement-local tables.

Normal pytest uses only the existing explicitly isolated PostgreSQL target. The
reusable exercise accepts a caller-owned read-only connection; it creates no
schema/table, writes no rows, and cannot prove physical concurrent commit order.
"""

import json

import asyncpg

from shared.runtime_team_consumer import CONSUMER
from shared.runtime_team_discovery import TeamScanHint, discover_team_events
from tests.integration.test_runtime_events_pg import connection_options


class SyntheticJournal:
    """Execute the production query; substitute only its two input relations."""

    def __init__(self, conn):
        self.conn = conn
        self.events = []
        self.receipts = []
        self.calls = 0

    def add(self, event_id, **changes):
        self.events.append(dict(id=event_id, event_type='round_stats_imported',
                                schema_version=1, round_number=1, validation_passed=True) | changes)

    async def fetch(self, query, *args):
        self.calls += 1
        prefix = """
            WITH runtime_events AS (
                SELECT * FROM jsonb_to_recordset($5::jsonb)
                AS e(id bigint,event_type text,schema_version integer,
                     round_number integer,validation_passed boolean)
            ), runtime_consumer_receipts AS (
                SELECT * FROM jsonb_to_recordset($6::jsonb)
                AS r(consumer_name text,event_id bigint)
            ),
        """
        assert query.lstrip().startswith('WITH ')
        return await self.conn.fetch(prefix + query.lstrip().removeprefix('WITH '),
                                     *args, json.dumps(self.events), json.dumps(self.receipts))


async def exercise_discovery(conn):
    """Return a non-sensitive proof summary after exercising the real query."""
    assert await conn.fetchval('SHOW transaction_read_only') == 'on'
    journal = SyntheticJournal(conn)
    empty = await discover_team_events(journal, batch_size=2)
    assert (empty.status, empty.candidates, empty.next_hint) == ('idle', (), None)
    journal.add(2, validation_passed=False)
    journal.add(3, schema_version=2)
    journal.add(4)
    journal.add(5, round_number=2)
    journal.add(6)
    # A receipt for another consumer must never hide this team's work.
    journal.receipts = [{'consumer_name': 'another-consumer', 'event_id': 4},
                        {'consumer_name': CONSUMER, 'event_id': 6}]
    first = await discover_team_events(journal, batch_size=2)
    assert [(c.event_id, c.reason) for c in first.candidates] == [
        (2, 'validation_unavailable'), (3, 'unsupported_event')]
    assert first.next_hint == TeamScanHint(3, 6)
    # Simulate a later statement snapshot exposing a lower committed ID, while
    # newer events arrive above the first sweep's fence. No commit-order claim.
    journal.add(1)
    for event_id in range(7, 17):
        journal.add(event_id)
    second = await discover_team_events(journal, batch_size=2, hint=first.next_hint)
    assert [(c.event_id, c.reason) for c in second.candidates] == [(4, None), (5, 'not_round_one')]
    assert second.next_hint == TeamScanHint(5, 6)
    exhausted = await discover_team_events(journal, batch_size=2, hint=second.next_hint)
    assert exhausted.status == 'idle' and exhausted.next_hint is None
    restarted = await discover_team_events(journal, batch_size=2, hint=exhausted.next_hint)
    assert [c.event_id for c in restarted.candidates] == [1, 2]
    assert restarted.next_hint == TeamScanHint(2, 16)
    # A new receipt between pages removes only that consumer's event. Discovery
    # never creates the receipt itself, including for pending/excluded metadata.
    journal.receipts.append({'consumer_name': CONSUMER, 'event_id': 4})
    after_receipt = await discover_team_events(journal, batch_size=2, hint=TeamScanHint(3, 6))
    assert [c.event_id for c in after_receipt.candidates] == [5]
    assert after_receipt.next_hint is None
    # Independent PostgreSQL count and row listing of receipt-filtered input.
    ids = await conn.fetch("""
        SELECT e.id FROM jsonb_to_recordset($1::jsonb) AS e(id bigint)
        WHERE NOT EXISTS (
            SELECT 1 FROM jsonb_to_recordset($2::jsonb) AS r(consumer_name text,event_id bigint)
            WHERE r.consumer_name=$3 AND r.event_id=e.id
        ) ORDER BY e.id
    """, json.dumps(journal.events), json.dumps(journal.receipts), CONSUMER)
    count = await conn.fetchval("""
        SELECT count(*) FROM jsonb_array_elements($1::jsonb) e
        WHERE NOT EXISTS (SELECT 1 FROM jsonb_array_elements($2::jsonb) r
                          WHERE r->>'consumer_name'=$3 AND r->>'event_id'=e->>'id')
    """, json.dumps(journal.events), json.dumps(journal.receipts), CONSUMER)
    expected = [1, 2, 3, 5, *range(7, 17)]
    assert [r['id'] for r in ids] == expected and count == len(ids) == 14
    assert len(journal.receipts) == 3  # discovery did not append any receipt
    assert await conn.fetchval('SHOW transaction_read_only') == 'on'
    return {'discovery_calls': journal.calls, 'unreceipted_rows': count,
            'late_lower_id_revisited': True, 'finite_sweep_exhausted': True,
            'other_consumer_receipt_ignored': True, 'read_only': True}


async def test_native_discovery_select_semantics(monkeypatch):
    options = connection_options()
    options['server_settings'] = {**options.get('server_settings', {}),
                                  'default_transaction_read_only': 'on',
                                  'statement_timeout': '5000'}
    monkeypatch.setenv('EVENT_STREAM_ENABLED', 'true')
    monkeypatch.setenv('RUNTIME_TEAM_EVENTS_ENABLED', 'true')
    conn = await asyncpg.connect(**options)
    try:
        async with conn.transaction(readonly=True):
            result = await exercise_discovery(conn)
        assert result['late_lower_id_revisited']
    finally:
        await conn.close(timeout=5)
