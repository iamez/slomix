"""Real file/seal boundary with established authenticated fixture receipt."""
import hashlib
import os

import pytest

from shared.runtime_timing_snapshot import timing_snapshot
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


@pytest.mark.parametrize('fault', ['none', 'symlink', 'hardlink', 'size', 'world-write'])
def test_closed_timing_snapshot_boundary(tmp_path, timing_ready, pin, fault):  # noqa: F811
    host, epoch, accepted, _ = timing_ready
    completed = receive(timing_ready, pin)
    source = tmp_path / 'source'
    source.mkdir(mode=0o700)
    path = source / 'round.json'
    payload = b'{}' + b' ' * 40
    path.write_bytes(payload)
    path.chmod(0o664)  # normal Lua permissions inside private directory
    if fault == 'symlink':
        path.rename(source / 'original.json')
        path.symlink_to(source / 'original.json')
    elif fault == 'hardlink':
        os.link(path, source / 'alias.json')
    elif fault == 'size':
        path.write_bytes(b'{}')
    elif fault == 'world-write':
        path.chmod(0o666)
    args = dict(accepted=accepted, completed=completed, expected_filename='round.json',
                source_directory=source)
    if fault != 'none':
        with pytest.raises((ValueError, OSError)), timing_snapshot(host, pin, epoch, **args):
            pytest.fail('Unsafe source admitted')
    else:
        with timing_snapshot(host, pin, epoch, **args) as (stream, digest):
            fd = stream.fileno()
            assert stream.read() == payload
            assert digest == hashlib.sha256(payload).hexdigest()
            with pytest.raises(OSError):
                os.write(fd, b'x')
        with pytest.raises(OSError):
            os.fstat(fd)
        assert path.read_bytes() == payload
