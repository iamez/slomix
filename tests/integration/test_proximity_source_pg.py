"""Verified runtime bytes and receipt digest commit or roll back together."""

import asyncio
import hashlib
from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from proximity.parser import ProximityParserV4
from shared import proximity_import
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401


@pytest.fixture
async def source_import(journal_db, monkeypatch, tmp_path):  # noqa: F811
    writer, observer = journal_db
    await writer.execute('CREATE TABLE proof_data (id INTEGER PRIMARY KEY, applied INTEGER NOT NULL)')
    await writer.execute('CREATE TABLE proximity_processed_files (filename TEXT PRIMARY KEY, aggregates_applied BOOLEAN, file_hash TEXT)')
    source = tmp_path / '2026-10-04-120000-fixture-round-1_engagements.txt'
    payload = b'# PROXIMITY_TRACKER_V4\n# map=fixture\n# round=1\n'
    source.write_bytes(payload)
    source.chmod(0o600)
    digest = hashlib.sha256(payload).hexdigest()
    controls = {'failure': None, 'replace_path': False}
    seen = []

    @asynccontextmanager
    async def transaction():
        async with writer.transaction():
            yield writer

    async def execute(query, params=None):
        return await writer.execute(query, *(params or ()))

    async def fetch_one(query, params=None):
        return await writer.fetchrow(query, *(params or ()))

    adapter = SimpleNamespace(transaction=transaction, execute=execute, fetch_one=fetch_one)

    def factory(**kwargs):
        # The boundary has already captured verified bytes. This path mutation
        # must not change the bytes parsed or their recorded digest.
        if controls['replace_path']:
            source.write_bytes(b'# map=changed\n# round=1\n')
        parser = ProximityParserV4(**kwargs)
        monkeypatch.setattr(parser, '_resolve_round_link_context', AsyncMock())
        monkeypatch.setattr(parser, '_table_has_column', AsyncMock(side_effect=lambda t, c: c == 'filename'))

        async def engagement(day):
            seen.append(parser.metadata['map_name'])
            assert await writer.fetchval('SELECT file_hash FROM proximity_processed_files') == digest
            if controls['failure'] == 'cancel':
                raise asyncio.CancelledError()
            if controls['failure'] == 'python':
                raise RuntimeError('injected canonical import failure after digest binding')

        async def aggregate():
            await writer.execute('INSERT INTO proof_data VALUES (1,1) ON CONFLICT (id) DO UPDATE SET applied=proof_data.applied+1')

        monkeypatch.setattr(parser, '_import_engagements', engagement)
        monkeypatch.setattr(parser, '_update_player_stats', aggregate)
        for method in ('_update_crossfire_pairs', '_import_heatmaps'):
            monkeypatch.setattr(parser, method, AsyncMock())
        return parser

    monkeypatch.setattr(proximity_import, 'ProximityParserV4', factory)
    async def run(expected_payload=payload):
        return await proximity_import.import_proximity_file(
            source, adapter=adapter, session_date=date(2026, 10, 4), gametimes_dir=tmp_path,
            expected_size=len(expected_payload), expected_sha256=hashlib.sha256(expected_payload).hexdigest(),
        )
    return writer, observer, source, payload, digest, controls, seen, run


async def test_verified_repeat_and_different_content_conflict(source_import):
    writer, observer, source, payload, digest, controls, seen, run = source_import
    for _ in range(2):
        assert (await run()).success
        assert await observer.fetchval('SELECT sum(applied) FROM proof_data') == 1
        assert [tuple(r) for r in await observer.fetch('SELECT * FROM proof_data')] == [(1, 1)]
        assert tuple(await observer.fetchrow('SELECT * FROM proximity_processed_files')) == (source.name, True, digest)
    changed = payload.replace(b'fixture', b'changed')
    source.write_bytes(changed)
    with pytest.raises(ValueError, match='conflicts with recorded'):
        await run(changed)
    assert seen == ['fixture', 'fixture']
    assert await observer.fetchval('SELECT file_hash FROM proximity_processed_files') == digest
    assert await observer.fetchval('SELECT sum(applied) FROM proof_data') == 1


@pytest.mark.parametrize('flag', [True, False, None])
async def test_unverified_existing_receipt_not_adopted(source_import, flag):
    writer, observer, source, payload, digest, controls, seen, run = source_import
    await writer.execute('INSERT INTO proximity_processed_files VALUES ($1,$2,NULL)', source.name, flag)
    with pytest.raises(ValueError, match='unverified source identity'):
        await run()
    assert seen == []
    assert tuple(await observer.fetchrow('SELECT * FROM proximity_processed_files')) == (source.name, flag, None)
    assert await observer.fetchval('SELECT count(*) FROM proof_data') == 0


@pytest.mark.parametrize('failure', ['python', 'cancel'])
async def test_failed_import_rolls_back_digest_and_claim(source_import, failure):
    writer, observer, source, payload, digest, controls, seen, run = source_import
    controls['failure'] = failure
    if failure == 'cancel':
        with pytest.raises(asyncio.CancelledError):
            await run()
    else:
        result = await run()
        assert not result.success and result.parsed_stats is None
    assert seen == ['fixture']
    for table in ('proof_data', 'proximity_processed_files'):
        assert await observer.fetchval(f'SELECT count(*) FROM {table}') == 0
        assert await observer.fetch(f'SELECT * FROM {table}') == []
    controls['failure'] = None
    assert (await run()).success
    assert await observer.fetchval('SELECT file_hash FROM proximity_processed_files') == digest


async def test_runtime_parses_captured_bytes_not_reopened_path(source_import):
    writer, observer, source, payload, digest, controls, seen, run = source_import
    controls['replace_path'] = True
    assert (await run()).success
    assert source.read_bytes() != payload
    assert seen == ['fixture']
    assert await observer.fetchval('SELECT file_hash FROM proximity_processed_files') == digest
    assert await observer.fetchval('SELECT sum(applied) FROM proof_data') == 1
