from datetime import date, datetime, timedelta
import json
from typing import Any

import pytest
from fastapi import FastAPI, Request

from website.backend.dependencies import get_db
from website.backend.routers import availability as availability_router

pytest.importorskip("httpx")
pytest.importorskip("itsdangerous")

from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware


class FakeAvailabilityDB:
    def __init__(self):
        self.current_date = date(2026, 2, 18)
        self.player_links: set[int] = set()
        self.availability_entries: dict[tuple[int, date], dict[str, Any]] = {}
        self.settings: dict[int, dict[str, Any]] = {}
        self.channel_links: dict[tuple[int, str], dict[str, Any]] = {}
        self.subscriptions: dict[tuple[int, str], dict[str, Any]] = {}
        self._tick = 0

    @staticmethod
    def _normalize(query: str) -> str:
        return " ".join(query.strip().lower().split())

    @staticmethod
    def _normalize_date(value: Any) -> date:
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value)[:10])

    def _now(self) -> datetime:
        self._tick += 1
        return datetime(2026, 2, 18, 12, 0, 0) + timedelta(seconds=self._tick)

    def seed_entry(self, user_id: int, entry_date: date, status: str, user_name: str = "seed") -> None:
        now = self._now()
        self.availability_entries[(int(user_id), entry_date)] = {
            "user_id": int(user_id),
            "user_name": user_name,
            "entry_date": entry_date,
            "status": status,
            "created_at": now,
            "updated_at": now,
        }

    async def fetch_val(self, query: str, params=None):
        normalized = self._normalize(query)
        if "select current_date" in normalized:
            return self.current_date
        raise AssertionError(f"Unsupported fetch_val query: {normalized}")

    async def fetch_one(self, query: str, params=None):
        normalized = self._normalize(query)

        if "select id from player_links where discord_id = $1 limit 1" in normalized:
            discord_id = int(params[0])
            return (1,) if discord_id in self.player_links else None

        if (
            "select sound_enabled, sound_cooldown_seconds, availability_reminders_enabled, timezone"
            in normalized
            and "from availability_user_settings" in normalized
        ):
            user_id = int(params[0])
            row = self.settings.get(user_id)
            if not row:
                return None
            return (
                row["sound_enabled"],
                row["sound_cooldown_seconds"],
                row["availability_reminders_enabled"],
                row["timezone"],
            )

        if (
            "select verified_at, destination from availability_channel_links"
            in normalized
            and "where user_id = $1 and channel_type = $2" in normalized
        ):
            user_id = int(params[0])
            channel_type = str(params[1])
            row = self.channel_links.get((user_id, channel_type))
            if not row:
                return None
            return (row.get("verified_at"), row.get("destination"))

        if (
            "select verified_at from availability_channel_links"
            in normalized
            and "where user_id = $1 and channel_type = $2" in normalized
        ):
            user_id = int(params[0])
            channel_type = str(params[1])
            row = self.channel_links.get((user_id, channel_type))
            if not row:
                return None
            return (row.get("verified_at"),)

        if (
            "select user_id from availability_channel_links" in normalized
            and "where channel_type = $1" in normalized
            and "verification_token_hash = $2" in normalized
        ):
            channel_type = str(params[0])
            token_hash = str(params[1])
            now = self._now()
            for (user_id, row_channel), row in self.channel_links.items():
                if row_channel != channel_type:
                    continue
                if row.get("verification_token_hash") != token_hash:
                    continue
                if row.get("verified_at") is not None:
                    continue
                token_expires_at = row.get("token_expires_at")
                if token_expires_at and token_expires_at < now:
                    continue
                return (user_id,)
            return None

        raise AssertionError(f"Unsupported fetch_one query: {normalized}")

    async def fetch_all(self, query: str, params=None):
        normalized = self._normalize(query)

        if (
            "select entry_date, status, count(*) as cnt from availability_entries" in normalized
            and "group by entry_date, status" in normalized
        ):
            from_date = self._normalize_date(params[0])
            to_date = self._normalize_date(params[1])
            counts: dict[tuple[date, str], int] = {}
            for row in self.availability_entries.values():
                entry_date = row["entry_date"]
                if entry_date < from_date or entry_date > to_date:
                    continue
                key = (entry_date, row["status"])
                counts[key] = counts.get(key, 0) + 1
            out = [(entry_date, status, cnt) for (entry_date, status), cnt in counts.items()]
            out.sort(key=lambda r: (r[0], r[1]))
            return out

        if (
            "select entry_date, status from availability_entries" in normalized
            and "where user_id = $1 and entry_date between $2 and $3" in normalized
        ):
            user_id = int(params[0])
            from_date = self._normalize_date(params[1])
            to_date = self._normalize_date(params[2])
            out = [
                (row["entry_date"], row["status"])
                for row in self.availability_entries.values()
                if int(row["user_id"]) == user_id and from_date <= row["entry_date"] <= to_date
            ]
            out.sort(key=lambda r: r[0])
            return out

        if (
            "select ae.entry_date, ae.status, ae.user_id" in normalized
            and "from availability_entries ae" in normalized
            and "left join player_links pl on pl.discord_id = ae.user_id" in normalized
        ):
            from_date = self._normalize_date(params[0])
            to_date = self._normalize_date(params[1])
            out = []
            for row in self.availability_entries.values():
                entry_date = row["entry_date"]
                if entry_date < from_date or entry_date > to_date:
                    continue
                out.append((entry_date, row["status"], row["user_id"], row["user_name"]))
            out.sort(key=lambda r: (r[0], r[1]))
            return out

        if (
            "select entry_date, status, created_at, updated_at from availability_entries" in normalized
            and "where user_id = $1 and entry_date between $2 and $3" in normalized
        ):
            user_id = int(params[0])
            from_date = self._normalize_date(params[1])
            to_date = self._normalize_date(params[2])
            out = [
                (row["entry_date"], row["status"], row["created_at"], row["updated_at"])
                for row in self.availability_entries.values()
                if int(row["user_id"]) == user_id and from_date <= row["entry_date"] <= to_date
            ]
            out.sort(key=lambda r: r[0])
            return out

        if (
            "select channel_type, enabled, channel_address, verified_at, preferences" in normalized
            and "from availability_subscriptions" in normalized
            and "where user_id = $1" in normalized
        ):
            user_id = int(params[0])
            out = []
            for (subscription_user_id, channel_type), row in self.subscriptions.items():
                if subscription_user_id != user_id:
                    continue
                out.append(
                    (
                        channel_type,
                        row["enabled"],
                        row["channel_address"],
                        row["verified_at"],
                        row.get("preferences", {}),
                    )
                )
            out.sort(key=lambda r: r[0])
            return out

        raise AssertionError(f"Unsupported fetch_all query: {normalized}")

    async def execute(self, query: str, params=None, *extra):
        normalized = self._normalize(query)

        if "insert into availability_entries" in normalized and "on conflict (user_id, entry_date) do update set" in normalized:
            user_id, user_name, raw_date, status = params
            entry_date = self._normalize_date(raw_date)
            key = (int(user_id), entry_date)
            now = self._now()
            existing = self.availability_entries.get(key)
            created_at = existing["created_at"] if existing else now
            self.availability_entries[key] = {
                "user_id": int(user_id),
                "user_name": user_name,
                "entry_date": entry_date,
                "status": status,
                "created_at": created_at,
                "updated_at": now,
            }
            return

        if "insert into availability_user_settings" in normalized and "on conflict (user_id) do update set" in normalized:
            user_id, sound_enabled, sound_cooldown_seconds, reminders_enabled, timezone = params
            self.settings[int(user_id)] = {
                "sound_enabled": bool(sound_enabled),
                "sound_cooldown_seconds": int(sound_cooldown_seconds),
                "availability_reminders_enabled": bool(reminders_enabled),
                "timezone": timezone,
                "updated_at": self._now(),
            }
            return

        if "insert into availability_subscriptions" in normalized and "on conflict (user_id, channel_type) do update set" in normalized:
            user_id = int(params[0])
            channel_type = str(params[1])
            channel_address = params[2]
            enabled = bool(params[3]) if len(params) > 3 else True
            verified_at = params[4] if len(params) > 4 else self._now()
            preferences = params[5] if len(params) > 5 else {}
            if isinstance(preferences, str):
                try:
                    preferences = json.loads(preferences)
                except json.JSONDecodeError:
                    preferences = {}
            key = (user_id, channel_type)
            existing = self.subscriptions.get(key, {})
            self.subscriptions[key] = {
                "enabled": enabled,
                "channel_address": channel_address or existing.get("channel_address"),
                "verified_at": verified_at or existing.get("verified_at"),
                "preferences": preferences if isinstance(preferences, dict) else {},
                "updated_at": self._now(),
            }
            return

        if "insert into availability_channel_links" in normalized and "on conflict (user_id, channel_type) do update set" in normalized:
            user_id, channel_type, token_hash, expires_at = params
            self.channel_links[(int(user_id), str(channel_type))] = {
                "destination": None,
                "verification_token_hash": token_hash,
                "token_expires_at": expires_at,
                "verified_at": None,
                "verification_requested_at": self._now(),
                "updated_at": self._now(),
            }
            return

        if "update availability_channel_links set destination = $1" in normalized:
            channel_address, user_id, channel_type = params
            key = (int(user_id), str(channel_type))
            row = self.channel_links.setdefault(key, {})
            row["destination"] = channel_address
            row["verified_at"] = self._now()
            row["updated_at"] = self._now()
            return

        raise AssertionError(f"Unsupported execute query: {normalized}")


def _build_app(db: FakeAvailabilityDB) -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="availability-test-secret")

    async def _db_override():
        yield db

    app.dependency_overrides[get_db] = _db_override
    app.include_router(availability_router.router, prefix="/api/availability")

    @app.post("/_test/login")
    async def _test_login(request: Request):
        payload = await request.json()
        request.session["user"] = {
            "id": str(payload["id"]),
            "username": payload.get("username", "tester"),
            "linked_player": payload.get("linked_player"),
        }
        return {"ok": True}

    return app


def _login(client: TestClient, user_id: int, username: str = "tester", *, linked: bool = False) -> None:
    payload = {"id": str(user_id), "username": username}
    if linked:
        payload["linked_player"] = "LinkedPlayer"
    response = client.post("/_test/login", json=payload)
    assert response.status_code == 200


def _day_lookup(days: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {day["date"]: day for day in days}


def test_get_availability_returns_aggregates_for_anonymous():
    db = FakeAvailabilityDB()
    db.seed_entry(1, date(2026, 2, 18), "LOOKING")
    db.seed_entry(2, date(2026, 2, 18), "AVAILABLE")
    db.seed_entry(3, date(2026, 2, 19), "NOT_PLAYING")

    client = TestClient(_build_app(db))
    response = client.get("/api/availability?from=2026-02-18&to=2026-02-19")

    assert response.status_code == 200
    body = response.json()
    days = _day_lookup(body["days"])

    assert body["statuses"] == ["LOOKING", "AVAILABLE", "MAYBE", "NOT_PLAYING"]
    assert body["viewer"]["authenticated"] is False
    assert days["2026-02-18"]["counts"]["LOOKING"] == 1
    assert days["2026-02-18"]["counts"]["AVAILABLE"] == 1
    assert days["2026-02-19"]["counts"]["NOT_PLAYING"] == 1
    assert "my_status" not in days["2026-02-18"]


def test_get_availability_includes_my_status_and_optional_users_for_logged_in():
    db = FakeAvailabilityDB()
    db.player_links.add(42)
    db.seed_entry(42, date(2026, 2, 18), "MAYBE", user_name="bob")
    db.seed_entry(99, date(2026, 2, 18), "AVAILABLE", user_name="alice")

    client = TestClient(_build_app(db))
    _login(client, user_id=42, username="bob", linked=True)

    response = client.get("/api/availability?from=2026-02-18&to=2026-02-19&include_users=true")
    assert response.status_code == 200

    body = response.json()
    days = _day_lookup(body["days"])

    assert body["viewer"]["authenticated"] is True
    assert body["viewer"]["linked_discord"] is True
    assert days["2026-02-18"]["my_status"] == "MAYBE"
    assert days["2026-02-18"]["users_by_status"]["AVAILABLE"][0]["display_name"] == "alice"


def test_post_availability_requires_authentication_and_linked_discord():
    db = FakeAvailabilityDB()
    client = TestClient(_build_app(db))

    anonymous = client.post(
        "/api/availability",
        json={"date": "2026-02-18", "status": "AVAILABLE"},
    )
    assert anonymous.status_code == 401

    _login(client, user_id=42, username="bob", linked=False)
    unlinked = client.post(
        "/api/availability",
        json={"date": "2026-02-18", "status": "AVAILABLE"},
    )
    assert unlinked.status_code == 403


def test_post_availability_rejects_invalid_dates_and_upserts():
    db = FakeAvailabilityDB()
    db.player_links.add(42)
    client = TestClient(_build_app(db))
    _login(client, user_id=42, username="bob", linked=True)

    past = client.post(
        "/api/availability",
        json={"date": "2026-02-17", "status": "AVAILABLE"},
    )
    far = client.post(
        "/api/availability",
        json={"date": "2026-06-30", "status": "AVAILABLE"},
    )
    first = client.post(
        "/api/availability",
        json={"date": "2026-02-20", "status": "LOOKING"},
    )
    second = client.post(
        "/api/availability",
        json={"date": "2026-02-20", "status": "AVAILABLE"},
    )

    assert past.status_code == 400
    assert far.status_code == 400
    assert first.status_code == 200
    assert second.status_code == 200
    assert len(db.availability_entries) == 1
    entry = next(iter(db.availability_entries.values()))
    assert entry["status"] == "AVAILABLE"


def test_get_me_requires_authentication_and_returns_entries():
    db = FakeAvailabilityDB()
    db.seed_entry(88, date(2026, 2, 18), "LOOKING", user_name="echo")

    client = TestClient(_build_app(db))
    unauth = client.get("/api/availability/me?from=2026-02-18&to=2026-02-20")
    assert unauth.status_code == 401

    _login(client, user_id=88, username="echo", linked=True)
    auth = client.get("/api/availability/me?from=2026-02-18&to=2026-02-20")
    assert auth.status_code == 200
    assert auth.json()["entries"][0]["status"] == "LOOKING"


def test_settings_defaults_updates_and_preferences_alias():
    db = FakeAvailabilityDB()
    db.player_links.add(55)
    client = TestClient(_build_app(db))
    _login(client, user_id=55, username="delta", linked=True)

    defaults = client.get("/api/availability/settings")
    assert defaults.status_code == 200
    assert defaults.json()["sound_enabled"] is True
    assert defaults.json()["sound_cooldown_seconds"] == 480

    blocked = client.post(
        "/api/availability/preferences",
        json={"telegram_notify": True},
    )
    assert blocked.status_code == 403

    unchanged = client.get("/api/availability/settings")
    assert unchanged.status_code == 200
    assert unchanged.json()["sound_enabled"] is True
    assert unchanged.json()["sound_cooldown_seconds"] == 480

    updated = client.post(
        "/api/availability/preferences",
        json={
            "sound_enabled": False,
            "availability_reminders_enabled": False,
            "sound_cooldown_seconds": 300,
            "timezone": "Europe/Ljubljana",
            "discord_notify": True,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["sound_enabled"] is False
    assert updated.json()["availability_reminders_enabled"] is False
    assert updated.json()["sound_cooldown_seconds"] == 300


def test_subscriptions_require_verified_telegram_and_signal_links():
    db = FakeAvailabilityDB()
    db.player_links.add(42)
    client = TestClient(_build_app(db))
    _login(client, user_id=42, username="bob", linked=True)

    telegram_fail = client.post(
        "/api/availability/subscriptions",
        json={"channel_type": "telegram", "enabled": True, "channel_address": "@bob"},
    )
    assert telegram_fail.status_code == 403

    db.channel_links[(42, "telegram")] = {
        "verified_at": datetime(2026, 2, 18, 12, 30, 0),
        "destination": "@bob",
    }
    telegram_ok = client.post(
        "/api/availability/subscriptions",
        json={"channel_type": "telegram", "enabled": True, "channel_address": "@bob"},
    )
    assert telegram_ok.status_code == 200

    rows = client.get("/api/availability/subscriptions")
    assert rows.status_code == 200
    by_channel = {row["channel_type"]: row for row in rows.json()["subscriptions"]}
    assert by_channel["telegram"]["enabled"] is True
    assert by_channel["telegram"]["verified"] is True


def test_link_token_create_and_confirm_flow_activates_subscription():
    db = FakeAvailabilityDB()
    db.player_links.add(101)
    client = TestClient(_build_app(db))
    _login(client, user_id=101, username="foxtrot", linked=True)

    token_resp = client.post(
        "/api/availability/link-token",
        json={"channel_type": "telegram", "ttl_minutes": 30},
    )
    assert token_resp.status_code == 200

    token = token_resp.json()["token"]
    confirm = client.post(
        "/api/availability/link-confirm",
        json={
            "channel_type": "telegram",
            "token": token,
            "channel_address": "123456789",
        },
    )
    assert confirm.status_code == 200

    subs = client.get("/api/availability/subscriptions")
    by_channel = {row["channel_type"]: row for row in subs.json()["subscriptions"]}
    assert by_channel["telegram"]["enabled"] is True
    assert by_channel["telegram"]["channel_address"] == "123456789"
