"""Persist trusted writer-close receipts against verified immutable local bytes."""

import json
import os
import stat
import uuid
from pathlib import Path

from shared.runtime_spool import inspect_published_stats_file


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
    if not isinstance(directory, Path) or not directory.is_absolute():
        raise ValueError('Manifest spool must be an absolute Path')
    if (type(completion) is not dict
            or set(completion) != {'version', 'filename', 'bytes', 'state'}
            or type(completion['version']) is not int or completion['version'] != 1
            or completion['state'] != 'writer_closed'):
        raise ValueError('Expected a version 1 writer_closed receipt')
    filename, size = completion['filename'], completion['bytes']
    if not isinstance(filename, str) or len(filename) > 200:
        raise ValueError('Manifest filename must be a bounded string')
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
