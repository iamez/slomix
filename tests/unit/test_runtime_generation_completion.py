"""Offline composition proof; no claim of authenticated delivery or sealed bytes."""

import hashlib
import json
import subprocess

import pytest

from shared.runtime_completion_manifest import record_completion_once
from shared.runtime_manifest_reader import inspect_completion_manifest
from shared.runtime_source_reservation import claim_source_generation, reserve_source_generation
from shared.runtime_spool import publish_stats_file

NAME = '2026-09-25-120000-oasis-round-1.txt'
GENERATION = 'a' * 32
PAYLOAD = b'offline synthetic stats\n'
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()
RECEIPT = {'version': 1, 'filename': NAME, 'bytes': len(PAYLOAD), 'state': 'writer_closed'}


@pytest.fixture
def captured(tmp_path):
    """Model trusted dispatcher and capture, using real private filesystem writes."""
    tmp_path.chmod(0o700)
    directory = reserve_source_generation(tmp_path, GENERATION)
    assert claim_source_generation(tmp_path, GENERATION) == directory
    publish_stats_file(directory, NAME, [PAYLOAD], expected_size=len(PAYLOAD),
                       expected_sha256=DIGEST)
    return tmp_path, directory


def test_generation_completion_retry_preserves_identity(captured):
    """Receipt retry observes existing content without replaying producer dispatch."""
    root, directory = captured
    assert record_completion_once(directory, RECEIPT, expected_sha256=DIGEST) == 'published'
    manifest = directory / (NAME + '.complete.json')
    before = manifest.stat().st_ino, manifest.read_bytes()
    assert record_completion_once(directory, RECEIPT, expected_sha256=DIGEST) == 'content_present'
    assert (manifest.stat().st_ino, manifest.read_bytes()) == before
    assert inspect_completion_manifest(directory, NAME).status == 'match'
    assert json.loads(before[1])['bytes'] == (directory / NAME).stat().st_size == len(PAYLOAD)
    assert subprocess.check_output(['sha256sum', str(directory / NAME)], text=True).split()[0] == DIGEST
    with pytest.raises(FileExistsError):
        claim_source_generation(root, GENERATION)
    print('Generation completion: private claim + content + receipt; retry preserves inode and bytes')


def test_receipt_cannot_find_content_in_another_generation(captured):
    """Identical basenames do not let one directory supply another's missing bytes."""
    root, directory = captured
    other = reserve_source_generation(root, 'b' * 32)
    claim_source_generation(root, 'b' * 32)
    assert record_completion_once(other, RECEIPT, expected_sha256=DIGEST) == 'missing_content'
    assert not (other / (NAME + '.complete.json')).exists()
    assert record_completion_once(directory, RECEIPT, expected_sha256=DIGEST) == 'published'


def test_completed_receipt_does_not_hide_later_owner_rewrite(captured):
    """Manifest detects later mutation; permissions do not make owner writes immutable."""
    _, directory = captured
    record_completion_once(directory, RECEIPT, expected_sha256=DIGEST)
    manifest = directory / (NAME + '.complete.json')
    before = manifest.read_bytes()
    (directory / NAME).write_bytes(b'x' * len(PAYLOAD))
    assert record_completion_once(directory, RECEIPT, expected_sha256=DIGEST) == 'content_conflict'
    assert manifest.read_bytes() == before


def test_round_end_is_not_writer_completion(captured):
    """A round-ended event cannot create a manifest even if bytes already exist."""
    _, directory = captured
    with pytest.raises(ValueError, match='writer_closed'):
        record_completion_once(directory, {**RECEIPT, 'state': 'round_ended'}, expected_sha256=DIGEST)
    assert not (directory / (NAME + '.complete.json')).exists()
