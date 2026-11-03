"""Stats progress is independent of the per-half timing queues."""
from contextlib import contextmanager
from unittest.mock import Mock

import pytest

from shared import runtime_timing_listener as module
from shared.runtime_timing_controller import RuntimeTimingController


@pytest.mark.parametrize('missing', [False, True])
def test_stats_finish_before_timing_wait_and_missing_stays_pending(monkeypatch, missing):
    controller = RuntimeTimingController.__new__(RuntimeTimingController)
    controller._state = 'ready'  # noqa: SLF001
    for name in ('prepare_half', 'check_waiting', 'check_timing_waiting', 'bootstrap', 'captured_match',
                 'complete', 'complete_timing', 'abort', 'captured_timing_match'):
        setattr(controller, name, Mock())
    controller.timing_status = Mock(return_value={1: 'pending' if missing else 'captured', 2: 'captured'})
    calls = []

    @contextmanager
    def listen(path):
        yield path, Mock()

    def accept(server, verify, waiting, wait):
        waiting.check_waiting()
        calls.append(wait)
        if len(calls) >= 5:
            assert controller.complete.call_count == 2
        if missing and len(calls) == 5:
            raise TimeoutError('fixture timing absent')
        return object()

    monkeypatch.setattr(module, '_listener', listen)
    monkeypatch.setattr(module, '_accept', accept)
    result = module.serve_timing_match(controller, 'stats', timing_socket_paths={1: 't1', 2: 't2'})
    assert result.stats is controller.captured_match.return_value
    assert calls == [1800, 3600, 1800, 3600, 30, 30]
    controller.abort.assert_not_called()
    if missing:
        assert result.timing_match is None
        controller.captured_timing_match.assert_not_called()
    else:
        assert result.timing_match is controller.captured_timing_match.return_value
