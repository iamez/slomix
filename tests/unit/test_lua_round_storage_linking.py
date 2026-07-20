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
    def __init__(self, *, has_round_id_column=True, null_candidates=None, stale_candidates=None):
        self.has_round_id_column = has_round_id_column
        self.null_candidates = null_candidates or []
        self.stale_candidates = stale_candidates or []
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
async def test_link_lua_round_teams_tied_candidates_currently_picks_first_arbitrarily():
    """L2 lock-in of the CURRENT gap (not desired behaviour): two candidates
    equally close to target_unix — neither an exact match to anything
    round_linker-side — silently resolves to whichever row the DB happened
    to return first. No ambiguity is signalled. This is the exact class of
    "guessing" a future exact-match-priority / tie-defer fix (L3) should
    close for this independent matcher, mirroring round_linker.py's fix."""
    target_unix = 1_776_800_000
    adapter = _FakeAdapter(null_candidates=[
        (10, target_unix - 100, None),  # tied: 100s away
        (20, target_unix + 100, None),  # tied: 100s away
    ])
    svc = _svc(adapter)

    await svc._link_lua_round_teams(round_id=42, metadata={
        "map_name": "supply", "round_number": 1, "round_end_unix": target_unix,
    })

    assert len(adapter.updates) == 1
    _, params = adapter.updates[0]
    assert params == (42, 10)  # first-iterated row silently wins the tie


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
