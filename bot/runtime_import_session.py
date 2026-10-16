"""Explicit single-owner importer session; no configuration discovery or activation."""

import asyncio
import math
from contextlib import asynccontextmanager

from postgresql_database_manager import PostgreSQLDatabaseManager


def validate_team_policy(defer_team_assignment, journal_enabled):
    if type(defer_team_assignment) is not bool:
        raise ValueError('defer_team_assignment must be an explicit boolean')
    if defer_team_assignment and journal_enabled is not True:
        raise ValueError('Deferred team assignment requires enabled journal')


@asynccontextmanager
async def open_import_session(config, *, pool_factory, journal_enabled, close_timeout=5.0,
                              defer_team_assignment=False):
    """Borrow the owned pool to one canonical manager for the context lifetime.

    The caller authenticates the target and supplies an asynchronous pool factory
    with bounded connection/query budgets and cancellation-safe creation. This
    helper does not discover credentials, migrate, schedule, retry or start tasks.
    Successful factory return transfers pool ownership here. Closing is bounded;
    failed/cancelled close terminates the pool and propagates the failure. Sources
    and durable receipts are never removed. An import failure or cancellation
    remains primary if close also fails, with the close error chained as cause.
    Without an import failure, the close error propagates as before.
    Do not retain or close the manager
    outside the context or use it concurrently with context exit. Explicit team
    deferral requires journaling before any pool creation; no ambient flag selects
    effect ownership. The default preserves legacy team assignment.
    """
    validate_team_policy(defer_team_assignment, journal_enabled)
    if config is None:
        raise ValueError('Explicit importer configuration is required')
    if type(journal_enabled) is not bool:
        raise ValueError('journal_enabled must be an explicit boolean')
    if isinstance(close_timeout, bool) or not isinstance(close_timeout, (int, float)):
        raise ValueError('close_timeout must be finite and between 0 and 30 seconds')
    if not math.isfinite(close_timeout) or not 0 < close_timeout <= 30:
        raise ValueError('close_timeout must be finite and between 0 and 30 seconds')
    manager = PostgreSQLDatabaseManager(config=config, defer_team_assignment=defer_team_assignment)
    manager.event_stream_enabled = journal_enabled
    pool = await pool_factory()
    manager.pool = pool
    failure = None
    try:
        yield manager
    except BaseException as error:
        failure = error
        raise
    finally:
        # Stop exposing a pool whose shutdown has started, including on failure.
        manager.pool = None
        try:
            await asyncio.wait_for(pool.close(), timeout=close_timeout)
        except BaseException as close_error:
            pool.terminate()
            if failure is not None:
                raise failure from close_error
            raise
