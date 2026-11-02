"""One paced strict import attempt; classification never acknowledges a commit."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from shared.runtime_proximity_ingest import CompletedProximityImportResult, import_admitted_proximity_file
from shared.runtime_proximity_retry import ProximityRetryPermit, reserve_proximity_retry


@dataclass(frozen=True)
class ProximityDispatchResult:
    permit: ProximityRetryPermit
    action: Literal['deferred', 'retry', 'reconcile', 'verify_commit']
    reason: str
    import_result: CompletedProximityImportResult | None = None


def classify_proximity_import(result: CompletedProximityImportResult) -> tuple[str, str]:
    """Retry only explicitly understood absence; unknown failures need review.

    Success is transaction-scoped. verify_commit is NOT done, a producer ack or
    permission to delete input. The caller must independently verify durable
    commit before retiring work. No exception is converted to a retry here.
    """
    if not isinstance(result, CompletedProximityImportResult):
        raise ValueError('Dispatcher requires a completed import observation')
    state, imported = result.manifest_status, result.import_result
    if state != 'match':
        if imported is not None:
            raise ValueError('Import result without matching completion')
        if state in ('missing_manifest', 'missing_content'):
            return 'retry', state
        if state in ('content_conflict', 'receipt_conflict'):
            return 'reconcile', state
        raise ValueError('Unknown completion observation')
    if imported is None or type(imported.success) is not bool:
        raise ValueError('Matching completion requires an import outcome')
    if imported.success:
        if (imported.pending_reason is not None
                or type(imported.round_id) is not int or imported.round_id <= 0
                or type(imported.gaming_session_id) is not int or imported.gaming_session_id <= 0):
            raise ValueError('Successful strict import requires exact parent/session identity')
        return 'verify_commit', 'transaction_scoped_success'
    if imported.pending_reason in ('parent_missing', 'session_missing'):
        return 'retry', imported.pending_reason
    # Do not echo arbitrary upstream error text into future status/log surfaces.
    if imported.pending_reason in ('parent_ambiguous', 'declared_identity_mapping_pending'):
        return 'reconcile', imported.pending_reason
    return 'reconcile', 'unclassified_import_failure'


async def dispatch_proximity_once(
    directory: Path, *, source_id: str, generation: str, now: int,
    adapter, gametimes_dir: Path,
    allow_declared_mapping: bool = False,
) -> ProximityDispatchResult:
    """Compose persisted pacing and canonical import while holding local flock.

    Non-reserved permits never call the importer or DB. Reserved attempts stay
    spent after cancellation/error; all exceptions propagate, releasing the lock.
    Caller owns timeouts and adapter/outer transaction. No connection, loop,
    discovery, deletion, terminal marker, source ack or service is created.
    Local private immutable directory and cooperative-lock limitations remain
    those of reserve_proximity_retry. Outcome is returned, not persisted; future
    scheduling must stop automatic retries on reconcile and verify commits on
    verify_commit, not infer completed work from the word success.
    """
    if type(allow_declared_mapping) is not bool:
        raise ValueError('Explicit declared mapping policy required')
    options = {'allow_declared_mapping': True} if allow_declared_mapping else {}
    with reserve_proximity_retry(directory, source_id=source_id, generation=generation, now=now) as permit:
        if permit.status != 'reserved':
            action = 'reconcile' if permit.status == 'exhausted' else 'deferred'
            return ProximityDispatchResult(permit, action, permit.status)
        result = await import_admitted_proximity_file(
            directory, source_id=source_id, generation=generation,
            adapter=adapter, gametimes_dir=gametimes_dir,
            **options,
        )
        action, reason = classify_proximity_import(result)
        return ProximityDispatchResult(permit, action, reason, result)
