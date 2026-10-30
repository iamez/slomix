"""Journey boundary safety through the actual HTTP route; synthetic DB rows."""

import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from tests.unit.test_proximity_player_journey import MATE, SUBJECT, _track
from website.backend.dependencies import get_db
from website.backend.routers.proximity_journey import _downsample_path, router


def point(time, event='sample'):
    return dict(time=time, x=time, y=0, event=event)


@pytest.mark.parametrize('marker_index', [0, 1, 2])
def test_downsample_preserves_whole_boundary_group(marker_index):
    group = [point(200), point(200)]
    group.insert(marker_index, point(200, 'capture_resume'))
    result = _downsample_path([point(0), *group, point(400), point(800)], 400)
    boundary = [p for p in result if p['t'] == 200]
    assert any(p['event'] == 'capture_resume' for p in boundary)
    assert all(p['break_before'] for p in boundary)
    strokes = draw(dict(path=result, proximity_series=[]))['strokes']
    assert len(strokes) == 1  # only the outgoing post-boundary segment
    assert strokes[0][0][0] == 200


def draw(life):
    result = subprocess.run(
        [shutil.which('node'), '--experimental-vm-modules', 'tests/js/journey_capture_harness.mjs'],
        input=json.dumps(life), text=True, capture_output=True,
        cwd=Path(__file__).resolve().parents[2], timeout=15,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_actual_canvas_does_not_bridge_resume_and_names_unavailability():
    path = _downsample_path([point(0), point(400), point(600, 'capture_resume'),
                             point(1000), point(1400)], 400)
    result = draw(dict(path=path, proximity_series=[],
                       proximity_unavailable='Proximity unavailable: capture interruption'))
    assert len(result['strokes']) == 3  # 0->400, 600->1000, 1000->1400
    assert all(abs(line[1][0] - line[0][0]) <= 400 for line in result['strokes'])
    assert not any(line[0][0] == 400 and line[1][0] == 600 for line in result['strokes'])
    assert 'capture interruption' in result['caption']


def test_actual_timeline_does_not_label_missing_teammate_solo():
    result = draw(dict(path=[], spawn_time_ms=0, death_time_ms=1000,
                       proximity_series=[dict(t=0, nearest_teammate=None, nearest_enemy=None)]))
    assert 'teammate coverage unavailable' in result['bands']
    assert '• solo' not in result['bands']


def test_coordinate_less_boundary_does_not_invent_origin_or_connect_canvas():
    path = _downsample_path([point(0), {'time': 200, 'event': 'capture_resume'}, point(800)], 400)
    assert path[1]['x'] is None and path[1]['break_before']
    assert draw(dict(path=path, proximity_series=[]))['strokes'] == []


@pytest.mark.asyncio
@pytest.mark.parametrize('marked_guid', [SUBJECT, MATE, None])
async def test_http_gap_is_unavailable_not_solo(marked_guid):
    rows = []
    for guid in (SUBJECT, MATE):
        row = list(_track(guid, 'Synthetic', 'AXIS', 'MEDIC', 0, 2000,
                          [(0, 0, 0), (1000, 0, 0)]))
        if guid == marked_guid:
            row[7] = json.dumps([point(0), point(200, 'capture_resume'), point(400)])
        elif guid == MATE:
            row[7] = '[]'  # absence is not observed solitude
        rows.append(tuple(row))
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
    life = response.json()['lives'][0]
    assert life['solo_pct'] is None
    assert 'alone' not in life['narrative']
    if marked_guid:
        assert life['proximity_series'] == []
        assert 'capture' in life['proximity_unavailable']
        rendered = draw(life)
        assert life['proximity_unavailable'] == rendered['caption']
        if marked_guid == SUBJECT:
            assert rendered['strokes'] == []
    else:
        assert all(s['nearest_teammate'] is None for s in life['proximity_series'])
