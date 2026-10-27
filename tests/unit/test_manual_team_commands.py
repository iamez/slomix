"""Manual team creation guards reads, pair writes and response timing."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.cogs.team_management_cog import TeamManagementCog


@pytest.mark.parametrize('modern', [False, True])
@pytest.mark.parametrize('failure', ['none', 'busy', 'second', 'commit', 'cancel', 'empty', 'schema'])
async def test_set_teams_transaction_boundary(modern, failure):
    state = {'depth': 0, 'inserts': 0, 'entered': 0}

    @asynccontextmanager
    async def transaction():
        state['depth'] += 1
        try:
            yield native
            if state['depth'] == 1 and failure == 'commit':
                raise RuntimeError('commit rejected')
        finally:
            state['depth'] -= 1

    async def fetchval(query, *args):
        assert state['depth'] >= 2
        return 'read committed' if query == 'SHOW transaction_isolation' else failure != 'busy'

    native = SimpleNamespace(transaction=transaction, fetchval=fetchval)

    async def fetch_one(query, *args):
        assert state['depth'] >= 2
        if 'information_schema' in query:
            if failure == 'schema':
                raise RuntimeError('schema unavailable')
            return (modern,)
        return None if failure == 'empty' else ('2026-09-25',)

    async def execute(query, *args):
        state['entered'] += 1
        assert state['depth'] >= 2
        if 'INSERT INTO' in query:
            target = 'session_identity' if modern else 'session_start_date'
            assert f'ON CONFLICT ({target}, map_name, team_name)' in query
            state['inserts'] += 1
            if state['inserts'] == 2:
                if failure == 'second':
                    raise RuntimeError('second insert rejected')
                if failure == 'cancel':
                    raise asyncio.CancelledError

    async def send(*args, **kwargs):
        assert state['depth'] == 0, 'Discord I/O must follow transaction cleanup'

    adapter = SimpleNamespace(transaction=transaction, fetch_one=fetch_one, execute=execute)
    cog = TeamManagementCog(SimpleNamespace(db_adapter=adapter))
    ctx = SimpleNamespace(send=AsyncMock(side_effect=send))
    if failure == 'cancel':
        with pytest.raises(asyncio.CancelledError):
            await TeamManagementCog.set_teams.callback(cog, ctx, 'Owner A', 'Owner B')
        ctx.send.assert_not_awaited()
    else:
        await TeamManagementCog.set_teams.callback(cog, ctx, 'Owner A', 'Owner B')
        ctx.send.assert_awaited_once()
        assert ('embed' in ctx.send.call_args.kwargs) is (failure == 'none')
    assert state['depth'] == 0
    if failure == 'busy':
        assert state['entered'] == 0


@pytest.mark.parametrize('failure', ['none', 'busy', 'update', 'commit', 'cancel', 'empty', 'alias', 'ambiguous', 'replay'])
async def test_assign_player_transaction_boundary(failure):
    state = {'depth': 0, 'entered': 0, 'updates': 0}

    @asynccontextmanager
    async def transaction():
        state['depth'] += 1
        try:
            yield native
            if state['depth'] == 1 and failure == 'commit':
                raise RuntimeError('commit rejected')
        finally:
            state['depth'] -= 1

    async def fetchval(query, *args):
        return 'read committed' if query == 'SHOW transaction_isolation' else failure != 'busy'

    native = SimpleNamespace(transaction=transaction, fetchval=fetchval)

    async def fetch_one(query, *args):
        assert state['depth'] >= 2
        if 'information_schema' in query:
            return (True,)
        if 'player_aliases' in query:
            return None if failure == 'alias' else ('guid1234', 'Player')
        return None if failure == 'empty' else ('2026-09-25',)

    async def fetch_all(*args):
        assert state['depth'] >= 2
        if failure == 'replay':
            return [('["guid1234"]', '["Player"]')]
        return [('[]', '[]')] * (2 if failure == 'ambiguous' else 1)

    async def execute(query, *args):
        state['entered'] += 1
        assert state['depth'] >= 2
        if 'UPDATE session_teams' in query:
            state['updates'] += 1
            if failure == 'update':
                raise RuntimeError('update rejected')
            if failure == 'cancel':
                raise asyncio.CancelledError

    async def send(*args, **kwargs):
        assert state['depth'] == 0

    adapter = SimpleNamespace(transaction=transaction, fetch_one=fetch_one, fetch_all=fetch_all, execute=execute)
    cog = TeamManagementCog(SimpleNamespace(db_adapter=adapter))
    ctx = SimpleNamespace(send=AsyncMock(side_effect=send))
    if failure == 'cancel':
        with pytest.raises(asyncio.CancelledError):
            await TeamManagementCog.assign_player.callback(cog, ctx, 'Player', 'Owner A')
        ctx.send.assert_not_awaited()
    else:
        await TeamManagementCog.assign_player.callback(cog, ctx, 'Player', 'Owner A')
        ctx.send.assert_awaited_once()
        assert ('embed' in ctx.send.call_args.kwargs) is (failure == 'none')
    assert state['depth'] == 0
    if failure == 'busy':
        assert state['entered'] == 0
    if failure in ('empty', 'alias', 'ambiguous', 'replay'):
        assert state['updates'] == 0
