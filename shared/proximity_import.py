"""Caller-owned proximity import boundary, without Discord or service startup.

This is not a scheduler or a single-writer lease. The caller supplies a sealed
private local file, its trusted size/SHA-256, the resolved session date, and a
transaction-capable adapter. Remote
capture, durable retries and correlation delivery remain caller responsibilities.
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from proximity.parser import ProximityParserV4
from proximity.parser.import_receipt import claim_import_receipt
from shared.proximity_source import bind_proximity_source, read_verified_proximity_source


class _ImportFailed(Exception):
    """Roll back the outer content binding when canonical import reports failure."""


@dataclass(frozen=True)
class ProximityImportResult:
    success: bool
    # Parsed counts are not proof of committed rows; absent on failed imports.
    parsed_stats: dict | None


async def import_proximity_file(
    filepath: Path, *, adapter, session_date: date, gametimes_dir: Path,
    expected_size: int, expected_sha256: str, max_bytes: int = 8 * 1024 * 1024,
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
    """
    if type(session_date) is not date:
        raise TypeError("session_date must be an explicitly resolved datetime.date")
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
    try:
        async with adapter.transaction():
            await claim_import_receipt(adapter, filepath.name, source_sha256=expected_sha256)
            await bind_proximity_source(adapter, filepath.name, expected_sha256)
            success = await parser.import_file(str(filepath), session_date, source_bytes=payload)
            if not success:
                raise _ImportFailed
    except _ImportFailed:
        return ProximityImportResult(False, None)
    return ProximityImportResult(True, parser.get_stats())
