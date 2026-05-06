"""Tests for round_linker Phase 4 canonical_id primary lookup.

The canonical-id branch is the new O(1) round_linker path added per
docs/ADR_round_canonical_id.md. It runs BEFORE the legacy fuzzy match
and short-circuits when an exact canonical hit is found.

These tests pin the contract:
- target_dt + matching canonical row → returns immediately
- target_dt + no canonical match → falls through to fuzzy logic
- canonical lookup failure → swallowed (non-fatal), falls through
- tz-aware target_dt is handled (PR #130 normalization regression)
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from bot.core.round_canonical import compute_canonical_id
from bot.core.round_linker import resolve_round_id_with_reason


class _ScriptedDb:
    """Fake DB that scripts answers per (query_substring, return_value).

    Real round_linker uses fetch_one + fetch_all with multiple SQL shapes.
    We pattern-match on substrings to keep the fixture readable.
    """

    def __init__(self):
        self.fetch_one_responses: list[tuple[str, object]] = []
        self.fetch_all_responses: list[tuple[str, object]] = []
        self.queries: list[tuple[str, str, tuple]] = []  # (kind, query, params)

    def add_fetch_one(self, substring: str, response):
        self.fetch_one_responses.append((substring, response))

    def add_fetch_all(self, substring: str, response):
        self.fetch_all_responses.append((substring, response))

    async def fetch_one(self, query, params=None):
        self.queries.append(("fetch_one", str(query), tuple(params or ())))
        for sub, resp in self.fetch_one_responses:
            if sub in str(query):
                return resp() if callable(resp) else resp
        return None

    async def fetch_all(self, query, params=None):
        self.queries.append(("fetch_all", str(query), tuple(params or ())))
        for sub, resp in self.fetch_all_responses:
            if sub in str(query):
                return resp() if callable(resp) else resp
        return []


@pytest.mark.asyncio
async def test_canonical_id_match_returns_immediately():
    """Happy path: target_dt yields canonical that matches a stored row."""
    target_unix = 1_700_000_000
    map_name = "te_escape2"
    round_number = 1
    expected_cid = compute_canonical_id(target_unix, map_name, round_number)
    target_dt = datetime.fromtimestamp(target_unix)

    db = _ScriptedDb()
    db.add_fetch_one("WHERE round_canonical_id =", (4242,))

    round_id, diag = await resolve_round_id_with_reason(
        db, map_name, round_number, target_dt=target_dt,
    )

    assert round_id == 4242
    assert diag["reason_code"] == "resolved_canonical_id_match"
    assert diag["best_diff_seconds"] == 0
    # Confirm the canonical_id was passed in the query params
    canonical_queries = [q for kind, q, p in db.queries if "round_canonical_id" in q]
    assert canonical_queries, "canonical_id query never fired"
    canonical_params = [
        p for kind, q, p in db.queries if "round_canonical_id" in q
    ][0]
    assert expected_cid in canonical_params


@pytest.mark.asyncio
async def test_canonical_miss_falls_through_to_fuzzy():
    """target_dt + no canonical row → continues to legacy SELECT path."""
    target_unix = 1_700_000_000
    target_dt = datetime.fromtimestamp(target_unix)

    db = _ScriptedDb()
    db.add_fetch_one("WHERE round_canonical_id =", None)
    # Legacy fuzzy fallback returns one candidate at the exact target_unix
    db.add_fetch_all(
        "FROM rounds",
        [(1234, "2023-11-14", "170000", None, target_unix)],
    )

    round_id, diag = await resolve_round_id_with_reason(
        db, "te_escape2", 1, target_dt=target_dt,
    )

    assert round_id == 1234
    # Reason code is the legacy exact-unix branch, not canonical
    assert diag["reason_code"] != "resolved_canonical_id_match"


@pytest.mark.asyncio
async def test_canonical_branch_skipped_when_no_target_dt():
    """No target_dt → no canonical computation; legacy path runs unchanged."""
    db = _ScriptedDb()
    db.add_fetch_all("FROM rounds", [])

    round_id, diag = await resolve_round_id_with_reason(
        db, "te_escape2", 1, round_date="2023-11-14",
    )

    assert round_id is None
    canonical_fired = any("round_canonical_id" in q for kind, q, p in db.queries)
    assert not canonical_fired, "canonical_id query must NOT fire without target_dt"


@pytest.mark.asyncio
async def test_canonical_lookup_exception_is_non_fatal():
    """If the canonical lookup raises, the linker logs and falls through."""
    target_dt = datetime.fromtimestamp(1_700_000_000)

    class _ExplodingDb:
        def __init__(self):
            self.fallthrough_called = False

        async def fetch_one(self, query, params=None):
            if "round_canonical_id" in str(query):
                raise RuntimeError("simulated DB hiccup")
            return None

        async def fetch_all(self, query, params=None):
            self.fallthrough_called = True
            return []

    db = _ExplodingDb()
    round_id, diag = await resolve_round_id_with_reason(
        db, "te_escape2", 1, target_dt=target_dt,
    )

    assert round_id is None  # nothing matched, but we did NOT raise
    assert db.fallthrough_called, "linker must continue past canonical exception"


@pytest.mark.asyncio
async def test_tz_aware_target_dt_is_normalized_for_canonical():
    """A tz-aware UTC target_dt (PR #130 relinker) must produce the same
    canonical_id as the equivalent naive-local one.

    Regression guard: if normalization is removed, the canonical hash on
    UTC vs local will diverge by `timezone offset` seconds and break
    every linker call from the proximity relinker path.
    """
    target_unix = 1_700_000_000
    naive_local = datetime.fromtimestamp(target_unix)
    aware_utc = datetime.fromtimestamp(target_unix, tz=timezone.utc)

    db_naive = _ScriptedDb()
    db_naive.add_fetch_one("WHERE round_canonical_id =", (1,))

    db_aware = _ScriptedDb()
    db_aware.add_fetch_one("WHERE round_canonical_id =", (1,))

    rid_naive, _ = await resolve_round_id_with_reason(
        db_naive, "te_escape2", 1, target_dt=naive_local,
    )
    rid_aware, _ = await resolve_round_id_with_reason(
        db_aware, "te_escape2", 1, target_dt=aware_utc,
    )

    cid_naive = [
        p[0] for kind, q, p in db_naive.queries if "round_canonical_id" in q
    ][0]
    cid_aware = [
        p[0] for kind, q, p in db_aware.queries if "round_canonical_id" in q
    ][0]
    assert cid_naive == cid_aware, "tz-aware/naive canonical_id must match"
    assert rid_naive == rid_aware == 1


@pytest.mark.asyncio
async def test_invalid_round_number_skips_canonical():
    """round_number not in (0,1,2) → canonical branch is silently skipped
    because compute_canonical_id() returns None for those values.

    Note: resolve_round_id_with_reason's `invalid_input` guard only fires
    on FALSY round_number (0 or None). For out-of-range values like 5
    the linker still proceeds into the legacy fuzzy SELECT — it's
    `compute_canonical_id`'s round_number ∈ (0,1,2) check that prevents
    a meaningless canonical lookup. The test asserts both halves of
    that contract.
    """
    target_dt = datetime.fromtimestamp(1_700_000_000)
    db = _ScriptedDb()
    db.add_fetch_all("FROM rounds", [])

    round_id, _ = await resolve_round_id_with_reason(
        db, "te_escape2", round_number=5, target_dt=target_dt,
    )

    canonical_fired = any("round_canonical_id" in q for kind, q, p in db.queries)
    legacy_fired = any(
        "FROM rounds" in q and "round_canonical_id" not in q
        for kind, q, p in db.queries
    )
    assert round_id is None
    assert not canonical_fired, "canonical lookup must be suppressed for round_number=5"
    assert legacy_fired, "legacy fuzzy SELECT should still run (no early invalid_input)"
