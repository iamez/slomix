"""All roster extensions from a round share a transaction."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.core.team_manager import TeamManager


@pytest.mark.parametrize('failure', ['none', 'second', 'commit', 'cancel'])
async def test_round_roster_extensions_are_atomic(failure):
    state = {'active': False, 'exited': False, 'writes': []}

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
        assert state['active'], 'roster write outside transaction'
        state['writes'].append(params)
        if len(state['writes']) == 2:
            if failure == 'second':
                raise RuntimeError('second roster rejected')
            if failure == 'cancel':
                raise asyncio.CancelledError

    manager = TeamManager(SimpleNamespace(
        transaction=transaction, execute=execute,
        fetch_val=AsyncMock(return_value=False),
        fetch_all=AsyncMock(return_value=[('a', 'A', 1), ('b', 'B', 2), ('c', 'C', 1), ('d', 'D', 2)]),
    ))
    manager._ensure_session_teams_table = AsyncMock()  # noqa: SLF001 -- isolate schema
    manager._get_session_teams_columns = AsyncMock(return_value={'gaming_session_id'})  # noqa: SLF001
    manager.get_session_teams = AsyncMock(return_value={
        'Owner A': {'guids': ['a'], 'names': ['A']},
        'Owner B': {'guids': ['b'], 'names': ['B']},
    })
    if failure == 'cancel':
        with pytest.raises(asyncio.CancelledError):
            await manager.update_teams_from_round(1, '2026-09-25', 42)
    else:
        result = await manager.update_teams_from_round(1, '2026-09-25', 42)
        assert result == ({'added': {'Owner A': ['C'], 'Owner B': ['D']}} if failure == 'none' else {})
    assert state['exited'] and not state['active']
    assert len(state['writes']) == 2
    assert [params[-2:] for params in state['writes']] == [(42, 'Owner A'), (42, 'Owner B')]
