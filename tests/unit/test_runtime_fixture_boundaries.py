"""Actual runtime fixture lifecycle with recorded transports, never real PG."""

import os
import pwd
import subprocess
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from tests.integration import test_runtime_events_pg as events
from tests.integration import test_runtime_full_import_pg as full


def test_runtime_fixture_collection_has_no_application_or_database_setup(tmp_path):
    script = r'''
import asyncpg
import dotenv
import pytest
def forbidden(*args, **kwargs):
    raise AssertionError('COLLECTION_SIDE_EFFECT')
asyncpg.connect = asyncpg.create_pool = dotenv.load_dotenv = forbidden
raise SystemExit(pytest.main([
    '-o', 'addopts=', '-p', 'pytest_asyncio.plugin', '-p', 'pytest_timeout',
    '--collect-only', '-q', 'tests/integration/test_runtime_events_pg.py',
    'tests/integration/test_runtime_full_import_pg.py',
]))
'''
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
             "BOT_LOG_DIR": str(tmp_path / "bot"), "WEB_LOG_DIR": str(tmp_path / "web")},
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "test_completed_pair_persists_real_player_weapon_rows" in result.stdout
    assert "test_commit_visibility_retry_and_notification" in result.stdout


def test_legacy_wrapper_pins_private_identity_despite_ambient_libpq(monkeypatch):
    with tempfile.TemporaryDirectory(prefix="slomix-runtime-pg-", dir="/tmp") as directory:
        monkeypatch.setenv("RUNTIME_EVENTS_TEST_SOCKET", directory)
        monkeypatch.setenv("PGUSER", "wrong")
        monkeypatch.setenv("PGPORT", "6543")
        monkeypatch.setenv("PGPASSWORD", "wrong")
        assert events.connection_options() == dict(
            host=directory, port=5432, database="postgres",
            user=pwd.getpwuid(os.getuid()).pw_name, password="",
            timeout=5, command_timeout=5, ssl=False,
        )


@pytest.mark.parametrize("flag", [None, "RUNTIME_EVENTS_TEST_SOCKET", "RUNTIME_EVENTS_TEST_CI"])
def test_only_absent_opt_in_skips(monkeypatch, flag):
    monkeypatch.delenv("RUNTIME_EVENTS_TEST_SOCKET", raising=False)
    monkeypatch.delenv("RUNTIME_EVENTS_TEST_CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    if flag:
        monkeypatch.setenv(flag, "")
    with pytest.raises(ValueError if flag else pytest.skip.Exception):
        events.connection_options()


async def test_full_fixture_rejects_target_before_transport(monkeypatch):
    monkeypatch.setenv("RUNTIME_EVENTS_TEST_SOCKET", "/var/run/postgresql")
    connect = AsyncMock(side_effect=AssertionError("TRANSPORT_REACHED"))
    monkeypatch.setattr(full.asyncpg, "connect", connect)
    with pytest.raises(ValueError, match="non-private"):
        await anext(full.full_import_db.__wrapped__())
    connect.assert_not_awaited()


@pytest.mark.parametrize("failure", [None, "connect", "database", "user", "schema", "pool",
                                    "body", "pool_close", "reader_close"])
async def test_full_fixture_cleanup_order_and_visible_failures(monkeypatch, failure):
    history = []
    config = dict(host="synthetic", port=5432, database="slomix_fixture_synthetic",
                  user="synthetic", password="")

    @asynccontextmanager
    async def owned():
        history.append("created")
        try:
            yield config
        finally:
            history.append("owned_cleanup")

    reader = AsyncMock()
    reader.fetchval.side_effect = [
        "wrong" if failure == "database" else config["database"],
        "wrong" if failure == "user" else config["user"],
    ]
    if failure == "schema":
        reader.execute.side_effect = RuntimeError("schema")

    async def close_reader(*, timeout):
        assert timeout == 5
        history.append("reader_close")
        if failure == "reader_close":
            raise RuntimeError("reader_close")

    reader.close.side_effect = close_reader
    pool = AsyncMock()

    async def close_pool():
        history.append("pool_close")
        if failure == "pool_close":
            raise RuntimeError("pool_close")

    pool.close.side_effect = close_pool
    connect = AsyncMock(return_value=reader)
    create_pool = AsyncMock(return_value=pool)
    if failure == "connect":
        connect.side_effect = OSError("connect")
    if failure == "pool":
        create_pool.side_effect = RuntimeError("pool")
    monkeypatch.setattr(full, "connection_options", lambda: config)
    monkeypatch.setattr(full, "isolated_database", owned)
    monkeypatch.setattr(full.asyncpg, "connect", connect)
    monkeypatch.setattr(full.asyncpg, "create_pool", create_pool)
    generator = full.full_import_db.__wrapped__()
    if failure in {"connect", "database", "user", "schema", "pool"}:
        error = AssertionError if failure in {"database", "user"} else (
            OSError if failure == "connect" else RuntimeError)
        with pytest.raises(error):
            await anext(generator)
    else:
        manager, observer = await anext(generator)
        assert manager.pool is pool and observer is reader and manager.event_stream_enabled
        if failure == "body":
            with pytest.raises(RuntimeError, match="body"):
                await generator.athrow(RuntimeError("body"))
        elif failure:
            with pytest.raises(RuntimeError, match=failure):
                await anext(generator)
        else:
            with pytest.raises(StopAsyncIteration):
                await anext(generator)
    expected = ["created"]
    if failure not in {"connect", "database", "user", "schema", "pool"}:
        expected.append("pool_close")
    if failure != "connect":
        expected.append("reader_close")
    expected.append("owned_cleanup")
    assert history == expected
    connect.assert_awaited_once_with(**config, timeout=5, command_timeout=5, ssl=False)
    if failure in {"database", "user"}:
        reader.execute.assert_not_awaited()
    if failure not in {"connect", "database", "user", "schema"}:
        create_pool.assert_awaited_once_with(
            **config, timeout=5, command_timeout=5, ssl=False, min_size=1, max_size=2)


@pytest.mark.parametrize("create_fails", [False, True])
async def test_journal_cleanup_requires_successful_schema_creation(monkeypatch, create_fails):
    writer, reader = AsyncMock(), AsyncMock()
    monkeypatch.setattr(events, "connection_options", lambda: {})
    monkeypatch.setattr(events.asyncpg, "connect", AsyncMock(side_effect=[writer, reader]))
    if create_fails:
        writer.execute.side_effect = RuntimeError("create denied or collision")
    generator = events.journal_db.__wrapped__()
    if create_fails:
        with pytest.raises(RuntimeError, match="create denied"):
            await anext(generator)
        assert writer.execute.await_count == 1  # No DROP of an unowned schema.
    else:
        assert await anext(generator) == (writer, reader)
        with pytest.raises(RuntimeError, match="body"):
            await generator.athrow(RuntimeError("body"))
        create = writer.execute.await_args_list[0].args[0]
        schema = create.split('"')[1]
        assert schema.startswith("runtime_events_test_")
        writer.execute.assert_awaited_with(f'DROP SCHEMA "{schema}" CASCADE', timeout=5)
    reader.close.assert_awaited_once_with(timeout=5)
    writer.close.assert_awaited_once_with(timeout=5)


@pytest.mark.parametrize("failure", ["reader_connect", "search_path", "reader_close", "drop"])
async def test_journal_setup_and_cleanup_failures_close_available_connections(monkeypatch, failure):
    writer, reader = AsyncMock(), AsyncMock()
    history = []

    async def execute(query, **kwargs):
        if query.startswith("CREATE SCHEMA"):
            history.append("created")
        if failure == "search_path" and query.startswith("SET search_path"):
            raise RuntimeError("search_path")
        if query.startswith("DROP SCHEMA"):
            history.append("drop")
            if failure == "drop":
                raise RuntimeError("drop")

    async def reader_close(**kwargs):
        history.append("reader_close")
        if failure == "reader_close":
            raise RuntimeError("reader_close")

    async def writer_close(**kwargs):
        history.append("writer_close")

    writer.execute.side_effect = execute
    reader.close.side_effect = reader_close
    writer.close.side_effect = writer_close
    monkeypatch.setattr(events, "connection_options", lambda: {})
    connect = AsyncMock(side_effect=[writer, OSError("reader_connect") if failure == "reader_connect" else reader])
    monkeypatch.setattr(events.asyncpg, "connect", connect)
    generator = events.journal_db.__wrapped__()
    if failure in {"reader_connect", "search_path"}:
        with pytest.raises(OSError if failure == "reader_connect" else RuntimeError, match=failure):
            await anext(generator)
    else:
        assert await anext(generator) == (writer, reader)
        with pytest.raises(RuntimeError, match=failure):
            await anext(generator)
    if failure == "reader_connect":
        assert history == ["writer_close"]
        writer.execute.assert_not_awaited()
        reader.close.assert_not_awaited()
    else:
        assert history == ["created", "reader_close", "drop", "writer_close"]
        reader.close.assert_awaited_once_with(timeout=5)
    writer.close.assert_awaited_once_with(timeout=5)
