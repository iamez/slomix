"""KIS recompute atomicity (Codex audit finding 8).

compute_session_kis stores results as DELETE + batch INSERT. Without a
transaction, a failed insert erases the session's KIS cache — every KIS-fed
surface (Smart Stats, Good Night, moments, ET Rating impact) then reads an
empty session until the next recompute. The store must roll back as one unit.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date

import pytest

from website.backend.services.storytelling.service import StorytellingService

SD = date(2026, 7, 6)

# kill tuple per kis.py schema:
# (ko_id, session_date, round_number, round_start_unix, map_name,
#  killer_guid, killer_name, victim_guid, victim_name, outcome, kill_time_ms)
KILL = (1, SD, 1, 1_700_000_000, "supply",
        "K1", "killer", "V1", "victim", "tapped_out", 10_000)


class TxFakeDB:
    """Fake adapter with snapshot/rollback transaction semantics.

    `kill_impact_rows` mimics storytelling_kill_impact for one session date;
    the transaction context snapshots it and restores it on exception —
    exactly what the PG adapter's transaction() guarantees.
    """

    def __init__(self, fail_insert=False):
        self.kill_impact_rows = [("old-row",)]
        self.fail_insert = fail_insert
        self.tx_entered = 0

    @asynccontextmanager
    async def transaction(self):
        self.tx_entered += 1
        snapshot = list(self.kill_impact_rows)
        try:
            yield self
        except Exception:
            self.kill_impact_rows = snapshot
            raise

    async def fetch_one(self, query, params=None):
        if "COUNT(*) FROM storytelling_kill_impact" in query:
            return (0,)  # force recompute path
        return None

    async def fetch_all(self, query, params=None):
        if "FROM proximity_kill_outcome" in query:
            return [KILL]
        return []  # all context loaders empty → default multipliers

    async def execute(self, query, params=None):
        if "DELETE FROM storytelling_kill_impact" in query:
            self.kill_impact_rows = []

    async def executemany(self, query, params_list):
        if self.fail_insert:
            raise RuntimeError("simulated insert failure")
        self.kill_impact_rows = list(params_list)


@pytest.mark.asyncio
async def test_failed_insert_preserves_old_kis_rows():
    db = TxFakeDB(fail_insert=True)
    svc = StorytellingService(db=db)
    with pytest.raises(RuntimeError, match="simulated insert failure"):
        await svc.compute_session_kis(SD, force=True)
    assert db.tx_entered == 1, "store must run inside db.transaction()"
    assert db.kill_impact_rows == [("old-row",)], (
        "failed recompute must keep the previous KIS cache"
    )


@pytest.mark.asyncio
async def test_successful_recompute_replaces_rows():
    db = TxFakeDB(fail_insert=False)
    svc = StorytellingService(db=db)
    result = await svc.compute_session_kis(SD, force=True)
    assert result["status"] == "computed"
    assert result["kills_scored"] == 1
    assert db.kill_impact_rows != [("old-row",)]
    assert len(db.kill_impact_rows) == 1
