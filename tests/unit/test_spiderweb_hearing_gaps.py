"""Capture coverage and hearing reconstruction coverage are separate facts."""
import pytest

from website.backend.services.round_web_service import CapturePolicy, build_snapshot, load_round_information_state


def tracks():
    return {'H': [('H', 'Holder', 'AXIS', 'MEDIC', 0, None,
                   [{'time': 1000, 'x': 100, 'y': 0, 'z': 0, 'health': 100}], 'supply', 1)]}


class ShotDB:
    def __init__(self, origin=(0, 0, 0)):
        self.origin = origin

    async def fetch_all(self, query, params):
        if 'FROM proximity_shot_fired' in query:
            assert 'origin_x IS NOT NULL' not in query, 'invalid captured origins must remain visible as gaps'
            return [('S', 1000, *self.origin)]
        if 'FROM rounds r' in query:
            return [(100,)]
        return []


@pytest.mark.asyncio
@pytest.mark.parametrize('missing_tracks,origin', [(True, (0, 0, 0)), (False, (0, None, 0))])
async def test_loader_discloses_reconstruction_gap_despite_enabled_capture(missing_tracks, origin):
    lives = tracks()
    payload = await load_round_information_state(
        ShotDB(origin), 1, 1000, build_snapshot(lives, 1000), {},
        CapturePolicy(capabilities={'shot_fired': 'enabled'}), None if missing_tracks else lives,
    )
    holder = payload['holders']['H']
    assert holder['beliefs'] == []
    assert 'gunfire_reconstruction' in holder['unavailable']
    assert 'gunfire' not in holder['unavailable']


@pytest.mark.parametrize('region,reason,admitted', [
    (None, 'missing_listener', False),
    ((0, 0, 0, -1), 'invalid_coordinates', False),
    ((float('nan'), 0, 0, 0), 'invalid_coordinates', False),
    ((1300, 0, 0, 100), 'uncertain_range', False),
    ((1430, 0, 0, 100), 'uncertain_range', False),
    ((1431, 0, 0, 100), None, False),
    ((1230, 0, 0, 100), None, True),
])
def test_reconstruction_distinguishes_uncertain_boundary_from_definite_range(region, reason, admitted):
    from website.backend.services.information_state import Region, gunfire_beliefs, reconstruct_gunfire

    def locate(holder, time):
        assert (holder, time) == ('H', 1000)
        return Region(*region) if region else None

    shots = [('S', 1000, 0, 0, 0)]
    result = reconstruct_gunfire(shots, iter(['H', 'S']), audible_radius=1330, locate=locate)
    assert bool(result.beliefs) is admitted
    assert result.unavailable == ({'H': (reason,)} if reason else {})
    assert gunfire_beliefs(shots, ['H', 'S'], audible_radius=1330, locate=locate) == result.beliefs
    if admitted:
        assert result.beliefs[0].subject_guid is None
        assert result.beliefs[0].region.radius > 0


@pytest.mark.parametrize('coordinate', [None, 'invalid', float('nan'), float('inf')])
def test_invalid_shot_coordinates_mark_only_other_holders(coordinate):
    from website.backend.services.information_state import reconstruct_gunfire

    result = reconstruct_gunfire([('S', 1000, 0, coordinate, 0)], ['H', 'S'],
                                audible_radius=1330, locate=lambda *_: None)
    assert result.beliefs == []
    assert result.unavailable == {'H': ('invalid_coordinates',)}


def test_partial_reconstruction_keeps_good_evidence_and_deduplicates_reasons_per_holder():
    from website.backend.services.information_state import Region, reconstruct_gunfire

    result = reconstruct_gunfire([('S', t, 0, 0, 0) for t in [1000, 2000, 3000]], ['H', 'FAR'],
                                audible_radius=1330,
                                locate=lambda h, t: Region(9000, 0, 0, 0) if h == 'FAR'
                                else Region(0, 0, 0, 0) if t == 1000 else None)
    assert len(result.beliefs) == 1
    assert result.unavailable == {'H': ('missing_listener',)}


@pytest.mark.asyncio
async def test_unknown_capture_and_missing_reconstruction_remain_separate():
    lives = tracks()
    payload = await load_round_information_state(
        ShotDB(), 1, 1000, build_snapshot(lives, 1000), {}, CapturePolicy(), None,
    )
    unavailable = payload['holders']['H']['unavailable']
    assert 'capture cannot be proven' in unavailable['gunfire']
    assert 'listener position' in unavailable['gunfire_reconstruction']


@pytest.mark.asyncio
@pytest.mark.parametrize('origin,future,reason', [
    ((0, None, 0), False, 'coordinates'),
    ((None, 0, 0), False, 'coordinates'),
    ((0, 0, 0), True, 'listener position'),
])
async def test_real_asgi_retains_gap_for_player_and_team_without_claiming_capture_failed(monkeypatch, origin, future, reason):
    import json

    import httpx
    from fastapi import FastAPI

    from website.backend.dependencies import get_db
    from website.backend.routers.replay_router import router
    from website.backend.services import line_of_sight

    class RouteDB(ShotDB):
        async def fetch_all(self, query, params):
            if 'SELECT 1 FROM rounds WHERE' in query:
                return [(1,)]
            if 'f.capabilities' in query:
                return [(json.dumps({'capabilities': {'shot_fired': 'enabled'}}),)]
            if 'SELECT pt.player_guid, pt.player_name, pt.team, pt.player_class' in query:
                rows = tracks()['H']
                if future:
                    rows[0][6][0]['time'] = 1100
                return rows
            return await super().fetch_all(query, params)

    monkeypatch.setattr(line_of_sight, '_DEFAULT', line_of_sight.GeometryProvider('/nonexistent/hearing-fixture'))
    app = FastAPI()
    app.include_router(router, prefix='/api')
    async def fixture_db():
        return RouteDB(origin)

    app.dependency_overrides[get_db] = fixture_db
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
        for pov in ['H', 'team:AXIS']:
            response = await client.get('/api/replay/round/1/web', params={'t': 2000, 'pov': pov})
            assert response.status_code == 200, response.text
            payload = response.json()
            holder = payload['information_state']['holders'][pov]
            assert holder['beliefs'] == []
            assert reason in holder['unavailable']['gunfire_reconstruction']
            assert 'not proof of hearing' in holder['unavailable']['gunfire_reconstruction']
            assert 'gunfire' not in holder['unavailable']
            assert payload['capture_policy']['capabilities']['shot_fired'] == 'enabled'


@pytest.mark.asyncio
@pytest.mark.parametrize('state', ['dead', 'not_joined', 'no_sample', 'no_history'])
@pytest.mark.parametrize('origin', [(0, 0, 0), (None, 0, 0)])
async def test_event_time_inactive_listener_is_not_a_reconstruction_failure(state, origin):
    lives = tracks()
    if state == 'dead':
        old = lives['H'][0]
        lives['H'] = [(*old[:5], 1000, *old[6:]),
                      ('H', 'Holder', 'AXIS', 'MEDIC', 1500, None,
                       [{'time': 1500, 'x': 100, 'y': 0, 'z': 0}], 'supply', 2)]
    elif state == 'not_joined':
        old = lives['H'][0]
        lives['H'] = [(*old[:4], 1500, old[5],
                       [{'time': 1500, 'x': 100, 'y': 0, 'z': 0}], *old[7:])]
    elif state == 'no_sample':
        lives['H'][0][6][0]['time'] = 1500
    payload = await load_round_information_state(
        ShotDB(origin), 1, 2000, build_snapshot(lives, 2000), {},
        CapturePolicy(capabilities={'shot_fired': 'enabled'}),
        None if state == 'no_history' else lives,
    )
    holder = payload['holders']['H']
    assert holder['beliefs'] == []
    assert ('gunfire_reconstruction' in holder['unavailable']) is (state in {'no_sample', 'no_history'})


def test_team_union_keeps_all_distinct_channel_reasons_in_stable_order():
    from website.backend.services.round_web_service import _team_information

    holders = {
        'H': {'beliefs': [], 'unavailable': {'gunfire_reconstruction': 'missing listener', 'capture': 'unknown'}},
        'H2': {'beliefs': [], 'unavailable': {'gunfire_reconstruction': 'invalid coordinates'}},
        'H3': {'beliefs': [], 'unavailable': {'gunfire_reconstruction': 'missing listener'}},
        'ENEMY': {'beliefs': [], 'unavailable': {'gunfire_reconstruction': 'enemy private gap'}},
    }
    results = [_team_information({'holders': holders}, {'team': 'AXIS', 'members': members}, 2000)
               ['holders']['team:AXIS']['unavailable']
               for members in [('H', 'H2', 'H3'), ('H3', 'H2', 'H')]]
    assert results[0] == results[1]
    assert results[0] == {'capture': 'unknown', 'gunfire_reconstruction': 'invalid coordinates; missing listener'}


@pytest.mark.parametrize('gap', [None, 'enemy_roster', 'gunfire_reconstruction'])
def test_heard_distance_is_independent_but_refuses_incomplete_modelling(gap):
    from website.backend.services.information_state import BeliefItem, HolderState, Region, to_dict

    state = HolderState('H', [
        BeliefItem('H', 'gunfire', 1000, region=Region(200, 0, 0, 400)),
        BeliefItem('H', 'aim_lock', 1000, subject_guid='S', region=Region(100, 0, 0, 10)),
    ])
    if gap:
        state.unavailable[gap] = 'Fixture unavailable'
    result = to_dict(state, 1000, (0, 0, 0), enemy_guids=frozenset({'S'}))
    assert len(result['beliefs']) == 2
    complete = gap != 'gunfire_reconstruction'
    assert result['heard_activity_distance_reconstruction_complete'] is complete
    assert (result['nearest_heard_activity_distance'] is not None) is complete
    assert result['known_enemy_count'] == (None if gap == 'enemy_roster' else 1)
    assert (result['nearest_known_enemy_distance'] is not None) is (gap != 'enemy_roster')


@pytest.mark.parametrize('horizon', [1000, 1000000])
@pytest.mark.parametrize('age', [0, 250, 500, 1000, 2000, 5000, 5001, 30000])
def test_gap_relevance_expires_with_actual_distance_confidence_and_horizon(monkeypatch, horizon, age):
    from website.backend.services import information_state as info

    monkeypatch.setattr(info, 'POSITION_CLAIM_MAX_RADIUS', horizon)
    hypothetical = info.BeliefItem('H', 'gunfire', 0, region=info.Region(0, 0, 0, info.GUNFIRE_REGION_RADIUS))
    would_contribute = info.nearest_heard_activity_distance(info.HolderState('H', [hypothetical]), age, (0, 0, 0)) is not None
    fresh = info.BeliefItem('H', 'gunfire', age, region=info.Region(100, 0, 0, info.GUNFIRE_REGION_RADIUS))
    state = info.HolderState('H', [fresh], {'gunfire_reconstruction': 'Historical missing shot'}, (0,))
    result = info.to_dict(state, age, (0, 0, 0), enemy_guids=frozenset())
    assert result['heard_activity_distance_reconstruction_complete'] is (not would_contribute)
    assert (result['nearest_heard_activity_distance'] is not None) is (not would_contribute)
    assert result['unavailable']['gunfire_reconstruction'] == 'Historical missing shot'
    assert len(result['beliefs']) == 1
    # A fresh missed shot must block even when an older gap has expired.
    state.gunfire_gap_times = (0, age)
    mixed = info.to_dict(state, age, (0, 0, 0), enemy_guids=frozenset())
    assert mixed['heard_activity_distance_reconstruction_complete'] is False
    assert mixed['nearest_heard_activity_distance'] is None


@pytest.mark.asyncio
@pytest.mark.parametrize('gap_time', [1000, 30000])
async def test_real_asgi_partial_hearing_keeps_regions_and_only_relevant_gaps_block_distance(monkeypatch, gap_time):
    import json

    import httpx
    from fastapi import FastAPI

    from website.backend.dependencies import get_db
    from website.backend.routers.replay_router import router
    from website.backend.services import line_of_sight

    class PartialDB(ShotDB):
        async def fetch_all(self, query, params):
            if 'SELECT 1 FROM rounds WHERE' in query:
                return [(1,)]
            if 'f.capabilities' in query:
                return [(json.dumps({'capabilities': {'shot_fired': 'enabled'}}),)]
            if 'SELECT pt.player_guid, pt.player_name, pt.team, pt.player_class' in query:
                rows = tracks()['H']
                rows[0][6].append({'time': 30000, 'x': 100, 'y': 0, 'z': 0, 'health': 100})
                return rows
            if 'FROM proximity_shot_fired' in query:
                return [('S', gap_time, None, 0, 0), ('S', 30000, 0, 0, 0)]
            return await super().fetch_all(query, params)

    monkeypatch.setattr(line_of_sight, '_DEFAULT', line_of_sight.GeometryProvider('/nonexistent/hearing-fixture'))
    app = FastAPI()
    app.include_router(router, prefix='/api')
    async def fixture_db():
        return PartialDB()

    app.dependency_overrides[get_db] = fixture_db
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
        for pov in ['H', 'team:AXIS']:
            response = await client.get('/api/replay/round/1/web', params={'t': 30000, 'pov': pov})
            assert response.status_code == 200, response.text
            holder = response.json()['information_state']['holders'][pov]
            assert len(holder['beliefs']) == 1
            assert holder['beliefs'][0]['source'] == 'gunfire'
            assert 'gunfire_reconstruction' in holder['unavailable']
            assert holder['heard_activity_distance_reconstruction_complete'] is (gap_time == 1000)
            assert (holder['nearest_heard_activity_distance'] is not None) is (gap_time == 1000 and pov == 'H')
            assert holder['known_enemy_count'] == 0


def test_team_hearing_completeness_requires_all_measured_members():
    from website.backend.services.round_web_service import _team_information

    known = {'beliefs': [], 'unavailable': {}, 'heard_activity_distance_reconstruction_complete': True}
    unknown = {**known, 'heard_activity_distance_reconstruction_complete': False}
    for members, holders, complete in [([], {}, False), (['H'], {}, False),
                                       (['H'], {'H': known}, True),
                                       (['H', 'S'], {'H': known}, False),
                                       (['H', 'S'], {'H': known, 'S': unknown}, False)]:
        result = _team_information({'holders': holders}, {'team': 'AXIS', 'members': members}, 0)
        team = result['holders']['team:AXIS']
        assert team['nearest_heard_activity_distance'] is None
        assert team['heard_activity_distance_reconstruction_complete'] is complete
        missing = not members or len(holders) < len(members)
        assert team['known_enemy_count'] == (None if missing else 0)
        assert ('team_knowledge' in team['unavailable']) is missing


def test_partial_team_preserves_known_beliefs_but_refuses_definitive_count():
    from website.backend.services.round_web_service import _team_information

    belief = {'subject_guid': 'E', 'counts_as_known': True, 'confidence': 1}
    info = {'holders': {'H': {'beliefs': [belief], 'unavailable': {}}}}
    result = _team_information(info, {'team': 'AXIS', 'members': ['H', 'MISSING']}, 0)
    team = result['holders']['team:AXIS']
    assert team['beliefs'] == [belief]
    assert team['known_enemy_count'] is None
    assert 'team_knowledge' in team['unavailable']


@pytest.mark.asyncio
async def test_real_asgi_stale_excluded_team_is_unavailable_not_zero(monkeypatch):
    import httpx
    from fastapi import FastAPI

    from website.backend.dependencies import get_db
    from website.backend.routers.replay_router import router
    from website.backend.services import line_of_sight

    class StaleDB(ShotDB):
        async def fetch_all(self, query, params):
            if 'SELECT 1 FROM rounds WHERE' in query:
                return [(1,)]
            if 'SELECT pt.player_guid, pt.player_name, pt.team, pt.player_class' in query:
                rows = tracks()['H']
                rows[0][6][0]['time'] = 0
                return rows
            if 'FROM proximity_shot_fired' in query:
                return []
            return await super().fetch_all(query, params)

    monkeypatch.setattr(line_of_sight, '_DEFAULT', line_of_sight.GeometryProvider('/nonexistent/hearing-fixture'))
    app = FastAPI()
    app.include_router(router, prefix='/api')
    async def fixture_db():
        return StaleDB()

    app.dependency_overrides[get_db] = fixture_db
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
        response = await client.get('/api/replay/round/1/web', params={'t': 500, 'pov': 'team:AXIS', 'max_stale_ms': 0})
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload['players'] == []
        holder = payload['information_state']['holders']['team:AXIS']
        assert holder['known_enemy_count'] is None
        assert holder['heard_activity_distance_reconstruction_complete'] is False
        assert 'team_knowledge' in holder['unavailable']
