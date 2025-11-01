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

# Load environment variables if available
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("UltimateBot")

# Reduce noise from verbose third-party libraries (paramiko/discord/asyncio)
logging.getLogger("paramiko").setLevel(logging.WARNING)
logging.getLogger("paramiko.transport").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("discord").setLevel(logging.INFO)


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
class StatsCache:
    """
    High-performance caching system for database queries.
    Reduces repeated queries by 80% during active sessions.

    Features:
    - TTL-based expiration (default 5 minutes)
    - Automatic cache invalidation
    - Memory-efficient storage

    Usage:
        cache = StatsCache(ttl_seconds=300)
        cached = cache.get("stats_player123")
        if not cached:
            cached = await fetch_from_db()
            cache.set("stats_player123", cached)
    """

    def __init__(self, ttl_seconds=300):
        self.cache = {}
        self.timestamps = {}
        self.ttl = ttl_seconds
        logger.info(f"📦 StatsCache initialized (TTL: {ttl_seconds}s)")

    def get(self, key):
        """Get cached value if still valid, None otherwise"""
        if key in self.cache:
            age = (datetime.now() - self.timestamps[key]).total_seconds()
            if age < self.ttl:
                logger.debug(f"✅ Cache HIT: {key} (age: {age:.1f}s)")
                return self.cache[key]
            else:
                logger.debug(f"⏰ Cache EXPIRED: {key} (age: {age:.1f}s)")
                del self.cache[key]
                del self.timestamps[key]
        return None

    def set(self, key, value):
        """Store value in cache with current timestamp"""
        self.cache[key] = value
        self.timestamps[key] = datetime.now()
        logger.debug(f"💾 Cache SET: {key} (total keys: {len(self.cache)})")

    def clear(self):
        """Clear all cached data"""
        count = len(self.cache)
        self.cache.clear()
        self.timestamps.clear()
        logger.info(f"🗑️  Cache CLEARED: {count} keys removed")

    def stats(self):
        """Get cache statistics"""
        total = len(self.cache)
        expired = sum(
            1
            for k in self.cache
            if (datetime.now() - self.timestamps[k]).total_seconds()
            >= self.ttl
        )
        return {
            "total_keys": total,
            "valid_keys": total - expired,
            "expired_keys": expired,
            "ttl_seconds": self.ttl,
        }


# ============================================================================
# 📅 SEASON SYSTEM: QUARTERLY COMPETITION RESETS
# ============================================================================
class SeasonManager:
    """
    Manages quarterly competitive seasons with leaderboard resets.

    Features:
    - Automatic season calculation (Q1: Jan-Mar, Q2: Apr-Jun, Q3: Jul-Sep, Q4: Oct-Dec)
    - Season-filtered queries for leaderboards
    - All-time stats preservation
    - Season transition detection

    Season Format: "2025-Q4" (Year-Quarter)

    Usage:
        sm = SeasonManager()
        current = sm.get_current_season()  # "2025-Q4"
        start, end = sm.get_season_dates(current)
        is_new = sm.is_new_season("2025-Q3")
    """

    def __init__(self):
        self.season_names = {1: "Spring", 2: "Summer", 3: "Fall", 4: "Winter"}
        logger.info(
            f"📅 SeasonManager initialized - Current: {self.get_current_season()}"
        )

    def get_current_season(self):
        """Get current season identifier (e.g., '2025-Q4')"""
        now = datetime.now()
        quarter = (now.month - 1) // 3 + 1
        return f"{now.year}-Q{quarter}"

    def get_season_name(self, season_id=None):
        """Get friendly season name (e.g., '2025 Winter (Q4)')"""
        if season_id is None:
            season_id = self.get_current_season()

        year, quarter = season_id.split("-Q")
        quarter_num = int(quarter)
        season_name = self.season_names.get(quarter_num, f"Q{quarter_num}")
        return f"{year} {season_name} (Q{quarter_num})"

    def get_season_dates(self, season_id=None):
        """Get start and end dates for a season"""
        if season_id is None:
            season_id = self.get_current_season()

        year, quarter = season_id.split("-Q")
        year = int(year)
        quarter = int(quarter)

        # Calculate start month
        start_month = (quarter - 1) * 3 + 1

        # Start: First day of first month
        start_date = datetime(year, start_month, 1)

        # End: Last day of last month in quarter
        if quarter == 4:
            end_date = datetime(year, 12, 31, 23, 59, 59)
        else:
            end_month = start_month + 2
            # Get last day of end month
            if end_month == 12:
                end_date = datetime(year, 12, 31, 23, 59, 59)
            else:
                # First day of next month minus 1 second
                next_month = datetime(year, end_month + 1, 1)
                end_date = datetime(
                    year,
                    end_month,
                    (next_month - datetime(year, end_month, 1)).days,
                    23,
                    59,
                    59,
                )

        return start_date, end_date

    def get_season_sql_filter(self, season_id=None):
        """Get SQL WHERE clause for filtering by season"""
        if season_id is None or season_id.lower() == "current":
            season_id = self.get_current_season()

        if season_id.lower() == "alltime":
            return ""  # No filter for all-time stats

        start_date, end_date = self.get_season_dates(season_id)
        return f"AND s.session_date >= '{start_date.strftime('%Y-%m-%d')}' AND s.session_date <= '{end_date.strftime('%Y-%m-%d')}'"

    def is_new_season(self, last_known_season):
        """Check if we've transitioned to a new season"""
        current = self.get_current_season()
        return current != last_known_season

    def get_all_seasons(self):
        """Get list of all available seasons (for dropdown/selection)"""
        # For now, just return current season
        # In future, could query database for actual seasons with data
        current = self.get_current_season()
        year, quarter = current.split("-Q")
        year = int(year)
        quarter = int(quarter)

        seasons = []
        # Generate last 4 quarters (1 year of seasons)
        for i in range(4):
            q = quarter - i
            y = year
            if q <= 0:
                q += 4
                y -= 1
            seasons.append(f"{y}-Q{q}")

        return seasons

    def get_days_until_season_end(self):
        """Get number of days until current season ends"""
        _, end_date = self.get_season_dates()
        now = datetime.now()
        delta = end_date - now
        return delta.days


# ============================================================================
# 🏆 ACHIEVEMENTS: MILESTONE TRACKING & NOTIFICATIONS
# ============================================================================
class AchievementSystem:
    """
    Track and notify players when they hit major milestones.

    Milestones Tracked:
    - Kill milestones: 100, 500, 1000, 2500, 5000, 10000
    - Game milestones: 10, 50, 100, 250, 500, 1000
    - K/D milestones: 1.0, 1.5, 2.0, 3.0

    Features:
    - @mention notifications in stats channel
    - Prevents duplicate notifications
    - Beautiful embed formatting
    """

    # Define all achievement thresholds
    KILL_MILESTONES = {
        100: {"emoji": "🎯", "title": "First Blood Century", "color": 0x95A5A6},
        500: {"emoji": "💥", "title": "Killing Machine", "color": 0x3498DB},
        1000: {"emoji": "💀", "title": "Thousand Killer", "color": 0x9B59B6},
        2500: {"emoji": "⚔️", "title": "Elite Warrior", "color": 0xE74C3C},
        5000: {"emoji": "☠️", "title": "Death Incarnate", "color": 0xC0392B},
        10000: {"emoji": "👑", "title": "Legendary Slayer", "color": 0xF39C12},
    }

    GAME_MILESTONES = {
        10: {"emoji": "🎮", "title": "Getting Started", "color": 0x95A5A6},
        50: {"emoji": "🎯", "title": "Regular Player", "color": 0x3498DB},
        100: {"emoji": "🏆", "title": "Dedicated Gamer", "color": 0x9B59B6},
        250: {"emoji": "⭐", "title": "Community Veteran", "color": 0xE74C3C},
        500: {"emoji": "💎", "title": "Hardcore Legend", "color": 0xF39C12},
        1000: {"emoji": "👑", "title": "Ultimate Champion", "color": 0xF1C40F},
    }

    KD_MILESTONES = {
        1.0: {"emoji": "⚖️", "title": "Balanced Fighter", "color": 0x95A5A6},
        1.5: {"emoji": "📈", "title": "Above Average", "color": 0x3498DB},
        2.0: {"emoji": "🔥", "title": "Elite Killer", "color": 0xE74C3C},
        3.0: {"emoji": "💯", "title": "Unstoppable", "color": 0xF39C12},
    }

    def __init__(self, bot):
        self.bot = bot
        self.notified_achievements = set()  # Track what we've already notified
        logger.info("🏆 AchievementSystem initialized")

    async def check_player_achievements(self, player_guid, channel=None):
        """
        Check if player hit any milestones and notify if needed.

        Args:
            player_guid: Player's GUID to check
            channel: Discord channel to send notifications (optional)

        Returns:
            List of newly unlocked achievements
        """
        try:
            new_achievements = []

            async with aiosqlite.connect(self.bot.db_path) as db:
                # Ensure a per-connection alias for player_name if DB uses a different column
                try:
                    await self._ensure_player_name_alias(db)
                except Exception:
                    # _ensure_player_name_alias logs its own errors; continue
                    pass
                # Get player totals
                async with db.execute(
                    """
                    SELECT 
                        SUM(kills) as total_kills,
                        SUM(deaths) as total_deaths,
                        COUNT(DISTINCT session_id) as total_games,
                        CASE 
                            WHEN SUM(deaths) > 0 
                            THEN CAST(SUM(kills) AS REAL) / SUM(deaths)
                            ELSE SUM(kills) 
                        END as overall_kd
                    FROM player_comprehensive_stats
                    WHERE player_guid = ?
                """,
                    (player_guid,),
                ) as cursor:
                    stats = await cursor.fetchone()

                if not stats or stats[0] is None:
                    return []

                kills, deaths, games, kd_ratio = stats

                # Get player's Discord link (if exists)
                async with db.execute(
                    """
                    SELECT discord_id, et_name FROM player_links
                    WHERE et_guid = ?
                """,
                    (player_guid,),
                ) as cursor:
                    link = await cursor.fetchone()

                discord_id = link[0] if link else None
                player_name = link[1] if link else "Unknown Player"

                # Check kill milestones
                for threshold, achievement in self.KILL_MILESTONES.items():
                    achievement_id = f"{player_guid}_kills_{threshold}"
                    if (
                        kills >= threshold
                        and achievement_id not in self.notified_achievements
                    ):
                        new_achievements.append(
                            {
                                "type": "kills",
                                "threshold": threshold,
                                "achievement": achievement,
                                "player_name": player_name,
                                "discord_id": discord_id,
                                "value": kills,
                            }
                        )
                        self.notified_achievements.add(achievement_id)

                # Check game milestones
                for threshold, achievement in self.GAME_MILESTONES.items():
                    achievement_id = f"{player_guid}_games_{threshold}"
                    if (
                        games >= threshold
                        and achievement_id not in self.notified_achievements
                    ):
                        new_achievements.append(
                            {
                                "type": "games",
                                "threshold": threshold,
                                "achievement": achievement,
                                "player_name": player_name,
                                "discord_id": discord_id,
                                "value": games,
                            }
                        )
                        self.notified_achievements.add(achievement_id)

                # Check K/D milestones (only if player has 20+ games)
                if games >= 20:
                    for threshold, achievement in self.KD_MILESTONES.items():
                        achievement_id = f"{player_guid}_kd_{threshold}"
                        if (
                            kd_ratio >= threshold
                            and achievement_id
                            not in self.notified_achievements
                        ):
                            new_achievements.append(
                                {
                                    "type": "kd",
                                    "threshold": threshold,
                                    "achievement": achievement,
                                    "player_name": player_name,
                                    "discord_id": discord_id,
                                    "value": kd_ratio,
                                }
                            )
                            self.notified_achievements.add(achievement_id)

                # Send notifications for new achievements
                if new_achievements and channel:
                    for ach in new_achievements:
                        await self._send_achievement_notification(ach, channel)

                return new_achievements

        except Exception as e:
            logger.error(
                f"Error checking achievements for {player_guid}: {e}",
                exc_info=True,
            )
            return []

    async def _send_achievement_notification(self, achievement, channel):
        """Send a beautiful achievement notification to Discord"""
        try:
            ach_data = achievement["achievement"]

            # Build description with @mention if available
            if achievement["discord_id"]:
                user = self.bot.get_user(int(achievement["discord_id"]))
                mention = user.mention if user else achievement["player_name"]
            else:
                mention = achievement["player_name"]

            # Format value based on type
            if achievement["type"] == "kills":
                value_text = f"{achievement['value']:,} kills"
            elif achievement["type"] == "games":
                value_text = f"{achievement['value']:,} games played"
            elif achievement["type"] == "kd":
                value_text = f"{achievement['value']:.2f} K/D ratio"
            else:
                value_text = str(achievement["value"])

            embed = discord.Embed(
                title=f"{ach_data['emoji']} Achievement Unlocked!",
                description=f"**{ach_data['title']}**",
                color=ach_data["color"],
                timestamp=datetime.now(),
            )

            embed.add_field(name="Player", value=mention, inline=True)

            embed.add_field(name="Milestone", value=value_text, inline=True)

            embed.set_footer(text="🎮 ET:Legacy Stats Bot")

            await channel.send(embed=embed)
            logger.info(
                f"🏆 Achievement notification sent: {achievement['player_name']} - {ach_data['title']}"
            )

        except Exception as e:
            logger.error(
                f"Error sending achievement notification: {e}", exc_info=True
            )


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

    @commands.command(name="session_start")
    async def session_start(self, ctx, *, map_name: str = "Unknown"):
        """🎬 Start a new gaming session"""
        try:
            if self.bot.current_session:
                await ctx.send(
                    "❌ A session is already active. End it first with `!session_end`"
                )
                return

            now = datetime.now()
            date_str = now.strftime("%Y-%m-%d")
            time_str = now.strftime("%H:%M:%S")

            async with aiosqlite.connect(self.bot.db_path) as db:
                # Ensure player_name alias exists for this connection
                try:
                    await self._ensure_player_name_alias(db)
                except Exception:
                    pass
                cursor = await db.execute(
                    """
                    INSERT INTO sessions (start_time, date, map_name, status)
                    VALUES (?, ?, ?, 'active')
                """,
                    (time_str, date_str, map_name),
                )

                session_id = cursor.lastrowid
                self.bot.current_session = session_id
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
                        # (session_start does not insert weapon rows here)

        except Exception as e:
            logger.error(f"Error in session_start: {e}")
            try:
                await ctx.send(f"❌ Error starting session: {e}")
            except Exception:
                pass

    def parse_time_period(self, period_str: str | None):
        """Parse a human-friendly period string into days.

        Returns:
            int days or None for 'all' (no limit)
        Examples accepted: '1day', '2weeks', '1month', '30', 'all'
        """
        import re

        if not period_str:
            return 14

        s = period_str.strip().lower()
        if s in ("all", "any", "everything"):
            return None

        # Full-word matches
        m = re.match(r"^(\d+)\s*(day|days|d)$", s)
        if m:
            return int(m.group(1))

        m = re.match(r"^(\d+)\s*(week|weeks|w)$", s)
        if m:
            return int(m.group(1)) * 7

        m = re.match(r"^(\d+)\s*(month|months|m)$", s)
        if m:
            return int(m.group(1)) * 30

        m = re.match(r"^(\d+)\s*(year|years|y)$", s)
        if m:
            return int(m.group(1)) * 365

        # Short shorthand like '1d', '2w', '3m', '1y'
        m = re.match(r"^(\d+)([dwmy])$", s)
        if m:
            n = int(m.group(1))
            u = m.group(2)
            return n if u == "d" else n * 7 if u == "w" else n * 30 if u == "m" else n * 365

        # Numeric-only -> days
        if s.isdigit():
            return int(s)

        # Unknown -> default None (caller may treat as all)
        return None

    def _should_include_file(self, filename: str, days_back: int | None):
        """Return True if the filename falls within days_back (None = include all)."""
        from datetime import datetime, timedelta

        if days_back is None:
            return True
        try:
            parts = filename.split("-")
            if len(parts) < 3:
                return True
            date_str = "-".join(parts[:3])
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            cutoff_date = datetime.now() - timedelta(days=days_back)
            return file_date >= cutoff_date
        except Exception:
            return True

    @commands.command(name="sync_stats", aliases=["syncstats", "sync_logs"])
    async def sync_stats(self, ctx, period: str = None):
        """🔄 Manually sync and process stats files from server

        Usage: !sync_stats [period]  (period examples: 1day, 2weeks, 1month, all)
        """
        try:
            if not self.bot.ssh_enabled:
                await ctx.send(
                    "❌ SSH monitoring is not enabled. "
                    "Set `SSH_ENABLED=true` in .env file."
                )
                return

            # Parse time period (default 2 weeks)
            # parse_time_period is synchronous, do not await it
            days_back = self.parse_time_period(period) if period else 14

            # Friendly period display
            if days_back:
                period_display = f"last {days_back} days"
                if days_back == 1:
                    period_display = "last 24 hours"
                elif days_back == 7:
                    period_display = "last week"
                elif days_back == 14:
                    period_display = "last 2 weeks"
                elif days_back == 30:
                    period_display = "last month"
                elif days_back == 365:
                    period_display = "last year"
            else:
                period_display = "all time (no filter)"

            # Send initial message
            status_msg = await ctx.send(
                f"🔄 Checking remote server for new stats files...\n📅 Time period: **{period_display}**"
            )

            # Build SSH config
            ssh_config = {
                "host": os.getenv("SSH_HOST"),
                "port": int(os.getenv("SSH_PORT", 22)),
                "user": os.getenv("SSH_USER"),
                "key_path": os.getenv("SSH_KEY_PATH", ""),
                "remote_path": os.getenv("REMOTE_STATS_PATH"),
            }

            # List remote files
            remote_files = await self.bot.ssh_list_remote_files(ssh_config)

            if not remote_files:
                await status_msg.edit(
                    content="❌ Could not connect to server or no files found."
                )
                return

            # Filter files by time period if requested
            if days_back:
                filtered = [f for f in remote_files if self._should_include_file(f, days_back)]
                excluded_count = len(remote_files) - len(filtered)
                remote_files = filtered
                if excluded_count > 0:
                    await status_msg.edit(
                        content=(
                            f"🔄 Checking remote server...\n📅 Time period: **{period_display}**\n"
                            f"📊 Found **{len(remote_files)}** files in period ({excluded_count} older files excluded)"
                        )
                    )

            # Check which files need processing
            files_to_process = []
            for filename in remote_files:
                if await self.bot.should_process_file(filename):
                    files_to_process.append(filename)

            if not files_to_process:
                await status_msg.edit(
                    content="✅ All files are already processed! Nothing new to sync."
                )
                return

            # Sort files: Round 1 before Round 2, chronologically
            # Format: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
            def sort_key(filename):
                parts = filename.split("-")
                if len(parts) >= 7:
                    date = "-".join(parts[:3])  # YYYY-MM-DD
                    time = parts[3]  # HHMMSS
                    round_num = parts[-1].replace(".txt", "")  # N from round-N
                    return (
                        date,
                        time,
                        round_num,
                    )  # Sort by date, time, then round
                return (filename, "", "99")  # Fallback

            files_to_process.sort(key=sort_key)

            # Phase 1: Download ALL files first
            await status_msg.edit(
                content=f"📥 Downloading {len(files_to_process)} file(s)..."
            )

            downloaded_files = []
            download_failed = 0

            for i, filename in enumerate(files_to_process):
                try:
                    # Download file
                    local_path = await self.bot.ssh_download_file(
                        ssh_config, filename, "local_stats"
                    )

                    if local_path:
                        downloaded_files.append((filename, local_path))

                        # Update progress every 50 files
                        if (i + 1) % 50 == 0:
                            await status_msg.edit(
                                content=f"📥 Downloading... {i + 1}/{len(files_to_process)}"
                            )
                    else:
                        download_failed += 1
                        logger.warning(f"Failed to download {filename}")

                except Exception as e:
                    logger.error(f"Download error for {filename}: {e}")
                    download_failed += 1

            # Phase 2: Verify downloads
            await status_msg.edit(
                content=f"🔍 Verifying downloads... {len(downloaded_files)} files"
            )

            local_files = set(os.listdir("local_stats"))
            verified_files = []

            for filename, local_path in downloaded_files:
                if os.path.basename(local_path) in local_files:
                    verified_files.append((filename, local_path))
                else:
                    logger.error(f"Downloaded file missing: {filename}")
                    download_failed += 1

            logger.info(
                f"✅ Downloaded {len(verified_files)} files, "
                f"{download_failed} failed"
            )

            if not verified_files:
                await status_msg.edit(
                    content="❌ No files were successfully downloaded."
                )
                return

            # Phase 3: Process/parse files for database import
            await status_msg.edit(
                content=f"⚙️ Processing {len(verified_files)} file(s) for database import..."
            )

            processed = 0
            process_failed = 0

            for i, (filename, local_path) in enumerate(verified_files):
                try:
                    # Process the file (parse + import)
                    result = await self.bot.process_gamestats_file(
                        local_path, filename
                    )

                    if result.get("success"):
                        processed += 1
                    else:
                        process_failed += 1
                        logger.error(
                            f"Processing failed for {filename}: {result.get('error')}"
                        )

                    # Update progress every 50 files
                    if (i + 1) % 50 == 0:
                        await status_msg.edit(
                            content=f"⚙️ Processing... {i + 1}/{len(verified_files)}"
                        )

                except Exception as e:
                    logger.error(f"Failed to process {filename}: {e}")
                    process_failed += 1

            # Final status
            embed = discord.Embed(
                title="✅ Stats Sync Complete!",
                color=0x00FF00,
                timestamp=datetime.now(),
            )
            embed.add_field(
                name="� Download Phase",
                value=(
                    f"✅ Downloaded: **{len(verified_files)}** file(s)\n"
                    f"❌ Failed: **{download_failed}** file(s)"
                ),
                inline=False,
            )
            embed.add_field(
                name="⚙️ Processing Phase",
                value=(
                    f"✅ Processed: **{processed}** file(s)\n"
                    f"❌ Failed: **{process_failed}** file(s)"
                ),
                inline=False,
            )

            if processed > 0:
                embed.add_field(
                    name="💡 What's Next?",
                    value=(
                        "Round summaries have been posted above!\n"
                        "Use `!last_session` to see full session details."
                    ),
                    inline=False,
                )

            await status_msg.edit(content=None, embed=embed)
            logger.info(
                f"✅ Manual sync complete: {len(verified_files)} downloaded, "
                f"{processed} processed, {process_failed} failed"
            )

        except Exception as e:
            logger.error(f"Error in sync_stats: {e}")
            await ctx.send(f"❌ Sync error: {e}")

    @commands.command(name="sync_today", aliases=["sync1day"])
    async def sync_today(self, ctx):
        """🔄 Quick sync: Today's matches only (last 24 hours)"""
        await self.sync_stats(ctx, period="1day")

    @commands.command(name="sync_week", aliases=["sync1week"])
    async def sync_week(self, ctx):
        """🔄 Quick sync: This week's matches (last 7 days)"""
        await self.sync_stats(ctx, period="1week")

    @commands.command(name="sync_month", aliases=["sync1month"])
    async def sync_month(self, ctx):
        """🔄 Quick sync: This month's matches (last 30 days)"""
        await self.sync_stats(ctx, period="1month")

    @commands.command(name="sync_all")
    async def sync_all(self, ctx):
        """🔄 Quick sync: ALL unprocessed files (no time filter)"""
        await self.sync_stats(ctx, period="all")

    @commands.command(name="session_end")
    async def session_end(self, ctx):
        """🏁 Stop SSH monitoring"""
        try:
            if not self.bot.monitoring:
                await ctx.send("❌ Monitoring is not currently active.")
                return

            # Disable monitoring flag
            self.bot.monitoring = False

            embed = discord.Embed(
                title="🏁 Monitoring Stopped",
                description=(
                    "SSH monitoring has been disabled.\n\n"
                    "Use `!session_start` to re-enable automatic monitoring."
                ),
                color=0xFF0000,
                timestamp=datetime.now(),
            )

            await ctx.send(embed=embed)
            logger.info("✅ Monitoring manually stopped via !session_end")

        except Exception as e:
            logger.error(f"Error ending session: {e}")
            await ctx.send(f"❌ Error ending session: {e}")

    @commands.command(name="ping")
    async def ping(self, ctx):
        """🏓 Check bot status and performance"""
        try:
            start_time = time.time()

            # Test database connection
            async with aiosqlite.connect(self.bot.db_path) as db:
                # Apply runtime alias to avoid schema mismatch errors
                try:
                    await self._ensure_player_name_alias(db)
                except Exception:
                    pass
                await db.execute("SELECT 1")

            db_latency = (time.time() - start_time) * 1000

            # Get cache stats
            cache_info = self.stats_cache.stats()

            embed = discord.Embed(
                title="🏓 Ultimate Bot Status", color=0x00FF00
            )
            embed.add_field(
                name="Bot Latency",
                value=f"{round(self.bot.latency * 1000)}ms",
                inline=True,
            )
            embed.add_field(
                name="DB Latency", value=f"{round(db_latency)}ms", inline=True
            )
            embed.add_field(
                name="Active Session",
                value="Yes" if self.bot.current_session else "No",
                inline=True,
            )
            embed.add_field(
                name="Commands",
                value=f"{len(list(self.bot.commands))}",
                inline=True,
            )
            embed.add_field(
                name="Query Cache",
                value=f"{cache_info['valid_keys']} active / {cache_info['total_keys']} total",
                inline=True,
            )
            embed.add_field(
                name="Cache TTL",
                value=f"{cache_info['ttl_seconds']}s",
                inline=True,
            )

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in ping command: {e}")
            await ctx.send(f"❌ Bot error: {e}")

    @commands.command(name="weapon_diag")
    async def weapon_diag(self, ctx, session_id: int = None):
        """🧪 Diagnostic: show weapon_comprehensive_stats aggregates for a session

        Usage: !weapon_diag [session_id]
        If session_id omitted, will use the most recent session in `sessions`.
        """
        try:
            async with aiosqlite.connect(self.bot.db_path) as db:
                # Ensure alias/temp view exists for this connection
                try:
                    await self._ensure_player_name_alias(db)
                except Exception:
                    pass

                if session_id is None:
                    async with db.execute("SELECT id FROM sessions ORDER BY id DESC LIMIT 1") as cur:
                        row = await cur.fetchone()
                        if not row:
                            await ctx.send("❌ No sessions found in DB.")
                            return
                        session_id = row[0]

                # PRAGMA to inspect schema
                pragma = []
                try:
                    async with db.execute("PRAGMA table_info(weapon_comprehensive_stats)") as cur:
                        pragma = await cur.fetchall()
                except Exception as e:
                    pragma = []

                cols = [r[1] for r in pragma]

                # Aggregates
                async with db.execute(
                    "SELECT COUNT(*) as rows, SUM(COALESCE(hits,0)) as total_hits, SUM(COALESCE(shots,0)) as total_shots, SUM(COALESCE(headshots,0)) as total_headshots FROM weapon_comprehensive_stats WHERE session_id = ?",
                    (session_id,)
                ) as cur:
                    agg = await cur.fetchone()

                # Sample rows (limited)
                sample_rows = []
                try:
                    async with db.execute(
                        "SELECT " + (", ".join(cols) if cols else "*") + " FROM weapon_comprehensive_stats WHERE session_id = ? LIMIT 5",
                        (session_id,)
                    ) as cur:
                        sample_rows = await cur.fetchall()
                except Exception:
                    sample_rows = []

                msg_lines = []
                msg_lines.append(f"🔎 weapon_diag for session_id={session_id}")
                msg_lines.append(f"PRAGMA columns: {cols}")
                if agg:
                    rows, hits, shots, headshots = agg
                    msg_lines.append(f"Rows: {rows} | total_hits: {hits or 0} | total_shots: {shots or 0} | total_headshots: {headshots or 0}")
                else:
                    msg_lines.append("No aggregate data available.")

                if sample_rows:
                    msg_lines.append("Sample rows (up to 5):")
                    for r in sample_rows:
                        msg_lines.append(str(r))
                else:
                    msg_lines.append("No sample rows returned (or PRAGMA failed).")

                # Send as a compact message (multiple lines)
                await ctx.send("\n".join(msg_lines))

        except Exception as e:
            logger.error(f"Error in weapon_diag: {e}", exc_info=True)
            await ctx.send(f"❌ weapon_diag failed: {e}")

    @commands.command(name="cache_clear")
    async def cache_clear(self, ctx):
        """🗑️ Clear query cache (Admin only)"""
        try:
            # Check permissions
            if not ctx.author.guild_permissions.manage_guild:
                await ctx.send(
                    "❌ You don't have permission to clear cache. **Required:** Manage Server"
                )
                return

            stats = self.stats_cache.stats()
            self.stats_cache.clear()

            await ctx.send(
                f"✅ Query cache cleared!\n"
                f"**Removed:** {stats['total_keys']} cached entries\n"
                f"💡 Cache will rebuild automatically as commands are used"
            )
            logger.info(f"🗑️ Cache cleared by {ctx.author} ({ctx.author.id})")

        except Exception as e:
            logger.error(f"Error in cache_clear command: {e}")
            await ctx.send(f"❌ Error clearing cache: {e}")

    @commands.command(name="check_achievements", aliases=["check_achivements", "check_achievement"])
    async def check_achievements_cmd(self, ctx, *, player_name: str = None):
        """🏆 Check your achievement progress

        Usage:
        - !check_achievements          → Your achievements (if linked)
        - !check_achievements player   → Check specific player
        - !check_achievements @user    → Check mentioned user
        """
        try:
            player_guid = None
            display_name = None

            async with aiosqlite.connect(self.bot.db_path) as db:
                # Ensure connection has player_name alias if needed
                try:
                    await self._ensure_player_name_alias(db)
                except Exception:
                    pass
                # Handle @mention
                if ctx.message.mentions:
                    mentioned_user = ctx.message.mentions[0]
                    mentioned_id = str(mentioned_user.id)

                    async with db.execute(
                        "SELECT et_guid, et_name FROM player_links WHERE discord_id = ?",
                        (mentioned_id,),
                    ) as cursor:
                        link = await cursor.fetchone()

                    if not link:
                        await ctx.send(
                            f"❌ {mentioned_user.mention} hasn't linked their account yet!"
                        )
                        return

                    player_guid = link[0]
                    display_name = link[1]

                # Handle no arguments - use author's linked account
                elif not player_name:
                    discord_id = str(ctx.author.id)
                    async with db.execute(
                        "SELECT et_guid, et_name FROM player_links WHERE discord_id = ?",
                        (discord_id,),
                    ) as cursor:
                        link = await cursor.fetchone()

                    if not link:
                        await ctx.send(
                            "❌ Please link your account with `!link` or specify a player name!"
                        )
                        return

                    player_guid = link[0]
                    display_name = link[1]

                # Handle player name search
                else:
                    async with db.execute(
                        "SELECT guid, alias FROM player_aliases WHERE LOWER(alias) LIKE LOWER(?) ORDER BY last_seen DESC LIMIT 1",
                        (f"%{player_name}%",),
                    ) as cursor:
                        result = await cursor.fetchone()

                    if not result:
                        await ctx.send(f"❌ Player '{player_name}' not found!")
                        return

                    player_guid = result[0]
                    display_name = result[1]

                # Get player stats
                async with db.execute(
                    """
                    SELECT 
                        SUM(kills) as total_kills,
                        SUM(deaths) as total_deaths,
                        COUNT(DISTINCT session_id) as total_games,
                        CASE 
                            WHEN SUM(deaths) > 0 
                            THEN CAST(SUM(kills) AS REAL) / SUM(deaths)
                            ELSE SUM(kills) 
                        END as overall_kd
                    FROM player_comprehensive_stats
                    WHERE player_guid = ?
                """,
                    (player_guid,),
                ) as cursor:
                    stats = await cursor.fetchone()

                if not stats or stats[0] is None:
                    await ctx.send(f"❌ No stats found for {display_name}!")
                    return

                kills, deaths, games, kd_ratio = stats

                # Build achievement progress embed
                embed = discord.Embed(
                    title=f"🏆 Achievement Progress: {display_name}",
                    color=0xFFD700,
                    timestamp=datetime.now(),
                )

                # Kill achievements
                kill_progress = []
                for threshold, ach in sorted(
                    self.achievements.KILL_MILESTONES.items()
                ):
                    if kills >= threshold:
                        kill_progress.append(
                            f"✅ {ach['emoji']} **{ach['title']}** ({threshold:,} kills)"
                        )
                    else:
                        remaining = threshold - kills
                        kill_progress.append(
                            f"🔒 {ach['emoji']} {ach['title']} - {remaining:,} kills away"
                        )

                embed.add_field(
                    name="💀 Kill Achievements",
                    value="\n".join(kill_progress),
                    inline=False,
                )

                # Game achievements
                game_progress = []
                for threshold, ach in sorted(
                    self.achievements.GAME_MILESTONES.items()
                ):
                    if games >= threshold:
                        game_progress.append(
                            f"✅ {ach['emoji']} **{ach['title']}** ({threshold:,} games)"
                        )
                    else:
                        remaining = threshold - games
                        game_progress.append(
                            f"🔒 {ach['emoji']} {ach['title']} - {remaining:,} games away"
                        )

                embed.add_field(
                    name="🎮 Game Achievements",
                    value="\n".join(game_progress),
                    inline=False,
                )

                # K/D achievements (only if 20+ games)
                if games >= 20:
                    kd_progress = []
                    for threshold, ach in sorted(
                        self.achievements.KD_MILESTONES.items()
                    ):
                        if kd_ratio >= threshold:
                            kd_progress.append(
                                f"✅ {ach['emoji']} **{ach['title']}** ({threshold:.1f} K/D)"
                            )
                        else:
                            needed = threshold - kd_ratio
                            kd_progress.append(
                                f"🔒 {ach['emoji']} {ach['title']} - {needed:.2f} K/D away"
                            )

                    embed.add_field(
                        name="⚔️ K/D Achievements",
                        value="\n".join(kd_progress),
                        inline=False,
                    )
                else:
                    embed.add_field(
                        name="⚔️ K/D Achievements",
                        value=f"🔒 Play {20 - games} more games to unlock K/D achievements",
                        inline=False,
                    )

                # Current stats
                embed.add_field(
                    name="📊 Current Stats",
                    value=f"**Kills:** {kills:,}\n**Games:** {games:,}\n**K/D:** {kd_ratio:.2f}",
                    inline=True,
                )

                embed.set_footer(
                    text=f"Requested by {ctx.author.display_name}"
                )

                await ctx.send(embed=embed)

        except Exception as e:
            logger.error(
                f"Error in check_achievements command: {e}", exc_info=True
            )
            await ctx.send(f"❌ Error checking achievements: {e}")

    @commands.command(name="compare")
    async def compare(self, ctx, player1_name: str, player2_name: str):
        """📊 Compare two players with a visual radar chart

        Usage: !compare player1 player2
        Example: !compare vid SuperBoyY

        Compares: K/D, Accuracy, DPM, Headshots%, Games Played
        """
        try:
            await ctx.send("📊 Generating comparison chart...")

            # Import here to avoid startup overhead. If matplotlib/numpy are
            # missing, fall back to a text-only comparison so the command
            # remains usable without adding dependencies to the runtime.
            has_matplotlib = True
            try:
                import matplotlib
                matplotlib.use("Agg")  # Non-GUI backend
                import matplotlib.pyplot as plt
                import numpy as np
                from pathlib import Path
            except Exception as e:
                logger.warning(
                    "matplotlib/numpy unavailable for compare - using text-only fallback: %s",
                    e,
                )
                has_matplotlib = False
                np = None
                plt = None
                Path = None

            async with aiosqlite.connect(self.bot.db_path) as db:
                # Ensure player_name alias for this command's DB connection
                try:
                    await self._ensure_player_name_alias(db)
                except Exception:
                    pass

                # Helper: get stats when we already have a GUID
                async def get_player_stats_by_guid(player_guid, display_name):
                    # Get comprehensive stats
                    async with db.execute(
                        """
                        SELECT 
                            SUM(kills) as total_kills,
                            SUM(deaths) as total_deaths,
                            COUNT(DISTINCT session_id) as total_games,
                            SUM(damage_given) as total_damage,
                            SUM(time_played_seconds) as total_time,
                            SUM(headshot_kills) as total_headshots
                        FROM player_comprehensive_stats
                        WHERE player_guid = ?
                    """,
                        (player_guid,),
                    ) as cursor:
                        stats = await cursor.fetchone()

                    if not stats or stats[0] is None:
                        return None

                    kills, deaths, games, damage, time_sec, headshots = stats

                    # Get weapon stats for accuracy
                    async with db.execute(
                        """
                        SELECT 
                            SUM(hits) as total_hits,
                            SUM(shots) as total_shots
                        FROM weapon_comprehensive_stats
                        WHERE player_guid = ?
                    """,
                        (player_guid,),
                    ) as cursor:
                        weapon_stats = await cursor.fetchone()

                    hits, shots = weapon_stats if weapon_stats else (0, 0)

                    # Calculate metrics
                    kd = kills / deaths if deaths > 0 else kills
                    accuracy = (hits / shots * 100) if shots > 0 else 0
                    dpm = (damage * 60 / time_sec) if time_sec > 0 else 0
                    hs_pct = (headshots / kills * 100) if kills > 0 else 0

                    return {
                        "name": display_name,
                        "guid": player_guid,
                        "kd": kd,
                        "accuracy": accuracy,
                        "dpm": dpm,
                        "hs_pct": hs_pct,
                        "games": games,
                        "kills": kills,
                    }

                # Function to get player stats (resolves mentions to linked GUIDs)
                async def get_player_stats(player_name):
                    import re

                    if not player_name:
                        return None

                    # If the caller passed a Discord mention like <@1234> or <@!1234>,
                    # resolve it to the linked ET GUID via player_links.
                    m = re.match(r"^<@!?(\d+)>$", player_name.strip())
                    if m:
                        discord_id = m.group(1)
                        async with db.execute(
                            "SELECT et_guid, et_name FROM player_links WHERE discord_id = ?",
                            (discord_id,),
                        ) as cursor:
                            link = await cursor.fetchone()

                        if link:
                            return await get_player_stats_by_guid(link[0], link[1])

                    # Try player_aliases first (name search)
                    async with db.execute(
                        "SELECT guid, alias FROM player_aliases WHERE LOWER(alias) LIKE LOWER(?) ORDER BY last_seen DESC LIMIT 1",
                        (f"%{player_name}%",),
                    ) as cursor:
                        result = await cursor.fetchone()

                    if not result:
                        return None

                    player_guid, display_name = result
                    return await get_player_stats_by_guid(player_guid, display_name)

                # Get stats for both players
                p1_stats = await get_player_stats(player1_name)
                p2_stats = await get_player_stats(player2_name)

                if not p1_stats:
                    await ctx.send(f"❌ Player '{player1_name}' not found!")
                    return

                if not p2_stats:
                    await ctx.send(f"❌ Player '{player2_name}' not found!")
                    return

                # If matplotlib/numpy aren't available, fall back to a
                # text-only comparison embed so the command still works.
                if not has_matplotlib:
                    embed = discord.Embed(
                        title="📊 Player Comparison (No Chart)",
                        description=f"**{p1_stats['name']}** vs **{p2_stats['name']}**",
                        color=0x9B59B6,
                        timestamp=datetime.now(),
                    )

                    embed.add_field(
                        name=f"🎯 {p1_stats['name']}",
                        value=(
                            f"**K/D:** {p1_stats['kd']:.2f}\n"
                            f"**Accuracy:** {p1_stats['accuracy']:.1f}%\n"
                            f"**DPM:** {p1_stats['dpm']:.0f}\n"
                            f"**Headshots:** {p1_stats['hs_pct']:.1f}%\n"
                            f"**Games:** {p1_stats['games']:,}\n"
                            f"**Kills:** {p1_stats['kills']:,}"
                        ),
                        inline=True,
                    )

                    embed.add_field(
                        name=f"🎯 {p2_stats['name']}",
                        value=(
                            f"**K/D:** {p2_stats['kd']:.2f}\n"
                            f"**Accuracy:** {p2_stats['accuracy']:.1f}%\n"
                            f"**DPM:** {p2_stats['dpm']:.0f}\n"
                            f"**Headshots:** {p2_stats['hs_pct']:.1f}%\n"
                            f"**Games:** {p2_stats['games']:,}\n"
                            f"**Kills:** {p2_stats['kills']:,}"
                        ),
                        inline=True,
                    )

                    winners = []
                    if p1_stats["kd"] > p2_stats["kd"]:
                        winners.append(f"🏆 K/D: {p1_stats['name']}")
                    elif p2_stats["kd"] > p1_stats["kd"]:
                        winners.append(f"🏆 K/D: {p2_stats['name']}")
                    else:
                        winners.append("🏆 K/D: Tie")

                    if p1_stats["accuracy"] > p2_stats["accuracy"]:
                        winners.append(f"🎯 Accuracy: {p1_stats['name']}")
                    elif p2_stats["accuracy"] > p1_stats["accuracy"]:
                        winners.append(f"🎯 Accuracy: {p2_stats['name']}")

                    if p1_stats["dpm"] > p2_stats["dpm"]:
                        winners.append(f"💥 DPM: {p1_stats['name']}")
                    elif p2_stats["dpm"] > p1_stats["dpm"]:
                        winners.append(f"💥 DPM: {p2_stats['name']}")

                    embed.add_field(
                        name="🏆 Category Winners",
                        value="\n".join(winners),
                        inline=False,
                    )

                    embed.set_footer(text=f"Requested by {ctx.author.display_name}")
                    await ctx.send(embed=embed)
                    return

                # Create radar chart
                categories = [
                    "K/D Ratio",
                    "Accuracy %",
                    "DPM/100",
                    "Headshot %",
                    "Games/10",
                ]

                # Normalize values for visualization (scale to 0-10)
                p1_values = [
                    min(p1_stats["kd"], 5) * 2,  # K/D (max 5 = score 10)
                    min(p1_stats["accuracy"], 50)
                    / 5,  # Accuracy (50% = score 10)
                    min(p1_stats["dpm"], 1000) / 100,  # DPM (1000 = score 10)
                    min(p1_stats["hs_pct"], 50)
                    / 5,  # Headshot% (50% = score 10)
                    min(p1_stats["games"], 500) / 50,  # Games (500 = score 10)
                ]

                p2_values = [
                    min(p2_stats["kd"], 5) * 2,
                    min(p2_stats["accuracy"], 50) / 5,
                    min(p2_stats["dpm"], 1000) / 100,
                    min(p2_stats["hs_pct"], 50) / 5,
                    min(p2_stats["games"], 500) / 50,
                ]

                # Number of variables
                num_vars = len(categories)

                # Compute angle for each axis
                angles = np.linspace(
                    0, 2 * np.pi, num_vars, endpoint=False
                ).tolist()

                # Complete the circle
                p1_values += p1_values[:1]
                p2_values += p2_values[:1]
                angles += angles[:1]

                # Create figure
                fig, ax = plt.subplots(
                    figsize=(10, 10), subplot_kw=dict(projection="polar")
                )

                # Plot data
                ax.plot(
                    angles,
                    p1_values,
                    "o-",
                    linewidth=2,
                    label=p1_stats["name"],
                    color="#3498db",
                )
                ax.fill(angles, p1_values, alpha=0.25, color="#3498db")

                ax.plot(
                    angles,
                    p2_values,
                    "o-",
                    linewidth=2,
                    label=p2_stats["name"],
                    color="#e74c3c",
                )
                ax.fill(angles, p2_values, alpha=0.25, color="#e74c3c")

                # Fix axis to go in the right order
                ax.set_theta_offset(np.pi / 2)
                ax.set_theta_direction(-1)

                # Draw axis lines for each angle and label
                ax.set_xticks(angles[:-1])
                ax.set_xticklabels(categories, size=12)

                # Set y-axis limits and labels
                ax.set_ylim(0, 10)
                ax.set_yticks([2, 4, 6, 8, 10])
                ax.set_yticklabels(
                    ["20%", "40%", "60%", "80%", "100%"], size=10
                )
                ax.set_rlabel_position(180 / num_vars)

                # Add title and legend
                plt.title(
                    f'Player Comparison\n{p1_stats["name"]} vs {p2_stats["name"]}',
                    size=16,
                    weight="bold",
                    pad=20,
                )
                plt.legend(
                    loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=12
                )

                # Add grid
                ax.grid(True, linestyle="--", alpha=0.7)

                # Save figure
                output_dir = Path("temp")
                output_dir.mkdir(exist_ok=True)
                output_path = (
                    output_dir
                    / f'compare_{p1_stats["guid"][:6]}_{p2_stats["guid"][:6]}.png'
                )

                plt.tight_layout()
                plt.savefig(
                    output_path,
                    dpi=150,
                    bbox_inches="tight",
                    facecolor="white",
                )
                plt.close()

                # Create detailed comparison embed
                embed = discord.Embed(
                    title="📊 Player Comparison",
                    description=f"**{p1_stats['name']}** vs **{p2_stats['name']}**",
                    color=0x9B59B6,
                    timestamp=datetime.now(),
                )

                # Add stats comparison
                embed.add_field(
                    name=f"🎯 {p1_stats['name']}",
                    value=(
                        f"**K/D:** {p1_stats['kd']:.2f}\n"
                        f"**Accuracy:** {p1_stats['accuracy']:.1f}%\n"
                        f"**DPM:** {p1_stats['dpm']:.0f}\n"
                        f"**Headshots:** {p1_stats['hs_pct']:.1f}%\n"
                        f"**Games:** {p1_stats['games']:,}\n"
                        f"**Kills:** {p1_stats['kills']:,}"
                    ),
                    inline=True,
                )

                embed.add_field(
                    name=f"🎯 {p2_stats['name']}",
                    value=(
                        f"**K/D:** {p2_stats['kd']:.2f}\n"
                        f"**Accuracy:** {p2_stats['accuracy']:.1f}%\n"
                        f"**DPM:** {p2_stats['dpm']:.0f}\n"
                        f"**Headshots:** {p2_stats['hs_pct']:.1f}%\n"
                        f"**Games:** {p2_stats['games']:,}\n"
                        f"**Kills:** {p2_stats['kills']:,}"
                    ),
                    inline=True,
                )

                # Determine winner for each category
                winners = []
                if p1_stats["kd"] > p2_stats["kd"]:
                    winners.append(f"🏆 K/D: {p1_stats['name']}")
                elif p2_stats["kd"] > p1_stats["kd"]:
                    winners.append(f"🏆 K/D: {p2_stats['name']}")
                else:
                    winners.append("🏆 K/D: Tie")

                if p1_stats["accuracy"] > p2_stats["accuracy"]:
                    winners.append(f"🎯 Accuracy: {p1_stats['name']}")
                elif p2_stats["accuracy"] > p1_stats["accuracy"]:
                    winners.append(f"🎯 Accuracy: {p2_stats['name']}")

                if p1_stats["dpm"] > p2_stats["dpm"]:
                    winners.append(f"💥 DPM: {p1_stats['name']}")
                elif p2_stats["dpm"] > p1_stats["dpm"]:
                    winners.append(f"💥 DPM: {p2_stats['name']}")

                embed.add_field(
                    name="🏆 Category Winners",
                    value="\n".join(winners),
                    inline=False,
                )

                embed.set_footer(
                    text=f"Requested by {ctx.author.display_name}"
                )

                # Send chart and embed
                file = discord.File(output_path, filename="comparison.png")
                embed.set_image(url="attachment://comparison.png")

                await ctx.send(embed=embed, file=file)

                # Clean up
                try:
                    output_path.unlink()
                except Exception:
                    pass

                logger.info(
                    f"📊 Comparison generated: {p1_stats['name']} vs {p2_stats['name']}"
                )

        except Exception as e:
            logger.error(f"Error in compare command: {e}", exc_info=True)
            await ctx.send(f"❌ Error generating comparison: {e}")

    @commands.command(name="season_info", aliases=["season", "seasons"])
    async def season_info(self, ctx):
        """📅 Show current season information and champions

        Displays:
        - Current season details
        - Days until season end
        - Current season champions
        - All-time champions

        Usage:
        - !season_info → Show season details
        - !season → Short alias
        """
        try:

    
            # Get current season info
            current_season = self.season_manager.get_current_season()
            season_name = self.season_manager.get_season_name()
            days_left = self.season_manager.get_days_until_season_end()
            start_date, end_date = self.season_manager.get_season_dates()

            # Create embed
            embed = discord.Embed(
                title="📅 Season Information",
                description=f"**{season_name}**\n`{current_season}`",
                color=0xFFD700,  # Gold
                timestamp=datetime.now(),
            )

            # Season dates
            embed.add_field(
                name="📆 Season Period",
                value=(
                    f"**Start:** {start_date.strftime('%B %d, %Y')}\n"
                    f"**End:** {end_date.strftime('%B %d, %Y')}\n"
                    f"**Days Remaining:** {days_left} days"
                ),
                inline=False,
            )

            # Get current season champion
            async with aiosqlite.connect(self.bot.db_path) as db:
                # Apply per-connection alias to handle legacy DB column names
                try:
                    await self._ensure_player_name_alias(db)
                except Exception:
                    pass
                season_filter = self.season_manager.get_season_sql_filter()

                # Season kills leader
                season_query = f"""
                    SELECT 
                        (SELECT player_name FROM player_comprehensive_stats 
                         WHERE player_guid = p.player_guid 
                         GROUP BY player_name 
                         ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                        SUM(p.kills) as total_kills,
                        SUM(p.deaths) as total_deaths,
                        COUNT(DISTINCT p.session_id) as games
                    FROM player_comprehensive_stats p
                    JOIN sessions s ON p.session_id = s.id
                    WHERE 1=1 {season_filter}
                    GROUP BY p.player_guid
                    HAVING games > 5
                    ORDER BY total_kills DESC
                    LIMIT 1
                """

                async with db.execute(season_query) as cursor:
                    season_leader = await cursor.fetchone()

                if season_leader:
                    kd = season_leader[1] / max(season_leader[2], 1)
                    embed.add_field(
                        name=f"🏆 {season_name} Champion",
                        value=(
                            f"**{season_leader[0]}**\n"
                            f"Kills: {season_leader[1]:,} | K/D: {kd:.2f}\n"
                            f"Games: {season_leader[3]}"
                        ),
                        inline=False,
                    )

                # All-time kills leader
                alltime_query = """
                    SELECT 
                        (SELECT player_name FROM player_comprehensive_stats 
                         WHERE player_guid = p.player_guid 
                         GROUP BY player_name 
                         ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                        SUM(p.kills) as total_kills,
                        SUM(p.deaths) as total_deaths,
                        COUNT(DISTINCT p.session_id) as games
                    FROM player_comprehensive_stats p
                    GROUP BY p.player_guid
                    HAVING games > 10
                    ORDER BY total_kills DESC
                    LIMIT 1
                """

                async with db.execute(alltime_query) as cursor:
                    alltime_leader = await cursor.fetchone()

                if alltime_leader:
                    kd = alltime_leader[1] / max(alltime_leader[2], 1)
                    embed.add_field(
                        name="👑 All-Time Champion",
                        value=(
                            f"**{alltime_leader[0]}**\n"
                            f"Kills: {alltime_leader[1]:,} | K/D: {kd:.2f}\n"
                            f"Games: {alltime_leader[3]}"
                        ),
                        inline=False,
                    )

            # Footer with usage info
            embed.set_footer(
                text="Use !leaderboard to see full rankings • Seasons reset quarterly"
            )

            await ctx.send(embed=embed)
            logger.info(f"📅 Season info displayed: {season_name}")

        except Exception as e:
            logger.error(f"Error in season_info command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving season information: {e}")

    async def _generate_aggregated_stats(
        self, db, where_clause: str, params: tuple
    ):
        """Helper to query top 6 players aggregated by given WHERE clause.

        Returns list of rows with fields matching the example SQL.
        """
        # Ensure player_name alias exists for this connection
        try:
            await self._ensure_player_name_alias(db)
        except Exception:
            pass

        # Defensive handling: some DB schemas use different round column names
        # and historical column names. Detect available columns and rewrite the
        # round-filter portion of the WHERE clause so we don't reference
        # non-existent columns. This also collapses duplicate round params.
        where = where_clause or "1=1"

        cols = []
        try:
            async with db.execute("PRAGMA table_info(player_comprehensive_stats)") as c:
                info = await c.fetchall()
            cols = [r[1] for r in info]
        except Exception:
            # If PRAGMA fails, fall back to no-op and let the main query run
            cols = []

        round_sub = "(round_number = ? OR round = ? OR round_num = ?)"
        if round_sub in where:
            chosen = None
            if 'round_number' in cols:
                chosen = 'round_number'
            elif 'round' in cols:
                chosen = 'round'
            elif 'round_num' in cols:
                chosen = 'round_num'

            if chosen:
                where = where.replace(round_sub, f"{chosen} = ?")
                # adjust params: collapse three placeholders into one
                before = where_clause.split(round_sub)[0]
                num_q_before = before.count('?')
                p = list(params)
                if len(p) >= num_q_before + 3:
                    new_p = p[:num_q_before] + [p[num_q_before]] + p[num_q_before+3:]
                    params = tuple(new_p)
            else:
                # remove the round filter entirely and drop its params
                where = where.replace(round_sub, "1=1")
                before = where_clause.split(round_sub)[0]
                num_q_before = before.count('?')
                p = list(params)
                if len(p) >= num_q_before + 3:
                    new_p = p[:num_q_before] + p[num_q_before+3:]
                    params = tuple(new_p)

        sql = f"""
            SELECT 
                player_name as player_name,
                SUM(COALESCE(kills,0)) as total_kills,
                SUM(COALESCE(deaths,0)) as total_deaths,
                SUM(COALESCE(gibs,0)) as total_gibs,
                AVG(COALESCE(dpm,0)) as avg_dpm,
                SUM(COALESCE(damage_given,0)) as total_dmg,
                SUM(COALESCE(damage_received,0)) as total_dmr,
                SUM(COALESCE(team_damage_given,0)) as total_tdg,
                SUM(COALESCE(team_damage_received,0)) as total_tdr,
                SUM(COALESCE(time_played_seconds,0))/60 as playtime_mins,
                SUM(COALESCE(denied_playtime,0)) as denied,
                SUM(COALESCE(time_dead_minutes,0)) as dead_mins,
                SUM(COALESCE(times_revived,0)) as revives
            FROM player_comprehensive_stats
            WHERE {where}
            GROUP BY player_name
            ORDER BY total_kills DESC
            LIMIT 6
        """

        try:
            async with db.execute(sql, params) as cursor:
                rows = await cursor.fetchall()
        except sqlite3.OperationalError:
            logger.error("OperationalError executing SQL: %s | params=%s", sql, params)
            try:
                async with db.execute("PRAGMA table_info(player_comprehensive_stats)") as c:
                    info = await c.fetchall()
                logger.error("PRAGMA table_info(player_comprehensive_stats): %s", info)
            except Exception:
                logger.exception("Failed to read PRAGMA table_info during diagnostic")
            try:
                async with db.execute(
                    "SELECT name, sql FROM sqlite_temp_master WHERE type='table'"
                ) as c:
                    temp = await c.fetchall()
                logger.error("sqlite_temp_master (temp objects): %s", temp)
            except Exception:
                logger.exception("Failed to read sqlite_temp_master during diagnostic")
            try:
                async with db.execute("PRAGMA database_list") as c:
                    dbl = await c.fetchall()
                logger.error("PRAGMA database_list: %s", dbl)
            except Exception:
                logger.exception("Failed to read PRAGMA database_list during diagnostic")
            raise

        return rows

    async def _build_12panel_figure(self, rows, title: str, playtime_shared: int = 0):
        """Build a 4x3 matplotlib figure from aggregated rows.

        rows: list of tuples in same order as _generate_aggregated_stats SELECT
        Returns BytesIO buffer with PNG image.
        """
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except Exception:
            raise

        # Unpack rows
        names = [r[0] for r in rows]
        total_kills = [int(r[1] or 0) for r in rows]
        total_deaths = [int(r[2] or 0) for r in rows]
        total_gibs = [int(r[3] or 0) for r in rows]
        avg_dpm = [float(r[4] or 0) for r in rows]
        total_dmg = [int(r[5] or 0) for r in rows]
        total_dmr = [int(r[6] or 0) for r in rows]
        total_tdg = [int(r[7] or 0) for r in rows]
        total_tdr = [int(r[8] or 0) for r in rows]
        playtime = [int(r[9] or 0) for r in rows]
        denied = [int(r[10] or 0) for r in rows]
        dead_mins = [float(r[11] or 0) for r in rows]
        revives = [int(r[12] or 0) for r in rows]

        fig, axes = plt.subplots(4, 3, figsize=(18, 16))
        fig.suptitle(title, fontsize=18, fontweight="bold")

        # Column 1: Combat
        cmap = [
            (total_kills, "Kills", "#57F287"),
            (total_deaths, "Deaths", "#ED4245"),
            (total_gibs, "Gibs", "#9B59B6"),
            (avg_dpm, "DPM", "#FEE75C"),
        ]

        # Column 2: Time & Support
        c2 = [
            (denied, "Playtime Denied", "#E67E22"),
            (dead_mins, "Time Dead (m)", "#EB459E"),
            (revives, "Revives", "#3498DB"),
            ([], "", ""),
        ]

        # Column 3: Damage
        c3 = [
            (total_dmg, "Damage Given", "#00FF00"),
            (total_dmr, "Damage Received", "#FF6B6B"),
            (total_tdg, "Team Damage Given", "#C0392B"),
            (total_tdr, "Team Damage Received", "#8B0000"),
        ]

        # helper to plot a subplot
        def _plot(ax, vals, label, color):
            if not vals:
                ax.axis("off")
                return
            ax.bar(names, vals, color=color)
            ax.set_title(label)
            ax.set_xticks(range(len(names)))
            ax.set_xticklabels(names, rotation=45, ha="right")

        # Fill grid
        for row_idx in range(4):
            _plot(axes[row_idx][0], *cmap[row_idx])
            _plot(axes[row_idx][1], *c2[row_idx])
            _plot(axes[row_idx][2], *c3[row_idx])

        # Add playtime subtitle on column 2 top
        if playtime_shared:
            fig.text(0.38, 0.96, f"Playtime: {playtime_shared} minutes", ha="center", fontsize=12)

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        buf.seek(0)
        plt.close()
        return buf

    async def generate_map_graphs(self, session_id: int, map_name: str):
        """Generate per-map aggregated graphs (top 6 players). Returns BytesIO buffer."""
        try:
            import matplotlib

            matplotlib.use("Agg")
        except Exception:
            raise

        async with aiosqlite.connect(self.bot.db_path) as db:
            try:
                await self._enable_sql_diag(db)
            except Exception:
                pass

            where = "session_id = ? AND map_name = ?"
            params = (session_id, map_name)
            rows = await self._generate_aggregated_stats(db, where, params)

            if not rows:
                return None

            # compute shared playtime as max of playtime_mins
            playtimes = [int(r[9] or 0) for r in rows]
            shared_play = int(max(playtimes)) if playtimes else 0

            title = f"Map Stats: {map_name} (Session {session_id})"
            buf = await self._build_12panel_figure(rows, title, playtime_shared=shared_play)
            return buf

    async def generate_session_graphs(self, session_id: int):
        """Generate session-wide aggregated graphs (all maps combined). Returns BytesIO buffer."""
        try:
            import matplotlib

            matplotlib.use("Agg")
        except Exception:
            raise

        async with aiosqlite.connect(self.bot.db_path) as db:
            try:
                await self._enable_sql_diag(db)
            except Exception:
                pass

            where = "session_id = ?"
            params = (session_id,)
            rows = await self._generate_aggregated_stats(db, where, params)

            if not rows:
                return None

            playtimes = [int(r[9] or 0) for r in rows]
            shared_play = int(max(playtimes)) if playtimes else 0
            title = f"Session Stats: Session {session_id}"
            buf = await self._build_12panel_figure(rows, title, playtime_shared=shared_play)
            return buf

    async def generate_round_graphs(self, session_id: int, round_num: int, map_name: str = None):
        """Generate round-level aggregated graphs. If map_name provided, filter by map too."""
        try:
            import matplotlib

            matplotlib.use("Agg")
        except Exception:
            raise

        async with aiosqlite.connect(self.bot.db_path) as db:
            try:
                await self._enable_sql_diag(db)
            except Exception:
                pass

            # Attempt to filter by common round column names; prefer round_number
            # Build where clause
            if map_name:
                where = "session_id = ? AND map_name = ? AND (round_number = ? OR round = ? OR round_num = ?)"
                params = (session_id, map_name, round_num, round_num, round_num)
            else:
                where = "session_id = ? AND (round_number = ? OR round = ? OR round_num = ?)"
                params = (session_id, round_num, round_num, round_num)

            rows = await self._generate_aggregated_stats(db, where, params)
            if not rows:
                return None
            playtimes = [int(r[9] or 0) for r in rows]
            shared_play = int(max(playtimes)) if playtimes else 0
            title = f"Round Stats: Session {session_id} - Round {round_num}"
            if map_name:
                title += f" - {map_name}"
            buf = await self._build_12panel_figure(rows, title, playtime_shared=shared_play)
            return buf

        async def _post_retro_round_complete(self, ctx, stats_file_path: str, map_name: str, round_num: int, session_id: int = None):
            """Unified poster for a completed round.

            - Generates the retro PNG using bot.retro_viz.create_round_visualization
            - Attempts to generate primary + detailed text stats via bot.retro_text_stats.generate_text_stats
            - Posts the PNG and any text outputs to the provided context

            Returns True if posting succeeded (PNG posted), False on failure.
            """
            try:
                # Import here to keep startup light and allow graceful fallback
                from bot.retro_viz import create_round_visualization
            except Exception:
                logger.exception("retro_viz import failed - cannot generate retro visualization")
                return False

            try:
                fig = create_round_visualization(stats_file_path)
                import matplotlib.pyplot as plt
                import io

                buf = io.BytesIO()
                fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
                buf.seek(0)
                try:
                    plt.close(fig)
                except Exception:
                    pass

                fname = f"{map_name}_round{round_num}_retro.png"
                await ctx.send(file=discord.File(buf, filename=fname))
                await asyncio.sleep(1.0)
            except Exception:
                logger.exception("Failed to build/send retro PNG for %s", stats_file_path)
                return False

            # Try to produce text statistics (primary + detailed) if the helper exists
            primary_text = None
            detailed_text = None
            try:
                from bot.retro_text_stats import generate_text_stats

                try:
                    primary_text, detailed_text = generate_text_stats(stats_file_path)
                except Exception:
                    logger.exception("retro_text_stats.generate_text_stats failed for %s", stats_file_path)
            except Exception:
                # Not fatal; text stats are optional. Log and continue.
                logger.debug("bot.retro_text_stats not available; skipping text stats for %s", stats_file_path)

            try:
                import io as _io

                if primary_text:
                    # If reasonably short, send as code block embed; otherwise attach as file
                    if len(primary_text) < 1900:
                        await ctx.send(f"```\n{primary_text}\n```")
                    else:
                        pbuf = _io.BytesIO(primary_text.encode("utf-8"))
                        pbuf.seek(0)
                        await ctx.send(file=discord.File(pbuf, filename=f"{map_name}_round{round_num}_primary.txt"))
                    await asyncio.sleep(0.6)

                if detailed_text:
                    if len(detailed_text) < 1900:
                        await ctx.send(f"```\n{detailed_text}\n```")
                    else:
                        dbuf = _io.BytesIO(detailed_text.encode("utf-8"))
                        dbuf.seek(0)
                        await ctx.send(file=discord.File(dbuf, filename=f"{map_name}_round{round_num}_detailed.txt"))
                    await asyncio.sleep(0.6)
            except Exception:
                logger.exception("Failed to send text stats for %s", stats_file_path)

            return True

    @commands.command(name="map_stats")
    async def map_stats(self, ctx, session_id: int, *, map_name: str):
        """!map_stats <session_id> <map_name> - generate per-map graphs"""
        try:
            await ctx.send("📊 Generating map stats chart...")
            buf = await self.generate_map_graphs(session_id, map_name)
            if not buf:
                await ctx.send("❌ No data found for that map/session.")
                return
            fname = f"map_stats_{session_id}_{map_name}.png"
            file = discord.File(buf, filename=fname)
            embed = discord.Embed(title=f"Map Stats: {map_name}", color=0x9B59B6)
            embed.set_image(url="attachment://%s" % fname)
            await ctx.send(embed=embed, file=file)
        except Exception as e:
            logger.error(f"Error in map_stats: {e}", exc_info=True)
            await ctx.send(f"❌ Error generating map stats: {e}")

    @commands.command(name="session_stats")
    async def session_stats(self, ctx, session_id: int = None):
        """!session_stats [session_id] - generate session-wide graphs (defaults to last session)"""
        try:
            if session_id is None:
                # find last session
                async with aiosqlite.connect(self.bot.db_path) as db:
                    try:
                        await self._ensure_player_name_alias(db)
                    except Exception:
                        pass
                    async with db.execute("SELECT id FROM sessions ORDER BY id DESC LIMIT 1") as cur:
                        row = await cur.fetchone()
                        if not row:
                            await ctx.send("❌ No sessions found in DB.")
                            return
                        session_id = row[0]

            await ctx.send("📊 Generating session stats chart...")
            buf = await self.generate_session_graphs(session_id)
            if not buf:
                await ctx.send("❌ No data found for that session.")
                return
            fname = f"session_stats_{session_id}.png"
            file = discord.File(buf, filename=fname)
            embed = discord.Embed(title=f"Session Stats: {session_id}", color=0x9B59B6)
            embed.set_image(url="attachment://%s" % fname)
            await ctx.send(embed=embed, file=file)
        except Exception as e:
            logger.error(f"Error in session_stats: {e}", exc_info=True)
            await ctx.send(f"❌ Error generating session stats: {e}")
    
    @commands.command(name="round_stats")
    async def round_stats(self, ctx, session_id: int, round_num: int, *, map_name: str = None):
        """!round_stats <session_id> <round_num> [map_name] - generate per-round graphs"""
        try:
            await ctx.send("📊 Generating round stats chart...")
            buf = await self.generate_round_graphs(session_id, round_num, map_name)
            if not buf:
                await ctx.send("❌ No data found for that round/session.")
                return
            mn = map_name or "all_maps"
            fname = f"round_stats_{session_id}_r{round_num}_{mn}.png"
            file = discord.File(buf, filename=fname)
            embed = discord.Embed(title=f"Round Stats: Session {session_id} Round {round_num}", color=0x9B59B6)
            embed.set_image(url="attachment://%s" % fname)
            await ctx.send(embed=embed, file=file)
        except Exception as e:
            logger.error(f"Error in round_stats: {e}", exc_info=True)
            await ctx.send(f"❌ Error generating round stats: {e}")
    

    @commands.command(name="help_command")
    async def help_command(self, ctx):
        """📚 Show all available commands"""
        embed = discord.Embed(
            title="🚀 Ultimate ET:Legacy Bot Commands",
            description="**Use `!` prefix for all commands** (e.g., `!ping`, not `/ping`)",
            color=0x0099FF,
        )

        embed.add_field(
            name="🎬 Session Management",
            value="• `!session_start [map]` - Start new session\\n• `!session_end` - End current session",
            inline=False,
        )

        embed.add_field(
            name="� Stats Commands",
            value="• `!stats [player]` - Player statistics\\n• `!leaderboard [type]` - Top players\\n• `!session [date]` - Session details",
            inline=False,
        )

        embed.add_field(
            name="�🔧 System",
            value="• `!ping` - Bot status\\n• `!help_command` - This help",
            inline=False,
        )

        await ctx.send(embed=embed)

    @commands.command(name="stats")
    async def stats(self, ctx, *, player_name: str = None):
        """📊 Show detailed player statistics

        Usage:
        - !stats              → Your stats (if linked)
        - !stats playerName   → Search by name
        - !stats @user        → Stats for mentioned Discord user
        """
        try:
            player_guid = None
            primary_name = None

            # Open ONE database connection for the entire command
            async with aiosqlite.connect(self.bot.db_path) as db:
                # Create TEMP VIEW alias early in the connection if needed
                try:
                    await self._ensure_player_name_alias(db)
                except Exception:
                    pass
                # Enable SQL diagnostics for this connection to capture details if
                # an OperationalError occurs while running queries in this command.
                try:
                    await self._enable_sql_diag(db)
                except Exception:
                    pass
                # === SCENARIO 1: @MENTION - Look up linked Discord user ===
                if ctx.message.mentions:
                    mentioned_user = ctx.message.mentions[0]
                    mentioned_id = str(mentioned_user.id)

                    async with db.execute(
                        """
                        SELECT et_guid, et_name FROM player_links
                        WHERE discord_id = ?
                    """,
                        (mentioned_id,),
                    ) as cursor:
                        link = await cursor.fetchone()

                    if not link:
                        # User not linked - helpful message
                        embed = discord.Embed(
                            title="⚠️ Account Not Linked",
                            description=(
                                f"{mentioned_user.mention} hasn't linked their "
                                f"ET:Legacy account yet!"
                            ),
                            color=0xFFA500,
                        )
                        embed.add_field(
                            name="How to Link",
                            value=(
                                "• `!link` - Search for your player\n"
                                "• `!link <name>` - Link by name\n"
                                "• `!link <GUID>` - Link with GUID"
                            ),
                            inline=False,
                        )
                        embed.add_field(
                            name="Admin Help",
                            value=(
                                f"Admins can help link with:\n"
                                f"`!link {mentioned_user.mention} <GUID>`"
                            ),
                            inline=False,
                        )
                        await ctx.send(embed=embed)
                        return

                    player_guid = link[0]
                    primary_name = link[1]
                    logger.info(
                        f"Stats via @mention: {ctx.author} looked up "
                        f"{mentioned_user} (GUID: {player_guid})"
                    )

                # === SCENARIO 2: NO ARGS - Use author's linked account ===
                elif not player_name:
                    discord_id = str(ctx.author.id)
                    async with db.execute(
                        """
                        SELECT et_guid, et_name FROM player_links
                        WHERE discord_id = ?
                    """,
                        (discord_id,),
                    ) as cursor:
                        link = await cursor.fetchone()

                    if not link:
                        await ctx.send(
                            "❌ Please specify a player name or link your "
                            "account with `!link`"
                        )
                        return

                    player_guid = link[0]
                    primary_name = link[1]

                # === SCENARIO 3: NAME SEARCH - Traditional lookup ===
                else:
                    # Try exact match in player_links first
                    async with db.execute(
                        """
                        SELECT et_guid, et_name FROM player_links
                        WHERE LOWER(et_name) = LOWER(?)
                        LIMIT 1
                    """,
                        (player_name,),
                    ) as cursor:
                        link = await cursor.fetchone()

                    if link:
                        player_guid = link[0]
                        primary_name = link[1]
                    else:
                        # Search in player_aliases (uses 'guid' and 'alias' columns)
                        async with db.execute(
                            """
                            SELECT guid, alias
                            FROM player_aliases
                            WHERE LOWER(alias) LIKE LOWER(?)
                            ORDER BY last_seen DESC
                            LIMIT 1
                        """,
                            (f"%{player_name}%",),
                        ) as cursor:
                            alias_result = await cursor.fetchone()

                        if alias_result:
                            player_guid = alias_result[0]
                            primary_name = alias_result[1]
                        else:
                            # Fallback to player_comprehensive_stats
                            async with db.execute(
                                """
                                SELECT player_guid, player_name
                                FROM player_comprehensive_stats
                                WHERE LOWER(player_name) LIKE LOWER(?)
                                GROUP BY player_guid
                                LIMIT 1
                            """,
                                (f"%{player_name}%",),
                            ) as cursor:
                                result = await cursor.fetchone()
                                if not result:
                                    await ctx.send(
                                        f"❌ Player '{player_name}' not found."
                                    )
                                    return
                                player_guid = result[0]
                                primary_name = result[1]

                # === NOW WE HAVE player_guid AND primary_name - Get Stats ===

                # 🚀 TRY CACHE FIRST
                cache_key = f"stats_{player_guid}"
                cached_data = self.stats_cache.get(cache_key)

                if cached_data:
                    # Use cached stats
                    overall, weapon_overall, fav_weapons, recent = cached_data
                    logger.info(f"📦 Cache HIT: {primary_name}")
                else:
                    # Cache MISS - Query database
                    logger.info(f"💾 Cache MISS: {primary_name} - querying DB")

                    # Get overall stats
                    async with db.execute(
                        """
                        SELECT
                            COUNT(DISTINCT session_id) as total_games,
                            SUM(kills) as total_kills,
                            SUM(deaths) as total_deaths,
                            SUM(damage_given) as total_damage,
                            SUM(damage_received) as total_damage_received,
                            SUM(headshot_kills) as total_headshots,
                            CASE
                                WHEN SUM(time_played_seconds) > 0
                                THEN (SUM(damage_given) * 60.0) / SUM(time_played_seconds)
                                ELSE 0
                            END as weighted_dpm,
                            AVG(kd_ratio) as avg_kd
                        FROM player_comprehensive_stats
                        WHERE player_guid = ?
                    """,
                        (player_guid,),
                    ) as cursor:
                        overall = await cursor.fetchone()

                    # Get weapon stats with accuracy
                    async with db.execute(
                        """
                        SELECT
                            SUM(w.hits) as total_hits,
                            SUM(w.shots) as total_shots,
                            SUM(w.headshots) as total_hs
                        FROM weapon_comprehensive_stats w
                        WHERE w.player_guid = ?
                    """,
                        (player_guid,),
                    ) as cursor:
                        weapon_overall = await cursor.fetchone()

                    # Get favorite weapons
                    async with db.execute(
                        """
                        SELECT weapon_name, SUM(kills) as total_kills
                        FROM weapon_comprehensive_stats
                        WHERE player_guid = ?
                        GROUP BY weapon_name
                        ORDER BY total_kills DESC
                        LIMIT 3
                    """,
                        (player_guid,),
                    ) as cursor:
                        fav_weapons = await cursor.fetchall()

                    # Get recent activity
                    async with db.execute(
                        """
                        SELECT s.session_date, s.map_name, p.kills, p.deaths
                        FROM player_comprehensive_stats p
                        JOIN sessions s ON p.session_id = s.id
                        WHERE p.player_guid = ?
                        ORDER BY s.session_date DESC
                        LIMIT 3
                    """,
                        (player_guid,),
                    ) as cursor:
                        recent = await cursor.fetchall()

                    # 💾 STORE IN CACHE
                    self.stats_cache.set(
                        cache_key,
                        (overall, weapon_overall, fav_weapons, recent),
                    )
                    logger.info(f"💾 Cached stats for {primary_name}")

                # Calculate stats
                (
                    games,
                    kills,
                    deaths,
                    dmg,
                    dmg_recv,
                    hs,
                    avg_dpm,
                    avg_kd,
                ) = overall
                hits, shots, hs_weapon = (
                    weapon_overall if weapon_overall else (0, 0, 0)
                )

                kd_ratio = kills / deaths if deaths > 0 else kills
                accuracy = (hits / shots * 100) if shots > 0 else 0
                hs_pct = (hs / hits * 100) if hits > 0 else 0

                # Build embed
                embed = discord.Embed(
                    title=f"📊 Stats for {primary_name}",
                    color=0x0099FF,
                    timestamp=datetime.now(),
                )

                embed.add_field(
                    name="🎮 Overview",
                    value=(
                        f"**Games Played:** {games:,}\\n**K/D Ratio:** {kd_ratio:.2f}\\n**Avg DPM:** {avg_dpm:.1f}"
                        if avg_dpm
                        else "0.0"
                    ),
                    inline=True,
                )

                embed.add_field(
                    name="⚔️ Combat",
                    value=f"**Kills:** {kills:,}\\n**Deaths:** {deaths:,}\\n**Headshots:** {hs:,} ({hs_pct:.1f}%)",
                    inline=True,
                )

                embed.add_field(
                    name="🎯 Accuracy",
                    value=f"**Overall:** {accuracy:.1f}%\\n**Damage Given:** {dmg:,}\\n**Damage Taken:** {dmg_recv:,}",
                    inline=True,
                )

                if fav_weapons:
                    weapons_text = "\\n".join(
                        [
                            f"**{w[0].replace('WS_', '').title()}:** {w[1]:,} kills"
                            for w in fav_weapons
                        ]
                    )
                    embed.add_field(
                        name="🔫 Favorite Weapons",
                        value=weapons_text,
                        inline=False,
                    )

                if recent:
                    recent_text = "\\n".join(
                        [
                            f"`{r[0]}` **{r[1]}** - {r[2]}K/{r[3]}D"
                            for r in recent
                        ]
                    )
                    embed.add_field(
                        name="📅 Recent Matches",
                        value=recent_text,
                        inline=False,
                    )

                # Get aliases for footer
                async with db.execute(
                    """
                    SELECT alias
                    FROM player_aliases
                    WHERE guid = ? AND LOWER(alias) != LOWER(?)
                    ORDER BY last_seen DESC, times_seen DESC
                    LIMIT 3
                """,
                    (player_guid, primary_name),
                ) as cursor:
                    aliases = await cursor.fetchall()

                # Build footer with GUID and aliases
                footer_text = f"GUID: {player_guid}"
                if aliases:
                    alias_names = ", ".join([a[0] for a in aliases])
                    footer_text += f" | Also known as: {alias_names}"

                embed.set_footer(text=footer_text)
                await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in stats command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving stats: {e}")

    @commands.command(
        name="last_session_compact", aliases=[]
    )
    async def last_session_compact(self, ctx, subcommand: str = None):
        """🎮 Show the most recent session/match

        Usage:
        - !last_session      → Quick session summary
        - !last_session more → Detailed analytics (graphs, weapons, DPM)
        """
        try:
            # Always send a tiny help hint so users know available subcommands
            try:
                await self._send_last_session_help(ctx)
            except Exception:
                # Non-fatal if sending the hint fails
                pass
            async with aiosqlite.connect(self.bot.db_path) as db:
                # Get most recent session date
                async with db.execute(
                    """
                    SELECT DISTINCT DATE(session_date) as date
                    FROM player_comprehensive_stats
                    ORDER BY date DESC
                    LIMIT 1
                """
                ) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        await ctx.send("❌ No sessions found")
                        return
                    latest_date = row[0]

                # Get all session IDs for this date
                async with db.execute(
                    """
                    SELECT id, map_name, round_number, session_date
                    FROM sessions
                    WHERE DATE(session_date) = ?
                    ORDER BY id ASC
                    """,
                    (latest_date,),
                ) as cursor:
                    sessions = await cursor.fetchall()

                if not sessions:
                    await ctx.send("❌ No sessions found for latest date")
                    return

                session_ids = [s[0] for s in sessions]
                session_ids_str = ",".join("?" * len(session_ids))

                # Use the Cog-level _log_and_send helper (defined on the Cog) and
                # the module-level _split_chunks helper for chunking.

                # If no subcommand: show compact summary
                if not subcommand:
                    query = f"""
                        SELECT COUNT(DISTINCT player_guid)
                        FROM player_comprehensive_stats
                        WHERE session_id IN ({session_ids_str})
                    """
                    async with db.execute(query, session_ids) as cursor:
                        player_count = (await cursor.fetchone())[0]

                    query = f"""
                        SELECT COUNT(DISTINCT session_id) / 2 as total_maps,
                               COUNT(DISTINCT session_id) as total_rounds
                        FROM player_comprehensive_stats
                        WHERE session_id IN ({session_ids_str})
                    """
                    async with db.execute(query, session_ids) as cursor:
                        result = await cursor.fetchone()
                        total_maps, total_rounds = result

                    # Try to get hardcoded teams, but be tolerant if helper missing
                    try:
                        hardcoded_teams = await self.get_hardcoded_teams(
                            db, latest_date
                        )
                    except Exception:
                        hardcoded_teams = []

                    team_1_name, team_2_name, team_1_score, team_2_score = (
                        "Team 1",
                        "Team 2",
                        0,
                        0,
                    )
                    if hardcoded_teams:
                        team_1_name = (
                            hardcoded_teams[0][0]
                            if hardcoded_teams
                            else "Team 1"
                        )
                        team_2_name = (
                            hardcoded_teams[0][1]
                            if len(hardcoded_teams[0]) > 1
                            else "Team 2"
                        )

                        async with db.execute(
                            f"""
                            SELECT map_name, round_number, team
                            FROM player_comprehensive_stats
                            WHERE session_id IN ({session_ids_str})
                            AND map_name IS NOT NULL
                            GROUP BY session_id, team
                        """,
                            session_ids,
                        ) as cursor:
                            round_results = await cursor.fetchall()

                        for map_name, round_num, team in round_results:
                            if team == 1:
                                team_1_score += 0.5
                            elif team == 2:
                                team_2_score += 0.5

                    # Aggregate player data
                    query = f"""
                        SELECT p.player_name,
                               SUM(p.kills) as kills,
                               SUM(p.deaths) as deaths,
                               CASE
                                   WHEN SUM(p.time_played_seconds) > 0
                                   THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                                   ELSE 0
                               END as weighted_dpm,
                               COALESCE(SUM(w.hits), 0) as total_hits,
                               COALESCE(SUM(w.shots), 0) as total_shots,
                               COALESCE(SUM(w.headshots), 0) as total_headshots,
                               SUM(p.headshot_kills) as headshot_kills,
                               SUM(p.time_played_seconds) as total_seconds,
                               CAST(SUM(p.time_played_seconds * p.time_dead_ratio / 100.0) AS INTEGER) as total_time_dead
                        FROM player_comprehensive_stats p
                        LEFT JOIN (
                            SELECT session_id, player_guid,
                                   SUM(hits) as hits,
                                   SUM(shots) as shots,
                                   SUM(headshots) as headshots
                            FROM weapon_comprehensive_stats
                            WHERE weapon_name NOT IN ('WS_GRENADE', 'WS_SYRINGE', 'WS_DYNAMITE', 'WS_AIRSTRIKE', 'WS_ARTILLERY', 'WS_SATCHEL', 'WS_LANDMINE')
                            GROUP BY session_id, player_guid
                        ) w ON p.session_id = w.session_id AND p.player_guid = w.player_guid
                        WHERE p.session_id IN ({session_ids_str})
                        GROUP BY p.player_name
                        ORDER BY kills DESC
                    """
                    async with db.execute(query, session_ids) as cursor:
                        all_players = await cursor.fetchall()

                    maps_played = total_maps
                    rounds_played = len(sessions)

                    description = (
                        f"**{maps_played} maps** • **{rounds_played} rounds** • "
                        f"**{player_count} players**"
                    )
                    if team_1_score > 0 or team_2_score > 0:
                        winner_icon = (
                            "🏆"
                            if team_1_score > team_2_score
                            else ("🏆" if team_2_score > team_1_score else "🤝")
                        )
                        description += (
                            f"\n\n**🎯 FINAL SCORE:** {winner_icon}\n"
                        )
                        description += (
                            f"**{team_1_name}:** {team_1_score} points\n"
                        )
                        description += (
                            f"**{team_2_name}:** {team_2_score} points"
                        )
                        if team_1_score == team_2_score:
                            description += " *(TIE)*"

                    embed1 = discord.Embed(
                        title=f"📊 Session Summary: {latest_date}",
                        description=description,
                        color=0x5865F2,
                        timestamp=datetime.now(),
                    )

                    # Maps list
                    maps_text = ""
                    map_play_counts = {}
                    for (
                        session_id,
                        map_name,
                        round_num,
                        actual_time,
                    ) in sessions:
                        if round_num == 2:
                            map_play_counts[map_name] = (
                                map_play_counts.get(map_name, 0) + 1
                            )

                    for map_name, plays in map_play_counts.items():
                        rounds = plays * 2
                        maps_text += f"• **{map_name}** ({rounds} rounds)\n"

                    if maps_text:
                        embed1.add_field(
                            name="🗺️ Maps Played",
                            value=maps_text,
                            inline=False,
                        )

                    # Top players
                    if all_players:
                        medals = ["🥇", "🥈", "🥉"]
                        # Build lines for each player entry so we can chunk safely
                        player_lines = []
                        for i, player in enumerate(all_players):
                            (
                                name,
                                kills,
                                deaths,
                                dpm,
                                hits,
                                shots,
                                total_hs,
                                hsk,
                                total_seconds,
                                total_time_dead,
                            ) = player
                            kd_ratio = (
                                kills / deaths
                                if deaths and deaths > 0
                                else (kills or 0)
                            )
                            acc = (
                                (hits / shots * 100)
                                if shots and shots > 0
                                else 0
                            )
                            hsk_rate = (
                                (hsk / kills * 100)
                                if kills and kills > 0
                                else 0
                            )
                            hs_rate = (
                                (total_hs / hits * 100)
                                if hits and hits > 0
                                else 0
                            )
                            hours = total_seconds // 3600
                            minutes = (total_seconds % 3600) // 60
                            time_display = (
                                f"{hours}h{minutes}m"
                                if hours > 0
                                else f"{minutes}m"
                            )
                            dead_hours = total_time_dead // 3600
                            dead_minutes = (total_time_dead % 3600) // 60
                            time_dead_display = (
                                f"{dead_hours}h{dead_minutes}m"
                                if dead_hours > 0
                                else f"{dead_minutes}m"
                            )
                            medal = medals[i] if i < 3 else f"{i+1}."
                            entry = (
                                f"{medal} **{name}**\n"
                                f"`{kills}K/{deaths}D ({kd_ratio:.2f})` • `{dpm:.0f} DPM` • `{acc:.1f}% ACC ({hits}/{shots})`\n"
                                f"`{hsk} HSK ({hsk_rate:.1f}%)` • `{total_hs} HS ({hs_rate:.1f}%)` • ⏱️ `{time_display}` • 💀 `{time_dead_display}`\n\n"
                            )
                            player_lines.append(entry)

                        # Chunk the player_lines into field-sized strings (<1024 chars)
                        chunks = []
                        current = ""
                        for line in player_lines:
                            if len(current) + len(line) > 900:  # keep buffer
                                chunks.append(current.rstrip())
                                current = line
                            else:
                                current += line
                        if current:
                            chunks.append(current.rstrip())

                        # If too many fields would be created for a single embed, split across embeds
                        # Start with embed1 as the first; if more chunks exist, create continuation embeds
                        field_count = 0
                        max_fields = 25
                        embeds_to_send = [embed1]
                        current_embed = embed1

                        for idx, chunk in enumerate(chunks):
                            # If current embed would exceed field limit, create a new embed
                            if field_count >= max_fields:
                                new_embed = discord.Embed(
                                    title="📊 Session Summary (continued)",
                                    description="Additional players (continued)",
                                    color=0x5865F2,
                                    timestamp=datetime.now(),
                                )
                                embeds_to_send.append(new_embed)
                                current_embed = new_embed
                                field_count = 0

                            name = (
                                "🏆 All Players"
                                if idx == 0
                                else f"🏆 All Players (cont. {idx+1})"
                            )
                            current_embed.add_field(
                                name=name, value=chunk, inline=False
                            )
                            field_count += 1

                        # If there are multiple embeds, send them sequentially (caller code will send embed1 now)
                        # Store embeds_to_send on the context for the caller to send after embed1
                        # We'll attach them to ctx._last_session_continuation for later sending
                        ctx._last_session_continuation = embeds_to_send[1:]

                    embed1.set_footer(
                        text="💡 Use !last_session more for detailed analytics (graphs, weapons, DPM)"
                    )
                    await ctx.send(embed=embed1)
                    return

                # Detailed analytics
                if subcommand and subcommand.lower() == "more":
                    await ctx.send("🔄 **Loading detailed analytics...**")
                    # (Detailed analytics implementation is large; reuse provided logic)
                    # For brevity keep the existing approach from the supplied fix file
                    # We'll replicate the key parts (DPM, Weapon Mastery, Graphs)

                    # Get player count
                    query = f"""
                        SELECT COUNT(DISTINCT player_guid)
                        FROM player_comprehensive_stats
                        WHERE session_id IN ({session_ids_str})
                    """
                    async with db.execute(query, session_ids) as cursor:
                        player_count = (await cursor.fetchone())[0]

                    # All players detailed
                    query = f"""
                        SELECT p.player_name,
                               SUM(p.kills) as kills,
                               SUM(p.deaths) as deaths,
                               CASE
                                   WHEN SUM(p.time_played_seconds) > 0
                                   THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                                   ELSE 0
                               END as weighted_dpm,
                               COALESCE(SUM(w.hits), 0) as total_hits,
                               COALESCE(SUM(w.shots), 0) as total_shots,
                               COALESCE(SUM(w.headshots), 0) as total_headshots,
                               SUM(p.headshot_kills) as headshot_kills,
                               SUM(p.time_played_seconds) as total_seconds,
                               CAST(SUM(p.time_played_seconds * p.time_dead_ratio / 100.0) AS INTEGER) as total_time_dead,
                               SUM(p.damage_given) as total_damage,
                               SUM(p.time_played_seconds * (100 - p.time_dead_ratio) / 100.0) as time_alive,
                               SUM(p.denied_playtime) as denied_playtime
                        FROM player_comprehensive_stats p
                        LEFT JOIN (
                            SELECT session_id, player_guid,
                                   SUM(hits) as hits,
                                   SUM(shots) as shots,
                                   SUM(headshots) as headshots
                            FROM weapon_comprehensive_stats
                            WHERE weapon_name NOT IN ('WS_GRENADE', 'WS_SYRINGE', 'WS_DYNAMITE', 'WS_AIRSTRIKE', 'WS_ARTILLERY', 'WS_SATCHEL', 'WS_LANDMINE')
                            GROUP BY session_id, player_guid
                        ) w ON p.session_id = w.session_id AND p.player_guid = w.player_guid
                        WHERE p.session_id IN ({session_ids_str})
                        GROUP BY p.player_name
                        ORDER BY kills DESC
                    """
                    async with db.execute(query, session_ids) as cursor:
                        all_players_detailed = await cursor.fetchall()

                    # Player weapons
                    query = f"""
                        SELECT p.player_name, w.weapon_name,
                               SUM(w.kills) as weapon_kills,
                               SUM(w.hits) as hits,
                               SUM(w.shots) as shots,
                               SUM(w.headshots) as headshots
                        FROM weapon_comprehensive_stats w
                        JOIN player_comprehensive_stats p
                            ON w.session_id = p.session_id
                            AND w.player_guid = p.player_guid
                        WHERE w.session_id IN ({session_ids_str})
                        GROUP BY p.player_name, w.weapon_name
                        HAVING weapon_kills > 0
                        ORDER BY p.player_name, weapon_kills DESC
                    """
                    async with db.execute(query, session_ids) as cursor:
                        player_weapons = await cursor.fetchall()

                    # DPM leaders
                    query = f"""
                        SELECT player_name,
                               CASE
                                   WHEN SUM(time_played_seconds) > 0
                                   THEN (SUM(damage_given) * 60.0) / SUM(time_played_seconds)
                                   ELSE 0
                               END as weighted_dpm,
                               SUM(kills) as total_kills,
                               SUM(deaths) as total_deaths
                        FROM player_comprehensive_stats
                        WHERE session_id IN ({session_ids_str})
                        GROUP BY player_name
                        ORDER BY weighted_dpm DESC
                        LIMIT 10
                    """
                    async with db.execute(query, session_ids) as cursor:
                        dpm_leaders = await cursor.fetchall()

                    # Build and send DPM embed
                    embed_dpm = discord.Embed(
                        title="💥 DPM Analytics - Damage Per Minute",
                        description="Enhanced DPM with Kill/Death Details",
                        color=0xFEE75C,
                        timestamp=datetime.now(),
                    )
                    if dpm_leaders:
                        dpm_text = ""
                        for i, (player, dpm, kills, deaths) in enumerate(
                            dpm_leaders[:10], 1
                        ):
                            kd = kills / deaths if deaths else kills
                            dpm_text += f"{i}. **{player}**\n"
                            dpm_text += f"   💥 `{dpm:.0f} DPM` • 💀 `{kd:.1f} K/D` ({kills}K/{deaths}D)\n"
                        embed_dpm.add_field(
                            name="🏆 Enhanced DPM Leaderboard",
                            value=dpm_text.rstrip(),
                            inline=False,
                        )
                        avg_dpm = sum(p[1] for p in dpm_leaders) / len(
                            dpm_leaders
                        )
                        highest_dpm = dpm_leaders[0][1] if dpm_leaders else 0
                        leader_name = (
                            dpm_leaders[0][0] if dpm_leaders else "N/A"
                        )
                        insights = (
                            f"📊 **Enhanced Session DPM Stats:**\n"
                            f"• Average DPM: `{avg_dpm:.1f}`\n"
                            f"• Highest DPM: `{highest_dpm:.0f}`\n"
                            f"• DPM Leader: **{leader_name}**\n"
                            f"• Formula: `(Total Damage × 60) / Time Played (seconds)`"
                        )
                        embed_dpm.add_field(
                            name="💥 DPM Insights", value=insights, inline=False
                        )
                    embed_dpm.set_footer(text=f"Session: {latest_date}")
                    await ctx.send(embed=embed_dpm)
                    await asyncio.sleep(2)

                    # Weapon Mastery - SIMPLE fix: send ALL weapons and split fields when needed
                    # Get player revives (used in weapon summary per player)
                    # Use revives_given (times the player revived others) for weapon summaries
                    query = f"""
                        SELECT player_name, SUM(revives_given) as revives
                        FROM player_comprehensive_stats
                        WHERE session_id IN ({session_ids_str})
                        GROUP BY player_name
                    """
                    async with db.execute(query, session_ids) as cursor:
                        player_revives_raw = await cursor.fetchall()

                    player_revives = {
                        player: revives
                        for player, revives in player_revives_raw
                    }

                    # Group by player and keep ALL weapons
                    player_weapon_map = {}
                    for (
                        player,
                        weapon,
                        kills,
                        hits,
                        shots,
                        hs,
                    ) in player_weapons:
                        if player not in player_weapon_map:
                            player_weapon_map[player] = []
                        acc = (hits / shots * 100) if shots > 0 else 0
                        hs_pct = (hs / hits * 100) if hits > 0 else 0
                        weapon_clean = (
                            weapon.replace("WS_", "").replace("_", " ").title()
                        )
                        player_weapon_map[player].append(
                            (weapon_clean, kills, acc, hs_pct, hs, hits, shots)
                        )

                    # Sort players by total kills - SHOW ALL PLAYERS
                    sorted_players = sorted(
                        player_weapon_map.items(),
                        key=lambda x: sum(w[1] for w in x[1]),
                        reverse=True,
                    )

                    # Create weapon mastery embeds - SPLIT AS NEEDED
                    weapon_embeds = []
                    current_embed = discord.Embed(
                        title="🎯 Weapon Mastery Breakdown",
                        description=f"Complete weapon statistics for all {len(sorted_players)} players",
                        color=0x57F287,
                        timestamp=datetime.now(),
                    )

                    current_field_count = 0

                    for player, weapons in sorted_players:
                        total_kills = sum(w[1] for w in weapons)
                        total_shots = sum(w[6] for w in weapons)
                        total_hits = sum(w[5] for w in weapons)
                        overall_acc = (
                            (total_hits / total_shots * 100)
                            if total_shots > 0
                            else 0
                        )
                        revives = player_revives.get(player, 0)

                        # Build weapon text for this player - SHOW ALL WEAPONS
                        weapon_text = f"**{total_kills} kills** • **{overall_acc:.1f}% ACC**"
                        if revives > 0:
                            weapon_text += f" • 💉 **{revives} revived**"
                        weapon_text += "\n"

                        # Add ALL weapons (not just top 3)
                        for (
                            weapon,
                            kills,
                            acc,
                            hs_pct,
                            hs,
                            hits,
                            shots,
                        ) in weapons:
                            weapon_text += f"• {weapon}: `{kills}K` `{acc:.0f}% ACC` `{hs} HS ({hs_pct:.0f}%)`\n"

                        # If this field itself is too large, split it into chunks
                        if (
                            current_field_count >= 25
                            or len(weapon_text) > 1024
                        ):
                            # Save current embed and start a new one
                            weapon_embeds.append(current_embed)
                            current_embed = discord.Embed(
                                title="🎯 Weapon Mastery Breakdown (continued)",
                                description=f"Part {len(weapon_embeds) + 1}",
                                color=0x57F287,
                                timestamp=datetime.now(),
                            )
                            current_field_count = 0

                        # If a SINGLE player's weapons exceed 1024 chars, split their weapons across embeds
                        if len(weapon_text) > 1024:
                            weapon_chunks = []
                            current_chunk = f"**{total_kills} kills** • **{overall_acc:.1f}% ACC**"
                            if revives > 0:
                                current_chunk += f" • 💉 **{revives} revived**"
                            current_chunk += "\n"

                            for (
                                weapon,
                                kills,
                                acc,
                                hs_pct,
                                hs,
                                hits,
                                shots,
                            ) in weapons:
                                weapon_line = f"• {weapon}: `{kills}K` `{acc:.0f}% ACC` `{hs} HS ({hs_pct:.0f}%)`\n"
                                if (
                                    len(current_chunk) + len(weapon_line) > 900
                                ):  # leave buffer
                                    weapon_chunks.append(current_chunk)
                                    current_chunk = ""
                                current_chunk += weapon_line

                            if current_chunk:
                                weapon_chunks.append(current_chunk)

                            for i, chunk in enumerate(weapon_chunks):
                                if current_field_count >= 25:
                                    weapon_embeds.append(current_embed)
                                    current_embed = discord.Embed(
                                        title="🎯 Weapon Mastery Breakdown (continued)",
                                        description=f"Part {len(weapon_embeds) + 1}",
                                        color=0x57F287,
                                        timestamp=datetime.now(),
                                    )
                                    current_field_count = 0

                                field_name = (
                                    f"⚔️ {player}"
                                    if i == 0
                                    else f"⚔️ {player} (continued)"
                                )
                                current_embed.add_field(
                                    name=field_name,
                                    value=chunk.rstrip(),
                                    inline=False,
                                )
                                current_field_count += 1
                        else:
                            current_embed.add_field(
                                name=f"⚔️ {player}",
                                value=weapon_text.rstrip(),
                                inline=False,
                            )
                            current_field_count += 1

                    # Add the last embed if it has content
                    if current_field_count > 0:
                        weapon_embeds.append(current_embed)

                    # Send ALL weapon embeds with delays to avoid rate limits
                    for i, embed in enumerate(weapon_embeds):
                        embed.set_footer(
                            text=f"Session: {latest_date} • Page {i+1}/{len(weapon_embeds)}"
                        )
                        await ctx.send(embed=embed)
                        if i < len(weapon_embeds) - 1:
                            await asyncio.sleep(3)

                    logger.info(
                        f"✅ Sent {len(weapon_embeds)} weapon mastery embeds"
                    )

                    # Graphs (attempt, skip if matplotlib missing)
                    try:
                        import io

                        import matplotlib.pyplot as plt

                        player_names = [p[0] for p in all_players_detailed[:6]]
                        kills = [p[1] for p in all_players_detailed[:6]]
                        deaths = [p[2] for p in all_players_detailed[:6]]
                        dpm = [p[3] for p in all_players_detailed[:6]]
                        time_played = [
                            p[8] / 60 for p in all_players_detailed[:6]
                        ]
                        time_dead = [
                            p[9] / 60 for p in all_players_detailed[:6]
                        ]
                        denied = [p[12] for p in all_players_detailed[:6]]
                        fig, axes = plt.subplots(2, 3, figsize=(18, 10))
                        axes[0, 0].bar(
                            range(len(player_names)), kills, color="#57F287"
                        )
                        axes[0, 1].bar(
                            range(len(player_names)), deaths, color="#ED4245"
                        )
                        axes[0, 2].bar(
                            range(len(player_names)), dpm, color="#FEE75C"
                        )
                        axes[1, 0].bar(
                            range(len(player_names)),
                            time_played,
                            color="#5865F2",
                        )
                        axes[1, 1].bar(
                            range(len(player_names)),
                            time_dead,
                            color="#EB459E",
                        )
                        axes[1, 2].bar(
                            range(len(player_names)), denied, color="#9B59B6"
                        )
                        plt.tight_layout()
                        buf = io.BytesIO()
                        plt.savefig(
                            buf, format="png", dpi=150, bbox_inches="tight"
                        )
                        buf.seek(0)
                        plt.close()
                        file = discord.File(
                            buf, filename="performance_analytics.png"
                        )
                        await ctx.send(
                            "📊 **Visual Performance Analytics**", file=file
                        )
                    except ImportError:
                        logger.warning(
                            "⚠️ matplotlib not installed - skipping graphs"
                        )
                    except Exception as e:
                        logger.error(
                            f"❌ Error generating graphs: {e}", exc_info=True
                        )

                    final_embed = discord.Embed(
                        title="✅ Detailed Analytics Complete",
                        description="All detailed statistics have been displayed above.",
                        color=0x00FF00,
                    )
                    await ctx.send(embed=final_embed)
                    return

                # Unknown subcommand
                await ctx.send(
                    "❌ Unknown option. Use:\n"
                    "• `!last_session` - Quick summary\n"
                    "• `!last_session more` - Detailed analytics"
                )
        except Exception as e:
            logger.error(f"Error in last_session command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving last session: {e}")

    @commands.command(name="leaderboard", aliases=["lb", "top"])
    async def leaderboard(self, ctx, stat_type: str = "kills", page: int = 1):
        """🏆 Show players leaderboard with pagination

        Usage:
        - !lb              → First page (kills)
        - !lb 2            → Page 2 (kills)
        - !lb dpm          → First page (DPM)
        - !lb dpm 2        → Page 2 (DPM)

        Available stat types:
        - kills: Total kills
        - kd: Kill/Death ratio
        - dpm: Damage per minute
        - accuracy/acc: Overall accuracy
        - headshots/hs: Headshot percentage
        - games: Games played
        - revives: Most revives given (medic)
        - gibs: Most gibs (finishing moves)
        - objectives/obj: Most objectives completed
        - efficiency/eff: Highest efficiency rating
        - teamwork: Best teamwork (lowest team damage %)
        - multikills: Most multikills (doubles, triples, etc)
        - grenades/nades: Top grenadiers (grenade kills + accuracy)
        """
        try:
            # Handle case where user passes page number as first arg
            # e.g., !lb 2 should be interpreted as page 2 of kills
            if stat_type.isdigit():
                page = int(stat_type)
                stat_type = "kills"
            else:
                stat_type = stat_type.lower()

            # Ensure page is at least 1
            page = max(1, page)

            # 10 players per page
            players_per_page = 10
            offset = (page - 1) * players_per_page

            # Map aliases to stat types
            stat_aliases = {
                "k": "kills",
                "kill": "kills",
                "kd": "kd",
                "ratio": "kd",
                "dpm": "dpm",
                "damage": "dpm",
                "acc": "accuracy",
                "accuracy": "accuracy",
                "hs": "headshots",
                "headshot": "headshots",
                "headshots": "headshots",
                "games": "games",
                "played": "games",
                "revives": "revives",
                "revive": "revives",
                "medic": "revives",
                "gibs": "gibs",
                "gib": "gibs",
                "obj": "objectives",
                "objective": "objectives",
                "objectives": "objectives",
                "eff": "efficiency",
                "efficiency": "efficiency",
                "teamwork": "teamwork",
                "team": "teamwork",
                "multikill": "multikills",
                "multikills": "multikills",
                "multi": "multikills",
                "grenade": "grenades",
                "grenades": "grenades",
                "nades": "grenades",
                "nade": "grenades",
            }

            stat_type = stat_aliases.get(stat_type, "kills")

            async with aiosqlite.connect(self.bot.db_path) as db:
                # Get total count for pagination
                count_query = """
                    SELECT COUNT(DISTINCT player_guid) 
                    FROM player_comprehensive_stats
                """
                async with db.execute(count_query) as cursor:
                    total_players = (await cursor.fetchone())[0]

                total_pages = (
                    total_players + players_per_page - 1
                ) // players_per_page

                if stat_type == "kills":
                    query = f"""
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(p.kills) as total_kills,
                            SUM(p.deaths) as total_deaths,
                            COUNT(DISTINCT p.session_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 10
                        ORDER BY total_kills DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                    title = (
                        f"🏆 Top Players by Kills (Page {page}/{total_pages})"
                    )

                elif stat_type == "kd":
                    query = f"""
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(p.kills) as total_kills,
                            SUM(p.deaths) as total_deaths,
                            COUNT(DISTINCT p.session_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 50 AND total_deaths > 0
                        ORDER BY (CAST(total_kills AS FLOAT) / total_deaths) DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                    title = f"🏆 Top Players by K/D Ratio (Page {page}/{total_pages})"

                elif stat_type == "dpm":
                    query = f"""
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            CASE
                                WHEN SUM(p.time_played_seconds) > 0
                                THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                                ELSE 0
                            END as weighted_dpm,
                            SUM(p.kills) as total_kills,
                            COUNT(DISTINCT p.session_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 50
                        ORDER BY weighted_dpm DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                    title = f"🏆 Top Players by DPM (Page {page}/{total_pages})"

                elif stat_type == "accuracy":
                    query = f"""
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(w.hits) as total_hits,
                            SUM(w.shots) as total_shots,
                            SUM(p.kills) as total_kills,
                            COUNT(DISTINCT p.session_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        JOIN weapon_comprehensive_stats w
                            ON p.session_id = w.session_id
                            AND p.player_guid = w.player_guid
                        GROUP BY p.player_guid
                        HAVING games > 50 AND total_shots > 1000
                        ORDER BY (CAST(total_hits AS FLOAT) / total_shots) DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                    title = f"🏆 Top Players by Accuracy (Page {page}/{total_pages})"

                elif stat_type == "headshots":
                    query = f"""
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(p.headshot_kills) as total_hs,
                            SUM(w.hits) as total_hits,
                            SUM(p.kills) as total_kills,
                            COUNT(DISTINCT p.session_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        JOIN weapon_comprehensive_stats w
                            ON p.session_id = w.session_id
                            AND p.player_guid = w.player_guid
                        GROUP BY p.player_guid
                        HAVING games > 50 AND total_hits > 1000
                        ORDER BY (CAST(total_hs AS FLOAT) / total_hits) DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                    title = f"🏆 Top Players by Headshot % (Page {page}/{total_pages})"

                elif stat_type == "games":
                    query = f"""
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            COUNT(DISTINCT p.session_id) as games,
                            SUM(p.kills) as total_kills,
                            SUM(p.deaths) as total_deaths,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        ORDER BY games DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                    title = (
                        f"🏆 Most Active Players (Page {page}/{total_pages})"
                    )

                elif stat_type == "revives":
                    query = f"""
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(p.revives_given) as total_revives,
                            SUM(p.kills) as total_kills,
                            COUNT(DISTINCT p.session_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 10
                        ORDER BY total_revives DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                    title = f"💉 Top Medics - Teammates Revived (Page {page}/{total_pages})"

                elif stat_type == "gibs":
                    query = f"""
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(p.gibs) as total_gibs,
                            SUM(p.kills) as total_kills,
                            COUNT(DISTINCT p.session_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 10
                        ORDER BY total_gibs DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                    title = f"💀 Top Gibbers (Page {page}/{total_pages})"

                elif stat_type == "objectives":
                    query = f"""
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(p.objectives_completed + p.objectives_destroyed + p.objectives_stolen + p.objectives_returned) as total_obj,
                            SUM(p.objectives_completed) as completed,
                            COUNT(DISTINCT p.session_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 10
                        ORDER BY total_obj DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                    title = (
                        f"🎯 Top Objective Players (Page {page}/{total_pages})"
                    )

                elif stat_type == "efficiency":
                    query = f"""
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            AVG(p.efficiency) as avg_eff,
                            SUM(p.kills) as total_kills,
                            COUNT(DISTINCT p.session_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 50
                        ORDER BY avg_eff DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                    title = f"⚡ Highest Efficiency (Page {page}/{total_pages})"

                elif stat_type == "teamwork":
                    query = f"""
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(p.team_damage_given) as total_team_dmg,
                            SUM(p.damage_given) as total_dmg,
                            COUNT(DISTINCT p.session_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 50 AND total_dmg > 0
                        ORDER BY (CAST(total_team_dmg AS FLOAT) / total_dmg) ASC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                    title = f"🤝 Best Teamwork (Lowest Team Damage %) (Page {page}/{total_pages})"

                elif stat_type == "multikills":
                    query = f"""
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(p.double_kills + p.triple_kills + p.quad_kills + p.multi_kills + p.mega_kills) as total_multi,
                            SUM(p.mega_kills) as megas,
                            COUNT(DISTINCT p.session_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 10
                        ORDER BY total_multi DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                    title = f"🔥 Most Multikills (Page {page}/{total_pages})"

                elif stat_type == "grenades":
                    query = f"""
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = w.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(w.kills) as total_kills,
                            SUM(w.shots) as total_throws,
                            SUM(w.hits) as total_hits,
                            CASE 
                                WHEN SUM(w.kills) > 0 
                                THEN ROUND(CAST(SUM(w.hits) AS FLOAT) / SUM(w.kills), 2)
                                ELSE 0 
                            END as aoe_ratio,
                            COUNT(DISTINCT w.session_id) as games,
                            w.player_guid
                        FROM weapon_comprehensive_stats w
                        WHERE w.weapon_name = 'WS_GRENADE'
                        GROUP BY w.player_guid
                        HAVING games > 10
                        ORDER BY total_kills DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                    title = f"💣 Top Grenadiers - AOE Masters (Page {page}/{total_pages})"

                async with db.execute(query) as cursor:
                    results = await cursor.fetchall()

            if not results:
                await ctx.send(
                    f"❌ No data found for leaderboard type: {stat_type}"
                )
                return

            # Build embed
            embed = discord.Embed(
                title=title,
                color=0xFFD700,
                timestamp=datetime.now(),  # Gold color
            )

            # Format results based on stat type
            leaderboard_text = ""
            medals = ["🥇", "🥈", "🥉"]

            for i, row in enumerate(results):
                # Calculate actual rank (based on page)
                rank = offset + i + 1

                # Use medal for top 3 overall, otherwise show rank number
                if rank <= 3:
                    medal = medals[rank - 1]
                else:
                    medal = f"{rank}."

                name = row[0]

                # Add dev badge for ciril (bot developer)
                player_guid = row[-1]  # GUID is always last column
                if player_guid == "E587CA5F":
                    name = f"{name} 👑"  # Crown emoji for dev

                if stat_type == "kills":
                    kills, deaths, games = row[1], row[2], row[3]
                    kd = kills / deaths if deaths > 0 else kills
                    leaderboard_text += f"{medal} **{name}** - {kills:,}K ({kd:.2f} K/D, {games} games)\n"

                elif stat_type == "kd":
                    kills, deaths, games = row[1], row[2], row[3]
                    kd = kills / deaths if deaths > 0 else kills
                    leaderboard_text += f"{medal} **{name}** - {kd:.2f} K/D ({kills:,}K/{deaths:,}D, {games} games)\n"

                elif stat_type == "dpm":
                    avg_dpm, kills, games = row[1], row[2], row[3]
                    leaderboard_text += f"{medal} **{name}** - {avg_dpm:.1f} DPM ({kills:,}K, {games} games)\n"

                elif stat_type == "accuracy":
                    hits, shots, kills, games = row[1], row[2], row[3], row[4]
                    acc = (hits / shots * 100) if shots > 0 else 0
                    leaderboard_text += f"{medal} **{name}** - {acc:.1f}% Acc ({kills:,}K, {games} games)\n"

                elif stat_type == "headshots":
                    hs, hits, kills, games = row[1], row[2], row[3], row[4]
                    hs_pct = (hs / hits * 100) if hits > 0 else 0
                    leaderboard_text += f"{medal} **{name}** - {hs_pct:.1f}% HS ({hs:,} HS, {games} games)\n"

                elif stat_type == "games":
                    games, kills, deaths = row[1], row[2], row[3]
                    kd = kills / deaths if deaths > 0 else kills
                    leaderboard_text += f"{medal} **{name}** - {games:,} games ({kills:,}K, {kd:.2f} K/D)\n"

                elif stat_type == "revives":
                    revives, kills, games = row[1], row[2], row[3]
                    leaderboard_text += f"{medal} **{name}** - {revives:,} teammates revived ({kills:,}K, {games} games)\n"

                elif stat_type == "gibs":
                    gibs, kills, games = row[1], row[2], row[3]
                    leaderboard_text += f"{medal} **{name}** - {gibs:,} gibs ({kills:,}K, {games} games)\n"

                elif stat_type == "objectives":
                    total_obj, completed, games = row[1], row[2], row[3]
                    leaderboard_text += f"{medal} **{name}** - {total_obj:,} objectives ({completed} completed, {games} games)\n"

                elif stat_type == "efficiency":
                    avg_eff, kills, games = row[1], row[2], row[3]
                    leaderboard_text += f"{medal} **{name}** - {avg_eff:.1f} efficiency ({kills:,}K, {games} games)\n"

                elif stat_type == "teamwork":
                    team_dmg, total_dmg, games = row[1], row[2], row[3]
                    team_pct = (
                        (team_dmg / total_dmg * 100) if total_dmg > 0 else 0
                    )
                    leaderboard_text += f"{medal} **{name}** - {team_pct:.2f}% team damage ({games} games)\n"

                elif stat_type == "multikills":
                    total_multi, megas, games = row[1], row[2], row[3]
                    leaderboard_text += f"{medal} **{name}** - {total_multi:,} multikills ({megas} mega, {games} games)\n"

                elif stat_type == "grenades":
                    kills, throws, hits, aoe_ratio, games = (
                        row[1],
                        row[2],
                        row[3],
                        row[4],
                        row[5],
                    )
                    accuracy = (hits / throws * 100) if throws > 0 else 0
                    aoe_emoji = "🔥" if aoe_ratio >= 3.0 else ""
                    leaderboard_text += f"{medal} **{name}** - {kills:,} kills • {accuracy:.1f}% acc • {aoe_ratio:.2f} AOE {aoe_emoji} ({games} games)\n"

            embed.description = leaderboard_text

            # Add usage footer with pagination info
            if page < total_pages:
                next_page_hint = f" | Next: !lb {stat_type} {page + 1}"
            else:
                next_page_hint = ""

            footer_text = f"💡 Use !lb [stat] [page]{next_page_hint}"
            embed.set_footer(text=footer_text)

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in leaderboard command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving leaderboard: {e}")

    @commands.command(name="session", aliases=["match", "game"])
    async def session(self, ctx, *date_parts):
        """📅 Show detailed session/match statistics for a full day

        Usage:
        - !session 2025-09-30  (show session from specific date)
        - !session 2025 9 30   (alternative format)
        - !session             (show most recent session)

        Shows aggregated stats for entire day (all maps/rounds combined).
        """
        try:
            # Parse date from arguments
            if date_parts:
                # Join parts: "2025 9 30" or "2025-09-30"
                date_str = "-".join(str(p) for p in date_parts)
                # Normalize format: ensure YYYY-MM-DD
                parts = date_str.replace("-", " ").split()
                if len(parts) >= 3:
                    year, month, day = parts[0], parts[1], parts[2]
                    date_filter = f"{year}-{int(month):02d}-{int(day):02d}"
                else:
                    date_filter = date_str
            else:
                # Get most recent date
                async with aiosqlite.connect(self.bot.db_path) as db:
                    async with db.execute(
                        """
                        SELECT DISTINCT DATE(session_date) as date
                        FROM player_comprehensive_stats
                        ORDER BY date DESC LIMIT 1
                    """
                    ) as cursor:
                        result = await cursor.fetchone()
                        if not result:
                            await ctx.send("❌ No sessions found in database")
                            return
                        date_filter = result[0]

            # Now use the same logic as !last_session but for the specified date
            # Just call last_session logic with date filter
            await ctx.send(f"📅 Loading session data for **{date_filter}**...")

            # Query aggregated stats for the full day
            async with aiosqlite.connect(self.bot.db_path) as db:
                # Get session metadata
                query = """
                    SELECT 
                        COUNT(DISTINCT session_id) / 2 as total_maps,
                        COUNT(DISTINCT session_id) as total_rounds,
                        COUNT(DISTINCT player_guid) as player_count,
                        MIN(session_date) as first_round,
                        MAX(session_date) as last_round
                    FROM player_comprehensive_stats
                    WHERE DATE(session_date) = ?
                """

                async with db.execute(query, (date_filter,)) as cursor:
                    result = await cursor.fetchone()
                    if not result or result[0] == 0:
                        await ctx.send(
                            f"❌ No session found for date: {date_filter}"
                        )
                        return

                    (
                        total_maps,
                        total_rounds,
                        player_count,
                        first_round,
                        last_round,
                    ) = result

                # Get unique maps played
                async with db.execute(
                    """
                    SELECT DISTINCT map_name
                    FROM player_comprehensive_stats
                    WHERE DATE(session_date) = ?
                    ORDER BY session_date
                """,
                    (date_filter,),
                ) as cursor:
                    maps = await cursor.fetchall()
                    maps_list = [m[0] for m in maps]

                # Build header embed
                embed = discord.Embed(
                    title=f"� Session Summary: {date_filter}",
                    description=f"**{int(total_maps)} maps** • **{total_rounds} rounds** • **{player_count} players**",
                    color=0x00FF88,
                )

                # Add maps played
                maps_text = ", ".join(maps_list)
                if len(maps_text) > 900:
                    maps_text = (
                        ", ".join(maps_list[:8])
                        + f" (+{len(maps_list) - 8} more)"
                    )
                embed.add_field(
                    name="🗺️ Maps Played", value=maps_text, inline=False
                )

                # Get top players aggregated
                async with db.execute(
                    """
                    SELECT 
                        p.player_name,
                        SUM(p.kills) as kills,
                        SUM(p.deaths) as deaths,
                        CASE
                            WHEN SUM(p.time_played_seconds) > 0
                            THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                            ELSE 0
                        END as dpm
                    FROM player_comprehensive_stats p
                    WHERE DATE(p.session_date) = ?
                    GROUP BY p.player_name
                    ORDER BY kills DESC
                    LIMIT 5
                """,
                    (date_filter,),
                ) as cursor:
                    top_players = await cursor.fetchall()

                # Add top 5 players
                if top_players:
                    player_text = ""
                    medals = ["🥇", "🥈", "🥉", "4.", "5."]
                    for i, (name, kills, deaths, dpm) in enumerate(
                        top_players
                    ):
                        kd = kills / deaths if deaths > 0 else kills
                        player_text += f"{medals[i]} **{name}** - {kills}K/{deaths}D ({kd:.2f} KD, {dpm:.0f} DPM)\n"
                    embed.add_field(
                        name="🏆 Top Players", value=player_text, inline=False
                    )

                embed.set_footer(
                    text="💡 Use !last_session for the most recent session with full details"
                )
                await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in session command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving session: {e}")

    @commands.command(
        name="last_session", aliases=["last", "latest", "recent"]
    )
    async def last_session(self, ctx, subcommand: str = None):
        """🎮 Show the most recent session/match

        Displays detailed stats for the latest played session (full day).
        A session = one day of gaming with all maps/rounds.

        Subcommands:
        - !last_session          → Clean view with 2 essential graphs
        - !last_session graphs   → Detailed round/map breakdown
        - !last_session full     → Everything including advanced stats
        """
        try:
            # Small persistent help hint printed on every invocation
            try:
                await self._send_last_session_help(ctx)
            except Exception:
                pass
            async with aiosqlite.connect(self.bot.db_path) as db:
                # Create a TEMP VIEW alias for player_name if the DB uses a different
                # column name (eg. clean_name). This prevents OperationalError when
                # existing SQL references p.player_name.
                try:
                    await self._ensure_player_name_alias(db)
                except Exception:
                    # _ensure_player_name_alias logs its own errors; continue
                    pass
                # Enable lightweight SQL diagnostics for this connection so we
                # can capture the exact SQL and connection-visible schema if an
                # OperationalError occurs during subsequent queries.
                try:
                    await self._enable_sql_diag(db)
                except Exception:
                    # Best-effort only; don't fail the command if diag setup fails
                    pass

                # Get the most recent date (using SUBSTR to handle both "2025-10-02" and "2025-10-02-221711" formats)
                async with db.execute(
                    """
                    SELECT DISTINCT SUBSTR(session_date, 1, 10) as date
                    FROM sessions
                    ORDER BY date DESC
                    LIMIT 1
                """
                ) as cursor:
                    result = await cursor.fetchone()

                if not result:
                    await ctx.send("❌ No sessions found in database")
                    return

                latest_date = result[0]

                # Get all session IDs for this date (chronologically)
                async with db.execute(
                    """
                    SELECT id, map_name, round_number, actual_time
                    FROM sessions
                    WHERE SUBSTR(session_date, 1, 10) = ?
                    ORDER BY id ASC
                """,
                    (latest_date,),
                ) as cursor:
                    sessions = await cursor.fetchall()

                if not sessions:
                    await ctx.send("❌ No sessions found for latest date")
                    return

                session_ids = [s[0] for s in sessions]
                session_ids_str = ",".join("?" * len(session_ids))

                # Get unique player count across all sessions
                query = f"""
                    SELECT COUNT(DISTINCT player_guid)
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                """
                async with db.execute(query, session_ids) as cursor:
                    player_count = (await cursor.fetchone())[0]

                # Early short-circuit: objectives-only view (minimal queries, no other embeds)
                if subcommand and subcommand.lower() in ("obj", "objectives"):
                    # Fetch awards/objective stats only and return a compact embed
                    query = f"""
                        SELECT clean_name, xp, kill_assists, objectives_stolen, objectives_returned,
                               dynamites_planted, dynamites_defused, times_revived,
                               double_kills, triple_kills, quad_kills, multi_kills, mega_kills,
                               denied_playtime, most_useful_kills, useless_kills, gibs,
                               killing_spree_best, death_spree_worst
                        FROM player_comprehensive_stats
                        WHERE session_id IN ({session_ids_str})
                    """
                    async with db.execute(query, session_ids) as cursor:
                        awards_rows = await cursor.fetchall()

                    if not awards_rows:
                        await ctx.send(
                            "❌ No objective/support data available for latest session"
                        )
                        return

                    # Also fetch revives GIVEN per player (distinct from times_revived which is times the player was revived)
                    # Use clean_name and SUM(revives_given) so the keys match the awards rows (which use clean_name)
                    rev_query = f"""
                        SELECT clean_name, SUM(revives_given) as revives_given
                        FROM player_comprehensive_stats
                        WHERE session_id IN ({session_ids_str})
                        GROUP BY clean_name
                    """
                    async with db.execute(rev_query, session_ids) as cursor:
                        rev_rows = await cursor.fetchall()
                    revives_map = {r[0]: (r[1] or 0) for r in rev_rows}

                    # Aggregate per-player across rounds (same logic as the full flow)
                    player_objectives_local = {}
                    for row in awards_rows:
                        name = row[0]
                        if name not in player_objectives_local:
                            player_objectives_local[name] = {
                                "xp": 0,
                                "assists": 0,
                                "obj_stolen": 0,
                                "obj_returned": 0,
                                "dyn_planted": 0,
                                "dyn_defused": 0,
                                "times_revived": 0,  # times the player WAS revived
                                "revives_given": 0,  # will merge from revives_map
                                "multi_2x": 0,
                                "multi_3x": 0,
                                "multi_4x": 0,
                                "multi_5x": 0,
                                "multi_6x": 0,
                                "denied_time": 0,
                                "useful_kills": 0,
                                "useless_kills": 0,
                                "gibs": 0,
                                "best_spree": 0,
                                "worst_spree": 0,
                            }

                        player_objectives_local[name]["xp"] += row[1] or 0
                        player_objectives_local[name]["assists"] += row[2] or 0
                        player_objectives_local[name]["obj_stolen"] += (
                            row[3] or 0
                        )
                        player_objectives_local[name]["obj_returned"] += (
                            row[4] or 0
                        )
                        player_objectives_local[name]["dyn_planted"] += (
                            row[5] or 0
                        )
                        player_objectives_local[name]["dyn_defused"] += (
                            row[6] or 0
                        )
                        player_objectives_local[name]["times_revived"] += (
                            row[7] or 0
                        )
                        player_objectives_local[name]["multi_2x"] += (
                            row[8] or 0
                        )
                        player_objectives_local[name]["multi_3x"] += (
                            row[9] or 0
                        )
                        player_objectives_local[name]["multi_4x"] += (
                            row[10] or 0
                        )
                        player_objectives_local[name]["multi_5x"] += (
                            row[11] or 0
                        )
                        player_objectives_local[name]["multi_6x"] += (
                            row[12] or 0
                        )
                        player_objectives_local[name]["denied_time"] += (
                            row[13] or 0
                        )
                        player_objectives_local[name]["useful_kills"] += (
                            row[14] or 0
                        )
                        player_objectives_local[name]["useless_kills"] += (
                            row[15] or 0
                        )
                        player_objectives_local[name]["gibs"] += row[16] or 0
                        player_objectives_local[name]["best_spree"] = max(
                            player_objectives_local[name]["best_spree"],
                            row[17] or 0,
                        )
                        player_objectives_local[name]["worst_spree"] = max(
                            player_objectives_local[name]["worst_spree"],
                            row[18] or 0,
                        )

                    # Merge revives_given into the aggregated structure
                    for pname, gv in revives_map.items():
                        if pname not in player_objectives_local:
                            player_objectives_local[pname] = {
                                "xp": 0,
                                "assists": 0,
                                "obj_stolen": 0,
                                "obj_returned": 0,
                                "dyn_planted": 0,
                                "dyn_defused": 0,
                                "times_revived": 0,
                                "revives_given": gv or 0,
                                "multi_2x": 0,
                                "multi_3x": 0,
                                "multi_4x": 0,
                                "multi_5x": 0,
                                "multi_6x": 0,
                                "denied_time": 0,
                                "useful_kills": 0,
                                "useless_kills": 0,
                                "gibs": 0,
                                "best_spree": 0,
                                "worst_spree": 0,
                            }
                        else:
                            player_objectives_local[pname]["revives_given"] = (
                                gv or 0
                            )

                    # Build compact embed showing more objective/support fields
                    top_n_local = min(8, len(player_objectives_local))
                    sorted_players_local = sorted(
                        player_objectives_local.items(),
                        key=lambda x: x[1]["xp"],
                        reverse=True,
                    )[:top_n_local]

                    compact = discord.Embed(
                        title=f"🎯 Objective & Support - {latest_date}",
                        description=f"Top objective contributors • {player_count} players",
                        color=0x00D166,
                        timestamp=datetime.now(),
                    )

                    # Helper to split long field values by lines (safe margin)
                    def _local_split(s: str, max_len: int = 900):
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

                    continuation_embeds = []

                    for i, (player, stats) in enumerate(
                        sorted_players_local, 1
                    ):
                        # Compose a richer objective/support summary per player
                        txt_lines = []
                        txt_lines.append(f"XP: `{stats.get('xp',0)}`")
                        # Distinguish revives given vs times revived
                        txt_lines.append(
                            f"Revives Given: `{stats.get('revives_given',0)}` • Times Revived: `{stats.get('times_revived',0)}`"
                        )
                        txt_lines.append(
                            f"Dyns P/D: `{stats.get('dyn_planted',0)}/{stats.get('dyn_defused',0)}` • S/R: `{stats.get('obj_stolen',0)}/{stats.get('obj_returned',0)}`"
                        )
                        txt_lines.append(
                            f"Useful/Useless Kills: `{stats.get('useful_kills',0)}/{stats.get('useless_kills',0)}` (parser noisy)"
                        )
                        if stats.get("gibs", 0) > 0:
                            txt_lines.append(f"Gibs: `{stats.get('gibs',0)}`")
                        # Best/Worst spree
                        txt_lines.append(
                            f"Best Spree: `{stats.get('best_spree',0)}` • Worst Spree: `{stats.get('worst_spree',0)}`"
                        )
                        # Denied playtime as MM:SS
                        if stats.get("denied_time", 0) > 0:
                            dt = int(stats.get("denied_time", 0))
                            dm = dt // 60
                            ds = dt % 60
                            txt_lines.append(f"Enemy Denied: `{dm}:{ds:02d}`")

                        field_value = "\n".join(txt_lines)

                        # If the field gets too long, split into continuation embeds
                        if len(field_value) > 900:
                            chunks = _local_split(field_value, max_len=900)
                            compact.add_field(
                                name=f"{i}. {player}",
                                value=chunks[0],
                                inline=False,
                            )
                            for idx_chunk, ch in enumerate(
                                chunks[1:], start=2
                            ):
                                cont = discord.Embed(
                                    title=f"🎯 Objective & Support - {latest_date} (cont.)",
                                    color=0x00D166,
                                    timestamp=datetime.now(),
                                )
                                cont.add_field(
                                    name=f"{i}. {player} (cont. {idx_chunk})",
                                    value=ch,
                                    inline=False,
                                )
                                continuation_embeds.append(cont)
                        else:
                            compact.add_field(
                                name=f"{i}. {player}",
                                value=field_value,
                                inline=False,
                            )

                    compact.set_footer(
                        text=f"Session: {latest_date} • Use !last_session for full report"
                    )

                    # Send main compact and any continuation embeds
                    await ctx.send(embed=compact)
                    for j, cont in enumerate(continuation_embeds):
                        try:
                            cont.set_footer(
                                text=f"Session: {latest_date} • Page {j+2}/{len(continuation_embeds)+1}"
                            )
                        except Exception:
                            pass
                        await ctx.send(embed=cont)
                        await asyncio.sleep(1.2)

                    return

                # Early short-circuit: combat-only view (minimal queries, no other embeds)
                if subcommand and subcommand.lower() in ("combat",):
                    # Fetch combat-focused aggregates and return a compact embed
                    query = f"""
                        SELECT p.player_name,
                               SUM(p.kills) as kills,
                               SUM(p.deaths) as deaths,
                               SUM(p.damage_given) as damage_given,
                               SUM(p.damage_received) as damage_received,
                               SUM(p.gibs) as gibs,
                               SUM(p.headshot_kills) as headshot_kills,
                               CASE
                                   WHEN SUM(p.time_played_seconds) > 0
                                   THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                                   ELSE 0
                               END as weighted_dpm
                        FROM player_comprehensive_stats p
                        WHERE p.session_id IN ({session_ids_str})
                        GROUP BY p.player_name
                        ORDER BY kills DESC
                    """
                    async with db.execute(query, session_ids) as cursor:
                        combat_rows = await cursor.fetchall()

                    if not combat_rows:
                        await ctx.send(
                            "❌ No combat data available for latest session"
                        )
                        return

                    embed = discord.Embed(
                        title=f"⚔️ Combat Stats - {latest_date}",
                        description=f"Combat leaders • {player_count} players",
                        color=0xED4245,
                        timestamp=datetime.now(),
                    )

                    medals = ["🥇", "🥈", "🥉"]
                    for i, row in enumerate(combat_rows, 1):
                        name, kills, deaths, dmg_g, dmg_r, gibs, hsk, dpm = row
                        kd = (
                            kills / deaths
                            if deaths and deaths > 0
                            else (kills or 0)
                        )
                        hours = int((0 if row[7] is None else 0))
                        time_display = ""
                        player_text = (
                            f"{medals[i-1] if i <=3 else f'{i}.'} **{name}**\n"
                            f"💀 `{kills}K/{deaths}D ({kd:.2f})` • `{dpm:.0f} DPM`\n"
                            f"💥 Damage: `{(dmg_g or 0):,}` given • `{(dmg_r or 0):,}` received\n"
                        )
                        if gibs and gibs > 0:
                            player_text += f"🦴 `{gibs} Gibs`"
                        if hsk and hsk > 0:
                            player_text += f" • 🎯 `{hsk} Headshot Kills`"

                        embed.add_field(
                            name="\u200b", value=player_text, inline=False
                        )

                    embed.set_footer(
                        text=f"Session: {latest_date} • Use !last_session for full report"
                    )
                    await self._log_and_send(
                        ctx, embed, "combat", latest_date=latest_date
                    )
                    return

                # Early short-circuit: weapons-only view (minimal queries)
                if subcommand and subcommand.lower() in (
                    "weapons",
                    "weapon",
                    "weap",
                ):
                    query = f"""
                        SELECT p.player_name, w.weapon_name,
                               SUM(w.kills) as weapon_kills,
                               SUM(w.hits) as hits,
                               SUM(w.shots) as shots,
                               SUM(w.headshots) as headshots
                        FROM weapon_comprehensive_stats w
                        JOIN player_comprehensive_stats p
                            ON w.session_id = p.session_id
                            AND w.player_guid = p.player_guid
                        WHERE w.session_id IN ({session_ids_str})
                        GROUP BY p.player_name, w.weapon_name
                        HAVING weapon_kills > 0
                        ORDER BY p.player_name, weapon_kills DESC
                    """
                    async with db.execute(query, session_ids) as cursor:
                        pw_rows = await cursor.fetchall()

                    if not pw_rows:
                        await ctx.send(
                            "❌ No weapon data available for latest session"
                        )
                        return

                    # Group by player
                    player_weapon_map = {}
                    for player, weapon, kills, hits, shots, hs in pw_rows:
                        if player not in player_weapon_map:
                            player_weapon_map[player] = []
                        acc = (
                            (hits / shots * 100) if shots and shots > 0 else 0
                        )
                        hs_pct = (hs / hits * 100) if hits and hits > 0 else 0
                        weapon_clean = (
                            weapon.replace("WS_", "").replace("_", " ").title()
                        )
                        player_weapon_map[player].append(
                            (weapon_clean, kills, acc, hs_pct, hs, hits, shots)
                        )

                    # Build embed with top players
                    embed = discord.Embed(
                        title=f"🔫 Weapon Mastery - {latest_date}",
                        description=f"Top weapons per player • {len(player_weapon_map)} players",
                        color=0x5865F2,
                        timestamp=datetime.now(),
                    )

                    for player, weapons in player_weapon_map.items():
                        text = ""
                        for (
                            weapon,
                            kills,
                            acc,
                            hs_pct,
                            hs,
                            hits,
                            shots,
                        ) in weapons[:6]:
                            text += f"**{weapon}**: `{kills}K` • `{acc:.1f}% ACC` • `{hs} HS ({hs_pct:.1f}%)`\n"
                        embed.add_field(
                            name=f"⚔️ {player}",
                            value=text.rstrip(),
                            inline=False,
                        )

                    embed.set_footer(
                        text=f"Session: {latest_date} • Use !last_session for full report"
                    )

                    # Manually chunk player weapon fields if any field is too long
                    weapon_conts = []
                    safe_embed = discord.Embed(
                        title=embed.title,
                        description=embed.description,
                        color=embed.color,
                        timestamp=embed.timestamp,
                    )

                    def _split_lines(s: str, max_len: int = 900):
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

                    for player, weapons in player_weapon_map.items():
                        text = ""
                        for (
                            weapon,
                            kills,
                            acc,
                            hs_pct,
                            hs,
                            hits,
                            shots,
                        ) in weapons:
                            text += f"**{weapon}**: `{kills}K` • `{acc:.1f}% ACC` • `{hs} HS ({hs_pct:.1f}%)`\n"

                        if len(text) > 900:
                            chunks = _split_lines(text, max_len=900)
                            safe_embed.add_field(
                                name=f"⚔️ {player}",
                                value=chunks[0],
                                inline=False,
                            )
                            for idx_ch, ch in enumerate(chunks[1:], start=2):
                                cont = discord.Embed(
                                    title=f"🔫 Weapon Mastery - {latest_date} (cont.)",
                                    color=0x5865F2,
                                    timestamp=datetime.now(),
                                )
                                cont.add_field(
                                    name=f"⚔️ {player} (cont. {idx_ch})",
                                    value=ch,
                                    inline=False,
                                )
                                weapon_conts.append(cont)
                        else:
                            safe_embed.add_field(
                                name=f"⚔️ {player}",
                                value=text.rstrip(),
                                inline=False,
                            )

                    await ctx.send(embed=safe_embed)
                    for i, cont in enumerate(weapon_conts):
                        try:
                            cont.set_footer(
                                text=f"Session: {latest_date} • Page {i+2}/{len(weapon_conts)+1}"
                            )
                        except Exception:
                            pass
                        await ctx.send(embed=cont)
                        await asyncio.sleep(1.2)
                    return

                # Early short-circuit: support-only view (medpacks, revives, etc.)
                if subcommand and subcommand.lower() in ("support",):
                    query = f"""
                        SELECT p.player_name,
                               SUM(p.revives_given) as revives_given,
                               SUM(p.times_revived) as times_revived,
                               SUM(p.kills) as kills,
                               SUM(p.deaths) as deaths
                        FROM player_comprehensive_stats p
                        WHERE p.session_id IN ({session_ids_str})
                        GROUP BY p.player_name
                        ORDER BY revives_given DESC
                    """
                    async with db.execute(query, session_ids) as cursor:
                        sup_rows = await cursor.fetchall()

                    if not sup_rows:
                        await ctx.send(
                            "❌ No support data available for latest session"
                        )
                        return

                    sup_embed = discord.Embed(
                        title=f"💉 Support Stats - {latest_date}",
                        description=f"Support activity • {player_count} players",
                        color=0x57F287,
                        timestamp=datetime.now(),
                    )

                    for (
                        name,
                        revives_given,
                        times_revived,
                        kills,
                        deaths,
                    ) in sup_rows:
                        txt = f"Revives Given: `{revives_given or 0}` • Times Revived: `{times_revived or 0}`\n"
                        txt += (
                            f"Kills: `{kills or 0}` • Deaths: `{deaths or 0}`"
                        )
                        sup_embed.add_field(
                            name=f"{name}", value=txt, inline=False
                        )

                    sup_embed.set_footer(text=f"Session: {latest_date}")
                    await ctx.send(embed=sup_embed)
                    return

                # Early short-circuit: sprees-only view (multikills, megas, best sprees)
                if subcommand and subcommand.lower() in ("sprees", "spree"):
                    query = f"""
                        SELECT p.player_name,
                               SUM(p.killing_spree_best) as best_spree,
                               SUM(p.double_kills) as doubles,
                               SUM(p.triple_kills) as triples,
                               SUM(p.quad_kills) as quads,
                               SUM(p.multi_kills) as multis,
                               SUM(p.mega_kills) as megas,
                               SUM(p.kills) as total_kills
                        FROM player_comprehensive_stats p
                        WHERE p.session_id IN ({session_ids_str})
                        GROUP BY p.player_name
                        ORDER BY best_spree DESC, megas DESC
                    """
                    async with db.execute(query, session_ids) as cursor:
                        spree_rows = await cursor.fetchall()

                    if not spree_rows:
                        await ctx.send(
                            "❌ No spree data available for latest session"
                        )
                        return

                    spree_embed = discord.Embed(
                        title=f"🔥 Killing Sprees & Multi-Kills - {latest_date}",
                        description=f"Sprees and monster kills • {player_count} players",
                        color=0xFEE75C,
                        timestamp=datetime.now(),
                    )

                    for i, (
                        name,
                        best_spree,
                        doubles,
                        triples,
                        quads,
                        multis,
                        megas,
                        total_kills,
                    ) in enumerate(spree_rows, 1):
                        if (
                            best_spree == 0
                            and doubles == 0
                            and triples == 0
                            and quads == 0
                            and multis == 0
                            and megas == 0
                        ):
                            continue
                        txt = f"Best Spree: `{best_spree}` • MEGA: `{megas}` • Multis: `{multis}`\n"
                        txt += f"Doubles/Triples/Quads: `{doubles}/{triples}/{quads}` • Kills: `{total_kills}`"
                        spree_embed.add_field(
                            name=f"{i}. {name}", value=txt, inline=False
                        )

                    spree_embed.set_footer(text=f"Session: {latest_date}")
                    await ctx.send(embed=spree_embed)
                    return

                    # Early short-circuit: graphs-only view (generate visuals and return)
                    if subcommand and subcommand.lower() in (
                        "graphs",
                        "graph",
                        "charts",
                    ):
                        try:
                            import matplotlib

                            matplotlib.use("Agg")
                            import io

                            import matplotlib.pyplot as plt

                            query = f"""
                                SELECT p.player_name,
                                       SUM(p.kills) as kills,
                                       SUM(p.deaths) as deaths,
                                       CASE
                                           WHEN SUM(p.time_played_seconds) > 0
                                           THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                                           ELSE 0
                                       END as dpm,
                                       SUM(p.time_played_seconds) as time_played,
                                       CAST(SUM(p.time_played_seconds * p.time_dead_ratio / 100.0) AS INTEGER) as time_dead,
                                       SUM(p.denied_playtime) as denied
                                FROM player_comprehensive_stats p
                                WHERE p.session_id IN ({session_ids_str})
                                GROUP BY p.player_name
                                ORDER BY kills DESC
                                LIMIT 6
                            """
                            async with db.execute(
                                query, session_ids
                            ) as cursor:
                                top_players = await cursor.fetchall()

                            if not top_players:
                                await ctx.send(
                                    "❌ No graph data available for latest session"
                                )
                                return

                            player_names = [p[0] for p in top_players]
                            kills = [p[1] or 0 for p in top_players]
                            deaths = [p[2] or 0 for p in top_players]
                            dpm = [p[3] or 0 for p in top_players]
                            time_played = [
                                p[4] / 60 if p[4] else 0 for p in top_players
                            ]
                            time_dead = [
                                p[5] / 60 if p[5] else 0 for p in top_players
                            ]
                            denied = [p[6] or 0 for p in top_players]

                            fig, axes = plt.subplots(2, 3, figsize=(18, 10))
                            fig.suptitle(
                                f"Visual Performance Analytics - {latest_date}",
                                fontsize=16,
                                fontweight="bold",
                            )

                            # Graph 1: Kills
                            axes[0, 0].bar(
                                range(len(player_names)),
                                kills,
                                color="#57F287",
                            )
                            axes[0, 0].set_title("Kills", fontweight="bold")
                            axes[0, 0].set_xticks(range(len(player_names)))
                            axes[0, 0].set_xticklabels(
                                player_names, rotation=45, ha="right"
                            )

                            # Graph 2: Deaths
                            axes[0, 1].bar(
                                range(len(player_names)),
                                deaths,
                                color="#ED4245",
                            )
                            axes[0, 1].set_title("Deaths", fontweight="bold")
                            axes[0, 1].set_xticks(range(len(player_names)))
                            axes[0, 1].set_xticklabels(
                                player_names, rotation=45, ha="right"
                            )

                            # Graph 3: DPM
                            axes[0, 2].bar(
                                range(len(player_names)), dpm, color="#FEE75C"
                            )
                            axes[0, 2].set_title(
                                "DPM (Damage Per Minute)", fontweight="bold"
                            )
                            axes[0, 2].set_xticks(range(len(player_names)))
                            axes[0, 2].set_xticklabels(
                                player_names, rotation=45, ha="right"
                            )

                            # Graph 4: Time Played
                            axes[1, 0].bar(
                                range(len(player_names)),
                                time_played,
                                color="#5865F2",
                            )
                            axes[1, 0].set_title(
                                "Time Played (minutes)", fontweight="bold"
                            )
                            axes[1, 0].set_xticks(range(len(player_names)))
                            axes[1, 0].set_xticklabels(
                                player_names, rotation=45, ha="right"
                            )

                            # Graph 5: Time Dead
                            axes[1, 1].bar(
                                range(len(player_names)),
                                time_dead,
                                color="#EB459E",
                            )
                            axes[1, 1].set_title(
                                "Time Dead (minutes)", fontweight="bold"
                            )
                            axes[1, 1].set_xticks(range(len(player_names)))
                            axes[1, 1].set_xticklabels(
                                player_names, rotation=45, ha="right"
                            )

                            # Graph 6: Time Denied
                            axes[1, 2].bar(
                                range(len(player_names)),
                                denied,
                                color="#9B59B6",
                            )
                            axes[1, 2].set_title(
                                "Time Denied (seconds)", fontweight="bold"
                            )
                            axes[1, 2].set_xticks(range(len(player_names)))
                            axes[1, 2].set_xticklabels(
                                player_names, rotation=45, ha="right"
                            )

                            plt.tight_layout()

                            buf = io.BytesIO()
                            plt.savefig(
                                buf, format="png", dpi=150, bbox_inches="tight"
                            )
                            buf.seek(0)
                            plt.close()

                            file = discord.File(
                                buf, filename="performance_analytics.png"
                            )
                            await ctx.send(
                                "📊 **Visual Performance Analytics**", file=file
                            )
                            return
                        except ImportError:
                            await ctx.send(
                                "⚠️ matplotlib not installed - graphs unavailable"
                            )
                            return
                        except Exception as e:
                            logger.exception(
                                f"Error generating quick graphs: {e}"
                            )
                            await ctx.send(
                                f"⚠️ Could not generate graphs: {str(e)[:120]}"
                            )
                            return

                # Get ALL players (aggregated across all rounds)
                # Calculate WEIGHTED DPM using actual playtime per round
                query = f"""
                    SELECT p.player_name,
                           SUM(p.kills) as kills,
                           SUM(p.deaths) as deaths,
                           CASE
                               WHEN SUM(p.time_played_seconds) > 0
                               THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                               ELSE 0
                           END as weighted_dpm,
                           COALESCE(SUM(w.hits), 0) as total_hits,
                           COALESCE(SUM(w.shots), 0) as total_shots,
                           COALESCE(SUM(w.headshots), 0) as total_headshots,
                           SUM(p.headshot_kills) as headshot_kills,
                           SUM(p.time_played_seconds) as total_seconds,
                  CAST(SUM(p.time_played_seconds * p.time_dead_ratio / 100.0) AS INTEGER) as total_time_dead,
                  SUM(p.denied_playtime) as total_denied
                    FROM player_comprehensive_stats p
                    LEFT JOIN (
                        SELECT session_id, player_guid,
                               SUM(hits) as hits,
                               SUM(shots) as shots,
                               SUM(headshots) as headshots
                        FROM weapon_comprehensive_stats
                        WHERE weapon_name NOT IN ('WS_GRENADE', 'WS_SYRINGE', 'WS_DYNAMITE', 'WS_AIRSTRIKE', 'WS_ARTILLERY', 'WS_SATCHEL', 'WS_LANDMINE')
                        GROUP BY session_id, player_guid
                    ) w ON p.session_id = w.session_id AND p.player_guid = w.player_guid
                    WHERE p.session_id IN ({session_ids_str})
                    GROUP BY p.player_name
                    ORDER BY kills DESC
                """
                async with db.execute(query, session_ids) as cursor:
                    all_players = await cursor.fetchall()

                # Get team stats (aggregated)
                query = f"""
                    SELECT team,
                           SUM(kills) as total_kills,
                           SUM(deaths) as total_deaths,
                           SUM(damage_given) as total_damage
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                    GROUP BY team
                """
                async with db.execute(query, session_ids) as cursor:
                    team_stats = await cursor.fetchall()

                # Get detailed weapon stats (individual weapons)
                query = f"""
                    SELECT weapon_name,
                           SUM(kills) as total_kills,
                           SUM(deaths) as total_deaths,
                           SUM(hits) as total_hits,
                           SUM(shots) as total_shots,
                           SUM(headshots) as total_headshots
                    FROM weapon_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                    GROUP BY weapon_name
                    HAVING total_kills > 0
                    ORDER BY total_kills DESC
                """
                async with db.execute(query, session_ids) as cursor:
                    await cursor.fetchall()

                # Get per-player weapon mastery
                query = f"""
                    SELECT p.player_name,
                           w.weapon_name,
                           SUM(w.kills) as weapon_kills,
                           SUM(w.hits) as weapon_hits,
                           SUM(w.shots) as weapon_shots,
                           SUM(w.headshots) as weapon_headshots
                    FROM weapon_comprehensive_stats w
                    JOIN player_comprehensive_stats p
                        ON w.session_id = p.session_id
                        AND w.player_guid = p.player_guid
                    WHERE w.session_id IN ({session_ids_str})
                    GROUP BY p.player_name, w.weapon_name
                    HAVING weapon_kills > 0
                    ORDER BY p.player_name, weapon_kills DESC
                """
                async with db.execute(query, session_ids) as cursor:
                    player_weapons = await cursor.fetchall()

                # Get DPM leaderboard (weighted by actual playtime)
                query = f"""
                    SELECT player_name,
                           CASE
                               WHEN SUM(time_played_seconds) > 0
                               THEN (SUM(damage_given) * 60.0) / SUM(time_played_seconds)
                               ELSE 0
                           END as weighted_dpm,
                           SUM(kills) as total_kills,
                           SUM(deaths) as total_deaths
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                    GROUP BY player_name
                    ORDER BY weighted_dpm DESC
                    LIMIT 10
                """
                async with db.execute(query, session_ids) as cursor:
                    dpm_leaders = await cursor.fetchall()

                # Quick incremental 'top' view (from ULTIMATE) - return early for testing
                # Ensure we have total_maps/total_rounds available for the header
                query = f"""
                    SELECT COUNT(DISTINCT session_id) / 2 as total_maps,
                           COUNT(DISTINCT session_id) as total_rounds
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                """
                async with db.execute(query, session_ids) as cursor:
                    map_counts = await cursor.fetchone()
                    total_maps = map_counts[0] if map_counts else 0
                    total_rounds = map_counts[1] if map_counts else 0

                if subcommand and subcommand.lower() in ("top", "top10"):
                    # Fetch top 10 players (by kills)
                    query = f"""
                        SELECT p.player_name,
                               SUM(p.kills) as kills,
                               SUM(p.deaths) as deaths,
                               CASE
                                   WHEN SUM(p.time_played_seconds) > 0
                                   THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                                   ELSE 0
                               END as weighted_dpm,
                               SUM(p.damage_given) as total_damage,
                               SUM(p.headshot_kills) as headshot_kills,
                               SUM(p.gibs) as gibs,
                               SUM(p.time_played_seconds) as total_seconds
                        FROM player_comprehensive_stats p
                        WHERE p.session_id IN ({session_ids_str})
                        GROUP BY p.player_name
                        ORDER BY kills DESC
                        LIMIT 10
                    """
                    async with db.execute(query, session_ids) as cursor:
                        top_players = await cursor.fetchall()

                    embed = discord.Embed(
                        title=f"🏆 Top 10 Players - {latest_date}",
                        description=f"Best performers from {total_maps} maps • {player_count} total players",
                        color=0xFEE75C,
                        timestamp=datetime.now(),
                    )

                    medals = [
                        "🥇",
                        "🥈",
                        "🥉",
                        "4.",
                        "5.",
                        "6.",
                        "7.",
                        "8.",
                        "9.",
                        "10.",
                    ]
                    for i, player in enumerate(top_players):
                        (
                            name,
                            kills,
                            deaths,
                            dpm,
                            damage,
                            hsk,
                            gibs,
                            seconds,
                        ) = player
                        kd = kills / deaths if deaths > 0 else kills
                        hours = int((seconds or 0) // 3600)
                        minutes = int(((seconds or 0) % 3600) // 60)
                        time_display = (
                            f"{hours}h{minutes}m"
                            if hours > 0
                            else f"{minutes}m"
                        )

                        player_stats = (
                            f"{medals[i]} **{name}**\n"
                            f"`{kills}K/{deaths}D ({kd:.2f})` • `{dpm:.0f} DPM` • `{damage:,} DMG`\n"
                            f"`{hsk} HSK` • `{gibs} Gibs` • ⏱️ `{time_display}`\n"
                        )

                        embed.add_field(
                            name="\u200b", value=player_stats, inline=False
                        )

                    embed.set_footer(
                        text="💡 Use !last_session for full session or !last_session help for more views"
                    )

                    # Log field lengths and send
                    try:
                        for idx, fld in enumerate(embed.fields):
                            val = fld.value or ""
                            ln = len(val)
                            logger.debug(
                                f"[last_session/top] field[{idx}] '{fld.name}' length={ln}"
                            )
                            if ln > 1024:
                                logger.warning(
                                    f"[last_session/top] field[{idx}] '{fld.name}' LENGTH {ln} > 1024"
                                )
                    except Exception:
                        logger.exception(
                            "Error while logging top view embed fields"
                        )

                    await ctx.send(embed=embed)
                    return

                # 🎯 TRY TO GET HARDCODED TEAMS FIRST
                hardcoded_teams = await self.get_hardcoded_teams(
                    db, latest_date
                )

                # 📊 Get total maps and rounds played
                # Query for map and round counts
                # Note: COUNT(map_name) counts all plays, including duplicates
                # Example: If te_escape2 is played twice, it counts as 2 maps
                query = f"""
                    SELECT COUNT(DISTINCT session_id) / 2 as total_maps,
                           COUNT(DISTINCT session_id) as total_rounds
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                """
                async with db.execute(query, session_ids) as cursor:
                    map_stats = await cursor.fetchone()
                    total_maps = map_stats[0] if map_stats else 0
                    total_rounds = map_stats[1] if map_stats else 0

                # 🏆 Calculate Stopwatch team scores
                scorer = StopwatchScoring(self.bot.db_path)
                scoring_result = scorer.calculate_session_scores(latest_date)

                # Extract team scores (team names are top-level keys)
                if scoring_result:
                    # Get team names (exclude 'maps' and 'total_maps' keys)
                    team_names = [
                        k
                        for k in scoring_result.keys()
                        if k not in ["maps", "total_maps"]
                    ]
                    if len(team_names) >= 2:
                        team_1_name = team_names[0]
                        team_2_name = team_names[1]
                        team_1_score = scoring_result[team_1_name]
                        team_2_score = scoring_result[team_2_name]
                    else:
                        team_1_name = "Team 1"
                        team_2_name = "Team 2"
                        team_1_score = 0
                        team_2_score = 0
                else:
                    team_1_name = "Team 1"
                    team_2_name = "Team 2"
                    team_1_score = 0
                    team_2_score = 0

                # NOTE: Removed legacy hardcoded override for 2025-10-02
                # The StopwatchScoring result computed above (scoring_result)
                # should be used directly. Overriding with hardcoded values
                # caused incorrect final scores and has been intentionally
                # removed. If a temporary patch is needed in future, comment
                # this section and add a clear justification.

                if hardcoded_teams:
                    # ✅ We have hardcoded teams! Use them for accurate team tracking
                    logger.info(
                        "✅ Using hardcoded teams from session_teams table"
                    )

                    # Extract team names and create GUID-to-team mapping
                    team_names_list = list(hardcoded_teams.keys())
                    team_1_name = (
                        team_names_list[0]
                        if len(team_names_list) > 0
                        else "Team A"
                    )
                    team_2_name = (
                        team_names_list[1]
                        if len(team_names_list) > 1
                        else "Team B"
                    )

                    # Create GUID -> team_name mapping
                    guid_to_team = {}
                    for team_name, team_data in hardcoded_teams.items():
                        for guid in team_data["guids"]:
                            guid_to_team[guid] = team_name

                    # Get player GUIDs to map names to teams
                    query = f"""
                        SELECT DISTINCT player_name, player_guid
                        FROM player_comprehensive_stats
                        WHERE session_id IN ({session_ids_str})
                    """
                    async with db.execute(query, session_ids) as cursor:
                        player_guid_map = await cursor.fetchall()

                    # Build name -> team mapping
                    name_to_team = {}
                    for player_name, player_guid in player_guid_map:
                        if player_guid in guid_to_team:
                            name_to_team[player_name] = guid_to_team[
                                player_guid
                            ]

                    # Organize players by hardcoded team
                    team_1_players_list = [
                        name
                        for name, team in name_to_team.items()
                        if team == team_1_name
                    ]
                    team_2_players_list = [
                        name
                        for name, team in name_to_team.items()
                        if team == team_2_name
                    ]

                    # No team swappers when using hardcoded teams (they stay consistent)
                    team_swappers = {}
                    player_teams = {
                        name: [(team, 1)]
                        for name, team in name_to_team.items()
                    }

                else:
                    # ❌ No hardcoded teams - auto-detect persistent teams, then re-fetch
                    created = await self._detect_and_store_persistent_teams(db, latest_date)
                    hardcoded_teams = await self.get_hardcoded_teams(db, latest_date)
                    if hardcoded_teams:
                        team_names_list = list(hardcoded_teams.keys())
                        team_1_name = team_names_list[0] if len(team_names_list) > 0 else "Team A"
                        team_2_name = team_names_list[1] if len(team_names_list) > 1 else "Team B"

                        # Build name mapping using GUIDs
                        guid_to_team = {}
                        for team_name, team_data in hardcoded_teams.items():
                            for guid in team_data["guids"]:
                                guid_to_team[guid] = team_name

                        query = f"""
                            SELECT DISTINCT player_name, player_guid
                            FROM player_comprehensive_stats
                            WHERE session_id IN ({session_ids_str})
                        """
                        async with db.execute(query, session_ids) as cursor:
                            player_guid_map = await cursor.fetchall()

                        name_to_team = {}
                        for player_name, player_guid in player_guid_map:
                            if player_guid in guid_to_team:
                                name_to_team[player_name] = guid_to_team[player_guid]

                        team_1_players_list = [
                            name for name, team in name_to_team.items() if team == team_1_name
                        ]
                        team_2_players_list = [
                            name for name, team in name_to_team.items() if team == team_2_name
                        ]

                        team_swappers = {}
                        player_teams = {name: [(team, 1)] for name, team in name_to_team.items()}
                    else:
                        # Final minimal fallback if detection failed
                        team_1_name = "Team 1"
                        team_2_name = "Team 2"
                        team_1_players_list = []
                        team_2_players_list = []
                        team_swappers = {}

                # 🎯 GET MVP PER TEAM (using hardcoded teams if available)
                team_mvps = {}

                if hardcoded_teams:
                    # ✅ Calculate MVP per hardcoded team (by GUID)
                    for team_name, team_data in hardcoded_teams.items():
                        team_guids = team_data["guids"]
                        team_guids_placeholders = ",".join(
                            "?" * len(team_guids)
                        )

                        query = f"""
                            SELECT player_name, SUM(kills) as total_kills, player_guid
                            FROM player_comprehensive_stats
                            WHERE session_id IN ({session_ids_str})
                            AND player_guid IN ({team_guids_placeholders})
                            GROUP BY player_name, player_guid
                            ORDER BY total_kills DESC
                            LIMIT 1
                        """
                        params = session_ids + team_guids
                        async with db.execute(query, params) as cursor:
                            result = await cursor.fetchone()
                            if result:
                                player_name, kills, guid = result
                                team_mvps[team_name] = (player_name, kills)
                else:
                    # ❌ Fall back to old Axis/Allies MVP calculation
                    query = f"""
                        SELECT team, player_name, SUM(kills) as total_kills
                        FROM player_comprehensive_stats
                        WHERE session_id IN ({session_ids_str})
                        GROUP BY team, player_name
                        ORDER BY team, total_kills DESC
                    """
                    async with db.execute(query, session_ids) as cursor:
                        team_mvps_raw = await cursor.fetchall()

                    # Get top player per team
                    for team, player, kills in team_mvps_raw:
                        if team not in team_mvps:
                            team_mvps[team] = (player, kills)

                # 🎯 GET DETAILED MVP STATS (using hardcoded teams if available)
                team_1_mvp_stats = None
                team_2_mvp_stats = None

                if hardcoded_teams:
                    # ✅ Get MVP stats for hardcoded teams
                    for team_name in [team_1_name, team_2_name]:
                        if team_name in team_mvps:
                            player, kills = team_mvps[team_name]
                            team_guids = hardcoded_teams[team_name]["guids"]
                            team_guids_placeholders = ",".join(
                                "?" * len(team_guids)
                            )

                            query = f"""
                                SELECT
                                    CASE
                                        WHEN SUM(time_played_seconds) > 0
                                        THEN (SUM(damage_given) * 60.0) / SUM(time_played_seconds)
                                        ELSE 0
                                    END as weighted_dpm,
                                    SUM(deaths),
                                    SUM(revives_given),
                                    SUM(gibs)
                                FROM player_comprehensive_stats
                                WHERE session_id IN ({session_ids_str})
                                AND player_name = ?
                                AND player_guid IN ({team_guids_placeholders})
                            """
                            params = session_ids + [player] + team_guids
                            async with db.execute(query, params) as cursor:
                                result = await cursor.fetchone()
                                if result:
                                    mvp_stats = (
                                        player,
                                        kills,
                                        result[0],
                                        result[1],
                                        result[2],
                                        result[3],
                                    )
                                    if team_name == team_1_name:
                                        team_1_mvp_stats = mvp_stats
                                    else:
                                        team_2_mvp_stats = mvp_stats
                else:
                    # ❌ Fall back to old Axis/Allies MVP stats
                    if 1 in team_mvps:
                        player, kills = team_mvps[1]
                        query = f"""
                            SELECT
                                CASE
                                    WHEN SUM(time_played_seconds) > 0
                                    THEN (SUM(damage_given) * 60.0) / SUM(time_played_seconds)
                                    ELSE 0
                                END as weighted_dpm,
                                SUM(deaths),
                                SUM(revives_given),
                                SUM(gibs)
                            FROM player_comprehensive_stats
                            WHERE session_id IN ({session_ids_str})
                            AND player_name = ? AND team = 1
                        """
                        async with db.execute(
                            query, session_ids + [player]
                        ) as cursor:
                            result = await cursor.fetchone()
                            if result:
                                team_1_mvp_stats = (
                                    player,
                                    kills,
                                    result[0],
                                    result[1],
                                    result[2],
                                    result[3],
                                )

                    if 2 in team_mvps:
                        player, kills = team_mvps[2]
                        query = f"""
                            SELECT
                                CASE
                                    WHEN SUM(time_played_seconds) > 0
                                    THEN (SUM(damage_given) * 60.0) / SUM(time_played_seconds)
                                    ELSE 0
                                END as weighted_dpm,
                                SUM(deaths),
                                SUM(revives_given),
                                SUM(gibs)
                            FROM player_comprehensive_stats
                            WHERE session_id IN ({session_ids_str})
                            AND player_name = ? AND team = 2
                        """
                        async with db.execute(
                            query, session_ids + [player]
                        ) as cursor:
                            result = await cursor.fetchone()
                            if result:
                                team_2_mvp_stats = (
                                    player,
                                    kills,
                                    result[0],
                                    result[1],
                                    result[2],
                                    result[3],
                                )

                # Count rounds won by each team (winners determined by session data)
                # For now, we'll count based on team performance
                # This is a simplified version - you might want to track actual round winners
                axis_rounds = sum(
                    1 for s in sessions if s[2] % 2 == 1
                )  # Odd rounds
                allies_rounds = sum(
                    1 for s in sessions if s[2] % 2 == 0
                )  # Even rounds

                # Fetch awards/objective stats data (MUST BE BEFORE CONNECTION CLOSES)
                query = f"""
                    SELECT clean_name, xp, kill_assists, objectives_stolen, objectives_returned,
                           dynamites_planted, dynamites_defused, times_revived,
                           double_kills, triple_kills, quad_kills, multi_kills, mega_kills,
                           denied_playtime, most_useful_kills, useless_kills, gibs,
                           killing_spree_best, death_spree_worst
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                """
                async with db.execute(query, session_ids) as cursor:
                    awards_data = await cursor.fetchall()

                # Fetch player revives for weapon mastery embed
                query = f"""
                    SELECT player_name, SUM(revives_given) as revives
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                    GROUP BY player_name
                """
                async with db.execute(query, session_ids) as cursor:
                    player_revives_raw = await cursor.fetchall()

                # Fetch per-map breakdown data for Graph 3
                query = f"""
                    SELECT
                        s.map_name,
                        p.clean_name,
                        SUM(p.kills) as kills,
                        SUM(p.deaths) as deaths,
                        AVG(p.dpm) as avg_dpm
                    FROM player_comprehensive_stats p
                    JOIN sessions s ON p.session_id = s.id
                    WHERE p.session_id IN ({session_ids_str})
                    GROUP BY s.map_name, p.clean_name
                    ORDER BY s.map_name, kills DESC
                """
                async with db.execute(query, session_ids) as cursor:
                    per_map_data = await cursor.fetchall()

                # Fetch additional stats for Graph 2 (Revives, Gibs, Useful Kills)
                query = f"""
                    SELECT
                        clean_name,
                        SUM(revives_given) as total_revives,
                        SUM(gibs) as total_gibs,
                        SUM(most_useful_kills) as total_useful_kills,
                        SUM(damage_given) as total_damage
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                    GROUP BY clean_name
                    ORDER BY total_damage DESC
                    LIMIT 6
                """
                async with db.execute(query, session_ids) as cursor:
                    advanced_graph_data = await cursor.fetchall()

                # Fetch chaos/awards stats (teamkills, self-kills, efficiency, etc)
                query = f"""
                    SELECT
                        clean_name,
                        SUM(team_kills) as total_teamkills,
                        SUM(self_kills) as total_selfkills,
                        SUM(kill_steals) as total_steals,
                        SUM(bullets_fired) as total_bullets,
                        SUM(kills) as total_kills,
                        SUM(deaths) as total_deaths,
                        SUM(damage_given) as total_dmg_given,
                        SUM(damage_received) as total_dmg_received,
                        SUM(constructions) as total_constructions,
                        SUM(tank_meatshield) as total_tank,
                        SUM(useless_kills) as total_useless_kills,
                        MAX(death_spree_worst) as worst_death_spree,
                        SUM(time_played_seconds) as total_time
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                    GROUP BY clean_name
                """
                async with db.execute(query, session_ids) as cursor:
                    chaos_awards_data = await cursor.fetchall()

            # ═══════════════════════════════════════════════════════
            # All database queries complete - connection closed
            # Now build and send embeds
            # ═══════════════════════════════════════════════════════

            

            # ═══════════════════════════════════════════════════════
            # MESSAGE 1: Session Overview
            # ═══════════════════════════════════════════════════════
            # Use total_maps from earlier query (counts te_escape2 twice if played twice)
            maps_played = total_maps  # This correctly counts duplicate maps
            rounds_played = len(sessions)

            # Early short-circuit: graphs-only view (images only)
            if subcommand and subcommand.lower() in ("graphs", "graph", "charts"):
                try:
                    import io

                    # Build per-map aggregates (open a fresh DB connection)
                    maps_aggregates = []
                    async with aiosqlite.connect(self.bot.db_path) as db2:
                        q = f"""
                       SELECT s.map_name,
                            SUM(p.kills) as kills,
                            SUM(p.deaths) as deaths,
                            SUM(p.gibs) as gibs,
                            SUM(p.time_played_seconds) / 60.0 as time_played,
                            SUM(p.denied_playtime) as denied,
                            CAST(SUM(p.time_played_seconds * p.time_dead_ratio / 100.0) / 60.0 AS FLOAT) as time_dead,
                            SUM(p.revives_given) as revives,
                            SUM(p.damage_given) as damage_given,
                            SUM(p.damage_received) as damage_received,
                            CASE WHEN SUM(p.time_played_seconds) > 0
                                THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                                ELSE 0
                            END as dpm
                            FROM player_comprehensive_stats p
                            JOIN sessions s ON p.session_id = s.id
                            WHERE p.session_id IN ({session_ids_str})
                            GROUP BY s.map_name
                            ORDER BY s.map_name
                        """
                        async with db2.execute(q, session_ids) as cursor:
                            rows = await cursor.fetchall()
                            for r in rows:
                                maps_aggregates.append(
                                    {
                                        "map": r[0],
                                        "kills": r[1] or 0,
                                        "deaths": r[2] or 0,
                                        "gibs": r[3] or 0,
                                        "time_played": float(r[4] or 0),
                                        "denied": r[5] or 0,
                                        "time_dead": float(r[6] or 0),
                                        "damage_given": r[7] or 0,
                                        "damage_received": r[8] or 0,
                                        "dpm": float(r[9] or 0),
                                    }
                                )

                    # Prepare an ordered map -> sessions mapping for the date
                    maps_to_sessions = {}
                    for sid, mname, rnd, atime in sessions:
                        maps_to_sessions.setdefault(mname, []).append((sid, rnd))

                    # For each map in aggregate order: send Round 1, Round 2, then Map Summary (12-panel)
                    for ma in maps_aggregates:
                        map_name = ma.get("map")
                        # send round images for each session id (ordered)
                        sessions_for_map = maps_to_sessions.get(map_name, [])
                        for sid, rnd in sessions_for_map:
                            try:
                                # Prefer retro viz per integration: try to locate raw stats file
                                try:
                                    async with aiosqlite.connect(self.bot.db_path) as db_lookup:
                                        async with db_lookup.execute(
                                            "SELECT session_date FROM sessions WHERE id = ?",
                                            (sid,),
                                        ) as cur:
                                            row = await cur.fetchone()
                                        session_date = row[0] if row else None

                                    stats_file_path = None
                                    if session_date:
                                        date_part = session_date[:10]
                                        time_part = session_date[11:19].replace(':', '') if len(session_date) >= 19 else ''
                                        if time_part:
                                            filename = f"{date_part}-{time_part}-{map_name}-round-{rnd}.txt"
                                            candidate = os.path.join('local_stats', filename)
                                            if os.path.exists(candidate):
                                                stats_file_path = candidate
                                except Exception:
                                    stats_file_path = None

                                if stats_file_path:
                                    # Delegate to unified poster (PNG + primary + detailed text)
                                    try:
                                        ok = await self._post_retro_round_complete(ctx, stats_file_path, map_name, rnd, sid)
                                        if ok:
                                            # already posted
                                            continue
                                    except Exception:
                                        logger.exception(f"_post_retro_round_complete failed for {stats_file_path}")

                                # Fallback: use existing aggregated 12-panel generator
                                buf = await self.generate_round_graphs(sid, rnd, map_name)
                                if buf:
                                    fname = f"{map_name}_round{rnd}_retro.png"
                                    file = discord.File(buf, filename=fname)
                                    await ctx.send(file=file)
                                    await asyncio.sleep(2)

                            except Exception as e:
                                logger.exception(f"Error sending round graph for {map_name} r{rnd}: {e}")

                        # Map summary (both rounds combined) - use aggregated 12-panel
                        try:
                            map_where = f"session_id IN ({session_ids_str}) AND map_name = ?"
                            map_params = tuple(session_ids) + (map_name,)
                            async with aiosqlite.connect(self.bot.db_path) as db_map:
                                map_rows = await self._generate_aggregated_stats(db_map, map_where, map_params)
                                if map_rows:
                                    playtimes = [int(r[9] or 0) for r in map_rows]
                                    shared_play = int(max(playtimes)) if playtimes else 0
                                    title = f"Map Summary: {map_name}"
                                    buf = await self._build_12panel_figure(map_rows, title, playtime_shared=shared_play)
                                    if buf:
                                        file = discord.File(buf, filename=f"{map_name}_summary.png")
                                        await ctx.send(file=file)
                                        await asyncio.sleep(2)
                        except Exception as e:
                            logger.exception(f"Error generating/sending map summary 12-panel for {map_name}: {e}")

                    # Finally, build and send session-level aggregated 12-panel figure
                    try:
                        # Aggregate across all session_ids for the date
                        where_all = f"session_id IN ({session_ids_str})"
                        async with aiosqlite.connect(self.bot.db_path) as db3:
                            rows = await self._generate_aggregated_stats(db3, where_all, tuple(session_ids))

                        if rows:
                            playtimes = [int(r[9] or 0) for r in rows]
                            shared_play = int(max(playtimes)) if playtimes else 0
                            title = f"Session Stats: {latest_date}"
                            buf = await self._build_12panel_figure(rows, title, playtime_shared=shared_play)
                            if buf:
                                file = discord.File(buf, filename="session_stats_total.png")
                                await ctx.send(file=file)
                    except Exception as e:
                        logger.exception(f"Error generating/sending session total graphs: {e}")

                    return
                except ImportError:
                    await ctx.send(
                        "⚠️ matplotlib not installed - graphs unavailable"
                    )
                    return
                except Exception as e:
                    logger.exception(f"Error generating graphs-only images: {e}")
                    await ctx.send(f"⚠️ Could not generate graphs: {str(e)[:200]}")
                    return

            # Build description with team scores if available
            description = (
                f"**{maps_played} maps** • **{rounds_played} rounds** • "
                f"**{player_count} players**"
            )

            # Add Stopwatch team scores if calculated
            if team_1_score > 0 or team_2_score > 0:
                winner_icon = (
                    "🏆"
                    if team_1_score > team_2_score
                    else ("🏆" if team_2_score > team_1_score else "🤝")
                )
                description += f"\n\n**🎯 FINAL SCORE:** {winner_icon}\n"
                description += f"**{team_1_name}:** {team_1_score} points\n"
                description += f"**{team_2_name}:** {team_2_score} points"
                if team_1_score == team_2_score:
                    description += " *(TIE)*"

            embed1 = discord.Embed(
                title=f"📊 Session Summary: {latest_date}",
                description=description,
                color=0x5865F2,
                timestamp=datetime.now(),
            )

            # Maps list - count ALL round 2 completions for each map
            maps_text = ""
            map_play_counts = {}
            for session_id, map_name, round_num, actual_time in sessions:
                # Count EVERY time we see round 2 (completes a 2-round map play)
                if round_num == 2:
                    map_play_counts[map_name] = (
                        map_play_counts.get(map_name, 0) + 1
                    )

            for map_name, plays in map_play_counts.items():
                rounds = plays * 2
                maps_text += f"• **{map_name}** ({rounds} rounds)\n"

            if maps_text:
                embed1.add_field(
                    name="🗺️ Maps Played", value=maps_text, inline=False
                )

            # All players on embed1 (chunk into safe-sized fields to avoid Discord limits)
            if all_players:
                top_text = ""
                medals = [
                    "🥇",
                    "🥈",
                    "🥉",
                    "4️⃣",
                    "5️⃣",
                    "6️⃣",
                    "7️⃣",
                    "8️⃣",
                    "9️⃣",
                    "🔟",
                ]
                for i, player in enumerate(all_players):
                    name, kills, deaths, dpm, hits, shots = player[0:6]
                    (
                        total_hs,
                        hsk,
                        total_seconds,
                        total_time_dead,
                        total_denied,
                    ) = player[6:11]

                    # Handle NULL values from database
                    kills = kills or 0
                    deaths = deaths or 0
                    dpm = dpm or 0
                    hits = hits or 0
                    shots = shots or 0
                    total_hs = total_hs or 0
                    hsk = hsk or 0
                    total_seconds = total_seconds or 0

                    # Convert seconds to MM:SS format
                    minutes = int(total_seconds // 60)
                    seconds = int(total_seconds % 60)
                    time_display = f"{minutes}:{seconds:02d}"

                    # Calculate time dead
                    time_dead_seconds = int(total_time_dead or 0)
                    dead_minutes = int(time_dead_seconds // 60)
                    dead_seconds = int(time_dead_seconds % 60)
                    time_dead_display = f"{dead_minutes}:{dead_seconds:02d}"

                    # Calculate time denied (NEW)
                    total_denied = int(total_denied or 0)
                    denied_minutes = int(total_denied // 60)
                    denied_seconds = int(total_denied % 60)
                    time_denied_display = (
                        f"{denied_minutes}:{denied_seconds:02d}"
                    )

                    # Calculate metrics
                    kd_ratio = kills / deaths if deaths > 0 else kills
                    acc = (hits / shots * 100) if shots and shots > 0 else 0
                    # HS rate = headshots / hits
                    hs_rate = (
                        (total_hs / hits * 100) if hits and hits > 0 else 0
                    )

                    medal = medals[i] if i < len(medals) else f"{i + 1}."
                    top_text += f"{medal} **{name}**\n"
                    # Line 1: Core combat stats
                    top_text += (
                        f"`{kills}K/{deaths}D ({kd_ratio:.2f})` • "
                        f"`{dpm:.0f} DPM` • "
                        f"`{acc:.1f}% ACC ({hits}/{shots})`\n"
                    )
                    # Line 2: Time stats and headshots (UPDATED: removed HSK, added time denied)
                    top_text += (
                        f"`{total_hs} HS ({hs_rate:.1f}%)` • "
                        f"⏱️ `{time_display}` • 💀 `{time_dead_display}` • ⏳ `{time_denied_display}`\n\n"
                    )

                # Use helper _split_chunks (defined earlier) to breakup long player text

                chunks = _split_chunks(top_text.rstrip(), max_len=900)

                if len(chunks) == 1:
                    embed1.add_field(
                        name="🏆 All Players", value=chunks[0], inline=False
                    )
                else:
                    # First chunk goes into the primary embed
                    embed1.add_field(
                        name="🏆 All Players", value=chunks[0], inline=False
                    )
                    # Build continuation embeds for the rest and attach to ctx for later sending
                    cont_embeds = []
                    for ch in chunks[1:]:
                        cont = discord.Embed(
                            title=f"📊 Session Summary: {latest_date} (cont.)",
                            color=0x5865F2,
                            timestamp=datetime.now(),
                        )
                        cont.add_field(
                            name="🏆 All Players (cont.)",
                            value=ch,
                            inline=False,
                        )
                        cont_embeds.append(cont)

                    # Save on ctx so the existing send loop below will pick them up
                    setattr(ctx, "_last_session_continuation", cont_embeds)

            embed1.set_footer(text=f"Session: {latest_date}")

            # Use shared Cog-level _log_and_send helper to send embed1 and any
            # continuations created earlier.
            await self._log_and_send(
                ctx, embed1, "embed1", latest_date=latest_date
            )

            # Send any continuation embeds created when chunking large fields
            if (
                hasattr(ctx, "_last_session_continuation")
                and ctx._last_session_continuation
            ):
                cont_embeds = getattr(ctx, "_last_session_continuation")
                for i, cont in enumerate(cont_embeds):
                    # Page numbering: first embed is embed1, continuations start at page 2
                    cont.set_footer(
                        text=f"Session: {latest_date} • Page {i+2}/{len(cont_embeds)+1}"
                    )
                    await self._log_and_send(
                        ctx, cont, f"cont_{i+2}", latest_date=latest_date
                    )
                    await asyncio.sleep(1.5)

            # Default behavior: if no subcommand was requested, stop after the
            # compact session summary and any continuation embeds. This makes
            # `!last_session` concise by default while preserving all subcommand
            # flows (e.g., `full`, `graphs`, `combat`, etc.).
            if not subcommand:
                return

            await asyncio.sleep(2)  # Rate limit protection

            # ═══════════════════════════════════════════════════════
            # GENERATE BEAUTIFUL SESSION OVERVIEW IMAGE
            # ═══════════════════════════════════════════════════════
            try:
                from image_generator import StatsImageGenerator

                generator = StatsImageGenerator()

                # Prepare session data
                session_info = {
                    "date": latest_date,
                    "maps": maps_played,
                    "rounds": rounds_played,
                    "players": player_count,
                }

                # Prepare all players data (use top 5 for image)
                top_players_data = []
                for player in all_players[:5]:
                    name, kills, deaths, dpm, hits, shots = player[0:6]
                    total_hs, hsk, total_seconds, total_time_dead = player[
                        6:10
                    ]

                    kd_ratio = (
                        kills / deaths
                        if deaths and deaths > 0
                        else (kills or 0)
                    )
                    acc = (hits / shots * 100) if shots and shots > 0 else 0
                    hsk_rate = (
                        (hsk / kills * 100) if kills and kills > 0 else 0
                    )
                    hs_rate = (
                        (total_hs / hits * 100) if hits and hits > 0 else 0
                    )

                    # Convert seconds to minutes for playtime display
                    playtime_minutes = (total_seconds or 0) / 60.0

                    top_players_data.append(
                        {
                            "name": name,
                            "kills": kills,
                            "deaths": deaths,
                            "kd": kd_ratio,
                            "dpm": dpm,
                            "acc": acc,
                            "hits": hits,
                            "shots": shots,
                            "hsk": hsk,
                            "hsk_rate": hsk_rate,
                            "hs": total_hs,
                            "hs_rate": hs_rate,
                            "playtime": playtime_minutes,
                        }
                    )

                # Prepare team data for image
                team_data_for_img = {"team1": {}, "team2": {}}

                for team, kills, deaths, damage in team_stats:
                    kd = kills / deaths if deaths > 0 else kills
                    team_info = {
                        "kills": kills,
                        "deaths": deaths,
                        "kd": kd,
                        "damage": damage,
                    }

                    if team == 1:
                        team_data_for_img["team1"] = team_info
                        if team_1_mvp_stats:
                            p, k, dpm, d, revived, gibs = team_1_mvp_stats
                            team_data_for_img["team1"]["mvp"] = {
                                "name": p,
                                "kd": k / d if d else k,
                                "dpm": dpm,
                            }
                    elif team == 2:
                        team_data_for_img["team2"] = team_info
                        if team_2_mvp_stats:
                            p, k, dpm, d, revived, gibs = team_2_mvp_stats
                            team_data_for_img["team2"]["mvp"] = {
                                "name": p,
                                "kd": k / d if d else k,
                                "dpm": dpm,
                            }

                # Generate the beautiful image!
                img_buf = generator.create_session_overview(
                    session_info,
                    top_players_data,
                    team_data_for_img,
                    (team_1_name, team_2_name),
                )

                file = discord.File(img_buf, filename="session_overview.png")
                await ctx.send("🎨 **Session Overview**", file=file)

            except Exception as e:
                logger.error(
                    f"Error generating session image: {e}", exc_info=True
                )

            # ═══════════════════════════════════════════════════════
            # MESSAGE 2: Team Analytics
            # ═══════════════════════════════════════════════════════
            # Build description with match score if available
            analytics_desc = "Comprehensive team performance comparison"
            if hardcoded_teams and team_1_score + team_2_score > 0:
                if team_1_score == team_2_score:
                    analytics_desc += f"\n\n🤝 **Maps Won: {team_1_score} - {team_2_score} (PERFECT TIE)**"
                else:
                    analytics_desc += (
                        f"\n\n🏆 **Maps Won: {team_1_score} - {team_2_score}**"
                    )

            embed2 = discord.Embed(
                title=f"⚔️ Team Analytics - {team_1_name} vs {team_2_name}",
                description=analytics_desc,
                color=0xED4245,
                timestamp=datetime.now(),
            )

            # Team stats - separate fields for each team for better readability
            if len(team_stats) > 1:
                for team, kills, deaths, damage in team_stats:
                    if team == 1:
                        current_team_name = team_1_name
                        emoji = "🔴"
                    elif team == 2:
                        current_team_name = team_2_name
                        emoji = "🔵"
                    else:
                        continue

                    kd_ratio = kills / deaths if deaths > 0 else kills

                    team_text = (
                        f"**Total Kills:** `{kills:,}`\n"
                        f"**Total Deaths:** `{deaths:,}`\n"
                        f"**K/D Ratio:** `{kd_ratio:.2f}`\n"
                        f"**Total Damage:** `{damage:,}`\n"
                    )

                    embed2.add_field(
                        name=f"{emoji} {current_team_name} Team Stats",
                        value=team_text,
                        inline=True,
                    )

            # Team MVPs (using pre-fetched stats)
            if team_1_mvp_stats:
                player, kills, dpm, deaths, revives, gibs = team_1_mvp_stats
                kd = kills / deaths if deaths else kills
                team_1_mvp_text = (
                    f"**{player}**\n"
                    f"💀 `{kd:.1f} K/D` ({kills}K/{deaths}D)\n"
                    f"💥 `{dpm:.0f} DPM`\n"
                    f"💉 `{revives} Teammates Revived` • 🦴 `{gibs} Gibs`"
                )
                embed2.add_field(
                    name=f"🔴 {team_1_name} MVP",
                    value=team_1_mvp_text,
                    inline=True,
                )

            if team_2_mvp_stats:
                player, kills, dpm, deaths, revives, gibs = team_2_mvp_stats
                kd = kills / deaths if deaths else kills
                team_2_mvp_text = (
                    f"**{player}**\n"
                    f"💀 `{kd:.1f} K/D` ({kills}K/{deaths}D)\n"
                    f"💥 `{dpm:.0f} DPM`\n"
                    f"💉 `{revives} Teammates Revived` • 🦴 `{gibs} Gibs`"
                )
                embed2.add_field(
                    name=f"🔵 {team_2_name} MVP",
                    value=team_2_mvp_text,
                    inline=True,
                )

            embed2.set_footer(text=f"Session: {latest_date}")
            await self._log_and_send(
                ctx, embed2, "embed2", latest_date=latest_date
            )
            await asyncio.sleep(4)  # Rate limit protection

            # ═══════════════════════════════════════════════════════
            # MESSAGE 3: Team Composition
            # ═══════════════════════════════════════════════════════
            embed3 = discord.Embed(
                title="👥 Team Composition",
                description=(
                    f"Player roster for {team_1_name} vs {team_2_name}\n"
                    f"🔄 indicates players who swapped teams during session"
                ),
                color=0x57F287,
                timestamp=datetime.now(),
            )

            # 🎯 Organize players by team (using hardcoded teams if available)
            team_1_players = []
            team_2_players = []

            if hardcoded_teams:
                # ✅ Use hardcoded team assignments
                team_1_players = [
                    (name, 1, False) for name in team_1_players_list
                ]
                team_2_players = [
                    (name, 1, False) for name in team_2_players_list
                ]
            else:
                # ❌ Fall back to Axis/Allies grouping
                for player, teams in player_teams.items():
                    primary_team, primary_rounds = teams[0]

                    if primary_team == 1:
                        team_1_players.append(
                            (player, primary_rounds, len(teams) > 1)
                        )
                    elif primary_team == 2:
                        team_2_players.append(
                            (player, primary_rounds, len(teams) > 1)
                        )

                team_1_players.sort(key=lambda x: x[1], reverse=True)
                team_2_players.sort(key=lambda x: x[1], reverse=True)

            # Team 1 roster
            if team_1_players:
                team_1_text = f"**{len(team_1_players)} players**\n\n"
                for i, (player, rounds, swapped) in enumerate(
                    team_1_players[:15], 1
                ):
                    swap_indicator = " 🔄" if swapped else ""
                    team_1_text += f"{i}. {player}{swap_indicator}\n"
                if len(team_1_players) > 15:
                    more_count = len(team_1_players) - 15
                    team_1_text += f"\n*...and {more_count} more*"
                embed3.add_field(
                    name=f"🔴 {team_1_name} Roster",
                    value=team_1_text.rstrip(),
                    inline=True,
                )

            # Team 2 roster
            if team_2_players:
                team_2_text = f"**{len(team_2_players)} players**\n\n"
                for i, (player, rounds, swapped) in enumerate(
                    team_2_players[:15], 1
                ):
                    swap_indicator = " 🔄" if swapped else ""
                    team_2_text += f"{i}. {player}{swap_indicator}\n"
                if len(team_2_players) > 15:
                    more_count = len(team_2_players) - 15
                    team_2_text += f"\n*...and {more_count} more*"
                embed3.add_field(
                    name=f"🔵 {team_2_name} Roster",
                    value=team_2_text.rstrip(),
                    inline=True,
                )

            # Team swaps (only show if NOT using hardcoded teams OR if actual swaps detected)
            if team_swappers and not hardcoded_teams:
                swap_text = ""
                for player, teams in list(team_swappers.items())[:10]:
                    team_names = []
                    for team, rounds in teams:
                        if team == 1:
                            team_names.append(f"🔴({rounds}r)")
                        elif team == 2:
                            team_names.append(f"🔵({rounds}r)")
                    swap_text += f"• **{player}**: {' → '.join(team_names)}\n"
                embed3.add_field(
                    name="🔄 Team Swaps", value=swap_text.rstrip(), inline=False
                )
            elif hardcoded_teams and not team_swappers:
                # Show confirmation that no swaps occurred
                embed3.add_field(
                    name="✅ Team Consistency",
                    value="No mid-session player swaps detected",
                    inline=False,
                )

            # 📊 Add session statistics with match score
            # Note: total_maps already calculated correctly (counts duplicates)
            unique_map_names = len(set(s[1] for s in sessions))
            session_info = (
                f"📍 **{total_rounds} rounds** played ({total_maps} maps)\n"
            )
            session_info += "🎮 **Format**: Stopwatch (2 rounds per map)\n"
            session_info += f"🗺️ **Unique map names**: {unique_map_names}\n"

            # Add match score if we have hardcoded teams
            if hardcoded_teams and team_1_score + team_2_score > 0:
                if team_1_score == team_2_score:
                    session_info += f"\n🤝 **Maps Won**: {team_1_name} {team_1_score} - {team_2_score} {team_2_name} (TIE)"
                else:
                    session_info += f"\n🏆 **Maps Won**: {team_1_name} {team_1_score} - {team_2_score} {team_2_name}"

            embed3.add_field(
                name="📊 Session Info", value=session_info, inline=False
            )

            embed3.set_footer(text=f"Session: {latest_date}")
            await self._log_and_send(
                ctx, embed3, "embed3", latest_date=latest_date
            )
            await asyncio.sleep(8)  # Rate limit protection

            # ═══════════════════════════════════════════════════════
            # MESSAGE 4: DPM Analytics
            # ═══════════════════════════════════════════════════════
            embed4 = discord.Embed(
                title="💥 DPM Analytics - Damage Per Minute",
                description="Enhanced DPM with Kill/Death Details",
                color=0xFEE75C,
                timestamp=datetime.now(),
            )

            # DPM Leaderboard with calculation details
            if dpm_leaders:
                dpm_text = ""
                # Get time played for each player to show calculation
                for i, (player, dpm, kills, deaths) in enumerate(
                    dpm_leaders[:10], 1
                ):
                    kd = kills / deaths if deaths else kills
                    dpm_text += f"{i}. **{player}**\n"
                    dpm_text += f"   💥 `{dpm:.0f} DPM` • 💀 `{kd:.1f} K/D` ({kills}K/{deaths}D)\n"

                embed4.add_field(
                    name="🏆 Enhanced DPM Leaderboard",
                    value=dpm_text.rstrip(),
                    inline=False,
                )

            # DPM Insights with calculation formula
            if dpm_leaders:
                avg_dpm = sum(p[1] for p in dpm_leaders) / len(dpm_leaders)
                highest_dpm = dpm_leaders[0][1] if dpm_leaders else 0
                leader_name = dpm_leaders[0][0] if dpm_leaders else "N/A"

                insights = (
                    f"📊 **Enhanced Session DPM Stats:**\n"
                    f"• Average DPM: `{avg_dpm:.1f}`\n"
                    f"• Highest DPM: `{highest_dpm:.0f}`\n"
                    f"• DPM Leader: **{leader_name}**\n"
                    f"• Formula: `(Total Damage × 60) / Time Played (seconds)`"
                )
                embed4.add_field(
                    name="💥 DPM Insights", value=insights, inline=False
                )

            embed4.set_footer(text="💥 Enhanced with Kill/Death Details")
            await self._log_and_send(
                ctx, embed4, "embed4", latest_date=latest_date
            )
            await asyncio.sleep(16)  # Rate limit protection

            # ═══════════════════════════════════════════════════════
            # MESSAGE 5: Weapon Mastery Breakdown (Text)
            # ═══════════════════════════════════════════════════════

            # Group by player and get their top weapons
            player_weapon_map = {}
            for player, weapon, kills, hits, shots, hs in player_weapons:
                if player not in player_weapon_map:
                    player_weapon_map[player] = []
                acc = (hits / shots * 100) if shots > 0 else 0
                hs_pct = (hs / hits * 100) if hits > 0 else 0
                weapon_clean = (
                    weapon.replace("WS_", "").replace("_", " ").title()
                )
                player_weapon_map[player].append(
                    (weapon_clean, kills, acc, hs_pct, hs, hits, shots)
                )

            # Convert revives data (already fetched before connection closed)
            player_revives = {
                player: revives for player, revives in player_revives_raw
            }

            # Sort players by total kills - SHOW ALL PLAYERS
            player_totals = []
            for player, weapons in player_weapon_map.items():
                total_kills = sum(w[1] for w in weapons)
                player_totals.append((player, total_kills))
            player_totals.sort(key=lambda x: x[1], reverse=True)

            # Create text-based weapon breakdown
            embed5 = discord.Embed(
                title="🔫 Weapon Mastery Breakdown",
                description="Top weapons and combat statistics",
                color=0x5865F2,
                timestamp=datetime.now(),
            )

            # Show ALL players and ALL their weapons (not just top 3)
            for player, total_kills in player_totals:
                weapons = player_weapon_map[player]  # ALL weapons
                revives = player_revives.get(player, 0)

                weapon_text = ""
                for weapon, kills, acc, hs_pct, hs, hits, shots in weapons:
                    # Format weapon line: Name, kills, accuracy, headshots
                    weapon_text += (
                        f"**{weapon}**: `{kills}K` • `{acc:.1f}% ACC` • "
                        f"`{hs} HS ({hs_pct:.1f}%)`\n"
                    )

                # Add revives info
                if revives > 0:
                    weapon_text += f"\n💉 **Teammates Revived**: `{revives}`"

                embed5.add_field(
                    name=f"{player} ({total_kills} total kills)",
                    value=weapon_text,
                    inline=False,
                )

            embed5.set_footer(text=f"Session: {latest_date}")
            await self._log_and_send(
                ctx, embed5, "embed5", latest_date=latest_date
            )
            await asyncio.sleep(2)

            # ═══════════════════════════════════════════════════════
            # MESSAGE 6: Objective & Support Stats
            # ═══════════════════════════════════════════════════════
            # Use awards_data that was already fetched before connection closed
            if awards_data:
                embed6 = discord.Embed(
                    title="🎯 Objective & Support Stats",
                    description="Comprehensive battlefield contributions",
                    color=0x00D166,
                    timestamp=datetime.now(),
                )

                # Aggregate stats across all rounds per player
                # awards_data format: (clean_name, xp, kill_assists, obj_stolen, obj_returned,
                #                      dyn_planted, dyn_defused, times_revived, double, triple, quad,
                #                      multi, mega, denied_time, useful_kills, useless_kills, gibs,
                #                      best_spree, worst_spree)
                player_objectives = {}
                for row in awards_data:
                    player_name = row[0]
                    if player_name not in player_objectives:
                        player_objectives[player_name] = {
                            "xp": 0,
                            "assists": 0,
                            "obj_stolen": 0,
                            "obj_returned": 0,
                            "dyn_planted": 0,
                            "dyn_defused": 0,
                            "revived": 0,
                            "multi_2x": 0,
                            "multi_3x": 0,
                            "multi_4x": 0,
                            "multi_5x": 0,
                            "multi_6x": 0,
                            "denied_time": 0,
                            "useful_kills": 0,
                            "useless_kills": 0,
                            "gibs": 0,
                            "best_spree": 0,
                            "worst_spree": 0,
                        }

                    # Accumulate stats from each round
                    player_objectives[player_name]["xp"] += row[1] or 0
                    player_objectives[player_name]["assists"] += row[2] or 0
                    player_objectives[player_name]["obj_stolen"] += row[3] or 0
                    player_objectives[player_name]["obj_returned"] += (
                        row[4] or 0
                    )
                    player_objectives[player_name]["dyn_planted"] += (
                        row[5] or 0
                    )
                    player_objectives[player_name]["dyn_defused"] += (
                        row[6] or 0
                    )
                    player_objectives[player_name]["revived"] += row[7] or 0
                    player_objectives[player_name]["multi_2x"] += row[8] or 0
                    player_objectives[player_name]["multi_3x"] += row[9] or 0
                    player_objectives[player_name]["multi_4x"] += row[10] or 0
                    player_objectives[player_name]["multi_5x"] += row[11] or 0
                    player_objectives[player_name]["multi_6x"] += row[12] or 0
                    player_objectives[player_name]["denied_time"] += (
                        row[13] or 0
                    )
                    player_objectives[player_name]["useful_kills"] += (
                        row[14] or 0
                    )
                    player_objectives[player_name]["useless_kills"] += (
                        row[15] or 0
                    )
                    player_objectives[player_name]["gibs"] += row[16] or 0
                    # Track best spree (max) and worst spree (max deaths)
                    player_objectives[player_name]["best_spree"] = max(
                        player_objectives[player_name]["best_spree"],
                        row[17] or 0,
                    )
                    player_objectives[player_name]["worst_spree"] = max(
                        player_objectives[player_name]["worst_spree"],
                        row[18] or 0,
                    )

                # Sort players by XP and show top N (default 8)
                top_n = min(8, len(player_objectives))
                sorted_players = sorted(
                    player_objectives.items(),
                    key=lambda x: x[1]["xp"],
                    reverse=True,
                )[:top_n]

                # If user requested objectives-only view, send a compact embed now
                if subcommand and subcommand.lower() in ("obj", "objectives"):
                    try:
                        compact = discord.Embed(
                            title=f"🎯 Objective & Support - {latest_date}",
                            description=f"Top objective contributors • {player_count} players",
                            color=0x00D166,
                            timestamp=datetime.now(),
                        )

                        for i, (player, stats) in enumerate(sorted_players, 1):
                            text = f"XP: `{stats['xp']}` • Revives: `{stats.get('revived', 0)}`\n"
                            text += (
                                f"Dyns: `{stats.get('dyn_planted', 0)}/{stats.get('dyn_defused', 0)}` • "
                                f"S/R: `{stats.get('obj_stolen', 0)}/{stats.get('obj_returned', 0)}`\n"
                            )
                            text += (
                                f"Useful/Useless: `{stats.get('useful_kills', 0)}/{stats.get('useless_kills', 0)}` • "
                                f"Gibs: `{stats.get('gibs', 0)}` • BestSpree: `{stats.get('best_spree', 0)}`"
                            )
                            compact.add_field(
                                name=f"{i}. {player}", value=text, inline=False
                            )

                        compact.set_footer(
                            text=f"Session: {latest_date} • Use !last_session for full report"
                        )

                        # Log field lengths and send
                        for idx, fld in enumerate(compact.fields):
                            ln = len(fld.value or "")
                            logger.debug(
                                f"[last_session/obj] field[{idx}] '{fld.name}' length={ln}"
                            )
                            if ln > 1024:
                                logger.warning(
                                    f"[last_session/obj] field[{idx}] '{fld.name}' LENGTH {ln} > 1024"
                                )

                        await ctx.send(embed=compact)
                        return
                    except Exception:
                        logger.exception(
                            "Error while building compact objectives view"
                        )

                for i, (player, stats) in enumerate(sorted_players, 1):
                    obj_text = f"**XP:** `{stats['xp']}`\n"
                    obj_text += f"**Assists:** `{stats['assists']}`\n"

                    # Objectives
                    if stats["obj_stolen"] > 0 or stats["obj_returned"] > 0:
                        obj_text += f"**Objectives:** `{stats['obj_stolen']}/{stats['obj_returned']}` S/R\n"

                    # Dynamites
                    if stats["dyn_planted"] > 0 or stats["dyn_defused"] > 0:
                        obj_text += f"**Dynamites:** `{stats['dyn_planted']}/{stats['dyn_defused']}` P/D\n"

                    # Revived
                    if stats["revived"] > 0:
                        obj_text += (
                            f"**Revived:** `{stats['revived']}` times\n"
                        )

                    # 🔥 ADVANCED STATS 🔥
                    # Killing spree
                    if stats["best_spree"] >= 3:
                        obj_text += f"🔥 **Best Spree:** `{stats['best_spree']}` kills\n"

                    # Death spree (embarrassing!)
                    if stats["worst_spree"] >= 3:
                        obj_text += f"💀 **Death Spree:** `{stats['worst_spree']}` deaths\n"

                    # Gibs
                    if stats["gibs"] > 0:
                        obj_text += f"🦴 **Gibs:** `{stats['gibs']}`\n"

                    # Useful kills
                    if stats["useful_kills"] > 0:
                        obj_text += (
                            f"✅ **Useful Kills:** `{stats['useful_kills']}`\n"
                        )

                    # Useless kills (with clown emoji!)
                    if stats["useless_kills"] > 0:
                        obj_text += f"🤡 **Useless Kills:** `{stats['useless_kills']}`\n"

                    # Denied playtime (convert seconds to MM:SS)
                    if stats["denied_time"] > 0:
                        denied_mins = stats["denied_time"] // 60
                        denied_secs = stats["denied_time"] % 60
                        obj_text += f"⏱️ **Enemy Denied:** `{denied_mins}:{denied_secs:02d}`\n"

                    # Multikills with fancy emojis
                    multikills = []
                    if stats["multi_2x"] > 0:
                        multikills.append(f"2️⃣✖️ {stats['multi_2x']}")
                    if stats["multi_3x"] > 0:
                        multikills.append(f"3️⃣✖️ {stats['multi_3x']}")
                    if stats["multi_4x"] > 0:
                        multikills.append(f"4️⃣✖️ {stats['multi_4x']}")
                    if stats["multi_5x"] > 0:
                        multikills.append(f"5️⃣✖️ {stats['multi_5x']}")
                    if stats["multi_6x"] > 0:
                        multikills.append(f"6️⃣✖️ {stats['multi_6x']}")
                    if multikills:
                        obj_text += (
                            f"💥 **Multikills:** {' '.join(multikills)}\n"
                        )

                    embed6.add_field(
                        name=f"{i}. {player}",
                        value=obj_text.rstrip(),
                        inline=True,
                    )

                embed6.set_footer(
                    text="🎯 S/R = Stolen/Returned | P/D = Planted/Defused"
                )
                await self._log_and_send(
                    ctx, embed6, "embed6", latest_date=latest_date
                )
                await asyncio.sleep(2)  # Rate limit before awards

            # ═══════════════════════════════════════════════════════
            # MESSAGE 7: SPECIAL AWARDS 🏆
            # ═══════════════════════════════════════════════════════
            logger.info("🏆 Calculating Special Awards...")

            # Calculate awards from chaos_awards_data
            awards = {
                "teamkill_king": {"player": None, "value": 0},
                "selfkill_master": {"player": None, "value": 0},
                "kill_thief": {"player": None, "value": 0},
                "spray_pray": {"player": None, "value": 0},
                "trigger_shy": {"player": None, "value": 999999},
                "damage_king": {"player": None, "value": 0},
                "glass_cannon": {"player": None, "value": 0},
                "engineer": {"player": None, "value": 0},
                "tank_shield": {"player": None, "value": 0},
                "respawn_king": {"player": None, "value": 0},
                "useless_king": {"player": None, "value": 0},
                "death_magnet": {"player": None, "value": 0},
                "worst_spree": {"player": None, "value": 0},
            }

            for row in chaos_awards_data:
                name = row[0]
                teamkills, selfkills, steals, bullets = row[1:5]
                kills, deaths, dmg_given, dmg_received = row[5:9]
                constructions, tank, useless = row[9:12]
                worst_spree, play_time = row[12:14]

                # Teamkill King
                if teamkills > awards["teamkill_king"]["value"]:
                    awards["teamkill_king"] = {
                        "player": name,
                        "value": teamkills,
                    }

                # Self-Kill Master
                if selfkills > awards["selfkill_master"]["value"]:
                    awards["selfkill_master"] = {
                        "player": name,
                        "value": selfkills,
                    }

                # Kill Thief
                if steals > awards["kill_thief"]["value"]:
                    awards["kill_thief"] = {"player": name, "value": steals}

                # Spray & Pray (most bullets per kill)
                if kills > 0:
                    bpk = bullets / kills
                    if bpk > awards["spray_pray"]["value"]:
                        awards["spray_pray"] = {"player": name, "value": bpk}

                # Too Scared to Shoot (fewest bullets, min 5 kills)
                if kills >= 5 and bullets < awards["trigger_shy"]["value"]:
                    awards["trigger_shy"] = {"player": name, "value": bullets}

                # Damage Efficiency King (best dmg given/received ratio)
                if dmg_received > 0:
                    eff = dmg_given / dmg_received
                    if eff > awards["damage_king"]["value"]:
                        awards["damage_king"] = {"player": name, "value": eff}

                # Glass Cannon (most damage taken)
                if dmg_received > awards["glass_cannon"]["value"]:
                    awards["glass_cannon"] = {
                        "player": name,
                        "value": dmg_received,
                    }

                # Chief Engineer
                if constructions > awards["engineer"]["value"]:
                    awards["engineer"] = {
                        "player": name,
                        "value": constructions,
                    }

                # Tank Shield
                if tank > awards["tank_shield"]["value"]:
                    awards["tank_shield"] = {"player": name, "value": tank}

                # Respawn King (most deaths)
                if deaths > awards["respawn_king"]["value"]:
                    awards["respawn_king"] = {"player": name, "value": deaths}

                # Most Useless Kills
                if useless > awards["useless_king"]["value"]:
                    awards["useless_king"] = {"player": name, "value": useless}

                # Death Magnet (most total deaths)
                if deaths > awards["death_magnet"]["value"]:
                    awards["death_magnet"] = {"player": name, "value": deaths}

                # Worst Death Spree
                if worst_spree > awards["worst_spree"]["value"]:
                    awards["worst_spree"] = {
                        "player": name,
                        "value": worst_spree,
                    }

            # Build awards embed
            embed7 = discord.Embed(
                title="🏆 SESSION SPECIAL AWARDS 🏆",
                description="*Celebrating excellence... and chaos!*",
                color=0xFFD700,  # Gold
            )

            awards_text = []

            # Positive awards
            if awards["damage_king"]["value"] > 1.5:
                player = awards["damage_king"]["player"]
                ratio = awards["damage_king"]["value"]
                awards_text.append(
                    f"💥 **Damage Efficiency King:** `{player}` ({ratio:.2f}x ratio)"
                )

            if awards["engineer"]["value"] >= 1:
                player = awards["engineer"]["player"]
                count = int(awards["engineer"]["value"])
                awards_text.append(
                    f"🔧 **Chief Engineer:** `{player}` ({count} repairs)"
                )

            # Funny/Chaos awards
            if awards["teamkill_king"]["value"] >= 2:
                player = awards["teamkill_king"]["player"]
                count = int(awards["teamkill_king"]["value"])
                awards_text.append(
                    f"🔥 **Friendly Fire King:** `{player}` ({count} teamkills)"
                )

            if awards["selfkill_master"]["value"] >= 3:
                player = awards["selfkill_master"]["player"]
                count = int(awards["selfkill_master"]["value"])
                awards_text.append(
                    f"🤦 **Self-Destruct Master:** `{player}` ({count} self-kills!)"
                )

            if awards["kill_thief"]["value"] >= 2:
                player = awards["kill_thief"]["player"]
                count = int(awards["kill_thief"]["value"])
                awards_text.append(
                    f"🥷 **Kill Thief:** `{player}` ({count} steals)"
                )

            if awards["spray_pray"]["value"] >= 100:
                player = awards["spray_pray"]["player"]
                bpk = awards["spray_pray"]["value"]
                awards_text.append(
                    f"🎯 **Spray & Pray:** `{player}` ({bpk:.0f} bullets/kill)"
                )

            if awards["trigger_shy"]["value"] < 999999:
                player = awards["trigger_shy"]["player"]
                bullets = int(awards["trigger_shy"]["value"])
                awards_text.append(
                    f"🙈 **Trigger Discipline:** `{player}` ({bullets} bullets only)"
                )

            if awards["respawn_king"]["value"] >= 15:
                player = awards["respawn_king"]["player"]
                count = int(awards["respawn_king"]["value"])
                awards_text.append(
                    f"💀 **Respawn Champion:** `{player}` ({count} deaths)"
                )

            if awards["worst_spree"]["value"] >= 5:
                player = awards["worst_spree"]["player"]
                count = int(awards["worst_spree"]["value"])
                awards_text.append(
                    f"⚰️ **Death Spree Record:** `{player}` ({count} deaths in a row)"
                )

            if awards["useless_king"]["value"] >= 3:
                player = awards["useless_king"]["player"]
                count = int(awards["useless_king"]["value"])
                awards_text.append(
                    f"🤡 **Most Useless Kills:** `{player}` ({count} useless)"
                )

            if awards["glass_cannon"]["value"] >= 1000:
                player = awards["glass_cannon"]["player"]
                dmg = int(awards["glass_cannon"]["value"])
                awards_text.append(
                    f"🩹 **Damage Sponge:** `{player}` ({dmg:,} dmg taken)"
                )

            if awards["tank_shield"]["value"] > 0:
                player = awards["tank_shield"]["player"]
                val = awards["tank_shield"]["value"]
                awards_text.append(
                    f"🛡️ **Tank Shield:** `{player}` ({val:.1f} tank hits)"
                )

            if awards_text:
                embed7.description = "\n".join(awards_text)
            else:
                embed7.description = "*No notable awards this session*"

            embed7.set_footer(text="🎉 Keep up the good work... or not!")
            await self._log_and_send(
                ctx, embed7, "embed7", latest_date=latest_date
            )
            await asyncio.sleep(2)

            # ═══════════════════════════════════════════════════════
            # MESSAGE 8: CHAOS STATS LEADERBOARDS 💀
            # ═══════════════════════════════════════════════════════
            logger.info("💀 Building Chaos Stats Leaderboards...")

            # Sort chaos_awards_data for leaderboards
            teamkill_leaders = sorted(
                [(r[0], r[1]) for r in chaos_awards_data if r[1] > 0],
                key=lambda x: x[1],
                reverse=True,
            )[:3]

            selfkill_leaders = sorted(
                [(r[0], r[2]) for r in chaos_awards_data if r[2] > 0],
                key=lambda x: x[1],
                reverse=True,
            )[:3]

            killsteal_leaders = sorted(
                [(r[0], r[3]) for r in chaos_awards_data if r[3] > 0],
                key=lambda x: x[1],
                reverse=True,
            )[:3]

            useless_leaders = sorted(
                [(r[0], r[12]) for r in chaos_awards_data if r[12] > 0],
                key=lambda x: x[1],
                reverse=True,
            )[:3]

            death_leaders = sorted(
                [(r[0], r[6]) for r in chaos_awards_data if r[6] > 0],
                key=lambda x: x[1],
                reverse=True,
            )[:3]

            embed8 = discord.Embed(
                title="💀 CHAOS & MAYHEM STATS 💀",
                description="*The good, the bad, and the ugly*",
                color=0xFF0000,  # Red
            )

            # Teamkills Leaderboard
            if teamkill_leaders:
                tk_text = "\n".join(
                    [
                        f"{'🥇🥈🥉'[i]} `{name:20s}` - {count} teamkill{'s' if count > 1 else ''}"
                        for i, (name, count) in enumerate(teamkill_leaders)
                    ]
                )
                embed8.add_field(
                    name="🔥 Friendly Fire Leaderboard",
                    value=tk_text,
                    inline=False,
                )

            # Self-Kills Leaderboard
            if selfkill_leaders:
                sk_text = "\n".join(
                    [
                        f"{'🥇🥈🥉'[i]} `{name:20s}` - {count} self-kill{'s' if count > 1 else ''}"
                        for i, (name, count) in enumerate(selfkill_leaders)
                    ]
                )
                embed8.add_field(
                    name="🤦 Self-Destruction Champions",
                    value=sk_text,
                    inline=False,
                )

            # Kill Steals Leaderboard
            if killsteal_leaders:
                ks_text = "\n".join(
                    [
                        f"{'🥇🥈🥉'[i]} `{name:20s}` - {count} steal{'s' if count > 1 else ''}"
                        for i, (name, count) in enumerate(killsteal_leaders)
                    ]
                )
                embed8.add_field(
                    name="🥷 Kill Thieves", value=ks_text, inline=False
                )

            # Useless Kills Leaderboard
            if useless_leaders:
                ul_text = "\n".join(
                    [
                        f"{'🥇🥈🥉'[i]} `{name:20s}` - {count} useless kill{'s' if count > 1 else ''}"
                        for i, (name, count) in enumerate(useless_leaders)
                    ]
                )
                embed8.add_field(
                    name="🤡 Most Useless Kills", value=ul_text, inline=False
                )

            # Most Deaths Leaderboard
            if death_leaders:
                dl_text = "\n".join(
                    [
                        f"{'🥇🥈🥉'[i]} `{name:20s}` - {count} death{'s' if count > 1 else ''}"
                        for i, (name, count) in enumerate(death_leaders)
                    ]
                )
                embed8.add_field(
                    name="💀 Respawn Champions (Most Deaths)",
                    value=dl_text,
                    inline=False,
                )

            embed8.set_footer(text="😈 Embrace the chaos!")
            await self._log_and_send(
                ctx, embed8, "embed8", latest_date=latest_date
            )
            await asyncio.sleep(2)  # Rate limit before graphs

            # ═══════════════════════════════════════════════════════
            # MESSAGE 9: Visual Stats Graph
            # ═══════════════════════════════════════════════════════
            logger.info("🎨 Generating visual performance graphs...")
            try:
                # Use centralized helper to create the performance image for top players
                from bot.last_session_helpers import create_performance_image

                try:
                    top_players = all_players[:6] if all_players else []
                    # Ensure session_date exists for older code paths that expect it
                    session_date = latest_date
                    title = (
                        session_date
                        if "session_date" in locals()
                        else "Latest Session"
                    )
                    img_buf = create_performance_image(top_players, title)
                    file = discord.File(img_buf, filename="session_stats.png")
                    logger.info("📊 Sending Graph 1 to Discord (via helper)...")
                    await ctx.send(
                        "📊 **Visual Performance Analytics - Part 1**",
                        file=file,
                    )
                    logger.info("✅ Graph 1 sent successfully (helper)!")
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(
                        f"❌ Error creating/sending performance image: {e}",
                        exc_info=True,
                    )
            except Exception:
                # If the helper or matplotlib isn't available, continue to next graphs
                logger.debug(
                    "Performance image helper unavailable; skipping Graph 1 via helper"
                )

            # ═══════════════════════════════════════════════════════
            # GRAPH 2: Advanced Combat Stats (Gibs and Damage Only)
            # NOTE: Revives and Useful Kills disabled - parser not capturing data
            # REMOVED FROM DEFAULT VIEW - Use !last_session full to see this
            # ═══════════════════════════════════════════════════════
            try:
                import matplotlib

                matplotlib.use("Agg")
                import io

                import matplotlib.pyplot as plt
            except Exception:
                plt = None

            if (
                plt
                and (subcommand == "full")
                and advanced_graph_data
                and len(advanced_graph_data) > 0
            ):
                logger.info("🎨 Generating Graph 2 (Advanced Combat Stats)...")
                fig2, (ax4, ax6) = plt.subplots(1, 2, figsize=(14, 6))
                fig2.patch.set_facecolor("#2b2d31")

                # Extract data (only gibs and damage for now)
                adv_names = [row[0] for row in advanced_graph_data]
                gibs = [row[2] or 0 for row in advanced_graph_data]
                total_damage = [row[4] or 0 for row in advanced_graph_data]

                x_adv = range(len(adv_names))

                # Subplot 1: Gibs
                ax4.barh(x_adv, gibs, color="#ed4245", alpha=0.8)
                ax4.set_yticks(x_adv)
                ax4.set_yticklabels(adv_names, color="white")
                ax4.set_xlabel("Gibs", color="white", fontsize=11)
                ax4.set_title(
                    "🦴 Gib Masters",
                    color="white",
                    fontsize=12,
                    fontweight="bold",
                )
                ax4.set_facecolor("#1e1f22")
                ax4.tick_params(colors="white")
                ax4.spines["bottom"].set_color("white")
                ax4.spines["left"].set_color("white")
                ax4.spines["top"].set_visible(False)
                ax4.spines["right"].set_visible(False)
                ax4.grid(True, alpha=0.2, color="white", axis="x")
                for i, v in enumerate(gibs):
                    ax4.text(
                        v,
                        i,
                        f" {int(v)}",
                        va="center",
                        color="white",
                        fontsize=9,
                    )

                # Subplot 2: Total Damage
                ax6.barh(x_adv, total_damage, color="#5865f2", alpha=0.8)
                ax6.set_yticks(x_adv)
                ax6.set_yticklabels(adv_names, color="white")
                ax6.set_xlabel("Total Damage", color="white", fontsize=11)
                ax6.set_title(
                    "💥 Damage Dealers",
                    color="white",
                    fontsize=12,
                    fontweight="bold",
                )
                ax6.set_facecolor("#1e1f22")
                ax6.tick_params(colors="white")
                ax6.spines["bottom"].set_color("white")
                ax6.spines["left"].set_color("white")
                ax6.spines["top"].set_visible(False)
                ax6.spines["right"].set_visible(False)
                ax6.grid(True, alpha=0.2, color="white", axis="x")
                for i, v in enumerate(total_damage):
                    ax6.text(
                        v,
                        i,
                        f" {int(v)}",
                        va="center",
                        color="white",
                        fontsize=9,
                    )

                plt.tight_layout()

                # Save and send Graph 2
                buf2 = io.BytesIO()
                plt.savefig(
                    buf2,
                    format="png",
                    facecolor="#2b2d31",
                    dpi=100,
                    bbox_inches="tight",
                )
                buf2.seek(0)
                plt.close()

                file2 = discord.File(buf2, filename="advanced_stats.png")
                logger.info("📊 Sending Graph 2 to Discord...")
                await ctx.send(
                    "📊 **Advanced Combat Stats - Part 2**", file=file2
                )
                logger.info("✅ Graph 2 sent successfully!")
                await asyncio.sleep(1)

            # ═══════════════════════════════════════════════════════
            # GRAPH 3: Per-Map Breakdown
            # MOVED TO !last_session graphs - Use that for detailed breakdown
            # ═══════════════════════════════════════════════════════
            if (
                (subcommand in ["graphs", "full"])
                and per_map_data
                and len(per_map_data) > 0
            ):
                logger.info("🎨 Generating Graph 3 (Per-Map Breakdown)...")

                # Group data by map
                map_stats = {}
                for row in per_map_data:
                    map_name = row[0]
                    if map_name not in map_stats:
                        map_stats[map_name] = []
                    map_stats[map_name].append(
                        {
                            "name": row[1],
                            "kills": row[2] or 0,
                            "deaths": row[3] or 0,
                            "dpm": row[4] or 0,
                        }
                    )

                # Create figure with subplots for each map (max 4 maps)
                num_maps = min(len(map_stats), 4)
                if num_maps > 0:
                    fig3, axes = plt.subplots(2, 2, figsize=(16, 12))
                    fig3.patch.set_facecolor("#2b2d31")
                    axes_flat = axes.flatten() if num_maps > 1 else [axes]

                    for idx, (map_name, players) in enumerate(
                        list(map_stats.items())[:4]
                    ):
                        ax = axes_flat[idx]

                        # Get top 5 players for this map
                        top_players = sorted(
                            players, key=lambda x: x["kills"], reverse=True
                        )[:5]
                        map_player_names = [p["name"] for p in top_players]
                        map_kills = [p["kills"] for p in top_players]
                        map_deaths = [p["deaths"] for p in top_players]
                        map_dpm = [p["dpm"] for p in top_players]

                        x_map = range(len(map_player_names))
                        width_map = 0.25

                        # Triple bar chart (Kills, Deaths, DPM)
                        ax.bar(
                            [i - width_map for i in x_map],
                            map_kills,
                            width_map,
                            label="Kills",
                            color="#5865f2",
                            alpha=0.8,
                        )
                        ax.bar(
                            x_map,
                            map_deaths,
                            width_map,
                            label="Deaths",
                            color="#ed4245",
                            alpha=0.8,
                        )
                        ax.bar(
                            [i + width_map for i in x_map],
                            map_dpm,
                            width_map,
                            label="DPM",
                            color="#fee75c",
                            alpha=0.8,
                        )

                        ax.set_title(
                            f"🗺️ {map_name}",
                            color="white",
                            fontsize=12,
                            fontweight="bold",
                        )
                        ax.set_xticks(x_map)
                        ax.set_xticklabels(
                            map_player_names,
                            rotation=20,
                            ha="right",
                            color="white",
                            fontsize=8,
                        )
                        ax.set_facecolor("#1e1f22")
                        ax.tick_params(colors="white")
                        ax.spines["bottom"].set_color("white")
                        ax.spines["left"].set_color("white")
                        ax.spines["top"].set_visible(False)
                        ax.spines["right"].set_visible(False)
                        ax.grid(True, alpha=0.2, color="white", axis="y")
                        ax.legend(
                            facecolor="#1e1f22",
                            edgecolor="white",
                            labelcolor="white",
                            fontsize=8,
                        )

                    # Hide unused subplots
                    for idx in range(num_maps, 4):
                        axes_flat[idx].set_visible(False)

                    plt.tight_layout()

                    # Save and send Graph 3
                    buf3 = io.BytesIO()
                    plt.savefig(
                        buf3,
                        format="png",
                        facecolor="#2b2d31",
                        dpi=100,
                        bbox_inches="tight",
                    )
                    buf3.seek(0)
                    plt.close()

                    file3 = discord.File(
                        buf3, filename="per_map_breakdown.png"
                    )
                    logger.info("📊 Sending Graph 3 to Discord...")
                    await ctx.send(
                        "📊 **Per-Map Performance Breakdown - Part 3**",
                        file=file3,
                    )
                    logger.info("✅ Graph 3 sent successfully!")
                    await asyncio.sleep(1)

            # ═══════════════════════════════════════════════════════
            # GRAPH 4: Combat Efficiency & Bullets Analysis
            # ═══════════════════════════════════════════════════════
            if chaos_awards_data and len(chaos_awards_data) > 0:
                logger.info("🎨 Generating Graph 4 (Combat Efficiency)...")

                # Get top 8 players by total kills for efficiency analysis
                efficiency_players = sorted(
                    chaos_awards_data,
                    key=lambda x: x[5],
                    reverse=True,  # total_kills
                )[:8]

                if efficiency_players:
                    fig4, ((ax7, ax8), (ax9, ax10)) = plt.subplots(
                        2, 2, figsize=(16, 12)
                    )
                    fig4.patch.set_facecolor("#2b2d31")

                    # Extract data
                    eff_names = [row[0] for row in efficiency_players]
                    eff_dmg_given = [row[7] or 0 for row in efficiency_players]
                    eff_dmg_received = [
                        row[8] or 0 for row in efficiency_players
                    ]
                    eff_bullets = [row[4] or 0 for row in efficiency_players]
                    eff_kills = [row[5] or 0 for row in efficiency_players]

                    # Calculate ratios
                    eff_damage_ratio = [
                        (g / r) if r > 0 else g
                        for g, r in zip(eff_dmg_given, eff_dmg_received)
                    ]
                    eff_bullets_per_kill = [
                        (b / k) if k > 0 else 0
                        for b, k in zip(eff_bullets, eff_kills)
                    ]

                    x_eff = range(len(eff_names))
                    width_eff = 0.35

                    # Subplot 1: Damage Given vs Received
                    ax7.bar(
                        [i - width_eff / 2 for i in x_eff],
                        eff_dmg_given,
                        width_eff,
                        label="Damage Given",
                        color="#5865f2",
                        alpha=0.8,
                    )
                    ax7.bar(
                        [i + width_eff / 2 for i in x_eff],
                        eff_dmg_received,
                        width_eff,
                        label="Damage Received",
                        color="#ed4245",
                        alpha=0.8,
                    )
                    ax7.set_xticks(x_eff)
                    ax7.set_xticklabels(
                        eff_names,
                        rotation=20,
                        ha="right",
                        color="white",
                        fontsize=9,
                    )
                    ax7.set_ylabel("Damage", color="white", fontsize=11)
                    ax7.set_title(
                        "Damage Given vs Received",
                        color="white",
                        fontsize=12,
                        fontweight="bold",
                    )
                    ax7.set_facecolor("#1e1f22")
                    ax7.tick_params(colors="white")
                    ax7.spines["bottom"].set_color("white")
                    ax7.spines["left"].set_color("white")
                    ax7.spines["top"].set_visible(False)
                    ax7.spines["right"].set_visible(False)
                    ax7.grid(True, alpha=0.2, color="white", axis="y")
                    ax7.legend(
                        facecolor="#1e1f22",
                        edgecolor="white",
                        labelcolor="white",
                        fontsize=9,
                    )

                    # Subplot 2: Damage Efficiency Ratio
                    colors_ratio = [
                        "#57f287"
                        if r > 1.5
                        else "#fee75c"
                        if r > 1.0
                        else "#ed4245"
                        for r in eff_damage_ratio
                    ]
                    ax8.bar(
                        x_eff, eff_damage_ratio, color=colors_ratio, alpha=0.8
                    )
                    ax8.axhline(
                        y=1.0,
                        color="white",
                        linestyle="--",
                        alpha=0.5,
                        linewidth=1,
                    )
                    ax8.set_xticks(x_eff)
                    ax8.set_xticklabels(
                        eff_names,
                        rotation=20,
                        ha="right",
                        color="white",
                        fontsize=9,
                    )
                    ax8.set_ylabel(
                        "Ratio (Given/Received)", color="white", fontsize=11
                    )
                    ax8.set_title(
                        "Damage Efficiency Ratio",
                        color="white",
                        fontsize=12,
                        fontweight="bold",
                    )
                    ax8.set_facecolor("#1e1f22")
                    ax8.tick_params(colors="white")
                    ax8.spines["bottom"].set_color("white")
                    ax8.spines["left"].set_color("white")
                    ax8.spines["top"].set_visible(False)
                    ax8.spines["right"].set_visible(False)
                    ax8.grid(True, alpha=0.2, color="white", axis="y")
                    for i, v in enumerate(eff_damage_ratio):
                        ax8.text(
                            i,
                            v,
                            f"{v:.2f}x",
                            ha="center",
                            va="bottom",
                            color="white",
                            fontsize=8,
                        )

                    # Subplot 3: Total Bullets Fired
                    ax9.bar(x_eff, eff_bullets, color="#fee75c", alpha=0.8)
                    ax9.set_xticks(x_eff)
                    ax9.set_xticklabels(
                        eff_names,
                        rotation=20,
                        ha="right",
                        color="white",
                        fontsize=9,
                    )
                    ax9.set_ylabel("Bullets Fired", color="white", fontsize=11)
                    ax9.set_title(
                        "Total Ammunition Fired",
                        color="white",
                        fontsize=12,
                        fontweight="bold",
                    )
                    ax9.set_facecolor("#1e1f22")
                    ax9.tick_params(colors="white")
                    ax9.spines["bottom"].set_color("white")
                    ax9.spines["left"].set_color("white")
                    ax9.spines["top"].set_visible(False)
                    ax9.spines["right"].set_visible(False)
                    ax9.grid(True, alpha=0.2, color="white", axis="y")
                    for i, v in enumerate(eff_bullets):
                        ax9.text(
                            i,
                            v,
                            f"{int(v):,}",
                            ha="center",
                            va="bottom",
                            color="white",
                            fontsize=8,
                        )

                    # Subplot 4: Bullets per Kill
                    colors_bpk = [
                        "#57f287"
                        if b < 100
                        else "#fee75c"
                        if b < 200
                        else "#ed4245"
                        for b in eff_bullets_per_kill
                    ]
                    ax10.bar(
                        x_eff,
                        eff_bullets_per_kill,
                        color=colors_bpk,
                        alpha=0.8,
                    )
                    ax10.set_xticks(x_eff)
                    ax10.set_xticklabels(
                        eff_names,
                        rotation=20,
                        ha="right",
                        color="white",
                        fontsize=9,
                    )
                    ax10.set_ylabel(
                        "Bullets per Kill", color="white", fontsize=11
                    )
                    ax10.set_title(
                        "Accuracy Metric (Lower = Better)",
                        color="white",
                        fontsize=12,
                        fontweight="bold",
                    )
                    ax10.set_facecolor("#1e1f22")
                    ax10.tick_params(colors="white")
                    ax10.spines["bottom"].set_color("white")
                    ax10.spines["left"].set_color("white")
                    ax10.spines["top"].set_visible(False)
                    ax10.spines["right"].set_visible(False)
                    ax10.grid(True, alpha=0.2, color="white", axis="y")
                    for i, v in enumerate(eff_bullets_per_kill):
                        ax10.text(
                            i,
                            v,
                            f"{v:.0f}",
                            ha="center",
                            va="bottom",
                            color="white",
                            fontsize=8,
                        )

                    plt.tight_layout()

                    # Save and send Graph 4
                    buf4 = io.BytesIO()
                    plt.savefig(
                        buf4,
                        format="png",
                        facecolor="#2b2d31",
                        dpi=100,
                        bbox_inches="tight",
                    )
                    buf4.seek(0)
                    plt.close()

                    file4 = discord.File(
                        buf4, filename="combat_efficiency.png"
                    )
                    logger.info("📊 Sending Graph 4 to Discord...")
                    await ctx.send(
                        "📊 **Combat Efficiency & Bullets Analysis - Part 4**",
                        file=file4,
                    )
                    logger.info("✅ Graph 4 sent successfully!")

                    # Show helpful message about additional options (if default view)
                    if not subcommand:
                        help_embed = discord.Embed(
                            title="💡 Want More Details?",
                            description=(
                                "**Available Options:**\n"
                                "`!last_session graphs` - Round-by-round and per-map breakdowns\n"
                                "`!last_session full` - Everything including advanced combat stats"
                            ),
                            color=0x5865F2,
                        )
                        await ctx.send(embed=help_embed)

            else:
                logger.warning(
                    "⚠️ No graph data available - empty graph_data list"
                )

        except ImportError as e:
            logger.warning(f"⚠️ matplotlib not installed: {e}")
        except Exception as e:
            logger.error(f"❌ Error generating graphs: {e}", exc_info=True)
            # Send error message to user
            await ctx.send(f"⚠️ Could not generate graphs: {str(e)[:100]}")

        except Exception as e:
            logger.error(f"Error in last_session command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving last session: {e}")

    @commands.command(name="sessions", aliases=["list_sessions", "ls"])
    async def list_sessions(self, ctx, *, month: str = None):
        """📅 List all gaming sessions, optionally filtered by month

        Usage:
        - !sessions              → List all sessions (last 20)
        - !sessions 10           → List sessions from October (current year)
        - !sessions 2025-10      → List sessions from October 2025
        - !sessions october      → List sessions from October (current year)
        - !sessions oct          → Same as above
        """
        try:
            conn = sqlite3.connect(self.bot.db_path)
            cursor = conn.cursor()

            # Build query based on month filter
            if month:
                # Handle different month formats
                month_lower = month.strip().lower()
                month_names = {
                    "january": "01",
                    "jan": "01",
                    "february": "02",
                    "feb": "02",
                    "march": "03",
                    "mar": "03",
                    "april": "04",
                    "apr": "04",
                    "may": "05",
                    "june": "06",
                    "jun": "06",
                    "july": "07",
                    "jul": "07",
                    "august": "08",
                    "aug": "08",
                    "september": "09",
                    "sep": "09",
                    "october": "10",
                    "oct": "10",
                    "november": "11",
                    "nov": "11",
                    "december": "12",
                    "dec": "12",
                }

                if month_lower in month_names:
                    # Month name provided - use current year
                    from datetime import datetime

                    current_year = datetime.now().year
                    month_filter = f"{current_year}-{month_names[month_lower]}"
                elif "-" in month:
                    # Full YYYY-MM format
                    month_filter = month
                elif month.isdigit() and len(month) <= 2:
                    # Just month number - use current year
                    from datetime import datetime

                    current_year = datetime.now().year
                    month_filter = f"{current_year}-{int(month):02d}"
                else:
                    await ctx.send(
                        f"❌ Invalid month format: `{month}`\nUse: `!sessions 10` or `!sessions october`"
                    )
                    conn.close()
                    return

                query = """
                    SELECT 
                        DATE(session_date) as date,
                        COUNT(DISTINCT session_id) / 2 as maps,
                        COUNT(DISTINCT session_id) as rounds,
                        COUNT(DISTINCT player_guid) as players,
                        MIN(session_date) as first_round,
                        MAX(session_date) as last_round
                    FROM player_comprehensive_stats
                    WHERE session_date LIKE ?
                    GROUP BY DATE(session_date)
                    ORDER BY date DESC
                """
                cursor.execute(query, (f"{month_filter}%",))
                filter_text = month_filter
            else:
                query = """
                    SELECT 
                        DATE(session_date) as date,
                        COUNT(DISTINCT session_id) / 2 as maps,
                        COUNT(DISTINCT session_id) as rounds,
                        COUNT(DISTINCT player_guid) as players,
                        MIN(session_date) as first_round,
                        MAX(session_date) as last_round
                    FROM player_comprehensive_stats
                    GROUP BY DATE(session_date)
                    ORDER BY date DESC
                    LIMIT 20
                """
                cursor.execute(query)
                filter_text = "all time (last 20)"

            sessions = cursor.fetchall()
            conn.close()

            if not sessions:
                await ctx.send(f"❌ No sessions found for {filter_text}")
                return

            # Create embed
            embed = discord.Embed(
                title="📅 Gaming Sessions",
                description=f"Showing sessions from **{filter_text}**",
                color=discord.Color.blue(),
            )

            session_list = []
            for date, maps, rounds, players, first, last in sessions:
                # Calculate duration
                from datetime import datetime

                try:
                    first_dt = datetime.fromisoformat(
                        first.replace("Z", "+00:00") if "Z" in first else first
                    )
                    last_dt = datetime.fromisoformat(
                        last.replace("Z", "+00:00") if "Z" in last else last
                    )
                    duration = last_dt - first_dt
                    hours = duration.total_seconds() / 3600
                    duration_str = f"{hours:.1f}h"
                except Exception:
                    duration_str = "N/A"

                session_list.append(
                    f"**{date}**\n"
                    f"└ {int(maps)} maps • {rounds} rounds • {players} players • {duration_str}"
                )

            # Split into chunks if too long
            chunk_size = 10
            for i in range(0, len(session_list), chunk_size):
                chunk = session_list[i : i + chunk_size]
                embed.add_field(
                    name=f"Sessions {i+1}-{min(i+chunk_size, len(session_list))}",
                    value="\n\n".join(chunk),
                    inline=False,
                )

            embed.set_footer(
                text=f"Total: {len(sessions)} sessions • Use !last_session or !session YYYY-MM-DD for details"
            )

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in list_sessions command: {e}", exc_info=True)
            await ctx.send(f"❌ Error listing sessions: {e}")

    @commands.command(name="list_players", aliases=["players", "lp"])
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

    @commands.command(name="link")
    async def link(self, ctx, target: str = None, *, guid: str = None):
        """🔗 Link your Discord account to your in-game profile

        Usage:
        - !link                        → Smart search with top 3 suggestions
        - !link YourPlayerName         → Search by name
        - !link GUID                   → Direct link by GUID
        - !link @user GUID             → Admin: Link another user (requires permissions)
        """
        try:
            # === SCENARIO 0: ADMIN LINKING (@mention + GUID) ===
            if ctx.message.mentions and guid:
                await self._admin_link(
                    ctx, ctx.message.mentions[0], guid.upper()
                )
                return

            # For self-linking
            discord_id = str(ctx.author.id)

            # Check if already linked
            async with aiosqlite.connect(self.bot.db_path) as db:
                async with db.execute(
                    """
                    SELECT et_name, et_guid FROM player_links
                    WHERE discord_id = ?
                """,
                    (discord_id,),
                ) as cursor:
                    existing = await cursor.fetchone()

                if existing:
                    await ctx.send(
                        f"⚠️ You're already linked to **{existing[0]}** (GUID: {existing[1]})\\n"
                        f"Use `!unlink` first to change your linked account."
                    )
                    return

                # === SCENARIO 1: NO ARGUMENTS - Smart Self-Linking ===
                if not target:
                    await self._smart_self_link(ctx, discord_id, db)
                    return

                # === SCENARIO 2: GUID Direct Link ===
                # Check if it's a GUID (8 hex characters)
                if len(target) == 8 and all(
                    c in "0123456789ABCDEFabcdef" for c in target
                ):
                    await self._link_by_guid(
                        ctx, discord_id, target.upper(), db
                    )
                    return

                # === SCENARIO 3: Name Search ===
                await self._link_by_name(ctx, discord_id, target, db)

        except Exception as e:
            logger.error(f"Error in link command: {e}", exc_info=True)
            await ctx.send(f"❌ Error linking account: {e}")

    async def _smart_self_link(self, ctx, discord_id: str, db):
        """Smart self-linking: show top 3 unlinked GUIDs with aliases"""
        try:
            # Get top 3 unlinked players by recent activity and total stats
            async with db.execute(
                """
                SELECT 
                    player_guid,
                    MAX(session_date) as last_played,
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths,
                    COUNT(DISTINCT session_id) as games
                FROM player_comprehensive_stats
                WHERE player_guid NOT IN (SELECT et_guid FROM player_links WHERE et_guid IS NOT NULL)
                GROUP BY player_guid
                ORDER BY last_played DESC, total_kills DESC
                LIMIT 3
            """,
            ) as cursor:
                top_players = await cursor.fetchall()

            if not top_players:
                await ctx.send(
                    "❌ No available players found!\\n"
                    "All players are already linked or no games recorded."
                )
                return

            # Build embed with top 3 options
            embed = discord.Embed(
                title="🔍 Link Your Account",
                description=(
                    f"Found **{len(top_players)}** potential matches!\\n"
                    f"React with 1️⃣/2️⃣/3️⃣ or use `!select <number>` within 60 seconds."
                ),
                color=0x3498DB,
            )

            options_data = []
            for idx, (guid, last_date, kills, deaths, games) in enumerate(
                top_players, 1
            ):
                # Get aliases for this GUID (uses 'guid' and 'alias' columns)
                async with db.execute(
                    """
                    SELECT alias, last_seen, times_seen
                    FROM player_aliases
                    WHERE guid = ?
                    ORDER BY last_seen DESC, times_seen DESC
                    LIMIT 3
                """,
                    (guid,),
                ) as cursor:
                    aliases = await cursor.fetchall()

                # Format aliases
                if aliases:
                    primary_name = aliases[0][0]
                    alias_str = ", ".join([a[0] for a in aliases[:3]])
                    if len(aliases) > 3:
                        alias_str += "..."
                else:
                    # Fallback to most recent name
                    async with db.execute(
                        """
                        SELECT player_name 
                        FROM player_comprehensive_stats 
                        WHERE player_guid = ? 
                        ORDER BY session_date DESC 
                        LIMIT 1
                    """,
                        (guid,),
                    ) as cursor:
                        name_row = await cursor.fetchone()
                        primary_name = name_row[0] if name_row else "Unknown"
                        alias_str = primary_name

                kd_ratio = kills / deaths if deaths > 0 else kills

                emoji = ["1️⃣", "2️⃣", "3️⃣"][idx - 1]
                embed.add_field(
                    name=f"{emoji} **{primary_name}**",
                    value=(
                        f"**GUID:** {guid}\\n"
                        f"**Stats:** {kills:,} kills / {deaths:,} deaths / {kd_ratio:.2f} K/D\\n"
                        f"**Games:** {games:,} | **Last Seen:** {last_date}\\n"
                        f"**Also:** {alias_str}"
                    ),
                    inline=False,
                )

                options_data.append(
                    {
                        "guid": guid,
                        "name": primary_name,
                        "kills": kills,
                        "games": games,
                    }
                )

            embed.set_footer(
                text=f"💡 Tip: Use !link <GUID> to link directly | Requested by {ctx.author.display_name}"
            )

            message = await ctx.send(embed=embed)

            # Add reaction emojis
            emojis = ["1️⃣", "2️⃣", "3️⃣"][: len(top_players)]
            for emoji in emojis:
                await message.add_reaction(emoji)

            # Wait for reaction
            def check(reaction, user):
                return (
                    user == ctx.author
                    and str(reaction.emoji) in emojis
                    and reaction.message.id == message.id
                )

            try:
                reaction, user = await self.bot.wait_for(
                    "reaction_add", timeout=60.0, check=check
                )

                # Get selected index
                selected_idx = emojis.index(str(reaction.emoji))
                selected = options_data[selected_idx]

                # Link the account
                await db.execute(
                    """
                    INSERT OR REPLACE INTO player_links
                    (discord_id, discord_username, et_guid, et_name, linked_date, verified)
                    VALUES (?, ?, ?, ?, datetime('now'), 1)
                """,
                    (
                        discord_id,
                        str(ctx.author),
                        selected["guid"],
                        selected["name"],
                    ),
                )
                await db.commit()

                # Success!
                await message.clear_reactions()
                success_embed = discord.Embed(
                    title="✅ Account Linked!",
                    description=f"Successfully linked to **{selected['name']}**",
                    color=0x00FF00,
                )
                success_embed.add_field(
                    name="Stats Preview",
                    value=f"**Games:** {selected['games']:,}\\n**Kills:** {selected['kills']:,}",
                    inline=True,
                )
                success_embed.add_field(
                    name="Quick Access",
                    value="Use `!stats` without arguments to see your stats!",
                    inline=False,
                )
                success_embed.set_footer(text=f"GUID: {selected['guid']}")
                await ctx.send(embed=success_embed)

            except asyncio.TimeoutError:
                await message.clear_reactions()
                await ctx.send(
                    "⏱️ Link request timed out. Try again with `!link`"
                )

        except Exception as e:
            logger.error(f"Error in smart self-link: {e}", exc_info=True)
            await ctx.send(f"❌ Error during self-linking: {e}")

    async def _link_by_guid(self, ctx, discord_id: str, guid: str, db):
        """Direct GUID linking with confirmation"""
        try:
            # Check if GUID exists
            async with db.execute(
                """
                SELECT 
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths,
                    COUNT(DISTINCT session_id) as games,
                    MAX(session_date) as last_seen
                FROM player_comprehensive_stats
                WHERE player_guid = ?
            """,
                (guid,),
            ) as cursor:
                stats = await cursor.fetchone()

            if not stats or stats[0] is None:
                await ctx.send(f"❌ GUID `{guid}` not found in database.")
                return

            # Get aliases (uses 'guid', 'alias', 'times_seen' columns)
            async with db.execute(
                """
                SELECT alias, last_seen, times_seen
                FROM player_aliases
                WHERE guid = ?
                ORDER BY last_seen DESC, times_seen DESC
                LIMIT 3
            """,
                (guid,),
            ) as cursor:
                aliases = await cursor.fetchall()

            if aliases:
                primary_name = aliases[0][0]
                alias_str = ", ".join([a[0] for a in aliases[:3]])
            else:
                # Fallback
                async with db.execute(
                    """
                    SELECT player_name 
                    FROM player_comprehensive_stats 
                    WHERE player_guid = ? 
                    ORDER BY session_date DESC 
                    LIMIT 1
                """,
                    (guid,),
                ) as cursor:
                    name_row = await cursor.fetchone()
                    primary_name = name_row[0] if name_row else "Unknown"
                    alias_str = primary_name

            kills, deaths, games, last_seen = stats
            kd_ratio = kills / deaths if deaths > 0 else kills

            # Confirmation embed
            embed = discord.Embed(
                title="🔗 Confirm Account Link",
                description=f"Link your Discord to **{primary_name}**?",
                color=0xFFA500,
            )
            embed.add_field(
                name="GUID",
                value=guid,
                inline=False,
            )
            embed.add_field(
                name="Known Names",
                value=alias_str,
                inline=False,
            )
            embed.add_field(
                name="Stats",
                value=f"{kills:,} kills / {deaths:,} deaths / {kd_ratio:.2f} K/D",
                inline=True,
            )
            embed.add_field(
                name="Activity",
                value=f"{games:,} games | Last: {last_seen}",
                inline=True,
            )
            embed.set_footer(text="React ✅ to confirm or ❌ to cancel (60s)")

            message = await ctx.send(embed=embed)
            await message.add_reaction("✅")
            await message.add_reaction("❌")

            def check(reaction, user):
                return (
                    user == ctx.author
                    and str(reaction.emoji) in ["✅", "❌"]
                    and reaction.message.id == message.id
                )

            try:
                reaction, user = await self.bot.wait_for(
                    "reaction_add", timeout=60.0, check=check
                )

                if str(reaction.emoji) == "✅":
                    # Confirmed - link it
                    await db.execute(
                        """
                        INSERT OR REPLACE INTO player_links
                        (discord_id, discord_username, et_guid, et_name, linked_date, verified)
                        VALUES (?, ?, ?, ?, datetime('now'), 1)
                    """,
                        (discord_id, str(ctx.author), guid, primary_name),
                    )
                    await db.commit()

                    await message.clear_reactions()
                    await ctx.send(
                        f"✅ Successfully linked to **{primary_name}** (GUID: {guid})"
                    )
                else:
                    await message.clear_reactions()
                    await ctx.send("❌ Link cancelled.")

            except asyncio.TimeoutError:
                await message.clear_reactions()
                await ctx.send("⏱️ Confirmation timed out.")

        except Exception as e:
            logger.error(f"Error in GUID link: {e}", exc_info=True)
            await ctx.send(f"❌ Error linking by GUID: {e}")

    async def _link_by_name(self, ctx, discord_id: str, player_name: str, db):
        """Name search linking (existing functionality enhanced)"""
        try:
            # Search in player_aliases first (uses 'guid' and 'alias' columns)
            async with db.execute(
                """
                SELECT DISTINCT pa.guid
                FROM player_aliases pa
                WHERE LOWER(pa.alias) LIKE LOWER(?)
                ORDER BY pa.last_seen DESC
                LIMIT 5
            """,
                (f"%{player_name}%",),
            ) as cursor:
                alias_guids = [row[0] for row in await cursor.fetchall()]

            # Also search main stats table
            async with db.execute(
                """
                SELECT player_guid, player_name,
                       SUM(kills) as total_kills,
                       COUNT(DISTINCT session_id) as games,
                       MAX(session_date) as last_seen
                FROM player_comprehensive_stats
                WHERE LOWER(player_name) LIKE LOWER(?)
                GROUP BY player_guid
                ORDER BY last_seen DESC, games DESC
                LIMIT 5
            """,
                (f"%{player_name}%",),
            ) as cursor:
                matches = await cursor.fetchall()

            # Combine and deduplicate
            guid_set = set(alias_guids)
            for match in matches:
                guid_set.add(match[0])

            if not guid_set:
                await ctx.send(
                    f"❌ No player found matching '{player_name}'\\n"
                    f"💡 Try: `!link` (no arguments) to see all available players"
                )
                return

            # Get full data for found GUIDs
            guid_list = list(guid_set)[:3]  # Limit to 3

            if len(guid_list) == 1:
                # Single match - link directly with confirmation
                await self._link_by_guid(ctx, discord_id, guid_list[0], db)
            else:
                # Multiple matches - show options (similar to smart self-link)
                embed = discord.Embed(
                    title=f"🔍 Multiple Matches for '{player_name}'",
                    description="React with 1️⃣/2️⃣/3️⃣ to select:",
                    color=0x3498DB,
                )

                options_data = []
                for idx, guid in enumerate(guid_list, 1):
                    # Get stats and aliases
                    async with db.execute(
                        """
                        SELECT SUM(kills), SUM(deaths), COUNT(DISTINCT session_id), MAX(session_date)
                        FROM player_comprehensive_stats
                        WHERE player_guid = ?
                    """,
                        (guid,),
                    ) as cursor:
                        stats = await cursor.fetchone()

                    async with db.execute(
                        """
                        SELECT alias FROM player_aliases
                        WHERE guid = ?
                        ORDER BY last_seen DESC LIMIT 1
                    """,
                        (guid,),
                    ) as cursor:
                        name_row = await cursor.fetchone()
                        name = name_row[0] if name_row else "Unknown"

                    kills, deaths, games, last_seen = stats
                    kd = kills / deaths if deaths > 0 else kills

                    emoji = ["1️⃣", "2️⃣", "3️⃣"][idx - 1]
                    embed.add_field(
                        name=f"{emoji} **{name}**",
                        value=(
                            f"**GUID:** {guid}\\n{kills:,} kills | **K/D: {kd:.2f}** | "
                            f"{games:,} games | Last: {last_seen}"
                        ),
                        inline=False,
                    )

                    options_data.append(
                        {
                            "guid": guid,
                            "name": name,
                            "kills": kills,
                            "games": games,
                        }
                    )

                message = await ctx.send(embed=embed)

                emojis = ["1️⃣", "2️⃣", "3️⃣"][: len(guid_list)]
                for emoji in emojis:
                    await message.add_reaction(emoji)

                def check(reaction, user):
                    return (
                        user == ctx.author
                        and str(reaction.emoji) in emojis
                        and reaction.message.id == message.id
                    )

                try:
                    reaction, user = await self.bot.wait_for(
                        "reaction_add", timeout=60.0, check=check
                    )
                    selected_idx = emojis.index(str(reaction.emoji))
                    selected = options_data[selected_idx]

                    await db.execute(
                        """
                        INSERT OR REPLACE INTO player_links
                        (discord_id, discord_username, et_guid, et_name, linked_date, verified)
                        VALUES (?, ?, ?, ?, datetime('now'), 1)
                    """,
                        (
                            discord_id,
                            str(ctx.author),
                            selected["guid"],
                            selected["name"],
                        ),
                    )
                    await db.commit()

                    await message.clear_reactions()
                    await ctx.send(
                        f"✅ Successfully linked to **{selected['name']}** (GUID: {selected['guid']})"
                    )

                except asyncio.TimeoutError:
                    await message.clear_reactions()
                    await ctx.send("⏱️ Selection timed out.")

        except Exception as e:
            logger.error(f"Error in name link: {e}", exc_info=True)
            await ctx.send(f"❌ Error linking by name: {e}")

    async def _admin_link(self, ctx, target_user: discord.User, guid: str):
        """Admin linking: Link another user's Discord to a GUID"""
        try:
            # Check permissions
            if not ctx.author.guild_permissions.manage_guild:
                await ctx.send(
                    "❌ You don't have permission to link other users.\\n"
                    "**Required:** Manage Server permission"
                )
                logger.warning(
                    f"Unauthorized admin link attempt by {ctx.author} "
                    f"(ID: {ctx.author.id})"
                )
                return

            # Validate GUID format (8 hex characters)
            if len(guid) != 8 or not all(
                c in "0123456789ABCDEFabcdef" for c in guid
            ):
                await ctx.send(
                    f"❌ Invalid GUID format: `{guid}`\\n"
                    f"**GUIDs must be exactly 8 hexadecimal characters** (e.g., `D8423F90`)\\n\\n"
                    f"💡 To link by player name instead:\\n"
                    f"   • Ask {target_user.mention} to use `!link {guid}` (searches by name)\\n"
                    f"   • Or use `!stats {guid}` to find their GUID first"
                )
                return

            target_discord_id = str(target_user.id)

            async with aiosqlite.connect(self.bot.db_path) as db:
                # Check if target already linked
                async with db.execute(
                    """
                    SELECT et_name, et_guid FROM player_links
                    WHERE discord_id = ?
                """,
                    (target_discord_id,),
                ) as cursor:
                    existing = await cursor.fetchone()

                if existing:
                    await ctx.send(
                        f"⚠️ {target_user.mention} is already linked to "
                        f"**{existing[0]}** (GUID: {existing[1]})\\n"
                        f"They need to `!unlink` first, or you can overwrite "
                        f"with force (react ⚠️ to confirm)."
                    )
                    # For now, just block. Future: Add force option
                    return

                # Validate GUID exists
                async with db.execute(
                    """
                    SELECT 
                        SUM(kills) as total_kills,
                        SUM(deaths) as total_deaths,
                        COUNT(DISTINCT session_id) as games,
                        MAX(session_date) as last_seen
                    FROM player_comprehensive_stats
                    WHERE player_guid = ?
                """,
                    (guid,),
                ) as cursor:
                    stats = await cursor.fetchone()

                if not stats or stats[0] is None:
                    await ctx.send(
                        f"❌ GUID `{guid}` not found in database.\\n"
                        f"💡 Use `!link` (no args) to see available players."
                    )
                    return

                # Get aliases (uses 'guid', 'alias', 'times_seen' columns)
                async with db.execute(
                    """
                    SELECT alias, last_seen, times_seen
                    FROM player_aliases
                    WHERE guid = ?
                    ORDER BY last_seen DESC, times_seen DESC
                    LIMIT 3
                """,
                    (guid,),
                ) as cursor:
                    aliases = await cursor.fetchall()

                if aliases:
                    primary_name = aliases[0][0]
                    alias_str = ", ".join([a[0] for a in aliases[:3]])
                else:
                    # Fallback
                    async with db.execute(
                        """
                        SELECT player_name 
                        FROM player_comprehensive_stats 
                        WHERE player_guid = ? 
                        ORDER BY session_date DESC 
                        LIMIT 1
                    """,
                        (guid,),
                    ) as cursor:
                        name_row = await cursor.fetchone()
                        primary_name = name_row[0] if name_row else "Unknown"
                        alias_str = primary_name

                kills, deaths, games, last_seen = stats
                kd_ratio = kills / deaths if deaths > 0 else kills

                # Admin confirmation embed
                embed = discord.Embed(
                    title="🔗 Admin Link Confirmation",
                    description=(
                        f"Link {target_user.mention} to **{primary_name}**?\\n\\n"
                        f"**Requested by:** {ctx.author.mention}"
                    ),
                    color=0xFF6B00,  # Orange for admin action
                )
                embed.add_field(
                    name="Target User",
                    value=f"{target_user.mention} ({target_user.name})",
                    inline=True,
                )
                embed.add_field(
                    name="GUID",
                    value=guid,
                    inline=True,
                )
                embed.add_field(
                    name="Known Names",
                    value=alias_str,
                    inline=False,
                )
                embed.add_field(
                    name="Stats",
                    value=(
                        f"**Kills:** {kills:,} | **Deaths:** {deaths:,}\\n"
                        f"**K/D:** {kd_ratio:.2f} | **Games:** {games:,}"
                    ),
                    inline=True,
                )
                embed.add_field(
                    name="Last Seen",
                    value=last_seen,
                    inline=True,
                )
                embed.set_footer(
                    text="React ✅ (admin) to confirm or ❌ to cancel (60s)"
                )

                message = await ctx.send(embed=embed)
                await message.add_reaction("✅")
                await message.add_reaction("❌")

                def check(reaction, user):
                    return (
                        user == ctx.author  # Only admin can confirm
                        and str(reaction.emoji) in ["✅", "❌"]
                        and reaction.message.id == message.id
                    )

                try:
                    reaction, user = await self.bot.wait_for(
                        "reaction_add", timeout=60.0, check=check
                    )

                    if str(reaction.emoji) == "✅":
                        # Confirmed - link it
                        await db.execute(
                            """
                            INSERT OR REPLACE INTO player_links
                            (discord_id, discord_username, et_guid, et_name, 
                             linked_date, verified)
                            VALUES (?, ?, ?, ?, datetime('now'), 1)
                        """,
                            (
                                target_discord_id,
                                str(target_user),
                                guid,
                                primary_name,
                            ),
                        )
                        await db.commit()

                        await message.clear_reactions()

                        # Success message
                        success_embed = discord.Embed(
                            title="✅ Admin Link Successful",
                            description=(
                                f"{target_user.mention} is now linked to "
                                f"**{primary_name}**"
                            ),
                            color=0x00FF00,
                        )
                        success_embed.add_field(
                            name="GUID",
                            value=guid,
                            inline=True,
                        )
                        success_embed.add_field(
                            name="Linked By",
                            value=ctx.author.mention,
                            inline=True,
                        )
                        success_embed.set_footer(
                            text=(
                                f"💡 {target_user.name} can now use "
                                f"!stats to see their stats"
                            )
                        )

                        await ctx.send(embed=success_embed)

                        # Log admin action
                        logger.info(
                            f"Admin link: {ctx.author} (ID: {ctx.author.id}) "
                            f"linked {target_user} (ID: {target_user.id}) "
                            f"to GUID {guid} ({primary_name})"
                        )

                    else:
                        await message.clear_reactions()
                        await ctx.send("❌ Admin link cancelled.")

                except asyncio.TimeoutError:
                    await message.clear_reactions()
                    await ctx.send("⏱️ Admin link confirmation timed out.")

        except Exception as e:
            logger.error(f"Error in admin link: {e}", exc_info=True)
            await ctx.send(f"❌ Error during admin linking: {e}")

    @commands.command(name="unlink")
    async def unlink(self, ctx):
        """🔓 Unlink your Discord account from your in-game profile"""
        try:
            discord_id = str(ctx.author.id)

            async with aiosqlite.connect(self.bot.db_path) as db:
                # Check if linked
                async with db.execute(
                    """
                    SELECT player_name FROM player_links
                    WHERE discord_id = ?
                """,
                    (discord_id,),
                ) as cursor:
                    existing = await cursor.fetchone()

                if not existing:
                    await ctx.send("❌ You don't have a linked account.")
                    return

                # Remove link
                await db.execute(
                    """
                    UPDATE player_links
                    SET discord_id = NULL
                    WHERE discord_id = ?
                """,
                    (discord_id,),
                )

                await db.commit()

            await ctx.send(f"✅ Unlinked from **{existing[0]}**")

        except Exception as e:
            logger.error(f"Error in unlink command: {e}", exc_info=True)
            await ctx.send(f"❌ Error unlinking account: {e}")

    @commands.command(name="select")
    async def select_option(self, ctx, selection: int = None):
        """🔢 Select an option from a link prompt (alternative to reactions)

        Usage: !select <1-3>

        Note: This works as an alternative to clicking reaction emojis.
        Must be used within 60 seconds of a !link command.
        """
        if selection is None:
            await ctx.send(
                "❌ Please specify a number!\\n"
                "Usage: `!select 1`, `!select 2`, or `!select 3`"
            )
            return

        if selection not in [1, 2, 3]:
            await ctx.send("❌ Please select 1, 2, or 3.")
            return

        await ctx.send(
            f"💡 You selected option **{selection}**!\\n\\n"
            f"**Note:** The `!select` command currently requires integration with the link workflow.\\n"
            f"For now, please use the reaction emojis (1️⃣/2️⃣/3️⃣) on the link message, "
            f"or use `!link <GUID>` to link directly.\\n\\n"
            f"**Tip:** To find your GUID, use `!link` (no arguments) and check the GUID field."
        )

        # TODO: Implement persistent selection state
        # This would require storing pending link requests per user
        # and checking if they have an active selection window

    async def get_hardcoded_teams(self, db, session_date):
        """🎯 Get hardcoded teams from session_teams table if available

        Returns dict with team info or None if not available:
        {
            'Team A': {
                'guids': ['GUID1', 'GUID2', ...],
                'names': ['Name1', 'Name2', ...],
                'maps': ['map1', 'map2', ...]
            },
            'Team B': { ... }
        }
        """
        try:
            import json

            # Check if session_teams table exists
            async with db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='session_teams'"
            ) as cursor:
                if not await cursor.fetchone():
                    return None

            # Get all teams for this session date
            async with db.execute(
                """
                SELECT team_name, player_guids, player_names, map_name
                FROM session_teams
                WHERE session_start_date LIKE ?
                ORDER BY team_name
                """,
                (f"{session_date}%",),
            ) as cursor:
                rows = await cursor.fetchall()

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
        return True

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
    @commands.command(name="set_teams")
    async def set_teams(self, ctx, team1_name: str, team2_name: str):
        """Manually set persistent team names for the latest session date."""
        try:
            import json
            async with aiosqlite.connect(self.bot.db_path) as db:
                await self._ensure_session_teams_table(db)

                # Determine latest session date (YYYY-MM-DD)
                async with db.execute(
                    "SELECT DISTINCT substr(session_date,1,10) as d FROM sessions ORDER BY d DESC LIMIT 1"
                ) as cur:
                    row = await cur.fetchone()
                if not row:
                    await ctx.send("❌ No sessions found to set teams for.")
                    return
                session_date = row[0]

                # Upsert two team rows with map_name='ALL' and empty rosters initially
                empty = json.dumps([])
                for tname in (team1_name, team2_name):
                    await db.execute(
                        """
                        INSERT INTO session_teams (session_start_date, map_name, team_name, player_guids, player_names)
                        VALUES (?, 'ALL', ?, ?, ?)
                        ON CONFLICT(session_start_date, map_name, team_name)
                        DO UPDATE SET team_name=excluded.team_name
                        """,
                        (session_date, tname, empty, empty),
                    )
                await db.commit()
            await ctx.send(f"✅ Teams set for {session_date}: **{team1_name}** vs **{team2_name}**")
        except Exception as e:
            logger.error(f"Error in set_teams: {e}", exc_info=True)
            await ctx.send(f"❌ Error setting teams: {e}")

    @commands.command(name="assign_player")
    async def assign_player(self, ctx, player_name: str, team_name: str):
        """Assign a player (by name) to a persistent team for the latest session date."""
        try:
            import json
            async with aiosqlite.connect(self.bot.db_path) as db:
                await self._ensure_session_teams_table(db)

                # Resolve latest session date
                async with db.execute(
                    "SELECT DISTINCT substr(session_date,1,10) as d FROM sessions ORDER BY d DESC LIMIT 1"
                ) as cur:
                    row = await cur.fetchone()
                if not row:
                    await ctx.send("❌ No sessions found.")
                    return
                session_date = row[0]

                # Resolve most recent GUID for the player (fuzzy match by alias)
                async with db.execute(
                    """
                    SELECT guid, alias
                    FROM player_aliases
                    WHERE lower(alias) LIKE lower(?)
                    ORDER BY last_seen DESC
                    LIMIT 1
                    """,
                    (f"%{player_name}%",),
                ) as cur:
                    pa = await cur.fetchone()
                if not pa:
                    await ctx.send(f"❌ Player '{player_name}' not found in aliases.")
                    return
                player_guid, resolved_alias = pa

                # Ensure team row exists for this date (map_name='ALL')
                empty = json.dumps([])
                await db.execute(
                    """
                    INSERT INTO session_teams (session_start_date, map_name, team_name, player_guids, player_names)
                    VALUES (?, 'ALL', ?, ?, ?)
                    ON CONFLICT(session_start_date, map_name, team_name)
                    DO NOTHING
                    """,
                    (session_date, team_name, empty, empty),
                )

                # Fetch current roster
                async with db.execute(
                    """
                    SELECT player_guids, player_names
                    FROM session_teams
                    WHERE session_start_date = ? AND map_name = 'ALL' AND team_name = ?
                    """,
                    (session_date, team_name),
                ) as cur:
                    row = await cur.fetchone()

                if not row:
                    await ctx.send(
                        f"❌ Team '{team_name}' not found for {session_date}. Use !set_teams first."
                    )
                    return

                guids = set(json.loads(row[0] or "[]"))
                names = set(json.loads(row[1] or "[]"))
                updated = False
                if player_guid not in guids:
                    guids.add(player_guid)
                    updated = True
                if resolved_alias not in names:
                    names.add(resolved_alias)
                    updated = True

                if updated:
                    await db.execute(
                        """
                        UPDATE session_teams
                        SET player_guids = ?, player_names = ?
                        WHERE session_start_date = ? AND map_name = 'ALL' AND team_name = ?
                        """,
                        (json.dumps(sorted(list(guids))), json.dumps(sorted(list(names))), session_date, team_name),
                    )
                    await db.commit()

            await ctx.send(
                f"✅ Assigned **{resolved_alias}** to **{team_name}** for {session_date}"
            )
        except Exception as e:
            logger.error(f"Error in assign_player: {e}", exc_info=True)
            await ctx.send(f"❌ Error assigning player: {e}")

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
        self.monitoring = False
        self.processed_files = set()
        self.auto_link_enabled = True
        self.gather_queue = {"3v3": [], "6v6": []}

        # 🤖 Automation System Flags (OFF by default for dev/testing)
        self.automation_enabled = (
            os.getenv("AUTOMATION_ENABLED", "false").lower() == "true"
        )
        self.ssh_enabled = os.getenv("SSH_ENABLED", "false").lower() == "true"

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

        # 🎯 FIVEEYES: Load synergy analytics cog (SAFE - disabled by default)
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

        # Start background tasks
        self.endstats_monitor.start()
        self.cache_refresher.start()
        self.scheduled_monitoring_check.start()
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
            player.get("team_damage_given", 0),
            player.get("team_damage_received", 0),
            obj_stats.get("gibs", 0),
            obj_stats.get("self_kills", 0),
            obj_stats.get("team_kills", 0),
            obj_stats.get("team_gibs", 0),
            player.get("headshots", 0),
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
            obj_stats.get("most_useful_kills", 0),
            obj_stats.get("useless_kills", 0),
            obj_stats.get("kill_steals", 0),
            obj_stats.get("denied_playtime", 0),
            0,  # constructions
            obj_stats.get("tank_meatshield", 0),
            obj_stats.get("double_kills", 0),
            obj_stats.get("triple_kills", 0),
            obj_stats.get("quad_kills", 0),
            obj_stats.get("multi_kills", 0),
            obj_stats.get("mega_kills", 0),
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
        5. Posts Discord round summaries
        """
        if not self.monitoring or not self.ssh_enabled:
            return

        try:
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
                    "⚠️ SSH config incomplete - monitoring disabled"
                )
                return

            # List remote files
            remote_files = await self.ssh_list_remote_files(ssh_config)

            if not remote_files:
                return

            # Check each file
            for filename in remote_files:
                # Check if already processed (4-layer check)
                if await self.should_process_file(filename):
                    logger.info(f"📥 New file detected: {filename}")

                    # Download file
                    local_path = await self.ssh_download_file(
                        ssh_config, filename, "local_stats"
                    )

                    if local_path:
                        # Wait 3 seconds for file to fully write
                        await asyncio.sleep(3)

                        # Process the file
                        await self.process_gamestats_file(local_path, filename)

        except Exception as e:
            logger.error(f"❌ endstats_monitor error: {e}")

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
