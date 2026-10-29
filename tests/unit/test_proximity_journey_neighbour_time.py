"""Simultaneous source observations, not spatial minima across time buckets."""

import json

import pytest

from tests.unit.test_proximity_journey_gaps import draw
from tests.unit.test_proximity_journey_identity import request
from tests.unit.test_proximity_player_journey import MATE, SUBJECT, _track


@pytest.mark.asyncio
@pytest.mark.parametrize('mate_points,expected', [
    ([(0, 10, 0), (1000, 900, 0), (2000, 20, 0)], 900),
    ([(900, 10, 0), (1100, 20, 0)], None),
    ([(1000, 300, 400)], 500),
])
async def test_http_uses_same_timestamp_not_closest_place(mate_points, expected):
    rows = [_track(SUBJECT, 'Subject', 'AXIS', 'MEDIC', 0, 3000, [(1000, 0, 0)]),
            _track(MATE, 'Mate', 'AXIS', 'MEDIC', 0, 3000, mate_points)]
    response, _ = await request(rows)
    life = response.json()['lives'][0]
    sample = life['proximity_series'][0]
    assert sample['nearest_teammate'] == expected
    assert sample['observed_teammates'] == int(expected is not None)
    assert life['solo_pct'] == (None if expected is None else 100 if expected > 500 else 0)


@pytest.mark.asyncio
@pytest.mark.parametrize('conflict', [False, True])
async def test_one_guid_counts_once_or_is_explicitly_ambiguous(conflict):
    rows = [_track(SUBJECT, 'Subject', 'AXIS', 'MEDIC', 0, 2000, [(1000, 0, 0)]),
            _track(MATE, 'Old name', 'AXIS', 'MEDIC', 0, 2000, [(1000, 100, 0)]),
            _track(MATE, 'New name', 'AXIS', 'MEDIC', 0, 2000, [(1000, 200 if conflict else 100, 0)])]
    response, _ = await request(rows)
    sample = response.json()['lives'][0]['proximity_series'][0]
    assert sample['teammates_500u'] == int(not conflict)
    assert sample['ambiguous_players'] == int(conflict)
    assert sample['nearest_teammate'] == (None if conflict else 100)


@pytest.mark.asyncio
async def test_missing_coordinates_never_invent_a_neighbour_at_origin():
    mate = list(_track(MATE, 'Mate', 'AXIS', 'MEDIC', 0, 2000, []))
    mate[7] = json.dumps([{'time': 1000, 'event': 'sample'}])
    response, _ = await request([
        _track(SUBJECT, 'Subject', 'AXIS', 'MEDIC', 0, 2000, [(1000, 0, 0)]), tuple(mate)])
    sample = response.json()['lives'][0]['proximity_series'][0]
    assert sample['nearest_teammate'] is None


@pytest.mark.asyncio
async def test_radius_eligibility_uses_unrounded_distance():
    rows = [_track(SUBJECT, 'Subject', 'AXIS', 'MEDIC', 0, 2000, [(1000, 0, 0)]),
            _track(MATE, 'Mate', 'AXIS', 'MEDIC', 0, 2000, [(1000, 500.04, 0)])]
    response, _ = await request(rows)
    life = response.json()['lives'][0]
    assert life['proximity_series'][0]['nearest_teammate'] == 500.0
    assert life['proximity_series'][0]['teammates_500u'] == 0
    assert life['solo_pct'] == 100
    assert life['proximity_coverage'] == {'subject_samples': 1, 'samples_with_observed_teammate': 1}
    assert 'observed teammate >500u' in draw(life)['bands']


@pytest.mark.asyncio
async def test_points_outside_declared_track_lifetime_are_excluded():
    rows = [_track(SUBJECT, 'Subject', 'AXIS', 'MEDIC', 0, 2000, [(1000, 0, 0)]),
            _track(MATE, 'Mate', 'AXIS', 'MEDIC', 0, 500, [(1000, 10, 0)])]
    response, _ = await request(rows)
    assert response.json()['lives'][0]['proximity_series'][0]['nearest_teammate'] is None
