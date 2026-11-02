"""Scoped inventory only; no source-to-round writes or bootstrap heuristics."""

import pytest

from bot.runtime_gametime_linkage import inspect_gametime_link
from tests.integration.test_lua_override_boundary_pg import adapter_for
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401
from tests.integration.test_runtime_gametime_retention_pg import retain, retention_db  # noqa: F401

SOURCE = dict(source_id='fixture-server', generation='a' * 32)


@pytest.fixture
async def link_db(retention_db, tmp_path):  # noqa: F811
    writer, reader = retention_db
    await writer.execute('''ALTER TABLE rounds ADD COLUMN map_name TEXT,
        ADD COLUMN round_start_unix BIGINT, ADD COLUMN round_end_unix BIGINT''')
    await retain(adapter_for(writer), tmp_path)
    return writer, reader


async def insert_round(conn, rid, *, start=1700000000, end=1700000610, half=1, map_name='supply'):
    await conn.execute('''INSERT INTO rounds
        (id,round_number,gaming_session_id,map_name,round_start_unix,round_end_unix)
        VALUES ($1,$2,1,$3,$4,$5)''', rid, half, map_name, start, end)


async def test_real_inspection_is_read_only_and_does_not_claim_link(link_db):
    writer, reader = link_db
    await insert_round(writer, 1)
    before = {table: await reader.fetch(f'SELECT * FROM {table}') for table in (
        'rounds', 'lua_correction_inputs', 'runtime_gametime_sources',
    )}
    async with writer.transaction(readonly=True):
        result = await inspect_gametime_link(adapter_for(writer), **SOURCE, round_ids=[1])
    assert result.status == 'candidate_in_scope' and result.candidate_round_id == 1
    for table, rows in before.items():
        assert await reader.fetch(f'SELECT * FROM {table}') == rows
    assert await reader.fetchval('SELECT count(*) FROM runtime_gametime_sources') == 1
    assert len(await reader.fetch('SELECT * FROM runtime_gametime_sources')) == 1
    print('READ-ONLY LINK INSPECTION: source receipt + explicit round -> candidate, all rows unchanged')


async def test_caller_uncommitted_candidate_is_not_committed_evidence(link_db):
    writer, reader = link_db
    with pytest.raises(RuntimeError, match='fixture rollback'):
        async with writer.transaction():
            await insert_round(writer, 1)
            own = await inspect_gametime_link(adapter_for(writer), **SOURCE, round_ids=[1])
            other = await inspect_gametime_link(adapter_for(reader), **SOURCE, round_ids=[1])
            assert own.status == 'candidate_in_scope'
            assert other.status == 'missing_parent'
            raise RuntimeError('fixture rollback')
    after = await inspect_gametime_link(adapter_for(writer), **SOURCE, round_ids=[1])
    assert after.status == 'missing_parent' and after.candidate_round_id is None


async def test_late_parent_and_later_ambiguity_are_reinspected(link_db):
    writer, _ = link_db
    adapter = adapter_for(writer)
    before = await inspect_gametime_link(adapter, **SOURCE, round_ids=[1, 2])
    assert before.status == 'missing_parent'
    await insert_round(writer, 1)
    waiting = await inspect_gametime_link(adapter, **SOURCE, round_ids=[1, 2])
    assert waiting.status == 'incomplete_scope'
    await insert_round(writer, 2, start=None)
    ambiguous = await inspect_gametime_link(adapter, **SOURCE, round_ids=[1, 2])
    assert ambiguous.status == 'ambiguous' and ambiguous.candidate_round_id is None
    # The prior immutable result must not turn into implicit cached approval.
    assert before.status == 'missing_parent' and waiting.status == 'incomplete_scope'


@pytest.mark.parametrize('start,end,status', [
    (None, 1700000610, 'needs_timing_evidence'),
    (1700000000, 1700000611, 'timing_conflict'),
    (1699999999, 1700000610, 'timing_conflict'),
])
async def test_missing_or_conflicting_start_is_never_inferred(link_db, start, end, status):
    writer, _ = link_db
    await insert_round(writer, 1, start=start, end=end)
    result = await inspect_gametime_link(adapter_for(writer), **SOURCE, round_ids=[1])
    assert result.status == status and result.candidate_round_id is None


@pytest.mark.parametrize('sibling_start', [None, 1700000000])
async def test_unknown_or_duplicate_sibling_blocks_unique_candidate(link_db, sibling_start):
    writer, _ = link_db
    await insert_round(writer, 1)
    await insert_round(writer, 2, start=sibling_start)
    result = await inspect_gametime_link(adapter_for(writer), **SOURCE, round_ids=[1, 2])
    assert result.status == 'ambiguous' and result.candidate_round_id is None


async def test_scope_is_not_a_global_search_and_missing_ids_stay_unknown(link_db):
    writer, _ = link_db
    await insert_round(writer, 1)
    await insert_round(writer, 2)
    result = await inspect_gametime_link(adapter_for(writer), **SOURCE, round_ids=[1])
    assert result.status == 'candidate_in_scope' and len(result.rounds) == 1
    missing = await inspect_gametime_link(adapter_for(writer), **SOURCE, round_ids=[1, 3])
    assert missing.status == 'incomplete_scope' and missing.missing_round_ids == (3,)
    empty = await inspect_gametime_link(adapter_for(writer), **SOURCE, round_ids=[3])
    assert empty.status == 'missing_parent'


@pytest.mark.parametrize('change', [dict(source_id='other-server'), dict(generation='b' * 32)])
async def test_other_source_or_generation_does_not_inherit_evidence(link_db, change):
    writer, _ = link_db
    await insert_round(writer, 1)
    result = await inspect_gametime_link(adapter_for(writer), **(SOURCE | change), round_ids=[1])
    assert result.status == 'source_missing'
    assert result.missing_round_ids is None  # Round query was not independently measured.


@pytest.mark.parametrize('half,map_name', [(0, 'supply'), (2, 'supply'), (1, 'oasis')])
async def test_map_and_half_must_match(link_db, half, map_name):
    writer, _ = link_db
    await insert_round(writer, 1, half=half, map_name=map_name)
    result = await inspect_gametime_link(adapter_for(writer), **SOURCE, round_ids=[1])
    assert result.status == 'identity_mismatch' and result.candidate_round_id is None


async def test_corrupted_input_is_an_error_not_missing_or_candidate(link_db):
    writer, _ = link_db
    await insert_round(writer, 1)
    await writer.execute("UPDATE lua_correction_inputs SET payload='{}'::jsonb")
    with pytest.raises(ValueError):
        await inspect_gametime_link(adapter_for(writer), **SOURCE, round_ids=[1])
