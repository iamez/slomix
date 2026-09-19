"""Process ownership/configuration proofs, without an application database."""

import asyncio
import json
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared import runtime_cache_main as entry
from shared.runtime_cache_worker import CacheWorkerState

FLAGS = ("EVENT_STREAM_ENABLED", "RUNTIME_HTTP_CACHE_EVENTS_ENABLED", "RUNTIME_HTTP_CACHE_WORKER_ENABLED")


@pytest.fixture
def config_env(monkeypatch):
    for flag in FLAGS:
        monkeypatch.setenv(flag, "true")
    for key, value in dict(BOT_ENVIRONMENT="dev", POSTGRES_HOST="127.0.0.1",
                           POSTGRES_PORT="5432", POSTGRES_DATABASE="test_only",
                           POSTGRES_USER="test_only", POSTGRES_PASSWORD="test-only").items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("RUNTIME_CACHE_DB_SCHEMA", raising=False)


@pytest.mark.parametrize("key,value", [
    ("BOT_ENVIRONMENT", "production"), ("BOT_ENVIRONMENT", ""),
    ("POSTGRES_HOST", "remote.invalid"), ("POSTGRES_HOST", "localhost"),
    ("POSTGRES_PORT", "0"), ("POSTGRES_PORT", "65536"), ("POSTGRES_PORT", "x"),
    ("POSTGRES_DATABASE", ""), ("POSTGRES_USER", ""), ("POSTGRES_PASSWORD", ""),
    ("RUNTIME_CACHE_DB_SCHEMA", "public, other"), ("RUNTIME_CACHE_DB_SCHEMA", 'x";'),
])
def test_config_rejects_unsafe_or_incomplete_environment(config_env, monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        entry.DatabaseConfig.from_environment()


def test_explicit_config_does_not_expose_password(config_env, monkeypatch):
    config = entry.DatabaseConfig.from_environment()
    assert config.password not in repr(config)
    assert config.pool_options()["min_size"] == 0
    assert config.pool_options()["max_size"] == 1
    monkeypatch.setenv("POSTGRES_HOST", "/tmp/test-socket")
    monkeypatch.delenv("POSTGRES_PASSWORD")
    assert entry.DatabaseConfig.from_environment().pool_options()["password"] == ""


@pytest.mark.parametrize("flag", FLAGS)
async def test_disabled_exits_before_config_pool_and_signals(config_env, monkeypatch, capsys, flag):
    monkeypatch.setenv(flag, "false")
    monkeypatch.setenv("BOT_ENVIRONMENT", "production")
    forbidden = MagicMock(side_effect=AssertionError("must not run"))
    monkeypatch.setattr(entry, "serve", forbidden)
    monkeypatch.setattr(entry.asyncio, "get_running_loop", forbidden)
    await entry.run()
    assert json.loads(capsys.readouterr().out)["status"] == "disabled"
    forbidden.assert_not_called()


def test_module_import_and_disabled_subprocess_need_no_discord():
    env = {key: value for key, value in os.environ.items()
           if key not in FLAGS and not key.startswith(("DISCORD_", "POSTGRES_"))}
    code = (
        "import sys; from shared.runtime_cache_main import main; "
        "assert not any(k.split('.')[0] in ('discord', 'bot', 'website') for k in sys.modules); "
        "raise SystemExit(main())"
    )
    result = subprocess.run([sys.executable, "-c", code], env=env,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "disabled"


def test_invalid_environment_fails_process_without_secret(config_env, monkeypatch, capsys):
    monkeypatch.setenv("POSTGRES_PORT", "test-secret-invalid-port")
    assert entry.main() == 1
    captured = capsys.readouterr()
    assert "test-secret" not in captured.out + captured.err
    assert json.loads(captured.out) == dict(component="runtime_cache_consumer",
                                          status="failed", error_type="ValueError")


def test_unexpected_runtime_failure_is_nonzero_and_sanitized(monkeypatch, capsys):
    monkeypatch.setattr(entry, "run", AsyncMock(side_effect=RuntimeError("test-secret")))
    assert entry.main() == 1
    captured = capsys.readouterr()
    assert "test-secret" not in captured.out + captured.err
    assert json.loads(captured.out)["error_type"] == "RuntimeError"


async def test_signal_handlers_restored_after_failure(config_env, monkeypatch):
    loop = MagicMock()
    monkeypatch.setattr(entry.asyncio, "get_running_loop", lambda: loop)
    monkeypatch.setattr(entry, "serve", AsyncMock(side_effect=RuntimeError("test-only")))
    with pytest.raises(RuntimeError):
        await entry.run()
    assert [call.args[0] for call in loop.add_signal_handler.call_args_list] == [
        call.args[0] for call in loop.remove_signal_handler.call_args_list
    ] == [entry.signal.SIGTERM, entry.signal.SIGINT]


class Worker:
    def __init__(self, mode="stop"):
        self.state = CacheWorkerState(status="starting")
        self.entered = asyncio.Event()
        self.cleaned = False
        self.mode = mode

    async def run(self, acquire, stop):
        try:
            async with acquire():
                self.entered.set()
                if self.mode == "fail":
                    self.state = replace(self.state, status="failed")
                    raise RuntimeError("unexpected-test-only")
                if self.mode == "hang":
                    await asyncio.Event().wait()
                else:
                    await stop.wait()
        finally:
            self.cleaned = True


def fake_pool():
    pool = MagicMock()
    pool.close = AsyncMock()
    pool.released = False

    @asynccontextmanager
    async def acquire():
        try:
            yield object()
        finally:
            pool.released = True

    pool.acquire = acquire
    return pool


@pytest.mark.parametrize("mode", ["stop", "hang", "fail", "cancel"])
async def test_owned_task_and_pool_cleanup(config_env, mode):
    worker = Worker("hang" if mode == "cancel" else mode)
    pool = fake_pool()
    factory = AsyncMock(return_value=pool)
    stop = asyncio.Event()
    states = []
    task = asyncio.create_task(entry.serve(
        entry.DatabaseConfig.from_environment(), stop, worker=worker,
        pool_factory=factory, reporter=states.append, drain_seconds=0.01,
    ))
    try:
        await asyncio.wait_for(worker.entered.wait(), 1)
        if mode == "cancel":
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        elif mode == "fail":
            with pytest.raises(RuntimeError, match="unexpected-test-only"):
                await task
        else:
            stop.set()
            await asyncio.wait_for(task, 1)
        assert worker.cleaned and pool.released
        factory.assert_awaited_once()
        pool.close.assert_awaited_once()
        pool.terminate.assert_not_called()
        assert states
        assert states[0].status == "starting"
        assert not any(t.get_name().startswith("runtime-cache-") for t in asyncio.all_tasks())
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_pool_close_timeout_terminates_and_fails(config_env):
    pool = fake_pool()
    async def stuck():
        await asyncio.Event().wait()

    pool.close.side_effect = stuck
    stop = asyncio.Event()
    stop.set()
    with pytest.raises(TimeoutError):
        await entry.serve(entry.DatabaseConfig.from_environment(), stop,
                          pool_factory=AsyncMock(return_value=pool), reporter=lambda _: None,
                          close_seconds=0.01)
    pool.terminate.assert_called_once()


def test_health_does_not_claim_ingest_progress(capsys):
    entry.report(CacheWorkerState(status="unavailable", generation=7,
                                  unsupported_pending=2, error_type="ConnectionError"))
    output = json.loads(capsys.readouterr().out)
    assert output["component"] == "runtime_cache_consumer"
    assert output["status"] == "unavailable"
    assert output["last_success_age_seconds"] is None
    assert output["generation"] == 7 and output["unsupported_pending"] == 2
