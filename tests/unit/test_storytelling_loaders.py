"""Tests for StorytellingService _LoadersMixin — DB → in-memory shapers.

These mixin methods convert SQL rows into dict-of-lists structures keyed
by (round_start_unix, round_number) tuples. Every Smart Stats compute
function (KIS, archetypes, moments, momentum) consumes these loaders.

A regression silently:

- Key tuple shape drift → downstream lookups by `(unix, round)` always
  miss → KIS/archetype scores all default to 0.
- A loader keys by `kill_time` instead of `(unix, round)` → grouping
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
# _load_carrier_kills — (killer_guid, round_start_unix, round_number) → [kill_time]
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
async def test_load_carrier_kills_keys_by_three_tuple(host, db):
    """Key is `(killer_guid, round_start_unix, round_number)`. Pin the
    exact tuple ordering — downstream consumers do `dict[(g, u, r)]`."""
    db.fetch_all = AsyncMock(return_value=[
        ("guidA", 1700000000, 1, 12.5),
    ])
    out = await host._load_carrier_kills("d")
    assert ("guidA", 1700000000, 1) in out


@pytest.mark.asyncio
async def test_load_carrier_kills_appends_multiple_events(host, db):
    """Multiple rows with same (guid, unix, round) → list of kill_times.
    Pin so a regression that switches to assignment loses repeat kills."""
    db.fetch_all = AsyncMock(return_value=[
        ("g1", 1700000000, 1, 5.0),
        ("g1", 1700000000, 1, 12.0),
        ("g1", 1700000000, 1, 30.0),
    ])
    out = await host._load_carrier_kills("d")
    assert out[("g1", 1700000000, 1)] == [5.0, 12.0, 30.0]


@pytest.mark.asyncio
async def test_load_carrier_kills_separates_rounds(host, db):
    """Different round_number → separate keys (R1 and R2 don't merge)."""
    db.fetch_all = AsyncMock(return_value=[
        ("g1", 1700000000, 1, 5.0),
        ("g1", 1700000000, 2, 8.0),
    ])
    out = await host._load_carrier_kills("d")
    assert out[("g1", 1700000000, 1)] == [5.0]
    assert out[("g1", 1700000000, 2)] == [8.0]


# ---------------------------------------------------------------------------
# _load_carrier_returns — (round_start_unix, round_number) → [return_time]
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_carrier_returns_keys_by_round(host, db):
    """Key is `(round_start_unix, round_number)` — guid-agnostic
    (returns are team-attributed, not per-killer)."""
    db.fetch_all = AsyncMock(return_value=[
        (1700000000, 1, 45.0),
    ])
    out = await host._load_carrier_returns("d")
    assert (1700000000, 1) in out
    assert out[(1700000000, 1)] == [45.0]


@pytest.mark.asyncio
async def test_load_carrier_returns_groups_multiple_returns_per_round(host, db):
    """Two returns in one round → both appended."""
    db.fetch_all = AsyncMock(return_value=[
        (1700000000, 1, 30.0),
        (1700000000, 1, 80.0),
    ])
    out = await host._load_carrier_returns("d")
    assert out[(1700000000, 1)] == [30.0, 80.0]


# ---------------------------------------------------------------------------
# _load_pushes — (round_start_unix, round_number) → [(start, end, quality, toward)]
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_pushes_tuple_shape(host, db):
    """Each entry is `(start_time, end_time, push_quality, toward_objective)`.
    Pin the 4-tuple order — momentum chart unpacks it positionally."""
    db.fetch_all = AsyncMock(return_value=[
        (1700000000, 1, 10.0, 25.0, 0.85, "flag"),
    ])
    out = await host._load_pushes("d")
    entry = out[(1700000000, 1)][0]
    assert entry == (10.0, 25.0, 0.85, "flag")


@pytest.mark.asyncio
async def test_load_pushes_quality_null_coerced_to_float_zero(host, db):
    """push_quality=NULL → 0.0 (NOT TypeError on `float(None)`).
    Pin so a missing column value doesn't kill the endpoint."""
    db.fetch_all = AsyncMock(return_value=[
        (1700000000, 1, 1.0, 5.0, None, "flag"),
    ])
    out = await host._load_pushes("d")
    entry = out[(1700000000, 1)][0]
    assert entry[2] == 0.0


@pytest.mark.asyncio
async def test_load_pushes_toward_null_coerced_to_empty_string(host, db):
    """toward_objective=NULL → '' (default). Pin so downstream string
    operations don't NoneError."""
    db.fetch_all = AsyncMock(return_value=[
        (1700000000, 1, 1.0, 5.0, 0.5, None),
    ])
    out = await host._load_pushes("d")
    entry = out[(1700000000, 1)][0]
    assert entry[3] == ''


# ---------------------------------------------------------------------------
# _load_crossfires — (round_start_unix, round_number) → [event_time]
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_crossfires_appends_event_times(host, db):
    db.fetch_all = AsyncMock(return_value=[
        (1700000000, 1, 5.0),
        (1700000000, 1, 12.0),
        (1700000000, 2, 8.0),
    ])
    out = await host._load_crossfires("d")
    assert out[(1700000000, 1)] == [5.0, 12.0]
    assert out[(1700000000, 2)] == [8.0]


# ---------------------------------------------------------------------------
# _load_spawn_timings — (round_start_unix, round_number) → [(guid, t, score, vr)]
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_spawn_timings_tuple_shape(host, db):
    """Each entry is `(killer_guid, kill_time, score, victim_reinf)`.
    Pin the 4-tuple — KIS v3 reinf_mult lookup unpacks index 3."""
    db.fetch_all = AsyncMock(return_value=[
        ("killer-1", 12.5, 0.8, 1700000000, 1, 25.0),
    ])
    out = await host._load_spawn_timings("d")
    assert out[(1700000000, 1)] == [("killer-1", 12.5, 0.8, 25.0)]


@pytest.mark.asyncio
async def test_load_spawn_timings_score_null_defaults_to_half(host, db):
    """spawn_timing_score=NULL → 0.5 (neutral). Pin so a missing
    score doesn't get treated as 0 (which would imply "perfectly bad
    timing" instead of "unknown")."""
    db.fetch_all = AsyncMock(return_value=[
        ("k", 5.0, None, 1700000000, 1, 30.0),
    ])
    out = await host._load_spawn_timings("d")
    entry = out[(1700000000, 1)][0]
    assert entry[2] == 0.5


@pytest.mark.asyncio
async def test_load_spawn_timings_victim_reinf_null_defaults_to_zero(host, db):
    """victim_reinf=NULL → 0.0 (no spawn-tier bonus when unknown)."""
    db.fetch_all = AsyncMock(return_value=[
        ("k", 5.0, 0.7, 1700000000, 1, None),
    ])
    out = await host._load_spawn_timings("d")
    entry = out[(1700000000, 1)][0]
    assert entry[3] == 0.0


@pytest.mark.asyncio
async def test_load_spawn_timings_groups_multiple_kills_per_round(host, db):
    """Two kills, same (unix, round) → both appended."""
    db.fetch_all = AsyncMock(return_value=[
        ("k1", 5.0, 0.6, 1700000000, 1, 20.0),
        ("k2", 8.0, 0.9, 1700000000, 1, 25.0),
    ])
    out = await host._load_spawn_timings("d")
    assert len(out[(1700000000, 1)]) == 2


# ---------------------------------------------------------------------------
# _load_victim_classes — (target_guid, round_start_unix, round_number) → class
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_victim_classes_first_write_wins(host, db):
    """If two rows for same (guid, unix, round) → FIRST class wins.

    Pin so a player who switched class mid-round (medic→engineer) gets
    attributed by what they were first observed as. A swap to "last
    write" would silently change archetype attribution downstream."""
    db.fetch_all = AsyncMock(return_value=[
        ("v1", 1700000000, 1, "medic"),
        ("v1", 1700000000, 1, "engineer"),  # ignored
    ])
    out = await host._load_victim_classes("d")
    assert out[("v1", 1700000000, 1)] == "medic"


@pytest.mark.asyncio
async def test_load_victim_classes_null_class_normalises_empty(host, db):
    """target_class=NULL → '' (NOT None). Pin so downstream string
    comparisons don't fall into the None != '' trap."""
    db.fetch_all = AsyncMock(return_value=[
        ("v1", 1700000000, 1, None),
    ])
    out = await host._load_victim_classes("d")
    assert out[("v1", 1700000000, 1)] == ''


@pytest.mark.asyncio
async def test_load_victim_classes_separate_rounds_get_distinct_keys(host, db):
    """Same victim, different rounds → separate keys."""
    db.fetch_all = AsyncMock(return_value=[
        ("v1", 1700000000, 1, "medic"),
        ("v1", 1700000000, 2, "soldier"),
    ])
    out = await host._load_victim_classes("d")
    assert out[("v1", 1700000000, 1)] == "medic"
    assert out[("v1", 1700000000, 2)] == "soldier"


# ---------------------------------------------------------------------------
# _load_combat_positions — (killer_guid, unix, round, event_time) → dict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_combat_positions_dict_shape(host, db):
    """Each value is dict with keys: killer_health, axis_alive,
    allies_alive, attacker_team. Pin schema for KIS v2 health/alive
    multipliers."""
    db.fetch_all = AsyncMock(return_value=[
        ("k1", 1700000000, 1, 12.5, 80, 4, 6, "axis"),
    ])
    out = await host._load_combat_positions(date(2026, 5, 7))
    entry = out[("k1", 1700000000, 1, 12.5)]
    assert entry == {
        "killer_health": 80,
        "axis_alive": 4,
        "allies_alive": 6,
        "attacker_team": "axis",
    }


@pytest.mark.asyncio
async def test_load_combat_positions_keys_include_event_time(host, db):
    """Key is 4-tuple including event_time — distinguishes multiple
    kills by the same player in the same round."""
    db.fetch_all = AsyncMock(return_value=[
        ("k1", 1700000000, 1, 5.0, 90, 5, 6, "axis"),
        ("k1", 1700000000, 1, 12.0, 75, 4, 6, "axis"),
    ])
    out = await host._load_combat_positions(date(2026, 5, 7))
    assert ("k1", 1700000000, 1, 5.0) in out
    assert ("k1", 1700000000, 1, 12.0) in out
    assert out[("k1", 1700000000, 1, 5.0)]["killer_health"] == 90
    assert out[("k1", 1700000000, 1, 12.0)]["killer_health"] == 75


@pytest.mark.asyncio
async def test_load_combat_positions_null_health_defaults_zero(host, db):
    """NULL killer_health → 0. Pin defensive default for KIS health
    multiplier (0% health = max bonus)."""
    db.fetch_all = AsyncMock(return_value=[
        ("k1", 1700000000, 1, 5.0, None, None, None, None),
    ])
    out = await host._load_combat_positions(date(2026, 5, 7))
    entry = out[("k1", 1700000000, 1, 5.0)]
    assert entry["killer_health"] == 0
    assert entry["axis_alive"] == 0
    assert entry["allies_alive"] == 0
    assert entry["attacker_team"] == ''


@pytest.mark.asyncio
async def test_load_combat_positions_last_event_wins_on_duplicate_key(host, db):
    """If same 4-tuple appears twice (shouldn't happen in production
    but defend against), last write wins. Pin observed dict-assignment
    semantics."""
    db.fetch_all = AsyncMock(return_value=[
        ("k1", 1700000000, 1, 5.0, 100, 6, 6, "axis"),
        ("k1", 1700000000, 1, 5.0, 50, 3, 3, "allies"),
    ])
    out = await host._load_combat_positions(date(2026, 5, 7))
    entry = out[("k1", 1700000000, 1, 5.0)]
    assert entry["killer_health"] == 50
    assert entry["attacker_team"] == "allies"


# ---------------------------------------------------------------------------
# Cross-loader: SQL parameter contract
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
