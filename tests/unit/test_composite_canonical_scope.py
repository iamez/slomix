"""Metrics and coverage must use the same accepted canonical round identity."""
from datetime import date

import pytest
from fastapi import HTTPException

from website.backend.routers.skill_router import get_composite_stats


class ScopeDB:
    def __init__(self, *, ambiguous=False, empty=False):
        self.ambiguous, self.empty = ambiguous, empty
        self.queries = []

    async def fetch_all(self, query, params=None):
        self.queries.append((query, params))
        if "GROUP BY gaming_session_id" in query:
            rows = [(42, '2026-08-11', '2026-08-12', 2)]
            return rows + [(43, '2026-08-11', '2026-08-11', 1)] if self.ambiguous else rows
        if "SELECT round_start_unix, map_name, round_number" in query:
            if self.empty and 'is_bot_round' in query:
                return []
            return [(1000, 'supply', 1, '2026-08-11'), (2000, 'supply', 1, '2026-08-12')]
        return []

    async def fetch_one(self, query, params=None):
        self.queries.append((query, params))
        return (0, 0, 0, 0, 0, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize('by_date', [False, True])
async def test_metrics_and_counts_share_all_canonical_keys(by_date):
    db = ScopeDB()
    result = await get_composite_stats(
        db=db, gaming_session_id=None if by_date else 42,
        session_date='2026-08-11' if by_date else None,
    )
    assert result['gaming_session_id'] == 42
    metric, metric_params = next((q, p) for q, p in db.queries if 'WITH session_pcs' in q)
    coverage, coverage_params = next((q, p) for q, p in db.queries if 'SELECT COUNT(*) FROM proximity_crossfire_opportunity' in q)
    expected = (42, [date(2026, 8, 11), date(2026, 8, 12)], [1000, 2000], ['supply', 'supply'], [1, 1])
    assert metric_params == coverage_params == expected
    assert metric.count('unnest($3::bigint[], $4::text[], $5::int[])') == 5
    assert coverage.count('unnest($3::bigint[], $4::text[], $5::int[])') == 6
    for sql in (metric, coverage):
        assert 'round_id IN' not in sql
        assert 'WHERE gaming_session_id = $1 AND kill_outcome_id IN' in sql
        assert 'session_date = ANY($2::date[])' in sql
    crossfire = metric.split('session_crossfire AS (')[1].split('session_trades AS (')[0]
    assert 'kill_outcome_id IN' in crossfire
    assert 'proximity_kill_outcome' in crossfire
    assert "r.round_status IN ('completed', 'substitution')" in metric
    accepted_query = next(q for q, _p in db.queries if 'SELECT round_start_unix' in q and 'is_bot_round' in q)
    assert 'is_valid IS DISTINCT FROM FALSE' in accepted_query
    assert "round_status IN ('completed', 'substitution')" in accepted_query


@pytest.mark.asyncio
async def test_ambiguous_date_is_not_silently_merged():
    with pytest.raises(HTTPException) as error:
        await get_composite_stats(db=ScopeDB(ambiguous=True), gaming_session_id=None, session_date='2026-08-11')
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_explicit_session_wins_over_ambiguous_date():
    result = await get_composite_stats(db=ScopeDB(ambiguous=True), gaming_session_id=42, session_date='2026-08-11')
    assert result['gaming_session_id'] == 42


@pytest.mark.asyncio
async def test_no_accepted_non_bot_rounds_is_unavailable():
    with pytest.raises(HTTPException) as error:
        await get_composite_stats(db=ScopeDB(empty=True), gaming_session_id=42, session_date=None)
    assert error.value.status_code == 404
