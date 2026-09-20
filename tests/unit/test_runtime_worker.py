"""Real spawned-child proofs; no SSH, server, service or database operations."""

import multiprocessing
import os
import signal
import time
from functools import partial
from pathlib import Path

import pytest

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


def test_unpicklable_task_fails_without_child():
    """Spawn preparation failure does not leak a task process."""
    before = {p.pid for p in multiprocessing.active_children()}
    with pytest.raises((AttributeError, TypeError)):
        run_bounded_capture_task(lambda: None, timeout_seconds=1)
    assert {p.pid for p in multiprocessing.active_children()} == before


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
