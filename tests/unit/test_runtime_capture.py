"""Real local socket and filesystem proofs for bounded stream publication."""

import os
import socket
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from shared import runtime_capture
from shared.runtime_capture import capture_stats_stream

NAME = '2026-09-20-120000-map-round-1.txt'
DIGEST = 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'


def capture(source, directory, **kwargs):
    """Exercise the same immutable abc snapshot in each transport scenario."""
    return capture_stats_stream(source, directory, NAME, expected_size=3,
                                expected_sha256=DIGEST, **kwargs)


def test_real_socket_capture(tmp_path):
    """A real EOF-terminated stream becomes exactly one verified file."""
    receiver, sender = socket.socketpair()
    with receiver, sender:
        sender.sendall(b'abc')
        sender.shutdown(socket.SHUT_WR)
        reader = SimpleNamespace(read=receiver.recv, settimeout=receiver.settimeout)
        path = capture(reader, tmp_path, chunk_size=1)
        assert path.read_bytes() == b'abc'
        assert path.stat().st_size == 3
        assert list(tmp_path.iterdir()) == [path]
        assert receiver.fileno() >= 0  # Ownership remains with caller.
        print('Capture proof: local socket -> verified 3-byte final file; caller retains socket')


def test_real_socket_without_eof_times_out_and_cleans(tmp_path):
    """Even all expected bytes are not published until snapshot EOF arrives."""
    receiver, sender = socket.socketpair()
    with receiver, sender:
        sender.sendall(b'abc')
        reader = SimpleNamespace(read=receiver.recv, settimeout=receiver.settimeout)
        with pytest.raises(TimeoutError):
            capture(reader, tmp_path, read_timeout=0.02, total_timeout=1)
        assert list(tmp_path.iterdir()) == []
        assert receiver.fileno() >= 0


def test_deadline_rejects_late_eof(tmp_path, monkeypatch):
    """Even a completed valid payload cannot sneak past the overall deadline."""
    clock = iter([0.0, 0.0, 0.1, 0.1, 2.0])
    monkeypatch.setattr(runtime_capture.time, 'monotonic', lambda: next(clock))
    reader = SimpleNamespace(read=Mock(side_effect=[b'abc', b'']), settimeout=Mock())
    with pytest.raises(TimeoutError, match='deadline'):
        capture(reader, tmp_path, total_timeout=1, read_timeout=5)
    assert [call.args[0] for call in reader.settimeout.call_args_list] == [1.0, 0.9]
    assert list(tmp_path.iterdir()) == []


def test_expired_deadline_does_not_read(tmp_path, monkeypatch):
    """No new read starts after the capture budget is exhausted."""
    clock = iter([0.0, 2.0])
    monkeypatch.setattr(runtime_capture.time, 'monotonic', lambda: next(clock))
    reader = SimpleNamespace(read=Mock(), settimeout=Mock())
    with pytest.raises(TimeoutError, match='deadline'):
        capture(reader, tmp_path, total_timeout=1)
    reader.read.assert_not_called()
    assert list(tmp_path.iterdir()) == []


def test_slow_spool_setup_does_not_consume_read_budget(tmp_path, monkeypatch):
    """Advance the clock during real file opens, before any stream consumption."""
    clock = [0.0]
    original_open = os.open
    def slow_open(*args, **kwargs):
        fd = original_open(*args, **kwargs)
        clock[0] = 10.0
        return fd
    monkeypatch.setattr(os, 'open', slow_open)
    monkeypatch.setattr(runtime_capture.time, 'monotonic', lambda: clock[0])
    reader = SimpleNamespace(read=Mock(side_effect=[b'abc', b'']), settimeout=Mock())
    path = capture(reader, tmp_path, total_timeout=1)
    assert path.read_bytes() == b'abc'
    assert path.stat().st_size == 3
    assert [call.args[0] for call in reader.settimeout.call_args_list] == [1.0, 1.0]


def test_capture_requires_source_digest(tmp_path):
    """Capture cannot silently downgrade to size-only publication."""
    with pytest.raises(ValueError, match='requires an expected SHA-256'):
        capture_stats_stream(None, tmp_path, NAME, expected_size=3, expected_sha256=None)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('value', [0, -1, float('inf'), float('nan'), True, '1'])
def test_invalid_deadline_before_source_access(tmp_path, value):
    """Bad configuration must fail before source access or spool writes."""
    reader = SimpleNamespace(read=Mock(), settimeout=Mock())
    with pytest.raises(ValueError, match='timeouts'):
        capture(reader, tmp_path, total_timeout=value)
    reader.read.assert_not_called()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('value', [0, -1, 65537, True])
def test_invalid_chunk_bound(tmp_path, value):
    """The adapter never requests unbounded reads."""
    with pytest.raises(ValueError, match='chunk size'):
        capture(None, tmp_path, chunk_size=value)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('chunk', [None, 'abc', b'abcd'])
def test_reader_contract_violation_cleans(tmp_path, chunk):
    """A misbehaving reader cannot publish oversized or non-byte chunks."""
    reader = SimpleNamespace(read=Mock(return_value=chunk), settimeout=Mock())
    with pytest.raises(ValueError, match='bounded bytes'):
        capture(reader, tmp_path, chunk_size=3)
    assert list(tmp_path.iterdir()) == []
