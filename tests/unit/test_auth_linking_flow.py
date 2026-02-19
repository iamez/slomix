from __future__ import annotations

from typing import Any

import pytest
import httpx
from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware

from website.backend.dependencies import get_db
from website.backend.routers import auth as auth_router


class _FakeAuthDB:
    def __init__(self):
        self.user_player_links: dict[int, dict[str, str]] = {}
        self.player_links_by_discord: dict[int, dict[str, str]] = {}
        self.player_owner_by_guid: dict[str, int] = {}
        self.audit_rows: list[dict[str, Any]] = []

    @staticmethod
    def _normalize(query: str) -> str:
        return " ".join(query.strip().lower().split())

    async def fetch_one(self, query: str, params=None):
        normalized = self._normalize(query)

        if "select player_guid, player_name from user_player_links where user_id = $1" in normalized:
            user_id = int(params[0])
            row = self.user_player_links.get(user_id)
            if not row:
                return None
            return (row["player_guid"], row["player_name"])

        if "select user_id from user_player_links where player_guid = $1" in normalized:
            player_guid = str(params[0])
            owner = self.player_owner_by_guid.get(player_guid)
            return (int(owner),) if owner is not None else None

        if "select discord_id from player_links where player_guid = $1" in normalized:
            player_guid = str(params[0])
            for discord_id, row in self.player_links_by_discord.items():
                if str(row.get("player_guid")) == player_guid:
                    return (int(discord_id),)
            return None

        if "select id from player_links where discord_id = $1" in normalized:
            discord_id = int(params[0])
            if discord_id in self.player_links_by_discord:
                return (1,)
            return None

        if "select player_guid, player_name from player_links where discord_id = $1" in normalized:
            discord_id = int(params[0])
            row = self.player_links_by_discord.get(discord_id)
            if not row:
                return None
            return (row["player_guid"], row["player_name"])

        raise AssertionError(f"Unexpected fetch_one query: {normalized}")

    async def fetch_all(self, query: str, params=None):
        _ = query
        _ = params
        return []

    async def execute(self, query: str, params=None, *extra):
        normalized = self._normalize(query)

        if "insert into user_player_links" in normalized:
            user_id = int(params[0])
            player_guid = str(params[1])
            player_name = str(params[2])

            previous = self.user_player_links.get(user_id)
            if previous:
                old_guid = str(previous.get("player_guid"))
                self.player_owner_by_guid.pop(old_guid, None)

            self.user_player_links[user_id] = {
                "player_guid": player_guid,
                "player_name": player_name,
            }
            self.player_owner_by_guid[player_guid] = user_id
            return

        if "update player_links set player_guid = $1, player_name = $2, linked_at = now()" in normalized:
            player_guid = str(params[0])
            player_name = str(params[1])
            discord_id = int(params[2])
            self.player_links_by_discord[discord_id] = {
                "player_guid": player_guid,
                "player_name": player_name,
            }
            return

        if "insert into player_links (player_guid, discord_id, discord_username, player_name, linked_at)" in normalized:
            player_guid = str(params[0])
            discord_id = int(params[1])
            player_name = str(params[3])
            self.player_links_by_discord[discord_id] = {
                "player_guid": player_guid,
                "player_name": player_name,
            }
            return

        if "delete from user_player_links where user_id = $1" in normalized:
            user_id = int(params[0])
            previous = self.user_player_links.pop(user_id, None)
            if previous:
                self.player_owner_by_guid.pop(str(previous.get("player_guid")), None)
            return

        if "delete from player_links where discord_id = $1" in normalized:
            discord_id = int(params[0])
            self.player_links_by_discord.pop(discord_id, None)
            return

        if "insert into account_link_audit_log" in normalized:
            self.audit_rows.append({"params": params})
            return

        if "delete from discord_accounts where discord_user_id = $1" in normalized:
            return

        raise AssertionError(f"Unexpected execute query: {normalized}")


def _build_app(db: _FakeAuthDB) -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="auth-link-test-secret")

    async def _db_override():
        yield db

    app.dependency_overrides[get_db] = _db_override
    app.include_router(auth_router.router, prefix="/auth")

    @app.post("/_test/login")
    async def _test_login(request: Request):
        payload = await request.json()
        request.session["user"] = payload
        return {"ok": True}

    return app


async def _login(client: httpx.AsyncClient, user_id: int, username: str = "tester") -> None:
    response = await client.post(
        "/_test/login",
        json={
            "id": str(user_id),
            "username": username,
            "display_name": username,
            "website_user_id": int(user_id),
        },
    )
    assert response.status_code == 200


def _xhr_headers() -> dict[str, str]:
    return {"X-Requested-With": "XMLHttpRequest"}


@pytest.mark.asyncio
async def test_link_requires_csrf_header():
    db = _FakeAuthDB()
    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, user_id=101, username="alpha")

        response = await client.post(
            "/auth/link",
            json={"player_guid": "GUID-A", "player_name": "Alpha"},
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Missing required CSRF header"


@pytest.mark.asyncio
async def test_link_rejects_player_already_owned_by_another_user():
    db = _FakeAuthDB()
    db.user_player_links[222] = {"player_guid": "GUID-TAKEN", "player_name": "Taken"}
    db.player_owner_by_guid["GUID-TAKEN"] = 222

    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, user_id=101, username="alpha")

        response = await client.post(
            "/auth/link",
            json={"player_guid": "GUID-TAKEN", "player_name": "Taken"},
            headers=_xhr_headers(),
        )
        assert response.status_code == 409
        assert "already linked" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_link_status_and_unlink_flow_persists_mapping_state():
    db = _FakeAuthDB()
    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, user_id=303, username="bravo")

        link_response = await client.post(
            "/auth/link",
            json={"player_guid": "GUID-BRAVO", "player_name": "Bravo"},
            headers=_xhr_headers(),
        )
        assert link_response.status_code == 200
        assert link_response.json()["linked_player_guid"] == "GUID-BRAVO"

        status_after_link = await client.get("/auth/link/status")
        assert status_after_link.status_code == 200
        body_after_link = status_after_link.json()
        assert body_after_link["authenticated"] is True
        assert body_after_link["player_linked"] is True
        assert body_after_link["linked_player"]["guid"] == "GUID-BRAVO"
        assert body_after_link["linked_player"]["name"] == "Bravo"

        unlink_response = await client.delete("/auth/link", headers=_xhr_headers())
        assert unlink_response.status_code == 200
        assert unlink_response.json()["success"] is True

        status_after_unlink = await client.get("/auth/link/status")
        assert status_after_unlink.status_code == 200
        body_after_unlink = status_after_unlink.json()
        assert body_after_unlink["authenticated"] is True
        assert body_after_unlink["player_linked"] is False
        assert body_after_unlink["linked_player"]["guid"] is None


@pytest.mark.asyncio
async def test_link_start_redirects_to_profile_hash_without_query_params():
    db = _FakeAuthDB()
    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, user_id=404, username="charlie")

        response = await client.get("/auth/link/start", follow_redirects=False)
        assert response.status_code in (302, 307)
        location = response.headers.get("location", "")
        assert location.endswith("/#/profile")
        assert "?link=" not in location
