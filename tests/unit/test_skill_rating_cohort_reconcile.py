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

    async def fetch_all(self, query, params=()):
        return self._rows

    async def execute(self, query, params=()):
        self.executed.append((" ".join(query.split()), params))

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
async def test_an_empty_run_deletes_nothing():
    """A failed or empty computation must not empty the table.

    Without this guard the reconciliation turns one bad run into data loss —
    the failure mode is silent, permanent, and worse than the staleness it
    was written to fix.
    """
    db = _RecordingDB([])

    await compute_and_store_ratings(db)

    assert [q for q, _ in db.deletes_from("player_skill_ratings") if "<> ALL" in q] == []
