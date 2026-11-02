"""Do not invent a life owner for unknown or overlapping source windows."""

from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from tests.unit.test_proximity_journey_gaps import draw
from tests.unit.test_proximity_player_journey import ENEMY, SUBJECT, _call, _track
from website.backend.dependencies import get_db
from website.backend.routers.proximity_journey import router


@pytest.mark.asyncio
@pytest.mark.parametrize('windows,time,owner', [
    ([(0, 1000), (1000, 2000)], 1000, None),
    ([(0, 1500), (1000, 2000)], 1200, None),
    ([(0, None), (1000, 2000)], 1200, None),
    ([(0, 0)], 1200, None),
    ([(0, 1000), (1500, 2000)], 1200, None),
    ([(0, 1000), (1500, 2000)], None, None),
    ([(0, 1000), (1500, 2000)], 0, 0),
    ([(0, 1000), (1500, 2000)], 1000, 0),
    ([(0, 1000), (1500, 2000)], 1700, 1),
])
async def test_http_event_has_one_known_owner_or_explicit_unassigned(windows, time, owner):
    rows = [_track(SUBJECT, 'Synthetic', 'AXIS', 'MEDIC', start, end, [])
            for start, end in windows]
    kill = (time, SUBJECT, 'Synthetic', ENEMY, 'Enemy', 'gibbed', 0, '', '')
    db = AsyncMock()
    db.fetch_all.side_effect = [rows, [kill], [], [], [], [(time, 'build', 'bridge')]]
    app = FastAPI()
    app.include_router(router, prefix='/api')
    app.dependency_overrides[get_db] = lambda: db
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/api/proximity/player-journey', params={
            'session_date': '2099-01-01', 'map_name': 'supply',
            'round_number': 1, 'player_guid': SUBJECT})
    assert response.status_code == 200
    body = response.json()
    expected_count = int(owner is not None)
    # Two independent enumerations: actual life arrays and response accounting.
    assert sum(len(life['kills']) for life in body['lives']) == expected_count
    assert sum(len(life['objective_events']) for life in body['lives']) == expected_count
    assert body['event_assignment']['assigned'] == 2 * expected_count
    assert body['event_assignment']['unassigned'] == 2 * (1 - expected_count)
    assert body['event_assignment']['source_events'] == 2
    if owner is not None:
        assert body['lives'][owner]['kills'][0]['time'] == time
        assert body['unassigned_events'] == []
    else:
        assert len(body['unassigned_events']) == 2
        assert all(e['reason'] for e in body['unassigned_events'])
        assert all(e['time'] == time for e in body['unassigned_events'])
        assert 'attribution incomplete' in draw({'payload': body})['narrative']


@pytest.mark.asyncio
async def test_multiple_death_outcomes_are_preserved_not_last_row_wins():
    rows = [_track(SUBJECT, 'Synthetic', 'AXIS', 'MEDIC', 0, 1000, [])]
    deaths = [(t, ENEMY, 'Enemy', SUBJECT, 'Synthetic', outcome, 0, '', '')
              for t, outcome in [(200, 'revived'), (1000, 'gibbed')]]
    db = AsyncMock()
    db.fetch_all.side_effect = [rows, deaths, [], [], [], []]
    body = await _call(db)
    life = body['lives'][0]
    assert life['death'] is None
    assert [d['time'] for d in life['deaths']] == [200, 1000]
    assert body['summary']['deaths'] == 2
    assert 'multiple death outcomes' in draw({'payload': body})['narrative']
