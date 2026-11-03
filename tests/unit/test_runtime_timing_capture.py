"""Durable private timing payload and manifest with no automatic retry."""
import hashlib
import json

import pytest

from shared.runtime_timing_capture import capture_closed_timing
from tests.unit.test_runtime_host_timing_completion import (  # noqa: F401
    approved,
    channels,
    child,
    pin,
    prepared,
    ready,
    receive,
    timing_ready,
)


def test_durable_capture_retains_source_and_refuses_reuse(tmp_path, timing_ready, pin):  # noqa: F811
    host, epoch, accepted, _ = timing_ready
    completed = receive(timing_ready, pin)
    source, capture = tmp_path / 'source', tmp_path / 'capture'
    source.mkdir(mode=0o700)
    capture.mkdir(mode=0o700)
    payload = b'{}' + b' ' * 40
    (source / 'round.json').write_bytes(payload)
    kwargs = dict(accepted=accepted, completed=completed, expected_filename='round.json',
                  source_directory=source, capture_root=capture)
    result = capture_closed_timing(host, pin, epoch, **kwargs)
    path = capture / completed.generation / result.filename
    record = json.loads(path.with_name('timing-capture.json').read_bytes())
    assert path.read_bytes() == payload == (source / 'round.json').read_bytes()
    assert record['sha256'] == result.sha256 == hashlib.sha256(payload).hexdigest()
    assert record['identity'] == accepted.delivery.dispatch.identity.encode()
    before = path.stat().st_ino, path.read_bytes()
    with pytest.raises(FileExistsError):
        capture_closed_timing(host, pin, epoch, **kwargs)
    assert (path.stat().st_ino, path.read_bytes()) == before


def test_post_reservation_failure_retains_claim(tmp_path, timing_ready, pin):  # noqa: F811
    host, epoch, accepted, _ = timing_ready
    completed = receive(timing_ready, pin)
    source, capture = tmp_path / 'source', tmp_path / 'capture'
    source.mkdir(mode=0o700)
    capture.mkdir(mode=0o700)
    kwargs = dict(accepted=accepted, completed=completed, expected_filename='round.json',
                  source_directory=source, capture_root=capture)
    with pytest.raises(FileNotFoundError):
        capture_closed_timing(host, pin, epoch, **kwargs)
    assert (capture / completed.generation).is_dir()
    (source / 'round.json').write_bytes(b'{}' + b' ' * 40)
    with pytest.raises(FileExistsError):
        capture_closed_timing(host, pin, epoch, **kwargs)


@pytest.mark.parametrize('fail_at', range(1, 7))
def test_each_fsync_failure_retains_attempt_and_never_returns_success(
        tmp_path, timing_ready, pin, monkeypatch, fail_at):  # noqa: F811
    import os

    host, epoch, accepted, _ = timing_ready
    completed = receive(timing_ready, pin)
    source, capture = tmp_path / 'source', tmp_path / 'capture'
    source.mkdir(mode=0o700)
    capture.mkdir(mode=0o700)
    original = b'{}' + b' ' * 40
    (source / 'round.json').write_bytes(original)
    kwargs = dict(accepted=accepted, completed=completed, expected_filename='round.json',
                  source_directory=source, capture_root=capture)
    fsync, calls = os.fsync, []

    def fail(fd):
        calls.append(fd)
        if len(calls) == fail_at:
            raise OSError('fixture timing fsync failure')
        fsync(fd)

    monkeypatch.setattr(os, 'fsync', fail)
    with pytest.raises(OSError, match='fixture timing fsync'):
        capture_closed_timing(host, pin, epoch, **kwargs)
    assert len(calls) == fail_at
    assert (capture / completed.generation).is_dir()
    assert (source / 'round.json').read_bytes() == original
    monkeypatch.setattr(os, 'fsync', fsync)
    before = {p: p.read_bytes() for p in capture.rglob('*') if p.is_file()}
    with pytest.raises(FileExistsError):
        capture_closed_timing(host, pin, epoch, **kwargs)
    assert {p: p.read_bytes() for p in capture.rglob('*') if p.is_file()} == before
