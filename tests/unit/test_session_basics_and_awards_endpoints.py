"""Stats 2.0 — /stats/session/{id}/basics and /awards (docs/design/18 §E).

Same harness as the sibling endpoint tests: a FastAPI sub-app, httpx over
ASGI, a stub DB that answers by query shape with POSITIONAL tuples in the
handlers' column order. The stub is the contract the SQL has to honour.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from website.backend.dependencies import get_db
from website.backend.routers.sessions_router import SessionAwards, SessionBasics, router

#: SESSION_ROUNDS_SQL: (id, map, round_number, winner_team, round_date,
#:  round_time, actual_time, round_start_unix, actual_duration_seconds)
_ROUNDS = [
    (11, "supply", 1, 1, "2026-08-27", "21:00:00", "10:00", 1000, 600),
    (12, "supply", 2, 2, "2026-08-27", "21:12:00", "10:00", 1700, None),  # duration from lua
]
#: session_player_sql column order (26 columns; useless_kills is #25):
#: guid, name, kills, deaths, dmg_given, dmg_recv, dpm, kd, hs_kills, kills_for_hs,
#: gibs, self_kills, useful, full_selfkills, rev_given, times_revived, time_played,
#: assists, time_dead_min, denied, hits, shots, weapon_hs, tpp_weighted, tpp_weight, useless
_HUMAN = ("AAAAAAAA", "^1alpha", 40, 20, 12000, 9000, 600.0, 2.0, 10, 40,
          5, 3, 12, 1, 4, 2, 1200, 6, 4.0, 180, 200, 500, 40, 60000.0, 1200.0, 7)
_QUIET = ("BBBBBBBB", "bravo", 0, 5, 0, 300, 0.0, 0.0, 0, 0,
          0, 0, 0, 0, 0, 1, 0, 0, 0.0, 0, 0, 0, 0, 0.0, 0.0, 0)
#: A 2025-backfill shape: 107 s played, 10 470 "seconds" denied — impossible.
_SUSPECT = ("CCCCCCCC", "charlie", 4, 2, 500, 400, 280.4, 2.0, 0, 4,
            0, 0, 0, 0, 0, 0, 107, 0, 0.0, 10470, 10, 20, 1, 0.0, 0.0, 0)
_BOT = ("OMNIBOT04bc6dd06bc927a9934367f17", "[BOT] eve", 99, 1, 99999, 1, 999.0, 99.0, 0, 99,
        0, 0, 0, 0, 0, 0, 1200, 0, 0.0, 0, 0, 0, 0, 0.0, 0.0, 0)
#: round_awards: (award_name, player_name, player_guid, award_value, award_value_numeric, round_id)
_AWARDS = [
    ("Most damage given", "^1alpha", "AAAAAAAA", "7000", 7000.0, 11),
    ("Most damage given", "^1alpha", "AAAAAAAA", "5000", 5000.0, 12),
    ("Best K/D ratio", "bravo", None, "3.0", 3.0, 11),          # name-only row -> alias lookup
    ("Best K/D ratio", "^1alpha", "AAAAAAAA", "2.0", 2.0, 12),
    ("Most kills", "[BOT] eve", "OMNIBOT04bc6dd06bc927a9934367f17", "99", 99.0, 11),  # dropped
]


class _StubDB:
    def __init__(self, *, kis: bool = True, teams: bool = False, awards: bool = True):
        self.kis = kis
        self.teams = teams
        self.awards = awards
        self.queries: list[str] = []

    async def fetch_all(self, query, params=None):
        self.queries.append(query)
        q = " ".join(query.split())
        if "FROM rounds r WHERE r.gaming_session_id" in q:
            return _ROUNDS
        if "FROM player_comprehensive_stats p" in q:
            rows = [_HUMAN, _QUIET, _SUSPECT, _BOT]
            if "NOT LIKE 'OMNIBOT%'" in q:
                rows = [r for r in rows if not r[0].startswith("OMNIBOT")]
            return rows
        if "FROM lua_round_teams" in q:
            return [(12, 660)]
        if "FROM storytelling_kill_impact" in q:
            # killer_guid is the 32-char proximity guid — the join is on [:8].
            return [("AAAAAAAA000000000000000000000000", 42.5, 17)] if self.kis else []
        if "FROM round_awards ra" in q:
            return _AWARDS if self.awards else []
        if "player_aliases" in q or "FROM player_comprehensive_stats" in q:
            return [("bravo", "BBBBBBBB")]
        # session_scope's round enumeration for the KIS scope
        if "gaming_session_id" in q and "round_start_unix" in q:
            return [(1000, "supply", 1, "2026-08-27"), (1700, "supply", 2, "2026-08-27")]
        if "session_teams" in q:
            return [("Team A", '["AAAAAAAA"]', '["alpha"]'), ("Team B", '["BBBBBBBB"]', '["bravo"]')] if self.teams else []
        return []

    async def fetch_one(self, query, params=None):
        self.queries.append(query)
        q = " ".join(query.split())
        if "COUNT(*) FROM rounds WHERE gaming_session_id" in q:
            return (3,)
        return None

    async def fetch_val(self, query, params=None):
        return None


class _EmptyDB(_StubDB):
    async def fetch_all(self, query, params=None):
        return []

    async def fetch_one(self, query, params=None):
        return None


async def _get(db, path: str) -> tuple[int, dict]:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        response = await client.get(path)
    return response.status_code, (response.json() if response.content else {})


@pytest.mark.asyncio
async def test_basics_rows_bots_dropped_definitions_honoured():
    db = _StubDB()
    status, body = await _get(db, "/api/stats/session/154/basics")
    assert status == 200
    SessionBasics.model_validate(body)
    names = [p["name"] for p in body["players"]]
    assert names == ["alpha", "charlie", "bravo"], "colour codes stripped, bot dropped, sorted by dpm"
    alpha, charlie, bravo = body["players"]
    # An impossible denial (10 470 s in 107 s) is null and counted, not 9 785 %.
    assert charlie["denied_pct"] is None and charlie["denied_playtime_seconds"] == 10470
    assert alpha["denied_pct"] == 15.0            # 180 / 1200
    assert alpha["dpm"] == 600.0                  # 12000*60/1200
    assert alpha["dmr"] == 1.33                   # 12000 / 9000
    assert alpha["accuracy"] == 40.0 and alpha["headshot_pct"] == 20.0   # 200/500, 40/200
    # UK means useful (the legacy column, owner 2026-09-03); useless is its own field.
    assert alpha["useful_kills"] == 12 and alpha["useless_kills"] == 7 and alpha["full_selfkills"] == 1
    assert alpha["kis_total"] == 42.5 and alpha["kis_per_min"] == 2.12   # 42.5 / 20 min, round-half-even
    # played_pct = 1200 / (600 + 660) — the lua duration wins for round 12.
    assert alpha["played_pct"] == 95.2
    assert alpha["alive_pct"] == 50.0 and alpha["alive_pct_drift"] is True   # engine 50 vs computed 80
    # Nothing fired, nothing played: the answer is "not measured", not 0.
    assert bravo["denied_pct"] is None and bravo["accuracy"] is None and bravo["headshot_pct"] is None
    assert bravo["played_pct"] == 0.0 and bravo["dpm"] == 0.0
    assert bravo["kis_total"] is None
    assert body["coverage"] == {
        "rounds_counted": 2, "rounds_total": 3, "total_kills": 44, "kis_kills": 17,
        "kis_covered": True, "teams_attributed": False, "denied_suspect_players": 1,
    }
    assert body["teams"] == [] and alpha["team"] is None


@pytest.mark.asyncio
async def test_basics_without_kis_is_null_everywhere_not_zero():
    status, body = await _get(_StubDB(kis=False), "/api/stats/session/154/basics")
    assert status == 200
    assert body["coverage"]["kis_covered"] is False and body["coverage"]["kis_kills"] == 0
    assert all(p["kis_total"] is None and p["kis_per_min"] is None for p in body["players"])


@pytest.mark.asyncio
async def test_basics_and_awards_404_on_an_unknown_session():
    assert (await _get(_EmptyDB(), "/api/stats/session/999/basics"))[0] == 404
    assert (await _get(_EmptyDB(), "/api/stats/session/999/awards"))[0] == 404


@pytest.mark.asyncio
async def test_awards_roll_up_by_rule_drop_bots_and_add_the_computed_three():
    db = _StubDB()
    status, body = await _get(db, "/api/stats/session/154/awards")
    assert status == 200
    SessionAwards.model_validate(body)
    assert body["rounds_counted"] == 2 and body["rounds_with_awards"] == 2
    flat = {a["engine_name"]: a for c in body["categories"] for a in c["awards"]}
    assert "Most kills" not in flat, "the bot's award never reaches the page"
    assert flat["Most damage given"]["value"] == "12 000" and flat["Most damage given"]["rounds_won"] == 2
    # Best K/D is a max, not a sum: bravo's single 3.0 beats alpha's 2.0.
    kd = flat["Best K/D ratio"]
    assert kd["player"] == "bravo" and kd["guid"] == "BBBBBBBB", "the name-only row resolved through the alias map"
    assert kd["sentence"].startswith("The Best KDR award goes to bravo for the best kill/death ratio — 3.00")
    # Computed from the basics rows (bots excluded): alpha has the kills and the playtime.
    assert flat["Top Fragger"]["player"] == "alpha" and flat["Top Fragger"]["value"] == "40"
    assert flat["Playtime"]["player"] == "alpha"
    # bravo played 0 % — below the iPod gate — so alpha, the only eligible, takes it.
    assert flat["iPod"]["player"] == "alpha"
    assert [c["key"] for c in body["categories"]][0] == "computed"


@pytest.mark.asyncio
async def test_awards_with_no_engine_rows_still_answers_the_computed_three():
    status, body = await _get(_StubDB(awards=False), "/api/stats/session/154/awards")
    assert status == 200 and body["rounds_with_awards"] == 0
    assert [c["key"] for c in body["categories"]] == ["computed"]
