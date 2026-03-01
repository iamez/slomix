"""Unified availability notifier with idempotent multi-channel delivery."""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, Optional

import discord

from bot.services.signal_connector import SignalConnector
from bot.services.telegram_connector import TelegramConnector

logger = logging.getLogger("bot.services.availability_notifier")

EVENT_DAILY_REMINDER = "DAILY_REMINDER"
EVENT_SESSION_READY = "SESSION_READY"
EVENT_FRIENDS_LOOKING = "FRIENDS_LOOKING"


@dataclass
class DeliveryResult:
    sent: int = 0
    skipped: int = 0
    failed: int = 0


class UnifiedAvailabilityNotifier:
    """Shared notifier for Discord/Telegram/Signal with ledger idempotency."""

    def __init__(self, bot, db_adapter, config):
        self.bot = bot
        self.db_adapter = db_adapter
        self.config = config

        self.max_attempts = max(
            1, int(getattr(config, "availability_notification_max_attempts", 5))
        )

        self.discord_dm_enabled = bool(
            getattr(config, "availability_discord_dm_enabled", True)
        )
        self.discord_channel_announce_enabled = bool(
            getattr(config, "availability_discord_channel_announce_enabled", False)
        )
        self.discord_announce_channel_id = int(
            getattr(config, "availability_discord_announce_channel_id", 0)
        )

        self.telegram_connector = TelegramConnector(
            enabled=bool(getattr(config, "availability_telegram_enabled", False)),
            bot_token=str(
                getattr(
                    config,
                    "availability_telegram_bot_token",
                    getattr(config, "telegram_bot_token", ""),
                )
            ),
            api_base_url=str(
                getattr(
                    config,
                    "availability_telegram_api_base_url",
                    "https://api.telegram.org",
                )
            ),
            min_interval_seconds=float(
                getattr(config, "availability_telegram_min_interval_seconds", 0.25)
            ),
            max_retries=int(getattr(config, "availability_telegram_max_retries", 3)),
            request_timeout_seconds=int(
                getattr(config, "availability_telegram_request_timeout_seconds", 15)
            ),
        )

        self.signal_connector = SignalConnector(
            enabled=bool(getattr(config, "availability_signal_enabled", False)),
            mode=str(getattr(config, "availability_signal_mode", "cli")),
            signal_cli_path=str(
                getattr(config, "availability_signal_cli_path", "signal-cli")
            ),
            sender_number=str(getattr(config, "availability_signal_sender", "")),
            daemon_url=str(
                getattr(config, "availability_signal_daemon_url", "http://127.0.0.1:8080")
            ),
            min_interval_seconds=float(
                getattr(config, "availability_signal_min_interval_seconds", 0.25)
            ),
            max_retries=int(getattr(config, "availability_signal_max_retries", 2)),
            request_timeout_seconds=int(
                getattr(config, "availability_signal_request_timeout_seconds", 20)
            ),
        )

        self.tables_ensured = False

    async def close(self) -> None:
        await self.telegram_connector.close()
        await self.signal_connector.close()

    async def ensure_tables(self) -> None:
        """Ensure runtime tables needed by notifier and link flow exist."""
        if self.tables_ensured:
            return

        await self.db_adapter.execute(
            """
            CREATE TABLE IF NOT EXISTS availability_channel_links (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                channel_type TEXT NOT NULL CHECK (channel_type IN ('discord', 'telegram', 'signal')),
                destination TEXT,
                verification_token_hash TEXT,
                token_expires_at TIMESTAMP,
                verification_requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verified_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (user_id, channel_type)
            )
            """
        )

        await self.db_adapter.execute(
            """
            CREATE TABLE IF NOT EXISTS availability_subscriptions (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                channel_type TEXT NOT NULL CHECK (channel_type IN ('discord', 'telegram', 'signal')),
                channel_address TEXT,
                enabled BOOLEAN NOT NULL DEFAULT TRUE,
                verified_at TIMESTAMP,
                preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (user_id, channel_type)
            )
            """
        )

        await self.db_adapter.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications_ledger (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                event_key TEXT NOT NULL,
                channel_type TEXT NOT NULL CHECK (channel_type IN ('discord', 'telegram', 'signal')),
                sent_at TIMESTAMP,
                message_id TEXT,
                error TEXT,
                retries INTEGER NOT NULL DEFAULT 0,
                payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (user_id, event_key, channel_type)
            )
            """
        )

        await self.db_adapter.execute(
            "CREATE INDEX IF NOT EXISTS idx_notifications_ledger_user_event ON notifications_ledger(user_id, event_key)"
        )
        await self.db_adapter.execute(
            "CREATE INDEX IF NOT EXISTS idx_availability_subscriptions_user ON availability_subscriptions(user_id)"
        )

        self.tables_ensured = True

    @staticmethod
    def build_event_key(event_type: str, event_date: date, qualifier: Optional[str] = None) -> str:
        base = f"{event_type}:{event_date.isoformat()}"
        if qualifier:
            return f"{base}:{qualifier}"
        return base

    async def create_link_token(
        self,
        *,
        user_id: int,
        channel_type: str,
        ttl_minutes: int = 30,
    ) -> tuple[str, datetime]:
        """Create token used by Telegram/Signal command flows to link channels."""
        await self.ensure_tables()

        normalized = (channel_type or "").strip().lower()
        if normalized not in {"telegram", "signal"}:
            raise ValueError("channel_type must be telegram or signal")

        token = secrets.token_urlsafe(24)
        token_hash = self._token_hash(token)
        expires_at = datetime.utcnow() + timedelta(minutes=max(5, int(ttl_minutes)))

        await self.db_adapter.execute(
            """
            INSERT INTO availability_channel_links
                (user_id, channel_type, destination, verification_token_hash, token_expires_at, verification_requested_at, verified_at, updated_at)
            VALUES ($1, $2, NULL, $3, $4, CURRENT_TIMESTAMP, NULL, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, channel_type) DO UPDATE SET
                destination = NULL,
                verification_token_hash = EXCLUDED.verification_token_hash,
                token_expires_at = EXCLUDED.token_expires_at,
                verification_requested_at = CURRENT_TIMESTAMP,
                verified_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            """,
            (int(user_id), normalized, token_hash, expires_at),
        )

        return token, expires_at

    async def consume_link_token(
        self,
        *,
        channel_type: str,
        token: str,
        channel_address: str,
    ) -> Optional[int]:
        """Resolve token from Telegram/Signal message and activate subscription."""
        await self.ensure_tables()

        normalized = (channel_type or "").strip().lower()
        if normalized not in {"telegram", "signal"}:
            return None

        token_hash = self._token_hash(token)

        row = await self.db_adapter.fetch_one(
            """
            SELECT user_id
            FROM availability_channel_links
            WHERE channel_type = $1
              AND verification_token_hash = $2
              AND verified_at IS NULL
              AND (token_expires_at IS NULL OR token_expires_at >= CURRENT_TIMESTAMP)
            LIMIT 1
            """,
            (normalized, token_hash),
        )
        if not row:
            return None

        user_id = int(row[0])
        target = str(channel_address).strip()
        if not target:
            return None

        await self.db_adapter.execute(
            """
            UPDATE availability_channel_links
            SET destination = $1,
                verified_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = $2 AND channel_type = $3
            """,
            (target, user_id, normalized),
        )

        await self.db_adapter.execute(
            """
            INSERT INTO availability_subscriptions
                (user_id, channel_type, channel_address, enabled, verified_at, preferences, created_at, updated_at)
            VALUES ($1, $2, $3, TRUE, CURRENT_TIMESTAMP, '{}'::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, channel_type) DO UPDATE SET
                channel_address = EXCLUDED.channel_address,
                enabled = TRUE,
                verified_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, normalized, target),
        )

        return user_id

    async def unsubscribe_by_channel_address(self, *, channel_type: str, channel_address: str) -> int:
        """Disable a subscription by inbound channel address (used by /unlink commands)."""
        await self.ensure_tables()

        normalized = (channel_type or "").strip().lower()
        if normalized not in {"telegram", "signal"}:
            return 0

        target = (channel_address or "").strip()
        if not target:
            return 0

        rows = await self.db_adapter.fetch_all(
            """
            UPDATE availability_subscriptions
            SET enabled = FALSE,
                updated_at = CURRENT_TIMESTAMP
            WHERE channel_type = $1
              AND channel_address = $2
              AND enabled = TRUE
            RETURNING user_id
            """,
            (normalized, target),
        )
        return len(rows or [])

    async def notify_users(
        self,
        *,
        event_type: str,
        event_key: str,
        message: str,
        user_ids: Iterable[int],
        payload: Optional[Dict[str, Any]] = None,
        announce_message: Optional[str] = None,
    ) -> DeliveryResult:
        """Notify target users across all enabled channels (idempotent)."""
        await self.ensure_tables()

        result = DeliveryResult()
        unique_ids = sorted({int(user_id) for user_id in user_ids if int(user_id) > 0})

        for user_id in unique_ids:
            delivery = await self._notify_single_user(
                user_id=user_id,
                event_key=event_key,
                event_type=event_type,
                message=message,
                payload=payload,
            )
            result.sent += delivery.sent
            result.failed += delivery.failed
            result.skipped += delivery.skipped

        if (
            announce_message
            and self.discord_channel_announce_enabled
            and self.discord_announce_channel_id > 0
        ):
            pseudo_user_id = -int(self.discord_announce_channel_id)
            status = await self._send_with_ledger(
                user_id=pseudo_user_id,
                event_key=event_key,
                channel_type="discord",
                payload=payload,
                send_callable=lambda: self._send_discord_channel(
                    int(self.discord_announce_channel_id),
                    announce_message,
                ),
            )
            if status == "sent":
                result.sent += 1
            elif status == "failed":
                result.failed += 1
            else:
                result.skipped += 1

        return result

    async def send_discord(self, user_or_channel: int | str, message: str) -> str:
        """Public channel adapter for promotion workflows."""
        raw_target = str(user_or_channel).strip()
        if not raw_target or not raw_target.lstrip("-").isdigit():
            raise RuntimeError("Discord target must be numeric user/channel id")
        target_id = int(raw_target)
        if target_id <= 0:
            raise RuntimeError("Discord target id must be positive")
        return await self._send_discord_dm(target_id, message)

    async def send_discord_channel(self, channel_id: int | str, message: str) -> str:
        raw_target = str(channel_id).strip()
        if not raw_target or not raw_target.lstrip("-").isdigit():
            raise RuntimeError("Discord channel id must be numeric")
        target_id = int(raw_target)
        if target_id <= 0:
            raise RuntimeError("Discord channel id must be positive")
        return await self._send_discord_channel(target_id, message)

    async def send_telegram(self, handle: str, message: str) -> str:
        if not self.telegram_connector.enabled:
            raise RuntimeError("Telegram connector is disabled")
        target = str(handle or "").strip()
        if not target:
            raise RuntimeError("Telegram handle is required")
        return await self.telegram_connector.send_message(target, message)

    async def send_signal(self, handle: str, message: str) -> str:
        if not self.signal_connector.enabled:
            raise RuntimeError("Signal connector is disabled")
        target = str(handle or "").strip()
        if not target:
            raise RuntimeError("Signal handle is required")
        return await self.signal_connector.send_message(target, message)

    async def send_via_channel(self, *, channel_type: str, target: str, message: str) -> str:
        normalized = str(channel_type or "").strip().lower()
        if normalized == "discord":
            return await self.send_discord(target, message)
        if normalized == "telegram":
            return await self.send_telegram(target, message)
        if normalized == "signal":
            return await self.send_signal(target, message)
        raise RuntimeError(f"Unsupported channel_type: {channel_type}")

    async def send_via_channel_idempotent(
        self,
        *,
        user_id: int,
        event_key: str,
        channel_type: str,
        target: str,
        message: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> tuple[str, str | None]:
        """
        Idempotent one-shot send for promotion workflows.
        Returns (status, message_id) where status is sent|skipped|failed.
        """
        await self.ensure_tables()

        normalized_channel = str(channel_type or "").strip().lower()
        if normalized_channel not in {"discord", "telegram", "signal"}:
            raise RuntimeError(f"Unsupported channel_type: {channel_type}")

        status = await self._send_with_ledger(
            user_id=int(user_id),
            event_key=str(event_key),
            channel_type=normalized_channel,
            payload=payload,
            send_callable=lambda: self.send_via_channel(
                channel_type=normalized_channel,
                target=str(target),
                message=message,
            ),
        )

        row = await self.db_adapter.fetch_one(
            """
            SELECT message_id
            FROM notifications_ledger
            WHERE user_id = $1 AND event_key = $2 AND channel_type = $3
            LIMIT 1
            """,
            (int(user_id), str(event_key), normalized_channel),
        )
        message_id = str(row[0]) if row and row[0] else None
        return status, message_id

    async def send_discord_channel_idempotent(
        self,
        *,
        channel_id: int,
        event_key: str,
        message: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> tuple[str, str | None]:
        """
        Idempotent Discord channel send for campaign summaries/followups.
        Uses negative pseudo-user IDs so it shares the same ledger table.
        """
        await self.ensure_tables()

        target_channel_id = int(channel_id)
        if target_channel_id <= 0:
            raise RuntimeError("Discord channel id must be positive")
        pseudo_user_id = -target_channel_id

        status = await self._send_with_ledger(
            user_id=pseudo_user_id,
            event_key=str(event_key),
            channel_type="discord",
            payload=payload,
            send_callable=lambda: self._send_discord_channel(target_channel_id, message),
        )

        row = await self.db_adapter.fetch_one(
            """
            SELECT message_id
            FROM notifications_ledger
            WHERE user_id = $1 AND event_key = $2 AND channel_type = 'discord'
            LIMIT 1
            """,
            (pseudo_user_id, str(event_key)),
        )
        message_id = str(row[0]) if row and row[0] else None
        return status, message_id

    async def _notify_single_user(
        self,
        *,
        user_id: int,
        event_key: str,
        event_type: str,
        message: str,
        payload: Optional[Dict[str, Any]],
    ) -> DeliveryResult:
        _ = event_type  # reserved for future formatting/routing

        result = DeliveryResult()
        subscriptions = await self._subscription_map(user_id)

        # Discord is default-enabled for linked users.
        discord_enabled = bool(subscriptions.get("discord", {}).get("enabled", True))
        if discord_enabled and self.discord_dm_enabled:
            status = await self._send_with_ledger(
                user_id=user_id,
                event_key=event_key,
                channel_type="discord",
                payload=payload,
                send_callable=lambda: self._send_discord_dm(user_id, message),
            )
            self._bump_result(result, status)

        telegram = subscriptions.get("telegram")
        if telegram and telegram.get("enabled") and telegram.get("channel_address") and self.telegram_connector.enabled:
            status = await self._send_with_ledger(
                user_id=user_id,
                event_key=event_key,
                channel_type="telegram",
                payload=payload,
                send_callable=lambda target=str(telegram["channel_address"]): self.telegram_connector.send_message(
                    target,
                    message,
                ),
            )
            self._bump_result(result, status)

        signal = subscriptions.get("signal")
        if signal and signal.get("enabled") and signal.get("channel_address") and self.signal_connector.enabled:
            status = await self._send_with_ledger(
                user_id=user_id,
                event_key=event_key,
                channel_type="signal",
                payload=payload,
                send_callable=lambda target=str(signal["channel_address"]): self.signal_connector.send_message(
                    target,
                    message,
                ),
            )
            self._bump_result(result, status)

        return result

    async def _subscription_map(self, user_id: int) -> Dict[str, Dict[str, Any]]:
        rows = await self.db_adapter.fetch_all(
            """
            SELECT channel_type, enabled, channel_address
            FROM availability_subscriptions
            WHERE user_id = $1
            """,
            (int(user_id),),
        )

        mapping: Dict[str, Dict[str, Any]] = {}
        for row in rows or []:
            channel_type = str(row[0] or "").lower()
            mapping[channel_type] = {
                "enabled": bool(row[1]),
                "channel_address": row[2],
            }

        if "discord" not in mapping:
            mapping["discord"] = {
                "enabled": True,
                "channel_address": str(user_id),
            }

        return mapping

    async def _send_with_ledger(
        self,
        *,
        user_id: int,
        event_key: str,
        channel_type: str,
        payload: Optional[Dict[str, Any]],
        send_callable,
    ) -> str:
        existing = await self.db_adapter.fetch_one(
            """
            SELECT id, message_id, retries
            FROM notifications_ledger
            WHERE user_id = $1 AND event_key = $2 AND channel_type = $3
            """,
            (int(user_id), event_key, channel_type),
        )

        if existing and existing[1]:
            return "skipped"

        retries = int(existing[2] or 0) if existing else 0
        if retries >= self.max_attempts:
            return "skipped"

        payload_json = json.dumps(payload or {}, ensure_ascii=True)

        try:
            message_id = await send_callable()
            message_id_str = str(message_id or "ok")

            if existing:
                await self.db_adapter.execute(
                    """
                    UPDATE notifications_ledger
                    SET sent_at = CURRENT_TIMESTAMP,
                        message_id = $1,
                        error = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = $2
                    """,
                    (message_id_str, int(existing[0])),
                )
            else:
                await self.db_adapter.execute(
                    """
                    INSERT INTO notifications_ledger
                        (user_id, event_key, channel_type, sent_at, message_id, error, retries, payload, updated_at)
                    VALUES ($1, $2, $3, CURRENT_TIMESTAMP, $4, NULL, 0, CAST($5 AS JSONB), CURRENT_TIMESTAMP)
                    """,
                    (int(user_id), event_key, channel_type, message_id_str, payload_json),
                )
            return "sent"
        except Exception as exc:
            error_text = str(exc).strip()[:1500]
            if existing:
                await self.db_adapter.execute(
                    """
                    UPDATE notifications_ledger
                    SET error = $1,
                        retries = COALESCE(retries, 0) + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = $2
                    """,
                    (error_text, int(existing[0])),
                )
            else:
                await self.db_adapter.execute(
                    """
                    INSERT INTO notifications_ledger
                        (user_id, event_key, channel_type, sent_at, message_id, error, retries, payload, updated_at)
                    VALUES ($1, $2, $3, NULL, NULL, $4, 1, CAST($5 AS JSONB), CURRENT_TIMESTAMP)
                    """,
                    (int(user_id), event_key, channel_type, error_text, payload_json),
                )
            logger.warning(
                "Availability notification failed user_id=%s event_key=%s channel=%s error=%s",
                user_id,
                event_key,
                channel_type,
                error_text,
            )
            return "failed"

    async def _send_discord_dm(self, user_id: int, message: str) -> str:
        user = self.bot.get_user(int(user_id))
        if user is None:
            user = await self.bot.fetch_user(int(user_id))

        for attempt in range(1, 4):
            try:
                sent_message = await user.send(message)
                return str(getattr(sent_message, "id", "ok"))
            except discord.Forbidden as exc:
                raise RuntimeError("Discord DMs are closed for this user") from exc
            except discord.HTTPException as exc:
                retry_after = getattr(exc, "retry_after", None)
                if exc.status == 429 and attempt < 3:
                    await asyncio.sleep(float(retry_after or 2.0))
                    continue
                raise RuntimeError(f"Discord DM failed ({exc.status}): {exc}") from exc

        raise RuntimeError("Discord DM failed after retries")

    async def _send_discord_channel(self, channel_id: int, message: str) -> str:
        channel = self.bot.get_channel(int(channel_id))
        if channel is None:
            channel = await self.bot.fetch_channel(int(channel_id))
        if not hasattr(channel, "send"):
            raise RuntimeError(f"Channel {channel_id} is not messageable")
        sent_message = await channel.send(message)
        return str(getattr(sent_message, "id", "ok"))

    @staticmethod
    def _token_hash(token: str) -> str:
        import hashlib

        return hashlib.sha256(str(token).encode("utf-8")).hexdigest()

    @staticmethod
    def _bump_result(result: DeliveryResult, status: str) -> None:
        if status == "sent":
            result.sent += 1
        elif status == "failed":
            result.failed += 1
        else:
            result.skipped += 1
