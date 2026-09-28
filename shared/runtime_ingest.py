"""Verified local-spool entry into the canonical dependency-aware importer."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from shared.runtime_import import (
    ImportStepResult,
    _can_wait_for_r1,
    _validate_import_filename,
    import_ready_file,
)
from shared.runtime_spool import inspect_published_stats_file


@dataclass(frozen=True)
class ExpectedStatsIdentity:
    """Trusted immutable source metadata, never derived from a conflicted spool."""

    size: int
    sha256: str


@dataclass(frozen=True)
class VerifiedImportResult:
    """Separate observations; capture None means filename rejected before I/O."""

    capture_status: Literal['missing', 'match', 'conflict'] | None
    import_result: ImportStepResult | None
    dependency_status: Literal['not_required', 'missing', 'unverified', 'match', 'conflict', 'invalid'] | None = None


async def import_verified_file(
    manager, directory: Path, filename: str, *, expected_size: int,
    expected_sha256: str, max_bytes: int = 8 * 1024 * 1024,
    expected_r1: Mapping[str, ExpectedStatsIdentity] | None = None,
) -> VerifiedImportResult:
    """Only a matching immutable spool entry reaches canonical import.

    Caller owns capture, expected source identity, stable private spool/R1
    retention, manager and pool. Construct the manager with
    allow_legacy_r1_fallback=False. Local inspection is synchronous and byte-bounded,
    not time-bounded; use in a dedicated ingestion process, not a web handler.
    No executor, network connection, retry loop, deletion or durability ack.
    Files must remain immutable between verification and parsing; no locking or
    protection against a same-UID writer is implied. I/O/DB/cancellation propagate.
    For R2, supply trusted source identities keyed by R1 filename. A selected
    dependency without admission metadata or with conflicting content blocks
    import without DB markers. Existing R1 callers need no additional argument.
    Invalid names return terminal failed before I/O, with capture_status=None;
    this is unmeasured content, not a missing file or a verified match.
    An invalid selected R1 returns terminal failed with dependency_status=invalid;
    the current capture remains match, but dependency bytes are not inspected.
    """
    try:
        _validate_import_filename(filename)
    except ValueError as error:
        return VerifiedImportResult(None, ImportStepResult('failed', str(error)))
    directory = directory.absolute()
    state = inspect_published_stats_file(
        directory, filename, expected_size=expected_size,
        expected_sha256=expected_sha256, max_bytes=max_bytes,
    )
    if state != 'match':
        return VerifiedImportResult(state, None)
    if manager.parser.allow_legacy_r1_fallback is not False:
        raise ValueError('Verified import requires a spool-only R1 parser')
    dependency_status = 'not_required' if filename.endswith('-round-1.txt') else None
    if _can_wait_for_r1(filename):
        selected = manager.parser.find_corresponding_round_1_file(str(directory / filename))
        dependency_status = 'missing'
        if selected is not None:
            dependency = Path(selected).absolute()
            if dependency.parent != directory:
                raise ValueError('Selected R1 must remain inside the verified spool')
            try:
                _validate_import_filename(dependency.name)
            except ValueError as error:
                return VerifiedImportResult(
                    state, ImportStepResult('failed', f'Invalid R1 dependency: {error}'), 'invalid',
                )
            identity = (expected_r1 or {}).get(dependency.name)
            if identity is None:
                return VerifiedImportResult(state, None, 'unverified')
            dependency_status = inspect_published_stats_file(
                directory, dependency.name, expected_size=identity.size,
                expected_sha256=identity.sha256, max_bytes=max_bytes,
            )
            if dependency_status != 'match':
                return VerifiedImportResult(state, None, dependency_status)
    result = await import_ready_file(manager, directory / filename)
    return VerifiedImportResult(state, result, dependency_status)
