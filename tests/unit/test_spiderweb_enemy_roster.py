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
    assert all(b['subject_is_enemy'] is None for b in holder['beliefs'] if b['subject_guid'])


@pytest.mark.parametrize('enemies,expected', [(frozenset(), 0), (frozenset({'S'}), 1)])
def test_distance_count_and_flag_share_the_enemy_filter(enemies, expected):
    state = HolderState('H', [BeliefItem(holder_guid='H', source='aim_lock', t_observed=0,
                                        subject_guid='S', region=Region(100, 0, 0, 10))])
    payload = to_dict(state, 0, (0, 0, 0), enemy_guids=enemies,
                      friendly_guids=frozenset() if enemies else frozenset({'S'}))
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
            assert all(b['subject_is_enemy'] is (None if expected is None else bool(expected)) for b in holder['beliefs'] if b['subject_guid'] == 'S')
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
async def test_layer4_blind_share_excludes_unmeasured_samples(monkeypatch, tmp_path, unmeasured, measured):
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
    import json

    saved = tmp_path / 'collected.jsonl'
    saved.write_text(json.dumps(row) + '\n')
    assert family.read_dataset(saved, cadence_ms=1000, los_enabled=False) == rows


@pytest.mark.asyncio
@pytest.mark.parametrize('case,expected', [
    ('enemy', True), ('teammate', False), ('self', False),
    ('subject_missing', None), ('subject_spectator', None), ('subject_conflict', None),
    ('holder_missing', None), ('holder_spectator', None), ('holder_conflict', None),
])
async def test_allegiance_classification_keeps_unknown_distinct_from_teammate(case, expected):
    tracks = {'H': [life('H', 'AXIS')], 'S': [life('S', 'ALLIES', identity=2)]}
    subject = 'H' if case == 'self' else 'S'
    if case == 'teammate':
        tracks['S'] = [life('S', 'AXIS', identity=2)]
    for role, guid in [('holder', 'H'), ('subject', 'S')]:
        if case == role + '_missing':
            tracks[guid] = [life(guid, None, identity=3)]
        elif case == role + '_spectator':
            tracks[guid] = [life(guid, 'SPECTATOR', identity=3)]
        elif case == role + '_conflict':
            tracks[guid].append(life(guid, 'AXIS', identity=3))

    class AimOnly(Events):
        async def fetch_all(self, query, params):
            if 'SELECT player_guid, team, death_time_ms' in query:
                return []
            if 'FROM proximity_aim_lock' in query:
                return [('H', subject, 1000)]
            return await super().fetch_all(query, params)

    result = await load_round_information_state(
        AimOnly(), 1, 1000, build_snapshot(tracks, 1000), {},
        CapturePolicy(capabilities={'aim_lock': 'enabled'}), tracks,
    )
    holder = result['holders']['H']
    assert holder['beliefs'][0]['subject_is_enemy'] is expected
    assert holder['beliefs'][0]['region'] is not None
    assert holder['beliefs'][0]['counts_as_known'] is (expected is True)
    assert holder['known_enemy_count'] == (None if expected is None else int(expected))


def test_team_union_preserves_each_holders_unknown_classification():
    belief = BeliefItem(holder_guid='H', source='aim_lock', t_observed=0,
                        subject_guid='S', region=Region(100, 0, 0, 10))
    known = to_dict(HolderState('H', [belief]), 0, (0, 0, 0), enemy_guids=frozenset({'S'}))
    uncertain = HolderState('H2', [belief], unavailable={'enemy_roster': 'Holder allegiance missing'})
    unknown = to_dict(uncertain, 0, (0, 0, 0), enemy_guids=frozenset())
    union = _team_information({'holders': {'H': known, 'H2': unknown}},
                              {'team': 'AXIS', 'members': ['H', 'H2']}, 0)
    holder = union['holders']['team:AXIS']
    assert [b['subject_is_enemy'] for b in holder['beliefs']] == [True, None]
    assert holder['known_enemy_count'] is None


def _layer4_row():
    from scripts import spiderweb_layer4_family as family

    return {'dataset_contract': family.dataset_contract(1000, False),
            'block': 1, 'round_id': 1, 'player': 'synthetic', 'won': 1, 'order_key': '2026-01-01',
            'metrics': {'blind_moving_share': 0.5},
            'samples': {'alive': 12, 'moving': 12, 'blind_moving': 3,
                        'blind_moving_measured': 6, 'blind_moving_excluded': {'missing_holder': 6}}}


@pytest.mark.parametrize('fault', ['unversioned', 'old-version', 'mixed-los', 'cadence', 'denominator', 'missing-samples', 'malformed'])
def test_layer4_analysis_rejects_incompatible_evidence_before_writing(tmp_path, fault):
    import json
    from types import SimpleNamespace

    from scripts import spiderweb_layer4_family as family

    row = _layer4_row()
    original = json.dumps(row)
    if fault == 'unversioned':
        row.pop('dataset_contract')
    elif fault == 'old-version':
        row['dataset_contract']['metric_definition_version'] = 'all_moving_v1'
    elif fault == 'mixed-los':
        row['dataset_contract']['los_enabled'] = True
    elif fault == 'cadence':
        row['dataset_contract']['cadence_ms'] = 5000
    elif fault == 'denominator':
        row['metrics']['blind_moving_share'] = 0.25  # Old all-moving denominator.
    elif fault == 'missing-samples':
        row.pop('samples')
    path = tmp_path / 'rows.jsonl'
    path.write_text(original + '\n' + ('{' if fault == 'malformed' else json.dumps(row)) + '\n')
    args = SimpleNamespace(rows=str(path), cadence_ms=1000, resamples=10,
                           out_md=str(tmp_path / 'result.md'), out_manifest=str(tmp_path / 'manifest.json'))
    with pytest.raises(ValueError, match='recollect'):
        family.analyse(args)
    assert not (tmp_path / 'result.md').exists()
    assert not (tmp_path / 'manifest.json').exists()


@pytest.mark.asyncio
@pytest.mark.parametrize('resume,versioned', [(True, False), (False, False), (False, True)])
async def test_layer4_collect_rejects_old_or_accidental_append_before_db(tmp_path, monkeypatch, resume, versioned):
    import json
    import sys
    from types import SimpleNamespace

    from scripts import spiderweb_layer4_family as family

    touched = []
    async def forbidden():
        touched.append('database')
        pytest.fail('Collection opened database before validating existing evidence')

    import website.backend
    dep = SimpleNamespace(init_db_pool=forbidden)
    monkeypatch.setitem(sys.modules, 'website.backend.dependencies', dep)
    monkeypatch.setattr(website.backend, 'dependencies', dep, raising=False)
    row = _layer4_row()
    if not versioned:
        row.pop('dataset_contract')
    path = tmp_path / 'rows.jsonl'
    original = json.dumps(row) + '\n'
    path.write_text(original)
    with pytest.raises(ValueError):
        await family.collect(SimpleNamespace(out=str(path), resume=resume, cadence_ms=1000, skip_los=True))
    assert touched == []
    assert path.read_text() == original


@pytest.mark.asyncio
async def test_layer4_resume_validates_contract_then_skips_completed_rounds(tmp_path, monkeypatch):
    import json
    import sys
    from types import SimpleNamespace

    import website.backend
    from scripts import spiderweb_layer4_family as family

    calls = []
    async def init():
        calls.append('init')
    async def rounds(*args):
        return [(1, 1, 'supply', 1, '2026-01-01', '12:00', 1)]
    async def forbidden(*args, **kwargs):
        pytest.fail('Resumed collector repeated an already completed round')

    dep = SimpleNamespace(init_db_pool=init, get_db_pool=lambda: SimpleNamespace(fetch_all=rounds))
    monkeypatch.setitem(sys.modules, 'website.backend.dependencies', dep)
    monkeypatch.setattr(website.backend, 'dependencies', dep, raising=False)
    monkeypatch.setattr(family, 'collect_round', forbidden)
    path = tmp_path / 'rows.jsonl'
    original = json.dumps(_layer4_row()) + '\n'
    path.write_text(original)
    await family.collect(SimpleNamespace(out=str(path), resume=True, cadence_ms=1000, skip_los=True, limit=0))
    assert calls == ['init'] and path.read_text() == original


def test_layer4_current_analysis_versions_its_manifest(tmp_path):
    import hashlib
    import json
    from types import SimpleNamespace

    from scripts import spiderweb_layer4_family as family

    rows = []
    for block in range(1, 5):
        for player in range(4):
            row = _layer4_row()
            row.update(block=block, round_id=block, player=str(player), won=player % 2,
                       order_key=f'2026-01-0{block}')
            row['samples']['blind_moving'] = (player % 2) * 6
            row['metrics']['blind_moving_share'] = player % 2
            rows.append(row)
    path = tmp_path / 'rows.jsonl'
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    output = tmp_path / 'manifest.json'
    family.analyse(SimpleNamespace(rows=str(path), cadence_ms=1000, resamples=10,
                                  out_md=str(tmp_path / 'table.md'), out_manifest=str(output)))
    manifest = json.loads(output.read_text())
    assert manifest['dataset_contract'] == family.dataset_contract(1000, False)
    assert manifest['rows'] == len(rows) == 16
    digest = manifest.pop('sha256')
    manifest.pop('result')
    assert hashlib.sha256(json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode()).hexdigest() == digest
