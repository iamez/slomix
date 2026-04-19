"""AvailabilityPollCog mixin: Daily Discord poll via reactions — post, listeners, threshold, reminders.

Extracted from bot/cogs/availability_poll_cog.py in Mega Audit v4 / Sprint 1.

All methods live on AvailabilityPollCog via mixin inheritance.
Discord.py's CogMeta scans base classes via MRO for @commands.command,
@commands.Cog.listener, and @tasks.loop decorators, so these work unchanged.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks

from bot.logging_config import get_logger

logger = get_logger("bot.core")


class _AvailabilityDailyPollMixin:
    """Daily Discord poll via reactions — post, listeners, threshold, reminders for AvailabilityPollCog."""

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
                        "⏰ **Game time reminder!** Don't forget about tonight's gaming session. "
                        "See you soon! 🎮"
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
