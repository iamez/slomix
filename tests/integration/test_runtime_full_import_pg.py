"""Real canonical writers on a fresh full schema, only in opted-in disposable PG."""

import asyncio
import hashlib
import uuid
from pathlib import Path
from types import SimpleNamespace

import asyncpg
import pytest

from bot.runtime_completed_import import CompletedRoundInput, import_completed_round
from bot.runtime_import_attempt import ImportAttemptTimeout, run_import_once
from bot.runtime_import_batch import ImportJob, run_exclusive_import_batch, run_import_batch
from bot.runtime_import_session import open_import_session
from postgresql_database_manager import PostgreSQLDatabaseManager
from shared.runtime_completion_manifest import record_completion_once
from shared.runtime_import_pool import ImportDatabaseConfig, create_import_pool
from shared.runtime_source_reservation import reserve_source_generation
from shared.runtime_spool import publish_stats_file
from tests.disposable_database import isolated_database
from tests.integration.test_runtime_events_pg import connection_options


@pytest.fixture
async def full_import_db():
    """Create/drop one named test database; no application connection fallback."""
    connection_options()  # Explicit absent opt-in may skip, requested failures may not.
    async with isolated_database() as config:
        isolated = {key: config[key] for key in ('host', 'port', 'database', 'user', 'password')}
        isolated.update(timeout=5, command_timeout=5, ssl=False)
        pool = reader = None
        try:
            reader = await asyncpg.connect(**isolated)
            assert await reader.fetchval('SELECT current_database()') == config['database']
            assert await reader.fetchval('SELECT current_user') == config['user']
            schema = Path(__file__).resolve().parents[2] / 'tools/schema_postgresql.sql'
            await reader.execute(schema.read_text(), timeout=90)
            pool = await asyncpg.create_pool(**isolated, min_size=1, max_size=2)
            manager = PostgreSQLDatabaseManager(
                config=SimpleNamespace(database_type='postgresql'), allow_legacy_r1_fallback=False)
            manager.pool = pool
            manager.event_stream_enabled = True
            yield manager, reader
        finally:
            try:
                if pool is not None:
                    await asyncio.wait_for(pool.close(), 5)
            finally:
                if reader is not None:
                    await reader.close(timeout=5)


def completed_pair(root, *, balanced=False):
    """Synthetic player/weapon counts increase from one to two cumulatively."""
    root.chmod(0o700)
    inputs = []
    for number in (1, 2):
        filename = f'2026-09-25-120000-supply-round-{number}.txt'
        raw = (f'x\\supply\\x\\{number}\\2\\1\\20:00\\10:00\n'
               f'12345678\\Player\\1\\1\\1 {number} {number} {number} {number} {number}\n').encode()
        if balanced:
            raw += (f'87654321\\Opponent\\1\\2\\1 {number} {number} {number} {number} {number}\n').encode()
        digest = hashlib.sha256(raw).hexdigest()
        generation = str(number) * 32
        directory = reserve_source_generation(root, generation)
        publish_stats_file(directory, filename, [raw], expected_size=len(raw), expected_sha256=digest)
        record_completion_once(directory, {
            'version': 1, 'filename': filename, 'bytes': len(raw), 'state': 'writer_closed',
        }, expected_sha256=digest)
        inputs.append(CompletedRoundInput(root, generation, filename, len(raw), digest))
    return inputs


@pytest.fixture
async def owned_session_pools(full_import_db):
    """Contain leaked test connections even when a shutdown mutation fails.

    Depending on full_import_db ensures this cleanup precedes database removal.
    Successful close/disconnect assertions run before this fallback is invoked.
    """
    pools = []
    try:
        yield pools
    finally:
        for pool in pools:
            pool.terminate()


@pytest.mark.timeout(120)
@pytest.mark.parametrize('batch', [False, True, 'exclusive'])
async def test_single_attempt_deadline_after_commit_retains_replay(full_import_db, tmp_path, monkeypatch, batch):
    """A real deadline after COMMIT is ambiguous, not evidence of rollback."""
    _, reader = full_import_db
    options = connection_options()
    if not options['host'].startswith('/'):
        pytest.skip('One-shot adapter currently supports Unix sockets only')
    database = ImportDatabaseConfig(
        options['host'], await reader.fetchval('SELECT current_database()'),
        await reader.fetchval('SELECT current_user'), '',
        application_name='runtime_session_test_' + uuid.uuid4().hex,
    )
    first, second = completed_pair(tmp_path)
    reached = asyncio.Event()

    async def pause_before_marker(*args, **kwargs):
        reached.set()
        await asyncio.Event().wait()

    with monkeypatch.context() as patch:
        patch.setattr(PostgreSQLDatabaseManager, 'mark_file_processed', pause_before_marker)
        with pytest.raises(ImportAttemptTimeout):
            await run_import_once(database, first, journal_enabled=True, timeout=1)
    assert reached.is_set(), 'Deadline must occur after commit, not during connection setup'
    assert await reader.fetchval('SELECT count(*) FROM processed_files') == 0
    assert await reader.fetchval('SELECT count(*) FROM runtime_events') == 1
    if batch:
        jobs = (ImportJob(first), ImportJob(second, first=first))
        batch_runner = run_import_batch
        options = {}
        if batch == 'exclusive':
            lock_directory = tmp_path / 'writer'
            lock_directory.mkdir(mode=0o700)
            options['lock_directory'] = lock_directory
            batch_runner = run_exclusive_import_batch
        assert await batch_runner(database, jobs, journal_enabled=True, **options) == (
            (True, 'Processed: 1 players, 1 weapons'), (True, 'Processed: 1 players, 1 weapons'),
        )
        assert await batch_runner(database, jobs, journal_enabled=True, **options) == (
            (True, 'Already processed'), (True, 'Already processed'),
        )
    else:
        for item, dependency in ((first, None), (second, first)):
            assert await run_import_once(database, item, first=dependency, journal_enabled=True) == (
                True, 'Processed: 1 players, 1 weapons',
            )
            assert await run_import_once(database, item, first=dependency, journal_enabled=True) == (
                True, 'Already processed',
            )
    for table, expected in (('rounds', 3), ('player_comprehensive_stats', 3),
                            ('weapon_comprehensive_stats', 3), ('processed_files', 2), ('runtime_events', 2)):
        assert await reader.fetchval(f'SELECT count(*) FROM {table}') == expected
        assert len(await reader.fetch(f'SELECT * FROM {table}')) == expected
    for item in (first, second):
        source = item.root / item.generation / item.filename
        assert hashlib.sha256(source.read_bytes()).hexdigest() == item.sha256
        assert source.with_name(source.name + '.complete.json').exists()
    async def disconnected():
        while await reader.fetchval(
            'SELECT count(*) FROM pg_stat_activity WHERE application_name=$1', database.application_name,
        ):
            await asyncio.sleep(0.01)
    await asyncio.wait_for(disconnected(), 2)
    assert await reader.fetch(
        'SELECT pid FROM pg_stat_activity WHERE application_name=$1', database.application_name,
    ) == []
    print('Real one-shot deadline after COMMIT retained source; fresh attempts repaired marker and deduplicated')


@pytest.mark.timeout(120)
@pytest.mark.parametrize('configured', [False, True])
async def test_owned_sessions_reconnect_without_duplicate_import(
    full_import_db, tmp_path, owned_session_pools, configured,
):
    """Real new pools per session; no process-crash or independent-daemon claim."""
    _, reader = full_import_db
    options = connection_options()
    options['database'] = await reader.fetchval('SELECT current_database()')
    application = 'runtime_session_test_' + uuid.uuid4().hex
    owned_pools = owned_session_pools
    if configured:
        if not options['host'].startswith('/'):
            pytest.skip('Explicit import adapter currently supports Unix sockets only')
        supplied = ImportDatabaseConfig(
            socket=options['host'], database=options['database'],
            user=await reader.fetchval('SELECT current_user'), password='',
            application_name=application,
        )

    async def factory():
        if configured:
            pool = await create_import_pool(supplied)
        else:
            pool = await asyncpg.create_pool(
                **options, min_size=1, max_size=2,
                server_settings={'application_name': application},
            )
        owned_pools.append(pool)
        return pool

    first, second = completed_pair(tmp_path)
    notifications = asyncio.Queue()
    await reader.add_listener(
        'round_events', lambda conn, pid, channel, payload: notifications.put_nowait(payload),
    )
    tables = ('rounds', 'player_comprehensive_stats', 'weapon_comprehensive_stats',
              'processed_files', 'runtime_events')
    baseline = None
    for replay in (False, True):
        for current in (first, second):
            async with open_import_session(
                SimpleNamespace(database_type='postgresql'), pool_factory=factory, journal_enabled=True,
            ) as manager:
                if configured:
                    assert manager.pool.get_size() == 0 and manager.pool.get_max_size() == 1
                    assert await reader.fetchval(
                        'SELECT count(*) FROM pg_stat_activity WHERE application_name=$1', application,
                    ) == 0
                    async with manager.pool.acquire(timeout=2) as conn:
                        assert await conn.fetchval('SELECT current_database()') == supplied.database
                        assert await conn.fetchval('SELECT current_user') == supplied.user
                        assert await conn.fetchval('SHOW search_path') == 'public'
                        assert await conn.fetchval('SHOW statement_timeout') == '10s'
                        assert await conn.fetchval(
                            "SELECT setting::int FROM pg_settings WHERE name='statement_timeout'",
                        ) == 10000
                assert await reader.fetchval(
                    'SELECT count(*) FROM pg_stat_activity WHERE application_name=$1', application,
                ) == 1
                result = await import_completed_round(
                    manager, current, first=first if current is second else None,
                )
                assert result == (True, 'Already processed' if replay else 'Processed: 1 players, 1 weapons')
            assert manager.pool is None
            with pytest.raises(asyncpg.InterfaceError, match='closed'):
                async with owned_pools[-1].acquire():
                    pytest.fail('Session leaked an open pool')
            # Backend exit visibility may lag client-side close briefly.
            async def wait_for_disconnect():
                while await reader.fetchval(
                    'SELECT count(*) FROM pg_stat_activity WHERE application_name=$1', application,
                ):
                    await asyncio.sleep(0.01)
            await asyncio.wait_for(wait_for_disconnect(), 2)
            assert await reader.fetch(
                'SELECT pid FROM pg_stat_activity WHERE application_name=$1', application,
            ) == []
        rows = {table: [dict(row) for row in await reader.fetch(f'SELECT * FROM {table} ORDER BY id')]
                for table in tables}
        if replay:
            assert rows == baseline
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(notifications.get(), 0.1)
        else:
            assert [len(rows[table]) for table in tables] == [3, 3, 3, 2, 2]
            for event in rows['runtime_events']:
                assert await asyncio.wait_for(notifications.get(), 2) == str(event['id'])
            baseline = rows
    assert len(owned_pools) == len({id(pool) for pool in owned_pools}) == 4
    print('Four real owned pools closed; R1/R2 persisted once, fresh-session replay unchanged')


@pytest.mark.timeout(120)
async def test_completed_pair_persists_real_player_weapon_rows(full_import_db, tmp_path):
    """No parser, writer, validation, marker or post-import method is stubbed."""
    manager, reader = full_import_db
    first, second = completed_pair(tmp_path)
    result = await import_completed_round(manager, first)
    assert result[0], result
    result = await import_completed_round(manager, second, first=first)
    assert result[0], result
    for table, expected in (
        ('rounds', 3), ('player_comprehensive_stats', 3),
        ('weapon_comprehensive_stats', 3), ('processed_files', 2), ('runtime_events', 2),
    ):
        rows = await reader.fetch(f'SELECT * FROM {table}')
        assert len(rows) == expected, (table, rows)
        assert await reader.fetchval(f'SELECT count(*) FROM {table}') == expected
    players = await reader.fetch('''
        SELECT r.round_number, p.player_guid, p.kills, p.deaths
        FROM player_comprehensive_stats p JOIN rounds r ON r.id = p.round_id
        ORDER BY r.round_number
    ''')
    assert [tuple(row) for row in players] == [
        (0, '12345678', 2, 2), (1, '12345678', 1, 1), (2, '12345678', 1, 1),
    ]
    weapons = await reader.fetch('''
        SELECT r.round_number, w.kills, w.deaths, w.shots, w.hits, w.headshots
        FROM weapon_comprehensive_stats w JOIN rounds r ON r.id = w.round_id
        ORDER BY r.round_number
    ''')
    assert [tuple(row) for row in weapons] == [
        (0, 2, 2, 2, 2, 2), (1, 1, 1, 1, 1, 1), (2, 1, 1, 1, 1, 1),
    ]
    assert await reader.fetchval('''
        SELECT sum(p.kills) FROM player_comprehensive_stats p
        JOIN rounds r ON r.id=p.round_id WHERE r.round_number IN (1, 2)
    ''') == 2
    events = await reader.fetch('SELECT round_number, source_filename FROM runtime_events ORDER BY round_number')
    assert [tuple(row) for row in events] == [(1, first.filename), (2, second.filename)]
    assert await reader.fetchval('SELECT bool_and(success) FROM processed_files') is True
    assert await reader.fetchval('SELECT bool_and(validation_passed) FROM runtime_events') is True
    for item in (first, second):
        source = item.root / item.generation / item.filename
        raw = source.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == item.sha256
        expected_hash = hashlib.sha256(b'\n'.join(raw.splitlines()[1:])).hexdigest()
        assert await reader.fetchval(
            'SELECT file_hash FROM processed_files WHERE filename=$1', item.filename,
        ) == expected_hash
        assert await reader.fetchval(
            'SELECT source_payload_sha256 FROM runtime_events WHERE source_filename=$1', item.filename,
        ) == expected_hash
        assert source.with_name(source.name + '.complete.json').exists()
    assert await import_completed_round(manager, second, first=first) == (True, 'Already processed')
    assert await reader.fetchval('SELECT count(*) FROM runtime_events') == 2
    assert await reader.fetchval('SELECT count(*) FROM player_comprehensive_stats') == 3
    print('Full-schema proof: R1/R2/R0 real player+weapon rows; two markers/events; repeat idempotent')


@pytest.mark.timeout(120)
async def test_missing_players_persist_validation_warning(full_import_db, tmp_path, monkeypatch):
    """Fault injection retains existing save-with-warning, but flags incomplete data."""
    manager, reader = full_import_db
    first, _ = completed_pair(tmp_path)

    async def omit_players(*args):
        return 0

    monkeypatch.setattr(manager, '_insert_player_stats', omit_players)
    result = await import_completed_round(manager, first)
    assert result == (True, 'Processed: 0 players, 1 weapons (WITH WARNINGS)')
    assert await reader.fetchval('SELECT count(*) FROM player_comprehensive_stats') == 0
    assert await reader.fetch('SELECT * FROM player_comprehensive_stats') == []
    assert await reader.fetchval('SELECT count(*) FROM weapon_comprehensive_stats') == 1
    assert await reader.fetchval('SELECT validation_passed FROM runtime_events') is False
    marker = await reader.fetchrow('SELECT success, error_message FROM processed_files')
    assert marker['success'] is True
    assert marker['error_message'].startswith('WARN: Import totals mismatch: players: expected 1, stored 0')
    print('Full-schema fault proof: missing player detected; event false; marker WARN; no rollback policy change')


@pytest.mark.timeout(120)
@pytest.mark.parametrize('round_number', [1, 2])
@pytest.mark.parametrize('failure', ['exception', 'cancellation'])
async def test_full_import_rolls_back_and_retries(
    full_import_db, tmp_path, monkeypatch, round_number, failure,
):
    """Interrupt after real writes/event; separate connection must see no partial data."""
    import postgresql_database_manager as canonical

    manager, reader = full_import_db
    first, second = completed_pair(tmp_path)
    current = first if round_number == 1 else second
    expected_rows = 1 if round_number == 1 else 2  # R2 also writes its R0 summary.
    tables = ('rounds', 'player_comprehensive_stats', 'weapon_comprehensive_stats',
              'runtime_events', 'processed_files')
    notifications = asyncio.Queue()
    await reader.add_listener(
        'round_events', lambda conn, pid, channel, payload: notifications.put_nowait(payload),
    )
    reached = asyncio.Event()
    original_emit = canonical.emit_round_stats_imported

    async def attempt():
        return await import_completed_round(manager, current, first=first if round_number == 2 else None)

    async def interrupt_after_event(conn, **kwargs):
        event_id = await original_emit(conn, **kwargs)
        assert event_id is not None
        # Prove the fault occurs after real data writes, not an earlier refusal.
        for table in tables[:3]:
            assert await conn.fetchval(f'SELECT count(*) FROM {table}') == expected_rows
        assert await conn.fetchval('SELECT count(*) FROM runtime_events') == 1
        reached.set()
        if failure == 'exception':
            raise RuntimeError('fixture failure after full import event')
        await asyncio.Event().wait()

    with monkeypatch.context() as patch:
        patch.setattr(canonical, 'emit_round_stats_imported', interrupt_after_event)
        if failure == 'exception':
            result = await attempt()
            assert result == (False, 'fixture failure after full import event') and result.retryable
        else:
            task = asyncio.create_task(attempt())
            try:
                await asyncio.wait_for(reached.wait(), 5)
                for table in tables:
                    assert await reader.fetchval(f'SELECT count(*) FROM {table}') == 0
            finally:
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
    assert reached.is_set()
    for table in tables:
        assert await reader.fetchval(f'SELECT count(*) FROM {table}') == 0
        assert await reader.fetch(f'SELECT * FROM {table}') == []
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(notifications.get(), 0.1)
    for item in (first, second):
        source = item.root / item.generation / item.filename
        assert hashlib.sha256(source.read_bytes()).hexdigest() == item.sha256
        assert source.with_name(source.name + '.complete.json').exists()

    result = await attempt()
    assert result == (True, 'Processed: 1 players, 1 weapons')
    for table in tables:
        expected = expected_rows if table in tables[:3] else 1
        assert await reader.fetchval(f'SELECT count(*) FROM {table}') == expected
        assert len(await reader.fetch(f'SELECT * FROM {table}')) == expected
    event = await reader.fetchrow('SELECT id, round_number, validation_passed FROM runtime_events')
    assert event['round_number'] == round_number and event['validation_passed'] is True
    assert await asyncio.wait_for(notifications.get(), 2) == str(event['id'])
    assert await attempt() == (True, 'Already processed')
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(notifications.get(), 0.1)
    print(f'Full-schema R{round_number} {failure}: real writes rolled back; retained source retries once')


@pytest.mark.timeout(120)
@pytest.mark.parametrize('round_number', [1, 2])
async def test_postcommit_cancel_recovers_with_fresh_manager(
    full_import_db, tmp_path, monkeypatch, round_number,
):
    """Cancel after commit/before marker; retry through a fresh manager, not a process crash."""
    manager, reader = full_import_db
    first, second = completed_pair(tmp_path)
    current = first if round_number == 1 else second
    dependency = first if round_number == 2 else None
    marker_reached = asyncio.Event()
    notifications = asyncio.Queue()
    await reader.add_listener(
        'round_events', lambda conn, pid, channel, payload: notifications.put_nowait(payload),
    )

    async def pause_before_marker(*args, **kwargs):
        marker_reached.set()
        await asyncio.Event().wait()

    tables = ('rounds', 'player_comprehensive_stats', 'weapon_comprehensive_stats', 'runtime_events')
    before = {}
    with monkeypatch.context() as patch:
        patch.setattr(manager, 'mark_file_processed', pause_before_marker)
        task = asyncio.create_task(import_completed_round(manager, current, first=dependency))
        try:
            await asyncio.wait_for(marker_reached.wait(), 5)
            # The independent observer sees committed data, but no completion marker.
            for table in tables:
                rows = await reader.fetch(f'SELECT * FROM {table} ORDER BY id')
                expected = 1 if table == 'runtime_events' or round_number == 1 else 2
                assert len(rows) == expected
                assert await reader.fetchval(f'SELECT count(*) FROM {table}') == expected
                before[table] = [dict(row) for row in rows]
            assert await reader.fetch('SELECT * FROM processed_files') == []
            event_id = before['runtime_events'][0]['id']
            assert await asyncio.wait_for(notifications.get(), 2) == str(event_id)
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
    assert marker_reached.is_set()
    assert await reader.fetchval('SELECT count(*) FROM processed_files') == 0
    fresh = PostgreSQLDatabaseManager(
        config=SimpleNamespace(database_type='postgresql'), allow_legacy_r1_fallback=False)
    fresh.pool = manager.pool
    fresh.event_stream_enabled = True
    result = await import_completed_round(fresh, current, first=dependency)
    assert result == (True, 'Processed: 1 players, 1 weapons')
    for table in tables:
        rows = await reader.fetch(f'SELECT * FROM {table} ORDER BY id')
        assert [dict(row) for row in rows] == before[table], table
    marker = await reader.fetchrow('SELECT filename, success FROM processed_files')
    assert dict(marker) == {'filename': current.filename, 'success': True}
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(notifications.get(), 0.1)
    assert await import_completed_round(fresh, current, first=dependency) == (True, 'Already processed')
    print(f'Full-schema R{round_number}: commit survives cancellation; fresh manager restores marker without duplication')
