"""Explicit Unix-socket development team session; no production startup wiring."""

import asyncio
import math

from shared.runtime_import_pool import ImportDatabaseConfig, create_import_pool
from shared.runtime_team_worker import RuntimeTeamWorker, TeamWorkerState, team_worker_enabled


async def run_team_worker(database, worker, stop, *, close_timeout=5.0):
    """Run one worker lifetime and close its owned pool before returning.

    Caller authenticates and obtains approval for the explicit Unix-socket target,
    chooses its application_name, and retains the worker for observation. The
    supplied configuration is unchanged; pool construction is not readiness.
    Disabled or already-stopped calls return a fresh state without changing the supplied worker or creating resources. Active calls
    return the worker's final state, not proof of database health or source ACK.
    Sequential calls own distinct pools; do not run the same worker concurrently.

    Successful factory return transfers ownership. The factory owns cleanup of
    incomplete creation. Worker cancellation propagates after pool cleanup;
    failed/cancelled close terminates the pool. A worker failure remains primary,
    with a simultaneous close failure chained as its cause; otherwise close
    failure propagates. No exception is logged here.
    Close timeout is cooperative, not a hard deadline for resistant cleanup.
    No target discovery, dotenv, tasks, schema setup or service action occurs.
    """
    if not team_worker_enabled():
        return TeamWorkerState()
    if not isinstance(stop, asyncio.Event):
        raise ValueError('Explicit asyncio stop event required')
    if stop.is_set():
        return TeamWorkerState(status='stopped')
    if not isinstance(database, ImportDatabaseConfig):
        raise ValueError('Explicit ImportDatabaseConfig required')
    if not isinstance(worker, RuntimeTeamWorker):
        raise ValueError('Explicit RuntimeTeamWorker required')
    if (type(close_timeout) not in (int, float) or not math.isfinite(close_timeout)
            or not 0 < close_timeout <= 30):
        raise ValueError('close_timeout must be finite and between 0 and 30 seconds')
    pool = await create_import_pool(database)
    failure = None
    try:
        await worker.run(pool.acquire, stop)
        return worker.state
    except BaseException as error:
        failure = error
        raise
    finally:
        try:
            await asyncio.wait_for(pool.close(), timeout=close_timeout)
        except BaseException as close_error:
            pool.terminate()
            if failure is not None:
                raise failure from close_error
            raise
