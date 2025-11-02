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
import sqlite3
import sys
import time
from datetime import datetime

import aiosqlite
import io
import discord
from discord.ext import commands, tasks

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.stopwatch_scoring import StopwatchScoring

# Import extracted core classes
from bot.core import StatsCache, SeasonManager, AchievementSystem

# Load environment variables if available
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# ==================== COMPREHENSIVE LOGGING SETUP ====================

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Configure logging with both file and console output
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
log_file = os.getenv("LOG_FILE", "logs/bot.log")

# Create formatter with timestamp, level, name, and message
formatter = logging.Formatter(
    '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# File handler - logs everything to file
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)  # Log everything to file
file_handler.setFormatter(formatter)

# Console handler - logs INFO and above to console
console_handler = logging.StreamHandler()
console_handler.setLevel(getattr(logging, log_level))
console_handler.setFormatter(formatter)

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,  # Capture everything
    handlers=[file_handler, console_handler]
)

# Get bot logger
logger = logging.getLogger("UltimateBot")
logger.info("=" * 80)
logger.info("🚀 ET:LEGACY DISCORD BOT - STARTING UP")
logger.info("=" * 80)
logger.info(f"📝 Log Level: {log_level}")
logger.info(f"📁 Log File: {log_file}")

# Reduce noise from verbose third-party libraries
logging.getLogger("paramiko").setLevel(logging.WARNING)
logging.getLogger("paramiko.transport").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("discord").setLevel(logging.INFO)
logging.getLogger("discord.http").setLevel(logging.WARNING)
logging.getLogger("discord.gateway").setLevel(logging.WARNING)

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


class ETLegacyCommands(commands.Cog):
    """🎮 ET:Legacy Bot Commands Cog"""

    def __init__(self, bot):
        self.bot = bot
        # Initialize query cache (5 min TTL)
        self.stats_cache = StatsCache(ttl_seconds=300)
        # Initialize achievement system
        self.achievements = AchievementSystem(bot)
        # Initialize season system
        self.season_manager = SeasonManager()
        logger.info(
            "✅ ETLegacyCommands initialized with caching, achievements & seasons"
        )

    async def _ensure_player_name_alias(
        self, db: "aiosqlite.Connection"
    ) -> None:
        """Delegate to the module-level ensure_player_name_alias helper.

        This keeps non-Cog code able to call the same logic via the top-level
        helper while preserving the original logging behavior here.
        """
        try:
            await ensure_player_name_alias(db)
        except Exception:
            logger.exception(
                "Failed to create TEMP VIEW alias for player_name; queries may still fail"
            )

    async def _send_last_session_help(self, ctx):
        """Send a compact one-line help hint for `!last_session`.

        This prints a short list of common subcommands so users see the
        available quick actions whenever they use `!last_session`.
        """
        help_text = (
            "`!last_session` subcommands: `graphs`, `full`, `weapons`, "
            "`combat`, `obj`, `support`, `sprees`, `top` — "
            "Use `!last_session help` for a detailed list."
        )
        try:
            await ctx.send(help_text)
        except Exception:
            # Non-fatal; don't block the main command if sending the hint fails
            logger.debug("Could not send last_session help hint to channel")

    async def _enable_sql_diag(self, db: "aiosqlite.Connection"):
        """Enable lightweight SQL diagnostics on a per-connection basis.

        This monkeypatches the connection.execute method to log the full SQL
        text, params and some PRAGMA information if an sqlite3.OperationalError
        occurs. It's intended as a temporary diagnostic aid to capture the
        exact failing statement and the connection-visible schema.
        """
        # Avoid double-wrapping the same connection
        if getattr(db, "_orig_execute", None):
            return

        import sqlite3

        # Save original bound method
        db._orig_execute = db.execute

        def _wrapped_execute(sql, params=()):
            """Return an async context manager that proxies the original
            execute() result but captures sqlite OperationalError diagnostics.

            The original aiosqlite Connection.execute returns an object that
            implements the async context manager protocol (used via
            `async with db.execute(...) as cur:`). Replacing `db.execute` with
            an async function caused a coroutine to be returned and broke that
            protocol. This wrapper returns a small proxy object that exposes
            `__aenter__`/`__aexit__` and delegates to the original result,
            allowing diagnostics on OperationalError without changing call
            sites.
            """

            class _CursorWrapper:
                def __init__(self, inner, db_conn, sql_text, params_val):
                    self._inner = inner
                    self._db = db_conn
                    self._sql = sql_text
                    self._params = params_val

                async def __aenter__(self):
                    try:
                        # Delegate to the underlying cursor's __aenter__
                        return await self._inner.__aenter__()
                    except sqlite3.OperationalError as e:
                        try:
                            logger.error(
                                "OperationalError executing SQL: %s | params=%r",
                                self._sql,
                                self._params,
                                exc_info=True,
                            )
                        except Exception:
                            logger.exception(
                                "OperationalError (unable to log SQL) %s", e
                            )

                        # Gather helpful diagnostics about the connection's schema/state
                        try:
                            async with self._db._orig_execute(
                                "PRAGMA table_info('player_comprehensive_stats')"
                            ) as cur:
                                cols = await cur.fetchall()
                                logger.error(
                                    "PRAGMA table_info(player_comprehensive_stats): %s",
                                    cols,
                                )
                        except Exception:
                            logger.exception("Failed to read PRAGMA table_info")

                        try:
                            async with self._db._orig_execute(
                                "SELECT name, type, sql FROM sqlite_temp_master"
                            ) as cur:
                                temp = await cur.fetchall()
                                logger.error(
                                    "sqlite_temp_master (temp objects): %s", temp
                                )
                        except Exception:
                            logger.exception("Failed to read sqlite_temp_master")

                        try:
                            async with self._db._orig_execute(
                                "PRAGMA database_list"
                            ) as cur:
                                dbl = await cur.fetchall()
                                logger.error("PRAGMA database_list: %s", dbl)
                        except Exception:
                            logger.exception("Failed to read PRAGMA database_list")

                        # Re-raise so calling code still sees the original exception
                        raise

                async def __aexit__(self, exc_type, exc, tb):
                    return await self._inner.__aexit__(exc_type, exc, tb)

            inner = db._orig_execute(sql, params)
            return _CursorWrapper(inner, db, sql, params)

        # Attach wrapper (regular function returning async context manager)
        db.execute = _wrapped_execute

    async def _log_and_send(
        self,
        ctx,
        embed_obj,
        name: str | None = None,
        latest_date: str | None = None,
    ):
        """Log embed field lengths and automatically chunk any overly-large field.

        This is the Cog-level shared helper that replaces nested copies. It will
        split fields longer than ~900 chars into continuation embeds and send
        them after the main embed. Pass `latest_date` if you want page footers
        that include the session date.
        """
        nm = name or "embed"
        try:
            main_fields = []
            continuation_embeds = []

            for idx, fld in enumerate(list(embed_obj.fields)):
                try:
                    val = fld.value or ""
                    ln = len(val)
                except Exception:
                    val = ""
                    ln = 0

                logger.debug(
                    f"[last_session] {nm} field[{idx}] '{getattr(fld, 'name', '')}' length={ln}"
                )
                if ln > 1024:
                    logger.warning(
                        f"[last_session] {nm} field[{idx}] '{getattr(fld, 'name', '')}' LENGTH {ln} > 1024 - will chunk to avoid HTTP 400"
                    )

                if ln > 900:
                    chunks = _split_chunks(val, max_len=900)
                    first_chunk = chunks[0] if chunks else ""
                    main_fields.append((fld.name, first_chunk, fld.inline))

                    for i, ch in enumerate(chunks[1:], start=2):
                        cont = discord.Embed(
                            title=(embed_obj.title + " (cont.)")
                            if embed_obj.title
                            else "(cont.)",
                            description=None,
                            color=getattr(
                                embed_obj,
                                "colour",
                                getattr(embed_obj, "color", None),
                            )
                            or 0x2B2D31,
                            timestamp=getattr(embed_obj, "timestamp", None),
                        )
                        cont.add_field(
                            name=f"{fld.name} (cont. {i})",
                            value=ch,
                            inline=False,
                        )
                        continuation_embeds.append(cont)
                else:
                    main_fields.append((fld.name, val, fld.inline))

            main = discord.Embed(
                title=embed_obj.title,
                description=embed_obj.description,
                color=getattr(
                    embed_obj, "colour", getattr(embed_obj, "color", None)
                )
                or 0x2B2D31,
                timestamp=getattr(embed_obj, "timestamp", None),
            )

            for name_f, value_f, inline_f in main_fields:
                main.add_field(name=name_f, value=value_f, inline=inline_f)

            try:
                if embed_obj.footer and getattr(
                    embed_obj.footer, "text", None
                ):
                    main.set_footer(text=embed_obj.footer.text)
            except Exception:
                pass

        except Exception as e:
            logger.exception(
                f"[last_session] error while preparing embed for send: {e}"
            )
            await ctx.send(embed=embed_obj)
            return

        await ctx.send(embed=main)

        if continuation_embeds:
            total_pages = 1 + len(continuation_embeds)
            for i, cont in enumerate(continuation_embeds):
                try:
                    if latest_date:
                        cont.set_footer(
                            text=(
                                f"Session: {latest_date} • Page {i+2}/{total_pages}"
                            )
                        )
                    else:
                        cont.set_footer(text=(f"Page {i+2}/{total_pages}"))
                except Exception:
                    pass
                await ctx.send(embed=cont)
                await asyncio.sleep(1.2)

    # 🎮 SESSION MANAGEMENT COMMANDS

    # ============================================================================
    # MOVED TO SESSION MANAGEMENT COG (bot/cogs/session_management_cog.py)
    # Commands: session_start, session_end
    # ============================================================================
    
    # ============================================================================
    # MOVED TO SYNC COG (bot/cogs/sync_cog.py)
    # Commands: sync_stats, sync_today, sync_week, sync_month, sync_all
    # Helpers: parse_time_period, _should_include_file
    # These commands have been moved to the Sync Cog and are commented out below
    # to prevent command registration conflicts.
    # ============================================================================

    # # @commands.command(name="sync_stats", aliases=["syncstats", "sync_logs"])
    # async def sync_stats(self, ctx, period: str = None):
    # """🔄 Manually sync and process stats files from server
    # 
    # Usage: !sync_stats [period]  (period examples: 1day, 2weeks, 1month, all)
    # """
    # try:
    # if not self.bot.ssh_enabled:
    # await ctx.send(
    # "❌ SSH monitoring is not enabled. "
    # "Set `SSH_ENABLED=true` in .env file."
    # )
    # return
    # 
    # # Parse time period (default 2 weeks)
    # # parse_time_period is synchronous, do not await it
    # days_back = self.parse_time_period(period) if period else 14
    # 
    # # Friendly period display
    # if days_back:
    # period_display = f"last {days_back} days"
    # if days_back == 1:
    # period_display = "last 24 hours"
    # elif days_back == 7:
    # period_display = "last week"
    # elif days_back == 14:
    # period_display = "last 2 weeks"
    # elif days_back == 30:
    # period_display = "last month"
    # elif days_back == 365:
    # period_display = "last year"
    # else:
    # period_display = "all time (no filter)"
    # 
    # # Send initial message
    # status_msg = await ctx.send(
    # f"🔄 Checking remote server for new stats files...\n📅 Time period: **{period_display}**"
    # )
    # 
    # # Build SSH config
    # ssh_config = {
    # "host": os.getenv("SSH_HOST"),
    # "port": int(os.getenv("SSH_PORT", 22)),
    # "user": os.getenv("SSH_USER"),
    # "key_path": os.getenv("SSH_KEY_PATH", ""),
    # "remote_path": os.getenv("REMOTE_STATS_PATH"),
    # }
    # 
    # # List remote files
    # remote_files = await self.bot.ssh_list_remote_files(ssh_config)
    # 
    # if not remote_files:
    # await status_msg.edit(
    # content="❌ Could not connect to server or no files found."
    # )
    # return
    # 
    # # Filter files by time period if requested
    # if days_back:
    # filtered = [f for f in remote_files if self._should_include_file(f, days_back)]
    # excluded_count = len(remote_files) - len(filtered)
    # remote_files = filtered
    # if excluded_count > 0:
    # await status_msg.edit(
    # content=(
    # f"🔄 Checking remote server...\n📅 Time period: **{period_display}**\n"
    # f"📊 Found **{len(remote_files)}** files in period ({excluded_count} older files excluded)"
    # )
    # )
    # 
    # # Check which files need processing
    # files_to_process = []
    # for filename in remote_files:
    # if await self.bot.should_process_file(filename):
    # files_to_process.append(filename)
    # 
    # if not files_to_process:
    # await status_msg.edit(
    # content="✅ All files are already processed! Nothing new to sync."
    # )
    # return
    # 
    # # Sort files: Round 1 before Round 2, chronologically
    # # Format: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
    # def sort_key(filename):
    # parts = filename.split("-")
    # if len(parts) >= 7:
    # date = "-".join(parts[:3])  # YYYY-MM-DD
    # time = parts[3]  # HHMMSS
    # round_num = parts[-1].replace(".txt", "")  # N from round-N
    # return (
    # date,
    # time,
    # round_num,
    # )  # Sort by date, time, then round
    # return (filename, "", "99")  # Fallback
    # 
    # files_to_process.sort(key=sort_key)
    # 
    # # Phase 1: Download ALL files first
    # await status_msg.edit(
    # content=f"📥 Downloading {len(files_to_process)} file(s)..."
    # )
    # 
    # downloaded_files = []
    # download_failed = 0
    # 
    # for i, filename in enumerate(files_to_process):
    # try:
    # # Download file
    # local_path = await self.bot.ssh_download_file(
    # ssh_config, filename, "local_stats"
    # )
    # 
    # if local_path:
    # downloaded_files.append((filename, local_path))
    # 
    # # Update progress every 50 files
    # if (i + 1) % 50 == 0:
    # await status_msg.edit(
    # content=f"📥 Downloading... {i + 1}/{len(files_to_process)}"
    # )
    # else:
    # download_failed += 1
    # logger.warning(f"Failed to download {filename}")
    # 
    # except Exception as e:
    # logger.error(f"Download error for {filename}: {e}")
    # download_failed += 1
    # 
    # # Phase 2: Verify downloads
    # await status_msg.edit(
    # content=f"🔍 Verifying downloads... {len(downloaded_files)} files"
    # )
    # 
    # local_files = set(os.listdir("local_stats"))
    # verified_files = []
    # 
    # for filename, local_path in downloaded_files:
    # if os.path.basename(local_path) in local_files:
    # verified_files.append((filename, local_path))
    # else:
    # logger.error(f"Downloaded file missing: {filename}")
    # download_failed += 1
    # 
    # logger.info(
    # f"✅ Downloaded {len(verified_files)} files, "
    # f"{download_failed} failed"
    # )
    # 
    # if not verified_files:
    # await status_msg.edit(
    # content="❌ No files were successfully downloaded."
    # )
    # return
    # 
    # # Phase 3: Process/parse files for database import
    # await status_msg.edit(
    # content=f"⚙️ Processing {len(verified_files)} file(s) for database import..."
    # )
    # 
    # processed = 0
    # process_failed = 0
    # 
    # for i, (filename, local_path) in enumerate(verified_files):
    # try:
    # # Process the file (parse + import)
    # result = await self.bot.process_gamestats_file(
    # local_path, filename
    # )
    # 
    # if result.get("success"):
    # processed += 1
    # else:
    # process_failed += 1
    # logger.error(
    # f"Processing failed for {filename}: {result.get('error')}"
    # )
    # 
    # # Update progress every 50 files
    # if (i + 1) % 50 == 0:
    # await status_msg.edit(
    # content=f"⚙️ Processing... {i + 1}/{len(verified_files)}"
    # )
    # 
    # except Exception as e:
    # logger.error(f"Failed to process {filename}: {e}")
    # process_failed += 1
    # 
    # # Final status
    # embed = discord.Embed(
    # title="✅ Stats Sync Complete!",
    # color=0x00FF00,
    # timestamp=datetime.now(),
    # )
    # embed.add_field(
    # name="� Download Phase",
    # value=(
    # f"✅ Downloaded: **{len(verified_files)}** file(s)\n"
    # f"❌ Failed: **{download_failed}** file(s)"
    # ),
    # inline=False,
    # )
    # embed.add_field(
    # name="⚙️ Processing Phase",
    # value=(
    # f"✅ Processed: **{processed}** file(s)\n"
    # f"❌ Failed: **{process_failed}** file(s)"
    # ),
    # inline=False,
    # )
    # 
    # if processed > 0:
    # embed.add_field(
    # name="💡 What's Next?",
    # value=(
    # "Round summaries have been posted above!\n"
    # "Use `!last_session` to see full session details."
    # ),
    # inline=False,
    # )
    # 
    # await status_msg.edit(content=None, embed=embed)
    # logger.info(
    # f"✅ Manual sync complete: {len(verified_files)} downloaded, "
    # f"{processed} processed, {process_failed} failed"
    # )
    # 
    # except Exception as e:
    # logger.error(f"Error in sync_stats: {e}")
    # await ctx.send(f"❌ Sync error: {e}")
    # 
    # @commands.command(name="sync_today", aliases=["sync1day"])
    # async def sync_today(self, ctx):
    # """🔄 Quick sync: Today's matches only (last 24 hours)"""
    # await self.sync_stats(ctx, period="1day")
    # 
    # @commands.command(name="sync_week", aliases=["sync1week"])
    # async def sync_week(self, ctx):
    # """🔄 Quick sync: This week's matches (last 7 days)"""
    # await self.sync_stats(ctx, period="1week")
    # 
    # @commands.command(name="sync_month", aliases=["sync1month"])
    # async def sync_month(self, ctx):
    # """🔄 Quick sync: This month's matches (last 30 days)"""
    # await self.sync_stats(ctx, period="1month")
    # 
    # @commands.command(name="sync_all")
    # async def sync_all(self, ctx):
    # """🔄 Quick sync: ALL unprocessed files (no time filter)"""
    # await self.sync_stats(ctx, period="all")
    # 
    # @commands.command(name="session_end")
    # async def session_end(self, ctx):
    # """🏁 Stop SSH monitoring"""
    # try:
    # if not self.bot.monitoring:
    # await ctx.send("❌ Monitoring is not currently active.")
    # return
    # 
    # # Disable monitoring flag
    # self.bot.monitoring = False
    # 
    # embed = discord.Embed(
    # title="🏁 Monitoring Stopped",
    # description=(
    # "SSH monitoring has been disabled.\n\n"
    # "Use `!session_start` to re-enable automatic monitoring."
    # ),
    # color=0xFF0000,
    # timestamp=datetime.now(),
    # )
    # 
    # await ctx.send(embed=embed)
    # logger.info("✅ Monitoring manually stopped via !session_end")
    # 
    # except Exception as e:
    # logger.error(f"Error ending session: {e}")
    # await ctx.send(f"❌ Error ending session: {e}")
    # 
    # @commands.command(name="session", aliases=["match", "game"])
    # async def session(self, ctx, *date_parts):
    # """📅 Show detailed session/match statistics for a full day
    # 
    # Usage:
    # - !session 2025-09-30  (show session from specific date)
    # - !session 2025 9 30   (alternative format)
    # - !session             (show most recent session)
    # 
    # Shows aggregated stats for entire day (all maps/rounds combined).
    # """
    # try:
    # # Parse date from arguments
    # if date_parts:
    # # Join parts: "2025 9 30" or "2025-09-30"
    # date_str = "-".join(str(p) for p in date_parts)
    # # Normalize format: ensure YYYY-MM-DD
    # parts = date_str.replace("-", " ").split()
    # if len(parts) >= 3:
    # year, month, day = parts[0], parts[1], parts[2]
    # date_filter = f"{year}-{int(month):02d}-{int(day):02d}"
    # else:
    # date_filter = date_str
    # else:
    # # Get most recent date
    # async with aiosqlite.connect(self.bot.db_path) as db:
    # async with db.execute(
    # """
    # SELECT DISTINCT DATE(session_date) as date
    # FROM player_comprehensive_stats
    # ORDER BY date DESC LIMIT 1
    # """
    # ) as cursor:
    # result = await cursor.fetchone()
    # if not result:
    # await ctx.send("❌ No sessions found in database")
    # return
    # date_filter = result[0]
    # 
    # # Now use the same logic as !last_session but for the specified date
    # # Just call last_session logic with date filter
    # await ctx.send(f"📅 Loading session data for **{date_filter}**...")
    # 
    # # Query aggregated stats for the full day
    # async with aiosqlite.connect(self.bot.db_path) as db:
    # # Get session metadata
    # query = """
    # SELECT 
    # COUNT(DISTINCT session_id) / 2 as total_maps,
    # COUNT(DISTINCT session_id) as total_rounds,
    # COUNT(DISTINCT player_guid) as player_count,
    # MIN(session_date) as first_round,
    # MAX(session_date) as last_round
    # FROM player_comprehensive_stats
    # WHERE DATE(session_date) = ?
    # """
    # 
    # async with db.execute(query, (date_filter,)) as cursor:
    # result = await cursor.fetchone()
    # if not result or result[0] == 0:
    # await ctx.send(
    # f"❌ No session found for date: {date_filter}"
    # )
    # return
    # 
    # (
    # total_maps,
    # total_rounds,
    # player_count,
    # first_round,
    # last_round,
    # ) = result
    # 
    # # Get unique maps played
    # async with db.execute(
    # """
    # SELECT DISTINCT map_name
    # FROM player_comprehensive_stats
    # WHERE DATE(session_date) = ?
    # ORDER BY session_date
    # """,
    # (date_filter,),
    # ) as cursor:
    # maps = await cursor.fetchall()
    # maps_list = [m[0] for m in maps]
    # 
    # # Build header embed
    # embed = discord.Embed(
    # title=f"� Session Summary: {date_filter}",
    # description=f"**{int(total_maps)} maps** • **{total_rounds} rounds** • **{player_count} players**",
    # color=0x00FF88,
    # )
    # 
    # # Add maps played
    # maps_text = ", ".join(maps_list)
    # if len(maps_text) > 900:
    # maps_text = (
    # ", ".join(maps_list[:8])
    # + f" (+{len(maps_list) - 8} more)"
    # )
    # embed.add_field(
    # name="🗺️ Maps Played", value=maps_text, inline=False
    # )
    # 
    # # Get top players aggregated
    # async with db.execute(
    # """
    # SELECT 
    # p.player_name,
    # SUM(p.kills) as kills,
    # SUM(p.deaths) as deaths,
    # CASE
    # WHEN SUM(p.time_played_seconds) > 0
    # THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
    # ELSE 0
    # END as dpm
    # FROM player_comprehensive_stats p
    # WHERE DATE(p.session_date) = ?
    # GROUP BY p.player_name
    # ORDER BY kills DESC
    # LIMIT 5
    # """,
    # (date_filter,),
    # ) as cursor:
    # top_players = await cursor.fetchall()
    # 
    # # Add top 5 players
    # if top_players:
    # player_text = ""
    # medals = ["🥇", "🥈", "🥉", "4.", "5."]
    # for i, (name, kills, deaths, dpm) in enumerate(
    # top_players
    # ):
    # kd = kills / deaths if deaths > 0 else kills
    # player_text += f"{medals[i]} **{name}** - {kills}K/{deaths}D ({kd:.2f} KD, {dpm:.0f} DPM)\n"
    # embed.add_field(
    # name="🏆 Top Players", value=player_text, inline=False
    # )
    # 
    # embed.set_footer(
    # text="💡 Use !last_session for the most recent session with full details"
    # )
    # await ctx.send(embed=embed)
    # 
    # except Exception as e:
    # logger.error(f"Error in session command: {e}", exc_info=True)
    # await ctx.send(f"❌ Error retrieving session: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════
    # NOTE: The massive !last_session command has been refactored into a
    # dedicated Last Session Cog (bot/cogs/last_session_cog.py) with 27
    # helper methods for better maintainability.
    # 
    # Original: 3,316 lines (lines 839-4155) 
    # Refactored: 1,516 lines organized into focused, reusable methods
    # Reduction: 54% smaller with MUCH better organization
    # 
    # The command now lives in: bot/cogs/last_session_cog.py
    # ═══════════════════════════════════════════════════════════════════════
    
    # @commands.command(
    # )
    # # 
    # @commands.command(name="sessions", aliases=["list_sessions", "ls"])
    # async def list_sessions(self, ctx, *, month: str = None):
    # """📅 List all gaming sessions, optionally filtered by month
    # 
    # Usage:
    # - !sessions              → List all sessions (last 20)
    # - !sessions 10           → List sessions from October (current year)
    # - !sessions 2025-10      → List sessions from October 2025
    # - !sessions october      → List sessions from October (current year)
    # - !sessions oct          → Same as above
    # """
    # try:
    # conn = sqlite3.connect(self.bot.db_path)
    # cursor = conn.cursor()
    # 
    # # Build query based on month filter
    # if month:
    # # Handle different month formats
    # month_lower = month.strip().lower()
    # month_names = {
    # "january": "01",
    # "jan": "01",
    # "february": "02",
    # "feb": "02",
    # "march": "03",
    # "mar": "03",
    # "april": "04",
    # "apr": "04",
    # "may": "05",
    # "june": "06",
    # "jun": "06",
    # "july": "07",
    # "jul": "07",
    # "august": "08",
    # "aug": "08",
    # "september": "09",
    # "sep": "09",
    # "october": "10",
    # "oct": "10",
    # "november": "11",
    # "nov": "11",
    # "december": "12",
    # "dec": "12",
    # }
    # 
    # if month_lower in month_names:
    # # Month name provided - use current year
    # from datetime import datetime
    # 
    # current_year = datetime.now().year
    # month_filter = f"{current_year}-{month_names[month_lower]}"
    # elif "-" in month:
    # # Full YYYY-MM format
    # month_filter = month
    # elif month.isdigit() and len(month) <= 2:
    # # Just month number - use current year
    # from datetime import datetime
    # 
    # current_year = datetime.now().year
    # month_filter = f"{current_year}-{int(month):02d}"
    # else:
    # await ctx.send(
    # f"❌ Invalid month format: `{month}`\nUse: `!sessions 10` or `!sessions october`"
    # )
    # conn.close()
    # return
    # 
    # query = """
    # SELECT 
    # DATE(session_date) as date,
    # COUNT(DISTINCT session_id) / 2 as maps,
    # COUNT(DISTINCT session_id) as rounds,
    # COUNT(DISTINCT player_guid) as players,
    # MIN(session_date) as first_round,
    # MAX(session_date) as last_round
    # FROM player_comprehensive_stats
    # WHERE session_date LIKE ?
    # GROUP BY DATE(session_date)
    # ORDER BY date DESC
    # """
    # cursor.execute(query, (f"{month_filter}%",))
    # filter_text = month_filter
    # else:
    # query = """
    # SELECT 
    # DATE(session_date) as date,
    # COUNT(DISTINCT session_id) / 2 as maps,
    # COUNT(DISTINCT session_id) as rounds,
    # COUNT(DISTINCT player_guid) as players,
    # MIN(session_date) as first_round,
    # MAX(session_date) as last_round
    # FROM player_comprehensive_stats
    # GROUP BY DATE(session_date)
    # ORDER BY date DESC
    # LIMIT 20
    # """
    # cursor.execute(query)
    # filter_text = "all time (last 20)"
    # 
    # sessions = cursor.fetchall()
    # conn.close()
    # 
    # if not sessions:
    # await ctx.send(f"❌ No sessions found for {filter_text}")
    # return
    # 
    # # Create embed
    # embed = discord.Embed(
    # title="📅 Gaming Sessions",
    # description=f"Showing sessions from **{filter_text}**",
    # color=discord.Color.blue(),
    # )
    # 
    # session_list = []
    # for date, maps, rounds, players, first, last in sessions:
    # # Calculate duration
    # from datetime import datetime
    # 
    # try:
    # first_dt = datetime.fromisoformat(
    # first.replace("Z", "+00:00") if "Z" in first else first
    # )
    # last_dt = datetime.fromisoformat(
    # last.replace("Z", "+00:00") if "Z" in last else last
    # )
    # duration = last_dt - first_dt
    # hours = duration.total_seconds() / 3600
    # duration_str = f"{hours:.1f}h"
    # except Exception:
    # duration_str = "N/A"
    # 
    # session_list.append(
    # f"**{date}**\n"
    # f"└ {int(maps)} maps • {rounds} rounds • {players} players • {duration_str}"
    # )
    # 
    # # Split into chunks if too long
    # chunk_size = 10
    # for i in range(0, len(session_list), chunk_size):
    # chunk = session_list[i : i + chunk_size]
    # embed.add_field(
    # name=f"Sessions {i+1}-{min(i+chunk_size, len(session_list))}",
    # value="\n\n".join(chunk),
    # inline=False,
    # )
    # 
    # embed.set_footer(
    # text=f"Total: {len(sessions)} sessions • Use !last_session or !session YYYY-MM-DD for details"
    # )
    # 
    # await ctx.send(embed=embed)
    # 
    # except Exception as e:
    # logger.error(f"Error in list_sessions command: {e}", exc_info=True)
    # await ctx.send(f"❌ Error listing sessions: {e}")
    # 
    # @commands.command(name="list_players", aliases=["players", "lp"])
    async def list_players(self, ctx, filter_type: str = None, page: int = 1):
        """
        👥 List all players with pagination

        Usage:
            !list_players              → Show all players (page 1)
            !list_players 2            → Show page 2
            !list_players linked       → Show only linked players
            !list_players unlinked     → Show only unlinked players
            !list_players active       → Show players from last 30 days
            !list_players linked 2     → Show linked players, page 2
        """
        try:
            conn = sqlite3.connect(self.bot.db_path)
            cursor = conn.cursor()

            # Base query to get all players with their link status
            base_query = """
                SELECT 
                    p.player_guid,
                    p.player_name,
                    pl.discord_id,
                    COUNT(DISTINCT p.session_date) as sessions_played,
                    MAX(p.session_date) as last_played,
                    SUM(p.kills) as total_kills,
                    SUM(p.deaths) as total_deaths
                FROM player_comprehensive_stats p
                LEFT JOIN player_links pl ON p.player_guid = pl.et_guid
                GROUP BY p.player_guid, p.player_name, pl.discord_id
            """

            # Handle case where user passed page as first arg (e.g., !lp 2)
            if filter_type and filter_type.isdigit():
                page = int(filter_type)
                filter_type = None

            # Apply filter
            if filter_type:
                filter_lower = filter_type.lower()
                if filter_lower in ["linked", "link"]:
                    base_query += " HAVING pl.discord_id IS NOT NULL"
                elif filter_lower in ["unlinked", "nolink"]:
                    base_query += " HAVING pl.discord_id IS NULL"
                elif filter_lower in ["active", "recent"]:
                    base_query += " HAVING MAX(p.session_date) >= date('now', '-30 days')"

            base_query += " ORDER BY sessions_played DESC, total_kills DESC"

            cursor.execute(base_query)
            players = cursor.fetchall()
            conn.close()

            if not players:
                await ctx.send(
                    f"❌ No players found" + (f" with filter: {filter_type}" if filter_type else "")
                )
                return

            # Count linked vs unlinked
            linked_count = sum(1 for p in players if p[2])
            unlinked_count = len(players) - linked_count

            # Pagination settings
            players_per_page = 15
            total_pages = (len(players) + players_per_page - 1) // players_per_page

            # Validate page number
            if page < 1:
                page = 1
            elif page > total_pages:
                page = total_pages

            start_idx = (page - 1) * players_per_page
            end_idx = min(start_idx + players_per_page, len(players))
            page_players = players[start_idx:end_idx]

            # Create embed
            filter_text = f" - {filter_type.upper()}" if filter_type else ""
            embed = discord.Embed(
                title=f"👥 Players List{filter_text}",
                description=(
                    f"**Total**: {len(players)} players • "
                    f"🔗 {linked_count} linked • ❌ {unlinked_count} unlinked\n"
                    f"**Page {page}/{total_pages}** (showing {start_idx+1}-{end_idx})"
                ),
                color=discord.Color.green(),
            )

            # Format player list (compact single-line per player)
            player_lines = []
            for (
                guid,
                name,
                discord_id,
                sessions,
                last_played,
                kills,
                deaths,
            ) in page_players:
                link_icon = "🔗" if discord_id else "❌"
                kd = kills / deaths if deaths > 0 else kills

                # Format last played date compactly
                try:
                    from datetime import datetime

                    last_date = datetime.fromisoformat(
                        last_played.replace("Z", "+00:00") if "Z" in last_played else last_played
                    )
                    days_ago = (datetime.now() - last_date).days
                    if days_ago == 0:
                        last_str = "today"
                    elif days_ago == 1:
                        last_str = "1d"
                    elif days_ago < 7:
                        last_str = f"{days_ago}d"
                    elif days_ago < 30:
                        last_str = f"{days_ago//7}w"
                    else:
                        last_str = f"{days_ago//30}mo"
                except Exception:
                    last_str = "?"

                player_lines.append(
                    f"{link_icon} **{name[:20]}** • "
                    f"{sessions}s • {kills}K/{deaths}D ({kd:.1f}) • {last_str}"
                )

            embed.add_field(
                name=f"Players {start_idx+1}-{end_idx}",
                value="\n".join(player_lines),
                inline=False,
            )

            # Navigation footer
            nav_text = ""
            if total_pages > 1:
                if page > 1:
                    nav_text += f"⬅️ `!lp {filter_type or ''} {page-1}`.strip() • "
                nav_text += f"Page {page}/{total_pages}"
                if page < total_pages:
                    nav_text += f" • `!lp {filter_type or ''} {page+1}`.strip() ➡️"

            if nav_text:
                embed.set_footer(text=nav_text)
            else:
                embed.set_footer(
                    text="Use !link to link • !list_players [linked|unlinked|active]"
                )

            # Try sending embed; if it fails due to size, fall back to simple text
            try:
                await ctx.send(embed=embed)
            except discord.HTTPException:
                logger.warning("Embed too large for list_players; falling back to simple text output")
                await ctx.send(
                    "⚠️ Embed too large — falling back to plain text output. Use `!lps` for a simpler list."
                )
                await self.list_players_simple(ctx, filter_type)

        except Exception as e:
            logger.error(f"Error in list_players command: {e}", exc_info=True)
            await ctx.send(f"❌ Error listing players: {e}")

    # @commands.command(name="link")
    # async def link(self, ctx, target: str = None, *, guid: str = None):
    # """🔗 Link your Discord account to your in-game profile
    # 
    # Usage:
    # - !link                        → Smart search with top 3 suggestions
    # - !link YourPlayerName         → Search by name
    # - !link GUID                   → Direct link by GUID
    # - !link @user GUID             → Admin: Link another user (requires permissions)
    # """
    # try:
    # # === SCENARIO 0: ADMIN LINKING (@mention + GUID) ===
    # if ctx.message.mentions and guid:
    # await self._admin_link(
    # ctx, ctx.message.mentions[0], guid.upper()
    # )
    # return
    # 
    # # For self-linking
    # discord_id = str(ctx.author.id)
    # 
    # # Check if already linked
    # async with aiosqlite.connect(self.bot.db_path) as db:
    # async with db.execute(
    # """
    # SELECT et_name, et_guid FROM player_links
    # WHERE discord_id = ?
    # """,
    # (discord_id,),
    # ) as cursor:
    # existing = await cursor.fetchone()
    # 
    # if existing:
    # await ctx.send(
    # f"⚠️ You're already linked to **{existing[0]}** (GUID: {existing[1]})\\n"
    # f"Use `!unlink` first to change your linked account."
    # )
    # return
    # 
    # # === SCENARIO 1: NO ARGUMENTS - Smart Self-Linking ===
    # if not target:
    # await self._smart_self_link(ctx, discord_id, db)
    # return
    # 
    # # === SCENARIO 2: GUID Direct Link ===
    # # Check if it's a GUID (8 hex characters)
    # if len(target) == 8 and all(
    # c in "0123456789ABCDEFabcdef" for c in target
    # ):
    # await self._link_by_guid(
    # ctx, discord_id, target.upper(), db
    # )
    # return
    # 
    # # === SCENARIO 3: Name Search ===
    # await self._link_by_name(ctx, discord_id, target, db)
    # 
    # except Exception as e:
    # logger.error(f"Error in link command: {e}", exc_info=True)
    # await ctx.send(f"❌ Error linking account: {e}")
    # 
    # async def _smart_self_link(self, ctx, discord_id: str, db):
    # """Smart self-linking: show top 3 unlinked GUIDs with aliases"""
    # try:
    # # Get top 3 unlinked players by recent activity and total stats
    # async with db.execute(
    # """
    # SELECT 
    # player_guid,
    # MAX(session_date) as last_played,
    # SUM(kills) as total_kills,
    # SUM(deaths) as total_deaths,
    # COUNT(DISTINCT session_id) as games
    # FROM player_comprehensive_stats
    # WHERE player_guid NOT IN (SELECT et_guid FROM player_links WHERE et_guid IS NOT NULL)
    # GROUP BY player_guid
    # ORDER BY last_played DESC, total_kills DESC
    # LIMIT 3
    # """,
    # ) as cursor:
    # top_players = await cursor.fetchall()
    # 
    # if not top_players:
    # await ctx.send(
    # "❌ No available players found!\\n"
    # "All players are already linked or no games recorded."
    # )
    # return
    # 
    # # Build embed with top 3 options
    # embed = discord.Embed(
    # title="🔍 Link Your Account",
    # description=(
    # f"Found **{len(top_players)}** potential matches!\\n"
    # f"React with 1️⃣/2️⃣/3️⃣ or use `!select <number>` within 60 seconds."
    # ),
    # color=0x3498DB,
    # )
    # 
    # options_data = []
    # for idx, (guid, last_date, kills, deaths, games) in enumerate(
    # top_players, 1
    # ):
    # # Get aliases for this GUID (uses 'guid' and 'alias' columns)
    # async with db.execute(
    # """
    # SELECT alias, last_seen, times_seen
    # FROM player_aliases
    # WHERE guid = ?
    # ORDER BY last_seen DESC, times_seen DESC
    # LIMIT 3
    # """,
    # (guid,),
    # ) as cursor:
    # aliases = await cursor.fetchall()
    # 
    # # Format aliases
    # if aliases:
    # primary_name = aliases[0][0]
    # alias_str = ", ".join([a[0] for a in aliases[:3]])
    # if len(aliases) > 3:
    # alias_str += "..."
    # else:
    # # Fallback to most recent name
    # async with db.execute(
    # """
    # SELECT player_name 
    # FROM player_comprehensive_stats 
    # WHERE player_guid = ? 
    # ORDER BY session_date DESC 
    # LIMIT 1
    # """,
    # (guid,),
    # ) as cursor:
    # name_row = await cursor.fetchone()
    # primary_name = name_row[0] if name_row else "Unknown"
    # alias_str = primary_name
    # 
    # kd_ratio = kills / deaths if deaths > 0 else kills
    # 
    # emoji = ["1️⃣", "2️⃣", "3️⃣"][idx - 1]
    # embed.add_field(
    # name=f"{emoji} **{primary_name}**",
    # value=(
    # f"**GUID:** {guid}\\n"
    # f"**Stats:** {kills:,} kills / {deaths:,} deaths / {kd_ratio:.2f} K/D\\n"
    # f"**Games:** {games:,} | **Last Seen:** {last_date}\\n"
    # f"**Also:** {alias_str}"
    # ),
    # inline=False,
    # )
    # 
    # options_data.append(
    # {
    # "guid": guid,
    # "name": primary_name,
    # "kills": kills,
    # "games": games,
    # }
    # )
    # 
    # embed.set_footer(
    # text=f"💡 Tip: Use !link <GUID> to link directly | Requested by {ctx.author.display_name}"
    # )
    # 
    # message = await ctx.send(embed=embed)
    # 
    # # Add reaction emojis
    # emojis = ["1️⃣", "2️⃣", "3️⃣"][: len(top_players)]
    # for emoji in emojis:
    # await message.add_reaction(emoji)
    # 
    # # Wait for reaction
    # def check(reaction, user):
    # return (
    # user == ctx.author
    # and str(reaction.emoji) in emojis
    # and reaction.message.id == message.id
    # )
    # 
    # try:
    # reaction, user = await self.bot.wait_for(
    # "reaction_add", timeout=60.0, check=check
    # )
    # 
    # # Get selected index
    # selected_idx = emojis.index(str(reaction.emoji))
    # selected = options_data[selected_idx]
    # 
    # # Link the account
    # await db.execute(
    # """
    # INSERT OR REPLACE INTO player_links
    # (discord_id, discord_username, et_guid, et_name, linked_date, verified)
    # VALUES (?, ?, ?, ?, datetime('now'), 1)
    # """,
    # (
    # discord_id,
    # str(ctx.author),
    # selected["guid"],
    # selected["name"],
    # ),
    # )
    # await db.commit()
    # 
    # # Success!
    # await message.clear_reactions()
    # success_embed = discord.Embed(
    # title="✅ Account Linked!",
    # description=f"Successfully linked to **{selected['name']}**",
    # color=0x00FF00,
    # )
    # success_embed.add_field(
    # name="Stats Preview",
    # value=f"**Games:** {selected['games']:,}\\n**Kills:** {selected['kills']:,}",
    # inline=True,
    # )
    # success_embed.add_field(
    # name="Quick Access",
    # value="Use `!stats` without arguments to see your stats!",
    # inline=False,
    # )
    # success_embed.set_footer(text=f"GUID: {selected['guid']}")
    # await ctx.send(embed=success_embed)
    # 
    # except asyncio.TimeoutError:
    # await message.clear_reactions()
    # await ctx.send(
    # "⏱️ Link request timed out. Try again with `!link`"
    # )
    # 
    # except Exception as e:
    # logger.error(f"Error in smart self-link: {e}", exc_info=True)
    # await ctx.send(f"❌ Error during self-linking: {e}")
    # 
    # async def _link_by_guid(self, ctx, discord_id: str, guid: str, db):
    # """Direct GUID linking with confirmation"""
    # try:
    # # Check if GUID exists
    # async with db.execute(
    # """
    # SELECT 
    # SUM(kills) as total_kills,
    # SUM(deaths) as total_deaths,
    # COUNT(DISTINCT session_id) as games,
    # MAX(session_date) as last_seen
    # FROM player_comprehensive_stats
    # WHERE player_guid = ?
    # """,
    # (guid,),
    # ) as cursor:
    # stats = await cursor.fetchone()
    # 
    # if not stats or stats[0] is None:
    # await ctx.send(f"❌ GUID `{guid}` not found in database.")
    # return
    # 
    # # Get aliases (uses 'guid', 'alias', 'times_seen' columns)
    # async with db.execute(
    # """
    # SELECT alias, last_seen, times_seen
    # FROM player_aliases
    # WHERE guid = ?
    # ORDER BY last_seen DESC, times_seen DESC
    # LIMIT 3
    # """,
    # (guid,),
    # ) as cursor:
    # aliases = await cursor.fetchall()
    # 
    # if aliases:
    # primary_name = aliases[0][0]
    # alias_str = ", ".join([a[0] for a in aliases[:3]])
    # else:
    # # Fallback
    # async with db.execute(
    # """
    # SELECT player_name 
    # FROM player_comprehensive_stats 
    # WHERE player_guid = ? 
    # ORDER BY session_date DESC 
    # LIMIT 1
    # """,
    # (guid,),
    # ) as cursor:
    # name_row = await cursor.fetchone()
    # primary_name = name_row[0] if name_row else "Unknown"
    # alias_str = primary_name
    # 
    # kills, deaths, games, last_seen = stats
    # kd_ratio = kills / deaths if deaths > 0 else kills
    # 
    # # Confirmation embed
    # embed = discord.Embed(
    # title="🔗 Confirm Account Link",
    # description=f"Link your Discord to **{primary_name}**?",
    # color=0xFFA500,
    # )
    # embed.add_field(
    # name="GUID",
    # value=guid,
    # inline=False,
    # )
    # embed.add_field(
    # name="Known Names",
    # value=alias_str,
    # inline=False,
    # )
    # embed.add_field(
    # name="Stats",
    # value=f"{kills:,} kills / {deaths:,} deaths / {kd_ratio:.2f} K/D",
    # inline=True,
    # )
    # embed.add_field(
    # name="Activity",
    # value=f"{games:,} games | Last: {last_seen}",
    # inline=True,
    # )
    # embed.set_footer(text="React ✅ to confirm or ❌ to cancel (60s)")
    # 
    # message = await ctx.send(embed=embed)
    # await message.add_reaction("✅")
    # await message.add_reaction("❌")
    # 
    # def check(reaction, user):
    # return (
    # user == ctx.author
    # and str(reaction.emoji) in ["✅", "❌"]
    # and reaction.message.id == message.id
    # )
    # 
    # try:
    # reaction, user = await self.bot.wait_for(
    # "reaction_add", timeout=60.0, check=check
    # )
    # 
    # if str(reaction.emoji) == "✅":
    # # Confirmed - link it
    # await db.execute(
    # """
    # INSERT OR REPLACE INTO player_links
    # (discord_id, discord_username, et_guid, et_name, linked_date, verified)
    # VALUES (?, ?, ?, ?, datetime('now'), 1)
    # """,
    # (discord_id, str(ctx.author), guid, primary_name),
    # )
    # await db.commit()
    # 
    # await message.clear_reactions()
    # await ctx.send(
    # f"✅ Successfully linked to **{primary_name}** (GUID: {guid})"
    # )
    # else:
    # await message.clear_reactions()
    # await ctx.send("❌ Link cancelled.")
    # 
    # except asyncio.TimeoutError:
    # await message.clear_reactions()
    # await ctx.send("⏱️ Confirmation timed out.")
    # 
    # except Exception as e:
    # logger.error(f"Error in GUID link: {e}", exc_info=True)
    # await ctx.send(f"❌ Error linking by GUID: {e}")
    # 
    # async def _link_by_name(self, ctx, discord_id: str, player_name: str, db):
    # """Name search linking (existing functionality enhanced)"""
    # try:
    # # Search in player_aliases first (uses 'guid' and 'alias' columns)
    # async with db.execute(
    # """
    # SELECT DISTINCT pa.guid
    # FROM player_aliases pa
    # WHERE LOWER(pa.alias) LIKE LOWER(?)
    # ORDER BY pa.last_seen DESC
    # LIMIT 5
    # """,
    # (f"%{player_name}%",),
    # ) as cursor:
    # alias_guids = [row[0] for row in await cursor.fetchall()]
    # 
    # # Also search main stats table
    # async with db.execute(
    # """
    # SELECT player_guid, player_name,
    # SUM(kills) as total_kills,
    # COUNT(DISTINCT session_id) as games,
    # MAX(session_date) as last_seen
    # FROM player_comprehensive_stats
    # WHERE LOWER(player_name) LIKE LOWER(?)
    # GROUP BY player_guid
    # ORDER BY last_seen DESC, games DESC
    # LIMIT 5
    # """,
    # (f"%{player_name}%",),
    # ) as cursor:
    # matches = await cursor.fetchall()
    # 
    # # Combine and deduplicate
    # guid_set = set(alias_guids)
    # for match in matches:
    # guid_set.add(match[0])
    # 
    # if not guid_set:
    # await ctx.send(
    # f"❌ No player found matching '{player_name}'\\n"
    # f"💡 Try: `!link` (no arguments) to see all available players"
    # )
    # return
    # 
    # # Get full data for found GUIDs
    # guid_list = list(guid_set)[:3]  # Limit to 3
    # 
    # if len(guid_list) == 1:
    # # Single match - link directly with confirmation
    # await self._link_by_guid(ctx, discord_id, guid_list[0], db)
    # else:
    # # Multiple matches - show options (similar to smart self-link)
    # embed = discord.Embed(
    # title=f"🔍 Multiple Matches for '{player_name}'",
    # description="React with 1️⃣/2️⃣/3️⃣ to select:",
    # color=0x3498DB,
    # )
    # 
    # options_data = []
    # for idx, guid in enumerate(guid_list, 1):
    # # Get stats and aliases
    # async with db.execute(
    # """
    # SELECT SUM(kills), SUM(deaths), COUNT(DISTINCT session_id), MAX(session_date)
    # FROM player_comprehensive_stats
    # WHERE player_guid = ?
    # """,
    # (guid,),
    # ) as cursor:
    # stats = await cursor.fetchone()
    # 
    # async with db.execute(
    # """
    # SELECT alias FROM player_aliases
    # WHERE guid = ?
    # ORDER BY last_seen DESC LIMIT 1
    # """,
    # (guid,),
    # ) as cursor:
    # name_row = await cursor.fetchone()
    # name = name_row[0] if name_row else "Unknown"
    # 
    # kills, deaths, games, last_seen = stats
    # kd = kills / deaths if deaths > 0 else kills
    # 
    # emoji = ["1️⃣", "2️⃣", "3️⃣"][idx - 1]
    # embed.add_field(
    # name=f"{emoji} **{name}**",
    # value=(
    # f"**GUID:** {guid}\\n{kills:,} kills | **K/D: {kd:.2f}** | "
    # f"{games:,} games | Last: {last_seen}"
    # ),
    # inline=False,
    # )
    # 
    # options_data.append(
    # {
    # "guid": guid,
    # "name": name,
    # "kills": kills,
    # "games": games,
    # }
    # )
    # 
    # message = await ctx.send(embed=embed)
    # 
    # emojis = ["1️⃣", "2️⃣", "3️⃣"][: len(guid_list)]
    # for emoji in emojis:
    # await message.add_reaction(emoji)
    # 
    # def check(reaction, user):
    # return (
    # user == ctx.author
    # and str(reaction.emoji) in emojis
    # and reaction.message.id == message.id
    # )
    # 
    # try:
    # reaction, user = await self.bot.wait_for(
    # "reaction_add", timeout=60.0, check=check
    # )
    # selected_idx = emojis.index(str(reaction.emoji))
    # selected = options_data[selected_idx]
    # 
    # await db.execute(
    # """
    # INSERT OR REPLACE INTO player_links
    # (discord_id, discord_username, et_guid, et_name, linked_date, verified)
    # VALUES (?, ?, ?, ?, datetime('now'), 1)
    # """,
    # (
    # discord_id,
    # str(ctx.author),
    # selected["guid"],
    # selected["name"],
    # ),
    # )
    # await db.commit()
    # 
    # await message.clear_reactions()
    # await ctx.send(
    # f"✅ Successfully linked to **{selected['name']}** (GUID: {selected['guid']})"
    # )
    # 
    # except asyncio.TimeoutError:
    # await message.clear_reactions()
    # await ctx.send("⏱️ Selection timed out.")
    # 
    # except Exception as e:
    # logger.error(f"Error in name link: {e}", exc_info=True)
    # await ctx.send(f"❌ Error linking by name: {e}")
    # 
    # async def _admin_link(self, ctx, target_user: discord.User, guid: str):
    # """Admin linking: Link another user's Discord to a GUID"""
    # try:
    # # Check permissions
    # if not ctx.author.guild_permissions.manage_guild:
    # await ctx.send(
    # "❌ You don't have permission to link other users.\\n"
    # "**Required:** Manage Server permission"
    # )
    # logger.warning(
    # f"Unauthorized admin link attempt by {ctx.author} "
    # f"(ID: {ctx.author.id})"
    # )
    # return
    # 
    # # Validate GUID format (8 hex characters)
    # if len(guid) != 8 or not all(
    # c in "0123456789ABCDEFabcdef" for c in guid
    # ):
    # await ctx.send(
    # f"❌ Invalid GUID format: `{guid}`\\n"
    # f"**GUIDs must be exactly 8 hexadecimal characters** (e.g., `D8423F90`)\\n\\n"
    # f"💡 To link by player name instead:\\n"
    # f"   • Ask {target_user.mention} to use `!link {guid}` (searches by name)\\n"
    # f"   • Or use `!stats {guid}` to find their GUID first"
    # )
    # return
    # 
    # target_discord_id = str(target_user.id)
    # 
    # async with aiosqlite.connect(self.bot.db_path) as db:
    # # Check if target already linked
    # async with db.execute(
    # """
    # SELECT et_name, et_guid FROM player_links
    # WHERE discord_id = ?
    # """,
    # (target_discord_id,),
    # ) as cursor:
    # existing = await cursor.fetchone()
    # 
    # if existing:
    # await ctx.send(
    # f"⚠️ {target_user.mention} is already linked to "
    # f"**{existing[0]}** (GUID: {existing[1]})\\n"
    # f"They need to `!unlink` first, or you can overwrite "
    # f"with force (react ⚠️ to confirm)."
    # )
    # # For now, just block. Future: Add force option
    # return
    # 
    # # Validate GUID exists
    # async with db.execute(
    # """
    # SELECT 
    # SUM(kills) as total_kills,
    # SUM(deaths) as total_deaths,
    # COUNT(DISTINCT session_id) as games,
    # MAX(session_date) as last_seen
    # FROM player_comprehensive_stats
    # WHERE player_guid = ?
    # """,
    # (guid,),
    # ) as cursor:
    # stats = await cursor.fetchone()
    # 
    # if not stats or stats[0] is None:
    # await ctx.send(
    # f"❌ GUID `{guid}` not found in database.\\n"
    # f"💡 Use `!link` (no args) to see available players."
    # )
    # return
    # 
    # # Get aliases (uses 'guid', 'alias', 'times_seen' columns)
    # async with db.execute(
    # """
    # SELECT alias, last_seen, times_seen
    # FROM player_aliases
    # WHERE guid = ?
    # ORDER BY last_seen DESC, times_seen DESC
    # LIMIT 3
    # """,
    # (guid,),
    # ) as cursor:
    # aliases = await cursor.fetchall()
    # 
    # if aliases:
    # primary_name = aliases[0][0]
    # alias_str = ", ".join([a[0] for a in aliases[:3]])
    # else:
    # # Fallback
    # async with db.execute(
    # """
    # SELECT player_name 
    # FROM player_comprehensive_stats 
    # WHERE player_guid = ? 
    # ORDER BY session_date DESC 
    # LIMIT 1
    # """,
    # (guid,),
    # ) as cursor:
    # name_row = await cursor.fetchone()
    # primary_name = name_row[0] if name_row else "Unknown"
    # alias_str = primary_name
    # 
    # kills, deaths, games, last_seen = stats
    # kd_ratio = kills / deaths if deaths > 0 else kills
    # 
    # # Admin confirmation embed
    # embed = discord.Embed(
    # title="🔗 Admin Link Confirmation",
    # description=(
    # f"Link {target_user.mention} to **{primary_name}**?\\n\\n"
    # f"**Requested by:** {ctx.author.mention}"
    # ),
    # color=0xFF6B00,  # Orange for admin action
    # )
    # embed.add_field(
    # name="Target User",
    # value=f"{target_user.mention} ({target_user.name})",
    # inline=True,
    # )
    # embed.add_field(
    # name="GUID",
    # value=guid,
    # inline=True,
    # )
    # embed.add_field(
    # name="Known Names",
    # value=alias_str,
    # inline=False,
    # )
    # embed.add_field(
    # name="Stats",
    # value=(
    # f"**Kills:** {kills:,} | **Deaths:** {deaths:,}\\n"
    # f"**K/D:** {kd_ratio:.2f} | **Games:** {games:,}"
    # ),
    # inline=True,
    # )
    # embed.add_field(
    # name="Last Seen",
    # value=last_seen,
    # inline=True,
    # )
    # embed.set_footer(
    # text="React ✅ (admin) to confirm or ❌ to cancel (60s)"
    # )
    # 
    # message = await ctx.send(embed=embed)
    # await message.add_reaction("✅")
    # await message.add_reaction("❌")
    # 
    # def check(reaction, user):
    # return (
    # user == ctx.author  # Only admin can confirm
    # and str(reaction.emoji) in ["✅", "❌"]
    # and reaction.message.id == message.id
    # )
    # 
    # try:
    # reaction, user = await self.bot.wait_for(
    # "reaction_add", timeout=60.0, check=check
    # )
    # 
    # if str(reaction.emoji) == "✅":
    # # Confirmed - link it
    # await db.execute(
    # """
    # INSERT OR REPLACE INTO player_links
    # (discord_id, discord_username, et_guid, et_name, 
    # linked_date, verified)
    # VALUES (?, ?, ?, ?, datetime('now'), 1)
    # """,
    # (
    # target_discord_id,
    # str(target_user),
    # guid,
    # primary_name,
    # ),
    # )
    # await db.commit()
    # 
    # await message.clear_reactions()
    # 
    # # Success message
    # success_embed = discord.Embed(
    # title="✅ Admin Link Successful",
    # description=(
    # f"{target_user.mention} is now linked to "
    # f"**{primary_name}**"
    # ),
    # color=0x00FF00,
    # )
    # success_embed.add_field(
    # name="GUID",
    # value=guid,
    # inline=True,
    # )
    # success_embed.add_field(
    # name="Linked By",
    # value=ctx.author.mention,
    # inline=True,
    # )
    # success_embed.set_footer(
    # text=(
    # f"💡 {target_user.name} can now use "
    # f"!stats to see their stats"
    # )
    # )
    # 
    # await ctx.send(embed=success_embed)
    # 
    # # Log admin action
    # logger.info(
    # f"Admin link: {ctx.author} (ID: {ctx.author.id}) "
    # f"linked {target_user} (ID: {target_user.id}) "
    # f"to GUID {guid} ({primary_name})"
    # )
    # 
    # else:
    # await message.clear_reactions()
    # await ctx.send("❌ Admin link cancelled.")
    # 
    # except asyncio.TimeoutError:
    # await message.clear_reactions()
    # await ctx.send("⏱️ Admin link confirmation timed out.")
    # 
    # except Exception as e:
    # logger.error(f"Error in admin link: {e}", exc_info=True)
    # await ctx.send(f"❌ Error during admin linking: {e}")
    # 
    # @commands.command(name="unlink")
    # async def unlink(self, ctx):
    # """🔓 Unlink your Discord account from your in-game profile"""
    # try:
    # discord_id = str(ctx.author.id)
    # 
    # async with aiosqlite.connect(self.bot.db_path) as db:
    # # Check if linked
    # async with db.execute(
    # """
    # SELECT player_name FROM player_links
    # WHERE discord_id = ?
    # """,
    # (discord_id,),
    # ) as cursor:
    # existing = await cursor.fetchone()
    # 
    # if not existing:
    # await ctx.send("❌ You don't have a linked account.")
    # return
    # 
    # # Remove link
    # await db.execute(
    # """
    # UPDATE player_links
    # SET discord_id = NULL
    # WHERE discord_id = ?
    # """,
    # (discord_id,),
    # )
    # 
    # await db.commit()
    # 
    # await ctx.send(f"✅ Unlinked from **{existing[0]}**")
    # 
    # except Exception as e:
    # logger.error(f"Error in unlink command: {e}", exc_info=True)
    # await ctx.send(f"❌ Error unlinking account: {e}")
    # 
    # @commands.command(name="select")
    # async def select_option(self, ctx, selection: int = None):
    # """🔢 Select an option from a link prompt (alternative to reactions)
    # 
    # Usage: !select <1-3>
    # 
    # Note: This works as an alternative to clicking reaction emojis.
    # Must be used within 60 seconds of a !link command.
    # """
    # if selection is None:
    # await ctx.send(
    # "❌ Please specify a number!\\n"
    # "Usage: `!select 1`, `!select 2`, or `!select 3`"
    # )
    # return
    # 
    # if selection not in [1, 2, 3]:
    # await ctx.send("❌ Please select 1, 2, or 3.")
    # return
    # 
    # await ctx.send(
    # f"💡 You selected option **{selection}**!\\n\\n"
    # f"**Note:** The `!select` command currently requires integration with the link workflow.\\n"
    # f"For now, please use the reaction emojis (1️⃣/2️⃣/3️⃣) on the link message, "
    # f"or use `!link <GUID>` to link directly.\\n\\n"
    # f"**Tip:** To find your GUID, use `!link` (no arguments) and check the GUID field."
    # )
    # 
    # # TODO: Implement persistent selection state
    # # This would require storing pending link requests per user
    # # and checking if they have an active selection window
    # 
    # async def get_hardcoded_teams(self, db, session_date):
    # """🎯 Get hardcoded teams from session_teams table if available
    # 
    # Returns dict with team info or None if not available:
    # {
    # 'Team A': {
    # 'guids': ['GUID1', 'GUID2', ...],
    # 'names': ['Name1', 'Name2', ...],
    # 'maps': ['map1', 'map2', ...]
    # },
    # 'Team B': { ... }
    # }
    # """
    # try:
    # import json
    # 
    # # Check if session_teams table exists
    # async with db.execute(
    # "SELECT name FROM sqlite_master WHERE type='table' AND name='session_teams'"
    # ) as cursor:
    # if not await cursor.fetchone():
    # return None
    # 
    # # Get all teams for this session date
    # async with db.execute(
    # """
    # SELECT team_name, player_guids, player_names, map_name
    # FROM session_teams
    # WHERE session_start_date LIKE ?
    # ORDER BY team_name
    # """,
    # (f"{session_date}%",),
    # ) as cursor:
    # rows = await cursor.fetchall()

            if not rows:
                return None

            # Organize by team name
            teams = {}
            for team_name, guids_json, names_json, map_name in rows:
                if team_name not in teams:
                    teams[team_name] = {
                        "guids": set(json.loads(guids_json)),
                        "names": set(json.loads(names_json)),
                        "maps": [],
                    }
                teams[team_name]["maps"].append(map_name)

            # Convert sets to sorted lists for consistency
            for team_name in teams:
                teams[team_name]["guids"] = sorted(
                    list(teams[team_name]["guids"])
                )
                teams[team_name]["names"] = sorted(
                    list(teams[team_name]["names"])
                )

            logger.info(
                f"✅ Found hardcoded teams for {session_date}: {list(teams.keys())}"
            )
            return teams

        except Exception as e:
            logger.error(f"Error getting hardcoded teams: {e}", exc_info=True)
            return None


    async def _detect_and_store_persistent_teams(self, db, session_date):
        """Auto-detect persistent teams for a session date and store in session_teams.

        Heuristic:
        - Seed teams from Round 1 game teams (team 1 vs team 2).
        - For players not in Round 1, assign to the team they most frequently shared a game-team with.
        """
        import json

        await self._ensure_session_teams_table(db)

        # Seed from Round 1
        async with db.execute(
            """
            SELECT player_guid, team
            FROM player_comprehensive_stats
            WHERE substr(session_date,1,10)=? AND round_number=1
            """,
            (session_date,),
        ) as cur:
            r1 = await cur.fetchall()

        team1_seed = {g for g, t in r1 if t == 1}
        team2_seed = {g for g, t in r1 if t == 2}

        # If no round1 data (edge case), seed from first available round
        if not team1_seed and not team2_seed:
            async with db.execute(
                """
                SELECT round_number FROM player_comprehensive_stats
                WHERE substr(session_date,1,10)=?
                ORDER BY round_number ASC LIMIT 1
                """,
                (session_date,),
            ) as cur:
                first_round = await cur.fetchone()
            if first_round:
                fr = first_round[0]
                async with db.execute(
                    """
                    SELECT player_guid, team
                    FROM player_comprehensive_stats
                    WHERE substr(session_date,1,10)=? AND round_number=?
                    """,
                    (session_date, fr),
                ) as cur:
                    rows = await cur.fetchall()
                team1_seed = {g for g, t in rows if t == 1}
                team2_seed = {g for g, t in rows if t == 2}

        # Collect all players this session
        async with db.execute(
            """
            SELECT DISTINCT player_guid FROM player_comprehensive_stats
            WHERE substr(session_date,1,10)=?
            """,
            (session_date,),
        ) as cur:
            all_players = {row[0] for row in (await cur.fetchall())}

        assigned = {}
        for g in team1_seed:
            assigned[g] = 1
        for g in team2_seed:
            assigned[g] = 2

        # For unseeded players, assign by co-membership with seeds
        unassigned = [g for g in all_players if g not in assigned]
        if unassigned and (team1_seed or team2_seed):
            # Build map of round -> sets of game-team members
            async with db.execute(
                """
                SELECT round_number, player_guid, team
                FROM player_comprehensive_stats
                WHERE substr(session_date,1,10)=?
                ORDER BY round_number
                """,
                (session_date,),
            ) as cur:
                rows = await cur.fetchall()

            from collections import defaultdict

            round_team_members = defaultdict(lambda: {1: set(), 2: set()})
            for rnd, guid, team in rows:
                if team in (1, 2):
                    round_team_members[rnd][team].add(guid)

            for guid in unassigned:
                votes = {1: 0, 2: 0}
                for rnd, teams in round_team_members.items():
                    if guid in teams[1] or guid in teams[2]:
                        # if shares game team with many seeds, vote for that persistent team
                        if guid in teams[1]:
                            votes[1] += len(teams[1] & team1_seed)
                            votes[2] += len(teams[1] & team2_seed)
                        elif guid in teams[2]:
                            votes[1] += len(teams[2] & team1_seed)
                            votes[2] += len(teams[2] & team2_seed)
                if votes[1] > votes[2]:
                    assigned[guid] = 1
                    team1_seed.add(guid)
                elif votes[2] > votes[1]:
                    assigned[guid] = 2
                    team2_seed.add(guid)
                # if tie, leave unassigned for now (ignored)

        # Resolve names for output
        async with db.execute(
            """
            SELECT guid, alias
            FROM player_aliases
            WHERE guid IN ({qs})
            AND last_seen = (
                SELECT MAX(last_seen) FROM player_aliases pa2 WHERE pa2.guid = player_aliases.guid
            )
            """.format(qs=",".join("?" * max(1, len(all_players)))),
            tuple(all_players) if all_players else ("",),
        ) as cur:
            alias_rows = await cur.fetchall()
        latest_alias = {}
        for g, a in alias_rows:
            latest_alias[g] = a

        # Write two rows into session_teams with map_name='ALL'
        guids1 = sorted(list(team1_seed))
        guids2 = sorted(list(team2_seed))
        names1 = sorted([latest_alias.get(g, g) for g in guids1])
        names2 = sorted([latest_alias.get(g, g) for g in guids2])

        # If nothing detected, skip
        if not guids1 and not guids2:
            return False

        cursor = await db.execute(
            """
            INSERT INTO session_teams (session_start_date, map_name, team_name, player_guids, player_names)
            VALUES (?, 'ALL', 'Team A', ?, ?)
            ON CONFLICT(session_start_date, map_name, team_name)
            DO UPDATE SET player_guids=excluded.player_guids, player_names=excluded.player_names
            """,
            (session_date, json.dumps(guids1), json.dumps(names1)),
        )
        cursor = await db.execute(
            """
            INSERT INTO session_teams (session_start_date, map_name, team_name, player_guids, player_names)
            VALUES (?, 'ALL', 'Team B', ?, ?)
            ON CONFLICT(session_start_date, map_name, team_name)
            DO UPDATE SET player_guids=excluded.player_guids, player_names=excluded.player_names
            """,
            (session_date, json.dumps(guids2), json.dumps(names2)),
        )
        await db.commit()
        
        # Update team history tracking
        await self._update_team_history(db, session_date, guids1, guids2, names1, names2)
        
        return True

    async def _update_team_history(self, db, session_date, team1_guids, team2_guids, team1_names, team2_names):
        """
        Update team_lineups and session_results tables for historical tracking.
        
        Args:
            db: Database connection
            session_date: Session date (YYYY-MM-DD)
            team1_guids: List of GUIDs for Team A
            team2_guids: List of GUIDs for Team B
            team1_names: List of names for Team A
            team2_names: List of names for Team B
        """
        import hashlib
        import json
        
        def calculate_lineup_hash(guids):
            sorted_guids = sorted(guids)
            guid_string = ",".join(sorted_guids)
            return hashlib.sha256(guid_string.encode()).hexdigest()[:16]
        
        # Calculate lineup hashes
        team1_hash = calculate_lineup_hash(team1_guids)
        team2_hash = calculate_lineup_hash(team2_guids)
        
        # Get or create lineup records
        for lineup_hash, guids in [(team1_hash, team1_guids), (team2_hash, team2_guids)]:
            async with db.execute(
                "SELECT id, first_seen, last_seen FROM team_lineups WHERE lineup_hash = ?",
                (lineup_hash,)
            ) as cur:
                row = await cur.fetchone()
            
            if row:
                lineup_id, first_seen, last_seen = row
                if session_date > last_seen:
                    await db.execute(
                        """
                        UPDATE team_lineups 
                        SET last_seen = ?, 
                            total_sessions = total_sessions + 1,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (session_date, lineup_id)
                    )
            else:
                await db.execute(
                    """
                    INSERT INTO team_lineups 
                    (lineup_hash, player_guids, player_count, first_seen, last_seen)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (lineup_hash, json.dumps(sorted(guids)), len(guids), session_date, session_date)
                )
        
        await db.commit()
        logger.debug(f"✅ Updated team history for {session_date}")

    async def _ensure_session_teams_table(self, db):
        """Ensure session_teams table exists with expected columns."""
        # Use executescript for DDL statements. executescript handles
        # multiple statements and ensures they're executed/committed
        # correctly with aiosqlite (avoids _CursorWrapper await issues).
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS session_teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_start_date TEXT NOT NULL,
                map_name TEXT NOT NULL,
                team_name TEXT NOT NULL,
                player_guids TEXT NOT NULL,
                player_names TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(session_start_date, map_name, team_name)
            );

            CREATE INDEX IF NOT EXISTS idx_session_teams_date ON session_teams(session_start_date);
            CREATE INDEX IF NOT EXISTS idx_session_teams_map ON session_teams(map_name);
            """
        )
    # @commands.command(name="set_teams")
    # async def set_teams(self, ctx, team1_name: str, team2_name: str):
    # """Manually set persistent team names for the latest session date."""
    # try:
    # import json
    # async with aiosqlite.connect(self.bot.db_path) as db:
    # await self._ensure_session_teams_table(db)
    # 
    # # Determine latest session date (YYYY-MM-DD)
    # async with db.execute(
    # "SELECT DISTINCT substr(session_date,1,10) as d FROM sessions ORDER BY d DESC LIMIT 1"
    # ) as cur:
    # row = await cur.fetchone()
    # if not row:
    # await ctx.send("❌ No sessions found to set teams for.")
    # return
    # session_date = row[0]
    # 
    # # Upsert two team rows with map_name='ALL' and empty rosters initially
    # empty = json.dumps([])
    # for tname in (team1_name, team2_name):
    # await db.execute(
    # """
    # INSERT INTO session_teams (session_start_date, map_name, team_name, player_guids, player_names)
    # VALUES (?, 'ALL', ?, ?, ?)
    # ON CONFLICT(session_start_date, map_name, team_name)
    # DO UPDATE SET team_name=excluded.team_name
    # """,
    # (session_date, tname, empty, empty),
    # )
    # await db.commit()
    # await ctx.send(f"✅ Teams set for {session_date}: **{team1_name}** vs **{team2_name}**")
    # except Exception as e:
    # logger.error(f"Error in set_teams: {e}", exc_info=True)
    # await ctx.send(f"❌ Error setting teams: {e}")
    # 
    # @commands.command(name="assign_player")
    # async def assign_player(self, ctx, player_name: str, team_name: str):
    # """Assign a player (by name) to a persistent team for the latest session date."""
    # try:
    # import json
    # async with aiosqlite.connect(self.bot.db_path) as db:
    # await self._ensure_session_teams_table(db)
    # 
    # # Resolve latest session date
    # async with db.execute(
    # "SELECT DISTINCT substr(session_date,1,10) as d FROM sessions ORDER BY d DESC LIMIT 1"
    # ) as cur:
    # row = await cur.fetchone()
    # if not row:
    # await ctx.send("❌ No sessions found.")
    # return
    # session_date = row[0]
    # 
    # # Resolve most recent GUID for the player (fuzzy match by alias)
    # async with db.execute(
    # """
    # SELECT guid, alias
    # FROM player_aliases
    # WHERE lower(alias) LIKE lower(?)
    # ORDER BY last_seen DESC
    # LIMIT 1
    # """,
    # (f"%{player_name}%",),
    # ) as cur:
    # pa = await cur.fetchone()
    # if not pa:
    # await ctx.send(f"❌ Player '{player_name}' not found in aliases.")
    # return
    # player_guid, resolved_alias = pa
    # 
    # # Ensure team row exists for this date (map_name='ALL')
    # empty = json.dumps([])
    # await db.execute(
    # """
    # INSERT INTO session_teams (session_start_date, map_name, team_name, player_guids, player_names)
    # VALUES (?, 'ALL', ?, ?, ?)
    # ON CONFLICT(session_start_date, map_name, team_name)
    # DO NOTHING
    # """,
    # (session_date, team_name, empty, empty),
    # )
    # 
    # # Fetch current roster
    # async with db.execute(
    # """
    # SELECT player_guids, player_names
    # FROM session_teams
    # WHERE session_start_date = ? AND map_name = 'ALL' AND team_name = ?
    # """,
    # (session_date, team_name),
    # ) as cur:
    # row = await cur.fetchone()
    # 
    # if not row:
    # await ctx.send(
    # f"❌ Team '{team_name}' not found for {session_date}. Use !set_teams first."
    # )
    # return
    # 
    # guids = set(json.loads(row[0] or "[]"))
    # names = set(json.loads(row[1] or "[]"))
    # updated = False
    # if player_guid not in guids:
    # guids.add(player_guid)
    # updated = True
    # if resolved_alias not in names:
    # names.add(resolved_alias)
    # updated = True
    # 
    # if updated:
    # await db.execute(
    # """
    # UPDATE session_teams
    # SET player_guids = ?, player_names = ?
    # WHERE session_start_date = ? AND map_name = 'ALL' AND team_name = ?
    # """,
    # (json.dumps(sorted(list(guids))), json.dumps(sorted(list(names))), session_date, team_name),
    # )
    # await db.commit()
    # 
    # await ctx.send(
    # f"✅ Assigned **{resolved_alias}** to **{team_name}** for {session_date}"
    # )
    # except Exception as e:
    # logger.error(f"Error in assign_player: {e}", exc_info=True)
    # await ctx.send(f"❌ Error assigning player: {e}")

    # ============================================================================
    # MOVED TO TEAM MANAGEMENT COG (bot/cogs/team_management_cog.py)
    # Commands: set_teams, assign_player
    # ============================================================================

class UltimateETLegacyBot(commands.Bot):
    """🚀 Ultimate consolidated ET:Legacy Discord bot with proper Cog structure"""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

        # 📊 Database Configuration - Try multiple locations
        import os

        bot_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(bot_dir)

        # ✅ Try multiple database locations
        # Prefer the DB inside the bot directory by default (local dev copy)
        possible_paths = [
            os.path.join(
                bot_dir, "etlegacy_production.db"
            ),  # Bot directory (preferred)
            os.path.join(parent_dir, "etlegacy_production.db"),  # Project root
            "etlegacy_production.db",  # Current dir
        ]

        # Allow explicit override via environment variable.
        # By default prefer the bot-local DB if it exists. To force the env
        # override, set ETLEGACY_DB_FORCE=true in the environment.
        env_db = os.getenv("ETLEGACY_DB_PATH") or os.getenv("DB_PATH")
        force_override = (
            os.getenv("ETLEGACY_DB_FORCE", "false").lower() == "true"
        )
        bot_db = os.path.join(bot_dir, "etlegacy_production.db")

        if env_db:
            # Expand user and make absolute for clarity
            env_db = os.path.abspath(os.path.expanduser(env_db))
            # If force flag set, honor env var; otherwise prefer local bot DB when present
            if force_override:
                logger.info(
                    f"🔧 DB override provided via env and forced: {env_db} (will be preferred)"
                )
                if env_db not in possible_paths:
                    possible_paths.insert(0, env_db)
            else:
                # If the bot-local DB exists, prefer it and keep env_db as fallback
                if os.path.exists(bot_db):
                    logger.warning(
                        f"⚠️ ETLEGACY_DB_PATH is set to {env_db} but a local bot DB was found at {bot_db}."
                        " Using the local bot DB by default. To force the env path set ETLEGACY_DB_FORCE=true."
                    )
                    # Ensure bot_db is first (possible_paths already has bot_db first by default)
                    if possible_paths[0] != bot_db:
                        # Remove bot_db if it appears later and put it first
                        try:
                            possible_paths.remove(bot_db)
                        except ValueError:
                            pass
                        possible_paths.insert(0, bot_db)
                    # Add env_db as a fallback if it's not already listed
                    if env_db not in possible_paths:
                        possible_paths.append(env_db)
                else:
                    # No local bot DB found - fall back to env_db
                    logger.info(
                        f"🔧 ETLEGACY_DB_PATH provided: {env_db} (no local bot DB found)"
                    )
                    if env_db not in possible_paths:
                        possible_paths.insert(0, env_db)

        self.db_path = None
        for path in possible_paths:
            if os.path.exists(path):
                self.db_path = path
                logger.info(f"✅ Database found: {path}")
                break

        if not self.db_path:
            error_msg = (
                f"❌ DATABASE NOT FOUND!\n"
                f"Tried: {possible_paths}\n"
                f"Run: python create_unified_database.py"
            )
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        # 🎮 Bot State
        self.current_session = None
        self.processed_files = set()
        self.auto_link_enabled = True
        self.gather_queue = {"3v3": [], "6v6": []}

        # 📊 Core Systems (for Cogs)
        self.stats_cache = StatsCache(ttl_seconds=300)
        self.season_manager = SeasonManager()
        self.achievements = AchievementSystem(self)
        logger.info("✅ Core systems initialized (cache, seasons, achievements)")

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
        self.gaming_sessions_db_id = None  # Link to gaming_sessions table

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

    async def validate_database_schema(self):
        """
        ✅ CRITICAL: Validate database has correct unified schema (53 columns)
        Prevents silent failures if wrong schema is used
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Ensure player_name alias for this connection (non-Cog helper)
                try:
                    await ensure_player_name_alias(db)
                except Exception:
                    pass
                # Check player_comprehensive_stats has 53 columns
                cursor = await db.execute(
                    "PRAGMA table_info(player_comprehensive_stats)"
                )
                columns = await cursor.fetchall()

                expected_columns = 53
                actual_columns = len(columns)

                if actual_columns != expected_columns:
                    error_msg = (
                        f"❌ DATABASE SCHEMA MISMATCH!\n"
                        f"Expected: {expected_columns} columns (UNIFIED)\n"
                        f"Found: {actual_columns} columns\n\n"
                        f"Schema: {'SPLIT (deprecated)' if actual_columns == 35 else 'UNKNOWN'}\n\n"
                        f"Solution:\n"
                        f"1. Backup: cp etlegacy_production.db backup.db\n"
                        f"2. Create: python create_unified_database.py\n"
                        f"3. Import: python tools/simple_bulk_import.py local_stats/*.txt\n"
                    )

                    logger.error(error_msg)
                    raise RuntimeError(error_msg)

                # Verify objective stats columns exist
                column_names = [col[1] for col in columns]
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
                    f"✅ Schema validated: {actual_columns} columns (UNIFIED)"
                )

        except Exception as e:
            logger.error(f"❌ Schema validation failed: {e}")
            raise

    def safe_divide(self, numerator, denominator, default=0.0):
        """✅ NULL-safe division"""
        try:
            if numerator is None or denominator is None or denominator == 0:
                return default
            return numerator / denominator
        except (TypeError, ZeroDivisionError):
            return default

    def safe_percentage(self, part, total, default=0.0):
        """✅ NULL-safe percentage (returns 0-100)"""
        result = self.safe_divide(part, total, default)
        return result * 100 if result != default else default

    def safe_dpm(self, damage, time_seconds, default=0.0):
        """✅ NULL-safe DPM calculation: (damage * 60) / time_seconds"""
        try:
            if damage is None or time_seconds is None or time_seconds == 0:
                return default
            return (damage * 60) / time_seconds
        except (TypeError, ZeroDivisionError):
            return default

    async def send_with_delay(self, ctx, *args, delay=0.5, **kwargs):
        """✅ Send message with rate limit delay"""
        await ctx.send(*args, **kwargs)
        await asyncio.sleep(delay)

    async def setup_hook(self):
        """🔧 Initialize all bot components"""
        logger.info("🚀 Initializing Ultimate ET:Legacy Bot...")

        # ✅ CRITICAL: Validate schema FIRST
        await self.validate_database_schema()

        # Add the commands cog
        await self.add_cog(ETLegacyCommands(self))

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

        # 🎮 Load Last Session Cog (comprehensive last session analytics)
        try:
            from bot.cogs.last_session_cog import LastSessionCog
            await self.add_cog(LastSessionCog(self))
            logger.info("✅ Last Session Cog loaded (last_session with multiple view modes)")
        except Exception as e:
            logger.error(f"❌ Failed to load Last Session Cog: {e}", exc_info=True)

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

        # Initialize database
        await self.initialize_database()

        # Sync existing local files to processed_files table
        await self.sync_local_files_to_processed_table()

        # Start background tasks (only if not already running)
        if not self.endstats_monitor.is_running():
            self.endstats_monitor.start()
        if not self.cache_refresher.is_running():
            self.cache_refresher.start()
        if not self.scheduled_monitoring_check.is_running():
            self.scheduled_monitoring_check.start()
        if not self.voice_session_monitor.is_running():
            self.voice_session_monitor.start()
        logger.info("✅ Background tasks started")

        logger.info("✅ Ultimate Bot initialization complete!")
        logger.info(
            f"📋 Commands available: {[cmd.name for cmd in self.commands]}"
        )

    async def initialize_database(self):
        """📊 Verify database tables exist (created by recreate_database.py)"""
        async with aiosqlite.connect(self.db_path) as db:
            # Ensure player_name alias for this connection (non-Cog helper)
            try:
                await ensure_player_name_alias(db)
            except Exception:
                pass
            # Verify critical tables exist
            required_tables = [
                "sessions",
                "player_comprehensive_stats",
                "weapon_comprehensive_stats",
                "player_links",
                "processed_files",
            ]

            cursor = await db.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name IN (?, ?, ?, ?, ?)
            """,
                tuple(required_tables),
            )

            existing_tables = [row[0] for row in await cursor.fetchall()]

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

            # Create database entry
            async with aiosqlite.connect(self.db_path) as db:
                # Ensure player_name alias for this connection (non-Cog helper)
                try:
                    await ensure_player_name_alias(db)
                except Exception:
                    pass
                cursor = await db.execute(
                    """
                    INSERT INTO gaming_sessions (
                        start_time, participant_count, participants, status
                    ) VALUES (?, ?, ?, 'active')
                """,
                    (
                        self.session_start_time.isoformat(),
                        len(participants),
                        ",".join(str(uid) for uid in participants),
                    ),
                )
                self.gaming_sessions_db_id = cursor.lastrowid
                await db.commit()

            logger.info(
                f"🎮 GAMING SESSION STARTED! {len(participants)} players detected"
            )
            logger.info(f"📊 Session ID: {self.gaming_sessions_db_id}")
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

            # Update database
            async with aiosqlite.connect(self.db_path) as db:
                # Ensure player_name alias for this connection (non-Cog helper)
                try:
                    await ensure_player_name_alias(db)
                except Exception:
                    pass
                await db.execute(
                    """
                    UPDATE gaming_sessions
                    SET end_time = ?, duration_seconds = ?, status = 'ended'
                    WHERE session_id = ?
                """,
                    (
                        end_time.isoformat(),
                        int(duration.total_seconds()),
                        self.gaming_sessions_db_id,
                    ),
                )
                await db.commit()

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
                        timestamp=end_time,
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
            self.gaming_sessions_db_id = None

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

    def parse_gamestats_filename(self, filename):
        """
        Parse gamestats filename to extract metadata

        Format: YYYY-MM-DD-HHMMSS-<map_name>-round-<N>.txt
        Example: 2025-10-02-232818-erdenberg_t2-round-2.txt

        Returns:
            dict with keys: date, time, map_name, round_number, etc.
        """
        import re

        pattern = r"^(\d{4}-\d{2}-\d{2})-(\d{6})-(.+?)-round-(\d+)\.txt$"
        match = re.match(pattern, filename)

        if not match:
            return None

        date, time, map_name, round_num = match.groups()
        round_number = int(round_num)

        return {
            "date": date,
            "time": time,
            "map_name": map_name,
            "round_number": round_number,
            "is_round_1": round_number == 1,
            "is_round_2": round_number == 2,
            "is_map_complete": round_number == 2,
            "full_timestamp": f"{date} {time[:2]}:{time[2:4]}:{time[4:6]}",
            "filename": filename,
        }

    async def ssh_list_remote_files(self, ssh_config):
        """List .txt files on remote SSH server"""
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            files = await loop.run_in_executor(
                None, self._ssh_list_files_sync, ssh_config
            )
            return files

        except Exception as e:
            logger.error(f"❌ SSH list files failed: {e}")
            return []

    def _ssh_list_files_sync(self, ssh_config):
        """Synchronous SSH file listing"""
        import paramiko

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        key_path = os.path.expanduser(ssh_config["key_path"])

        ssh.connect(
            hostname=ssh_config["host"],
            port=ssh_config["port"],
            username=ssh_config["user"],
            key_filename=key_path,
            timeout=10,
        )

        sftp = ssh.open_sftp()
        files = sftp.listdir(ssh_config["remote_path"])
        # Filter: only .txt files, exclude obsolete _ws.txt files
        txt_files = [
            f
            for f in files
            if f.endswith(".txt") and not f.endswith("_ws.txt")
        ]

        sftp.close()
        ssh.close()

        return txt_files

    async def ssh_download_file(
        self, ssh_config, filename, local_dir="local_stats"
    ):
        """Download a single file from remote server"""
        try:
            # Ensure local directory exists
            os.makedirs(local_dir, exist_ok=True)

            # Run in executor
            loop = asyncio.get_event_loop()
            local_path = await loop.run_in_executor(
                None,
                self._ssh_download_file_sync,
                ssh_config,
                filename,
                local_dir,
            )
            return local_path

        except Exception as e:
            logger.error(f"❌ SSH download failed for {filename}: {e}")
            return None

    def _ssh_download_file_sync(self, ssh_config, filename, local_dir):
        """Synchronous SSH file download"""
        import paramiko

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        key_path = os.path.expanduser(ssh_config["key_path"])

        ssh.connect(
            hostname=ssh_config["host"],
            port=ssh_config["port"],
            username=ssh_config["user"],
            key_filename=key_path,
            timeout=10,
        )

        sftp = ssh.open_sftp()

        remote_file = f"{ssh_config['remote_path']}/{filename}"
        local_file = os.path.join(local_dir, filename)

        logger.info(f"📥 Downloading {filename}...")
        sftp.get(remote_file, local_file)

        sftp.close()
        ssh.close()

        return local_file

    async def process_gamestats_file(self, local_path, filename):
        """
        Process a gamestats file: parse and import to database

        Returns:
            dict with keys: success, session_id, player_count, error
        """
        try:
            from community_stats_parser import C0RNP0RN3StatsParser

            logger.info(f"⚙️ Processing {filename}...")

            # Parse using existing parser (it reads the file itself)
            parser = C0RNP0RN3StatsParser()
            stats_data = parser.parse_stats_file(local_path)

            if not stats_data or stats_data.get("error"):
                error_msg = (
                    stats_data.get("error") if stats_data else "No data"
                )
                raise Exception(f"Parser error: {error_msg}")

            # Import to database using existing import logic
            session_id = await self._import_stats_to_db(stats_data, filename)
            # Mark file as processed only after successful import
            try:
                await self._mark_file_processed(filename, success=True)
                self.processed_files.add(filename)
            except Exception as e:
                logger.debug(f"Failed to mark {filename} as processed: {e}")

            return {
                "success": True,
                "session_id": session_id,
                "player_count": len(stats_data.get("players", [])),
                "error": None,
                "stats_data": stats_data,
            }

        except Exception as e:
            logger.error(f"❌ Processing failed: {e}")
            return {
                "success": False,
                "session_id": None,
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
            
            # Get round data from the result
            stats_data = result.get('stats_data')
            session_id = result.get('session_id')
            
            if not stats_data or not session_id:
                logger.warning(f"⚠️ No stats data for {filename}, skipping post")
                logger.debug(f"   stats_data: {bool(stats_data)}, session_id: {session_id}")
                return
            
            # Extract round info from stats_data
            round_num = stats_data.get('round', 0)
            map_name = stats_data.get('map', 'Unknown')
            players = stats_data.get('players', [])
            
            logger.info(f"📋 Creating embed: Round {round_num}, Map {map_name}, {len(players)} players")
            
            # Create main embed
            embed = discord.Embed(
                title=f"🎮 Round {round_num} Complete - {map_name}",
                description=f"**{len(players)} Players** participated in this round",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            # Sort players by kills (descending)
            sorted_players = sorted(players, key=lambda p: p.get('kills', 0), reverse=True)
            
            # Build detailed stats for ALL players
            if sorted_players:
                logger.debug(f"📊 Building stats for {len(sorted_players)} players")
                
                # Split into chunks for multiple fields (Discord has field limits)
                chunk_size = 10
                for chunk_idx, i in enumerate(range(0, len(sorted_players), chunk_size)):
                    chunk = sorted_players[i:i + chunk_size]
                    field_name = f"👥 Players {i+1}-{min(i+chunk_size, len(sorted_players))}" if len(sorted_players) > chunk_size else "👥 All Players"
                    
                    player_lines = []
                    for player in chunk:
                        name = player.get('name', 'Unknown')[:20]  # Truncate long names
                        kills = player.get('kills', 0)
                        deaths = player.get('deaths', 0)
                        dmg = player.get('damage_given', 0)
                        dmgr = player.get('damage_received', 0)
                        acc = player.get('accuracy', 0)
                        hs = player.get('headshots', 0)
                        revives = player.get('revives', 0)
                        times_revived = player.get('ammogiven', 0)  # Need to map correct field
                        gibs = player.get('gibs', 0)
                        team_dmg_given = player.get('team_damage_given', 0)
                        team_dmg_rcvd = player.get('team_damage_received', 0)
                        time_dead = player.get('time_dead', 0)
                        
                        # Format: Name with primary stats
                        kd_ratio = f"{kills/deaths:.2f}" if deaths > 0 else f"{kills:.0f}"
                        
                        # Line 1: Core combat stats
                        line1 = (
                            f"**{name}** `K/D:{kills}/{deaths}` `KD:{kd_ratio}` "
                            f"`DMG:{int(dmg)}` `DMGR:{int(dmgr)}` `ACC:{acc:.1f}%`"
                        )
                        
                        # Line 2: Support & deaths stats  
                        line2 = (
                            f"    ↳ `HS:{hs}` `Revives:{revives}` `Gibs:{gibs}` "
                            f"`TmDMG:{int(team_dmg_given)}/{int(team_dmg_rcvd)}` `Dead:{time_dead}s`"
                        )
                        
                        player_lines.append(f"{line1}\n{line2}")
                    
                    embed.add_field(
                        name=field_name,
                        value="\n".join(player_lines),
                        inline=False
                    )
            
            # Calculate round totals
            total_kills = sum(p.get('kills', 0) for p in players)
            total_deaths = sum(p.get('deaths', 0) for p in players)
            total_dmg = sum(p.get('damage_given', 0) for p in players)
            total_hs = sum(p.get('headshots', 0) for p in players)
            avg_acc = sum(p.get('accuracy', 0) for p in players) / len(players) if players else 0
            
            embed.add_field(
                name="📊 Round Totals",
                value=(
                    f"**Kills:** {total_kills} | **Deaths:** {total_deaths}\n"
                    f"**Damage:** {int(total_dmg):,} | **Headshots:** {total_hs}\n"
                    f"**Avg Accuracy:** {avg_acc:.1f}%"
                ),
                inline=False
            )
            
            embed.set_footer(text=f"Session ID: {session_id} | {filename}")
            
            # Post to channel
            logger.info(f"📤 Sending detailed stats embed to #{channel.name}...")
            await channel.send(embed=embed)
            logger.info(f"✅ Successfully posted stats for {len(players)} players to Discord!")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ Error posting round stats to Discord: {e}", exc_info=True)

    async def _import_stats_to_db(self, stats_data, filename):
        """Import parsed stats to database"""
        try:
            logger.info(
                f"📊 Importing {len(stats_data.get('players', []))} "
                f"players to database..."
            )

            # Extract date from filename: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
            timestamp = "-".join(filename.split("-")[:4])  # Full timestamp
            date_part = "-".join(filename.split("-")[:3])  # Date for stats

            async with aiosqlite.connect(self.db_path) as db:
                # Ensure player_name alias for this connection (non-Cog helper)
                try:
                    await ensure_player_name_alias(db)
                except Exception:
                    pass
                # Start an explicit transaction so we can rollback on error
                await db.execute("BEGIN")
                # Insert session
                cursor = await db.execute(
                    """
                    SELECT id FROM sessions
                    WHERE session_date = ? AND map_name = ? AND round_number = ?
                """,
                    (
                        timestamp,
                        stats_data["map_name"],
                        stats_data["round_num"],
                    ),
                )

                existing = await cursor.fetchone()
                if existing:
                    logger.info(
                        f"⚠️ Session already exists (ID: {existing[0]})"
                    )
                    return existing[0]

                # Insert new session
                cursor = await db.execute(
                    """
                    INSERT INTO sessions (
                        session_date, map_name, round_number,
                        time_limit, actual_time
                    ) VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        timestamp,
                        stats_data["map_name"],
                        stats_data["round_num"],
                        stats_data.get("map_time", ""),
                        stats_data.get("actual_time", ""),
                    ),
                )

                session_id = cursor.lastrowid

                # Insert player stats
                for player in stats_data.get("players", []):
                    await self._insert_player_stats(
                        db, session_id, date_part, stats_data, player
                    )

                await db.commit()

                logger.info(
                    f"✅ Imported session {session_id} with "
                    f"{len(stats_data.get('players', []))} players"
                )

                return session_id

        except Exception as e:
            # Attempt a rollback to ensure partial writes are not committed
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    # Ensure player_name alias for this connection (non-Cog helper)
                    try:
                        await ensure_player_name_alias(db)
                    except Exception:
                        pass
                    await db.execute("ROLLBACK")
            except Exception:
                logger.debug("Rollback failed or not required")

            logger.error(f"❌ Database import failed: {e}")
            raise

    async def _insert_player_stats(
        self, db, session_id, session_date, result, player
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
            session_id,
            session_date,
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
            obj_stats.get("headshot_kills", 0),  # ✅ FIX: was player.get("headshots")
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

        cursor = await db.execute(
            """
            INSERT INTO player_comprehensive_stats (
                session_id, session_date, map_name, round_number,
                player_guid, player_name, clean_name, team,
                kills, deaths, damage_given, damage_received,
                team_damage_given, team_damage_received,
                gibs, self_kills, team_kills, team_gibs, headshot_kills,
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
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """,
            values,
        )
        # Capture inserted player row id for optional FK reference
        try:
            player_stats_id = cursor.lastrowid
        except Exception:
            player_stats_id = None

        # Insert weapon stats into weapon_comprehensive_stats if available
        try:
            weapon_stats = player.get("weapon_stats", {}) or {}
            if weapon_stats:
                pragma_cur = await db.execute("PRAGMA table_info(weapon_comprehensive_stats)")
                pragma_rows = await pragma_cur.fetchall()
                cols = [r[1] for r in pragma_rows]

                # Include session metadata columns if present (they're NOT NULL in some schemas)
                insert_cols = ["session_id"]
                if "session_date" in cols:
                    insert_cols.append("session_date")
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
                    f"Preparing to insert {len(weapon_stats)} weapon rows for {player.get('name')} (session {session_id})"
                )
                for weapon_name, w in weapon_stats.items():
                    w_hits = int(w.get("hits", 0) or 0)
                    w_shots = int(w.get("shots", 0) or 0)
                    w_kills = int(w.get("kills", 0) or 0)
                    w_deaths = int(w.get("deaths", 0) or 0)
                    w_headshots = int(w.get("headshots", 0) or 0)
                    w_acc = (w_hits / w_shots * 100) if w_shots > 0 else 0.0

                    # Build row values in the same order as insert_cols
                    row_vals = [session_id]
                    if "session_date" in cols:
                        row_vals.append(session_date)
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
                                "DIAG WEAPON INSERT: session_id=%s player=%s",
                                session_id,
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

                    await db.execute(insert_sql, tuple(row_vals))
        except Exception as e:
            # Weapon insert failures should be visible — escalate to error and include traceback
            logger.error(
                f"Failed to insert weapon stats for {player.get('name')} (session {session_id}): {e}",
                exc_info=True,
            )
        
        # 🔗 CRITICAL: Update player aliases for !stats and !link commands
        await self._update_player_alias(
            db,
            player.get("guid", "UNKNOWN"),
            player.get("name", "Unknown"),
            session_date,
        )

    async def _update_player_alias(self, db, guid, alias, last_seen_date):
        """
        Track player aliases for !stats and !link commands
        
        This is CRITICAL for !stats and !link to work properly!
        Updates the player_aliases table every time we see a player.
        """
        try:
            # Check if this GUID+alias combination exists
            async with db.execute(
                'SELECT times_seen FROM player_aliases WHERE guid = ? AND alias = ?',
                (guid, alias),
            ) as cursor:
                existing = await cursor.fetchone()

            if existing:
                # Update existing alias: increment times_seen and update last_seen
                await db.execute(
                    '''UPDATE player_aliases 
                       SET times_seen = times_seen + 1, last_seen = ?
                       WHERE guid = ? AND alias = ?''',
                    (last_seen_date, guid, alias),
                )
            else:
                # Insert new alias
                await db.execute(
                    '''INSERT INTO player_aliases (guid, alias, first_seen, last_seen, times_seen)
                       VALUES (?, ?, ?, ?, 1)''',
                    (guid, alias, last_seen_date, last_seen_date),
                )

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

    async def should_process_file(self, filename):
        """
        Smart file processing decision (Hybrid Approach)

        Checks multiple sources to avoid re-processing:
        1. In-memory cache (fastest)
        2. Local file exists (fast)
        3. Processed files table (fast, persistent)
        4. Sessions table (slower, definitive)

        Returns:
            bool: True if file should be processed, False if already done
        """
        try:
            # 1. Check in-memory cache
            if filename in self.processed_files:
                return False

            # 2. Check if local file exists
            local_path = os.path.join("local_stats", filename)
            if os.path.exists(local_path):
                logger.debug(
                    f"⏭️ {filename} exists locally, marking processed"
                )
                self.processed_files.add(filename)
                await self._mark_file_processed(filename, success=True)
                return False

            # 3. Check processed_files table
            if await self._is_in_processed_files_table(filename):
                logger.debug(f"⏭️ {filename} in processed_files table")
                self.processed_files.add(filename)
                return False

            # 4. Check if session exists in database
            if await self._session_exists_in_db(filename):
                logger.debug(f"⏭️ {filename} session exists in DB")
                self.processed_files.add(filename)
                await self._mark_file_processed(filename, success=True)
                return False

            # File is truly new!
            return True

        except Exception as e:
            logger.error(f"Error checking if should process {filename}: {e}")
            return False  # Skip on error to be safe

    async def _is_in_processed_files_table(self, filename):
        """Check if filename exists in processed_files table"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Ensure player_name alias for this connection (non-Cog helper)
                try:
                    await ensure_player_name_alias(db)
                except Exception:
                    pass
                cursor = await db.execute(
                    """SELECT 1 FROM processed_files 
                       WHERE filename = ? AND success = 1""",
                    (filename,),
                )
                result = await cursor.fetchone()
                return result is not None
        except Exception as e:
            logger.debug(f"Error checking processed_files table: {e}")
            return False

    async def _session_exists_in_db(self, filename):
        """
        Check if session exists in database by parsing filename

        Filename format: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
        """
        try:
            file_info = self.parse_gamestats_filename(filename)
            if not file_info:
                return False

            # Use full timestamp for unique identification
            timestamp = "-".join(filename.split("-")[:4])

            async with aiosqlite.connect(self.db_path) as db:
                # Ensure player_name alias for this connection (non-Cog helper)
                try:
                    await ensure_player_name_alias(db)
                except Exception:
                    pass
                cursor = await db.execute(
                    """
                    SELECT 1 FROM sessions
                    WHERE session_date = ? 
                      AND map_name = ? 
                      AND round_number = ?
                    LIMIT 1
                """,
                    (
                        timestamp,
                        file_info["map_name"],
                        file_info["round_number"],
                    ),
                )

                result = await cursor.fetchone()
                return result is not None

        except Exception as e:
            logger.debug(f"Error checking session in DB: {e}")
            return False

    async def _mark_file_processed(
        self, filename, success=True, error_msg=None
    ):
        """
        Mark a file as processed in the processed_files table

        Args:
            filename: Name of the processed file
            success: Whether processing was successful
            error_msg: Error message if processing failed
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Ensure player_name alias for this connection (non-Cog helper)
                try:
                    await ensure_player_name_alias(db)
                except Exception:
                    pass
                await db.execute(
                    """
                    INSERT OR REPLACE INTO processed_files 
                    (filename, success, error_message, processed_at)
                    VALUES (?, ?, ?, ?)
                """,
                    (
                        filename,
                        1 if success else 0,
                        error_msg,
                        datetime.now().isoformat(),
                    ),
                )
                await db.commit()

        except Exception as e:
            logger.debug(f"Error marking file as processed: {e}")

    async def sync_local_files_to_processed_table(self):
        """
        One-time sync: Add existing local_stats files to processed_files

        Call this during bot startup to populate the table with
        already-downloaded files
        """
        try:
            local_dir = "local_stats"
            if not os.path.exists(local_dir):
                return

            files = [f for f in os.listdir(local_dir) if f.endswith(".txt")]

            if not files:
                return

            logger.info(
                f"🔄 Syncing {len(files)} local files to "
                f"processed_files table..."
            )

            synced = 0
            async with aiosqlite.connect(self.db_path) as db:
                for filename in files:
                    # Check if already in table
                    cursor = await db.execute(
                        "SELECT 1 FROM processed_files WHERE filename = ?",
                        (filename,),
                    )
                    if await cursor.fetchone():
                        continue  # Already tracked

                    # Add to table
                    await db.execute(
                        """
                        INSERT INTO processed_files 
                        (filename, success, error_message, processed_at)
                        VALUES (?, 1, NULL, ?)
                    """,
                        (filename, datetime.now().isoformat()),
                    )

                    self.processed_files.add(filename)
                    synced += 1

                await db.commit()

            if synced > 0:
                logger.info(
                    f"✅ Synced {synced} local files to "
                    f"processed_files table"
                )

        except Exception as e:
            logger.error(f"Error syncing local files: {e}")

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

            # Create session end notification
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
                async with aiosqlite.connect(self.db_path) as db:
                    # Ensure player_name alias for this connection (non-Cog helper)
                    try:
                        await ensure_player_name_alias(db)
                    except Exception:
                        pass
                    # Get most recent session data
                    cursor = await db.execute(
                        """
                        SELECT DISTINCT DATE(session_date) as date
                        FROM player_comprehensive_stats
                        ORDER BY date DESC
                        LIMIT 1
                    """
                    )
                    row = await cursor.fetchone()

                    if row:
                        session_date = row[0]
                        logger.info(
                            f"📊 Posting auto-summary for {session_date}"
                        )

                        # Use last_session logic to generate embeds
                        # (This would call the existing last_session code)
                        await channel.send(
                            f"📊 **Session Summary for {session_date}**\n"
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

    @tasks.loop(seconds=30)
    async def endstats_monitor(self):
        """
        🔄 SSH Monitoring Task - Runs every 30 seconds

        Monitors remote game server for new stats files:
        1. Lists files on remote server via SSH
        2. Compares with processed_files tracking
        3. Downloads new files
        4. Parses and imports to database
        5. Posts Discord round summaries automatically
        """
        if not self.monitoring or not self.ssh_enabled:
            # Silent return - only log once when monitoring starts/stops
            return

        try:
            logger.debug("🔍 SSH monitor check starting...")
            
            # Build SSH config
            ssh_config = {
                "host": os.getenv("SSH_HOST"),
                "port": int(os.getenv("SSH_PORT", 22)),
                "user": os.getenv("SSH_USER"),
                "key_path": os.getenv("SSH_KEY_PATH", ""),
                "remote_path": os.getenv("REMOTE_STATS_PATH"),
            }

            # Validate SSH config
            if not all(
                [
                    ssh_config["host"],
                    ssh_config["user"],
                    ssh_config["key_path"],
                    ssh_config["remote_path"],
                ]
            ):
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
            remote_files = await self.ssh_list_remote_files(ssh_config)

            if not remote_files:
                logger.debug("📂 No remote files found or SSH connection failed")
                return

            logger.debug(f"📂 Found {len(remote_files)} total files on remote server")

            # Check each file
            new_files_count = 0
            for filename in remote_files:
                # Check if already processed (4-layer check)
                if await self.should_process_file(filename):
                    new_files_count += 1
                    logger.info("=" * 60)
                    logger.info(f"📥 NEW FILE DETECTED: {filename}")
                    logger.info("=" * 60)

                    # Download file
                    download_start = time.time()
                    local_path = await self.ssh_download_file(
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
        logger.info("✅ SSH monitoring task ready")

    @tasks.loop(seconds=30)
    async def cache_refresher(self):
        """
        🔄 Cache Refresh Task - Runs every 30 seconds

        Keeps in-memory cache in sync with database
        """
        try:
            # Refresh processed files cache
            async with aiosqlite.connect(self.db_path) as db:
                # Ensure player_name alias for this connection (non-Cog helper)
                try:
                    await ensure_player_name_alias(db)
                except Exception:
                    pass
                cursor = await db.execute(
                    "SELECT filename FROM processed_files WHERE success = 1"
                )
                rows = await cursor.fetchall()
                self.processed_files = {row[0] for row in rows}

        except Exception as e:
            logger.debug(f"Cache refresh error: {e}")

    @cache_refresher.before_loop
    async def before_cache_refresher(self):
        """Wait for bot to be ready"""
        await self.wait_until_ready()

    @tasks.loop(minutes=1)
    async def scheduled_monitoring_check(self):
        """
        ⏰ Scheduled Monitoring - Runs every 1 minute

        Auto-starts monitoring at 20:00 CET daily
        No manual !session_start needed!
        """
        if not self.ssh_enabled:
            return

        try:
            # Determine CET timezone: prefer pytz, then zoneinfo. If neither is
            # available (or the tz database isn't present on the platform),
            # fall back to the local system time (naive datetime) so the
            # scheduler keeps running instead of crashing repeatedly.
            cet = None
            try:
                import pytz

                cet = pytz.timezone("Europe/Paris")
            except Exception:
                try:
                    from zoneinfo import ZoneInfo

                    try:
                        cet = ZoneInfo("Europe/Paris")
                    except Exception as e:
                        logger.warning(
                            "Could not load ZoneInfo('Europe/Paris'): %s", e
                        )
                        cet = None
                except Exception:
                    cet = None

            if cet is not None:
                now = datetime.now(cet)
            else:
                logger.warning(
                    "Timezone 'Europe/Paris' not available; using local system time"
                )
                now = datetime.now()

            # Check if it's 20:00 CET
            if now.hour == 20 and now.minute == 0:
                if not self.monitoring:
                    logger.info("⏰ 20:00 CET - Auto-starting monitoring!")
                    self.monitoring = True

                    # Post notification to Discord
                    channel = self.get_channel(self.stats_channel_id)
                    if channel:
                        embed = discord.Embed(
                            title="🎮 Monitoring Started",
                            description=(
                                "Automatic monitoring enabled at 20:00 CET!\n\n"
                                "Round summaries will be posted automatically "
                                "when games are played."
                            ),
                            color=0x00FF00,
                            timestamp=datetime.now(),
                        )
                        await channel.send(embed=embed)

                    logger.info("✅ Monitoring auto-started at 20:00 CET")

        except Exception as e:
            logger.error(f"Scheduled monitoring error: {e}")

    @scheduled_monitoring_check.before_loop
    async def before_scheduled_monitoring(self):
        """Wait for bot to be ready"""
        await self.wait_until_ready()

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
        logger.info(f"🚀 Ultimate ET:Legacy Bot logged in as {self.user}")
        logger.info(f"📊 Connected to database: {self.db_path}")
        logger.info(f"🎮 Bot ready with {len(list(self.commands))} commands!")

        # Clear any old slash commands to avoid confusion
        try:
            self.tree.clear_commands(guild=None)
            await self.tree.sync()
            logger.info("🧹 Cleared old slash commands")
        except Exception as e:
            logger.warning(f"Could not clear slash commands: {e}")

    async def on_command_error(self, ctx, error):
        """🚨 Handle command errors"""
        self.error_count += 1

        if isinstance(error, commands.CommandNotFound):
            await ctx.send(
                "❌ Command not found. Use `!help_command` for available commands."
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                f"❌ Missing argument: {error.param}. Use `!help_command` for usage."
            )
        else:
            logger.error(f"Command error: {error}")
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
