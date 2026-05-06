"""Unit tests for the round_canonical_id module.

This module is the foundation of Phase 3+4 of the canonical id migration —
new ingest paths and the round-linker primary lookup both depend on it
producing the same hash for the same inputs across processes (Python +
PostgreSQL DIGEST). Lock the contract here so any future drift fails loud.
"""
from __future__ import annotations

import hashlib

import pytest

from bot.core.round_canonical import (
    CANONICAL_ID_LENGTH,
    compute_canonical_id,
    derive_round_start_from_stats_filename,
    update_canonical_id_if_possible,
)


def test_deterministic_for_identical_inputs():
    a = compute_canonical_id(1_700_000_000, "te_escape2", 1)
    b = compute_canonical_id(1_700_000_000, "te_escape2", 1)
    assert a == b
    assert a is not None
    assert len(a) == CANONICAL_ID_LENGTH


def test_distinct_for_different_round_start():
    a = compute_canonical_id(1_700_000_000, "te_escape2", 1)
    b = compute_canonical_id(1_700_000_001, "te_escape2", 1)
    assert a != b


def test_distinct_for_different_map():
    a = compute_canonical_id(1_700_000_000, "te_escape2", 1)
    b = compute_canonical_id(1_700_000_000, "frostbite", 1)
    assert a != b


def test_distinct_for_different_round_number():
    a = compute_canonical_id(1_700_000_000, "te_escape2", 1)
    b = compute_canonical_id(1_700_000_000, "te_escape2", 2)
    assert a != b


def test_map_normalisation_case_and_whitespace():
    """Match-id stability does not depend on caller capitalising the map name."""
    base = compute_canonical_id(1_700_000_000, "te_escape2", 1)
    assert compute_canonical_id(1_700_000_000, "TE_ESCAPE2", 1) == base
    assert compute_canonical_id(1_700_000_000, "  te_escape2  ", 1) == base
    assert compute_canonical_id(1_700_000_000, "Te_Escape2", 1) == base


def test_map_normalisation_strips_et_color_codes():
    """ET server can emit color-prefixed map names in edge cases."""
    base = compute_canonical_id(1_700_000_000, "te_escape2", 1)
    assert compute_canonical_id(1_700_000_000, "^1te_^7escape2", 1) == base


@pytest.mark.parametrize("bad_unix", [None, 0, -1, -9_999])
def test_rejects_bad_round_start(bad_unix):
    assert compute_canonical_id(bad_unix, "te_escape2", 1) is None


@pytest.mark.parametrize("bad_map", [None, "", "   ", "^7"])
def test_rejects_bad_map_name(bad_map):
    assert compute_canonical_id(1_700_000_000, bad_map, 1) is None


@pytest.mark.parametrize("bad_round", [None, -1, 3, 5, 99])
def test_rejects_round_number_outside_0_1_2(bad_round):
    """Only summary (0), R1 (1), R2 (2) are valid."""
    assert compute_canonical_id(1_700_000_000, "te_escape2", bad_round) is None


@pytest.mark.parametrize("good_round", [0, 1, 2])
def test_accepts_summary_r1_r2(good_round):
    assert compute_canonical_id(1_700_000_000, "te_escape2", good_round) is not None


def test_matches_postgres_digest_payload_format():
    """Cross-language determinism guard.

    PostgreSQL backfill SQL uses:
        ENCODE(DIGEST(round_start_unix || ':' || lower(trim(map_name)) || ':' || round_number, 'sha256'), 'hex')
    Truncated to 16 chars. This test reproduces the same payload manually
    and asserts Python hashlib agrees byte-for-byte.
    """
    payload = "1700000000:te_escape2:1"
    expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:CANONICAL_ID_LENGTH]
    actual = compute_canonical_id(1_700_000_000, "te_escape2", 1)
    assert actual == expected


# ---------------------------------------------------------------------------
# derive_round_start_from_stats_filename
# ---------------------------------------------------------------------------


def test_derive_round_start_subtracts_duration():
    flush_ts = 1_700_000_300  # filename timestamp = round end + 0-3s
    duration = 270            # round was 4m30s long
    derived = derive_round_start_from_stats_filename(flush_ts, duration)
    assert derived == 1_700_000_030


@pytest.mark.parametrize("flush_ts", [None, 0, -1])
def test_derive_round_start_rejects_bad_flush_ts(flush_ts):
    assert derive_round_start_from_stats_filename(flush_ts, 240) is None


@pytest.mark.parametrize("duration", [None, -1])
def test_derive_round_start_rejects_bad_duration(duration):
    assert derive_round_start_from_stats_filename(1_700_000_300, duration) is None


def test_derive_round_start_accepts_zero_duration():
    """A 0-second round is still a valid (if degenerate) input — caller decides."""
    assert derive_round_start_from_stats_filename(1_700_000_300, 0) == 1_700_000_300


# ---------------------------------------------------------------------------
# update_canonical_id_if_possible
# ---------------------------------------------------------------------------


class _FakeDb:
    def __init__(self, row):
        self._row = row
        self.executes: list[tuple] = []

    async def fetch_one(self, query, params=None):
        return self._row

    async def execute(self, query, params=None):
        self.executes.append((str(query), params))


@pytest.mark.asyncio
async def test_update_writes_when_canonical_id_missing():
    db = _FakeDb(row=(1_700_000_000, "te_escape2", 1, None))
    cid = await update_canonical_id_if_possible(db, round_id=42)
    expected = compute_canonical_id(1_700_000_000, "te_escape2", 1)
    assert cid == expected
    # Conditional UPDATE was issued
    assert len(db.executes) == 1
    query, params = db.executes[0]
    assert "UPDATE rounds SET round_canonical_id" in query
    assert "round_canonical_id IS NULL" in query  # race guard
    assert params == (expected, 42)


@pytest.mark.asyncio
async def test_update_is_noop_when_already_set():
    """Idempotent — never overwrite an existing canonical id."""
    db = _FakeDb(row=(1_700_000_000, "te_escape2", 1, "existing_cid_xx"))
    cid = await update_canonical_id_if_possible(db, round_id=42)
    assert cid == "existing_cid_xx"
    assert db.executes == []  # no UPDATE issued


@pytest.mark.asyncio
async def test_update_skips_when_round_lacks_start_unix():
    db = _FakeDb(row=(None, "te_escape2", 1, None))
    cid = await update_canonical_id_if_possible(db, round_id=42)
    assert cid is None
    assert db.executes == []


@pytest.mark.asyncio
async def test_update_skips_when_round_id_invalid():
    db = _FakeDb(row=None)
    assert await update_canonical_id_if_possible(db, round_id=None) is None
    assert await update_canonical_id_if_possible(db, round_id=0) is None
    assert await update_canonical_id_if_possible(db, round_id=-1) is None


@pytest.mark.asyncio
async def test_update_returns_none_when_row_missing():
    """If the rounds row was deleted between INSERT and the canonical
    update call (rare but possible during cleanup), we degrade gracefully."""
    db = _FakeDb(row=None)
    assert await update_canonical_id_if_possible(db, round_id=999) is None
    assert db.executes == []


class _CollidingDb:
    """DB whose UPDATE raises a UniqueViolation-like error.

    Mirrors what asyncpg does when migration 050's partial UNIQUE index
    rejects a duplicate canonical_id (real-world: 1 of 409 historic rounds
    collided during backfill).
    """

    def __init__(self, row, exc):
        self._row = row
        self._exc = exc
        self.executes: list[tuple] = []

    async def fetch_one(self, query, params=None):
        return self._row

    async def execute(self, query, params=None):
        self.executes.append((str(query), params))
        raise self._exc


class _FakeUniqueViolation(Exception):
    """Stands in for asyncpg.exceptions.UniqueViolationError.

    asyncpg's UniqueViolationError exposes `constraint_name`; we mirror
    that attribute so the production code can prefer the structured
    field over message-scanning.
    """

    def __init__(self, message, constraint_name=None):
        super().__init__(message)
        self.constraint_name = constraint_name


@pytest.mark.asyncio
async def test_update_swallows_canonical_collision_by_constraint_name():
    """asyncpg-style: structured constraint_name attribute is the
    primary signal — message contents irrelevant."""
    exc = _FakeUniqueViolation(
        "duplicate key value violates unique constraint",
        constraint_name="uniq_rounds_canonical_id",
    )
    db = _CollidingDb(row=(1_700_000_000, "te_escape2", 1, None), exc=exc)
    cid = await update_canonical_id_if_possible(db, round_id=42)
    assert cid is None
    assert len(db.executes) == 1


@pytest.mark.asyncio
async def test_update_swallows_canonical_collision_by_message_fallback():
    """When the driver doesn't expose `constraint_name`, fall back to
    scanning the error message for the canonical index name."""
    # Plain Exception subclass with no constraint_name attribute
    class _NoAttrError(Exception):
        pass

    exc = _NoAttrError(
        'duplicate key value violates unique constraint "uniq_rounds_canonical_id"'
    )
    db = _CollidingDb(row=(1_700_000_000, "te_escape2", 1, None), exc=exc)
    cid = await update_canonical_id_if_possible(db, round_id=42)
    assert cid is None


@pytest.mark.asyncio
async def test_update_re_raises_other_unique_violations():
    """A UniqueViolation on a DIFFERENT constraint must NOT be swallowed —
    that's a real bug that needs admin attention.
    """
    exc = _FakeUniqueViolation(
        "duplicate key value violates unique constraint",
        constraint_name="rounds_pkey",  # different constraint!
    )
    db = _CollidingDb(row=(1_700_000_000, "te_escape2", 1, None), exc=exc)
    with pytest.raises(_FakeUniqueViolation):
        await update_canonical_id_if_possible(db, round_id=42)


@pytest.mark.asyncio
async def test_update_re_raises_unrelated_errors():
    """Non-collision DB errors must propagate so callers can react."""
    exc = RuntimeError("connection lost mid-query")
    db = _CollidingDb(row=(1_700_000_000, "te_escape2", 1, None), exc=exc)
    with pytest.raises(RuntimeError, match="connection lost"):
        await update_canonical_id_if_possible(db, round_id=42)
