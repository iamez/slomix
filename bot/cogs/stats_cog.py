"""
Stats Cog - General statistics, comparisons, achievements, and seasons

This cog handles:
- !ping - Bot status and performance check
- !check_achievements - Achievement progress tracking
- !compare - Visual comparison of two players with radar chart
- !season_info - Current season details and champions
- !help_command - Command help system

Commands use the bot's StatsCache for performance and SeasonManager for
season filtering. All commands support @mentions and linked accounts.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

import discord
from discord.ext import commands

from bot.core.checks import is_public_channel
from bot.core.database_adapter import ensure_player_name_alias
from bot.core.utils import escape_like_pattern_for_query, sanitize_error_message
from bot.stats import StatsCalculator

logger = logging.getLogger(__name__)


class StatsCog(commands.Cog, name="Stats"):
    """General statistics, player comparisons, achievements, and season info"""

    def __init__(self, bot):
        self.bot = bot
        self.stats_cache = bot.stats_cache
        self.season_manager = bot.season_manager
        self.achievements = bot.achievements
        logger.info("📊 StatsCog initializing...")

    @is_public_channel()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.command(name="ping")
    async def ping(self, ctx):
        """🏓 Check bot status and performance"""
        try:
            import time
            start_time = time.time()

            # Test database connection
            # Apply runtime alias to avoid schema mismatch errors
            try:
                await ensure_player_name_alias(self.bot.db_adapter, self.bot.config)
            except Exception:  # nosec B110
                pass  # Alias is optional
            await self.bot.db_adapter.execute("SELECT 1")

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
            await ctx.send(f"❌ Bot error: {sanitize_error_message(e)}")

    @is_public_channel()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command(name="check_achievements", aliases=["check_achivements", "check_achievement"])
    async def check_achievements_cmd(self, ctx, *, player_name: Optional[str] = None):
        """🏆 Check your achievement progress

        Usage:
        - !check_achievements          → Your achievements (if linked)
        - !check_achievements player   → Check specific player
        - !check_achievements @user    → Check mentioned user
        """
        try:
            player_guid = None
            display_name = None

            # Ensure connection has player_name alias if needed
            try:
                await ensure_player_name_alias(self.bot.db_adapter, self.bot.config)
            except Exception:  # nosec B110
                pass  # Alias is optional
            
            # Handle @mention
            if ctx.message.mentions:
                mentioned_user = ctx.message.mentions[0]
                mentioned_id = int(mentioned_user.id)  # Convert to int for PostgreSQL BIGINT

                link = await self.bot.db_adapter.fetch_one(
                    "SELECT player_guid, player_name FROM player_links WHERE discord_id = ?",
                    (mentioned_id,),
                )

                if not link:
                    await ctx.send(
                        f"❌ {mentioned_user.mention} hasn't linked their account yet!"
                    )
                    return

                player_guid = link[0]
                display_name = link[1]

            # Handle no arguments - use author's linked account
            elif not player_name:
                discord_id = int(ctx.author.id)  # BIGINT in PostgreSQL
                placeholder = '$1' if self.bot.config.database_type == 'postgresql' else '?'
                link = await self.bot.db_adapter.fetch_one(
                    f"SELECT player_guid, player_name FROM player_links WHERE discord_id = {placeholder}",
                    (discord_id,),
                )

                if not link:
                    await ctx.send(
                        "❌ Please link your account with `!link` or specify a player name!"
                    )
                    return

                player_guid = link[0]
                display_name = link[1]

            # Handle player name search
            else:
                # Escape LIKE pattern special chars to prevent injection
                safe_pattern = escape_like_pattern_for_query(player_name)
                result = await self.bot.db_adapter.fetch_one(
                    "SELECT guid, alias FROM player_aliases "
                    "WHERE LOWER(alias) LIKE LOWER(?) ESCAPE '\\' "
                    "ORDER BY last_seen DESC LIMIT 1",
                    (safe_pattern,),
                )

                if not result:
                    await ctx.send(f"❌ Player '{player_name}' not found!")
                    return

                player_guid = result[0]
                display_name = result[1]

            # Get player stats
            stats = await self.bot.db_adapter.fetch_one(
                """
                SELECT
                    SUM(p.kills) as total_kills,
                    SUM(p.deaths) as total_deaths,
                    COUNT(DISTINCT p.round_id) as total_games,
                    CASE
                        WHEN SUM(p.deaths) > 0
                        THEN CAST(SUM(p.kills) AS REAL) / SUM(p.deaths)
                        ELSE SUM(p.kills)
                    END as overall_kd
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE p.player_guid = ?
                  AND r.round_number IN (1, 2)
                  AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
            """,
                (player_guid,),
            )

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
            await ctx.send(
                f"❌ Error checking achievements: {sanitize_error_message(e)}")

    @is_public_channel()
    @commands.cooldown(1, 15, commands.BucketType.user)
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

            # Ensure player_name alias for this command's DB connection
            try:
                await ensure_player_name_alias(self.bot.db_adapter, self.bot.config)
            except Exception:  # nosec B110
                pass  # Alias is optional

            # Helper: get stats when we already have a GUID
            async def get_player_stats_by_guid(player_guid, display_name):
                # Get comprehensive stats with round durations for DPM
                stats = await self.bot.db_adapter.fetch_one(
                    """
                    SELECT
                        SUM(p.kills) as total_kills,
                        SUM(p.deaths) as total_deaths,
                        COUNT(DISTINCT p.round_id) as total_games,
                        SUM(p.damage_given) as total_damage,
                        SUM(p.headshot_kills) as total_headshots,
                        SUM(p.time_played_seconds) as total_time_seconds
                    FROM player_comprehensive_stats p
                    JOIN rounds r ON p.round_id = r.id
                    WHERE p.player_guid = ?
                      AND r.round_number IN (1, 2)
                      AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                """,
                    (player_guid,),
                )

                if not stats or stats[0] is None:
                    return None

                kills, deaths, games, damage, headshots, time_sec = stats

                # Get weapon stats for accuracy and headshot hits
                weapon_stats = await self.bot.db_adapter.fetch_one(
                    """
                    SELECT
                        SUM(w.hits) as total_hits,
                        SUM(w.shots) as total_shots,
                        SUM(w.headshots) as total_headshot_hits
                    FROM weapon_comprehensive_stats w
                    JOIN rounds r ON w.round_id = r.id
                    WHERE w.player_guid = ?
                      AND r.round_number IN (1, 2)
                      AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                """,
                    (player_guid,),
                )

                hits, shots, headshot_hits = weapon_stats if weapon_stats else (0, 0, 0)

                # Calculate metrics using centralized calculator
                kd = StatsCalculator.calculate_kd(kills, deaths)
                accuracy = StatsCalculator.calculate_accuracy(hits, shots)
                dpm = StatsCalculator.calculate_dpm(damage, time_sec)
                hs_pct = StatsCalculator.calculate_headshot_accuracy(headshot_hits, hits)

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
                    discord_id = int(m.group(1))  # Convert to int for PostgreSQL BIGINT
                    link = await self.bot.db_adapter.fetch_one(
                        "SELECT player_guid, player_name FROM player_links WHERE discord_id = ?",
                        (discord_id,),
                    )

                    if link:
                        return await get_player_stats_by_guid(link[0], link[1])

                # Try player_aliases first (name search)
                # Escape LIKE pattern special chars to prevent injection
                safe_pattern = escape_like_pattern_for_query(player_name)
                result = await self.bot.db_adapter.fetch_one(
                    "SELECT guid, alias FROM player_aliases "
                    "WHERE LOWER(alias) LIKE LOWER(?) ESCAPE '\\' "
                    "ORDER BY last_seen DESC LIMIT 1",
                    (safe_pattern,),
                )

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
            except Exception:  # nosec B110
                pass  # Cleanup failure is non-critical

            logger.info(
                f"📊 Comparison generated: {p1_stats['name']} vs {p2_stats['name']}"
            )

        except Exception as e:
            logger.error(f"Error in compare command: {e}", exc_info=True)
            await ctx.send(f"❌ Error generating comparison: {sanitize_error_message(e)}")

    @is_public_channel()
    @commands.cooldown(1, 10, commands.BucketType.user)
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
            # Apply per-connection alias to handle legacy DB column names
            try:
                await ensure_player_name_alias(self.bot.db_adapter, self.bot.config)
            except Exception:  # nosec B110
                pass  # Alias is optional
            season_filter = self.season_manager.get_season_sql_filter()

            # Season kills leader
            # Note: season_filter is a trusted SQL fragment from SeasonManager, not user input
            season_query = """
                SELECT
                    (SELECT player_name FROM player_comprehensive_stats
                     WHERE player_guid = p.player_guid
                     GROUP BY player_name
                     ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                    SUM(p.kills) as total_kills,
                    SUM(p.deaths) as total_deaths,
                    COUNT(DISTINCT p.round_id) as games
                FROM player_comprehensive_stats p
                JOIN rounds s ON p.round_id = s.id
                WHERE s.round_number IN (1, 2)
                  AND (s.round_status IN ('completed', 'substitution') OR s.round_status IS NULL)
                  {season_filter}
                GROUP BY p.player_guid
                HAVING COUNT(DISTINCT p.round_id) > 5
                ORDER BY total_kills DESC
                LIMIT 1
            """.format(season_filter=season_filter)  # nosec B608 - season_filter from trusted SeasonManager

            season_leader = await self.bot.db_adapter.fetch_one(season_query)

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
                    COUNT(DISTINCT p.round_id) as games
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE r.round_number IN (1, 2)
                  AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                GROUP BY p.player_guid
                HAVING games > 10
                ORDER BY total_kills DESC
                LIMIT 1
            """

            alltime_leader = await self.bot.db_adapter.fetch_one(alltime_query)

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
            await ctx.send(
                f"❌ Error retrieving season information: {sanitize_error_message(e)}")

    @is_public_channel()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.command(name="help_command", aliases=["commands", "cmds", "bothelp"])
    async def help_command(self, ctx, category: str = None):
        """📚 Show all available commands with examples
        
        Usage: !help [category]
        Categories: stats, sessions, teams, predictions, synergy, server, admin, automation
        """
        
        # Define all command categories
        categories = {
            "stats": self._help_stats,
            "sessions": self._help_sessions,
            "teams": self._help_teams,
            "predictions": self._help_predictions,
            "synergy": self._help_synergy,
            "server": self._help_server,
            "admin": self._help_admin,
            "automation": self._help_automation,
            "players": self._help_players,
        }
        
        # If category specified, show that category only
        if category and category.lower() in categories:
            embed = categories[category.lower()]()
            await ctx.send(embed=embed)
            return
        
        # Main overview embed
        embed1 = discord.Embed(
            title="🚀 Ultimate ET:Legacy Bot - Command Reference",
            description=(
                "**60+ commands across 16 modules!**\n"
                "Use `!help <category>` for detailed commands:\n"
                "`stats` `sessions` `teams` `predictions` `synergy` `server` `players` `admin` `automation`"
            ),
            color=0x0099FF,
        )

        embed1.add_field(
            name="📊 **Session Commands** (8)",
            value=(
                "`!last_session` `!session` `!sessions`\n"
                "`!session_start` `!session_end`\n"
                "└ Aliases: `!last`, `!latest`, `!ls`, `!rounds`"
            ),
            inline=True,
        )

        embed1.add_field(
            name="🎯 **Player Stats** (7)",
            value=(
                "`!stats` `!leaderboard` `!compare`\n"
                "`!list_players` `!find_player`\n"
                "└ Aliases: `!lb`, `!top`, `!fp`"
            ),
            inline=True,
        )

        embed1.add_field(
            name="👥 **Team Commands** (6)",
            value=(
                "`!teams` `!session_score` `!lineup_changes`\n"
                "`!set_team_names` `!set_teams` `!assign_player`"
            ),
            inline=True,
        )

        embed1.add_field(
            name="🏆 **Achievements** (4)",
            value=(
                "`!achievements` `!check_achievements`\n"
                "`!badges` `!season_info`\n"
                "└ Aliases: `!medals`, `!season`"
            ),
            inline=True,
        )

        embed1.add_field(
            name="🎲 **Predictions** (7)",
            value=(
                "`!predictions` `!prediction_stats`\n"
                "`!my_predictions` `!prediction_trends`\n"
                "`!prediction_leaderboard` `!map_predictions`"
            ),
            inline=True,
        )

        embed1.add_field(
            name="🤝 **Synergy & Analytics** (7)",
            value=(
                "`!synergy` `!best_duos` `!team_builder`\n"
                "`!suggest_teams` `!player_impact`\n"
                "└ Aliases: `!duo`, `!tb`, `!st`"
            ),
            inline=True,
        )

        embed1.add_field(
            name="🖥️ **Server Control** (10)",
            value=(
                "`!server_status` `!server_start` `!server_stop`\n"
                "`!server_restart` `!list_maps` `!addmap`\n"
                "`!changemap` `!rcon` `!kick` `!say`"
            ),
            inline=True,
        )

        embed1.add_field(
            name="👤 **Player Linking** (6)",
            value=(
                "`!link` `!unlink` `!select`\n"
                "`!setname` `!myaliases`\n"
                "└ Link Discord to ET name"
            ),
            inline=True,
        )

        embed1.add_field(
            name="⚙️ **Admin & Automation** (14)",
            value=(
                "`!health` `!ssh_stats` `!automation_status`\n"
                "`!sync_stats` `!cache_clear` `!reload`\n"
                "└ Use `!help admin` for full list"
            ),
            inline=True,
        )

        # Examples embed
        embed2 = discord.Embed(
            title="💡 Quick Examples",
            color=0x00FF00,
        )

        embed2.add_field(
            name="📅 **Sessions**",
            value=(
                "```\n"
                "!last_session        → Latest (5 graphs!)\n"
                "!session 2025-11-02  → Specific date\n"
                "!sessions 10         → October only\n"
                "```"
            ),
            inline=True,
        )

        embed2.add_field(
            name="🎯 **Stats**",
            value=(
                "```\n"
                "!stats carniee       → Player stats\n"
                "!lb kills            → Leaderboard\n"
                "!compare p1 p2       → Head-to-head\n"
                "```"
            ),
            inline=True,
        )

        embed2.add_field(
            name="🤝 **Synergy**",
            value=(
                "```\n"
                "!synergy p1 p2       → Duo chemistry\n"
                "!best_duos           → Top pairs\n"
                "!suggest_teams       → Balance teams\n"
                "```"
            ),
            inline=True,
        )

        embed2.add_field(
            name="🔥 **Pro Tips**",
            value=(
                "• **Date format**: `YYYY-MM-DD` (e.g., `2025-11-02`)\n"
                "• **Player names**: Case-insensitive\n"
                "• **Month filters**: Numbers (`10`) or names (`october`)\n"
                "• **Aliases**: Many shortcuts exist (`!lb` = `!leaderboard`)"
            ),
            inline=False,
        )

        embed2.set_footer(
            text="📖 Use !help <category> for detailed commands | 🐛 Report issues to admins"
        )

        await ctx.send(embed=embed1)
        await ctx.send(embed=embed2)

    def _help_stats(self) -> discord.Embed:
        """Generate stats category help embed"""
        embed = discord.Embed(
            title="🎯 Player Stats Commands",
            description="View individual player statistics and comparisons",
            color=0xFF6B6B,
        )
        embed.add_field(
            name="`!stats <player>`",
            value="View comprehensive player statistics\n└ Example: `!stats carniee`",
            inline=False,
        )
        embed.add_field(
            name="`!leaderboard [stat] [page]`",
            value="Top players by stat (kills, accuracy, kd, revives, xp, etc.)\n└ Aliases: `!lb`, `!top`\n└ Example: `!lb accuracy 2`",
            inline=False,
        )
        embed.add_field(
            name="`!compare <player1> <player2>`",
            value="Head-to-head player comparison\n└ Example: `!compare carniee superboyy`",
            inline=False,
        )
        embed.add_field(
            name="`!achievements [player]`",
            value="View player achievements and badges\n└ Aliases: `!medals`, `!achievement`",
            inline=False,
        )
        embed.add_field(
            name="`!check_achievements [player]`",
            value="Check achievement progress",
            inline=False,
        )
        embed.add_field(
            name="`!badges`",
            value="Show achievement badge legend\n└ Aliases: `!badge_legend`, `!achievements_legend`",
            inline=False,
        )
        embed.add_field(
            name="`!season_info`",
            value="Current season statistics\n└ Aliases: `!season`, `!seasons`",
            inline=False,
        )
        return embed

    def _help_sessions(self) -> discord.Embed:
        """Generate sessions category help embed"""
        embed = discord.Embed(
            title="📊 Session Commands",
            description="View gaming sessions and rounds",
            color=0x4ECDC4,
        )
        embed.add_field(
            name="`!last_session [subcommand]`",
            value=(
                "View latest gaming session with 5 performance graphs\n"
                "└ Aliases: `!last`, `!latest`, `!recent`, `!last_round`\n"
                "└ Subcommands: `graphs`, `stats`, `weapons`, `teams`"
            ),
            inline=False,
        )
        embed.add_field(
            name="`!session <date>`",
            value="View specific date session\n└ Aliases: `!match`, `!game`\n└ Example: `!session 2025-11-02`",
            inline=False,
        )
        embed.add_field(
            name="`!sessions [month]`",
            value="List all gaming sessions, optionally filtered by month\n└ Aliases: `!rounds`, `!list_sessions`, `!ls`\n└ Example: `!sessions 10` or `!sessions october`",
            inline=False,
        )
        embed.add_field(
            name="`!team_history <player>`",
            value="View a player's team history across sessions",
            inline=False,
        )
        embed.add_field(
            name="`!session_start`",
            value="🔒 Admin: Mark start of new gaming session",
            inline=False,
        )
        embed.add_field(
            name="`!session_end`",
            value="🔒 Admin: Mark end of current gaming session",
            inline=False,
        )
        return embed

    def _help_teams(self) -> discord.Embed:
        """Generate teams category help embed"""
        embed = discord.Embed(
            title="👥 Team Commands",
            description="View and manage team information",
            color=0x45B7D1,
        )
        embed.add_field(
            name="`!teams [date]`",
            value="Show team rosters for a session\n└ Example: `!teams 2025-11-02`",
            inline=False,
        )
        embed.add_field(
            name="`!session_score [date]`",
            value="Team scores with map-by-map breakdown",
            inline=False,
        )
        embed.add_field(
            name="`!lineup_changes [current] [previous]`",
            value="Show who switched teams between sessions\n└ Example: `!lineup_changes 2025-11-02`",
            inline=False,
        )
        embed.add_field(
            name="`!set_team_names <date> <team_a> <team_b>`",
            value="🔒 Admin: Set custom team names for a session\n└ Example: `!set_team_names 2025-11-02 Alpha Bravo`",
            inline=False,
        )
        embed.add_field(
            name="`!set_teams`",
            value="🔒 Admin: Manually set team assignments",
            inline=False,
        )
        embed.add_field(
            name="`!assign_player <player> <team>`",
            value="🔒 Admin: Assign player to a team",
            inline=False,
        )
        return embed

    def _help_predictions(self) -> discord.Embed:
        """Generate predictions category help embed"""
        embed = discord.Embed(
            title="🎲 Prediction Commands",
            description="Match predictions and betting system",
            color=0xF7DC6F,
        )
        embed.add_field(
            name="`!predictions`",
            value="View available predictions and place bets",
            inline=False,
        )
        embed.add_field(
            name="`!prediction_stats`",
            value="Your prediction statistics and accuracy\n└ Aliases: `!pred_stats`",
            inline=False,
        )
        embed.add_field(
            name="`!my_predictions`",
            value="View your prediction history",
            inline=False,
        )
        embed.add_field(
            name="`!prediction_trends`",
            value="Analyze prediction trends over time",
            inline=False,
        )
        embed.add_field(
            name="`!prediction_leaderboard`",
            value="Top predictors by accuracy",
            inline=False,
        )
        embed.add_field(
            name="`!map_predictions`",
            value="Predictions by map statistics",
            inline=False,
        )
        embed.add_field(
            name="`!prediction_help`",
            value="Detailed prediction system help",
            inline=False,
        )
        return embed

    def _help_synergy(self) -> discord.Embed:
        """Generate synergy & analytics help embed"""
        embed = discord.Embed(
            title="🤝 Synergy & Analytics Commands",
            description="Player chemistry and team building tools",
            color=0xBB8FCE,
        )
        embed.add_field(
            name="`!synergy <player1> <player2>`",
            value="Analyze duo chemistry and performance\n└ Aliases: `!chemistry`, `!duo`\n└ Example: `!synergy carniee superboyy`",
            inline=False,
        )
        embed.add_field(
            name="`!best_duos [count]`",
            value="Show top performing player pairs\n└ Aliases: `!top_duos`, `!best_pairs`\n└ Example: `!best_duos 10`",
            inline=False,
        )
        embed.add_field(
            name="`!team_builder <players...>`",
            value="Build optimal teams from player list\n└ Aliases: `!tb`, `!build_teams`",
            inline=False,
        )
        embed.add_field(
            name="`!suggest_teams`",
            value="Auto-suggest balanced team compositions\n└ Aliases: `!suggest`, `!balance`, `!st`",
            inline=False,
        )
        embed.add_field(
            name="`!player_impact <player>`",
            value="Analyze player's impact on teammates\n└ Aliases: `!teammates`, `!partners`",
            inline=False,
        )
        embed.add_field(
            name="`!recalculate_synergies`",
            value="🔒 Admin: Recalculate synergy data",
            inline=False,
        )
        return embed

    def _help_server(self) -> discord.Embed:
        """Generate server control help embed"""
        embed = discord.Embed(
            title="🖥️ Server Control Commands",
            description="Game server management (requires permissions)",
            color=0xE74C3C,
        )
        embed.add_field(
            name="`!server_status`",
            value="View game server status\n└ Aliases: `!status`, `!srv_status`",
            inline=False,
        )
        embed.add_field(
            name="`!server_start`",
            value="🔒 Start the game server\n└ Aliases: `!start`, `!srv_start`",
            inline=False,
        )
        embed.add_field(
            name="`!server_stop`",
            value="🔒 Stop the game server\n└ Aliases: `!stop`, `!srv_stop`",
            inline=False,
        )
        embed.add_field(
            name="`!server_restart`",
            value="🔒 Restart the game server\n└ Aliases: `!restart`, `!srv_restart`",
            inline=False,
        )
        embed.add_field(
            name="`!list_maps`",
            value="List available maps\n└ Aliases: `!map_list`, `!listmaps`",
            inline=False,
        )
        embed.add_field(
            name="`!addmap`",
            value="🔒 Upload a new map (attach .pk3)\n└ Aliases: `!map_add`, `!upload_map`",
            inline=False,
        )
        embed.add_field(
            name="`!changemap <mapname>`",
            value="🔒 Change current map\n└ Aliases: `!map_change`, `!map`",
            inline=False,
        )
        embed.add_field(
            name="`!rcon <command>`",
            value="🔒 Execute RCON command",
            inline=False,
        )
        embed.add_field(
            name="`!kick <player>` / `!say <message>`",
            value="🔒 Kick player / Send server message",
            inline=False,
        )
        return embed

    def _help_players(self) -> discord.Embed:
        """Generate player linking help embed"""
        embed = discord.Embed(
            title="👤 Player Linking Commands",
            description="Link your Discord account to your ET player name",
            color=0x3498DB,
        )
        embed.add_field(
            name="`!list_players [page]`",
            value="Show all registered players\n└ Aliases: `!players`, `!lp`",
            inline=False,
        )
        embed.add_field(
            name="`!find_player <name>`",
            value="Search for a player by name\n└ Aliases: `!findplayer`, `!fp`, `!search_player`",
            inline=False,
        )
        embed.add_field(
            name="`!link <guid|name>`",
            value="Link your Discord to an ET player",
            inline=False,
        )
        embed.add_field(
            name="`!unlink`",
            value="Unlink your Discord from ET player",
            inline=False,
        )
        embed.add_field(
            name="`!select <number>`",
            value="Select player when multiple matches found",
            inline=False,
        )
        embed.add_field(
            name="`!setname <newname>`",
            value="Set your preferred display name",
            inline=False,
        )
        embed.add_field(
            name="`!myaliases`",
            value="View all your linked player aliases\n└ Aliases: `!aliases`, `!mynames`",
            inline=False,
        )
        return embed

    def _help_admin(self) -> discord.Embed:
        """Generate admin commands help embed"""
        embed = discord.Embed(
            title="⚙️ Admin Commands",
            description="🔒 Requires administrator permissions",
            color=0x95A5A6,
        )
        embed.add_field(
            name="**Sync Commands**",
            value=(
                "`!sync_stats` - Sync stats from game server\n"
                "`!sync_today` - Sync last 24 hours\n"
                "`!sync_week` - Sync last 7 days\n"
                "`!sync_month` - Sync last 30 days\n"
                "`!sync_all` - Full sync (slow)"
            ),
            inline=False,
        )
        embed.add_field(
            name="**Cache & System**",
            value=(
                "`!cache_clear` - Clear stats cache\n"
                "`!reload <cog>` - Reload a cog module\n"
                "`!weapon_diag` - Weapon diagnostics"
            ),
            inline=False,
        )
        embed.add_field(
            name="**Prediction Admin**",
            value=(
                "`!admin_predictions` - Admin prediction panel\n"
                "`!update_prediction_outcome` - Update results\n"
                "`!recalculate_predictions` - Recalc all predictions\n"
                "`!prediction_performance` - System performance"
            ),
            inline=False,
        )
        embed.add_field(
            name="**FiveEyes System**",
            value=(
                "`!fiveeyes_enable` - Enable FiveEyes tracking\n"
                "`!fiveeyes_disable` - Disable FiveEyes"
            ),
            inline=False,
        )
        return embed

    def _help_automation(self) -> discord.Embed:
        """Generate automation commands help embed"""
        embed = discord.Embed(
            title="🤖 Automation Commands",
            description="Bot health and automated systems",
            color=0x1ABC9C,
        )
        embed.add_field(
            name="`!health`",
            value="View bot health and system status",
            inline=False,
        )
        embed.add_field(
            name="`!ssh_stats`",
            value="SSH connection statistics",
            inline=False,
        )
        embed.add_field(
            name="`!automation_status`",
            value="View all automation services status",
            inline=False,
        )
        embed.add_field(
            name="`!start_monitoring`",
            value="🔒 Start SSH monitoring service",
            inline=False,
        )
        embed.add_field(
            name="`!stop_monitoring`",
            value="🔒 Stop SSH monitoring service",
            inline=False,
        )
        embed.add_field(
            name="`!metrics_report`",
            value="Detailed metrics report",
            inline=False,
        )
        embed.add_field(
            name="`!metrics_summary`",
            value="Quick metrics overview",
            inline=False,
        )
        embed.add_field(
            name="`!backup_db`",
            value="🔒 Create database backup",
            inline=False,
        )
        embed.add_field(
            name="`!vacuum_db`",
            value="🔒 Optimize database (vacuum)",
            inline=False,
        )
        embed.add_field(
            name="`!ping`",
            value="Check bot latency",
            inline=False,
        )
        return embed

    @is_public_channel()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command(name="badges", aliases=["badge_legend", "achievements_legend"])
    async def badges_legend(self, ctx):
        """🏅 Show achievement badge legend

        Displays all available achievement badges and their requirements.
        """
        embed = discord.Embed(
            title="🏅 Achievement Badge Legend",
            description="Badges are earned through lifetime achievements across all sessions.\nThey appear next to your name in session stats!",
            color=0xFFD700,
        )

        # Kill Milestones
        embed.add_field(
            name="💀 Kill Milestones",
            value=(
                "🎯 **100 kills**\n"
                "💥 **500 kills**\n"
                "💀 **1,000 kills**\n"
                "⚔️ **2,500 kills**\n"
                "☠️ **5,000 kills**\n"
                "👑 **10,000 kills**"
            ),
            inline=True,
        )

        # Game Milestones
        embed.add_field(
            name="🎮 Games Played",
            value=(
                "🎮 **10 games**\n"
                "🎯 **50 games**\n"
                "🏆 **100 games**\n"
                "⭐ **250 games**\n"
                "💎 **500 games**\n"
                "👑 **1,000 games**"
            ),
            inline=True,
        )

        # K/D Ratio
        embed.add_field(
            name="📊 K/D Ratio",
            value=(
                "⚖️ **1.0 K/D**\n"
                "📈 **1.5 K/D**\n"
                "🔥 **2.0 K/D**\n"
                "💯 **3.0 K/D**"
            ),
            inline=True,
        )

        # Support & Objectives
        embed.add_field(
            name="🏥 Medic / Revives Given",
            value=(
                "💉 **100 revives**\n"
                "🏥 **1,000 revives**\n"
                "⚕️ **10,000 revives**"
            ),
            inline=True,
        )

        embed.add_field(
            name="♻️ Times Revived",
            value=(
                "🔄 **50 revives**\n"
                "♻️ **500 revives**\n"
                "🔁 **5,000 revives**"
            ),
            inline=True,
        )

        embed.add_field(
            name="🧨 Engineer / Dynamite",
            value=(
                "**Planted:**\n"
                "💣 **50** • 🧨 **500** • 💥 **5,000**\n\n"
                "**Defused:**\n"
                "🛡️ **50** • 🔰 **500** • 🏛️ **5,000**"
            ),
            inline=True,
        )

        embed.add_field(
            name="🎯 Objectives",
            value=(
                "*(Stolen + Returned)*\n\n"
                "🎯 **25 objectives**\n"
                "🏆 **250 objectives**\n"
                "👑 **2,500 objectives**"
            ),
            inline=True,
        )

        embed.add_field(
            name="\u200b",  # Empty field for spacing
            value="\u200b",
            inline=True,
        )

        embed.add_field(
            name="\u200b",  # Empty field for spacing
            value="\u200b",
            inline=True,
        )

        embed.set_footer(
            text="💡 Badges are calculated from your lifetime stats • Use !check_achievements to see your progress"
        )

        await ctx.send(embed=embed)


async def setup(bot):
    """Load the Stats Cog"""
    await bot.add_cog(StatsCog(bot))
    logger.info("✅ Stats Cog loaded (ping, check_achievements, compare, season_info, help_command, badges)")
