"""Real importer preflight lifecycle with a caller-owned protocol-test pool."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize('outcome', ['duplicate', 'outage', 'cancel'])
def test_neutral_process_file_keeps_borrowed_pool(tmp_path, outcome):
    """Duplicate, failure and cancellation release leases without closing pools."""
    script = r'''
import asyncio
from contextlib import asynccontextmanager
import importlib.abc
from pathlib import Path
import sys
from types import SimpleNamespace

class BlockSetup(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'discord', 'dotenv', 'website'} or fullname in {
            'bot.config', 'bot.logging_config', 'shared.importer_startup',
        }:
            raise ModuleNotFoundError('Forbidden ingestion dependency: ' + fullname)
sys.meta_path.insert(0, BlockSetup())
from postgresql_database_manager import PostgreSQLDatabaseManager

outcome, fixture = sys.argv[1:]
events = []
class Connection:
    async def fetchval(self, query, *args):
        assert 'FROM processed_files' in query and 'success = TRUE' in query
        assert args == (Path(fixture).name,)
        events.append('query')
        if outcome == 'outage':
            raise OSError('fixture database outage')
        if outcome == 'cancel':
            raise asyncio.CancelledError()
        return 1

class BorrowedPool:
    @asynccontextmanager
    async def acquire(self):
        events.append('acquire')
        try:
            yield Connection()
        finally:
            events.append('release')
    async def close(self):
        raise AssertionError('Importer closed caller-owned pool')

async def main():
    pool = BorrowedPool()
    manager = PostgreSQLDatabaseManager(config=SimpleNamespace(database_type='postgresql'))
    manager.pool = pool
    await manager.connect()  # Existing pool must be reused, not replaced.
    try:
        result = await manager.process_file(Path(fixture))
    except asyncio.CancelledError:
        assert outcome == 'cancel'
    else:
        assert outcome != 'cancel', 'Cancellation was swallowed'
        if outcome == 'duplicate':
            assert result == (True, 'Already processed')
            assert manager.stats['files_skipped'] == 1
        else:
            assert result.retryable is True
            assert tuple(result) == (False, 'fixture database outage')
            assert manager.stats['files_failed'] == 1
    assert manager.pool is pool
    assert manager.stats['files_processed'] == 0
    assert events == ['acquire', 'query', 'release']
    print('Importer preflight proof: ' + outcome + '; lease released, borrowed pool retained')
asyncio.run(main())
'''
    root = Path(__file__).resolve().parents[2]
    fixture = root / 'tests/fixtures/sample_stats_files/2025-12-17-120000-goldrush-round-1.txt'
    assert fixture.is_file()
    result = subprocess.run(
        [sys.executable, '-c', script, outcome, str(fixture)], cwd=tmp_path,
        env={**os.environ, 'PYTHONPATH': str(root), 'BOT_LOG_DIR': str(tmp_path / 'logs')},
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Importer preflight proof: ' + outcome in result.stdout
    assert not (tmp_path / 'logs').exists()
