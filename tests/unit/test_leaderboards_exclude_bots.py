"""Every proximity leaderboard speaks the same bot exclusion.

Measured on 31. 8. 2026, range_days=30: OMNIBOT players held 7/10 spawn
seats, 6/10 reactions and 7/10 focus-fire — the S6 gate excludes bot
ROUNDS, and bots in mixed human rounds sailed through it. KROGT was the
only board already filtering players. The fix is one helper (`_no_bots`)
spliced into every category query, and power needs it only on its seed:
every component map filters by the seed's guid_set, so the percentile
pools inherit the exclusion from that single place.

The test drives the real router through a TestClient with a recording
database, then reads the SQL each category actually built — the same
"pin the executed query, not the source text" shape as
test_player_endpoints_r0_and_validity_scope.py. Zero entries come back
(the stub answers []), which is fine: the QUERY is the subject.
"""

import warnings

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

warnings.filterwarnings("ignore")

from website.backend import dependencies as deps  # noqa: E402
from website.backend.routers import proximity_scoring  # noqa: E402


class _RecordingDb:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def fetch_all(self, query, params=None):
        self.queries.append(" ".join(query.split()))
        return []

    async def fetch_one(self, query, params=None):
        self.queries.append(" ".join(query.split()))
        return None


@pytest.fixture()
def client_and_db():
    db = _RecordingDb()
    app = FastAPI()
    app.include_router(proximity_scoring.router, prefix="/api")
    app.dependency_overrides[deps.get_db] = lambda: db
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, db


# category -> the guid column whose rows the board ranks.
SUBJECT = {
    "power": "target_guid",
    "spawn": "killer_guid",
    "trades": "trader_guid",
    "reactions": "target_guid",
    "survivors": "target_guid",
    "movement": "player_guid",
    "focus_fire": "target_guid",
}


@pytest.mark.parametrize("category", sorted(SUBJECT))
def test_the_board_excludes_bot_players(client_and_db, category):
    client, db = client_and_db
    resp = client.get(f"/api/proximity/leaderboards?category={category}&range_days=30")
    assert resp.status_code == 200
    ranked = [q for q in db.queries if f"GROUP BY {SUBJECT[category]}" in q]
    assert ranked, f"no ranking query recorded for {category}: {db.queries}"
    q = ranked[0]
    assert f"{SUBJECT[category]} NOT LIKE 'OMNIBOT%'" in q
    assert "NOT LIKE '%[BOT]%'" in q


def test_crossfire_excludes_bots_on_both_teammate_columns(client_and_db):
    client, db = client_and_db
    resp = client.get("/api/proximity/leaderboards?category=crossfire&range_days=30")
    assert resp.status_code == 200
    subs = [q for q in db.queries if "teammate1_guid" in q]
    assert subs, f"crossfire query not recorded: {db.queries}"
    q = subs[0]
    assert "c.teammate1_guid NOT LIKE 'OMNIBOT%'" in q
    assert "c.teammate2_guid NOT LIKE 'OMNIBOT%'" in q


def test_krogt_still_carries_its_own_filter(client_and_db):
    # The one board that was already clean must stay clean — a refactor
    # that centralises the others could drop the original by accident.
    client, db = client_and_db
    resp = client.get("/api/proximity/leaderboards?category=krogt&range_days=30")
    assert resp.status_code == 200
    lives = [q for q in db.queries if "player_track pt" in q]
    assert lives, f"krogt lives query not recorded: {db.queries}"
    assert "pt.player_guid NOT LIKE 'OMNIBOT%'" in lives[0]
