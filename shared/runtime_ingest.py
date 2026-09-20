"""Verified local-spool entry into the canonical dependency-aware importer."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from shared.runtime_import import ImportStepResult, import_ready_file
from shared.runtime_spool import inspect_published_stats_file


@dataclass(frozen=True)
class VerifiedImportResult:
    """Content verification and database import are separate observations."""

    capture_status: Literal['missing', 'match', 'conflict']
    import_result: ImportStepResult | None


async def import_verified_file(
    manager, directory: Path, filename: str, *, expected_size: int,
    expected_sha256: str, max_bytes: int = 8 * 1024 * 1024,
) -> VerifiedImportResult:
    """Only a matching immutable spool entry reaches canonical import.

    Caller owns capture, expected source identity, stable private spool/R1
    retention, manager and pool. Local inspection is synchronous and byte-bounded,
    not time-bounded; use in a dedicated ingestion process, not a web handler.
    No executor, network connection, retry loop, deletion or durability ack.
    Files must remain immutable between verification and parsing; no locking or
    protection against a same-UID writer is implied. I/O/DB/cancellation propagate.
    """
    directory = directory.absolute()
    state = inspect_published_stats_file(
        directory, filename, expected_size=expected_size,
        expected_sha256=expected_sha256, max_bytes=max_bytes,
    )
    if state != 'match':
        return VerifiedImportResult(state, None)
    result = await import_ready_file(manager, directory / filename)
    return VerifiedImportResult(state, result)
