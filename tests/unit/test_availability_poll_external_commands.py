from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from bot.cogs.availability_poll_cog import AvailabilityPollCog


class _FakeDB:
    def __init__(self):
        self.channel_links: dict[tuple[str, str], int] = {}
        self.player_links: dict[int, dict[str, str]] = {}
        self.availability_entries: dict[tuple[int, date], dict[str, Any]] = {}

    @staticmethod
    def _normalize(query: str) -> str:
        return " ".join(query.strip().lower().split())

    @staticmethod
    def _coerce_date(value: Any) -> date:
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value)[:10])

    async def execute(self, query: str, params=None, *extra):
        normalized = self._normalize(query)

        if normalized.startswith("create table if not exists") or normalized.startswith("create index if not exists"):
            return

        if "insert into availability_entries" in normalized and "on conflict (user_id, entry_date) do update set" in normalized:
            user_id = int(params[0])
            user_name = str(params[1] or "")
            entry_date = self._coerce_date(params[2])
            status = str(params[3] or "")
            self.availability_entries[(user_id, entry_date)] = {
                "user_id": user_id,
                "user_name": user_name,
                "entry_date": entry_date,
                "status": status,
            }
            return

        if "delete from availability_entries" in normalized:
            user_id = int(params[0])
            entry_date = self._coerce_date(params[1])
            self.availability_entries.pop((user_id, entry_date), None)
            return

        if normalized.startswith("update availability_subscriptions"):
            return

        raise AssertionError(f"Unexpected execute query: {normalized}")

    async def fetch_one(self, query: str, params=None):
        normalized = self._normalize(query)

        if "select user_id from availability_channel_links" in normalized:
            channel_type = str(params[0]).strip().lower()
            destination = str(params[1]).strip()
            user_id = self.channel_links.get((channel_type, destination))
            return (user_id,) if user_id is not None else None

        if "select 1 from player_links where discord_id = $1 limit 1" in normalized:
            discord_id = int(params[0])
            return (1,) if discord_id in self.player_links else None

        if "select player_name, discord_username from player_links where discord_id = $1 limit 1" in normalized:
            discord_id = int(params[0])
            row = self.player_links.get(discord_id)
            if not row:
                return None
            return (row.get("player_name"), row.get("discord_username"))

        if "select id from availability_entries" in normalized and "where user_id = $1" in normalized:
            user_id = int(params[0])
            entry_date = self._coerce_date(params[1])
            return (1,) if (user_id, entry_date) in self.availability_entries else None

        raise AssertionError(f"Unexpected fetch_one query: {normalized}")

    async def fetch_all(self, query: str, params=None):
        normalized = self._normalize(query)

        if "select entry_date, status from availability_entries" in normalized:
            user_id = int(params[0])
            from_date = self._coerce_date(params[1])
            to_date = self._coerce_date(params[2])
            rows = []
            for (entry_user_id, entry_date), row in self.availability_entries.items():
                if entry_user_id != user_id:
                    continue
                if entry_date < from_date or entry_date > to_date:
                    continue
                rows.append((entry_date, row["status"]))
            rows.sort(key=lambda item: item[0])
            return rows

        if normalized.startswith("update availability_subscriptions"):
            return []

        raise AssertionError(f"Unexpected fetch_all query: {normalized}")


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
            availability_promotion_enabled=False,
            availability_telegram_enabled=False,
            availability_signal_enabled=False,
            availability_discord_dm_enabled=False,
            availability_discord_channel_announce_enabled=False,
            availability_discord_announce_channel_id=0,
        )


def _build_cog(db: _FakeDB) -> AvailabilityPollCog:
    bot = _FakeBot(db)
    return AvailabilityPollCog(bot)


def test_parse_availability_operation_supports_set_and_remove_forms():
    now_date = date(2026, 2, 19)

    target, operation, status = AvailabilityPollCog._parse_availability_operation(["today", "looking"], now_date)
    assert target == now_date
    assert operation == "SET"
    assert status == "LOOKING"

    target, operation, status = AvailabilityPollCog._parse_availability_operation(["2026-02-20", "not", "playing"], now_date)
    assert target == date(2026, 2, 20)
    assert operation == "SET"
    assert status == "NOT_PLAYING"

    target, operation, status = AvailabilityPollCog._parse_availability_operation(["remove", "tomorrow"], now_date)
    assert target == now_date + timedelta(days=1)
    assert operation == "REMOVE"
    assert status is None


@pytest.mark.asyncio
async def test_apply_external_availability_command_set_status_and_remove():
    db = _FakeDB()
    db.channel_links[("telegram", "12345")] = 42
    db.player_links[42] = {"player_name": "Alpha", "discord_username": "alpha42"}

    cog = _build_cog(db)
    now_date = datetime.now(cog.timezone).date()

    set_reply = await cog._apply_external_availability_command(
        channel_type="telegram",
        channel_address="12345",
        command_text="/avail today looking",
    )
    assert "Availability set" in set_reply
    assert (42, now_date) in db.availability_entries
    assert db.availability_entries[(42, now_date)]["status"] == "LOOKING"

    status_reply = await cog._apply_external_availability_command(
        channel_type="telegram",
        channel_address="12345",
        command_text="/avail status",
    )
    assert "Today" in status_reply
    assert "LOOKING" in status_reply

    remove_reply = await cog._apply_external_availability_command(
        channel_type="telegram",
        channel_address="12345",
        command_text="/avail today remove",
    )
    assert "cleared" in remove_reply.lower()
    assert (42, now_date) not in db.availability_entries

    remove_again = await cog._apply_external_availability_command(
        channel_type="telegram",
        channel_address="12345",
        command_text="/avail today remove",
    )
    assert "no availability entry existed" in remove_again.lower()


@pytest.mark.asyncio
async def test_apply_external_availability_command_requires_linked_channel():
    db = _FakeDB()
    cog = _build_cog(db)

    reply = await cog._apply_external_availability_command(
        channel_type="telegram",
        channel_address="unknown",
        command_text="/avail today available",
    )
    assert "not linked" in reply.lower()
