"""Persist trusted writer-close receipts against verified immutable local bytes."""

import json
import os
import stat
import uuid
from pathlib import Path
from typing import Literal

from shared.runtime_manifest_reader import inspect_completion_manifest
from shared.runtime_spool import _validate_metadata, inspect_published_stats_file


def _receipt_fields(directory, completion, expected_sha256):
    """Validate the same caller contract before either publication or retry."""
    if not isinstance(directory, Path) or not directory.is_absolute():
        raise ValueError('Manifest spool must be an absolute Path')
    if (type(completion) is not dict
            or set(completion) != {'version', 'filename', 'bytes', 'state'}
            or type(completion['version']) is not int or completion['version'] != 1
            or completion['state'] != 'writer_closed'):
        raise ValueError('Expected a version 1 writer_closed receipt')
    filename, size = completion['filename'], completion['bytes']
    # 240 ASCII bytes plus the 14-byte suffix fits the Linux 255-byte entry.
    if not isinstance(filename, str) or len(filename) > 240:
        raise ValueError('Manifest filename must be a bounded string')
    if expected_sha256 is None:
        raise ValueError('Completion requires SHA-256')
    _validate_metadata(filename, size, 8 * 1024 * 1024, expected_sha256)
    return filename, size


def publish_completion_manifest(
    directory: Path, completion: dict, *, expected_sha256: str,
) -> Path:
    """Publish a bounded JSON receipt without replacing existing entries.

    Caller authenticates the producer receipt, reserves a fresh immutable source
    identity and keeps this private spool unchanged through publication/use.
    Validating writer_closed text does NOT establish producer trust. Receipt size
    and supplied digest must match local bytes before recording them. This fsyncs
    the manifest and directory, not the payload (whose durability is a separate
    capture contract). No snapshot reservation, producer wiring, source deletion
    or import ack. Local inspection is byte-bounded, not time-bounded.

    An error after link can leave a complete manifest: reconcile, never overwrite.
    Existing manifests, including identical ones, raise FileExistsError.
    """
    filename, size = _receipt_fields(directory, completion, expected_sha256)
    content = inspect_published_stats_file(
        directory, filename, expected_size=size, expected_sha256=expected_sha256,
    )
    if content != 'match':
        raise ValueError('Completion receipt does not match captured content')
    payload = (json.dumps({
        'version': 1, 'filename': filename, 'bytes': size,
        'state': 'writer_closed', 'sha256': expected_sha256,
    }, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii')
    name = filename + '.complete.json'
    directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = '.receipt-' + uuid.uuid4().hex + '.part'
    created = False
    try:
        info = os.fstat(directory_fd)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError('Manifest spool must be owned by this user with mode 0700')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=directory_fd)
        created = True
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd,
                follow_symlinks=False)
        os.fsync(directory_fd)
    finally:
        try:
            if created:
                os.unlink(temporary, dir_fd=directory_fd)
        finally:
            os.close(directory_fd)
    return directory / name


def record_completion_once(
    directory: Path, completion: dict, *, expected_sha256: str,
) -> Literal['published', 'content_present', 'missing_content', 'content_conflict', 'receipt_conflict']:
    """One caller-driven retry, never overwrite or silently accept another receipt.

    Existing receipt must match THIS supplied size/hash as well as local bytes.
    content_present is observation only, not recovered fsync durability/import ack.
    Missing receipt is published only against verified content. Publication races,
    malformed manifests and I/O errors propagate; caller can inspect on a later
    attempt. No loop, source ack/delete or durability upgrade. Caller owns trusted
    immutable receipt/spool. New publication verifies payload twice (at most16MiB
    reads), existing receipt once; local filesystem waits are not time-bounded.
    """
    filename, size = _receipt_fields(directory, completion, expected_sha256)
    observed = inspect_completion_manifest(directory, filename)
    if observed.status != 'missing_manifest':
        if observed.size != size or observed.sha256 != expected_sha256:
            return 'receipt_conflict'
        return 'content_present' if observed.status == 'match' else observed.status
    content = inspect_published_stats_file(
        directory, filename, expected_size=size, expected_sha256=expected_sha256,
    )
    if content != 'match':
        return 'missing_content' if content == 'missing' else 'content_conflict'
    publish_completion_manifest(directory, completion, expected_sha256=expected_sha256)
    return 'published'
