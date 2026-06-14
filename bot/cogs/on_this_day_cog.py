"""On This Day cog — daily scheduled throwback post (VISION_2026 S6 SPOMIN).

A single daily post (not event-driven) surfacing history from the same calendar
day in prior years. Gated by ON_THIS_DAY_ENABLED (default OFF). Mirrors the
availability daily-poll scheduling pattern (5-min loop + time window + dedup).
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from discord.ext import commands, tasks

from bot.logging_config import get_logger
from bot.services.on_this_day_service import OnThisDayService

logger = get_logger("bot.cogs.on_this_day")


class OnThisDayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        self.service = OnThisDayService(bot, bot.db_adapter, bot.config)
        try:
            self.timezone = ZoneInfo(self.config.on_this_day_timezone)
        except Exception:
            # Fall back to UTC rather than another ZoneInfo (which can also raise
            # if tzdata is missing) so the cog always starts.
            logger.warning("on-this-day: bad timezone %s — using UTC",
                           getattr(self.config, "on_this_day_timezone", "?"))
            self.timezone = timezone.utc
        self.last_check_minute = None
        self.last_posted_date = None
        if self.config.on_this_day_enabled:
            self.on_this_day_loop.start()
            logger.info("📅 On-this-day scheduler started (post_time=%s %s)",
                        self.config.on_this_day_post_time, self.config.on_this_day_timezone)

    def cog_unload(self):
        if self.on_this_day_loop.is_running():
            self.on_this_day_loop.cancel()

    @tasks.loop(minutes=5)
    async def on_this_day_loop(self):
        try:
            now = datetime.now(self.timezone)
            current_minute = now.hour * 60 + now.minute
            if self.last_check_minute == current_minute:
                return
            self.last_check_minute = current_minute

            try:
                ph, pm = map(int, self.config.on_this_day_post_time.split(":"))
            except (ValueError, AttributeError):
                logger.error("on-this-day: invalid post_time %s", self.config.on_this_day_post_time)
                return
            target = ph * 60 + pm

            # 5-minute window so non-aligned post times still fire; post once/day.
            if target <= current_minute < target + 5 and self.last_posted_date != now.date():
                self.last_posted_date = now.date()
                await self.service.generate_and_post(now.date())
        except Exception:
            logger.error("on-this-day loop error", exc_info=True)

    @on_this_day_loop.before_loop
    async def before_on_this_day_loop(self):
        await self.bot.wait_until_ready()
        self.last_check_minute = None


async def setup(bot):
    await bot.add_cog(OnThisDayCog(bot))
