"""Successful controller capture -> existing exclusive canonical import batch."""

from bot.runtime_completed_import import CompletedRoundInput
from bot.runtime_import_batch import ImportJob, run_exclusive_import_batch
from bot.runtime_import_session import validate_team_policy
from shared.runtime_captured_match import CapturedMatch


async def import_captured_match(database, captured, *, lock_directory, attempt_timeout=60.0,
                                defer_team_assignment=False):
    """Explicit opt-in import with mandatory journal and declared identity checks.

    Pass the successful controller.captured_match() result, never reconstruct
    authority from files. Uses the existing importer/parser, R2 differential,
    identity mapping and cooperative local writer lock. The caller supplies a
    schema-ready isolated/exclusively handed-over DB and stable lock directory.
    Private captured files must be readable under the existing same-UID contract;
    this is not a remote or cross-user transport and does not relax permissions.

    Return canonical outcomes unchanged, including warnings or a failed prefix.
    A later failure/cancellation may follow an earlier commit. Sources remain,
    explicit idempotent replay is possible, and there is no automatic retry,
    source ACK, notification, service control or scheduler. Capture state stays
    separate from import results, so DB failure does not invalidate captured bytes.
    """
    validate_team_policy(defer_team_assignment, True)
    if not isinstance(captured, CapturedMatch):
        raise ValueError('Successful controller capture handoff required')
    captured.verify()

    def completed(item):
        ref = item.reference
        return CompletedRoundInput(item.root, ref.generation, ref.filename, ref.size, ref.sha256)

    first, second = completed(captured.first), completed(captured.second)
    return await run_exclusive_import_batch(
        database, (ImportJob(first, expected_identity=captured.first_identity),
                   ImportJob(second, first=first, expected_identity=captured.second_identity)),
        lock_directory=lock_directory, journal_enabled=True,
        attempt_timeout=attempt_timeout, require_declared_identity=True,
        defer_team_assignment=defer_team_assignment,
    )
