"""ACL fixtures must own their role and release connections on every exit."""

from unittest.mock import AsyncMock, Mock

import pytest

from tests.integration import test_runtime_website_privileges_pg as module


@pytest.fixture
def recorded(monkeypatch):
    history = []
    conn, tx = AsyncMock(), AsyncMock()
    conn.transaction = Mock(return_value=tx)
    conn.fetchval.side_effect = ["140019", False]

    async def started():
        history.append("start")

    async def rollback():
        history.append("rollback")

    async def close(*, timeout):
        assert timeout == 5
        history.append("close")

    tx.start.side_effect = started
    tx.rollback.side_effect = rollback
    conn.close.side_effect = close
    monkeypatch.setenv("RUNTIME_ACL_EXPECTED_PG_MAJOR", "14")
    monkeypatch.setattr(module, "connection_options", lambda: {})
    monkeypatch.setattr(module.asyncpg, "connect", AsyncMock(return_value=conn))
    return conn, tx, history


@pytest.mark.parametrize("failure", ["transaction", "start", "version", "existing_role", "setup"])
async def test_setup_failure_always_closes_and_only_rolls_back_started_transaction(recorded, failure):
    conn, tx, history = recorded
    if failure == "transaction":
        conn.transaction.side_effect = RuntimeError("transaction")
    elif failure == "start":
        tx.start.side_effect = RuntimeError("start")
    elif failure == "version":
        conn.fetchval.side_effect = ["170001"]
    elif failure == "existing_role":
        conn.fetchval.side_effect = ["140019", True]
    else:
        conn.execute.side_effect = RuntimeError("setup")
    expected = AssertionError if failure == "version" else RuntimeError
    generator = module.acl_db.__wrapped__()
    try:
        with pytest.raises(expected):
            await anext(generator)
    finally:
        await generator.aclose()
    conn.close.assert_awaited_once_with(timeout=5)
    if failure in {"transaction", "start"}:
        tx.rollback.assert_not_awaited()
        assert history == ["close"]
    else:
        tx.rollback.assert_awaited_once()
        assert history == ["start", "rollback", "close"]
    if failure != "setup":
        conn.execute.assert_not_awaited()


@pytest.mark.parametrize("failure", [None, "body", "rollback", "close", "body_and_rollback"])
async def test_body_and_teardown_failures_are_visible_and_connection_closes(recorded, failure):
    conn, tx, history = recorded
    generator = module.acl_db.__wrapped__()
    assert await anext(generator) is conn
    assert conn.execute.await_args_list[0].args[0] == (
        "CREATE ROLE website_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT")
    if failure in {"rollback", "body_and_rollback"}:
        async def rollback():
            history.append("rollback")
            raise RuntimeError("rollback")
        tx.rollback.side_effect = rollback
    if failure == "close":
        async def close(*, timeout):
            history.append("close")
            raise RuntimeError("close")
        conn.close.side_effect = close
    try:
        if failure is None:
            with pytest.raises(StopAsyncIteration):
                await anext(generator)
        elif failure in {"body", "body_and_rollback"}:
            with pytest.raises(RuntimeError, match="rollback" if failure.endswith("rollback") else "body") as exc:
                await generator.athrow(RuntimeError("body"))
            if failure == "body_and_rollback":
                assert str(exc.value.__context__) == "body"
        else:
            with pytest.raises(RuntimeError, match=failure):
                await anext(generator)
    finally:
        await generator.aclose()
    assert history == ["start", "rollback", "close"]
    tx.rollback.assert_awaited_once()
    conn.close.assert_awaited_once_with(timeout=5)
