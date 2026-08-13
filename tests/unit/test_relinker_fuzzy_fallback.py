"""Relinker: a positive SOURCE round_start_unix must not dead-end when the
TARGET rounds row has NULL round_start_unix (T6, live evidence 2026-08-11).

The real case this locks in: evening bot-test round sw_goldrush_te id 11184
(round_time 19:49:49) was imported with round_start_unix NULL because Lua
metadata enrichment was itself deferred — that enrichment is what backfills
the column, and it is populated on only ~60% of rounds (1/11 on
2026-08-11). Proximity rows carried the positive Lua start unix
(1786469867), so the relinker took the exact/relaxed unix-keyed paths, both
of which require rounds.round_start_unix = $N — impossible against NULL —
and never fell back to the time-based resolver, which provably resolves the
round (diff 722 s, well inside the 120-min window). Every such orphan was
permanent: "0 linked, 1 unresolved" every 5 minutes, forever.
"""
# ruff: noqa: SLF001

from __future__ import annotations

import importlib
import time
from contextlib import asynccontextmanager

import pytest

from bot.cogs.proximity_cog import ProximityCog

relinker = importlib.import_module("bot.cogs.proximity_mixins.relinker_mixin")

_RESOLVED_ID = 11184
_MAP = "sw_goldrush_te"
_RN = 1


class _NullUnixTargetDB:
    """One fresh orphan with a positive source unix; the rounds table has
    no row at that unix (its row exists but with NULL round_start_unix),
    so both unix-keyed lookups return nothing."""

    def __init__(self, target_unix: int, round_date: str):
        self.executed: list[tuple[str, tuple]] = []
        self.fetched: list[tuple[str, tuple | None]] = []
        self._target_unix = target_unix
        self._round_date = round_date

    async def fetch_all(self, query, params=None):
        q = " ".join(str(query).split())
        self.fetched.append((q, params))
        if "SELECT DISTINCT map_name" in q:
            return [(_MAP, _RN, self._target_unix, self._round_date)]
        # strict (SELECT id FROM rounds ... round_start_unix = $3) and
        # relaxed (SELECT id, round_number ... round_start_unix = $2):
        # target row has NULL unix -> no hits, ever.
        if "FROM rounds" in q and "round_start_unix" in q:
            return []
        return []

    async def execute(self, query, params=None):
        self.executed.append((" ".join(str(query).split()), params))

    @asynccontextmanager
    async def transaction(self):
        yield self

    async def fetch_val(self, query, params=None):
        self.executed.append((" ".join(str(query).split()), params))
        return None


class _FakeBot:
    def __init__(self, db):
        self.db_adapter = db


def _relinker(db):
    svc = relinker._ProximityRelinkerMixin.__new__(relinker._ProximityRelinkerMixin)
    svc._PROXIMITY_ROUND_ID_TABLES = ProximityCog._PROXIMITY_ROUND_ID_TABLES
    svc.bot = _FakeBot(db)
    return svc


def _recent_identity() -> tuple[int, str]:
    target_unix = int(time.time()) - 300
    return target_unix, time.strftime("%Y-%m-%d", time.localtime(target_unix))


@pytest.mark.asyncio
async def test_null_unix_target_falls_back_to_time_resolver(monkeypatch):
    """Exact+relaxed miss -> the fuzzy resolver must get a chance, and its
    hit must drive the fanout."""
    target_unix, round_date = _recent_identity()
    db = _NullUnixTargetDB(target_unix, round_date)
    svc = _relinker(db)

    calls: list[dict] = []

    async def _fake_resolve(_db, map_name, round_number, **kwargs):
        calls.append({"map": map_name, "rn": round_number, **kwargs})
        return _RESOLVED_ID

    monkeypatch.setattr("bot.core.round_linker.resolve_round_id", _fake_resolve)

    await svc._relink_null_round_ids()

    assert len(calls) == 1, "fuzzy resolver was never consulted"
    assert calls[0]["map"] == _MAP and calls[0]["rn"] == _RN
    assert calls[0].get("target_dt") is not None  # unix still drives the window
    assert calls[0].get("quiet") is True

    generic_updates = [
        p for q, p in db.executed
        if q.startswith("UPDATE") and "SET round_id = $1" in q
        and "lua_round_teams" not in q
    ]
    assert generic_updates, "fanout never ran — orphan stayed permanent"
    assert all(p[0] == _RESOLVED_ID for p in generic_updates)


@pytest.mark.asyncio
async def test_resolver_miss_keeps_never_guess_behaviour(monkeypatch):
    """When even the fuzzy resolver finds nothing, no UPDATE may run."""
    target_unix, round_date = _recent_identity()
    db = _NullUnixTargetDB(target_unix, round_date)
    svc = _relinker(db)

    async def _fake_resolve(*_a, **_k):
        return None

    monkeypatch.setattr("bot.core.round_linker.resolve_round_id", _fake_resolve)

    await svc._relink_null_round_ids()

    assert not [q for q, _ in db.executed if q.startswith("UPDATE")]
