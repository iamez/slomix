"""Actual filesystem recovery proofs, including corruption and entry replacement."""

import hashlib
import json
import os
import stat

import pytest

from shared.runtime_completion_manifest import publish_completion_manifest
from shared.runtime_manifest_reader import inspect_completion_manifest
from shared.runtime_spool import publish_stats_file

NAME = '2026-09-20-120000-oasis-round-1.txt'
HASH = hashlib.sha256(b'abc').hexdigest()
RECEIPT = {'version': 1, 'filename': NAME, 'bytes': 3, 'state': 'writer_closed'}


@pytest.fixture
def ready(tmp_path):
    """Prepare a real immutable capture and durable receipt."""
    tmp_path.chmod(0o700)
    publish_stats_file(tmp_path, NAME, [b'abc'], expected_size=3, expected_sha256=HASH)
    publish_completion_manifest(tmp_path, RECEIPT, expected_sha256=HASH)
    return tmp_path


def test_recovery_matches_without_writes(ready):
    """Read a committed manifest twice, with unchanged content and identity."""
    before = {p.name: (p.stat().st_ino, p.read_bytes()) for p in ready.iterdir()}
    first = inspect_completion_manifest(ready, NAME)
    assert first.status == 'match' and first.size == 3 and first.sha256 == HASH
    assert inspect_completion_manifest(ready, NAME) == first
    assert {p.name: (p.stat().st_ino, p.read_bytes()) for p in ready.iterdir()} == before
    print('Recovery proof: persisted receipt matches actual bytes; repeated read changes nothing')


@pytest.mark.parametrize('target,status', [('manifest', 'missing_manifest'), ('payload', 'missing_content')])
def test_missing_states_are_distinct(ready, target, status):
    """Simulate lost entries independently; absence is not malformed data."""
    (ready / (NAME + '.complete.json' if target == 'manifest' else NAME)).unlink()
    assert inspect_completion_manifest(ready, NAME).status == status


def test_content_conflict_is_not_match(ready):
    """Corrupt equal-size synthetic data; preserve the manifest and conflicting bytes."""
    (ready / NAME).write_bytes(b'xyz')
    assert inspect_completion_manifest(ready, NAME).status == 'content_conflict'
    assert (ready / NAME).read_bytes() == b'xyz'


@pytest.mark.parametrize('payload', [
    b'{', b'[]', b'{}', b'\xff', b' ' * 4097,
    json.dumps({**RECEIPT, 'sha256': HASH, 'version': True}).encode(),
    json.dumps({**RECEIPT, 'sha256': HASH, 'bytes': True}).encode(),
    json.dumps({**RECEIPT, 'sha256': None}).encode(),
    json.dumps({**RECEIPT, 'sha256': HASH, 'filename': 'other.txt'}).encode(),
    (json.dumps({**RECEIPT, 'sha256': HASH})[:-1] + ',"version":1}').encode(),
])
def test_malformed_receipts_raise_not_absent(ready, payload):
    """Reject truncated, oversized, non-ASCII, ambiguous and mismatched schemas."""
    (ready / (NAME + '.complete.json')).write_bytes(payload)
    with pytest.raises(ValueError):
        inspect_completion_manifest(ready, NAME)


@pytest.mark.parametrize('kind', ['symlink', 'fifo', 'permissions'])
def test_unsafe_receipt_rejected(ready, kind):
    """No symlink following or FIFO blocking; only private regular entries."""
    path = ready / (NAME + '.complete.json')
    if kind == 'permissions':
        path.chmod(0o644)
    else:
        path.unlink()
        if kind == 'symlink':
            path.symlink_to(ready / NAME)
        else:
            os.mkfifo(path, 0o600)
    with pytest.raises((ValueError, OSError)):
        inspect_completion_manifest(ready, NAME)


def test_replaced_manifest_detected(ready, monkeypatch):
    """Change named identity while the original descriptor stays open."""
    original = os.read
    path = ready / (NAME + '.complete.json')
    replaced = False

    def read(fd, size):
        nonlocal replaced
        chunk = original(fd, size)
        if not replaced:
            replaced = True
            replacement = ready / 'replacement'
            replacement.write_bytes(path.read_bytes())
            replacement.chmod(0o600)
            replacement.replace(path)
        return chunk

    monkeypatch.setattr('shared.runtime_manifest_reader.os.read', read)
    with pytest.raises(RuntimeError, match='changed during inspection'):
        inspect_completion_manifest(ready, NAME)


def test_post_link_sync_failure_can_be_inspected(ready, monkeypatch):
    """Visible complete receipt after failed sync remains evidence, not a durability ack."""
    (ready / (NAME + '.complete.json')).unlink()
    original = os.fsync

    def sync(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError('fixture directory sync failure')
        original(fd)

    monkeypatch.setattr('shared.runtime_completion_manifest.os.fsync', sync)
    with pytest.raises(OSError, match='fixture directory sync failure'):
        publish_completion_manifest(ready, RECEIPT, expected_sha256=HASH)
    assert inspect_completion_manifest(ready, NAME).status == 'match'


def test_missing_directory_is_not_missing_manifest(tmp_path):
    """Infrastructure failure must not masquerade as an absent receipt."""
    with pytest.raises(FileNotFoundError):
        inspect_completion_manifest(tmp_path / 'absent', NAME)
