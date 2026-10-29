"""Read committed receipt provenance, never acknowledge from writer-local state."""

from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Literal

from shared.proximity_source import read_verified_proximity_source
from shared.runtime_proximity_admission import read_proximity_admission
from shared.runtime_proximity_identity import proximity_header_identity
from shared.runtime_proximity_mapping import (
    DeclaredProximityBinding,
    resolve_declared_parent,
    validate_declared_receipt,
)


@dataclass(frozen=True)
class ProximityCommitObservation:
    status: Literal['missing_admission', 'not_committed', 'conflict', 'committed']
    reason: str


async def inspect_proximity_commit(
    directory: Path, *, source_id: str, generation: str, observer,
    allow_declared_mapping: bool = False,
) -> ProximityCommitObservation:
    """Observe a matching strict receipt through a fresh read-only transaction.

    Caller supplies an exclusively owned native asyncpg connection to the SAME
    authoritative primary/schema as ingestion, not a lagging replica. Never
    reuse a connection already in a transaction: it might expose its own
    uncommitted receipt. Caller owns connection lifecycle and timeouts; no
    connection, credentials, migrations or service are created here.

    Receipt provenance is valid only under exclusive forward handover from
    legacy writers and the canonical atomic receipt/child import contract.
    Migration096's durable parent link is required: the older strict boolean
    alone cannot prove which round received the artifact. This observes evidence
    verified at ingestion, not immutability of later round metadata/session edits.
    This observes commit visibility, NOT fsync/power-loss durability, complete
    analytics coverage, a source ack or permission to delete/retire data. It
    writes no terminal marker; later DB restore/mutation can invalidate an old
    observation. Admission/private spool must stay immutable. Infrastructure
    errors propagate rather than looking like absence or committed work.
    """
    if type(allow_declared_mapping) is not bool:
        raise ValueError('Explicit declared mapping policy required')
    admission = read_proximity_admission(directory, source_id=source_id, generation=generation)
    if admission is None:
        return ProximityCommitObservation('missing_admission', 'missing_admission')
    if observer.is_in_transaction() is not False:
        raise RuntimeError('Commit observation requires a connection outside any transaction')
    isolation = 'repeatable_read' if allow_declared_mapping else 'read_committed'
    async with observer.transaction(isolation=isolation, readonly=True):
        row = await observer.fetchrow(
            'SELECT file_hash, runtime_parent_gate, aggregates_applied, linked_round_id '
            'FROM proximity_processed_files WHERE filename = $1', admission.filename,
        )
        if row is not None:
            payload = read_verified_proximity_source(directory / admission.filename,
                expected_size=admission.size, expected_sha256=admission.sha256)
            declared = proximity_header_identity(StringIO(payload.decode('utf-8')), admission.filename)
            if declared is not None and not allow_declared_mapping:
                return ProximityCommitObservation('conflict', 'declared_identity_mapping_pending')
        if row is not None and allow_declared_mapping:
            try:
                binding = DeclaredProximityBinding(admission.source_id, admission.generation, admission.filename,
                                                   admission.size, admission.sha256, admission.session_date)
                identity, map_name = binding.verify(payload, admission.filename, admission.session_date)
                reader = _MappingSnapshotReader(observer)
                parent = await resolve_declared_parent(reader, identity, map_name, lock=False)
                await validate_declared_receipt(reader, binding, identity, parent)
            except ValueError:
                return ProximityCommitObservation('conflict', 'strict_provenance_missing')
    if row is None:
        return ProximityCommitObservation('not_committed', 'receipt_not_visible')
    if row['file_hash'] != admission.sha256:
        return ProximityCommitObservation('conflict', 'source_identity_conflict')
    if row['runtime_parent_gate'] is not True:
        return ProximityCommitObservation('conflict', 'strict_provenance_missing')
    if row['aggregates_applied'] is not True:
        return ProximityCommitObservation('conflict', 'aggregates_not_confirmed')
    if row['linked_round_id'] is None:
        return ProximityCommitObservation('conflict', 'strict_provenance_missing')
    return ProximityCommitObservation('committed', 'matching_strict_receipt_visible')


class _MappingSnapshotReader:
    """Bridge ONLY the fixed mapping queries to the caller-owned native reader.

    These private queries contain no quoted question marks/operators; no user SQL
    is accepted. This does not create a pool or import bot/website configuration.
    """

    def __init__(self, connection):
        self.connection = connection

    async def fetch_one(self, query, params=()):
        parts = query.split('?')
        if len(parts) != len(params) + 1:
            raise ValueError('Unexpected mapping query parameter shape')
        sql = parts[0] + ''.join(f'${index}{part}' for index, part in enumerate(parts[1:], 1))
        return await self.connection.fetchrow(sql, *params)
