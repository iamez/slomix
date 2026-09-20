"""Offline transport seam, real spawned task and filesystem publication proofs."""

import hashlib
import multiprocessing
import os
import subprocess
import time
from contextlib import contextmanager
from functools import partial
from pathlib import Path
from unittest.mock import patch

import pytest

from shared.runtime_ssh import RuntimeSSHConfig
from shared.runtime_ssh_capture import SSHCaptureTask
from shared.runtime_worker import run_bounded_capture_task

NAME = '2026-09-20-120000-oasis-round-1.txt'
PAYLOAD = b'abc'
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


def _offline_child(task, marker, mode):
    """Replace only the connection boundary inside a fresh real spawned child."""
    def record(event):
        with marker.open('a') as stream:
            stream.write(event + '\n')

    class Source:
        def __enter__(self):
            record('file-open')
            self.sent = False
            return self

        def __exit__(self, *args):
            record('file-close')
            if mode == 'close-block':
                time.sleep(30)

        def settimeout(self, seconds):
            assert 0 < seconds <= task.read_timeout

        def read(self, size):
            assert 0 < size <= 65536
            if mode == 'read-block':
                record('read-block')
                time.sleep(30)
            if self.sent:
                return b''
            self.sent = True
            return b'xyz' if mode == 'corrupt' else PAYLOAD

    class SFTP:
        def open(self, path, mode):
            assert path == '/snapshots/' + NAME and mode == 'rb'
            return Source()

    @contextmanager
    def connect(config):
        assert config == task.ssh
        record(str(os.getpid()))
        try:
            yield SFTP()
        finally:
            record('session-close')

    with patch('shared.runtime_ssh_capture.open_runtime_sftp', connect):
        task()


def _task(tmp_path, **kwargs):
    """Construct explicit synthetic settings without reading credentials/env."""
    return SSHCaptureTask(
        RuntimeSSHConfig('offline.invalid', 22, 'fixture', tmp_path / 'key', tmp_path / 'hosts'),
        kwargs.pop('remote_path', '/snapshots/' + NAME), tmp_path,
        len(PAYLOAD), DIGEST, **kwargs,
    )


@pytest.mark.parametrize('mode', ['ok', 'corrupt', 'read-block', 'close-block'])
def test_spawned_ssh_capture_lifecycle(tmp_path, mode):
    """Real publication/kill evidence distinguishes absent, partial and final."""
    tmp_path.chmod(0o700)
    marker = tmp_path / 'events'
    result = run_bounded_capture_task(
        partial(_offline_child, _task(tmp_path), marker, mode),
        timeout_seconds=2 if mode.endswith('block') else 5, shutdown_grace=0.2,
    )
    events = marker.read_text().splitlines()
    assert int(events[0]) == result.pid
    assert not Path(f'/proc/{result.pid}').exists()
    assert result.pid not in [child.pid for child in multiprocessing.active_children()]
    final = tmp_path / NAME
    if mode in ('ok', 'close-block'):
        assert final.read_bytes() == PAYLOAD
        assert subprocess.check_output(['sha256sum', str(final)], text=True).split()[0] == DIGEST
    else:
        assert not final.exists()
    if mode.endswith('block'):
        assert result.status == 'timed_out'
        assert result.exit_code < 0
        assert 'session-close' not in events
        assert ('read-block' if mode == 'read-block' else 'file-close') in events
        assert len(list(tmp_path.glob('*.part'))) == (1 if mode == 'read-block' else 0)
    else:
        assert result.status == ('completed' if mode == 'ok' else 'failed')
        assert events[1:] == ['file-open', 'file-close', 'session-close']
        assert not list(tmp_path.glob('*.part'))
    print(f'Offline SSH task: mode={mode}, status={result.status}, final={final.exists()}, child reaped')


@pytest.mark.parametrize('path', ['relative/file', '/a/../file', '/a/./file', '//file', '/a/', '/a\x00b'])
def test_ambiguous_remote_paths_rejected(tmp_path, path):
    """Remote target is explicit data, never normalised across ambiguous segments."""
    with pytest.raises(ValueError, match='absolute and canonical'):
        _task(tmp_path, remote_path=path)


def test_relative_spool_rejected(tmp_path):
    """Spawn must not interpret a spool relative to its working directory."""
    task = _task(tmp_path)
    with pytest.raises(ValueError, match='absolute Path'):
        SSHCaptureTask(task.ssh, task.remote_path, Path('relative'), 3, DIGEST)
