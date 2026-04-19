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

import logging
from datetime import datetime

import discord
from discord.ext import commands

from bot.cogs.stats_mixins.compare_mixin import _StatsCompareMixin
from bot.cogs.stats_mixins.help_embeds_mixin import _StatsHelpEmbedsMixin
from bot.core.checks import is_public_channel
from bot.core.database_adapter import ensure_player_name_alias
from bot.core.utils import escape_like_pattern_for_query, sanitize_error_message

logger = logging.getLogger(__name__)


class StatsCog(
    _StatsHelpEmbedsMixin,
    _StatsCompareMixin,
    commands.Cog,
    name="Stats",
):
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
                logger.debug("Failed to set up player_name alias (optional)", exc_info=True)
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
    async def check_achievements_cmd(self, ctx, *, player_name: str | None = None):
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
                logger.debug("Failed to set up player_name alias (optional)", exc_info=True)

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
                logger.debug("Failed to set up player_name alias (optional)", exc_info=True)
            season_filter = self.season_manager.get_season_sql_filter()

            # Season kills leader
            # Note: season_filter is a trusted SQL fragment from SeasonManager, not user input
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
                WHERE s.round_number IN (1, 2)
                  AND (s.round_status IN ('completed', 'substitution') OR s.round_status IS NULL)
                  {season_filter}
                GROUP BY p.player_guid
                HAVING COUNT(DISTINCT p.round_id) > 5
                ORDER BY total_kills DESC
                LIMIT 1
            """  # nosec B608 - season_filter from trusted SeasonManager

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
