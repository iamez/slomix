"""Tests for SessionDataService — DB query orchestration for !last_session.

This service is the data backbone for `!last_session` and the website
session views. A regression silently:

- `get_latest_session_date`: SQL filter drops in-progress rounds → bot
  posts stale "latest session" hours after a new one started.
- `fetch_session_data`: returns rounds from MULTIPLE gaming sessions
  if filter slips → midnight-spanning previous session bleeds into
  today's stats.
- `get_hardcoded_teams`: empty session_ids list NOT short-circuited →
  query fires `WHERE id IN ()` (PostgreSQL syntax error).
- `get_hardcoded_teams`: player_guids stored as JSON string vs native
  list (asyncpg vs SQLite return different types) — falling-through
  branch breaks one of the two backends silently.
- `build_team_mappings` hardcoded path: team name extraction wrong order
  → "Team A" and "Team B" swapped on every embed.
- `build_team_mappings` auto-detect: empty record set crashes with
  StopIteration on `next(iter(all_guids))`.

Pin the public-method contract so a refactor that re-orders branches
(or drops a `.get` default) is loud.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from bot.services.session_data_service import SessionDataService


@pytest.fixture
def db():
    a = AsyncMock()
    a.fetch_one = AsyncMock(return_value=None)
    a.fetch_all = AsyncMock(return_value=[])
    a.execute = AsyncMock(return_value=None)
    return a


@pytest.fixture
def service(db):
    return SessionDataService(db_adapter=db)


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


def test_init_stores_db_adapter(db):
    s = SessionDataService(db)
    assert s.db_adapter is db
    assert s.db_path is None


def test_init_stores_optional_db_path(db):
    """db_path is for legacy SQLite stopwatch_scoring fallback. Pin so
    the optional kwarg stays optional (production never sets it)."""
    s = SessionDataService(db, db_path="/tmp/fake.sqlite3")
    assert s.db_path == "/tmp/fake.sqlite3"


# ---------------------------------------------------------------------------
# get_latest_session_date
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_latest_session_date_returns_none_when_db_empty(service, db):
    """No rows → None (NOT crash on `result[0]`)."""
    db.fetch_one = AsyncMock(return_value=None)
    out = await service.get_latest_session_date()
    assert out is None


@pytest.mark.asyncio
async def test_get_latest_session_date_returns_first_column(service, db):
    """Returns row[0] — the date string. Pin so a refactor that
    selects extra columns and indexes wrong doesn't break callers."""
    db.fetch_one = AsyncMock(return_value=("2026-05-07",))
    out = await service.get_latest_session_date()
    assert out == "2026-05-07"


@pytest.mark.asyncio
async def test_get_latest_session_date_excludes_in_progress_rounds(service, db):
    """SQL filter must restrict to round_status IN
    ('completed', 'cancelled', 'substitution') OR NULL — pin so
    half-imported rounds don't surface as "latest"."""
    db.fetch_one = AsyncMock(return_value=("2026-05-07",))
    await service.get_latest_session_date()
    args, _ = db.fetch_one.await_args
    sql = args[0]
    assert "completed" in sql
    assert "cancelled" in sql
    assert "substitution" in sql


@pytest.mark.asyncio
async def test_get_latest_session_date_filters_to_r1_r2_only(service, db):
    """`round_number IN (1, 2)` — pin so R0 match summaries never set
    "latest session date" by themselves (R0 is cumulative, not a play)."""
    db.fetch_one = AsyncMock(return_value=("2026-05-07",))
    await service.get_latest_session_date()
    args, _ = db.fetch_one.await_args
    sql = args[0]
    assert "round_number IN (1, 2)" in sql


# ---------------------------------------------------------------------------
# fetch_session_data — gaming_session_id scoping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_session_data_returns_quad_none_when_no_gsid(service, db):
    """No gaming_session_id in DB → (None, None, None, 0) tuple of
    length 4. Pin tuple shape so caller's 4-way unpack doesn't crash."""
    db.fetch_one = AsyncMock(return_value=(None,))
    out = await service.fetch_session_data("2026-05-07")
    assert out == (None, None, None, 0)


@pytest.mark.asyncio
async def test_fetch_session_data_returns_quad_none_when_no_rounds(service, db):
    """gaming_session_id exists but no R1/R2 rounds → (None, None, None, 0)."""
    db.fetch_one = AsyncMock(return_value=(42,))
    db.fetch_all = AsyncMock(return_value=[])
    out = await service.fetch_session_data("2026-05-07")
    assert out == (None, None, None, 0)


@pytest.mark.asyncio
async def test_fetch_session_data_uses_max_gaming_session_id(service, db):
    """Fetches MAX(gaming_session_id) — the LATEST session globally,
    not a per-date max. Pin the bug-fix from production: a session
    spanning midnight must be one session, not two."""
    db.fetch_one = AsyncMock(return_value=(99,))
    db.fetch_all = AsyncMock(return_value=[])
    await service.fetch_session_data("2026-05-07")
    # First fetch_one call: SELECT MAX(gaming_session_id)
    first_args, _ = db.fetch_one.await_args_list[0]
    assert "MAX(gaming_session_id)" in first_args[0]


@pytest.mark.asyncio
async def test_fetch_session_data_returns_4_tuple_shape_on_success(service, db):
    """Success path: (sessions, session_ids, session_ids_str, count)."""
    db.fetch_one = AsyncMock(side_effect=[
        (42,),            # MAX(gaming_session_id)
        (5,),             # COUNT(DISTINCT player_guid)
    ])
    db.fetch_all = AsyncMock(return_value=[
        (101, "oasis", 1, 240),
        (102, "oasis", 2, 180),
    ])
    sessions, session_ids, ids_str, player_count = await service.fetch_session_data("2026-05-07")
    assert len(sessions) == 2
    assert session_ids == [101, 102]
    assert ids_str == "?,?"
    assert player_count == 5


# ---------------------------------------------------------------------------
# get_hardcoded_teams
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hardcoded_teams_empty_session_ids_returns_none(service, db):
    """Empty session_ids → None immediately (no SQL `IN ()` syntax error)."""
    out = await service.get_hardcoded_teams([])
    assert out is None
    db.fetch_all.assert_not_awaited()


@pytest.mark.asyncio
async def test_hardcoded_teams_parses_json_string_columns(service, db):
    """player_guids and player_names stored as JSON strings (asyncpg
    sometimes returns these unparsed) → parsed via json.loads.

    Pin so a SQLite/asyncpg backend swap doesn't leave guids as a
    raw string '["guid1", "guid2"]' downstream."""
    db.fetch_all = AsyncMock(side_effect=[
        [(7,)],                                                           # gsid lookup
        [
            ("Puran", json.dumps(["guid1", "guid2"]), json.dumps(["a", "b"])),
        ],                                                                # session_teams rows
    ])
    out = await service.get_hardcoded_teams([101])
    assert out == {"Puran": {"guids": ["guid1", "guid2"], "names": ["a", "b"]}}


@pytest.mark.asyncio
async def test_hardcoded_teams_passes_through_native_lists(service, db):
    """If columns are already native lists (postgres jsonb auto-decoded)
    → use as-is, no double-parse."""
    db.fetch_all = AsyncMock(side_effect=[
        [(7,)],
        [
            ("Sk", ["g1", "g2"], ["n1", "n2"]),
        ],
    ])
    out = await service.get_hardcoded_teams([101])
    assert out["Sk"]["guids"] == ["g1", "g2"]
    assert out["Sk"]["names"] == ["n1", "n2"]


@pytest.mark.asyncio
async def test_hardcoded_teams_handles_empty_json_string(service, db):
    """player_guids = '' (empty string) → empty list (NOT json.loads
    crash on empty input)."""
    db.fetch_all = AsyncMock(side_effect=[
        [(7,)],
        [
            ("X", "", ""),
        ],
    ])
    out = await service.get_hardcoded_teams([101])
    assert out["X"]["guids"] == []
    assert out["X"]["names"] == []


@pytest.mark.asyncio
async def test_hardcoded_teams_dedupes_by_team_name(service, db):
    """If session_teams has multiple rows per team (legacy bug had
    dual creation), the FIRST row wins. Pin so a refactor doesn't
    silently merge rosters."""
    db.fetch_all = AsyncMock(side_effect=[
        [(7,)],
        [
            ("Puran", ["g1"], ["a"]),
            ("Puran", ["g2"], ["b"]),  # ignored
        ],
    ])
    out = await service.get_hardcoded_teams([101])
    assert out["Puran"]["guids"] == ["g1"]


@pytest.mark.asyncio
async def test_hardcoded_teams_returns_none_on_db_exception(service, db):
    """Outer try/except → None on any error (no logging crash).
    Pin the fail-safe so a transient DB error doesn't bubble to user."""
    db.fetch_all = AsyncMock(side_effect=RuntimeError("DB down"))
    out = await service.get_hardcoded_teams([101])
    assert out is None


# ---------------------------------------------------------------------------
# build_team_mappings — hardcoded path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_mappings_hardcoded_extracts_first_two_team_names(service, db):
    """Team name iteration order from dict.keys() — first two names
    become Team 1 and Team 2. Pin observed semantics so a refactor
    doesn't silently swap displays."""
    db.fetch_all = AsyncMock(return_value=[
        ("playerA", "g1"),
        ("playerB", "g2"),
    ])
    teams = {
        "Puran": {"guids": ["g1"], "names": ["playerA"]},
        "Sk":    {"guids": ["g2"], "names": ["playerB"]},
    }
    t1, t2, t1p, t2p, name_to_team = await service.build_team_mappings(
        [101], "?", teams
    )
    assert t1 == "Puran"
    assert t2 == "Sk"
    assert "playerA" in t1p
    assert "playerB" in t2p


@pytest.mark.asyncio
async def test_build_mappings_hardcoded_single_team_falls_back_to_default(service, db):
    """Only one team in hardcoded dict → second slot becomes "Team B"
    placeholder. Pin so a malformed row doesn't crash with IndexError."""
    db.fetch_all = AsyncMock(return_value=[("playerA", "g1")])
    teams = {"Puran": {"guids": ["g1"], "names": ["playerA"]}}
    t1, t2, *_ = await service.build_team_mappings([101], "?", teams)
    assert t1 == "Puran"
    assert t2 == "Team B"


@pytest.mark.asyncio
async def test_build_mappings_hardcoded_empty_dict_falls_through_to_defaults(service, db):
    """Empty dict is FALSY → falls into auto-detect path. Pin so a
    `{}` from the prior call doesn't render embeds with "Team A" /
    "Team B" headers despite hardcoded path being requested."""
    db.fetch_all = AsyncMock(return_value=[])  # auto-detect: no records
    out = await service.build_team_mappings([101], "?", {})
    # Auto-detect path with no records returns "Team 1" / "Team 2"
    assert out[0] == "Team 1"
    assert out[1] == "Team 2"


@pytest.mark.asyncio
async def test_build_mappings_hardcoded_maps_unknown_player_to_no_team(service, db):
    """A player in player_comprehensive_stats whose GUID isn't in any
    hardcoded team → NOT in name_to_team mapping (silently dropped).
    Pin so a substitute who arrived after team creation isn't auto-
    bucketed into the wrong team."""
    db.fetch_all = AsyncMock(return_value=[
        ("playerA", "g1"),
        ("substitute", "g_unknown"),
    ])
    teams = {
        "Puran": {"guids": ["g1"], "names": ["playerA"]},
        "Sk":    {"guids": [], "names": []},
    }
    *_, name_to_team = await service.build_team_mappings([101], "?", teams)
    assert "playerA" in name_to_team
    assert "substitute" not in name_to_team


# ---------------------------------------------------------------------------
# build_team_mappings — auto-detect path edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_mappings_auto_detect_no_records_returns_empty(service, db):
    """No rows from player_comprehensive_stats → ("Team 1", "Team 2",
    [], [], {}). Pin tuple shape so the unpacker doesn't crash on a
    fresh-bot, no-data state."""
    db.fetch_all = AsyncMock(return_value=[])
    out = await service.build_team_mappings([101], "?", None)
    assert out == ("Team 1", "Team 2", [], [], {})


# ---------------------------------------------------------------------------
# calculate_team_scores — graceful fallback when stopwatch unavailable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_calculate_team_scores_returns_zero_when_no_db_path(service):
    """No db_path (production PostgreSQL mode) → returns
    ('Team 1', 'Team 2', 0, 0, None) — pin the no-op fallback so a
    PostgreSQL deploy doesn't crash on missing stopwatch_scoring helper."""
    out = await service.calculate_team_scores([101])
    assert out == ("Team 1", "Team 2", 0, 0, None)


@pytest.mark.asyncio
async def test_calculate_team_scores_returns_zero_when_stopwatch_module_missing(db):
    """Even if db_path is set, if StopwatchScoring import failed →
    no-op fallback. Pin so an environment that lacks the optional
    module doesn't break commands."""
    import bot.services.session_data_service as mod
    s = SessionDataService(db, db_path="/tmp/fake.db")
    original = mod.StopwatchScoring
    mod.StopwatchScoring = None
    try:
        out = await s.calculate_team_scores([101])
        assert out == ("Team 1", "Team 2", 0, 0, None)
    finally:
        mod.StopwatchScoring = original
