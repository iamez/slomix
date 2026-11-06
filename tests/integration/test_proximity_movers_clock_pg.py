"""Raw movers SQL/ASGI proof on owner-started private PG, never application DB."""

import asyncio
from datetime import date

import httpx
import pytest
from fastapi import FastAPI

from tests.integration.test_proximity_tracks_route_scope_pg import private_pg  # noqa: F401
from website.backend.dependencies import get_db
from website.backend.routers.proximity_movement import router

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def movers_db(private_pg):  # noqa: F811
    await private_pg.execute('''
        ALTER TABLE rounds ADD COLUMN is_bot_round boolean, ADD COLUMN is_valid boolean;
        ALTER TABLE player_track ADD COLUMN total_distance real DEFAULT 10,
            ADD COLUMN sprint_percentage real DEFAULT 25,
            ADD COLUMN duration_ms integer DEFAULT 99999,
            ADD COLUMN time_to_first_move_ms integer DEFAULT 99999,
            ADD COLUMN round_start_unix bigint DEFAULT 1000;
    ''')
    return private_pg


async def insert(conn, guid, name, start, end, first):
    await conn.execute('''
        INSERT INTO player_track(player_guid,player_name,spawn_time_ms,death_time_ms,
            first_move_time_ms,session_date,map_name,round_number,round_id)
        VALUES($1,$2,$3,$4,$5,$6,'supply',1,1)
    ''', guid, name, start, end, first, date(2099, 1, 1))


async def request(conn, **params):
    # Production uses a pool. Serialize this fixture's one real connection so
    # concurrent endpoint queries do not produce a fake adapter race.
    lock = asyncio.Lock()

    class Adapter:
        async def fetch_all(self, sql, args=()):
            async with lock:
                return await conn.fetch(sql, *args)

    app = FastAPI()
    app.include_router(router, prefix='/api')
    app.dependency_overrides[get_db] = Adapter
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        return await client.get('/api/proximity/movers', params={
            'session_date': '2099-01-01', 'map_name': 'supply', 'round_number': 1, **params})


async def test_source_deltas_not_stale_aggregates_and_aliases(movers_db):
    await insert(movers_db, 'G1', 'Earlier', 0, 1000, 100)
    await insert(movers_db, 'G1', 'Later', 1000, 4000, 1300)
    response = await request(movers_db)
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'ok'
    for metric in ('distance', 'sprint', 'reaction', 'survival'):
        assert len(body[metric]) == 1
        assert body[metric][0]['tracks'] == 2
    rows = await movers_db.fetch('SELECT spawn_time_ms,death_time_ms,first_move_time_ms FROM player_track')
    assert body['reaction'][0]['reaction_ms'] == sum(r[2] - r[0] for r in rows) / len(rows) == 200
    assert body['survival'][0]['duration_ms'] == sum(r[1] - r[0] for r in rows) / len(rows) == 2000
    assert body['elapsed_time_quality']['active_time_verified'] is False
    assert await movers_db.fetchval('SELECT min(duration_ms) FROM player_track') == 99999
    print('MOVERS SQL/ASGI: alias rows merge by GUID; raw means200/2000ms; persisted99999 unchanged')


@pytest.mark.parametrize('start,end,first,reaction,survival', [
    (0, 900, 0, 0, 900), (0, None, 100, 100, None),
    (100, 0, 200, 100, None), (100, 50, 200, None, None),
    (-1, 900, 100, None, None), (100, 900, 50, None, 800),
    (100, 900, 1000, None, 800), (100, 900, None, None, 800),
    (100, 100, 100, 0, 0), (None, 900, 100, None, None),
])
async def test_endpoint_eligibility(movers_db, start, end, first, reaction, survival):
    await insert(movers_db, 'G1', 'Synthetic', start, end, first)
    body = (await request(movers_db)).json()
    assert body['status'] == 'ok', body
    assert [r['reaction_ms'] for r in body['reaction']] == ([] if reaction is None else [reaction])
    assert [r['duration_ms'] for r in body['survival']] == ([] if survival is None else [survival])
    assert body['distance'][0]['tracks'] == 1  # timing exclusion is not loss of all track data


async def test_scope_quality_and_bounded_limit(movers_db):
    await insert(movers_db, 'A' * 32, 'A', 0, 1000, 100)
    await insert(movers_db, 'B' * 32, 'B', 0, 2000, 200)
    body = (await request(movers_db, limit=1)).json()
    assert body['reaction'][0]['guid'] == 'A' * 32
    assert body['survival'][0]['guid'] == 'B' * 32
    scoped = (await request(movers_db, player_guid='B' * 32)).json()
    assert [r['guid'] for r in scoped['reaction']] == ['B' * 32]
    assert (await request(movers_db, map_name='oasis')).json()['reaction'] == []
    await movers_db.execute('UPDATE player_track SET round_number=0')
    assert (await request(movers_db, round_number=0)).json()['distance'] == []
    await movers_db.execute('UPDATE player_track SET round_number=1')
    await movers_db.execute('UPDATE rounds SET is_bot_round=TRUE')
    assert (await request(movers_db)).json()['distance'] == []


async def test_metric_denominators_exclude_only_ineligible_samples(movers_db):
    await insert(movers_db, 'G1', 'First', 0, 1000, 100)
    await insert(movers_db, 'G1', 'Second', 1000, 4000, 1300)
    await insert(movers_db, 'G1', 'UnknownEnd', 100, 0, 300)
    await insert(movers_db, 'G1', 'LateMove', 100, 900, 1000)
    await insert(movers_db, 'G1', 'NoMove', 100, 2100, None)
    body = (await request(movers_db)).json()
    assert body['status'] == 'ok'
    assert body['distance'][0]['tracks'] == body['sprint'][0]['tracks'] == 5
    assert body['reaction'][0]['tracks'] == 3
    assert body['survival'][0]['tracks'] == 4
    # Independent known fixture arithmetic: different eligible denominators
    # for the two metrics; no zero-imputation for either missing endpoint.
    assert body['reaction'][0]['reaction_ms'] == (100 + 300 + 200) / 3
    assert body['survival'][0]['duration_ms'] == (1000 + 3000 + 800 + 2000) / 4


async def test_equal_metric_order_is_guid_order_not_insert_order(movers_db):
    for guid in ('C' * 32, 'A' * 32, 'B' * 32):
        await insert(movers_db, guid, 'SameAlias', 0, 1000, 100)
    body = (await request(movers_db, limit=2)).json()
    for metric in ('distance', 'sprint', 'reaction', 'survival'):
        assert [row['guid'] for row in body[metric]] == ['A' * 32, 'B' * 32]
