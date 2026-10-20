"""Connection-owned team effect and caller transaction, only in disposable PG."""

from unittest.mock import AsyncMock

import asyncpg
import pytest

from bot.runtime_completed_import import import_completed_round
from shared.import_team_assignment import TeamAssignment, assign_round_teams
from shared.team_write_guard import TeamWriteBusy, team_write_transaction
from tests.integration.test_runtime_full_import_pg import completed_pair
from tests.integration.test_runtime_full_import_pg import full_import_db as _full_import_db

full_import_db = _full_import_db


@pytest.mark.timeout(120)
@pytest.mark.parametrize('operation', ['create', 'update', 'repair'])
async def test_manager_entry_guards_cover_reads_and_outer_lifetime(full_import_db, tmp_path, operation):
    from bot.core.database_adapter import PostgreSQLAdapter
    from bot.core.team_manager import TeamManager

    manager, conn = full_import_db
    first, _ = completed_pair(tmp_path, balanced=True)
    assert (await import_completed_round(manager, first))[0] is True
    round_row = await conn.fetchrow('SELECT id, gaming_session_id FROM rounds WHERE round_number=1')
    adapter = PostgreSQLAdapter('unused', 5432, 'unused', 'unused', '')
    adapter.pool = manager.pool
    teams = TeamManager(adapter)
    original = await conn.fetch('SELECT * FROM session_teams ORDER BY id')

    async def operate():
        if operation == 'create':
            return await teams.create_initial_teams_from_round(round_row['id'], '2026-09-25', round_row['gaming_session_id'])
        if operation == 'update':
            return await teams.update_teams_from_round(round_row['id'], '2026-09-25', round_row['gaming_session_id'])
        return await teams.get_session_teams('2026-09-25', gaming_session_id=round_row['gaming_session_id'])

    async with team_write_transaction(conn):
        if operation == 'repair':
            with pytest.raises(TeamWriteBusy):
                await operate()
        else:
            assert await operate() == (False if operation == 'create' else {})
        assert await conn.fetch('SELECT * FROM session_teams ORDER BY id') == original
    async with adapter.transaction():
        assert await operate()
        with pytest.raises(TeamWriteBusy):
            await assign_round_teams(conn, round_id=round_row['id'], session_date='2026-09-25')
    assert await conn.fetch('SELECT * FROM session_teams ORDER BY id') == original
    assert len(original) == await conn.fetchval('SELECT count(*) FROM session_teams') == 2
    assert await assign_round_teams(conn, round_id=round_row['id'], session_date='2026-09-25') is TeamAssignment.ALREADY_ASSIGNED


@pytest.mark.timeout(120)
@pytest.mark.parametrize('writer', ['replace', 'random'])
async def test_pair_writer_guard_and_nested_naming(full_import_db, tmp_path, monkeypatch, writer):
    import random

    from bot.core.database_adapter import PostgreSQLAdapter
    from bot.core.team_manager import TeamManager

    manager, conn = full_import_db
    first, _ = completed_pair(tmp_path, balanced=True)
    assert (await import_completed_round(manager, first))[0] is True
    round_row = await conn.fetchrow('SELECT id, gaming_session_id FROM rounds WHERE round_number=1')
    adapter = PostgreSQLAdapter('unused', 5432, 'unused', 'unused', '')
    adapter.pool = manager.pool
    teams = TeamManager(adapter)
    teams.get_team_pool = AsyncMock(return_value=[
        {'name': 'Owner A', 'color': 1}, {'name': 'Owner B', 'color': 2},
    ])
    monkeypatch.setattr(random, 'sample', lambda population, count: population[:count])
    replacement = {
        'Team A': {'guids': ['87654321'], 'names': ['Opponent']},
        'Team B': {'guids': ['12345678'], 'names': ['Player']},
    }

    async def write(scope):
        if writer == 'replace':
            return await teams.store_session_teams('2026-09-25', replacement, gaming_session_id=scope)
        return await teams.assign_random_team_names('2026-09-25', gaming_session_id=scope)

    original = await conn.fetch('SELECT * FROM session_teams ORDER BY id')
    async with team_write_transaction(conn):
        for scope in (None, round_row['gaming_session_id']):
            with pytest.raises(TeamWriteBusy):
                await write(scope)
        assert await conn.fetch('SELECT * FROM session_teams ORDER BY id') == original
    async with adapter.transaction():
        assert await write(round_row['gaming_session_id'])
        with pytest.raises(TeamWriteBusy):
            await assign_round_teams(conn, round_id=round_row['id'], session_date='2026-09-25')
        assert await conn.fetch('SELECT * FROM session_teams ORDER BY id') == original
    owner_rows = await conn.fetch('SELECT * FROM session_teams ORDER BY id')
    assert len(owner_rows) == await conn.fetchval('SELECT count(*) FROM session_teams') == 2
    assert [row['team_name'] for row in owner_rows] == ['Owner A', 'Owner B']
    assert await assign_round_teams(conn, round_id=round_row['id'], session_date='2026-09-25') is TeamAssignment.ALREADY_ASSIGNED
    assert await conn.fetch('SELECT * FROM session_teams ORDER BY id') == owner_rows
    if writer == 'replace':
        # Optional naming remains best effort: its savepoint rolls back while
        # the enclosing replacement commits both default-named rosters.
        await conn.execute("ALTER TABLE session_teams ADD CONSTRAINT optional_name_failure CHECK (team_name <> 'Owner B') NOT VALID")
        assert await write(round_row['gaming_session_id']) is True
        assert [row['team_name'] for row in await conn.fetch('SELECT team_name FROM session_teams ORDER BY id')] == ['Team A', 'Team B']
        assert await conn.fetchval('SELECT count(*) FROM session_teams') == 2
        await conn.execute('ALTER TABLE session_teams DROP CONSTRAINT optional_name_failure')


@pytest.mark.timeout(120)
@pytest.mark.parametrize('scope', ['date', 'id'])
async def test_manual_name_guard_coordinates_with_import(full_import_db, tmp_path, scope):
    """Manual date/ID naming and native import mutually exclude before reads."""
    from bot.core.database_adapter import PostgreSQLAdapter
    from bot.core.team_manager import TeamManager

    manager, conn = full_import_db
    first, _ = completed_pair(tmp_path, balanced=True)
    assert (await import_completed_round(manager, first))[0] is True
    round_row = await conn.fetchrow('SELECT id, gaming_session_id FROM rounds WHERE round_number=1')
    session_id = round_row['gaming_session_id'] if scope == 'id' else None
    adapter = PostgreSQLAdapter('unused', 5432, 'unused', 'unused', '')
    adapter.pool = manager.pool
    teams = TeamManager(adapter)
    original = await conn.fetch('SELECT * FROM session_teams ORDER BY id')
    async with team_write_transaction(conn):
        with pytest.raises(TeamWriteBusy):
            await teams.set_custom_team_names('2026-09-25', 'Owner A', 'Owner B', session_id)
        assert await conn.fetch('SELECT * FROM session_teams ORDER BY id') == original
    async with adapter.transaction():
        assert await teams.set_custom_team_names('2026-09-25', 'Owner A', 'Owner B', session_id)
        with pytest.raises(TeamWriteBusy):
            await assign_round_teams(conn, round_id=round_row['id'], session_date='2026-09-25')
        # The naming call has returned but its owner's transaction is uncommitted.
        assert await conn.fetch('SELECT * FROM session_teams ORDER BY id') == original
    owner_rows = await conn.fetch('SELECT * FROM session_teams ORDER BY id')
    assert len(owner_rows) == await conn.fetchval('SELECT count(*) FROM session_teams') == 2
    assert [row['team_name'] for row in owner_rows] == ['Owner A', 'Owner B']
    assert await assign_round_teams(conn, round_id=round_row['id'], session_date='2026-09-25') is TeamAssignment.ALREADY_ASSIGNED
    assert await conn.fetch('SELECT * FROM session_teams ORDER BY id') == owner_rows


@pytest.mark.timeout(120)
@pytest.mark.parametrize('owner_result', ['commit', 'rollback'])
async def test_guarded_import_assignment_blocks_competing_connection(full_import_db, tmp_path, monkeypatch, owner_result):
    manager, conn = full_import_db
    first, _ = completed_pair(tmp_path, balanced=True)
    with monkeypatch.context() as patch:
        patch.setattr(manager, '_auto_assign_teams_from_r1', AsyncMock(return_value=False))
        assert (await import_completed_round(manager, first))[0] is True
    round_id = await conn.fetchval('SELECT id FROM rounds WHERE round_number=1')
    tables = ('rounds', 'player_comprehensive_stats', 'weapon_comprehensive_stats', 'processed_files', 'runtime_events')
    before = {table: await conn.fetch(f'SELECT * FROM {table} ORDER BY 1') for table in tables}

    async def owner_operation():
        async with team_write_transaction(conn):
            assert await assign_round_teams(conn, round_id=round_id, session_date='2026-09-25') is TeamAssignment.ASSIGNED
            async with manager.pool.acquire() as contender:
                with pytest.raises(TeamWriteBusy):
                    await assign_round_teams(contender, round_id=round_id, session_date='2026-09-25')
                assert await contender.fetchval('SELECT count(*) FROM session_teams') == 0
            assert await manager._auto_assign_teams_from_r1(round_id, '2026-09-25') is False  # noqa: SLF001 -- legacy contract
            await conn.execute("UPDATE session_teams SET team_name='Owner choice' WHERE team_name='Team A'")
            if owner_result == 'rollback':
                raise RuntimeError('owner rollback')

    if owner_result == 'rollback':
        with pytest.raises(RuntimeError, match='owner rollback'):
            await owner_operation()
        assert await conn.fetchval('SELECT count(*) FROM session_teams') == 0
        assert await conn.fetch('SELECT * FROM session_teams') == []
        expected = TeamAssignment.ASSIGNED
    else:
        await owner_operation()
        expected = TeamAssignment.ALREADY_ASSIGNED
    owner_rows = await conn.fetch('SELECT * FROM session_teams ORDER BY id')
    async with manager.pool.acquire() as contender:
        assert await assign_round_teams(contender, round_id=round_id, session_date='2026-09-25') is expected
    result_rows = await conn.fetch('SELECT * FROM session_teams ORDER BY id')
    assert len(result_rows) == await conn.fetchval('SELECT count(*) FROM session_teams') == 2
    if owner_result == 'commit':
        assert result_rows == owner_rows
        assert await conn.fetchval("SELECT count(*) FROM session_teams WHERE team_name='Owner choice'") == 1
    for table in tables:
        assert await conn.fetch(f'SELECT * FROM {table} ORDER BY 1') == before[table]


@pytest.mark.timeout(120)
async def test_round_roster_extension_rolls_back_and_retries(full_import_db, tmp_path):
    """Two new players on opposite sides must not produce a half-updated round."""
    import json

    from bot.core.database_adapter import PostgreSQLAdapter
    from bot.core.team_manager import TeamManager

    manager, conn = full_import_db
    first, _ = completed_pair(tmp_path, balanced=True)
    assert (await import_completed_round(manager, first))[0] is True
    round_row = await conn.fetchrow('SELECT id, gaming_session_id FROM rounds WHERE round_number=1')
    for guid, name, side in [('aaaaaaaa', 'New A', 1), ('bbbbbbbb', 'New B', 2)]:
        await conn.execute("""
            INSERT INTO player_comprehensive_stats
            (round_id, round_date, map_name, round_number, player_guid, player_name, team)
            VALUES ($1, '2026-09-25', 'supply', 1, $2, $3, $4)
        """, round_row['id'], guid, name, side)
    original = await conn.fetch('SELECT * FROM session_teams ORDER BY id')
    assert len(original) == await conn.fetchval('SELECT count(*) FROM session_teams') == 2
    adapter = PostgreSQLAdapter('unused', 5432, 'unused', 'unused', '')
    adapter.pool = manager.pool
    teams = TeamManager(adapter)
    await conn.execute("ALTER TABLE session_teams ADD CONSTRAINT runtime_roster_failure CHECK (NOT (player_guids ? 'bbbbbbbb'))")
    assert await teams.update_teams_from_round(round_row['id'], '2026-09-25', round_row['gaming_session_id']) == {}
    assert await conn.fetch('SELECT * FROM session_teams ORDER BY id') == original
    assert await conn.fetchval('SELECT sum(jsonb_array_length(player_guids)) FROM session_teams') == 2
    await conn.execute('ALTER TABLE session_teams DROP CONSTRAINT runtime_roster_failure')
    assert await teams.update_teams_from_round(round_row['id'], '2026-09-25', round_row['gaming_session_id']) == {
        'added': {'Team B': ['New A'], 'Team A': ['New B']},
    }
    updated = await conn.fetch('SELECT * FROM session_teams ORDER BY id')
    assert sum(len(json.loads(row['player_guids'])) for row in updated) == 4
    assert await conn.fetchval('SELECT sum(jsonb_array_length(player_guids)) FROM session_teams') == 4
    assert {guid for row in updated for guid in json.loads(row['player_guids'])} == {
        '12345678', '87654321', 'aaaaaaaa', 'bbbbbbbb',
    }
    assert await teams.update_teams_from_round(round_row['id'], '2026-09-25', round_row['gaming_session_id']) == {'added': {}}
    assert await conn.fetch('SELECT * FROM session_teams ORDER BY id') == updated


@pytest.mark.timeout(120)
async def test_initial_team_creation_retries_after_second_insert_failure(full_import_db, tmp_path):
    """A failed initial pair must not make a retry think assignment is complete."""
    from bot.core.database_adapter import PostgreSQLAdapter
    from bot.core.team_manager import TeamManager

    manager, conn = full_import_db
    manager._auto_assign_teams_from_r1 = AsyncMock(return_value=False)  # noqa: SLF001 -- leave teams pending
    first, _ = completed_pair(tmp_path, balanced=True)
    assert (await import_completed_round(manager, first))[0] is True
    round_row = await conn.fetchrow('SELECT id, gaming_session_id FROM rounds WHERE round_number=1')
    adapter = PostgreSQLAdapter('unused', 5432, 'unused', 'unused', '')
    adapter.pool = manager.pool
    teams = TeamManager(adapter)
    teams.assign_random_team_names = AsyncMock(return_value=('Team A', 'Team B'))
    await conn.execute("ALTER TABLE session_teams ADD CONSTRAINT runtime_initial_failure CHECK (team_name <> 'Team B')")
    assert await teams.create_initial_teams_from_round(round_row['id'], '2026-09-25', round_row['gaming_session_id']) is False
    assert await conn.fetchval('SELECT count(*) FROM session_teams') == 0
    assert await conn.fetch('SELECT * FROM session_teams') == []
    teams.assign_random_team_names.assert_not_awaited()
    await conn.execute('ALTER TABLE session_teams DROP CONSTRAINT runtime_initial_failure')
    assert await teams.create_initial_teams_from_round(round_row['id'], '2026-09-25', round_row['gaming_session_id']) is True
    original = await conn.fetch('SELECT * FROM session_teams ORDER BY id')
    assert len(original) == await conn.fetchval('SELECT count(*) FROM session_teams') == 2
    assert [row['team_name'] for row in original] == ['Team A', 'Team B']
    assert await teams.create_initial_teams_from_round(round_row['id'], '2026-09-25', round_row['gaming_session_id']) is True
    assert await conn.fetch('SELECT * FROM session_teams ORDER BY id') == original
    teams.assign_random_team_names.assert_awaited_once()


@pytest.mark.timeout(120)
@pytest.mark.parametrize('failure', ['outer_rollback', 'second_insert', 'deferred_commit'])
async def test_team_effect_rolls_back_and_retries_on_borrowed_connection(full_import_db, tmp_path, failure):
    manager, conn = full_import_db
    first, _ = completed_pair(tmp_path, balanced=True)
    # Leave the post-import effect pending while canonical stats really commit.
    manager._auto_assign_teams_from_r1 = AsyncMock(return_value=False)  # noqa: SLF001 -- leave effect pending
    assert (await import_completed_round(manager, first))[0] is True
    round_id = await conn.fetchval('SELECT id FROM rounds WHERE round_number=1')
    tables = ('rounds', 'player_comprehensive_stats', 'weapon_comprehensive_stats',
              'processed_files', 'runtime_events')
    before = {table: await conn.fetch(f'SELECT * FROM {table} ORDER BY 1') for table in tables}
    if failure in ('second_insert', 'deferred_commit'):
        if failure == 'second_insert':
            constraint = "CHECK (team_name <> 'Team B')"
            expected_error = asyncpg.CheckViolationError
        else:
            # Both inserts succeed; only the helper's transaction exit fails.
            constraint = 'UNIQUE (session_start_date) DEFERRABLE INITIALLY DEFERRED'
            expected_error = asyncpg.UniqueViolationError
        await conn.execute(f'ALTER TABLE session_teams ADD CONSTRAINT runtime_test_failure {constraint}')
        with pytest.raises(expected_error):
            await assign_round_teams(conn, round_id=round_id, session_date='2026-09-25')
        await conn.execute('ALTER TABLE session_teams DROP CONSTRAINT runtime_test_failure')
    else:
        with pytest.raises(RuntimeError, match='caller rolls back'):
            async with conn.transaction():
                assert await assign_round_teams(
                    conn, round_id=round_id, session_date='2026-09-25',
                ) is TeamAssignment.ASSIGNED
                assert await conn.fetchval('SELECT count(*) FROM session_teams') == 2
                raise RuntimeError('caller rolls back')
    assert await conn.fetchval('SELECT count(*) FROM session_teams') == 0
    assert await conn.fetch('SELECT * FROM session_teams') == []
    assert await assign_round_teams(conn, round_id=round_id, session_date='2026-09-25') is TeamAssignment.ASSIGNED
    rows = await conn.fetch('SELECT * FROM session_teams ORDER BY id')
    assert len(rows) == await conn.fetchval('SELECT count(*) FROM session_teams') == 2
    # Existing owner choices are preserved by the unchanged early-return policy.
    await conn.execute("UPDATE session_teams SET team_name='Owner choice' WHERE team_name='Team A'")
    owner_rows = await conn.fetch('SELECT * FROM session_teams ORDER BY id')
    assert await assign_round_teams(
        conn, round_id=round_id, session_date='2026-09-25',
    ) is TeamAssignment.ALREADY_ASSIGNED
    assert await conn.fetch('SELECT * FROM session_teams ORDER BY id') == owner_rows
    for table in tables:
        assert await conn.fetch(f'SELECT * FROM {table} ORDER BY 1') == before[table]
    assert not conn.is_closed() and await conn.fetchval('SELECT 1') == 1


@pytest.mark.timeout(120)
@pytest.mark.parametrize('writer', ['manual', 'replace', 'random'])
async def test_team_writers_are_atomic_on_second_write_failure(full_import_db, tmp_path, monkeypatch, writer):
    """A rejected second write must preserve both original rows, including IDs."""
    import random

    from bot.core.database_adapter import PostgreSQLAdapter
    from bot.core.team_manager import TeamManager

    manager, conn = full_import_db
    first, _ = completed_pair(tmp_path, balanced=True)
    assert (await import_completed_round(manager, first))[0] is True
    session_id = await conn.fetchval('SELECT gaming_session_id FROM rounds WHERE round_number=1')
    assert session_id is not None
    original = await conn.fetch('SELECT * FROM session_teams ORDER BY id')
    assert len(original) == await conn.fetchval('SELECT count(*) FROM session_teams') == 2
    # Borrow the fixture's isolated pool; never initialize an application pool.
    adapter = PostgreSQLAdapter('unused', 5432, 'unused', 'unused', '')
    adapter.pool = manager.pool
    teams = TeamManager(adapter)
    if writer == 'random':
        teams.get_team_pool = AsyncMock(return_value=[
            {'name': 'Owner A', 'color': 1}, {'name': 'Owner B', 'color': 2},
        ])
        monkeypatch.setattr(random, 'sample', lambda population, count: population[:count])

    async def write_pair():
        if writer == 'manual':
            return await teams.set_custom_team_names('2026-09-25', 'Owner A', 'Owner B', gaming_session_id=session_id)
        if writer == 'random':
            return await teams.assign_random_team_names('2026-09-25', gaming_session_id=session_id)
        return await teams.store_session_teams('2026-09-25', {
            'Owner A': {'guids': ['87654321'], 'names': ['Opponent']},
            'Owner B': {'guids': ['12345678'], 'names': ['Player']},
        }, auto_assign_names=False, gaming_session_id=session_id)

    await conn.execute("ALTER TABLE session_teams ADD CONSTRAINT runtime_name_failure CHECK (team_name <> 'Owner B')")
    with pytest.raises(asyncpg.CheckViolationError):
        await write_pair()
    assert await conn.fetch('SELECT * FROM session_teams ORDER BY id') == original
    assert await conn.fetchval("SELECT count(*) FROM session_teams WHERE team_name LIKE 'Owner %'") == 0
    await conn.execute('ALTER TABLE session_teams DROP CONSTRAINT runtime_name_failure')
    assert await write_pair()
    assert await conn.fetchval("SELECT count(*) FROM session_teams WHERE team_name LIKE 'Owner %'") == 2
    assert [row['team_name'] for row in await conn.fetch('SELECT team_name FROM session_teams ORDER BY id')] == [
        'Owner A', 'Owner B',
    ]


@pytest.mark.timeout(120)
async def test_invalid_roster_repair_preserves_data_until_commit(full_import_db, tmp_path, monkeypatch):
    """Read-only/failed repair preserves all rows; successful repair keeps map rows."""
    from bot.core.database_adapter import PostgreSQLAdapter
    from bot.core.team_manager import TeamManager

    manager, conn = full_import_db
    first, _ = completed_pair(tmp_path, balanced=True)
    assert (await import_completed_round(manager, first))[0] is True
    session_id = await conn.fetchval('SELECT gaming_session_id FROM rounds WHERE round_number=1')
    await conn.execute("UPDATE session_teams SET player_guids='[\"same\"]'::jsonb")
    await conn.execute("""
        INSERT INTO session_teams (session_start_date, map_name, team_name, player_guids, player_names, gaming_session_id)
        VALUES ('2026-09-25', 'supply', 'Map owner', '[]', '[]', $1)
    """, session_id)
    original = await conn.fetch('SELECT * FROM session_teams ORDER BY id')
    assert len(original) == await conn.fetchval('SELECT count(*) FROM session_teams') == 3
    adapter = PostgreSQLAdapter('unused', 5432, 'unused', 'unused', '')
    adapter.pool = manager.pool
    teams = TeamManager(adapter)
    assert await teams.get_session_teams('2026-09-25', auto_detect=False, gaming_session_id=session_id) == {}
    assert await conn.fetch('SELECT * FROM session_teams ORDER BY id') == original
    for failure in ('empty', 'error'):
        with monkeypatch.context() as patch:
            detector = AsyncMock(return_value={})
            if failure == 'error':
                detector.side_effect = RuntimeError('detection unavailable')
            patch.setattr(teams, 'detect_session_teams', detector)
            if failure == 'error':
                with pytest.raises(RuntimeError, match='detection unavailable'):
                    await teams.get_session_teams('2026-09-25', gaming_session_id=session_id)
            else:
                assert await teams.get_session_teams('2026-09-25', gaming_session_id=session_id) == {}
        assert await conn.fetch('SELECT * FROM session_teams ORDER BY id') == original
    # NOT VALID retains the original row but rejects its attempted replacement.
    await conn.execute("ALTER TABLE session_teams ADD CONSTRAINT runtime_repair_failure CHECK (team_name <> 'Team B') NOT VALID")
    with pytest.raises(asyncpg.CheckViolationError):
        await teams.get_session_teams('2026-09-25', gaming_session_id=session_id)
    assert await conn.fetch('SELECT * FROM session_teams ORDER BY id') == original
    await conn.execute('ALTER TABLE session_teams DROP CONSTRAINT runtime_repair_failure')
    repaired = await teams.get_session_teams('2026-09-25', gaming_session_id=session_id)
    assert set(repaired) == {'Team A', 'Team B'}
    assert set(repaired['Team A']['guids']) != set(repaired['Team B']['guids'])
    assert await conn.fetch("SELECT * FROM session_teams WHERE map_name='supply'") == [original[2]]
    rows = await conn.fetch('SELECT * FROM session_teams ORDER BY id')
    assert len(rows) == await conn.fetchval('SELECT count(*) FROM session_teams') == 3
