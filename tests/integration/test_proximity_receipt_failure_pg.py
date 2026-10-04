"""Canonical receipt failure rolls back earlier writes on disposable PostgreSQL."""

from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from proximity.parser import ProximityParserV4
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401


@pytest.mark.parametrize('failure', ['python', 'sql', 'missing'])
async def test_receipt_failure_then_retry(journal_db, monkeypatch, tmp_path, failure):  # noqa: F811
    writer, reader = journal_db
    await writer.execute('CREATE TABLE proof_data (id INTEGER PRIMARY KEY)')
    await writer.execute('CREATE TABLE proximity_processed_files (filename TEXT PRIMARY KEY, aggregates_applied BOOLEAN)')
    armed = True
    injected = []

    @asynccontextmanager
    async def transaction():
        async with writer.transaction():
            yield writer

    async def execute(query, params=None):
        if armed and 'VALUES ($1, FALSE)' not in query:
            assert await writer.fetchval('SELECT count(*) FROM proof_data') == 1
            assert await reader.fetchval('SELECT count(*) FROM proof_data') == 0
            injected.append(True)
            if failure == 'python':
                raise RuntimeError('injected receipt failure')
            if failure == 'sql':
                await writer.execute('SELECT 1 / 0')
        return await writer.execute(query, *(params or ()))

    parser = ProximityParserV4(db_adapter=SimpleNamespace(transaction=transaction, execute=execute))
    source = tmp_path / '2026-10-03-120000-fixture-round-1_engagements.txt'
    source.write_text('# PROXIMITY_TRACKER_V4\n# map=fixture\n# round=1\n')
    monkeypatch.setattr(parser, '_resolve_round_link_context', AsyncMock())

    async def processed(filename):
        return bool(await writer.fetchval('SELECT aggregates_applied FROM proximity_processed_files WHERE filename=$1', filename))

    async def has_column(table, column):
        if armed and failure == 'missing' and column == 'filename':
            assert await writer.fetchval('SELECT count(*) FROM proof_data') == 1
            assert await reader.fetchval('SELECT count(*) FROM proof_data') == 0
            injected.append(True)
            return False
        return column == 'filename'

    async def write_data(day):
        await writer.execute('INSERT INTO proof_data VALUES (1) ON CONFLICT DO NOTHING')

    monkeypatch.setattr(parser, '_check_processed_file', processed)
    monkeypatch.setattr(parser, '_table_has_column', has_column)
    monkeypatch.setattr(parser, '_import_engagements', write_data)
    for method in ('_update_player_stats', '_update_crossfire_pairs', '_import_heatmaps'):
        monkeypatch.setattr(parser, method, AsyncMock())
    assert await parser.import_file(str(source), date(2026, 10, 3)) is False
    assert injected == [True]
    for table in ('proof_data', 'proximity_processed_files'):
        assert await reader.fetchval(f'SELECT count(*) FROM {table}') == 0
        assert await reader.fetch(f'SELECT * FROM {table}') == []
    armed = False
    for _ in range(2):
        assert await parser.import_file(str(source), date(2026, 10, 3)) is True
        for table in ('proof_data', 'proximity_processed_files'):
            assert await reader.fetchval(f'SELECT count(*) FROM {table}') == 1
            assert len(await reader.fetch(f'SELECT * FROM {table}')) == 1
