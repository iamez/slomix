"""Tests for `resolve_player_guid` + `resolve_player_guids`.

This module is the single canonical lookup chain for "name → GUID"
across all analytics cogs. A regression silently:

- Wrong order of fallbacks → exact name match overridden by aliases.
- Missing escape on LIKE → wildcard injection (`%`/`_` in user input).
- Missing exception swallow → aliases table absent crashes lookup.

Pin every fallback step + the SQL escape contract.
"""
from __future__ import annotations

import pytest

from bot.services.player_resolver_service import (
    resolve_player_guid,
    resolve_player_guids,
)


class _FakeDb:
    """Stub that returns canned rows in the exact order they're queried.

    The lookup chain runs 4 fetch_one calls (in the worst case);
    each call gets the next row from the script."""
    def __init__(self, script=None, raise_on_aliases=False):
        self.script = list(script or [])
        self.raise_on_aliases = raise_on_aliases
        self.queries = []
        self.params = []

    async def fetch_one(self, query, params=None):
        self.queries.append(query)
        self.params.append(params)
        if self.raise_on_aliases and "player_aliases" in query:
            raise RuntimeError("aliases table missing")
        if self.script:
            return self.script.pop(0)
        return None


# ---------------------------------------------------------------------------
# resolve_player_guid — single-name resolution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_returns_none_for_empty_string():
    db = _FakeDb()
    out = await resolve_player_guid(db, "")
    assert out is None
    assert db.queries == []  # no DB call


@pytest.mark.asyncio
async def test_returns_none_for_whitespace_only():
    """`"   "` after .strip() → empty → no DB call."""
    db = _FakeDb()
    out = await resolve_player_guid(db, "   ")
    assert out is None
    assert db.queries == []


@pytest.mark.asyncio
async def test_returns_none_for_none_input():
    db = _FakeDb()
    out = await resolve_player_guid(db, None)
    assert out is None


@pytest.mark.asyncio
async def test_strips_whitespace_before_lookup():
    """Leading/trailing whitespace stripped; the bound param is the
    cleaned value."""
    db = _FakeDb(script=[("guid-found",)])  # exact GUID hit
    await resolve_player_guid(db, "  guid-x  ")
    assert db.params[0] == ("guid-x",)


@pytest.mark.asyncio
async def test_step1_exact_guid_match_short_circuits():
    """Step 1 hit → return immediately, NO further DB calls."""
    db = _FakeDb(script=[("guid-x",)])
    out = await resolve_player_guid(db, "guid-x")
    assert out == "guid-x"
    assert len(db.queries) == 1


@pytest.mark.asyncio
async def test_step2_exact_name_match_when_no_guid():
    """Step 1 misses → step 2 fires; case-insensitive."""
    db = _FakeDb(script=[None, ("guid-from-name",)])
    out = await resolve_player_guid(db, "Alice")
    assert out == "guid-from-name"
    assert len(db.queries) == 2
    assert "LOWER(player_name)" in db.queries[1]


@pytest.mark.asyncio
async def test_step3_partial_name_like_when_no_exact():
    """Steps 1+2 miss → step 3: LIKE %identifier% with escaped wildcards."""
    db = _FakeDb(script=[None, None, ("guid-partial",)])
    out = await resolve_player_guid(db, "Ali")
    assert out == "guid-partial"
    assert len(db.queries) == 3
    # Step 3 param is wrapped in %...%
    assert db.params[2] == ("%Ali%",)


@pytest.mark.asyncio
async def test_step3_escapes_wildcards_in_user_input():
    """Wildcard injection prevention: `%` and `_` in user input must
    be escaped before being wrapped in `%...%`. Pin so a regression
    that drops escape_like_pattern silently lets users craft
    user names that match every player."""
    db = _FakeDb(script=[None, None, ("guid",)])
    await resolve_player_guid(db, "100%match")
    # Param is "%100\\%match%" (escaped percent in middle)
    assert db.params[2] == ("%100\\%match%",)


@pytest.mark.asyncio
async def test_step4_aliases_when_no_partial_match():
    """Steps 1-3 miss → step 4: alias table."""
    db = _FakeDb(script=[None, None, None, ("guid-from-alias",)])
    out = await resolve_player_guid(db, "OldNick")
    assert out == "guid-from-alias"
    assert len(db.queries) == 4
    assert "player_aliases" in db.queries[3]


@pytest.mark.asyncio
async def test_step4_aliases_table_missing_returns_none():
    """If aliases table doesn't exist (legacy DB), exception is swallowed
    and we return None gracefully — pin so a fresh DB without that
    table doesn't crash the cog."""
    db = _FakeDb(
        script=[None, None, None],  # steps 1-3 miss
        raise_on_aliases=True,
    )
    out = await resolve_player_guid(db, "Ghost")
    assert out is None


@pytest.mark.asyncio
async def test_returns_none_when_all_steps_miss():
    db = _FakeDb(script=[None, None, None, None])
    out = await resolve_player_guid(db, "NobodyEverHeardOf")
    assert out is None


@pytest.mark.asyncio
async def test_step1_returns_none_when_row_has_null_guid():
    """Step 1 row exists but `[0]` is falsy → fall through to step 2.
    Pin the truthiness check (NOT just `if row:`)."""
    db = _FakeDb(script=[(None,), ("step2-guid",)])
    out = await resolve_player_guid(db, "Alice")
    assert out == "step2-guid"


@pytest.mark.asyncio
async def test_step2_uses_case_insensitive_lookup():
    """Step 2 query uses LOWER on both sides — pin so a regression
    that drops one side silently breaks for mixed-case stored names."""
    db = _FakeDb(script=[None, ("guid",)])
    await resolve_player_guid(db, "alice")
    assert "LOWER(player_name)" in db.queries[1]
    assert "LOWER(?)" in db.queries[1]


@pytest.mark.asyncio
async def test_step3_orders_by_max_round_date_desc():
    """Step 3 picks the MOST RECENT player matching the partial name.
    Pin so a regression to ASC silently returns ancient nicknames."""
    db = _FakeDb(script=[None, None, ("guid",)])
    await resolve_player_guid(db, "Ali")
    assert "MAX(round_date) DESC" in db.queries[2]


@pytest.mark.asyncio
async def test_step4_orders_by_last_seen_desc():
    """Aliases table → most-recent alias wins."""
    db = _FakeDb(script=[None, None, None, ("guid",)])
    await resolve_player_guid(db, "OldNick")
    assert "last_seen DESC" in db.queries[3]


# ---------------------------------------------------------------------------
# resolve_player_guids — batch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_returns_resolved_guids_only():
    """Names that don't resolve are SKIPPED — output may be shorter than
    input. Pin so a caller iterating zip(names, guids) doesn't get
    desynced (would mis-attribute stats)."""
    db = _FakeDb(script=[
        # name1: step 1 hit
        ("guid1",),
        # name2: step 1, 2, 3, 4 all miss
        None, None, None, None,
        # name3: step 1 hit
        ("guid3",),
    ])
    out = await resolve_player_guids(db, ["name1", "name2", "name3"])
    assert out == ["guid1", "guid3"]


@pytest.mark.asyncio
async def test_batch_returns_empty_for_empty_input():
    db = _FakeDb()
    out = await resolve_player_guids(db, [])
    assert out == []
    assert db.queries == []


@pytest.mark.asyncio
async def test_batch_preserves_order_for_resolved_guids():
    """Resolved GUIDs maintain input order (NOT sorted)."""
    db = _FakeDb(script=[
        ("guid-c",),  # name1
        ("guid-a",),  # name2
        ("guid-b",),  # name3
    ])
    out = await resolve_player_guids(db, ["name1", "name2", "name3"])
    assert out == ["guid-c", "guid-a", "guid-b"]


@pytest.mark.asyncio
async def test_batch_handles_each_name_independently():
    """One name failing doesn't affect others."""
    db = _FakeDb(script=[
        # name1: step 1 hit
        ("guid1",),
        # name2: step 1 miss, step 2 miss, step 3 miss, step 4 raise → None
        None, None, None,
    ], raise_on_aliases=True)
    out = await resolve_player_guids(db, ["name1", "name2"])
    assert out == ["guid1"]
