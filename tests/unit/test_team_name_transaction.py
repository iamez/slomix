"""Owner name changes use one transaction and propagate failure/cancellation."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.core.team_manager import TeamManager
from shared.team_write_guard import TeamWriteBusy


@pytest.mark.parametrize('session_id', [42, None])
@pytest.mark.parametrize('writer', ['manual', 'replace', 'random'])
async def test_busy_team_writers_do_not_read_or_write(session_id, writer):
    @asynccontextmanager
    async def transaction():
        yield native

    native = SimpleNamespace(transaction=transaction, fetchval=AsyncMock(side_effect=['read committed', False]))
    db = SimpleNamespace(transaction=transaction, execute=AsyncMock())
    manager = TeamManager(db)
    manager._get_session_teams_columns = AsyncMock()  # noqa: SLF001 -- guard must precede schema reads
    manager._ensure_session_teams_table = AsyncMock()  # noqa: SLF001
    manager._store_session_teams = AsyncMock(return_value=True)  # noqa: SLF001 -- guarded body must not execute
    manager._assign_random_team_names = AsyncMock(return_value=('A', 'B'))  # noqa: SLF001
    with pytest.raises(TeamWriteBusy):
        if writer == 'manual':
            await manager.set_custom_team_names('2026-09-25', 'Owner A', 'Owner B', session_id)
        elif writer == 'replace':
            await manager.store_session_teams('2026-09-25', {}, gaming_session_id=session_id)
        else:
            await manager.assign_random_team_names('2026-09-25', gaming_session_id=session_id)
    manager._get_session_teams_columns.assert_not_awaited()  # noqa: SLF001
    manager._ensure_session_teams_table.assert_not_awaited()  # noqa: SLF001
    manager._store_session_teams.assert_not_awaited()  # noqa: SLF001
    manager._assign_random_team_names.assert_not_awaited()  # noqa: SLF001
    db.execute.assert_not_awaited()


@pytest.mark.parametrize('failure', ['none', 'second', 'commit', 'cancel'])
@pytest.mark.parametrize('session_id', [42, None])
@pytest.mark.parametrize('writer', ['manual', 'replace', 'random'])
async def test_team_writers_share_transaction_and_propagate_errors(failure, session_id, writer, monkeypatch):
    import random

    state = {'active': False, 'exited': False, 'calls': []}
    write_count = 3 if writer == 'replace' else 2

    @asynccontextmanager
    async def transaction():
        was_active = state['active']
        state['active'] = True
        try:
            yield native
            if failure == 'commit':
                raise RuntimeError('commit rejected')
        finally:
            state['active'] = was_active
            state['exited'] = True

    async def fetchval(query, *args):
        assert state['active']
        return 'read committed' if query == 'SHOW transaction_isolation' else True

    native = SimpleNamespace(transaction=transaction, fetchval=fetchval)

    async def execute(query, params):
        assert state['active'], 'owner name write outside transaction'
        state['calls'].append((query, params))
        if len(state['calls']) == write_count:
            if failure == 'second':
                raise RuntimeError('second write rejected')
            if failure == 'cancel':
                raise asyncio.CancelledError

    manager = TeamManager(SimpleNamespace(transaction=transaction, execute=execute, fetch_val=AsyncMock(return_value=False)))
    manager._get_session_teams_columns = AsyncMock(return_value={'gaming_session_id'})  # noqa: SLF001 -- isolate schema probe
    manager._ensure_session_teams_table = AsyncMock()  # noqa: SLF001 -- schema exists in this protocol test
    manager.get_session_teams = AsyncMock(return_value={'Team A': {}, 'Team B': {}})
    manager.get_team_pool = AsyncMock(return_value=[
        {'name': 'Owner A', 'color': 1}, {'name': 'Owner B', 'color': 2},
    ])
    monkeypatch.setattr(random, 'sample', lambda population, count: population[:count])

    async def write_pair():
        if writer == 'manual':
            return await manager.set_custom_team_names('2026-09-25', 'Owner A', 'Owner B', session_id)
        if writer == 'random':
            return await manager.assign_random_team_names('2026-09-25', gaming_session_id=session_id)
        return await manager.store_session_teams('2026-09-25', {
            'Owner A': {'guids': ['a'], 'names': ['A']},
            'Owner B': {'guids': ['b'], 'names': ['B']},
        }, auto_assign_names=False, gaming_session_id=session_id)

    if failure == 'none':
        assert await write_pair()
    else:
        error = asyncio.CancelledError if failure == 'cancel' else RuntimeError
        with pytest.raises(error):
            await write_pair()
    assert state['exited'] and not state['active']
    expected_scope = session_id if session_id is not None else '2026-09-25%'
    assert len(state['calls']) == write_count
    if writer == 'replace':
        assert state['calls'][0][0].startswith('DELETE FROM session_teams')
        assert state['calls'][0][1] == (expected_scope,)
        assert [params[1] for _, params in state['calls'][1:]] == ['Owner A', 'Owner B']
        assert all(params[-1] == session_id for _, params in state['calls'][1:])
    else:
        assert [params for _, params in state['calls']] == [('Owner A', expected_scope), ('Owner B', expected_scope)]
