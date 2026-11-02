"""Source endpoint timing through actual ASGI and the shipped legacy renderer."""

import json
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from tests.unit.test_proximity_journey_gaps import draw
from tests.unit.test_proximity_player_journey import SUBJECT, _track
from website.backend.dependencies import get_db
from website.backend.routers.proximity_journey import router


async def request(rows):
    db = AsyncMock()
    db.fetch_all.side_effect = [rows, [], [], [], [], []]
    app = FastAPI()
    app.include_router(router, prefix='/api')
    app.dependency_overrides[get_db] = lambda: db
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/api/proximity/player-journey', params={
            'session_date': '2099-01-01', 'map_name': 'supply',
            'round_number': 1, 'player_guid': SUBJECT})
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
@pytest.mark.parametrize('start,end,expected', [(0, 1000, 1000), (100, 100, 0),
                         (100, 0, None), (100, None, None), (100, 50, None),
                         (-1, 100, None), (None, 100, None)])
async def test_raw_spans_do_not_use_stale_duration_or_unknown_zero(start, end, expected):
    row = list(_track(SUBJECT, 'Synthetic', 'AXIS', 'MEDIC', 0, 1000, []))
    row[4:7] = [start, end, 99999]
    body = await request([tuple(row)])
    life = body['lives'][0]
    assert life['duration_ms'] == 99999  # compatibility only, never displayed
    assert life['raw_duration_ms'] == expected
    assert body['elapsed_time_quality']['active_time_verified'] is False
    assert body['summary']['avg_life_s'] is None
    assert body['summary']['raw_span_samples'] == (0 if expected is None else 1)
    assert body['summary']['avg_raw_span_s'] == (None if expected is None else expected / 1000)
    assert 'lived' not in life['narrative']
    result = draw({'payload': body})
    assert 'avg life' not in result['status']
    assert 'pauses' in result['status']
    assert '100s' not in result['lives']
    assert ('raw span unavailable' in result['lives']) is (expected is None)


@pytest.mark.asyncio
async def test_empty_has_clock_quality_not_zero_active_time():
    body = await request([])
    assert body['elapsed_time_quality']['active_time_verified'] is False
    assert body['summary']['raw_span_samples'] == 0
    assert body['summary']['avg_raw_span_s'] is None


@pytest.mark.asyncio
async def test_mixed_endpoints_average_eligible_spans_only():
    rows = [_track(SUBJECT, 'Synthetic', 'AXIS', 'MEDIC', a, b, [])
            for a, b in [(0, 1000), (1000, 4000), (100, 0)]]
    body = await request(rows)
    assert body['summary']['avg_raw_span_s'] == (1000 + 3000) / 2 / 1000
    assert body['summary']['raw_span_samples'] == 2


@pytest.mark.asyncio
async def test_resume_marker_does_not_turn_raw_span_into_active_time():
    row = list(_track(SUBJECT, 'Synthetic', 'AXIS', 'MEDIC', 0, 1000, []))
    row[7] = json.dumps([{'time': 0, 'x': 0, 'y': 0, 'event': 'sample'},
                         {'time': 800, 'x': 100, 'y': 0, 'event': 'capture_resume'}])
    body = await request([tuple(row)])
    life = body['lives'][0]
    assert life['raw_duration_ms'] == 1000  # no guessed pause subtraction
    assert 'may include pauses' in life['narrative']
    assert life['proximity_series'] == []  # prior safety gate remains
    assert body['elapsed_time_quality']['active_time_verified'] is False


def test_legacy_render_does_not_fall_back_to_old_duration():
    body = {'player': {'name': 'Synthetic'}, 'summary': {'lives': 1, 'avg_life_s': 99999},
            'lives': [{'life_index': 1, 'duration_ms': 99999000, 'path': [], 'kills': [],
                       'narrative': 'lived 99999s'}]}
    result = draw({'payload': body})
    assert 'raw span unavailable' in result['lives']
    assert 'average raw span unavailable' in result['status']
    assert '99999' not in result['status'] + result['lives'] + result['narrative']
    assert 'timing unverified' in result['narrative']
