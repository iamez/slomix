"""Controller timing failure preserves captured stats and never retries."""
from threading import Lock
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from shared import runtime_timing_controller as module


def controller():
    value = module.RuntimeTimingController.__new__(module.RuntimeTimingController)
    value._lock = Lock()  # noqa: SLF001
    value._state = 'complete'  # noqa: SLF001
    value._timing_accepted = {1: SimpleNamespace(delivery=SimpleNamespace(  # noqa: SLF001
        dispatch=SimpleNamespace(generation='a' * 32)))}
    value._timing_attempted = set()  # noqa: SLF001
    value._timings = {}  # noqa: SLF001
    value._timing_names = {1: 'round.json'}  # noqa: SLF001
    value._host = value._pin = value._epoch = None  # noqa: SLF001
    value._verify_context = Mock()  # noqa: SLF001
    return value


def test_failed_timing_attempt_preserves_stats_state_and_closes_socket(monkeypatch):
    value = controller()
    socket = Mock()
    receive = Mock(side_effect=ValueError('fixture invalid completion'))
    monkeypatch.setattr(module, 'receive_timing_completion', receive)
    with pytest.raises(ValueError, match='fixture'):
        value.complete_timing(1, socket)
    assert value.state == 'complete'
    assert value.timing_status() == {1: 'failed', 2: 'pending'}
    socket.close.assert_called_once()
    with pytest.raises(ValueError, match='already attempted'):
        value.complete_timing(1, Mock())
    receive.assert_called_once()


def test_bootstrap_hook_preserves_distinct_halves():
    value = controller()
    accepted = SimpleNamespace(delivery=SimpleNamespace(dispatch=SimpleNamespace(
        identity=SimpleNamespace(round_number=2))))
    value._record_bootstrap(accepted)  # noqa: SLF001
    assert value._timing_accepted[2] is accepted  # noqa: SLF001
    assert 1 in value._timing_accepted  # noqa: SLF001


def test_successful_timing_capture_is_recorded(monkeypatch, tmp_path):
    value = controller()
    value._spool = tmp_path  # noqa: SLF001
    value._timing_root = tmp_path / 'capture'  # noqa: SLF001
    completed, captured = object(), object()
    monkeypatch.setattr(module, 'receive_timing_completion', Mock(return_value=completed))
    publish = Mock(return_value=captured)
    monkeypatch.setattr(module, 'capture_closed_timing', publish)
    assert value.complete_timing(1, Mock()) is captured
    assert value.timing_status() == {1: 'captured', 2: 'pending'}
    assert publish.call_args.kwargs['completed'] is completed
    assert value.state == 'complete'



def test_close_failure_cannot_export_timing_success(monkeypatch, tmp_path):
    value = controller()
    value._spool = tmp_path  # noqa: SLF001
    value._timing_root = tmp_path / 'capture'  # noqa: SLF001
    monkeypatch.setattr(module, 'receive_timing_completion', Mock(return_value=object()))
    monkeypatch.setattr(module, 'capture_closed_timing', Mock(return_value=object()))
    socket = Mock()
    socket.close.side_effect = OSError('fixture close failure')
    with pytest.raises(OSError, match='fixture close'):
        value.complete_timing(1, socket)
    assert value.timing_status() == {1: 'failed', 2: 'pending'}
    assert value.state == 'complete'
    socket.close.assert_called_once()
