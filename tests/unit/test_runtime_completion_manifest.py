"""Real filesystem manifest ordering, no-clobber and failure proofs."""

import hashlib
import json
import os
import stat
import subprocess

import pytest

from shared.runtime_completion_manifest import publish_completion_manifest
from shared.runtime_spool import publish_stats_file

NAME = '2026-09-20-120000-oasis-round-1.txt'
HASH = hashlib.sha256(b'abc').hexdigest()
RECEIPT = {'version': 1, 'filename': NAME, 'bytes': 3, 'state': 'writer_closed'}


@pytest.fixture
def spool(tmp_path):
    """Prepare known immutable synthetic content through the capture publisher."""
    tmp_path.chmod(0o700)
    publish_stats_file(tmp_path, NAME, [b'abc'], expected_size=3, expected_sha256=HASH)
    return tmp_path


def test_manifest_matches_bytes_and_sync_order(spool, monkeypatch):
    """Receipt is visible only after its file fsync, then directory is synced."""
    original = os.fsync
    seen = []
    final = spool / (NAME + '.complete.json')

    def sync(fd):
        seen.append('dir' if stat.S_ISDIR(os.fstat(fd).st_mode) else 'file')
        assert final.exists() == (seen[-1] == 'dir')
        original(fd)

    monkeypatch.setattr('shared.runtime_completion_manifest.os.fsync', sync)
    result = publish_completion_manifest(spool, RECEIPT, expected_sha256=HASH)
    assert result == final and seen == ['file', 'dir']
    data = json.loads(final.read_text())
    assert data == {**RECEIPT, 'sha256': HASH}
    assert data['bytes'] == (spool / NAME).stat().st_size == len((spool / NAME).read_bytes())
    assert data['sha256'] == subprocess.check_output(['sha256sum', str(spool / NAME)], text=True).split()[0]
    assert stat.S_IMODE(final.stat().st_mode) == 0o600
    assert not list(spool.glob('*.part'))
    print('Manifest proof: verified bytes, file fsync, no-clobber link, directory fsync')


@pytest.mark.parametrize('existing', ['identical', 'conflict', 'symlink'])
def test_existing_receipt_never_replaced(spool, existing):
    """Even a matching manifest is not permission to overwrite anything."""
    final = spool / (NAME + '.complete.json')
    if existing == 'identical':
        publish_completion_manifest(spool, RECEIPT, expected_sha256=HASH)
    elif existing == 'symlink':
        final.symlink_to(spool / NAME)
    else:
        final.write_bytes(b'conflicting receipt')
    before = final.lstat(), final.read_bytes()
    with pytest.raises(FileExistsError):
        publish_completion_manifest(spool, RECEIPT, expected_sha256=HASH)
    assert final.lstat().st_ino == before[0].st_ino
    assert final.read_bytes() == before[1]
    assert (spool / NAME).read_bytes() == b'abc'
    assert not list(spool.glob('*.part'))


@pytest.mark.parametrize('phase', ['file', 'dir'])
def test_sync_failure_preserves_only_complete_visible_receipt(spool, monkeypatch, phase):
    """Post-link error leaves a valid final; pre-link error leaves none."""
    def broken(fd):
        kind = 'dir' if stat.S_ISDIR(os.fstat(fd).st_mode) else 'file'
        if kind == phase:
            raise OSError('fixture sync failure')
    monkeypatch.setattr('shared.runtime_completion_manifest.os.fsync', broken)
    with pytest.raises(OSError, match='fixture sync failure'):
        publish_completion_manifest(spool, RECEIPT, expected_sha256=HASH)
    final = spool / (NAME + '.complete.json')
    assert final.exists() == (phase == 'dir')
    if final.exists():
        assert json.loads(final.read_text()) == {**RECEIPT, 'sha256': HASH}
    assert not list(spool.glob('*.part'))


@pytest.mark.parametrize('change', [
    {'version': True}, {'version': 2}, {'state': 'round_ended'},
    {'bytes': 4}, {'bytes': True}, {'filename': '../unsafe'}, {'extra': 'field'},
])
def test_invalid_receipt_never_published(spool, change):
    """Metadata and actual captured content must both satisfy the contract."""
    with pytest.raises(ValueError):
        publish_completion_manifest(spool, {**RECEIPT, **change}, expected_sha256=HASH)
    assert list(spool.iterdir()) == [spool / NAME]


def test_wrong_digest_never_published(spool):
    """A same-size snapshot is insufficient to bind a receipt."""
    with pytest.raises(ValueError, match='does not match'):
        publish_completion_manifest(spool, RECEIPT, expected_sha256='0' * 64)
    assert list(spool.iterdir()) == [spool / NAME]
