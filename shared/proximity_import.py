"""Caller-owned proximity import boundary, without Discord or service startup.

This is not a scheduler or a single-writer lease. The caller supplies a sealed
private local file, its trusted size/SHA-256, the resolved session date, and a
transaction-capable adapter. Remote
capture, durable retries and correlation delivery remain caller responsibilities.
"""

import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from proximity.parser import ProximityParserV4
from proximity.parser.import_receipt import claim_import_receipt
from shared.proximity_source import bind_proximity_source, read_verified_proximity_source


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
    This mode requires migration094 and defers first ingestion, rather than
    repairing history. Receipts created by the permissive path are rejected:
    the persisted runtime_parent_gate must prove strict first ingestion.
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
    parser = ProximityParserV4(
        db_adapter=adapter, output_dir=str(filepath.parent),
        gametimes_dir=str(gametimes_dir),
    )
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
            success = await parser.import_file(str(filepath), session_date, source_bytes=payload)
            if not success:
                raise _ImportFailed
            if require_linked_parent:
                confirmed = await _linked_parent(adapter, parser.metadata)
                if (confirmed != parent
                        or parser._round_link_context.get('round_id') != parent[0]):  # noqa: SLF001 -- canonical parser integration seam, checked before commit
                    raise RuntimeError('Proximity parent identity changed during import')
    except _ParentPending as exc:
        return ProximityImportResult(False, None, pending_reason=str(exc))
    except _ImportFailed:
        return ProximityImportResult(False, None)
    return ProximityImportResult(
        True, parser.get_stats(), round_id=parent[0] if parent else None,
        gaming_session_id=parent[1] if parent else None,
    )
