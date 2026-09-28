"""Real filesystem retry proofs: no overwrite, no implicit durability upgrade."""

import hashlib
import os
import stat

import pytest

from shared.runtime_completion_manifest import record_completion_once
from shared.runtime_spool import publish_stats_file

NAME = '2026-09-20-120000-oasis-round-1.txt'
HASH = hashlib.sha256(b'abc').hexdigest()
RECEIPT = {'version': 1, 'filename': NAME, 'bytes': 3, 'state': 'writer_closed'}


@pytest.fixture
def spool(tmp_path):
    """Create an immutable synthetic capture with no receipt yet."""
    tmp_path.chmod(0o700)
    publish_stats_file(tmp_path, NAME, [b'abc'], expected_size=3, expected_sha256=HASH)
    return tmp_path


def test_repeated_record_does_not_write(spool, monkeypatch):
    """The second attempt observes content without publishing or fsyncing again."""
    assert record_completion_once(spool, RECEIPT, expected_sha256=HASH) == 'published'
    before = {p.name: (p.stat().st_ino, p.read_bytes()) for p in spool.iterdir()}

    def forbidden(*args, **kwargs):
        raise AssertionError('Retry must not publish existing receipt')
    monkeypatch.setattr('shared.runtime_completion_manifest.publish_completion_manifest', forbidden)
    assert record_completion_once(spool, RECEIPT, expected_sha256=HASH) == 'content_present'
    assert {p.name: (p.stat().st_ino, p.read_bytes()) for p in spool.iterdir()} == before


@pytest.mark.parametrize('field,value', [('bytes', 4), ('sha256', '0' * 64)])
def test_existing_receipt_must_match_caller_identity(spool, field, value):
    """A self-consistent old receipt cannot satisfy a different requested snapshot."""
    record_completion_once(spool, RECEIPT, expected_sha256=HASH)
    supplied = {**RECEIPT, **({'bytes': value} if field == 'bytes' else {})}
    assert record_completion_once(spool, supplied, expected_sha256=value if field == 'sha256' else HASH) == 'receipt_conflict'


@pytest.mark.parametrize('existing_receipt', [False, True])
@pytest.mark.parametrize('state', ['missing', 'corrupt'])
def test_missing_or_wrong_payload_never_acknowledged(spool, existing_receipt, state):
    """Payload failure remains distinct with and without a saved receipt."""
    if existing_receipt:
        record_completion_once(spool, RECEIPT, expected_sha256=HASH)
    if state == 'missing':
        (spool / NAME).unlink()
    else:
        (spool / NAME).write_bytes(b'xyz')
    assert record_completion_once(spool, RECEIPT, expected_sha256=HASH) == (
        'missing_content' if state == 'missing' else 'content_conflict')
    assert (spool / (NAME + '.complete.json')).exists() == existing_receipt


@pytest.mark.parametrize('phase', ['file', 'dir'])
def test_retry_after_sync_failure(spool, monkeypatch, phase):
    """Before-link retry publishes; after-link retry observes only, retaining bytes."""
    original = os.fsync
    def sync(fd):
        kind = 'dir' if stat.S_ISDIR(os.fstat(fd).st_mode) else 'file'
        if kind == phase:
            raise OSError('fixture sync failure')
        original(fd)
    with monkeypatch.context() as patch:
        patch.setattr('shared.runtime_completion_manifest.os.fsync', sync)
        with pytest.raises(OSError, match='fixture sync failure'):
            record_completion_once(spool, RECEIPT, expected_sha256=HASH)
    result = record_completion_once(spool, RECEIPT, expected_sha256=HASH)
    assert result == ('published' if phase == 'file' else 'content_present')
    assert (spool / NAME).read_bytes() == b'abc'
    assert not list(spool.glob('*.part'))
    print(f'Manifest retry proof: failed {phase} sync -> {result}')


def test_invalid_caller_not_hidden_by_valid_receipt(spool):
    """Validate new input even when previously saved content matches."""
    record_completion_once(spool, RECEIPT, expected_sha256=HASH)
    with pytest.raises(ValueError):
        record_completion_once(spool, {**RECEIPT, 'version': True}, expected_sha256=HASH)
