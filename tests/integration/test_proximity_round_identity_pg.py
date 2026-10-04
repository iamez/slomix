"""Canonical proximity resolver with real candidate identity rows on private PG."""
# ruff: noqa: SLF001 -- exercise the canonical parser's internal linkage boundary

import time
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from proximity.parser import ProximityParserV4
from tests.integration.proximity_adapter_helpers import pg_query
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401
from tests.unit.test_relinker_round_number_mismatch import _relinker


@pytest.mark.parametrize('second_start,expected', [(1789795260, 101), (1789794600, None)])
async def test_physical_start_identity_with_real_candidates(journal_db, second_start, expected):  # noqa: F811
    writer, observer = journal_db
    await writer.execute('ALTER TABLE rounds ADD COLUMN map_name TEXT, ADD COLUMN round_start_unix BIGINT')
    await writer.executemany('INSERT INTO rounds (id,map_name,round_number,round_start_unix,gaming_session_id) VALUES ($1,$2,$3,$4,$5)', [
        (101, 'fixture', 1, 1789794600, 201), (102, 'fixture', 1, second_start, 202),
        (103, 'other_map', 1, 1789794600, 203), (104, 'fixture', 2, 1789794600, 204),
    ])
    async def fetch_all(query, params):
        # Same placeholder contract as the application adapter; all variables
        # remain bound values. Any legacy fallback is unexpected in these cases.
        assert 'round_start_unix = ?' in query
        for index in range(1, query.count('?') + 1):
            query = query.replace('?', f'${index}', 1)
        return await writer.fetch(query, *params)
    parser = ProximityParserV4(db_adapter=SimpleNamespace(fetch_all=fetch_all))
    parser.metadata.update(map_name='fixture', round_num=1,
                           round_start_unix=1789794600, round_end_unix=1789795200)
    await parser._resolve_round_link_context(date(2026, 9, 19))
    assert parser._round_link_context['round_id'] == expected
    if expected is not None:
        assert await observer.fetchval('SELECT gaming_session_id FROM rounds WHERE id=$1', expected) == 201
        assert [tuple(row) for row in await observer.fetch('SELECT id,gaming_session_id FROM rounds WHERE id=$1', expected)] == [(101, 201)]
    else:
        assert parser._round_link_context['round_link_reason'] == 'ambiguous_source_start'
    assert await observer.fetchval('SELECT count(*) FROM rounds') == 4


@pytest.mark.parametrize('strict', [True, False])
async def test_relinker_preserves_duplicate_pg_identity(journal_db, monkeypatch, strict):  # noqa: F811
    """Real candidate SQL, injected discovery; no service/Discord connection."""
    writer, observer = journal_db
    start = int(time.time()) - 300
    await writer.execute('ALTER TABLE rounds ADD COLUMN map_name TEXT, ADD COLUMN round_start_unix BIGINT')
    await writer.executemany('INSERT INTO rounds (id,map_name,round_number,round_start_unix) VALUES ($1,$2,$3,$4)', [
        (101, 'fixture', 1 if strict else 2, start),
        (102, 'fixture', 1 if strict else 2, start),
    ])
    await writer.execute('CREATE TABLE proof_links (round_id INTEGER)')
    await writer.execute('INSERT INTO proof_links VALUES (NULL)')
    queries = []
    async def fetch_all(query, params=None):
        if 'SELECT DISTINCT map_name' in query:
            return [('fixture', 1, start, '2026-10-04')]
        queries.append(query)
        return await writer.fetch(pg_query(query), *(params or ()))
    fallback = AsyncMock(return_value=101)
    monkeypatch.setattr('bot.core.round_linker.resolve_round_id', fallback)
    execute = AsyncMock()
    adapter = SimpleNamespace(fetch_all=fetch_all, execute=execute, fetch_val=execute)
    await _relinker(adapter)._relink_null_round_ids()
    fallback.assert_not_awaited()
    execute.assert_not_awaited()
    assert len(queries) == (1 if strict else 2)
    assert await observer.fetchval('SELECT count(*) FROM proof_links WHERE round_id IS NULL') == 1
    assert [tuple(row) for row in await observer.fetch('SELECT * FROM proof_links')] == [(None,)]
