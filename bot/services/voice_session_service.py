"""
Voice Session Service - Manages gaming session detection and lifecycle

This service handles:
- Voice state monitoring (detecting players in voice channels)
- Gaming session start/end detection
- 5-minute delay timer before ending sessions (bathroom breaks!)
- Startup recovery (resume sessions on bot restart)
- Discord embed notifications for session events

Extracted from ultimate_bot.py as part of Week 7-8 refactoring.
"""

import asyncio
import discord
from datetime import datetime, timedelta
from typing import Set, Optional
import logging

logger = logging.getLogger('VoiceSessionService')


class VoiceSessionService:
    """
    Manages gaming session lifecycle based on voice channel activity.

    Session Flow:
    1. 6+ players join voice → Start session
    2. <2 players remain → Start 5-minute timer
    3. Timer expires → End session
    4. Players return before timer → Cancel timer, continue session
    """

    def __init__(self, bot, config, db_adapter):
        """
        Initialize voice session service.

        Args:
            bot: Discord bot instance (for channel access and embeds)
            config: BotConfig instance (for thresholds and channel IDs)
            db_adapter: DatabaseAdapter instance (for startup queries)
        """
        self.bot = bot
        self.config = config
        self.db_adapter = db_adapter

        # Session State
        self.session_active: bool = False
        self.session_start_time: Optional[datetime] = None
        self.session_participants: Set[int] = set()  # Discord user IDs
        self.session_end_timer: Optional[asyncio.Task] = None

        logger.info("✅ VoiceSessionService initialized")

    async def handle_voice_state_change(self, member, before, after):
        """
        Handle voice state updates from Discord.

        Called by bot.on_voice_state_update() event handler.
        Detects gaming sessions based on voice channel activity.

        Args:
            member: Discord member who changed voice state
            before: Previous voice state
            after: New voice state
        """
        if not self.config.automation_enabled:
            return  # Automation disabled

        if not self.config.gaming_voice_channels:
            return  # Voice detection disabled

        try:
            # Count players in gaming voice channels
            total_players = 0
            current_participants = set()

            for channel_id in self.config.gaming_voice_channels:
                channel = self.bot.get_channel(channel_id)
                if channel and isinstance(channel, discord.VoiceChannel):
                    total_players += len(channel.members)
                    current_participants.update([m.id for m in channel.members])

            logger.debug(f"🎙️ Voice update: {total_players} players in gaming channels")

            # Session Start Detection
            if (
                total_players >= self.config.session_start_threshold
                and not self.session_active
            ):
                await self.start_session(current_participants)

            # Session End Detection
            elif (
                total_players < self.config.session_end_threshold
                and self.session_active
            ):
                # Cancel existing timer if any
                if self.session_end_timer:
                    self.session_end_timer.cancel()

                # Start 5-minute countdown
                self.session_end_timer = asyncio.create_task(
                    self.delayed_end(current_participants)
                )

            # Update participants if session active
            elif self.session_active:
                # Add new participants
                new_participants = current_participants - self.session_participants
                if new_participants:
                    self.session_participants.update(new_participants)
                    logger.info(f"👥 New participants joined: {len(new_participants)}")

                # Cancel end timer if people came back
                if (
                    self.session_end_timer
                    and total_players >= self.config.session_end_threshold
                ):
                    self.session_end_timer.cancel()
                    self.session_end_timer = None
                    logger.info(
                        f"⏰ Session end cancelled - players returned ({total_players} in voice)"
                    )

        except Exception as e:
            logger.error(f"Voice state update error: {e}", exc_info=True)

    async def start_session(self, participants: Set[int]):
        """
        Start a gaming session when threshold met.

        Args:
            participants: Set of Discord user IDs in voice channels
        """
        try:
            self.session_active = True
            self.session_start_time = discord.utils.utcnow()
            self.session_participants = participants.copy()

            # Enable monitoring (sets bot.monitoring = True)
            self.bot.monitoring = True

            logger.info(f"🎮 GAMING SESSION STARTED! {len(participants)} players detected")
            logger.info("🔄 Monitoring enabled")

            # Post to Discord if production channel configured
            if self.config.production_channel_id:
                channel = self.bot.get_channel(self.config.production_channel_id)
                if channel:
                    embed = discord.Embed(
                        title="🎮 Gaming Session Started!",
                        description=f"{len(participants)} players detected in voice channels",
                        color=0x00FF00,
                        timestamp=self.session_start_time,
                    )
                    embed.add_field(
                        name="Status",
                        value="Monitoring enabled automatically",
                        inline=False,
                    )
                    embed.set_footer(text="Good luck and have fun!")
                    await channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Error starting gaming session: {e}", exc_info=True)

    async def delayed_end(self, last_participants: Set[int]):
        """
        Wait before ending session (allows bathroom breaks).

        Waits for session_end_delay seconds (default 5 minutes), then
        re-checks player count. If still below threshold, ends session.

        Args:
            last_participants: Participants before delay started
        """
        try:
            logger.info(
                f"⏰ Session end timer started - waiting {self.config.session_end_delay}s..."
            )
            await asyncio.sleep(self.config.session_end_delay)

            # Re-check player count after delay
            total_players = 0
            for channel_id in self.config.gaming_voice_channels:
                channel = self.bot.get_channel(channel_id)
                if channel and isinstance(channel, discord.VoiceChannel):
                    total_players += len(channel.members)

            if total_players >= self.config.session_end_threshold:
                logger.info(
                    f"⏰ Session end cancelled - players returned ({total_players} in voice)"
                )
                return

            # Still empty after delay - end session
            await self.end_session()

        except asyncio.CancelledError:
            logger.debug("⏰ Session end timer cancelled")
        except Exception as e:
            logger.error(f"Error in delayed session end: {e}", exc_info=True)

    async def end_session(self):
        """End gaming session and post summary to Discord."""
        try:
            if not self.session_active:
                return

            end_time = discord.utils.utcnow()
            duration = end_time - self.session_start_time

            # Disable monitoring
            self.bot.monitoring = False

            logger.info("🏁 GAMING SESSION ENDED!")
            logger.info(f"⏱️ Duration: {duration}")
            logger.info(f"👥 Participants: {len(self.session_participants)}")
            logger.info("🔄 Monitoring disabled")

            # Post session summary
            if self.config.production_channel_id:
                channel = self.bot.get_channel(self.config.production_channel_id)
                if channel:
                    embed = discord.Embed(
                        title="🏁 Gaming Session Complete!",
                        description=f"Duration: {self._format_duration(duration)}",
                        color=0xFFD700,
                        timestamp=datetime.now(),
                    )
                    embed.add_field(
                        name="👥 Participants",
                        value=f"{len(self.session_participants)} players",
                        inline=True,
                    )
                    embed.set_footer(text="Thanks for playing! GG! 🎮")
                    await channel.send(embed=embed)

            # Reset session state
            self.session_active = False
            self.session_start_time = None
            self.session_participants = set()
            self.session_end_timer = None

        except Exception as e:
            logger.error(f"Error ending gaming session: {e}", exc_info=True)

    async def auto_end_session(self):
        """
        Auto-end session and post summary.

        NOTE: Currently unused - kept for future auto-end functionality.
        Posts notification to stats channel and attempts to link to last_session.
        """
        try:
            logger.info("🏁 Auto-ending gaming session...")

            # Mark session as ended
            self.session_active = False
            self.session_end_timer = None

            # Post session summary to Discord
            stats_channel_id = getattr(self.config, 'stats_channel_id', 0)
            channel = self.bot.get_channel(stats_channel_id)
            if not channel:
                logger.error("❌ Stats channel not found")
                return

            # Create round end notification
            embed = discord.Embed(
                title="🏁 Gaming Session Ended",
                description=(
                    "All players have left voice channels.\n"
                    "Generating session summary..."
                ),
                color=0xFF8800,
                timestamp=datetime.now(),
            )
            await channel.send(embed=embed)

            # Generate and post !last_session summary
            try:
                # Query database for most recent session
                query = """
                    SELECT DISTINCT DATE(round_date) as date
                    FROM player_comprehensive_stats
                    ORDER BY date DESC
                    LIMIT 1
                """
                row = await self.db_adapter.fetch_one(query)

                if row:
                    round_date = row[0]
                    logger.info(f"📊 Posting auto-summary for {round_date}")

                    # TODO: Use last_session logic to generate embeds
                    await channel.send(
                        f"📊 **Session Summary for {round_date}**\n"
                        f"Use `!last_session` for full details!"
                    )

                logger.info("✅ Session auto-ended successfully")

            except Exception as e:
                logger.error(f"❌ Failed to generate session summary: {e}")
                await channel.send(
                    "⚠️ Session ended but summary generation failed. "
                    "Use `!last_session` for details."
                )

        except Exception as e:
            logger.error(f"Auto-end session error: {e}")

    async def check_startup_voice_state(self):
        """
        Check voice channels on bot startup and auto-start session if players detected.

        This ensures the bot doesn't miss active sessions if it restarts
        while players are already in voice.

        Features:
        - Waits 2 seconds for Discord cache to populate
        - Counts non-bot players in gaming channels
        - Checks for recent database activity (within 60 min)
        - Auto-starts new session if threshold met and no recent activity
        - Silently resumes monitoring if ongoing session detected
        """
        try:
            if not self.config.automation_enabled or not self.config.gaming_voice_channels:
                return

            # Wait a moment for Discord cache to populate
            await asyncio.sleep(2)

            # Count players in gaming voice channels
            total_players = 0
            current_participants = set()

            for channel_id in self.config.gaming_voice_channels:
                channel = self.bot.get_channel(channel_id)
                if channel and hasattr(channel, "members"):
                    for member in channel.members:
                        if not member.bot:
                            total_players += 1
                            current_participants.add(member.id)

            logger.info(
                f"🎙️ Startup voice check: {total_players} players detected "
                f"in {len(self.config.gaming_voice_channels)} monitored channels"
            )

            # Check for recent database activity (within last 60 minutes)
            # to avoid creating duplicate "session start" messages when bot restarts
            # during an ongoing gaming session
            recent_activity = False
            if total_players >= self.config.session_start_threshold:
                cutoff_time = datetime.now() - timedelta(minutes=60)
                cutoff_date = cutoff_time.strftime('%Y-%m-%d')
                cutoff_time_str = cutoff_time.strftime('%H%M%S')

                recent_round = await self.db_adapter.fetch_one(
                    """
                    SELECT id FROM rounds
                    WHERE (round_date > $1 OR (round_date = $2 AND round_time >= $3))
                    ORDER BY round_date DESC, round_time DESC
                    LIMIT 1
                    """,
                    (cutoff_date, cutoff_date, cutoff_time_str)
                )
                recent_activity = recent_round is not None

                if recent_activity:
                    logger.info(
                        f"✅ Detected ongoing session (database activity within last 60min) - "
                        f"skipping auto-start announcement"
                    )

            # Auto-start session if threshold met AND no recent activity
            if total_players >= self.config.session_start_threshold and not self.session_active and not recent_activity:
                logger.info(
                    f"🎮 AUTO-STARTING SESSION: {total_players} players detected "
                    f"(threshold: {self.config.session_start_threshold})"
                )
                await self.start_session(current_participants)
            elif total_players >= self.config.session_start_threshold and recent_activity:
                # Resume monitoring for ongoing session without announcement
                self.session_active = True
                self.session_participants = current_participants
            elif total_players > 0:
                logger.info(
                    f"ℹ️  {total_players} players in voice but below threshold "
                    f"({self.config.session_start_threshold} needed to auto-start)"
                )

        except Exception as e:
            logger.error(f"❌ Error checking voice channels on startup: {e}", exc_info=True)

    def _format_duration(self, duration: timedelta) -> str:
        """
        Format timedelta as human-readable string.

        Args:
            duration: Time duration to format

        Returns:
            Formatted string like "2h 15m" or "45m"
        """
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
