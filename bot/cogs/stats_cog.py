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

logger = logging.getLogger(__name__)


class StatsCog(commands.Cog, name="Stats"):
    """General statistics, player comparisons, achievements, and season info"""

    def __init__(self, bot):
        self.bot = bot
        self.stats_cache = bot.stats_cache
        self.season_manager = bot.season_manager
        self.achievements = bot.achievements
        logger.info("📊 StatsCog initializing...")

    async def _ensure_player_name_alias(self):
        """Create temp view/alias for player_name column compatibility"""
        try:
            # Only create alias for SQLite (PostgreSQL will have proper schema)
            if self.bot.config.database_type == 'sqlite':
                await self.bot.db_adapter.execute(
                    "CREATE TEMP VIEW IF NOT EXISTS player_comprehensive_stats_alias AS "
                    "SELECT *, player_name AS name FROM player_comprehensive_stats"
                )
        except Exception:
            pass

    @commands.command(name="ping")
    async def ping(self, ctx):
        """🏓 Check bot status and performance"""
        try:
            import time
            start_time = time.time()

            # Test database connection
            # Apply runtime alias to avoid schema mismatch errors
            try:
                await self._ensure_player_name_alias()
            except Exception:
                pass
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
            await ctx.send(f"❌ Bot error: {e}")

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
                await self._ensure_player_name_alias()
            except Exception:
                pass
            
            # Handle @mention
            if ctx.message.mentions:
                mentioned_user = ctx.message.mentions[0]
                mentioned_id = str(mentioned_user.id)

                link = await self.bot.db_adapter.fetch_one(
                    "SELECT et_guid, et_name FROM player_links WHERE discord_id = ?",
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
                    f"SELECT et_guid, et_name FROM player_links WHERE discord_id = {placeholder}",
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
                result = await self.bot.db_adapter.fetch_one(
                    "SELECT guid, alias FROM player_aliases WHERE LOWER(alias) LIKE LOWER(?) ORDER BY last_seen DESC LIMIT 1",
                    (f"%{player_name}%",),
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
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths,
                    COUNT(DISTINCT round_id) as total_games,
                    CASE 
                        WHEN SUM(deaths) > 0 
                        THEN CAST(SUM(kills) AS REAL) / SUM(deaths)
                        ELSE SUM(kills) 
                    END as overall_kd
                FROM player_comprehensive_stats
                WHERE player_guid = ?
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

            # Ensure player_name alias for this command's DB connection
            try:
                await self._ensure_player_name_alias()
            except Exception:
                pass

            # Helper: get stats when we already have a GUID
            async def get_player_stats_by_guid(player_guid, display_name):
                # Get comprehensive stats
                stats = await self.bot.db_adapter.fetch_one(
                    """
                    SELECT 
                        SUM(kills) as total_kills,
                        SUM(deaths) as total_deaths,
                        COUNT(DISTINCT round_id) as total_games,
                        SUM(damage_given) as total_damage,
                        SUM(time_played_seconds) as total_time,
                        SUM(headshot_kills) as total_headshots
                    FROM player_comprehensive_stats
                    WHERE player_guid = ?
                """,
                    (player_guid,),
                )

                if not stats or stats[0] is None:
                    return None

                kills, deaths, games, damage, time_sec, headshots = stats

                # Get weapon stats for accuracy
                weapon_stats = await self.bot.db_adapter.fetch_one(
                    """
                    SELECT 
                        SUM(hits) as total_hits,
                        SUM(shots) as total_shots
                    FROM weapon_comprehensive_stats
                    WHERE player_guid = ?
                """,
                    (player_guid,),
                )

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
                    link = await self.bot.db_adapter.fetch_one(
                        "SELECT et_guid, et_name FROM player_links WHERE discord_id = ?",
                        (discord_id,),
                    )

                    if link:
                        return await get_player_stats_by_guid(link[0], link[1])

                # Try player_aliases first (name search)
                result = await self.bot.db_adapter.fetch_one(
                    "SELECT guid, alias FROM player_aliases WHERE LOWER(alias) LIKE LOWER(?) ORDER BY last_seen DESC LIMIT 1",
                    (f"%{player_name}%",),
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
            # Apply per-connection alias to handle legacy DB column names
            try:
                await self._ensure_player_name_alias()
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
                    COUNT(DISTINCT p.round_id) as games
                FROM player_comprehensive_stats p
                JOIN rounds s ON p.round_id = s.id
                WHERE 1=1 {season_filter}
                GROUP BY p.player_guid
                HAVING games > 5
                ORDER BY total_kills DESC
                LIMIT 1
            """

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
            await ctx.send(f"❌ Error retrieving season information: {e}")

    @commands.command(name="help_command", aliases=["commands"])
    async def help_command(self, ctx):
        """📚 Show all available commands with examples"""
        
        # Main Commands Embed
        embed1 = discord.Embed(
            title="🚀 Ultimate ET:Legacy Bot - Command Reference",
            description="**Use `!` prefix for all commands** | 📖 Full examples below",
            color=0x0099FF,
        )

        embed1.add_field(
            name="📊 **Session Commands**",
            value=(
                "• `!last_session` - View latest gaming session with full stats\n"
                "• `!session <date>` - View specific date session\n"
                "  └ Example: `!session 2025-11-02`\n"
                "• `!sessions` - List all recent gaming sessions\n"
                "  └ Aliases: `!rounds`, `!list_sessions`, `!ls`\n"
                "  └ Example: `!sessions 10` (filter by October)"
            ),
            inline=False,
        )

        embed1.add_field(
            name="🎯 **Player Stats**",
            value=(
                "• `!stats <player>` - Individual player statistics\n"
                "  └ Example: `!stats carniee`\n"
                "• `!leaderboard [type]` - Top players by kills/accuracy/etc\n"
                "• `!list_players` - Show all registered players\n"
                "• `!compare <player1> <player2>` - Compare two players"
            ),
            inline=False,
        )

        embed1.add_field(
            name="👥 **Team Commands**",
            value=(
                "• `!teams [date]` - Show team rosters\n"
                "• `!session_score [date]` - Team scores & map breakdown\n"
                "• `!lineup_changes [current] [previous]` - Who switched teams\n"
                "• `!set_team_names <date> <team_a> <team_b>` - Custom names"
            ),
            inline=False,
        )

        embed1.add_field(
            name="🏆 **Achievements & Season**",
            value=(
                "• `!check_achievements [player]` - View achievements\n"
                "• `!season_info` - Current season statistics"
            ),
            inline=False,
        )

        embed1.add_field(
            name="🔧 **System Commands**",
            value=(
                "• `!ping` - Check bot status & latency\n"
                "• `!help` - Show this help menu"
            ),
            inline=False,
        )

        # Examples & Tips Embed
        embed2 = discord.Embed(
            title="💡 Command Examples & Pro Tips",
            color=0x00FF00,
        )

        embed2.add_field(
            name="📅 **Session Viewing**",
            value=(
                "```\n"
                "!last_session              → Latest session (6 graphs!)\n"
                "!session 2025-11-02        → Specific date\n"
                "!sessions                  → List all sessions\n"
                "!sessions 10               → October sessions only\n"
                "!sessions october          → Same as above\n"
                "```"
            ),
            inline=False,
        )

        embed2.add_field(
            name="🎯 **Player Stats**",
            value=(
                "```\n"
                "!stats carniee             → Full player stats\n"
                "!leaderboard               → Top 10 by kills\n"
                "!compare carniee superboyy → Head-to-head\n"
                "!list_players              → All 45+ players\n"
                "```"
            ),
            inline=False,
        )

        embed2.add_field(
            name="👥 **Team Analysis**",
            value=(
                "```\n"
                "!teams                     → Latest session teams\n"
                "!session_score             → Team scores + maps\n"
                "!lineup_changes            → Who switched sides\n"
                "!lineup_changes 2025-11-02 → Compare with date\n"
                "```"
            ),
            inline=False,
        )

        embed2.add_field(
            name="🔥 **Pro Tips**",
            value=(
                "• **`!last_session`** shows 6 graphs:\n"
                "  └ Player scores, K/D, Accuracy, Team KPD, Weapon usage, Headshots\n"
                "• **Date format**: Always use `YYYY-MM-DD` (e.g., `2025-11-02`)\n"
                "• **Player names**: Case-insensitive (`carniee` = `CARNIEE`)\n"
                "• **Month filters**: Use numbers (`10`) or names (`october`, `oct`)\n"
                "• **Aliases**: Many commands have shortcuts (e.g., `!ls` = `!sessions`)"
            ),
            inline=False,
        )

        embed2.set_footer(
            text="💬 Questions? Ask in #bot-commands | 🐛 Report issues to admins"
        )

        # Send both embeds
        await ctx.send(embed=embed1)
        await ctx.send(embed=embed2)


async def setup(bot):
    """Load the Stats Cog"""
    await bot.add_cog(StatsCog(bot))
    logger.info("✅ Stats Cog loaded (ping, check_achievements, compare, season_info, help_command)")
