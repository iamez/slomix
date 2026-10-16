"""Invalid stored rosters are not permission to delete before replacement."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.core.team_manager import TeamManager


@pytest.mark.parametrize('mode', ['disabled', 'empty', 'error', 'replacement'])
async def test_invalid_roster_read_preserves_rows_until_replacement(mode):
    @asynccontextmanager
    async def transaction():
        yield native

    native = SimpleNamespace(transaction=transaction, fetchval=AsyncMock(side_effect=['read committed', True]))
    db = SimpleNamespace(
        transaction=transaction,
        fetch_val=AsyncMock(return_value=False),
        execute=AsyncMock(),
        fetch_all=AsyncMock(return_value=[
            ('Team A', '["same"]', '["Player"]'),
            ('Team B', '["same"]', '["Player"]'),
        ]),
    )
    manager = TeamManager(db)
    manager._ensure_session_teams_table = AsyncMock()  # noqa: SLF001 -- isolate existing schema
    manager._get_session_teams_columns = AsyncMock(return_value={'gaming_session_id'})  # noqa: SLF001
    replacement = {'Team A': {'guids': ['a']}, 'Team B': {'guids': ['b']}}
    manager.detect_session_teams = AsyncMock(return_value=replacement if mode == 'replacement' else {})
    manager.store_session_teams = AsyncMock()
    if mode == 'error':
        manager.detect_session_teams.side_effect = RuntimeError('detection unavailable')
        with pytest.raises(RuntimeError, match='detection unavailable'):
            await manager.get_session_teams('2026-09-25', gaming_session_id=42)
    else:
        result = await manager.get_session_teams(
            '2026-09-25', auto_detect=mode != 'disabled', gaming_session_id=42,
        )
        assert result == (replacement if mode == 'replacement' else {})
    db.execute.assert_not_awaited()
    if mode == 'disabled':
        manager.detect_session_teams.assert_not_awaited()
    if mode == 'replacement':
        manager.store_session_teams.assert_awaited_once_with(
            '2026-09-25', replacement, auto_assign_names=False, gaming_session_id=42,
        )
    else:
        manager.store_session_teams.assert_not_awaited()
