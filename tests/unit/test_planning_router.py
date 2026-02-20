from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware

from website.backend.dependencies import get_db
from website.backend.routers import planning as planning_router


class FakePlanningDB:
    def __init__(self):
        self.current_date = date(2026, 2, 19)
        self._clock = datetime(2026, 2, 19, 12, 0, 0)

        self.user_player_links: set[int] = set()
        self.player_links: dict[int, dict[str, Any]] = {}

        self.availability_entries: dict[tuple[int, date], dict[str, Any]] = {}

        self.planning_sessions: dict[date, dict[str, Any]] = {}
        self.planning_team_names: dict[int, dict[str, Any]] = {}
        self.planning_votes: dict[tuple[int, int], dict[str, Any]] = {}
        self.planning_teams: dict[tuple[int, str], dict[str, Any]] = {}
        self.planning_team_members: dict[tuple[int, int], dict[str, Any]] = {}

        self.next_session_id = 1
        self.next_suggestion_id = 1
        self.next_team_id = 1

    @staticmethod
    def _normalize(query: str) -> str:
        return " ".join(query.strip().lower().split())

    def _now(self) -> datetime:
        self._clock += timedelta(seconds=1)
        return self._clock

    @staticmethod
    def _as_date(value: Any) -> date:
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value)[:10])

    def seed_entry(self, user_id: int, entry_date: date, status: str, user_name: str | None = None):
        self.availability_entries[(int(user_id), entry_date)] = {
            "user_id": int(user_id),
            "entry_date": entry_date,
            "status": str(status).upper(),
            "user_name": user_name or f"user-{user_id}",
            "updated_at": self._now(),
        }
        self.player_links.setdefault(
            int(user_id),
            {
                "player_name": f"Player {user_id}",
                "discord_username": f"user{user_id}",
            },
        )

    async def fetch_val(self, query: str, params=None):
        normalized = self._normalize(query)
        if "select current_date" in normalized:
            return self.current_date
        raise AssertionError(f"Unexpected fetch_val query: {normalized}")

    async def fetch_one(self, query: str, params=None):
        normalized = self._normalize(query)

        if "select user_id from user_player_links where user_id = $1" in normalized:
            user_id = int(params[0])
            return (user_id,) if user_id in self.user_player_links else None

        if "select id from player_links where discord_id = $1 limit 1" in normalized:
            discord_id = int(params[0])
            return (1,) if discord_id in self.player_links else None

        if "select count(*) from availability_entries where entry_date = $1 and status = 'looking'" in normalized:
            target_date = self._as_date(params[0])
            looking = sum(
                1
                for row in self.availability_entries.values()
                if row["entry_date"] == target_date and row["status"] == "LOOKING"
            )
            return (looking,)

        if "select id, session_date, created_by_user_id, discord_thread_id, created_at, updated_at" in normalized and "from planning_sessions" in normalized:
            target_date = self._as_date(params[0])
            row = self.planning_sessions.get(target_date)
            if not row:
                return None
            return (
                row["id"],
                row["session_date"],
                row["created_by_user_id"],
                row["discord_thread_id"],
                row["created_at"],
                row["updated_at"],
            )

        if "insert into planning_sessions" in normalized and "returning id" in normalized:
            target_date = self._as_date(params[0])
            created_by_user_id = int(params[1])
            if target_date in self.planning_sessions:
                return None
            row = {
                "id": self.next_session_id,
                "session_date": target_date,
                "created_by_user_id": created_by_user_id,
                "discord_thread_id": None,
                "created_at": self._now(),
                "updated_at": self._now(),
            }
            self.next_session_id += 1
            self.planning_sessions[target_date] = row
            return (row["id"],)

        if "select player_name, discord_username from player_links where discord_id = $1 limit 1" in normalized:
            user_id = int(params[0])
            row = self.player_links.get(user_id)
            if not row:
                return None
            return (row.get("player_name"), row.get("discord_username"))

        if "select status from availability_entries where user_id = $1 and entry_date = $2 limit 1" in normalized:
            user_id = int(params[0])
            target_date = self._as_date(params[1])
            row = self.availability_entries.get((user_id, target_date))
            if not row:
                return None
            return (row["status"],)

        if "select id from planning_team_names where session_id = $1 and lower(name) = lower($2)" in normalized:
            session_id = int(params[0])
            name = str(params[1]).strip().lower()
            for row in self.planning_team_names.values():
                if int(row["session_id"]) == session_id and str(row["name"]).lower() == name:
                    return (int(row["id"]),)
            return None

        if "insert into planning_team_names" in normalized and "returning id" in normalized:
            session_id = int(params[0])
            suggested_by_user_id = int(params[1])
            name = str(params[2]).strip()
            row = {
                "id": self.next_suggestion_id,
                "session_id": session_id,
                "suggested_by_user_id": suggested_by_user_id,
                "name": name,
                "created_at": self._now(),
            }
            self.planning_team_names[self.next_suggestion_id] = row
            self.next_suggestion_id += 1
            return (row["id"],)

        if "select id from planning_team_names where id = $1 and session_id = $2" in normalized:
            suggestion_id = int(params[0])
            session_id = int(params[1])
            row = self.planning_team_names.get(suggestion_id)
            if row and int(row["session_id"]) == session_id:
                return (suggestion_id,)
            return None

        if "insert into planning_teams" in normalized and "returning id" in normalized:
            session_id = int(params[0])
            captain_user_id = int(params[1]) if params[1] is not None else None
            side = "A" if "values ($1, 'a', $2" in normalized else "B"
            key = (session_id, side)
            existing = self.planning_teams.get(key)
            if existing:
                existing["captain_user_id"] = captain_user_id
                existing["updated_at"] = self._now()
                return (existing["id"],)

            row = {
                "id": self.next_team_id,
                "session_id": session_id,
                "side": side,
                "captain_user_id": captain_user_id,
                "created_at": self._now(),
                "updated_at": self._now(),
            }
            self.next_team_id += 1
            self.planning_teams[key] = row
            return (row["id"],)

        if "select tier from user_permissions where discord_id = $1 limit 1" in normalized:
            return None

        raise AssertionError(f"Unexpected fetch_one query: {normalized}")

    async def fetch_all(self, query: str, params=None):
        normalized = self._normalize(query)

        if "from availability_entries ae" in normalized and "left join player_links pl on pl.discord_id = ae.user_id" in normalized:
            target_date = self._as_date(params[0])
            rows = []
            for row in self.availability_entries.values():
                if row["entry_date"] != target_date:
                    continue
                if row["status"] not in {"LOOKING", "AVAILABLE", "MAYBE"}:
                    continue
                player = self.player_links.get(int(row["user_id"]), {})
                display_name = player.get("player_name") or row.get("user_name") or player.get("discord_username")
                rows.append((row["user_id"], display_name, row["status"], row["updated_at"]))
            rows.sort(key=lambda item: item[3], reverse=True)
            return [(row[0], row[1], row[2]) for row in rows]

        if "select id, name, suggested_by_user_id, created_at from planning_team_names" in normalized:
            session_id = int(params[0])
            rows = [
                (row["id"], row["name"], row["suggested_by_user_id"], row["created_at"])
                for row in self.planning_team_names.values()
                if int(row["session_id"]) == session_id
            ]
            rows.sort(key=lambda item: (item[3], item[0]))
            return rows

        if "select suggestion_id, user_id from planning_votes where session_id = $1" in normalized:
            session_id = int(params[0])
            rows = []
            for (row_session_id, user_id), row in self.planning_votes.items():
                if row_session_id != session_id:
                    continue
                rows.append((row["suggestion_id"], user_id))
            return rows

        if "select id, side, captain_user_id from planning_teams" in normalized:
            session_id = int(params[0])
            rows = []
            for row in self.planning_teams.values():
                if int(row["session_id"]) != session_id:
                    continue
                rows.append((row["id"], row["side"], row["captain_user_id"]))
            rows.sort(key=lambda item: item[1])
            return rows

        if "select user_id from planning_team_members where team_id = $1" in normalized:
            team_id = int(params[0])
            rows = []
            for row in self.planning_team_members.values():
                if int(row["team_id"]) != team_id:
                    continue
                rows.append((row["user_id"], row["created_at"], row["id"]))
            rows.sort(key=lambda item: (item[1], item[2]))
            return [(row[0],) for row in rows]

        raise AssertionError(f"Unexpected fetch_all query: {normalized}")

    async def execute(self, query: str, params=None, *extra):
        normalized = self._normalize(query)

        if "update planning_sessions set discord_thread_id = $1" in normalized:
            thread_id = params[0]
            session_id = int(params[1])
            for row in self.planning_sessions.values():
                if int(row["id"]) == session_id:
                    row["discord_thread_id"] = thread_id
                    row["updated_at"] = self._now()
                    return
            return

        if "insert into availability_entries" in normalized and "on conflict (user_id, entry_date) do update set" in normalized:
            user_id = int(params[0])
            user_name = str(params[1] or "")
            target_date = self._as_date(params[2])
            self.availability_entries[(user_id, target_date)] = {
                "user_id": user_id,
                "entry_date": target_date,
                "status": "LOOKING",
                "user_name": user_name,
                "updated_at": self._now(),
            }
            return

        if "insert into planning_votes" in normalized and "on conflict (session_id, user_id) do update set" in normalized:
            session_id = int(params[0])
            user_id = int(params[1])
            suggestion_id = int(params[2])
            self.planning_votes[(session_id, user_id)] = {
                "session_id": session_id,
                "user_id": user_id,
                "suggestion_id": suggestion_id,
                "updated_at": self._now(),
            }
            return

        if "delete from planning_team_members where session_id = $1" in normalized:
            session_id = int(params[0])
            self.planning_team_members = {
                key: value
                for key, value in self.planning_team_members.items()
                if int(value["session_id"]) != session_id
            }
            return

        if "insert into planning_team_members" in normalized and "on conflict (session_id, user_id) do update set" in normalized:
            session_id = int(params[0])
            team_id = int(params[1])
            user_id = int(params[2])
            self.planning_team_members[(session_id, user_id)] = {
                "id": len(self.planning_team_members) + 1,
                "session_id": session_id,
                "team_id": team_id,
                "user_id": user_id,
                "created_at": self._now(),
            }
            return

        raise AssertionError(f"Unexpected execute query: {normalized}")


def _build_app(db: FakePlanningDB) -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="planning-test-secret")

    async def _db_override():
        yield db

    app.dependency_overrides[get_db] = _db_override
    app.include_router(planning_router.router, prefix="/api/planning")

    @app.post("/_test/login")
    async def _test_login(request: Request):
        payload = await request.json()
        request.session["user"] = payload
        return {"ok": True}

    return app


async def _login(
    client: httpx.AsyncClient,
    *,
    user_id: int,
    username: str,
    linked: bool,
) -> None:
    payload = {
        "id": str(user_id),
        "username": username,
        "display_name": username,
        "website_user_id": int(user_id),
    }
    if linked:
        payload["linked_player"] = f"Player {user_id}"
    response = await client.post("/_test/login", json=payload)
    assert response.status_code == 200


def _xhr_headers() -> dict[str, str]:
    return {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _disable_planning_discord_thread_creation(monkeypatch):
    monkeypatch.setenv("AVAILABILITY_PLANNING_DISCORD_CREATE_THREAD", "false")
    # Keep test env deterministic even if workstation env has Discord bot settings.
    monkeypatch.delenv("AVAILABILITY_PLANNING_THREAD_PARENT_CHANNEL_ID", raising=False)
    monkeypatch.delenv("AVAILABILITY_PLANNING_DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    yield


@pytest.mark.asyncio
async def test_get_today_planning_room_reports_locked_when_threshold_not_met():
    db = FakePlanningDB()
    db.seed_entry(10, db.current_date, "LOOKING")

    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/planning/today")

    assert response.status_code == 200
    body = response.json()
    assert body["session"] is None
    assert body["unlocked"] is False
    assert body["session_ready"]["looking_count"] == 1


@pytest.mark.asyncio
async def test_create_planning_room_requires_linked_user_and_readiness():
    db = FakePlanningDB()
    for idx in range(1, 7):
        db.seed_entry(100 + idx, db.current_date, "LOOKING")

    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, user_id=500, username="planner", linked=False)

        unlinked = await client.post("/api/planning/today/create", headers=_xhr_headers(), json={})
        assert unlinked.status_code == 403

        db.user_player_links.add(500)
        await _login(client, user_id=500, username="planner", linked=True)

        created = await client.post("/api/planning/today/create", headers=_xhr_headers(), json={})
        assert created.status_code == 200
        payload = created.json()
        assert payload["success"] is True
        assert payload["state"]["session"] is not None


@pytest.mark.asyncio
async def test_planning_room_suggest_vote_and_save_teams_flow():
    db = FakePlanningDB()
    for uid, status in [
        (600, "LOOKING"),
        (601, "LOOKING"),
        (602, "LOOKING"),
        (603, "LOOKING"),
        (604, "LOOKING"),
        (605, "LOOKING"),
    ]:
        db.seed_entry(uid, db.current_date, status)
    db.seed_entry(606, db.current_date, "AVAILABLE")

    db.user_player_links.add(600)

    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, user_id=600, username="captain", linked=True)

        create_resp = await client.post("/api/planning/today/create", headers=_xhr_headers(), json={})
        assert create_resp.status_code == 200

        first = await client.post(
            "/api/planning/today/suggestions",
            headers=_xhr_headers(),
            json={"name": "Wolves"},
        )
        assert first.status_code == 200
        first_id = int(first.json()["suggestion_id"])

        second = await client.post(
            "/api/planning/today/suggestions",
            headers=_xhr_headers(),
            json={"name": "Panthers"},
        )
        assert second.status_code == 200
        second_id = int(second.json()["suggestion_id"])

        vote_resp = await client.post(
            "/api/planning/today/vote",
            headers=_xhr_headers(),
            json={"suggestion_id": second_id},
        )
        assert vote_resp.status_code == 200

        teams_resp = await client.post(
            "/api/planning/today/teams",
            headers=_xhr_headers(),
            json={
                "side_a": [600, 601, 602],
                "side_b": [603, 604, 605],
                "captain_a": 600,
                "captain_b": 603,
            },
        )
        assert teams_resp.status_code == 200

        today_resp = await client.get("/api/planning/today")
        assert today_resp.status_code == 200
        body = today_resp.json()

        assert body["session"] is not None
        suggestions = body["session"]["suggestions"]
        assert {item["id"] for item in suggestions} == {first_id, second_id}
        top = suggestions[0]
        assert top["id"] == second_id
        assert int(top["votes"]) >= 1

        team_a = body["session"]["teams"]["A"]["members"]
        team_b = body["session"]["teams"]["B"]["members"]
        assert len(team_a) == 3
        assert len(team_b) == 3
