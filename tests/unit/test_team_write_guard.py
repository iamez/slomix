"""A team writer never enters on missing, rejected or failed lock acquisition."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from shared.team_write_guard import TeamWriteBusy, team_write_transaction


@pytest.mark.parametrize('lock_result', [True, False, None, 1, 'true', RuntimeError('SQL error'), asyncio.CancelledError()])
async def test_guard_fails_closed_and_leaves_transaction(lock_result):
    state = {'active': False, 'exited': False, 'entered': False}

    @asynccontextmanager
    async def transaction():
        state['active'] = True
        try:
            yield
        finally:
            state['active'] = False
            state['exited'] = True

    async def fetchval(query, *params):
        assert state['active']
        if query == 'SHOW transaction_isolation':
            return 'read committed'
        if isinstance(lock_result, BaseException):
            raise lock_result
        return lock_result

    conn = SimpleNamespace(transaction=transaction, fetchval=AsyncMock(side_effect=fetchval))

    async def operate():
        async with team_write_transaction(conn) as borrowed:
            assert borrowed is conn
            state['entered'] = True

    if lock_result is True:
        await operate()
    else:
        expected = type(lock_result) if isinstance(lock_result, BaseException) else TeamWriteBusy
        with pytest.raises(expected):
            await operate()
    assert state['entered'] is (lock_result is True)
    assert state['exited'] and not state['active']
    assert conn.fetchval.await_count == 2
