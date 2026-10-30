"""One killable batch with child-owned DB resources; no service or automatic loop."""

import asyncio
import time
from functools import partial

import asyncpg

from shared.runtime_cache_main import emit_status
from shared.runtime_proximity_config import ProximityProcessConfig
from shared.runtime_proximity_cursor import process_proximity_checkpointed_batch
from shared.runtime_worker import WorkerResult, run_bounded_owned_task


async def _batch(config):
    # The parent passes configuration only, never a connection, pool or lock.
    pool = await asyncpg.create_pool(**config.pool_options())
    try:
        acquire = config.resource_factory(pool)
        mapping_options = {'allow_declared_mapping': True} if config.allow_declared_mapping else {}
        async with acquire() as (adapter, observer):
            result = await process_proximity_checkpointed_batch(
                config.root, source_id=config.source_id, now=int(time.time()),
                adapter=adapter, observer=observer, gametimes_dir=config.gametimes_dir,
                **mapping_options,
            )
        counts = dict.fromkeys(('committed', 'deferred', 'retry', 'reconcile'), 0)
        for item in result.items:
            counts[item.result.action] += 1
        emit_status(dict(component='runtime_proximity_batch', status='observed',
                         last_batch_counts=counts,
                         last_batch_exhausted=sum(item.result.reason == 'exhausted' for item in result.items)))
    finally:
        try:
            async with asyncio.timeout(5):
                await pool.close()
        except (Exception, asyncio.CancelledError):
            pool.terminate()
            raise


def _execute_batch(config):
    asyncio.run(_batch(config))


def run_bounded_proximity_batch(
    config: ProximityProcessConfig, *, timeout_seconds: float = 60, shutdown_grace: float = 1,
) -> WorkerResult:
    """Synchronously supervise one fresh spawned batch, reaping before return.

    Caller supplies explicitly approved DEV config/immutable local spool, ideally
    built through the guarded process config reader. This helper is not an
    activation gate, legacy-writer lease or restart/polling loop. Do not call it
    directly on an event loop. Connections and flock are created ONLY inside
    the child; never inherit active DB state into it. No shared IPC queue.

    Timeout may occur before, during OR after DB commit/cursor fsync. It is an
    UNKNOWN import outcome, not rollback or success. Retain all inputs/history;
    next batch rechecks current receipts through the existing queue path. Child
    JSON describes its last batch observation, not source deletion permission.
    Child success means the call returned and cleanup completed, not all inputs
    imported (some may be deferred/reconcile). Parent receives process status.

    Existing supervisor bounds child join then terminates/kills only its owned
    child and reaps it. Sync user-space stalls no longer freeze the parent;
    uninterruptible kernel I/O/process creation still cannot be hard-bounded.
    Reaping failure raises; never report success while an old child may run.
    SIGINT/termination policy follows runtime_worker; service SIGTERM orchestration
    remains a separate gate. A crash bypasses child finally; DB backend rollback
    may lag reaping and must be independently observed, not assumed instantaneous.
    """
    if not isinstance(config, ProximityProcessConfig):
        raise TypeError('Explicit proximity process configuration required')
    return run_bounded_owned_task(partial(_execute_batch, config),
                                  timeout_seconds=timeout_seconds, shutdown_grace=shutdown_grace)
