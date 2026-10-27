"""Actual one-match listener, pinned protocol peer, retained files; NOT ET engine."""

import hashlib
import os
import socket
import stat
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from pathlib import Path

import pytest

from shared import runtime_match_listener as module
from shared.runtime_game_console import map_release
from shared.runtime_match_listener import serve_match
from shared.runtime_process_channel import process_channel
from shared.runtime_process_pin import pin_process
from tests.unit import test_runtime_process_pin as processes
from tests.unit.test_runtime_match_controller import controller, roots
from tests.unit.test_runtime_process_channel import approval

approved, child = processes.approved, processes.child


def test_interrupted_ready_callback_fences_controller_and_closes_listener(
    tmp_path, listener_path, child, approved,
):
    class Interrupted(BaseException):
        pass

    def interrupted():
        raise Interrupted

    with pin_process(child.pid, **approved) as pin:
        driver = controller(roots(tmp_path), pin)
        with pytest.raises(Interrupted):
            serve_match(driver, listener_path, on_ready=interrupted)
        assert driver.state == 'failed'
        # Retained socket entries prevent an ambiguous run from rebinding.
        assert listener_path.is_socket()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client, pytest.raises(ConnectionRefusedError):
            client.connect(str(listener_path))


PEER = r'''
import socket, sys
from pathlib import Path
print('READY', flush=True)
if sys.stdin.readline().strip() == 'go':
    for half in (1, 2):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(5)
            sock.connect(sys.argv[1])
            sock.sendall(f'slomix_init_v1|{half * 1000}|supply|{half}\n'.encode())
            with sock.makefile('rb') as stream:
                context = stream.readline().decode().strip()
                wire = stream.readline().decode().strip()
            fields = wire.split('|')
            assert len(fields) == 7
            assert context.startswith('slomix_bootstrap_context_v1|')
            sock.sendall((wire.replace('slomix_stats_bind_v1', 'slomix_stats_ack_v1', 1) + '\n').encode())
        name = f'2026-10-10-12000{half}-supply-round-{half}.txt'
        header = '\\'.join(['host', 'supply', '1', str(half), '2', '1', '20:00', '10:00', '600000', fields[4]])
        raw = (header + f'\n12345678\\Player\\1\\1\\1 {half} {half} {half} {half} {half}\n').encode()
        with (Path(sys.argv[2]) / fields[5] / name).open('xb') as output:
            output.write(raw)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(5)
            sock.connect(sys.argv[1])
            sock.sendall(f'slomix_stats_closed_v1|{fields[5]}|{name}|{len(raw)}\n'.encode())
    print('CLOSED BOTH', flush=True)
    sys.stdin.readline()  # Keep the pinned producer alive through durable capture.
'''


@pytest.fixture
def listener_path(tmp_path_factory):
    directory = tmp_path_factory.mktemp('rl')
    directory.chmod(0o700)
    return directory / 's'


def wait_bound(path, future):
    deadline = time.monotonic() + 5
    while not path.exists():
        if future.done():
            future.result()
        assert time.monotonic() < deadline, 'Listener did not bind'
        time.sleep(.005)
    # The test's peer is released only after listen(), not merely pathname bind.
    # No test probe connects: that would correctly consume/fail the first slot.


@contextmanager
def native_pair(tmp_path, path, *, console=False, readiness_delay=0, bootstrap_wait=5, completion_wait=5):
    all_roots = roots(tmp_path)
    executable = Path(sys.executable).resolve()
    peer_code = PEER.replace("== 'go'", "== 'map supply'") if console else PEER
    if readiness_delay:
        peer_code = peer_code.replace('for half in (1, 2):',
            f'import time; time.sleep({readiness_delay})\n    for half in (1, 2):')
    with subprocess.Popen([str(executable), '-c', peer_code, str(path), str(all_roots[1])],
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, umask=0o077) as peer:
        try:
            assert peer.stdout.readline().strip() == 'READY'
            with pin_process(peer.pid, **approval(executable)) as pin, ExitStack() as stack:
                driver = controller(all_roots, pin)
                ready_states = []
                if console:
                    os.set_blocking(peer.stdin.fileno(), False)
                    release = stack.enter_context(map_release(pin, peer.stdin.fileno()))

                def ready():
                    assert path.is_socket()
                    ready_states.append(driver.state)
                    if console:
                        release()
                        with pytest.raises(ValueError, match='consumed'):
                            release()
                    else:
                        peer.stdin.write('go\n')
                        peer.stdin.flush()

                with ThreadPoolExecutor(max_workers=1) as pool:
                    completion_options = {} if completion_wait is None else {'completion_wait': completion_wait}
                    future = pool.submit(serve_match, driver, path, initial_readiness_wait=5,
                                         bootstrap_wait=bootstrap_wait, on_ready=ready, **completion_options)
                    captured = future.result(timeout=15)
                assert ready_states == ['awaiting_bootstrap']
                assert peer.stdout.readline().strip() == 'CLOSED BOTH'
                assert driver.state == 'complete'
            yield captured, all_roots[1], driver
        finally:
            peer.stdin.close()
            peer.wait(timeout=10)
        assert peer.returncode == 0, peer.stderr.read()


def test_native_listener_captures_both_halves_and_closes(tmp_path, listener_path):
    with native_pair(tmp_path, listener_path) as (captured, producer, driver):
        for item in (captured.first, captured.second):
            source = producer / item.reference.generation / item.reference.filename
            copy = item.directory / item.reference.filename
            assert source.read_bytes() == copy.read_bytes()
            digest = hashlib.sha256(copy.read_bytes()).hexdigest()
            assert subprocess.check_output(['sha256sum', str(source)], text=True).split()[0] == digest
            assert digest == item.reference.sha256
        assert len(list(producer.glob('*/*.txt'))) == 2
        assert listener_path.is_socket() and stat.S_IMODE(listener_path.stat().st_mode) == 0o600
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock, pytest.raises(ConnectionRefusedError):
            sock.connect(str(listener_path))
        with pytest.raises(ValueError, match='ready match controller'):
            serve_match(driver, listener_path)
    print('NATIVE LISTENER: 4 authenticated connections -> 2 retained source files + '
          '2 sealed captures; SHA256 checked independently; closed listener; NOT actual ET')


def test_console_release_after_listen_drives_native_match(tmp_path, listener_path):
    with native_pair(tmp_path, listener_path, console=True) as (captured, producer, driver):
        assert driver.state == 'complete'
        assert captured.first.reference.sha256 != captured.second.reference.sha256
        assert len(list(producer.glob('*/*.txt'))) == 2
    print('CONSOLE PIPE: pinned stdin received map supply only after listener readiness; '
          'one release, four authenticated connections, two captures; NOT an ET game')


@pytest.mark.parametrize('change', ['none', 'replace-root', 'remove-root', 'replace-socket', 'mode'])
def test_listener_timeout_or_path_change_fences_controller(tmp_path, listener_path, child, approved, change):
    from threading import Event

    with pin_process(child.pid, **approved) as pin:
        driver = controller(roots(tmp_path), pin)
        ready = Event()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(serve_match, driver, listener_path, initial_readiness_wait=.25,
                                 on_ready=ready.set)
            assert ready.wait(timeout=5), 'Readiness must follow dispatch reservation'
            if change in {'replace-root', 'remove-root'}:
                parent = listener_path.parent
                parent.rename(parent.with_name(parent.name + '-held'))
                if change == 'replace-root':
                    parent.mkdir(mode=0o700)
            elif change == 'replace-socket':
                listener_path.rename(listener_path.with_name('held'))
                listener_path.write_text('replacement retained')
            elif change == 'mode':
                listener_path.chmod(0o666)
            with pytest.raises((TimeoutError, ValueError, FileNotFoundError)) as refusal:
                future.result(timeout=5)
            if isinstance(refusal.value, FileNotFoundError):
                # Rename/recreate deliberately has an observable absence window.
                assert change in {'replace-root', 'remove-root', 'replace-socket'}
                assert refusal.value.filename in {str(listener_path.parent), str(listener_path), listener_path.name}
        assert driver.state == 'failed'
        # A deadline/root failure never erases source ownership for retry.
        assert list(tmp_path.rglob('.writer-claimed'))
        with pytest.raises(ValueError, match='Both successful captures'):
            driver.captured_match()
        with pytest.raises(ValueError, match='out of order'):
            driver.prepare_half()


def test_wrong_live_peer_is_rejected_without_retry(tmp_path, listener_path, child, approved):
    with pin_process(child.pid, **approved) as pin:
        driver = controller(roots(tmp_path), pin)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(serve_match, driver, listener_path, bootstrap_wait=1)
            wait_bound(listener_path, future)
            deadline = time.monotonic() + 2
            while driver.state in ('ready', 'busy'):
                assert time.monotonic() < deadline
                time.sleep(.005)
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.connect(str(listener_path))
                sock.sendall(b'slomix_init_v1|1000|supply|1\n')
                with pytest.raises(ValueError, match='peer disagrees'):
                    future.result(timeout=5)
        assert driver.state == 'failed'


def test_dead_source_does_not_wait_for_round_timeout(tmp_path, listener_path, child, approved):
    with pin_process(child.pid, **approved) as pin:
        driver = controller(roots(tmp_path), pin)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(serve_match, driver, listener_path, bootstrap_wait=30)
            wait_bound(listener_path, future)
            child.stdin.write('exit\n')
            child.stdin.flush()
            child.wait(timeout=5)
            with pytest.raises(ValueError, match='exited|invalidated'):
                future.result(timeout=2)
        assert driver.state == 'failed'


@pytest.mark.parametrize('change', ['public', 'symlink'])
def test_unprotected_or_redirected_directory_refused(tmp_path, listener_path, child, approved, change):
    if change == 'public':
        listener_path.parent.chmod(0o755)
    else:
        parent = listener_path.parent
        held = parent.with_name(parent.name + '-held')
        parent.rename(held)
        parent.symlink_to(held, target_is_directory=True)
    with pin_process(child.pid, **approved) as pin:
        driver = controller(roots(tmp_path), pin)
        with pytest.raises(ValueError):
            serve_match(driver, listener_path)
        assert driver.state == 'failed' and not listener_path.exists()


def test_listener_teardown_failure_revokes_handoff(tmp_path, listener_path, monkeypatch):
    original = module._listener  # noqa: SLF001

    @contextmanager
    def failed_close(path):
        with original(path) as bound:
            yield bound
        raise OSError('fixture listener teardown failure')

    monkeypatch.setattr(module, '_listener', failed_close)
    with pytest.raises(OSError, match='listener teardown failure'), native_pair(tmp_path, listener_path):
        pytest.fail('Listener exported success despite teardown failure')


@pytest.mark.parametrize('value', [0, -1, True, float('nan'), float('inf'), 7201, '5'])
def test_invalid_timeouts_do_not_consume_controller(tmp_path, listener_path, child, approved, value):
    with pin_process(child.pid, **approved) as pin:
        driver = controller(roots(tmp_path), pin)
        with pytest.raises(ValueError, match='timeout'):
            serve_match(driver, listener_path, completion_wait=value)
        assert driver.state == 'ready' and not listener_path.exists()


@pytest.mark.parametrize('kind', ['file', 'symlink', 'socket'])
def test_existing_socket_entry_is_never_overwritten(tmp_path, listener_path, child, approved, kind):
    held = listener_path.with_name('original')
    held.write_text('preserve me')
    if kind == 'file':
        listener_path.write_text('original file')
    elif kind == 'symlink':
        listener_path.symlink_to(held)
    else:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.bind(str(listener_path))
    before = listener_path.lstat()
    with pin_process(child.pid, **approved) as pin:
        driver = controller(roots(tmp_path), pin)
        with pytest.raises(OSError):
            serve_match(driver, listener_path)
        assert driver.state == 'failed'
    assert listener_path.lstat() == before and held.read_text() == 'preserve me'


def test_pre_accept_bytes_have_credentials(listener_path):
    with (
        pin_process(os.getpid(), **approval(Path(sys.executable).resolve())) as pin,
        module._listener(listener_path) as (server, verify),  # noqa: SLF001
        socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer,
    ):
        peer.connect(str(listener_path))
        peer.sendall(b'queued-before-accept\n')
        connection, _ = server.accept()
        with process_channel(connection, pin) as channel:
            assert channel.receive_line() == 'queued-before-accept'
        verify()


def test_ready_notification_precedes_accept_once(tmp_path, listener_path, child, approved):
    with pin_process(child.pid, **approved) as pin:
        driver = controller(roots(tmp_path), pin)
        observations = []

        def ready():
            assert listener_path.is_socket()
            driver.check_waiting()
            # Connect only when notified, proving listen() happened first. This
            # is intentionally NOT the pinned producer and must be refused.
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
                peer.connect(str(listener_path))
            observations.append(driver.state)

        with pytest.raises(ValueError, match='peer disagrees'):
            serve_match(driver, listener_path, bootstrap_wait=.05, on_ready=ready)
        assert observations == ['awaiting_bootstrap']
        assert driver.state == 'failed'


def test_ready_notification_failure_fences_and_retains(tmp_path, listener_path, child, approved):
    with pin_process(child.pid, **approved) as pin:
        all_roots = roots(tmp_path)
        driver = controller(all_roots, pin)
        claimed = []

        def broken_observer():
            claimed.extend(all_roots[0].glob('*/.writer-claimed'))
            raise OSError('fixture readiness notification failed')

        with pytest.raises(OSError, match='readiness notification failed'):
            serve_match(driver, listener_path, on_ready=broken_observer)
        assert claimed and all(path.exists() for path in claimed)
        assert driver.state == 'failed' and listener_path.is_socket()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer, pytest.raises(ConnectionRefusedError):
            peer.connect(str(listener_path))
        with pytest.raises(ValueError, match='Both successful captures'):
            driver.captured_match()


def test_invalid_ready_observer_does_not_consume_controller(tmp_path, listener_path, child, approved):
    with pin_process(child.pid, **approved) as pin:
        driver = controller(roots(tmp_path), pin)
        with pytest.raises(ValueError, match='readiness observer'):
            serve_match(driver, listener_path, on_ready='not callable')
        assert driver.state == 'ready' and not listener_path.exists()


def test_initial_readiness_allows_warmup_longer_than_between_half_budget(tmp_path, listener_path):
    # A real pinned peer waits 300ms before its first InitGame handshake. The
    # independent 100ms inter-half budget must not terminate initial readiness.
    with native_pair(tmp_path, listener_path, readiness_delay=.3, bootstrap_wait=.1) as (captured, _, driver):
        assert driver.state == 'complete'
        assert captured.first.reference.generation != captured.second.reference.generation


@pytest.mark.parametrize('name', ['initial_readiness_wait', 'bootstrap_wait'])
@pytest.mark.parametrize('value', [0, -1, True, float('nan'), float('inf'), 3601, '5'])
def test_readiness_deadlines_are_bounded_before_consuming_controller(
    tmp_path, listener_path, child, approved, name, value,
):
    with pin_process(child.pid, **approved) as pin:
        driver = controller(roots(tmp_path), pin)
        with pytest.raises(ValueError, match='timeout'):
            serve_match(driver, listener_path, **{name: value})
        assert driver.state == 'ready' and not listener_path.exists()


def test_default_completion_covers_paused_half_longer_than_thirty_minutes(
    tmp_path, listener_path, monkeypatch,
):
    # Native pinned peer, real files and credentials; only elapsed wait time is
    # virtual. Advance31 minutes after the R1 completion accept deadline starts.
    accept, poll, monotonic = module._accept, module.select.select, module.time.monotonic  # noqa: SLF001 -- clock/accept boundary
    calls = 0

    def accept_with_pause(server, verify, driver, wait):
        nonlocal calls
        calls += 1
        if calls != 2:
            return accept(server, verify, driver, wait)
        elapsed = 0
        def paused_poll(*args):
            nonlocal elapsed
            elapsed = 31 * 60
            return poll(*args)
        with monkeypatch.context() as patch:
            patch.setattr(module.time, 'monotonic', lambda: monotonic() + elapsed)
            patch.setattr(module.select, 'select', paused_poll)
            result = accept(server, verify, driver, wait)
        assert elapsed == 1860
        return result

    monkeypatch.setattr(module, '_accept', accept_with_pause)
    with native_pair(tmp_path, listener_path, completion_wait=None) as (captured, _, driver):
        assert driver.state == 'complete' and calls == 4
        captured.verify()
    print('COMPLETION BUDGET: native peer and files; virtual31-minute pause accepted within global60-minute budget')
