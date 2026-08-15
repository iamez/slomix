"""The aim summary is cached on a fingerprint of its inputs, not on a clock.

Computing it costs 2,770 ms warm and 16,887 ms cold for the heaviest player
(103,258 shots), against ~500 ms for the twelve other profile sections together.
It is derived from data that only changes when rounds import, so it is computed
once and stored — and every one of these tests exists because a cache that
returns a stale answer is worse than a slow one.
"""
from __future__ import annotations

import json

import pytest

from website.backend.routers import players_profile_router as P
from website.backend.routers.players_profile_router import (
    _AIM_FORMULA_VERSION,
    _fetch_aim_summary,
)


class FakeDB:
    """Minimal stand-in: canned rows per query fragment, plus a call log."""

    def __init__(self, *, cache_row=None, fingerprint=(10, 500, 1234.0), fail_read=False,
                 fail_write=False):
        self.cache_row = cache_row
        self.fingerprint = fingerprint
        self.fail_read = fail_read
        self.fail_write = fail_write
        self.writes: list[tuple] = []

    async def fetch_one(self, query, params=()):
        if "FROM proximity_shot_fired" in query:
            return self.fingerprint
        if "FROM player_aim_summary" in query:
            if self.fail_read:
                raise RuntimeError("relation \"player_aim_summary\" does not exist")
            return self.cache_row
        raise AssertionError(f"unexpected query: {query[:60]}")

    async def execute(self, query, params=()):
        if self.fail_write:
            raise RuntimeError("permission denied for table player_aim_summary")
        self.writes.append(params)


SUMMARY = {"available": True, "lifetime": {"n": 10}, "flick": {"available": False}}


@pytest.fixture
def no_compute(monkeypatch):
    """Fail loudly if the expensive path runs when it should not."""
    async def _boom(*_a, **_k):
        raise AssertionError("the expensive computation ran")
    monkeypatch.setattr(P, "_compute_aim_summary", _boom)


@pytest.fixture
def counted_compute(monkeypatch):
    calls = {"n": 0}

    async def _compute(*_a, **_k):
        calls["n"] += 1
        return SUMMARY
    monkeypatch.setattr(P, "_compute_aim_summary", _compute)
    return calls


async def test_a_current_row_is_served_without_computing(no_compute):
    db = FakeDB(cache_row=(json.dumps(SUMMARY), 10, 500, 1234.0))

    assert await _fetch_aim_summary(db, "D8423F90") == SUMMARY


async def test_payload_already_decoded_is_accepted(no_compute):
    """asyncpg may hand JSONB back as a dict or as text depending on codecs."""
    db = FakeDB(cache_row=(SUMMARY, 10, 500, 1234.0))

    assert await _fetch_aim_summary(db, "D8423F90") == SUMMARY


@pytest.mark.parametrize("stored,label", [
    ((json.dumps(SUMMARY), 11, 500, 1234.0), "a shot was added or removed"),
    ((json.dumps(SUMMARY), 10, 501, 1234.0), "a newer shot exists"),
    ((json.dumps(SUMMARY), 10, 500, 9999.0), "shots were re-linked to other rounds"),
])
async def test_every_fingerprint_column_invalidates(counted_compute, stored, label):
    """round_id_sum is not decoration: the flick window is partitioned by round,
    so re-linking changes the answer while count and last event stay put."""
    db = FakeDB(cache_row=stored)

    result = await _fetch_aim_summary(db, "D8423F90")

    assert counted_compute["n"] == 1, f"should have recomputed: {label}"
    assert result == SUMMARY
    assert db.writes, "the fresh answer should replace the stale row"


async def test_a_missing_row_computes_and_stores(counted_compute):
    db = FakeDB(cache_row=None)

    await _fetch_aim_summary(db, "D8423F90")

    assert counted_compute["n"] == 1
    written = db.writes[0]
    assert written[0] == "D8423F90"
    assert written[1] == _AIM_FORMULA_VERSION
    assert written[2:5] == (10, 500, 1234.0)
    assert json.loads(written[5]) == SUMMARY


async def test_an_unreadable_cache_never_breaks_the_profile(counted_compute):
    """The table arrives with migration 077; the endpoint predates it, and a
    profile that 500s over a derived table would be a worse product than a slow
    one."""
    db = FakeDB(fail_read=True)

    assert await _fetch_aim_summary(db, "D8423F90") == SUMMARY
    assert counted_compute["n"] == 1


async def test_an_unwritable_cache_still_serves_the_answer(counted_compute):
    db = FakeDB(cache_row=None, fail_write=True)

    assert await _fetch_aim_summary(db, "D8423F90") == SUMMARY


async def test_a_corrupt_payload_is_recomputed_not_served(counted_compute):
    db = FakeDB(cache_row=("{not json", 10, 500, 1234.0))

    assert await _fetch_aim_summary(db, "D8423F90") == SUMMARY
    assert counted_compute["n"] == 1


async def test_a_payload_that_is_not_an_object_is_rejected(counted_compute):
    db = FakeDB(cache_row=(json.dumps([1, 2, 3]), 10, 500, 1234.0))

    assert await _fetch_aim_summary(db, "D8423F90") == SUMMARY
    assert counted_compute["n"] == 1


async def test_the_formula_version_is_part_of_the_lookup(no_compute):
    """A cached row from older maths must never be served. The version is in the
    WHERE clause, so an old row simply does not come back."""
    captured = {}

    class VersionDB(FakeDB):
        async def fetch_one(self, query, params=()):
            if "FROM player_aim_summary" in query:
                captured["query"] = query
                captured["params"] = params
            return await super().fetch_one(query, params)

    db = VersionDB(cache_row=(json.dumps(SUMMARY), 10, 500, 1234.0))
    await _fetch_aim_summary(db, "D8423F90")

    assert "formula_version = $2" in captured["query"]
    assert captured["params"][1] == _AIM_FORMULA_VERSION


async def test_a_player_with_no_shots_has_a_zero_fingerprint(counted_compute):
    db = FakeDB(cache_row=None, fingerprint=(0, None, None))

    await _fetch_aim_summary(db, "NOSHOTS0")

    assert db.writes[0][2:5] == (0, None, None)
