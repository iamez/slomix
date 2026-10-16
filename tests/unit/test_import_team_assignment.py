"""Connection ownership, explicit outcomes and legacy compatibility."""

import asyncio
import json
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from postgresql_database_manager import PostgreSQLDatabaseManager
from shared.import_team_assignment import TeamAssignment, assign_round_teams
from shared.team_identity import TeamIdentityConflict
from shared.team_write_guard import TeamWriteBusy


class Connection:
    def __init__(self, *, has_session=True, has_identity=True, session_id=7):
        self.round = dict(defender_team=2, winner_team=1, round_number=1, gaming_session_id=session_id)
        self.columns = (has_session, has_identity)
        self.existing = 0
        self.unresolved_manual_scope = False
        self.players = [dict(player_guid='a', player_name='A', team=1),
                        dict(player_guid='b', player_name='B', team=2),
                        dict(player_guid='s', player_name='Spectator', team=0)]
        self.writes = []
        self.queries = []
        self.failure = None
        self.commit_failure = None
        self.transactions = 0
        self.lock_acquired = True

    async def fetchrow(self, query, *args):
        self.queries.append((query, args))
        return self.round

    async def fetchval(self, query, *args):
        self.queries.append((query, args))
        if query == 'SHOW transaction_isolation':
            return 'read committed'
        if 'pg_try_advisory_xact_lock' in query:
            return self.lock_acquired
        if 'information_schema' in query:
            return self.columns[0 if "'gaming_session_id'" in query else 1]
        if 'gaming_session_id IS NULL' in query:
            return self.unresolved_manual_scope
        return self.existing

    async def fetch(self, query, *args):
        self.queries.append((query, args))
        return self.players

    async def execute(self, query, *args):
        self.writes.append((query, args))
        if self.failure and len(self.writes) == 2:
            raise self.failure

    @asynccontextmanager
    async def transaction(self):
        self.transactions += 1
        before = self.writes.copy()
        try:
            yield
            if self.commit_failure:
                raise self.commit_failure
        except BaseException:
            self.writes = before
            raise


@pytest.mark.parametrize('has_session', [False, True])
@pytest.mark.parametrize('has_identity', [False, True])
@pytest.mark.parametrize('session_id', [None, 7])
async def test_preserved_schema_branches(has_session, has_identity, session_id):
    conn = Connection(has_session=has_session, has_identity=has_identity, session_id=session_id)
    assert await assign_round_teams(conn, round_id=3, session_date='2026-09-26') is TeamAssignment.ASSIGNED
    assert conn.transactions == 2 and len(conn.writes) == 2
    first, second = conn.writes
    assert json.loads(first[1][1]) == ['b']  # R1 defenders remain Team A.
    assert json.loads(second[1][1]) == ['a']
    for query, args in conn.writes:
        assert ('ON CONFLICT ON CONSTRAINT' in query) == has_identity
        assert len(args) == (5 if has_session else 4)
        assert args[3].tzinfo is None  # Preserve naive local timestamp storage.
    lookup = next(query for query, _ in conn.queries if 'COUNT(*)' in query)
    assert ('WHERE gaming_session_id' in lookup) == (has_session and session_id is not None)


@pytest.mark.parametrize('reason', [
    TeamAssignment.ROUND_MISSING, TeamAssignment.NOT_ROUND_ONE,
    TeamAssignment.DEFENDER_UNAVAILABLE, TeamAssignment.ALREADY_ASSIGNED,
    TeamAssignment.NO_PLAYERS, TeamAssignment.UNBALANCED,
])
async def test_explicit_noop_reasons_do_not_write(reason):
    conn = Connection()
    if reason is TeamAssignment.ROUND_MISSING:
        conn.round = None
    elif reason is TeamAssignment.NOT_ROUND_ONE:
        conn.round['round_number'] = 2
    elif reason is TeamAssignment.DEFENDER_UNAVAILABLE:
        conn.round['defender_team'] = 0
    elif reason is TeamAssignment.ALREADY_ASSIGNED:
        conn.existing = 1
    elif reason is TeamAssignment.NO_PLAYERS:
        conn.players = []
    else:
        conn.players = conn.players[:1]
    assert await assign_round_teams(conn, round_id=3, session_date='2026-09-26') is reason
    assert conn.writes == [] and conn.transactions == 1


@pytest.mark.parametrize('existing', [0, 2])
async def test_unresolved_manual_scope_is_not_assignment_or_successful_noop(existing):
    conn = Connection()
    conn.existing = existing
    conn.unresolved_manual_scope = True
    with pytest.raises(TeamIdentityConflict, match='explicit session resolution'):
        await assign_round_teams(conn, round_id=3, session_date='2026-09-26')
    assert conn.writes == []
    assert not any('player_comprehensive_stats' in query for query, _ in conn.queries)


@pytest.mark.parametrize('failure', [RuntimeError('SQL failed'), asyncio.CancelledError()])
async def test_second_write_failure_propagates_and_rolls_back(failure):
    conn = Connection()
    conn.failure = failure
    with pytest.raises(type(failure)) as exc:
        await assign_round_teams(conn, round_id=3, session_date='2026-09-26')
    assert exc.value is failure
    assert conn.transactions == 2 and conn.writes == []


async def test_read_failure_is_not_a_noop():
    conn = Connection()
    conn.fetchrow = AsyncMock(side_effect=OSError('unavailable'))
    with pytest.raises(OSError, match='unavailable'):
        await assign_round_teams(conn, round_id=3, session_date='2026-09-26')


@pytest.mark.parametrize('failure', [RuntimeError('commit failed'), asyncio.CancelledError()])
async def test_transaction_exit_failure_is_not_reported_as_assigned(failure):
    conn = Connection()
    conn.commit_failure = failure
    with pytest.raises(type(failure)) as exc:
        await assign_round_teams(conn, round_id=3, session_date='2026-09-26')
    assert exc.value is failure
    assert conn.transactions == 2 and conn.writes == []


async def test_busy_assignment_does_not_read_or_write_team_state():
    conn = Connection()
    conn.lock_acquired = False
    conn.fetchrow = AsyncMock()
    with pytest.raises(TeamWriteBusy):
        await assign_round_teams(conn, round_id=3, session_date='2026-09-26')
    conn.fetchrow.assert_not_awaited()
    assert conn.writes == [] and conn.transactions == 1


@pytest.mark.parametrize('mode', ['assigned', 'existing', 'manual_identity', 'failure', 'cancel', 'commit_failure', 'commit_cancel'])
async def test_legacy_wrapper_keeps_bool_contract_and_borrowed_pool(mode):
    conn = Connection()
    released = []
    if mode == 'existing':
        conn.existing = 1
    elif mode == 'manual_identity':
        conn.unresolved_manual_scope = True
    elif mode in ('failure', 'cancel'):
        conn.failure = RuntimeError('SQL failed') if mode == 'failure' else asyncio.CancelledError()
    elif mode in ('commit_failure', 'commit_cancel'):
        conn.commit_failure = RuntimeError('commit failed') if mode == 'commit_failure' else asyncio.CancelledError()
    @asynccontextmanager
    async def acquire():
        try:
            yield conn
        finally:
            released.append(True)
    pool = SimpleNamespace(acquire=acquire)
    manager = PostgreSQLDatabaseManager(config=SimpleNamespace(database_type='postgresql'))
    manager.pool = pool
    if mode in ('cancel', 'commit_cancel'):
        with pytest.raises(asyncio.CancelledError):
            await manager._auto_assign_teams_from_r1(3, '2026-09-26')  # noqa: SLF001 -- compatibility seam
    else:
        assert await manager._auto_assign_teams_from_r1(3, '2026-09-26') is (mode == 'assigned')  # noqa: SLF001
    assert released == [True] and manager.pool is pool


def test_fresh_process_effect_without_presentation_setup(tmp_path):
    script = '''
import asyncio, importlib.abc, json, sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'discord', 'dotenv', 'website'} or fullname in {
            'bot.config', 'bot.logging_config', 'shared.importer_startup',
        }:
            raise AssertionError('Forbidden startup dependency')
sys.meta_path.insert(0, Block())
from tests.unit.test_import_team_assignment import Connection
from shared.import_team_assignment import assign_round_teams
conn = Connection()
result = asyncio.run(assign_round_teams(conn, round_id=3, session_date='2026-09-26'))
print(json.dumps({'status': result.value, 'writes': len(conn.writes)}))
'''
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, '-c', script], cwd=tmp_path,
        env={**os.environ, 'PYTHONPATH': str(root)}, capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'status': 'assigned', 'writes': 2}
    assert result.stderr == '' and list(tmp_path.iterdir()) == []
