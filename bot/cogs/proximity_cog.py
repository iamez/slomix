"""
Proximity Tracker Cog
ISOLATED cog for processing engagement data from proximity_tracker.lua

This cog runs its own background task to watch for engagement files
and import them independently of the main stats pipeline.

Features:
- Background task to scan for new engagement files
- Admin commands for status and manual import
- Completely isolated - errors here won't crash main bot
"""

import asyncio
import logging
import os
import sys

from discord.ext import commands

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from bot.cogs.proximity_mixins.admin_commands_mixin import _ProximityAdminCommandsMixin
from bot.cogs.proximity_mixins.ingestion_mixin import _ProximityIngestionMixin
from bot.cogs.proximity_mixins.relinker_mixin import _ProximityRelinkerMixin
from bot.cogs.proximity_mixins.stats_commands_mixin import _ProximityStatsCommandsMixin

logger = logging.getLogger(__name__)

# Try to import the proximity parser
try:
    from proximity.parser import ProximityParserV4  # noqa: F401
    PROXIMITY_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ ProximityParserV4 not available: {e}")
    PROXIMITY_AVAILABLE = False


class ProximityCog(
    _ProximityIngestionMixin,
    _ProximityRelinkerMixin,
    _ProximityAdminCommandsMixin,
    _ProximityStatsCommandsMixin,
    commands.Cog,
    name="Proximity",
):
    """
    Proximity Tracker - Combat engagement analytics

    ISOLATED COG - errors here won't affect main bot functionality

    Admin Commands:
    - !proximity_status - Show tracker status
    - !proximity_import [file] - Manual file import
    - !proximity_scan - Force scan for new files
    """

    def __init__(self, bot):
        self.bot = bot
        self.stats_dir = getattr(bot.config, 'stats_directory', 'local_stats')
        self.local_dir = getattr(bot.config, 'proximity_local_path', self.stats_dir)
        self.remote_path = getattr(bot.config, 'proximity_remote_path', '')
        self.lookback_hours = getattr(
            bot.config, 'proximity_startup_lookback_hours', 24
        )
        self.ssh_enabled = getattr(bot.config, 'ssh_enabled', False)
        self.processed_engagement_files = set()
        self.processed_remote_files = set()
        self.last_scan_time = None
        self.import_count = 0
        self.error_count = 0
        self._startup_scan_completed = False
        self._scan_lock = asyncio.Lock()

        # Check if proximity is enabled
        self.enabled = getattr(bot.config, 'proximity_enabled', False)
        self.debug_log = getattr(bot.config, 'proximity_debug_log', False)
        self.commands_enabled = getattr(bot.config, 'proximity_discord_commands', False)

        if not PROXIMITY_AVAILABLE:
            logger.warning("⚠️ Proximity cog loaded but parser not available")
            self.enabled = False

        if self.enabled:
            logger.info("🎯 Proximity Tracker cog initialized (ENABLED)")
            self.scan_engagement_files.start()
            self.relink_null_rounds.start()
        else:
            logger.info("🎯 Proximity Tracker cog initialized (DISABLED)")

        # Ensure local directory exists
        try:
            os.makedirs(self.local_dir, exist_ok=True)
        except Exception as e:
            logger.warning(f"⚠️ Could not create proximity local dir {self.local_dir}: {e}")

        # Load processed remote index (best-effort)
        self._load_remote_index()
        self._load_local_index()


    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        if self.scan_engagement_files.is_running():
            self.scan_engagement_files.cancel()
        if self.relink_null_rounds.is_running():
            self.relink_null_rounds.cancel()

    async def cog_command_error(self, ctx, error):
        """Handle errors without crashing bot"""
        logger.error(f"Error in ProximityCog: {error}", exc_info=True)
        await ctx.send(
            "⚠️ An error occurred in proximity tracker.\n"
            "Main bot functionality is unaffected."
        )

    # =========================================================================
    # BACKGROUND TASK - Scan for new engagement files
    # =========================================================================


    # =========================================================================
    # RE-LINKER — fix NULL round_id in proximity tables
    # =========================================================================

    # Whitelist of proximity tables that have round_id columns (used in SQL interpolation)
    _PROXIMITY_ROUND_ID_TABLES = frozenset({
        "proximity_carrier_event",
        "proximity_carrier_kill",
        "proximity_carrier_return",
        "proximity_combat_position",
        "proximity_construction_event",
        "proximity_crossfire_opportunity",
        "proximity_escort_credit",
        "proximity_focus_fire",
        "proximity_hit_region",
        "proximity_kill_outcome",
        "proximity_lua_trade_kill",
        "proximity_objective_focus",
        "proximity_objective_run",
        "proximity_reaction_metric",
        # proximity_revive excluded: no round_number/round_start_unix/session_date columns
        "proximity_spawn_timing",
        "proximity_support_summary",
        "proximity_team_cohesion",
        "proximity_team_push",
        "proximity_trade_event",
        "proximity_vehicle_progress",
        # proximity_weapon_accuracy excluded: no round_number/round_start_unix/session_date columns
    })


    # =========================================================================
    # IMPORT LOGIC
    # =========================================================================


    # =========================================================================
    # ADMIN COMMANDS
    # =========================================================================


    # =========================================================================
    # V5 TEAMPLAY COMMANDS
    # =========================================================================


    # ── SESSION SCORE ──────────────────────────────────────────────────


    # ===== v6 CARRIER INTELLIGENCE COMMANDS =====


async def setup(bot):
    """Setup function for cog loading"""
    await bot.add_cog(ProximityCog(bot))
