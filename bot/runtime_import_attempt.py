"""One explicitly requested import; no discovery, retries, daemon or activation."""

import asyncio
import math
import re
from functools import partial
from pathlib import Path
from types import SimpleNamespace

from bot.runtime_completed_import import CompletedRoundInput, import_completed_round
from bot.runtime_import_session import open_import_session, validate_team_policy
from bot.runtime_round_mapping import StatsRoundBinding
from bot.runtime_snapshot_pair import _identity, validate_pair_metadata
from shared.runtime_import_pool import ImportDatabaseConfig, create_import_pool
from shared.runtime_round_identity import RoundIdentity
from shared.runtime_spool import _validate_metadata


class ImportAttemptTimeout(TimeoutError):
    """Attempt deadline expired; commit outcome may be unknown, retain the source."""


def validate_import_envelope(current, first, expected_identity, *, journal_enabled):
    """Pure metadata preflight, never derive authority from source bytes."""
    for item in (current,) if first is None else (current, first):
        if not isinstance(item, CompletedRoundInput):
            raise ValueError('Every job requires explicit completed inputs')
        if not isinstance(item.root, Path) or not item.root.is_absolute():
            raise ValueError('Completion root must be an absolute Path')
        if not isinstance(item.generation, str) or re.fullmatch('[0-9a-f]{32}', item.generation) is None:
            raise ValueError('Invalid completion generation')
        if not isinstance(item.filename, str) or len(item.filename) > 240 or item.sha256 is None:
            raise ValueError('Completion requires bounded filename and trusted digest')
        _validate_metadata(item.filename, item.size, 8 * 1024 * 1024, item.sha256)
    half = 2 if current.filename.endswith('-round-2.txt') else 1
    if (half == 1 and first is not None) or (half == 2 and first is None):
        raise ValueError('Explicit R1 dependency required only for R2')
    if first is not None and not first.filename.endswith('-round-1.txt'):
        raise ValueError('Dependency must be R1')
    map_name = validate_pair_metadata(first, current) if first is not None else _identity(current, 1)[0]
    if expected_identity is not None:
        if not isinstance(expected_identity, RoundIdentity) or expected_identity.round_number != half:
            raise ValueError('Expected identity must match input half')
        if journal_enabled is not True:
            raise ValueError('Canonical identity mapping requires enabled journal')
        dependency = None
        if first is not None:
            first_identity = RoundIdentity(expected_identity.source_id, expected_identity.match_id,
                                           expected_identity.first_round_id, 1, expected_identity.first_round_id)
            dependency = StatsRoundBinding(first_identity, first.generation, first.filename,
                                           first.size, first.sha256, map_name)
        StatsRoundBinding(expected_identity, current.generation, current.filename, current.size,
                          current.sha256, map_name, dependency)


def validate_attempt_policy(require_declared_identity, timeout):
    if type(require_declared_identity) is not bool:
        raise ValueError('Explicit boolean identity policy required')
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise ValueError('Attempt timeout must be finite and between 0 and 300 seconds')
    if not math.isfinite(timeout) or not 0 < timeout <= 300:
        raise ValueError('Attempt timeout must be finite and between 0 and 300 seconds')


async def run_import_once(database, current, *, first=None, journal_enabled, timeout=60.0,
                          require_declared_identity=False, expected_identity=None, defer_team_assignment=False):
    """Compose explicit pool, owned session and canonical receipt-based import.

    Caller authenticates database/source expectations and serializes attempts.
    Return canonical results unchanged, including warnings/retry eligibility.
    Cancellation propagates after session cleanup. A timeout is NOT proof of a
    rollback: it can occur after commit or during close. Retain inputs for replay.
    Budget is cooperative; synchronous sealing/parsing and cancellation cleanup
    may exceed it. No hard process deadline, source deletion or automatic retry.
    Optional strict declaration checking is forwarded before canonical preflight;
    it detects contradictions, not source authentication or physical provenance.
    Explicit defer_team_assignment passes through the owned session; it requires
    journaling and changes no batch/CLI defaults or other writers.
    """
    validate_team_policy(defer_team_assignment, journal_enabled)
    validate_attempt_policy(require_declared_identity, timeout)
    if not isinstance(database, ImportDatabaseConfig):
        raise ValueError('Explicit ImportDatabaseConfig required')
    validate_import_envelope(current, first, expected_identity, journal_enabled=journal_enabled)
    budget = asyncio.timeout(timeout)
    try:
        async with budget, open_import_session(
            SimpleNamespace(database_type='postgresql'),
            pool_factory=partial(create_import_pool, database), journal_enabled=journal_enabled,
            defer_team_assignment=defer_team_assignment,
        ) as manager:
            return await import_completed_round(
                manager, current, first=first, require_declared_identity=require_declared_identity,
                expected_identity=expected_identity,
            )
    except TimeoutError:
        if budget.expired():
            raise ImportAttemptTimeout('Import attempt deadline exceeded; retain source for replay') from None
        raise
