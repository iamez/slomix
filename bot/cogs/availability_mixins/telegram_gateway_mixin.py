"""AvailabilityPollCog mixin: Telegram/Signal gateway command handling.

Extracted from bot/cogs/availability_poll_cog.py in Mega Audit v4 / Sprint 1.

All methods live on AvailabilityPollCog via mixin inheritance.
Discord.py's CogMeta scans base classes via MRO for @commands.command,
@commands.Cog.listener, and @tasks.loop decorators, so these work unchanged.
"""
from __future__ import annotations

from discord.ext import tasks

from bot.logging_config import get_logger

logger = get_logger("bot.core")


class _AvailabilityTelegramGatewayMixin:
    """Telegram/Signal gateway command handling for AvailabilityPollCog."""

    async def _poll_telegram_updates(self):
        connector = self.notifier.telegram_connector
        if not connector.enabled:
            return

        client = await connector._get_client()
        endpoint = f"{connector.api_base_url}/bot{connector.bot_token}/getUpdates"
        response = await client.get(
            endpoint,
            params={
                "offset": self.telegram_update_offset,
                "timeout": 0,
                "allowed_updates": "[\"message\"]",
            },
        )
        if response.status_code != 200:
            return

        payload = response.json()
        if not isinstance(payload, dict) or not payload.get("ok"):
            return

        updates = payload.get("result") or []
        for update in updates:
            if not isinstance(update, dict):
                continue
            update_id = int(update.get("update_id", 0))
            if update_id >= self.telegram_update_offset:
                self.telegram_update_offset = update_id + 1

            message = update.get("message")
            if not isinstance(message, dict):
                continue
            chat = message.get("chat") or {}
            chat_id = chat.get("id")
            text = (message.get("text") or "").strip()
            if not chat_id or not text:
                continue
            await self._handle_telegram_command(str(chat_id), text)

    async def _handle_telegram_command(self, chat_id: str, text: str):
        connector = self.notifier.telegram_connector
        command = text.strip()
        lower = command.lower()

        if lower.startswith("/link "):
            token = command.split(maxsplit=1)[1].strip()
            user_id = await self.notifier.consume_link_token(
                channel_type="telegram",
                token=token,
                channel_address=chat_id,
            )
            if user_id:
                await connector.send_message(
                    chat_id,
                    "✅ Telegram linked. You'll now receive availability notifications.",
                )
            else:
                await connector.send_message(
                    chat_id,
                    "❌ Invalid or expired token. Generate a fresh token with !avail_link telegram.",
                )
            return

        if lower.startswith("/unlink"):
            disabled = await self.notifier.unsubscribe_by_channel_address(
                channel_type="telegram",
                channel_address=chat_id,
            )
            if disabled > 0:
                await connector.send_message(chat_id, "✅ Telegram availability notifications disabled.")
            else:
                await connector.send_message(chat_id, "ℹ️ No active Telegram availability subscription found.")
            return

        if lower.startswith("/help"):
            await connector.send_message(chat_id, self._format_external_usage())
            return

        if lower.startswith("/avail") or lower.startswith("/today") or lower.startswith("/tomorrow"):
            reply = await self._apply_external_availability_command(
                channel_type="telegram",
                channel_address=chat_id,
                command_text=command,
            )
            await connector.send_message(chat_id, reply)
            return

        await connector.send_message(
            chat_id,
            "Commands: /link <token>, /unlink, /avail, /today, /tomorrow, /help.",
        )

    async def handle_signal_gateway_command(self, sender: str, text: str) -> str:
        """
        Entry-point for Signal gateway integrations (webhook/operator wrappers).
        Returns response text so caller can relay it back to Signal user.
        """
        return await self._apply_external_availability_command(
            channel_type="signal",
            channel_address=str(sender or "").strip(),
            command_text=text,
        )

    @tasks.loop(seconds=8)
    async def telegram_command_loop(self):
        try:
            await self._ensure_multichannel_tables()
            await self._poll_telegram_updates()
        except Exception as exc:
            logger.warning("Telegram command loop error: %s", exc)

    @telegram_command_loop.before_loop
    async def before_telegram_command_loop(self):
        await self.bot.wait_until_ready()
