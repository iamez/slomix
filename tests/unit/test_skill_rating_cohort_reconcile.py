"""The ratings table is reconciled to the run that produced it.

Measured on dev 2026-08-29: `player_skill_ratings` held 31 rows with 31
different `last_rated_at` values. Twenty-eight came from that morning's run.
Three — G4rch4, -C3jZi and MrAvAc — were written on 2026-05-06 and had sat on
the public leaderboard ever since. Their players had fallen under
MIN_ROUNDS (the table claimed 6 rounds; each has 4 valid ones today), so no
later run included them, and `compute_and_store_ratings` deleted only bot
rows. Their ratings therefore predate the shrinkage fix entirely — MrAvAc's
published rating equalled his raw score exactly.

That matters beyond tidiness. A rating is a percentile against the cohort it
was computed with, so a row from another cohort is a different measurement
sharing a column name, ranked against numbers it was never comparable to.
The proof is arithmetic: reconstructing every published rating from its own
components, the residual is 0.0001 median when the pool is the 28-row cohort
and up to 0.009 when the three stale rows are mixed into it. They corrupted
the pool, not just their own rank.

The function's own comment already stated the principle for bots; these
tests hold it to every player.
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from website.backend.services.skill_rating_service import (  # noqa: E402
    compute_and_store_ratings,
)


class _RecordingDB:
    """Records every execute(); returns a fixed cohort from fetch_all()."""

    def __init__(self, rows):
        self._rows = rows
        self.executed: list[tuple[str, tuple]] = []
        self.in_transaction = False
        self.outside_transaction: list[str] = []

    async def fetch_all(self, query, params=()):
        return self._rows

    @asynccontextmanager
    async def transaction(self):
        self.in_transaction = True
        try:
            yield self
        finally:
            self.in_transaction = False

    async def execute(self, query, params=()):
        flat = " ".join(query.split())
        if not self.in_transaction:
            self.outside_transaction.append(flat)
        self.executed.append((flat, params))

    def deletes_from(self, table: str) -> list[tuple[str, tuple]]:
        return [
            (q, p) for q, p in self.executed
            if q.startswith("DELETE") and table in q
        ]


def _row(guid, name, rounds, dpm=300.0, kpr=1.5):
    """One cohort row in the column order compute_all_ratings expects."""
    return (
        guid, name, rounds,
        dpm, kpr, 1.0, 40.0, 0.5, 0.5, 0.3, 0.3,   # 8 PCS metrics
        10.0, 0.4, 0.4, 0.5, 0.1, 0.1, 0.5,        # 7 proximity metrics
    )


@pytest.mark.asyncio
async def test_rows_outside_the_run_are_removed():
    """The published table holds exactly the players this run rated."""
    db = _RecordingDB([
        _row("keeps_playing", "Regular", 900),
        _row("also_playing", "Veteran", 400),
    ])

    await compute_and_store_ratings(db)

    reconcile = [
        (q, p) for q, p in db.deletes_from("player_skill_ratings")
        if "<> ALL" in q
    ]
    assert reconcile, "no reconciliation delete was issued"
    _, params = reconcile[0]
    assert sorted(params[0]) == ["also_playing", "keeps_playing"]


@pytest.mark.asyncio
async def test_a_concurrent_run_is_not_reconciled_away():
    """The delete is bounded by this run's own start time.

    Two requests can cross the one-hour staleness boundary together, and each
    execute() auto-commits, so an unbounded delete could remove rows another
    run had just written. Rows newer than this run's start are somebody
    else's fresh work, never this run's leftovers.
    """
    db = _RecordingDB([_row("still_here", "Player", 300)])

    await compute_and_store_ratings(db)

    reconcile = [
        (q, p) for q, p in db.deletes_from("player_skill_ratings")
        if "<> ALL" in q
    ]
    assert reconcile, "no reconciliation delete was issued"
    query, params = reconcile[0]
    assert "last_rated_at <" in query, "the delete is not bounded in time"
    # …and the bound is a real timestamp, not a placeholder that never binds.
    assert params[1] is not None
    assert hasattr(params[1], "tzinfo") and params[1].tzinfo is not None


@pytest.mark.asyncio
async def test_history_is_never_reconciled_away():
    """The past belongs in player_skill_history and stays there.

    Only the bot cleanup may touch history; a player leaving the cohort must
    not erase the snapshots of when they were in it.
    """
    db = _RecordingDB([_row("someone", "Someone", 120)])

    await compute_and_store_ratings(db)

    history_deletes = db.deletes_from("player_skill_history")
    assert len(history_deletes) == 1
    assert "OMNIBOT" in history_deletes[0][0]


@pytest.mark.asyncio
async def test_an_empty_run_clears_the_published_board():
    """An empty cohort is a result, and the board has to show it.

    This test asserted the opposite first, on the reasoning that an empty run
    must not "turn a bad run into data loss". These rows are a cache of a
    computation over player_comprehensive_stats — the next run rebuilds them
    and player_skill_history keeps every snapshot — so nothing is lost, while
    exempting the empty case left the previous cohort published under old
    timestamps and re-computed on every request (Codex on #835).

    The delete is still bounded in time, so an empty run cannot wipe a
    concurrent one's writes.
    """
    db = _RecordingDB([])

    await compute_and_store_ratings(db)

    reconcile = [
        (q, p) for q, p in db.deletes_from("player_skill_ratings")
        if "last_rated_at <" in q
    ]
    assert reconcile, "an empty run left the previous board published"
    query, params = reconcile[0]
    assert "<> ALL" not in query, (
        "an empty keep-list leaves the array's element type to the driver"
    )
    assert params[0].tzinfo is not None


@pytest.mark.asyncio
async def test_the_replacement_is_one_transaction():
    """Every write of a run lands together or not at all.

    db.execute() commits on its own, so without this the delete-then-write
    sequence was that many visible states — and one successful upsert
    refreshes last_rated_at, which makes a half-written board look fresh for
    an hour and poisons the pool mean derived from it (Codex on #835).
    """
    db = _RecordingDB([_row("a", "A", 300), _row("b", "B", 200)])

    await compute_and_store_ratings(db)

    assert db.executed, "nothing was written"
    assert db.outside_transaction == [], (
        "write(s) issued outside the transaction:\n"
        + "\n".join(db.outside_transaction)
    )
