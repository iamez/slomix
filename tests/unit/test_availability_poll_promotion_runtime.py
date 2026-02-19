from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from bot.cogs.availability_poll_cog import AvailabilityPollCog


class _RuntimeDB:
    def __init__(self):
        self.jobs: dict[int, dict[str, Any]] = {}
        self.campaigns: dict[int, dict[str, Any]] = {}
        self.live_status: dict[str, dict[str, Any]] = {}
        self.send_logs: list[dict[str, Any]] = []

    @staticmethod
    def _normalize(query: str) -> str:
        return " ".join(query.strip().lower().split())

    async def fetch_all(self, query: str, params=None):
        normalized = self._normalize(query)

        if (
            "select id, campaign_id, job_type from availability_promotion_jobs" in normalized
            and "where status = 'pending'" in normalized
            and "run_at <= $1" in normalized
        ):
            now_utc = params[0]
            rows = []
            for job in self.jobs.values():
                if str(job.get("status")) != "pending":
                    continue
                if job.get("run_at") > now_utc:
                    continue
                rows.append((int(job["id"]), int(job["campaign_id"]), str(job["job_type"]), job.get("run_at")))
            rows.sort(key=lambda item: (item[3], item[0]))
            return [(row[0], row[1], row[2]) for row in rows]

        raise AssertionError(f"Unexpected fetch_all query: {normalized}")

    async def fetch_one(self, query: str, params=None):
        normalized = self._normalize(query)

        if (
            "update availability_promotion_jobs set status = 'running'," in normalized
            and "returning attempts, max_attempts" in normalized
        ):
            job_id = int(params[0])
            job = self.jobs.get(job_id)
            if not job or str(job.get("status")) != "pending":
                return None
            job["status"] = "running"
            job["attempts"] = int(job.get("attempts", 0)) + 1
            return (int(job["attempts"]), int(job.get("max_attempts", 5)))

        if (
            "select id, campaign_date, initiated_by_user_id, initiated_by_discord_id, dry_run, status, recipients_snapshot"
            in normalized
            and "from availability_promotion_campaigns" in normalized
            and "where id = $1" in normalized
        ):
            campaign_id = int(params[0])
            campaign = self.campaigns.get(campaign_id)
            if not campaign:
                return None
            return (
                int(campaign["id"]),
                campaign["campaign_date"],
                int(campaign["initiated_by_user_id"]),
                int(campaign["initiated_by_discord_id"]),
                bool(campaign.get("dry_run", False)),
                str(campaign.get("status", "scheduled")),
                campaign.get("recipients_snapshot", []),
            )

        if (
            "select status_data from live_status where status_type = 'voice_channel' limit 1" in normalized
        ):
            payload = self.live_status.get("voice_channel")
            if payload is None:
                return None
            return (payload,)

        if (
            "select status_data from live_status where status_type = 'game_server' limit 1" in normalized
        ):
            payload = self.live_status.get("game_server")
            if payload is None:
                return None
            return (payload,)

        raise AssertionError(f"Unexpected fetch_one query: {normalized}")

    async def execute(self, query: str, params=None, *extra):
        normalized = self._normalize(query)

        if (
            "update availability_promotion_jobs set status = $1, sent_at = current_timestamp, last_error = null" in normalized
            and "where id = $2" in normalized
        ):
            status, job_id = params
            job = self.jobs[int(job_id)]
            job["status"] = str(status)
            job["sent_at"] = datetime.now(timezone.utc)
            job["last_error"] = None
            return

        if (
            "update availability_promotion_jobs set status = 'sent'" in normalized
            and "where id = $1" in normalized
        ):
            job_id = int(params[0])
            job = self.jobs[job_id]
            job["status"] = "sent"
            job["sent_at"] = datetime.now(timezone.utc)
            job["last_error"] = None
            return

        if (
            "update availability_promotion_jobs set status = 'skipped'" in normalized
            and "where id = $1" in normalized
        ):
            job_id = int(params[0])
            job = self.jobs[job_id]
            job["status"] = "skipped"
            job["sent_at"] = datetime.now(timezone.utc)
            return

        if (
            "update availability_promotion_jobs set status = $1, last_error = $2" in normalized
            and "where id = $3" in normalized
        ):
            status, error_text, job_id = params
            job = self.jobs[int(job_id)]
            job["status"] = str(status)
            job["last_error"] = str(error_text)
            return

        if (
            "update availability_promotion_campaigns set status = $1, updated_at = current_timestamp where id = $2"
            in normalized
        ):
            status, campaign_id = params
            campaign = self.campaigns[int(campaign_id)]
            campaign["status"] = str(status)
            campaign["updated_at"] = datetime.now(timezone.utc)
            return

        if (
            "update availability_promotion_campaigns set status = 'followup_sent', updated_at = current_timestamp where id = $1"
            in normalized
        ):
            campaign_id = int(params[0])
            campaign = self.campaigns[campaign_id]
            campaign["status"] = "followup_sent"
            campaign["updated_at"] = datetime.now(timezone.utc)
            return

        if (
            "insert into availability_promotion_send_logs" in normalized
            and "values ($1, $2, $3, $4, $5, $6, $7, cast($8 as jsonb), current_timestamp)" in normalized
        ):
            (
                campaign_id,
                job_id,
                user_id,
                channel_type,
                status,
                message_id,
                error,
                payload_json,
            ) = params
            self.send_logs.append(
                {
                    "campaign_id": int(campaign_id),
                    "job_id": int(job_id),
                    "user_id": int(user_id),
                    "channel_type": str(channel_type),
                    "status": str(status),
                    "message_id": message_id,
                    "error": error,
                    "payload_json": str(payload_json),
                }
            )
            return

        raise AssertionError(f"Unexpected execute query: {normalized}")


class _FakeNotifier:
    def __init__(self):
        self.discord_announce_channel_id = 0
        self.direct_calls: list[dict[str, Any]] = []
        self.channel_calls: list[dict[str, Any]] = []

    async def send_via_channel_idempotent(
        self,
        *,
        user_id: int,
        event_key: str,
        channel_type: str,
        target: str,
        message: str,
        payload: dict[str, Any],
    ):
        self.direct_calls.append(
            {
                "user_id": int(user_id),
                "event_key": str(event_key),
                "channel_type": str(channel_type),
                "target": str(target),
                "message": str(message),
                "payload": dict(payload),
            }
        )
        return "sent", f"dm-{user_id}"

    async def send_discord_channel_idempotent(
        self,
        *,
        channel_id: int,
        event_key: str,
        message: str,
        payload: dict[str, Any],
    ):
        self.channel_calls.append(
            {
                "channel_id": int(channel_id),
                "event_key": str(event_key),
                "message": str(message),
                "payload": dict(payload),
            }
        )
        return "sent", f"ch-{channel_id}"


class _FakeBot:
    def __init__(self, db):
        self.db_adapter = db
        self.config = SimpleNamespace(
            availability_poll_enabled=False,
            availability_multichannel_enabled=False,
            availability_poll_channel_id=0,
            availability_poll_timezone="Europe/Ljubljana",
            availability_poll_threshold=6,
            availability_session_ready_threshold=6,
            availability_scheduler_lock_key=875211,
            availability_poll_reminder_times="20:45,21:00",
            availability_promotion_enabled=True,
            availability_promotion_timezone="Europe/Ljubljana",
            availability_promotion_reminder_time="20:45",
            availability_promotion_start_time="21:00",
            availability_promotion_followup_channel_id=777,
            availability_promotion_voice_check_enabled=True,
            availability_promotion_server_check_enabled=True,
            availability_promotion_job_max_attempts=5,
            availability_telegram_enabled=False,
            availability_signal_enabled=False,
            availability_discord_dm_enabled=True,
            availability_discord_channel_announce_enabled=False,
            availability_discord_announce_channel_id=0,
        )


def _build_cog(db: _RuntimeDB) -> AvailabilityPollCog:
    bot = _FakeBot(db)
    cog = AvailabilityPollCog(bot)
    cog.notifier = _FakeNotifier()
    return cog


@pytest.mark.asyncio
async def test_process_promotion_jobs_marks_start_campaign_partial_when_some_failures():
    db = _RuntimeDB()
    db.campaigns[10] = {
        "id": 10,
        "campaign_date": date(2026, 2, 19),
        "initiated_by_user_id": 555,
        "initiated_by_discord_id": 555,
        "dry_run": False,
        "status": "scheduled",
        "recipients_snapshot": [
            {"user_id": 1, "display_name": "Alpha", "selected_channel": "discord"},
            {"user_id": 2, "display_name": "Bravo", "selected_channel": "discord"},
        ],
    }
    db.jobs[101] = {
        "id": 101,
        "campaign_id": 10,
        "job_type": "send_start_2100",
        "status": "pending",
        "attempts": 0,
        "max_attempts": 5,
        "run_at": datetime(2026, 2, 19, 20, 0, tzinfo=timezone.utc),
    }

    cog = _build_cog(db)
    dispatch_calls: list[dict[str, Any]] = []

    async def _fake_dispatch(**kwargs):
        dispatch_calls.append(dict(kwargs))
        return 1, 1

    cog._dispatch_promotion_notification = _fake_dispatch  # type: ignore[method-assign]

    now_local = datetime(2026, 2, 19, 21, 5, tzinfo=ZoneInfo("Europe/Ljubljana"))
    await cog._process_promotion_jobs(now_local)

    assert db.jobs[101]["status"] == "sent"
    assert db.campaigns[10]["status"] == "partial"
    assert len(dispatch_calls) == 1
    assert dispatch_calls[0]["job_type"] == "send_start_2100"
    assert dispatch_calls[0]["campaign_id"] == 10


@pytest.mark.asyncio
async def test_process_promotion_jobs_retries_then_fails_after_max_attempts():
    db = _RuntimeDB()
    db.campaigns[20] = {
        "id": 20,
        "campaign_date": date(2026, 2, 19),
        "initiated_by_user_id": 777,
        "initiated_by_discord_id": 777,
        "dry_run": False,
        "status": "scheduled",
        "recipients_snapshot": [
            {"user_id": 9, "display_name": "Echo", "selected_channel": "discord"},
        ],
    }
    db.jobs[202] = {
        "id": 202,
        "campaign_id": 20,
        "job_type": "send_reminder_2045",
        "status": "pending",
        "attempts": 0,
        "max_attempts": 2,
        "run_at": datetime(2026, 2, 19, 19, 45, tzinfo=timezone.utc),
    }

    cog = _build_cog(db)

    async def _boom(**_kwargs):
        raise RuntimeError("dispatch failed")

    cog._dispatch_promotion_notification = _boom  # type: ignore[method-assign]

    now_local = datetime(2026, 2, 19, 21, 0, tzinfo=ZoneInfo("Europe/Ljubljana"))

    await cog._process_promotion_jobs(now_local)
    assert db.jobs[202]["attempts"] == 1
    assert db.jobs[202]["status"] == "pending"
    assert "dispatch failed" in str(db.jobs[202]["last_error"])

    await cog._process_promotion_jobs(now_local)
    assert db.jobs[202]["attempts"] == 2
    assert db.jobs[202]["status"] == "failed"
    assert "dispatch failed" in str(db.jobs[202]["last_error"])


@pytest.mark.asyncio
async def test_dispatch_voice_check_followup_targets_missing_and_posts_summary():
    db = _RuntimeDB()
    db.live_status["voice_channel"] = {
        "members": [
            {"id": 1, "name": "Alpha"},
        ]
    }
    db.live_status["game_server"] = {
        "players": [
            {"name": "Bravo"},
        ]
    }

    cog = _build_cog(db)
    recipients = [
        {"user_id": 1, "display_name": "Alpha", "selected_channel": "discord", "quiet_hours": {}},
        {"user_id": 2, "display_name": "Bravo", "selected_channel": "discord", "quiet_hours": {}},
        {
            "user_id": 3,
            "display_name": "Charlie",
            "selected_channel": "discord",
            "quiet_hours": {"start": "00:00", "end": "00:00"},
            "timezone": "Europe/Ljubljana",
        },
    ]

    await cog._dispatch_voice_check_followup(
        campaign_id=300,
        job_id=301,
        campaign_date=date(2026, 2, 19),
        recipients=recipients,
        initiated_by_discord_id=999,
    )

    notifier = cog.notifier
    assert len(notifier.direct_calls) == 1
    assert notifier.direct_calls[0]["user_id"] == 2
    assert "in server but not in voice" in notifier.direct_calls[0]["message"].lower()

    assert len(notifier.channel_calls) == 1
    summary = notifier.channel_calls[0]["message"]
    assert "We're waiting on: Bravo, Charlie." in summary
    assert "Direct follow-up sent: 1/2." in summary
    assert "In server but not in voice: Bravo." in summary

    quiet_logs = [row for row in db.send_logs if row["user_id"] == 3]
    assert quiet_logs
    assert quiet_logs[0]["status"] == "skipped"
    assert "quiet hours" in str(quiet_logs[0]["error"]).lower()
