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
import json
import re

import discord
from discord.ext import commands, tasks
import logging
from datetime import datetime, date as dt_date, time as dt_time, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Set

from bot.services.availability_notifier_service import (
    UnifiedAvailabilityNotifier,
    EVENT_DAILY_REMINDER,
    EVENT_SESSION_READY,
)
from website.backend.services.contact_handle_crypto import ContactHandleCrypto

logger = logging.getLogger("bot.cogs.availability_poll")
REMOVE_STATUS_KEYWORDS = {"REMOVE", "DELETE", "CLEAR", "UNSET", "NONE"}


class AvailabilityPollCog(commands.Cog, name="AvailabilityPoll"):
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
        self.active_poll_ids: Set[int] = set()  # Message IDs of active polls
        self.last_check_minute: Optional[int] = None  # Prevent duplicate checks
        self.tables_ensured: bool = False
        self.channel_failures: int = 0  # Track consecutive channel fetch failures
        self.last_daily_reminder_date: Optional[dt_date] = None
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

    async def _ensure_tables(self):
        """Create tables if they don't exist (idempotent)"""
        if self.tables_ensured:
            return

        try:
            # Daily polls table
            await self.bot.db_adapter.execute("""
                CREATE TABLE IF NOT EXISTS daily_polls (
                    id SERIAL PRIMARY KEY,
                    poll_date DATE NOT NULL UNIQUE,
                    channel_id BIGINT NOT NULL,
                    message_id BIGINT NOT NULL UNIQUE,
                    guild_id BIGINT NOT NULL,
                    threshold_reached BOOLEAN DEFAULT FALSE,
                    threshold_notified_at TIMESTAMP,
                    reminder_sent_at TIMESTAMP,
                    event_id BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Poll responses table
            await self.bot.db_adapter.execute("""
                CREATE TABLE IF NOT EXISTS poll_responses (
                    id SERIAL PRIMARY KEY,
                    poll_id INTEGER NOT NULL,
                    discord_user_id BIGINT NOT NULL,
                    discord_username TEXT,
                    response_type TEXT NOT NULL CHECK (response_type IN ('yes', 'no', 'tentative')),
                    responded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(poll_id, discord_user_id)
                )
            """)

            # Reminder preferences table
            await self.bot.db_adapter.execute("""
                CREATE TABLE IF NOT EXISTS poll_reminder_preferences (
                    discord_user_id BIGINT PRIMARY KEY,
                    discord_username TEXT,
                    threshold_notify BOOLEAN DEFAULT TRUE,
                    game_time_notify BOOLEAN DEFAULT TRUE,
                    notify_method TEXT DEFAULT 'dm' CHECK (notify_method IN ('dm', 'channel', 'none')),
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Indexes
            await self.bot.db_adapter.execute("CREATE INDEX IF NOT EXISTS idx_daily_polls_date ON daily_polls(poll_date DESC)")
            await self.bot.db_adapter.execute("CREATE INDEX IF NOT EXISTS idx_poll_responses_poll ON poll_responses(poll_id)")
            await self.bot.db_adapter.execute("CREATE INDEX IF NOT EXISTS idx_poll_responses_user ON poll_responses(discord_user_id)")
            await self.bot.db_adapter.execute("CREATE INDEX IF NOT EXISTS idx_poll_responses_type ON poll_responses(response_type)")

            self.tables_ensured = True
            logger.info("✅ Poll tables verified/created")

        except Exception as e:
            logger.error(f"Failed to ensure poll tables: {e}", exc_info=True)
            raise

    async def _load_active_polls(self):
        """Load active poll message IDs from database for fast reaction lookup"""
        try:
            # Load polls from last 7 days
            cutoff = datetime.now(self.timezone).date() - timedelta(days=7)
            query = "SELECT message_id FROM daily_polls WHERE poll_date >= ?"
            results = await self.bot.db_adapter.fetch_all(query, (cutoff,))

            self.active_poll_ids = {row[0] for row in results}
            logger.info(f"📊 Loaded {len(self.active_poll_ids)} active poll message IDs")

        except Exception as e:
            logger.error(f"Failed to load active polls: {e}", exc_info=True)

    @tasks.loop(minutes=5)
    async def poll_check_loop(self):
        """Check every 5 minutes for scheduled tasks"""
        try:
            await self._ensure_tables()
            await self._load_active_polls()

            now = datetime.now(self.timezone)
            current_minute = now.hour * 60 + now.minute

            # Prevent duplicate checks in same minute
            if self.last_check_minute == current_minute:
                return
            self.last_check_minute = current_minute

            # Check if it's time to post daily poll (use window to handle non-5min-aligned times)
            try:
                post_hour, post_minute = map(int, self.post_time.split(':'))
                post_time_minutes = post_hour * 60 + post_minute
            except (ValueError, AttributeError):
                logger.error(f"Invalid post_time format: {self.post_time}")
                return

            if post_time_minutes <= current_minute < post_time_minutes + 5:
                await self._post_daily_poll(now.date())

            # Check if it's time for any reminders
            current_time_str = f"{now.hour:02d}:{now.minute:02d}"
            if current_time_str in self.reminder_times:
                await self._send_reminders(now.date())

        except Exception as e:
            logger.error(f"Error in poll check loop: {e}", exc_info=True)

    @poll_check_loop.before_loop
    async def before_poll_check_loop(self):
        """Wait for bot to be ready before starting loop"""
        await self.bot.wait_until_ready()
        self.last_check_minute = None  # Reset on loop start

    async def _post_daily_poll(self, poll_date):
        """Post the daily availability poll"""
        try:
            # Check if poll already exists for today
            existing = await self.bot.db_adapter.fetch_one(
                "SELECT id FROM daily_polls WHERE poll_date = ?",
                (poll_date,)
            )

            if existing:
                logger.debug(f"Poll already exists for {poll_date}")
                return

            # Get channel with failure tracking
            channel = self.bot.get_channel(self.channel_id)
            if not channel:
                self.channel_failures += 1
                if self.channel_failures >= 5:
                    logger.critical(f"Poll channel {self.channel_id} unavailable for 5 consecutive attempts. Stopping loop.")
                    self.poll_check_loop.cancel()
                else:
                    logger.error(f"Could not find poll channel {self.channel_id} (attempt {self.channel_failures}/5)")
                return
            self.channel_failures = 0

            # Create embed
            embed = discord.Embed(
                title="🎮 Who can play tonight?",
                description=(
                    "React with your availability for today's gaming session!\n\n"
                    "✅ **Yes** — I'm in!\n"
                    "❌ **No** — Can't make it\n"
                    "❔ **Maybe** — Depends on timing"
                ),
                color=0x3B82F6,  # Brand blue
                timestamp=datetime.now(tz=self.timezone)
            )
            embed.set_footer(text=f"Poll for {poll_date.strftime('%A, %B %d')}")

            # Post message
            message = await channel.send(embed=embed)

            # Add reactions
            await message.add_reaction("✅")
            await message.add_reaction("❌")
            await message.add_reaction("❔")

            # Store in database
            await self.bot.db_adapter.execute(
                """INSERT INTO daily_polls
                   (poll_date, channel_id, message_id, guild_id)
                   VALUES (?, ?, ?, ?)""",
                (poll_date, channel.id, message.id, channel.guild.id)
            )

            # Add to active polls
            self.active_poll_ids.add(message.id)

            logger.info(f"✅ Posted daily poll for {poll_date} (msg_id={message.id})")

        except Exception as e:
            logger.error(f"Failed to post daily poll: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Track poll reactions (survives bot restarts)"""
        try:
            # Skip bot's own reactions
            if payload.user_id == self.bot.user.id:
                return

            # Check if this is a poll message
            if payload.message_id not in self.active_poll_ids:
                return

            # Map emoji to response type
            emoji_map = {
                "✅": "yes",
                "❌": "no",
                "❔": "tentative"
            }

            response_type = emoji_map.get(str(payload.emoji))
            if not response_type:
                return

            # Get poll ID
            poll = await self.bot.db_adapter.fetch_one(
                "SELECT id FROM daily_polls WHERE message_id = ?",
                (payload.message_id,)
            )

            if not poll:
                logger.warning(f"Poll not found for message {payload.message_id}")
                return

            poll_id = poll[0]

            # Get user info
            try:
                user = await self.bot.fetch_user(payload.user_id)
                username = f"{user.name}#{user.discriminator}" if user.discriminator != "0" else user.name
            except Exception:
                username = f"User#{payload.user_id}"

            # UPSERT response (INSERT ON CONFLICT UPDATE)
            await self.bot.db_adapter.execute(
                """INSERT INTO poll_responses
                   (poll_id, discord_user_id, discord_username, response_type, responded_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT (poll_id, discord_user_id)
                   DO UPDATE SET
                       response_type = EXCLUDED.response_type,
                       responded_at = EXCLUDED.responded_at,
                       discord_username = EXCLUDED.discord_username""",
                (poll_id, payload.user_id, username, response_type, datetime.now(self.timezone))
            )

            logger.info(f"📊 {username} reacted {payload.emoji} to poll {poll_id}")

            # Check threshold
            await self._check_threshold(poll_id, payload.message_id)

        except Exception as e:
            logger.error(f"Error handling reaction add: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Remove poll response when reaction is removed"""
        try:
            # Skip bot's own reactions
            if payload.user_id == self.bot.user.id:
                return

            # Check if this is a poll message
            if payload.message_id not in self.active_poll_ids:
                return

            # Map emoji to response type
            emoji_map = {
                "✅": "yes",
                "❌": "no",
                "❔": "tentative"
            }

            response_type = emoji_map.get(str(payload.emoji))
            if not response_type:
                return

            # Get poll ID
            poll = await self.bot.db_adapter.fetch_one(
                "SELECT id FROM daily_polls WHERE message_id = ?",
                (payload.message_id,)
            )

            if not poll:
                return

            poll_id = poll[0]

            # Only delete if removed emoji matches stored response type
            await self.bot.db_adapter.execute(
                "DELETE FROM poll_responses WHERE poll_id = ? AND discord_user_id = ? AND response_type = ?",
                (poll_id, payload.user_id, response_type)
            )

            logger.info(f"📊 User {payload.user_id} removed reaction from poll {poll_id}")

        except Exception as e:
            logger.error(f"Error handling reaction remove: {e}", exc_info=True)

    async def _check_threshold(self, poll_id: int, message_id: int):
        """Check if threshold is reached and send notifications"""
        try:
            # Get poll info
            poll_info = await self.bot.db_adapter.fetch_one(
                """SELECT threshold_reached, threshold_notified_at
                   FROM daily_polls WHERE id = ?""",
                (poll_id,)
            )

            if not poll_info:
                return

            threshold_reached, threshold_notified_at = poll_info

            # Already notified
            if threshold_notified_at:
                return

            # Count YES responses
            yes_count = await self.bot.db_adapter.fetch_one(
                "SELECT COUNT(*) FROM poll_responses WHERE poll_id = ? AND response_type = 'yes'",
                (poll_id,)
            )

            yes_count = yes_count[0] if yes_count else 0

            # Check if threshold reached - use WHERE threshold_notified_at IS NULL
            # to prevent race condition with concurrent reactions
            if yes_count >= self.threshold:
                # Atomic check-and-set to prevent double notifications
                updated = await self.bot.db_adapter.fetch_one(
                    """UPDATE daily_polls
                       SET threshold_reached = TRUE, threshold_notified_at = ?
                       WHERE id = ? AND threshold_notified_at IS NULL
                       RETURNING id""",
                    (datetime.now(self.timezone), poll_id)
                )
                if not updated:
                    return  # Another handler already notified

                # Get users to notify (YES or TENTATIVE, opted-in)
                notify_users = await self.bot.db_adapter.fetch_all(
                    """SELECT DISTINCT pr.discord_user_id, pr.discord_username
                       FROM poll_responses pr
                       LEFT JOIN poll_reminder_preferences prp ON pr.discord_user_id = prp.discord_user_id
                       WHERE pr.poll_id = ?
                         AND pr.response_type IN ('yes', 'tentative')
                         AND (prp.threshold_notify IS NULL OR prp.threshold_notify = TRUE)
                         AND (prp.notify_method IS NULL OR prp.notify_method = 'dm')""",
                    (poll_id,)
                )

                # Send DMs with rate limit protection
                notification_count = 0
                for user_id, username in notify_users:
                    try:
                        user = await self.bot.fetch_user(user_id)
                        await user.send(
                            f"🎮 **Game on!** {yes_count} players are ready to play tonight. "
                            f"See you in-game! 🔥"
                        )
                        notification_count += 1
                        await asyncio.sleep(0.25)  # Rate limit protection
                    except discord.Forbidden:
                        logger.warning(f"Could not DM user {username} ({user_id}) - DMs closed")
                    except discord.HTTPException as e:
                        if e.status == 429:
                            retry_after = getattr(e, 'retry_after', 5.0)
                            logger.warning(f"Rate limited sending DM, waiting {retry_after}s")
                            await asyncio.sleep(retry_after)
                        else:
                            logger.error(f"Error sending threshold notification to {user_id}: {e}")
                    except Exception as e:
                        logger.error(f"Error sending threshold notification to {user_id}: {e}")

                logger.info(f"✅ Threshold reached for poll {poll_id} ({yes_count} players). Sent {notification_count} DMs.")

        except Exception as e:
            logger.error(f"Error checking threshold: {e}", exc_info=True)

    async def _send_reminders(self, poll_date):
        """Send game-time reminders to opted-in players"""
        try:
            # Get today's poll
            poll = await self.bot.db_adapter.fetch_one(
                "SELECT id, reminder_sent_at FROM daily_polls WHERE poll_date = ?",
                (poll_date,)
            )

            if not poll:
                logger.debug(f"No poll found for {poll_date} to send reminders")
                return

            poll_id, reminder_sent_at = poll

            # Check if reminder already sent
            if reminder_sent_at:
                logger.debug(f"Reminder already sent for poll {poll_id}")
                return

            # Get users to remind (YES or TENTATIVE, opted-in for game time)
            remind_users = await self.bot.db_adapter.fetch_all(
                """SELECT DISTINCT pr.discord_user_id, pr.discord_username
                   FROM poll_responses pr
                   LEFT JOIN poll_reminder_preferences prp ON pr.discord_user_id = prp.discord_user_id
                   WHERE pr.poll_id = ?
                     AND pr.response_type IN ('yes', 'tentative')
                     AND (prp.game_time_notify IS NULL OR prp.game_time_notify = TRUE)
                     AND (prp.notify_method IS NULL OR prp.notify_method = 'dm')""",
                (poll_id,)
            )

            # Send reminders with rate limit protection
            reminder_count = 0
            for user_id, username in remind_users:
                try:
                    user = await self.bot.fetch_user(user_id)
                    await user.send(
                        f"⏰ **Game time reminder!** Don't forget about tonight's gaming session. "
                        f"See you soon! 🎮"
                    )
                    reminder_count += 1
                    await asyncio.sleep(0.25)  # Rate limit protection
                except discord.Forbidden:
                    logger.warning(f"Could not DM user {username} ({user_id}) - DMs closed")
                except discord.HTTPException as e:
                    if e.status == 429:
                        retry_after = getattr(e, 'retry_after', 5.0)
                        logger.warning(f"Rate limited sending reminder, waiting {retry_after}s")
                        await asyncio.sleep(retry_after)
                    else:
                        logger.error(f"Error sending reminder to {user_id}: {e}")
                except Exception as e:
                    logger.error(f"Error sending reminder to {user_id}: {e}")

            # Update poll
            await self.bot.db_adapter.execute(
                "UPDATE daily_polls SET reminder_sent_at = ? WHERE id = ?",
                (datetime.now(self.timezone), poll_id)
            )

            logger.info(f"✅ Sent {reminder_count} game-time reminders for poll {poll_id}")

        except Exception as e:
            logger.error(f"Error sending reminders: {e}", exc_info=True)

    @commands.command(name="poll_notify")
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def toggle_notifications(self, ctx, setting: str = None):
        """
        Toggle availability poll notifications

        Usage:
            !poll_notify           → Show current settings
            !poll_notify on        → Enable all notifications
            !poll_notify off       → Disable all notifications
            !poll_notify threshold → Toggle threshold notifications only
            !poll_notify reminder  → Toggle game-time reminders only
        """
        try:
            user_id = ctx.author.id
            username = f"{ctx.author.name}#{ctx.author.discriminator}" if ctx.author.discriminator != "0" else ctx.author.name

            # Get current preferences
            prefs = await self.bot.db_adapter.fetch_one(
                "SELECT threshold_notify, game_time_notify FROM poll_reminder_preferences WHERE discord_user_id = ?",
                (user_id,)
            )

            if not prefs:
                # Create default preferences
                await self.bot.db_adapter.execute(
                    """INSERT INTO poll_reminder_preferences
                       (discord_user_id, discord_username, threshold_notify, game_time_notify, notify_method)
                       VALUES (?, ?, TRUE, TRUE, 'dm')""",
                    (user_id, username)
                )
                prefs = (True, True)

            threshold_notify, game_time_notify = prefs

            # Handle setting change
            if setting and setting.lower() in ('on', 'off', 'threshold', 'reminder'):
                if setting.lower() == 'on':
                    threshold_notify = True
                    game_time_notify = True
                elif setting.lower() == 'off':
                    threshold_notify = False
                    game_time_notify = False
                elif setting.lower() == 'threshold':
                    threshold_notify = not threshold_notify
                elif setting.lower() == 'reminder':
                    game_time_notify = not game_time_notify

                # Update preferences
                await self.bot.db_adapter.execute(
                    """UPDATE poll_reminder_preferences
                       SET threshold_notify = ?, game_time_notify = ?, updated_at = ?
                       WHERE discord_user_id = ?""",
                    (threshold_notify, game_time_notify, datetime.now(self.timezone), user_id)
                )

            # Show current settings
            embed = discord.Embed(
                title="📊 Poll Notification Settings",
                color=0x3B82F6
            )
            embed.add_field(
                name="Threshold Notifications",
                value="✅ Enabled" if threshold_notify else "❌ Disabled",
                inline=True
            )
            embed.add_field(
                name="Game-Time Reminders",
                value="✅ Enabled" if game_time_notify else "❌ Disabled",
                inline=True
            )
            embed.set_footer(text="Use !poll_notify on/off/threshold/reminder to change")

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in poll_notify command: {e}", exc_info=True)
            await ctx.send(f"❌ Error updating notification settings: {e}")

    @commands.command(name="poll_status")
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def poll_status(self, ctx):
        """Show today's poll results"""
        try:
            today = datetime.now(self.timezone).date()

            # Get today's poll
            poll = await self.bot.db_adapter.fetch_one(
                "SELECT id, message_id, threshold_reached FROM daily_polls WHERE poll_date = ?",
                (today,)
            )

            if not poll:
                await ctx.send("❌ No poll found for today.")
                return

            poll_id, message_id, threshold_reached = poll

            # Get response counts
            responses = await self.bot.db_adapter.fetch_all(
                """SELECT response_type, COUNT(*)
                   FROM poll_responses
                   WHERE poll_id = ?
                   GROUP BY response_type""",
                (poll_id,)
            )

            response_dict = {resp_type: count for resp_type, count in responses}
            yes_count = response_dict.get('yes', 0)
            no_count = response_dict.get('no', 0)
            tentative_count = response_dict.get('tentative', 0)

            # Create embed
            embed = discord.Embed(
                title=f"📊 Poll Status - {today.strftime('%A, %B %d')}",
                color=0x10B981 if threshold_reached else 0x3B82F6
            )

            embed.add_field(name="✅ Yes", value=str(yes_count), inline=True)
            embed.add_field(name="❌ No", value=str(no_count), inline=True)
            embed.add_field(name="❔ Maybe", value=str(tentative_count), inline=True)

            if threshold_reached:
                embed.add_field(
                    name="🎉 Status",
                    value=f"Threshold reached! ({yes_count}/{self.threshold} players)",
                    inline=False
                )
            else:
                remaining = self.threshold - yes_count
                embed.add_field(
                    name="📈 Progress",
                    value=f"{remaining} more player{'s' if remaining != 1 else ''} needed to reach threshold ({self.threshold})",
                    inline=False
                )

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in poll_status command: {e}", exc_info=True)
            await ctx.send(f"❌ Error fetching poll status: {e}")

    # ------------------------------------------------------------------
    # Multi-channel availability system (date-based source of truth)
    # ------------------------------------------------------------------

    async def _ensure_multichannel_tables(self):
        await self.notifier.ensure_tables()
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
    def _normalize_status_input(raw_status: str) -> Optional[str]:
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
    def _parse_date_arg(raw_date: str, now_date: dt_date) -> Optional[dt_date]:
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
    def _normalize_operation_input(raw_status: str) -> tuple[Optional[str], Optional[str]]:
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
        status = AvailabilityPollCog._normalize_status_input(normalized)
        if status:
            return "SET", status
        return None, None

    @staticmethod
    def _parse_availability_operation(args: list[str], now_date: dt_date) -> tuple[Optional[dt_date], Optional[str], Optional[str]]:
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
        first_op, _ = AvailabilityPollCog._normalize_operation_input(first)

        if first_op == "REMOVE":
            target_date = AvailabilityPollCog._parse_date_arg(second, now_date)
            if target_date is None:
                return None, None, None
            return target_date, "REMOVE", None

        target_date = AvailabilityPollCog._parse_date_arg(first, now_date)
        if target_date is None:
            return None, None, None

        status_text = " ".join(args[1:]).strip()
        operation, status = AvailabilityPollCog._normalize_operation_input(status_text)
        if operation is None:
            return None, None, None
        return target_date, operation, status

    async def _resolve_linked_user_from_channel(self, *, channel_type: str, channel_address: str) -> Optional[int]:
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

    async def _run_scheduler_with_lock(self, now: datetime) -> None:
        lock_acquired = False
        try:
            lock_row = await self.bot.db_adapter.fetch_one(
                "SELECT pg_try_advisory_lock($1)",
                (self.scheduler_lock_key,),
            )
            lock_acquired = bool(lock_row and lock_row[0])
        except Exception:
            # SQLite/local adapters do not support advisory locks.
            lock_acquired = True

        if not lock_acquired:
            return

        try:
            today = now.date()
            if self._is_reminder_due(now):
                if self.last_daily_reminder_date != today:
                    await self._send_daily_reminder(today)
                    self.last_daily_reminder_date = today
            await self._check_session_ready(today)
            if self.promotion_enabled:
                await self._process_promotion_jobs(now)
        finally:
            try:
                await self.bot.db_adapter.fetch_one(
                    "SELECT pg_advisory_unlock($1)",
                    (self.scheduler_lock_key,),
                )
            except Exception:
                pass

    def _is_reminder_due(self, now: datetime) -> bool:
        try:
            hour, minute = map(int, self.daily_reminder_time.split(":"))
        except (TypeError, ValueError):
            return False
        return now.hour == hour and now.minute == minute

    async def _send_daily_reminder(self, today: dt_date) -> None:
        rows = await self.bot.db_adapter.fetch_all(
            "SELECT discord_id FROM player_links WHERE discord_id IS NOT NULL",
        )
        user_ids = [int(row[0]) for row in (rows or []) if row[0]]
        if not user_ids:
            return

        event_key = self.notifier.build_event_key(EVENT_DAILY_REMINDER, today)
        message = (
            "🎮 Availability check-in: set your status for today and tomorrow "
            "on the website or with !avail."
        )
        announce = (
            "📣 Daily availability reminder is out. "
            "Set status on the website or run `!avail today LOOKING`."
        )
        result = await self.notifier.notify_users(
            event_type=EVENT_DAILY_REMINDER,
            event_key=event_key,
            message=message,
            user_ids=user_ids,
            payload={"date": today.isoformat()},
            announce_message=announce,
        )
        logger.info(
            "Daily reminder dispatched: sent=%s failed=%s skipped=%s",
            result.sent,
            result.failed,
            result.skipped,
        )

    async def _check_session_ready(self, today: dt_date) -> None:
        count_row = await self.bot.db_adapter.fetch_one(
            "SELECT COUNT(*) FROM availability_entries WHERE entry_date = $1 AND status = 'LOOKING'",
            (today,),
        )
        looking_count = int(count_row[0]) if count_row else 0
        if looking_count < self.session_ready_threshold:
            return

        event_key = self.notifier.build_event_key(
            EVENT_SESSION_READY,
            today,
            qualifier=f"threshold={self.session_ready_threshold}",
        )

        users = await self.bot.db_adapter.fetch_all(
            """
            SELECT DISTINCT user_id
            FROM availability_entries
            WHERE entry_date = $1
              AND status IN ('LOOKING', 'AVAILABLE', 'MAYBE')
            """,
            (today,),
        )
        user_ids = [int(row[0]) for row in (users or []) if row[0]]
        if not user_ids:
            return

        message = (
            f"🔥 Session ready for {today.isoformat()}: "
            f"{looking_count} players marked Looking."
        )
        announce = (
            f"🔥 Session ready: {looking_count} players are looking to play "
            f"(threshold {self.session_ready_threshold})."
        )
        result = await self.notifier.notify_users(
            event_type=EVENT_SESSION_READY,
            event_key=event_key,
            message=message,
            user_ids=user_ids,
            payload={
                "date": today.isoformat(),
                "looking_count": looking_count,
                "threshold": self.session_ready_threshold,
            },
            announce_message=announce,
        )
        logger.info(
            "Session-ready notifications dispatched: sent=%s failed=%s skipped=%s",
            result.sent,
            result.failed,
            result.skipped,
        )

    @staticmethod
    def _decode_json_dict(value) -> dict:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                loaded = json.loads(value)
                if isinstance(loaded, dict):
                    return loaded
            except json.JSONDecodeError:
                return {}
        return {}

    @staticmethod
    def _decode_json_list(value) -> list[dict]:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, str):
            try:
                loaded = json.loads(value)
                if isinstance(loaded, list):
                    return [item for item in loaded if isinstance(item, dict)]
            except json.JSONDecodeError:
                return []
        return []

    @staticmethod
    def _normalize_name_for_match(name: str | None) -> str:
        text = str(name or "").strip().lower()
        text = re.sub(r"\^[0-9]", "", text)
        text = re.sub(r"[^a-z0-9]+", "", text)
        return text

    @staticmethod
    def _is_time_in_quiet_window(local_time: dt_time, quiet_start: dt_time, quiet_end: dt_time) -> bool:
        """Evaluate quiet-hours windows, including overnight ranges (e.g. 23:00-08:00)."""
        current_minutes = (local_time.hour * 60) + local_time.minute
        start_minutes = (quiet_start.hour * 60) + quiet_start.minute
        end_minutes = (quiet_end.hour * 60) + quiet_end.minute

        if start_minutes == end_minutes:
            return True
        if start_minutes < end_minutes:
            return start_minutes <= current_minutes < end_minutes
        return current_minutes >= start_minutes or current_minutes < end_minutes

    def _recipient_in_quiet_hours_now(self, recipient: dict, *, now_utc: datetime | None = None) -> bool:
        quiet_hours = recipient.get("quiet_hours")
        if not isinstance(quiet_hours, dict):
            quiet_hours = self._decode_json_dict(quiet_hours)

        start_raw = str(quiet_hours.get("start") or "").strip()
        end_raw = str(quiet_hours.get("end") or "").strip()
        if not start_raw or not end_raw:
            return False
        if not re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", start_raw):
            return False
        if not re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", end_raw):
            return False

        start_hour, start_minute = map(int, start_raw.split(":"))
        end_hour, end_minute = map(int, end_raw.split(":"))
        quiet_start = dt_time(hour=start_hour, minute=start_minute)
        quiet_end = dt_time(hour=end_hour, minute=end_minute)

        timezone_name = str(recipient.get("timezone") or self.promotion_timezone or "Europe/Ljubljana").strip()
        try:
            recipient_tz = ZoneInfo(timezone_name)
        except Exception:
            recipient_tz = self.timezone

        reference_utc = now_utc or datetime.now(timezone.utc)
        if reference_utc.tzinfo is None:
            reference_utc = reference_utc.replace(tzinfo=timezone.utc)
        local_now = reference_utc.astimezone(recipient_tz).time().replace(tzinfo=None)

        return self._is_time_in_quiet_window(local_now, quiet_start, quiet_end)

    @staticmethod
    def _coerce_campaign_date(value) -> dt_date:
        if isinstance(value, dt_date):
            return value
        return dt_date.fromisoformat(str(value)[:10])

    @staticmethod
    def _promotion_event_key(*, campaign_date: dt_date, phase: str) -> str:
        return f"PROMOTE:{phase}:{campaign_date.isoformat()}"

    async def _process_promotion_jobs(self, now: datetime) -> None:
        now_utc = now.astimezone(timezone.utc)
        rows = await self.bot.db_adapter.fetch_all(
            """
            SELECT id, campaign_id, job_type
            FROM availability_promotion_jobs
            WHERE status = 'pending'
              AND run_at <= $1
            ORDER BY run_at ASC, id ASC
            LIMIT 20
            """,
            (now_utc,),
        )
        if not rows:
            return

        for row in rows:
            job_id = int(row[0])
            campaign_id = int(row[1])
            job_type = str(row[2])

            claim = await self.bot.db_adapter.fetch_one(
                """
                UPDATE availability_promotion_jobs
                SET status = 'running',
                    attempts = COALESCE(attempts, 0) + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $1
                  AND status = 'pending'
                RETURNING attempts, max_attempts
                """,
                (job_id,),
            )
            if not claim:
                continue

            attempts = int(claim[0] or 0)
            max_attempts = int(claim[1] or self.promotion_job_max_attempts)

            try:
                campaign = await self.bot.db_adapter.fetch_one(
                    """
                    SELECT id,
                           campaign_date,
                           initiated_by_user_id,
                           initiated_by_discord_id,
                           dry_run,
                           status,
                           recipients_snapshot
                    FROM availability_promotion_campaigns
                    WHERE id = $1
                    LIMIT 1
                    """,
                    (campaign_id,),
                )
                if not campaign:
                    await self.bot.db_adapter.execute(
                        """
                        UPDATE availability_promotion_jobs
                        SET status = 'skipped',
                            sent_at = CURRENT_TIMESTAMP,
                            last_error = 'campaign not found',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = $1
                        """,
                        (job_id,),
                    )
                    continue

                campaign_date = self._coerce_campaign_date(campaign[1])
                recipients = self._decode_json_list(campaign[6])
                if job_type in {"send_reminder_2045", "send_start_2100"}:
                    sent, failed = await self._dispatch_promotion_notification(
                        campaign_id=campaign_id,
                        job_id=job_id,
                        job_type=job_type,
                        campaign_date=campaign_date,
                        recipients=recipients,
                    )
                    await self.bot.db_adapter.execute(
                        """
                        UPDATE availability_promotion_jobs
                        SET status = $1,
                            sent_at = CURRENT_TIMESTAMP,
                            last_error = NULL,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = $2
                        """,
                        ("failed" if sent == 0 and failed > 0 else "sent", job_id),
                    )
                    if job_type == "send_start_2100":
                        campaign_status = "sent" if failed == 0 else ("partial" if sent > 0 else "failed")
                        await self.bot.db_adapter.execute(
                            """
                            UPDATE availability_promotion_campaigns
                            SET status = $1,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = $2
                            """,
                            (campaign_status, campaign_id),
                        )
                elif job_type == "voice_check_2100":
                    await self._dispatch_voice_check_followup(
                        campaign_id=campaign_id,
                        job_id=job_id,
                        campaign_date=campaign_date,
                        recipients=recipients,
                        initiated_by_discord_id=int(campaign[3]),
                    )
                    await self.bot.db_adapter.execute(
                        """
                        UPDATE availability_promotion_jobs
                        SET status = 'sent',
                            sent_at = CURRENT_TIMESTAMP,
                            last_error = NULL,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = $1
                        """,
                        (job_id,),
                    )
                    await self.bot.db_adapter.execute(
                        """
                        UPDATE availability_promotion_campaigns
                        SET status = 'followup_sent',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = $1
                        """,
                        (campaign_id,),
                    )
                else:
                    await self.bot.db_adapter.execute(
                        """
                        UPDATE availability_promotion_jobs
                        SET status = 'skipped',
                            sent_at = CURRENT_TIMESTAMP,
                            last_error = 'unsupported job type',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = $1
                        """,
                        (job_id,),
                    )
            except Exception as exc:
                error_text = str(exc).strip()[:1200]
                retry_status = "pending" if attempts < max_attempts else "failed"
                await self.bot.db_adapter.execute(
                    """
                    UPDATE availability_promotion_jobs
                    SET status = $1,
                        last_error = $2,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = $3
                    """,
                    (retry_status, error_text, job_id),
                )
                logger.warning(
                    "Promotion job failed id=%s campaign=%s type=%s attempts=%s/%s error=%s",
                    job_id,
                    campaign_id,
                    job_type,
                    attempts,
                    max_attempts,
                    error_text,
                )

    async def _dispatch_promotion_notification(
        self,
        *,
        campaign_id: int,
        job_id: int,
        job_type: str,
        campaign_date: dt_date,
        recipients: list[dict],
    ) -> tuple[int, int]:
        sent = 0
        failed = 0
        phase = "T-15" if job_type == "send_reminder_2045" else "T0"
        event_key = self._promotion_event_key(campaign_date=campaign_date, phase=phase)
        message = (
            "Session reminder: kickoff is at 21:00 CET (in 15 minutes). "
            "Join voice if you're available."
            if job_type == "send_reminder_2045"
            else "Session starts now (21:00 CET). Join voice and game server when ready."
        )

        for recipient in recipients:
            user_id = int(recipient.get("user_id") or 0)
            channel_type = str(recipient.get("selected_channel") or "discord").lower()
            if self._recipient_in_quiet_hours_now(recipient):
                await self._log_promotion_send(
                    campaign_id=campaign_id,
                    job_id=job_id,
                    user_id=user_id,
                    channel_type=channel_type,
                    status="skipped",
                    message_id=None,
                    error="recipient in quiet hours",
                    payload={"job_type": job_type},
                )
                continue
            target = self._promotion_target_for_recipient(recipient, channel_type)
            if not target:
                await self._log_promotion_send(
                    campaign_id=campaign_id,
                    job_id=job_id,
                    user_id=user_id,
                    channel_type=channel_type,
                    status="skipped",
                    message_id=None,
                    error="missing delivery target",
                    payload={"job_type": job_type},
                )
                continue

            try:
                status, message_id = await self.notifier.send_via_channel_idempotent(
                    user_id=user_id,
                    event_key=event_key,
                    channel_type=channel_type,
                    target=target,
                    message=message,
                    payload={
                        "campaign_id": int(campaign_id),
                        "job_type": job_type,
                    },
                )
                if status == "sent":
                    sent += 1
                elif status == "failed":
                    failed += 1
                await self._log_promotion_send(
                    campaign_id=campaign_id,
                    job_id=job_id,
                    user_id=user_id,
                    channel_type=channel_type,
                    status=status,
                    message_id=str(message_id or ""),
                    error=None if status != "skipped" else "idempotent skip",
                    payload={"job_type": job_type, "event_key": event_key},
                )
            except Exception as exc:
                failed += 1
                await self._log_promotion_send(
                    campaign_id=campaign_id,
                    job_id=job_id,
                    user_id=user_id,
                    channel_type=channel_type,
                    status="failed",
                    message_id=None,
                    error=str(exc)[:1200],
                    payload={"job_type": job_type, "event_key": event_key},
                )
        return sent, failed

    def _promotion_target_for_recipient(self, recipient: dict, channel_type: str) -> Optional[str]:
        if channel_type == "discord":
            user_id = int(recipient.get("user_id") or 0)
            return str(user_id) if user_id > 0 else None

        if channel_type == "telegram":
            encrypted = recipient.get("telegram_handle_encrypted")
            return self.contact_crypto.decrypt(encrypted)
        if channel_type == "signal":
            encrypted = recipient.get("signal_handle_encrypted")
            return self.contact_crypto.decrypt(encrypted)
        return None

    async def _dispatch_voice_check_followup(
        self,
        *,
        campaign_id: int,
        job_id: int,
        campaign_date: dt_date,
        recipients: list[dict],
        initiated_by_discord_id: int,
    ) -> None:
        if not self.promotion_voice_check_enabled:
            return

        expected_by_id: dict[int, dict] = {}
        for recipient in recipients:
            user_id = int(recipient.get("user_id") or 0)
            if user_id > 0:
                expected_by_id[user_id] = recipient
        if not expected_by_id:
            return

        voice_row = await self.bot.db_adapter.fetch_one(
            """
            SELECT status_data
            FROM live_status
            WHERE status_type = 'voice_channel'
            LIMIT 1
            """
        )
        voice_members = []
        if voice_row and voice_row[0]:
            voice_payload = self._decode_json_dict(voice_row[0])
            voice_members = voice_payload.get("members") if isinstance(voice_payload.get("members"), list) else []

        voice_member_ids: set[int] = set()
        voice_member_names: list[str] = []
        for member in voice_members:
            if not isinstance(member, dict):
                continue
            raw_id = member.get("id") or member.get("discord_id")
            try:
                member_id = int(raw_id)
            except (TypeError, ValueError):
                member_id = None
            if member_id is not None:
                voice_member_ids.add(member_id)
            name = str(member.get("name") or "").strip()
            if name:
                voice_member_names.append(name)

        missing_ids = sorted(user_id for user_id in expected_by_id if user_id not in voice_member_ids)
        if not missing_ids:
            return

        missing_names = [
            str(expected_by_id[user_id].get("display_name") or f"User {user_id}")
            for user_id in missing_ids
        ]

        in_server_not_voice: list[str] = []
        if self.promotion_server_check_enabled:
            server_row = await self.bot.db_adapter.fetch_one(
                """
                SELECT status_data
                FROM live_status
                WHERE status_type = 'game_server'
                LIMIT 1
                """
            )
            server_names: set[str] = set()
            if server_row and server_row[0]:
                server_payload = self._decode_json_dict(server_row[0])
                players = server_payload.get("players") if isinstance(server_payload.get("players"), list) else []
                for player in players:
                    if isinstance(player, dict):
                        server_names.add(self._normalize_name_for_match(player.get("name")))
            for name in missing_names:
                if self._normalize_name_for_match(name) in server_names:
                    in_server_not_voice.append(name)

        targeted_message_base = "We're starting now (21:00 CET). Join voice if you can."
        targeted_sent = 0
        followup_event_key = self._promotion_event_key(campaign_date=campaign_date, phase="FOLLOWUP")
        for user_id in missing_ids:
            recipient = expected_by_id[user_id]
            channel_type = str(recipient.get("selected_channel") or "discord").lower()

            if self._recipient_in_quiet_hours_now(recipient):
                await self._log_promotion_send(
                    campaign_id=campaign_id,
                    job_id=job_id,
                    user_id=user_id,
                    channel_type=channel_type,
                    status="skipped",
                    message_id=None,
                    error="recipient in quiet hours",
                    payload={"job_type": "voice_check_2100"},
                )
                continue

            target = self._promotion_target_for_recipient(recipient, channel_type)
            if not target:
                await self._log_promotion_send(
                    campaign_id=campaign_id,
                    job_id=job_id,
                    user_id=user_id,
                    channel_type=channel_type,
                    status="skipped",
                    message_id=None,
                    error="missing delivery target",
                    payload={"job_type": "voice_check_2100"},
                )
                continue

            display_name = str(recipient.get("display_name") or f"User {user_id}")
            direct_message = targeted_message_base
            if display_name in in_server_not_voice:
                direct_message += " You're in server but not in voice."

            try:
                status, message_id = await self.notifier.send_via_channel_idempotent(
                    user_id=user_id,
                    event_key=followup_event_key,
                    channel_type=channel_type,
                    target=target,
                    message=direct_message,
                    payload={
                        "campaign_id": int(campaign_id),
                        "job_type": "voice_check_2100",
                    },
                )
                if status == "sent":
                    targeted_sent += 1
                await self._log_promotion_send(
                    campaign_id=campaign_id,
                    job_id=job_id,
                    user_id=user_id,
                    channel_type=channel_type,
                    status=status,
                    message_id=str(message_id or ""),
                    error=None if status != "skipped" else "idempotent skip",
                    payload={"job_type": "voice_check_2100", "event_key": followup_event_key},
                )
            except Exception as exc:
                await self._log_promotion_send(
                    campaign_id=campaign_id,
                    job_id=job_id,
                    user_id=user_id,
                    channel_type=channel_type,
                    status="failed",
                    message_id=None,
                    error=str(exc)[:1200],
                    payload={"job_type": "voice_check_2100", "event_key": followup_event_key},
                )

        followup_parts = [f"We're waiting on: {', '.join(missing_names)}."]
        if voice_member_names:
            followup_parts.append(f"In voice now: {', '.join(voice_member_names[:12])}.")
        if in_server_not_voice:
            followup_parts.append(f"In server but not in voice: {', '.join(in_server_not_voice)}.")
        followup_parts.append(f"Direct follow-up sent: {targeted_sent}/{len(missing_ids)}.")
        message = " ".join(followup_parts)

        channel_id = int(
            self.promotion_followup_channel_id
            or self.notifier.discord_announce_channel_id
            or self.channel_id
            or 0
        )
        if channel_id > 0:
            try:
                summary_status, summary_message_id = await self.notifier.send_discord_channel_idempotent(
                    channel_id=channel_id,
                    event_key=followup_event_key,
                    message=message,
                    payload={
                        "campaign_id": int(campaign_id),
                        "job_type": "voice_check_2100",
                        "missing_count": len(missing_names),
                        "targeted_sent": targeted_sent,
                    },
                )
                await self._log_promotion_send(
                    campaign_id=campaign_id,
                    job_id=job_id,
                    user_id=int(initiated_by_discord_id),
                    channel_type="discord",
                    status=summary_status,
                    message_id=str(summary_message_id or ""),
                    error=None if summary_status != "skipped" else "idempotent skip",
                    payload={
                        "job_type": "voice_check_2100",
                        "event_key": followup_event_key,
                        "missing_count": len(missing_names),
                        "targeted_sent": targeted_sent,
                    },
                )
            except Exception as exc:
                await self._log_promotion_send(
                    campaign_id=campaign_id,
                    job_id=job_id,
                    user_id=int(initiated_by_discord_id),
                    channel_type="discord",
                    status="failed",
                    message_id=None,
                    error=str(exc)[:1200],
                    payload={
                        "job_type": "voice_check_2100",
                        "missing_count": len(missing_names),
                        "targeted_sent": targeted_sent,
                    },
                )

    async def _log_promotion_send(
        self,
        *,
        campaign_id: int,
        job_id: int,
        user_id: int,
        channel_type: str,
        status: str,
        message_id: str | None,
        error: str | None,
        payload: dict,
    ) -> None:
        payload_json = json.dumps(payload or {}, ensure_ascii=True)
        await self.bot.db_adapter.execute(
            """
            INSERT INTO availability_promotion_send_logs
                (campaign_id, job_id, user_id, channel_type, status, message_id, error, payload, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, CAST($8 AS JSONB), CURRENT_TIMESTAMP)
            """,
            (
                int(campaign_id),
                int(job_id),
                int(user_id or 0),
                str(channel_type),
                str(status),
                message_id,
                error,
                payload_json,
            ),
        )

    @tasks.loop(minutes=1)
    async def availability_scheduler_loop(self):
        if not self.multichannel_enabled:
            return

        try:
            await self._ensure_multichannel_tables()
            now = datetime.now(self.timezone)
            await self._run_scheduler_with_lock(now)
        except Exception as exc:
            logger.error("Error in availability scheduler loop: %s", exc, exc_info=True)

    @availability_scheduler_loop.before_loop
    async def before_availability_scheduler_loop(self):
        await self.bot.wait_until_ready()

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
            await ctx.send(f"⚠️ Couldn't DM you. Here is the token (delete after use): `{token}`")

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


async def setup(bot):
    """Setup function for loading the cog"""
    await bot.add_cog(AvailabilityPollCog(bot))
