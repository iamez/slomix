"""Offline transport seam, real spawned task and filesystem publication proofs."""

import hashlib
import multiprocessing
import os
import stat
import subprocess
import time
from contextlib import contextmanager
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from shared.runtime_ssh import RuntimeSSHConfig
from shared.runtime_ssh_capture import SSHCaptureTask
from shared.runtime_supervised_capture import capture_ssh_once
from shared.runtime_worker import run_bounded_capture_task

NAME = '2026-09-20-120000-oasis-round-1.txt'
PAYLOAD = b'abc'
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


def _offline_child(task, marker, mode):
    """Replace only the connection boundary inside a fresh real spawned child."""
    def record(event):
        with marker.open('a') as stream:
            stream.write(event + '\n')

    sent = False

    def attributes(named=False):
        return SimpleNamespace(
            st_mode=stat.S_IFREG | 0o600,
            st_size=3 + (1 if sent and mode == 'grow' else 0),
            st_mtime=100 + (1 if sent and (mode == 'mtime' or (named and mode == 'replace')) else 0),
        )

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

        def stat(self):
            return attributes()

        def read(self, size):
            nonlocal sent
            assert 0 < size <= 65536
            if mode == 'read-block':
                record('read-block')
                time.sleep(30)
            if self.sent:
                return b''
            self.sent = True
            sent = True
            return b'xyz' if mode == 'corrupt' else PAYLOAD

    class SFTP:
        def lstat(self, path):
            assert path == '/snapshots/' + NAME
            return attributes(named=True)

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


@pytest.mark.parametrize('mode', ['ok', 'corrupt', 'read-block', 'close-block', 'grow', 'mtime', 'replace'])
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


@pytest.mark.parametrize('field,value', [
    ('st_mode', stat.S_IFLNK | 0o777), ('st_mode', stat.S_IFDIR | 0o700),
    ('st_mode', None), ('st_size', None), ('st_size', 4),
    ('st_mtime', None), ('st_mtime', True),
])
def test_unusable_source_metadata_rejected_before_open(tmp_path, field, value):
    """Missing metadata, nonregular paths and wrong sizes cannot begin a read."""
    attributes = dict(st_mode=stat.S_IFREG | 0o600, st_size=3, st_mtime=100)
    attributes[field] = value

    class SFTP:
        def lstat(self, path):
            return SimpleNamespace(**attributes)

        def open(self, *args):
            raise AssertionError('Unsafe metadata must not open source')

    @contextmanager
    def connect(config):
        yield SFTP()

    with patch('shared.runtime_ssh_capture.open_runtime_sftp', connect), pytest.raises(ValueError):
        _task(tmp_path)()
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('mode', ['ok', 'corrupt', 'read-block', 'close-block'])
def test_supervised_retry_preserves_worker_and_content(tmp_path, monkeypatch, mode):
    """Post-reap inspection and a second call do not confuse timeout with absence."""
    tmp_path.chmod(0o700)
    marker = tmp_path / 'events'
    calls = []

    def offline_worker(task, **limits):
        calls.append(task)
        return run_bounded_capture_task(partial(_offline_child, task, marker, mode), **limits)

    monkeypatch.setattr('shared.runtime_supervised_capture.run_bounded_capture_task', offline_worker)
    task = _task(tmp_path)
    result = capture_ssh_once(task, timeout_seconds=2, shutdown_grace=0.2)
    assert len(calls) == 1
    assert result.content == ('match' if mode in ('ok', 'close-block') else 'missing')
    assert result.worker.status == ('timed_out' if mode.endswith('block') else
                                    'failed' if mode == 'corrupt' else 'completed')
    assert not Path(f'/proc/{result.worker.pid}').exists()
    assert result.worker.pid not in [child.pid for child in multiprocessing.active_children()]
    if result.content == 'match':
        again = capture_ssh_once(task, timeout_seconds=2)
        assert again.content == 'match' and again.worker is None
        assert len(calls) == 1
        assert subprocess.check_output(['sha256sum', str(tmp_path / NAME)], text=True).split()[0] == DIGEST
    else:
        leftovers = {path: path.read_bytes() for path in tmp_path.glob('*.part')}
        mode = 'ok'
        again = capture_ssh_once(task, timeout_seconds=5)
        assert again.content == 'match' and again.worker.status == 'completed'
        assert len(calls) == 2
        assert {path: path.read_bytes() for path in tmp_path.glob('*.part')} == leftovers
        assert (tmp_path / NAME).read_bytes() == PAYLOAD
    print(f'Reconciled task: {result.worker.status}, content={result.content}, attempts={len(calls)}')


@pytest.mark.parametrize('payload,state', [(PAYLOAD, 'match'), (b'xyz', 'conflict')])
def test_existing_content_never_spawns(tmp_path, monkeypatch, payload, state):
    """Neither an already captured snapshot nor a conflict may open a connection."""
    tmp_path.chmod(0o700)
    final = tmp_path / NAME
    final.write_bytes(payload)
    final.chmod(0o600)

    def forbidden(*args, **kwargs):
        raise AssertionError('Existing content must not spawn capture')

    monkeypatch.setattr('shared.runtime_supervised_capture.run_bounded_capture_task', forbidden)
    result = capture_ssh_once(_task(tmp_path), timeout_seconds=2)
    assert result.content == state and result.worker is None
    assert final.read_bytes() == payload
