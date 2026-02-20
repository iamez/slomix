from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from typing import Any

import httpx
import pytest
from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware

from website.backend.dependencies import get_db
from website.backend.routers import availability as availability_router


class FakePromotionDB:
    def __init__(self):
        self.current_date = date(2026, 2, 19)
        self.user_player_links: set[int] = set()
        self.player_links: dict[int, dict[str, str | None]] = {}
        self.preferences: dict[int, dict[str, Any]] = {}
        self.availability_entries: list[dict[str, Any]] = []
        self.campaigns: list[dict[str, Any]] = []
        self.jobs: list[dict[str, Any]] = []
        self._campaign_id_seq = 0
        self._job_id_seq = 0
        self._tick = 0

    @staticmethod
    def _normalize(query: str) -> str:
        return " ".join(query.strip().lower().split())

    @staticmethod
    def _normalize_date(value: Any) -> date:
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value)[:10])

    def _next_timestamp(self) -> datetime:
        self._tick += 1
        return datetime(2026, 2, 19, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=self._tick)

    def seed_availability(self, *, user_id: int, user_name: str, entry_date: date, status: str) -> None:
        self.availability_entries.append(
            {
                "user_id": int(user_id),
                "user_name": str(user_name),
                "entry_date": self._normalize_date(entry_date),
                "status": str(status).upper(),
                "updated_at": self._next_timestamp(),
            }
        )

    def seed_preference(
        self,
        *,
        user_id: int,
        allow_promotions: bool,
        preferred_channel: str = "any",
        telegram_handle_encrypted: str | None = None,
        signal_handle_encrypted: str | None = None,
        quiet_hours: dict[str, str] | None = None,
        pref_timezone: str = "Europe/Ljubljana",
        notify_threshold: int = 0,
    ) -> None:
        self.preferences[int(user_id)] = {
            "allow_promotions": bool(allow_promotions),
            "preferred_channel": str(preferred_channel),
            "telegram_handle_encrypted": telegram_handle_encrypted,
            "signal_handle_encrypted": signal_handle_encrypted,
            "quiet_hours": quiet_hours or {},
            "timezone": pref_timezone,
            "notify_threshold": int(notify_threshold),
        }

    async def fetch_val(self, query: str, params=None):
        normalized = self._normalize(query)
        if "select current_date" in normalized:
            return self.current_date
        raise AssertionError(f"Unsupported fetch_val query: {normalized}")

    async def fetch_one(self, query: str, params=None):
        normalized = self._normalize(query)

        if "select user_id from user_player_links where user_id = $1 limit 1" in normalized:
            user_id = int(params[0])
            return (user_id,) if user_id in self.user_player_links else None

        if "select id from player_links where discord_id = $1 limit 1" in normalized:
            discord_id = int(params[0])
            return (1,) if discord_id in self.player_links else None

        if "select tier from user_permissions where discord_id = $1 limit 1" in normalized:
            return None

        if (
            "select allow_promotions," in normalized
            and "from subscription_preferences" in normalized
            and "where user_id = $1" in normalized
        ):
            user_id = int(params[0])
            pref = self.preferences.get(user_id)
            if not pref:
                return None
            return (
                bool(pref.get("allow_promotions", False)),
                str(pref.get("preferred_channel", "any")),
                pref.get("telegram_handle_encrypted"),
                pref.get("signal_handle_encrypted"),
                pref.get("quiet_hours") or {},
                str(pref.get("timezone", "Europe/Ljubljana")),
                int(pref.get("notify_threshold", 0)),
            )

        if "select player_name, discord_username from player_links where discord_id = $1 limit 1" in normalized:
            discord_id = int(params[0])
            row = self.player_links.get(discord_id)
            if not row:
                return None
            return (row.get("player_name"), row.get("discord_username"))

        if (
            "select id from availability_promotion_campaigns" in normalized
            and "where campaign_date = $1" in normalized
            and "and initiated_by_user_id = $2" in normalized
        ):
            campaign_date = self._normalize_date(params[0])
            user_id = int(params[1])
            for campaign in self.campaigns:
                if campaign["campaign_date"] == campaign_date and campaign["initiated_by_user_id"] == user_id:
                    return (campaign["id"],)
            return None

        if (
            "select id from availability_promotion_campaigns" in normalized
            and "where campaign_date = $1" in normalized
            and "and initiated_by_user_id = $2" not in normalized
        ):
            campaign_date = self._normalize_date(params[0])
            for campaign in self.campaigns:
                if campaign["campaign_date"] == campaign_date:
                    return (campaign["id"],)
            return None

        if "insert into availability_promotion_campaigns" in normalized and "returning id" in normalized:
            (
                campaign_date,
                target_timezone,
                target_start_time,
                initiated_by_user_id,
                initiated_by_discord_id,
                include_maybe,
                include_available,
                dry_run,
                idempotency_key,
                recipient_count,
                channels_summary_json,
                recipients_json,
            ) = params
            self._campaign_id_seq += 1
            campaign = {
                "id": self._campaign_id_seq,
                "campaign_date": self._normalize_date(campaign_date),
                "target_timezone": str(target_timezone),
                "target_start_time": str(target_start_time),
                "initiated_by_user_id": int(initiated_by_user_id),
                "initiated_by_discord_id": int(initiated_by_discord_id),
                "include_maybe": bool(include_maybe),
                "include_available": bool(include_available),
                "dry_run": bool(dry_run),
                "status": "scheduled",
                "idempotency_key": str(idempotency_key),
                "recipient_count": int(recipient_count),
                "channels_summary": json.loads(channels_summary_json),
                "recipients_snapshot": json.loads(recipients_json),
                "created_at": self._next_timestamp(),
                "updated_at": self._next_timestamp(),
            }
            self.campaigns.append(campaign)
            return (campaign["id"],)

        raise AssertionError(f"Unsupported fetch_one query: {normalized}")

    async def fetch_all(self, query: str, params=None):
        normalized = self._normalize(query)

        if (
            "select user_id, user_name, status from availability_entries" in normalized
            and "where entry_date = $1" in normalized
        ):
            target_date = self._normalize_date(params[0])
            rows = [
                (row["user_id"], row["user_name"], row["status"], row["updated_at"])
                for row in self.availability_entries
                if row["entry_date"] == target_date
                and row["status"] in {"LOOKING", "AVAILABLE", "MAYBE"}
            ]
            rows.sort(key=lambda value: value[3], reverse=True)
            return [(user_id, user_name, status) for (user_id, user_name, status, _updated_at) in rows]

        if (
            "select id, job_type, run_at, status, attempts, max_attempts, last_error, sent_at" in normalized
            and "from availability_promotion_jobs" in normalized
            and "where campaign_id = $1" in normalized
        ):
            campaign_id = int(params[0])
            rows = [
                (
                    int(job["id"]),
                    str(job["job_type"]),
                    job["run_at"],
                    str(job["status"]),
                    int(job["attempts"]),
                    int(job["max_attempts"]),
                    job["last_error"],
                    job["sent_at"],
                )
                for job in self.jobs
                if int(job["campaign_id"]) == campaign_id
            ]
            rows.sort(key=lambda value: (value[2], value[0]))
            return rows

        raise AssertionError(f"Unsupported fetch_all query: {normalized}")

    async def execute(self, query: str, params=None, *extra):
        normalized = self._normalize(query)

        if "insert into availability_promotion_jobs" in normalized:
            campaign_id, job_type, run_at, payload_json = params
            for existing in self.jobs:
                if int(existing["campaign_id"]) == int(campaign_id) and str(existing["job_type"]) == str(job_type):
                    return
            self._job_id_seq += 1
            self.jobs.append(
                {
                    "id": self._job_id_seq,
                    "campaign_id": int(campaign_id),
                    "job_type": str(job_type),
                    "run_at": run_at,
                    "status": "pending",
                    "attempts": 0,
                    "max_attempts": 5,
                    "last_error": None,
                    "payload": json.loads(payload_json),
                    "sent_at": None,
                    "created_at": self._next_timestamp(),
                    "updated_at": self._next_timestamp(),
                }
            )
            return

        if "insert into subscription_preferences" in normalized and "on conflict (user_id) do update set" in normalized:
            (
                user_id,
                allow_promotions,
                preferred_channel,
                telegram_handle_encrypted,
                signal_handle_encrypted,
                quiet_hours_json,
                pref_timezone,
                notify_threshold,
            ) = params
            quiet_hours = json.loads(quiet_hours_json)
            self.preferences[int(user_id)] = {
                "allow_promotions": bool(allow_promotions),
                "preferred_channel": str(preferred_channel),
                "telegram_handle_encrypted": telegram_handle_encrypted,
                "signal_handle_encrypted": signal_handle_encrypted,
                "quiet_hours": quiet_hours if isinstance(quiet_hours, dict) else {},
                "timezone": str(pref_timezone),
                "notify_threshold": int(notify_threshold),
            }
            return

        raise AssertionError(f"Unsupported execute query: {normalized}")


def _build_app(db: FakePromotionDB) -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="availability-promotions-test-secret")

    async def _db_override():
        yield db

    app.dependency_overrides[get_db] = _db_override
    app.include_router(availability_router.router, prefix="/api/availability")

    @app.post("/_test/login")
    async def _test_login(request: Request):
        payload = await request.json()
        request.session["user"] = payload
        return {"ok": True}

    return app


async def _login(client: httpx.AsyncClient, *, user_id: int, linked: bool) -> None:
    payload: dict[str, Any] = {
        "id": str(user_id),
        "username": f"user-{user_id}",
        "display_name": f"User {user_id}",
        "website_user_id": int(user_id),
    }
    if linked:
        payload["linked_player"] = f"Player {user_id}"
        payload["linked_player_guid"] = f"GUID-{user_id}"
    response = await client.post("/_test/login", json=payload)
    assert response.status_code == 200


def _xhr_headers() -> dict[str, str]:
    return {"X-Requested-With": "XMLHttpRequest"}


@pytest.mark.asyncio
async def test_promotions_preview_requires_auth_link_and_promoter(monkeypatch):
    db = FakePromotionDB()
    transport = httpx.ASGITransport(app=_build_app(db))

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        anonymous = await client.get("/api/availability/promotions/preview")
        assert anonymous.status_code == 401

        monkeypatch.setenv("PROMOTER_DISCORD_IDS", "42")
        await _login(client, user_id=42, linked=False)
        unlinked = await client.get("/api/availability/promotions/preview")
        assert unlinked.status_code == 403
        assert "linked discord account required" in unlinked.json()["detail"].lower()

        monkeypatch.delenv("PROMOTER_DISCORD_IDS", raising=False)
        await _login(client, user_id=42, linked=True)
        not_promoter = await client.get("/api/availability/promotions/preview")
        assert not_promoter.status_code == 403
        assert "promoter permission required" in not_promoter.json()["detail"].lower()


@pytest.mark.asyncio
async def test_promotions_preview_filters_recipients_by_status_and_opt_in(monkeypatch):
    db = FakePromotionDB()
    db.current_date = date(2026, 2, 19)
    db.seed_availability(user_id=11, user_name="Alpha", entry_date=db.current_date, status="LOOKING")
    db.seed_availability(user_id=12, user_name="Bravo", entry_date=db.current_date, status="AVAILABLE")
    db.seed_availability(user_id=13, user_name="Charlie", entry_date=db.current_date, status="MAYBE")
    db.seed_availability(user_id=14, user_name="Delta", entry_date=db.current_date, status="LOOKING")

    db.seed_preference(user_id=11, allow_promotions=True, preferred_channel="any")
    db.seed_preference(user_id=12, allow_promotions=True, preferred_channel="any")
    db.seed_preference(user_id=13, allow_promotions=False, preferred_channel="any")
    db.seed_preference(user_id=14, allow_promotions=False, preferred_channel="any")

    db.player_links[11] = {"player_name": "Alpha", "discord_username": "alpha"}
    db.player_links[12] = {"player_name": "Bravo", "discord_username": "bravo"}
    db.player_links[13] = {"player_name": "Charlie", "discord_username": "charlie"}
    db.player_links[14] = {"player_name": "Delta", "discord_username": "delta"}

    monkeypatch.setenv("PROMOTER_DISCORD_IDS", "99")

    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, user_id=99, linked=True)

        default_preview = await client.get("/api/availability/promotions/preview")
        assert default_preview.status_code == 200
        body = default_preview.json()
        assert body["recipient_count"] == 1
        assert body["channels_summary"]["discord"] == 1
        assert [row["status"] for row in body["recipients_preview"]] == ["LOOKING"]

        expanded_preview = await client.get(
            "/api/availability/promotions/preview?include_available=true&include_maybe=true"
        )
        assert expanded_preview.status_code == 200
        expanded = expanded_preview.json()
        assert expanded["recipient_count"] == 2
        statuses = sorted(row["status"] for row in expanded["recipients_preview"])
        assert statuses == ["AVAILABLE", "LOOKING"]


@pytest.mark.asyncio
async def test_create_campaign_schedules_jobs_and_blocks_second_campaign_same_day(monkeypatch):
    db = FakePromotionDB()
    db.current_date = date(2026, 2, 19)
    db.seed_availability(user_id=22, user_name="Echo", entry_date=db.current_date, status="LOOKING")
    db.seed_preference(user_id=22, allow_promotions=True, preferred_channel="any")
    db.player_links[22] = {"player_name": "Echo", "discord_username": "echo"}

    monkeypatch.setenv("PROMOTER_DISCORD_IDS", "77")
    transport = httpx.ASGITransport(app=_build_app(db))

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, user_id=77, linked=True)

        first = await client.post(
            "/api/availability/promotions/campaigns",
            json={"include_available": False, "include_maybe": False, "dry_run": False},
            headers=_xhr_headers(),
        )
        assert first.status_code == 200
        body = first.json()
        assert body["success"] is True
        assert body["status"] == "scheduled"
        assert body["recipient_count"] == 1
        assert body["campaign_id"] == 1

        assert len(db.campaigns) == 1
        assert len(db.jobs) == 3
        job_types = sorted(job["job_type"] for job in db.jobs)
        assert job_types == ["send_reminder_2045", "send_start_2100", "voice_check_2100"]
        assert all(isinstance(job["run_at"], datetime) for job in db.jobs)

        second = await client.post(
            "/api/availability/promotions/campaigns",
            json={"include_available": False, "include_maybe": False, "dry_run": False},
            headers=_xhr_headers(),
        )
        assert second.status_code == 409
        detail = second.json()["detail"].lower()
        assert "campaign" in detail
        assert "already" in detail


@pytest.mark.asyncio
async def test_promotion_preferences_validate_opt_in_and_quiet_hours():
    db = FakePromotionDB()
    transport = httpx.ASGITransport(app=_build_app(db))

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, user_id=501, linked=True)

        blocked = await client.post(
            "/api/availability/promotion-preferences",
            json={
                "allow_promotions": False,
                "preferred_channel": "any",
                "telegram_handle": "@tester",
            },
            headers=_xhr_headers(),
        )
        assert blocked.status_code == 400
        assert "allow_promotions must be true" in blocked.json()["detail"]

        invalid_quiet = await client.post(
            "/api/availability/promotion-preferences",
            json={
                "allow_promotions": True,
                "preferred_channel": "any",
                "quiet_hours": {"start": "25:00", "end": "07:00"},
            },
            headers=_xhr_headers(),
        )
        assert invalid_quiet.status_code == 400
        assert "hh:mm" in invalid_quiet.json()["detail"].lower()

        valid = await client.post(
            "/api/availability/promotion-preferences",
            json={
                "allow_promotions": True,
                "preferred_channel": "any",
                "timezone": "Europe/Ljubljana",
                "quiet_hours": {"start": "23:00", "end": "07:00"},
            },
            headers=_xhr_headers(),
        )
        assert valid.status_code == 200
        body = valid.json()
        assert body["allow_promotions"] is True
        assert body["preferred_channel"] == "any"
        assert body["quiet_hours"] == {"start": "23:00", "end": "07:00"}


@pytest.mark.asyncio
async def test_access_reports_can_promote_for_linked_promoter(monkeypatch):
    db = FakePromotionDB()
    monkeypatch.setenv("PROMOTER_DISCORD_IDS", "606")

    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, user_id=606, linked=True)

        response = await client.get("/api/availability/access")
        assert response.status_code == 200
        body = response.json()
        assert body["authenticated"] is True
        assert body["linked_discord"] is True
        assert body["can_submit"] is True
        assert body["can_promote"] is True
