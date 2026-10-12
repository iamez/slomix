"""Normalized parent lookups retain bounded index access on real PostgreSQL."""
# ruff: noqa: SLF001 -- capture the actual strict parent lookup SQL

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from proximity.parser.round_identity import resolve_proximity_round_id
from shared.proximity_import import _linked_parent
from tests.integration.proximity_adapter_helpers import pg_query
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
INDEX = 'idx_rounds_normalized_map_round_start'


def index_ddl(source):
    if source == 'migration':
        return (ROOT / 'migrations/095_proximity_normalized_parent_index.sql').read_text()
    schema = (ROOT / 'tools/schema_postgresql.sql').read_text()
    match = re.search(rf'CREATE INDEX IF NOT EXISTS {INDEX}\b[^;]+;', schema)
    assert match, 'Bootstrap schema must provide the normalized parent index'
    return match.group(0)


def plan_nodes(plan):
    yield plan
    for child in plan.get('Plans', []):
        yield from plan_nodes(child)


@pytest.mark.parametrize('source', ['migration', 'bootstrap'])
async def test_normalized_parent_index_is_bounded_and_nonunique(journal_db, source):  # noqa: F811
    writer, _ = journal_db
    await writer.execute('''ALTER TABLE rounds ADD COLUMN map_name TEXT,
                           ADD COLUMN round_start_unix BIGINT''')
    await writer.execute('''INSERT INTO rounds
        (id, map_name, round_number, round_start_unix, gaming_session_id)
        SELECT i, CASE WHEN i % 3 = 0 THEN ' MAP' || (i % 20) || ' '
                       ELSE 'map' || (i % 20) END,
               1 + i % 2, 1700000000::bigint + i * 60, i / 10
        FROM generate_series(1, 100000) AS s(i)''')
    await writer.execute('''CREATE INDEX idx_rounds_map_round_start
        ON rounds (map_name, round_number, round_start_unix)''')
    await writer.execute('''CREATE INDEX idx_rounds_start_unix
        ON rounds (round_start_unix DESC)
        WHERE round_start_unix IS NOT NULL AND gaming_session_id IS NOT NULL''')
    ddl = index_ddl(source)
    await writer.execute(ddl)
    await writer.execute(ddl)  # Reapplication must not drop or rewrite data.
    # A normalized index must NOT silently forbid ambiguous existing identities.
    await writer.execute('''INSERT INTO rounds
        (id, map_name, round_number, round_start_unix, gaming_session_id) VALUES
        (100001, 'DUPLICATE', 1, 1700000000, 1),
        (100002, ' duplicate ', 1, 1700000000, NULL)''')
    await writer.execute('ANALYZE rounds')
    assert await writer.fetchval('SELECT count(*) FROM rounds') == 100002

    queries = []

    async def capture(query, params):
        queries.append(pg_query(query))
        return [(1, 1)]

    adapter = SimpleNamespace(fetch_all=capture)
    await resolve_proximity_round_id(adapter, 'map0', 1, source_start_unix=1700000000)
    await _linked_parent(adapter, {'map_name': 'map0', 'round_num': 1,
                                  'round_start_unix': 1700000000})
    assert len(queries) == 2
    for query in queries:
        for params, expected in (
            ((' MAP0 ', 1, 1700000000 + 50000 * 60), [50000]),
            (('absent', 1, 1700000000), []),
            (('duplicate', 1, 1700000000), [100001, 100002]),
        ):
            async with writer.transaction():  # Retain FOR SHARE semantics.
                rows = await writer.fetch(query, *params)
                assert [row[0] for row in rows] == expected
                # No enable_seqscan override: exercise the default planner.
                raw = await writer.fetchval(
                    'EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + query, *params,
                )
            plan = json.loads(raw)[0]['Plan']
            scans = [node for node in plan_nodes(plan)
                     if node.get('Index Name') == INDEX]
            assert scans, plan
            # Index usage alone is insufficient: all identity parts must be
            # index conditions, not residual filters after a broad scan.
            cond = ' '.join(node.get('Index Cond', '') for node in scans).lower()
            assert all(key in cond for key in (
                'lower(btrim(map_name))', 'round_number', 'round_start_unix',
            )), plan
            assert plan.get('Shared Hit Blocks', 0) + plan.get('Shared Read Blocks', 0) < 100, plan
            assert not any(node['Node Type'] == 'Seq Scan' for node in plan_nodes(plan))
