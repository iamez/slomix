"""Native SQL proof for the actual SPA/legacy tracks route; private PG ONLY.

Source audit found the sibling replay service guarded, but not this route.
Exercise actual ASGI responses, not a fake connection interpreting SQL text.
Never connect to the application database as fallback.
"""

import uuid

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

from tests.integration.test_runtime_events_pg import connection_options
from website.backend.dependencies import get_db
from website.backend.routers.proximity_round import router


@pytest.fixture
async def private_pg():
    conn = await asyncpg.connect(**connection_options())
    schema = "tracks_audit_" + uuid.uuid4().hex
    created = False
    try:
        await conn.execute(f'CREATE SCHEMA "{schema}"')
        created = True
        await conn.execute(f'SET search_path TO "{schema}"')
        await conn.execute("""
            CREATE TABLE rounds(id integer PRIMARY KEY, round_date timestamp, round_number integer, map_name text);
            CREATE TABLE player_track(
                player_guid text, player_name text, team text, player_class text,
                spawn_time_ms integer, death_time_ms integer, first_move_time_ms integer,
                path jsonb, round_id integer, session_date date, round_number integer, map_name text,
                death_type text
            );
            INSERT INTO rounds VALUES (1,'2099-01-01 19:00',1,'supply');
        """)
        yield conn
    finally:
        try:
            await conn.execute('SET search_path TO public')
            if created:
                await conn.execute(f'DROP SCHEMA "{schema}" CASCADE')
        finally:
            await conn.close()


async def track(conn, linked):
    await conn.execute("""
        INSERT INTO player_track (player_guid,player_name,team,player_class,
            spawn_time_ms,death_time_ms,first_move_time_ms,path,round_id,session_date,round_number,map_name) VALUES
          ('G1','Synthetic','AXIS','MEDIC',0,200,100,'[]'::jsonb,$1,'2099-01-01',1,'supply')
    """, linked)


async def request(conn, round_id):
    class Adapter:
        async def fetch_all(self, sql, params=()):
            return await conn.fetch(sql, *params)

    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_db] = Adapter
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(f"/api/proximity/round/{round_id}/tracks")


@pytest.mark.asyncio
@pytest.mark.parametrize("linked", [None, 1])
async def test_desired_tracks_never_borrow_another_round(private_pg, linked):
    conn = private_pg
    await conn.execute("INSERT INTO rounds VALUES (2,'2099-01-01 22:00',1,'supply')")
    await track(conn, linked)
    # Independent relational eligibility: two candidate parents; no FK to2.
    count = await conn.fetchval("SELECT count(*) FROM player_track WHERE round_id=2")
    if count != 0:
        raise RuntimeError("bad synthetic precondition: a direct track exists")
    result = await request(conn, 2)
    assert result.status_code == 404, result.text


@pytest.mark.asyncio
@pytest.mark.parametrize("linked", [None, 1])
async def test_unique_or_direct_track_remains_available(private_pg, linked):
    await track(private_pg, linked)
    result = await request(private_pg, 1)
    assert result.status_code == 200, result.text
    assert result.json()["track_count"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("first_move", [None, 0, 100])
async def test_raw_first_move_wire_preserves_zero_and_absence(private_pg, first_move):
    await track(private_pg, 1)
    await private_pg.execute('UPDATE player_track SET first_move_time_ms=$1', first_move)
    result = await request(private_pg, 1)
    assert result.status_code == 200, result.text
    expected = await private_pg.fetchval('SELECT first_move_time_ms FROM player_track')
    assert result.json()['tracks'][0]['first_move_time'] == expected == first_move


@pytest.mark.asyncio
async def test_linked_guard_is_required_even_when_target_metadata_is_unique(private_pg):
    # Different metadata for the real parent isolates the NULL-link guard from
    # the ambiguity guard. Stale date metadata cannot override an explicit FK.
    await private_pg.execute("INSERT INTO rounds VALUES (2,'2099-01-02 22:00',2,'oasis')")
    await track(private_pg, 2)
    result = await request(private_pg, 1)
    assert result.status_code == 404, result.text
    direct = await request(private_pg, 2)
    assert direct.status_code == 200, direct.text
    assert direct.json()["track_count"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("repeated", [False, True])
async def test_direct_match_wins_without_mixing_unlinked_tracks(private_pg, repeated):
    await track(private_pg, 1)
    await track(private_pg, None)
    await private_pg.execute("UPDATE player_track SET player_guid='Unlinked' WHERE round_id IS NULL")
    if repeated:
        await private_pg.execute("INSERT INTO rounds VALUES (2,'2099-01-01 22:00',1,'supply')")
    result = await request(private_pg, 1)
    assert result.status_code == 200, result.text
    assert [p['guid'] for p in result.json()['tracks']] == ['G1']


@pytest.mark.asyncio
@pytest.mark.parametrize("date,half,map_name", [
    ('2099-01-02 00:00', 1, 'supply'),
    ('2099-01-01 22:00', 2, 'supply'),
    ('2099-01-01 22:00', 1, 'oasis'),
])
async def test_other_day_half_or_map_does_not_make_key_ambiguous(private_pg, date, half, map_name):
    await private_pg.execute(
        "INSERT INTO rounds VALUES (2,$1::text::timestamp,$2,$3)", date, half, map_name)
    await track(private_pg, None)
    original = await request(private_pg, 1)
    assert original.status_code == 200, original.text
    assert original.json()["track_count"] == 1
    different = await request(private_pg, 2)
    assert different.status_code == 404, different.text


@pytest.mark.asyncio
async def test_missing_round_does_not_adopt_unlinked_tracks(private_pg):
    await track(private_pg, None)
    result = await request(private_pg, 999)
    assert result.status_code == 404, result.text


@pytest.mark.asyncio
async def test_native_api_matches_independent_round_key_cardinality(private_pg):
    # Distinct names expose leakage even when track_count happens to agree.
    await private_pg.execute("""
        INSERT INTO rounds VALUES
          (2,'2099-01-01 22:00',1,'supply'), (3,'2099-01-02 00:00',1,'supply'),
          (4,'2099-01-01 19:00',2,'supply'), (5,'2099-01-01 19:00',1,'oasis');
        INSERT INTO player_track (player_guid,player_name,team,player_class,
            spawn_time_ms,death_time_ms,first_move_time_ms,path,round_id,session_date,round_number,map_name) VALUES
          ('A','A','AXIS','MEDIC',0,200,100,'[]',1,'2099-01-01',1,'supply'),
          ('B','B','AXIS','MEDIC',0,200,100,'[]',NULL,'2099-01-01',1,'supply'),
          ('C','C','AXIS','MEDIC',0,200,100,'[]',NULL,'2099-01-02',1,'supply'),
          ('D','D','AXIS','MEDIC',0,200,100,'[]',NULL,'2099-01-01',2,'supply'),
          ('E','E','AXIS','MEDIC',0,200,100,'[]',NULL,'2099-01-01',1,'oasis');
    """)
    rounds = await private_pg.fetch('SELECT id,round_date,round_number,map_name FROM rounds')
    tracks = await private_pg.fetch('SELECT player_guid,round_id,session_date,round_number,map_name FROM player_track')
    observed = {}
    for r in rounds:
        key = (r['round_date'].date(), r['round_number'], r['map_name'])
        parents = [x['id'] for x in rounds if (x['round_date'].date(), x['round_number'], x['map_name']) == key]
        direct = [p['player_guid'] for p in tracks if p['round_id'] == r['id']]
        expected = direct or [p['player_guid'] for p in tracks if p['round_id'] is None
                              and (p['session_date'], p['round_number'], p['map_name']) == key
                              and len(parents) == 1]
        response = await request(private_pg, r['id'])
        assert response.status_code == (200 if expected else 404), response.text
        actual = sorted(p['guid'] for p in response.json()['tracks']) if expected else []
        assert actual == sorted(expected)
        if expected:
            assert response.json()['track_count'] == len(expected)
        observed[r['id']] = actual
    assert observed == {1: ['A'], 2: [], 3: ['C'], 4: ['D'], 5: ['E']}
    print(f'NATIVE TRACKS ASGI/PG PROOF: {observed}; independent Python key cardinality agrees')
