"""Real spawned-child proofs; no SSH, server, service or database operations."""

import multiprocessing
import multiprocessing.popen_spawn_posix
import os
import pickle
import signal
import time
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import pytest

from shared import runtime_worker
from shared.runtime_worker import run_bounded_capture_task


def _complete(marker):
    """Record child execution without carrying application state."""
    Path(marker).write_text(str(os.getpid()))


def _fail():
    """Failure text must not be forwarded by the supervisor."""
    raise ValueError('fixture task failure')


def _block(marker, ignore_term):
    """Model an unbounded library wait, optionally refusing graceful termination."""
    if ignore_term:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    Path(marker).write_text(str(os.getpid()))
    time.sleep(30)


def test_completed_child_is_reaped(tmp_path):
    """Exit status and procfs independently confirm no owned child remains."""
    marker = tmp_path / 'child'
    result = run_bounded_capture_task(partial(_complete, marker), timeout_seconds=5)
    assert result.status == 'completed' and result.exit_code == 0
    assert int(marker.read_text()) == result.pid and result.pid != os.getpid()
    assert not Path(f'/proc/{result.pid}').exists()
    assert result.pid not in [p.pid for p in multiprocessing.active_children()]
    print('Worker proof: child completed, joined and absent from procfs/active_children')


def test_failed_child_is_not_success(capfd):
    """Task failure returns only status/exit code, no raw error text."""
    result = run_bounded_capture_task(_fail, timeout_seconds=5)
    assert result.status == 'failed' and result.exit_code == 1
    assert 'fixture task failure' not in capfd.readouterr().err
    assert not Path(f'/proc/{result.pid}').exists()


@pytest.mark.parametrize('fails', [False, True])
def test_late_parent_observation_preserves_finished_child(tmp_path, monkeypatch, fails):
    """A clock advance after real join cannot change an observed child exit."""
    process_type = multiprocessing.get_context('spawn').Process
    original_join = process_type.join
    clock = [100.0]
    joined = []

    def delayed_observation(process, timeout=None):
        original_join(process, timeout)
        assert not process.is_alive(), 'Fixture child did not finish within join budget'
        joined.append(process.pid)
        clock[0] = 106.0

    # Patch only the supervisor's clock, not multiprocessing's real wait clock.
    monkeypatch.setattr(runtime_worker, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(process_type, 'join', delayed_observation)
    marker = tmp_path / 'child'
    task = _fail if fails else partial(_complete, marker)
    result = run_bounded_capture_task(task, timeout_seconds=5)
    assert result.status == ('failed' if fails else 'completed')
    assert result.exit_code == (1 if fails else 0)
    assert joined == [result.pid]
    if not fails:
        assert int(marker.read_text()) == result.pid
    assert not Path(f'/proc/{result.pid}').exists()
    assert result.pid not in [p.pid for p in multiprocessing.active_children()]
    print(f'Late observer proof: child exit={result.exit_code}, status={result.status}, reaped')


def test_parent_interruption_still_reaps_child(tmp_path, monkeypatch):
    """Interrupting parent join cannot abandon the child it just created."""
    process_type = multiprocessing.get_context('spawn').Process
    original_join = process_type.join
    pids = []
    def interrupted_join(process, timeout=None):
        if not pids:
            pids.append(process.pid)
            raise KeyboardInterrupt
        return original_join(process, timeout)
    monkeypatch.setattr(process_type, 'join', interrupted_join)
    with pytest.raises(KeyboardInterrupt):
        run_bounded_capture_task(partial(_block, tmp_path / 'child', False),
                                 timeout_seconds=2, shutdown_grace=0.2)
    assert len(pids) == 1
    assert not Path(f'/proc/{pids[0]}').exists()
    assert pids[0] not in [p.pid for p in multiprocessing.active_children()]


class _UnpicklableTask:
    def __reduce__(self):
        raise pickle.PicklingError('fixture serialization failure')

    def __call__(self):
        raise AssertionError('Unpicklable task must not execute')


@pytest.mark.parametrize('explicit_pickling_error', [False, True])
def test_unpicklable_task_fails_without_child(explicit_pickling_error):
    """Spawn preparation failure does not leak a task process."""
    before = {p.pid for p in multiprocessing.active_children()}
    task = _UnpicklableTask() if explicit_pickling_error else lambda: None
    with pytest.raises((AttributeError, TypeError, pickle.PicklingError)):
        run_bounded_capture_task(task, timeout_seconds=1)
    assert {p.pid for p in multiprocessing.active_children()} == before


@pytest.mark.parametrize('interrupt_calls', [(2,), (3,), (1, 2, 3)])
@pytest.mark.parametrize('error_type', [KeyboardInterrupt, SystemExit])
def test_cleanup_interruption_still_reaps_child(tmp_path, monkeypatch, interrupt_calls, error_type):
    """Delay cancellation until the SIGTERM-resistant real child is reaped."""
    process_type = multiprocessing.get_context('spawn').Process
    original_join = process_type.join
    processes = []
    calls = []
    errors = {n: error_type(f'join {n}') for n in interrupt_calls}

    def interrupted_join(process, timeout=None):
        if not processes:
            processes.append(process)
        calls.append(timeout)
        number = len(calls)
        # First real wait lets the child install its SIGTERM handler.
        if number == 1 or number not in errors:
            original_join(process, timeout)
        if number in errors:
            raise errors[number]

    monkeypatch.setattr(process_type, 'join', interrupted_join)
    marker = tmp_path / 'child'
    try:
        try:
            raise LookupError('caller is already handling an unrelated error')
        except LookupError:
            with pytest.raises(error_type) as raised:
                run_bounded_capture_task(partial(_block, marker, True),
                                         timeout_seconds=2, shutdown_grace=0.2)
        assert raised.value is errors[interrupt_calls[0]]
        assert len(calls) >= max(interrupt_calls)
        pid = int(marker.read_text())
        assert not Path(f'/proc/{pid}').exists()
        assert pid not in [p.pid for p in multiprocessing.active_children()]
        with pytest.raises(ValueError, match='process object is closed'):
            processes[0].is_alive()
        print(f'Interrupted cleanup proof: joins={interrupt_calls}, child={pid}, reaped and closed')
    finally:
        # Keep the deliberately broken implementation from leaking a fixture child.
        for process in processes:
            try:
                alive = process.is_alive()
            except ValueError:
                continue  # Already closed by the supervisor.
            if alive:
                process.kill()
            original_join(process, 2)
            process.close()


@pytest.mark.parametrize('ignore_term', [False, True])
def test_stuck_child_times_out_and_is_reaped(tmp_path, ignore_term):
    """Deadline stops the owned child; SIGTERM refusal escalates to SIGKILL."""
    marker = tmp_path / 'child'
    started = time.monotonic()
    result = run_bounded_capture_task(partial(_block, marker, ignore_term),
                                      timeout_seconds=2, shutdown_grace=0.2)
    elapsed = time.monotonic() - started
    assert marker.exists(), 'Child did not start within the fixture budget'
    assert result.status == 'timed_out'
    assert result.exit_code == -(signal.SIGKILL if ignore_term else signal.SIGTERM)
    assert int(marker.read_text()) == result.pid
    assert not Path(f'/proc/{result.pid}').exists()
    assert result.pid not in [p.pid for p in multiprocessing.active_children()]
    assert elapsed < 10, elapsed
    print(f'Worker timeout proof: ignore_term={ignore_term}, reaped exit={result.exit_code}, elapsed={elapsed:.3f}s')


@pytest.mark.parametrize('timeout,grace', [(0, 1), (-1, 1), (301, 1), (True, 1),
                                         (float('nan'), 1), (1, 0), (1, 6)])
def test_invalid_limits_do_not_spawn(timeout, grace, tmp_path):
    """Reject invalid supervision bounds before any child-side effect."""
    marker = tmp_path / 'child'
    with pytest.raises(ValueError):
        run_bounded_capture_task(partial(_complete, marker), timeout_seconds=timeout, shutdown_grace=grace)
    assert not marker.exists()


@pytest.mark.parametrize('operation', ['kill', 'is_alive'])
def test_escalation_interruption_retries_and_reaps(tmp_path, monkeypatch, operation):
    """One interruption anywhere in escalation cannot abandon a real child."""
    kind = multiprocessing.get_context('spawn').Process
    original = getattr(kind, operation)
    original_join, original_kill, original_alive = kind.join, kind.kill, kind.is_alive
    processes, interrupted = [], []
    error = KeyboardInterrupt('fixture escalation interrupt')

    def interrupt(process, *args):
        if not processes:
            processes.append(process)
        # is_alive is first used for timeout classification; interrupt cleanup.
        interrupted.append(None)
        if len(interrupted) == (3 if operation == 'is_alive' else 1):
            raise error
        return original(process, *args)

    monkeypatch.setattr(kind, operation, interrupt)
    try:
        with pytest.raises(KeyboardInterrupt) as raised:
            run_bounded_capture_task(partial(_block, tmp_path / 'child', True),
                                     timeout_seconds=1, shutdown_grace=0.2)
        assert raised.value is error
        pid = int((tmp_path / 'child').read_text())
        assert not Path(f'/proc/{pid}').exists()
        assert pid not in [p.pid for p in multiprocessing.active_children()]
    finally:
        for process in processes:
            try:
                if original_alive(process):
                    original_kill(process)
                original_join(process, 2)
                process.close()
            except ValueError:
                pass  # Already closed by supervisor.


def test_sigint_during_spawn_keeps_child_owned(tmp_path, monkeypatch):
    """Deliver real SIGINT after OS spawn but before Process owns its Popen."""
    popen = multiprocessing.popen_spawn_posix.Popen
    original = popen._launch  # noqa: SLF001 - inject at the actual OS-spawn ownership gap
    handles = []
    marker = tmp_path / 'child'
    previous_handler = signal.getsignal(signal.SIGINT)

    def interrupted_launch(handle, process):
        original(handle, process)
        handles.append(handle)
        os.kill(os.getpid(), signal.SIGINT)

    monkeypatch.setattr(popen, '_launch', interrupted_launch)
    try:
        with pytest.raises(KeyboardInterrupt):
            run_bounded_capture_task(partial(_block, marker, False),
                                     timeout_seconds=1, shutdown_grace=0.2)
        pid = handles[0].pid
        assert not Path(f'/proc/{pid}').exists()
        assert pid not in [p.pid for p in multiprocessing.active_children()]
        assert signal.getsignal(signal.SIGINT) == previous_handler
    finally:
        # Raw Popen remains available even when broken Process.pid is None.
        for handle in handles:
            if handle.poll() is None:
                handle.kill()
            handle.wait(2)
            handle.close()


def _record_signal_mask(marker):
    """Observe child mask without changing it."""
    blocked = signal.pthread_sigmask(signal.SIG_BLOCK, [])
    Path(marker).write_text(','.join(str(int(item)) for item in sorted(blocked)))


@pytest.mark.parametrize('ignored', [False, True])
def test_startup_preserves_signal_handler_and_child_mask(tmp_path, monkeypatch, ignored):
    """Deferred custom handlers run restored; ignored SIGINT remains ignored."""
    popen = multiprocessing.popen_spawn_posix.Popen
    original = popen._launch  # noqa: SLF001 - observe actual startup signal behavior
    previous = signal.getsignal(signal.SIGINT)
    calls = []

    def custom(signum, frame):
        assert signal.getsignal(signal.SIGINT) is custom
        calls.append(signum)

    handler = signal.SIG_IGN if ignored else custom
    mask = signal.pthread_sigmask(signal.SIG_BLOCK, [])

    def interrupted_launch(handle, process):
        original(handle, process)
        os.kill(os.getpid(), signal.SIGINT)

    monkeypatch.setattr(popen, '_launch', interrupted_launch)
    signal.signal(signal.SIGINT, handler)
    try:
        result = run_bounded_capture_task(partial(_record_signal_mask, tmp_path / 'mask'),
                                         timeout_seconds=3, shutdown_grace=0.2)
        assert result.status == 'completed'
        assert signal.getsignal(signal.SIGINT) == handler
        assert calls == ([] if ignored else [signal.SIGINT])
        assert (tmp_path / 'mask').read_text() == ','.join(str(int(item)) for item in sorted(mask))
        assert not Path(f'/proc/{result.pid}').exists()
    finally:
        signal.signal(signal.SIGINT, previous)


@pytest.mark.parametrize('operation', ['is_alive', 'kill'])
def test_persistent_cleanup_failure_is_bounded_and_truthful(operation):
    """Unobservable process death must never be reported as successful reaping."""
    class BrokenProcess:
        pid = 123

        def is_alive(self):
            if operation == 'is_alive':
                raise OSError('fixture unavailable process status')
            return True

        def terminate(self):
            pass

        def join(self, timeout):
            pass

        def kill(self):
            raise OSError('fixture unable to kill')

    started = time.monotonic()
    with pytest.raises(RuntimeError, match='could not be reaped') as raised:
        runtime_worker._reap(BrokenProcess(), 0.02)  # noqa: SLF001 - isolated bounded cleanup fault
    assert isinstance(raised.value.__cause__, OSError)
    assert time.monotonic() - started < 1


def test_finished_child_with_minimum_supported_grace(tmp_path):
    """The supported minimum remains usable for an already finished child."""
    result = run_bounded_capture_task(partial(_complete, tmp_path / 'child'),
                                     timeout_seconds=3, shutdown_grace=0.01)
    assert result.status == 'completed'
    assert not Path(f'/proc/{result.pid}').exists()


@pytest.mark.parametrize('parent_error', [False, True])
def test_cleanup_clock_sigint_reaps_before_delivery(tmp_path, monkeypatch, parent_error):
    """Real SIGINT at cleanup loop control cannot escape child ownership."""
    kind = multiprocessing.get_context('spawn').Process
    original_join, original_kill, original_alive = kind.join, kind.kill, kind.is_alive
    clock = time.monotonic
    processes, calls = [], []
    error = LookupError('fixture original parent failure')

    def join(process, timeout=None):
        first = not processes
        if first:
            processes.append(process)
        original_join(process, timeout)
        if first and parent_error:
            raise error

    def interrupt_clock():
        calls.append(None)
        # deadline, initial join budget, cleanup phase deadline, loop condition.
        if len(calls) == 4:
            os.kill(os.getpid(), signal.SIGINT)
        return clock()

    monkeypatch.setattr(kind, 'join', join)
    monkeypatch.setattr(runtime_worker, 'time', SimpleNamespace(monotonic=interrupt_clock))
    try:
        with pytest.raises(LookupError if parent_error else KeyboardInterrupt) as raised:
            run_bounded_capture_task(partial(_block, tmp_path / 'child', True),
                                     timeout_seconds=1, shutdown_grace=0.2)
        if parent_error:
            assert raised.value is error
        pid = int((tmp_path / 'child').read_text())
        assert not Path(f'/proc/{pid}').exists()
        assert pid not in [p.pid for p in multiprocessing.active_children()]
    finally:
        for process in processes:
            try:
                if original_alive(process):
                    original_kill(process)
                original_join(process, 2)
                process.close()
            except ValueError:
                pass


@pytest.mark.parametrize('mode', ['custom', 'ignored', 'system_exit'])
def test_cleanup_restores_and_replays_caller_handler(tmp_path, monkeypatch, mode):
    """Cleanup deferral preserves the caller's signal policy after handle close."""
    kind = multiprocessing.get_context('spawn').Process
    original_close = kind.close
    previous = signal.getsignal(signal.SIGINT)
    closed, calls = [], []
    error = SystemExit(42)

    def custom(signum, frame):
        assert signal.getsignal(signal.SIGINT) is custom
        assert closed
        calls.append(signum)
        if mode == 'system_exit':
            raise error

    def close(process):
        pid = process.pid
        os.kill(os.getpid(), signal.SIGINT)
        original_close(process)
        closed.append(pid)

    handler = signal.SIG_IGN if mode == 'ignored' else custom
    monkeypatch.setattr(kind, 'close', close)
    signal.signal(signal.SIGINT, handler)
    try:
        task = partial(_complete, tmp_path / 'child')
        if mode == 'system_exit':
            with pytest.raises(SystemExit) as raised:
                run_bounded_capture_task(task, timeout_seconds=3)
            assert raised.value is error
        else:
            assert run_bounded_capture_task(task, timeout_seconds=3).status == 'completed'
        assert calls == ([] if mode == 'ignored' else [signal.SIGINT])
        assert signal.getsignal(signal.SIGINT) == handler
        assert not Path(f'/proc/{closed[0]}').exists()
    finally:
        signal.signal(signal.SIGINT, previous)


def test_tiny_grace_is_rejected_before_child_creation(tmp_path, monkeypatch):
    kind = multiprocessing.get_context('spawn').Process
    original_start, original_join = kind.start, kind.join
    processes = []

    def start(process):
        processes.append(process)
        return original_start(process)

    monkeypatch.setattr(kind, 'start', start)
    try:
        with pytest.raises(ValueError, match='grace'):
            run_bounded_capture_task(partial(_block, tmp_path / 'child', True),
                                     timeout_seconds=1, shutdown_grace=1e-20)
        assert not processes
    finally:
        for process in processes:
            try:
                if process.is_alive():
                    process.kill()
                original_join(process, 2)
                process.close()
            except ValueError:
                pass


def test_no_signal_handler_reinstallation_after_child_exists(tmp_path, monkeypatch):
    kind = multiprocessing.get_context('spawn').Process
    original_start, original_join = kind.start, kind.join
    previous = signal.getsignal(signal.SIGINT)
    processes, calls = [], []

    def start(process):
        result = original_start(process)
        processes.append(process)
        return result

    def getsignal(signum):
        calls.append(signum)
        if len(calls) == 2:
            os.kill(os.getpid(), signal.SIGINT)
        return signal.getsignal(signum)

    monkeypatch.setattr(kind, 'start', start)
    monkeypatch.setattr(runtime_worker, 'signal', SimpleNamespace(
        SIGINT=signal.SIGINT, getsignal=getsignal, signal=signal.signal,
    ))
    try:
        try:
            run_bounded_capture_task(partial(_block, tmp_path / 'child', True),
                                     timeout_seconds=1, shutdown_grace=0.2)
        except KeyboardInterrupt:
            pass
        pid = int((tmp_path / 'child').read_text())
        assert not Path(f'/proc/{pid}').exists()
        assert pid not in [p.pid for p in multiprocessing.active_children()]
        assert len(calls) == 1, 'Signal ownership must be installed only before spawn'
        assert signal.getsignal(signal.SIGINT) == previous
    finally:
        for process in processes:
            try:
                if process.is_alive():
                    process.kill()
                original_join(process, 2)
                process.close()
            except ValueError:
                pass


@pytest.mark.parametrize('handler_raises', [False, True])
def test_launch_failure_still_replays_custom_signal_policy(tmp_path, monkeypatch, handler_raises):
    popen = multiprocessing.popen_spawn_posix.Popen
    previous = signal.getsignal(signal.SIGINT)
    calls = []
    original_error = OSError('fixture launch failed before OS spawn')

    def custom(signum, frame):
        assert signal.getsignal(signal.SIGINT) is custom
        calls.append(signum)
        if handler_raises:
            raise SystemExit(17)

    def launch(handle, process):
        os.kill(os.getpid(), signal.SIGINT)
        raise original_error

    monkeypatch.setattr(popen, '_launch', launch)
    signal.signal(signal.SIGINT, custom)
    try:
        with pytest.raises(OSError) as raised:
            run_bounded_capture_task(partial(_complete, tmp_path / 'child'), timeout_seconds=1)
        assert raised.value is original_error
        assert calls == [signal.SIGINT]
        assert signal.getsignal(signal.SIGINT) is custom
    finally:
        signal.signal(signal.SIGINT, previous)


@pytest.mark.parametrize('mode', ['default', 'custom', 'system_exit'])
@pytest.mark.parametrize('parent_error', [False, True])
def test_join_signal_replayed_after_close_with_original_error_precedence(tmp_path, monkeypatch, mode, parent_error):
    """Actual SIGINT during a real join is deferred until bounded cleanup."""
    kind = multiprocessing.get_context('spawn').Process
    original_join, original_close = kind.join, kind.close
    previous = signal.getsignal(signal.SIGINT)
    processes, closed, calls = [], [], []
    failure = LookupError('fixture operation error')

    def custom(signum, frame):
        assert signal.getsignal(signal.SIGINT) is custom
        assert closed, 'Custom policy must run after owned handles are closed'
        calls.append(signum)
        if mode == 'system_exit':
            raise SystemExit(23)

    def join(process, timeout=None):
        first = not processes
        if first:
            processes.append(process)
            os.kill(os.getpid(), signal.SIGINT)
        original_join(process, timeout)
        if first and parent_error:
            raise failure

    def close(process):
        pid = process.pid
        original_close(process)
        closed.append(pid)

    monkeypatch.setattr(kind, 'join', join)
    monkeypatch.setattr(kind, 'close', close)
    signal.signal(signal.SIGINT, signal.default_int_handler if mode == 'default' else custom)
    started = time.monotonic()
    try:
        expected = LookupError if parent_error else (
            KeyboardInterrupt if mode == 'default' else SystemExit if mode == 'system_exit' else None
        )
        task = partial(_block, tmp_path / 'child', True)
        if expected:
            with pytest.raises(expected) as raised:
                run_bounded_capture_task(task, timeout_seconds=1, shutdown_grace=0.2)
            if parent_error:
                assert raised.value is failure
        else:
            assert run_bounded_capture_task(task, timeout_seconds=1, shutdown_grace=0.2).status == 'timed_out'
        elapsed = time.monotonic() - started
        assert 1 <= elapsed < 5, elapsed
        pid = int((tmp_path / 'child').read_text())
        assert not Path(f'/proc/{pid}').exists()
        assert pid not in [p.pid for p in multiprocessing.active_children()]
        assert calls == ([] if mode == 'default' else [signal.SIGINT])
    finally:
        signal.signal(signal.SIGINT, previous)
        for process in processes:
            try:
                if process.is_alive():
                    process.kill()
                original_join(process, 2)
                original_close(process)
            except ValueError:
                pass
