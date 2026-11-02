"""One recoverable queue turn; outcome history is never a permanent done flag."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from shared.runtime_manifest_reader import _decode_manifest, _read_private_manifest_bytes
from shared.runtime_proximity_admission import read_proximity_admission
from shared.runtime_proximity_commit import inspect_proximity_commit
from shared.runtime_proximity_dispatch import classify_proximity_import
from shared.runtime_proximity_ingest import import_admitted_proximity_file
from shared.runtime_proximity_retry import _LIMIT, _history, _identity, reserve_proximity_retry
from shared.runtime_spool import _publish_file

_REASONS = {
    'retry': {'missing_manifest', 'missing_content', 'parent_missing', 'session_missing', 'receipt_not_visible'},
    'reconcile': {'content_conflict', 'receipt_conflict', 'parent_ambiguous', 'unclassified_import_failure',
                  'source_identity_conflict', 'strict_provenance_missing', 'aggregates_not_confirmed',
                  'declared_identity_mapping_pending'},
    'committed': {'matching_strict_receipt_visible'},
}


@dataclass(frozen=True)
class ProximityQueueResult:
    action: str
    reason: str
    attempt: int | None = None


def _name(number):
    return f'.proximity-outcome-{number:03d}.json'


def _hold(directory, identity):
    """Validate bounded history; sticky reconciliation survives worker restarts."""
    latest = _history(directory, identity)
    spent = latest['attempt'] if latest else 0
    hold = None
    for number in range(1, _LIMIT + 1):
        raw = _read_private_manifest_bytes(directory, _name(number))
        if raw is None:
            continue  # A charged attempt may have crashed before an outcome.
        data = _decode_manifest(raw)
        if (type(data) is not dict or set(data) != {'version', 'attempt', 'identity_sha256', 'action', 'reason'}
                or type(data['version']) is not int or data['version'] != 1
                or type(data['attempt']) is not int or data['attempt'] != number or number > spent
                or data['identity_sha256'] != identity
                or not isinstance(data['action'], str) or data['action'] not in _REASONS
                or not isinstance(data['reason'], str) or data['reason'] not in _REASONS[data['action']]):
            raise ValueError('Invalid queue outcome schema, identity or attempt')
        if data['action'] == 'reconcile' and hold is None:
            hold = ProximityQueueResult('reconcile', data['reason'], number)
    return hold


def _record(directory, identity, result):
    data = dict(version=1, attempt=result.attempt, identity_sha256=identity,
                action=result.action, reason=result.reason)
    payload = (json.dumps(data, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii')
    _publish_file(directory, _name(result.attempt), [payload], len(payload), hashlib.sha256(payload).hexdigest())


async def process_proximity_once(
    directory: Path, *, source_id: str, generation: str, now: int, adapter, observer, gametimes_dir: Path,
    allow_declared_mapping: bool = False,
) -> ProximityQueueResult:
    """Recover, observe current DB, and perform at most one charged import.

    Immutable, identity-bound per-attempt outcomes persist under the same flock
    as import and post-import verification. Reconcile outcomes conservatively
    block future attempts until explicit operator handling; no reset API exists.
    A recorded committed outcome is HISTORY ONLY: fresh DB verification is
    required on every turn, including after restart/restore and at exhaustion.
    Matching current DB avoids replay and spending a new attempt. Missing DB
    receipt can resume paced import; conflicting DB requires reconciliation.

    Caller owns exclusive primary observer, writer adapter/transaction, local
    immutable private spool, operation timeouts and polling/backoff for DB
    outages. All I/O/DB/cancellation errors propagate, not acknowledged. A crash
    after charge may leave no outcome; canonical receipt replay is still needed.
    Post-link fsync failure may leave visible history, not recovered durability.
    No source deletion/ack, automatic loop/discovery, connection or service.
    Committed means current receipt visibility, not permanent terminal state or
    power-loss durability. Up to 64 attempt +64 outcome reads per history check;
    local cooperating locks are not exclusive handover from legacy writers.
    """
    if type(allow_declared_mapping) is not bool:
        raise ValueError('Explicit declared mapping policy required')
    mapping_options = {'allow_declared_mapping': True} if allow_declared_mapping else {}
    admission = read_proximity_admission(directory, source_id=source_id, generation=generation)
    if admission is None:
        return ProximityQueueResult('deferred', 'missing_admission')
    identity = _identity(admission)
    held = _hold(directory, identity)
    if held is not None:
        return held
    options = dict(source_id=source_id, generation=generation)
    before = await inspect_proximity_commit(directory, **options, observer=observer, **mapping_options)
    if before.status == 'committed':
        return ProximityQueueResult('committed', before.reason)
    if before.status == 'conflict':
        return ProximityQueueResult('reconcile', before.reason)
    if before.status != 'not_committed':
        raise RuntimeError('Admission changed during queue observation')
    with reserve_proximity_retry(directory, **options, now=now) as permit:
        if permit.status != 'reserved':
            return ProximityQueueResult('reconcile' if permit.status == 'exhausted' else 'deferred',
                                        permit.status, permit.attempt)
        # A previous worker may have recorded a hold between our first read and
        # lock acquisition. Conservatively spend this reservation, never import.
        held = _hold(directory, identity)
        if held is not None:
            return held
        result = await import_admitted_proximity_file(directory, **options, adapter=adapter,
                                                      gametimes_dir=gametimes_dir, **mapping_options)
        action, reason = classify_proximity_import(result)
        if action == 'verify_commit':
            after = await inspect_proximity_commit(directory, **options, observer=observer, **mapping_options)
            if after.status == 'committed':
                action, reason = 'committed', after.reason
            elif after.status == 'not_committed':
                action, reason = 'retry', after.reason
            elif after.status == 'conflict':
                action, reason = 'reconcile', after.reason
            else:
                raise RuntimeError('Admission changed during queue verification')
        outcome = ProximityQueueResult(action, reason, permit.attempt)
        _record(directory, identity, outcome)
        return outcome
