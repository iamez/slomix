"""Caller-driven import step for an immutable, fully downloaded stats spool."""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class ImportStepResult:
    """Waiting is not success or a terminal parse failure; retain the file."""

    status: Literal['waiting_for_r1', 'imported', 'retryable_failure', 'failed']
    message: str


def _can_wait_for_r1(filename: str) -> bool:
    """Only a structurally and calendrically valid R2 can await a future R1."""
    if '..' in filename or not re.fullmatch(r'\d{4}-\d{2}-\d{2}-\d{6}-[A-Za-z0-9_.+-]+-round-2\.txt',
                        filename, re.ASCII):
        return False
    try:
        datetime.strptime(filename[:17] + '+0000', '%Y-%m-%d-%H%M%S%z')
    except ValueError:
        return False
    return True


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
    if _can_wait_for_r1(file_path.name):
        dependency = manager.parser.find_corresponding_round_1_file(str(file_path))
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
