"""Actual CLI TCP writes/replay observed separately, only on disposable CI PG."""

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

from tests.integration.test_runtime_events_pg import connection_options
from tests.integration.test_runtime_full_import_pg import completed_pair
from tests.integration.test_runtime_full_import_pg import full_import_db as _full_import_db

full_import_db = _full_import_db


@pytest.mark.timeout(120)
@pytest.mark.parametrize('corrupt_second', [False, True], ids=['complete-replay', 'partial-commit'])
async def test_pinned_tcp_cli_actual_commit_and_replay(full_import_db, tmp_path, corrupt_second):
    options = connection_options()
    if options['host'].startswith('/'):
        pytest.skip('Explicit TCP proof requires the opted-in disposable CI service')
    _, observer = full_import_db
    database = await observer.fetchval('SELECT current_database()')
    user = await observer.fetchval('SELECT current_user')
    assert database.startswith('slomix_fixture_')
    root = tmp_path / 'spool'
    root.mkdir(mode=0o700)
    pair = completed_pair(root, balanced=True)
    if corrupt_second:
        second = pair[1].root / pair[1].generation / pair[1].filename
        second.write_bytes(second.read_bytes() + b'corrupted-after-completion\n')
    preserved = [(item.root / item.generation / item.filename).read_bytes() for item in pair]
    lock = tmp_path / 'lock'
    lock.mkdir(mode=0o700)
    config = tmp_path / 'import.env'
    # This is only the disposable fixture credential; never load an application .env.
    raw = ''.join(f'{key}={value}\n' for key, value in {
        'POSTGRES_HOST': options['host'], 'POSTGRES_PORT': options['port'],
        'POSTGRES_DATABASE': database, 'POSTGRES_USER': user,
        'POSTGRES_PASSWORD': options['password'],
    }.items()).encode()
    config.write_bytes(raw)
    config.chmod(0o600)
    args = ['--execute', '--env-file', str(config), '--config-sha256', hashlib.sha256(raw).hexdigest(),
            '--expected-target', options['host'], str(options['port']), database, user,
            '--writer-handover-confirmed', '--spool', str(root), '--lock-directory', str(lock),
            '--journal', 'enabled', '--defer-team-assignment']
    for number, item in enumerate(pair, start=1):
        args.extend([f'--r{number}', item.generation, item.filename, str(item.size), item.sha256])
    # Only the child is scrubbed: parent fixture authority remains intact.
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(('POSTGRES_', 'DB_', 'PG', 'DATABASE_'))
                   and key not in {'PYTHONPATH', 'PYTHONHOME', 'LD_PRELOAD', 'LD_LIBRARY_PATH',
                                   'LD_AUDIT', 'BOT_ENVIRONMENT'}}

    async def invoke():
        process = await asyncio.create_subprocess_exec(
            sys.executable, '-m', 'bot.runtime_import_cli', *args,
            cwd=Path(__file__).resolve().parents[2], env=environment,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), 45)
        finally:
            if process.returncode is None:
                process.kill()  # Own disposable CLI child, never a service/process discovered by name.
                await process.communicate()
        assert stderr == b''
        if corrupt_second:
            assert process.returncode == 1
            assert json.loads(stdout) == {'status': 'failed', 'source_acknowledged': False}
        else:
            assert process.returncode == 0
            assert json.loads(stdout) == {'status': 'completed', 'attempted': 2, 'successful': 2,
                                           'source_acknowledged': False}

    async def snapshot():
        tables = ('rounds', 'player_comprehensive_stats', 'weapon_comprehensive_stats',
                  'runtime_events', 'processed_files')
        result = {}
        for table in tables:
            rows = await observer.fetch(f'SELECT * FROM {table}')
            assert len(rows) == await observer.fetchval(f'SELECT count(*) FROM {table}')
            result[table] = rows
        return result

    await invoke()
    committed = await snapshot()
    expected_rounds = 1 if corrupt_second else 2
    assert len(committed['rounds']) == len(committed['runtime_events']) == len(committed['processed_files']) == expected_rounds
    assert len(committed['player_comprehensive_stats']) == 2 * expected_rounds
    await invoke()
    assert await snapshot() == committed
    for item, retained in zip(pair, preserved, strict=True):
        path = item.root / item.generation / item.filename
        assert path.read_bytes() == retained
        if not corrupt_second or item is pair[0]:
            assert hashlib.sha256(path.read_bytes()).hexdigest() == item.sha256
        assert path.with_name(path.name + '.complete.json').exists()
    assert config.read_bytes() == raw
    print(f'Two actual TCP CLI lifetimes: separate SQL observer sees {expected_rounds} committed imports, '
          f'unchanged replay and preserved sources; corrupt_second={corrupt_second}')
