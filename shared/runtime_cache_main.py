"""Dev-only cache consumer process: python -m shared.runtime_cache_main.

No dotenv, Discord, HTTP startup, ingestion or service supervision. The three
worker flags default OFF. Explicit local PostgreSQL configuration is required
when enabled; BOT_ENVIRONMENT=dev is a guard, not database identity attestation.
"""

import asyncio
import json
import os
import re
import signal
import sys
import time
from dataclasses import dataclass, field, replace

import asyncpg

from shared.runtime_cache_worker import RuntimeCacheWorker, cache_worker_enabled


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    database: str
    user: str
    password: str = field(repr=False)
    schema: str = "public"

    @classmethod
    def from_environment(cls):
        if os.environ.get("BOT_ENVIRONMENT") != "dev":
            raise ValueError("Cache process requires explicit dev environment")
        required = ("POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DATABASE", "POSTGRES_USER")
        if any(not os.environ.get(key, "").strip() for key in required):
            raise ValueError("Explicit PostgreSQL configuration required")
        host, port, database, user = (os.environ[key] for key in required)
        # No DNS, remote hosts or multi-host fallback in this dev-only slice.
        if host not in ("127.0.0.1", "::1") and not host.startswith("/"):
            raise ValueError("Local PostgreSQL host required")
        port = int(port)
        if not 1 <= port <= 65535:
            raise ValueError("Invalid PostgreSQL port")
        password = os.environ.get("POSTGRES_PASSWORD", "")
        if not host.startswith("/") and not password:
            raise ValueError("Explicit TCP password required")
        schema = os.environ.get("RUNTIME_CACHE_DB_SCHEMA", "public")
        if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", schema):
            raise ValueError("Invalid PostgreSQL schema")
        return cls(host, port, database, user, password, schema)

    def pool_options(self):
        return dict(
            host=self.host, port=self.port, database=self.database, user=self.user,
            password=self.password, min_size=0, max_size=1,
            timeout=5, command_timeout=10,
            server_settings={
                "search_path": f'"{self.schema}"',
                "application_name": "slomix-runtime-cache-dev",
                "statement_timeout": "10000",
            },
        )


def emit_status(values):
    sys.stdout.write(json.dumps(values) + "\n")
    sys.stdout.flush()


def report(state):
    """Machine-readable health of this consumer only, never producer health."""
    age = None if state.last_success_monotonic is None else max(
        0, time.monotonic() - state.last_success_monotonic,
    )
    emit_status(dict(
        component="runtime_cache_consumer", status=state.status,
        generation=state.generation, unsupported_pending=state.unsupported_pending,
        last_success_age_seconds=age, error_type=state.error_type,
    ))


async def serve(config, stop, *, worker=None, pool_factory=None, reporter=report,
                health_seconds=5, drain_seconds=11, close_seconds=5):
    """Own exactly one worker and pool; return only after both are cleaned up.

    Pool starts empty so initial DB outages follow the worker's bounded retry
    path. Schema/permission errors remain unavailable, never healthy idle.
    Caller cancellation cancels active work; a stop event first allows draining.
    """
    worker = worker or RuntimeCacheWorker()
    pool_factory = pool_factory or asyncpg.create_pool
    pool = await pool_factory(**config.pool_options())
    task = None
    stopping = None
    try:
        task = asyncio.create_task(worker.run(pool.acquire, stop), name="runtime-cache-consumer")
        stopping = asyncio.create_task(stop.wait(), name="runtime-cache-stop")
        reporter(replace(worker.state, status="starting"))
        while not task.done() and not stop.is_set():
            await asyncio.wait((task, stopping), timeout=health_seconds,
                               return_when=asyncio.FIRST_COMPLETED)
            reporter(worker.state)
        if stop.is_set() and not task.done():
            reporter(replace(worker.state, status="shutting_down"))
            done, _ = await asyncio.wait((task,), timeout=drain_seconds)
            if not done:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass  # Only our requested cancellation is a clean stop.
                return
        await task  # Unexpected worker errors must reach the process exit code.
    finally:
        for owned in (task, stopping):
            if owned is not None and not owned.done():
                owned.cancel()
        await asyncio.gather(*(owned for owned in (task, stopping) if owned is not None),
                             return_exceptions=True)
        try:
            async with asyncio.timeout(close_seconds):
                await pool.close()
        except BaseException:
            pool.terminate()
            raise
        finally:
            reporter(worker.state)


async def run():
    if not cache_worker_enabled():
        report(RuntimeCacheWorker().state)
        return
    config = DatabaseConfig.from_environment()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    installed = []
    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(signum, stop.set)
            installed.append(signum)
        await serve(config, stop)
    finally:
        for signum in installed:
            loop.remove_signal_handler(signum)


def main():
    try:
        asyncio.run(run())
    except Exception as error:
        # No raw exception, DSN, environment values or traceback in process logs.
        emit_status(dict(component="runtime_cache_consumer", status="failed",
                         error_type=type(error).__name__))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
