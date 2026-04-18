#!/usr/bin/env python3
"""
ULTIMATE ET:LEGACY DISCORD BOT - COG-BASED VERSION
"""

import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta

import discord
from discord.ext import commands

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import extracted core classes
from bot.automation import FileTracker, SSHHandler
from bot.config import load_config
from bot.core import AchievementSystem, SeasonManager, StatsCache

# Import database adapter and config for PostgreSQL migration
from bot.core.database_adapter import create_adapter
from bot.core.team_manager import TeamManager
from bot.core.utils import sanitize_error_message
from bot.repositories import FileRepository
from bot.services.endstats_pipeline_mixin import _EndstatsPipelineMixin
from bot.services.lua_round_storage_mixin import _LuaRoundStorageMixin
from bot.services.monitor_tasks_mixin import _MonitorTasksMixin
from bot.services.round_publisher_service import RoundPublisherService
from bot.services.stats_import_mixin import _StatsImportMixin
from bot.services.timing_comparison_service import TimingComparisonService
from bot.services.timing_debug_service import TimingDebugService
from bot.services.voice_session_service import VoiceSessionService
from bot.services.webhook_handler_mixin import _WebhookHandlerMixin
from bot.services.webhook_round_metadata_service import WebhookRoundMetadataService

# WebSocket client for push-based file notifications (optional)
try:
    from bot.services.automation.ws_client import StatsWebSocketClient, is_websocket_available
    WS_CLIENT_AVAILABLE = is_websocket_available()
except ImportError:
    WS_CLIENT_AVAILABLE = False
    StatsWebSocketClient = None

# Load environment variables if available
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # nosec B110
    pass  # python-dotenv is optional

# ==================== COMPREHENSIVE LOGGING SETUP ====================

# Import our custom logging configuration
from bot.logging_config import get_logger, log_command_execution, log_performance_warning, setup_logging

# Setup comprehensive logging system
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
setup_logging(getattr(logging, log_level))

# Get bot logger
logger = get_logger("bot.core")
webhook_logger = get_logger("bot.webhook")  # Separate logger for webhook activity

logger.info("🚀 ET:LEGACY DISCORD BOT - STARTING UP")
logger.info(f"📝 Log Level: {log_level}")
logger.info(f"🐍 Python: {sys.version}")
logger.info(f"📦 Discord.py: {discord.__version__}")

# ======================================================================


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


class UltimateETLegacyBot(
    _EndstatsPipelineMixin,
    _WebhookHandlerMixin,
    _LuaRoundStorageMixin,
    _StatsImportMixin,
    _MonitorTasksMixin,
    commands.Bot,
):
    """🚀 Ultimate consolidated ET:Legacy Discord bot with proper Cog structure"""

    @staticmethod
    def _safe_create_task(coro, *, name=None):
        """Create an asyncio task with error logging to prevent silent failures."""
        task = asyncio.create_task(coro, name=name)

        def _handle_exception(t):
            if t.cancelled():
                return
            exc = t.exception()
            if exc:
                logger.error(f"Unhandled exception in background task {t.get_name()}: {exc}", exc_info=exc)

        task.add_done_callback(_handle_exception)
        return task

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True  # Required for voice channel member detection
        super().__init__(command_prefix="!", intents=intents)

        # 📊 Database Configuration - Load config and create adapter

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
        self.processed_endstats_files = set()  # In-memory set to prevent race conditions
        self.processed_gametimes_files = set()
        self.gametimes_index_path = None
        self.endstats_retry_counts = {}
        self.endstats_retry_tasks = {}
        self.endstats_retry_max_attempts = 5
        self.endstats_retry_base_delay = 5
        self.endstats_retry_max_delay = 60
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

        # Gametimes fallback tracking (Lua webhook JSON files)
        self._load_gametimes_index()

        # 🎙️ Voice Session Service (manages gaming session detection)
        self.voice_session_service = VoiceSessionService(self, self.config, self.db_adapter)
        logger.info("✅ Voice session service initialized")

        # 📊 Activity Monitoring Service (server + voice history for website)
        self.monitoring_enabled = self.config.monitoring_enabled
        self.monitoring_service = None
        self._monitoring_started = False

        # ⏱️ Timing Debug Service (compares stats file vs Lua webhook timing)
        self.timing_debug_service = TimingDebugService(self, self.db_adapter, self.config)

        # 👥 Timing Comparison Service (per-player timing analysis for dev channel)
        self.timing_comparison_service = TimingComparisonService(self.db_adapter, self)
        logger.info("✅ Timing comparison service initialized")
        self.webhook_round_metadata_service = WebhookRoundMetadataService()
        logger.info("✅ Webhook round metadata service initialized")

        # 📊 Round Publisher Service (manages Discord auto-posting of stats)
        self.round_publisher = RoundPublisherService(
            self, self.config, self.db_adapter,
            timing_debug_service=self.timing_debug_service,
            timing_comparison_service=self.timing_comparison_service
        )
        logger.info("✅ Round publisher service initialized")

        # 🔗 Round Correlation Service (tracks R1+R2 data completeness)
        self.correlation_service = None
        if self.config.correlation_enabled:
            from bot.services.round_correlation_service import RoundCorrelationService
            self.correlation_service = RoundCorrelationService(
                self.db_adapter,
                dry_run=self.config.correlation_dry_run,
                require_schema_check=self.config.correlation_require_schema_check,
                write_error_threshold=self.config.correlation_write_error_threshold,
            )
            requested_mode = "dry-run" if self.config.correlation_dry_run else "live"
            logger.info(
                "✅ Round correlation service initialized "
                f"(requested={requested_mode}, "
                f"schema_check={self.config.correlation_require_schema_check}, "
                f"error_threshold={self.config.correlation_write_error_threshold})"
            )
        else:
            logger.warning("⚠️ Round correlation service disabled (CORRELATION_ENABLED=false)")

        # 📁 File Repository (data access layer for processed files)
        self.file_repository = FileRepository(self.db_adapter, self.config)
        logger.info("✅ File repository initialized")

        # 👥 Team Manager (auto-detect persistent teams from sessions)
        self.team_manager = TeamManager(self.db_adapter, self.config)
        logger.info("✅ Team manager initialized")

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
        self._last_dead_hour_log = None  # Track dead hour logging to reduce log spam

        # Webhook rate limiting (prevent DoS)
        from collections import defaultdict, deque

        self._webhook_rate_limit = defaultdict(deque)
        self._webhook_rate_limit_max = 5  # Max 5 triggers per minute
        self._webhook_rate_limit_window = 60  # Seconds
        self._stats_ready_rate_limit = defaultdict(deque)
        self._stats_ready_rate_limit_max = 4
        self._stats_ready_rate_limit_window = 30  # Lightweight burst protection
        self._processed_webhook_message_ids = deque()
        self._processed_webhook_message_id_set = set()
        self._webhook_message_dedupe_ttl = 600  # Seconds

        # Pending metadata queue keyed by map+round (supports repeated events safely)
        self._pending_round_metadata = defaultdict(list)
        self._pending_metadata_ttl_seconds = 3 * 3600
        self._pending_metadata_max_per_key = 8

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
        self.owner_user_id = self.config.owner_user_id

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

        # 🚨 Error tracking for admin notifications
        self._consecutive_errors = {}

    # =========================================================================
    # 🚨 ADMIN NOTIFICATION SYSTEM
    # =========================================================================

    async def alert_admins(self, title: str, description: str, severity: str = "warning"):
        """
        Send critical error notifications to admin channel.

        Args:
            title: Short title for the alert
            description: Detailed description of the issue
            severity: One of "info", "warning", "error", "critical"

        Returns:
            True if notification was sent, False otherwise
        """
        if not self.admin_channel_id:
            logger.warning(f"Cannot send admin alert (no admin_channel_id configured): {title}")
            return False

        try:
            channel = self.get_channel(self.admin_channel_id)
            if not channel:
                logger.error(f"Admin channel {self.admin_channel_id} not found")
                return False

            # Color based on severity
            colors = {
                "info": 0x3498DB,      # Blue
                "warning": 0xF39C12,   # Orange
                "error": 0xE74C3C,     # Red
                "critical": 0x8B0000,  # Dark Red
            }
            color = colors.get(severity, colors["warning"])

            # Emoji based on severity
            emojis = {
                "info": "ℹ️",
                "warning": "⚠️",
                "error": "❌",
                "critical": "🚨",
            }
            emoji = emojis.get(severity, "⚠️")

            embed = discord.Embed(
                title=f"{emoji} {title}",
                description=description[:4000],  # Discord limit
                color=color,
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"Severity: {severity.upper()}")

            await channel.send(embed=embed)
            logger.info(f"Admin alert sent: {title} ({severity})")
            return True

        except discord.Forbidden:
            logger.error(f"Permission denied to send to admin channel {self.admin_channel_id}")
            return False
        except Exception as e:
            logger.error(f"Failed to send admin alert: {e}")
            return False

    async def track_error(self, error_key: str, error_msg: str, max_consecutive: int = 3):
        """
        Track consecutive errors and alert admins when threshold is reached.

        Args:
            error_key: Unique identifier for this error type (e.g., "ssh_monitor")
            error_msg: Human-readable error message
            max_consecutive: Number of consecutive errors before alerting

        Returns:
            Current consecutive error count for this key
        """
        self._consecutive_errors[error_key] = self._consecutive_errors.get(error_key, 0) + 1
        count = self._consecutive_errors[error_key]

        if count == max_consecutive:
            await self.alert_admins(
                f"{error_key.replace('_', ' ').title()} Failing",
                f"**{count} consecutive failures detected.**\n\n"
                f"Latest error: {error_msg}\n\n"
                f"This service may need attention.",
                severity="error"
            )
        elif count > max_consecutive and count % 10 == 0:
            # Reminder every 10 failures after threshold
            await self.alert_admins(
                f"{error_key.replace('_', ' ').title()} Still Failing",
                f"**{count} total consecutive failures.**\n\n"
                f"Latest error: {error_msg}",
                severity="critical"
            )

        return count

    def reset_error_tracking(self, error_key: str):
        """Reset consecutive error count for a key (call on success)."""
        if error_key in self._consecutive_errors:
            self._consecutive_errors[error_key] = 0

    async def close(self):
        """
        🔌 Clean up database connections and close bot gracefully
        """
        try:
            if self.monitoring_service and self._monitoring_started:
                await self.monitoring_service.stop()
            if hasattr(self, 'db_adapter'):
                await self.db_adapter.close()
                logger.info("✅ Database adapter closed successfully")
        except Exception as e:
            logger.error(f"⚠️ Error closing database adapter: {e}")

        # Call parent close
        await super().close()

    async def validate_database_schema(self):
        """
        ✅ CRITICAL: Validate database has the required unified schema columns
        Prevents silent failures if wrong schema is used
        Supports both SQLite and PostgreSQL
        """
        try:
            # Query schema (PostgreSQL)
            query = """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'player_comprehensive_stats'
                ORDER BY ordinal_position
            """
            columns = await self.db_adapter.fetch_all(query)
            column_names = [col[0] for col in columns]

            actual_columns = len(column_names)
            # Additive columns are valid; only the required unified-schema contract matters.
            required_columns = [
                "round_id",
                "player_guid",
                "player_name",
                "kills",
                "deaths",
                "damage_given",
                "damage_received",
                "time_played_seconds",
                "time_dead_minutes",
                "time_dead_ratio",
                "kill_assists",
                "dynamites_planted",
                "times_revived",
                "revives_given",
                "most_useful_kills",
                "useless_kills",
                "kill_steals",
                "denied_playtime",
                "constructions",
            ]

            missing = [
                col for col in required_columns if col not in column_names
            ]
            if missing:
                schema_hint = "SPLIT (deprecated)" if actual_columns == 35 else "UNKNOWN"
                error_msg = (
                    f"❌ DATABASE SCHEMA MISMATCH!\n"
                    f"Found: {actual_columns} columns\n"
                    f"Schema: {schema_hint}\n"
                    f"Missing required unified-schema columns: {missing}"
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            logger.info(
                f"✅ Schema validated: {actual_columns} columns with required unified schema on "
                f"{self.config.database_type.upper()}"
            )

        except Exception as e:
            logger.error(f"❌ Schema validation failed: {e}")
            raise

    def _load_gametimes_index(self) -> None:
        """Load processed gametimes filenames from local index (best-effort)."""
        if not self.config.gametimes_enabled:
            return
        local_dir = self.config.gametimes_local_path
        if not local_dir:
            return
        os.makedirs(local_dir, exist_ok=True)
        index_path = os.path.join(local_dir, ".processed_gametimes.txt")
        self.gametimes_index_path = index_path
        if not os.path.exists(index_path):
            return
        try:
            with open(index_path, encoding="utf-8") as handle:
                for line in handle:
                    filename = line.strip()
                    if filename:
                        self.processed_gametimes_files.add(filename)
            logger.info(
                f"📁 Loaded {len(self.processed_gametimes_files)} processed gametimes entries"
            )
        except Exception as e:
            logger.debug(f"Gametime index load failed: {e}")

    def _mark_gametime_processed(self, filename: str) -> None:
        if not filename or filename in self.processed_gametimes_files:
            return
        self.processed_gametimes_files.add(filename)
        if not self.gametimes_index_path:
            return
        try:
            with open(self.gametimes_index_path, "a", encoding="utf-8") as handle:
                handle.write(f"{filename}\n")
        except Exception as e:
            logger.debug(f"Gametime index update failed: {e}")

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

        # 🔗 Correlation guardrail initialization (schema preflight/live fallback)
        if self.correlation_service:
            await self.correlation_service.initialize()
            effective_mode = "DRY-RUN" if self.correlation_service.dry_run else "LIVE"
            guardrail_reason = getattr(self.correlation_service, "guardrail_reason", None)
            if guardrail_reason:
                logger.warning(
                    f"⚠️ Correlation service effective mode={effective_mode}, "
                    f"guardrail_reason={guardrail_reason}"
                )
            else:
                logger.info(f"✅ Correlation service effective mode={effective_mode}")


        # � Load Admin Cog (database operations, maintenance commands)
        try:
            from bot.cogs.admin_cog import AdminCog
            await self.add_cog(AdminCog(self))
            logger.info("✅ Admin Cog loaded (11 admin commands)")
        except Exception as e:
            logger.error(f"❌ Failed to load Admin Cog: {e}", exc_info=True)

        # 🔒 Load Permission Management Cog (user whitelist, permission tiers)
        try:
            from bot.cogs.permission_management_cog import PermissionManagement
            await self.add_cog(PermissionManagement(self))
            logger.info("✅ Permission Management Cog loaded (admin_add, admin_remove, admin_list, admin_audit)")
        except Exception as e:
            logger.error(f"❌ Failed to load Permission Management Cog: {e}", exc_info=True)

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

        # 📊 MATCHUP ANALYTICS: Lineup vs lineup statistics
        try:
            from bot.cogs.matchup_cog import MatchupCog
            await self.add_cog(MatchupCog(self))
            logger.info('✅ Matchup Cog loaded (matchup, synergy, nemesis)')
        except Exception as e:
            logger.error(f'Failed to load Matchup Cog: {e}', exc_info=True)

        # 📈 PLAYER ANALYTICS: Consistency, map affinity, playstyle analysis
        try:
            from bot.cogs.analytics_cog import AnalyticsCog
            await self.add_cog(AnalyticsCog(self))
            logger.info('✅ Analytics Cog loaded (consistency, map_stats, playstyle, awards, fatigue)')
        except Exception as e:
            logger.error(f'Failed to load Analytics Cog: {e}', exc_info=True)

        # �🎯 FIVEEYES: Load synergy analytics cog (SAFE - disabled by default)
        # synergy_analytics disabled — analytics package never created

        # 🎯 PROXIMITY TRACKER: Load combat engagement analytics (SAFE - disabled by default)
        try:
            await self.load_extension("bot.cogs.proximity_cog")
            status = "ENABLED" if self.config.proximity_enabled else "disabled"
            logger.info(f"✅ Proximity Tracker cog loaded ({status})")
        except Exception as e:
            logger.warning(f"⚠️  Could not load Proximity Tracker cog: {e}")
            logger.warning("Bot will continue without proximity tracking features")

        # 🎮 SERVER CONTROL: Load server control cog (optional)
        try:
            await self.load_extension("bot.cogs.server_control")
            logger.info("✅ Server Control cog loaded")
        except Exception as e:
            logger.warning(f"⚠️  Could not load Server Control cog: {e}")
            logger.warning("Bot will continue without server control features")

        # 🔮 COMPETITIVE ANALYTICS: Load prediction cogs (Phase 5)
        try:
            await self.load_extension("bot.cogs.predictions_cog")
            logger.info("✅ Predictions cog loaded (!predictions, !prediction_stats, !my_predictions)")
        except Exception as e:
            logger.warning(f"⚠️  Could not load Predictions cog: {e}")
            logger.warning("Bot will continue without prediction commands")

        try:
            await self.load_extension("bot.cogs.admin_predictions_cog")
            logger.info("✅ Admin Predictions cog loaded (!admin_predictions, !update_prediction_outcome)")
        except Exception as e:
            logger.warning(f"⚠️  Could not load Admin Predictions cog: {e}")
            logger.warning("Bot will continue without admin prediction commands")

        # 📊 AVAILABILITY POLL: Daily gaming availability tracking
        try:
            from bot.cogs.availability_poll_cog import AvailabilityPollCog
            await self.add_cog(AvailabilityPollCog(self))
            status = "ENABLED" if self.config.availability_poll_enabled else "disabled"
            logger.info(f"✅ Availability Poll cog loaded ({status})")
        except Exception as e:
            logger.warning(f"⚠️ Could not load Availability Poll cog: {e}")

        # 🤖 AUTOMATION: Initialize automation services
        try:
            from bot.services.automation import DatabaseMaintenance, HealthMonitor, MetricsLogger, SSHMonitor

            # Get configuration from already-parsed channel config
            admin_channel_id = self.admin_channel_id

            # For PostgreSQL, we don't have a db_path, but metrics_logger needs one for its own SQLite db
            # Use a sensible default path for metrics database
            db_type = str(getattr(self.config, "database_type", "postgresql")).strip().lower()
            metrics_db_path = getattr(self.config, "metrics_db_path", "")

            if db_type in ("postgresql", "postgres"):
                sqlite_path = getattr(self.config, "sqlite_db_path", "") or ""
                default_metrics_path = os.path.join("logs", "metrics", "metrics.db")
                sqlite_abs = os.path.abspath(sqlite_path) if sqlite_path else ""
                metrics_abs = os.path.abspath(metrics_db_path) if metrics_db_path else ""
                metrics_basename = os.path.basename(metrics_abs) if metrics_abs else ""
                needs_dedicated_metrics_store = (
                    not metrics_db_path
                    or (sqlite_abs and metrics_abs == sqlite_abs)
                    or metrics_basename == "etlegacy.db"
                )
                if needs_dedicated_metrics_store:
                    metrics_db_path = default_metrics_path
                    logger.info("Using dedicated metrics SQLite store for PostgreSQL mode")

            # Create automation services in correct order (MetricsLogger first, it's needed by HealthMonitor)
            self.metrics = MetricsLogger(db_path=metrics_db_path)
            await self.metrics.initialize_metrics_db()
            self.ssh_monitor = SSHMonitor(self)
            self.health_monitor = HealthMonitor(self, admin_channel_id, self.metrics)
            backup_path: str | None = None
            if db_type in ("sqlite", "sqlite3"):
                backup_candidate = self.db_path or self.config.sqlite_db_path
                if backup_candidate and os.path.exists(backup_candidate):
                    backup_path = backup_candidate
            self.db_maintenance = DatabaseMaintenance(self, backup_path, admin_channel_id)

            logger.info("✅ Automation services initialized (SSH, Health, Metrics, DB Maintenance)")

            # Load automation commands cog
            await self.load_extension("bot.cogs.automation_commands")
            logger.info("✅ Automation Commands cog loaded")

            # SSHMonitor auto-start disabled: endstats_monitor task handles SSH + Discord posting.
            # SSHMonitor remains available for manual control via !automation commands.
            logger.info(f"🔍 Bot ssh_enabled={self.ssh_enabled} (SSHMonitor available for manual use only)")

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
        if not self.live_status_updater.is_running():
            self.live_status_updater.start()
        # scheduled_monitoring_check task removed - see performance optimization
        # voice_session_monitor disabled - using on_voice_state_update event instead (more efficient)
        # if not self.voice_session_monitor.is_running():
        #     self.voice_session_monitor.start()
        logger.info("✅ Background tasks started (optimized SSH monitoring with voice detection)")

        # WebSocket push notifications: disabled in practice (VPS uses webhook instead).
        # Kept for potential future use; gated behind WS_ENABLED env var.
        self.ws_client = None
        if self.config.ws_enabled and WS_CLIENT_AVAILABLE:
            try:
                self.ws_client = StatsWebSocketClient(
                    self.config,
                    on_new_file=self._handle_ws_file_notification
                )
                self.ws_client.start()
                logger.info("🔌 WebSocket client started")
            except Exception as e:
                logger.warning(f"⚠️ WebSocket client failed: {e}")
        else:
            logger.debug("📡 WebSocket push disabled (using SSH polling)")

        # 🎯 Proximity Tracker Cog (optional, isolated)
        # NOTE: It is already loaded above via load_extension("bot.cogs.proximity_cog").
        # Keep this as a no-op guard so startup does not create duplicate cog instances.
        try:
            if self.get_cog("Proximity") is not None:
                logger.info("⏭️ Proximity Cog already loaded via extension")
            elif self.config.proximity_enabled or self.config.proximity_discord_commands:
                from bot.cogs.proximity_cog import ProximityCog
                await self.add_cog(ProximityCog(self))
                logger.info("✅ Proximity Cog loaded (fallback)")
            else:
                logger.info("⏭️ Proximity Cog not enabled")
        except Exception as e:
            logger.warning(f"⚠️ Proximity Cog failed to load: {e}")

        logger.info("✅ Ultimate Bot initialization complete!")
        logger.info(
            f"📋 Commands available: {[cmd.name for cmd in self.commands]}"
        )

    async def _handle_ws_file_notification(self, filename: str):
        """
        Handle file notification from WebSocket push.

        Called by StatsWebSocketClient when VPS notifies of new file.
        Downloads file via SSH, processes, and posts to Discord.

        Args:
            filename: Name of the new stats file on remote server
        """
        try:
            logger.info(f"📥 WebSocket notification: {filename}")

            # Check if already processed (race condition prevention)
            # should_process_file returns True if file needs processing
            if not await self.file_tracker.should_process_file(filename):
                logger.debug(f"⏭️ File already processed: {filename}")
                return

            # Build SSH config
            ssh_config = {
                "host": self.config.ssh_host,
                "port": self.config.ssh_port,
                "user": self.config.ssh_user,
                "key_path": self.config.ssh_key_path,
                "remote_path": self.config.ssh_remote_path,
            }

            # Download file via SSH
            local_path = await self.ssh_download_file(
                ssh_config, filename, self.config.stats_directory
            )

            if not local_path:
                logger.error(f"❌ Failed to download: {filename}")
                return

            # Track download time for grace period logic (fallback SSH uses this)
            self.last_file_download_time = datetime.now()

            # Wait 3 seconds for file to fully write on remote
            logger.debug("⏳ Waiting 3s for file to fully write...")
            await asyncio.sleep(3)

            # Check for pending Lua metadata (from STATS_READY or gametime)
            override_metadata = self._pop_pending_metadata(filename)

            # Process the file (parse + import + Discord post)
            result = await self.process_gamestats_file(local_path, filename, override_metadata=override_metadata)

            if result and result.get('success'):
                # Post to Discord via round publisher
                try:
                    await self.round_publisher.publish_round_stats(filename, result)
                    logger.info(f"✅ WebSocket-triggered import complete: {filename}")
                except Exception as post_err:
                    logger.error(f"❌ Discord post FAILED for {filename}: {post_err}", exc_info=True)
                    await self.track_error("discord_posting", f"Failed to post {filename}: {post_err}", max_consecutive=2)
            else:
                logger.warning(f"⚠️ File processed but no stats: {filename}")

        except Exception as e:
            logger.error(f"❌ WebSocket file handler error: {e}", exc_info=True)

    async def initialize_database(self):
        # Verify critical tables exist
        required_tables = [
            "rounds",
            "player_comprehensive_stats",
            "weapon_comprehensive_stats",
            "player_links",
            "processed_files",
        ]

        # Query table existence (PostgreSQL)
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
        import shlex

        import paramiko

        def _list_files_sync():
            ssh = None
            try:
                from bot.automation.ssh_handler import configure_ssh_host_key_policy

                ssh = paramiko.SSHClient()
                configure_ssh_host_key_policy(ssh)

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
                    except Exception:  # nosec B110
                        logger.debug("SSH connection cleanup failed", exc_info=True)

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

    async def process_gamestats_file(self, local_path, filename, override_metadata=None):
        """
        Process a gamestats file: parse and import to database

        Args:
            local_path: Path to the downloaded stats file
            filename: Original filename for tracking
            override_metadata: Optional dict from Lua webhook with accurate timing:
                - actual_duration_seconds: Real played time (correct on surrender)
                - winner_team: Which team won
                - total_pause_seconds: Time spent paused
                - pause_count: Number of pauses
                - round_start_unix, round_end_unix: Unix timestamps
                - end_reason: "objective", "surrender", "time_expired"

        Returns:
            dict with keys: success, round_id, player_count, error
        """
        try:
            logger.info(f"⚙️ Processing {filename}...")

            # 🔥 FIX: Use PostgreSQL database manager instead of bot's own import logic
            # This ensures proper transaction handling and constraint checks
            db_type = str(getattr(self.config, "database_type", "")).strip().lower()
            if db_type in {"postgres", "postgresql"}:
                from pathlib import Path

                from postgresql_database_manager import PostgreSQLDatabaseManager

                # Create database manager instance and share the bot's existing pool
                db_manager = PostgreSQLDatabaseManager()
                # Reuse the same correlation service so stats imports participate
                # in the same round completeness lifecycle as webhook/gametime data.
                if hasattr(self, 'correlation_service') and self.correlation_service:
                    db_manager._correlation_service = self.correlation_service
                # Reuse the bot's existing asyncpg pool instead of creating a new one
                if hasattr(self, 'db_adapter') and hasattr(self.db_adapter, 'pool') and self.db_adapter.pool:
                    db_manager.pool = self.db_adapter.pool
                else:
                    await db_manager.connect()

                success, message = await db_manager.process_file(Path(local_path))

                # Only disconnect if we created our own pool
                if not (hasattr(self, 'db_adapter') and hasattr(self.db_adapter, 'pool') and self.db_adapter.pool):
                    await db_manager.disconnect()

                if not success:
                    # Mark parse failures as processed (with success=FALSE) to prevent
                    # infinite retry loops on legitimately unparseable files (e.g. header-only)
                    try:
                        await self.file_tracker.mark_processed(
                            filename, success=False, error_msg=message, file_path=local_path
                        )
                        self.processed_files.add(filename)
                        logger.warning(f"Marked {filename} as failed (will not retry): {message}")
                    except Exception as mark_err:
                        logger.debug(f"Failed to mark {filename} as failed: {mark_err}")
                    raise Exception(f"Import failed: {message}")

                # Parse file to get player count for return value
                from bot.community_stats_parser import C0RNP0RN3StatsParser
                parser = C0RNP0RN3StatsParser(
                    round_match_window_minutes=self.config.round_match_window_minutes
                )
                stats_data = parser.parse_stats_file(local_path)

                # Resolve round_id for live posting (Postgres path)
                # Brief delay lets the DB import commit before round_linker queries — MED-BOT-003
                await asyncio.sleep(2)
                resolved_round_id = None
                if stats_data and not stats_data.get("error"):
                    round_meta = {
                        "map_name": stats_data.get("map_name") or stats_data.get("map"),
                        "round_number": stats_data.get("round_num") or stats_data.get("round_number") or stats_data.get("round"),
                    }
                    resolved_round_id = await self._resolve_round_id_for_metadata(
                        filename, round_meta
                    )

                # Mark as processed (with SHA256 hash for integrity verification)
                try:
                    await self.file_tracker.mark_processed(
                        filename, success=True, file_path=local_path
                    )
                    self.processed_files.add(filename)
                except Exception as e:
                    logger.debug(f"Failed to mark {filename} as processed: {e}")

                # Reset error tracking on success
                self.reset_error_tracking("file_processing")

                # Apply override metadata from Lua webhook if provided
                # This gives us accurate timing even on surrenders
                if override_metadata:
                    await self._apply_round_metadata_override(filename, override_metadata)

                # Live achievements: announce new milestones (non-blocking)
                if stats_data:
                    self._safe_create_task(self._post_live_achievements(stats_data), name="live_achievements")

                return {
                    "success": True,
                    "round_id": resolved_round_id,
                    "player_count": len(stats_data.get("players", [])) if stats_data else 0,
                    "error": None,
                    "stats_data": stats_data if stats_data else {},
                    "override_metadata": override_metadata,  # Pass through for publisher
                }
            else:
                # SQLite fallback - use old import logic
                from bot.community_stats_parser import C0RNP0RN3StatsParser

                # Parse using existing parser (it reads the file itself)
                parser = C0RNP0RN3StatsParser(
                    round_match_window_minutes=self.config.round_match_window_minutes
                )
                stats_data = parser.parse_stats_file(local_path)

                if not stats_data or stats_data.get("error"):
                    error_msg = (
                        stats_data.get("error") if stats_data else "No data"
                    )
                    raise Exception(f"Parser error: {error_msg}")

                # Import to database using existing import logic
                round_id = await self._import_stats_to_db(stats_data, filename)
                # Mark file as processed only after successful import (with SHA256)
                try:
                    await self.file_tracker.mark_processed(
                        filename, success=True, file_path=local_path
                    )
                    self.processed_files.add(filename)
                except Exception as e:
                    logger.debug(f"Failed to mark {filename} as processed: {e}")

                # Reset error tracking on success
                self.reset_error_tracking("file_processing")

                # Live achievements: announce new milestones (non-blocking)
                if stats_data:
                    self._safe_create_task(self._post_live_achievements(stats_data), name="live_achievements")

                return {
                    "success": True,
                    "round_id": round_id,
                    "player_count": len(stats_data.get("players", [])),
                    "error": None,
                    "stats_data": stats_data,
                }

        except Exception as e:
            logger.error(f"❌ Processing failed for {filename}: {e}")

            # Track consecutive processing failures
            await self.track_error(
                "file_processing",
                f"Failed to process {filename}: {e}",
                max_consecutive=5
            )

            return {
                "success": False,
                "round_id": None,
                "player_count": 0,
                "error": str(e),
                "stats_data": None,
            }

    async def _resolve_round_id_for_metadata(self, filename: str | None, metadata: dict):
        """
        Resolve round_id using shared round_linker logic.
        This avoids mismatches between stats filenames, Lua timestamps, and endstats.
        """
        try:
            from datetime import datetime

            from bot.core.round_linker import resolve_round_id_with_reason

            map_name = metadata.get('map_name') or metadata.get('map')
            round_number = metadata.get('round_number') or metadata.get('round')
            round_date = metadata.get('round_date')
            round_time = metadata.get('round_time')

            if (not map_name or not round_number) and filename:
                match = re.match(
                    r'^(\d{4}-\d{2}-\d{2})-(\d{6})-(.+)-round-(\d+)\.txt$',
                    filename
                )
                if match:
                    round_date = round_date or match.group(1)
                    round_time = round_time or match.group(2)
                    map_name = map_name or match.group(3)
                    round_number = round_number or int(match.group(4))

            if not map_name or not round_number:
                return None

            try:
                round_number = int(round_number)
            except (TypeError, ValueError):
                return None

            target_dt = None
            try:
                round_end_unix = int(metadata.get('round_end_unix', 0) or 0)
            except (TypeError, ValueError):
                round_end_unix = 0
            try:
                round_start_unix = int(metadata.get('round_start_unix', 0) or 0)
            except (TypeError, ValueError):
                round_start_unix = 0

            if round_end_unix:
                target_dt = datetime.fromtimestamp(round_end_unix)
            elif round_start_unix:
                target_dt = datetime.fromtimestamp(round_start_unix)

            window_minutes = getattr(self.config, "round_match_window_minutes", 45)
            round_id, diag = await resolve_round_id_with_reason(
                self.db_adapter,
                map_name,
                round_number,
                target_dt=target_dt,
                round_date=round_date,
                round_time=round_time,
                window_minutes=window_minutes,
            )
            reason_code = diag.get("reason_code")
            if round_id:
                logger.info(
                    "🔗 Round linker resolved: map=%s round=%s round_id=%s reason=%s candidates=%s diff_s=%s",
                    map_name,
                    round_number,
                    round_id,
                    reason_code,
                    diag.get("candidate_count"),
                    diag.get("best_diff_seconds"),
                )
            else:
                logger.warning(
                    "⚠️ Round linker unresolved: map=%s round=%s reason=%s candidates=%s parsed=%s "
                    "best_diff_s=%s round_date=%s round_time=%s",
                    map_name,
                    round_number,
                    reason_code,
                    diag.get("candidate_count"),
                    diag.get("parsed_candidate_count"),
                    diag.get("best_diff_seconds"),
                    round_date,
                    round_time,
                )
            return round_id
        except Exception as e:
            logger.debug(f"Round ID resolve failed: {e}")
            return None

    async def _resolve_round_correlation_context(
        self,
        round_id: int | None,
        fallback_match_id: str,
        fallback_map_name: str,
        fallback_round_number: int,
    ) -> tuple[str, str, int]:
        """
        Resolve canonical correlation identity from rounds when round_id is known.

        This keeps R1/R2 timestamp reality intact in source payloads while ensuring
        correlation keys align with canonical rounds.match_id.
        """
        canonical_match_id = fallback_match_id
        canonical_map_name = fallback_map_name
        canonical_round_number = fallback_round_number

        if not round_id:
            return canonical_match_id, canonical_map_name, canonical_round_number

        try:
            row = await self.db_adapter.fetch_one(
                "SELECT match_id, map_name, round_number FROM rounds WHERE id = $1",
                (round_id,),
            )
            if row:
                if row[0]:
                    canonical_match_id = row[0]
                if row[1]:
                    canonical_map_name = row[1]
                if row[2] is not None:
                    canonical_round_number = int(row[2])
        except Exception as e:
            logger.debug(f"Round correlation context resolve failed for round_id={round_id}: {e}")

        return canonical_match_id, canonical_map_name, canonical_round_number

    async def _post_live_achievements(self, stats_data: dict) -> None:
        """
        Post achievement unlocks live after a round is imported.

        Uses parsed stats data to collect GUIDs, then checks lifetime
        milestones via AchievementSystem and posts any new unlocks.
        """
        try:
            mode = getattr(self.config, "live_achievement_mode", "off")
            mode = str(mode).strip().lower()
            if mode == "off":
                return

            if not stats_data:
                return

            players = stats_data.get("players", [])
            if not players:
                return

            channel_id = (
                self.config.production_channel_id
                or self.config.general_channel_id
                or 0
            )
            if not channel_id:
                return

            channel = self.get_channel(channel_id)
            if not channel:
                return

            guids = {p.get("guid") for p in players if p.get("guid")}
            if not guids:
                return

            if mode == "individual":
                for guid in guids:
                    await self.achievements.check_player_achievements(
                        guid, channel=channel
                    )
                return

            # summary mode: collect unlocks but emit a single embed
            all_unlocks = []
            for guid in guids:
                unlocks = await self.achievements.check_player_achievements(
                    guid, channel=None
                )
                if unlocks:
                    all_unlocks.extend(unlocks)

            if all_unlocks:
                await self._post_live_achievement_summary(all_unlocks, channel)

        except Exception as e:
            logger.error(f"Live achievement posting failed: {e}", exc_info=True)

    async def _post_live_achievement_summary(self, unlocks: list, channel) -> None:
        """
        Post one compact round summary for newly unlocked achievements.
        """
        try:
            by_player = {}
            for unlock in unlocks:
                player = unlock.get("player_name", "Unknown")
                title = unlock.get("achievement", {}).get("title", "Unknown")
                if player not in by_player:
                    by_player[player] = []
                if title not in by_player[player]:
                    by_player[player].append(title)

            if not by_player:
                return

            lines = []
            ordered_players = sorted(
                by_player.items(),
                key=lambda item: (-len(item[1]), item[0].lower())
            )
            for player_name, titles in ordered_players:
                preview = ", ".join(titles[:4])
                if len(titles) > 4:
                    preview += f", +{len(titles) - 4} more"
                lines.append(f"**{player_name}**: {preview}")

            max_lines = 12
            hidden_count = max(0, len(lines) - max_lines)
            shown_lines = lines[:max_lines]
            if hidden_count:
                shown_lines.append(f"... and {hidden_count} more player(s)")

            embed = discord.Embed(
                title="🏆 Achievement Round Summary",
                description="New achievements unlocked this round.",
                color=discord.Color.gold(),
                timestamp=datetime.now(),
            )
            embed.add_field(
                name=f"Players ({len(by_player)})",
                value="\n".join(shown_lines),
                inline=False,
            )
            embed.set_footer(text=f"{len(unlocks)} unlock(s) • mode=summary")

            await channel.send(embed=embed)
            logger.info(
                f"🏆 Posted achievement summary: {len(unlocks)} unlocks across {len(by_player)} players"
            )
        except Exception as e:
            logger.error(f"Failed to post achievement summary: {e}", exc_info=True)

    async def _apply_round_metadata_override(self, filename: str, metadata: dict):
        """
        Update a round's timing data with accurate values from Lua webhook.

        This fixes the surrender timing bug where stats files show full map duration
        instead of actual played time. The Lua script captures the real round_end_unix
        when the gamestate transitions to INTERMISSION.

        Args:
            filename: Stats filename to identify the round
            metadata: Dict with accurate timing from Lua:
                - actual_duration_seconds
                - winner_team
                - total_pause_seconds
                - pause_count
                - round_start_unix
                - round_end_unix
                - end_reason
        """
        try:
            round_id = await self._resolve_round_id_for_metadata(filename, metadata)
            if not round_id:
                logger.warning(f"Could not resolve round_id for metadata override: {filename}")
                return

            # DEBUG LOGGING: Compare Lua timing vs stats file timing
            # This helps verify the surrender fix is working correctly
            # Query current values from DB (from stats file)
            compare_query = """
                SELECT actual_duration_seconds, time_limit, winner_team
                FROM rounds WHERE id = $1
            """
            current_values = await self.db_adapter.fetch_one(compare_query, (round_id,))
            if current_values:
                stats_file_duration = current_values[0] if current_values[0] else 0
                stats_file_limit = current_values[1] if current_values[1] else 0
                stats_file_winner = current_values[2] if current_values[2] else 0
                lua_duration = metadata.get('actual_duration_seconds', 0)
                lua_winner = metadata.get('winner_team', 0)

                # Log comparison (always to file, helpful for debugging)
                timing_diff = abs(stats_file_duration - lua_duration)
                logger.info(
                    f"🔬 TIMING DEBUG [{filename}]:\n"
                    f"   Stats file: duration={stats_file_duration}s, limit={stats_file_limit}s, winner={stats_file_winner}\n"
                    f"   Lua webhook: duration={lua_duration}s, winner={lua_winner}, "
                    f"end_reason={metadata.get('end_reason', 'unknown')}\n"
                    f"   Difference: {timing_diff}s {'⚠️ SURRENDER FIX APPLIED' if timing_diff > 60 else '✓ within tolerance'}"
                )

                # If there's a big difference, it's likely a surrender scenario
                if timing_diff > 60:
                    logger.info(
                        f"   📋 Surrender detected! Stats said {stats_file_duration}s, "
                        f"actual was {lua_duration}s (saved {timing_diff}s of fake time)"
                    )

            # Build update query for available metadata fields
            # Only update columns that exist in the schema
            update_fields = []
            update_values = []
            param_num = 1

            # Always update winner_team if provided
            if 'winner_team' in metadata and metadata['winner_team']:
                update_fields.append(f"winner_team = ${param_num}")
                update_values.append(metadata['winner_team'])
                param_num += 1

            # Check if new columns exist before trying to update them
            # These may not be present until schema migration is run
            try:
                schema_check = await self.db_adapter.fetch_one(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'rounds' AND column_name = 'actual_duration_seconds'"
                )
                has_new_columns = schema_check is not None
            except Exception:
                has_new_columns = False

            if has_new_columns:
                if 'actual_duration_seconds' in metadata:
                    update_fields.append(f"actual_duration_seconds = ${param_num}")
                    update_values.append(metadata['actual_duration_seconds'])
                    param_num += 1

                if 'total_pause_seconds' in metadata:
                    update_fields.append(f"total_pause_seconds = ${param_num}")
                    update_values.append(metadata['total_pause_seconds'])
                    param_num += 1

                if 'pause_count' in metadata:
                    update_fields.append(f"pause_count = ${param_num}")
                    update_values.append(metadata['pause_count'])
                    param_num += 1

                if 'end_reason' in metadata:
                    update_fields.append(f"end_reason = ${param_num}")
                    update_values.append(metadata['end_reason'])
                    param_num += 1

                if 'round_start_unix' in metadata:
                    update_fields.append(f"round_start_unix = ${param_num}")
                    update_values.append(metadata['round_start_unix'])
                    param_num += 1

                if 'round_end_unix' in metadata:
                    update_fields.append(f"round_end_unix = ${param_num}")
                    update_values.append(metadata['round_end_unix'])
                    param_num += 1

            if not update_fields:
                logger.debug("No metadata fields to update")
                return

            update_values.append(round_id)
            update_query = f"""
                UPDATE rounds
                SET {', '.join(update_fields)}
                WHERE id = ${param_num}
            """

            await self.db_adapter.execute(update_query, tuple(update_values))

            logger.info(
                f"✅ Applied Lua metadata to round {round_id}: "
                f"winner={metadata.get('winner_team')}, "
                f"duration={metadata.get('actual_duration_seconds')}s, "
                f"pauses={metadata.get('pause_count')}"
            )

            # FIX: When Lua webhook provides actual_duration_seconds, use it to correct
            # player stats that were computed with an inflated header-fallback time_played_seconds.
            # This handles the ET:Legacy R2 actual_time quirk where stats files report cumulative
            # server uptime instead of round duration.
            # See: DPM Bug Investigation (Feb 27, 2026) - root cause: header fallback in parser
            lua_duration = metadata.get('actual_duration_seconds')
            if lua_duration and lua_duration > 0:
                try:
                    fix_query = """
                        UPDATE player_comprehensive_stats
                        SET
                            time_played_seconds = $1,
                            time_played_minutes = $1 / 60.0,
                            dpm = CASE WHEN $1 > 0 THEN (damage_given * 60.0) / $1 ELSE 0 END
                        WHERE round_id = $2
                          AND time_played_seconds > $1 * 1.5
                    """
                    await self.db_adapter.execute(fix_query, (lua_duration, round_id))
                    logger.debug(
                        f"✅ Fixed player stats for round {round_id} using Lua duration: "
                        f"clamped inflated time_played_seconds to {lua_duration}s"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to fix player stats for round {round_id}: {e} "
                        "(non-fatal, round still imported correctly)"
                    )

            # Link Lua rows to this round_id when possible
            await self._link_lua_round_teams(round_id, metadata)

        except Exception as e:
            logger.warning(f"Failed to apply round metadata override: {e}")
            # Non-fatal - stats were still imported correctly


            # Non-fatal - round was still imported successfully


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


    # ==================== WEBSITE LIVE STATUS UPDATER ====================


    # ==================== BOT EVENTS ====================

    async def on_message(self, message):
        """Process messages and filter by allowed channels"""
        # ========== WEBHOOK TRIGGER HANDLER ==========
        # Check if this is a webhook notification from VPS to trigger stats processing
        # Webhook posts to control channel, bot processes and posts to production channel
        if await self._handle_webhook_trigger(message):
            return  # Handled as webhook trigger, don't process as command

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

    def _normalize_lua_round_for_metadata_paths(self, raw_round) -> int:
        """
        Normalize Lua round numbering for webhook/gametime metadata paths.
        ET:Legacy may report g_currentRound=0 for stopwatch R2.
        """
        if raw_round is None:
            return 0
        raw_text = str(raw_round).strip()
        if not raw_text:
            return 0
        try:
            parsed = int(raw_text)
        except (TypeError, ValueError):
            return 0
        if parsed == 0 and raw_text.lstrip("+-") == "0":
            return 2
        if parsed < 0:
            return 0
        return parsed

    def _normalize_metadata_map_name(self, map_name: str | None) -> str:
        return str(map_name or "").strip().lower()

    def _pending_metadata_key(self, map_name: str | None, round_number) -> str | None:
        normalized_map = self._normalize_metadata_map_name(map_name)
        normalized_round = self._normalize_lua_round_for_metadata_paths(round_number)
        if not normalized_map or normalized_round <= 0:
            return None
        return f"{normalized_map}_R{normalized_round}"

    def _metadata_event_unix(self, metadata: dict) -> int:
        for field in ("round_end_unix", "round_start_unix"):
            try:
                value = int(metadata.get(field, 0) or 0)
            except (TypeError, ValueError):
                value = 0
            if value > 0:
                return value
        return 0

    def _parse_stats_filename_context(self, filename: str) -> dict | None:
        match = re.match(
            r'^(\d{4}-\d{2}-\d{2})-(\d{6})-(.+)-round-(\d+)\.txt$',
            filename,
        )
        if not match:
            return None
        date_part, time_part, map_name, round_text = match.groups()
        try:
            filename_ts = int(
                datetime.strptime(
                    f"{date_part} {time_part}", "%Y-%m-%d %H%M%S"
                ).timestamp()
            )
        except ValueError:
            filename_ts = 0
        return {
            "map_name": map_name,
            "round_number": int(round_text),
            "filename_ts": filename_ts,
        }

    def _prune_pending_round_metadata(self) -> None:
        if not self._pending_round_metadata:
            return
        cutoff_unix = int(time.time()) - self._pending_metadata_ttl_seconds
        stale_keys = []
        for key, entries in list(self._pending_round_metadata.items()):
            pruned_entries = [
                entry for entry in entries
                if int(entry.get("received_unix", 0)) >= cutoff_unix
            ]
            if len(pruned_entries) > self._pending_metadata_max_per_key:
                pruned_entries = pruned_entries[-self._pending_metadata_max_per_key:]
            if pruned_entries:
                self._pending_round_metadata[key] = pruned_entries
            else:
                stale_keys.append(key)
        for key in stale_keys:
            self._pending_round_metadata.pop(key, None)

    def _queue_pending_metadata(self, round_metadata: dict, source: str) -> None:
        metadata_key = self._pending_metadata_key(
            round_metadata.get("map_name"),
            round_metadata.get("round_number"),
        )
        if not metadata_key:
            return

        self._prune_pending_round_metadata()
        bucket = self._pending_round_metadata[metadata_key]
        bucket.append(
            {
                "metadata": dict(round_metadata),
                "received_unix": int(time.time()),
                "source": source,
            }
        )
        if len(bucket) > self._pending_metadata_max_per_key:
            del bucket[:-self._pending_metadata_max_per_key]

    def _pop_pending_metadata(self, filename: str):
        """
        Pop best matching Lua metadata from pending queue for this stats filename.
        Chooses by timestamp proximity when both sides have timestamps.
        """
        self._prune_pending_round_metadata()
        if not self._pending_round_metadata:
            return None

        context = self._parse_stats_filename_context(filename)
        if not context:
            return None

        metadata_key = self._pending_metadata_key(
            context.get("map_name"),
            context.get("round_number"),
        )
        if not metadata_key:
            return None

        candidates = self._pending_round_metadata.get(metadata_key) or []
        if not candidates:
            return None

        filename_ts = int(context.get("filename_ts", 0) or 0)
        best_idx = len(candidates) - 1  # Fallback to newest metadata
        best_diff = None
        if filename_ts:
            for idx, entry in enumerate(candidates):
                meta_ts = self._metadata_event_unix(entry.get("metadata") or {})
                if not meta_ts:
                    continue
                diff = abs(meta_ts - filename_ts)
                if best_diff is None or diff < best_diff:
                    best_diff = diff
                    best_idx = idx

        selected = candidates.pop(best_idx)
        if not candidates:
            self._pending_round_metadata.pop(metadata_key, None)

        metadata = selected.get("metadata")
        if metadata:
            if best_diff is not None:
                webhook_logger.info(
                    f"📎 Attached pending Lua metadata for {metadata_key} (Δ {best_diff}s)"
                )
            else:
                webhook_logger.info(f"📎 Attached pending Lua metadata for {metadata_key}")
        return metadata

    def _prune_processed_webhook_message_ids(self) -> None:
        if not self._processed_webhook_message_ids:
            return
        cutoff = datetime.now() - timedelta(seconds=self._webhook_message_dedupe_ttl)
        while self._processed_webhook_message_ids and self._processed_webhook_message_ids[0][0] < cutoff:
            _, stale_id = self._processed_webhook_message_ids.popleft()
            self._processed_webhook_message_id_set.discard(stale_id)

    def _register_processed_webhook_message_id(self, message_id: int | None) -> bool:
        """
        Return False when this webhook message id was already seen recently.
        """
        if not message_id:
            return True
        self._prune_processed_webhook_message_ids()
        if message_id in self._processed_webhook_message_id_set:
            return False
        now = datetime.now()
        self._processed_webhook_message_ids.append((now, message_id))
        self._processed_webhook_message_id_set.add(message_id)
        return True

    def _check_rate_limit(
        self,
        bucket,
        bucket_key: int,
        *,
        max_events: int,
        window_seconds: int,
        label: str,
    ) -> bool:
        now = datetime.now()
        window_start = now - timedelta(seconds=window_seconds)
        timestamps = bucket[bucket_key]

        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()

        if len(timestamps) >= max_events:
            wait_time = (timestamps[0] + timedelta(seconds=window_seconds) - now).total_seconds()
            webhook_logger.warning(
                f"🚨 {label} {bucket_key} rate limited "
                f"({len(timestamps)} triggers in {window_seconds}s). "
                f"Retry in {wait_time:.1f}s"
            )
            return False

        timestamps.append(now)
        return True

    def _check_webhook_rate_limit(self, webhook_id: int) -> bool:
        """Rate limit filename/endstats triggers per webhook."""
        return self._check_rate_limit(
            self._webhook_rate_limit,
            webhook_id,
            max_events=self._webhook_rate_limit_max,
            window_seconds=self._webhook_rate_limit_window,
            label="Webhook",
        )

    def _check_stats_ready_rate_limit(self, webhook_id: int) -> bool:
        """Lightweight STATS_READY rate limit per webhook."""
        return self._check_rate_limit(
            self._stats_ready_rate_limit,
            webhook_id,
            max_events=self._stats_ready_rate_limit_max,
            window_seconds=self._stats_ready_rate_limit_window,
            label="STATS_READY webhook",
        )


    def _fields_to_metadata_map(self, fields) -> dict:
        return self.webhook_round_metadata_service.fields_to_metadata_map(fields)

    def _parse_spawn_stats_from_metadata(self, metadata: dict) -> list:
        return self.webhook_round_metadata_service.parse_spawn_stats_from_metadata(metadata)

    def _parse_lua_version_from_footer(self, footer_text: str | None) -> str | None:
        return self.webhook_round_metadata_service.parse_lua_version_from_footer(footer_text)

    def _build_round_metadata_from_map(
        self,
        metadata: dict,
        footer_text: str | None = None,
    ) -> dict:
        return self.webhook_round_metadata_service.build_round_metadata_from_map(
            metadata,
            footer_text=footer_text,
            normalize_round_number=self._normalize_lua_round_for_metadata_paths,
            warn=webhook_logger.warning,
        )

    async def _process_stats_ready_webhook(self, message):
        """
        Process STATS_READY webhook from Lua script with embedded metadata.

        The Lua script on the game server sends accurate timing data including:
        - Winner team
        - Actual duration (correct even on surrender)
        - Pause tracking
        - Start/end unix timestamps
        - Team composition (Axis/Allies player lists)

        This metadata is used to override potentially incorrect values in stats files.
        Team data is stored separately in lua_round_teams table for analysis.
        """
        try:
            embed = message.embeds[0]

            metadata = self._fields_to_metadata_map(embed.fields)
            footer_text = None
            if embed.footer and embed.footer.text:
                footer_text = embed.footer.text
            round_metadata = self._build_round_metadata_from_map(metadata, footer_text=footer_text)

            if round_metadata.get("map_name") == "unknown" or round_metadata.get("round_number", 0) <= 0:
                webhook_logger.warning("STATS_READY webhook missing map/round metadata; skipping")
                return

            # Filter ghost rounds (< 30 seconds) — MED-TIMING-002
            actual_duration = round_metadata.get('lua_playtime_seconds', 0)
            if actual_duration is not None and 0 < actual_duration < 30:
                webhook_logger.info(
                    f"⏭️ Skipping ghost round: {round_metadata['map_name']} R{round_metadata['round_number']} "
                    f"(duration {actual_duration}s < 30s minimum)"
                )
                return

            # Human-readable team names (for logging)
            axis_names = metadata.get('axis', '(none)')
            allies_names = metadata.get('allies', '(none)')
            if (axis_names in {"(none)", ""}) and round_metadata.get("axis_players"):
                axis_names = ", ".join(
                    p.get("name", "") for p in round_metadata.get("axis_players", []) if p.get("name")
                )
            if (allies_names in {"(none)", ""}) and round_metadata.get("allies_players"):
                allies_names = ", ".join(
                    p.get("name", "") for p in round_metadata.get("allies_players", []) if p.get("name")
                )

            # Log summary including surrender info (v1.4.0)
            surrender_info = ""
            if round_metadata['surrender_team'] > 0:
                team_name = "Axis" if round_metadata['surrender_team'] == 1 else "Allies"
                caller = round_metadata.get('surrender_caller_name', 'unknown')
                surrender_info = f", surrender={team_name} (by {caller})"

            webhook_logger.info(
                f"📊 STATS_READY: {round_metadata['map_name']} R{round_metadata['round_number']} "
                f"(winner={round_metadata['winner_team']}, playtime={round_metadata['lua_playtime_seconds']}s, "
                f"warmup={round_metadata['lua_warmup_seconds']}s, pauses={round_metadata['lua_pause_count']}"
                f"{surrender_info}, score={round_metadata['axis_score']}-{round_metadata['allies_score']})"
            )
            webhook_logger.info(f"   Axis: {axis_names}")
            webhook_logger.info(f"   Allies: {allies_names}")

            # Store team data in lua_round_teams table (separate from stats file data)
            await self._store_lua_round_teams(round_metadata)

            # Store spawn stats if present (Lua v1.6.0+)
            spawn_stats = self._parse_spawn_stats_from_metadata(metadata)
            if spawn_stats:
                await self._store_lua_spawn_stats(round_metadata, spawn_stats)

            # Keep metadata queued for later filename-triggered processing as fallback.
            self._queue_pending_metadata(round_metadata, source="stats_ready")

            # Now trigger SSH fetch for the actual stats file
            # Build expected filename pattern: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
            from datetime import datetime
            timestamp = datetime.fromtimestamp(round_metadata['round_end_unix'])
            # Give some flexibility - file might have slightly different timestamp
            date_prefix = timestamp.strftime('%Y-%m-%d')

            webhook_logger.info(f"🔍 Looking for stats file from {date_prefix} for {round_metadata['map_name']}")

            # Trigger immediate SSH check for the file
            await self._fetch_latest_stats_file(round_metadata, message)

            # Delete the webhook message to keep channel clean
            try:
                await message.delete()
                webhook_logger.debug("🗑️ Deleted STATS_READY webhook message")
            except Exception as e:
                webhook_logger.debug(f"Could not delete webhook message: {e}")

        except Exception as e:
            webhook_logger.error(f"❌ Error processing STATS_READY webhook: {e}", exc_info=True)
            await self.track_error("stats_ready_webhook", str(e), max_consecutive=3)

    def _extract_gametime_timestamp(self, filename: str) -> int | None:
        match = re.match(r"^gametime-.*-R\d+-(\d+)\.json$", filename)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    async def _process_gametimes_file(self, local_path: str, filename: str) -> bool:
        """
        Process a gametimes JSON fallback file (Lua webhook payload stored locally).
        """
        try:
            with open(local_path, encoding="utf-8") as handle:
                gametime_data = json.load(handle)
        except Exception as e:
            webhook_logger.error(f"❌ Failed to read gametime file {filename}: {e}")
            return False

        payload = gametime_data.get("payload")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError as e:
                webhook_logger.error(f"❌ Gametime payload JSON decode failed: {e}")
                return False

        if not isinstance(payload, dict):
            webhook_logger.error("❌ Gametime payload missing or invalid")
            return False

        embeds = payload.get("embeds") or []
        if not embeds:
            webhook_logger.warning(f"⚠️ Gametime payload has no embeds: {filename}")
            return False

        embed = embeds[0] or {}
        metadata = self._fields_to_metadata_map(embed.get("fields", []))
        footer_text = None
        footer = embed.get("footer") if isinstance(embed, dict) else None
        if isinstance(footer, dict):
            footer_text = footer.get("text")

        round_metadata = self._build_round_metadata_from_map(metadata, footer_text=footer_text)

        meta = gametime_data.get("meta") or {}
        if round_metadata.get("map_name") == "unknown" and meta.get("map"):
            round_metadata["map_name"] = meta.get("map")
        if round_metadata.get("round_number", 0) == 0 and meta.get("round") is not None:
            round_metadata["round_number"] = self._normalize_lua_round_for_metadata_paths(
                meta.get("round")
            )
        if round_metadata.get("round_end_unix", 0) == 0 and meta.get("round_end_unix"):
            round_metadata["round_end_unix"] = int(meta.get("round_end_unix"))
        spawn_stats_meta = meta.get("spawn_stats")
        if isinstance(spawn_stats_meta, str):
            try:
                spawn_stats_meta = json.loads(spawn_stats_meta)
            except json.JSONDecodeError:
                spawn_stats_meta = []
        if not isinstance(spawn_stats_meta, list):
            spawn_stats_meta = []

        if round_metadata.get("map_name") == "unknown" or round_metadata.get("round_number", 0) <= 0:
            webhook_logger.warning(f"⚠️ Gametime file missing map/round metadata: {filename}")
            return False

        axis_players = round_metadata.get("axis_players", [])
        allies_players = round_metadata.get("allies_players", [])
        axis_names = metadata.get("axis", "") or ", ".join(
            [p.get("name", "") for p in axis_players if p.get("name")]
        )
        allies_names = metadata.get("allies", "") or ", ".join(
            [p.get("name", "") for p in allies_players if p.get("name")]
        )

        webhook_logger.info(
            f"📁 GAMETIME: {round_metadata['map_name']} R{round_metadata['round_number']} "
            f"(winner={round_metadata.get('winner_team')}, playtime={round_metadata.get('lua_playtime_seconds')}s, "
            f"warmup={round_metadata.get('lua_warmup_seconds')}s, pauses={round_metadata.get('lua_pause_count')})"
        )
        if axis_names:
            webhook_logger.info(f"   Axis: {axis_names}")
        if allies_names:
            webhook_logger.info(f"   Allies: {allies_names}")

        stored_round_id = await self._store_lua_round_teams(round_metadata)
        if spawn_stats_meta:
            await self._store_lua_spawn_stats(round_metadata, spawn_stats_meta)

        # 🔗 CORRELATION: notify of gametime arrival
        if hasattr(self, 'correlation_service') and self.correlation_service:
            try:
                round_end = int(round_metadata.get('round_end_unix', 0) or 0)
                fallback_match_id = "unknown"
                if round_end:
                    from datetime import datetime as _dt
                    # NOTE: fromtimestamp() uses local time, matching Lua os.date()
                    # which generates stats filenames in the game server's local TZ.
                    # Both machines are CET — do NOT change to utcfromtimestamp().
                    ts = _dt.fromtimestamp(round_end)
                    fallback_match_id = ts.strftime('%Y-%m-%d-%H%M%S')

                try:
                    round_number = int(round_metadata.get('round_number', 0) or 0)
                except (TypeError, ValueError):
                    round_number = 0
                map_name = round_metadata.get('map_name', 'unknown')
                corr_match_id, corr_map_name, corr_round_number = (
                    await self._resolve_round_correlation_context(
                        stored_round_id,
                        fallback_match_id=fallback_match_id,
                        fallback_map_name=map_name,
                        fallback_round_number=round_number,
                    )
                )
                if corr_match_id != "unknown":
                    await self.correlation_service.on_gametime_processed(
                        match_id=corr_match_id,
                        round_number=corr_round_number,
                        map_name=corr_map_name,
                    )
            except Exception as corr_err:
                webhook_logger.warning(f"[CORRELATION] gametime hook error (non-fatal): {corr_err}")

        self._queue_pending_metadata(round_metadata, source="gametime")

        # Attempt to fetch the matching stats file using the Lua timing data
        if self.ssh_enabled:
            webhook_logger.info(
                f"🔍 Gametime trigger: searching stats for {round_metadata['map_name']} "
                f"R{round_metadata['round_number']}"
            )
            await self._fetch_latest_stats_file(round_metadata, None)

        return True

    async def _process_remote_gametimes_files(self) -> None:
        if not self.config.gametimes_enabled:
            return
        if not self.ssh_enabled:
            return

        ssh_config = {
            "host": self.config.ssh_host,
            "port": self.config.ssh_port,
            "user": self.config.ssh_user,
            "key_path": self.config.ssh_key_path,
            "remote_path": self.config.gametimes_remote_path,
        }

        if not all([
            ssh_config["host"],
            ssh_config["user"],
            ssh_config["key_path"],
            ssh_config["remote_path"],
        ]):
            if not hasattr(self, "_gametimes_config_logged"):
                self._gametimes_config_logged = True
                logger.warning(
                    "⚠️ Gametimes SSH config incomplete - skipping gametimes ingestion\n"
                    f"   Host: {ssh_config['host']}\n"
                    f"   User: {ssh_config['user']}\n"
                    f"   Key: {ssh_config['key_path']}\n"
                    f"   Path: {ssh_config['remote_path']}"
                )
            return

        files = await SSHHandler.list_remote_files(
            ssh_config,
            extensions=[".json"],
            exclude_suffixes=None,
        )
        if not files:
            return

        cutoff = None
        if self.config.gametimes_startup_lookback_hours > 0:
            cutoff = datetime.now().timestamp() - (self.config.gametimes_startup_lookback_hours * 3600)

        gametime_files = [f for f in files if f.startswith("gametime-") and f.endswith(".json")]
        if not gametime_files:
            return

        webhook_logger.debug(
            f"📂 Gametimes files on server: {len(gametime_files)}"
        )

        new_files = [
            f for f in gametime_files
            if f not in self.processed_gametimes_files
        ]
        if not new_files:
            return

        webhook_logger.info(
            f"📥 New gametimes files detected: {len(new_files)}"
        )

        for filename in sorted(new_files):
            ts = self._extract_gametime_timestamp(filename)
            if cutoff and ts and ts < cutoff:
                self._mark_gametime_processed(filename)
                continue

            webhook_logger.info(f"📥 Downloading gametime file: {filename}")
            local_path = await SSHHandler.download_file(
                ssh_config,
                filename,
                self.config.gametimes_local_path,
            )

            if not local_path:
                webhook_logger.warning(f"❌ Failed to download gametime file: {filename}")
                continue

            success = await self._process_gametimes_file(local_path, filename)
            if success:
                self._mark_gametime_processed(filename)
            else:
                webhook_logger.warning(f"⚠️ Gametime file processing failed: {filename}")

    async def _reconcile_missing_round_timing(self):
        """Backfill rounds.actual_duration_seconds from lua_round_teams
        for rounds that were processed before gametime data arrived."""
        query = """
            UPDATE rounds r SET
              actual_duration_seconds = lrt.actual_duration_seconds,
              round_start_unix = lrt.round_start_unix,
              round_end_unix = lrt.round_end_unix,
              end_reason = lrt.end_reason,
              total_pause_seconds = lrt.total_pause_seconds,
              pause_count = lrt.pause_count
            FROM lua_round_teams lrt
            WHERE lrt.round_id = r.id
              AND r.actual_duration_seconds IS NULL
              AND lrt.actual_duration_seconds IS NOT NULL
        """
        try:
            result = await self.db_adapter.execute(query)
            # asyncpg returns status string like "UPDATE 5"
            if result and isinstance(result, str):
                parts = result.split()
                if len(parts) == 2 and parts[1] != '0':
                    logger.info(f"[TIMING RECONCILE] Backfilled timing for {parts[1]} rounds")
        except Exception as e:
            logger.warning(f"[TIMING RECONCILE] Failed: {e}")


    async def _validate_webhook_security_config(self):
        """Validate webhook security configuration on startup."""

        if not self.config.webhook_trigger_channel_id:
            logger.info("ℹ️ Webhook trigger not configured (feature disabled)")
            return

        logger.info("🔒 Validating webhook security configuration...")

        errors = []

        # CRITICAL: Webhook whitelist required
        if not self.config.webhook_trigger_whitelist:
            errors.append(
                "WEBHOOK_TRIGGER_WHITELIST is REQUIRED when webhook trigger enabled.\n"
                "  Prevents unauthorized webhooks from triggering downloads.\n"
                "  Set in .env: WEBHOOK_TRIGGER_WHITELIST=webhook_id_1,webhook_id_2"
            )
        else:
            logger.info(f"✅ Webhook whitelist: {len(self.config.webhook_trigger_whitelist)} IDs")

        webhook_mode = self._webhook_trigger_mode()
        logger.info(f"✅ Webhook trigger mode: {webhook_mode}")
        if webhook_mode == "stats_ready_only" and self.config.ws_enabled:
            errors.append(
                "WS_ENABLED must be false when WEBHOOK_TRIGGER_MODE=stats_ready_only.\n"
                "  This prevents duplicate trigger paths (deprecated websocket + webhook)."
            )
        elif webhook_mode != "stats_ready_only":
            logger.warning(
                "⚠️ WEBHOOK_TRIGGER_MODE is not strict stats_ready_only. "
                "Legacy filename trigger path remains enabled."
            )

        # Validate SSH config
        if not all([self.config.ssh_host, self.config.ssh_user,
                    self.config.ssh_key_path, self.config.ssh_remote_path]):
            errors.append("SSH configuration incomplete (required for webhook downloads)")

        if errors:
            error_msg = "\n\n❌ WEBHOOK SECURITY ERRORS:\n\n" + "\n\n".join(f"  • {e}" for e in errors)
            logger.error(error_msg)
            logger.error("\n🚨 Bot startup FAILED - fix errors and restart\n")
            raise RuntimeError("Webhook security validation failed")

        logger.info("✅ Webhook security validated")

    async def on_ready(self):
        """✅ Bot startup message"""
        logger.info("=" * 80)
        logger.info(f"🚀 Ultimate ET:Legacy Bot logged in as {self.user}")
        logger.info(f"🆔 Bot ID: {self.user.id}")
        logger.info(f"📊 Database Type: {self.config.database_type.upper()}")
        if self.config.database_type == 'postgresql':
            logger.info(f"📍 Database: {self.config.postgres_database}@{self.config.postgres_host}")
        else:
            logger.info(f"📍 Database: {self.db_path}")
        logger.info(f"🎮 Commands Loaded: {len(list(self.commands))}")
        logger.info(f"🔧 Cogs Loaded: {len(self.cogs)}")
        logger.info(f"🌐 Servers: {len(self.guilds)}")
        logger.info("=" * 80)

        # Validate webhook security
        try:
            await self._validate_webhook_security_config()
        except RuntimeError as e:
            logger.critical(f"❌ Security validation failed: {e}")
            await self.close()
            return

        # Clear any old slash commands to avoid confusion
        try:
            self.tree.clear_commands(guild=None)
            await self.tree.sync()
            logger.info("🧹 Cleared old slash commands")
        except Exception as e:
            logger.warning(f"Could not clear slash commands: {e}")

        # 🆕 AUTO-DETECT ACTIVE GAMING SESSION ON STARTUP
        await self.voice_session_service.check_startup_voice_state()

        # 📊 Start monitoring service (server + voice history)
        if self.monitoring_enabled:
            try:
                if self.monitoring_service is None:
                    from bot.services.monitoring_service import MonitoringService
                    self.monitoring_service = MonitoringService(
                        self, self.db_adapter, self.config
                    )
                if not self._monitoring_started:
                    await self.monitoring_service.start()
                    self._monitoring_started = True
                    logger.info("✅ Monitoring service started")
            except Exception as e:
                logger.error(f"⚠️ Monitoring service failed to start: {e}", exc_info=True)

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
def main() -> int:
    """🚀 Start the Ultimate ET:Legacy Discord Bot."""

    validate_only = os.getenv("BOT_STARTUP_VALIDATE_ONLY", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if validate_only:
        try:
            config = load_config()
            logger.info(
                "✅ BOT_STARTUP_VALIDATE_ONLY enabled; config validated (database_type=%s).",
                config.database_type,
            )
            return 0
        except Exception as exc:
            logger.error("❌ BOT_STARTUP_VALIDATE_ONLY failed: %s", exc)
            return 1

    # Create bot (config is loaded in __init__)
    bot = UltimateETLegacyBot()

    # Get Discord token from config
    token = bot.config.discord_token
    if not token:
        logger.error("❌ DISCORD_BOT_TOKEN not found in environment variables!")
        logger.info("Please set your Discord bot token in the .env file")
        return 4

    try:
        logger.info("🚀 Starting Ultimate ET:Legacy Bot...")
        bot.run(token)
        return 0
    except discord.LoginFailure:
        logger.error("❌ Invalid Discord token!")
        return 2
    except Exception as e:
        logger.error(f"❌ Bot startup failed: {e}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
