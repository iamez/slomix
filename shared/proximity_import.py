"""Caller-owned proximity import boundary, without Discord or service startup.

This is not a scheduler or a single-writer lease. The caller supplies a sealed
local file, the resolved session date, and a transaction-capable adapter. Remote
capture, durable retries and correlation delivery remain caller responsibilities.
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from proximity.parser import ProximityParserV4


@dataclass(frozen=True)
class ProximityImportResult:
    success: bool
    # Parsed counts are not proof of committed rows; absent on failed imports.
    parsed_stats: dict | None


async def import_proximity_file(
    filepath: Path, *, adapter, session_date: date, gametimes_dir: Path,
) -> ProximityImportResult:
    """Use the canonical parser; never create a connection or guess a session.

    Canonical and runtime imports require transactions. A failure must not be
    acknowledged as a completed import.
    The adapter must implement the canonical database adapter contract, including
    transaction-bound execute/fetch methods. No local marker is written here.
    """
    if type(session_date) is not date:
        raise TypeError("session_date must be an explicitly resolved datetime.date")
    if not callable(getattr(adapter, "transaction", None)):
        raise TypeError("Proximity runtime import requires a transaction-capable adapter")
    if not filepath.is_file():
        raise FileNotFoundError(filepath)
    parser = ProximityParserV4(
        db_adapter=adapter, output_dir=str(filepath.parent),
        gametimes_dir=str(gametimes_dir),
    )
    success = await parser.import_file(str(filepath), session_date)
    return ProximityImportResult(success, parser.get_stats() if success else None)
