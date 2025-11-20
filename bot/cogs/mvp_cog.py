"""
MVP Cog - MVP voting and statistics

This cog handles:
- !mvp_stats - View MVP voting history
- !mvp_leaderboard - See who has the most MVP wins

Commands track community recognition through post-session voting.
"""

import logging
from typing import Optional

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class MVPCog(commands.Cog, name="MVP"):
    """MVP voting and statistics system"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("🏆 MVPCog initializing...")

    async def _ensure_player_name_alias(self):
        """Create temp view/alias for player_name column compatibility"""
        try:
            if self.bot.config.database_type == 'sqlite':
                await self.bot.db_adapter.execute(
                    "CREATE TEMP VIEW IF NOT EXISTS player_comprehensive_stats_alias AS "
                    "SELECT *, player_name AS name FROM player_comprehensive_stats"
                )
        except Exception:
            pass

    async def _resolve_player(self, ctx, player_name: Optional[str] = None):
        """Resolve player from @mention, linked account, or name search"""
        try:
            await self._ensure_player_name_alias()
        except Exception:
            pass

        player_guid = None
        primary_name = None

        # Handle @mention
        if ctx.message.mentions:
            mentioned_user = ctx.message.mentions[0]
            mentioned_id = int(mentioned_user.id)

            link = await self.bot.db_adapter.fetch_one(
                "SELECT et_guid, et_name FROM player_links WHERE discord_id = ?",
                (mentioned_id,),
            )

            if not link:
                await ctx.send(f"❌ {mentioned_user.mention} hasn't linked their account yet!")
                return None

            player_guid = link[0]
            primary_name = link[1]

        # Handle no arguments - use author's linked account
        elif not player_name:
            discord_id = int(ctx.author.id)
            query = """
                SELECT et_guid, et_name FROM player_links WHERE discord_id = $1
            """ if self.bot.config.database_type == 'postgresql' else """
                SELECT et_guid, et_name FROM player_links WHERE discord_id = ?
            """
            link = await self.bot.db_adapter.fetch_one(query, (discord_id,))

            if not link:
                await ctx.send("❌ You haven't linked your account! Use `!link` to get started.")
                return None

            player_guid = link[0]
            primary_name = link[1]

        # Handle name search
        else:
            # Try exact GUID match first
            result = await self.bot.db_adapter.fetch_one(
                "SELECT player_guid, player_name FROM player_comprehensive_stats WHERE player_guid = ? LIMIT 1",
                (player_name,),
            )

            # If not GUID, search by name
            if not result:
                query = """
                    SELECT player_guid, player_name FROM player_comprehensive_stats
                    WHERE player_name ILIKE $1
                    LIMIT 1
                """ if self.bot.config.database_type == 'postgresql' else """
                    SELECT player_guid, player_name FROM player_comprehensive_stats
                    WHERE player_name LIKE ?
                    LIMIT 1
                """
                result = await self.bot.db_adapter.fetch_one(
                    query,
                    (f"%{player_name}%",),
                )

            if not result:
                await ctx.send(f"❌ Player '{player_name}' not found.")
                return None

            player_guid = result[0]
            primary_name = result[1]

        return (player_guid, primary_name)

    @commands.command(name="mvp_stats", aliases=["mvp", "mvps"])
    async def mvp_stats(self, ctx, *, player_name: Optional[str] = None):
        """🏆 View MVP voting history and statistics

        Usage:
        - !mvp_stats              → Your MVP stats (if linked)
        - !mvp_stats playerName   → Search by name
        - !mvp_stats @user        → MVP stats for mentioned user
        """
        try:
            if not hasattr(self.bot, 'mvp_service') or not self.bot.mvp_service:
                await ctx.send("❌ MVP voting system is not enabled.")
                return

            result = await self._resolve_player(ctx, player_name)
            if not result:
                return

            player_guid, primary_name = result

            # Get MVP wins
            mvp_wins = await self.bot.mvp_service.get_mvp_wins(player_guid)

            # Get MVP history
            history = await self.bot.mvp_service.get_mvp_history(player_guid, limit=10)

            if not history and mvp_wins == 0:
                await ctx.send(f"❌ No MVP voting history found for {primary_name}")
                return

            # Build embed
            embed = discord.Embed(
                title=f"🏆 MVP Stats - {primary_name}",
                description=f"Community recognition and MVP achievements",
                color=0xFFD700  # Gold
            )

            # MVP wins
            embed.add_field(
                name="👑 MVP Wins",
                value=f"**{mvp_wins}** session{'' if mvp_wins == 1 else 's'}",
                inline=True
            )

            # Total appearances
            embed.add_field(
                name="📊 Total Nominations",
                value=f"**{len(history)}** session{'' if len(history) == 1 else 's'}",
                inline=True
            )

            # Recent history
            if history:
                history_text = []
                for i, entry in enumerate(history[:5], 1):
                    percentage = (entry['vote_count'] / entry['total_votes'] * 100) if entry['total_votes'] > 0 else 0
                    is_winner = entry['vote_count'] > 0  # Simplified, should check if highest
                    medal = "🏆" if is_winner and percentage > 50 else "🥈"
                    history_text.append(
                        f"{medal} {entry['vote_count']}/{entry['total_votes']} votes ({percentage:.1f}%)"
                    )

                embed.add_field(
                    name="📜 Recent Sessions",
                    value="\n".join(history_text) if history_text else "No recent sessions",
                    inline=False
                )

            embed.set_footer(text="💡 MVPs are voted by the community after each session")
            embed.timestamp = discord.utils.utcnow()

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in mvp_stats command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving MVP stats: {e}")

    @commands.command(name="mvp_leaderboard", aliases=["mvp_lb", "mvp_top"])
    async def mvp_leaderboard(self, ctx):
        """🏆 View the MVP wins leaderboard

        Shows players with the most session MVP wins.
        """
        try:
            if not hasattr(self.bot, 'mvp_service') or not self.bot.mvp_service:
                await ctx.send("❌ MVP voting system is not enabled.")
                return

            # Get top MVP winners
            query = """
                SELECT
                    player_guid,
                    player_name,
                    COUNT(*) as mvp_wins
                FROM mvp_votes
                WHERE vote_count = (
                    SELECT MAX(vote_count)
                    FROM mvp_votes m2
                    WHERE m2.session_id = mvp_votes.session_id
                )
                GROUP BY player_guid, player_name
                ORDER BY mvp_wins DESC
                LIMIT 10
            """

            results = await self.bot.db_adapter.fetch_all(query)

            if not results:
                await ctx.send("❌ No MVP voting data available yet.")
                return

            # Build embed
            embed = discord.Embed(
                title="🏆 MVP Leaderboard",
                description="Players with the most session MVP wins",
                color=0xFFD700
            )

            # Leaderboard
            leaderboard_text = []
            for i, (guid, name, wins) in enumerate(results, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                leaderboard_text.append(
                    f"{medal} **{name}** - {wins} MVP{'' if wins == 1 else 's'}"
                )

            embed.add_field(
                name="👑 Top MVPs",
                value="\n".join(leaderboard_text),
                inline=False
            )

            embed.set_footer(text="💡 MVPs are voted by the community")
            embed.timestamp = discord.utils.utcnow()

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in mvp_leaderboard command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving MVP leaderboard: {e}")


async def setup(bot):
    """Load the MVPCog"""
    await bot.add_cog(MVPCog(bot))
