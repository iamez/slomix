"""
Matchup Analytics Cog

Discord commands for querying matchup statistics between player lineups.

Commands:
- !matchup <player1> <player2> ... vs <player3> <player4> ...
- !synergy <player1> <player2>
- !nemesis <player>
"""

import logging
from typing import List

import discord
from discord.ext import commands

from bot.core.checks import is_public_channel
from bot.core.utils import sanitize_error_message
from bot.services.matchup_analytics_service import MatchupAnalyticsService

logger = logging.getLogger("bot.cogs.matchup")


class MatchupCog(commands.Cog):
    """Matchup analytics commands for lineup vs lineup statistics."""

    def __init__(self, bot):
        self.bot = bot
        self.matchup_service = MatchupAnalyticsService(bot.db_adapter)
        logger.info("MatchupCog initialized")

    async def _resolve_player_guids(self, player_names: List[str]) -> List[str]:
        """
        Resolve player names to GUIDs.

        Args:
            player_names: List of player names

        Returns:
            List of player GUIDs
        """
        guids = []
        for name in player_names:
            # Try exact match first
            query = """
                SELECT player_guid
                FROM player_comprehensive_stats
                WHERE LOWER(player_name) = LOWER($1)
                GROUP BY player_guid
                ORDER BY MAX(round_date) DESC
                LIMIT 1
            """
            result = await self.bot.db_adapter.fetch_one(query, (name,))

            if result:
                guids.append(result[0])
            else:
                # Try partial match
                query = """
                    SELECT player_guid
                    FROM player_comprehensive_stats
                    WHERE LOWER(player_name) LIKE LOWER($1)
                    GROUP BY player_guid
                    ORDER BY MAX(round_date) DESC
                    LIMIT 1
                """
                result = await self.bot.db_adapter.fetch_one(query, (f"%{name}%",))
                if result:
                    guids.append(result[0])
                else:
                    logger.warning(f"Could not resolve player: {name}")

        return guids

    async def _get_player_name(self, guid: str) -> str:
        """Get the most recent name for a player GUID."""
        query = """
            SELECT player_name FROM player_comprehensive_stats
            WHERE player_guid = $1
            ORDER BY round_date DESC
            LIMIT 1
        """
        result = await self.bot.db_adapter.fetch_one(query, (guid,))
        return result[0] if result else guid[:8]

    @commands.command(name="matchup", aliases=["vs", "headtohead"])
    @is_public_channel()
    async def matchup_command(self, ctx, *, args: str = None):
        """
        Show matchup statistics between two lineups.

        Usage:
        !matchup player1, player2, player3 vs player4, player5, player6
        !matchup player1 player2 vs player3 player4

        Examples:
        !matchup puran, sWat, olympus vs noob, pro, legend
        !matchup puran sWat vs noob pro
        """
        if not args or 'vs' not in args.lower():
            await ctx.send(
                "**Usage:** `!matchup player1, player2 vs player3, player4`\n"
                "**Example:** `!matchup puran, sWat vs noob, pro`"
            )
            return

        # Parse lineups
        parts = args.lower().split(' vs ')
        if len(parts) != 2:
            await ctx.send("Please separate teams with 'vs' (e.g., `player1, player2 vs player3, player4`)")
            return

        # Parse player names (comma or space separated)
        def parse_players(text):
            if ',' in text:
                return [p.strip() for p in text.split(',') if p.strip()]
            else:
                return [p.strip() for p in text.split() if p.strip()]

        lineup_a_names = parse_players(parts[0])
        lineup_b_names = parse_players(parts[1])

        if not lineup_a_names or not lineup_b_names:
            await ctx.send("Please provide at least one player on each side")
            return

        # Resolve names to GUIDs
        async with ctx.typing():
            try:
                lineup_a_guids = await self._resolve_player_guids(lineup_a_names)
                lineup_b_guids = await self._resolve_player_guids(lineup_b_names)

                if len(lineup_a_guids) < len(lineup_a_names):
                    missing = len(lineup_a_names) - len(lineup_a_guids)
                    await ctx.send(f"Could not find {missing} player(s) from lineup A")
                    return

                if len(lineup_b_guids) < len(lineup_b_names):
                    missing = len(lineup_b_names) - len(lineup_b_guids)
                    await ctx.send(f"Could not find {missing} player(s) from lineup B")
                    return

                # Get matchup stats
                stats = await self.matchup_service.get_matchup_stats(
                    lineup_a_guids, lineup_b_guids
                )

                if not stats:
                    await ctx.send(
                        f"No matchup history found between these lineups.\n"
                        f"Lineup A: {', '.join(lineup_a_names)}\n"
                        f"Lineup B: {', '.join(lineup_b_names)}"
                    )
                    return

                # Format and send
                summary = self.matchup_service.format_matchup_summary(stats, perspective='a')
            except Exception as e:
                logger.error(f"Error in matchup command: {e}", exc_info=True)
                await ctx.send(f"Error analyzing matchup: {sanitize_error_message(e)}")
                return

            embed = discord.Embed(
                title="Matchup Statistics",
                description=summary,
                color=discord.Color.blue(),
            )

            # Add map breakdown if available
            if stats.map_stats:
                map_lines = []
                for map_name, map_data in stats.map_stats.items():
                    winrate = map_data['a_wins'] / map_data['matches'] * 100 if map_data['matches'] > 0 else 0
                    map_lines.append(f"`{map_name}`: {map_data['matches']} matches, {winrate:.0f}% WR")

                if map_lines:
                    embed.add_field(
                        name="Map Breakdown",
                        value='\n'.join(map_lines[:5]),  # Limit to 5 maps
                        inline=False
                    )

            await ctx.send(embed=embed)

    @commands.command(name="duo_perf", aliases=["duoperf", "pair_stats"])
    @is_public_channel()
    async def synergy_command(self, ctx, player1: str = None, player2: str = None):
        """
        Show performance stats when two players are on the same team.

        Usage: !duo_perf <player1> <player2>
        Example: !duo_perf puran sWat

        Note: For chemistry/synergy analysis, use !synergy from SynergyAnalytics.
        """
        if not player1 or not player2:
            await ctx.send("**Usage:** `!duo_perf player1 player2`\n**Example:** `!duo_perf puran sWat`")
            return

        async with ctx.typing():
            try:
                # Resolve to GUIDs
                guids = await self._resolve_player_guids([player1, player2])

                if len(guids) < 2:
                    await ctx.send(f"Could not find one or both players: {player1}, {player2}")
                    return

                # Get synergy stats
                synergy = await self.matchup_service.get_player_synergy(guids[0], guids[1])

                if not synergy:
                    await ctx.send(f"Not enough data for synergy between {player1} and {player2}")
                    return

                # Get player names
                name1 = await self._get_player_name(guids[0])
                name2 = await self._get_player_name(guids[1])

                # Format and send
                summary = self.matchup_service.format_synergy_summary(synergy, name1, name2)
            except Exception as e:
                logger.error(f"Error in synergy command: {e}", exc_info=True)
                await ctx.send(f"Error analyzing synergy: {sanitize_error_message(e)}")
                return

            # Color based on synergy
            if synergy['synergy_percent'] > 10:
                color = discord.Color.green()
                emoji = "🔥"
            elif synergy['synergy_percent'] < -10:
                color = discord.Color.red()
                emoji = "📉"
            else:
                color = discord.Color.gold()
                emoji = "➖"

            embed = discord.Embed(
                title=f"{emoji} Player Synergy",
                description=summary,
                color=color,
            )

            await ctx.send(embed=embed)

    @commands.command(name="nemesis", aliases=["counter"])
    @is_public_channel()
    async def nemesis_command(self, ctx, player: str = None):
        """
        Show which opponents suppress a player's performance.

        Usage: !nemesis <player>
        Example: !nemesis puran
        """
        if not player:
            await ctx.send("**Usage:** `!nemesis player`\n**Example:** `!nemesis puran`")
            return

        async with ctx.typing():
            try:
                guids = await self._resolve_player_guids([player])

                if not guids:
                    await ctx.send(f"Could not find player: {player}")
                    return

                player_guid = guids[0]
                player_name = await self._get_player_name(player_guid)

                # Get all unique opponents from matchup history
                query = """
                    SELECT DISTINCT opponent_guid
                    FROM (
                        SELECT jsonb_array_elements_text(lineup_b_guids) AS opponent_guid
                        FROM matchup_history
                        WHERE lineup_a_guids::text LIKE $1
                        UNION
                        SELECT jsonb_array_elements_text(lineup_a_guids) AS opponent_guid
                        FROM matchup_history
                        WHERE lineup_b_guids::text LIKE $1
                    ) sub
                """
                rows = await self.bot.db_adapter.fetch_all(query, (f'%{player_guid}%',))

                if not rows:
                    await ctx.send(f"No matchup history found for {player_name}")
                    return

                # Check anti-synergy with each opponent
                nemeses = []
                for row in rows:
                    opponent_guid = row[0]
                    if not opponent_guid or opponent_guid == player_guid:
                        continue

                    anti_syn = await self.matchup_service.get_player_anti_synergy(
                        player_guid, opponent_guid
                    )

                    if anti_syn and anti_syn['matches_versus'] >= 3:
                        opponent_name = await self._get_player_name(opponent_guid)
                        nemeses.append({
                            'name': opponent_name,
                            'suppression': anti_syn['suppression_percent'],
                            'matches': anti_syn['matches_versus']
                        })

                if not nemeses:
                    await ctx.send(f"Not enough data to determine nemeses for {player_name}")
                    return

                # Sort by suppression (most negative = biggest nemesis)
                nemeses.sort(key=lambda x: x['suppression'])
            except Exception as e:
                logger.error(f"Error in nemesis command: {e}", exc_info=True)
                await ctx.send(f"Error analyzing nemesis: {sanitize_error_message(e)}")
                return

            # Format output
            lines = [f"**{player_name}'s Performance vs Opponents**\n"]

            # Nemeses (negative impact)
            worst = [n for n in nemeses if n['suppression'] < -5][:3]
            if worst:
                lines.append("**Nemeses** (underperforms against):")
                for n in worst:
                    lines.append(f"• {n['name']}: {n['suppression']:.0f}% ({n['matches']} matches)")

            # Easy matchups (positive impact)
            best = [n for n in nemeses if n['suppression'] > 5]
            best.sort(key=lambda x: x['suppression'], reverse=True)
            best = best[:3]
            if best:
                lines.append("\n**Favorable Matchups** (overperforms against):")
                for n in best:
                    lines.append(f"• {n['name']}: +{n['suppression']:.0f}% ({n['matches']} matches)")

            embed = discord.Embed(
                title="Nemesis Analysis",
                description='\n'.join(lines),
                color=discord.Color.purple(),
            )

            await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(MatchupCog(bot))
