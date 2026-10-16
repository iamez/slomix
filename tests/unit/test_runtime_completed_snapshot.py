"""Actual receipt/generation/filesystem/seal integration, no DB or transport."""

import hashlib
import os

import pytest

from shared import runtime_completed_snapshot as completed
from shared.runtime_completion_manifest import record_completion_once
from shared.runtime_source_reservation import reserve_source_generation
from shared.runtime_spool import publish_stats_file

GENERATION = 'a' * 32
NAME = '2026-09-25-120000-supply-round-1.txt'
PAYLOAD = b'x\\supply\\x\\1\\2\\1\\20:00\\10:00\n'
HASH = hashlib.sha256(PAYLOAD).hexdigest()
RECEIPT = {'version': 1, 'filename': NAME, 'bytes': len(PAYLOAD), 'state': 'writer_closed'}


@pytest.fixture
def spool(tmp_path):
    """Publish real private content and its manifest in one reserved generation."""
    tmp_path.chmod(0o700)
    directory = reserve_source_generation(tmp_path, GENERATION)
    publish_stats_file(directory, NAME, [PAYLOAD], expected_size=len(PAYLOAD), expected_sha256=HASH)
    record_completion_once(directory, RECEIPT, expected_sha256=HASH)
    return tmp_path, directory


def test_receipt_to_sealed_reader_preserves_bytes_after_rewrite(spool):
    """No acknowledgement/deletion: only immutable processing bytes are delivered."""
    root, directory = spool
    before = set(os.listdir('/proc/self/fd'))
    with completed.open_completed_snapshot(root, GENERATION, NAME, expected_size=len(PAYLOAD),
                                           expected_sha256=HASH) as view:
        (directory / NAME).write_bytes(b'x' * len(PAYLOAD))
        data = view.read()
        assert data == PAYLOAD and hashlib.sha256(data).hexdigest() == HASH
    assert set(os.listdir('/proc/self/fd')) == before
    assert (directory / (NAME + '.complete.json')).exists()
    print('Completed input proof: trusted expectation -> generation receipt -> sealed bytes; source retained')


@pytest.mark.parametrize('generation,digest', [('b' * 32, HASH), (GENERATION, '0' * 64)])
def test_another_generation_or_expectation_never_delivers(spool, generation, digest):
    """A matching basename or locally self-consistent receipt is insufficient."""
    root, _ = spool
    if generation != GENERATION:
        reserve_source_generation(root, generation)
    before = set(os.listdir('/proc/self/fd'))
    with pytest.raises(ValueError), completed.open_completed_snapshot(
        root, generation, NAME, expected_size=len(PAYLOAD), expected_sha256=digest,
    ):
        pytest.fail('wrong receipt delivered')
    assert set(os.listdir('/proc/self/fd')) == before


def test_change_after_receipt_inspection_is_rehashed(spool, monkeypatch):
    """Close the gap between manifest inspection and the descriptor handed to sealing."""
    root, directory = spool
    inspect = completed.inspect_completion_manifest
    def changed(*args):
        result = inspect(*args)
        (directory / NAME).write_bytes(b'x' * len(PAYLOAD))
        return result
    monkeypatch.setattr(completed, 'inspect_completion_manifest', changed)
    before = set(os.listdir('/proc/self/fd'))
    with pytest.raises(ValueError, match='SHA-256 mismatch'), completed.open_completed_snapshot(
        root, GENERATION, NAME, expected_size=len(PAYLOAD), expected_sha256=HASH,
    ):
        pytest.fail('changed content delivered')
    assert set(os.listdir('/proc/self/fd')) == before


def test_correct_payload_without_receipt_is_not_completed(spool):
    """Bytes and hash alone cannot substitute for the completion record."""
    root, directory = spool
    receipt = directory / (NAME + '.complete.json')
    receipt.rename(directory / 'retained-receipt')
    with pytest.raises(ValueError, match='receipt/content'), completed.open_completed_snapshot(
        root, GENERATION, NAME, expected_size=len(PAYLOAD), expected_sha256=HASH,
    ):
        pytest.fail('missing receipt delivered')


def test_generation_symlink_is_not_followed(spool):
    """Another generation token may not alias a valid generation through symlinks."""
    root, directory = spool
    (root / ('b' * 32)).symlink_to(directory, target_is_directory=True)
    with pytest.raises(OSError), completed.open_completed_snapshot(
        root, 'b' * 32, NAME, expected_size=len(PAYLOAD), expected_sha256=HASH,
    ):
        pytest.fail('symlink generation delivered')


def test_owner_readonly_capture_is_consistent_with_manifest_reader(spool):
    root, directory = spool
    (directory / NAME).chmod(0o400)
    (directory / (NAME + '.complete.json')).chmod(0o400)
    assert completed.inspect_completion_manifest(directory, NAME).status == 'match'
    with completed.open_completed_snapshot(root, GENERATION, NAME, expected_size=len(PAYLOAD),
                                           expected_sha256=HASH) as view:
        assert view.read() == PAYLOAD
    assert (directory / NAME).stat().st_mode & 0o777 == 0o400
