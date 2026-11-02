"""Explicit durable artifact linkage only; never apply timing/player corrections."""

from dataclasses import dataclass
from typing import Literal

from bot.runtime_gametime_correlation import inspect_timing_snapshot, verified_timing_binding
from bot.services.lua_correction_inbox import correction_payload_digest, lock_correction_identity


@dataclass(frozen=True)
class GametimeLinkResult:
    status: Literal['linked', 'already_linked', 'not_linked', 'missing_retention', 'mapping_pending', 'conflict']
    reason: str
    round_id: int | None = None
    input_id: int | None = None


_COLUMNS = ('source_key', 'generation', 'round_key', 'canonical_round_id', 'input_id',
            'filename', 'source_size', 'source_sha256', 'projection_sha256')


def _values(timing, identity, projection, observed):
    return (timing.source_id, timing.generation, identity.round_id, observed.round_id, observed.input_id,
            timing.filename, timing.size, timing.sha256, correction_payload_digest(projection))


async def link_declared_gametime(adapter, source_fd, **binding):
    """Write101 only after fresh locked097/098/inbox/099 verification.

    Adapter transaction must yield its native asyncpg connection. Caller owns
    adapter/FD/deadline and trusted binding. Nested transaction success does NOT
    confirm outer commit. Uses read committed and the same correction identity
    advisory lock as retention; canonical/source locks last through outer commit.
    Exclusive handover from legacy correction workers is still required.
    One artifact per canonical round; revisions/new generations reconcile, never
    overwrite. No historical adoption, correction receipt, clock lookup, timing
    or player-stat updates, scheduler, activation, source ACK or deletion.
    """
    timing, projection = verified_timing_binding(source_fd, **binding)
    identity = binding['expected_identity']
    async with adapter.transaction() as connection:
        if await connection.fetchval('SHOW transaction_isolation') != 'read committed':
            raise ValueError('Timing linkage requires read committed writer transaction')
        await lock_correction_identity(adapter, timing.source_id, projection)
        observed = await inspect_timing_snapshot(connection, timing, identity, projection, lock=True)
        if observed.status != 'canonical_target_verified':
            return GametimeLinkResult(observed.status, observed.reason)
        if await connection.fetchval('SELECT 1 FROM lua_correction_receipts WHERE input_id=$1', observed.input_id):
            return GametimeLinkResult('conflict', 'legacy_correction_receipt_present')
        expected = _values(timing, identity, projection, observed)
        # Conflict waiting is provided by PK + unique canonical parent; next
        # SELECT in READ COMMITTED sees the winner, never reassigns its artifact.
        columns = ','.join(_COLUMNS)
        row = await connection.fetchrow(
            f'INSERT INTO runtime_gametime_links ({columns}) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) '
            f'ON CONFLICT DO NOTHING RETURNING {columns}', *expected)
        created = row is not None
        if row is None:
            row = await connection.fetchrow(
                f'SELECT {columns} FROM runtime_gametime_links WHERE source_key=$1 AND generation=$2 FOR SHARE',
                timing.source_id, timing.generation)
        if row is None or tuple(row) != expected:
            raise ValueError('Timing link conflicts with existing artifact or canonical parent')
        return GametimeLinkResult('linked' if created else 'already_linked', 'matching_declared_link',
                                 observed.round_id, observed.input_id)


async def inspect_declared_gametime_link(observer, source_fd, **binding):
    """Independently observe101 and the full current chain in one fresh snapshot.

    Linked means committed LINK only, not timing application or whole-file import.
    Fresh bytes required on replay; changed receipts/parents never inherit proof.
    """
    timing, projection = verified_timing_binding(source_fd, **binding)
    identity = binding['expected_identity']
    if observer.is_in_transaction() is not False:
        raise RuntimeError('Timing link observation requires a connection outside any transaction')
    async with observer.transaction(isolation='repeatable_read', readonly=True):
        return await inspect_link_snapshot(observer, timing, identity, projection)


async def inspect_link_snapshot(connection, timing, identity, projection, *, lock=False):
    """Internal validator: caller owns fresh snapshot or correction lock + tx."""
    observed = await inspect_timing_snapshot(connection, timing, identity, projection, lock=lock)
    if observed.status != 'canonical_target_verified':
        return GametimeLinkResult(observed.status, observed.reason)
    if await connection.fetchval('SELECT 1 FROM lua_correction_receipts WHERE input_id=$1', observed.input_id):
        return GametimeLinkResult('conflict', 'legacy_correction_receipt_present')
    row = await connection.fetchrow(
        'SELECT ' + ','.join(_COLUMNS) + ' FROM runtime_gametime_links WHERE source_key=$1 AND generation=$2'
        + (' FOR SHARE' if lock else ''), timing.source_id, timing.generation)
    if row is None:
        return GametimeLinkResult('not_linked', 'link_not_visible')
    if tuple(row) != _values(timing, identity, projection, observed):
        return GametimeLinkResult('conflict', 'retained_link_conflict')
    return GametimeLinkResult('linked', 'matching_declared_link_visible', observed.round_id, observed.input_id)
