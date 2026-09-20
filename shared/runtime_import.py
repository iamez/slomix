"""Caller-driven import step for an immutable, fully downloaded stats spool."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class ImportStepResult:
    """Waiting is not success or a terminal parse failure; retain the file."""

    status: Literal['waiting_for_r1', 'imported', 'retryable_failure', 'failed']
    message: str


async def import_ready_file(manager, file_path: Path) -> ImportStepResult:
    """Defer R2 without its parser-selected R1; otherwise use canonical import.

    The caller owns the manager, pool, retries and immutable completed spool.
    No files are deleted, no pool is created/closed, and no background task or
    marker is written for a deferred R2. A missing dependency first checks for
    existing successful processing; lookup failures propagate to the caller.
    This does not repair existing orphans.
    Retention must keep selected R1 files stable throughout parsing; this check
    is not a filesystem lock or a guard against concurrent spool mutation.
    """
    file_path = file_path.absolute()
    if file_path.name.lower().endswith('-round-2.txt'):
        dependency = manager.parser.find_corresponding_round_1_file(str(file_path))
        if dependency is None:
            if await manager.is_file_processed(file_path.name):
                return ImportStepResult('imported', 'Already processed')
            return ImportStepResult('waiting_for_r1', 'Matching R1 file is not available')
    result = await manager.process_file(file_path)
    success, message = result
    if success:
        return ImportStepResult('imported', message)
    status = 'retryable_failure' if getattr(result, 'retryable', False) else 'failed'
    return ImportStepResult(status, message)
