"""L2 (Codex): regression lock on _link_lua_round_teams's CURRENT matching
behaviour, BEFORE any change (test/linkage-writer-lock).

_link_lua_round_teams (lua_round_storage_mixin.py) implements its OWN
independent nearest-neighbour matcher against lua_round_teams — it does NOT
call bot.core.round_linker at all, so round_linker's exact-match-first fix
does not apply here. Codex §18 found lua_round_teams among the tables with
the WORST wrong-round-linkage rates; these tests pin exactly what "closest
wins" means today, including the tied-candidate case where the current
strict `<` comparison silently picks whichever row was iterated first with
no ambiguity signal — the same class of "guessing" L3 addresses in
round_linker.py, but this is an independent implementation that needs its
own fix.
"""
from __future__ import annotations

import pytest

from bot.services.lua_round_storage_mixin import _LuaRoundStorageMixin


class _Cfg:
    round_match_window_minutes = 45


class _FakeAdapter:
    def __init__(
        self,
        *,
        has_round_id_column=True,
        null_candidates=None,
        stale_candidates=None,
        exact_lua_candidates=None,
        exact_round_candidates=None,
    ):
        self.has_round_id_column = has_round_id_column
        self.null_candidates = null_candidates or []
        self.stale_candidates = stale_candidates or []
        self.exact_lua_candidates = exact_lua_candidates or []
        self.exact_round_candidates = exact_round_candidates or []
        self.updates: list[tuple] = []
        self.round_lookups: dict[int, tuple] = {}

    async def fetch_one(self, query, params=None):
        q = " ".join(str(query).split())
        if "information_schema.columns" in q:
            return (1,) if self.has_round_id_column else None
        if "FROM rounds WHERE id" in q:
            rid = params[0]
            return self.round_lookups.get(rid)
        return None

    async def fetch_all(self, query, params=None):
        q = " ".join(str(query).split())
        if "SELECT id FROM rounds" in q and "round_start_unix = ?" in q:
            return self.exact_round_candidates
        if "SELECT id, round_id FROM lua_round_teams" in q:
            return self.exact_lua_candidates
        if "FROM lua_round_teams" in q and "round_id IS NULL" in q:
            return self.null_candidates
        if "lrt.round_id IS NOT NULL" in q:
            return self.stale_candidates
        return []

    async def execute(self, query, params=None):
        self.updates.append((str(query), params))


def _svc(adapter: _FakeAdapter) -> _LuaRoundStorageMixin:
    svc = _LuaRoundStorageMixin.__new__(_LuaRoundStorageMixin)
    svc.db_adapter = adapter
    svc.config = _Cfg()
    return svc


@pytest.mark.asyncio
async def test_lua_resolver_requires_unique_exact_start_when_available():
    start_unix = 1_776_800_000
    adapter = _FakeAdapter(exact_round_candidates=[(42,)])
    svc = _svc(adapter)

    round_id = await svc._resolve_lua_round_id_for_metadata({
        "map_name": "supply",
        "round_number": 1,
        "round_start_unix": start_unix,
        # A neighbouring round can be closer to end time; it must not matter.
        "round_end_unix": start_unix + 900,
    })

    assert round_id == 42


@pytest.mark.asyncio
async def test_lua_resolver_defers_missing_or_ambiguous_exact_start():
    metadata = {
        "map_name": "supply",
        "round_number": 1,
        "round_start_unix": 1_776_800_000,
        "round_end_unix": 1_776_800_900,
    }
    for candidates in ([], [(10,), (20,)]):
        adapter = _FakeAdapter(exact_round_candidates=candidates)
        svc = _svc(adapter)
        assert await svc._resolve_lua_round_id_for_metadata(metadata) is None


@pytest.mark.asyncio
async def test_lua_resolver_does_not_fuzzy_match_an_invalid_present_start():
    adapter = _FakeAdapter()
    svc = _svc(adapter)

    assert await svc._resolve_lua_round_id_for_metadata({
        "map_name": "supply",
        "round_number": 1,
        "round_start_unix": "not-a-timestamp",
        "round_end_unix": 1_776_800_900,
    }) is None
    assert adapter.updates == []


@pytest.mark.asyncio
async def test_link_lua_round_teams_uses_exact_source_start():
    start_unix = 1_776_800_000
    adapter = _FakeAdapter(
        exact_lua_candidates=[(77, 999)],
        exact_round_candidates=[(42,)],
    )
    svc = _svc(adapter)

    await svc._link_lua_round_teams(round_id=42, metadata={
        "map_name": "supply",
        "round_number": 1,
        "round_start_unix": start_unix,
        "round_end_unix": start_unix + 900,
    })

    assert adapter.updates == [
        ("UPDATE lua_round_teams SET round_id = ? WHERE id = ?", (42, 77))
    ]


@pytest.mark.asyncio
async def test_link_lua_round_teams_defers_nonunique_exact_source():
    adapter = _FakeAdapter(
        exact_lua_candidates=[(10, None), (20, 999)],
        exact_round_candidates=[(42,)],
    )
    svc = _svc(adapter)

    await svc._link_lua_round_teams(round_id=42, metadata={
        "map_name": "supply",
        "round_number": 1,
        "round_start_unix": 1_776_800_000,
    })

    assert adapter.updates == []


@pytest.mark.asyncio
async def test_link_lua_round_teams_rejects_a_neighboring_caller_round():
    adapter = _FakeAdapter(
        exact_lua_candidates=[(77, None)],
        exact_round_candidates=[(99,)],
    )
    svc = _svc(adapter)

    await svc._link_lua_round_teams(round_id=42, metadata={
        "map_name": "supply",
        "round_number": 1,
        "round_start_unix": 1_776_800_000,
    })

    assert adapter.updates == []


@pytest.mark.asyncio
async def test_link_lua_round_teams_picks_closest_of_multiple_null_candidates():
    """Baseline: with a clear winner (not tied), the closest candidate by
    |round_end/start_unix - target| links — this is the intended, correct
    behaviour and must survive any future change."""
    target_unix = 1_776_800_000
    # (id, round_end_unix, round_start_unix)
    adapter = _FakeAdapter(null_candidates=[
        (1, target_unix - 500, None),   # 500s away
        (2, target_unix - 50, None),    # 50s away — closest
        (3, target_unix + 900, None),   # 900s away
    ])
    svc = _svc(adapter)

    await svc._link_lua_round_teams(round_id=42, metadata={
        "map_name": "supply", "round_number": 1, "round_end_unix": target_unix,
    })

    assert len(adapter.updates) == 1
    _, params = adapter.updates[0]
    assert params == (42, 2)  # (round_id, lua_row_id) — row 2 was closest


@pytest.mark.asyncio
async def test_link_lua_round_teams_tied_candidates_defers_instead_of_guessing():
    """Codex §18/L3: two candidates equally close to target_unix — neither
    an exact match — must defer (no update), never silently pick whichever
    row the DB happened to return first. Mirrors round_linker.py's
    tie-defer fix for this independent matcher."""
    target_unix = 1_776_800_000
    adapter = _FakeAdapter(null_candidates=[
        (10, target_unix - 100, None),  # tied: 100s away
        (20, target_unix + 100, None),  # tied: 100s away
    ])
    svc = _svc(adapter)

    await svc._link_lua_round_teams(round_id=42, metadata={
        "map_name": "supply", "round_number": 1, "round_end_unix": target_unix,
    })

    assert adapter.updates == [], "a genuine tie must defer, never guess"


@pytest.mark.asyncio
async def test_link_lua_round_teams_no_null_candidates_is_noop():
    adapter = _FakeAdapter(null_candidates=[])
    svc = _svc(adapter)

    await svc._link_lua_round_teams(round_id=42, metadata={
        "map_name": "supply", "round_number": 1, "round_end_unix": 1_776_800_000,
    })

    assert adapter.updates == []


@pytest.mark.asyncio
async def test_link_lua_round_teams_second_pass_relinks_to_closer_match():
    """Stale-fix second pass: a lua_round_teams row already linked to a
    DIFFERENT round gets moved to THIS round if this round's target_unix is
    a closer match than the round it's currently linked to.

    Note: the second pass only runs if the FIRST pass's candidate query
    returned at least one row (`if not rows: return` exits the whole
    function before the second pass is ever reached) — a dummy
    unusable-timestamp row (both unix fields NULL) gets the function past
    that guard without itself being linkable."""
    target_unix = 1_776_800_000
    adapter = _FakeAdapter(
        null_candidates=[(999999, None, None)],
        # (lua_id, round_end_unix, round_start_unix, current_round_id)
        stale_candidates=[(77, target_unix + 30, None, 999)],
    )
    # The currently-linked round (999) is far away — this round is closer.
    adapter.round_lookups[999] = ("2020-01-01", "000000")
    svc = _svc(adapter)

    await svc._link_lua_round_teams(round_id=42, metadata={
        "map_name": "supply", "round_number": 1, "round_end_unix": target_unix,
    })

    update_queries = [q for q, _ in adapter.updates]
    assert any("SET round_id = ? WHERE id = ?" in q for q in update_queries)
    relink_params = [p for q, p in adapter.updates if "SET round_id = ? WHERE id = ?" in q]
    assert (42, 77) in relink_params


@pytest.mark.asyncio
async def test_link_lua_round_teams_missing_round_id_column_is_noop():
    """Schema without lua_round_teams.round_id (migration not run) — must
    exit cleanly, never raise."""
    adapter = _FakeAdapter(has_round_id_column=False, null_candidates=[(1, 1_776_800_000, None)])
    svc = _svc(adapter)

    await svc._link_lua_round_teams(round_id=42, metadata={
        "map_name": "supply", "round_number": 1, "round_end_unix": 1_776_800_000,
    })

    assert adapter.updates == []
