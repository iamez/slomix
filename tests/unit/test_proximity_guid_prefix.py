"""Proximity endpoints accept the 8-character guid prefix (2026-09-06).

The session and profile pages key players on the 8-char prefix that
player_comprehensive_stats stores; the proximity tables hold the tracker's
full 32-char guid. Every proximity endpoint compared the two with `=`, so a
prefix rendered a valid "not tracked" page for every player and the parity
sweep could not see it. The resolver in proximity_helpers turns a prefix into
the full guid ONCE per request; the queries then bind the full form.

Measured on the live corpus before writing this: the only prefixes shared
by more than one guid are the bots' (OMNIBOT0 x9, OMNIBOT1 x4) -- every
human prefix is unique, so a bot prefix is a 400, not a guess.

Controls that must fail are marked; the last test removes the resolver's
effect and asserts the old behaviour is gone.
"""
# ruff: noqa: SLF001
from __future__ import annotations

import pytest
from fastapi import HTTPException

from website.backend.routers import proximity_helpers as helpers
from website.backend.routers import proximity_player as player_router
from website.backend.routers.proximity_helpers import (
    normalise_player_guid,
    resolve_player_guid,
)

FULL = "D8423F90F045D9D3E2C0550811C5A899"
SHORT = FULL[:8]


class _ResolverDB:
    """Records every fetch_val; answers the canonical lookup, the track
    fallback, or nothing, depending on what the test wants to see."""

    def __init__(self, *, canonical: str | None = None, track: str | None = None):
        self.canonical = canonical
        self.track = track
        self.calls: list[tuple[str, tuple]] = []

    async def fetch_val(self, query: str, params=None):
        self.calls.append((" ".join(query.split()), tuple(params or ())))
        if "storytelling_kill_impact" in query:
            return self.canonical
        if "player_track" in query:
            return self.track
        raise AssertionError(query)


@pytest.fixture(autouse=True)
def _clear_cache():
    helpers._GUID_PREFIX_CACHE.clear()
    yield
    helpers._GUID_PREFIX_CACHE.clear()


# ---- normalisation ---------------------------------------------------------

def test_full_guid_passes_through_uppercased():
    assert normalise_player_guid(f" {FULL.lower()} ") == FULL


def test_empty_is_none():
    assert normalise_player_guid(None) is None
    assert normalise_player_guid("   ") is None


@pytest.mark.parametrize("bad", ["D8423F9", "D8423F90-1", "d842 3f90", "X" * 33])
def test_malformed_guid_is_a_400_not_a_guess(bad):
    with pytest.raises(HTTPException) as exc:
        normalise_player_guid(bad)
    assert exc.value.status_code == 400


@pytest.mark.parametrize("bot", ["OMNIBOT0", "OMNIBOT1", "SLOT0001"])
def test_bot_prefix_is_a_400_because_it_names_several_bots(bot):
    with pytest.raises(HTTPException) as exc:
        normalise_player_guid(bot)
    assert exc.value.status_code == 400
    assert "bot" in exc.value.detail


def test_full_bot_guid_is_still_accepted():
    assert normalise_player_guid("OMNIBOT0" + "1" * 24) == "OMNIBOT0" + "1" * 24


# ---- resolution ------------------------------------------------------------

@pytest.mark.asyncio
async def test_prefix_resolves_through_the_indexed_canonical_column_first():
    db = _ResolverDB(canonical=FULL)
    assert await resolve_player_guid(db, SHORT) == FULL
    assert len(db.calls) == 1
    sql, params = db.calls[0]
    assert "killer_guid_canonical = $1" in sql
    assert params == (SHORT,)


@pytest.mark.asyncio
async def test_prefix_falls_back_to_player_track_when_the_player_never_killed():
    db = _ResolverDB(canonical=None, track=FULL)
    assert await resolve_player_guid(db, SHORT) == FULL
    assert [c[0].split(" FROM ")[1].split(" ")[0] for c in db.calls] == [
        "storytelling_kill_impact", "player_track",
    ]
    assert "LEFT(player_guid, 8) = $1" in db.calls[1][0]


@pytest.mark.asyncio
async def test_unknown_prefix_returns_the_prefix_so_the_result_is_empty_not_500():
    db = _ResolverDB()
    assert await resolve_player_guid(db, SHORT) == SHORT
    assert SHORT not in helpers._GUID_PREFIX_CACHE  # misses are not cached


@pytest.mark.asyncio
async def test_full_guid_never_touches_the_database():
    db = _ResolverDB()
    assert await resolve_player_guid(db, FULL) == FULL
    assert db.calls == []


@pytest.mark.asyncio
async def test_a_hit_is_cached_for_the_next_request():
    db = _ResolverDB(canonical=FULL)
    await resolve_player_guid(db, SHORT)
    await resolve_player_guid(db, SHORT)
    assert len(db.calls) == 1


@pytest.mark.asyncio
async def test_an_adapter_without_fetch_val_fails_open():
    class Bare:
        pass
    assert await resolve_player_guid(Bare(), SHORT) == SHORT


@pytest.mark.asyncio
async def test_a_raising_lookup_fails_open():
    class Boom:
        async def fetch_val(self, query, params=None):
            raise RuntimeError("db down")
    assert await resolve_player_guid(Boom(), SHORT) == SHORT


# ---- the endpoints bind the FULL guid --------------------------------------

class _ProfileDB(_ResolverDB):
    """The profile endpoint's seven queries, each recording the guid it was
    bound with. Values are the shape test_proximity_profile_and_aggregates
    uses; only the bound guid matters here."""

    def __init__(self):
        super().__init__(canonical=FULL)
        self.bound: list[str] = []

    async def fetch_one(self, query: str, params=()):
        q = " ".join(query.split()).lower()
        if params:
            self.bound.append(str(params[0]))
        if "count(*) as total_engagements" in q:
            return (12, 4, 8, 1400, 90, 220, 3)
        if "count(*) as total_kills" in q:
            return (5,)
        if "from proximity_spawn_timing" in q:
            return (0.61, 5, 730)
        if "from proximity_reaction_metric" in q:
            return (410, 620, 800, 9)
        if "from player_track" in q and "avg_speed" in q:
            return (123.4, 42.5, 880, 14)
        if "from proximity_lua_trade_kill" in q:
            return (2,)
        if "select player_name from player_track" in q:
            return ("Alpha",)
        raise AssertionError(q)


@pytest.mark.asyncio
async def test_profile_with_a_prefix_binds_the_full_guid_in_every_query():
    db = _ProfileDB()
    payload = await player_router.get_proximity_player_profile(SHORT, range_days=30, db=db)
    assert payload["guid"] == FULL
    assert payload["requested_guid"] == SHORT
    assert payload["player_name"] == "Alpha"
    assert db.bound, "no query bound a guid"
    assert set(db.bound) == {FULL}, db.bound


@pytest.mark.asyncio
async def test_profile_with_the_full_guid_is_byte_identical_except_requested_guid():
    a = await player_router.get_proximity_player_profile(SHORT, range_days=30, db=_ProfileDB())
    b = await player_router.get_proximity_player_profile(FULL, range_days=30, db=_ProfileDB())
    a.pop("requested_guid")
    b.pop("requested_guid")
    assert a == b


@pytest.mark.asyncio
async def test_profile_with_a_bot_prefix_is_a_400():
    with pytest.raises(HTTPException) as exc:
        await player_router.get_proximity_player_profile("OMNIBOT0", range_days=30, db=_ProfileDB())
    assert exc.value.status_code == 400


# ---- the control that must fail --------------------------------------------

@pytest.mark.asyncio
async def test_control_without_the_resolver_the_prefix_reaches_the_queries(monkeypatch):
    """Mutation, kept as a test: with the resolver bypassed the old behaviour
    (prefix bound verbatim, empty results, 'not tracked') comes back. If this
    test ever passes WITHOUT the monkeypatch, the fix is gone."""
    async def passthrough(db, raw):
        return raw
    monkeypatch.setattr(player_router, "resolve_player_guid", passthrough)
    db = _ProfileDB()
    payload = await player_router.get_proximity_player_profile(SHORT, range_days=30, db=db)
    assert payload["guid"] == SHORT
    assert set(db.bound) == {SHORT}


# ---- every guid-taking proximity handler goes through the resolver --------

import ast  # noqa: E402
import pathlib  # noqa: E402

_ROUTERS = pathlib.Path(__file__).resolve().parents[2] / "website" / "backend" / "routers"

# Handlers that take `player_guid` and deliberately do NOT call the shared
# resolver, each with the reason a reader can check.
_RESOLVER_EXEMPT = {
    "get_proximity_duos": "matches by _guid_key LIKE on jsonb text — prefix-native already",
    "get_proximity_pushes": "the guid filter is dropped on purpose (column is a team name)",
    "get_proximity_kill_outcomes_player_stats": "accepts the param but never binds it",
    "get_player_journey": "prefix-native: startswith over the fetched tracks",
    "get_player_card": "prefix-native: LIKE guid || '%'",
    "get_proximity_player_heatmap": "scope-aware canonical resolver (_resolve_player_guid_canonical)",
    "get_proximity_player_aim": "scope-aware canonical resolver (_resolve_player_guid_canonical)",
}


def _handlers_with_player_guid():
    out = []
    for path in sorted(_ROUTERS.glob("proximity_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef):
                continue
            names = {a.arg for a in node.args.args + node.args.kwonlyargs}
            if "player_guid" in names or "guid" in names and node.name.startswith("get_proximity_player_"):
                out.append((path.name, node))
    return out


def _awaits_resolver(fn: ast.AsyncFunctionDef) -> bool:
    for node in ast.walk(fn):
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
            f = node.value.func
            if getattr(f, "id", None) == "resolve_player_guid" or getattr(f, "attr", None) == "resolve_player_guid":
                return True
    return False


def test_the_inventory_of_guid_handlers_is_the_one_this_test_knows():
    """The exemption list is only honest while it names real handlers."""
    known = {fn.name for _, fn in _handlers_with_player_guid()}
    missing = set(_RESOLVER_EXEMPT) - known
    assert not missing, f"exempt handlers that no longer exist: {missing}"
    assert len(known) >= 17, sorted(known)


@pytest.mark.parametrize(
    "file_name, fn",
    [pytest.param(f, fn, id=f"{f}::{fn.name}") for f, fn in _handlers_with_player_guid()],
)
def test_every_guid_handler_resolves_the_prefix_or_says_why_not(file_name, fn):
    if fn.name in _RESOLVER_EXEMPT:
        pytest.skip(_RESOLVER_EXEMPT[fn.name])
    assert _awaits_resolver(fn), (
        f"{file_name}::{fn.name} takes player_guid but never awaits resolve_player_guid — "
        "an 8-character key from the session page would bind verbatim and match nothing"
    )
