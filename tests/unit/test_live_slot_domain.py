"""Bound player state by the pinned ET engine's 64 client slots, not traffic."""

import time

import pytest

from website.backend.services.live_state import LiveStateReducer


@pytest.mark.parametrize('slot', [0, 63, '0', '63'])
def test_boundary_player_slots_and_legacy_numeric_strings_remain_valid(slot):
    reducer = LiveStateReducer()
    for event in [
        {'type': 'TEAM_CHANGE', 'slot': slot, 'name': 'Player', 'team': 1},
        {'type': 'LIVE_AGGREGATE', 'slot': slot, 'kills': 1},
        {'type': 'LIVE_MOVEMENT', 'players': [{'slot': slot, 'x': 42, 'y': 99}]},
    ]:
        reducer.apply(dict(event, received_at=time.time()))
    player = reducer.snapshot()['roster']['axis'][0]
    assert player['slot'] == int(slot)
    assert player['live']['kills'] == 1 and player['pos']['x'] == 42


@pytest.mark.parametrize('slot', [-1, 64, 1022, True, False, 1.0, 'invalid', '-1', '64', '1022', '--1'])
@pytest.mark.parametrize('channel', ['CONNECT', 'BEGIN', 'TEAM_CHANGE', 'LIVE_AGGREGATE', 'LIVE_MOVEMENT', 'LIVE_KILL'])
def test_nonplayer_slots_cannot_allocate_player_state(slot, channel):
    reducer = LiveStateReducer()
    event = {'type': channel, 'slot': slot, 'victim_slot': slot, 'name': 'Invalid', 'team': 1,
             'players': [{'slot': slot, 'x': 42, 'y': 99}]}
    reducer.apply(dict(event, received_at=time.time()))
    # Snapshot hides telemetry without a roster entry; inspect all maps so the
    # test detects retained unreachable state, not merely absent rendered rows.
    assert not reducer._roster  # noqa: SLF001
    assert not reducer._live_stats  # noqa: SLF001
    assert not reducer._positions  # noqa: SLF001


def test_many_invalid_slots_cannot_grow_the_three_player_maps():
    reducer = LiveStateReducer()
    for slot in range(10000):
        for event in [
            {'type': 'CONNECT', 'slot': slot},
            {'type': 'LIVE_AGGREGATE', 'slot': slot},
            {'type': 'LIVE_MOVEMENT', 'players': [{'slot': slot, 'x': 0, 'y': 0}]},
        ]:
            reducer.apply(dict(event, received_at=time.time()))
    assert len(reducer._roster) == 64  # noqa: SLF001
    assert len(reducer._live_stats) == 64  # noqa: SLF001
    assert len(reducer._positions) == 64  # noqa: SLF001
    assert len(reducer.snapshot()['roster']['spectators']) == 64


def test_world_kill_remains_an_event_without_allocating_a_world_player():
    reducer = LiveStateReducer()
    reducer.apply({'type': 'TEAM_CHANGE', 'slot': 63, 'name': 'Victim', 'team': 2,
                   'received_at': time.time()})
    reducer.apply({'type': 'LIVE_KILL', 'killer_slot': 1022, 'victim_slot': 63,
                   'distance': -1, 'received_at': time.time()})
    snapshot = reducer.snapshot()
    assert snapshot['roster']['allies'][0]['live']['alive'] is False
    assert len(snapshot['recent_kills']) == 1
    kill = snapshot['recent_kills'][0]
    assert kill['killer_slot'] is None and kill['killer'] is None
    assert kill['victim_slot'] == 63 and kill['victim'] == 'Victim'


@pytest.mark.asyncio
async def test_asgi_keeps_world_feed_event_but_bounds_renderer_player_state(monkeypatch):
    import importlib
    import uuid

    import httpx
    from fastapi import FastAPI

    live = importlib.import_module('website.backend.routers.live')
    monkeypatch.setattr(live, '_UPSTREAM', '')
    monkeypatch.setattr(live, '_state', LiveStateReducer())
    monkeypatch.setattr(live, '_seq', 0)
    monkeypatch.setattr(live, '_events', type(live._events)(maxlen=live._BUFFER_MAX))  # noqa: SLF001
    monkeypatch.setattr(live, '_recent_livex_kills', {})
    secret = uuid.uuid4().hex
    monkeypatch.setenv('INTERNAL_API_SECRET', secret)
    events = []
    for slot in [0, 63, 64, True]:
        events.extend([
            {'type': 'TEAM_CHANGE', 'fields': {'slot': slot, 'name': 'Player', 'team': 1}},
            {'type': 'LIVE_AGGREGATE', 'fields': {'slot': slot, 'kills': 1}},
            {'type': 'LIVE_MOVEMENT', 'fields': {'players': [{'slot': slot, 'x': 42, 'y': 99}]}},
        ])
    events.append({'type': 'LIVE_KILL', 'fields': {'killer_slot': 1022, 'victim_slot': 63, 'distance': -1}})
    app = FastAPI()
    app.include_router(live.router, prefix='/api/live')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
        posted = await client.post('/api/live/events', json={'events': events},
                                   headers={'X-Internal-Token': secret})
        assert posted.status_code == 200, posted.text
        assert posted.json()['accepted'] == len(events)
        state = (await client.get('/api/live/state')).json()
        assert [p['slot'] for p in state['roster']['axis']] == [0, 63]
        assert all(p['live']['kills'] == 1 for p in state['roster']['axis'])
        assert state['recent_kills'][0]['killer'] is None
        feed = (await client.get('/api/live/feed', params={'types': 'LIVE_KILL'})).json()
        assert feed['events'][0]['killer_slot'] == 1022
