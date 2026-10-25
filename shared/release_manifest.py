"""Git-free release integrity (not a signature or protection from its owner).

Release payloads contain no mutable state. Set PYTHONPYCACHEPREFIX outside the
release or PYTHONDONTWRITEBYTECODE=1; config/state/logs belong outside it too.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath

MANIFEST = '.slomix-release.json'


def file_hash(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def payload_files(root: Path) -> dict[str, Path]:
    """Inventory every payload file; never traverse links or special files."""
    files = {}
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('Release must not contain symlinks')
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError('Release must contain only regular files')
        relative = path.relative_to(root).as_posix()
        if relative != MANIFEST:
            files[relative] = path
    return files


def verify_release(root: Path) -> dict:
    """Validate complete file inventory and bytes before trusting release SHA."""
    root = Path(root)
    marker = root / MANIFEST
    if root.is_symlink() or marker.is_symlink() or not marker.is_file():
        raise ValueError('Missing or symlinked release manifest/root')
    if marker.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Oversized release manifest')
    record = json.loads(marker.read_text(encoding='utf-8'))
    if (not isinstance(record, dict) or record.get('version') != 1
            or not isinstance(record.get('source_commit'), str)
            or not re.fullmatch(r'[0-9a-f]{40}', record['source_commit'])):
        raise ValueError('Invalid release identity')
    files = record.get('files')
    if not isinstance(files, dict) or not files or len(files) > 10000:
        raise ValueError('Invalid release inventory')
    for name, digest in files.items():
        relative = PurePosixPath(name)
        if (relative.is_absolute() or '..' in relative.parts or str(relative) != name
                or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest)):
            raise ValueError('Invalid release file entry')
    actual = payload_files(root)
    if set(actual) != set(files):
        raise ValueError('Release file inventory differs from manifest')
    if any(file_hash(actual[name]) != digest for name, digest in files.items()):
        raise ValueError('Release payload checksum mismatch')
    return record
