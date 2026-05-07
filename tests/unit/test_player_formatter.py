"""Tests for PlayerFormatter — global player name display service.

This is the canonical source for "how a player is shown" across every
bot command (leaderboard, !last_session, profile embeds, etc.).
A regression silently:

- Breaks display-name lookup → linked players show as in-game names.
- Breaks badge attachment → achievements vanish from leaderboards.
- Breaks the cache → display-name lookups N+1 the database on every
  embed render (perf catastrophe).

Pin the contract for `get_display_name`, `format_player`, and
`format_players_batch`.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from bot.services.player_formatter import PlayerFormatter


class _FakeBadgeService:
    """Stub that returns a predictable badge string per GUID."""
    def __init__(self, badges_by_guid=None):
        self.badges_by_guid = badges_by_guid or {}
        self.calls = 0

    async def get_player_badges(self, guid, session_stats=None):
        self.calls += 1
        return self.badges_by_guid.get(guid, "")


class _FakeDb:
    """Captures last query/params + returns canned rows."""
    def __init__(self, fetch_one_row=None, fetch_all_rows=None,
                 raise_on_one=None, raise_on_all=None):
        self.fetch_one_row = fetch_one_row
        self.fetch_all_rows = fetch_all_rows or []
        self.raise_on_one = raise_on_one
        self.raise_on_all = raise_on_all
        self.last_one_query = None
        self.last_one_params = None
        self.last_all_query = None
        self.last_all_params = None

    async def fetch_one(self, query, params=None):
        self.last_one_query = query
        self.last_one_params = params
        if self.raise_on_one:
            raise self.raise_on_one
        return self.fetch_one_row

    async def fetch_all(self, query, params=None):
        self.last_all_query = query
        self.last_all_params = params
        if self.raise_on_all:
            raise self.raise_on_all
        return self.fetch_all_rows


@pytest.fixture
def make_formatter():
    """Build a PlayerFormatter with a fake DB + injectable badge svc."""
    def _make(db=None, badge_service=None):
        db = db or _FakeDb()
        badge_service = badge_service or _FakeBadgeService()
        return PlayerFormatter(db_adapter=db, badge_service=badge_service)
    return _make


# ---------------------------------------------------------------------------
# get_display_name — DB lookup with cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_display_name_returns_custom_when_set(make_formatter):
    """player_links row with display_name → use it."""
    db = _FakeDb(fetch_one_row=("CustomName",))
    f = make_formatter(db=db)
    out = await f.get_display_name("guid1", "FallbackName")
    assert out == "CustomName"


@pytest.mark.asyncio
async def test_get_display_name_falls_back_when_no_row(make_formatter):
    """No DB row → fallback to in-game name."""
    db = _FakeDb(fetch_one_row=None)
    f = make_formatter(db=db)
    out = await f.get_display_name("guid1", "Fallback")
    assert out == "Fallback"


@pytest.mark.asyncio
async def test_get_display_name_falls_back_when_row_has_null(make_formatter):
    """Row exists but display_name is NULL → fallback. Pin so a future
    "trust the DB" change is loud."""
    db = _FakeDb(fetch_one_row=(None,))
    f = make_formatter(db=db)
    out = await f.get_display_name("guid1", "Fallback")
    assert out == "Fallback"


@pytest.mark.asyncio
async def test_get_display_name_uses_cache_on_second_call(make_formatter):
    """Second call for the same GUID does NOT hit DB. Pin so a
    regression that drops the cache silently N+1's the DB on every
    embed render."""
    db = _FakeDb(fetch_one_row=("CustomName",))
    f = make_formatter(db=db)
    out1 = await f.get_display_name("guid1", "fallback")
    db.last_one_query = None  # reset
    out2 = await f.get_display_name("guid1", "fallback2")
    assert out1 == "CustomName"
    assert out2 == "CustomName"  # cached
    assert db.last_one_query is None  # NO second DB call


@pytest.mark.asyncio
async def test_get_display_name_caches_negative_lookups(make_formatter):
    """Even when DB has no row, the negative result is cached so
    repeated lookups don't re-query. Critical for unlinked players."""
    db = _FakeDb(fetch_one_row=None)
    f = make_formatter(db=db)
    await f.get_display_name("guid1", "fb")
    db.last_one_query = None
    await f.get_display_name("guid1", "fb")
    assert db.last_one_query is None


@pytest.mark.asyncio
async def test_get_display_name_db_error_returns_fallback(make_formatter):
    """DB exception → fallback (NOT raise). Pin fail-safe so a
    transient DB hiccup doesn't crash a public command."""
    db = _FakeDb(raise_on_one=RuntimeError("connection lost"))
    f = make_formatter(db=db)
    out = await f.get_display_name("guid1", "fallback")
    assert out == "fallback"


@pytest.mark.asyncio
async def test_get_display_name_passes_guid_as_param(make_formatter):
    """Parameterised query — guid must be a bound param, not interpolated."""
    db = _FakeDb(fetch_one_row=("X",))
    f = make_formatter(db=db)
    await f.get_display_name("guid-abc", "fb")
    assert db.last_one_params == ("guid-abc",)


# ---------------------------------------------------------------------------
# format_player — combines display name + badges
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_format_player_combines_name_and_badges(make_formatter):
    db = _FakeDb(fetch_one_row=("CustomName",))
    badges = _FakeBadgeService(badges_by_guid={"guid1": "🏥🔧"})
    f = make_formatter(db=db, badge_service=badges)
    out = await f.format_player("guid1", "Fallback")
    assert out == "CustomName 🏥🔧"


@pytest.mark.asyncio
async def test_format_player_omits_badges_when_disabled(make_formatter):
    db = _FakeDb(fetch_one_row=("CustomName",))
    badges = _FakeBadgeService(badges_by_guid={"guid1": "🏥🔧"})
    f = make_formatter(db=db, badge_service=badges)
    out = await f.format_player("guid1", "Fallback", include_badges=False)
    assert out == "CustomName"
    assert badges.calls == 0  # badge service not called


@pytest.mark.asyncio
async def test_format_player_no_badges_no_trailing_space(make_formatter):
    """Empty badge string → no trailing space (no `Name `)."""
    db = _FakeDb(fetch_one_row=("Name",))
    badges = _FakeBadgeService()  # no badges
    f = make_formatter(db=db, badge_service=badges)
    out = await f.format_player("guid1", "Fallback")
    assert out == "Name"
    assert not out.endswith(" ")


@pytest.mark.asyncio
async def test_format_player_uses_fallback_when_no_custom(make_formatter):
    db = _FakeDb(fetch_one_row=None)
    badges = _FakeBadgeService(badges_by_guid={"guid1": "🎯"})
    f = make_formatter(db=db, badge_service=badges)
    out = await f.format_player("guid1", "InGame")
    assert out == "InGame 🎯"


# ---------------------------------------------------------------------------
# format_players_batch — bulk lookup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_returns_empty_dict_for_empty_list(make_formatter):
    """No players → empty dict (NOT None or list)."""
    f = make_formatter()
    out = await f.format_players_batch([])
    assert out == {}


@pytest.mark.asyncio
async def test_batch_formats_each_player(make_formatter):
    """Build placeholder + IN-clause query, attach display + badges
    per GUID."""
    # display_name fetch returns 2 rows; stats fetch returns 2 rows.
    # We use a single FakeDb where fetch_all returns the FIRST list,
    # then we'd need to switch — easier with side_effect mock.
    db = AsyncMock()
    db.fetch_all = AsyncMock(side_effect=[
        # First call: display_names
        [("guid1", "CustomA"), ("guid2", "CustomB")],
        # Second call: stats (for badges)
        [("guid1", 5, 0, 0, 0, 0, 0), ("guid2", 0, 10, 0, 0, 0, 0)],
    ])
    badges = _FakeBadgeService(badges_by_guid={"guid1": "🏥", "guid2": "🔧"})
    f = make_formatter(db=db, badge_service=badges)
    out = await f.format_players_batch([
        ("guid1", "InGameA"),
        ("guid2", "InGameB"),
    ])
    assert out["guid1"] == "CustomA 🏥"
    assert out["guid2"] == "CustomB 🔧"


@pytest.mark.asyncio
async def test_batch_falls_back_to_ingame_when_no_display(make_formatter):
    db = AsyncMock()
    db.fetch_all = AsyncMock(side_effect=[
        [],  # no display names
        [],  # no stats
    ])
    badges = _FakeBadgeService()
    f = make_formatter(db=db, badge_service=badges)
    out = await f.format_players_batch([("guid1", "Fallback")])
    assert out["guid1"] == "Fallback"


@pytest.mark.asyncio
async def test_batch_handles_db_error_in_display_names(make_formatter):
    """Display-name query fails → all players use fallback names."""
    db = AsyncMock()
    db.fetch_all = AsyncMock(side_effect=[
        RuntimeError("display query failed"),
        [],  # stats query still attempted
    ])
    badges = _FakeBadgeService()
    f = make_formatter(db=db, badge_service=badges)
    out = await f.format_players_batch([("guid1", "Fallback")])
    assert out["guid1"] == "Fallback"


@pytest.mark.asyncio
async def test_batch_skips_badges_when_flag_false(make_formatter):
    """include_badges=False → no second query, no badge service calls."""
    db = AsyncMock()
    db.fetch_all = AsyncMock(side_effect=[
        [("guid1", "Name1")],
    ])
    badges = _FakeBadgeService(badges_by_guid={"guid1": "🎯"})
    f = make_formatter(db=db, badge_service=badges)
    out = await f.format_players_batch(
        [("guid1", "Fallback")], include_badges=False,
    )
    assert out["guid1"] == "Name1"
    assert badges.calls == 0
    # Only ONE fetch_all (display names) — stats query skipped.
    assert db.fetch_all.await_count == 1


# ---------------------------------------------------------------------------
# __init__ wiring
# ---------------------------------------------------------------------------


def test_init_creates_default_badge_service_when_none_passed():
    """When badge_service=None, the formatter creates a real
    PlayerBadgeService. Pin so a future refactor that breaks the
    default DI doesn't silently disable badges."""
    from bot.services.player_badge_service import PlayerBadgeService
    db = AsyncMock()
    f = PlayerFormatter(db_adapter=db)
    assert isinstance(f.badge_service, PlayerBadgeService)


def test_init_uses_injected_badge_service():
    """Pin the injection seam — tests + DI containers rely on it."""
    db = AsyncMock()
    bs = _FakeBadgeService()
    f = PlayerFormatter(db_adapter=db, badge_service=bs)
    assert f.badge_service is bs


def test_init_starts_with_empty_display_name_cache():
    db = AsyncMock()
    f = PlayerFormatter(db_adapter=db, badge_service=_FakeBadgeService())
    assert f._display_name_cache == {}
