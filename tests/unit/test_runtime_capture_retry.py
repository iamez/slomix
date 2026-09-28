"""Real filesystem retry proofs, including ambiguous post-publication failure."""

import os

import pytest

from shared.runtime_capture_retry import capture_once
from shared.runtime_spool import publish_stats_file

NAME = '2026-09-20-120000-map-round-1.txt'
DIGEST = 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'


def attempt(directory, chunks):
    """Drive a single attempt with a fixed externally known source identity."""
    return capture_once(directory, NAME, chunks, expected_size=3, expected_sha256=DIGEST)


def untouched_source():
    """A reconciled entry must not cause another source read."""
    raise AssertionError('Source must not be consumed')
    yield b''


def test_published_then_content_present_without_read(tmp_path):
    """Retry is content reconciliation, not a second publication or import ack."""
    assert attempt(tmp_path, [b'a', b'bc']) == 'published'
    path = tmp_path / NAME
    before = path.stat()
    assert attempt(tmp_path, untouched_source()) == 'content_present'
    assert path.read_bytes() == b'abc'
    assert path.stat().st_size == 3
    assert path.stat().st_ino == before.st_ino
    print('Retry proof: published -> content_present, no source read and unchanged inode')


def test_conflict_preserves_file_without_read(tmp_path):
    """Conflicting content is retained for explicit resolution."""
    assert attempt(tmp_path, [b'abc']) == 'published'
    path = tmp_path / NAME
    path.write_bytes(b'xyz')
    assert attempt(tmp_path, untouched_source()) == 'conflict'
    assert path.read_bytes() == b'xyz'


def test_transfer_failure_then_retry(tmp_path):
    """A partial source failure cleans its temp and remains retryable by caller."""
    def broken():
        yield b'a'
        raise ConnectionError('fixture disconnect')
    with pytest.raises(ConnectionError, match='disconnect'):
        attempt(tmp_path, broken())
    assert list(tmp_path.iterdir()) == []
    assert attempt(tmp_path, [b'abc']) == 'published'


def test_ambiguous_sync_failure_then_content_inspection(tmp_path, monkeypatch):
    """Never mask a failed sync as success; later retry only certifies content."""
    original = os.fsync
    count = 0
    def sync(fd):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError('fixture directory sync failure')
        original(fd)
    monkeypatch.setattr(os, 'fsync', sync)
    with pytest.raises(OSError, match='directory sync'):
        attempt(tmp_path, [b'abc'])
    assert attempt(tmp_path, untouched_source()) == 'content_present'
    assert len(list(tmp_path.iterdir())) == 1


def test_racing_publisher_survives_loser_then_retry(tmp_path):
    """Another writer may win between inspect and link; no automatic overwrite."""
    def racing_source():
        publish_stats_file(tmp_path, NAME, [b'abc'], expected_size=3, expected_sha256=DIGEST)
        yield b'abc'
    with pytest.raises(FileExistsError):
        attempt(tmp_path, racing_source())
    assert attempt(tmp_path, untouched_source()) == 'content_present'
    assert (tmp_path / NAME).read_bytes() == b'abc'
    assert len(list(tmp_path.iterdir())) == 1


def test_source_file_exists_error_is_not_success(tmp_path):
    """An identically typed transport exception cannot masquerade as a race."""
    def broken():
        raise FileExistsError('fixture source exception')
        yield b''
    with pytest.raises(FileExistsError, match='source exception'):
        attempt(tmp_path, broken())
    assert list(tmp_path.iterdir()) == []
