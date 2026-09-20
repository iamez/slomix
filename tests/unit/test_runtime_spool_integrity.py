"""Real filesystem proofs for source-digest validation before publication."""

import subprocess

import pytest

from shared.runtime_spool import publish_stats_file

NAME = '2026-09-20-120000-map-round-1.txt'
# Standard SHA-256 known-answer vector for b'abc', not derived by the publisher.
ABC_SHA256 = 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'


def test_verified_stream_publishes_exact_content(tmp_path):
    """Chunk boundaries and empty chunks do not alter the verified content."""
    def chunks():
        for chunk in [b'a', b'', b'bc']:
            assert not (tmp_path / NAME).exists()
            yield chunk
    path = publish_stats_file(tmp_path, NAME, chunks(), expected_size=3,
                              expected_sha256=ABC_SHA256)
    assert path.read_bytes() == b'abc'
    assert path.stat().st_size == 3
    actual = subprocess.run(['sha256sum', str(path)], check=True, capture_output=True,
                            text=True, timeout=5).stdout.split()[0]
    assert actual == ABC_SHA256
    assert list(tmp_path.iterdir()) == [path]
    print('Integrity proof: exact abc bytes, stat size 3, independent sha256sum matches')


def test_equal_length_corruption_never_publishes(tmp_path):
    """Size alone passes but a changed byte must leave no import candidate."""
    with pytest.raises(ValueError, match='SHA-256 mismatch'):
        publish_stats_file(tmp_path, NAME, [b'abd'], expected_size=3,
                           expected_sha256=ABC_SHA256)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('digest', ['', 'a' * 63, 'a' * 65, 'g' * 64,
                                    ABC_SHA256.upper(), ABC_SHA256 + '\n', 123, b'a' * 64])
def test_invalid_digest_does_not_consume_source(tmp_path, digest):
    """Malformed expected metadata fails before any filesystem or source work."""
    def chunks():
        raise AssertionError('Source must not be consumed')
        yield b''
    with pytest.raises(ValueError, match='Expected SHA-256'):
        publish_stats_file(tmp_path / 'absent', NAME, chunks(), expected_size=3,
                           expected_sha256=digest)
    assert list(tmp_path.iterdir()) == []


def test_verified_retry_cannot_overwrite_existing_file(tmp_path):
    """Even verified incoming bytes cannot replace an existing identity."""
    destination = tmp_path / NAME
    destination.write_bytes(b'old')
    with pytest.raises(FileExistsError):
        publish_stats_file(tmp_path, NAME, [b'abc'], expected_size=3,
                           expected_sha256=ABC_SHA256)
    assert destination.read_bytes() == b'old'
    assert list(tmp_path.iterdir()) == [destination]
