"""
🎮 Session Cog - Session Viewing Commands
Handles all session viewing and analytics commands for the Ultimate ET:Legacy Bot.

Commands:
- session: View specific session by date
- last_session: View most recent session with multiple views
- sessions: List all gaming sessions

This cog contains ~3,600 lines of session viewing logic including:
- Session summaries and detailed stats
- Team analytics and composition
- Performance graphs and visualizations
- Weapon mastery breakdowns
- Objective & support stats
- Special awards and chaos stats
"""

import asyncio
import logging
import os
from datetime import datetime

# import aiosqlite  # Removed - using database adapter
import discord
from discord.ext import commands

# Import shared utilities
from bot.core.achievement_system import AchievementSystem
from bot.core.season_manager import SeasonManager
from bot.stats import StatsCalculator
from bot.core.stats_cache import StatsCache
from tools.stopwatch_scoring import StopwatchScoring

logger = logging.getLogger("UltimateBot.SessionCog")


def _split_chunks(text: str, max_len: int = 900):
    """Helper to split long text into Discord-safe chunks"""
    lines = text.splitlines(keepends=True)
    chunks = []
    current = ""
    for line in lines:
        if len(current) + len(line) > max_len:
            chunks.append(current.rstrip())
            current = line
        else:
            current += line
    if current:
        chunks.append(current.rstrip())
    return chunks


class SessionCog(commands.Cog, name="Session Commands"):
    """🎮 Session viewing and analytics commands"""

    def __init__(self, bot):
        self.bot = bot
        # Use bot-level systems (initialized in bot's __init__)
        self.stats_cache = bot.stats_cache
        logger.info("🎮 SessionCog initializing...")

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
                if self.bot.config.database_type == 'sqlite':
                    result = await self.bot.db_adapter.fetch_one(
                        """
                        SELECT DISTINCT DATE(round_date) as date
                        FROM player_comprehensive_stats
                        ORDER BY date DESC LIMIT 1
                        """
                    )
                else:  # PostgreSQL
                    result = await self.bot.db_adapter.fetch_one(
                        """
                        SELECT DISTINCT round_date
                        FROM player_comprehensive_stats
                        ORDER BY round_date DESC LIMIT 1
                        """
                    )
                if not result:
                    await ctx.send("❌ No rounds found in database")
                    return
                # Convert to string if it's a date object (PostgreSQL)
                date_filter = str(result[0]) if result[0] else None
                if not date_filter:
                    await ctx.send("❌ No rounds found in database")
                    return

            await ctx.send(f"📅 Loading session data for **{date_filter}**...")

            # Get round metadata (database-specific)
            # Filter out R0 (warmup rounds) using round_number > 0
            if self.bot.config.database_type == 'sqlite':
                query = """
                    SELECT
                        COUNT(DISTINCT round_id) / 2 as total_maps,
                        COUNT(DISTINCT round_id) as total_rounds,
                        COUNT(DISTINCT player_guid) as player_count,
                        MIN(round_date) as first_round,
                        MAX(round_date) as last_round
                    FROM player_comprehensive_stats
                    WHERE DATE(round_date) = ? AND round_number > 0
                """
                result = await self.bot.db_adapter.fetch_one(query, (date_filter,))
            else:  # PostgreSQL
                query = """
                    SELECT
                        COUNT(DISTINCT round_id) / 2 as total_maps,
                        COUNT(DISTINCT round_id) as total_rounds,
                        COUNT(DISTINCT player_guid) as player_count,
                        MIN(round_date) as first_round,
                        MAX(round_date) as last_round
                    FROM player_comprehensive_stats
                    WHERE round_date = $1 AND round_number > 0
                """
                result = await self.bot.db_adapter.fetch_one(query, (date_filter,))
            if not result or result[0] == 0:
                await ctx.send(
                    f"❌ No round found for date: {date_filter}"
                )
                return

            (
                total_maps,
                total_rounds,
                player_count,
                first_round,
                last_round,
            ) = result

            # Get unique maps played (database-specific)
            # Filter out R0 (warmup rounds) using round_number > 0
            if self.bot.config.database_type == 'sqlite':
                maps = await self.bot.db_adapter.fetch_all(
                    """
                    SELECT DISTINCT map_name
                    FROM player_comprehensive_stats
                    WHERE DATE(round_date) = ? AND round_number > 0
                    ORDER BY round_date
                """,
                    (date_filter,)
                )
            else:  # PostgreSQL
                maps = await self.bot.db_adapter.fetch_all(
                    """
                    SELECT DISTINCT map_name, MIN(round_date) as first_seen
                    FROM player_comprehensive_stats
                    WHERE round_date = $1 AND round_number > 0
                    GROUP BY map_name
                    ORDER BY first_seen
                """,
                    (date_filter,)
                )
            maps_list = [m[0] for m in maps]

            # Build header embed
            embed = discord.Embed(
                title=f"📊 Session Summary: {date_filter}",
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

            # Get top players aggregated (database-specific)
            # Filter out R0 (warmup rounds) using round_number > 0
            if self.bot.config.database_type == 'sqlite':
                top_players = await self.bot.db_adapter.fetch_all(
                    """
                    SELECT
                        p.player_name,
                        SUM(p.kills) as kills,
                        SUM(p.deaths) as deaths,
                        CASE
                            WHEN SUM(
                                CASE
                                    WHEN r.actual_time LIKE '%:%' THEN
                                        (CAST(SUBSTR(r.actual_time, 1, INSTR(r.actual_time, ':')-1) AS INTEGER) * 60 +
                                         CAST(SUBSTR(r.actual_time, INSTR(r.actual_time, ':')+1) AS INTEGER))
                                    ELSE
                                        CAST(r.actual_time AS INTEGER)
                                END
                            ) > 0
                            THEN (SUM(p.damage_given) * 60.0) / SUM(
                                CASE
                                    WHEN r.actual_time LIKE '%:%' THEN
                                        (CAST(SUBSTR(r.actual_time, 1, INSTR(r.actual_time, ':')-1) AS INTEGER) * 60 +
                                         CAST(SUBSTR(r.actual_time, INSTR(r.actual_time, ':')+1) AS INTEGER))
                                    ELSE
                                        CAST(r.actual_time AS INTEGER)
                                END
                            )
                            ELSE 0
                        END as dpm
                    FROM player_comprehensive_stats p
                    WHERE DATE(p.round_date) = ? AND p.round_number > 0
                    GROUP BY p.player_name
                    ORDER BY kills DESC
                    LIMIT 5
                """,
                    (date_filter,)
                )
            else:  # PostgreSQL
                top_players = await self.bot.db_adapter.fetch_all(
                    """
                    SELECT
                        p.player_name,
                        SUM(p.kills) as kills,
                        SUM(p.deaths) as deaths,
                        CASE
                            WHEN SUM(
                                CASE
                                    WHEN r.actual_time LIKE '%:%' THEN
                                        CAST(SPLIT_PART(r.actual_time, ':', 1) AS INTEGER) * 60 +
                                        CAST(SPLIT_PART(r.actual_time, ':', 2) AS INTEGER)
                                    ELSE
                                        CAST(r.actual_time AS INTEGER)
                                END
                            ) > 0
                            THEN (SUM(p.damage_given) * 60.0) / SUM(
                                CASE
                                    WHEN r.actual_time LIKE '%:%' THEN
                                        CAST(SPLIT_PART(r.actual_time, ':', 1) AS INTEGER) * 60 +
                                        CAST(SPLIT_PART(r.actual_time, ':', 2) AS INTEGER)
                                    ELSE
                                        CAST(r.actual_time AS INTEGER)
                                END
                            )
                            ELSE 0
                        END as dpm
                    FROM player_comprehensive_stats p
                    WHERE p.round_date = $1 AND p.round_number > 0
                    GROUP BY p.player_name
                    ORDER BY kills DESC
                    LIMIT 5
                """,
                    (date_filter,)
                )

            # Add top 5 players
            if top_players:
                player_text = ""
                medals = ["🥇", "🥈", "🥉", "4.", "5."]
                for i, (name, kills, deaths, dpm) in enumerate(
                    top_players
                ):
                    kd = StatsCalculator.calculate_kd(kills, deaths)
                    player_text += f"{medals[i]} **{name}** • {kills}K/{deaths}D ({kd:.2f}) • {dpm:.0f} DPM\n"
                embed.add_field(
                    name="🏆 Top Players", value=player_text, inline=False
                )

            embed.set_footer(
                text="💡 Use !last_round for the most recent session with full details"
            )
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in session command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving session: {e}")

    # NOTE: !last_session command has been moved to Last Round Cog
    # See bot/cogs/last_session_cog.py for the full implementation
    # This stub has been removed to avoid command conflicts

    @commands.command(name="rounds", aliases=["sessions", "list_sessions", "ls"])
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
                    return

                # Use database adapter (works for both SQLite and PostgreSQL)
                if self.bot.config.database_type == 'sqlite':
                    query = """
                        SELECT 
                            DATE(round_date) as date,
                            COUNT(DISTINCT round_id) / 2 as maps,
                            COUNT(DISTINCT round_id) as rounds,
                            COUNT(DISTINCT player_guid) as players,
                            MIN(round_date) as first_round,
                            MAX(round_date) as last_round
                        FROM player_comprehensive_stats
                        WHERE round_date LIKE ?
                        GROUP BY DATE(round_date)
                        ORDER BY date DESC
                    """
                    sessions = await self.bot.db_adapter.fetch_all(query, (f"{month_filter}%",))
                else:  # PostgreSQL
                    query = """
                        SELECT 
                            DATE(round_date::date) as date,
                            COUNT(DISTINCT round_id) / 2 as maps,
                            COUNT(DISTINCT round_id) as rounds,
                            COUNT(DISTINCT player_guid) as players,
                            MIN(round_date) as first_round,
                            MAX(round_date) as last_round
                        FROM player_comprehensive_stats
                        WHERE round_date LIKE $1
                        GROUP BY DATE(round_date::date)
                        ORDER BY date DESC
                    """
                    sessions = await self.bot.db_adapter.fetch_all(query, (f"{month_filter}%",))
                filter_text = month_filter
            else:
                # Use database adapter (works for both SQLite and PostgreSQL)
                if self.bot.config.database_type == 'sqlite':
                    query = """
                        SELECT 
                            DATE(round_date) as date,
                            COUNT(DISTINCT round_id) / 2 as maps,
                            COUNT(DISTINCT round_id) as rounds,
                            COUNT(DISTINCT player_guid) as players,
                            MIN(round_date) as first_round,
                            MAX(round_date) as last_round
                        FROM player_comprehensive_stats
                        GROUP BY DATE(round_date)
                        ORDER BY date DESC
                        LIMIT 20
                    """
                    sessions = await self.bot.db_adapter.fetch_all(query)
                else:  # PostgreSQL
                    query = """
                        SELECT 
                            DATE(round_date::date) as date,
                            COUNT(DISTINCT round_id) / 2 as maps,
                            COUNT(DISTINCT round_id) as rounds,
                            COUNT(DISTINCT player_guid) as players,
                            MIN(round_date) as first_round,
                            MAX(round_date) as last_round
                        FROM player_comprehensive_stats
                        GROUP BY DATE(round_date::date)
                        ORDER BY date DESC
                        LIMIT 20
                    """
                    sessions = await self.bot.db_adapter.fetch_all(query)
                filter_text = "all time (last 20)"

            if not sessions:
                await ctx.send(f"❌ No rounds found for {filter_text}")
                return

            # Create embed
            embed = discord.Embed(
                title="📅 Gaming Sessions",
                description=f"Showing sessions from **{filter_text}**",
                color=discord.Color.blue(),
            )

            session_list = []
            for row in sessions:
                # Handle both dict (PostgreSQL) and tuple (SQLite) results
                if isinstance(row, dict):
                    date = row['date']
                    maps = row['maps']
                    rounds = row['rounds']
                    players = row['players']
                    first = row['first_round']
                    last = row['last_round']
                else:
                    date, maps, rounds, players, first, last = row
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


async def setup(bot):
    """Load the Session Cog"""
    await bot.add_cog(SessionCog(bot))
