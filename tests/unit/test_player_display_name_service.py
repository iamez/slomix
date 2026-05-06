"""Tests for PlayerDisplayNameService — name resolution + custom-name CRUD.

This service decides what name a player shows up as everywhere in the
bot (embeds, leaderboards, achievements). A regression silently:

- Priority chain inverted → linked player's chosen name overridden by
  recent alias they actually wanted to hide.
- Length validation drift (≥2 / ≤32 chars) → DB column overflow or
  blank names slip through.
- `reset_display_name` doesn't NULL the column → "auto" mode still
  shows the cached custom name.
- Batch resolution: a guid present in the input list missing from the
  output dict → KeyError downstream when callers do `names[guid]`.
- Alias case-insensitive lookup falls through → user types the alias
  with different capitalisation and it's "not found".

Pin every priority-chain branch + every validation rule.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from bot.services.player_display_name_service import PlayerDisplayNameService


@pytest.fixture
def db():
    """A db_adapter with AsyncMock for fetch_one/fetch_all/execute."""
    adapter = AsyncMock()
    adapter.fetch_one = AsyncMock(return_value=None)
    adapter.fetch_all = AsyncMock(return_value=[])
    adapter.execute = AsyncMock(return_value=None)
    return adapter


@pytest.fixture
def service(db):
    return PlayerDisplayNameService(db_adapter=db)


# ---------------------------------------------------------------------------
# get_display_name — single-player priority chain
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_display_name_returns_custom_when_set(service, db):
    """Linked player with custom display_name → that name wins, no
    further DB queries needed for the resolution chain."""
    db.fetch_one = AsyncMock(return_value=("MyChosenName", "custom"))
    out = await service.get_display_name("guid123")
    assert out == "MyChosenName"


@pytest.mark.asyncio
async def test_get_display_name_falls_to_alias_when_no_custom(service, db):
    """No custom name → most-recent alias wins.

    Pin the strict priority order: link table queried FIRST, alias only
    consulted when display_name is NULL/missing."""
    db.fetch_one = AsyncMock(side_effect=[
        None,                # link query: not linked
        ("RecentAlias",),    # alias query: hit
    ])
    out = await service.get_display_name("guid123")
    assert out == "RecentAlias"


@pytest.mark.asyncio
async def test_get_display_name_link_with_null_display_falls_to_alias(service, db):
    """Linked but display_name IS NULL → fall through to alias.

    Pin so a player who linked then reset to auto still gets their
    most-recent alias (not their old custom name)."""
    db.fetch_one = AsyncMock(side_effect=[
        (None, "auto"),       # linked, but display_name=NULL
        ("CurrentAlias",),    # alias query
    ])
    out = await service.get_display_name("guid123")
    assert out == "CurrentAlias"


@pytest.mark.asyncio
async def test_get_display_name_falls_to_stats_when_no_alias(service, db):
    """No custom + no alias → stats table fallback."""
    db.fetch_one = AsyncMock(side_effect=[
        None,             # link
        None,             # alias
        ("StatsName",),   # stats fallback
    ])
    out = await service.get_display_name("guid123")
    assert out == "StatsName"


@pytest.mark.asyncio
async def test_get_display_name_returns_unknown_when_all_empty(service, db):
    """All three tiers empty → "Unknown Player". Pin so embed render
    never gets an empty string (which would render as zero-width)."""
    db.fetch_one = AsyncMock(return_value=None)
    out = await service.get_display_name("ghost-guid")
    assert out == "Unknown Player"


@pytest.mark.asyncio
async def test_get_display_name_swallows_exception_returns_unknown(service, db):
    """DB raises mid-chain → "Unknown Player" (NOT propagate). Pin
    so a rotating DB outage doesn't crash every embed mid-render."""
    db.fetch_one = AsyncMock(side_effect=RuntimeError("connection lost"))
    out = await service.get_display_name("guid123")
    assert out == "Unknown Player"


# ---------------------------------------------------------------------------
# get_display_names_batch — bulk priority resolution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_empty_input_returns_empty_dict(service, db):
    """No guids → no DB calls, empty dict. Pin so a caller passing
    an empty list (zero-roster session) doesn't fan out a `WHERE IN ()`
    that the planner can't handle."""
    out = await service.get_display_names_batch([])
    assert out == {}
    db.fetch_all.assert_not_awaited()


@pytest.mark.asyncio
async def test_batch_returns_link_names_when_all_have_custom(service, db):
    """Every guid has custom display_name → no alias/stats lookups.
    Pin the early-bail behaviour so we don't fire 3 queries when 1 suffices."""
    db.fetch_all = AsyncMock(return_value=[
        ("g1", "Custom1"),
        ("g2", "Custom2"),
    ])
    out = await service.get_display_names_batch(["g1", "g2"])
    assert out == {"g1": "Custom1", "g2": "Custom2"}
    # link query is the only one needed (1 fetch_all)
    assert db.fetch_all.await_count == 1


@pytest.mark.asyncio
async def test_batch_partial_link_then_alias_then_stats(service, db):
    """Three guids: g1 has custom, g2 has alias, g3 falls to stats.
    Pin the priority chain holds across mixed inputs."""
    db.fetch_all = AsyncMock(side_effect=[
        [("g1", "Custom1")],                # link query
        [("g2", "Alias2")],                 # alias query (only g2, g3)
        [("g3", "StatsName3")],             # stats query (only g3)
    ])
    out = await service.get_display_names_batch(["g1", "g2", "g3"])
    assert out == {"g1": "Custom1", "g2": "Alias2", "g3": "StatsName3"}


@pytest.mark.asyncio
async def test_batch_unresolved_guid_gets_unknown_fallback(service, db):
    """A guid with no link/alias/stats → "Unknown Player" in result.
    Pin so output dict ALWAYS has every input guid as key (callers
    do `names[guid]` directly, would KeyError on missing)."""
    db.fetch_all = AsyncMock(side_effect=[
        [],   # link: nothing
        [],   # alias: nothing
        [],   # stats: nothing
    ])
    out = await service.get_display_names_batch(["ghost1", "ghost2"])
    assert out == {"ghost1": "Unknown Player", "ghost2": "Unknown Player"}


@pytest.mark.asyncio
async def test_batch_returns_empty_dict_on_outer_exception(service, db):
    """Outer try/except catches everything → returns {} (NOT raise).
    Pin so a malformed DB schema doesn't crash the caller."""
    db.fetch_all = AsyncMock(side_effect=RuntimeError("db down"))
    out = await service.get_display_names_batch(["g1"])
    assert out == {}


# ---------------------------------------------------------------------------
# set_custom_display_name — validation + linkage check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_custom_rejects_too_short(service, db):
    """Length <2 → False, with explicit message. Pin lower bound."""
    ok, msg = await service.set_custom_display_name(123, "x")
    assert ok is False
    assert "at least 2" in msg
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_custom_rejects_too_long(service, db):
    """Length >32 → False. Pin upper bound (DB column is VARCHAR(32))."""
    ok, msg = await service.set_custom_display_name(123, "x" * 33)
    assert ok is False
    assert "32 characters" in msg
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_custom_accepts_2_char_minimum(service, db):
    """Exactly 2 chars → accepted (inclusive lower)."""
    db.fetch_one = AsyncMock(return_value=("guid123",))
    ok, msg = await service.set_custom_display_name(123, "ab")
    assert ok is True
    db.execute.assert_awaited()


@pytest.mark.asyncio
async def test_set_custom_accepts_32_char_maximum(service, db):
    """Exactly 32 chars → accepted (inclusive upper)."""
    db.fetch_one = AsyncMock(return_value=("guid123",))
    ok, msg = await service.set_custom_display_name(123, "x" * 32)
    assert ok is True


@pytest.mark.asyncio
async def test_set_custom_rejects_unlinked_user(service, db):
    """User not in player_links → False with link instructions.
    Pin so an unlinked Discord user can't ghost-update a row."""
    db.fetch_one = AsyncMock(return_value=None)
    ok, msg = await service.set_custom_display_name(123, "ValidName")
    assert ok is False
    assert "linked" in msg.lower()
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_custom_executes_update_when_linked(service, db):
    """Linked + valid → UPDATE fires with correct args."""
    db.fetch_one = AsyncMock(return_value=("guid123",))
    ok, msg = await service.set_custom_display_name(456, "NewName")
    assert ok is True
    assert "NewName" in msg
    # The execute call args[0] is (display_name, datetime, discord_id)
    args, _ = db.execute.await_args
    params = args[1]
    assert params[0] == "NewName"
    assert params[2] == 456


@pytest.mark.asyncio
async def test_set_custom_returns_false_on_exception(service, db):
    """DB error during update → (False, error msg). Pin so caller
    can show user feedback instead of a 500."""
    db.fetch_one = AsyncMock(return_value=("guid123",))
    db.execute = AsyncMock(side_effect=RuntimeError("update failed"))
    ok, msg = await service.set_custom_display_name(123, "Name")
    assert ok is False
    assert "Error" in msg


# ---------------------------------------------------------------------------
# set_alias_display_name — case-insensitive lookup, preserve DB casing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_alias_rejects_unlinked(service, db):
    db.fetch_one = AsyncMock(return_value=None)
    ok, msg = await service.set_alias_display_name(123, "anyalias")
    assert ok is False
    assert "linked" in msg.lower()


@pytest.mark.asyncio
async def test_set_alias_rejects_unknown_alias(service, db):
    """User is linked but the alias doesn't exist for their GUID → False."""
    db.fetch_one = AsyncMock(side_effect=[
        ("guid123",),   # link lookup hit
        None,           # alias lookup miss
    ])
    ok, msg = await service.set_alias_display_name(123, "fake-alias")
    assert ok is False
    assert "not found" in msg.lower()


@pytest.mark.asyncio
async def test_set_alias_preserves_db_capitalisation(service, db):
    """User passes "PURAN" but DB has "Puran" → DB casing wins.

    Pin so case-insensitive match doesn't lose the player's preferred
    display capitalisation. Also pin: passes the EXACT alias to UPDATE,
    not the user-typed casing."""
    db.fetch_one = AsyncMock(side_effect=[
        ("guid123",),   # link hit
        ("Puran",),     # alias hit (DB case)
    ])
    ok, msg = await service.set_alias_display_name(123, "PURAN")
    assert ok is True
    assert "Puran" in msg
    # UPDATE called with DB-cased alias
    args, _ = db.execute.await_args
    params = args[1]
    assert params[0] == "Puran"


# ---------------------------------------------------------------------------
# reset_display_name — clears custom + sets source='auto'
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reset_rejects_unlinked(service, db):
    db.fetch_one = AsyncMock(return_value=None)
    ok, msg = await service.reset_display_name(123)
    assert ok is False
    assert "linked" in msg.lower()


@pytest.mark.asyncio
async def test_reset_nulls_display_and_sets_source_auto(service, db):
    """Reset: display_name=NULL, source='auto'. Pin so "auto" mode
    stays auto (a leftover custom value would shadow the alias chain)."""
    db.fetch_one = AsyncMock(return_value=("guid123",))
    ok, msg = await service.reset_display_name(123)
    assert ok is True
    args, _ = db.execute.await_args
    sql = args[0]
    params = args[1]
    assert "display_name = NULL" in sql
    assert "'auto'" in sql
    # 2 params: timestamp + discord_id
    assert params[1] == 123


@pytest.mark.asyncio
async def test_reset_returns_false_on_db_error(service, db):
    db.fetch_one = AsyncMock(return_value=("guid123",))
    db.execute = AsyncMock(side_effect=RuntimeError("DB down"))
    ok, msg = await service.reset_display_name(123)
    assert ok is False
    assert "Error" in msg


# ---------------------------------------------------------------------------
# get_player_aliases — read-only listing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_aliases_returns_false_when_unlinked(service, db):
    """Unlinked → (False, []). Pin tuple shape — caller does
    `success, aliases = await ...` so a single None would crash."""
    db.fetch_one = AsyncMock(return_value=None)
    ok, aliases = await service.get_player_aliases(123)
    assert ok is False
    assert aliases == []


@pytest.mark.asyncio
async def test_get_aliases_returns_true_with_list(service, db):
    """Linked → (True, list of (alias, times_seen, last_seen) tuples)."""
    db.fetch_one = AsyncMock(return_value=("guid123",))
    db.fetch_all = AsyncMock(return_value=[
        ("Puran",  100, "2026-01-15"),
        ("p_uran", 50,  "2026-01-10"),
    ])
    ok, aliases = await service.get_player_aliases(123)
    assert ok is True
    assert len(aliases) == 2
    assert aliases[0][0] == "Puran"


@pytest.mark.asyncio
async def test_get_aliases_returns_false_on_exception(service, db):
    """DB error → (False, []). Pin shape so caller can `if ok:` safely."""
    db.fetch_one = AsyncMock(side_effect=RuntimeError("fail"))
    ok, aliases = await service.get_player_aliases(123)
    assert ok is False
    assert aliases == []
