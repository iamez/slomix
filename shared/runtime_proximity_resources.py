"""Borrow separate writer/observer resources from an existing owned adapter."""

from contextlib import asynccontextmanager

from bot.core.database_adapter import PostgreSQLAdapter

_IDENTITY = '''SELECT current_database() AS database, current_schema() AS schema,
    pg_is_in_recovery() AS recovery,
    current_setting('transaction_read_only') AS read_only'''


async def _identity(connection):
    if connection.is_in_transaction() is not False:
        raise RuntimeError('Proximity resources require connections outside transactions')
    row = await connection.fetchrow(_IDENTITY)
    if (row is None or row['recovery'] is not False or row['read_only'] != 'off'
            or not row['database'] or not row['schema']):
        raise RuntimeError('Proximity resources require a writable primary and explicit schema')
    return row['database'], row['schema']


@asynccontextmanager
async def proximity_database_resources(adapter: PostgreSQLAdapter):
    """Per-batch factory for RuntimeProximityWorker; never create a pool.

    Caller explicitly configures/connects and exclusively owns this adapter/pool
    for one worker, to the SAME authoritative primary/schema. No dotenv/default
    credentials, migration, service or DB mutation. Pool needs at least two slots:
    hold observer while canonical adapter transactions borrow another connection.
    Reject inherited writer transactions, replicas/read-only connections and
    database/schema mismatch before yielding. The probe transaction is NOT held
    around the batch: canonical import must commit before observer checks it.

    Pool acquire/release provides native rollback/reset; retain no borrowed
    connection after context exit. Errors/cancellation propagate and unwind both
    contexts. Worker bounds acquisition/work cooperatively; caller owns pool
    close/termination and explicit connection/command/server statement timeouts.
    Query identity checks are observations, not host/cluster/production attestation
    or an exclusive legacy-writer lease. External pool reconfiguration/use during
    a batch violates ownership; never point this at a load-balanced replica pool.
    """
    if not isinstance(adapter, PostgreSQLAdapter) or adapter.pool is None:
        raise TypeError('An explicitly connected PostgreSQLAdapter is required')
    pool = adapter.pool
    if pool.get_max_size() < 2:
        raise ValueError('Proximity writer and observer require at least two pool slots')
    async with pool.acquire() as observer:
        observer_identity = await _identity(observer)
        async with adapter.connection() as writer:
            if writer.get_server_pid() == observer.get_server_pid():
                raise RuntimeError('Proximity writer and observer must be separate backends')
            if await _identity(writer) != observer_identity:
                raise RuntimeError('Proximity writer and observer database/schema differ')
        # Writer probe is released; no encompassing transaction hides later commits.
        yield adapter, observer
