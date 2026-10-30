"""Parent pacing, signal drain and wiring; no services or application DB."""

import json
import os
import selectors
import signal
import subprocess
import sys
import threading
import time
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import pytest

from shared import runtime_proximity_supervisor as module
from shared.runtime_worker import run_bounded_owned_task


class Stop:
    def __init__(self, count):
        self.delays = []
        self.count = count

    def is_set(self):
        return len(self.delays) >= self.count

    def wait(self, delay):
        self.delays.append(delay)


def test_backoff_reset_and_always_wait():
    stop = Stop(5)
    outcomes = iter(('failed', 'timed_out', 'failed', 'completed', 'failed'))
    states = []
    module.supervise(None, stop, runner=lambda *_a, **_k: SimpleNamespace(status=next(outcomes)),
                     reporter=states.append, retry_seconds=2, max_retry_seconds=5, poll_seconds=7)
    assert stop.delays == [2, 4, 5, 7, 2]
    assert states[-1]['status'] == 'stopped'
    assert [s['consecutive_failures'] for s in states if 'consecutive_failures' in s] == [1, 2, 3, 0, 1]


def test_no_second_child_after_reaping_error():
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise RuntimeError('could not reap')
    with pytest.raises(RuntimeError, match='could not reap'):
        module.supervise(None, Stop(2), runner=fail, reporter=lambda _state: None)
    assert calls == [1]


@pytest.mark.parametrize('options', [dict(timeout_seconds=0), dict(shutdown_grace=0.001),
    dict(poll_seconds=True), dict(retry_seconds=float('nan')), dict(max_retry_seconds=float('inf')),
    dict(retry_seconds=10, max_retry_seconds=1)])
def test_bad_limits_before_child(options):
    with pytest.raises(ValueError):
        module.supervise(None, Stop(0), **options)


def test_signal_during_wait_interrupts_and_restores_handlers():
    previous = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
    def report(state):
        if state['status'] == 'completed':
            os.kill(os.getpid(), signal.SIGTERM)  # Test-owned parent only.
    module.supervise_with_signals(None, reporter=report,
        runner=lambda *_a, **_k: SimpleNamespace(status='completed'), poll_seconds=3600)
    assert {s: signal.getsignal(s) for s in previous} == previous


def signal_parent_then_block(marker, parent, signum):
    marker.write_text(str(os.getpid()))
    os.kill(parent, signum)
    time.sleep(60)


@pytest.mark.parametrize('signum', [signal.SIGTERM, signal.SIGINT])
def test_real_child_signal_requests_drain_then_timeout_reaps(tmp_path, signum):
    marker = tmp_path / 'child'
    states, calls = [], []
    previous = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}

    def run(*args, **kwargs):
        calls.append(1)
        return run_bounded_owned_task(partial(signal_parent_then_block, marker, os.getpid(), signum),
                                      **kwargs)

    module.supervise_with_signals(None, runner=run, reporter=states.append,
                                 timeout_seconds=2, shutdown_grace=0.1)
    child_pid = int(marker.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(child_pid, 0)
    assert calls == [1]
    assert states[-1]['status'] == 'stopped'
    assert states[-2]['status'] == 'timed_out' and states[-2]['next_delay_seconds'] is None
    assert {s: signal.getsignal(s) for s in previous} == previous
    print(f'Parent signal proof: signal={signum}, stopped after one reaped timed-out child')


def test_main_uses_isolated_supervisor_after_config_validation(monkeypatch):
    from shared import runtime_proximity_main as main
    from shared.runtime_proximity_config import ProximityProcessConfig
    assert main.ProximityProcessConfig is ProximityProcessConfig
    assert ProximityProcessConfig.__module__ == 'shared.runtime_proximity_config'
    monkeypatch.setenv('RUNTIME_PROXIMITY_WORKER_ENABLED', 'true')
    config = object()
    monkeypatch.setattr(ProximityProcessConfig, 'from_environment', lambda: config)
    seen = []
    monkeypatch.setattr(main, 'supervise_with_signals', seen.append)
    main.run()
    assert seen == [config]


def test_stop_already_set_never_spawns():
    stop = threading.Event()
    stop.set()
    def fail(*args, **kwargs):
        pytest.fail('must not spawn')
    module.supervise(Path('/unused'), stop, runner=fail, reporter=lambda _state: None)


def test_real_module_entrypoint_spawns_then_sigterm_stops_on_db_outage(tmp_path):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('POSTGRES_', 'RUNTIME_PROXIMITY_', 'BOT_ENVIRONMENT'))}
    env.update(BOT_ENVIRONMENT='dev', RUNTIME_PROXIMITY_WORKER_ENABLED='true',
               RUNTIME_PROXIMITY_DEV_HANDOVER_CONFIRMED='true', RUNTIME_PROXIMITY_ROOT=str(tmp_path),
               RUNTIME_PROXIMITY_SOURCE_ID='fixture', RUNTIME_PROXIMITY_GAMETIMES_DIR=str(tmp_path),
               POSTGRES_HOST=str(tmp_path / 'nonexistent-socket'), POSTGRES_PORT='5432',
               POSTGRES_DATABASE='proof', POSTGRES_USER='fixture', RUNTIME_PROXIMITY_DB_SCHEMA='proof')
    lines = []
    with subprocess.Popen([sys.executable, '-u', '-m', 'shared.runtime_proximity_main'],
                          env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0) as process:
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    assert selector.select(timeout=max(0, deadline - time.monotonic())), 'No supervisor output'
                    line = process.stdout.readline()
                    assert line, 'Entrypoint exited before child outcome'
                    state = json.loads(line)
                    lines.append(state)
                    if state['status'] == 'failed' and 'consecutive_failures' in state:
                        break
                else:
                    pytest.fail('No failed child observed')
            process.send_signal(signal.SIGTERM)
            remaining, errors = process.communicate(timeout=10)
            lines.extend(json.loads(line) for line in remaining.splitlines())
            assert process.returncode == 0 and not errors
            assert lines[-1]['status'] == 'stopped'
            assert sum(s['status'] == 'batch_running' for s in lines) == 1
            print('Module process proof: spawned child sees unavailable local DB, parent backs off, SIGTERM exits cleanly')
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
                process.communicate(timeout=70)
