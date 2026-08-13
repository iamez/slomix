"""Relinker: round_number disagreement must not defeat an exact
map+round_start_unix match (T5, live evidence 2026-08-11).

The real case this locks in: one physical te_escape2 round
(round_start_unix=1786418696, round_end_unix=1786418856, both identical in
both stores). The stats path (rounds id 11180) recorded round_number=2 —
engine/endstats/gametime all called it R2, the engine's round counter
having survived a fresh `map` load issued right after the previous
delivery's R2. proximity_tracker reset to round 1 on the new map, so every
proximity row carries round_number=1. The relinker's strict exact lookup
(map+round_number+round_start_unix) therefore returned nothing on every
5-minute cycle, forever: ~159 rows permanently unlinked on a COVERED table
(round_link_reason='no_rows_for_map_round'). Historic scope on prod: 2 of
643 linkable rounds (0.31%; first occurrence mp_sillyctf 2026-06-08).

The fix: when the strict lookup finds nothing but map_name (normalized the
same way) + round_start_unix match EXACTLY ONE rounds row, trust the
timestamps — one game server cannot start two rounds of the same map in
the same second. Zero or multiple candidates keep the old never-guess
behaviour.
"""
# ruff: noqa: SLF001

from __future__ import annotations

import importlib
import logging
import time
from contextlib import asynccontextmanager

import pytest

from bot.cogs.proximity_cog import ProximityCog

relinker = importlib.import_module("bot.cogs.proximity_mixins.relinker_mixin")

# The real round ids/numbers from the 2026-08-11 live test; the timestamp
# must be recent so the orphan clears the 6h permanent-orphan cutoff.
_ROUNDS_ID = 11180
_STATS_RN = 2
_PROXIMITY_RN = 1


class _MismatchDB:
    """One orphan round whose proximity identity says round 1 while the
    only rounds row at that exact map+round_start_unix says round 2."""

    def __init__(self, target_unix: int, round_date: str,
                 relaxed_rows: list | None = None,
                 strict_rows: list | None = None):
        self.executed: list[tuple[str, tuple]] = []
        self.fetched: list[tuple[str, tuple | None]] = []
        self._target_unix = target_unix
        self._round_date = round_date
        self._strict_rows = strict_rows if strict_rows is not None else []
        self._relaxed_rows = (
            relaxed_rows if relaxed_rows is not None
            else [(_ROUNDS_ID, _STATS_RN)]
        )

    async def fetch_all(self, query, params=None):
        q = " ".join(str(query).split())
        self.fetched.append((q, params))
        if "SELECT DISTINCT map_name" in q:
            return [("te_escape2", _PROXIMITY_RN, self._target_unix, self._round_date)]
        if "SELECT id, round_number FROM rounds" in q:
            return self._relaxed_rows
        if "SELECT id FROM rounds" in q:
            return self._strict_rows
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
async def test_exact_unix_match_survives_round_number_disagreement(caplog):
    """The te_escape2/11180 case: strict lookup empty, exactly one rounds
    row at the same map+round_start_unix -> the fanout must run against it,
    keyed on the SOURCE round_number so the mismatched rows are matched."""
    target_unix, round_date = _recent_identity()
    db = _MismatchDB(target_unix, round_date)
    svc = _relinker(db)

    with caplog.at_level(logging.WARNING, logger="bot.cogs.proximity"):
        await svc._relink_null_round_ids()

    generic_updates = [
        (q, p) for q, p in db.executed
        if q.startswith("UPDATE") and "SET round_id = $1" in q
        and "lua_round_teams" not in q
    ]
    assert generic_updates, "fanout never ran — mismatch still disqualifies"
    for _q, params in generic_updates:
        assert params[0] == _ROUNDS_ID  # linked to the stats-path round
        assert params[1] == "te_escape2"
        assert params[2] == _PROXIMITY_RN  # UPDATE keys on the SOURCE rn

    warnings = [r for r in caplog.records if "round_number mismatch tolerated" in r.message]
    assert len(warnings) == 1
    assert "te_escape2" in warnings[0].getMessage()


@pytest.mark.asyncio
async def test_relaxed_lookup_queries_exact_unix_without_round_number():
    target_unix, round_date = _recent_identity()
    db = _MismatchDB(target_unix, round_date)
    svc = _relinker(db)

    await svc._relink_null_round_ids()

    relaxed = [
        (q, p) for q, p in db.fetched
        if "SELECT id, round_number FROM rounds" in q
    ]
    assert len(relaxed) == 1
    query, params = relaxed[0]
    assert "LOWER(BTRIM(map_name)) = LOWER(BTRIM($1))" in query
    assert "round_start_unix = $2" in query
    assert "round_number = " not in query.split("SELECT id, round_number", 1)[1].split("FROM")[1]
    assert params == ("te_escape2", target_unix)
    assert "LIMIT 2" in query  # must be able to SEE ambiguity


@pytest.mark.asyncio
async def test_strict_match_still_wins_without_touching_the_relaxed_path():
    """When the strict (map, rn, unix) lookup succeeds, behaviour is
    byte-for-byte the old one: the relaxed query must not even run."""
    target_unix, round_date = _recent_identity()
    db = _MismatchDB(target_unix, round_date, strict_rows=[(999,)])
    svc = _relinker(db)

    await svc._relink_null_round_ids()

    assert not any(
        "SELECT id, round_number FROM rounds" in q for q, _ in db.fetched
    )
    generic_updates = [
        p for q, p in db.executed
        if q.startswith("UPDATE") and "SET round_id = $1" in q
        and "lua_round_teams" not in q
    ]
    assert generic_updates
    assert all(p[0] == 999 for p in generic_updates)


@pytest.mark.asyncio
async def test_multiple_relaxed_candidates_defer_instead_of_guessing(caplog):
    """Two rounds rows at the same map+unix is a data anomaly, not a
    licence to guess — old behaviour (no link) must be kept."""
    target_unix, round_date = _recent_identity()
    db = _MismatchDB(
        target_unix, round_date,
        relaxed_rows=[(_ROUNDS_ID, 1), (_ROUNDS_ID + 1, 2)],
    )
    svc = _relinker(db)

    with caplog.at_level(logging.WARNING, logger="bot.cogs.proximity"):
        await svc._relink_null_round_ids()

    assert not [q for q, _ in db.executed if q.startswith("UPDATE")]
    assert not [r for r in caplog.records if "mismatch tolerated" in r.message]


@pytest.mark.asyncio
async def test_no_relaxed_candidates_keep_the_old_unresolved_outcome():
    target_unix, round_date = _recent_identity()
    db = _MismatchDB(target_unix, round_date, relaxed_rows=[])
    svc = _relinker(db)

    await svc._relink_null_round_ids()

    assert not [q for q, _ in db.executed if q.startswith("UPDATE")]
