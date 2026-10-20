"""Cooperative team-writer transaction boundary; all writers must opt in."""

from contextlib import asynccontextmanager

# One database-wide namespace covers both legacy date and numeric session scopes.
# Two signed-int keys use PostgreSQL's distinct two-key advisory-lock namespace.
TEAM_LOCK_NAMESPACE = int.from_bytes(b'SLOM', 'big')
TEAM_LOCK_RESOURCE = int.from_bytes(b'TEAM', 'big')


class TeamWriteBusy(RuntimeError):
    """Another transaction owns the team writer slot; retry the whole operation."""


@asynccontextmanager
async def team_write_transaction(conn):
    """Borrow a native connection and serialize cooperating read/modify/write work.

    Enter BEFORE roster reads; keep effect and any consumer receipt inside this
    scope. Never acknowledge on contention. The caller owns connection/pool life
    and deadlines; a nonblocking lock request does not bound network I/O.
    A nested scope uses a savepoint: success retains the lock until outer COMMIT.
    READ COMMITTED is required so a prior snapshot cannot bypass serialization.
    No manual unlock, session-level locks, fallback, retry loop or service setup.
    All writers must adopt this protocol before system-wide exclusion is claimed.
    """
    async with conn.transaction():
        if await conn.fetchval('SHOW transaction_isolation') != 'read committed':
            raise ValueError('Team writer requires READ COMMITTED isolation')
        acquired = await conn.fetchval(
            'SELECT pg_try_advisory_xact_lock($1::integer, $2::integer)',
            TEAM_LOCK_NAMESPACE, TEAM_LOCK_RESOURCE,
        )
        if acquired is not True:
            raise TeamWriteBusy('Team writer is busy; retry the complete operation')
        yield conn
