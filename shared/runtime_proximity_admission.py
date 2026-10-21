"""Immutable local admission identity retained before capture, without a DB."""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from shared.runtime_completion_manifest import _receipt_fields
from shared.runtime_manifest_reader import _decode_manifest, _read_private_manifest_bytes
from shared.runtime_spool import _PROXIMITY_NAME, _publish_file

_ENTRY = '.proximity-admission.json'


@dataclass(frozen=True)
class ProximityAdmission:
    """Previously authenticated input identity, not capture/import completion."""

    source_id: str
    generation: str
    filename: str
    size: int
    sha256: str
    session_date: date

    def completion(self) -> dict:
        """Reconstruct the unchanged producer v1 receipt, scoped by generation."""
        return dict(version=1, filename=self.filename, bytes=self.size, state='writer_closed')


def _scope(directory, source_id, generation):
    if (not isinstance(directory, Path) or not directory.is_absolute()
            or not isinstance(generation, str)
            or re.fullmatch(r'[0-9a-f]{32}', generation, re.ASCII) is None
            or directory.name != generation):
        raise ValueError('Admission requires its absolute generation directory')
    if (not isinstance(source_id, str)
            or re.fullmatch(r'[a-z0-9][a-z0-9_.-]{0,63}', source_id, re.ASCII) is None):
        raise ValueError('Admission requires a bounded configured source ID')


def _validate(directory, data, source_id, generation):
    if (type(data) is not dict or set(data) != {
        'version', 'input_kind', 'source_id', 'generation', 'session_date', 'completion', 'sha256',
    } or type(data['version']) is not int or data['version'] != 1
            or data['input_kind'] != 'proximity'
            or data['source_id'] != source_id or data['generation'] != generation):
        raise ValueError('Invalid admission schema or source/generation identity')
    day = data['session_date']
    if not isinstance(day, str):
        raise ValueError('Admission requires an explicit ISO session date')
    try:
        parsed_day = date.fromisoformat(day)
    except ValueError as exc:
        raise ValueError('Admission requires an explicit ISO session date') from exc
    if parsed_day.isoformat() != day:
        raise ValueError('Admission requires an explicit ISO session date')
    filename, size = _receipt_fields(directory, data['completion'], data['sha256'], _PROXIMITY_NAME)
    return ProximityAdmission(source_id, generation, filename, size, data['sha256'], parsed_day)


def publish_proximity_admission(
    directory: Path, *, source_id: str, generation: str, completion: dict,
    expected_sha256: str, session_date: date,
) -> Path:
    """Persist one authenticated dispatch identity before capture/DB work.

    Caller authenticates completion and source hash, resolves the session date,
    reserves a unique generation directory and keeps this private spool stable.
    No remote trust is inferred from JSON. One source/input per generation;
    every existing entry (even identical) refuses overwrite. Same no-clobber,
    file-then-directory fsync publication as captured files. Post-link errors
    may leave visible content; reading that content does not recover durability.

    No source bytes are needed yet: this record survives an unavailable capture
    or DB and carries independent expected identity into later retries. It is
    NOT proof of captured data, an import ack, lease, scheduling state or source
    deletion permission. No directories/connections/services are created here.
    Bounded bytes, not a filesystem latency bound; same-UID mutation is outside
    the caller-owned immutable-spool contract.
    """
    _scope(directory, source_id, generation)
    if type(session_date) is not date:
        raise TypeError('session_date must be an explicitly resolved datetime.date')
    data = dict(version=1, input_kind='proximity', source_id=source_id, generation=generation,
                session_date=session_date.isoformat(), completion=completion, sha256=expected_sha256)
    _validate(directory, data, source_id, generation)
    payload = (json.dumps(data, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii')
    if len(payload) > 4096:
        raise ValueError('Admission exceeds manifest byte bound')
    return _publish_file(directory, _ENTRY, [payload], len(payload), hashlib.sha256(payload).hexdigest())


def read_proximity_admission(
    directory: Path, *, source_id: str, generation: str,
) -> ProximityAdmission | None:
    """Recover expected identity without consulting payload bytes or a database.

    Compare against caller-configured source and selected generation, never
    silently adopt another origin. None means ONLY the admission entry is absent;
    infrastructure/unsafe/malformed/changed entries raise. Reading is non-mutating
    and does not acknowledge a producer, captured content or committed import.
    """
    _scope(directory, source_id, generation)
    payload = _read_private_manifest_bytes(directory, _ENTRY)
    if payload is None:
        return None
    return _validate(directory, _decode_manifest(payload), source_id, generation)
