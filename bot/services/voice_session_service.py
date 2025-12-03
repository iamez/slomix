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
from typing import Set, Optional, Dict, List
import logging

logger = logging.getLogger('VoiceSessionService')

# Phase 3: Import prediction engine
try:
    from bot.services.prediction_engine import PredictionEngine
    PREDICTION_ENGINE_AVAILABLE = True
except ImportError:
    PREDICTION_ENGINE_AVAILABLE = False
    logger.warning("⚠️ PredictionEngine not available")

# Phase 4: Import prediction embed builder
try:
    from bot.services.prediction_embed_builder import PredictionEmbedBuilder
    PREDICTION_EMBED_AVAILABLE = True
except ImportError:
    PREDICTION_EMBED_AVAILABLE = False
    logger.warning("⚠️ PredictionEmbedBuilder not available")


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

        # Team Split Detection (Phase 2: Competitive Analytics)
        self.channel_distribution: Dict[int, Set[int]] = {}  # {channel_id: {user_ids}}
        self.team_split_detected: bool = False
        self.team_a_channel_id: Optional[int] = None
        self.team_b_channel_id: Optional[int] = None
        self.team_a_guids: List[str] = []
        self.team_b_guids: List[str] = []
        self.last_split_time: Optional[datetime] = None
        self.prediction_cooldown_minutes: int = config.prediction_cooldown_minutes

        # Prediction Engine (Phase 3: Competitive Analytics)
        if PREDICTION_ENGINE_AVAILABLE and config.enable_match_predictions:
            self.prediction_engine = PredictionEngine(db_adapter)
            logger.info("✅ PredictionEngine enabled")
        else:
            self.prediction_engine = None
            if config.enable_match_predictions and not PREDICTION_ENGINE_AVAILABLE:
                logger.warning("⚠️ Match predictions enabled but engine unavailable")

        # Prediction Embed Builder (Phase 4: Discord Integration)
        if PREDICTION_EMBED_AVAILABLE:
            self.prediction_embed_builder = PredictionEmbedBuilder()
            logger.info("✅ PredictionEmbedBuilder enabled")
        else:
            self.prediction_embed_builder = None

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

        # ========== VOICE LOGGING ==========
        # Log when players join/leave gaming voice channels
        if self.config.enable_voice_logging:
            before_channel = before.channel
            after_channel = after.channel
            
            # Check if this involves a gaming voice channel
            before_is_gaming = (
                before_channel and before_channel.id in self.config.gaming_voice_channels
            )
            after_is_gaming = (
                after_channel and after_channel.id in self.config.gaming_voice_channels
            )
            
            if before_is_gaming or after_is_gaming:
                if before_channel != after_channel:
                    if after_is_gaming and not before_is_gaming:
                        # Joined a gaming channel
                        logger.info(
                            f"🔊 {member.display_name} (ID: {member.id}) "
                            f"joined #{after_channel.name}"
                        )
                    elif before_is_gaming and not after_is_gaming:
                        # Left a gaming channel
                        logger.info(
                            f"🔇 {member.display_name} (ID: {member.id}) "
                            f"left #{before_channel.name}"
                        )
                    elif before_is_gaming and after_is_gaming:
                        # Switched between gaming channels
                        logger.info(
                            f"🔀 {member.display_name} (ID: {member.id}) "
                            f"moved #{before_channel.name} → #{after_channel.name}"
                        )

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

            # ========== PHASE 2: TEAM SPLIT DETECTION ==========
            # Check for team splits during active sessions
            if self.session_active and self.config.enable_team_split_detection:
                await self._check_team_split()

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
                        "Use `!last_session` for full details!"
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

            # Check for recent database activity (within configured session gap)
            # to avoid creating duplicate "session start" messages when bot restarts
            # during an ongoing gaming session
            recent_activity = False
            if total_players >= self.config.session_start_threshold:
                cutoff_time = datetime.now() - timedelta(minutes=self.config.session_gap_minutes)
                cutoff_date = cutoff_time.strftime('%Y-%m-%d')
                cutoff_time_str = cutoff_time.strftime('%H%M%S')

                recent_round = await self.db_adapter.fetch_one(
                    """
                    SELECT id FROM rounds
                    WHERE (round_date > ? OR (round_date = ? AND round_time >= ?))
                    ORDER BY round_date DESC, round_time DESC
                    LIMIT 1
                    """,
                    (cutoff_date, cutoff_date, cutoff_time_str)
                )
                recent_activity = recent_round is not None

                if recent_activity:
                    logger.info(
                        f"✅ Detected ongoing session (database activity within last {self.config.session_gap_minutes}min) - "
                        "skipping auto-start announcement"
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

    async def _check_team_split(self):
        """
        Check for team split and update state.

        Phase 2: Competitive Analytics - Team Split Detection Handler

        Called by handle_voice_state_change() when session is active
        and team split detection is enabled.
        """
        try:
            # Detect team split
            split_data = await self._detect_team_split()

            if split_data:
                # Check if this is a NEW split or same as before
                is_new_split = (
                    not self.team_split_detected
                    or split_data['team_a_channel_id'] != self.team_a_channel_id
                    or split_data['team_b_channel_id'] != self.team_b_channel_id
                )

                # Check cooldown (don't spam if teams keep splitting)
                if self.last_split_time:
                    time_since_last = datetime.now() - self.last_split_time
                    cooldown = timedelta(minutes=self.prediction_cooldown_minutes)
                    if time_since_last < cooldown and not is_new_split:
                        logger.debug(
                            "⏳ Team split detected but in cooldown "
                            f"({time_since_last.seconds}s / {cooldown.seconds}s)"
                        )
                        return

                # Update state
                self.team_split_detected = True
                self.team_a_channel_id = split_data['team_a_channel_id']
                self.team_b_channel_id = split_data['team_b_channel_id']
                self.team_a_guids = split_data['team_a_guids']
                self.team_b_guids = split_data['team_b_guids']
                self.last_split_time = datetime.now()

                # Log event
                if is_new_split:
                    logger.info(
                        f"🎮 NEW TEAM SPLIT DETECTED! {split_data['format']} "
                        f"(Confidence: {split_data['confidence']}, "
                        f"GUID Coverage: {split_data['guid_coverage']:.0%})"
                    )
                    logger.info(
                        f"   Team A: {len(split_data['team_a_discord_ids'])} players "
                        f"({len(split_data['team_a_guids'])} mapped)"
                    )
                    logger.info(
                        f"   Team B: {len(split_data['team_b_discord_ids'])} players "
                        f"({len(split_data['team_b_guids'])} mapped)"
                    )

                    # Phase 3: Trigger prediction engine
                    if self.prediction_engine and len(split_data['team_a_guids']) > 0 and len(split_data['team_b_guids']) > 0:
                        try:
                            prediction = await self.prediction_engine.predict_match(
                                split_data['team_a_guids'],
                                split_data['team_b_guids'],
                                map_name=None  # Map detection in Phase 4
                            )

                            logger.info(
                                f"🔮 PREDICTION: Team A {prediction['team_a_win_probability']:.0%} vs "
                                f"Team B {prediction['team_b_win_probability']:.0%} "
                                f"(Confidence: {prediction['confidence']})"
                            )
                            logger.info(f"💡 Insight: {prediction['key_insight']}")

                            # Phase 4: Store prediction in database and post to Discord
                            if self.prediction_embed_builder:
                                try:
                                    # Get player names for better display
                                    player_names = await self._get_player_names(
                                        split_data['team_a_guids'] + split_data['team_b_guids']
                                    )

                                    # Build prediction embed
                                    embed = self.prediction_embed_builder.build_prediction_embed(
                                        prediction,
                                        split_data,
                                        player_names
                                    )

                                    # Post to Discord (production channel)
                                    channel = self.bot.get_channel(self.config.production_channel_id)
                                    if channel:
                                        message = await channel.send(embed=embed)
                                        discord_message_id = message.id
                                        discord_channel_id = channel.id
                                        logger.info(f"📤 Prediction posted to Discord (msg_id={discord_message_id})")
                                    else:
                                        discord_message_id = None
                                        discord_channel_id = None
                                        logger.warning("⚠️ Production channel not found, prediction not posted")

                                    # Store prediction in database
                                    session_date = datetime.now().strftime('%Y-%m-%d')
                                    prediction_id = await self.prediction_engine.store_prediction(
                                        prediction,
                                        split_data,
                                        session_date,
                                        discord_channel_id,
                                        discord_message_id
                                    )

                                    logger.info(f"✅ Prediction workflow complete (id={prediction_id})")

                                except Exception as e:
                                    logger.error(f"❌ Failed to post/store prediction: {e}", exc_info=True)

                            if self.config.enable_prediction_logging:
                                logger.debug(f"📊 Full prediction: {prediction}")

                        except Exception as e:
                            logger.error(f"❌ Prediction failed: {e}", exc_info=True)
                    elif self.config.enable_match_predictions and not self.prediction_engine:
                        logger.warning("⚠️ Predictions enabled but engine not available")
                    elif len(split_data['team_a_guids']) == 0 or len(split_data['team_b_guids']) == 0:
                        logger.warning("⚠️ Cannot predict: No GUIDs mapped for one or both teams")

            else:
                # No split detected - reset state
                if self.team_split_detected:
                    logger.info("ℹ️ Team split ended (players merged or left)")
                    self.team_split_detected = False
                    self.team_a_channel_id = None
                    self.team_b_channel_id = None
                    self.team_a_guids = []
                    self.team_b_guids = []

        except Exception as e:
            logger.error(f"❌ Error checking team split: {e}", exc_info=True)

    async def _detect_team_split(self) -> Optional[Dict]:
        """
        Detect when players split into two roughly equal team channels.

        Phase 2: Competitive Analytics - Team Split Detection

        Returns:
            {
                'team_a_discord_ids': [user_id1, user_id2, ...],
                'team_b_discord_ids': [user_id3, user_id4, ...],
                'team_a_channel_id': channel_id_1,
                'team_b_channel_id': channel_id_2,
                'team_a_guids': ['GUID1', 'GUID2', ...],
                'team_b_guids': ['GUID3', 'GUID4', ...],
                'format': '4v4',
                'confidence': 'high',
                'guid_coverage': 0.85
            }
            OR None if no valid team split detected
        """
        # 1. Count players in each gaming voice channel
        distribution = {}
        for channel_id in self.config.gaming_voice_channels:
            channel = self.bot.get_channel(channel_id)
            if channel and hasattr(channel, 'members'):
                member_ids = {m.id for m in channel.members if not m.bot}
                if member_ids:
                    distribution[channel_id] = member_ids

        # 2. Need exactly 2 active channels for team split
        if len(distribution) != 2:
            return None

        # 3. Get the two channels
        channels = list(distribution.items())
        channel_a_id, users_a = channels[0]
        channel_b_id, users_b = channels[1]

        count_a = len(users_a)
        count_b = len(users_b)
        total = count_a + count_b

        # 4. Minimum 6 players for competitive match
        if total < self.config.min_players_for_prediction:
            return None

        # 5. Teams must be roughly equal (max 1 player difference)
        if abs(count_a - count_b) > 1:
            return None

        # 6. Determine format
        format_map = {6: "3v3", 8: "4v4", 10: "5v5", 12: "6v6"}
        format_str = format_map.get(total, f"{count_a}v{count_b}")

        # 7. Resolve Discord IDs to Player GUIDs
        team_a_guids = await self._resolve_discord_ids_to_guids(list(users_a))
        team_b_guids = await self._resolve_discord_ids_to_guids(list(users_b))

        # 8. Check if we have enough GUIDs mapped
        guid_coverage = (len(team_a_guids) + len(team_b_guids)) / total
        if guid_coverage < self.config.min_guid_coverage:
            logger.warning(
                f"⚠️ Low GUID coverage ({guid_coverage:.0%}), skipping team split "
                f"(need {self.config.min_guid_coverage:.0%})"
            )
            return None

        # 9. Confidence based on balance and GUID coverage
        confidence = "high" if (count_a == count_b and guid_coverage > 0.8) else "medium"

        logger.info(
            f"✅ Team split detected: {format_str} "
            f"({count_a} vs {count_b}), "
            f"confidence={confidence}, "
            f"GUID coverage={guid_coverage:.0%}"
        )

        return {
            'team_a_discord_ids': list(users_a),
            'team_b_discord_ids': list(users_b),
            'team_a_channel_id': channel_a_id,
            'team_b_channel_id': channel_b_id,
            'team_a_guids': team_a_guids,
            'team_b_guids': team_b_guids,
            'format': format_str,
            'confidence': confidence,
            'guid_coverage': guid_coverage
        }

    async def _resolve_discord_ids_to_guids(
        self,
        discord_ids: List[int]
    ) -> List[str]:
        """
        Convert Discord user IDs to ET:Legacy player GUIDs.

        Phase 2: Competitive Analytics - GUID Resolution

        Uses the player_links table to map Discord IDs to game GUIDs.

        Args:
            discord_ids: List of Discord user IDs

        Returns:
            List of player GUIDs (skips unmapped IDs)
        """
        if not discord_ids:
            return []

        # Build query with correct number of placeholders for PostgreSQL
        placeholders = ', '.join([f'${i+1}' for i in range(len(discord_ids))])
        # nosec B608 - placeholders are parameterized, not user input
        query = f"""
            SELECT discord_id, et_guid
            FROM player_links
            WHERE discord_id IN ({placeholders})
        """

        rows = await self.db_adapter.fetch_all(query, tuple(discord_ids))

        # Build mapping
        id_to_guid = {int(row[0]): row[1] for row in rows}

        # Return GUIDs in order (skip unmapped)
        guids = []
        for discord_id in discord_ids:
            if discord_id in id_to_guid:
                guids.append(id_to_guid[discord_id])

        logger.debug(
            f"GUID resolution: {len(guids)}/{len(discord_ids)} Discord IDs mapped "
            f"({len(guids)/len(discord_ids)*100:.0f}% coverage)"
        )

        return guids

    async def _get_player_names(
        self,
        guids: List[str]
    ) -> Dict[str, str]:
        """
        Get player names for given GUIDs.

        Phase 4: Discord Integration - Player name lookup

        Args:
            guids: List of player GUIDs

        Returns:
            Dict mapping GUID to player name
        """
        if not guids:
            return {}

        try:
            # Build query with correct number of placeholders
            placeholders = ', '.join([f'${i+1}' for i in range(len(guids))])
            # nosec B608 - placeholders are parameterized integers, not user input
            query = f"""
                SELECT DISTINCT player_guid, player_name
                FROM player_comprehensive_stats
                WHERE player_guid IN ({placeholders})
                ORDER BY id DESC
            """

            rows = await self.db_adapter.fetch_all(query, tuple(guids))

            # Build mapping (use most recent name for each GUID)
            guid_to_name = {}
            for guid, name in rows:
                if guid not in guid_to_name:
                    guid_to_name[guid] = name

            logger.debug(f"Player name lookup: {len(guid_to_name)}/{len(guids)} GUIDs resolved")

            return guid_to_name

        except Exception as e:
            logger.error(f"❌ Failed to get player names: {e}", exc_info=True)
            return {}
