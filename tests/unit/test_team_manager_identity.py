"""All ID-scoped team writers reject ambiguous ownership before roster access."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.core.team_manager import TeamManager
from shared.team_identity import TeamIdentityConflict, require_resolved_team_identity


@pytest.mark.parametrize('value', [True, None, 0, 1, 'false'])
def test_identity_admission_requires_explicit_false(value):
    with pytest.raises(TeamIdentityConflict):
        require_resolved_team_identity(value)
    require_resolved_team_identity(False)


@pytest.mark.parametrize('operation', ['create', 'update', 'replace', 'repair', 'random', 'custom'])
async def test_manager_rejects_identity_before_roster_access(operation):
    state = {'depth': 0, 'locked': False}

    @asynccontextmanager
    async def transaction():
        state['depth'] += 1
        try:
            yield native
        finally:
            state['depth'] -= 1

    async def fetchval(query, *args):
        assert state['depth'] >= 2
        if query == 'SHOW transaction_isolation':
            return 'read committed'
        assert 'pg_try_advisory_xact_lock' in query
        state['locked'] = True
        return True

    async def identity(query, params):
        assert state['depth'] >= 2 and state['locked']
        assert 'gaming_session_id IS NULL' in query
        assert params == (42, '2026-09-25')
        return True

    native = SimpleNamespace(transaction=transaction, fetchval=fetchval)
    db = SimpleNamespace(
        transaction=transaction, fetch_val=AsyncMock(side_effect=identity),
        fetch_one=AsyncMock(), fetch_all=AsyncMock(), execute=AsyncMock(),
    )
    manager = TeamManager(db)
    manager._ensure_session_teams_table = AsyncMock()  # noqa: SLF001 -- isolate existing schema
    manager._get_session_teams_columns = AsyncMock(return_value={'gaming_session_id'})  # noqa: SLF001
    manager.detect_session_teams = AsyncMock()
    manager.get_team_pool = AsyncMock()

    async def invoke():
        if operation == 'create':
            return await manager.create_initial_teams_from_round(1, '2026-09-25', 42)
        if operation == 'update':
            return await manager.update_teams_from_round(1, '2026-09-25', 42)
        if operation == 'replace':
            return await manager.store_session_teams('2026-09-25', {}, gaming_session_id=42)
        if operation == 'repair':
            return await manager.get_session_teams('2026-09-25', gaming_session_id=42)
        if operation == 'random':
            return await manager.assign_random_team_names('2026-09-25', gaming_session_id=42)
        return await manager.set_custom_team_names('2026-09-25', 'A', 'B', 42)

    if operation in ('create', 'update'):
        assert await invoke() == (False if operation == 'create' else {})
    else:
        with pytest.raises(TeamIdentityConflict):
            await invoke()
    assert state['depth'] == 0
    db.fetch_val.assert_awaited_once()
    db.fetch_one.assert_not_awaited()
    db.fetch_all.assert_not_awaited()
    db.execute.assert_not_awaited()
    manager.detect_session_teams.assert_not_awaited()
    manager.get_team_pool.assert_not_awaited()


@pytest.mark.parametrize('columns,session_id', [(set(), 42), ({'gaming_session_id'}, None)])
async def test_legacy_scope_does_not_query_missing_identity(columns, session_id):
    db = SimpleNamespace(fetch_val=AsyncMock())
    await TeamManager(db)._require_team_identity(columns, '2026-09-25', session_id)  # noqa: SLF001 -- compatibility boundary
    db.fetch_val.assert_not_awaited()
