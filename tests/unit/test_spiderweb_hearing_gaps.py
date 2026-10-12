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
