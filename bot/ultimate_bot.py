#!/usr/bin/env python3
"""
ULTIMATE ET:LEGACY DISCORD BOT - COG-BASED VERSION

This module contains the ET:Legacy discord bot commands. The file is large
and contains many helper classes and Cog commands. Only minimal top-level
initialization is present here; heavy lifting is done inside Cog methods.
"""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime

import io
import discord
from discord.ext import commands, tasks

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.stopwatch_scoring import StopwatchScoring

# Import extracted core classes
from bot.core import StatsCache, SeasonManager, AchievementSystem

# Import database adapter and config for PostgreSQL migration
from bot.core.database_adapter import create_adapter, DatabaseAdapter
from bot.config import load_config
from bot.stats import StatsCalculator
from bot.automation import SSHHandler, FileTracker

# Load environment variables if available
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# ==================== COMPREHENSIVE LOGGING SETUP ====================

# Import our custom logging configuration
from bot.logging_config import (
    setup_logging,
    log_command_execution,
    log_database_operation,
    log_stats_import,
    log_performance_warning,
    get_logger
)

# Setup comprehensive logging system
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
setup_logging(getattr(logging, log_level))

# Get bot logger
logger = get_logger("bot.core")
logger.info("🚀 ET:LEGACY DISCORD BOT - STARTING UP")
logger.info(f"📝 Log Level: {log_level}")
logger.info(f"� Python: {sys.version}")
logger.info(f"📦 Discord.py: {discord.__version__}")

# ======================================================================


async def ensure_player_name_alias(db: "aiosqlite.Connection") -> None:
    """Create a TEMP VIEW aliasing an existing name column to `player_name`.

    This standalone helper mirrors the Cog method and can be used by
    non-Cog code paths that open their own DB connections (where `self`
    isn't available).
    """
    try:
        async with db.execute(
            "PRAGMA table_info('player_comprehensive_stats')"
        ) as cur:
            cols = await cur.fetchall()

        col_names = [c[1] for c in cols]
        if "player_name" in col_names:
            return

        # Common alternate name columns we've seen in older DBs
        candidates = [
            "player_name",
            "clean_name",
            "clean_name_final",
            "clean_name_normalized",
            "name",
            "player",
            "display_name",
        ]
        # Pick the first candidate present in the table
        alt = next((c for c in candidates if c in col_names), None)
        if not alt:
            logger.warning(
                "player_comprehensive_stats missing 'player_name' and no alternative found"
            )
            return

        tmp_tbl_sql = (
            f"CREATE TEMP TABLE tmp_player_comprehensive_stats AS "
            f"SELECT *, {alt} AS player_name FROM main.player_comprehensive_stats"
        )
        view_sql = "CREATE TEMP VIEW player_comprehensive_stats AS SELECT * FROM tmp_player_comprehensive_stats"

        await db.execute(tmp_tbl_sql)
        await db.execute(view_sql)
        await db.commit()
        logger.info(
            f"Created TEMP VIEW player_comprehensive_stats aliasing {alt} -> player_name via tmp table"
        )
    except Exception:
        logger.exception(
            "Failed to create TEMP VIEW alias for player_name; queries may still fail"
        )


def _split_chunks(s: str, max_len: int = 900):
    """Split a long string into line-preserving chunks under max_len.

    Used by embed helpers to avoid Discord field size limits.
    """
    lines = s.splitlines(keepends=True)
    chunks = []
    cur = ""
    for line in lines:
        if len(cur) + len(line) > max_len:
            chunks.append(cur.rstrip())
            cur = line
        else:
            cur += line
    if cur:
        chunks.append(cur.rstrip())
    return chunks


# ============================================================================
# 🚀 PERFORMANCE: QUERY CACHE
# ============================================================================
# NOTE: StatsCache has been extracted to bot/core/stats_cache.py
# ============================================================================
# 📅 SEASON SYSTEM: QUARTERLY COMPETITION RESETS
# ============================================================================
# EXTRACTED: SeasonManager class moved to bot/core/season_manager.py
# Imported at top of file: from bot.core import SeasonManager


# ============================================================================
# 🏆 ACHIEVEMENTS: MILESTONE TRACKING & NOTIFICATIONS
# ============================================================================
# EXTRACTED: AchievementSystem class moved to bot/core/achievement_system.py
# Imported at top of file: from bot.core import AchievementSystem


class UltimateETLegacyBot(commands.Bot):
    """🚀 Ultimate consolidated ET:Legacy Discord bot with proper Cog structure"""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

        # 📊 Database Configuration - Load config and create adapter
        import os
        
        # Load configuration (from env vars or bot_config.json)
        self.config = load_config()
        logger.info(f"✅ Configuration loaded: {self.config}")
        
        # Create PostgreSQL database adapter
        adapter_kwargs = self.config.get_database_adapter_kwargs()
        self.db_adapter = create_adapter(**adapter_kwargs)
        logger.info(f"✅ PostgreSQL adapter created: {self.config.postgres_host}:{self.config.postgres_port}/{self.config.postgres_database}")

        # No db_path needed for PostgreSQL
        self.db_path = None

        # 🎮 Bot State
        self.bot_startup_time = datetime.now()  # Track when bot started (for auto-import filtering)
        self.current_session = None
        self.processed_files = set()
        self.auto_link_enabled = True
        self.gather_queue = {"3v3": [], "6v6": []}

        # 📊 Core Systems (for Cogs)
        self.stats_cache = StatsCache(ttl_seconds=300)
        self.season_manager = SeasonManager()
        self.achievements = AchievementSystem(self)
        self.file_tracker = FileTracker(
            self.db_adapter, self.config, self.bot_startup_time, self.processed_files
        )
        logger.info("✅ Core systems initialized (cache, seasons, achievements, file_tracker)")

        # 🤖 Automation System Flags (OFF by default for dev/testing)
        self.automation_enabled = (
            os.getenv("AUTOMATION_ENABLED", "false").lower() == "true"
        )
        self.ssh_enabled = os.getenv("SSH_ENABLED", "false").lower() == "true"
        
        # Enable monitoring when SSH is enabled (for auto stats posting)
        self.monitoring = self.ssh_enabled

        if self.automation_enabled:
            logger.info("✅ Automation system ENABLED")
        else:
            logger.warning(
                "⚠️ Automation system DISABLED (set AUTOMATION_ENABLED=true to enable)"
            )
        # �️ Voice Channel Session Detection
        self.session_active = False
        self.session_start_time = None
        self.session_participants = set()  # Discord user IDs
        self.session_end_timer = None  # For 5-minute buffer
        
        # SSH monitoring optimization - counter-based intervals
        self.ssh_check_counter = 0  # Tracks cycles for interval-based checking

        # Load gaming voice channel IDs from .env
        gaming_channels_str = os.getenv("GAMING_VOICE_CHANNELS", "")
        self.gaming_voice_channels = (
            [
                int(ch.strip())
                for ch in gaming_channels_str.split(",")
                if ch.strip()
            ]
            if gaming_channels_str
            else []
        )

        # Load allowed bot command channels from .env
        bot_channels_str = os.getenv("BOT_COMMAND_CHANNELS", "")
        self.bot_command_channels = (
            [
                int(ch.strip())
                for ch in bot_channels_str.split(",")
                if ch.strip()
            ]
            if bot_channels_str
            else []
        )

        # Session thresholds
        self.session_start_threshold = int(
            os.getenv("SESSION_START_THRESHOLD", "6")
        )
        self.session_end_threshold = int(
            os.getenv("SESSION_END_THRESHOLD", "2")
        )
        self.session_end_delay = int(
            os.getenv("SESSION_END_DELAY", "300")
        )  # 5 minutes

        if self.gaming_voice_channels:
            logger.info(
                f"🎙️ Voice monitoring enabled for channels: {self.gaming_voice_channels}"
            )
            logger.info(
                f"📊 Thresholds: {self.session_start_threshold}+ to start, <{self.session_end_threshold} for {self.session_end_delay}s to end"
            )
        
        if self.bot_command_channels:
            logger.info(
                f"🔒 Bot commands restricted to channels: {self.bot_command_channels}"
            )
        else:
            logger.warning(
                "⚠️ No gaming voice channels configured - voice detection disabled"
            )

        # �🏆 Awards and achievements tracking
        self.awards_cache = {}
        self.mvp_cache = {}

        # 📈 Performance tracking
        self.command_stats = {}
        self.error_count = 0

    async def close(self):
        """
        🔌 Clean up database connections and close bot gracefully
        """
        try:
            if hasattr(self, 'db_adapter'):
                await self.db_adapter.close()
                logger.info("✅ Database adapter closed successfully")
        except Exception as e:
            logger.error(f"⚠️ Error closing database adapter: {e}")
        
        # Call parent close
        await super().close()

    async def validate_database_schema(self):
        """
        ✅ CRITICAL: Validate database has correct unified schema (54 columns)
        Prevents silent failures if wrong schema is used
        Supports both SQLite and PostgreSQL
        """
        try:
            # Query schema based on database type
            if self.config.database_type == 'sqlite':
                # SQLite: Use PRAGMA table_info
                query = "PRAGMA table_info(player_comprehensive_stats)"
                columns = await self.db_adapter.fetch_all(query)
                column_names = [col[1] for col in columns]
            else:
                # PostgreSQL: Query information_schema
                query = """
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'player_comprehensive_stats' 
                    ORDER BY ordinal_position
                """
                columns = await self.db_adapter.fetch_all(query)
                column_names = [col[0] for col in columns]

            expected_columns = 54
            actual_columns = len(column_names)

            if actual_columns != expected_columns:
                error_msg = (
                    f"❌ DATABASE SCHEMA MISMATCH!\n"
                    f"Expected: {expected_columns} columns (UNIFIED)\n"
                    f"Found: {actual_columns} columns\n\n"
                    f"Schema: {'SPLIT (deprecated)' if actual_columns == 35 else 'UNKNOWN'}\n\n"
                    f"Solution:\n"
                    f"1. Backup database\n"
                    f"2. Run schema conversion script\n"
                    f"3. Re-import data\n"
                )

                logger.error(error_msg)
                raise RuntimeError(error_msg)

            # Verify objective stats columns exist
            required_stats = [
                "kill_assists",
                "dynamites_planted",
                "times_revived",
                "revives_given",
                "most_useful_kills",
                "useless_kills",
            ]

            missing = [
                col for col in required_stats if col not in column_names
            ]
            if missing:
                logger.error(f"❌ MISSING COLUMNS: {missing}")
                raise RuntimeError(f"Missing objective stats: {missing}")

            logger.info(
                f"✅ Schema validated: {actual_columns} columns (UNIFIED) on {self.config.database_type.upper()}"
            )

        except Exception as e:
            logger.error(f"❌ Schema validation failed: {e}")
            raise

    async def send_with_delay(self, ctx, *args, delay=0.5, **kwargs):
        """✅ Send message with rate limit delay"""
        await ctx.send(*args, **kwargs)
        await asyncio.sleep(delay)

    async def setup_hook(self):
        """🔧 Initialize all bot components"""
        logger.info("🚀 Initializing Ultimate ET:Legacy Bot...")

        # 🔌 Connect database adapter (required for PostgreSQL pool)
        try:
            await self.db_adapter.connect()
            logger.info("✅ Database adapter connected successfully")
        except Exception as e:
            logger.error(f"❌ Failed to connect database adapter: {e}")
            raise

        # ✅ CRITICAL: Validate schema FIRST
        await self.validate_database_schema()


        # � Load Admin Cog (database operations, maintenance commands)
        try:
            from bot.cogs.admin_cog import AdminCog
            await self.add_cog(AdminCog(self))
            logger.info("✅ Admin Cog loaded (11 admin commands)")
        except Exception as e:
            logger.error(f"❌ Failed to load Admin Cog: {e}", exc_info=True)

        # 🔗 Load Link Cog (player account linking and management)
        try:
            from bot.cogs.link_cog import LinkCog
            await self.add_cog(LinkCog(self))
            logger.info("✅ Link Cog loaded (link, unlink, select, list_players, find_player)")
        except Exception as e:
            logger.error(f"❌ Failed to load Link Cog: {e}", exc_info=True)

        # �📊 Load Stats Cog (general statistics, comparisons, achievements, seasons)
        try:
            from bot.cogs.stats_cog import StatsCog
            await self.add_cog(StatsCog(self))
            logger.info("✅ Stats Cog loaded (ping, check_achievements, compare, season_info, help_command)")
        except Exception as e:
            logger.error(f"❌ Failed to load Stats Cog: {e}", exc_info=True)

        # 🏆 Load Leaderboard Cog (player stats and rankings)
        try:
            from bot.cogs.leaderboard_cog import LeaderboardCog
            await self.add_cog(LeaderboardCog(self))
            logger.info("✅ Leaderboard Cog loaded (stats, leaderboard)")
        except Exception as e:
            logger.error(f"❌ Failed to load Leaderboard Cog: {e}", exc_info=True)

        # � Load Session Cog (session viewing and analytics)
        try:
            from bot.cogs.session_cog import SessionCog
            await self.add_cog(SessionCog(self))
            logger.info("✅ Session Cog loaded (session, sessions)")
        except Exception as e:
            logger.error(f"❌ Failed to load Session Cog: {e}", exc_info=True)

        # 🎮 Load Last Round Cog (comprehensive last session analytics)
        try:
            from bot.cogs.last_session_cog import LastSessionCog
            await self.add_cog(LastSessionCog(self))
            logger.info("✅ Last Round Cog loaded (last_session with multiple view modes)")
        except Exception as e:
            logger.error(f"❌ Failed to load Last Round Cog: {e}", exc_info=True)

        # Load Sync Cog
        try:
            from bot.cogs.sync_cog import SyncCog
            await self.add_cog(SyncCog(self))
            logger.info('Sync Cog loaded')
        except Exception as e:
            logger.error(f'Failed to load Sync Cog: {e}', exc_info=True)


        # Load Session Management Cog
        try:
            from bot.cogs.session_management_cog import SessionManagementCog
            await self.add_cog(SessionManagementCog(self))
            logger.info('Session Management Cog loaded (session_start, session_end)')
        except Exception as e:
            logger.error(f'Failed to load Session Management Cog: {e}', exc_info=True)

        # Load Team Management Cog (manual commands)
        try:
            from bot.cogs.team_management_cog import TeamManagementCog
            await self.add_cog(TeamManagementCog(self))
            logger.info('Team Management Cog loaded (set_teams, assign_player)')
        except Exception as e:
            logger.error(f'Failed to load Team Management Cog: {e}', exc_info=True)
        
        # Load Team System Cog (comprehensive team tracking)
        try:
            from bot.cogs.team_cog import TeamCog
            await self.add_cog(TeamCog(self))
            logger.info('✅ Team System Cog loaded (teams, lineup_changes, session_score)')
        except Exception as e:
            logger.error(f'Failed to load Team System Cog: {e}', exc_info=True)
        # �🎯 FIVEEYES: Load synergy analytics cog (SAFE - disabled by default)
        try:
            await self.load_extension("cogs.synergy_analytics")
            logger.info(
                "✅ FIVEEYES synergy analytics cog loaded (disabled by default)"
            )
        except Exception as e:
            logger.warning(f"⚠️  Could not load FIVEEYES cog: {e}")
            logger.warning(
                "Bot will continue without synergy analytics features"
            )

        # 🎮 SERVER CONTROL: Load server control cog (optional)
        try:
            await self.load_extension("cogs.server_control")
            logger.info("✅ Server Control cog loaded")
        except Exception as e:
            logger.warning(f"⚠️  Could not load Server Control cog: {e}")
            logger.warning("Bot will continue without server control features")

        # 🤖 AUTOMATION: Initialize automation services
        try:
            from bot.services.automation import SSHMonitor, HealthMonitor, MetricsLogger, DatabaseMaintenance

            # Get configuration from environment
            admin_channel_id = int(os.getenv("ADMIN_CHANNEL_ID", "0"))

            # For PostgreSQL, we don't have a db_path, but metrics_logger needs one for its own SQLite db
            # Use a sensible default path for metrics database
            metrics_db_path = os.getenv("METRICS_DB_PATH", "bot/data/metrics.db")

            # Create automation services in correct order (MetricsLogger first, it's needed by HealthMonitor)
            self.metrics = MetricsLogger(db_path=metrics_db_path)
            self.ssh_monitor = SSHMonitor(self)
            self.health_monitor = HealthMonitor(self, admin_channel_id, self.metrics)
            self.db_maintenance = DatabaseMaintenance(self, self.db_path or "bot/data/etlegacy.db", admin_channel_id)

            logger.info("✅ Automation services initialized (SSH, Health, Metrics, DB Maintenance)")

            # Load automation commands cog
            await self.load_extension("cogs.automation_commands")
            logger.info("✅ Automation Commands cog loaded")

            # Auto-start SSH monitoring if enabled
            logger.info(f"🔍 Bot ssh_enabled={self.ssh_enabled} (from SSH_ENABLED env var)")
            if self.ssh_enabled:
                logger.info("🔄 SSH monitoring enabled - starting automatically...")
                await self.ssh_monitor.start_monitoring()
            else:
                logger.info("⏭️ SSH monitoring not enabled, skipping auto-start")

        except Exception as e:
            logger.warning(f"⚠️  Could not initialize automation services: {e}", exc_info=True)
            logger.warning("Bot will continue without automation features")

        # Initialize database
        await self.initialize_database()

        # Sync existing local files to processed_files table
        await self.file_tracker.sync_local_files_to_processed_table()

        # Start background tasks (only if not already running)
        if not self.endstats_monitor.is_running():
            self.endstats_monitor.start()
        if not self.cache_refresher.is_running():
            self.cache_refresher.start()
        # scheduled_monitoring_check task removed - see performance optimization
        # voice_session_monitor disabled - using on_voice_state_update event instead (more efficient)
        # if not self.voice_session_monitor.is_running():
        #     self.voice_session_monitor.start()
        logger.info("✅ Background tasks started (optimized SSH monitoring with voice detection)")

        logger.info("✅ Ultimate Bot initialization complete!")
        logger.info(
            f"📋 Commands available: {[cmd.name for cmd in self.commands]}"
        )

    async def initialize_database(self):
        """📊 Verify database tables exist (created by recreate_database.py)"""
        # Verify critical tables exist
        required_tables = [
            "rounds",
            "player_comprehensive_stats",
            "weapon_comprehensive_stats",
            "player_links",
            "processed_files",
        ]

        # Query depends on database type
        if self.config.database_type == 'sqlite':
            query = """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name IN (?, ?, ?, ?, ?)
            """
        else:
            # PostgreSQL: Query information_schema
            query = """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name IN ($1, $2, $3, $4, $5)
            """

        rows = await self.db_adapter.fetch_all(query, tuple(required_tables))
        existing_tables = [row[0] for row in rows]

        missing_tables = set(required_tables) - set(existing_tables)

        if missing_tables:
            logger.error(f"❌ Missing required tables: {missing_tables}")
            logger.error("   Run: python recreate_database.py")
            logger.error("   Then: python tools/simple_bulk_import.py")
            raise Exception(
                f"Database missing required tables: {missing_tables}"
            )

            logger.info(
                f"✅ Database verified - all {len(required_tables)} required tables exist"
            )

    # 🎙️ VOICE CHANNEL SESSION DETECTION

    async def on_voice_state_update(self, member, before, after):
        """🎙️ Detect gaming sessions based on voice channel activity"""
        if not self.automation_enabled:
            return  # Automation disabled

        if not self.gaming_voice_channels:
            return  # Voice detection disabled

        try:
            # Count players in gaming voice channels
            total_players = 0
            current_participants = set()

            for channel_id in self.gaming_voice_channels:
                channel = self.get_channel(channel_id)
                if channel and isinstance(channel, discord.VoiceChannel):
                    total_players += len(channel.members)
                    current_participants.update(
                        [m.id for m in channel.members]
                    )

            logger.debug(
                f"🎙️ Voice update: {total_players} players in gaming channels"
            )

            # Session Start Detection
            if (
                total_players >= self.session_start_threshold
                and not self.session_active
            ):
                await self._start_gaming_session(current_participants)

            # Session End Detection
            elif (
                total_players < self.session_end_threshold
                and self.session_active
            ):
                # Cancel existing timer if any
                if self.session_end_timer:
                    self.session_end_timer.cancel()

                # Start 5-minute countdown
                self.session_end_timer = asyncio.create_task(
                    self._delayed_session_end(current_participants)
                )

            # Update participants if session active
            elif self.session_active:
                # Add new participants
                new_participants = (
                    current_participants - self.session_participants
                )
                if new_participants:
                    self.session_participants.update(new_participants)
                    logger.info(
                        f"👥 New participants joined: {len(new_participants)}"
                    )

                # Cancel end timer if people came back
                if (
                    self.session_end_timer
                    and total_players >= self.session_end_threshold
                ):
                    self.session_end_timer.cancel()
                    self.session_end_timer = None
                    logger.info(
                        f"⏰ Session end cancelled - players returned ({total_players} in voice)"
                    )

        except Exception as e:
            logger.error(f"Voice state update error: {e}", exc_info=True)

    async def _start_gaming_session(self, participants):
        """🎮 Start a gaming session when 6+ players in voice"""
        try:
            self.session_active = True
            self.session_start_time = discord.utils.utcnow()
            self.session_participants = participants.copy()

            # Enable monitoring
            self.monitoring = True

            logger.info(
                f"🎮 GAMING SESSION STARTED! {len(participants)} players detected"
            )
            logger.info("🔄 Monitoring enabled")

            # Post to Discord if stats channel configured
            stats_channel_id = os.getenv("STATS_CHANNEL_ID")
            if stats_channel_id:
                channel = self.get_channel(int(stats_channel_id))
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
                    embed.set_footer(text="Good luck and have fun! �")
                    await channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Error starting gaming session: {e}", exc_info=True)

    async def _delayed_session_end(self, last_participants):
        """⏰ Wait 5 minutes before ending session (allows bathroom breaks)"""
        try:
            logger.info(
                f"⏰ Session end timer started - waiting {self.session_end_delay}s..."
            )
            await asyncio.sleep(self.session_end_delay)

            # Re-check player count after delay
            total_players = 0
            for channel_id in self.gaming_voice_channels:
                channel = self.get_channel(channel_id)
                if channel and isinstance(channel, discord.VoiceChannel):
                    total_players += len(channel.members)

            if total_players >= self.session_end_threshold:
                logger.info(
                    f"⏰ Session end cancelled - players returned ({total_players} in voice)"
                )
                return

            # Still empty after delay - end session
            await self._end_gaming_session()

        except asyncio.CancelledError:
            logger.debug("⏰ Session end timer cancelled")
        except Exception as e:
            logger.error(f"Error in delayed session end: {e}", exc_info=True)

    async def _end_gaming_session(self):
        """🏁 End gaming session and post summary"""
        try:
            if not self.session_active:
                return

            end_time = discord.utils.utcnow()
            duration = end_time - self.session_start_time

            # Disable monitoring
            self.monitoring = False

            logger.info("🏁 GAMING SESSION ENDED!")
            logger.info(f"⏱️ Duration: {duration}")
            logger.info(f"👥 Participants: {len(self.session_participants)}")
            logger.info("�🔄 Monitoring disabled")

            # Post session summary (will be implemented in next todo)
            stats_channel_id = os.getenv("STATS_CHANNEL_ID")
            if stats_channel_id:
                channel = self.get_channel(int(stats_channel_id))
                if channel:
                    # TODO: Post comprehensive session summary
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

    def _format_duration(self, duration):
        """Format timedelta as human-readable string"""
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

    # � SSH MONITORING HELPER METHODS

    # NOTE: SSH operations moved to bot/automation/ssh_handler.py
    # - SSHHandler.parse_gamestats_filename()
    # - SSHHandler.list_remote_files()
    # - SSHHandler.download_file()

    async def process_gamestats_file(self, local_path, filename):
        """
        Process a gamestats file: parse and import to database

        Returns:
            dict with keys: success, round_id, player_count, error
        """
        try:
            logger.info(f"⚙️ Processing {filename}...")

            # 🔥 FIX: Use PostgreSQL database manager instead of bot's own import logic
            # This ensures proper transaction handling and constraint checks
            if self.config.database_type == "postgres":
                from postgresql_database_manager import PostgreSQLDatabase
                from pathlib import Path
                
                # Create database manager instance (reuses existing pool)
                db_config = {
                    'host': self.config.postgres_host,
                    'port': self.config.postgres_port,
                    'database': self.config.postgres_database,
                    'user': self.config.postgres_user,
                    'password': self.config.postgres_password
                }
                
                db_manager = PostgreSQLDatabase(db_config)
                await db_manager.connect()
                
                # 🔧 FIX: Use process_file() not import_stats_file() (method doesn't exist!)
                success, message = await db_manager.process_file(Path(local_path))
                
                await db_manager.disconnect()
                
                if not success:
                    raise Exception(f"Import failed: {message}")
                
                # Parse file to get player count for return value
                from community_stats_parser import C0RNP0RN3StatsParser
                parser = C0RNP0RN3StatsParser()
                stats_data = parser.parse_stats_file(local_path)
                
                # Mark as processed
                try:
                    await self.file_tracker.mark_processed(filename, success=True)
                    self.processed_files.add(filename)
                except Exception as e:
                    logger.debug(f"Failed to mark {filename} as processed: {e}")
                
                return {
                    "success": True,
                    "round_id": None,  # Database manager doesn't return round_id
                    "player_count": len(stats_data.get("players", [])) if stats_data else 0,
                    "error": None,
                    "stats_data": stats_data if stats_data else {},
                }
            else:
                # SQLite fallback - use old import logic
                from community_stats_parser import C0RNP0RN3StatsParser

                # Parse using existing parser (it reads the file itself)
                parser = C0RNP0RN3StatsParser()
                stats_data = parser.parse_stats_file(local_path)

                if not stats_data or stats_data.get("error"):
                    error_msg = (
                        stats_data.get("error") if stats_data else "No data"
                    )
                    raise Exception(f"Parser error: {error_msg}")

                # Import to database using existing import logic
                round_id = await self._import_stats_to_db(stats_data, filename)
                # Mark file as processed only after successful import
                try:
                    await self.file_tracker.mark_processed(filename, success=True)
                    self.processed_files.add(filename)
                except Exception as e:
                    logger.debug(f"Failed to mark {filename} as processed: {e}")

                return {
                    "success": True,
                    "round_id": round_id,
                    "player_count": len(stats_data.get("players", [])),
                    "error": None,
                    "stats_data": stats_data,
                }

        except Exception as e:
            logger.error(f"❌ Processing failed: {e}")
            return {
                "success": False,
                "round_id": None,
                "player_count": 0,
                "error": str(e),
                "stats_data": None,
            }

    async def post_round_stats_auto(self, filename: str, result: dict):
        """
        🆕 Auto-post round statistics to Discord after processing
        
        Called automatically by endstats_monitor after successful file processing.
        Shows ALL players with detailed stats.
        """
        try:
            logger.debug(f"📤 Preparing Discord post for {filename}")
            
            # Get the stats channel
            stats_channel_id = int(os.getenv("STATS_CHANNEL_ID", 0))
            if not stats_channel_id:
                logger.warning("⚠️ STATS_CHANNEL_ID not configured, skipping Discord post")
                return
            
            logger.debug(f"📡 Looking for channel ID: {stats_channel_id}")
            channel = self.get_channel(stats_channel_id)
            if not channel:
                logger.error(f"❌ Stats channel {stats_channel_id} not found")
                logger.error(f"   Available channels: {[c.id for c in self.get_all_channels()][:10]}")
                return
            
            logger.debug(f"✅ Found channel: {channel.name}")
            
            # Get round_id from result
            round_id = result.get('round_id')
            stats_data = result.get('stats_data', {})
            
            if not round_id:
                logger.warning(f"⚠️ No round_id for {filename}, skipping post")
                return
            
            # Get basic round info from parser (for round outcome/winner)
            round_num = stats_data.get('round_num', stats_data.get('round', 1))
            map_name = stats_data.get('map_name', stats_data.get('map', 'Unknown'))
            winner_team = stats_data.get('winner_team', 'Unknown')
            round_outcome = stats_data.get('round_outcome', '')
            round_duration = stats_data.get('actual_time', stats_data.get('map_time', 'Unknown'))
            
            # 🔥 FETCH ALL PLAYER DATA FROM DATABASE (not from parser!)
            # This gives us access to ALL 54 fields, not just the limited parser output
            logger.debug(f"📊 Fetching full player data from database for session {round_id}, round {round_num}...")
            
            # Get round info (time limit, actual time)
            round_query = """
                SELECT time_limit, actual_time, winner_team, round_outcome
                FROM rounds
                WHERE id = ?
            """
            round_info = await self.db_adapter.fetch_one(round_query, (round_id,))
            
            time_limit = round_info[0] if round_info else 'Unknown'
            actual_time = round_info[1] if round_info else 'Unknown'
            db_winner_team = round_info[2] if round_info else winner_team
            db_round_outcome = round_info[3] if round_info else round_outcome
            
            # Get player stats
            players_query = """
                SELECT 
                    player_name, team, kills, deaths, damage_given, damage_received,
                    team_damage_given, team_damage_received, gibs, headshots,
                    accuracy, revives_given, times_revived, time_dead_minutes,
                    efficiency, kd_ratio, time_played_minutes, dpm
                FROM player_comprehensive_stats
                WHERE round_id = ? AND round_number = ?
                ORDER BY kills DESC
            """
            rows = await self.db_adapter.fetch_all(players_query, (round_id, round_num))
            
            # Convert to dict format
            players = []
            for row in rows:
                    players.append({
                        'name': row[0],
                        'team': row[1],
                        'kills': row[2],
                        'deaths': row[3],
                        'damage_given': row[4],
                        'damage_received': row[5],
                        'team_damage_given': row[6],
                        'team_damage_received': row[7],
                        'gibs': row[8],
                        'headshots': row[9],
                        'accuracy': row[10],
                        'revives': row[11],
                        'times_revived': row[12],
                        'time_dead': row[13],
                        'efficiency': row[14],
                        'kd_ratio': row[15],
                        'time_played': row[16],
                        'dpm': row[17]
                    })
            
            logger.info(f"📊 Fetched {len(players)} players with FULL stats from database")
            
            logger.info(f"📋 Creating embed: Round {round_num}, Map {map_name}, {len(players)} players")
            
            # Determine round type
            round_type = "Round 1" if round_num == 1 else "Round 2"
            
            # Build title - simple and clean
            title = f"🎮 {round_type} Complete - {map_name}"
            
            description_parts = []
            
            # Add time information (limit vs actual)
            if time_limit and actual_time and time_limit != 'Unknown' and actual_time != 'Unknown':
                description_parts.append(f"⏱️ **Time:** {actual_time} / {time_limit}")
            elif actual_time and actual_time != 'Unknown':
                description_parts.append(f"⏱️ **Duration:** {actual_time}")
            
            # Add round outcome - use DB values if available
            outcome_to_show = db_round_outcome if db_round_outcome else round_outcome
            winner_to_show = db_winner_team if db_winner_team and str(db_winner_team) != 'Unknown' else winner_team
            
            # Build outcome line
            outcome_line = ""
            if winner_to_show and str(winner_to_show) != 'Unknown':
                outcome_line = f"🏆 **Winner:** {winner_to_show}"
            if outcome_to_show:
                if outcome_line:
                    outcome_line += f" ({outcome_to_show})"
                else:
                    outcome_line = f"🏆 **Outcome:** {outcome_to_show}"
            
            if outcome_line:
                description_parts.append(outcome_line)
            
            # Determine embed color based on round type
            embed_color = discord.Color.blue() if round_num == 1 else discord.Color.red()
            
            # Create main embed
            embed = discord.Embed(
                title=title,
                description="\n".join(description_parts),
                color=embed_color,
                timestamp=datetime.now()
            )
            
            # Sort all players by kills
            players_sorted = sorted(players, key=lambda p: p.get('kills', 0), reverse=True)
            
            # Rank emoji/number helper
            def get_rank_display(rank):
                """Get rank emoji for top 3, numbers with emojis for 4+"""
                if rank == 1:
                    return "🥇"
                elif rank == 2:
                    return "🥈"
                elif rank == 3:
                    return "🥉"
                else:
                    # Convert number to digit emojis (4-9 use number emojis, 10+ use digits)
                    num_str = str(rank)
                    emoji_map = {
                        '0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
                        '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'
                    }
                    return ''.join(emoji_map.get(digit, digit) for digit in num_str)
            
            # Split into chunks of 5 for Discord field limits (more stats per player = fewer per field)
            chunk_size = 5
            for i in range(0, len(players_sorted), chunk_size):
                chunk = players_sorted[i:i + chunk_size]
                field_name = f'📊 Players {i+1}-{min(i+chunk_size, len(players_sorted))}'
                
                player_lines = []
                for idx, player in enumerate(chunk):
                    rank = i + idx + 1  # Global rank across all chunks
                    rank_display = get_rank_display(rank)
                    
                    name = player.get('name', 'Unknown')[:16]
                    kills = player.get('kills', 0)
                    deaths = player.get('deaths', 0)
                    dmg = player.get('damage_given', 0)
                    dmgr = player.get('damage_received', 0)
                    acc = player.get('accuracy', 0)
                    hs = player.get('headshots', 0)
                    dpm = player.get('dpm', 0)
                    revives = player.get('revives', 0)
                    got_revived = player.get('times_revived', 0)
                    gibs = player.get('gibs', 0)
                    team_dmg_given = player.get('team_damage_given', 0)
                    team_dmg_rcvd = player.get('team_damage_received', 0)
                    time_dead = player.get('time_dead', 0)
                    
                    kd_str = f'{kills}/{deaths}'
                    
                    # Line 1: Rank + Name + Core stats (simplified)
                    line1 = (
                        f"{rank_display} **{name}** • K/D:`{kd_str}` "
                        f"DMG:`{int(dmg):,}` DPM:`{int(dpm)}` "
                        f"ACC:`{acc:.1f}%` HS:`{hs}`"
                    )
                    
                    # Line 2: Support stats (simplified)
                    line2 = (
                        f"     ↳ Rev:`{revives}/{got_revived}` Gibs:`{gibs}` "
                        f"TmDmg:`{int(team_dmg_given)}` Dead:`{time_dead:.1f}m`"
                    )
                    
                    player_lines.append(f"{line1}\n{line2}")
                
                embed.add_field(
                    name=field_name,
                    value='\n'.join(player_lines) if player_lines else 'No stats',
                    inline=False
                )
            
            # Calculate round totals (comprehensive)
            total_kills = sum(p.get('kills', 0) for p in players)
            total_deaths = sum(p.get('deaths', 0) for p in players)
            total_dmg = sum(p.get('damage_given', 0) for p in players)
            total_hs = sum(p.get('headshots', 0) for p in players)
            total_revives = sum(p.get('revives', 0) for p in players)
            total_gibs = sum(p.get('gibs', 0) for p in players)
            total_team_dmg = sum(p.get('team_damage_given', 0) for p in players)
            avg_acc = sum(p.get('accuracy', 0) for p in players) / len(players) if players else 0
            avg_dpm = sum(p.get('dpm', 0) for p in players) / len(players) if players else 0
            avg_time_dead = sum(p.get('time_dead', 0) for p in players) / len(players) if players else 0
            
            embed.add_field(
                name="📊 Round Summary",
                value=(
                    f"**Totals:** Kills:`{total_kills}` Deaths:`{total_deaths}` HS:`{total_hs}` "
                    f"Damage:`{int(total_dmg):,}` TeamDmg:`{int(total_team_dmg):,}`\n"
                    f"**Averages:** Accuracy:`{avg_acc:.1f}%` DPM:`{int(avg_dpm)}` DeadTime:`{avg_time_dead:.1f}m`"
                ),
                inline=False
            )
            
            embed.set_footer(text=f"Round ID: {round_id} | {filename}")
            
            # Post to channel
            logger.info(f"📤 Sending detailed stats embed to #{channel.name}...")
            await channel.send(embed=embed)
            logger.info(f"✅ Successfully posted stats for {len(players)} players to Discord!")
            
            # 🗺️ Check if this was the last round for the map → post map summary
            await self._check_and_post_map_completion(round_id, map_name, round_num, channel)
            
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ Error posting round stats to Discord: {e}", exc_info=True)

    async def _check_and_post_map_completion(self, round_id: int, map_name: str, current_round: int, channel):
        """
        Check if we just finished the last round of a map.
        If so, post aggregate map statistics.
        """
        try:
            # Check if there are any more rounds for this map in this session
            query = """
                SELECT MAX(round_number) as max_round, COUNT(DISTINCT round_number) as round_count
                FROM player_comprehensive_stats
                WHERE round_id = ? AND map_name = ?
            """
            row = await self.db_adapter.fetch_one(query, (round_id, map_name))
            
            if not row:
                return
            
            max_round, round_count = row
            
            logger.debug(f"🗺️ Map check: {map_name} - current round {current_round}, max in DB: {max_round}, total rounds: {round_count}")
            
            # If current round matches max round in DB, this is the last round for the map
            if current_round == max_round and round_count >= 2:
                logger.info(f"🏁 Map complete! {map_name} finished after {round_count} rounds. Posting map summary...")
                await self._post_map_summary(round_id, map_name, channel)
            else:
                logger.debug(f"⏳ Map {map_name} not complete yet (round {current_round}/{max_round})")
                    
        except Exception as e:
            logger.error(f"❌ Error checking map completion: {e}", exc_info=True)

    async def _post_map_summary(self, round_id: int, map_name: str, channel):
        """
        Post aggregate statistics for all rounds of a completed map.
        """
        try:
            logger.info(f"📊 Generating map summary for {map_name}...")
            
            # Get map-level aggregate stats
            map_query = """
                SELECT 
                    COUNT(DISTINCT round_number) as total_rounds,
                    COUNT(DISTINCT player_guid) as unique_players,
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths,
                    SUM(damage_given) as total_damage,
                    SUM(headshot_kills) as total_headshots,
                    AVG(accuracy) as avg_accuracy
                FROM player_comprehensive_stats
                WHERE round_id = ? AND map_name = ?
            """
            map_stats = await self.db_adapter.fetch_one(map_query, (round_id, map_name))
            
            if not map_stats:
                logger.warning(f"⚠️ No map stats found for {map_name}")
                return
            
            total_rounds, unique_players, total_kills, total_deaths, total_damage, total_headshots, avg_accuracy = map_stats
            
            # Get top 5 players across all rounds on this map
            top_players_query = """
                SELECT 
                    player_name,
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths,
                    SUM(damage_given) as total_damage,
                    AVG(accuracy) as avg_accuracy
                FROM player_comprehensive_stats
                WHERE round_id = ? AND map_name = ?
                GROUP BY player_guid
                ORDER BY total_kills DESC
                LIMIT 5
            """
            top_players = await self.db_adapter.fetch_all(top_players_query, (round_id, map_name))
            
            # Create embed
            embed = discord.Embed(
                title=f"🗺️ {map_name.upper()} - Map Complete!",
                description=f"Aggregate stats from **{total_rounds} rounds**",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )
            
            # Map overview
            kd_ratio = total_kills / total_deaths if total_deaths > 0 else total_kills
            embed.add_field(
                    name="📊 Map Overview",
                    value=(
                        f"**Rounds Played:** {total_rounds}\n"
                        f"**Unique Players:** {unique_players}\n"
                        f"**Total Kills:** {total_kills:,}\n"
                        f"**Total Deaths:** {total_deaths:,}\n"
                        f"**K/D Ratio:** {kd_ratio:.2f}\n"
                        f"**Total Damage:** {int(total_damage):,}\n"
                        f"**Total Headshots:** {total_headshots}\n"
                        f"**Avg Accuracy:** {avg_accuracy:.1f}%"
                    ),
                    inline=False
            )
            
            # Top performers
            if top_players:
                top_lines = []
                for i, (name, kills, deaths, damage, acc) in enumerate(top_players, 1):
                    kd = kills / deaths if deaths > 0 else kills
                    top_lines.append(
                        f"{i}. **{name}** - {kills}/{deaths} K/D ({kd:.2f}) | {int(damage):,} DMG | {acc:.1f}% ACC"
                    )
                
                embed.add_field(
                    name="🏆 Top Performers (All Rounds)",
                    value="\n".join(top_lines),
                    inline=False
                )
            
            embed.set_footer(text=f"Round ID: {round_id}")
            
            # Post to channel
            logger.info(f"📤 Posting map summary to #{channel.name}...")
            await channel.send(embed=embed)
            logger.info(f"✅ Map summary posted for {map_name}!")
                
        except Exception as e:
            logger.error(f"❌ Error posting map summary: {e}", exc_info=True)

    async def _import_stats_to_db(self, stats_data, filename):
        """Import parsed stats to database"""
        try:
            logger.info(
                f"📊 Importing {len(stats_data.get('players', []))} "
                f"players to database..."
            )

            # Extract date from filename: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
            timestamp = "-".join(filename.split("-")[:4])  # Full timestamp YYYY-MM-DD-HHMMSS
            date_part = "-".join(filename.split("-")[:3])  # Date YYYY-MM-DD
            time_part = filename.split("-")[3] if len(filename.split("-")) > 3 else "000000"  # HHMMSS
            
            # Store time as HHMMSS (NO COLONS) to match postgresql_database_manager format
            if len(time_part) == 6:
                round_time = time_part  # Keep as HHMMSS: "221941"
            else:
                round_time = "000000"
            
            # Create match_id (ORIGINAL BEHAVIOR - includes timestamp)
            match_id = f"{date_part}-{time_part}"

            # Check if round already exists
            check_query = """
                SELECT id FROM rounds
                WHERE round_date = ? AND map_name = ? AND round_number = ?
            """
            existing = await self.db_adapter.fetch_one(
                check_query,
                (
                    date_part,  # Use date_part not timestamp
                    stats_data["map_name"],
                    stats_data["round_num"],
                ),
            )

            if existing:
                logger.info(
                    f"⚠️ Round already exists (ID: {existing[0]})"
                )
                return existing[0]

            # Calculate gaming_session_id (60-minute gap logic)
            gaming_session_id = await self._calculate_gaming_session_id(date_part, round_time)

            # Insert new round
            insert_round_query = """
                INSERT INTO rounds (
                    round_date, round_time, match_id, map_name, round_number,
                    time_limit, actual_time, gaming_session_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
            """
            round_id = await self.db_adapter.fetch_val(
                insert_round_query,
                (
                    date_part,
                    round_time,
                    match_id,
                    stats_data["map_name"],
                    stats_data["round_num"],
                    stats_data.get("map_time", ""),
                    stats_data.get("actual_time", ""),
                    gaming_session_id,
                ),
            )

            # Insert player stats
            for player in stats_data.get("players", []):
                await self._insert_player_stats(
                    round_id, date_part, stats_data, player
                )

            # 🆕 If Round 2 file, also import match summary (cumulative stats)
            match_summary_id = None
            if stats_data.get('match_summary'):
                logger.info("📋 Importing match summary (cumulative R1+R2 stats)...")
                match_summary = stats_data['match_summary']
                
                # Check if match summary already exists
                check_summary_query = """
                    SELECT id FROM rounds
                    WHERE round_date = ? AND map_name = ? AND round_number = 0
                """
                existing_summary = await self.db_adapter.fetch_one(
                    check_summary_query,
                    (date_part, stats_data["map_name"]),
                )
                
                if not existing_summary:
                    # Insert match summary as round_number = 0 (use same gaming_session_id as the rounds)
                    insert_summary_query = """
                        INSERT INTO rounds (
                            round_date, round_time, match_id, map_name, round_number,
                            time_limit, actual_time, winner_team, defender_team, round_outcome, gaming_session_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        RETURNING id
                    """
                    match_summary_id = await self.db_adapter.fetch_val(
                        insert_summary_query,
                        (
                            date_part,
                            round_time,
                            match_id,
                            match_summary["map_name"],
                            0,  # round_number = 0 for match summary
                            match_summary.get("map_time", ""),
                            match_summary.get("actual_time", ""),
                            match_summary.get("winner_team", 0),
                            match_summary.get("defender_team", 0),
                            match_summary.get("round_outcome", ""),
                            gaming_session_id,  # Same session as R1/R2
                        ),
                    )
                    
                    # Insert match summary player stats
                    for player in match_summary.get("players", []):
                        await self._insert_player_stats(
                            match_summary_id, date_part, match_summary, player
                        )
                    
                    logger.info(
                        f"✅ Imported match summary (ID: {match_summary_id}) with "
                        f"{len(match_summary.get('players', []))} players"
                    )
                else:
                    match_summary_id = existing_summary[0]
                    logger.info(f"⏭️  Match summary already exists (ID: {match_summary_id})")

            logger.info(
                f"✅ Imported session {round_id} with "
                f"{len(stats_data.get('players', []))} players"
            )

            return round_id

        except Exception as e:
            logger.error(f"❌ Database import failed: {e}")
            raise

    async def _calculate_gaming_session_id(self, round_date: str, round_time: str) -> int:
        """
        Calculate gaming_session_id using 60-minute gap logic.
        
        Args:
            round_date: Date string like '2025-11-06'
            round_time: Time string like '234153' (HHMMSS) or '23:41:53' (HH:MM:SS)
        
        Returns:
            gaming_session_id (integer, starts at 1)
        """
        try:
            from datetime import datetime, timedelta
            
            # Get most recent round with gaming_session_id
            query = """
                SELECT gaming_session_id, round_date, round_time
                FROM rounds
                WHERE gaming_session_id IS NOT NULL
                ORDER BY round_date DESC, round_time DESC
                LIMIT 1
            """
            last_round = await self.db_adapter.fetch_one(query)
            
            if not last_round:
                # First round ever
                return 1
            
            last_session_id = last_round[0]
            last_date = last_round[1]
            last_time = last_round[2]
            
            # Parse current timestamp (handle both HHMMSS and HH:MM:SS formats)
            try:
                current_dt = datetime.strptime(f"{round_date} {round_time}", '%Y-%m-%d %H%M%S')
            except ValueError:
                # Fallback to format with colons
                current_dt = datetime.strptime(f"{round_date} {round_time}", '%Y-%m-%d %H:%M:%S')
            
            # Parse last timestamp (handle both HHMMSS and HH:MM:SS formats from DB)
            try:
                last_dt = datetime.strptime(f"{last_date} {last_time}", '%Y-%m-%d %H%M%S')
            except ValueError:
                # Fallback to format with colons
                last_dt = datetime.strptime(f"{last_date} {last_time}", '%Y-%m-%d %H:%M:%S')
            
            # Calculate time gap
            gap = current_dt - last_dt
            gap_minutes = gap.total_seconds() / 60
            
            # If gap > 60 minutes, start new session
            if gap_minutes > 60:
                new_session_id = last_session_id + 1
                logger.info(f"🎮 New gaming session #{new_session_id} (gap: {gap_minutes:.1f} min)")
                return new_session_id
            else:
                logger.debug(f"🎮 Continuing session #{last_session_id} (gap: {gap_minutes:.1f} min)")
                return last_session_id
                
        except Exception as e:
            logger.warning(f"⚠️ Error calculating gaming_session_id: {e}. Using NULL.")
            return None

    async def _insert_player_stats(
        self, round_id, round_date, result, player
    ):
        """Insert player comprehensive stats"""
        obj_stats = player.get("objective_stats", {})

        # Time fields - seconds is primary
        time_seconds = player.get("time_played_seconds", 0)
        time_minutes = time_seconds / 60.0 if time_seconds > 0 else 0.0

        # DPM already calculated by parser
        dpm = player.get("dpm", 0.0)

        # K/D ratio
        kills = player.get("kills", 0)
        deaths = player.get("deaths", 0)
        kd_ratio = kills / deaths if deaths > 0 else float(kills)

        # Efficiency / accuracy
        # Use parser-provided accuracy (hits/shots) rather than an incorrect
        # calculation that used kills/bullets_fired. Also calculate a
        # simple efficiency metric for insertion.
        bullets_fired = obj_stats.get("bullets_fired", 0)
        efficiency = (
            (kills / (kills + deaths) * 100) if (kills + deaths) > 0 else 0.0
        )
        accuracy = player.get("accuracy", 0.0)

        # Time dead
        # time_dead_ratio from parser may be provided as either a fraction (0.75)
        # or a percentage (75). Normalize to percentage and compute minutes.
        raw_td = obj_stats.get("time_dead_ratio", 0) or 0
        if raw_td <= 1:
            td_percent = raw_td * 100.0
        else:
            td_percent = float(raw_td)

        time_dead_minutes = time_minutes * (td_percent / 100.0)
        time_dead_mins = time_dead_minutes
        time_dead_ratio = td_percent

        values = (
            round_id,
            round_date,
            result["map_name"],
            result["round_num"],
            player.get("guid", "UNKNOWN"),
            player.get("name", "Unknown"),
            player.get("name", "Unknown"),  # clean_name
            player.get("team", 0),
            kills,
            deaths,
            player.get("damage_given", 0),
            player.get("damage_received", 0),
            obj_stats.get("team_damage_given", 0),  # ✅ FIX: was player.get()
            obj_stats.get("team_damage_received", 0),  # ✅ FIX: was player.get()
            obj_stats.get("gibs", 0),
            obj_stats.get("self_kills", 0),
            obj_stats.get("team_kills", 0),
            obj_stats.get("team_gibs", 0),
            obj_stats.get("headshot_kills", 0),  # ✅ TAB field 14 - actual headshot kills
            player.get("headshots", 0),  # ✅ Sum of weapon headshot hits (what we display!)
            time_seconds,
            time_minutes,
            time_dead_mins,
            time_dead_ratio,
            obj_stats.get("xp", 0),
            kd_ratio,
            dpm,
            efficiency,
            bullets_fired,
            accuracy,
            obj_stats.get("kill_assists", 0),
            0,
            0,  # objectives_completed, objectives_destroyed
            obj_stats.get("objectives_stolen", 0),
            obj_stats.get("objectives_returned", 0),
            obj_stats.get("dynamites_planted", 0),
            obj_stats.get("dynamites_defused", 0),
            obj_stats.get("times_revived", 0),
            obj_stats.get("revives_given", 0),
            obj_stats.get("useful_kills", 0),  # ✅ FIX: was "most_useful_kills"
            obj_stats.get("useless_kills", 0),
            obj_stats.get("kill_steals", 0),
            obj_stats.get("denied_playtime", 0),
            obj_stats.get("repairs_constructions", 0),  # ✅ FIX: was hardcoded 0
            obj_stats.get("tank_meatshield", 0),
            obj_stats.get("multikill_2x", 0),  # ✅ FIX: was "double_kills"
            obj_stats.get("multikill_3x", 0),  # ✅ FIX: was "triple_kills"
            obj_stats.get("multikill_4x", 0),  # ✅ FIX: was "quad_kills"
            obj_stats.get("multikill_5x", 0),  # ✅ FIX: was "multi_kills"
            obj_stats.get("multikill_6x", 0),  # ✅ FIX: was "mega_kills"
            obj_stats.get("killing_spree", 0),
            obj_stats.get("death_spree", 0),
        )

        query = """
            INSERT INTO player_comprehensive_stats (
                round_id, round_date, map_name, round_number,
                player_guid, player_name, clean_name, team,
                kills, deaths, damage_given, damage_received,
                team_damage_given, team_damage_received,
                gibs, self_kills, team_kills, team_gibs, headshot_kills, headshots,
                time_played_seconds, time_played_minutes,
                time_dead_minutes, time_dead_ratio,
                xp, kd_ratio, dpm, efficiency,
                bullets_fired, accuracy,
                kill_assists,
                objectives_completed, objectives_destroyed,
                objectives_stolen, objectives_returned,
                dynamites_planted, dynamites_defused,
                times_revived, revives_given,
                most_useful_kills, useless_kills, kill_steals,
                denied_playtime, constructions, tank_meatshield,
                double_kills, triple_kills, quad_kills,
                multi_kills, mega_kills,
                killing_spree_best, death_spree_worst
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """
        player_stats_id = await self.db_adapter.execute(query, values)

        # Insert weapon stats into weapon_comprehensive_stats if available
        try:
            weapon_stats = player.get("weapon_stats", {}) or {}
            if weapon_stats:
                # Get table column info (database-agnostic)
                if self.config.database_type == 'sqlite':
                    col_query = "PRAGMA table_info(weapon_comprehensive_stats)"
                    pragma_rows = await self.db_adapter.fetch_all(col_query)
                    cols = [r[1] for r in pragma_rows]
                else:
                    # PostgreSQL: Query information_schema
                    col_query = """
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name = 'weapon_comprehensive_stats'
                        ORDER BY ordinal_position
                    """
                    pragma_rows = await self.db_adapter.fetch_all(col_query)
                    cols = [r[0] for r in pragma_rows]

                # Include session metadata columns if present (they're NOT NULL in some schemas)
                insert_cols = ["round_id"]
                if "round_date" in cols:
                    insert_cols.append("round_date")
                if "map_name" in cols:
                    insert_cols.append("map_name")
                if "round_number" in cols:
                    insert_cols.append("round_number")

                if "player_comprehensive_stat_id" in cols:
                    insert_cols.append("player_comprehensive_stat_id")
                # If DB has both GUID and player_name columns, include both.
                # Some schemas require player_name NOT NULL even when GUID exists.
                if "player_guid" in cols:
                    insert_cols.append("player_guid")
                if "player_name" in cols:
                    insert_cols.append("player_name")

                insert_cols += ["weapon_name", "kills", "deaths", "headshots", "hits", "shots", "accuracy"]
                placeholders = ",".join(["?"] * len(insert_cols))
                insert_sql = f"INSERT INTO weapon_comprehensive_stats ({', '.join(insert_cols)}) VALUES ({placeholders})"

                logger.debug(
                    f"Preparing to insert {len(weapon_stats)} weapon rows for {player.get('name')} (session {round_id})"
                )
                for weapon_name, w in weapon_stats.items():
                    w_hits = int(w.get("hits", 0) or 0)
                    w_shots = int(w.get("shots", 0) or 0)
                    w_kills = int(w.get("kills", 0) or 0)
                    w_deaths = int(w.get("deaths", 0) or 0)
                    w_headshots = int(w.get("headshots", 0) or 0)
                    w_acc = (w_hits / w_shots * 100) if w_shots > 0 else 0.0

                    # Build row values in the same order as insert_cols
                    row_vals = [round_id]
                    if "round_date" in cols:
                        row_vals.append(round_date)
                    if "map_name" in cols:
                        row_vals.append(result.get("map_name"))
                    if "round_number" in cols:
                        row_vals.append(result.get("round_num"))

                    if "player_comprehensive_stat_id" in cols:
                        row_vals.append(player_stats_id)
                    # Append GUID then player_name if present, matching insert_cols order above
                    if "player_guid" in cols:
                        row_vals.append(player.get("guid", "UNKNOWN"))
                    if "player_name" in cols:
                        row_vals.append(player.get("name", "Unknown"))

                    row_vals += [weapon_name, w_kills, w_deaths, w_headshots, w_hits, w_shots, w_acc]

                    # Temporary diagnostic logging: capture the first few weapon INSERTs
                    # to verify column/value alignment (will be removed after debugging).
                    try:
                        logged = getattr(self, "_weapon_diag_logged", 0)
                        if logged < 5:
                            logger.debug(
                                "DIAG WEAPON INSERT: round_id=%s player=%s",
                                round_id,
                                player.get("name"),
                            )
                            logger.debug("  insert_cols: %s", insert_cols)
                            logger.debug("  row_vals: %r", tuple(row_vals))
                            logger.debug("  insert_sql: %s", insert_sql)
                            # increment global counter on the bot cog instance
                            try:
                                self._weapon_diag_logged = logged + 1
                            except Exception:
                                # Best-effort; don't raise from diagnostics
                                pass
                    except Exception:
                        logger.exception("Failed to log weapon insert diagnostic")

                    await self.db_adapter.execute(insert_sql, tuple(row_vals))
        except Exception as e:
            # Weapon insert failures should be visible — escalate to error and include traceback
            logger.error(
                f"Failed to insert weapon stats for {player.get('name')} (session {round_id}): {e}",
                exc_info=True,
            )
        
        # 🔗 CRITICAL: Update player aliases for !stats and !link commands
        await self._update_player_alias(
            player.get("guid", "UNKNOWN"),
            player.get("name", "Unknown"),
            round_date,
        )

    async def _update_player_alias(self, guid, alias, last_seen_date):
        """
        Track player aliases for !stats and !link commands
        
        This is CRITICAL for !stats and !link to work properly!
        Updates the player_aliases table every time we see a player.
        """
        try:
            # Convert string date to datetime for PostgreSQL compatibility
            from datetime import datetime
            if isinstance(last_seen_date, str):
                last_seen_datetime = datetime.strptime(last_seen_date, '%Y-%m-%d')
            else:
                last_seen_datetime = last_seen_date
            
            # Check if this GUID+alias combination exists
            check_query = 'SELECT times_seen FROM player_aliases WHERE guid = ? AND alias = ?'
            existing = await self.db_adapter.fetch_one(check_query, (guid, alias))

            if existing:
                # Update existing alias: increment times_seen and update last_seen
                update_query = '''UPDATE player_aliases 
                       SET times_seen = times_seen + 1, last_seen = ?
                       WHERE guid = ? AND alias = ?'''
                await self.db_adapter.execute(update_query, (last_seen_datetime, guid, alias))
            else:
                # Insert new alias
                insert_query = '''INSERT INTO player_aliases (guid, alias, first_seen, last_seen, times_seen)
                       VALUES (?, ?, ?, ?, 1)'''
                await self.db_adapter.execute(insert_query, (guid, alias, last_seen_datetime, last_seen_datetime))

            logger.debug(f"✅ Updated alias: {alias} for GUID {guid}")

        except Exception as e:
            logger.error(f"❌ Failed to update alias for {guid}/{alias}: {e}")

    async def post_round_summary(self, file_info, result):
        """
        Post round summary to Discord channel

        Handles:
        - Round 1 complete (single embed)
        - Round 2 complete (2 embeds: round summary + map summary)
        """
        try:
            channel = self.get_channel(self.stats_channel_id)
            if not channel:
                logger.error("❌ Stats channel not found")
                return

            stats_data = result.get("stats_data")
            if not stats_data:
                return

            # Round summary embed
            round_embed = discord.Embed(
                title=f"🎯 {file_info['map_name']} - "
                f"Round {file_info['round_number']} Complete",
                color=0x00FF00,
                timestamp=datetime.now(),
            )

            # Add top 3 players
            players = stats_data.get("players", [])[:3]
            top_players_text = "\n".join(
                [
                    f"**{i+1}.** {p['name']} - "
                    f"{p.get('kills', 0)}K/{p.get('deaths', 0)}D "
                    f"({p.get('dpm', 0):.0f} DPM)"
                    for i, p in enumerate(players)
                ]
            )

            round_embed.add_field(
                name="🏆 Top Performers",
                value=top_players_text or "No data",
                inline=False,
            )

            await channel.send(embed=round_embed)

            # If round 2, also post map summary
            if file_info["is_map_complete"]:
                await self.post_map_summary(file_info, stats_data)

            logger.info(
                f"✅ Posted round summary for "
                f"{file_info['map_name']} R{file_info['round_number']}"
            )

        except Exception as e:
            logger.error(f"❌ Failed to post round summary: {e}")

    async def post_map_summary(self, file_info, stats_data):
        """Post map summary after round 2 completes"""
        try:
            channel = self.get_channel(self.stats_channel_id)
            if not channel:
                return

            map_embed = discord.Embed(
                title=f"🗺️ {file_info['map_name']} - MAP COMPLETE",
                description="Both rounds finished!",
                color=0xFFD700,
                timestamp=datetime.now(),
            )

            map_embed.add_field(
                name="📊 Status",
                value="Map completed - Check stats above for details",
                inline=False,
            )

            await channel.send(embed=map_embed)

        except Exception as e:
            logger.error(f"❌ Failed to post map summary: {e}")

    # NOTE: File tracking methods moved to bot/automation/file_tracker.py
    # - FileTracker.should_process_file()
    # - FileTracker.mark_processed()
    # - FileTracker.sync_local_files_to_processed_table()

    # Wrapper methods for backward compatibility
    async def should_process_file(
        self, filename: str, ignore_startup_time: bool = False, check_db_only: bool = False
    ) -> bool:
        """Delegate to FileTracker.should_process_file()"""
        return await self.file_tracker.should_process_file(
            filename, ignore_startup_time=ignore_startup_time, check_db_only=check_db_only
        )

    async def ssh_list_remote_files(self, ssh_config: dict) -> list:
        """Delegate to SSHHandler.list_remote_files()"""
        return await SSHHandler.list_remote_files(ssh_config)

    async def ssh_download_file(self, ssh_config: dict, filename: str, local_dir: str = "local_stats") -> str:
        """Delegate to SSHHandler.download_file()"""
        return await SSHHandler.download_file(ssh_config, filename, local_dir)

    async def _auto_end_session(self):
        """Auto-end session and post summary"""
        try:
            logger.info("🏁 Auto-ending gaming session...")

            # Mark session as ended
            self.session_active = False
            self.session_end_timer = None

            # Post session summary to Discord
            channel = self.get_channel(self.stats_channel_id)
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
            # (Reuse the last_session command logic)
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
                    logger.info(
                        f"📊 Posting auto-summary for {round_date}"
                    )

                    # Use last_session logic to generate embeds
                    # (This would call the existing last_session code)
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

    # ==================== BACKGROUND TASKS ====================

    @tasks.loop(seconds=60)
    async def endstats_monitor(self):
        """
        🔄 SSH Monitoring Task - Optimized Performance Version
        
        **Performance Optimization (93% reduction in SSH calls):**
        - Dead Hours (02:00-11:00): No SSH checks
        - Voice Detection: 6+ players → check every 60s
        - Idle Mode: <6 players → check every 6 hours
        - Uses counter-based intervals (Option B from design doc)
        
        Monitors remote game server for new stats files:
        1. Lists files on remote server via SSH
        2. Compares with processed_files tracking
        3. Downloads new files
        4. Parses and imports to database
        5. Posts Discord round summaries automatically
        
        **Old system:** ~2,880 SSH checks/day (every 30s continuously)
        **New system:** ~182 SSH checks/day (interval-based)
        """
        if not self.monitoring or not self.ssh_enabled:
            return

        try:
            # ========== DEAD HOURS CHECK (02:00-11:00 CET) ==========
            try:
                import pytz
                cet = pytz.timezone("Europe/Paris")
            except:
                try:
                    from zoneinfo import ZoneInfo
                    cet = ZoneInfo("Europe/Paris")
                except:
                    cet = None
            
            now = datetime.now(cet) if cet else datetime.now()
            hour = now.hour
            
            # Skip SSH check during dead hours (02:00-11:00)
            if 2 <= hour < 11:
                logger.debug(f"⏸️  Dead hours ({hour:02d}:00 CET) - skipping SSH check")
                return
            
            # ========== VOICE DETECTION (Player Count Check) ==========
            total_players = 0
            for channel_id in self.gaming_voice_channels:
                channel = self.get_channel(channel_id)
                if channel and hasattr(channel, "members"):
                    total_players += sum(1 for m in channel.members if not m.bot)
            
            # ========== INTERVAL-BASED CHECKING (Counter System) ==========
            self.ssh_check_counter += 1
            
            if total_players >= 6:
                # ACTIVE MODE: Check every 60 seconds (every 1 cycle)
                interval = 1
                mode = "ACTIVE"
            else:
                # IDLE MODE: Check every 6 hours (360 cycles at 60s each)
                interval = 360
                mode = "IDLE"
            
            # Only perform SSH check when counter reaches interval
            if self.ssh_check_counter < interval:
                logger.debug(
                    f"⏭️  Skipping SSH check ({mode} mode: "
                    f"{self.ssh_check_counter}/{interval}, "
                    f"{total_players} players in voice)"
                )
                return
            
            # Reset counter and perform check
            self.ssh_check_counter = 0
            logger.info(
                f"🔍 SSH check triggered ({mode} mode, "
                f"{total_players} players in voice)"
            )
            
            # ========== SSH CHECK EXECUTION ==========
            # Build SSH config
            ssh_config = {
                "host": os.getenv("SSH_HOST"),
                "port": int(os.getenv("SSH_PORT", 22)),
                "user": os.getenv("SSH_USER"),
                "key_path": os.getenv("SSH_KEY_PATH", ""),
                "remote_path": os.getenv("REMOTE_STATS_PATH"),
            }

            # Validate SSH config
            if not all([
                ssh_config["host"],
                ssh_config["user"],
                ssh_config["key_path"],
                ssh_config["remote_path"],
            ]):
                logger.warning(
                    "⚠️ SSH config incomplete - monitoring disabled\n"
                    f"   Host: {ssh_config['host']}\n"
                    f"   User: {ssh_config['user']}\n"
                    f"   Key: {ssh_config['key_path']}\n"
                    f"   Path: {ssh_config['remote_path']}"
                )
                return

            # List remote files
            logger.debug(f"📡 Connecting to SSH: {ssh_config['user']}@{ssh_config['host']}:{ssh_config['port']}")
            remote_files = await SSHHandler.list_remote_files(ssh_config)

            if not remote_files:
                logger.debug("📂 No remote files found or SSH connection failed")
                return

            logger.debug(f"📂 Found {len(remote_files)} total files on remote server")

            # Check each file
            new_files_count = 0
            for filename in remote_files:
                # Check if already processed (4-layer check)
                if await self.file_tracker.should_process_file(filename):
                    new_files_count += 1
                    logger.info("=" * 60)
                    logger.info(f"📥 NEW FILE DETECTED: {filename}")
                    logger.info("=" * 60)

                    # Download file
                    download_start = time.time()
                    local_path = await SSHHandler.download_file(
                        ssh_config, filename, "local_stats"
                    )
                    download_time = time.time() - download_start

                    if local_path:
                        logger.info(f"✅ Downloaded in {download_time:.2f}s: {local_path}")
                        
                        # Wait 3 seconds for file to fully write
                        logger.debug("⏳ Waiting 3s for file to fully write...")
                        await asyncio.sleep(3)

                        # Process the file (imports to DB)
                        logger.info(f"⚙️ Processing file: {filename}")
                        process_start = time.time()
                        result = await self.process_gamestats_file(local_path, filename)
                        process_time = time.time() - process_start
                        
                        logger.info(f"⚙️ Processing completed in {process_time:.2f}s")
                        
                        # 🆕 AUTO-POST to Discord after processing!
                        if result and result.get('success'):
                            logger.info(f"📊 Posting to Discord: {result.get('player_count', 0)} players")
                            await self.post_round_stats_auto(filename, result)
                            logger.info(f"✅ Successfully processed and posted: {filename}")
                        else:
                            error_msg = result.get('error', 'Unknown error') if result else 'No result'
                            logger.warning(f"⚠️ Processing failed for {filename}: {error_msg}")
                            logger.warning(f"⚠️ Skipping Discord post")
                    else:
                        logger.error(f"❌ Download failed for {filename}")
            
            if new_files_count == 0:
                logger.debug(f"✅ All {len(remote_files)} files already processed")
            else:
                logger.info(f"🎉 Processed {new_files_count} new file(s) this check")

        except Exception as e:
            logger.error(f"❌ endstats_monitor error: {e}", exc_info=True)

    @endstats_monitor.before_loop
    async def before_endstats_monitor(self):
        """Wait for bot to be ready before starting SSH monitoring"""
        await self.wait_until_ready()
        logger.info("✅ SSH monitoring task ready (optimized with voice detection)")

    @tasks.loop(seconds=30)
    async def cache_refresher(self):
        """
        🔄 Cache Refresh Task - Runs every 30 seconds

        Keeps in-memory cache in sync with database
        """
        try:
            # Refresh processed files cache
            query = "SELECT filename FROM processed_files WHERE success = 1"
            rows = await self.db_adapter.fetch_all(query)
            self.processed_files = {row[0] for row in rows}

        except Exception as e:
            logger.debug(f"Cache refresh error: {e}")

    @cache_refresher.before_loop
    async def before_cache_refresher(self):
        """Wait for bot to be ready"""
        await self.wait_until_ready()

    # ========== DEPRECATED: Scheduled Monitoring (Removed in Performance Optimization) ==========
    # This task has been removed - monitoring is now controlled by:
    # 1. Voice detection (6+ players = active mode)
    # 2. Dead hours detection (02:00-11:00 = no checks)
    # 3. Manual !session_start / !session_end commands (if needed)
    #
    # Old auto-start at 20:00 CET is no longer needed - voice detection handles everything
    #
    # @tasks.loop(minutes=1)
    # async def scheduled_monitoring_check(self):
    #     """⏰ DEPRECATED - Monitoring now voice-triggered"""
    #     pass
    #
    # @scheduled_monitoring_check.before_loop
    # async def before_scheduled_monitoring(self):
    #     """Wait for bot to be ready"""
    #     await self.wait_until_ready()

    @tasks.loop(seconds=30)
    async def voice_session_monitor(self):
        """
        🎙️ Voice Session Monitor - Runs every 30 seconds

        Monitors voice channels for session end:
        - Counts players in gaming voice channels
        - Starts 3-minute timer when players drop below threshold
        - Auto-ends session and posts summary
        - Cancels timer if players return
        """
        if not self.automation_enabled:
            return

        try:
            # Count players in gaming voice channels
            total_players = 0
            for channel_id in self.gaming_voice_channels:
                channel = self.get_channel(channel_id)
                if channel and hasattr(channel, "members"):
                    # Count non-bot members
                    total_players += sum(
                        1 for m in channel.members if not m.bot
                    )

            # Check if below threshold
            if total_players < self.session_end_threshold:
                if self.session_active and not self.session_end_timer:
                    # Start timer
                    self.session_end_timer = datetime.now()
                    logger.info(
                        f"⏱️ Session end timer started "
                        f"({total_players} < {self.session_end_threshold})"
                    )

                elif self.session_end_timer:
                    # Check if timer expired
                    elapsed = (datetime.now() - self.session_end_timer).seconds
                    if elapsed >= self.session_end_delay:
                        logger.info(
                            "🏁 3 minutes elapsed - auto-ending session"
                        )
                        await self._auto_end_session()
            else:
                # Players returned - cancel timer
                if self.session_end_timer:
                    logger.info(
                        f"⏰ Session end cancelled - players returned "
                        f"({total_players})"
                    )
                    self.session_end_timer = None

        except Exception as e:
            logger.error(f"Voice monitor error: {e}")

    @voice_session_monitor.before_loop
    async def before_voice_monitor(self):
        """Wait for bot to be ready"""
        await self.wait_until_ready()

    # ==================== BOT EVENTS ====================

    async def on_message(self, message):
        """Process messages and filter by allowed channels"""
        # Ignore bot's own messages
        if message.author.bot:
            return
        
        # Check if channel restriction is enabled and if message is in allowed channel
        if self.bot_command_channels:
            if message.channel.id not in self.bot_command_channels:
                # Silently ignore commands in non-whitelisted channels
                return
        
        # Process commands normally
        await self.process_commands(message)

    async def on_ready(self):
        """✅ Bot startup message"""
        logger.info("=" * 80)
        logger.info(f"🚀 Ultimate ET:Legacy Bot logged in as {self.user}")
        logger.info(f"🆔 Bot ID: {self.user.id}")
        logger.info(f"📊 Database Type: {self.config.database_type.upper()}")
        logger.info(f"📍 Database: {self.db_path}")
        logger.info(f"🎮 Commands Loaded: {len(list(self.commands))}")
        logger.info(f"🔧 Cogs Loaded: {len(self.cogs)}")
        logger.info(f"🌐 Servers: {len(self.guilds)}")
        logger.info("=" * 80)

        # Clear any old slash commands to avoid confusion
        try:
            self.tree.clear_commands(guild=None)
            await self.tree.sync()
            logger.info("🧹 Cleared old slash commands")
        except Exception as e:
            logger.warning(f"Could not clear slash commands: {e}")
        
        # 🆕 AUTO-DETECT ACTIVE GAMING SESSION ON STARTUP
        await self._check_voice_channels_on_startup()

    async def _check_voice_channels_on_startup(self):
        """
        Check voice channels on bot startup and auto-start session if players detected.
        
        This ensures the bot doesn't miss active sessions if it restarts
        while players are already in voice.
        """
        try:
            if not self.automation_enabled or not self.gaming_voice_channels:
                return
            
            # Wait a moment for Discord cache to populate
            await asyncio.sleep(2)
            
            # Count players in gaming voice channels
            total_players = 0
            current_participants = set()
            
            for channel_id in self.gaming_voice_channels:
                channel = self.get_channel(channel_id)
                if channel and hasattr(channel, "members"):
                    for member in channel.members:
                        if not member.bot:
                            total_players += 1
                            current_participants.add(member.id)
            
            logger.info(
                f"🎙️ Startup voice check: {total_players} players detected "
                f"in {len(self.gaming_voice_channels)} monitored channels"
            )
            
            # Auto-start session if threshold met
            if total_players >= self.session_start_threshold and not self.session_active:
                logger.info(
                    f"🎮 AUTO-STARTING SESSION: {total_players} players detected "
                    f"(threshold: {self.session_start_threshold})"
                )
                await self._start_gaming_session(current_participants)
            elif total_players > 0:
                logger.info(
                    f"ℹ️  {total_players} players in voice but below threshold "
                    f"({self.session_start_threshold} needed to auto-start)"
                )
                
        except Exception as e:
            logger.error(f"❌ Error checking voice channels on startup: {e}", exc_info=True)

    async def on_command(self, ctx):
        """Track command execution start"""
        import time
        ctx.command_start_time = time.time()
        
        command_logger = get_logger('bot.commands')
        user = f"{ctx.author.name}#{ctx.author.discriminator} ({ctx.author.id})"
        guild = f"{ctx.guild.name} ({ctx.guild.id})" if ctx.guild else "DM"
        channel = f"#{ctx.channel.name}" if hasattr(ctx.channel, 'name') else "DM"
        
        command_logger.info(
            f"▶ COMMAND: !{ctx.command.name} | "
            f"User: {user} | Guild: {guild} | Channel: {channel}"
        )

    async def on_command_completion(self, ctx):
        """Track successful command completion"""
        import time
        duration = time.time() - getattr(ctx, 'command_start_time', time.time())
        
        log_command_execution(
            ctx,
            f"!{ctx.command.name}",
            start_time=getattr(ctx, 'command_start_time', None),
            end_time=time.time()
        )
        
        # Warn about slow commands
        if duration > 5.0:
            log_performance_warning(f"!{ctx.command.name}", duration, threshold=5.0)

    async def on_command_error(self, ctx, error):
        """🚨 Handle command errors"""
        import time
        self.error_count += 1
        
        # Log the error with full context
        duration = time.time() - getattr(ctx, 'command_start_time', time.time())
        
        log_command_execution(
            ctx,
            f"!{ctx.command.name}" if ctx.command else "unknown",
            start_time=getattr(ctx, 'command_start_time', None),
            end_time=time.time(),
            error=str(error)
        )

        if isinstance(error, commands.CommandNotFound):
            await ctx.send(
                "❌ Command not found. Use `!help_command` for available commands."
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                f"❌ Missing argument: {error.param}. Use `!help_command` for usage."
            )
        else:
            error_logger = get_logger('bot.errors')
            error_logger.error(
                f"Command error in !{ctx.command.name if ctx.command else 'unknown'}: {error}",
                exc_info=True
            )
            await ctx.send(f"❌ An error occurred: {error}")



# 🚀 BOT STARTUP
def main():
    """🚀 Start the Ultimate ET:Legacy Discord Bot"""

    # Get Discord token
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        logger.error("❌ DISCORD_BOT_TOKEN not found in environment variables!")
        logger.info("Please set your Discord bot token in the .env file")
        return

    # Create and run bot
    bot = UltimateETLegacyBot()

    try:
        logger.info("🚀 Starting Ultimate ET:Legacy Bot...")
        bot.run(token)
    except discord.LoginFailure:
        logger.error("❌ Invalid Discord token!")
    except Exception as e:
        logger.error(f"❌ Bot startup failed: {e}")


if __name__ == "__main__":
    main()
