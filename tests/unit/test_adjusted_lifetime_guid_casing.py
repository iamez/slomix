""":301 (Codex on #846): a history-only player's GUID must keep its stored
casing on the wire.

resolve_player_guid() resolves profiles with an exact, case-sensitive
`player_guid = $1`, and rated players already emit their stored casing via
`life[p][2]` for exactly that reason — but orphans used to emit the
UPPERCASED join key, so their profile link 404'd. Measured today: 0 history
GUIDs differ from their uppercase form (the fix is schema-truth about a
free-text column, not a live repair) — which is precisely why the test feeds
a lowercase one: a fixture cannot fail on a value the data does not contain.
"""

import json

import pytest

from website.backend.services.s_effort_service import FORMULA_VERSION, SEffortService


class _Db:
    """history carries a lowercase guid with no lifetime row (an orphan)."""

    def __init__(self):
        self.calls = 0

    async def fetch_all(self, query, params=None):
        self.calls += 1
        if "player_skill_history" in query:
            # 4 columns, and components must carry the CURRENT formula
            # version or the read-side filter drops the row before the
            # casing question is ever asked.
            return [
                (
                    "abcd1234efgh5678",
                    "2026-08-01",
                    0.5,
                    json.dumps({"formula_version": FORMULA_VERSION}),
                )
            ]
        if "player_skill_ratings" in query:
            return []
        return []


@pytest.mark.asyncio
async def test_an_orphan_guid_keeps_its_stored_casing():
    rows = await SEffortService(_Db()).compute_adjusted_lifetime()
    assert rows, "the orphan vanished entirely"
    assert rows[0]["player_guid"] == "abcd1234efgh5678", (
        f"emitted {rows[0]['player_guid']!r} — an uppercased key 404s the "
        "profile link, because resolve_player_guid is case-sensitive"
    )
