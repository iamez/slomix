"""Regression: /proximity/revives must APPLY the scope it accepts.

`session_date`, `round_number` and `round_start_unix` were declared on the
handler and never read, while `website/js/proximity.js` sends all three on
every scoped call (`buildScopeParams`). So a reader who narrowed the page to
one round still saw the rolling 30-day revive total, sitting beside panels
that had honoured the same scope. Measured on dev 2026-08-29, before the fix:

    no filter                              1,873 revives
    session_date=2026-08-27                1,873   ← unchanged
    session_date=2026-08-27&round_number=1 1,873   ← unchanged
    map_name=supply                          320   ← map_name did filter

and after:

    session_date=2026-08-27                  155
    session_date=2026-08-27&round_number=1    90
    session_date=1999-01-01                    0

A parameter that is accepted, VALIDATED and then discarded is the worst of
the three possible states: the validation is exactly what makes it look like
it works (`min_games=abc` answers 422 while `min_games=999` changes nothing —
the brother's finding on #830, same shape, different endpoint).

These assertions are on the SQL rather than on counts because the unit suite
has no database; the numbers above are the runtime half of the evidence.
"""
import pytest

from website.backend.routers.proximity_scoring import get_proximity_revives


class _CaptureDB:
    """Records every SQL string and parameter tuple the handler issues."""

    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []

    async def fetch_one(self, sql, params=None):
        self.calls.append((sql, tuple(params or ())))
        return (0, 0, 0)

    async def fetch_all(self, sql, params=None):
        self.calls.append((sql, tuple(params or ())))
        return []

    def summary_sql(self) -> str:
        return next(sql for sql, _ in self.calls if "total_revives" in sql)

    def summary_params(self) -> tuple:
        return next(params for sql, params in self.calls if "total_revives" in sql)


@pytest.mark.asyncio
async def test_unscoped_call_filters_only_by_range():
    db = _CaptureDB()
    await get_proximity_revives(db=db)

    sql = db.summary_sql()
    assert "session_date >= CURRENT_DATE" in sql, "the range window vanished"
    assert "round_number =" not in sql
    assert "round_start_unix =" not in sql


@pytest.mark.asyncio
async def test_session_date_reaches_the_query_as_a_date():
    """A string parameter against a `date` column is a 500, not a filter.

    asyncpg infers the parameter type from the column, so passing the raw
    string raises `'str' object has no attribute 'toordinal'` — which is how
    the first version of this fix failed. `_parse_iso_date` also turns a
    malformed value into a 400 instead of a 500.
    """
    from datetime import date

    db = _CaptureDB()
    await get_proximity_revives(session_date="2026-08-27", db=db)

    assert "session_date = $" in db.summary_sql()
    assert date(2026, 8, 27) in db.summary_params()


@pytest.mark.asyncio
async def test_round_scope_reaches_the_query():
    db = _CaptureDB()
    await get_proximity_revives(
        session_date="2026-08-27", round_number=1, round_start_unix=1787855942, db=db,
    )

    sql = db.summary_sql()
    params = db.summary_params()
    assert "round_number = $" in sql
    assert "round_start_unix = $" in sql
    assert 1 in params
    assert 1787855942 in params


@pytest.mark.asyncio
async def test_scope_applies_to_the_medic_board_too():
    """Both queries, not just the summary — a filtered total over an
    unfiltered leaderboard is worse than either alone, because the two
    disagree on the same screen."""
    db = _CaptureDB()
    await get_proximity_revives(session_date="2026-08-27", round_number=2, db=db)

    board_sql = next(sql for sql, _ in db.calls if "medic_guid, MAX(medic_name)" in sql)
    assert "session_date = $" in board_sql
    assert "round_number = $" in board_sql


@pytest.mark.asyncio
async def test_a_malformed_date_is_rejected_not_ignored():
    from fastapi import HTTPException

    db = _CaptureDB()
    with pytest.raises(HTTPException) as excinfo:
        await get_proximity_revives(session_date="27-08-2026", db=db)
    assert excinfo.value.status_code == 400
