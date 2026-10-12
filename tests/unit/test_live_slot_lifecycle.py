"""Live engine slots must not transfer one client's state to its successor."""

import importlib
import time
import uuid

import httpx
import pytest
from fastapi import FastAPI

from website.backend.services.live_state import LiveStateReducer


def apply(reducer, kind, **fields):
    reducer.apply({'type': kind, 'received_at': time.time(), **fields})


def reused_slot_events():
    return [
        {'type': 'TEAM_CHANGE', 'slot': 7, 'name': 'Old', 'team': 1},
        {'type': 'TEAM_CHANGE', 'slot': 2, 'name': 'Victim', 'team': 2},
        {'type': 'LIVE_AGGREGATE', 'slot': 7, 'kills': 5, 'damage_given': 900},
        {'type': 'LIVE_MOVEMENT', 'players': [{'slot': 7, 'x': 42, 'y': 99}]},
        {'type': 'LIVE_KILL', 'killer_slot': 7, 'victim_slot': 2, 'distance': 30},
        {'type': 'DISCONNECT', 'slot': 7},
        {'type': 'TEAM_CHANGE', 'slot': 7, 'name': 'New', 'team': 1},
    ]


def assert_reuse_snapshot(snapshot):
    player = snapshot['roster']['axis'][0]
    assert player['name'] == 'New'
    assert 'live' not in player
    assert 'pos' not in player
    assert snapshot['recent_kills'][0]['killer'] == 'Old'
    assert not any(key.startswith('_') for key in snapshot['recent_kills'][0])


def test_disconnect_clears_counters_positions_without_rewriting_history():
    reducer = LiveStateReducer()
    for event in reused_slot_events():
        reducer.apply(dict(event, received_at=time.time()))
    assert_reuse_snapshot(reducer.snapshot())


@pytest.mark.parametrize('role', ['killer', 'victim'])
@pytest.mark.parametrize('disconnect', [False, True])
@pytest.mark.parametrize('connected', [False, True])
def test_late_name_resolves_only_within_the_same_connection(role, disconnect, connected):
    reducer = LiveStateReducer()
    if connected:
        apply(reducer, 'CONNECT', slot=7)
    apply(reducer, 'LIVE_KILL', **{role + '_slot': 7}, distance=30)
    if disconnect:
        apply(reducer, 'DISCONNECT', slot=7)
    apply(reducer, 'TEAM_CHANGE', slot=7, name='Later', team=1)
    assert reducer.snapshot()['recent_kills'][0][role] == (None if disconnect else 'Later')


def test_name_change_does_not_rewrite_already_named_kill():
    reducer = LiveStateReducer()
    apply(reducer, 'TEAM_CHANGE', slot=7, name='Before', team=1)
    apply(reducer, 'LIVE_KILL', killer_slot=7, victim_slot=2, distance=30)
    apply(reducer, 'TEAM_CHANGE', slot=7, name='After', team=2)
    assert reducer.snapshot()['recent_kills'][0]['killer'] == 'Before'


@pytest.mark.asyncio
async def test_actual_ingest_and_state_asgi_payload_preserves_slot_identity(monkeypatch):
    live = importlib.import_module('website.backend.routers.live')
    monkeypatch.setattr(live, '_UPSTREAM', '')
    monkeypatch.setattr(live, '_state', LiveStateReducer())
    monkeypatch.setattr(live, '_seq', 0)
    monkeypatch.setattr(live, '_events', type(live._events)(maxlen=live._BUFFER_MAX))  # noqa: SLF001
    monkeypatch.setattr(live, '_recent_livex_kills', {})
    secret = uuid.uuid4().hex
    monkeypatch.setenv('INTERNAL_API_SECRET', secret)
    app = FastAPI()
    app.include_router(live.router, prefix='/api/live')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
        response = await client.post('/api/live/events', json={'events': [
            {'type': event['type'], 'fields': {k: v for k, v in event.items() if k != 'type'}}
            for event in reused_slot_events()
        ]},
                                     headers={'X-Internal-Token': secret})
        assert response.status_code == 200, response.text
        snapshot = await client.get('/api/live/state')
        assert snapshot.status_code == 200
        assert_reuse_snapshot(snapshot.json())


def test_disconnect_clears_telemetry_even_without_a_roster_announcement():
    reducer = LiveStateReducer()
    apply(reducer, 'LIVE_AGGREGATE', slot=7, kills=5)
    apply(reducer, 'LIVE_MOVEMENT', players=[{'slot': 7, 'x': 42, 'y': 99}])
    apply(reducer, 'DISCONNECT', slot=7)
    apply(reducer, 'TEAM_CHANGE', slot=7, name='New', team=1)
    player = reducer.snapshot()['roster']['axis'][0]
    assert 'live' not in player and 'pos' not in player
