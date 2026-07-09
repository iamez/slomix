"""Tests for StorytellingService _LoadersMixin — DB → in-memory shapers.

These mixin methods convert SQL rows into dict-of-lists structures keyed
by the canonical round key `(round_start_unix, map_name, round_number)`
(guid-prefixed / kill_time-suffixed for some) built via `round_ctx_key`.
`round_start_unix` alone is NOT unique repo-wide — two rounds on different
maps can share a start second across sessions — so `map_name` is part of
every key, in the SAME order ois.py / ssr use (codex follow-up audit
#10/#11, Copilot PR #486 ordering review). The KIS compute in kis.py
consumes these loaders and `_score_kill` looks them up through the same
`round_ctx_key` helper, so build and lookup key shapes can never drift.

A regression silently:

- Key tuple shape/order drift → downstream lookups always miss →
  KIS scores all default to 0.
- map_name dropped from the key → two same-second rounds on different maps
  collide → one round's context bleeds into the other's kills.
- A loader keys by `kill_time` instead of the round key → grouping
  collapses across rounds, mixing R1 + R2 events.
- `setdefault(key, []).append(...)` swapped to `result[key] = ...` →
  multiple events per round overwrite each other → only last kill
  survives → impact totals shrink.
- `_load_victim_classes` first-write-wins flipped to last-write-wins:
  player class can flip mid-round (medic→soldier) and the wrong class
  gets attributed.
- NULL handling for numeric coercions changes → `float(None)` raises
  TypeError → endpoint 500s.
- Empty result handling (None → []) regresses → loader iterates None
  and crashes.

Pin every loader's key shape, NULL handling, and append/overwrite semantics.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest

from website.backend.services.storytelling.loaders import _LoadersMixin

MAP = "supply"
MAP2 = "goldrush"


class _Host(_LoadersMixin):
    """Minimal host that exposes `db` like StorytellingService does."""
    def __init__(self, db):
        self.db = db


@pytest.fixture
def db():
    a = AsyncMock()
    a.fetch_all = AsyncMock(return_value=[])
    return a


@pytest.fixture
def host(db):
    return _Host(db)


# ---------------------------------------------------------------------------
# _load_carrier_kills — (killer_guid, round_start_unix, map_name, round_number) → [kill_time]
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_carrier_kills_empty_result(host, db):
    """No rows → empty dict (NOT crash on `for r in None`)."""
    db.fetch_all = AsyncMock(return_value=[])
    out = await host._load_carrier_kills("2026-05-07")
    assert out == {}


@pytest.mark.asyncio
async def test_load_carrier_kills_handles_none_rows(host, db):
    """fetch_all → None (some adapters do for empty) → handled as empty."""
    db.fetch_all = AsyncMock(return_value=None)
    out = await host._load_carrier_kills("2026-05-07")
    assert out == {}


@pytest.mark.asyncio
async def test_load_carrier_kills_keys_by_canonical_round(host, db):
    """Key is `(killer_guid, round_start_unix, map_name, round_number)`. Pin
    the exact ordering — downstream consumers do `dict[(g, u, m, r)]`."""
    db.fetch_all = AsyncMock(return_value=[
        ("guidA", 1700000000, 1, 12.5, MAP),
    ])
    out = await host._load_carrier_kills("d")
    assert ("guidA", 1700000000, MAP, 1) in out


@pytest.mark.asyncio
async def test_load_carrier_kills_appends_multiple_events(host, db):
    """Multiple rows with same (guid, unix, map, round) → list of kill_times.
    Pin so a regression that switches to assignment loses repeat kills."""
    db.fetch_all = AsyncMock(return_value=[
        ("g1", 1700000000, 1, 5.0, MAP),
        ("g1", 1700000000, 1, 12.0, MAP),
        ("g1", 1700000000, 1, 30.0, MAP),
    ])
    out = await host._load_carrier_kills("d")
    assert out[("g1", 1700000000, MAP, 1)] == [5.0, 12.0, 30.0]


@pytest.mark.asyncio
async def test_load_carrier_kills_separates_rounds(host, db):
    """Different round_number → separate keys (R1 and R2 don't merge)."""
    db.fetch_all = AsyncMock(return_value=[
        ("g1", 1700000000, 1, 5.0, MAP),
        ("g1", 1700000000, 2, 8.0, MAP),
    ])
    out = await host._load_carrier_kills("d")
    assert out[("g1", 1700000000, MAP, 1)] == [5.0]
    assert out[("g1", 1700000000, MAP, 2)] == [8.0]


@pytest.mark.asyncio
async def test_load_carrier_kills_separates_maps_on_same_second(host, db):
    """Same (guid, unix, round) but DIFFERENT map → separate keys.

    This is the codex #10 collision: two rounds sharing a start second on
    different maps must NOT merge their carrier kills."""
    db.fetch_all = AsyncMock(return_value=[
        ("g1", 1700000000, 1, 5.0, MAP),
        ("g1", 1700000000, 1, 9.0, MAP2),
    ])
    out = await host._load_carrier_kills("d")
    assert out[("g1", 1700000000, MAP, 1)] == [5.0]
    assert out[("g1", 1700000000, MAP2, 1)] == [9.0]


# ---------------------------------------------------------------------------
# _load_carrier_returns — (round_start_unix, map_name, round_number) → [return_time]
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_carrier_returns_keys_by_round(host, db):
    """Key is `(round_start_unix, map_name, round_number)` — guid-agnostic
    (returns are team-attributed, not per-killer)."""
    db.fetch_all = AsyncMock(return_value=[
        (1700000000, 1, 45.0, MAP),
    ])
    out = await host._load_carrier_returns("d")
    assert (1700000000, MAP, 1) in out
    assert out[(1700000000, MAP, 1)] == [45.0]


@pytest.mark.asyncio
async def test_load_carrier_returns_groups_multiple_returns_per_round(host, db):
    """Two returns in one round → both appended."""
    db.fetch_all = AsyncMock(return_value=[
        (1700000000, 1, 30.0, MAP),
        (1700000000, 1, 80.0, MAP),
    ])
    out = await host._load_carrier_returns("d")
    assert out[(1700000000, MAP, 1)] == [30.0, 80.0]


# ---------------------------------------------------------------------------
# _load_pushes — (round_start_unix, map_name, round_number) → [(start, end, quality, toward)]
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_pushes_tuple_shape(host, db):
    """Each entry is `(start_time, end_time, push_quality, toward_objective)`.
    Pin the 4-tuple order — momentum chart unpacks it positionally."""
    db.fetch_all = AsyncMock(return_value=[
        (1700000000, 1, 10.0, 25.0, 0.85, "flag", MAP),
    ])
    out = await host._load_pushes("d")
    entry = out[(1700000000, MAP, 1)][0]
    assert entry == (10.0, 25.0, 0.85, "flag")


@pytest.mark.asyncio
async def test_load_pushes_quality_null_coerced_to_float_zero(host, db):
    """push_quality=NULL → 0.0 (NOT TypeError on `float(None)`).
    Pin so a missing column value doesn't kill the endpoint."""
    db.fetch_all = AsyncMock(return_value=[
        (1700000000, 1, 1.0, 5.0, None, "flag", MAP),
    ])
    out = await host._load_pushes("d")
    entry = out[(1700000000, MAP, 1)][0]
    assert entry[2] == 0.0


@pytest.mark.asyncio
async def test_load_pushes_toward_null_coerced_to_empty_string(host, db):
    """toward_objective=NULL → '' (default). Pin so downstream string
    operations don't NoneError."""
    db.fetch_all = AsyncMock(return_value=[
        (1700000000, 1, 1.0, 5.0, 0.5, None, MAP),
    ])
    out = await host._load_pushes("d")
    entry = out[(1700000000, MAP, 1)][0]
    assert entry[3] == ''


# ---------------------------------------------------------------------------
# _load_crossfires — (round_start_unix, map_name, round_number) → [event_time]
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_crossfires_appends_event_times(host, db):
    db.fetch_all = AsyncMock(return_value=[
        (1700000000, 1, 5.0, MAP),
        (1700000000, 1, 12.0, MAP),
        (1700000000, 2, 8.0, MAP),
    ])
    out = await host._load_crossfires("d")
    assert out[(1700000000, MAP, 1)] == [5.0, 12.0]
    assert out[(1700000000, MAP, 2)] == [8.0]


# ---------------------------------------------------------------------------
# _load_spawn_timings — (round_start_unix, map_name, round_number) → [(guid, t, score, vr)]
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_spawn_timings_tuple_shape(host, db):
    """Each entry is `(killer_guid, kill_time, score, victim_reinf)`.
    Pin the 4-tuple — KIS v3 reinf_mult lookup unpacks index 3."""
    db.fetch_all = AsyncMock(return_value=[
        ("killer-1", 12.5, 0.8, 1700000000, 1, 25.0, MAP),
    ])
    out = await host._load_spawn_timings("d")
    assert out[(1700000000, MAP, 1)] == [("killer-1", 12.5, 0.8, 25.0)]


@pytest.mark.asyncio
async def test_load_spawn_timings_score_null_defaults_to_half(host, db):
    """spawn_timing_score=NULL → 0.5 (neutral). Pin so a missing
    score doesn't get treated as 0 (which would imply "perfectly bad
    timing" instead of "unknown")."""
    db.fetch_all = AsyncMock(return_value=[
        ("k", 5.0, None, 1700000000, 1, 30.0, MAP),
    ])
    out = await host._load_spawn_timings("d")
    entry = out[(1700000000, MAP, 1)][0]
    assert entry[2] == 0.5


@pytest.mark.asyncio
async def test_load_spawn_timings_victim_reinf_null_defaults_to_zero(host, db):
    """victim_reinf=NULL → 0.0 (no spawn-tier bonus when unknown)."""
    db.fetch_all = AsyncMock(return_value=[
        ("k", 5.0, 0.7, 1700000000, 1, None, MAP),
    ])
    out = await host._load_spawn_timings("d")
    entry = out[(1700000000, MAP, 1)][0]
    assert entry[3] == 0.0


@pytest.mark.asyncio
async def test_load_spawn_timings_groups_multiple_kills_per_round(host, db):
    """Two kills, same (unix, map, round) → both appended."""
    db.fetch_all = AsyncMock(return_value=[
        ("k1", 5.0, 0.6, 1700000000, 1, 20.0, MAP),
        ("k2", 8.0, 0.9, 1700000000, 1, 25.0, MAP),
    ])
    out = await host._load_spawn_timings("d")
    assert len(out[(1700000000, MAP, 1)]) == 2


# ---------------------------------------------------------------------------
# _load_victim_classes — (target_guid, round_start_unix, map_name, round_number) → class
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_victim_classes_first_write_wins(host, db):
    """If two rows for same (guid, unix, map, round) → FIRST class wins.

    Pin so a player who switched class mid-round (medic→engineer) gets
    attributed by what they were first observed as. A swap to "last
    write" would silently change archetype attribution downstream."""
    db.fetch_all = AsyncMock(return_value=[
        ("v1", 1700000000, 1, "medic", MAP),
        ("v1", 1700000000, 1, "engineer", MAP),  # ignored
    ])
    out = await host._load_victim_classes("d")
    assert out[("v1", 1700000000, MAP, 1)] == "medic"


@pytest.mark.asyncio
async def test_load_victim_classes_null_class_normalises_empty(host, db):
    """target_class=NULL → '' (NOT None). Pin so downstream string
    comparisons don't fall into the None != '' trap."""
    db.fetch_all = AsyncMock(return_value=[
        ("v1", 1700000000, 1, None, MAP),
    ])
    out = await host._load_victim_classes("d")
    assert out[("v1", 1700000000, MAP, 1)] == ''


@pytest.mark.asyncio
async def test_load_victim_classes_separate_rounds_get_distinct_keys(host, db):
    """Same victim, different rounds → separate keys."""
    db.fetch_all = AsyncMock(return_value=[
        ("v1", 1700000000, 1, "medic", MAP),
        ("v1", 1700000000, 2, "soldier", MAP),
    ])
    out = await host._load_victim_classes("d")
    assert out[("v1", 1700000000, MAP, 1)] == "medic"
    assert out[("v1", 1700000000, MAP, 2)] == "soldier"


# ---------------------------------------------------------------------------
# _load_combat_positions — (killer_guid, unix, map_name, round, event_time) → dict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_combat_positions_dict_shape(host, db):
    """Each value is dict with keys: killer_health, axis_alive,
    allies_alive, attacker_team. Pin schema for KIS v2 health/alive
    multipliers."""
    db.fetch_all = AsyncMock(return_value=[
        ("k1", 1700000000, 1, 12.5, 80, 4, 6, "axis", MAP),
    ])
    out = await host._load_combat_positions(date(2026, 5, 7))
    entry = out[("k1", 1700000000, MAP, 1, 12.5)]
    assert entry == {
        "killer_health": 80,
        "axis_alive": 4,
        "allies_alive": 6,
        "attacker_team": "axis",
    }


@pytest.mark.asyncio
async def test_load_combat_positions_keys_include_event_time(host, db):
    """Key includes event_time (as the suffix) — distinguishes multiple
    kills by the same player in the same round."""
    db.fetch_all = AsyncMock(return_value=[
        ("k1", 1700000000, 1, 5.0, 90, 5, 6, "axis", MAP),
        ("k1", 1700000000, 1, 12.0, 75, 4, 6, "axis", MAP),
    ])
    out = await host._load_combat_positions(date(2026, 5, 7))
    assert ("k1", 1700000000, MAP, 1, 5.0) in out
    assert ("k1", 1700000000, MAP, 1, 12.0) in out
    assert out[("k1", 1700000000, MAP, 1, 5.0)]["killer_health"] == 90
    assert out[("k1", 1700000000, MAP, 1, 12.0)]["killer_health"] == 75


@pytest.mark.asyncio
async def test_load_combat_positions_null_health_defaults_zero(host, db):
    """NULL killer_health → 0. Pin defensive default for KIS health
    multiplier (0% health = max bonus)."""
    db.fetch_all = AsyncMock(return_value=[
        ("k1", 1700000000, 1, 5.0, None, None, None, None, MAP),
    ])
    out = await host._load_combat_positions(date(2026, 5, 7))
    entry = out[("k1", 1700000000, MAP, 1, 5.0)]
    assert entry["killer_health"] == 0
    assert entry["axis_alive"] == 0
    assert entry["allies_alive"] == 0
    assert entry["attacker_team"] == ''


@pytest.mark.asyncio
async def test_load_combat_positions_last_event_wins_on_duplicate_key(host, db):
    """If same key appears twice (shouldn't happen in production but
    defend against), last write wins. Pin observed dict-assignment
    semantics."""
    db.fetch_all = AsyncMock(return_value=[
        ("k1", 1700000000, 1, 5.0, 100, 6, 6, "axis", MAP),
        ("k1", 1700000000, 1, 5.0, 50, 3, 3, "allies", MAP),
    ])
    out = await host._load_combat_positions(date(2026, 5, 7))
    entry = out[("k1", 1700000000, MAP, 1, 5.0)]
    assert entry["killer_health"] == 50
    assert entry["attacker_team"] == "allies"


@pytest.mark.asyncio
async def test_load_combat_positions_separates_maps_on_same_second(host, db):
    """Same (guid, unix, round, event_time) but DIFFERENT map → separate
    keys (codex #10 collision guard)."""
    db.fetch_all = AsyncMock(return_value=[
        ("k1", 1700000000, 1, 5.0, 100, 6, 6, "axis", MAP),
        ("k1", 1700000000, 1, 5.0, 40, 2, 5, "allies", MAP2),
    ])
    out = await host._load_combat_positions(date(2026, 5, 7))
    assert out[("k1", 1700000000, MAP, 1, 5.0)]["killer_health"] == 100
    assert out[("k1", 1700000000, MAP2, 1, 5.0)]["killer_health"] == 40


# ---------------------------------------------------------------------------
# Cross-loader: SQL parameter + column contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_loaders_pass_session_date_as_single_param_tuple(host, db):
    """All loaders pass session_date as a single-element tuple
    `(session_date,)` — pin so a refactor that flattens to a string
    doesn't change asyncpg parameter binding (would silently bind
    NULL or raise)."""
    db.fetch_all = AsyncMock(return_value=[])
    await host._load_carrier_kills("2026-05-07")
    args, _ = db.fetch_all.await_args
    assert args[1] == ("2026-05-07",)


@pytest.mark.asyncio
async def test_load_carrier_kills_uses_dollar_placeholders(host, db):
    """SQL must use `$1` placeholders (asyncpg/PostgreSQL), NOT `?`.
    Pin so a SQLite-syntax regression (which works in dev) doesn't
    crash production."""
    db.fetch_all = AsyncMock(return_value=[])
    await host._load_carrier_kills("d")
    args, _ = db.fetch_all.await_args
    sql = args[0]
    assert "$1" in sql
    assert "?" not in sql


@pytest.mark.asyncio
@pytest.mark.parametrize("loader", [
    "_load_carrier_kills",
    "_load_carrier_returns",
    "_load_pushes",
    "_load_crossfires",
    "_load_spawn_timings",
    "_load_victim_classes",
])
async def test_every_loader_selects_map_name(host, db, loader):
    """Every context loader must SELECT map_name — it's part of the
    canonical round key (codex #10). A loader that drops it from the
    SELECT would IndexError building the key or key on a stale column."""
    db.fetch_all = AsyncMock(return_value=[])
    await getattr(host, loader)("d")
    args, _ = db.fetch_all.await_args
    assert "map_name" in args[0]


@pytest.mark.asyncio
async def test_load_combat_positions_selects_map_name(host, db):
    db.fetch_all = AsyncMock(return_value=[])
    await host._load_combat_positions(date(2026, 5, 7))
    args, _ = db.fetch_all.await_args
    assert "map_name" in args[0]
