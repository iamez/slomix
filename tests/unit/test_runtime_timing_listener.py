"""Ordered strict timing listener composition and missing-close failure."""
from contextlib import contextmanager
from unittest.mock import Mock

import pytest

from shared import runtime_timing_listener as module
from shared.runtime_timing_controller import RuntimeTimingController


def driver():
    controller = RuntimeTimingController.__new__(RuntimeTimingController)
    controller._state = 'ready'  # noqa: SLF001
    for name in ('prepare_half', 'check_waiting', 'check_timing_waiting', 'bootstrap',
                 'complete', 'complete_timing', 'abort', 'captured_timing_match'):
        setattr(controller, name, Mock())
    return controller


@pytest.mark.parametrize('missing', [False, True])
def test_strict_six_exchange_order_and_no_export_on_missing_timing(monkeypatch, missing):
    controller = driver()
    calls = []

    @contextmanager
    def listen(path):
        yield object(), Mock()

    def accept(server, verify, waiting, wait):
        waiting.check_waiting()
        calls.append(wait)
        if missing and len(calls) == 3:
            raise TimeoutError('fixture timing absent')
        return object()

    monkeypatch.setattr(module, '_listener', listen)
    monkeypatch.setattr(module, '_accept', accept)
    if missing:
        with pytest.raises(TimeoutError, match='timing absent'):
            module.serve_timing_match(controller, object())
        controller.complete.assert_called_once()
        controller.captured_timing_match.assert_not_called()
        controller.abort.assert_called_once()
    else:
        result = module.serve_timing_match(controller, object())
        assert result is controller.captured_timing_match.return_value
        assert calls == [1800, 3600, 30, 1800, 3600, 30]
        assert [c.args[0] for c in controller.complete_timing.call_args_list] == [1, 2]
        controller.abort.assert_not_called()
