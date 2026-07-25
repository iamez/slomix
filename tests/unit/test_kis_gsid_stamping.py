"""Legacy-path KIS rows must not recreate the NULL-gsid regression.

Migration 063 added storytelling_kill_impact.gaming_session_id without a
backfill, and #533/#535/#539 then started filtering on it — every session
whose rows were computed via the legacy session_date path (87% of the table
before migration 064) returned empty/zero on useless-defense, PWC crossfire
and enabler. Migration 064 backfills history; this file locks in the code
half of the fix: the legacy compute path must stamp gaming_session_id on
the rows it just inserted (via the canonical round key against rounds),
so a legacy recompute can never reintroduce NULL-gsid rows for sessions
that rounds can attribute.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date

import pytest

from website.backend.services.storytelling.service import StorytellingService

DATE1 = date(2026, 7, 13)

# proximity_kill_outcome row shape (kis.py's kills query):
# (id, session_date, round_number, round_start_unix, map_name,
#  killer_guid, killer_name, victim_guid, victim_name, outcome, kill_time)
KILL = (1, DATE1, 1, 1000, "supply", "K1", "killer1", "V1", "victim1", "tapped_out", 5000)

# _fetch_scope_rounds row shape: (round_start_unix, map_name, round_number, rdate)
SCOPE_ROUNDS = [(1000, "supply", 1, "2026-07-13")]


class _StampFakeDB:
    def __init__(self):
        self.updates: list[tuple[str, tuple]] = []
        self.deletes: list[tuple[str, tuple]] = []
        self.inserted_batches: list[tuple] = []

    @asynccontextmanager
    async def transaction(self):
        yield self

    async def fetch_one(self, query, params=None):
        return None  # force=True bypasses cache checks anyway

    async def fetch_all(self, query, params=None):
        q = " ".join(query.split())
        if "FROM rounds" in q and "round_start_unix, map_name, round_number" in q:
            return SCOPE_ROUNDS
        if "FROM proximity_kill_outcome" in q:
            return [KILL]
        return []  # context loaders: empty -> default multipliers

    async def execute(self, query, params=None):
        q = " ".join(query.split())
        if q.startswith("DELETE FROM storytelling_kill_impact"):
            self.deletes.append((q, params))
        elif q.startswith("UPDATE storytelling_kill_impact"):
            self.updates.append((q, params))

    async def executemany(self, query, params_list):
        self.inserted_batches = list(params_list)


@pytest.mark.asyncio
async def test_legacy_date_path_stamps_gsid_after_insert():
    db = _StampFakeDB()
    svc = StorytellingService(db=db)

    result = await svc.compute_session_kis(DATE1, force=True)

    assert result["status"] == "computed"
    assert result["kills_scored"] == 1
    # Rows themselves went in with a NULL gaming_session_id ...
    assert db.inserted_batches[0][-1] is None
    # ... so the path MUST follow up with the round-key stamping UPDATE.
    assert len(db.updates) == 1
    q, params = db.updates[0]
    assert "SET gaming_session_id" in q
    assert "k.session_date = ANY($1)" in q
    # Only rows this compute touched, and only the still-NULL ones.
    assert "k.gaming_session_id IS NULL" in q
    # Canonical round-key join — the same triple every scoped reader uses.
    assert "k.round_start_unix = r.round_start_unix" in q
    assert "k.map_name = r.map_name" in q
    assert "k.round_number = r.round_number" in q
    # Ambiguous keys (one round key -> two gsids) must be skipped, not guessed.
    assert "HAVING COUNT(DISTINCT gaming_session_id) = 1" in q
    assert params == ([DATE1],)


@pytest.mark.asyncio
async def test_gsid_native_path_does_not_double_stamp():
    """The gsid path already writes gaming_session_id on every row —
    an extra UPDATE there would be wasted work (and would mask a stamping
    bug on the legacy path if the assertion above ever regressed)."""
    db = _StampFakeDB()
    svc = StorytellingService(db=db)

    result = await svc.compute_session_kis_for_gsid(137, force=True)

    assert result["status"] == "computed"
    assert db.inserted_batches[0][-1] == 137
    assert db.updates == []
