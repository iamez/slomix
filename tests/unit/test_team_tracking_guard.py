"""Import orchestration must guard reads as well as team publication."""
# ruff: noqa: SLF001 -- the mixin's internal import hook is the tested boundary.

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.services.stats_import_mixin import _StatsImportMixin


@pytest.mark.parametrize('case', ['r1', 'r2', 'existing', 'busy', 'body', 'commit', 'cancel'])
async def test_tracking_guard_covers_reads_and_cleans_up(case):
    state = {'depth': 0, 'committed': False}

    @asynccontextmanager
    async def transaction():
        state['depth'] += 1
        try:
            yield native
            if state['depth'] == 1:
                if case == 'commit':
                    raise RuntimeError('commit rejected')
                state['committed'] = True
        finally:
            state['depth'] -= 1

    async def fetchval(query, *args):
        assert state['depth'] >= 2
        return 'read committed' if query == 'SHOW transaction_isolation' else case != 'busy'

    native = SimpleNamespace(transaction=transaction, fetchval=fetchval)
    host = _StatsImportMixin()

    async def read(*args, **kwargs):
        assert state['depth'] >= 2
        if case == 'body':
            raise RuntimeError('read rejected')
        if case == 'cancel':
            raise asyncio.CancelledError
        return {'Team A': {}, 'Team B': {}} if case == 'existing' else {}

    async def detect(*args, **kwargs):
        assert state['depth'] >= 2
        return {'Team A': {'guids': ['one']}, 'Team B': {'guids': ['two']}}

    async def write(*args, **kwargs):
        assert state['depth'] >= 2
        return {'added': {}}

    host.team_manager = SimpleNamespace(
        db=SimpleNamespace(transaction=transaction),
        get_session_teams=AsyncMock(side_effect=read),
        detect_session_teams=AsyncMock(side_effect=detect),
        create_initial_teams_from_round=AsyncMock(side_effect=write),
        store_session_teams=AsyncMock(side_effect=write),
        update_teams_from_round=AsyncMock(side_effect=write),
        assign_random_team_names=AsyncMock(side_effect=write),
    )
    if case == 'cancel':
        with pytest.raises(asyncio.CancelledError):
            await host._handle_team_tracking(1, 2, '2026-09-25', 42)
    else:
        await host._handle_team_tracking(1, 1 if case == 'r1' else 2, '2026-09-25', 42)
    assert state['depth'] == 0
    assert state['committed'] is (case in ('r1', 'r2', 'existing'))
    teams = host.team_manager
    assert teams.get_session_teams.await_count == (0 if case == 'busy' else 1)
    if case == 'r1':
        teams.create_initial_teams_from_round.assert_awaited_once()
        teams.detect_session_teams.assert_not_awaited()
    elif case == 'r2':
        teams.detect_session_teams.assert_awaited_once()
        teams.store_session_teams.assert_awaited_once()
    elif case == 'existing':
        teams.update_teams_from_round.assert_awaited_once()
        teams.assign_random_team_names.assert_awaited_once()


async def test_missing_team_manager_needs_no_database():
    await _StatsImportMixin()._handle_team_tracking(1, 2, '2026-09-25', 42)
