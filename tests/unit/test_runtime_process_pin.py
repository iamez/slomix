"""Real Linux child handles, no daemon/service/game process or signal delivery."""

import errno
import hashlib
import os
import shutil
import subprocess
import sys
import time
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from shared import runtime_process_pin as process
from shared.runtime_process_pin import _start_ticks as start_ticks


@pytest.fixture
def child():
    # EOF closes naturally, including failed tests. The exec target also exits
    # after 0.5 seconds; no kill/terminate or background monitor is needed.
    sleeper = shutil.which('sleep')
    assert sleeper
    code = ('import os,sys; print("READY",flush=True); command=sys.stdin.readline().strip(); '
            'os.execl(sys.argv[1],"sleep","0.5") if command=="exec" else None')
    with subprocess.Popen([sys.executable, '-c', code, sleeper], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as running:
        assert running.stdout.readline().strip() == 'READY'
        try:
            yield running
        finally:
            running.stdin.close()
            running.wait(timeout=5)
            assert running.stderr.read() == ''


@pytest.fixture
def approved():
    path = Path(sys.executable).resolve()
    return dict(expected_uid=os.getuid(), expected_executable=path,
                expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def test_real_process_stable_snapshot_exit_and_owned_handle_cleanup(child, approved):
    with process.pin_process(child.pid, **approved) as pin:
        identity = pin.assert_current()
        assert identity.pid == child.pid and identity.uid == os.getuid()
        assert identity.start_ticks == start_ticks(Path(f'/proc/{child.pid}/stat').read_bytes(), child.pid)
        # Independent ps reports the same process UID; no command line/env read.
        uid = subprocess.run(['ps', '-o', 'uid=', '-p', str(child.pid)],
                             capture_output=True, text=True, check=True, timeout=5)
        assert int(uid.stdout.strip()) == identity.uid
        assert pin.assert_current() == identity
        with pytest.raises(FrozenInstanceError):
            identity.pid = 0
        child.stdin.write('exit\n')
        child.stdin.flush()
        child.wait(timeout=5)
        with pytest.raises(ValueError, match='exited'):
            pin.assert_current()
        with pytest.raises(ValueError, match='invalidated'):
            pin.assert_current()
    with pytest.raises(ValueError, match='closed'):
        pin.assert_current()
    print('NATIVE PIDFD: approved child revalidated, UID agrees with ps, exit rejected, pin permanently invalidated')


def test_interrupted_check_permanently_invalidates_pin(child, approved, monkeypatch):
    class Interrupted(BaseException):
        pass

    with process.pin_process(child.pid, **approved) as pin:
        def interrupted():
            raise Interrupted

        monkeypatch.setattr(process, '_boot_id', interrupted)
        with pytest.raises(Interrupted):
            pin.assert_current()
        with pytest.raises(ValueError, match='invalidated'):
            pin.assert_current()


def test_real_exec_changes_executable_without_changing_pid(child, approved):
    with process.pin_process(child.pid, **approved) as pin:
        original = pin.identity
        child.stdin.write('exec\n')
        child.stdin.flush()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            # Wait for the actual kernel /exe inode change, NOT just a pre-exec
            # message or a timing assumption. No signal sent to the child.
            if os.stat(f'/proc/{child.pid}/exe').st_ino != os.stat(approved['expected_executable']).st_ino:
                break
            time.sleep(.005)
        else:
            pytest.fail('fixture child did not exec')
        assert child.poll() is None
        assert start_ticks(Path(f'/proc/{child.pid}/stat').read_bytes(), child.pid) == original.start_ticks
        with pytest.raises(ValueError, match='executable changed'):
            pin.assert_current()


@pytest.mark.parametrize('fault', ['uid', 'digest', 'path', 'symlink', 'missing'])
def test_rejects_unapproved_process_without_leaking_owned_descriptors(child, approved, tmp_path, monkeypatch, fault):
    if fault == 'uid':
        approved['expected_uid'] += 1
    elif fault == 'digest':
        approved['expected_sha256'] = '0' * 64
    elif fault == 'path':
        approved['expected_executable'] = Path(shutil.which('sleep')).resolve()
    elif fault == 'symlink':
        alias = tmp_path / 'alias'
        alias.symlink_to(approved['expected_executable'])
        approved['expected_executable'] = alias
    else:
        approved['expected_executable'] = tmp_path / 'missing'
    owned = []
    real_open, real_pidfd = os.open, os.pidfd_open

    def track_open(*args, **kwargs):
        fd = real_open(*args, **kwargs)
        owned.append(fd)
        return fd

    def track_pidfd(*args, **kwargs):
        fd = real_pidfd(*args, **kwargs)
        owned.append(fd)
        return fd

    monkeypatch.setattr(os, 'open', track_open)
    monkeypatch.setattr(os, 'pidfd_open', track_pidfd)
    with pytest.raises((ValueError, OSError)), process.pin_process(child.pid, **approved):
        pytest.fail('unapproved process accepted')
    assert owned
    for fd in owned:
        with pytest.raises(OSError) as closed:
            os.fstat(fd)
        assert closed.value.errno == errno.EBADF
    assert child.poll() is None


@pytest.mark.parametrize('override', [dict(pid=True), dict(pid=0), dict(pid=2**31),
    dict(expected_uid=True), dict(expected_uid=-1), dict(expected_sha256='A' * 64),
    dict(expected_executable=Path('relative'))])
def test_invalid_request_does_no_process_io(approved, monkeypatch, override):
    def forbidden(*args):
        pytest.fail('invalid request opened a pidfd')
    monkeypatch.setattr(os, 'pidfd_open', forbidden)
    with pytest.raises(ValueError), process.pin_process(**(dict(pid=123, **approved) | override)):
        pytest.fail('invalid request accepted')


@pytest.mark.parametrize('comm', [b'normal', b'a b', b'a ) b', b'new\nline ) ', b'\xff'])
def test_stat_comm_is_not_split_into_numeric_fields(comm):
    raw = b'123 (' + comm + b') S ' + b' '.join([b'0'] * 18 + [b'456'] + [b'0'] * 8)
    assert start_ticks(raw, 123) == 456


@pytest.mark.parametrize('raw', [b'', b'123 (x) Z ' + b'0 ' * 30,
    b'124 (x) S ' + b'0 ' * 30, b'123 (x) S 0',
    b'123 (x) S ' + b'0 ' * 18 + b'-1', b'123 (x) S ' + b'0 ' * 18 + b'18446744073709551616'])
def test_invalid_or_dead_stat_rejected(raw):
    with pytest.raises(ValueError):
        start_ticks(raw, 123)


def test_unsupported_pidfd_refuses_fallback(child, approved, monkeypatch):
    def unsupported(*args):
        raise OSError(errno.ENOSYS, 'pidfd unavailable')

    monkeypatch.setattr(os, 'pidfd_open', unsupported)
    with pytest.raises(OSError, match='pidfd unavailable') as error, process.pin_process(child.pid, **approved):
        pytest.fail('unsupported kernel accepted')
    assert error.value.errno == errno.ENOSYS
    assert child.poll() is None


def test_exit_during_initial_hash_cannot_create_a_valid_pin(child, approved, monkeypatch):
    real_pread = os.pread

    def read_then_exit(*args):
        chunk = real_pread(*args)
        if child.poll() is None:
            child.stdin.write('exit\n')
            child.stdin.flush()
            child.wait(timeout=5)
        return chunk

    monkeypatch.setattr(os, 'pread', read_then_exit)
    with pytest.raises((ValueError, ProcessLookupError, FileNotFoundError)), process.pin_process(child.pid, **approved):
        pytest.fail('exited process accepted during initial capture')


def test_normal_scope_closes_pidfd_without_stopping_process(child, approved, monkeypatch):
    handles = []
    real_pidfd = os.pidfd_open

    def remember_pidfd(*args):
        fd = real_pidfd(*args)
        handles.append(fd)
        return fd

    monkeypatch.setattr(os, 'pidfd_open', remember_pidfd)
    with process.pin_process(child.pid, **approved) as pin:
        assert os.fstat(handles[0])
        assert pin.assert_current().pid == child.pid
    assert child.poll() is None
    with pytest.raises(OSError) as error:
        os.fstat(handles[0])
    assert error.value.errno == errno.EBADF
    with pytest.raises(ValueError, match='closed'):
        pin.assert_current()
