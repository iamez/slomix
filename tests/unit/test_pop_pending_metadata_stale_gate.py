"""Regression tests: B1 stale-metadata DB gate in _pop_pending_metadata.

Pins the 2026-05-13 fix in `bot/services/webhook_metadata_mixin.py`.

Background — see `docs/PLAN_B1_metadata_timestamp_leak_fix.md` and memory
`round_metadata_timestamp_leak.md` for the full motivation. Short version:
when a Lua webhook arrived AFTER its corresponding stats file was already
imported, the leftover bucket entry could be mis-attached to the NEXT
round on the same map, producing two rounds with identical
`round_start_unix` (canonical-id collision).

The fix: before returning a selected candidate, run a single DB query —
"is there already a round with this `(map_name, round_number,
round_start_unix)` triple?". If yes, the entry is stale — discard.

These tests cover the gate behavior end-to-end on a minimal mixin host
mock (mirrors the pattern in `test_stats_ready_race_reorder.py`).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.services.webhook_metadata_mixin import _WebhookMetadataMixin


def _make_bot(db_adapter=None):
    """Construct a minimal mixin host suitable for _pop_pending_metadata tests.

    Initializes the in-memory bucket + ttl fields that the mixin expects
    its hosting class to set up. `db_adapter` is attached only when given —
    omitting it exercises the "gate skipped because no DB" branch.
    """
    from collections import defaultdict

    class _Bot(_WebhookMetadataMixin):
        def __init__(self):
            self._pending_round_metadata = defaultdict(list)
            self._pending_metadata_ttl_seconds = 3 * 3600
            self._pending_metadata_max_per_key = 8

    bot = _Bot()
    if db_adapter is not None:
        bot.db_adapter = db_adapter
    return bot


def _make_metadata(map_name="te_escape2", round_number=1, start_unix=1771969065,
                   end_unix=1771969784):
    return {
        "map_name": map_name,
        "round_number": round_number,
        "round_start_unix": start_unix,
        "round_end_unix": end_unix,
    }


# ---------------------------------------------------------------------------
# Test 1 — happy path: DB returns no row, metadata is attached
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_happy_path_attaches_metadata_when_no_db_row():
    """Normal case: queue an entry, DB has no matching round → pop
    returns the metadata. This is the path that runs ~100% of the time
    in production."""
    db = MagicMock()
    db.fetch_one = AsyncMock(return_value=None)
    bot = _make_bot(db_adapter=db)

    bot._queue_pending_metadata(_make_metadata(), source="stats_ready")
    filename = "2026-02-24-223229-te_escape2-round-1.txt"

    result = await bot._pop_pending_metadata(filename)

    assert result is not None
    assert result["round_start_unix"] == 1771969065
    db.fetch_one.assert_awaited_once()


# ---------------------------------------------------------------------------
# Test 2 — stale gate fires: DB row exists with same start_unix
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stale_gate_discards_when_round_already_has_start_unix(caplog):
    """B1 regression: when the queued metadata's round_start_unix is
    already attached to a prior round in DB, the gate must return None
    (caller proceeds without Lua data instead of corrupting the new
    round with stale metadata)."""
    db = MagicMock()
    db.fetch_one = AsyncMock(return_value=(9955,))  # existing round_id
    bot = _make_bot(db_adapter=db)

    bot._queue_pending_metadata(_make_metadata(), source="stats_ready")
    # Different filename timestamp from the queued metadata — this is
    # the "next round on same map" scenario from the field incidents.
    filename = "2026-02-24-224947-te_escape2-round-1.txt"

    with caplog.at_level("WARNING", logger="bot.webhook"):
        result = await bot._pop_pending_metadata(filename)

    assert result is None
    assert any(
        "Stale Lua metadata" in rec.message
        for rec in caplog.records
    ), f"Expected stale-metadata WARN, got: {[r.message for r in caplog.records]}"


# ---------------------------------------------------------------------------
# Test 3 — gate skipped when round_start_unix is 0
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gate_skips_when_round_start_unix_is_zero():
    """Degenerate metadata (no start_unix yet — partial Lua payload)
    bypasses the gate entirely. Otherwise the gate's "WHERE
    round_start_unix=0" lookup would match all in-flight rounds and
    spuriously discard fresh metadata."""
    db = MagicMock()
    db.fetch_one = AsyncMock(return_value=(123,))  # would discard if asked
    bot = _make_bot(db_adapter=db)

    bot._queue_pending_metadata(
        _make_metadata(start_unix=0, end_unix=0),
        source="gametime",
    )
    filename = "2026-02-24-223229-te_escape2-round-1.txt"

    result = await bot._pop_pending_metadata(filename)

    assert result is not None
    assert result["round_start_unix"] == 0
    db.fetch_one.assert_not_awaited()


# ---------------------------------------------------------------------------
# Test 4 — fail open on DB error
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gate_fails_open_on_db_error(caplog):
    """If the gate's DB query raises (transient PG error, pool
    exhaustion, etc.), we must NOT block imports. Fall through with
    metadata intact — same behavior as pre-fix. WARN log surfaces it."""
    db = MagicMock()
    db.fetch_one = AsyncMock(side_effect=RuntimeError("pool exhausted"))
    bot = _make_bot(db_adapter=db)

    bot._queue_pending_metadata(_make_metadata(), source="stats_ready")
    filename = "2026-02-24-223229-te_escape2-round-1.txt"

    with caplog.at_level("WARNING", logger="bot.webhook"):
        result = await bot._pop_pending_metadata(filename)

    assert result is not None
    assert result["round_start_unix"] == 1771969065
    assert any(
        "DB lookup failed" in rec.message
        for rec in caplog.records
    )


# ---------------------------------------------------------------------------
# Test 5 — gate skipped when db_adapter is absent (partial init / tests)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gate_skips_when_db_adapter_absent():
    """During partial bot init or in tests that mock around the mixin,
    `db_adapter` may not be set yet. Gate must be a no-op in that case
    to avoid AttributeError + preserve legacy behavior."""
    bot = _make_bot(db_adapter=None)  # no db_adapter attached
    assert not hasattr(bot, "db_adapter")

    bot._queue_pending_metadata(_make_metadata(), source="stats_ready")
    filename = "2026-02-24-223229-te_escape2-round-1.txt"

    result = await bot._pop_pending_metadata(filename)

    assert result is not None
    assert result["round_start_unix"] == 1771969065


# ---------------------------------------------------------------------------
# Test 6 — map_name normalization matches pending-queue bucket key
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gate_normalizes_map_name_consistently_with_queue_keys(caplog):
    """Regression for Copilot review #255: the gate's DB lookup must use
    the same `_normalize_metadata_map_name` (strip + lower) that the
    pending-queue bucket keys use. A bare `str.lower()` would miss the
    DB row when the webhook payload has leading/trailing whitespace in
    `map_name`, false-negative letting stale metadata through.

    Here we queue metadata with surrounding whitespace + mixed case,
    then verify the gate's DB query was called with the stripped-lower
    normalized value (matching what the round row actually stores).
    """
    db = MagicMock()
    db.fetch_one = AsyncMock(return_value=(9955,))  # round exists
    bot = _make_bot(db_adapter=db)

    bot._queue_pending_metadata(
        _make_metadata(
            map_name="  TE_Escape2  ",  # quirky payload — strip + lower
            round_number=1,
            start_unix=1771969065,
        ),
        source="stats_ready",
    )
    # filename normalization in _parse_stats_filename_context returns
    # the regex group as-is, so this filename uses the lowercased form
    # that the bucket key was actually built from (queue key uses
    # _normalize_metadata_map_name internally).
    filename = "2026-02-24-223229-te_escape2-round-1.txt"

    with caplog.at_level("WARNING", logger="bot.webhook"):
        result = await bot._pop_pending_metadata(filename)

    # Gate should have fired (DB found a match because normalization
    # was consistent).
    assert result is None
    # Verify the query used the normalized form, not the raw quirky value.
    db.fetch_one.assert_awaited_once()
    call_args = db.fetch_one.await_args
    sql, params = call_args.args
    assert params[0] == "te_escape2", (
        f"Gate must use _normalize_metadata_map_name output 'te_escape2', "
        f"got {params[0]!r}. If this passes with the raw value, the "
        f"normalization regression has returned."
    )


# ---------------------------------------------------------------------------
# Test 7 — stopwatch R2 (Lua g_currentRound=0) goes through the gate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gate_normalizes_stopwatch_r2_round_number(caplog):
    """Regression for Codex P1 review on #255: this codebase maps Lua
    `g_currentRound=0` → stopwatch round 2 via
    `_normalize_lua_round_for_metadata_paths`. Bucket keys (`..._R2`)
    are built with that normalization, so a stale stopwatch-R2 entry
    can be SELECTED by the proximity matcher. If the gate then used a
    bare `int(round_number)` and skipped on `<= 0`, the exact collision
    this fix targets would still occur for stopwatch traffic.

    The gate must apply the same normalization before looking up
    or short-circuiting on `round_number`.
    """
    db = MagicMock()
    db.fetch_one = AsyncMock(return_value=(8888,))  # round exists
    bot = _make_bot(db_adapter=db)

    # Lua-style stopwatch R2 metadata: raw round_number=0, which the
    # codebase treats as R2. Queue uses _pending_metadata_key which
    # itself normalizes — so this entry lands in a "<map>_R2" bucket
    # the same way real production payloads do.
    bot._queue_pending_metadata(
        _make_metadata(
            map_name="te_escape2",
            round_number=0,  # Lua g_currentRound=0 means R2 in stopwatch
            start_unix=1771969065,
        ),
        source="gametime",
    )
    # The stats filename uses literal `round-2` (post-parser convention).
    filename = "2026-02-24-224947-te_escape2-round-2.txt"

    with caplog.at_level("WARNING", logger="bot.webhook"):
        result = await bot._pop_pending_metadata(filename)

    # Gate must fire: the entry IS stale (DB has the round).
    assert result is None, (
        "Stale stopwatch-R2 metadata must be caught by the gate. "
        "If this returns metadata, the gate skipped on a bare `int(0)<=0` "
        "check and missed the Lua R2 convention."
    )
    db.fetch_one.assert_awaited_once()
    # Verify the query used the normalized round number (2, not 0).
    call_args = db.fetch_one.await_args
    sql, params = call_args.args
    assert params[1] == 2, (
        f"Gate must use _normalize_lua_round_for_metadata_paths output 2, "
        f"got {params[1]!r}. If this passes with 0, the Lua R2 "
        f"normalization regression has returned."
    )


# ---------------------------------------------------------------------------
# Test 8 — replay of real field incident: round 9955/9958 collision
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_replay_real_incident_te_escape2_r1_collision(caplog):
    """End-to-end replay of the 2026-02-24 PROD incident:

      9955 imported: 2026-02-24 22:32:29, te_escape2 R1
      9958 imported: 2026-02-24 22:49:47, te_escape2 R1 (17 min later)
      Both stored with round_start_unix=1771969065 → canonical_id collision.

    The leftover Lua metadata from round 9955 (queued AFTER its stats
    file was already imported) sat in the bucket. Round 9958's stats
    file arrived, matched the leftover by proximity, and inherited
    9955's `round_start_unix`. This test simulates that exact sequence
    and verifies the gate now blocks the mis-attach.
    """
    db = MagicMock()
    # 9955 already imported with this round_start_unix.
    db.fetch_one = AsyncMock(return_value=(9955,))
    bot = _make_bot(db_adapter=db)

    # Lua webhook for round 9955 arrives LATE — after 9955's stats file
    # was already imported (so nothing pops it at import time).
    bot._queue_pending_metadata(
        _make_metadata(
            map_name="te_escape2",
            round_number=1,
            start_unix=1771969065,
            end_unix=1771969784,
        ),
        source="gametime",
    )

    # 17 minutes later, round 9958's stats file (te_escape2 R1 again)
    # arrives. Old behavior: matcher picks the leftover, attaches
    # 9955's start_unix to 9958 → collision. New behavior: gate
    # discards the leftover, 9958 imports without Lua metadata.
    filename = "2026-02-24-224947-te_escape2-round-1.txt"

    with caplog.at_level("WARNING", logger="bot.webhook"):
        result = await bot._pop_pending_metadata(filename)

    assert result is None, (
        "Gate should discard the stale 9955 metadata; "
        "without the gate, 9958 would inherit it and collide."
    )
    assert any(
        "round_id=9955" in rec.message
        for rec in caplog.records
    ), "WARN log should name the round_id that's claiming the start_unix"
