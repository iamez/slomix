"""AvailabilityPollCog mixin: External channel availability commands (Telegram/Signal linked users).

Extracted from bot/cogs/availability_poll_cog.py in Mega Audit v4 / Sprint 1.

All methods live on AvailabilityPollCog via mixin inheritance.
Discord.py's CogMeta scans base classes via MRO for @commands.command,
@commands.Cog.listener, and @tasks.loop decorators, so these work unchanged.
"""
from __future__ import annotations

from datetime import date as dt_date
from datetime import datetime, timedelta

import discord
from discord.ext import commands

from bot.cogs.availability_mixins import REMOVE_STATUS_KEYWORDS
from bot.logging_config import get_logger

logger = get_logger("bot.core")


class _AvailabilityExternalChannelsMixin:
    """External channel availability commands (Telegram/Signal linked users) for _AvailabilityExternalChannelsMixin."""

    async def _ensure_multichannel_tables(self):
        await self.notifier.ensure_tables()
        # Fast path: if last table exists, all availability tables are present
        row = await self.bot.db_adapter.fetch_one(
            "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = $1 LIMIT 1",
            ("subscription_preferences",),
        )
        if row:
            return
        await self.bot.db_adapter.execute(
            """
            CREATE TABLE IF NOT EXISTS availability_entries (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                user_name TEXT,
                entry_date DATE NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('LOOKING', 'AVAILABLE', 'MAYBE', 'NOT_PLAYING')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (user_id, entry_date)
            )
            """
        )
        await self.bot.db_adapter.execute(
            "CREATE INDEX IF NOT EXISTS idx_availability_entries_date ON availability_entries(entry_date)"
        )
        await self.bot.db_adapter.execute(
            """
            CREATE TABLE IF NOT EXISTS availability_promotion_campaigns (
                id BIGSERIAL PRIMARY KEY,
                campaign_date DATE NOT NULL,
                target_timezone TEXT NOT NULL DEFAULT 'Europe/Ljubljana',
                target_start_time TIME NOT NULL DEFAULT '21:00',
                initiated_by_user_id BIGINT NOT NULL,
                initiated_by_discord_id BIGINT NOT NULL,
                include_maybe BOOLEAN NOT NULL DEFAULT FALSE,
                include_available BOOLEAN NOT NULL DEFAULT FALSE,
                dry_run BOOLEAN NOT NULL DEFAULT FALSE,
                status TEXT NOT NULL DEFAULT 'scheduled' CHECK (
                    status IN ('scheduled', 'running', 'sent', 'followup_sent', 'partial', 'failed', 'cancelled')
                ),
                idempotency_key TEXT NOT NULL,
                recipient_count INTEGER NOT NULL DEFAULT 0,
                channels_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
                recipients_snapshot JSONB NOT NULL DEFAULT '[]'::jsonb,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (campaign_date, initiated_by_user_id),
                UNIQUE (campaign_date, idempotency_key)
            )
            """
        )
        await self.bot.db_adapter.execute(
            """
            CREATE TABLE IF NOT EXISTS availability_promotion_jobs (
                id BIGSERIAL PRIMARY KEY,
                campaign_id BIGINT NOT NULL REFERENCES availability_promotion_campaigns(id) ON DELETE CASCADE,
                job_type TEXT NOT NULL CHECK (
                    job_type IN ('send_reminder_2045', 'send_start_2100', 'voice_check_2100')
                ),
                run_at TIMESTAMPTZ NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending' CHECK (
                    status IN ('pending', 'running', 'sent', 'skipped', 'failed')
                ),
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 5,
                last_error TEXT,
                payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                sent_at TIMESTAMPTZ,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (campaign_id, job_type)
            )
            """
        )
        await self.bot.db_adapter.execute(
            """
            CREATE TABLE IF NOT EXISTS availability_promotion_send_logs (
                id BIGSERIAL PRIMARY KEY,
                campaign_id BIGINT NOT NULL REFERENCES availability_promotion_campaigns(id) ON DELETE CASCADE,
                job_id BIGINT REFERENCES availability_promotion_jobs(id) ON DELETE SET NULL,
                user_id BIGINT NOT NULL,
                channel_type TEXT NOT NULL CHECK (channel_type IN ('discord', 'telegram', 'signal')),
                status TEXT NOT NULL CHECK (status IN ('pending', 'sent', 'failed', 'skipped')),
                message_id TEXT,
                error TEXT,
                payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await self.bot.db_adapter.execute(
            """
            CREATE TABLE IF NOT EXISTS subscription_preferences (
                user_id BIGINT PRIMARY KEY,
                allow_promotions BOOLEAN NOT NULL DEFAULT FALSE,
                preferred_channel TEXT NOT NULL DEFAULT 'any'
                    CHECK (preferred_channel IN ('discord', 'telegram', 'signal', 'any')),
                telegram_handle_encrypted TEXT,
                signal_handle_encrypted TEXT,
                quiet_hours JSONB NOT NULL DEFAULT '{}'::jsonb,
                timezone TEXT NOT NULL DEFAULT 'Europe/Ljubljana',
                notify_threshold INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await self.bot.db_adapter.execute(
            "CREATE INDEX IF NOT EXISTS idx_availability_promotion_jobs_due ON availability_promotion_jobs(status, run_at)"
        )

    async def _is_discord_linked(self, discord_user_id: int) -> bool:
        row = await self.bot.db_adapter.fetch_one(
            "SELECT 1 FROM player_links WHERE discord_id = $1 LIMIT 1",
            (int(discord_user_id),),
        )
        return bool(row)

    @staticmethod
    def _normalize_status_input(raw_status: str) -> str | None:
        if not raw_status:
            return None
        normalized = str(raw_status).strip().upper()
        mapping = {
            "LOOKING": "LOOKING",
            "LOOKING_TO_PLAY": "LOOKING",
            "L": "LOOKING",
            "AVAILABLE": "AVAILABLE",
            "A": "AVAILABLE",
            "MAYBE": "MAYBE",
            "TENTATIVE": "MAYBE",
            "M": "MAYBE",
            "NOT_PLAYING": "NOT_PLAYING",
            "NOTPLAYING": "NOT_PLAYING",
            "NO": "NOT_PLAYING",
            "N": "NOT_PLAYING",
        }
        return mapping.get(normalized)

    @staticmethod
    def _parse_date_arg(raw_date: str, now_date: dt_date) -> dt_date | None:
        if not raw_date:
            return None
        lowered = raw_date.strip().lower()
        if lowered == "today":
            return now_date
        if lowered == "tomorrow":
            return now_date + timedelta(days=1)
        try:
            return dt_date.fromisoformat(raw_date.strip())
        except ValueError:
            return None

    @staticmethod
    def _normalize_operation_input(raw_status: str) -> tuple[str | None, str | None]:
        if not raw_status:
            return None, None
        normalized = (
            str(raw_status)
            .strip()
            .upper()
            .replace("-", "_")
            .replace(" ", "_")
        )
        if normalized in REMOVE_STATUS_KEYWORDS:
            return "REMOVE", None
        status = _AvailabilityExternalChannelsMixin._normalize_status_input(normalized)
        if status:
            return "SET", status
        return None, None

    @staticmethod
    def _parse_availability_operation(args: list[str], now_date: dt_date) -> tuple[dt_date | None, str | None, str | None]:
        """
        Parse date + status/remove operation from command args.

        Supported forms:
        - <today|tomorrow|YYYY-MM-DD> <STATUS>
        - <today|tomorrow|YYYY-MM-DD> <REMOVE|DELETE|CLEAR>
        - <REMOVE|DELETE|CLEAR> <today|tomorrow|YYYY-MM-DD>
        """
        if len(args) < 2:
            return None, None, None

        first = args[0].strip()
        second = args[1].strip()
        first_op, _ = _AvailabilityExternalChannelsMixin._normalize_operation_input(first)

        if first_op == "REMOVE":
            target_date = _AvailabilityExternalChannelsMixin._parse_date_arg(second, now_date)
            if target_date is None:
                return None, None, None
            return target_date, "REMOVE", None

        target_date = _AvailabilityExternalChannelsMixin._parse_date_arg(first, now_date)
        if target_date is None:
            return None, None, None

        status_text = " ".join(args[1:]).strip()
        operation, status = _AvailabilityExternalChannelsMixin._normalize_operation_input(status_text)
        if operation is None:
            return None, None, None
        return target_date, operation, status

    async def _resolve_linked_user_from_channel(self, *, channel_type: str, channel_address: str) -> int | None:
        row = await self.bot.db_adapter.fetch_one(
            """
            SELECT user_id
            FROM availability_channel_links
            WHERE channel_type = $1
              AND destination = $2
              AND verified_at IS NOT NULL
            LIMIT 1
            """,
            (str(channel_type).strip().lower(), str(channel_address).strip()),
        )
        if not row:
            return None

        user_id = int(row[0])
        if not await self._is_discord_linked(user_id):
            return None
        return user_id

    async def _delete_user_availability(
        self,
        *,
        user_id: int,
        entry_date: dt_date,
    ) -> bool:
        existing = await self.bot.db_adapter.fetch_one(
            """
            SELECT id
            FROM availability_entries
            WHERE user_id = $1
              AND entry_date = $2
            LIMIT 1
            """,
            (int(user_id), entry_date),
        )
        if not existing:
            return False

        await self.bot.db_adapter.execute(
            """
            DELETE FROM availability_entries
            WHERE user_id = $1
              AND entry_date = $2
            """,
            (int(user_id), entry_date),
        )
        return True

    @staticmethod
    def _format_external_usage() -> str:
        return (
            "Commands:\n"
            "/avail <today|tomorrow|YYYY-MM-DD> <LOOKING|AVAILABLE|MAYBE|NOT_PLAYING>\n"
            "/avail <today|tomorrow|YYYY-MM-DD> <remove>\n"
            "/avail remove <today|tomorrow|YYYY-MM-DD>\n"
            "/today <status>  |  /tomorrow <status>\n"
            "/avail status"
        )

    async def _format_external_status_summary(self, *, user_id: int, now_date: dt_date) -> str:
        tomorrow = now_date + timedelta(days=1)
        rows = await self.bot.db_adapter.fetch_all(
            """
            SELECT entry_date, status
            FROM availability_entries
            WHERE user_id = $1
              AND entry_date BETWEEN $2 AND $3
            ORDER BY entry_date ASC
            """,
            (int(user_id), now_date, tomorrow),
        )
        by_date = {
            row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0])[:10]: str(row[1] or "")
            for row in (rows or [])
        }
        today_status = by_date.get(now_date.isoformat(), "not set")
        tomorrow_status = by_date.get(tomorrow.isoformat(), "not set")
        return (
            f"Your availability:\n"
            f"- Today ({now_date.isoformat()}): {today_status}\n"
            f"- Tomorrow ({tomorrow.isoformat()}): {tomorrow_status}"
        )

    async def _apply_external_availability_command(
        self,
        *,
        channel_type: str,
        channel_address: str,
        command_text: str,
    ) -> str:
        await self._ensure_multichannel_tables()

        now_date = datetime.now(self.timezone).date()
        tokens = [token for token in str(command_text or "").strip().split() if token]
        if not tokens:
            return self._format_external_usage()

        head = tokens[0].lower()
        if head in {"/today", "today"}:
            args = ["today", *tokens[1:]]
        elif head in {"/tomorrow", "tomorrow"}:
            args = ["tomorrow", *tokens[1:]]
        elif head in {"/avail", "!avail", "avail"}:
            if len(tokens) >= 2 and tokens[1].strip().lower() in {"status"}:
                linked_user_id = await self._resolve_linked_user_from_channel(
                    channel_type=channel_type,
                    channel_address=channel_address,
                )
                if linked_user_id is None:
                    return (
                        "❌ This channel is not linked to a Discord player profile yet.\n"
                        "Generate a token on Discord with `!avail_link telegram` (or signal) and run `/link <token>`."
                    )
                return await self._format_external_status_summary(
                    user_id=linked_user_id,
                    now_date=now_date,
                )
            if len(tokens) == 1:
                return self._format_external_usage()
            args = tokens[1:]
        else:
            return self._format_external_usage()

        target_date, operation, status = self._parse_availability_operation(args, now_date)
        if target_date is None or operation is None:
            return self._format_external_usage()

        if target_date < now_date:
            return "❌ Past dates are read-only."
        if target_date > now_date + timedelta(days=90):
            return "❌ Date must be within 90 days."

        linked_user_id = await self._resolve_linked_user_from_channel(
            channel_type=channel_type,
            channel_address=channel_address,
        )
        if linked_user_id is None:
            return (
                "❌ This channel is not linked to a Discord player profile yet.\n"
                "Generate a token on Discord with `!avail_link telegram` (or signal) and run `/link <token>`."
            )

        link_row = await self.bot.db_adapter.fetch_one(
            "SELECT player_name, discord_username FROM player_links WHERE discord_id = $1 LIMIT 1",
            (int(linked_user_id),),
        )
        user_name = (
            str(link_row[0] or "").strip()
            if link_row and link_row[0]
            else str(link_row[1] or "").strip()
            if link_row and link_row[1]
            else f"User {linked_user_id}"
        )

        if operation == "REMOVE":
            removed = await self._delete_user_availability(
                user_id=linked_user_id,
                entry_date=target_date,
            )
            if removed:
                return f"✅ Availability cleared for {target_date.isoformat()}."
            return f"ℹ️ No availability entry existed for {target_date.isoformat()}."

        await self._upsert_user_availability(
            user_id=linked_user_id,
            user_name=user_name,
            entry_date=target_date,
            status=str(status),
        )
        return f"✅ Availability set: {target_date.isoformat()} -> {status}."

    async def _upsert_user_availability(
        self,
        *,
        user_id: int,
        user_name: str,
        entry_date: dt_date,
        status: str,
    ) -> None:
        await self.bot.db_adapter.execute(
            """
            INSERT INTO availability_entries
                (user_id, user_name, entry_date, status, created_at, updated_at)
            VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, entry_date) DO UPDATE SET
                user_name = EXCLUDED.user_name,
                status = EXCLUDED.status,
                updated_at = CURRENT_TIMESTAMP
            """,
            (int(user_id), user_name, entry_date, status),
        )

    @commands.command(name="avail")
    @commands.cooldown(2, 15, commands.BucketType.user)
    async def set_availability_command(self, ctx, *args):
        """
        Set date-based availability.

        Usage:
            !avail today LOOKING
            !avail tomorrow MAYBE
            !avail 2026-02-20 AVAILABLE
            !avail 2026-02-20 NOT_PLAYING
            !avail today remove
            !avail remove tomorrow
            !avail status
        """
        await self._ensure_multichannel_tables()

        user_id = int(ctx.author.id)
        if not await self._is_discord_linked(user_id):
            await ctx.send("❌ Your Discord account must be linked first (`!link`).")
            return

        now_date = datetime.now(self.timezone).date()

        if args and str(args[0]).strip().lower() == "status":
            await ctx.send(await self._format_external_status_summary(user_id=user_id, now_date=now_date))
            return

        parsed_args = [str(arg) for arg in args]
        target_date, operation, status = self._parse_availability_operation(parsed_args, now_date)
        if target_date is None or operation is None:
            await ctx.send(
                "Usage: `!avail <today|tomorrow|YYYY-MM-DD> <LOOKING|AVAILABLE|MAYBE|NOT_PLAYING|remove>`\n"
                "Also: `!avail remove <today|tomorrow|YYYY-MM-DD>` or `!avail status`."
            )
            return
        if target_date < now_date:
            await ctx.send("❌ Past dates are read-only.")
            return
        if target_date > now_date + timedelta(days=90):
            await ctx.send("❌ Date must be within 90 days.")
            return

        if operation == "REMOVE":
            removed = await self._delete_user_availability(
                user_id=user_id,
                entry_date=target_date,
            )
            if removed:
                await ctx.send(f"✅ Availability cleared for **{target_date.isoformat()}**.")
            else:
                await ctx.send(f"ℹ️ No availability entry existed for **{target_date.isoformat()}**.")
            return

        username = (
            f"{ctx.author.name}#{ctx.author.discriminator}"
            if getattr(ctx.author, "discriminator", "0") != "0"
            else ctx.author.name
        )
        await self._upsert_user_availability(
            user_id=user_id,
            user_name=username,
            entry_date=target_date,
            status=str(status),
        )

        await ctx.send(f"✅ Availability set: **{target_date.isoformat()}** → **{status}**")

    @commands.command(name="avail_link")
    @commands.cooldown(1, 20, commands.BucketType.user)
    async def availability_link_token(self, ctx, channel_type: str = None):
        """
        Generate a one-time link token for Telegram/Signal notification subscription.

        Usage:
            !avail_link telegram
            !avail_link signal
        """
        normalized = (channel_type or "").strip().lower()
        if normalized not in {"telegram", "signal"}:
            await ctx.send("Usage: `!avail_link <telegram|signal>`")
            return

        await self._ensure_multichannel_tables()
        user_id = int(ctx.author.id)
        if not await self._is_discord_linked(user_id):
            await ctx.send("❌ Your Discord account must be linked first (`!link`).")
            return

        ttl = int(getattr(self.bot.config, "availability_link_token_ttl_minutes", 30))
        token, expires_at = await self.notifier.create_link_token(
            user_id=user_id,
            channel_type=normalized,
            ttl_minutes=ttl,
        )

        instructions = (
            f"Link token for {normalized}: `{token}`\n"
            f"Expires: {expires_at.isoformat()} UTC\n"
        )
        if normalized == "telegram":
            instructions += "Send `/link <token>` to the Telegram bot to activate.\n"
            instructions += "Use `/unlink` in Telegram to stop notifications."
        else:
            instructions += "Signal integration expects gateway/operator flow to consume this token."

        try:
            await ctx.author.send(instructions)
            await ctx.send(f"✅ Sent your {normalized} link token via DM.")
        except discord.Forbidden:
            await ctx.send("⚠️ Couldn't DM you. Please enable DMs from server members and try again.")

    @commands.command(name="avail_unsubscribe")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def availability_unsubscribe(self, ctx, channel_type: str = None):
        """
        Disable availability notifications for a channel type.

        Usage:
            !avail_unsubscribe discord
            !avail_unsubscribe telegram
            !avail_unsubscribe signal
        """
        normalized = (channel_type or "").strip().lower()
        if normalized not in {"discord", "telegram", "signal"}:
            await ctx.send("Usage: `!avail_unsubscribe <discord|telegram|signal>`")
            return

        await self._ensure_multichannel_tables()
        user_id = int(ctx.author.id)

        rows = await self.bot.db_adapter.fetch_all(
            """
            UPDATE availability_subscriptions
            SET enabled = FALSE,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = $1
              AND channel_type = $2
              AND enabled = TRUE
            RETURNING id
            """,
            (user_id, normalized),
        )
        if rows:
            await ctx.send(f"✅ {normalized.title()} availability notifications disabled.")
        else:
            await ctx.send(f"ℹ️ No active {normalized} availability subscription was found.")
