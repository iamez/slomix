"""Player identity and per-life team contracts through actual ASGI requests."""

from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from tests.unit.test_proximity_player_journey import ENEMY, MATE, SUBJECT, _track
from website.backend.dependencies import get_db
from website.backend.routers.proximity_journey import router


async def request(rows, guid=SUBJECT):
    db = AsyncMock()
    db.fetch_all.side_effect = [rows, [], [], [], [], []]
    app = FastAPI()
    app.include_router(router, prefix='/api')
    app.dependency_overrides[get_db] = lambda: db
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/api/proximity/player-journey', params={
            'session_date': '2099-01-01', 'map_name': 'supply',
            'round_number': 1, 'player_guid': guid})
    return response, db


@pytest.mark.asyncio
async def test_colliding_prefix_refuses_to_combine_players():
    other = SUBJECT[:8] + '0' * 24
    rows = [_track(g, 'Same display name', 'AXIS', 'MEDIC', 0, 1000, [])
            for g in (SUBJECT, other)]
    response, db = await request(rows, SUBJECT[:8])
    assert response.status_code == 409
    assert 'ambiguous' in response.json()['detail'].lower()
    assert db.fetch_all.await_count == 1
    full, _ = await request(rows)
    assert full.status_code == 200
    assert full.json()['player']['guid'] == SUBJECT
    assert len(full.json()['lives']) == 1


@pytest.mark.asyncio
async def test_unique_prefix_keeps_all_name_changed_lives():
    rows = [_track(SUBJECT, name, 'AXIS', 'MEDIC', start, start + 1000, [])
            for name, start in [('Old', 0), ('New', 2000)]]
    response, _ = await request(rows, SUBJECT[:8].lower())
    assert response.status_code == 200
    assert len(response.json()['lives']) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('second_team', ['ALLIES', None, 'SPECTATOR'])
async def test_neighbours_use_each_life_team_not_first_life(second_team):
    rows = [
        _track(SUBJECT, 'Subject', 'AXIS', 'MEDIC', 0, 1000, [(0, 0, 0)]),
        _track(SUBJECT, 'Subject', second_team, 'MEDIC', 2000, 3000, [(2000, 0, 0)]),
        _track(MATE, 'Axis', 'AXIS', 'MEDIC', 0, 3000, [(0, 300, 0), (2000, 300, 0)]),
        _track(ENEMY, 'Allies', 'ALLIES', 'MEDIC', 0, 3000, [(0, 900, 0), (2000, 900, 0)]),
    ]
    response, _ = await request(rows)
    assert response.status_code == 200
    first, second = response.json()['lives']
    assert first['proximity_series'][0]['nearest_teammate'] == 300
    assert second['team'] == second_team
    if second_team == 'ALLIES':
        assert second['proximity_series'][0]['nearest_teammate'] == 900
        assert second['proximity_series'][0]['nearest_enemy'] == 300
        assert second['solo_pct'] == 100
    else:
        assert second['proximity_series'] == []
        assert second['solo_pct'] is None
        assert 'team' in second['proximity_unavailable'].lower()


@pytest.mark.asyncio
async def test_unknown_other_team_is_not_invented_enemy():
    rows = [_track(SUBJECT, 'Subject', 'AXIS', 'MEDIC', 0, 1000, [(0, 0, 0)]),
            _track(MATE, 'Unknown', None, 'MEDIC', 0, 1000, [(0, 10, 0)])]
    response, _ = await request(rows)
    sample = response.json()['lives'][0]['proximity_series'][0]
    assert sample['nearest_enemy'] is None
    assert sample['enemies_500u'] == 0
