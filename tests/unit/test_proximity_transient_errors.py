"""Transient parser/worker failures must unwind and remain eligible for bounded retry."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import asyncpg
import pytest

from proximity.parser.parser import ProximityParserV4
from shared.runtime_proximity_worker import RuntimeProximityWorker

ERRORS = (TimeoutError, asyncpg.QueryCanceledError, asyncpg.PostgresConnectionError,
          asyncpg.CannotConnectNowError, asyncpg.SerializationError,
          asyncpg.DeadlockDetectedError, asyncpg.TooManyConnectionsError)


@pytest.mark.parametrize('error_type', ERRORS)
async def test_actual_parser_propagates_transient_receipt_failure(tmp_path, monkeypatch, error_type):
    released = []

    @asynccontextmanager
    async def transaction():
        try:
            yield
        finally:
            released.append(True)

    adapter = SimpleNamespace(transaction=transaction, execute=AsyncMock(),
                              fetch_one=AsyncMock(side_effect=error_type('fixture transient')))
    path = tmp_path / '2026-10-08-120000-supply-round-1_engagements.txt'
    path.write_text('# map=supply\n# round=1\n')
    parser = ProximityParserV4(db_adapter=adapter, gametimes_dir=str(tmp_path))
    monkeypatch.setattr(parser, '_resolve_round_link_context', AsyncMock())
    with pytest.raises(error_type):
        await parser.import_file(str(path), '2026-10-08', source_bytes=path.read_bytes())
    assert released == [True]
    assert path.is_file()
    with pytest.raises(error_type):
        await parser._table_has_column('player_track', 'round_id')  # noqa: SLF001 -- optional probe cannot hide outage


@pytest.mark.parametrize('error_type', ERRORS)
async def test_worker_releases_resources_and_backs_off_transient_database_errors(tmp_path, monkeypatch, error_type):
    from shared import runtime_proximity_worker as module

    worker = RuntimeProximityWorker(tmp_path, source_id='fixture', gametimes_dir=tmp_path, enabled=True)
    stop = asyncio.Event()
    released = []

    @asynccontextmanager
    async def resources():
        try:
            yield None, None
        finally:
            released.append(True)

    process = AsyncMock(side_effect=error_type('fixture transient'))
    monkeypatch.setattr(module, 'process_proximity_checkpointed_batch', process)

    async def wait(_stop, delay):
        assert released == [True]
        assert delay == 5
        assert worker.state.status == 'unavailable'
        assert worker.state.error_type == error_type.__name__
        stop.set()

    monkeypatch.setattr(worker, '_wait', wait)
    await worker.run(resources, stop)
    process.assert_awaited_once()
