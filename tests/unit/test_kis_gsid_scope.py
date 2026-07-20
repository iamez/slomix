"""compute_session_kis_for_gsid — KIS on the full gaming-session scope
(Codex §5/§8 SS-B).

storytelling_kill_impact was keyed only by session_date, the same scope
defect BOX score had (#524): a gaming session that crosses midnight has
kills split across two independent session_date fragments. This locks in
that the gsid-native compute path (1) resolves the FULL scope via
session_scope.py, (2) loads context (carrier kills, pushes, ...) for EVERY
date fragment and merges them — not just the first one, which would
silently under-score the second fragment's kills with default multipliers
— and (3) stamps gaming_session_id on every row it writes.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date

import pytest

from website.backend.services.storytelling.base import CARRIER_KILL_MULTIPLIER
from website.backend.services.storytelling.service import StorytellingService

DATE1 = date(2026, 7, 18)
DATE2 = date(2026, 7, 19)  # midnight-crossing fragment

# _fetch_scope_rounds row shape: (round_start_unix, map_name, round_number, rdate)
SCOPE_ROUNDS = [
    (1000, "supply", 1, "2026-07-18"),
    (90000, "goldrush", 1, "2026-07-19"),
]

# proximity_kill_outcome row shape (kis.py's kills query):
# (id, session_date, round_number, round_start_unix, map_name,
#  killer_guid, killer_name, victim_guid, victim_name, outcome, kill_time)
KILL_A = (1, DATE1, 1, 1000, "supply", "K1", "killer1", "V1", "victim1", "tapped_out", 5000)
KILL_B = (2, DATE2, 1, 90000, "goldrush", "K2", "killer2", "V2", "victim2", "tapped_out", 8000)

# proximity_carrier_kill row shape (loaders.py._load_carrier_kills):
# (killer_guid, round_start_unix, round_number, kill_time, map_name)
CARRIER_KILL_ROWS_BY_DATE = {
    DATE1: [("K1", 1000, 1, 5000, "supply")],
    DATE2: [("K2", 90000, 1, 8000, "goldrush")],
}


class _GsidKisFakeDB:
    def __init__(self):
        self.executed_deletes: list[tuple] = []
        self.inserted_batches: list[tuple] = []
        self.kills_query_text: str | None = None
        self.tx_entered = 0

    @asynccontextmanager
    async def transaction(self):
        self.tx_entered += 1
        yield self

    async def fetch_one(self, query, params=None):
        return None  # force=True bypasses every cache-check read in tests below

    async def fetch_all(self, query, params=None):
        q = " ".join(query.split())
        params = params or ()
        if "FROM rounds" in q and "round_start_unix, map_name, round_number" in q:
            return SCOPE_ROUNDS
        if "FROM proximity_kill_outcome" in q:
            self.kills_query_text = q
            return [KILL_A, KILL_B]
        if "FROM proximity_carrier_kill" in q:
            d = params[0]
            return CARRIER_KILL_ROWS_BY_DATE.get(d, [])
        return []  # the other 6 context loaders: empty -> default multipliers

    async def execute(self, query, params=None):
        q = " ".join(query.split())
        if "DELETE FROM storytelling_kill_impact" in q:
            self.executed_deletes.append(params)

    async def executemany(self, query, params_list):
        self.inserted_batches = list(params_list)


@pytest.mark.asyncio
async def test_compute_session_kis_for_gsid_merges_context_across_date_fragments():
    db = _GsidKisFakeDB()
    svc = StorytellingService(db=db)

    result = await svc.compute_session_kis_for_gsid(137, force=True)

    assert result["status"] == "computed"
    assert result["kills_scored"] == 2

    by_killer = {row[5]: row for row in db.inserted_batches}
    assert set(by_killer) == {"K1", "K2"}
    # Both kills' carrier_multiplier must reflect their OWN date's context.
    # If the second date fragment's loaders were never called (a bug this
    # test exists to catch), K2's kill would silently score at the default
    # 1.0 multiplier instead of CARRIER_KILL_MULTIPLIER.
    assert by_killer["K1"][10] == pytest.approx(CARRIER_KILL_MULTIPLIER)
    assert by_killer["K2"][10] == pytest.approx(CARRIER_KILL_MULTIPLIER)


class _SharedDateFakeDB:
    """Two DIFFERENT gaming sessions (137 and 999) both play on DATE1 —
    proximity_kill_outcome has no gaming_session_id column, only
    session_date/round_start_unix/map_name/round_number, so a bare
    session_date filter cannot tell the two sessions' kills apart."""

    def __init__(self):
        self.executed_deletes: list[tuple] = []
        self.inserted_batches: list[tuple] = []
        self.tx_entered = 0
        # gsid 137 owns round_start_unix=1000 (supply); a DIFFERENT session
        # (999, never resolved here) owns round_start_unix=5000 (goldrush)
        # on the SAME calendar date.
        self.scope_rounds = [(1000, "supply", 1, "2026-07-18")]
        self.kill_mine = (1, DATE1, 1, 1000, "supply", "K1", "killer1", "V1", "victim1", "tapped_out", 5000)
        self.kill_other_session = (
            2, DATE1, 1, 5000, "goldrush", "K9", "killer9", "V9", "victim9", "tapped_out", 3000,
        )

    @asynccontextmanager
    async def transaction(self):
        self.tx_entered += 1
        yield self

    async def fetch_one(self, query, params=None):
        return None

    async def fetch_all(self, query, params=None):
        q = " ".join(query.split())
        if "FROM rounds" in q and "round_start_unix, map_name, round_number" in q:
            return self.scope_rounds
        if "FROM proximity_kill_outcome" in q:
            # A REGRESSION back to `session_date = ANY(...)` would make this
            # branch return BOTH kills (both share DATE1); a precise
            # round-key filter must exclude the other session's kill.
            if "session_date = any" in q.lower():
                return [self.kill_mine, self.kill_other_session]
            return [self.kill_mine]  # round-key filter correctly excludes kill_other_session
        return []

    async def execute(self, query, params=None):
        q = " ".join(query.split())
        if "DELETE FROM storytelling_kill_impact" in q:
            self.executed_deletes.append(params)

    async def executemany(self, query, params_list):
        self.inserted_batches = list(params_list)


@pytest.mark.asyncio
async def test_compute_session_kis_for_gsid_excludes_other_session_sharing_same_date():
    """The exact bug Copilot flagged on #525: two gaming sessions on the
    same calendar date must not have their kills mixed by a gsid-scoped
    compute for one of them."""
    db = _SharedDateFakeDB()
    svc = StorytellingService(db=db)

    result = await svc.compute_session_kis_for_gsid(137, force=True)

    assert result["kills_scored"] == 1
    assert len(db.inserted_batches) == 1
    assert db.inserted_batches[0][5] == "K1"  # killer_guid — only OUR session's kill
    # The other session's kill (K9, round_start_unix=5000) must never appear.
    assert all(row[5] != "K9" for row in db.inserted_batches)


@pytest.mark.asyncio
async def test_compute_session_kis_for_gsid_stamps_gaming_session_id_on_every_row():
    db = _GsidKisFakeDB()
    svc = StorytellingService(db=db)

    await svc.compute_session_kis_for_gsid(137, force=True)

    assert len(db.inserted_batches) == 2
    for row in db.inserted_batches:
        assert row[32] == 137  # gaming_session_id is the last column


@pytest.mark.asyncio
async def test_compute_session_kis_for_gsid_deletes_by_precise_round_keys():
    """The delete (and the kills fetch feeding it) must scope by the exact
    round_start_unix/map_name/round_number triples this gsid's scope
    contains — NOT by session_date, which another, unrelated gaming session
    could share (Copilot review on #525: a bare date filter would wipe out
    that other session's KIS rows too)."""
    db = _GsidKisFakeDB()
    svc = StorytellingService(db=db)

    await svc.compute_session_kis_for_gsid(137, force=True)

    assert len(db.executed_deletes) == 1
    starts, maps, nums = db.executed_deletes[0]
    assert set(starts) == {1000, 90000}
    assert set(maps) == {"supply", "goldrush"}
    assert set(nums) == {1}


@pytest.mark.asyncio
async def test_compute_session_kis_for_gsid_kills_query_filters_by_round_key_not_date():
    """Locks in the actual SQL shape: the gsid-native path must filter kills
    by the (round_start_unix, map_name, round_number) triple, never by a
    bare `session_date = ANY(...)` — a regression back to date-only
    filtering would silently reintroduce the cross-session mixing bug."""
    db = _GsidKisFakeDB()
    svc = StorytellingService(db=db)

    await svc.compute_session_kis_for_gsid(137, force=True)

    assert db.kills_query_text is not None
    assert "round_start_unix, ko.map_name, ko.round_number) in" in db.kills_query_text.lower()
    assert "unnest(" in db.kills_query_text.lower()
    assert "session_date = any" not in db.kills_query_text.lower()


@pytest.mark.asyncio
async def test_compute_session_kis_for_gsid_runs_inside_a_transaction():
    db = _GsidKisFakeDB()
    svc = StorytellingService(db=db)

    await svc.compute_session_kis_for_gsid(137, force=True)

    assert db.tx_entered == 1


@pytest.mark.asyncio
async def test_compute_session_kis_for_gsid_unknown_id_is_404():
    from fastapi import HTTPException

    db_no_rounds = _GsidKisFakeDB()

    async def _empty_fetch_all(query, params=None):
        return []
    db_no_rounds.fetch_all = _empty_fetch_all

    svc = StorytellingService(db=db_no_rounds)
    with pytest.raises(HTTPException) as exc_info:
        await svc.compute_session_kis_for_gsid(9999, force=True)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_legacy_compute_session_kis_still_stamps_null_gaming_session_id():
    """Regression: the existing session_date-scoped entrypoint must keep
    writing gaming_session_id=NULL — it has no gsid to stamp, and must not
    silently guess one."""
    db = _GsidKisFakeDB()
    svc = StorytellingService(db=db)

    result = await svc.compute_session_kis(DATE1, force=True)

    assert result["status"] == "computed"
    assert result["kills_scored"] == 2  # FakeDB returns both KILL_A/KILL_B regardless of date filter
    for row in db.inserted_batches:
        assert row[32] is None
