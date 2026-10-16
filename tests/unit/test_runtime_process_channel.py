"""Actual Linux sockets/credentials/fork and whole Lua writer, no live service."""

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

from shared.runtime_init_observation import decode_init_observation
from shared.runtime_process_authority import prepare_observed_process_delivery, reserve_process_epoch
from shared.runtime_process_channel import process_channel
from shared.runtime_process_pin import pin_process
from shared.runtime_round_identity import stats_header_identity
from tests.unit.test_runtime_stats_dispatch import prepare, setup_pair

ROOT = Path(__file__).resolve().parents[2]
CHILD = '''
import array, os, socket, sys, time
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect(sys.argv[1])
print('READY', flush=True)
command = sys.stdin.readline().strip()
if command == 'fork':
    pid = os.fork()
    if pid == 0:
        s.sendall(b'hello\\n'); os._exit(0)
    os.waitpid(pid, 0)
elif command.startswith('rights'):
    fd = os.open('/dev/null', os.O_RDONLY)
    count = 100 if command == 'rights-many' else 1
    s.sendmsg([b'hello\\n'], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [fd]*count))])
    os.close(fd)
elif command == 'fragment':
    s.sendall(b'hel'); time.sleep(.01); s.sendall(b'lo\\nnext\\n')
elif command == 'oversize': s.sendall(b'a'*514)
elif command == 'partial': s.sendall(b'hello'); s.shutdown(socket.SHUT_WR)
elif command == 'empty': s.sendall(b'\\n')
elif command == 'control': s.sendall(b'he\\x00llo\\n')
elif command == 'unicode': s.sendall(b'\\xff\\n')
elif command == 'exit': s.close(); sys.exit(0)
elif command == 'receive':
    data = b''
    while not data.endswith(b'\\n'): data += s.recv(1024)
    print('RECEIVED ' + data.decode().strip(), flush=True)
elif command == 'send': s.sendall(b'hello\\n')
print('SENT', flush=True)
sys.stdin.readline()
s.close()
'''


@pytest.fixture
def listener(tmp_path_factory):
    directory = tmp_path_factory.mktemp('channel')
    directory.chmod(0o700)
    path = directory / 's'
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
        server.bind(str(path))
        path.chmod(0o600)
        server.listen(1)
        server.settimeout(5)
        yield server, path


def approval(executable):
    return dict(expected_uid=os.getuid(), expected_executable=executable,
                expected_sha256=hashlib.sha256(executable.read_bytes()).hexdigest())


@contextmanager
def connected(listener):
    server, path = listener
    executable = Path(sys.executable).resolve()
    with subprocess.Popen([str(executable), '-c', CHILD, str(path)], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as child:
        try:
            assert child.stdout.readline().strip() == 'READY'
            connection, _ = server.accept()
            with connection, pin_process(child.pid, **approval(executable)) as pin:
                yield child, connection, pin
        finally:
            child.stdin.close()
            child.wait(timeout=5)
            error = child.stderr.read()
            assert child.returncode == 0, error


def command(child, value):
    child.stdin.write(value + '\n')
    child.stdin.flush()


@pytest.mark.parametrize('operation', ['receive', 'send'])
def test_interrupted_io_closes_adopted_socket(listener, monkeypatch, operation):
    class Interrupted(BaseException):
        pass

    with connected(listener) as (_, connection, pin), process_channel(connection, pin) as channel:
        def interrupted(*args, **kwargs):
            raise Interrupted

        monkeypatch.setattr(channel, '_wait', interrupted)
        with pytest.raises(Interrupted):
            if operation == 'receive':
                channel.receive_line()
            else:
                channel.send_line('fixture')
        assert connection.fileno() == -1
        with pytest.raises(ValueError, match='closed'):
            channel.receive_line()


def test_native_fragmented_and_coalesced_frames(listener):
    with connected(listener) as (child, connection, pin):
        with process_channel(connection, pin) as channel:
            command(child, 'fragment')
            assert channel.receive_line() == 'hello'
            assert channel.receive_line() == 'next'
        assert connection.fileno() == -1
        with pytest.raises(ValueError, match='closed'):
            channel.receive_line()
    print('NATIVE CHANNEL: pinned PID + per-read kernel credentials, fragmented/coalesced frames accepted')


def test_native_host_response(listener):
    with connected(listener) as (child, connection, pin), process_channel(connection, pin) as channel:
        command(child, 'receive')
        channel.send_line('host-response')
        assert child.stdout.readline().strip() == 'RECEIVED host-response'


def test_send_backpressure_obeys_total_deadline(listener):
    with connected(listener) as (_, connection, pin):
        connection.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024)
        with process_channel(connection, pin, timeout=.05) as channel:
            with pytest.raises(TimeoutError, match='deadline'):
                for _ in range(1000):
                    channel.send_line('x'*512)
            assert connection.fileno() == -1


def test_forked_writer_cannot_use_parents_connection_identity(listener):
    with connected(listener) as (child, connection, pin), process_channel(connection, pin) as channel:
        command(child, 'fork')
        assert child.stdout.readline().strip() == 'SENT'
        # Parent remains alive and connect-time SO_PEERCRED still matches.
        assert pin.assert_current().pid == child.pid
        with pytest.raises(ValueError, match='message sender'):
            channel.receive_line()
        assert connection.fileno() == -1
    print('NATIVE FORK: live approved parent peer, actual child sender rejected')


@pytest.mark.parametrize('mode', ['rights', 'rights-many'])
def test_received_file_descriptors_are_rejected_and_closed(listener, mode):
    with connected(listener) as (child, connection, pin), process_channel(connection, pin) as channel:
        command(child, mode)
        assert child.stdout.readline().strip() == 'SENT'
        before = len(os.listdir('/proc/self/fd'))
        with pytest.raises(ValueError, match='credentials'):
            channel.receive_line()
        assert len(os.listdir('/proc/self/fd')) == before - 1  # Owned socket closed; no imported FD leaks.


@pytest.mark.parametrize('mode', ['oversize', 'partial', 'empty', 'control', 'unicode'])
def test_bad_frame_permanently_closes_channel(listener, mode):
    with connected(listener) as (child, connection, pin), process_channel(connection, pin) as channel:
        command(child, mode)
        with pytest.raises((ValueError, EOFError)):
            channel.receive_line()
        with pytest.raises(ValueError, match='closed'):
            channel.send_line('no-retry')


def test_deadline_is_terminal_not_a_new_budget_per_read(listener):
    with connected(listener) as (child, connection, pin), process_channel(connection, pin, timeout=.05) as channel:
        command(child, 'send')
        assert channel.receive_line() == 'hello'
        with pytest.raises(TimeoutError, match='deadline'):
            channel.receive_line()
        with pytest.raises(ValueError, match='closed'):
            channel.receive_line()


def test_pin_exit_is_not_a_valid_queued_message(listener):
    with connected(listener) as (child, connection, pin), process_channel(connection, pin) as channel:
        command(child, 'exit')
        child.wait(timeout=5)
        with pytest.raises(ValueError, match='exited'):
            channel.receive_line()


def test_credentials_must_be_enabled_before_adoption(listener):
    with connected(listener) as (_, connection, pin):
        connection.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 0)
        with pytest.raises(ValueError, match='disabled'), process_channel(connection, pin):
            pass
        assert connection.fileno() == -1


def test_different_independently_pinned_pid_is_rejected(listener):
    with connected(listener) as (_, connection, _):
        executable = Path(sys.executable).resolve()
        with (pin_process(os.getpid(), **approval(executable)) as wrong,
              pytest.raises(ValueError, match='peer disagrees'), process_channel(connection, wrong)):
            pass
        assert connection.fileno() == -1


@pytest.mark.parametrize('timeout', [True, 0, -1, float('nan'), float('inf'), 11, '1'])
def test_invalid_timeout_closes_adopted_socket(listener, timeout):
    with connected(listener) as (_, connection, pin):
        with pytest.raises(ValueError, match='timeout'), process_channel(connection, pin, timeout=timeout):
            pass
        assert connection.fileno() == -1


@pytest.mark.parametrize('value', ['', 'x'*513, 'a\nb', '\x00', 'č', None])
def test_invalid_send_is_terminal(listener, value):
    with connected(listener) as (_, connection, pin), process_channel(connection, pin) as channel:
        with pytest.raises(ValueError, match='ASCII'):
            channel.send_line(value)
        assert connection.fileno() == -1


@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
@pytest.mark.parametrize('wrong_epoch', [False, True])
def test_credentialed_lua_channel_reaches_actual_c0rn_writer(tmp_path, listener, lua, wrong_epoch):
    server, path = listener
    executable = Path(shutil.which(lua)).resolve()
    authority, spool, pair = setup_pair(tmp_path / 'rounds')
    dispatch = prepare(authority, spool, pair)
    directory = spool / dispatch.generation
    host = tmp_path / 'host'
    host.mkdir(mode=0o700)
    args = [str(executable), str(ROOT / 'tests/lua/runtime_identity_writer_harness.lua'),
            str(ROOT), str(directory), pair.first.source_id, pair.first.match_id,
            pair.first.round_id, pair.second.round_id, '1', dispatch.generation, 'bound-ipc',
            '@unix:' + str(path), 'required-entrypoint', '1234']
    with subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, umask=0o077) as child:
        try:
            connection, _ = server.accept()
            with (connection, pin_process(child.pid, **approval(executable)) as pin,
                  process_channel(connection, pin) as channel):
                observation = decode_init_observation(channel.receive_line())
                assert observation.init_time == 1234 and observation.round_number == 1
                epoch = reserve_process_epoch(host, pin, source_id=pair.first.source_id)
                delivery = prepare_observed_process_delivery(host, pin, epoch, lifecycle_epoch='2'*32,
                                                             observation=observation, dispatch=dispatch)
                channel.send_line(delivery.encode())
                channel.send_line('f'*32 if wrong_epoch else epoch.process_epoch)
                channel.send_line(delivery.lifecycle_epoch)
            stdout, stderr = child.communicate('finish\n', timeout=10)
        finally:
            if not child.stdin.closed:
                child.stdin.close()
            child.wait(timeout=10)
    if wrong_epoch:
        assert child.returncode != 0 and 'sender context mismatch' in stderr
        assert not list(directory.glob('*.txt'))
        return
    assert child.returncode == 0, stdout + stderr
    assert 'IPC FULL MODULE accepted' in stdout
    envelopes = [json.loads(line[8:]) for line in stdout.splitlines() if line.startswith('receipt ')]
    assert len(envelopes) == 1
    receipt = envelopes[0]['completion']
    output = directory / receipt['filename']
    raw = output.read_bytes()
    assert len(raw) == output.stat().st_size == receipt['bytes']
    assert stats_header_identity(raw.splitlines(keepends=True)[0].decode()) == pair.first
    print(f'UNIX {lua}: kernel-authenticated Lua child -> observed InitGame -> leased IPC -> real stats/receipt; '
          'synthetic ET APIs and fixed lifecycle, no running engine')


@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
@pytest.mark.parametrize('fault', ['fragments', 'boundary', 'full-eof', 'partial-eof', 'oversize', 'empty',
    'control', 'partial-send', 'invalid-send', 'deadline', 'backward', 'nan'])
def test_lua_nonblocking_bounds_and_terminal_failures(lua, fault):
    result = subprocess.run([lua, str(ROOT / 'tests/lua/runtime_host_channel_harness.lua'), str(ROOT), fault],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'BOUNDED LUA CHANNEL ' + fault in result.stdout
