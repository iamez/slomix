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
import discord
from discord.ext import commands, tasks
import os
import sys
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

logger = logging.getLogger(__name__)

# Try to import the proximity parser
try:
    from proximity.parser import ProximityParserV4
    PROXIMITY_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ ProximityParserV4 not available: {e}")
    PROXIMITY_AVAILABLE = False


class ProximityCog(commands.Cog, name="Proximity"):
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

    def _remote_index_path(self) -> str:
        return os.path.join(self.local_dir, ".processed_proximity.txt")

    def _local_index_path(self) -> str:
        return os.path.join(self.local_dir, ".processed_proximity_local.txt")

    def _load_remote_index(self) -> None:
        index_path = self._remote_index_path()
        if not os.path.exists(index_path):
            return
        try:
            with open(index_path, "r", encoding="utf-8") as handle:
                for line in handle:
                    filename = line.strip()
                    if filename:
                        self.processed_remote_files.add(filename)
        except Exception as e:
            logger.debug(f"Proximity index load failed: {e}")

    def _mark_remote_processed(self, filename: str) -> None:
        if not filename or filename in self.processed_remote_files:
            return
        self.processed_remote_files.add(filename)
        try:
            with open(self._remote_index_path(), "a", encoding="utf-8") as handle:
                handle.write(f"{filename}\n")
        except Exception as e:
            logger.debug(f"Proximity index update failed: {e}")

    def _load_local_index(self) -> None:
        index_path = self._local_index_path()
        if not os.path.exists(index_path):
            return
        try:
            with open(index_path, "r", encoding="utf-8") as handle:
                for line in handle:
                    filename = line.strip()
                    if filename:
                        self.processed_engagement_files.add(filename)
        except Exception as e:
            logger.debug(f"Proximity local index load failed: {e}")

    def _mark_local_processed(self, filename: str) -> None:
        if not filename or filename in self.processed_engagement_files:
            return
        self.processed_engagement_files.add(filename)
        try:
            with open(self._local_index_path(), "a", encoding="utf-8") as handle:
                handle.write(f"{filename}\n")
        except Exception as e:
            logger.debug(f"Proximity local index update failed: {e}")

    def _extract_timestamp(self, filename: str) -> int | None:
        match = re.match(r"^(\d{4}-\d{2}-\d{2})-(\d{6})-.*_engagements\.txt$", filename)
        if not match:
            return None
        date_str, time_str = match.groups()
        try:
            from datetime import datetime
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H%M%S")
            return int(dt.timestamp())
        except ValueError:
            return None

    def _load_objective_coords(self) -> dict:
        template_path = Path("proximity/objective_coords_template.json")
        if not template_path.exists():
            return {}
        try:
            return json.loads(template_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"⚠️ Failed to read objective coords template: {e}")
            return {}

    async def _fetch_remote_files(self) -> None:
        if not self.ssh_enabled or not self.remote_path or not self.enabled:
            return
        try:
            from bot.automation.ssh_handler import SSHHandler
        except Exception as e:
            logger.warning(f"⚠️ Proximity SSH handler unavailable: {e}")
            return

        ssh_config = {
            "host": self.bot.config.ssh_host,
            "port": self.bot.config.ssh_port,
            "user": self.bot.config.ssh_user,
            "key_path": self.bot.config.ssh_key_path,
            "remote_path": self.remote_path,
        }

        if not all([ssh_config["host"], ssh_config["user"], ssh_config["key_path"], ssh_config["remote_path"]]):
            if self.debug_log:
                logger.debug("Proximity SSH config incomplete")
            return

        remote_files = await SSHHandler.list_remote_files(
            ssh_config,
            extensions=[".txt"],
            exclude_suffixes=None,
        )
        if not remote_files:
            return

        proximity_files = [f for f in remote_files if f.endswith("_engagements.txt")]
        if not proximity_files:
            return

        cutoff = None
        if self.lookback_hours and self.lookback_hours > 0:
            cutoff = (datetime.now().timestamp() - (self.lookback_hours * 3600))

        for filename in sorted(proximity_files):
            if filename in self.processed_remote_files:
                continue
            ts = self._extract_timestamp(filename)
            if cutoff and ts and ts < cutoff:
                self._mark_remote_processed(filename)
                continue

            if self.debug_log:
                logger.info(f"📥 Downloading proximity file: {filename}")

            local_path = await SSHHandler.download_file(
                ssh_config,
                filename,
                self.local_dir,
            )
            if not local_path:
                logger.warning(f"⚠️ Failed to download proximity file: {filename}")
                continue

            self._mark_remote_processed(filename)

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

    async def _scan_and_import(self, force: bool = False) -> None:
        if not self.enabled:
            return
        if not force and not self.bot.config.proximity_auto_import:
            return

        if self._scan_lock.locked():
            logger.debug("Proximity scan already in progress, skipping")
            return

        async with self._scan_lock:
            try:
                self.last_scan_time = datetime.now()

                # Fetch new files from remote server if configured
                await self._fetch_remote_files()

                # Find all engagement files
                stats_path = Path(self.local_dir)
                if not stats_path.exists():
                    if self.debug_log:
                        logger.debug(f"Stats directory not found: {stats_path}")
                    return

                engagement_files = list(stats_path.glob("*_engagements.txt"))

                # On startup, respect lookback to avoid replaying stale local files.
                startup_cutoff = None
                if (
                    not force
                    and not self._startup_scan_completed
                    and self.lookback_hours
                    and self.lookback_hours > 0
                ):
                    startup_cutoff = int(datetime.now().timestamp() - (self.lookback_hours * 3600))

                new_files = [
                    f for f in engagement_files
                    if f.name not in self.processed_engagement_files
                ]

                if new_files and self.debug_log:
                    logger.info(f"🎯 Found {len(new_files)} new engagement files")

                for filepath in sorted(new_files, key=lambda p: p.name):
                    if startup_cutoff is not None:
                        ts = self._extract_timestamp(filepath.name)
                        if ts and ts < startup_cutoff:
                            self._mark_local_processed(filepath.name)
                            continue
                    await self._import_engagement_file(filepath)

            except Exception as e:
                self.error_count += 1
                logger.error(f"Error in engagement scan: {e}", exc_info=True)
            finally:
                if not self._startup_scan_completed:
                    self._startup_scan_completed = True

    @tasks.loop(minutes=2)
    async def scan_engagement_files(self):
        """Periodically scan for new engagement files and import them"""
        await self._scan_and_import(force=False)

    @scan_engagement_files.before_loop
    async def before_scan(self):
        """Wait for bot to be ready before starting scan task"""
        await self.bot.wait_until_ready()

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

    async def _relink_null_round_ids(self) -> None:
        """Find proximity rows with NULL round_id and attempt to resolve them."""
        try:
            from bot.core.round_linker import resolve_round_id

            db = self.bot.db_adapter

            # Find distinct unlinked proximity rounds across all tables that
            # carry session_date + round_number + round_start_unix.
            # Tables without those columns (proximity_revive, proximity_weapon_accuracy)
            # are excluded; they rely on map_name + round_start_unix fallback only.
            unlinked = await db.fetch_all(
                "SELECT DISTINCT map_name, round_number, round_start_unix, session_date FROM ("
                "  SELECT map_name, round_number, round_start_unix, session_date FROM proximity_reaction_metric WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_spawn_timing WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_team_cohesion WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_kill_outcome WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_carrier_event WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_carrier_kill WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_carrier_return WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_combat_position WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_construction_event WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_crossfire_opportunity WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_escort_credit WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_focus_fire WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_hit_region WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_lua_trade_kill WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_objective_focus WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_objective_run WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_support_summary WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_team_push WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_trade_event WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_vehicle_progress WHERE round_id IS NULL"
                ") sub ORDER BY session_date DESC LIMIT 50"
            )

            if not unlinked:
                return

            linked = 0
            failed = 0

            for row in unlinked:
                map_name = row[0] if isinstance(row, (list, tuple)) else row.get('map_name') or row['map_name']
                round_number = row[1] if isinstance(row, (list, tuple)) else row.get('round_number') or row['round_number']
                round_start_unix = row[2] if isinstance(row, (list, tuple)) else row.get('round_start_unix') or row['round_start_unix']
                session_date = row[3] if isinstance(row, (list, tuple)) else row.get('session_date') or row['session_date']

                # Build target_dt from unix timestamp if available
                target_dt = None
                if round_start_unix:
                    try:
                        target_dt = datetime.fromtimestamp(
                            int(round_start_unix), tz=timezone.utc
                        ).replace(tzinfo=None)
                    except (ValueError, TypeError, OSError):
                        pass  # Invalid timestamp format; fall back to date-based resolution

                round_date_str = str(session_date) if session_date else None

                round_id = await resolve_round_id(
                    db,
                    map_name,
                    round_number,
                    target_dt=target_dt,
                    round_date=round_date_str,
                )

                if round_id is None:
                    failed += 1
                    continue

                # Update all proximity tables that have round_id
                # Use different WHERE clauses since not all tables have round_number/session_date
                for table in self._PROXIMITY_ROUND_ID_TABLES:
                    if table not in self._PROXIMITY_ROUND_ID_TABLES:
                        continue  # whitelist guard for SQL interpolation safety
                    try:
                        # Try most specific match first (map + round_number + session_date)
                        await db.execute(
                            f"UPDATE {table} SET round_id = $1 "
                            f"WHERE round_id IS NULL "
                            f"AND map_name = $2 AND round_number = $3 "
                            f"AND session_date = $4",
                            (round_id, map_name, round_number, session_date),
                        )
                    except Exception as e:
                        logger.warning(f"Re-linker: {table} primary update failed: {e}")
                        # Fallback: some tables lack round_number/session_date columns
                        try:
                            await db.execute(
                                f"UPDATE {table} SET round_id = $1 "
                                f"WHERE round_id IS NULL AND map_name = $2 "
                                f"AND round_start_unix = $3",
                                (round_id, map_name, round_start_unix),
                            )
                        except Exception as e:
                            logger.warning(f"Re-linker: {table} fallback update failed: {e}")

                linked += 1

            if linked > 0 or failed > 0:
                logger.info(
                    f"🔗 Proximity re-linker: {linked} rounds linked, "
                    f"{failed} unresolved (of {len(unlinked)} total)"
                )

        except Exception as e:
            logger.error(f"Re-linker error: {e}", exc_info=True)

    @tasks.loop(minutes=5)
    async def relink_null_rounds(self):
        """Periodically attempt to link NULL round_id rows in proximity tables."""
        await self._relink_null_round_ids()

    @relink_null_rounds.before_loop
    async def before_relink(self):
        """Wait for bot to be ready + 60s before starting re-linker."""
        await self.bot.wait_until_ready()
        await asyncio.sleep(60)

    # =========================================================================
    # IMPORT LOGIC
    # =========================================================================

    async def _resolve_session_date(
        self, file_date: str, file_time: str, parts: list, filename: str
    ) -> str:
        """Resolve the correct session date, handling midnight crossovers.

        If a round starts before midnight (23:xx) on day N but the proximity
        file is written after midnight on day N+1, we need to link it to
        the session on day N. Strategy:
        1. Check if a matching round exists on the file's date
        2. If not and time is in the early hours (00:00-05:00), check previous date
        3. Fall back to file date
        """
        # Extract map name from filename parts
        # Format: YYYY-MM-DD-HHMMSS-mapname-round-N_engagements.txt
        # parts[4:-1] could be mapname pieces, last part is "N_engagements.txt"
        try:
            # Find round number from the part containing "_engagements"
            for p in parts:
                if '_engagements' in p or '_proximity' in p:
                    break

            map_parts = parts[4:]
            # Remove the "round" keyword and everything after
            map_name_parts = []
            for i, p in enumerate(map_parts):
                if p == 'round':
                    break
                map_name_parts.append(p)
            map_name = '-'.join(map_name_parts) if map_name_parts else None

            if not map_name:
                return file_date

            # Step 1: Check for round on same date
            query = """
                SELECT round_date FROM rounds
                WHERE SUBSTR(round_date, 1, 10) = ?
                AND map_name = ?
                LIMIT 1
            """
            result = await self.bot.db_adapter.fetch_one(query, (file_date, map_name))
            if result:
                return file_date

            # Step 2: If file time is early morning (00:00-05:00), check previous date
            hour = int(file_time[:2]) if len(file_time) >= 2 else 99
            if hour < 5:
                prev_date = (
                    datetime.strptime(file_date, '%Y-%m-%d') - timedelta(days=1)
                ).strftime('%Y-%m-%d')

                result = await self.bot.db_adapter.fetch_one(query, (prev_date, map_name))
                if result:
                    logger.info(
                        f"🌙 Midnight crossing: linking {filename} to previous date {prev_date}"
                    )
                    return prev_date

        except Exception as e:
            logger.debug(f"Session date resolution failed for {filename}: {e}")

        return file_date

    async def _import_engagement_file(self, filepath: Path) -> bool:
        """Import a single engagement file"""
        try:
            if self.debug_log:
                logger.info(f"🎯 Importing: {filepath.name}")

            # Extract session date from filename, with midnight-crossing support
            # Format: YYYY-MM-DD-HHMMSS-mapname-round-N_engagements.txt
            filename = filepath.name
            parts = filename.split('-')
            if len(parts) >= 4:
                file_date = f"{parts[0]}-{parts[1]}-{parts[2]}"
                file_time = parts[3]  # HHMMSS
                session_date = await self._resolve_session_date(
                    file_date, file_time, parts, filename
                )
            else:
                session_date = datetime.now().strftime("%Y-%m-%d")

            # Create parser with database adapter
            parser = ProximityParserV4(
                db_adapter=self.bot.db_adapter,
                output_dir=str(filepath.parent),
                gametimes_dir=getattr(self.bot.config, "gametimes_local_path", "local_gametimes"),
            )

            # Import the file
            success = await parser.import_file(str(filepath), session_date)

            if success:
                self._mark_local_processed(filepath.name)
                self.import_count += 1

                stats = parser.get_stats()
                if self.debug_log:
                    logger.info(
                        f"✅ Imported {filepath.name}: "
                        f"{stats['total_engagements']} engagements, "
                        f"{stats['crossfire_engagements']} crossfires"
                    )
                return True
            else:
                self.error_count += 1
                logger.warning(f"⚠️ Failed to import {filepath.name}")
                return False

        except Exception as e:
            self.error_count += 1
            logger.error(f"Error importing {filepath}: {e}", exc_info=True)
            return False

    # =========================================================================
    # ADMIN COMMANDS
    # =========================================================================

    @commands.command(name='proximity_status')
    @commands.has_permissions(administrator=True)
    async def proximity_status(self, ctx):
        """Show proximity tracker status (admin only)"""
        if not self.commands_enabled and not self.enabled:
            await ctx.send("⚠️ Proximity commands are disabled.")
            return

        embed = discord.Embed(
            title="🎯 Proximity Tracker Status",
            color=0x00FF00 if self.enabled else 0xFF0000
        )

        embed.add_field(
            name="Status",
            value="✅ ENABLED" if self.enabled else "❌ DISABLED",
            inline=True
        )

        embed.add_field(
            name="Parser Available",
            value="✅ Yes" if PROXIMITY_AVAILABLE else "❌ No",
            inline=True
        )

        embed.add_field(
            name="Files Imported",
            value=str(self.import_count),
            inline=True
        )

        embed.add_field(
            name="Local Path",
            value=self.local_dir,
            inline=False
        )

        if self.remote_path:
            embed.add_field(
                name="Remote Path",
                value=self.remote_path,
                inline=False
            )

        embed.add_field(
            name="Errors",
            value=str(self.error_count),
            inline=True
        )

        if self.last_scan_time:
            embed.add_field(
                name="Last Scan",
                value=self.last_scan_time.strftime("%H:%M:%S"),
                inline=True
            )

        # Get database stats if enabled
        if self.enabled and PROXIMITY_AVAILABLE:
            try:
                result = await self.bot.db_adapter.fetch_one(
                    "SELECT COUNT(*) FROM combat_engagement"
                )
                engagement_count = result[0] if result else 0

                result = await self.bot.db_adapter.fetch_one(
                    "SELECT COUNT(*) FROM crossfire_pairs"
                )
                pair_count = result[0] if result else 0

                embed.add_field(
                    name="📊 Database",
                    value=f"Engagements: {engagement_count:,}\nCrossfire pairs: {pair_count}",
                    inline=False
                )
            except Exception as e:
                embed.add_field(
                    name="📊 Database",
                    value=f"Error: {e}",
                    inline=False
                )

        # v5 teamplay table counts
        try:
            v5_tables = {
                'proximity_spawn_timing': 'Spawn Timing',
                'proximity_team_cohesion': 'Team Cohesion',
                'proximity_crossfire_opportunity': 'Crossfire Opps',
                'proximity_team_push': 'Team Pushes',
                'proximity_lua_trade_kill': 'Lua Trade Kills',
            }
            v5_parts = []
            for table, label in v5_tables.items():
                count_row = await self.bot.db_adapter.fetch_one(
                    f"SELECT COUNT(*) FROM {table}"
                )
                count = int(count_row[0]) if count_row else 0
                v5_parts.append(f"{label}: {count:,}")
            embed.add_field(
                name="v5 Teamplay Data",
                value="\n".join(v5_parts),
                inline=False
            )
        except Exception as e:
            logger.debug("v5 teamplay data unavailable: %s", e)

        embed.set_footer(text="Proximity tracker runs independently of main stats")

        await ctx.send(embed=embed)

    @commands.command(name='proximity_objectives')
    @commands.has_permissions(administrator=True)
    async def proximity_objectives(self, ctx):
        """Show which maps have objective coordinates configured"""
        if not self.commands_enabled and not self.enabled:
            await ctx.send("⚠️ Proximity commands are disabled.")
            return

        data = self._load_objective_coords()
        maps = data.get("maps", {})
        if not maps:
            await ctx.send("⚠️ No objective coord data found.")
            return

        configured = []
        missing = []
        for map_name, entries in maps.items():
            has_coords = False
            for entry in entries or []:
                if entry.get("x") is not None and entry.get("y") is not None and entry.get("z") is not None:
                    has_coords = True
                    break
            if has_coords:
                configured.append(map_name)
            else:
                missing.append(map_name)

        configured.sort()
        missing.sort()

        header = f"Objective coords: {len(configured)}/{len(configured) + len(missing)} maps configured"
        parts = [header]
        if configured:
            parts.append("Configured: " + ", ".join(configured))
        if missing:
            parts.append("Missing: " + ", ".join(missing))

        message = "\n".join(parts)
        if len(message) <= 1900:
            await ctx.send(message)
            return

        # Split into multiple messages if too long
        await ctx.send(header)
        if configured:
            await ctx.send("Configured: " + ", ".join(configured))
        if missing:
            await ctx.send("Missing: " + ", ".join(missing))

    @commands.command(name='proximity_scan')
    @commands.has_permissions(administrator=True)
    async def proximity_scan(self, ctx):
        """Force scan for new engagement files (admin only)"""
        if not self.commands_enabled and not self.enabled:
            await ctx.send("⚠️ Proximity commands are disabled.")
            return

        await ctx.send("🔍 Scanning for engagement files...")

        # Run the scan manually
        await self._scan_and_import(force=True)

        await ctx.send(
            f"✅ Scan complete.\n"
            f"• Files processed this session: {self.import_count}\n"
            f"• Files in memory: {len(self.processed_engagement_files)}"
        )

    @commands.command(name='proximity_import')
    @commands.has_permissions(administrator=True)
    async def proximity_import(self, ctx, filename: str = None):
        """Manually import an engagement file (admin only)"""
        if not self.commands_enabled and not self.enabled:
            await ctx.send("⚠️ Proximity commands are disabled.")
            return

        if not PROXIMITY_AVAILABLE:
            await ctx.send("❌ Proximity parser not available")
            return

        if not filename:
            await ctx.send("Usage: `!proximity_import <filename>`")
            return

        filepath = Path(self.local_dir) / filename
        if not filepath.exists():
            await ctx.send(f"❌ File not found: {filepath}")
            return

        await ctx.send(f"📥 Importing {filename}...")

        success = await self._import_engagement_file(filepath)

        if success:
            await ctx.send(f"✅ Successfully imported {filename}")
        else:
            await ctx.send(f"❌ Failed to import {filename}")

    # =========================================================================
    # V5 TEAMPLAY COMMANDS
    # =========================================================================

    @commands.command(name='proximity_spawn_efficiency', aliases=['pse'])
    async def proximity_spawn_efficiency(self, ctx, session_date: str = None):
        """Top 10 players by spawn timing efficiency (v5)"""
        if not self.commands_enabled and not self.enabled:
            await ctx.send("Proximity commands are disabled.")
            return

        try:
            date_filter = ""
            params = []
            if session_date:
                date_filter = "WHERE session_date = $1"
                params = [session_date]
            else:
                date_filter = "WHERE session_date >= CURRENT_DATE - INTERVAL '30 days'"

            rows = await self.bot.db_adapter.fetch_all(f"""
                SELECT killer_guid, MAX(killer_name) AS name,
                       ROUND(AVG(spawn_timing_score)::numeric, 3) AS avg_score,
                       COUNT(*) AS kills,
                       ROUND(AVG(time_to_next_spawn)::numeric, 0) AS avg_denial_ms
                FROM proximity_spawn_timing
                {date_filter}
                GROUP BY killer_guid
                HAVING COUNT(*) >= 5
                ORDER BY avg_score DESC
                LIMIT 10
            """, tuple(params))

            if not rows:
                await ctx.send("No spawn timing data found.")
                return

            embed = discord.Embed(
                title="Spawn Timing Efficiency - Top 10",
                description="Higher score = kills timed to maximize enemy respawn wait",
                color=discord.Color.orange()
            )
            for i, row in enumerate(rows, 1):
                name = row[1] or row[0][:8]
                score = float(row[2] or 0)
                kills = int(row[3] or 0)
                denial_ms = int(row[4] or 0)
                embed.add_field(
                    name=f"{i}. {name}",
                    value=f"Score: **{score:.1%}** | Kills: {kills} | Avg denial: {denial_ms}ms",
                    inline=False
                )

            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"spawn_efficiency error: {e}", exc_info=True)
            await ctx.send(f"Error: {e}")

    @commands.command(name='proximity_cohesion', aliases=['pco'])
    async def proximity_cohesion(self, ctx, session_date: str = None):
        """Team cohesion summary - Axis vs Allies formation tightness (v5)"""
        if not self.commands_enabled and not self.enabled:
            await ctx.send("Proximity commands are disabled.")
            return

        try:
            date_filter = ""
            params = []
            if session_date:
                date_filter = "WHERE session_date = $1"
                params = [session_date]
            else:
                date_filter = "WHERE session_date >= CURRENT_DATE - INTERVAL '30 days'"

            rows = await self.bot.db_adapter.fetch_all(f"""
                SELECT team,
                       ROUND(AVG(dispersion)::numeric, 1) AS avg_dispersion,
                       ROUND(AVG(max_spread)::numeric, 1) AS avg_max_spread,
                       ROUND(AVG(straggler_count)::numeric, 1) AS avg_stragglers,
                       ROUND(AVG(alive_count)::numeric, 1) AS avg_alive,
                       COUNT(*) AS samples
                FROM proximity_team_cohesion
                {date_filter}
                GROUP BY team
                ORDER BY team
            """, tuple(params))

            if not rows:
                await ctx.send("No team cohesion data found.")
                return

            def classify(disp):
                if disp < 300:
                    return "TIGHT"
                if disp < 800:
                    return "NORMAL"
                if disp < 1500:
                    return "LOOSE"
                return "SCATTERED"

            embed = discord.Embed(
                title="Team Cohesion Summary",
                description="Formation tightness analysis",
                color=discord.Color.blue()
            )

            for row in rows:
                team = row[0]
                disp = float(row[1] or 0)
                spread = float(row[2] or 0)
                stragglers = float(row[3] or 0)
                alive = float(row[4] or 0)
                samples = int(row[5] or 0)
                classification = classify(disp)

                embed.add_field(
                    name=f"{team} - {classification}",
                    value=(
                        f"Avg dispersion: **{disp:.0f}** units\n"
                        f"Max spread: {spread:.0f} | Stragglers: {stragglers:.1f}\n"
                        f"Avg alive: {alive:.1f} | Samples: {samples}"
                    ),
                    inline=True
                )

            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"cohesion error: {e}", exc_info=True)
            await ctx.send(f"Error: {e}")

    @commands.command(name='proximity_crossfire_angles', aliases=['pxa'])
    async def proximity_crossfire_angles(self, ctx, session_date: str = None):
        """Crossfire opportunity analysis with utilization rate (v5)"""
        if not self.commands_enabled and not self.enabled:
            await ctx.send("Proximity commands are disabled.")
            return

        try:
            date_filter = ""
            params = []
            if session_date:
                date_filter = "WHERE session_date = $1"
                params = [session_date]
            else:
                date_filter = "WHERE session_date >= CURRENT_DATE - INTERVAL '30 days'"

            summary = await self.bot.db_adapter.fetch_one(f"""
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN was_executed THEN 1 ELSE 0 END) AS executed,
                       ROUND(AVG(angular_separation)::numeric, 1) AS avg_angle
                FROM proximity_crossfire_opportunity
                {date_filter}
            """, tuple(params))

            total = int(summary[0] or 0) if summary else 0
            if total == 0:
                await ctx.send("No crossfire opportunity data found.")
                return

            executed = int(summary[1] or 0)
            avg_angle = float(summary[2] or 0)
            util_rate = (executed / total * 100) if total > 0 else 0

            duos = await self.bot.db_adapter.fetch_all(f"""
                SELECT teammate1_guid, teammate2_guid,
                       COUNT(*) AS executions
                FROM proximity_crossfire_opportunity
                {date_filter} AND was_executed = TRUE
                GROUP BY teammate1_guid, teammate2_guid
                ORDER BY executions DESC
                LIMIT 5
            """, tuple(params))

            embed = discord.Embed(
                title="Crossfire Opportunity Analysis",
                color=discord.Color.red()
            )
            embed.add_field(
                name="Summary",
                value=(
                    f"Total opportunities: **{total}**\n"
                    f"Executed: **{executed}** ({util_rate:.1f}%)\n"
                    f"Avg angle: {avg_angle:.1f} deg"
                ),
                inline=False
            )

            if duos:
                duo_text = ""
                for i, row in enumerate(duos, 1):
                    duo_text += f"{i}. `{row[0][:8]}` + `{row[1][:8]}` = {row[2]} executions\n"
                embed.add_field(name="Top Crossfire Duos", value=duo_text, inline=False)

            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"crossfire_angles error: {e}", exc_info=True)
            await ctx.send(f"Error: {e}")

    @commands.command(name='proximity_trades_lua', aliases=['ptl'])
    async def proximity_trades_lua(self, ctx, session_date: str = None):
        """Lua-detected trade kill leaderboard (v5)"""
        if not self.commands_enabled and not self.enabled:
            await ctx.send("Proximity commands are disabled.")
            return

        try:
            date_filter = ""
            params = []
            if session_date:
                date_filter = "WHERE session_date = $1"
                params = [session_date]
            else:
                date_filter = "WHERE session_date >= CURRENT_DATE - INTERVAL '30 days'"

            leaders = await self.bot.db_adapter.fetch_all(f"""
                SELECT trader_guid, MAX(trader_name) AS name,
                       COUNT(*) AS trades,
                       ROUND(AVG(delta_ms)::numeric, 0) AS avg_reaction,
                       MIN(delta_ms) AS fastest
                FROM proximity_lua_trade_kill
                {date_filter}
                GROUP BY trader_guid
                ORDER BY trades DESC
                LIMIT 10
            """, tuple(params))

            recent = await self.bot.db_adapter.fetch_all(f"""
                SELECT original_victim_name, original_killer_name, trader_name, delta_ms
                FROM proximity_lua_trade_kill
                {date_filter}
                ORDER BY session_date DESC, traded_kill_time DESC
                LIMIT 5
            """, tuple(params))

            embed = discord.Embed(
                title="Trade Kill Leaderboard (Lua-detected)",
                description="Teammate avenges your death within time window",
                color=discord.Color.gold()
            )

            if leaders:
                for i, row in enumerate(leaders, 1):
                    name = row[1] or row[0][:8]
                    trades = int(row[2] or 0)
                    avg_ms = int(row[3] or 0)
                    fastest = int(row[4] or 0)
                    embed.add_field(
                        name=f"{i}. {name}",
                        value=f"Trades: **{trades}** | Avg: {avg_ms}ms | Fastest: {fastest}ms",
                        inline=False
                    )
            else:
                embed.add_field(name="No data", value="No trade kills recorded", inline=False)

            if recent:
                chain_text = ""
                for row in recent:
                    chain_text += f"{row[0]} killed by {row[1]} -> avenged by **{row[2]}** ({row[3]}ms)\n"
                embed.add_field(name="Recent Trades", value=chain_text, inline=False)

            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"trades_lua error: {e}", exc_info=True)
            await ctx.send(f"Error: {e}")

    @commands.command(name='proximity_pushes', aliases=['ppu'])
    async def proximity_pushes(self, ctx, session_date: str = None):
        """Team push quality comparison - Axis vs Allies (v5)"""
        if not self.commands_enabled and not self.enabled:
            await ctx.send("Proximity commands are disabled.")
            return

        try:
            date_filter = ""
            params = []
            if session_date:
                date_filter = "WHERE session_date = $1"
                params = [session_date]
            else:
                date_filter = "WHERE session_date >= CURRENT_DATE - INTERVAL '30 days'"

            rows = await self.bot.db_adapter.fetch_all(f"""
                SELECT team,
                       COUNT(*) AS pushes,
                       ROUND(AVG(push_quality)::numeric, 3) AS avg_quality,
                       ROUND(AVG(participant_count)::numeric, 1) AS avg_participants,
                       SUM(CASE WHEN toward_objective NOT IN ('NO', 'N/A') THEN 1 ELSE 0 END) AS obj_pushes
                FROM proximity_team_push
                {date_filter}
                GROUP BY team
                ORDER BY team
            """, tuple(params))

            if not rows:
                await ctx.send("No team push data found.")
                return

            embed = discord.Embed(
                title="Team Push Comparison",
                description="Coordinated team movement analysis",
                color=discord.Color.purple()
            )

            for row in rows:
                team = row[0]
                pushes = int(row[1] or 0)
                quality = float(row[2] or 0)
                participants = float(row[3] or 0)
                obj = int(row[4] or 0)
                obj_pct = (obj / pushes * 100) if pushes > 0 else 0

                embed.add_field(
                    name=f"{team}",
                    value=(
                        f"Pushes: **{pushes}**\n"
                        f"Avg quality: {quality:.3f}\n"
                        f"Avg participants: {participants:.1f}\n"
                        f"Objective-oriented: {obj_pct:.0f}%"
                    ),
                    inline=True
                )

            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"pushes error: {e}", exc_info=True)
            await ctx.send(f"Error: {e}")


    # ── SESSION SCORE ──────────────────────────────────────────────────

    @commands.command(name="proximity_session", aliases=["psession", "pscore"])
    async def proximity_session_scores(self, ctx, session_date: str = None):
        """Per-session proximity combat scores.

        Usage: !psession [YYYY-MM-DD]
        Shows composite score (0-100) from 7 categories:
        Kill Timing, Crossfire, Focus Fire, Trades, Survivability, Movement, Reactions
        """
        try:
            from bot.services.proximity_session_score_service import ProximitySessionScoreService
            svc = ProximitySessionScoreService(self.bot.db_adapter)

            if not session_date:
                session_date = await svc.get_latest_session_date()
            if not session_date:
                await ctx.send("No proximity data found.")
                return

            results = await svc.compute_session_scores(session_date)
            if not results:
                await ctx.send(f"No proximity data for session {session_date} (min {3} engagements required).")
                return

            embed = discord.Embed(
                title=f"Proximity Session Score — {session_date}",
                description="Composite combat performance from proximity analytics",
                color=discord.Color.teal(),
            )

            medal = ["🥇", "🥈", "🥉"]
            for i, p in enumerate(results[:12]):
                cat = p["categories"]
                prefix = medal[i] if i < 3 else f"{i+1}."
                embed.add_field(
                    name=f"{prefix} {p['name']} — **{p['total_score']:.1f}** / 100",
                    value=(
                        f"⏱ Tim: {cat['kill_timing']['weighted']:.0f} "
                        f"✕ XF: {cat['crossfire']['weighted']:.0f} "
                        f"🎯 FF: {cat['focus_fire']['weighted']:.0f} "
                        f"⚔ Trd: {cat['trades']['weighted']:.0f}\n"
                        f"🛡 Srv: {cat['survivability']['weighted']:.0f} "
                        f"💨 Mov: {cat['movement']['weighted']:.0f} "
                        f"⚡ Rct: {cat['reactions']['weighted']:.0f} "
                        f"({p['engagement_count']} eng)"
                    ),
                    inline=False,
                )

            total_eng = sum(p["engagement_count"] for p in results)
            embed.set_footer(text=f"{len(results)} players, {total_eng} total engagements")
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"psession error: {e}", exc_info=True)
            await ctx.send(f"Error: {e}")


    # ===== v6 CARRIER INTELLIGENCE COMMANDS =====

    @commands.command(name='proximity_carriers', aliases=['pca'])
    async def proximity_carriers(self, ctx, session_date: str = None):
        """Top carrier leaderboard - distance, secures, efficiency (v6)"""
        if not self.commands_enabled and not self.enabled:
            await ctx.send("Proximity commands are disabled.")
            return

        try:
            date_filter = ""
            params = []
            if session_date:
                date_filter = "WHERE session_date = $1"
                params = [session_date]
            else:
                date_filter = "WHERE session_date >= CURRENT_DATE - INTERVAL '30 days'"

            rows = await self.bot.db_adapter.fetch_all(f"""
                SELECT carrier_guid, MAX(carrier_name) AS name,
                       COUNT(*) AS carries,
                       SUM(CASE WHEN outcome = 'secured' THEN 1 ELSE 0 END) AS secures,
                       SUM(CASE WHEN outcome = 'killed' THEN 1 ELSE 0 END) AS killed,
                       ROUND(SUM(carry_distance)::numeric, 0) AS total_distance,
                       ROUND(AVG(efficiency)::numeric, 3) AS avg_efficiency,
                       ROUND(AVG(duration_ms)::numeric, 0) AS avg_duration
                FROM proximity_carrier_event
                {date_filter}
                GROUP BY carrier_guid
                HAVING COUNT(*) >= 1
                ORDER BY secures DESC, total_distance DESC
                LIMIT 10
            """, tuple(params))

            if not rows:
                await ctx.send("No carrier data found.")
                return

            embed = discord.Embed(
                title="Objective Carriers - Top 10",
                description="Flag/docs/gold carrier stats",
                color=discord.Color.gold()
            )
            for i, row in enumerate(rows, 1):
                name = row[1] or row[0][:8]
                carries = int(row[2] or 0)
                secures = int(row[3] or 0)
                killed = int(row[4] or 0)
                distance = float(row[5] or 0)
                eff = float(row[6] or 0)
                duration = int(row[7] or 0)
                secure_rate = (secures / carries * 100) if carries > 0 else 0
                embed.add_field(
                    name=f"{i}. {name}",
                    value=(
                        f"Carries: {carries} | Secures: **{secures}** ({secure_rate:.0f}%)\n"
                        f"Killed: {killed} | Distance: {distance:.0f}u | Eff: {eff:.1%}\n"
                        f"Avg carry: {duration/1000:.1f}s"
                    ),
                    inline=False
                )

            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"carriers error: {e}", exc_info=True)
            await ctx.send(f"Error: {e}")

    @commands.command(name='proximity_carrier_kills', aliases=['pck'])
    async def proximity_carrier_kills(self, ctx, session_date: str = None):
        """Top carrier killers - who stops objective runners (v6)"""
        if not self.commands_enabled and not self.enabled:
            await ctx.send("Proximity commands are disabled.")
            return

        try:
            date_filter = ""
            params = []
            if session_date:
                date_filter = "WHERE session_date = $1"
                params = [session_date]
            else:
                date_filter = "WHERE session_date >= CURRENT_DATE - INTERVAL '30 days'"

            rows = await self.bot.db_adapter.fetch_all(f"""
                SELECT killer_guid, MAX(killer_name) AS name,
                       COUNT(*) AS carrier_kills,
                       ROUND(AVG(carrier_distance_at_kill)::numeric, 0) AS avg_distance_stopped
                FROM proximity_carrier_kill
                {date_filter}
                GROUP BY killer_guid
                HAVING COUNT(*) >= 1
                ORDER BY carrier_kills DESC
                LIMIT 10
            """, tuple(params))

            if not rows:
                await ctx.send("No carrier kill data found.")
                return

            embed = discord.Embed(
                title="Carrier Killers - Top 10",
                description="Most objective carrier kills",
                color=discord.Color.red()
            )
            for i, row in enumerate(rows, 1):
                name = row[1] or row[0][:8]
                kills = int(row[2] or 0)
                avg_dist = float(row[3] or 0)
                embed.add_field(
                    name=f"{i}. {name}",
                    value=f"Carrier kills: **{kills}** | Avg distance stopped: {avg_dist:.0f}u",
                    inline=False
                )

            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"carrier_kills error: {e}", exc_info=True)
            await ctx.send(f"Error: {e}")

    @commands.command(name='proximity_carry_detail', aliases=['pcd'])
    async def proximity_carry_detail(self, ctx, session_date: str = None):
        """Detailed carrier event log for a session (v6)"""
        if not self.commands_enabled and not self.enabled:
            await ctx.send("Proximity commands are disabled.")
            return

        try:
            date_filter = ""
            params = []
            if session_date:
                date_filter = "WHERE session_date = $1"
                params = [session_date]
            else:
                date_filter = "WHERE session_date = (SELECT MAX(session_date) FROM proximity_carrier_event)"

            rows = await self.bot.db_adapter.fetch_all(f"""
                SELECT carrier_name, carrier_team, flag_team, outcome,
                       carry_distance, beeline_distance, efficiency,
                       duration_ms, map_name, killer_name
                FROM proximity_carrier_event
                {date_filter}
                ORDER BY pickup_time
                LIMIT 20
            """, tuple(params))

            if not rows:
                await ctx.send("No carrier events found.")
                return

            outcome_icons = {
                'secured': '+', 'killed': 'X', 'dropped': 'D',
                'returned': 'R', 'round_end': 'E', 'disconnected': 'DC'
            }

            embed = discord.Embed(
                title="Carrier Event Log",
                description="Recent objective carry events",
                color=discord.Color.dark_gold()
            )
            for row in rows:
                name = row[0]
                team = row[1]
                outcome = row[3]
                distance = float(row[4] or 0)
                eff = float(row[6] or 0)
                duration = int(row[7] or 0)
                map_name = row[8]
                killer = row[9]
                icon = outcome_icons.get(outcome, '?')

                detail = f"[{icon}] {outcome} | {distance:.0f}u ({eff:.0%}) | {duration/1000:.1f}s"
                if outcome == 'killed' and killer:
                    detail += f" by {killer}"
                embed.add_field(
                    name=f"{name} ({team}) on {map_name}",
                    value=detail,
                    inline=False
                )

            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"carry_detail error: {e}", exc_info=True)
            await ctx.send(f"Error: {e}")


async def setup(bot):
    """Setup function for cog loading"""
    await bot.add_cog(ProximityCog(bot))
