"""Initial team pairs commit together before optional naming begins."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.core.team_manager import TeamManager


@pytest.mark.parametrize('failure', ['none', 'second', 'commit', 'cancel'])
@pytest.mark.parametrize('columns', [set(), {'gaming_session_id', 'session_identity'}])
async def test_initial_pair_transaction(failure, columns):
    state = {'active': False, 'exited': False, 'writes': 0}

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
        assert state['active'], 'initial team write outside transaction'
        state['writes'] += 1
        if state['writes'] == 2:
            if failure == 'second':
                raise RuntimeError('second write rejected')
            if failure == 'cancel':
                raise asyncio.CancelledError

    async def naming(*args, **kwargs):
        assert state['exited'] and state['active']  # Pair savepoint ended; outer guard still owns the operation.
        return 'Team A', 'Team B'

    manager = TeamManager(SimpleNamespace(
        transaction=transaction, execute=execute,
        fetch_val=AsyncMock(return_value=False),
        fetch_one=AsyncMock(return_value=(0,)),
        fetch_all=AsyncMock(return_value=[('a', 'A', 1), ('b', 'B', 2)]),
    ))
    manager._ensure_session_teams_table = AsyncMock()  # noqa: SLF001 -- isolate schema
    manager._get_session_teams_columns = AsyncMock(return_value=columns)  # noqa: SLF001
    manager.assign_random_team_names = AsyncMock(side_effect=naming)
    if failure == 'cancel':
        with pytest.raises(asyncio.CancelledError):
            await manager.create_initial_teams_from_round(1, '2026-09-25', 42)
    else:
        assert await manager.create_initial_teams_from_round(1, '2026-09-25', 42) is (failure == 'none')
    assert state['exited'] and not state['active']
    assert state['writes'] == 2
    if failure == 'none':
        manager.assign_random_team_names.assert_awaited_once()
    else:
        manager.assign_random_team_names.assert_not_awaited()
