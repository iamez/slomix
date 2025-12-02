#!/usr/bin/env python3
"""
ULTIMATE ET:LEGACY DISCORD BOT - COG-BASED VERSION
"""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timedelta

import io
import discord
from discord.ext import commands, tasks

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.stopwatch_scoring import StopwatchScoring

# Import extracted core classes
from bot.core import StatsCache, SeasonManager, AchievementSystem
from bot.core.utils import sanitize_error_message

# Import database adapter and config for PostgreSQL migration
from bot.core.database_adapter import create_adapter, DatabaseAdapter
from bot.config import load_config
from bot.stats import StatsCalculator
from bot.automation import SSHHandler, FileTracker
from bot.services.voice_session_service import VoiceSessionService
from bot.services.round_publisher_service import RoundPublisherService
from bot.repositories import FileRepository

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
logger.info(f"🐍 Python: {sys.version}")
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
        intents.members = True  # Required for voice channel member detection
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

        # 🎙️ Voice Session Service (manages gaming session detection)
        self.voice_session_service = VoiceSessionService(self, self.config, self.db_adapter)
        logger.info("✅ Voice session service initialized")

        # 📊 Round Publisher Service (manages Discord auto-posting of stats)
        self.round_publisher = RoundPublisherService(self, self.config, self.db_adapter)
        logger.info("✅ Round publisher service initialized")

        # 📁 File Repository (data access layer for processed files)
        self.file_repository = FileRepository(self.db_adapter, self.config)
        logger.info("✅ File repository initialized")

        # 🤖 Automation System Flags (OFF by default for dev/testing)
        self.automation_enabled = self.config.automation_enabled
        self.ssh_enabled = self.config.ssh_enabled

        # Enable monitoring when SSH is enabled (for auto stats posting)
        self.monitoring = self.ssh_enabled

        if self.automation_enabled:
            logger.info("✅ Automation system ENABLED")
        else:
            logger.warning(
                "⚠️ Automation system DISABLED (set AUTOMATION_ENABLED=true to enable)"
            )
        
        # SSH monitoring optimization - counter-based intervals
        self.ssh_check_counter = 0  # Tracks cycles for interval-based checking
        self.last_file_download_time = None  # Track last file download for grace period logic

        # Load channel configuration from config object
        self.gaming_voice_channels = self.config.gaming_voice_channels
        self.bot_command_channels = self.config.bot_command_channels
        self.production_channel_id = self.config.production_channel_id
        self.gather_channel_id = self.config.gather_channel_id
        self.general_channel_id = self.config.general_channel_id
        self.admin_channels = self.config.admin_channels
        self.admin_channel_id = self.config.admin_channel_id
        self.public_channels = self.config.public_channels
        self.all_allowed_channels = self.config.all_allowed_channels

        # Session thresholds
        self.session_start_threshold = self.config.session_start_threshold
        self.session_end_threshold = self.config.session_end_threshold
        self.session_end_delay = self.config.session_end_delay

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

        # Log channel routing configuration
        if self.production_channel_id:
            logger.info(f"📊 Production channel: {self.production_channel_id}")
        if self.gather_channel_id:
            logger.info(f"🎮 Gather channel: {self.gather_channel_id}")
        if self.general_channel_id:
            logger.info(f"💬 General channel: {self.general_channel_id}")
        if self.admin_channel_id:
            logger.info(f"🔐 Admin channel: {self.admin_channel_id}")
        if self.public_channels:
            logger.info(f"✅ Public commands enabled in: {self.public_channels}")

        if not self.gaming_voice_channels:
            logger.warning(
                "⚠️ No gaming voice channels configured - voice detection disabled"
            )

        # 🏆 Awards and achievements tracking
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

    async def bot_check(self, ctx):
        """
        Global check: Silently ignore commands from unauthorized channels.

        Only responds to commands in:
        - Public channels (production, gather, general)
        - Admin channels

        Commands from other channels are completely ignored (no response).
        """
        # If no channels configured, allow all
        if not self.all_allowed_channels:
            return True

        # Check if command is in an allowed channel
        if ctx.channel.id in self.all_allowed_channels:
            return True

        # Silently ignore - return False without sending any message
        return False

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

        # 🏆 Load Achievements Cog (achievement badge information and help)
        try:
            from bot.cogs.achievements_cog import AchievementsCog
            await self.add_cog(AchievementsCog(self))
            logger.info("✅ Achievements Cog loaded (achievements, medals, badges)")
        except Exception as e:
            logger.error(f"❌ Failed to load Achievements Cog: {e}", exc_info=True)

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

        # 🔮 COMPETITIVE ANALYTICS: Load prediction cogs (Phase 5)
        try:
            await self.load_extension("cogs.predictions_cog")
            logger.info("✅ Predictions cog loaded (!predictions, !prediction_stats, !my_predictions)")
        except Exception as e:
            logger.warning(f"⚠️  Could not load Predictions cog: {e}")
            logger.warning("Bot will continue without prediction commands")

        try:
            await self.load_extension("cogs.admin_predictions_cog")
            logger.info("✅ Admin Predictions cog loaded (!admin_predictions, !update_prediction_outcome)")
        except Exception as e:
            logger.warning(f"⚠️  Could not load Admin Predictions cog: {e}")
            logger.warning("Bot will continue without admin prediction commands")

        # 🤖 AUTOMATION: Initialize automation services
        try:
            from bot.services.automation import SSHMonitor, HealthMonitor, MetricsLogger, DatabaseMaintenance

            # Get configuration from already-parsed channel config
            admin_channel_id = self.admin_channel_id

            # For PostgreSQL, we don't have a db_path, but metrics_logger needs one for its own SQLite db
            # Use a sensible default path for metrics database
            metrics_db_path = self.config.metrics_db_path

            # Create automation services in correct order (MetricsLogger first, it's needed by HealthMonitor)
            self.metrics = MetricsLogger(db_path=metrics_db_path)
            self.ssh_monitor = SSHMonitor(self)
            self.health_monitor = HealthMonitor(self, admin_channel_id, self.metrics)
            self.db_maintenance = DatabaseMaintenance(self, self.db_path or "bot/data/etlegacy.db", admin_channel_id)

            logger.info("✅ Automation services initialized (SSH, Health, Metrics, DB Maintenance)")

            # Load automation commands cog
            await self.load_extension("cogs.automation_commands")
            logger.info("✅ Automation Commands cog loaded")

            # NOTE: SSHMonitor service is DISABLED - endstats_monitor task handles everything
            # SSHMonitor only downloads + imports, but endstats_monitor also posts to Discord.
            # Having both running causes a race condition where SSHMonitor processes files first,
            # marking them as "already processed" before endstats_monitor can post to Discord.
            # 
            # The endstats_monitor task loop (line ~1315) handles:
            # 1. SSH connection to game server
            # 2. File download
            # 3. Database import
            # 4. Discord posting via RoundPublisherService
            #
            # SSHMonitor service remains available for manual control via !automation commands
            logger.info(f"🔍 Bot ssh_enabled={self.ssh_enabled} (from SSH_ENABLED env var)")
            if self.ssh_enabled:
                logger.info("⏭️ SSHMonitor auto-start DISABLED (endstats_monitor handles SSH + Discord posting)")
                # await self.ssh_monitor.start_monitoring()  # DISABLED - causes race condition
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

    # 🔌 SSH HELPER METHODS

    async def ssh_list_remote_files(self, ssh_config: dict) -> list:
        """
        List files in remote SSH directory using provided config.
        Used by sync_cog for manual sync operations.

        Args:
            ssh_config: Dict with keys: host, port, user, key_path, remote_path

        Returns:
            List of filenames in remote directory
        """
        import paramiko
        import shlex

        def _list_files_sync():
            ssh = None
            try:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                ssh.connect(
                    hostname=ssh_config['host'],
                    port=ssh_config['port'],
                    username=ssh_config['user'],
                    key_filename=os.path.expanduser(ssh_config['key_path']),
                    timeout=10
                )

                safe_path = shlex.quote(ssh_config['remote_path'])
                stdin, stdout, stderr = ssh.exec_command(f"ls -1 {safe_path}")  # nosec B601
                files = stdout.read().decode().strip().split('\n')

                return [f.strip() for f in files if f.strip()]

            except Exception as e:
                logger.error(f"❌ SSH list files error: {e}")
                return []
            finally:
                if ssh:
                    try:
                        ssh.close()
                    except Exception:
                        pass

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _list_files_sync)

    # 🎙️ VOICE CHANNEL SESSION DETECTION

    async def on_voice_state_update(self, member, before, after):
        """🎙️ Detect gaming sessions based on voice channel activity (delegates to service)"""
        await self.voice_session_service.handle_voice_state_change(member, before, after)

    # 🔌 SSH MONITORING HELPER METHODS

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

            # Create match_id - for R2 files, use R1's timestamp so they share same match_id
            if stats_data.get('r1_filename'):
                # This is an R2 file with matched R1 - extract R1's timestamp
                r1_filename = stats_data['r1_filename']
                r1_parts = r1_filename.split("-")
                r1_date = "-".join(r1_parts[:3])  # YYYY-MM-DD
                r1_time = r1_parts[3] if len(r1_parts) > 3 else "000000"  # HHMMSS
                match_id = f"{r1_date}-{r1_time}"
                logger.info(f"🔗 R2 matched to R1: using R1 timestamp for match_id: {match_id}")
            else:
                # R1 file or orphan R2 - use own timestamp
                match_id = f"{date_part}-{time_part}"

            # Check if round already exists (FIXED: includes round_time to prevent false duplicates)
            check_query = """
                SELECT id FROM rounds
                WHERE round_date = ? AND round_time = ? AND map_name = ? AND round_number = ?
            """
            existing = await self.db_adapter.fetch_one(
                check_query,
                (
                    date_part,  # Use date_part not timestamp
                    round_time,  # FIXED: Add round_time to prevent duplicate detection when same map played twice
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

        FIXED: Now finds the chronologically PREVIOUS round (before current round),
        not the latest round in the database. This allows importing old rounds
        without breaking session grouping.

        Args:
            round_date: Date string like '2025-11-06'
            round_time: Time string like '234153' (HHMMSS) or '23:41:53' (HH:MM:SS)

        Returns:
            gaming_session_id (integer, starts at 1)
        """
        try:
            from datetime import datetime, timedelta

            # Parse current timestamp first
            try:
                current_dt = datetime.strptime(f"{round_date} {round_time}", '%Y-%m-%d %H%M%S')
            except ValueError:
                current_dt = datetime.strptime(f"{round_date} {round_time}", '%Y-%m-%d %H:%M:%S')

            # Get the chronologically PREVIOUS round (before current round)
            # This allows importing old rounds without messing up session IDs
            query = """
                SELECT gaming_session_id, round_date, round_time
                FROM rounds
                WHERE gaming_session_id IS NOT NULL
                  AND (round_date < ? OR (round_date = ? AND round_time < ?))
                ORDER BY round_date DESC, round_time DESC
                LIMIT 1
            """
            prev_round = await self.db_adapter.fetch_one(
                query,
                (round_date, round_date, round_time)
            )

            if not prev_round:
                # No previous round - this is first round OR earliest round being imported
                # Get max session_id and increment, or start at 1
                max_query = "SELECT MAX(gaming_session_id) FROM rounds WHERE gaming_session_id IS NOT NULL"
                max_session = await self.db_adapter.fetch_val(max_query, ())

                if max_session:
                    new_session_id = max_session + 1
                    logger.info(f"🎮 New gaming session #{new_session_id} (first round in chronological order)")
                    return new_session_id
                else:
                    logger.info("🎮 Starting first gaming session #1")
                    return 1

            prev_session_id = prev_round[0]
            prev_date = prev_round[1]
            prev_time = prev_round[2]

            # Parse previous timestamp
            try:
                prev_dt = datetime.strptime(f"{prev_date} {prev_time}", '%Y-%m-%d %H%M%S')
            except ValueError:
                prev_dt = datetime.strptime(f"{prev_date} {prev_time}", '%Y-%m-%d %H:%M:%S')

            # Calculate time gap (current - previous, should always be positive)
            gap = current_dt - prev_dt
            gap_minutes = gap.total_seconds() / 60

            # If gap > session_gap_minutes, start new session
            if gap_minutes > self.config.session_gap_minutes:
                # Get max session_id and increment
                max_query = "SELECT MAX(gaming_session_id) FROM rounds WHERE gaming_session_id IS NOT NULL"
                max_session = await self.db_adapter.fetch_val(max_query, ())
                new_session_id = (max_session or 0) + 1
                logger.info(f"🎮 New gaming session #{new_session_id} (gap: {gap_minutes:.1f} min from previous round)")
                return new_session_id
            else:
                logger.debug(f"🎮 Continuing session #{prev_session_id} (gap: {gap_minutes:.1f} min from previous round)")
                return prev_session_id
                
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


    async def ssh_download_file(self, ssh_config: dict, filename: str, local_dir: str = "local_stats") -> str:
        """Delegate to SSHHandler.download_file()"""
        return await SSHHandler.download_file(ssh_config, filename, local_dir)

    # ==================== BACKGROUND TASKS ====================

    @tasks.loop(seconds=60)
    async def endstats_monitor(self):
        """
        🔄 SSH Monitoring Task - Optimized Performance with Grace Period

        **Performance Optimization with File Loss Prevention:**
        - Dead Hours (02:00-11:00 CET): No SSH checks
        - Active Mode: 6+ players in voice → check every 60s
        - Grace Period: Within 30min of last file → check every 60s (prevents file loss during player drops)
        - Idle Mode: No players + no recent files → check every 10min (reduced from 6hr to prevent file loss)
        - Uses counter-based intervals with grace period logic

        Monitors remote game server for new stats files:
        1. Lists files on remote server via SSH
        2. Compares with processed_files tracking
        3. Downloads new files
        4. Parses and imports to database
        5. Posts Discord round summaries automatically
        6. Detects and marks round restarts/cancellations

        **Old system:** ~2,880 SSH checks/day (every 30s continuously)
        **New system:** ~200 SSH checks/day (with grace period + 10min idle)
        **File loss prevention:** Grace period keeps checking for 30min after last file
        """
        if not self.monitoring or not self.ssh_enabled:
            return

        try:
            # ========== DEAD HOURS CHECK (02:00-11:00 CET) ==========
            try:
                import pytz
                cet = pytz.timezone("Europe/Paris")
            except ImportError:
                try:
                    from zoneinfo import ZoneInfo
                    cet = ZoneInfo("Europe/Paris")
                except ImportError:
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
            
            # ========== INTERVAL-BASED CHECKING (Counter System with Grace Period) ==========
            self.ssh_check_counter += 1

            # Calculate time since last file was downloaded
            grace_period_active = False
            if hasattr(self, 'last_file_download_time') and self.last_file_download_time:
                time_since_last_file = (datetime.now() - self.last_file_download_time).total_seconds()
                grace_period_active = time_since_last_file < 1800  # 30 minutes grace period

            if total_players >= 6 or grace_period_active:
                # ACTIVE MODE: Check every 60 seconds (every 1 cycle)
                # Triggered by: 6+ players in voice OR within 30min of last file
                interval = 1
                mode = "ACTIVE (players)" if total_players >= 6 else "ACTIVE (grace period)"
            else:
                # IDLE MODE: Check every 10 minutes (10 cycles at 60s each)
                # 🔧 REDUCED from 6 hours to 10 minutes to prevent file loss
                interval = 10
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
            # Build SSH config from config object
            ssh_config = {
                "host": self.config.ssh_host,
                "port": self.config.ssh_port,
                "user": self.config.ssh_user,
                "key_path": self.config.ssh_key_path,
                "remote_path": self.config.ssh_remote_path,
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

                        # Track download time for grace period logic
                        self.last_file_download_time = datetime.now()

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
                            await self.round_publisher.publish_round_stats(filename, result)
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
        Uses FileRepository for data access (Repository Pattern)
        """
        try:
            # Refresh processed files cache via repository
            self.processed_files = await self.file_repository.get_processed_filenames()

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
        
        # Only process commands in allowed channels
        # Use bot_command_channels if set, otherwise fall back to public_channels
        allowed_channels = self.bot_command_channels or self.public_channels
        if allowed_channels:
            if message.channel.id not in allowed_channels:
                # Silently ignore messages in non-whitelisted channels
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
        await self.voice_session_service.check_startup_voice_state()

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
            # Silently ignore CommandNotFound - could be commands for other bots
            # Only respond in designated bot command channels (if configured)
            if not self.bot_command_channels or ctx.channel.id not in self.bot_command_channels:
                return  # Don't respond to unknown commands - might be for another bot

            await ctx.send(
                "❌ Command not found. Use `!help_command` for available commands."
            )
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"⏱️ Slow down! Try again in {error.retry_after:.1f}s",
                delete_after=5
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                f"❌ Missing argument: {error.param}. Use `!help_command` for usage."
            )
        elif isinstance(error, commands.CheckFailure):
            # For channel check failures, just send the custom message without extra error text
            from bot.core.checks import ChannelCheckFailure
            if isinstance(error, ChannelCheckFailure):
                await ctx.send(str(error))
            else:
                # Other check failures
                await ctx.send(f"❌ {sanitize_error_message(error)}")
        else:
            error_logger = get_logger('bot.errors')
            error_logger.error(
                f"Command error in !{ctx.command.name if ctx.command else 'unknown'}: {error}",
                exc_info=True
            )
            await ctx.send(f"❌ An error occurred: {sanitize_error_message(error)}")



# 🚀 BOT STARTUP
def main():
    """🚀 Start the Ultimate ET:Legacy Discord Bot"""

    # Create bot (config is loaded in __init__)
    bot = UltimateETLegacyBot()

    # Get Discord token from config
    token = bot.config.discord_token
    if not token:
        logger.error("❌ DISCORD_BOT_TOKEN not found in environment variables!")
        logger.info("Please set your Discord bot token in the .env file")
        return

    try:
        logger.info("🚀 Starting Ultimate ET:Legacy Bot...")
        bot.run(token)
    except discord.LoginFailure:
        logger.error("❌ Invalid Discord token!")
    except Exception as e:
        logger.error(f"❌ Bot startup failed: {e}")


if __name__ == "__main__":
    main()
