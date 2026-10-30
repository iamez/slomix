"""Exercise shipped legacy marker placement, not a duplicate implementation."""

import pytest

from tests.unit.test_proximity_journey_gaps import draw


@pytest.mark.parametrize('time,visible', [(-100, False), (200, True), (600, False),
                                       (800, True), (1000, True), (1400, False)])
def test_marker_never_crosses_segment_boundary_or_extrapolates(time, visible):
    path = [dict(t=t, x=t, y=0, break_before=t == 800)
            for t in (0, 400, 800, 1200)]
    result = draw(dict(path=path, kills=[dict(time=time)], death=dict(time=time),
                       proximity_series=[]))
    assert len([fill for fill in result['fills'] if len(fill) == 3]) == int(visible)
    assert len([stroke for stroke in result['strokes'] if len(stroke) == 4]) == int(visible)


def test_coordinate_less_boundary_does_not_let_marker_snap_across_gap():
    path = [dict(t=0, x=0, y=0), dict(t=400, x=None, y=None, break_before=True),
            dict(t=800, x=800, y=0)]
    result = draw(dict(path=path, kills=[dict(time=600)], proximity_series=[]))
    assert not any(len(fill) == 3 for fill in result['fills'])


def test_shared_boundary_timestamp_is_not_a_unique_segment():
    path = [dict(t=0, x=0, y=0), dict(t=400, x=400, y=0),
            dict(t=400, x=900, y=0, event='capture_resume'), dict(t=800, x=950, y=0)]
    result = draw(dict(path=path, kills=[dict(time=400)], proximity_series=[]))
    assert not any(len(fill) == 3 for fill in result['fills'])
