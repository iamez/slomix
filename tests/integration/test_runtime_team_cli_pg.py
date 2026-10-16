"""Opt-in real-process team CLI acceptance on a disposable Unix-socket DB.

The operator must verify the approved cluster before setting the opt-in. This
module never starts PostgreSQL or selects an ambient application target. Without
that cluster, collection/skips are not native acceptance. The existing full
schema fixture closes its connections and drops its own database without FORCE.
"""

import asyncio
import json
import os
import signal
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from bot.runtime_completed_import import import_completed_round
from shared.runtime_team_consumer import CONSUMER
from tests.integration.test_runtime_events_pg import connection_options
from tests.integration.test_runtime_full_import_pg import completed_pair
from tests.integration.test_runtime_full_import_pg import full_import_db as _full_import_db

full_import_db = _full_import_db
FLAGS = ('EVENT_STREAM_ENABLED', 'RUNTIME_TEAM_EVENTS_ENABLED', 'RUNTIME_TEAM_WORKER_ENABLED')
APPLICATION = 'slomix-runtime-team-dev'


def private_target():
    options = connection_options()
    if not options['host'].startswith('/'):
        pytest.skip('Team CLI requires an explicitly approved private Unix test socket')
    return options


@pytest.fixture
def native_cli_db(request):
    # Validate/skip BEFORE requesting the fixture which creates the database.
    target = private_target()
    importer, observer = request.getfixturevalue('full_import_db')
    return target, importer, observer


@pytest.mark.parametrize('configured', [False, True])
def test_cli_native_target_guard_precedes_database_fixture(monkeypatch, configured):
    for name in ('RUNTIME_EVENTS_TEST_SOCKET', 'RUNTIME_EVENTS_TEST_CI'):
        monkeypatch.delenv(name, raising=False)
    if configured:
        for name, value in {
            'RUNTIME_EVENTS_TEST_CI': 'true', 'GITHUB_ACTIONS': 'true',
            'POSTGRES_TEST_HOST': '127.0.0.1', 'POSTGRES_TEST_PORT': '5432',
            'POSTGRES_TEST_DATABASE': 'etlegacy_test', 'POSTGRES_TEST_USER': 'etlegacy_user',
            'POSTGRES_TEST_PASSWORD': 'fixture-only',
        }.items():
            monkeypatch.setenv(name, value)
    requested = []

    def forbidden_fixture(name):
        requested.append(name)
        pytest.fail('Database fixture requested before private target validation')

    request = SimpleNamespace(getfixturevalue=forbidden_fixture)
    with pytest.raises(pytest.skip.Exception):
        native_cli_db.__wrapped__(request)
    assert requested == []


async def run_cli(target, observer, cwd):
    database = await observer.fetchval('SELECT current_database()')
    role = await observer.fetchval('SELECT current_user')
    child = await asyncio.create_subprocess_exec(
        sys.executable, '-m', 'shared.runtime_team_cli', '--execute',
        '--socket', target['host'], '--port', str(target['port']),
        '--database', database, '--user', role,
        '--run-seconds', '1', '--poll-seconds', '60',
        '--attempt-timeout', '10', '--close-timeout', '5',
        cwd=cwd,
        env={**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[2]),
             **dict.fromkeys(FLAGS, 'true')},
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    output = asyncio.create_task(child.communicate())
    try:
        stdout, stderr = await asyncio.wait_for(asyncio.shield(output), 20)
    finally:
        if child.returncode is None:
            child.kill()  # Only this test-owned child; never a service process.
        captured = await output
    assert child.returncode == 0, captured
    assert stderr == b''
    report = json.loads(stdout)
    assert report['status'] == 'stopped'
    assert report['has_successful_page'] is True
    assert report['last_error_type'] is None
    assert report['source_acknowledged'] is False
    # Pool ownership is measured independently of the child's JSON/exit code.
    query = 'SELECT pid FROM pg_stat_activity WHERE datname=$1 AND application_name=$2'
    async def disconnected():
        while await observer.fetch(query, database, APPLICATION):
            await asyncio.sleep(0.01)
    await asyncio.wait_for(disconnected(), 2)
    assert await observer.fetch(query, database, APPLICATION) == []
    assert await observer.fetchval(
        'SELECT count(*) FROM pg_stat_activity WHERE datname=$1 AND application_name=$2',
        database, APPLICATION,
    ) == 0
    return child.pid, report


@pytest.mark.timeout(150)
async def test_real_team_cli_commits_replays_and_disconnects(native_cli_db, tmp_path):
    target, importer, observer = native_cli_db
    importer.defer_team_assignment = True
    first, _ = completed_pair(tmp_path, balanced=True)
    assert (await import_completed_round(importer, first))[0] is True
    for table in ('session_teams', 'runtime_consumer_receipts'):
        assert await observer.fetch(f'SELECT * FROM {table}') == []
        assert await observer.fetchval(f'SELECT count(*) FROM {table}') == 0
    events = await observer.fetch('SELECT * FROM runtime_events ORDER BY id')
    assert len(events) == await observer.fetchval('SELECT count(*) FROM runtime_events') == 1
    snapshots, reports, pids = [], [], []
    for _ in range(2):
        pid, report = await run_cli(target, observer, tmp_path)
        pids.append(pid)
        reports.append(report)
        teams = await observer.fetch('SELECT * FROM session_teams ORDER BY id')
        receipts = await observer.fetch('SELECT * FROM runtime_consumer_receipts ORDER BY event_id')
        assert len(teams) == await observer.fetchval('SELECT count(*) FROM session_teams') == 2
        assert len(receipts) == await observer.fetchval('SELECT count(*) FROM runtime_consumer_receipts') == 1
        assert receipts[0]['consumer_name'] == CONSUMER
        assert receipts[0]['event_id'] == events[0]['id']
        assert await observer.fetch('SELECT * FROM runtime_events ORDER BY id') == events
        snapshots.append((teams, receipts))
    assert pids[0] != pids[1]
    assert reports[0]['last_page'] == dict(inspected=1, processed=1, pending=0, already_processed=0)
    assert reports[1]['last_page'] == dict(inspected=0, processed=0, pending=0, already_processed=0)
    assert snapshots[0] == snapshots[1]
    print('native CLI: two real processes, two teams, one stable receipt, unchanged replay, no child connections')


def import_command(target, database, role, root, lock, pair):
    # The importer CLI currently exposes only its fixed default port. Never
    # silently run the two children against different database servers.
    if target['port'] != 5432:
        raise ValueError('Connected importer CLI requires the explicit port 5432 target')
    command = [sys.executable, '-m', 'bot.runtime_import_cli', '--execute',
               '--socket', target['host'], '--database', database, '--user', role,
               '--spool', str(root), '--lock-directory', str(lock),
               '--journal', 'enabled', '--defer-team-assignment']
    for number, item in enumerate(pair, start=1):
        command.extend([f'--r{number}', item.generation, item.filename, str(item.size), item.sha256])
    return command


def test_connected_command_preserves_target_and_deferred_policy(tmp_path):
    from bot.runtime_import_cli import parser

    pair = completed_pair(tmp_path, balanced=True)
    target = {'host': '/tmp/slomix-runtime-pg-fixture', 'port': 5432}
    command = import_command(target, 'fixture_database', 'fixture_role', tmp_path, tmp_path / 'writer', pair)
    args = parser().parse_args(command[3:])
    assert args.execute is True and args.journal == 'enabled' and args.defer_team_assignment is True
    assert (args.socket, args.database, args.user) == (target['host'], 'fixture_database', 'fixture_role')
    assert args.spool == str(tmp_path) and args.lock_directory == str(tmp_path / 'writer')
    for item, fields in zip(pair, (args.r1, args.r2), strict=True):
        assert fields == [item.generation, item.filename, str(item.size), item.sha256]
    with pytest.raises(ValueError, match='port 5432'):
        import_command({**target, 'port': 5433}, 'fixture_database', 'fixture_role', tmp_path, tmp_path, pair)


async def run_import_cli(target, observer, root, lock, pair):
    database = await observer.fetchval('SELECT current_database()')
    role = await observer.fetchval('SELECT current_user')
    child = await asyncio.create_subprocess_exec(
        *import_command(target, database, role, root, lock, pair), cwd=root,
        env={**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[2]),
             # Explicit importer journal policy must override ambient OFF.
             **dict.fromkeys(FLAGS, 'false')},
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    output = asyncio.create_task(child.communicate())
    try:
        stdout, stderr = await asyncio.wait_for(asyncio.shield(output), 30)
    finally:
        if child.returncode is None:
            child.kill()  # Only the child created by this test, never a service.
        captured = await output
    assert child.returncode == 0, captured
    assert stderr == b''
    assert json.loads(stdout) == dict(status='completed', attempted=2, successful=2, source_acknowledged=False)
    query = 'SELECT pid FROM pg_stat_activity WHERE datname=$1 AND application_name=$2'
    async def disconnected():
        while await observer.fetch(query, database, 'slomix-runtime-import-dev'):
            await asyncio.sleep(0.01)
    await asyncio.wait_for(disconnected(), 2)
    assert await observer.fetch(query, database, 'slomix-runtime-import-dev') == []
    assert await observer.fetchval(
        'SELECT count(*) FROM pg_stat_activity WHERE datname=$1 AND application_name=$2',
        database, 'slomix-runtime-import-dev',
    ) == 0
    return child.pid


async def session_rounds_http(observer, session_id):
    """Actual router/serialization; only its database dependency is supplied.

    No main-app startup, TCP listener, browser or synthetic Lua roster. Native
    callers forward both endpoint SELECTs to the same committed fixture DB.
    """
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from website.backend.dependencies import get_db
    from website.backend.routers.sessions_router import router

    class Reader:
        async def fetch_all(self, query, params=None):
            return await observer.fetch(query, *(params or ()))

    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: Reader()
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://fixture') as client:
        response = await client.get(f'/api/stats/session/{session_id}/rounds')
    return response.status_code, response.json()


def assert_rounds_http_rows(body, session_id, round_rows, player_rows):
    """Independent selected columns, not values computed by endpoint SQL."""
    assert body['gaming_session_id'] == session_id
    expected = {row[0]: row[1] for row in round_rows if row[1] in (1, 2)}
    assert len(round_rows) == 3 and sorted(row[1] for row in round_rows) == [0, 1, 2]
    assert body['total_rounds'] == 2
    assert len(body['rounds']) == 2
    assert {r['round_id']: r['round_number'] for r in body['rounds']} == expected
    for round_ in body['rounds']:
        actual = sorted((p['player_guid'], p['kills'], p['damage_given']) for p in round_['players'])
        wanted = sorted((row[1], row[2], row[3]) for row in player_rows if row[0] == round_['round_id'])
        assert wanted and actual == wanted


async def verified_session_rounds_http(observer, session_id):
    rounds = await observer.fetch(
        'SELECT id, round_number FROM rounds WHERE gaming_session_id=$1 ORDER BY id', session_id,
    )
    players = await observer.fetch(
        'SELECT p.round_id, p.player_guid, p.kills, p.damage_given '
        'FROM player_comprehensive_stats p JOIN rounds r ON r.id=p.round_id '
        'WHERE r.gaming_session_id=$1 ORDER BY p.round_id, p.player_guid', session_id,
    )
    status, body = await session_rounds_http(observer, session_id)
    assert status == 200
    assert_rounds_http_rows(body, session_id, rounds, players)
    for round_ in body['rounds']:
        totals = await observer.fetchrow(
            'SELECT COUNT(*), SUM(kills), SUM(damage_given) FROM player_comprehensive_stats WHERE round_id=$1',
            round_['round_id'],
        )
        assert tuple(totals) == (len(round_['players']), sum(p['kills'] for p in round_['players']),
                                 sum(p['damage_given'] for p in round_['players']))
    return body


@pytest.mark.timeout(180)
async def test_connected_import_and_team_cli_pair_replay(native_cli_db, tmp_path):
    import hashlib

    target, _, observer = native_cli_db
    pair = completed_pair(tmp_path, balanced=True)
    lock = tmp_path / 'writer'
    lock.mkdir(mode=0o700)
    expected = {'rounds': 3, 'player_comprehensive_stats': 6, 'weapon_comprehensive_stats': 6,
                'processed_files': 2, 'runtime_events': 2}

    async def snapshot(counts):
        result = {}
        for table, count in counts.items():
            rows = await observer.fetch(f'SELECT * FROM {table}')
            assert len(rows) == await observer.fetchval(f'SELECT count(*) FROM {table}') == count
            result[table] = sorted((tuple(row) for row in rows), key=repr)
        return result

    first_import_pid = await run_import_cli(target, observer, tmp_path, lock, pair)
    before = await snapshot({**expected, 'session_teams': 0, 'runtime_consumer_receipts': 0})
    session_ids = await observer.fetch('SELECT DISTINCT gaming_session_id FROM rounds')
    assert len(session_ids) == 1 and session_ids[0][0] is not None
    session_id = session_ids[0][0]
    before_http = await verified_session_rounds_http(observer, session_id)
    # Session identity is carried by rounds; there is no gaming_sessions table.
    absent_id = await observer.fetchval('SELECT COALESCE(MAX(gaming_session_id), 0) + 1 FROM rounds')
    assert not await observer.fetchval('SELECT EXISTS(SELECT 1 FROM rounds WHERE gaming_session_id=$1)', absent_id)
    status, missing = await session_rounds_http(observer, absent_id)
    assert status == 404 and missing == {'detail': 'Session not found'}
    first_consumer_pid, report = await run_cli(target, observer, tmp_path)
    assert report['last_page'] == dict(inspected=2, processed=1, pending=1, already_processed=0)
    after = await snapshot({**expected, 'session_teams': 2, 'runtime_consumer_receipts': 1})
    assert await verified_session_rounds_http(observer, session_id) == before_http
    for table in expected:
        assert before[table] == after[table]
    receipt = await observer.fetchrow('SELECT event_id, consumer_name FROM runtime_consumer_receipts')
    assert receipt['consumer_name'] == CONSUMER
    assert await observer.fetchval(
        'SELECT r.round_number FROM runtime_events e JOIN rounds r ON r.id=e.round_id WHERE e.id=$1',
        receipt['event_id'],
    ) == 1
    # R2 is deliberately ineligible, not acknowledged or hidden by a cursor.
    pending = await observer.fetch(
        'SELECT r.round_number FROM runtime_events e JOIN rounds r ON r.id=e.round_id '
        'WHERE NOT EXISTS (SELECT 1 FROM runtime_consumer_receipts c '
        'WHERE c.event_id=e.id AND c.consumer_name=$1)', CONSUMER,
    )
    assert [row['round_number'] for row in pending] == [2]
    second_import_pid = await run_import_cli(target, observer, tmp_path, lock, pair)
    assert await snapshot({**expected, 'session_teams': 2, 'runtime_consumer_receipts': 1}) == after
    second_consumer_pid, replay = await run_cli(target, observer, tmp_path)
    assert replay['last_page'] == dict(inspected=1, processed=0, pending=1, already_processed=0)
    assert first_import_pid != second_import_pid and first_consumer_pid != second_consumer_pid
    assert await verified_session_rounds_http(observer, session_id) == before_http
    assert await snapshot({**expected, 'session_teams': 2, 'runtime_consumer_receipts': 1}) == after
    for item in pair:
        source = item.root / item.generation / item.filename
        assert source.stat().st_size == item.size
        assert hashlib.sha256(source.read_bytes()).hexdigest() == item.sha256
        assert source.with_name(source.name + '.complete.json').exists()
    print('connected native CLI: four processes, R1 receipt stable, R2 pending, rows replay-stable, pools closed')


@pytest.mark.asyncio
async def test_connected_import_launcher_protocol_without_database(monkeypatch, tmp_path):
    """Exercise subprocess admission/cleanup checks with explicit protocol doubles."""
    from unittest.mock import AsyncMock

    from bot.runtime_import_cli import parser

    target = {'host': '/tmp/slomix-runtime-pg-fixture', 'port': 5432}
    observer = SimpleNamespace(fetch=AsyncMock(return_value=[]),
                               fetchval=AsyncMock(side_effect=['fixture_database', 'fixture_role', 0]))
    output = json.dumps(dict(status='completed', attempted=2, successful=2, source_acknowledged=False)).encode()
    child = SimpleNamespace(pid=12345, returncode=0, communicate=AsyncMock(return_value=(output, b'')))
    launches = []

    async def launch(*command, **kwargs):
        launches.append(command)
        args = parser().parse_args(command[3:])
        assert (args.socket, args.database, args.user) == (target['host'], 'fixture_database', 'fixture_role')
        assert args.defer_team_assignment is True and args.journal == 'enabled'
        assert kwargs['cwd'] == tmp_path
        assert all(kwargs['env'][flag] == 'false' for flag in FLAGS)
        return child

    monkeypatch.setattr(asyncio, 'create_subprocess_exec', launch)
    pid = await run_import_cli(target, observer, tmp_path, tmp_path / 'writer', completed_pair(tmp_path, balanced=True))
    assert pid == 12345 and len(launches) == 1
    child.communicate.assert_awaited_once()
    assert observer.fetch.await_count == 2
    assert observer.fetchval.await_args.args[1:] == ('fixture_database', 'slomix-runtime-import-dev')
    print('protocol-double runtime: explicit shared target, deferred journal, ambient OFF, cleanup queries executed')


@pytest.mark.asyncio
async def test_session_rounds_asgi_protocol_without_database():
    """Offline adapter/HTTP proof; does not claim SQL or committed rows."""
    queries = []
    class Observer:
        async def fetch(self, query, *args):
            queries.append((query, args))
            assert args in ((7,), (8,))
            if args == (8,):
                return []
            if 'player_comprehensive_stats' in query:
                return [(10, 'A', 'Alpha', 1, 60, 0, 0, 90, 3, 1, 0, 0, 0, 0, 0),
                        (11, 'A', 'Alpha', 2, 60, 0, 0, 150, 5, 1, 0, 0, 0, 0, 0)]
            return [(10, 'supply', 1, '2026-10-15 12:00:00', 60, None, 'completed', 'm', True, False),
                    (11, 'supply', 2, '2026-10-15 12:01:00', 60, None, 'completed', 'm', True, False)]
    status, body = await session_rounds_http(Observer(), 7)
    assert status == 200
    assert_rounds_http_rows(body, 7, [(9, 0), (10, 1), (11, 2)],
                           [(9, 'A', 8, 240), (10, 'A', 3, 90), (11, 'A', 5, 150)])
    # Exercise the verifier's R0 guard without pretending the fixture executes SQL.
    import copy
    bad = copy.deepcopy(body)
    bad['rounds'].append({**bad['rounds'][0], 'round_id': 9, 'round_number': 0})
    with pytest.raises(AssertionError):
        assert_rounds_http_rows(bad, 7, [(9, 0), (10, 1), (11, 2)], [(10, 'A', 3, 90)])
    assert await session_rounds_http(Observer(), 8) == (404, {'detail': 'Session not found'})
    assert len(queries) == 3
    assert 'r.round_number IN (1, 2)' in queries[0][0]


@pytest.mark.timeout(120)
@pytest.mark.parametrize('blocked', [False, True], ids=['after-commit', 'blocked-before-effect'])
async def test_team_cli_sigterm_drains_and_closes(native_cli_db, tmp_path, blocked):
    """Signal only our child; no systemd, Discord or ambient application target."""
    target, importer, observer = native_cli_db
    importer.defer_team_assignment = True
    first, _ = completed_pair(tmp_path, balanced=True)
    assert (await import_completed_round(importer, first))[0] is True
    database = await observer.fetchval('SELECT current_database()')
    role = await observer.fetchval('SELECT current_user')
    lock = observer.transaction()
    locked = False
    child = output = None
    try:
        if blocked:
            await lock.start()
            locked = True
            await observer.execute('LOCK TABLE session_teams IN ACCESS EXCLUSIVE MODE')
        child = await asyncio.create_subprocess_exec(
            sys.executable, '-m', 'shared.runtime_team_cli', '--execute',
            '--socket', target['host'], '--port', str(target['port']),
            '--database', database, '--user', role,
            '--run-seconds', '60', '--poll-seconds', '60',
            '--attempt-timeout', '2', '--close-timeout', '5',
            cwd=tmp_path,
            env={**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[2]),
                 **dict.fromkeys(FLAGS, 'true')},
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        output = asyncio.create_task(child.communicate())
        async with asyncio.timeout(10):
            while True:
                if blocked:
                    # This observer holds the lock transaction; PostgreSQL
                    # caches activity snapshots until explicitly refreshed.
                    await observer.fetchval('SELECT pg_stat_clear_snapshot()')
                    ready = await observer.fetchval(
                        "SELECT count(*) FROM pg_stat_activity WHERE datname=$1 "
                        "AND application_name=$2 AND wait_event_type='Lock'", database, APPLICATION,
                    ) == 1
                else:
                    ready = await observer.fetchval('SELECT count(*) FROM runtime_consumer_receipts') == 1
                if ready:
                    break
                assert child.returncode is None, await output if output.done() else 'Premature child exit'
                await asyncio.sleep(0.01)
        child.send_signal(signal.SIGTERM)
        stdout, stderr = await asyncio.wait_for(asyncio.shield(output), 8)
        assert stderr == b''
        assert child.returncode == (1 if blocked else 0), (stdout, stderr)
        report = json.loads(stdout)
        assert report['status'] == 'stopped' and report['source_acknowledged'] is False
        assert report['has_successful_page'] is not blocked
        if blocked:
            assert report['last_page'] is None and report['last_error_type'] == 'TimeoutError'
            await lock.rollback()
            locked = False
        else:
            assert report['last_error_type'] is None
            assert report['last_page'] == dict(inspected=1, processed=1, pending=0, already_processed=0)
        for table, count in (('session_teams', 0 if blocked else 2),
                             ('runtime_consumer_receipts', 0 if blocked else 1)):
            assert len(await observer.fetch(f'SELECT * FROM {table}')) == count
            assert await observer.fetchval(f'SELECT count(*) FROM {table}') == count
        assert await observer.fetch(
            'SELECT pid FROM pg_stat_activity WHERE datname=$1 AND application_name=$2', database, APPLICATION,
        ) == []
        print(f'native team SIGTERM blocked={blocked}: exit={child.returncode}, effects consistent, pool disconnected')
    finally:
        if child is not None:
            if child.returncode is None:
                child.kill()  # Failure containment for this owned fixture child only.
            if output is not None:
                await output
        if locked:
            await lock.rollback()
