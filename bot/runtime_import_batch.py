"""Bounded caller-supplied batch; not a durable scheduler or source discovery."""

from dataclasses import dataclass

from bot.runtime_completed_import import CompletedRoundInput
from bot.runtime_import_attempt import run_import_once, validate_attempt_policy, validate_import_envelope
from bot.runtime_import_session import validate_team_policy
from shared.runtime_round_identity import RoundIdentity, require_round_pair
from shared.runtime_writer_lock import local_import_writer


@dataclass(frozen=True)
class ImportJob:
    current: CompletedRoundInput
    first: CompletedRoundInput | None = None
    expected_identity: RoundIdentity | None = None


async def run_import_batch(database, jobs, *, journal_enabled, attempt_timeout=60.0,
                           require_declared_identity=False, defer_team_assignment=False):
    """Run up to sixteen explicit jobs serially; stop at first unsuccessful result.

    Validate the entire finite job envelope before any attempt. Caller supplies
    trusted source identities/pairing and owns ordering and durable scheduling.
    Returned tuple contains attempted canonical results, including a final failure;
    it is NOT an acknowledgement or permission to delete sources. Warnings retain
    canonical success semantics. Exceptions/deadlines/cancellation propagate and
    prevent subsequent jobs. Earlier commits remain durable; replay is idempotent.
    No automatic retry, parallel tasks, cross-process lock or hard batch deadline.
    Empty input is a no-op. Each attempt retains its own cooperative time budget.
    Each bound job supplies its independently trusted expected identity. No mixed
    bound/legacy batch: missing expectations must not silently downgrade a job.
    Metadata is preflighted for all jobs; later file/DB failures may still leave
    earlier commits. Sources are not opened until their attempt.
    """
    validate_team_policy(defer_team_assignment, journal_enabled)
    validate_attempt_policy(require_declared_identity, attempt_timeout)
    if type(jobs) is not tuple or len(jobs) > 16:
        raise ValueError('Provide an explicit tuple of at most sixteen import jobs')
    for job in jobs:
        if (not isinstance(job, ImportJob) or not isinstance(job.current, CompletedRoundInput)
                or (job.first is not None and not isinstance(job.first, CompletedRoundInput))):
            raise ValueError('Every job requires explicit completed inputs')
        validate_import_envelope(job.current, job.first, job.expected_identity, journal_enabled=journal_enabled)
    if any(job.expected_identity is not None for job in jobs):
        if any(job.expected_identity is None for job in jobs):
            raise ValueError('Do not mix bound and legacy jobs')
        for job in jobs:
            if job.first is None:
                continue
            for candidate in jobs:
                if (candidate.current.root, candidate.current.generation) == (job.first.root, job.first.generation):
                    if candidate.current != job.first:
                        raise ValueError('Conflicting R1 artifact in batch')
                    require_round_pair(candidate.expected_identity, job.expected_identity)
    outcomes = []
    for job in jobs:
        result = await run_import_once(
            database, job.current, first=job.first,
            journal_enabled=journal_enabled, timeout=attempt_timeout,
            require_declared_identity=require_declared_identity,
            expected_identity=job.expected_identity, defer_team_assignment=defer_team_assignment,
        )
        outcomes.append(result)
        if result[0] is not True:
            break
    return tuple(outcomes)


async def run_exclusive_import_batch(
    database, jobs, *, lock_directory, journal_enabled, attempt_timeout=60.0,
    require_declared_identity=False, defer_team_assignment=False,
):
    """Opt-in host-local exclusion spanning all attempts and their cleanup.

    All cooperating writers must use the same stable directory/inode. This does
    not stop an existing bot/manual writer or provide cross-host DB exclusion.
    Busy fails before an attempt; exception/cancellation releases the local lock.
    """
    validate_team_policy(defer_team_assignment, journal_enabled)
    with local_import_writer(lock_directory):
        return await run_import_batch(
            database, jobs, journal_enabled=journal_enabled, attempt_timeout=attempt_timeout,
            require_declared_identity=require_declared_identity, defer_team_assignment=defer_team_assignment,
        )
