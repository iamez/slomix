"""Receipt reads fail closed on real SQL errors; retries do not reapply sums."""

from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from proximity.parser import ProximityParserV4
from tests.integration.proximity_adapter_helpers import pg_query
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401


@pytest.mark.parametrize('failure', ['missing_table', 'missing_column', 'sql'])
async def test_receipt_read_failure_then_retry(journal_db, monkeypatch, tmp_path, caplog, failure):  # noqa: F811
    writer, reader = journal_db
    await writer.execute('CREATE TABLE proof_data (id INTEGER PRIMARY KEY, applied INTEGER NOT NULL)')
    if failure != 'missing_table':
        column = ', aggregates_applied BOOLEAN' if failure == 'sql' else ''
        await writer.execute(f'CREATE TABLE proximity_processed_files (filename TEXT PRIMARY KEY{column})')
    armed = True
    reads = []
    writes = []

    @asynccontextmanager
    async def transaction():
        async with writer.transaction():
            yield writer

    async def fetch_one(query, params=None):
        assert query.startswith('SELECT aggregates_applied')
        assert writer.is_in_transaction()
        reads.append(True)
        if armed and failure == 'sql':
            await writer.execute('SELECT 1 / 0')
        return await writer.fetchrow(pg_query(query), *(params or ()))

    async def execute(query, params=None):
        return await writer.execute(pg_query(query), *(params or ()))

    parser = ProximityParserV4(db_adapter=SimpleNamespace(
        transaction=transaction, fetch_one=fetch_one, execute=execute,
    ))
    source = tmp_path / '2026-10-04-120000-fixture-round-1_engagements.txt'
    source.write_text('# PROXIMITY_TRACKER_V4\n# map=fixture\n# round=1\n')
    monkeypatch.setattr(parser, '_resolve_round_link_context', AsyncMock())
    # Optional receipt-write metadata is outside this test; the mandatory read
    # deliberately uses the real helper and the real PostgreSQL relation.
    monkeypatch.setattr(parser, '_table_has_column', AsyncMock(side_effect=lambda t, c: c == 'filename'))

    async def engagement(day):
        writes.append('engagement')

    async def aggregate():
        writes.append('aggregate')
        await writer.execute('INSERT INTO proof_data VALUES (1,1) ON CONFLICT (id) DO UPDATE SET applied=proof_data.applied+1')

    monkeypatch.setattr(parser, '_import_engagements', engagement)
    monkeypatch.setattr(parser, '_update_player_stats', aggregate)
    for method in ('_update_crossfire_pairs', '_import_heatmaps'):
        monkeypatch.setattr(parser, method, AsyncMock())
    assert await parser.import_file(str(source), date(2026, 10, 4)) is False
    # Missing schema now fails even earlier, while acquiring the receipt row.
    assert reads == ([True] if failure == 'sql' else [])
    assert writes == []
    assert await reader.fetchval('SELECT count(*) FROM proof_data') == 0
    assert await reader.fetch('SELECT * FROM proof_data') == []
    assert not writer.is_in_transaction()
    expected_error = {
        'missing_table': 'relation "proximity_processed_files" does not exist',
        'missing_column': 'column "aggregates_applied" of relation "proximity_processed_files" does not exist',
        'sql': 'division by zero',
    }[failure]
    assert f'Import error: {expected_error}' in caplog.text

    if failure == 'missing_table':
        await writer.execute('CREATE TABLE proximity_processed_files (filename TEXT PRIMARY KEY, aggregates_applied BOOLEAN)')
    elif failure == 'missing_column':
        await writer.execute('ALTER TABLE proximity_processed_files ADD COLUMN aggregates_applied BOOLEAN')
    armed = False
    for _ in range(2):
        assert await parser.import_file(str(source), date(2026, 10, 4)) is True
        assert await reader.fetchval('SELECT applied FROM proof_data WHERE id=1') == 1
        assert [tuple(r) for r in await reader.fetch('SELECT * FROM proof_data')] == [(1, 1)]
        assert await reader.fetchval('SELECT aggregates_applied FROM proximity_processed_files WHERE filename=$1', source.name) is True
        assert await reader.fetchval('SELECT count(*) FROM proximity_processed_files') == 1
        assert [tuple(r) for r in await reader.fetch('SELECT * FROM proximity_processed_files')] == [(source.name, True)]
    assert writes == ['engagement', 'aggregate', 'engagement']
    assert len(reads) == (3 if failure == 'sql' else 2)
    print(f'Receipt read proof: {failure}, failed writes=0, retry applied=1, replay applied=1, receipts=1')
