"""StatsCog mixin: !compare command (radar chart + detailed stats comparison).

Extracted from bot/cogs/stats_cog.py in Mega Audit v4 / Sprint 2.

All methods live on StatsCog via mixin inheritance.
"""
from __future__ import annotations

import logging
from datetime import datetime

import discord
from discord.ext import commands

from bot.core.checks import is_public_channel
from bot.core.database_adapter import ensure_player_name_alias
from bot.core.utils import escape_like_pattern_for_query, sanitize_error_message
from bot.stats import StatsCalculator

logger = logging.getLogger("bot.cogs.stats")


class _StatsCompareMixin:
    """!compare command (radar chart + detailed stats comparison) for StatsCog."""

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
                from pathlib import Path

                import matplotlib.pyplot as plt
                import numpy as np
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
                logger.debug("Failed to set up player_name alias (optional)", exc_info=True)

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
                logger.debug("Failed to clean up comparison chart file", exc_info=True)

            logger.info(
                f"📊 Comparison generated: {p1_stats['name']} vs {p2_stats['name']}"
            )

        except Exception as e:
            logger.error(f"Error in compare command: {e}", exc_info=True)
            await ctx.send(f"❌ Error generating comparison: {sanitize_error_message(e)}")
