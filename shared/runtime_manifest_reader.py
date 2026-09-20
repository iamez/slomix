"""Bounded read-only recovery of completion manifests; never a source/import ack."""

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from shared.runtime_spool import _validate_metadata, inspect_published_stats_file


@dataclass(frozen=True)
class ManifestInspection:
    """Observed manifest/content state, not provenance or crash durability."""

    status: Literal['missing_manifest', 'missing_content', 'content_conflict', 'match']
    filename: str
    size: int | None = None
    sha256: str | None = None


def _unique_object(pairs):
    """Reject ambiguous duplicate JSON keys instead of taking the last value."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate manifest field')
        result[key] = value
    return result


def inspect_completion_manifest(directory: Path, filename: str) -> ManifestInspection:
    """Read one private immutable manifest and verify the referenced local bytes.

    Only a missing manifest entry means missing_manifest. Unsafe/malformed input
    raises ValueError (symlink open may raise OSError); operational errors and
    concurrent entry changes propagate. Never repair/delete/overwrite a receipt.
    Reads at most 4097 manifest bytes plus the bounded snapshot (8 MiB maximum).
    No wall-clock bound. Caller keeps directory/files immutable through use;
    stat comparisons detect observed drift, not future changes or source trust.
    Neither a match nor recovery after sync failure authorizes source deletion.
    """
    if not isinstance(directory, Path) or not directory.is_absolute():
        raise ValueError('Manifest spool must be an absolute Path')
    if not isinstance(filename, str) or len(filename) > 240:
        raise ValueError('Manifest filename must be a bounded string')
    _validate_metadata(filename, 1, 8 * 1024 * 1024, None)
    name = filename + '.complete.json'
    directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        owner = os.fstat(directory_fd)
        if owner.st_uid != os.getuid() or stat.S_IMODE(owner.st_mode) != 0o700:
            raise ValueError('Manifest spool must be owned by this user with mode 0700')
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
        except FileNotFoundError:
            return ManifestInspection('missing_manifest', filename)
        try:
            before = os.fstat(fd)
            if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid()
                    or stat.S_IMODE(before.st_mode) != 0o600 or not 0 < before.st_size <= 4096):
                raise ValueError('Manifest must be an owned mode 0600 regular file of 1..4096 bytes')
            payload = bytearray()
            while len(payload) <= 4096:
                chunk = os.read(fd, 4097 - len(payload))
                if not chunk:
                    break
                payload.extend(chunk)
            after = os.fstat(fd)
            named = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            for current in (after, named):
                if any(getattr(before, field) != getattr(current, field) for field in (
                    'st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode', 'st_uid',
                )):
                    raise RuntimeError('Manifest changed during inspection')
            if len(payload) != before.st_size:
                raise ValueError('Manifest read length mismatch')
        finally:
            os.close(fd)
    finally:
        os.close(directory_fd)
    try:
        data = json.loads(payload.decode('ascii'), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('Malformed completion manifest') from exc
    if (type(data) is not dict
            or set(data) != {'version', 'filename', 'bytes', 'state', 'sha256'}
            or type(data['version']) is not int or data['version'] != 1
            or data['filename'] != filename or data['state'] != 'writer_closed'):
        raise ValueError('Invalid completion manifest schema or identity')
    if data['sha256'] is None:
        raise ValueError('Manifest requires SHA-256')
    _validate_metadata(filename, data['bytes'], 8 * 1024 * 1024, data['sha256'])
    content = inspect_published_stats_file(
        directory, filename, expected_size=data['bytes'], expected_sha256=data['sha256'],
    )
    status = {'missing': 'missing_content', 'conflict': 'content_conflict', 'match': 'match'}[content]
    return ManifestInspection(status, filename, data['bytes'], data['sha256'])
