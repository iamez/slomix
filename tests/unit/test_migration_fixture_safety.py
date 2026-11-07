"""Exercise actual migration fixtures with transport denied or recorded."""

import os
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from tests.integration import test_apply_migrations_pg as fixtures


def test_migration_collection_never_loads_dotenv_or_connects(tmp_path):
    root = Path(__file__).resolve().parents[2]
    script = r'''
import asyncpg
import dotenv
import pytest
def forbidden(*args, **kwargs):
    raise AssertionError('COLLECTION_SIDE_EFFECT')
asyncpg.connect = asyncpg.create_pool = dotenv.load_dotenv = forbidden
raise SystemExit(pytest.main([
    '-o', 'addopts=', '-p', 'pytest_asyncio.plugin', '--collect-only', '-q',
    'tests/integration/test_apply_migrations_pg.py',
]))
'''
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=root,
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
             "BOT_LOG_DIR": str(tmp_path / "bot"), "WEB_LOG_DIR": str(tmp_path / "web")},
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "4 tests collected" in result.stdout


@pytest.mark.parametrize("requested", [False, True])
async def test_unapproved_target_never_connects(monkeypatch, requested):
    monkeypatch.delenv("RUNTIME_EVENTS_TEST_SOCKET", raising=False)
    monkeypatch.delenv("RUNTIME_EVENTS_TEST_CI", raising=False)
    monkeypatch.setenv("POSTGRES_TEST_HOST", "192.0.2.1")
    monkeypatch.setenv("POSTGRES_TEST_DATABASE", "etlegacy")
    if requested:
        monkeypatch.setenv("RUNTIME_EVENTS_TEST_CI", "true")
    connect = AsyncMock(side_effect=AssertionError("TRANSPORT_REACHED"))
    monkeypatch.setattr(fixtures.asyncpg, "connect", connect)
    generator = fixtures.migration_target.__wrapped__()
    error = ValueError if requested else pytest.skip.Exception
    with pytest.raises(error):
        await anext(generator)
    connect.assert_not_awaited()


@pytest.mark.parametrize("failure", [OSError("requested unavailable"), RuntimeError("cleanup failed")])
async def test_requested_setup_and_cleanup_failures_are_not_skipped(monkeypatch, failure):
    monkeypatch.setenv("RUNTIME_EVENTS_TEST_CI", "true")
    reached = []

    @asynccontextmanager
    async def owned():
        if isinstance(failure, OSError):
            raise failure
        try:
            yield target()
        finally:
            reached.append("cleanup")
            raise failure

    monkeypatch.setattr(fixtures, "isolated_database", owned)
    generator = fixtures.migration_target.__wrapped__()
    if isinstance(failure, OSError):
        with pytest.raises(OSError, match="requested unavailable"):
            await anext(generator)
    else:
        assert await anext(generator) == target()
        with pytest.raises(RuntimeError, match="cleanup failed"):
            await anext(generator)
        assert reached == ["cleanup"]


def target():
    return dict(host="synthetic", port=5432, database="slomix_fixture_synthetic",
                user="synthetic", password="")


async def test_runner_uses_owned_identity_and_refuses_later_drift(monkeypatch, tmp_path):
    monkeypatch.setenv("POSTGRES_DATABASE", "etlegacy")
    monkeypatch.setenv("DB_PASSWORD", "hostile-fallback")
    monkeypatch.setenv("PGPORT", "6543")
    runner = fixtures.migration_runner.__wrapped__(monkeypatch)
    directory = fixtures.runner_env.__wrapped__(monkeypatch, tmp_path, target(), runner)
    assert directory == runner.MIGRATIONS_DIR
    assert runner.get_connection_kwargs() == target()
    connect = AsyncMock()
    monkeypatch.setattr(fixtures.asyncpg, "connect", connect)
    assert await runner.get_connection() is connect.return_value
    connect.assert_awaited_once_with(**target(), timeout=5, command_timeout=5, ssl=False)
    monkeypatch.setenv("POSTGRES_DATABASE", "etlegacy")
    with pytest.raises(AssertionError, match="escaped its owned test database"):
        await runner.get_connection()
    assert connect.await_count == 1


@pytest.mark.parametrize("identity_ok", [False, True])
async def test_reader_is_closed_on_setup_or_body_failure(monkeypatch, identity_ok):
    conn = AsyncMock()
    conn.fetchval.side_effect = [target()["database"] if identity_ok else "wrong", None]
    monkeypatch.setattr(fixtures.asyncpg, "connect", AsyncMock(return_value=conn))
    generator = fixtures.pg.__wrapped__(None, target())
    if identity_ok:
        reader, namespace = await anext(generator)
        assert reader is conn and namespace.startswith("migit_")
        with pytest.raises(RuntimeError, match="test body failed"):
            await generator.athrow(RuntimeError("test body failed"))
    else:
        with pytest.raises(AssertionError):
            await anext(generator)
    conn.close.assert_awaited_once_with(timeout=5)
