"""Enemy metrics classify retained evidence against the snapshot's roster."""

import pytest

from website.backend.services.information_state import (
    BeliefItem,
    HolderState,
    Region,
    to_dict,
)
from website.backend.services.round_web_service import (
    CapturePolicy,
    _team_information,
    build_snapshot,
    load_round_information_state,
)


def life(guid, team, *, start=0, end=None, identity=1):
    return (guid, guid, team, 'MEDIC', start, end,
            [{'time': start, 'x': 100, 'y': 0, 'z': 0, 'health': 100}], 'supply', identity)


class Events:
    async def fetch_all(self, query, params):
        if 'SELECT player_guid, team, death_time_ms' in query:
            return [('S', 'AXIS', 1000)]
        if 'FROM proximity_aim_lock' in query:
            return [('H', 'S', 1000)]
        if 'FROM rounds r' in query:
            return [(100,)]
        return []


async def information(tracks, t=2000):
    return await load_round_information_state(
        Events(), 1, t, build_snapshot(tracks, t), {},
        CapturePolicy(capabilities={'aim_lock': 'enabled'}), tracks,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('subject_team,expected,unknown', [
    ('AXIS', 0, False), ('ALLIES', 1, False), ('SPECTATOR', None, True), (None, None, True),
])
async def test_loader_retains_friendly_obituary_without_enemy_metrics(subject_team, expected, unknown):
    tracks = {'H': [life('H', 'AXIS')], 'S': [life('S', subject_team, identity=2)]}
    result = await information(tracks)
    holder = result['holders']['H']
    assert holder['known_enemy_count'] == expected
    assert any(b['source'] == 'public_obituary' for b in holder['beliefs'])
    assert {b['subject_guid'] for b in holder['beliefs'] if b['counts_as_known']} == (
        {'S'} if expected else set()
    )
    assert ('enemy_roster' in holder['unavailable']) is unknown
    team = _team_information(result, {'team': 'AXIS', 'members': ['H']}, 2000)
    assert team['holders']['team:AXIS']['known_enemy_count'] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize('switcher', ['H', 'S'])
async def test_current_allegiance_changes_metrics_without_deleting_old_evidence(switcher):
    tracks = {'H': [life('H', 'AXIS')], 'S': [life('S', 'ALLIES', identity=2)]}
    before = 'AXIS' if switcher == 'H' else 'ALLIES'
    after = 'ALLIES' if switcher == 'H' else 'AXIS'
    tracks[switcher] = [life(switcher, before, end=3000, identity=3),
                        life(switcher, after, start=3000, identity=4)]
    earlier = (await information(tracks, 2000))['holders']['H']
    later = (await information(tracks, 3000))['holders']['H']
    assert earlier['known_enemy_count'] == 1
    assert later['known_enemy_count'] == 0
    assert any(b['subject_guid'] == 'S' for b in later['beliefs'])


@pytest.mark.asyncio
@pytest.mark.parametrize('uncertain', ['holder_missing', 'subject_future', 'holder_overlap', 'subject_overlap'])
async def test_unknown_or_conflicting_allegiance_never_invents_an_enemy(uncertain):
    tracks = {'H': [life('H', 'AXIS')], 'S': [life('S', 'ALLIES', identity=2)]}
    if uncertain == 'subject_future':
        tracks['S'] = [life('S', 'ALLIES', start=4000, identity=2)]
    elif uncertain == 'holder_missing':
        tracks['H'] = [life('H', None)]
    else:
        guid = 'H' if uncertain == 'holder_overlap' else 'S'
        tracks[guid].append(life(guid, 'ALLIES', identity=3))
    holder = (await information(tracks))['holders']['H']
    assert holder['known_enemy_count'] is None
    assert holder['nearest_known_enemy_distance'] is None
    assert 'enemy_roster' in holder['unavailable']
    assert all(b['subject_is_enemy'] is False for b in holder['beliefs'] if b['subject_guid'])


@pytest.mark.parametrize('enemies,expected', [(frozenset(), 0), (frozenset({'S'}), 1)])
def test_distance_count_and_flag_share_the_enemy_filter(enemies, expected):
    state = HolderState('H', [BeliefItem(holder_guid='H', source='aim_lock', t_observed=0,
                                        subject_guid='S', region=Region(100, 0, 0, 10))])
    payload = to_dict(state, 0, (0, 0, 0), enemy_guids=enemies)
    assert payload['known_enemy_count'] == expected
    assert payload['beliefs'][0]['counts_as_known'] is bool(expected)
    assert payload['beliefs'][0]['subject_is_enemy'] is bool(expected)
    assert (payload['nearest_known_enemy_distance'] is not None) is bool(expected)
    assert len(payload['beliefs']) == 1


@pytest.mark.asyncio
async def test_team_union_deduplicates_enemy_and_excludes_friendly_subjects():
    tracks = {'H': [life('H', 'AXIS')], 'H2': [life('H2', 'AXIS', identity=3)],
              'S': [life('S', 'ALLIES', identity=2)]}
    result = await information(tracks)
    for guid in ('H', 'H2'):
        assert result['holders'][guid]['known_enemy_count'] == 1
    union = _team_information(result, {'team': 'AXIS', 'members': ['H', 'H2']}, 2000)
    assert union['holders']['team:AXIS']['known_enemy_count'] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('team,expected', [('AXIS', 0), ('ALLIES', 1), (None, None)])
async def test_real_asgi_route_propagates_roster_to_player_and_team_pov(monkeypatch, team, expected):
    import httpx
    from fastapi import FastAPI

    from website.backend.dependencies import get_db
    from website.backend.routers.replay_router import router
    from website.backend.services import line_of_sight

    class RouteDB(Events):
        async def fetch_all(self, query, params):
            if 'SELECT 1 FROM rounds WHERE' in query:
                return [(1,)]
            if 'SELECT pt.player_guid, pt.player_name, pt.team, pt.player_class' in query:
                return [life('H', 'AXIS'), life('S', team, identity=2)]
            return await super().fetch_all(query, params)

    # This fixture has no installed world geometry; no ambient asset scan.
    monkeypatch.setattr(line_of_sight, '_DEFAULT', line_of_sight.GeometryProvider('/nonexistent/sw-a02'))
    app = FastAPI()
    app.include_router(router, prefix='/api')
    app.dependency_overrides[get_db] = lambda: RouteDB()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
        for pov in ('H', 'team:AXIS'):
            response = await client.get('/api/replay/round/1/web', params={'t': 2000, 'pov': pov})
            assert response.status_code == 200, response.text
            holder = response.json()['information_state']['holders'][pov]
            assert holder['known_enemy_count'] == expected
            assert any(b['subject_guid'] == 'S' for b in holder['beliefs'])
            assert all(b['subject_is_enemy'] is bool(expected) for b in holder['beliefs'] if b['subject_guid'] == 'S')
            assert {b['subject_guid'] for b in holder['beliefs'] if b['counts_as_known']} == (
                {'S'} if expected else set()
            )


def test_uncertain_roster_belief_cannot_return_distance_while_count_is_zero():
    state = HolderState('H', [BeliefItem(
        holder_guid='H', source='public_obituary', t_observed=0,
        subject_guid='S', region=Region(100, 0, 0, 10),
        roster_state='uncertain_after_down', expires_at_ms=10000,
    )])
    payload = to_dict(state, 0, (0, 0, 0), enemy_guids=frozenset({'S'}))
    assert payload['beliefs']
    assert payload['known_enemy_count'] == 0
    assert payload['nearest_known_enemy_distance'] is None


def test_enemy_classification_survives_below_known_confidence_floor():
    state = HolderState('H', [BeliefItem(holder_guid='H', source='aim_lock', t_observed=0,
                                        subject_guid='S', region=Region(100, 0, 0, 10))])
    payload = to_dict(state, 6000, (0, 0, 0), enemy_guids=frozenset({'S'}))
    assert payload['beliefs'][0]['subject_is_enemy'] is True
    assert payload['beliefs'][0]['counts_as_known'] is False


@pytest.mark.parametrize('partial', [False, True])
def test_unavailable_roster_has_null_metrics_but_preserves_classified_evidence(partial):
    beliefs = [BeliefItem(holder_guid='H', source='aim_lock', t_observed=0,
                         subject_guid='S', region=Region(100, 0, 0, 10))] if partial else []
    beliefs.append(BeliefItem(holder_guid='H', source='gunfire', t_observed=0,
                             subject_guid=None, region=Region(200, 0, 0, 10)))
    state = HolderState('H', beliefs)
    state.unavailable['enemy_roster'] = 'Named subject allegiance missing'
    result = to_dict(state, 0, (0, 0, 0), enemy_guids=frozenset({'S'}))
    assert result['known_enemy_count'] is None
    assert result['nearest_known_enemy_distance'] is None
    assert result['nearest_heard_activity_distance'] is not None
    assert any(b['counts_as_known'] for b in result['beliefs']) is partial
    assert len(result['beliefs']) == len(beliefs)
    union = _team_information({'holders': {'H': result}}, {'team': 'AXIS', 'members': ['H']}, 0)
    assert union['holders']['team:AXIS']['known_enemy_count'] is None


def test_team_union_cannot_turn_a_members_unknown_count_into_a_partial_number():
    known = to_dict(HolderState('H', [BeliefItem(
        holder_guid='H', source='aim_lock', t_observed=0, subject_guid='S',
        region=Region(100, 0, 0, 10),
    )]), 0, (0, 0, 0), enemy_guids=frozenset({'S'}))
    unknown_state = HolderState('H2', [])
    unknown_state.unavailable['enemy_roster'] = 'Holder allegiance ambiguous'
    unknown = to_dict(unknown_state, 0, None, enemy_guids=frozenset())
    result = _team_information({'holders': {'H': known, 'H2': unknown}},
                               {'team': 'AXIS', 'members': ['H', 'H2']}, 0)
    holder = result['holders']['team:AXIS']
    assert holder['known_enemy_count'] is None
    assert any(b['counts_as_known'] for b in holder['beliefs'])


def test_unrelated_hearing_gap_does_not_disable_known_enemy_metrics():
    state = HolderState('H', [BeliefItem(holder_guid='H', source='aim_lock', t_observed=0,
                                        subject_guid='S', region=Region(100, 0, 0, 10))])
    state.unavailable['shot_fired'] = 'Capture unavailable'
    result = to_dict(state, 0, (0, 0, 0), enemy_guids=frozenset({'S'}))
    assert result['known_enemy_count'] == 1
    assert result['nearest_known_enemy_distance'] is not None
    union = _team_information({'holders': {'H': result}}, {'team': 'AXIS', 'members': ['H']}, 0)
    assert union['holders']['team:AXIS']['known_enemy_count'] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('t,expected,visible', [(1000, None, True), (7000, 0, True), (40000, 0, False)])
async def test_only_metric_relevant_subjects_require_current_allegiance(t, expected, visible):
    class AimOnly(Events):
        async def fetch_all(self, query, params):
            if 'SELECT player_guid, team, death_time_ms' in query:
                return []
            return await super().fetch_all(query, params)

    tracks = {'H': [life('H', 'AXIS')]}
    result = await load_round_information_state(
        AimOnly(), 1, t, build_snapshot(tracks, t), {},
        CapturePolicy(capabilities={'aim_lock': 'enabled'}), tracks,
    )
    holder = result['holders']['H']
    assert holder['known_enemy_count'] == expected
    assert ('enemy_roster' in holder['unavailable']) is (expected is None)
    assert bool(holder['beliefs']) is visible
    assert holder['nearest_known_enemy_distance'] is None
    union = _team_information(result, {'team': 'AXIS', 'members': ['H']}, t)
    assert union['holders']['team:AXIS']['known_enemy_count'] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize('unmeasured', ['enemy_roster', 'missing_holder'])
@pytest.mark.parametrize('measured', [5, 6])
async def test_layer4_blind_share_excludes_unmeasured_samples(monkeypatch, unmeasured, measured):
    from types import SimpleNamespace

    from scripts import spiderweb_layer4_family as family

    async def tracks(*args):
        return {'H': [life('H', 'AXIS')]}

    async def engagements(*args):
        return []

    async def policy(*args):
        return CapturePolicy()

    async def end(*args):
        return 12000

    async def clock(*args):
        return {}

    async def info(_db, _rid, t, *args):
        if t < (12 - measured) * 1000:
            holder = {'unavailable': {'enemy_roster': 'Current allegiance missing'},
                      'beliefs': [], 'known_enemy_count': None}
            return {'holders': {'H': holder} if unmeasured == 'enemy_roster' else {}}
        # Three measured blind ticks followed by measured placeable evidence.
        beliefs = [] if t < (15 - measured) * 1000 else [{
            'subject_guid': 'S', 'counts_as_known': True, 'region': {'radius': 10}}]
        return {'holders': {'H': {'beliefs': beliefs, 'unavailable': {'shot_fired': 'Capture unavailable'},
                                 'position_claim_max_radius': 1200}}}

    for name, fn in [('load_round_tracks', tracks), ('load_round_engagements', engagements),
                     ('load_capture_policy', policy), ('load_round_end_ms', end),
                     ('load_round_clock', clock), ('load_round_information_state', info)]:
        monkeypatch.setattr(family.rws, name, fn)
    monkeypatch.setattr(family.rws, 'build_snapshot', lambda *a, **kw: SimpleNamespace(
        players={'H': SimpleNamespace(alive=True, x=0, speed=200, team='AXIS')}, edges=[]))
    monkeypatch.setattr(family.rws, 'nearest_teammate_separation', lambda snap: {})
    rows = await family.collect_round(Events(), 1, {'map': 'supply', 'winner': 1,
        'block': 1, 'date': '2026-10-13', 'time': '12:00'}, cadence_ms=1000, provider=None)
    assert len(rows) == 1
    row = rows[0]
    assert row['metrics']['blind_moving_share'] == (0.5 if measured == 6 else None)
    assert row['samples']['moving'] == 12
    assert row['samples']['blind_moving_measured'] == measured
    assert row['samples']['blind_moving_excluded'] == {unmeasured: 12 - measured}
