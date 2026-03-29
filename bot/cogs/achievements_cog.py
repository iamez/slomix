"""
Achievements Cog - Achievement Badge Documentation
==================================================
Provides help and information about achievement badges.

Commands:
- !achievements - Show all achievement categories
- !achievements medals - Show full badge legend with descriptions
"""

import logging
from datetime import datetime

import discord
from discord.ext import commands

from bot.core.checks import is_public_channel

logger = logging.getLogger("bot.cogs.achievements")


class AchievementsCog(commands.Cog, name="Achievements"):
    """🏆 Achievement badge information and help"""

    def __init__(self, bot):
        """Initialize the Achievements Cog"""
        self.bot = bot
        logger.info("🏆 AchievementsCog loaded")

    @is_public_channel()
    @commands.command(name="achievements", aliases=["medals", "achievement"])
    async def achievements(self, ctx, subcommand: str = None):
        """
        🏆 View achievement badge information

        Usage:
            !achievements         → Show achievement categories overview
            !achievements medals  → Show complete badge legend
            !achievements help    → Same as medals

        Badges appear after player names in !last_session and represent lifetime achievements.
        Every achievement now has a unique emoji - no more stacking!
        """
        if subcommand and subcommand.lower() in ("medals", "help", "legend", "list"):
            await self._show_medals_legend(ctx)
        else:
            await self._show_overview(ctx)

    async def _show_overview(self, ctx):
        """Show achievement categories overview"""
        embed = discord.Embed(
            title="🏆 Achievement System",
            description=(
                "Earn badges for lifetime achievements! Badges appear after your name in !last_session.\n\n"
                "**Unique Badges:** Every achievement now has its own unique emoji - "
                "no more stacking confusion!"
            ),
            color=0xFFD700,  # Gold
            timestamp=datetime.now()
        )

        # Core Achievements
        embed.add_field(
            name="⚔️ Combat Achievements",
            value=(
                "🎯💀☠️👑 **Kills** - Total enemy kills (1K-20K)\n"
                "🎮🕹️🏆⭐💎 **Games** - Rounds played (50-30K)\n"
                "⚰️⚖️📈🔥⚡💯 **K/D Ratio** - Kill/Death ratio (0.0 to 3.0)"
            ),
            inline=False
        )

        # Support Achievements
        embed.add_field(
            name="💉 Support Achievements",
            value=(
                "💉🏥⚕️ **Medic** - Teammates revived (100-5K)\n"
                "🔄♻️🔁 **Survivor** - Times you were revived (100-3K)\n"
                "💣🧨💥 **Demolition** - Dynamites planted (50-1K)\n"
                "🛡️🔰🏛️ **Defuser** - Dynamites defused (50-1K)"
            ),
            inline=False
        )

        # Objective Achievements
        embed.add_field(
            name="🎯 Objective Achievements",
            value=(
                "🎯🏆👑 **Objectives** - Objectives stolen + returned combined"
            ),
            inline=False
        )

        embed.add_field(
            name="💡 View Full Legend",
            value="Use `!achievements medals` to see all badges with exact thresholds",
            inline=False
        )

        embed.set_footer(text="🎮 Keep playing to unlock more badges!")
        await ctx.send(embed=embed)

    async def _show_medals_legend(self, ctx):
        """Show complete medal legend with thresholds"""
        # Create multiple embeds for better organization
        embeds = []

        # Embed 1: Combat Achievements
        embed1 = discord.Embed(
            title="⚔️ Combat Achievements",
            description="Earn these badges through kills, games played, and K/D ratio",
            color=0xE74C3C,  # Red
            timestamp=datetime.now()
        )

        embed1.add_field(
            name="💀 Kill Milestones",
            value=(
                "🎯 **First Blood Century** - 100 kills\n"
                "💥 **Killing Machine** - 500 kills\n"
                "💀 **Thousand Killer** - 1,000 kills\n"
                "⚔️ **Elite Warrior** - 2,500 kills\n"
                "☠️ **Death Incarnate** - 5,000 kills\n"
                "👑 **Legendary Slayer** - 10,000 kills"
            ),
            inline=False
        )

        embed1.add_field(
            name="🎮 Game Milestones",
            value=(
                "🎮 **Getting Started** - 10 games\n"
                "🎯 **Regular Player** - 50 games\n"
                "🏆 **Dedicated Gamer** - 100 games\n"
                "⭐ **Community Veteran** - 250 games\n"
                "💎 **Hardcore Legend** - 500 games\n"
                "👑 **Ultimate Champion** - 1,000 games"
            ),
            inline=False
        )

        embed1.add_field(
            name="📊 K/D Ratio Milestones",
            value=(
                "⚰️ **Ground Zero** - 0.0 K/D (no kills yet)\n"
                "⚖️ **Balanced Fighter** - 1.0 K/D (requires 20+ games)\n"
                "📈 **Above Average** - 1.5 K/D\n"
                "🔥 **Elite Killer** - 2.0 K/D\n"
                "⚡ **Dominator** - 2.5 K/D\n"
                "💯 **God Tier** - 3.0 K/D (nearly impossible)\n\n"
                "*Calculated: Total Kills ÷ Total Deaths*"
            ),
            inline=False
        )

        embeds.append(embed1)

        # Embed 2: Support Achievements
        embed2 = discord.Embed(
            title="💉 Support & Objective Achievements",
            description="Earn these through teamwork and objective play",
            color=0x57F287,  # Green
            timestamp=datetime.now()
        )

        embed2.add_field(
            name="💉 Medic Achievements",
            value=(
                "💉 **Field Medic** - 100 revives given\n"
                "🏥 **Combat Surgeon** - 500 revives given\n"
                "⚕️ **Miracle Worker** - 5,000 revives given\n\n"
                "*Tracks teammates you successfully revived*"
            ),
            inline=False
        )

        embed2.add_field(
            name="🔄 Survivor Achievements",
            value=(
                "🔄 **Lucky One** - 100 times revived\n"
                "♻️ **Frequent Visitor** - 500 times revived\n"
                "🔁 **Immortal** - 3,000 times revived\n\n"
                "*Tracks how many times teammates revived you*"
            ),
            inline=False
        )

        embed2.add_field(
            name="💣 Demolition Achievements",
            value=(
                "💣 **Demolitions Expert** - 50 dynamites planted\n"
                "🧨 **Explosive Artist** - 200 dynamites planted\n"
                "💥 **Master Demolitionist** - 1,000 dynamites planted"
            ),
            inline=False
        )

        embed2.add_field(
            name="🛡️ Defuser Achievements",
            value=(
                "🛡️ **Bomb Squad** - 50 dynamites defused\n"
                "🔰 **Elite Defuser** - 200 dynamites defused\n"
                "🏛️ **Fortress Guardian** - 1,000 dynamites defused"
            ),
            inline=False
        )

        embed2.add_field(
            name="🚩 Objective Achievements",
            value=(
                "🚩 **Objective Hunter** - 25 objectives\n"
                "🎖️ **Mission Specialist** - 250 objectives\n"
                "🏅 **Objective Master** - 2,500 objectives\n\n"
                "*Combines objectives stolen + objectives returned*"
            ),
            inline=False
        )

        embeds.append(embed2)

        # Embed 3: How It Works
        embed3 = discord.Embed(
            title="❓ How Achievement Badges Work",
            description="Everything you need to know about earning and displaying badges",
            color=0x5865F2,  # Discord Blurple
            timestamp=datetime.now()
        )

        embed3.add_field(
            name="📍 Where Badges Appear",
            value=(
                "Badges display after your name in `!last_session`:\n"
                "```\n"
                "🥇 **YourName** 💀🏆📈💉\n"
                "   25K/10D/5G (2.50) • 450 DPM • ...\n"
                "```"
            ),
            inline=False
        )

        embed3.add_field(
            name="📚 No Badge Stacking",
            value=(
                "Each badge emoji is unique! Every achievement has its own distinct badge.\n\n"
                "**Examples:**\n"
                "• 🎯 = Only Kills (1K)\n"
                "• 🎮 = Only Games (50)\n"
                "• 🚩 = Only Objectives (25)\n"
                "• 👑 = Only Kills (20K)\n\n"
                "No more confusion about what a badge means!"
            ),
            inline=False
        )

        embed3.add_field(
            name="🔢 How Stats Are Calculated",
            value=(
                "**Lifetime Stats** - All achievements track your ALL-TIME stats\n"
                "**Filtered Rounds** - Only counts R1 & R2 (completed/substitution)\n"
                "**No Warmup** - R0 warmup rounds are excluded\n\n"
                "Check your progress: `!stats` or `!mystats`"
            ),
            inline=False
        )

        embed3.add_field(
            name="🚀 Coming Soon (Phase 2)",
            value=(
                "• 🏅 **Record Holders** - Most kills in a round/map/month/year\n"
                "• 🎯 **Weapon Mastery** - MP40/Thompson accuracy achievements\n"
                "• ⚡ **DPM Records** - Damage per minute milestones"
            ),
            inline=False
        )

        embed3.set_footer(text="🏆 Keep grinding to earn them all!")
        embeds.append(embed3)

        # Send all embeds
        for embed in embeds:
            await ctx.send(embed=embed)


async def setup(bot):
    """Load the Achievements Cog"""
    await bot.add_cog(AchievementsCog(bot))
