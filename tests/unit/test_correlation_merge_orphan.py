"""Tests for RoundCorrelationService._merge_orphan (Phase E late-merge).

The merge picks up flags + lua_teams_id from a stale orphan correlation
row and copies them into the canonical target, then deletes the orphan.
Pin behavior so a future "optimize" doesn't silently drop completeness
flags or leak orphan rows.
"""
from __future__ import annotations

import pytest

from bot.services.round_correlation_service import RoundCorrelationService

# Column order matches the SELECT in _merge_orphan
# (has_r1_stats, has_r2_stats, has_r1_lua_teams, has_r2_lua_teams,
#  has_r1_gametime, has_r2_gametime, has_r1_endstats, has_r2_endstats,
#  has_r1_proximity, has_r2_proximity, r1_lua_teams_id, r2_lua_teams_id)


def _row(**kwargs):
    """Build a row tuple, defaulting unspecified columns to False/None."""
    flags = [
        "has_r1_stats", "has_r2_stats",
        "has_r1_lua_teams", "has_r2_lua_teams",
        "has_r1_gametime", "has_r2_gametime",
        "has_r1_endstats", "has_r2_endstats",
        "has_r1_proximity", "has_r2_proximity",
    ]
    ids = ["r1_lua_teams_id", "r2_lua_teams_id"]
    return tuple(
        [kwargs.get(f, False) for f in flags] + [kwargs.get(i, None) for i in ids]
    )


class _MergeFakeDb:
    def __init__(self, rows: dict[str, tuple | None]):
        self.rows = rows  # correlation_id -> row tuple (or None)
        self.executed: list[tuple[str, tuple]] = []

    async def fetch_one(self, query, params=None):
        q = str(query)
        if "FROM round_correlations" in q and "correlation_id = ?" in q:
            cid = params[0] if params else None
            row = self.rows.get(cid)
            if row is None:
                return None
            # _recalculate_completeness selects only the 10 has_* flags;
            # _merge_orphan additionally selects 2 lua_teams_id cols.
            if "r1_lua_teams_id" in q:
                return row  # full 12-tuple
            return row[:10]   # flag-only 10-tuple
        if "GROUP BY status" in q:
            return None
        return None

    async def fetch_all(self, query, params=None):
        return []

    async def execute(self, query, params=None, *extra):
        self.executed.append((str(query), params))
        return "EXECUTE"


def _make_service(db):
    svc = RoundCorrelationService(
        db,
        dry_run=False,
        require_schema_check=False,
        write_error_threshold=5,
    )
    svc._initialized = True
    svc.preflight_ok = True
    return svc


@pytest.mark.asyncio
async def test_merge_copies_flags_and_deletes_source():
    """Source has has_r1_proximity + r1_lua_teams_id, target lacks both."""
    db = _MergeFakeDb({
        "src-cid": _row(has_r1_proximity=True, r1_lua_teams_id=42),
        "tgt-cid": _row(has_r1_stats=True, has_r2_stats=True),
    })
    svc = _make_service(db)

    ok = await svc._merge_orphan("src-cid", "tgt-cid")
    assert ok is True

    # An UPDATE must have been issued for the target with the missing fields
    update_calls = [
        (q, p) for q, p in db.executed
        if "UPDATE round_correlations SET" in q
    ]
    assert len(update_calls) >= 1
    update_q, update_params = update_calls[0]
    assert "has_r1_proximity" in update_q
    assert "r1_lua_teams_id" in update_q
    # Last param is the WHERE correlation_id binding
    assert update_params[-1] == "tgt-cid"

    # And the source must have been deleted
    delete_calls = [
        (q, p) for q, p in db.executed
        if "DELETE FROM round_correlations" in q
    ]
    assert len(delete_calls) == 1
    assert delete_calls[0][1] == ("src-cid",)


@pytest.mark.asyncio
async def test_merge_no_op_when_nothing_to_copy_still_deletes_source():
    """Source has no extra flags vs target → no UPDATE, but source still
    gets cleaned up so the orphan stops accumulating.
    """
    db = _MergeFakeDb({
        "src-cid": _row(has_r1_stats=True),
        "tgt-cid": _row(has_r1_stats=True, has_r2_stats=True),
    })
    svc = _make_service(db)

    ok = await svc._merge_orphan("src-cid", "tgt-cid")
    assert ok is True

    update_calls = [q for q, _ in db.executed if "UPDATE round_correlations SET" in q]
    delete_calls = [q for q, _ in db.executed if "DELETE FROM round_correlations" in q]
    assert update_calls == [], "no UPDATE should fire when nothing to copy"
    assert len(delete_calls) == 1, "DELETE should still run to clear the orphan"


@pytest.mark.asyncio
async def test_merge_returns_false_when_source_missing():
    db = _MergeFakeDb({"tgt-cid": _row()})
    svc = _make_service(db)
    ok = await svc._merge_orphan("does-not-exist", "tgt-cid")
    assert ok is False
    # No writes attempted
    assert all("UPDATE" not in q and "DELETE" not in q for q, _ in db.executed)


@pytest.mark.asyncio
async def test_merge_returns_false_when_target_missing():
    db = _MergeFakeDb({"src-cid": _row(has_r1_proximity=True)})
    svc = _make_service(db)
    ok = await svc._merge_orphan("src-cid", "no-target")
    assert ok is False
    assert all("UPDATE" not in q and "DELETE" not in q for q, _ in db.executed)


@pytest.mark.asyncio
async def test_merge_does_not_overwrite_target_flags():
    """If target already has has_r1_stats=True, source flag is NOT
    re-applied (would generate noisy UPDATE param duplication)."""
    db = _MergeFakeDb({
        "src-cid": _row(has_r1_stats=True, has_r1_proximity=True),
        "tgt-cid": _row(has_r1_stats=True),  # already set
    })
    svc = _make_service(db)

    await svc._merge_orphan("src-cid", "tgt-cid")
    update_calls = [
        (q, p) for q, p in db.executed
        if "UPDATE round_correlations SET" in q
    ]
    # Only has_r1_proximity should be in the UPDATE — has_r1_stats is
    # already true on target.
    assert update_calls
    update_q = update_calls[0][0]
    assert "has_r1_proximity" in update_q
    # Crude but sufficient: the UPDATE must NOT mention has_r1_stats again
    assert "has_r1_stats" not in update_q


@pytest.mark.asyncio
async def test_merge_does_not_overwrite_existing_lua_teams_id():
    """When both source and target have a non-NULL lua_teams_id, target's
    value wins (no overwrite). This protects against accidentally pointing
    a healthy target row at a now-deleted lua_round_teams id."""
    db = _MergeFakeDb({
        "src-cid": _row(r1_lua_teams_id=99),
        "tgt-cid": _row(r1_lua_teams_id=10),  # already set, must not be touched
    })
    svc = _make_service(db)

    await svc._merge_orphan("src-cid", "tgt-cid")
    update_calls = [
        q for q, _ in db.executed if "UPDATE round_correlations SET" in q
    ]
    # No flag/id differences worth copying → no UPDATE issued.
    assert update_calls == []
