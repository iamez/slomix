"""Protocol separation and real socket-to-verified-proximity-source proofs."""

import hashlib
import os
import socket
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from shared.proximity_source import read_verified_proximity_source
from shared.runtime_capture import capture_proximity_stream, capture_stats_stream
from shared.runtime_spool import (
    inspect_published_proximity_file,
    inspect_published_stats_file,
)

STATS = '2026-10-05-120000-map-round-1.txt'
PROXIMITY = STATS.replace('.txt', '_engagements.txt')
PAYLOAD = b'fixture proximity transport bytes\n'
METADATA = {'expected_size': len(PAYLOAD), 'expected_sha256': hashlib.sha256(PAYLOAD).hexdigest()}


def reader():
    return SimpleNamespace(read=Mock(side_effect=[PAYLOAD, b'']), settimeout=Mock())


@pytest.mark.parametrize('capture,inspect,name', [
    (capture_stats_stream, inspect_published_stats_file, PROXIMITY),
    (capture_proximity_stream, inspect_published_proximity_file, STATS),
])
def test_protocols_reject_each_others_filenames_before_io(tmp_path, capture, inspect, name):
    source = reader()
    with pytest.raises(ValueError, match='filename'):
        capture(source, tmp_path, name, **METADATA)
    with pytest.raises(ValueError, match='filename'):
        inspect(tmp_path, name, **METADATA)
    source.read.assert_not_called()
    source.settimeout.assert_not_called()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('directory', [Path('relative'), '/not/a/Path/object'])
def test_proximity_requires_absolute_path_before_io(directory):
    source = reader()
    with pytest.raises(ValueError, match='absolute Path'):
        capture_proximity_stream(source, directory, PROXIMITY, **METADATA)
    with pytest.raises(ValueError, match='absolute Path'):
        inspect_published_proximity_file(directory, PROXIMITY, **METADATA)
    source.read.assert_not_called()


@pytest.mark.parametrize('override', [
    {'expected_sha256': None}, {'expected_sha256': 'invalid'},
    {'expected_size': True}, {'expected_size': 0}, {'max_bytes': len(PAYLOAD) - 1},
])
def test_invalid_metadata_does_not_consume_or_publish(tmp_path, override):
    source = reader()
    with pytest.raises(ValueError):
        capture_proximity_stream(source, tmp_path, PROXIMITY, **(METADATA | override))
    with pytest.raises(ValueError):
        inspect_published_proximity_file(tmp_path, PROXIMITY, **(METADATA | override))
    source.read.assert_not_called()
    assert list(tmp_path.iterdir()) == []


def test_real_socket_to_same_verified_bytes_without_import_ack(tmp_path):
    """Two independent read paths verify capture; no DB or remote is involved."""
    assert inspect_published_proximity_file(tmp_path, PROXIMITY, **METADATA) == 'missing'
    receiver, sender = socket.socketpair()
    with receiver, sender:
        sender.sendall(PAYLOAD)
        sender.shutdown(socket.SHUT_WR)
        source = SimpleNamespace(read=receiver.recv, settimeout=receiver.settimeout)
        path = capture_proximity_stream(source, tmp_path, PROXIMITY, chunk_size=7, **METADATA)
        assert receiver.fileno() >= 0
    before = path.stat()
    assert inspect_published_proximity_file(tmp_path, PROXIMITY, **METADATA) == 'match'
    assert read_verified_proximity_source(path, **METADATA) == PAYLOAD
    assert hashlib.sha256(path.read_bytes()).hexdigest() == METADATA['expected_sha256']
    assert path.stat().st_size == len(PAYLOAD)
    assert path.stat().st_ino == before.st_ino
    assert list(tmp_path.iterdir()) == [path]
    print('Proximity capture proof: real socket -> private file -> independent verified bytes; '
          'matching content only, no import acknowledgement')


def test_no_clobber_and_digest_mismatch(tmp_path):
    path = capture_proximity_stream(reader(), tmp_path, PROXIMITY, **METADATA)
    before = path.stat()
    with pytest.raises(FileExistsError):
        capture_proximity_stream(reader(), tmp_path, PROXIMITY, **METADATA)
    assert path.read_bytes() == PAYLOAD and path.stat().st_ino == before.st_ino
    other_name = PROXIMITY.replace('round-1', 'round-2')
    with pytest.raises(ValueError, match='SHA-256 mismatch'):
        capture_proximity_stream(reader(), tmp_path, other_name,
                                 **(METADATA | {'expected_sha256': '0' * 64}))
    assert list(tmp_path.iterdir()) == [path]


def test_capture_post_link_error_is_only_content_observation(tmp_path, monkeypatch):
    real_sync = os.fsync
    sync_calls = 0

    def fail_directory_sync(fd):
        nonlocal sync_calls
        sync_calls += 1
        if sync_calls == 2:
            raise OSError('fixture proximity directory sync failed')
        real_sync(fd)

    monkeypatch.setattr(os, 'fsync', fail_directory_sync)
    with pytest.raises(OSError, match='directory sync failed'):
        capture_proximity_stream(reader(), tmp_path, PROXIMITY, **METADATA)
    assert inspect_published_proximity_file(tmp_path, PROXIMITY, **METADATA) == 'match'
    assert read_verified_proximity_source(tmp_path / PROXIMITY, **METADATA) == PAYLOAD
    assert len(list(tmp_path.iterdir())) == 1
    print('Proximity failure proof: directory fsync failed; content observed without upgrading '
          'the failed capture to durability or import success')
