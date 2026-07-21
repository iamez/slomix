"""GamingSessionScope resolver (Codex §5/§8 PR-A).

Smart Stats must identify a session by rounds.gaming_session_id, never a
bare calendar date — a midnight-crossing session or a date holding more
than one gaming session are the two failure modes this resolver exists to
handle honestly (409 on ambiguity, never a `LIMIT 1` guess).
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from website.backend.services.session_scope import (
    AmbiguousSessionDateError,
    ScopeBackendUnsupportedError,
    list_recent_scopes,
    resolve_gaming_session_scope,
)


class FakeScopeDB:
    """Routes by SQL fingerprint, matching the query shapes in
    session_scope.py exactly (substring match on distinctive fragments)."""

    def __init__(self, *, gsids_for_date=None, rounds_by_gsid=None):
        # date -> list of candidate dicts as _find_gsids_for_date returns
        self.gsids_for_date: dict[str, list[tuple]] = gsids_for_date or {}
        # gsid -> list of (round_start_unix, map_name, round_number, rdate) rows
        self.rounds_by_gsid: dict[int, list[tuple]] = rounds_by_gsid or {}
        self.calls: list[tuple[str, tuple]] = []

    async def fetch_all(self, query, params=None):
        self.calls.append((query, params))
        q = " ".join(query.split())
        if "MIN(SUBSTR(CAST(round_date AS TEXT), 1, 10)) AS start_date" in q:
            date = params[0]
            return self.gsids_for_date.get(date, [])
        if "round_start_unix, map_name, round_number" in q:
            gsid = params[0]
            return self.rounds_by_gsid.get(gsid, [])
        raise AssertionError(f"unexpected query: {q[:80]}")

    async def fetch_one(self, query, params=None):
        raise AssertionError("session_scope must not call fetch_one")


def _rows(gsid, *, dates_and_maps):
    """Build (round_start_unix, map_name, round_number, rdate) rows."""
    return [
        (start, map_name, rn, rdate)
        for start, map_name, rn, rdate in dates_and_maps
    ]


@pytest.mark.asyncio
async def test_resolves_by_gaming_session_id_directly():
    rounds = _rows(137, dates_and_maps=[
        (1000, "supply", 1, "2026-07-18"),
        (1600, "supply", 2, "2026-07-18"),
    ])
    db = FakeScopeDB(rounds_by_gsid={137: rounds})

    scope = await resolve_gaming_session_scope(db, gaming_session_id=137)

    assert scope.gaming_session_id == 137
    assert scope.dates == ("2026-07-18",)
    assert scope.accepted_round_count == 2
    assert scope.distinct_map_names == ("supply",)
    assert scope.round_keys == ((1000, "supply", 1), (1600, "supply", 2))
    assert scope.scope_version == "gaming-session-v1"


@pytest.mark.asyncio
async def test_midnight_crossing_session_resolves_all_dates_from_either_side():
    """The production repro: a session spanning two calendar dates must
    resolve to ONE scope containing BOTH dates, regardless of which date
    the caller queried by."""
    rounds = _rows(137, dates_and_maps=[
        (1000, "supply", 1, "2026-07-18"),
        (1600, "supply", 2, "2026-07-18"),
        (5000, "radar", 1, "2026-07-19"),  # crosses midnight
        (5600, "radar", 2, "2026-07-19"),
    ])
    db = FakeScopeDB(
        gsids_for_date={
            "2026-07-18": [(137, "2026-07-18", "2026-07-19", 4)],
            "2026-07-19": [(137, "2026-07-18", "2026-07-19", 4)],
        },
        rounds_by_gsid={137: rounds},
    )

    scope_from_day1 = await resolve_gaming_session_scope(db, session_date="2026-07-18")
    scope_from_day2 = await resolve_gaming_session_scope(db, session_date="2026-07-19")

    assert scope_from_day1.gaming_session_id == 137
    assert scope_from_day1.dates == ("2026-07-18", "2026-07-19")
    assert scope_from_day1.accepted_round_count == 4
    assert scope_from_day1 == scope_from_day2  # same session regardless of entry date


@pytest.mark.asyncio
async def test_two_sessions_same_date_returns_409_with_candidates():
    """Owner decision: ambiguous date -> 409 with candidates, NEVER a
    LIMIT 1 guess (the exact bug the old box-score query had)."""
    db = FakeScopeDB(
        gsids_for_date={
            "2026-07-18": [
                (201, "2026-07-18", "2026-07-18", 12),
                (202, "2026-07-18", "2026-07-18", 8),
            ],
        },
    )

    with pytest.raises(AmbiguousSessionDateError) as exc_info:
        await resolve_gaming_session_scope(db, session_date="2026-07-18")

    assert exc_info.value.status_code == 409
    detail = exc_info.value.detail
    assert detail["code"] == "AMBIGUOUS_SESSION_DATE"
    candidate_ids = {c["gaming_session_id"] for c in detail["candidates"]}
    assert candidate_ids == {201, 202}


@pytest.mark.asyncio
async def test_repeated_map_plays_stay_distinct_round_keys():
    """Two plays of the same map/round_number in one session (a rematch)
    must NOT collapse into one round_key — round_start_unix disambiguates."""
    rounds = _rows(300, dates_and_maps=[
        (1000, "supply", 1, "2026-07-18"),
        (1600, "supply", 2, "2026-07-18"),
        (5000, "supply", 1, "2026-07-18"),  # rematch, same map+round_number
        (5600, "supply", 2, "2026-07-18"),
    ])
    db = FakeScopeDB(rounds_by_gsid={300: rounds})

    scope = await resolve_gaming_session_scope(db, gaming_session_id=300)

    assert scope.accepted_round_count == 4
    assert len(scope.round_keys) == 4  # all four stay distinct


@pytest.mark.asyncio
async def test_unknown_gaming_session_id_is_404():
    db = FakeScopeDB(rounds_by_gsid={})

    with pytest.raises(HTTPException) as exc_info:
        await resolve_gaming_session_scope(db, gaming_session_id=9999)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_unknown_session_date_is_404():
    db = FakeScopeDB(gsids_for_date={})

    with pytest.raises(HTTPException) as exc_info:
        await resolve_gaming_session_scope(db, session_date="2020-01-01")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_both_params_supplied_is_422():
    db = FakeScopeDB()

    with pytest.raises(HTTPException) as exc_info:
        await resolve_gaming_session_scope(
            db, gaming_session_id=1, session_date="2026-07-18"
        )

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_neither_param_supplied_is_422():
    db = FakeScopeDB()

    with pytest.raises(HTTPException) as exc_info:
        await resolve_gaming_session_scope(db)

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_list_recent_scopes_raises_503_on_sqlite_backend():
    """STRING_AGG is PostgreSQL-only — SQLite (local dev fallback, per
    CLAUDE.md) must fail loudly, never silently return an empty/wrong
    session list (D4: degraded, never a silent fallback)."""
    db = FakeScopeDB()
    db.db_path = "/tmp/local-dev.sqlite3"  # duck-typed SQLite marker

    with pytest.raises(ScopeBackendUnsupportedError) as exc_info:
        await list_recent_scopes(db)

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["code"] == "SCOPE_BACKEND_UNSUPPORTED"
    assert db.calls == []  # never even attempted the STRING_AGG query


def test_scope_to_metadata_shape():
    from website.backend.services.session_scope import GamingSessionScope

    scope = GamingSessionScope(
        gaming_session_id=137,
        dates=("2026-07-18", "2026-07-19"),
        round_keys=((1000, "supply", 1),),
        accepted_round_count=23,
        distinct_map_names=("supply", "radar"),
    )
    meta = scope.to_metadata()
    assert meta == {
        "kind": "gaming_session",
        "version": "gaming-session-v1",
        "gaming_session_id": 137,
        "dates": ["2026-07-18", "2026-07-19"],
        "accepted_round_count": 23,
        "distinct_map_names": ["supply", "radar"],
    }


# ── Per-panel multi-date query filters (deep SS-C) ────────────────────


def _scope_with_keys(round_keys):
    from website.backend.services.session_scope import GamingSessionScope
    return GamingSessionScope(
        gaming_session_id=137,
        dates=("2026-07-18", "2026-07-19"),
        round_keys=tuple(round_keys),
        accepted_round_count=len(round_keys),
        distinct_map_names=("supply",),
    )


def test_round_key_arrays_unzips_in_order():
    """The three parallel arrays must line up index-for-index with the
    scope's round_keys (unnest binds them positionally)."""
    scope = _scope_with_keys([(1000, "supply", 1), (1600, "radar", 2)])
    starts, maps, rnums = scope.round_key_arrays()
    assert starts == [1000, 1600]
    assert maps == ["supply", "radar"]
    assert rnums == [1, 2]


def test_round_key_arrays_coerces_types():
    """round_start_unix/round_number coerced to int, map_name to str, so a
    stray Decimal/str from the resolver can't break asyncpg array binding."""
    scope = _scope_with_keys([("1000", "supply", "1")])
    starts, maps, rnums = scope.round_key_arrays()
    assert starts == [1000] and rnums == [1]
    assert maps == ["supply"]


def test_round_key_filter_sql_binds_three_consecutive_params():
    """Fragment must reference exactly $n,$n+1,$n+2 with the array casts,
    so callers append round_key_arrays() at those positions."""
    scope = _scope_with_keys([(1000, "supply", 1)])
    sql = scope.round_key_filter_sql(5)
    assert "$5::bigint[]" in sql
    assert "$6::text[]" in sql
    assert "$7::int[]" in sql
    assert "round_start_unix" in sql and "map_name" in sql and "round_number" in sql


def test_round_key_filter_sql_alias_qualifies_columns():
    """With an alias, the row columns must be prefixed (st.round_start_unix)
    so a joined/aliased proximity table filters on the right relation."""
    scope = _scope_with_keys([(1000, "supply", 1)])
    sql = scope.round_key_filter_sql(1, alias="st")
    assert "st.round_start_unix" in sql
    assert "st.map_name" in sql
    assert "st.round_number" in sql


def test_round_key_filter_sql_no_alias_leaves_columns_bare():
    scope = _scope_with_keys([(1000, "supply", 1)])
    sql = scope.round_key_filter_sql(1)
    # The three row columns must be compared BARE (no table-alias prefix),
    # even though the unnest helper column `_rk.*` is always prefixed.
    assert "= round_start_unix" in sql
    assert "= map_name" in sql
    assert "= round_number" in sql
    # ...and no dot-qualified form of the row columns leaked in (which is
    # exactly what alias mode would produce, e.g. `= st.round_start_unix`).
    assert ".round_start_unix" not in sql
    assert ".map_name" not in sql
    assert ".round_number" not in sql
