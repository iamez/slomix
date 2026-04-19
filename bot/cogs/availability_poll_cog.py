"""
Availability Poll Cog - Daily Gaming Availability Tracker
==========================================================
Posts daily "Who can play tonight?" polls and tracks responses.

Features:
- Automated daily poll posting at configured time
- Reaction tracking (✅ Yes, ❌ No, ❔ Maybe)
- Threshold notifications when enough players commit
- Game-time reminders for opted-in players
- Per-user notification preferences

Commands:
- !poll_notify - Toggle notification preferences
- !poll_status - View today's poll results
"""

import asyncio
import logging
from datetime import date as dt_date
from zoneinfo import ZoneInfo

from discord.ext import commands

from bot.cogs.availability_mixins.daily_poll_mixin import _AvailabilityDailyPollMixin
from bot.cogs.availability_mixins.external_channels_mixin import _AvailabilityExternalChannelsMixin
from bot.cogs.availability_mixins.scheduler_mixin import _AvailabilitySchedulerMixin
from bot.cogs.availability_mixins.telegram_gateway_mixin import _AvailabilityTelegramGatewayMixin
from bot.services.availability_notifier_service import (
    UnifiedAvailabilityNotifier,
)
from website.backend.services.contact_handle_crypto import ContactHandleCrypto

logger = logging.getLogger("bot.cogs.availability_poll")


class AvailabilityPollCog(
    _AvailabilityDailyPollMixin,
    _AvailabilityExternalChannelsMixin,
    _AvailabilitySchedulerMixin,
    _AvailabilityTelegramGatewayMixin,
    commands.Cog,
    name="AvailabilityPoll",
):
    """📊 Daily gaming availability poll system"""

    def __init__(self, bot):
        """Initialize the Availability Poll Cog"""
        self.bot = bot

        # Load configuration
        self.enabled = getattr(self.bot.config, 'availability_poll_enabled', False)
        self.multichannel_enabled = getattr(self.bot.config, 'availability_multichannel_enabled', True)
        self.channel_id = getattr(self.bot.config, 'availability_poll_channel_id', 0)
        self.post_time = getattr(self.bot.config, 'availability_poll_post_time', '10:00')
        self.daily_reminder_time = getattr(self.bot.config, 'availability_daily_reminder_time', '16:00')
        try:
            tz_str = getattr(self.bot.config, 'availability_poll_timezone', 'Europe/Ljubljana')
            self.timezone = ZoneInfo(tz_str)
        except Exception:
            logger.error(f"Invalid timezone '{tz_str}', falling back to UTC")
            self.timezone = ZoneInfo('UTC')
        self.threshold = max(1, int(getattr(self.bot.config, 'availability_poll_threshold', 6)))
        self.session_ready_threshold = max(
            1,
            int(getattr(self.bot.config, 'availability_session_ready_threshold', self.threshold)),
        )
        self.scheduler_lock_key = int(getattr(self.bot.config, 'availability_scheduler_lock_key', 875211))
        reminder_str = getattr(self.bot.config, 'availability_poll_reminder_times', '20:45,21:00')
        self.reminder_times = [t.strip() for t in reminder_str.split(',')]
        self.promotion_enabled = bool(getattr(self.bot.config, "availability_promotion_enabled", True))
        self.promotion_timezone = str(
            getattr(self.bot.config, "availability_promotion_timezone", "Europe/Ljubljana")
        )
        self.promotion_reminder_time = str(
            getattr(self.bot.config, "availability_promotion_reminder_time", "20:45")
        )
        self.promotion_start_time = str(
            getattr(self.bot.config, "availability_promotion_start_time", "21:00")
        )
        self.promotion_followup_channel_id = int(
            getattr(self.bot.config, "availability_promotion_followup_channel_id", 0)
        )
        self.promotion_voice_check_enabled = bool(
            getattr(self.bot.config, "availability_promotion_voice_check_enabled", True)
        )
        self.promotion_server_check_enabled = bool(
            getattr(self.bot.config, "availability_promotion_server_check_enabled", True)
        )
        self.promotion_job_max_attempts = max(
            1,
            int(getattr(self.bot.config, "availability_promotion_job_max_attempts", 5)),
        )
        self.contact_crypto = ContactHandleCrypto.from_env()

        self.notifier = UnifiedAvailabilityNotifier(self.bot, self.bot.db_adapter, self.bot.config)

        # Runtime state
        self.active_poll_ids: set[int] = set()  # Message IDs of active polls
        self.last_check_minute: int | None = None  # Prevent duplicate checks
        self.tables_ensured: bool = False
        self.channel_failures: int = 0  # Track consecutive channel fetch failures
        self.last_daily_reminder_date: dt_date | None = None
        self.telegram_update_offset: int = 0

        logger.info(f"📊 AvailabilityPollCog initialized (enabled={self.enabled})")

        # Start task loop if enabled
        if self.enabled and self.channel_id > 0:
            self.poll_check_loop.start()
            logger.info(f"✅ Poll check loop started (post_time={self.post_time}, reminders={self.reminder_times})")
        else:
            logger.info("⚠️ Availability poll disabled or channel not configured")

        if self.multichannel_enabled:
            self.availability_scheduler_loop.start()
            logger.info(
                "✅ Multi-channel availability scheduler started (daily_reminder_time=%s, ready_threshold=%s)",
                self.daily_reminder_time,
                self.session_ready_threshold,
            )
        else:
            logger.info("⚠️ Multi-channel availability scheduler disabled")

        if self.notifier.telegram_connector.enabled:
            self.telegram_command_loop.start()
            logger.info("✅ Telegram command polling enabled for availability linking")

    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        if self.poll_check_loop.is_running():
            self.poll_check_loop.cancel()
            logger.info("🛑 Poll check loop cancelled")
        if self.availability_scheduler_loop.is_running():
            self.availability_scheduler_loop.cancel()
            logger.info("🛑 Availability scheduler loop cancelled")
        if self.telegram_command_loop.is_running():
            self.telegram_command_loop.cancel()
            logger.info("🛑 Telegram command loop cancelled")
        asyncio.create_task(self.notifier.close())


    # ------------------------------------------------------------------
    # Multi-channel availability system (date-based source of truth)
    # ------------------------------------------------------------------


async def setup(bot):
    """Setup function for loading the cog"""
    await bot.add_cog(AvailabilityPollCog(bot))
