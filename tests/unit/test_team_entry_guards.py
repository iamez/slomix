"""Whole-operation guard failures are handled only after transaction cleanup."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.core.team_manager import TeamManager
from shared.team_write_guard import TeamWriteBusy


@pytest.mark.parametrize('operation', ['create', 'update', 'repair'])
@pytest.mark.parametrize('failure', ['none', 'busy', 'body', 'commit', 'cancel'])
async def test_guarded_entry_cleanup_and_legacy_results(operation, failure):
    state = {'depth': 0}

    @asynccontextmanager
    async def transaction():
        state['depth'] += 1
        try:
            yield native
            if state['depth'] == 1:
                if failure == 'commit':
                    raise RuntimeError('outer commit rejected')
                if failure == 'cancel':
                    raise asyncio.CancelledError
        finally:
            state['depth'] -= 1

    async def fetchval(query, *args):
        assert state['depth'] >= 2
        return 'read committed' if query == 'SHOW transaction_isolation' else failure != 'busy'

    native = SimpleNamespace(transaction=transaction, fetchval=fetchval)
    manager = TeamManager(SimpleNamespace(transaction=transaction))
    method, private, args, success, rejected = {
        'create': ('create_initial_teams_from_round', '_create_initial_teams_from_round', (1, '2026-09-25', 42), True, False),
        'update': ('update_teams_from_round', '_update_teams_from_round', (1, '2026-09-25', 42), {'added': {}}, {}),
        'repair': ('get_session_teams', '_get_session_teams', ('2026-09-25', True, 42), {'Team A': {}}, None),
    }[operation]

    async def protected_body(*args):
        assert state['depth'] >= 2
        if failure == 'body':
            raise RuntimeError('body rejected')
        return success

    body = AsyncMock(side_effect=protected_body)
    setattr(manager, private, body)
    if failure == 'cancel':
        with pytest.raises(asyncio.CancelledError):
            await getattr(manager, method)(*args)
    elif operation == 'repair' and failure != 'none':
        with pytest.raises(TeamWriteBusy if failure == 'busy' else RuntimeError):
            await getattr(manager, method)(*args)
    else:
        assert await getattr(manager, method)(*args) == (success if failure == 'none' else rejected)
    assert state['depth'] == 0
    assert body.await_count == (0 if failure == 'busy' else 1)
