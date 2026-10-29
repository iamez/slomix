"""Caller-owned proximity import boundary, without Discord or service startup.

This is not a scheduler or a single-writer lease. The caller supplies a sealed
private local file, its trusted size/SHA-256, the resolved session date, and a
transaction-capable adapter. Remote
capture, durable retries and correlation delivery remain caller responsibilities.
"""

import time
from dataclasses import dataclass
from datetime import date
from io import StringIO
from pathlib import Path

from proximity.parser import ProximityParserV4
from proximity.parser.import_receipt import claim_import_receipt
from shared.proximity_receipt_link import record_receipt_parent, validate_receipt_parent
from shared.proximity_source import bind_proximity_source, read_verified_proximity_source
from shared.runtime_proximity_identity import proximity_header_identity
from shared.runtime_proximity_mapping import DeclaredMappingPending, DeclaredProximityBinding, resolve_declared_parent


class _ImportFailed(Exception):
    """Roll back the outer content binding when canonical import reports failure."""


class _ParentPending(Exception):
    """No completed import may escape while its parent is unavailable."""


async def _linked_parent(adapter, metadata):
    """Strict physical identity only; no date/nearest-round fallback or repair.

    Caller owns the transaction. Lock the existing parent against update/delete
    through import; this is not a predicate lock against future duplicate inserts.
    A second lookup after parsing detects identity changes observed during import.
    """
    start = metadata.get('round_start_unix')
    number = metadata.get('round_num')
    map_name = metadata.get('map_name')
    if (metadata.get('round_start_is_fallback') or type(start) is not int
            or not 1577836800 < start <= int(time.time()) + 86400
            or type(number) is not int or number not in (1, 2)
            or not isinstance(map_name, str) or not map_name.strip()):
        raise _ParentPending('source_identity_unavailable')
    rows = await adapter.fetch_all(
        'SELECT id, gaming_session_id FROM rounds WHERE LOWER(BTRIM(map_name)) = LOWER(BTRIM(?)) '
        'AND round_number = ? AND round_start_unix = ? ORDER BY id LIMIT 2 FOR SHARE',
        (map_name, number, start),
    )
    if not rows:
        raise _ParentPending('parent_missing')
    if len(rows) != 1:
        raise _ParentPending('parent_ambiguous')
    round_id, session_id = rows[0]
    if session_id is None:
        raise _ParentPending('session_missing')
    return round_id, session_id


@dataclass(frozen=True)
class ProximityImportResult:
    success: bool
    # Parsed counts are not proof of committed rows; absent on failed imports.
    parsed_stats: dict | None
    pending_reason: str | None = None
    round_id: int | None = None
    gaming_session_id: int | None = None


async def import_proximity_file(
    filepath: Path, *, adapter, session_date: date, gametimes_dir: Path,
    expected_size: int, expected_sha256: str, max_bytes: int = 8 * 1024 * 1024,
    require_linked_parent: bool = False,
    declared_binding: DeclaredProximityBinding | None = None,
) -> ProximityImportResult:
    """Use the canonical parser; never create a connection or guess a session.

    Canonical and runtime imports require transactions. A failure must not be
    acknowledged as a completed import.
    The adapter must implement the canonical database adapter contract, including
    transaction-bound execute/fetch methods. No local marker is written here.
    Source validation/conflicts raise before data import; a canonical parser
    failure returns success=False and rolls back the outer digest reservation.
    Legacy receipt adoption is deliberately refused, even for FALSE/NULL flags.
    This is not safe to overlap with an unverified legacy writer. Synchronous
    bounded local reading/parsing is not a background worker or latency promise.

    New runtime delivery must opt into require_linked_parent after exclusive
    forward-only handover. Pending results are NOT acknowledgments: retain the
    sealed source and retry missing parents/sessions with bounded scheduling;
    ambiguous/missing source identity needs reconciliation, not a guessed link.
    This mode requires migrations094/096 and defers first ingestion, rather than
    repairing history. Receipts created by the permissive path are rejected:
    the persisted runtime_parent_gate and linked_round_id must prove strict first
    ingestion. Already-completed pre096 receipts are not silently adopted.
    Default preserves the existing low-level boundary for compatibility. No cog
    or worker is activated here. Successful results remain caller-transaction
    scoped, not evidence that an enclosing transaction has committed.
    """
    if type(session_date) is not date:
        raise TypeError("session_date must be an explicitly resolved datetime.date")
    if type(require_linked_parent) is not bool:
        raise TypeError('require_linked_parent must be a boolean')
    if not callable(getattr(adapter, "transaction", None)):
        raise TypeError("Proximity runtime import requires a transaction-capable adapter")
    payload = read_verified_proximity_source(
        filepath, expected_size=expected_size, expected_sha256=expected_sha256,
        max_bytes=max_bytes,
    )
    declared = proximity_header_identity(StringIO(payload.decode('utf-8', errors='replace')), filepath.name)
    if declared_binding is not None:
        if not isinstance(declared_binding, DeclaredProximityBinding) or require_linked_parent is not True:
            raise ValueError('Declared import requires explicit binding and strict parent policy')
        identity, map_name = declared_binding.verify(payload, filepath.name, session_date)
    if declared is not None and declared_binding is None:
        # Never discard an explicit producer identity and fall back to a clock
        # join. Durable trusted ID-to-parent mapping is a separate activation gate.
        return ProximityImportResult(False, None, pending_reason='declared_identity_mapping_pending')
    parser = ProximityParserV4(
        db_adapter=adapter, output_dir=str(filepath.parent),
        gametimes_dir=str(gametimes_dir),
    )
    if declared_binding is not None:
        try:
            async with adapter.transaction():
                parent = await resolve_declared_parent(adapter, identity, map_name)
                success = await parser.import_file(str(filepath), session_date, source_bytes=payload,
                                                   declared_binding=declared_binding)
                if not success:
                    raise _ImportFailed
                confirmed = await resolve_declared_parent(adapter, identity, map_name)
                if (confirmed != parent or parser._round_link_context.get('round_id') != parent.round_id):  # noqa: SLF001
                    raise ValueError('Declared proximity parent changed during import')
        except DeclaredMappingPending:
            return ProximityImportResult(False, None, pending_reason='declared_identity_mapping_pending')
        except _ImportFailed:
            return ProximityImportResult(False, None)
        return ProximityImportResult(True, parser.get_stats(), round_id=parent.round_id,
                                     gaming_session_id=parent.gaming_session_id)
    parent = None
    if require_linked_parent and not parser.parse_file(str(filepath), source_bytes=payload):
        return ProximityImportResult(False, None)
    try:
        async with adapter.transaction():
            await claim_import_receipt(
                adapter, filepath.name, source_sha256=expected_sha256,
                require_linked_parent=require_linked_parent,
            )
            await bind_proximity_source(adapter, filepath.name, expected_sha256)
            if require_linked_parent:
                parent = await _linked_parent(adapter, parser.metadata)
                await validate_receipt_parent(adapter, filepath.name, parent[0])
            success = await parser.import_file(str(filepath), session_date, source_bytes=payload)
            if not success:
                raise _ImportFailed
            if require_linked_parent:
                confirmed = await _linked_parent(adapter, parser.metadata)
                if (confirmed != parent
                        or parser._round_link_context.get('round_id') != parent[0]):  # noqa: SLF001 -- canonical parser integration seam, checked before commit
                    raise RuntimeError('Proximity parent identity changed during import')
                await record_receipt_parent(adapter, filepath.name, parent[0])
    except _ParentPending as exc:
        return ProximityImportResult(False, None, pending_reason=str(exc))
    except _ImportFailed:
        return ProximityImportResult(False, None)
    return ProximityImportResult(
        True, parser.get_stats(), round_id=parent[0] if parent else None,
        gaming_session_id=parent[1] if parent else None,
    )
