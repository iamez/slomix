"""One manifest-gated proximity import attempt; no scheduler or source ack."""

from dataclasses import dataclass
from datetime import date
from io import StringIO
from pathlib import Path
from typing import Literal

from shared import proximity_import
from shared.proximity_source import read_verified_proximity_source
from shared.runtime_manifest_reader import inspect_proximity_completion_manifest
from shared.runtime_proximity_admission import read_proximity_admission
from shared.runtime_proximity_identity import proximity_header_identity
from shared.runtime_proximity_mapping import DeclaredProximityBinding
from shared.runtime_spool import _PROXIMITY_NAME, _validate_metadata


@dataclass(frozen=True)
class CompletedProximityImportResult:
    """Local completion observation and independent transaction-scoped import."""

    manifest_status: Literal[
        'missing_manifest', 'missing_content', 'content_conflict', 'receipt_conflict', 'match',
    ]
    import_result: proximity_import.ProximityImportResult | None = None


async def import_admitted_proximity_file(
    directory: Path, *, source_id: str, generation: str, adapter, gametimes_dir: Path,
    allow_declared_mapping: bool = False,
) -> CompletedProximityImportResult | None:
    """Recover persisted admission identity, then attempt the existing strict path.

    None means the admission entry is absent, not completed or acknowledged.
    Never reconstruct expected hashes/dates from payload or completion manifest.
    Caller supplies configured source/generation and owns stable immutable spool,
    scheduling, adapter and final commit; all existing import limits still apply.
    No admission, source or completion is changed or deleted on any outcome.
    """
    if type(allow_declared_mapping) is not bool:
        raise ValueError('Explicit declared mapping policy required')
    admission = read_proximity_admission(directory, source_id=source_id, generation=generation)
    if admission is None:
        return None
    options = {}
    if allow_declared_mapping:
        # Select declared verification only after a matching sealed completion.
        # The opt-in permits new declarations; it does not upgrade legacy bytes
        # to declared provenance or bypass their existing strict parent gate.
        completion = inspect_proximity_completion_manifest(directory, admission.filename)
        if (completion.status == 'match' and completion.size == admission.size
                and completion.sha256 == admission.sha256):
            payload = read_verified_proximity_source(directory / admission.filename,
                expected_size=admission.size, expected_sha256=admission.sha256)
            identity = proximity_header_identity(
                StringIO(payload.decode('utf-8', errors='replace')), admission.filename)
            if identity is not None:
                options['declared_binding'] = DeclaredProximityBinding(
                    admission.source_id, admission.generation, admission.filename, admission.size,
                    admission.sha256, admission.session_date)
    return await import_completed_proximity_file(
        directory, admission.filename, adapter=adapter, session_date=admission.session_date,
        gametimes_dir=gametimes_dir, expected_size=admission.size, expected_sha256=admission.sha256,
        **options,
    )


async def import_completed_proximity_file(
    directory: Path, filename: str, *, adapter, session_date: date, gametimes_dir: Path,
    expected_size: int, expected_sha256: str, max_bytes: int = 8 * 1024 * 1024,
    declared_binding: DeclaredProximityBinding | None = None,
) -> CompletedProximityImportResult:
    """Require a matching completion receipt before a strict-parent import.

    Caller supplies authenticated source metadata independently of the local
    manifest, explicit resolved date, stable private spool and owned adapter.
    A self-consistent receipt for another size/hash cannot authorize this input.
    Missing/conflicting completion never enters the database; invalid metadata,
    malformed/unsafe entries, I/O/DB errors and cancellation propagate.

    A match alone is not imported. Canonical import ALWAYS requires an exact
    linked parent and strict receipt provenance (migrations 094/096). Missing parent
    or session stays pending, with source/manifest retained for caller retry;
    ambiguous identity needs reconciliation. No date guessing or legacy adoption.
    The canonical boundary revalidates source bytes before parsing. Caller must
    keep entries immutable across both reads; no same-UID writer lock is claimed.

    Synchronous local reads are bounded by the 8 MiB manifest protocol; canonical
    import also enforces max_bytes. No wall-clock bound, connection management,
    retry scheduling, file mutation, source acknowledgement or service startup.
    Success is transaction-scoped: caller must commit any enclosing transaction
    before treating the import as durable. Exclusive forward handover from legacy
    writers remains a prerequisite; this wrapper does not acquire that lease.
    """
    if type(session_date) is not date:
        raise TypeError('session_date must be an explicitly resolved datetime.date')
    if not callable(getattr(adapter, 'transaction', None)):
        raise TypeError('Proximity runtime import requires a transaction-capable adapter')
    if not isinstance(filename, str) or len(filename) > 240:
        raise ValueError('Manifest filename must be a bounded string')
    if expected_sha256 is None:
        raise ValueError('Completed proximity import requires SHA-256')
    _validate_metadata(filename, expected_size, max_bytes, expected_sha256,
                       name_pattern=_PROXIMITY_NAME)
    observed = inspect_proximity_completion_manifest(directory, filename)
    if observed.status == 'missing_manifest':
        return CompletedProximityImportResult(observed.status)
    if observed.size != expected_size or observed.sha256 != expected_sha256:
        return CompletedProximityImportResult('receipt_conflict')
    if observed.status != 'match':
        return CompletedProximityImportResult(observed.status)
    options = {}
    if declared_binding is not None:
        if (not isinstance(declared_binding, DeclaredProximityBinding)
                or (declared_binding.filename, declared_binding.size, declared_binding.sha256,
                    declared_binding.session_date, declared_binding.generation) !=
                   (filename, expected_size, expected_sha256, session_date, directory.name)):
            raise ValueError('Completed proximity expectation conflicts with declared binding')
        options['declared_binding'] = declared_binding
    result = await proximity_import.import_proximity_file(
        directory / filename, adapter=adapter, session_date=session_date,
        gametimes_dir=gametimes_dir, expected_size=expected_size,
        expected_sha256=expected_sha256, max_bytes=max_bytes, require_linked_parent=True,
        **options,
    )
    return CompletedProximityImportResult('match', result)
