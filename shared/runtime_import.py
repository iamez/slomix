"""Caller-driven import step for an immutable, fully downloaded stats spool."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from shared.runtime_spool import validate_stats_filename


@dataclass(frozen=True)
class ImportStepResult:
    """Waiting is not success or a terminal parse failure; retain the file."""

    status: Literal['waiting_for_r1', 'imported', 'retryable_failure', 'failed']
    message: str


def _validate_import_filename(filename: str) -> None:
    """Shared importer admission before dependency discovery or deduplication."""
    validate_stats_filename(filename)
    try:
        stamp = datetime.strptime(filename[:17] + '+0000', '%Y-%m-%d-%H%M%S%z')
    except ValueError as error:
        raise ValueError('Invalid stats timestamp') from error
    # Match the canonical filename year range without importing bot presentation.
    # In particular year 0001 can underflow the parser's previous-day lookup.
    if not 2020 <= stamp.year <= 2035:
        raise ValueError('Invalid stats timestamp')


def _can_wait_for_r1(filename: str) -> bool:
    """Only a structurally and calendrically valid R2 can await a future R1."""
    try:
        _validate_import_filename(filename)
    except ValueError:
        return False
    return filename.endswith('-round-2.txt')


async def import_ready_file(manager, file_path: Path) -> ImportStepResult:
    """Defer R2 without its parser-selected R1; otherwise use canonical import.

    The caller owns the manager, pool, retries and immutable completed spool.
    No files are deleted, no pool is created/closed, and no background task or
    marker is written for a deferred R2. A missing dependency first checks for
    existing successful processing; lookup failures propagate to the caller.
    This does not repair existing orphans. Invalid filenames/calendar dates fail
    before canonical import, without a processed_files marker; callers must
    consume the returned terminal status rather than infer it from markers.
    Retention must keep selected R1 files stable throughout parsing; this check
    is not a filesystem lock or a guard against concurrent spool mutation.
    """
    file_path = file_path.absolute()
    try:
        _validate_import_filename(file_path.name)
    except ValueError as error:
        return ImportStepResult('failed', str(error))
    if _can_wait_for_r1(file_path.name):
        dependency = manager.parser.find_corresponding_round_1_file(str(file_path))
        if dependency is not None:
            try:
                _validate_import_filename(Path(dependency).name)
            except ValueError as error:
                return ImportStepResult('failed', f'Invalid R1 dependency: {error}')
        if dependency is None:
            if await manager.is_file_processed(file_path.name):
                return ImportStepResult('imported', 'Already processed')
            duplicate = await manager.find_processed_duplicate(file_path)
            if not duplicate or duplicate == file_path.name or not _can_wait_for_r1(duplicate):
                return ImportStepResult('waiting_for_r1', 'Matching R1 file is not available')
            # Let the canonical path record the renamed duplicate's marker.
    result = await manager.process_file(file_path)
    success, message = result
    if success:
        return ImportStepResult('imported', message)
    status = 'retryable_failure' if getattr(result, 'retryable', False) else 'failed'
    return ImportStepResult(status, message)
