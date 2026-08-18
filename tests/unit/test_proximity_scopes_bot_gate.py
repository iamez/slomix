"""Regression: /proximity/scopes must gate out bot-test / rejected rounds.

The session dropdown is built from `combat_engagement` in
`get_proximity_scopes`. It was the one proximity surface that skipped the
canonical `_round_quality_gate_sql`, so an all-bot test date (e.g. an
all-OMNIBOT 2026-08-12) showed up in the picker and — sorted newest-first —
became the page's DEFAULT scope, making the last real gather's proximity look
"missing". This pins the gate onto both queries the endpoint runs.
"""
import pytest

from website.backend.routers.proximity_dashboard import get_proximity_scopes


class _CaptureDB:
    """DB adapter stub that records every SQL string passed to fetch_all."""
    def __init__(self):
        self.queries: list[str] = []

    async def fetch_all(self, sql, params=None):
        self.queries.append(sql)
        return []


@pytest.mark.asyncio
async def test_scopes_applies_bot_round_gate_to_both_queries():
    db = _CaptureDB()
    await get_proximity_scopes(range_days=60, db=db)

    # The engagement-discovery query (combat_engagement) must carry the shared
    # round-quality gate, keeping orphans but excluding bot/rejected rounds.
    combat_q = next((q for q in db.queries if "FROM combat_engagement" in q), None)
    assert combat_q is not None, "scopes never queried combat_engagement"
    assert "is_bot_round IS DISTINCT FROM TRUE" in combat_q
    assert "is_valid IS DISTINCT FROM FALSE" in combat_q  # rejected rounds gated too
    assert "round_id IS NULL OR EXISTS" in combat_q  # orphan-keeping gate shape
    # Orphaned bot engagements (round_id NULL) slip past the round gate, so a
    # bot's OMNIBOT guid must be excluded directly on both sides of the kill.
    assert "killer_guid, '') NOT LIKE 'OMNIBOT%'" in combat_q
    assert "target_guid, '') NOT LIKE 'OMNIBOT%'" in combat_q

    # The canonical maps-played query (rounds) must exclude bot rounds too, so a
    # mixed bot+real date can't inflate the map count.
    rounds_q = next(
        (q for q in db.queries if "FROM rounds" in q and "round_number = 1" in q), None
    )
    assert rounds_q is not None, "scopes never ran the canonical maps-played query"
    assert "is_bot_round IS DISTINCT FROM TRUE" in rounds_q
