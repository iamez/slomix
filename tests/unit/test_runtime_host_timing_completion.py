"""Timing receipts remain distinct from stats and reject host-context mismatch."""
from contextlib import contextmanager

import pytest

from shared import runtime_host_timing_completion as timing
from shared.runtime_timing_completion import TimingCompletion
from tests.unit.test_runtime_host_completion import (  # noqa: F401
    approved,
    channels,
    child,
    pin,
    prepared,
    ready,
)


@pytest.fixture
def timing_ready(ready, monkeypatch):  # noqa: F811 -- imported pytest fixture
    host, epoch, accepted, state = ready
    state['wire'] = TimingCompletion(accepted.delivery.dispatch.generation, 'round.json', 42).encode()

    @contextmanager
    def channel(*args, **kwargs):
        class Channel:
            def receive_line(self):
                return state['wire']
        try:
            yield Channel()
        finally:
            state['closed'] += 1
    monkeypatch.setattr(timing, 'process_channel', channel)
    return host, epoch, accepted, state


def receive(context, pin):  # noqa: F811 -- imported pytest fixture
    host, epoch, accepted, _ = context
    return timing.receive_timing_completion(None, host, pin, epoch,
                                           accepted=accepted, expected_filename='round.json')


def test_receipt_is_separate_and_replay_preserves_original(timing_ready, pin):  # noqa: F811
    host, epoch, accepted, _ = timing_ready
    result = receive(timing_ready, pin)
    timing.verify_timing_completion(host, pin, epoch, accepted=accepted,
                                   completed=result, expected_filename='round.json')
    paths = list(host.rglob(timing.RECEIPT))
    assert len(paths) == 1
    original = paths[0].read_bytes(), paths[0].stat().st_ino
    assert not list(host.rglob('stats-writer-closed.txt'))
    with pytest.raises(FileExistsError):
        receive(timing_ready, pin)
    assert (paths[0].read_bytes(), paths[0].stat().st_ino) == original


@pytest.mark.parametrize('field', ['generation', 'filename', 'protocol'])
def test_mismatched_notice_never_persists(timing_ready, pin, field):  # noqa: F811
    host, _, accepted, state = timing_ready
    if field == 'generation':
        state['wire'] = TimingCompletion('f' * 32, 'round.json', 42).encode()
    elif field == 'filename':
        state['wire'] = TimingCompletion(accepted.delivery.dispatch.generation, 'other.json', 42).encode()
    else:
        state['wire'] = state['wire'].replace('slomix_timing_closed_v1', 'slomix_stats_closed_v1')
    with pytest.raises(ValueError):
        receive(timing_ready, pin)
    assert not list(host.rglob(timing.RECEIPT))
    assert state['closed'] == 1
