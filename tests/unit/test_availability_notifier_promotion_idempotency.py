from __future__ import annotations

from types import SimpleNamespace

import pytest

from bot.services.availability_notifier_service import UnifiedAvailabilityNotifier


class _FakeMessage:
    def __init__(self, message_id: int):
        self.id = int(message_id)


class _FakeUser:
    def __init__(self, user_id: int):
        self.user_id = int(user_id)
        self.sent_count = 0

    async def send(self, _message: str):
        self.sent_count += 1
        return _FakeMessage((self.user_id * 1000) + self.sent_count)


class _FakeChannel:
    def __init__(self, channel_id: int):
        self.channel_id = int(channel_id)
        self.sent_count = 0

    async def send(self, _message: str):
        self.sent_count += 1
        return _FakeMessage((self.channel_id * 1000) + self.sent_count)


class _FakeBot:
    def __init__(self):
        self.users: dict[int, _FakeUser] = {}
        self.channels: dict[int, _FakeChannel] = {}

    def get_user(self, user_id: int):
        return self.users.get(int(user_id))

    async def fetch_user(self, user_id: int):
        user = self.users.get(int(user_id))
        if user is None:
            user = _FakeUser(int(user_id))
            self.users[int(user_id)] = user
        return user

    def get_channel(self, channel_id: int):
        return self.channels.get(int(channel_id))

    async def fetch_channel(self, channel_id: int):
        channel = self.channels.get(int(channel_id))
        if channel is None:
            channel = _FakeChannel(int(channel_id))
            self.channels[int(channel_id)] = channel
        return channel


class _FakeDB:
    def __init__(self):
        self._next_id = 1
        self._by_key: dict[tuple[int, str, str], dict] = {}
        self._id_to_key: dict[int, tuple[int, str, str]] = {}

    @staticmethod
    def _normalize(query: str) -> str:
        return " ".join(query.strip().lower().split())

    async def fetch_one(self, query: str, params=None):
        normalized = self._normalize(query)

        if "select id, message_id, retries from notifications_ledger" in normalized:
            key = (int(params[0]), str(params[1]), str(params[2]))
            row = self._by_key.get(key)
            if not row:
                return None
            return (row["id"], row.get("message_id"), row.get("retries", 0))

        if "select message_id from notifications_ledger" in normalized:
            if "channel_type = 'discord'" in normalized:
                key = (int(params[0]), str(params[1]), "discord")
            else:
                key = (int(params[0]), str(params[1]), str(params[2]))
            row = self._by_key.get(key)
            if not row:
                return None
            return (row.get("message_id"),)

        raise AssertionError(f"Unexpected fetch_one query: {normalized}")

    async def execute(self, query: str, params=None, *extra):
        normalized = self._normalize(query)

        if normalized.startswith("create table if not exists") or normalized.startswith(
            "create index if not exists"
        ):
            return

        if (
            "insert into notifications_ledger" in normalized
            and "current_timestamp, $4, null, 0" in normalized
        ):
            user_id, event_key, channel_type, message_id, _payload = params
            key = (int(user_id), str(event_key), str(channel_type))
            if key not in self._by_key:
                row = {
                    "id": self._next_id,
                    "message_id": str(message_id),
                    "retries": 0,
                    "error": None,
                }
                self._next_id += 1
                self._by_key[key] = row
                self._id_to_key[int(row["id"])] = key
            return

        if (
            "insert into notifications_ledger" in normalized
            and "null, null, $4, 1" in normalized
        ):
            user_id, event_key, channel_type, error_text, _payload = params
            key = (int(user_id), str(event_key), str(channel_type))
            if key not in self._by_key:
                row = {
                    "id": self._next_id,
                    "message_id": None,
                    "retries": 1,
                    "error": str(error_text),
                }
                self._next_id += 1
                self._by_key[key] = row
                self._id_to_key[int(row["id"])] = key
            return

        if "update notifications_ledger set sent_at = current_timestamp" in normalized:
            message_id, row_id = params
            key = self._id_to_key.get(int(row_id))
            if key is None:
                raise AssertionError("Unknown ledger row id")
            row = self._by_key[key]
            row["message_id"] = str(message_id)
            row["error"] = None
            return

        if "update notifications_ledger set error = $1" in normalized:
            error_text, row_id = params
            key = self._id_to_key.get(int(row_id))
            if key is None:
                raise AssertionError("Unknown ledger row id")
            row = self._by_key[key]
            row["error"] = str(error_text)
            row["retries"] = int(row.get("retries", 0)) + 1
            return

        raise AssertionError(f"Unexpected execute query: {normalized}")


@pytest.mark.asyncio
async def test_send_via_channel_idempotent_skips_duplicate_dm_delivery():
    db = _FakeDB()
    bot = _FakeBot()
    notifier = UnifiedAvailabilityNotifier(bot=bot, db_adapter=db, config=SimpleNamespace())

    status1, message_id1 = await notifier.send_via_channel_idempotent(
        user_id=42,
        event_key="PROMOTE:T0:2026-02-19",
        channel_type="discord",
        target="42",
        message="Session starts now.",
        payload={"job_type": "send_start_2100"},
    )
    status2, message_id2 = await notifier.send_via_channel_idempotent(
        user_id=42,
        event_key="PROMOTE:T0:2026-02-19",
        channel_type="discord",
        target="42",
        message="Session starts now.",
        payload={"job_type": "send_start_2100"},
    )

    assert status1 == "sent"
    assert status2 == "skipped"
    assert message_id1
    assert message_id2 == message_id1
    assert bot.users[42].sent_count == 1


@pytest.mark.asyncio
async def test_send_discord_channel_idempotent_skips_duplicate_channel_post():
    db = _FakeDB()
    bot = _FakeBot()
    notifier = UnifiedAvailabilityNotifier(bot=bot, db_adapter=db, config=SimpleNamespace())

    status1, message_id1 = await notifier.send_discord_channel_idempotent(
        channel_id=77,
        event_key="PROMOTE:FOLLOWUP:2026-02-19",
        message="We're waiting on players.",
        payload={"job_type": "voice_check_2100"},
    )
    status2, message_id2 = await notifier.send_discord_channel_idempotent(
        channel_id=77,
        event_key="PROMOTE:FOLLOWUP:2026-02-19",
        message="We're waiting on players.",
        payload={"job_type": "voice_check_2100"},
    )

    assert status1 == "sent"
    assert status2 == "skipped"
    assert message_id1
    assert message_id2 == message_id1
    assert bot.channels[77].sent_count == 1
