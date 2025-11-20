"""
Title Cog - Player titles and badges

This cog handles:
- !titles - View unlocked titles
- !title equip <title> - Equip a title
- !title check - Check for new title unlocks
- !all_titles - View all available titles

Commands allow players to unlock and display achievement-based titles.
"""

import logging
from typing import Optional

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class TitleCog(commands.Cog, name="Titles"):
    """Player title and badge system"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("🎖️ TitleCog initializing...")

    async def _resolve_player(self, ctx, player_name: Optional[str] = None):
        """Resolve player from @mention, linked account, or name search"""
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

    @commands.group(name="title", aliases=["titles"], invoke_without_command=True)
    async def title(self, ctx, *, player_name: Optional[str] = None):
        """🎖️ View unlocked titles

        Usage:
        - !titles              → Your titles (if linked)
        - !titles playerName   → View someone's titles
        - !titles @user        → View mentioned user's titles
        - !title equip <id>    → Equip a title
        - !title check         → Check for new unlocks
        """
        try:
            if not hasattr(self.bot, 'title_system') or not self.bot.title_system:
                await ctx.send("❌ Title system is not enabled.")
                return

            result = await self._resolve_player(ctx, player_name)
            if not result:
                return

            player_guid, primary_name = result

            # Get unlocked titles
            unlocked = await self.bot.title_system.get_unlocked_titles(player_guid)

            if not unlocked:
                await ctx.send(
                    f"❌ No titles unlocked yet for {primary_name}!\n"
                    f"Use `!title check` to see which titles you can unlock."
                )
                return

            # Build embed
            embed = discord.Embed(
                title=f"🎖️ Titles - {primary_name}",
                description=f"{len(unlocked)} title{'' if len(unlocked) == 1 else 's'} unlocked",
                color=0x9B59B6  # Purple
            )

            # Show equipped title
            equipped = next((t for t in unlocked if t['is_equipped']), None)
            if equipped:
                embed.add_field(
                    name="⭐ Currently Equipped",
                    value=f"**{equipped['title']}**\n*{equipped['description']}*",
                    inline=False
                )

            # Show all unlocked titles
            titles_text = []
            for title in unlocked:
                status = "✅" if title['is_equipped'] else "📦"
                titles_text.append(
                    f"{status} **{title['title']}** `{title['id']}`\n"
                    f"└ {title['description']}"
                )

            if titles_text:
                # Split into chunks if too long
                chunk_size = 5
                for i in range(0, len(titles_text), chunk_size):
                    chunk = titles_text[i:i+chunk_size]
                    embed.add_field(
                        name=f"🎖️ Unlocked Titles ({i+1}-{min(i+chunk_size, len(titles_text))})",
                        value="\n\n".join(chunk),
                        inline=False
                    )

            embed.set_footer(text="💡 Use !title equip <id> to equip a title")
            embed.timestamp = discord.utils.utcnow()

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in title command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving titles: {e}")

    @title.command(name="equip")
    async def title_equip(self, ctx, title_id: str):
        """Equip a title

        Usage: !title equip <title_id>
        Example: !title equip sharpshooter
        """
        try:
            if not hasattr(self.bot, 'title_system') or not self.bot.title_system:
                await ctx.send("❌ Title system is not enabled.")
                return

            result = await self._resolve_player(ctx, None)  # Only for self
            if not result:
                return

            player_guid, primary_name = result

            # Check if title exists
            if title_id not in self.bot.title_system.TITLES:
                await ctx.send(f"❌ Title '{title_id}' doesn't exist. Use `!all_titles` to see available titles.")
                return

            # Check if player has unlocked the title
            unlocked = await self.bot.title_system.get_unlocked_titles(player_guid)
            if not any(t['id'] == title_id for t in unlocked):
                await ctx.send(f"❌ You haven't unlocked the '{title_id}' title yet!")
                return

            # Equip the title
            success = await self.bot.title_system.equip_title(player_guid, title_id)

            if success:
                title_name = self.bot.title_system.TITLES[title_id]['title']
                await ctx.send(f"✅ Equipped title: **{title_name}**")
            else:
                await ctx.send("❌ Failed to equip title.")

        except Exception as e:
            logger.error(f"Error equipping title: {e}", exc_info=True)
            await ctx.send(f"❌ Error equipping title: {e}")

    @title.command(name="check")
    async def title_check(self, ctx):
        """Check for new title unlocks

        Usage: !title check
        """
        try:
            if not hasattr(self.bot, 'title_system') or not self.bot.title_system:
                await ctx.send("❌ Title system is not enabled.")
                return

            result = await self._resolve_player(ctx, None)  # Only for self
            if not result:
                return

            player_guid, primary_name = result

            # Check for new unlocks
            await ctx.send("🔍 Checking for new title unlocks...")
            newly_unlocked = await self.bot.title_system.check_and_unlock_titles(player_guid)

            if newly_unlocked:
                # Build embed for new unlocks
                embed = discord.Embed(
                    title="🎉 New Titles Unlocked!",
                    description=f"Congratulations, **{primary_name}**!",
                    color=0xFFD700  # Gold
                )

                for title_id in newly_unlocked:
                    title_info = self.bot.title_system.TITLES[title_id]
                    embed.add_field(
                        name=f"✨ {title_info['title']}",
                        value=title_info['description'],
                        inline=False
                    )

                embed.set_footer(text="💡 Use !title equip <id> to equip a title")
                await ctx.send(embed=embed)
            else:
                await ctx.send("✅ No new titles unlocked. Keep playing to unlock more!")

        except Exception as e:
            logger.error(f"Error checking titles: {e}", exc_info=True)
            await ctx.send(f"❌ Error checking titles: {e}")

    @commands.command(name="all_titles", aliases=["title_list", "available_titles"])
    async def all_titles(self, ctx):
        """📜 View all available titles and requirements

        Shows every title that can be unlocked and how to unlock them.
        """
        try:
            if not hasattr(self.bot, 'title_system') or not self.bot.title_system:
                await ctx.send("❌ Title system is not enabled.")
                return

            # Group titles by category
            categories = {
                'Combat': ['sharpshooter', 'fragger', 'god_mode', 'deadeye'],
                'Support': ['medic', 'guardian'],
                'Objectives': ['objective_runner', 'mission_master'],
                'Milestones': ['veteran', 'legend', 'immortal'],
                'Kills': ['killer', 'slayer', 'destroyer'],
                'Special': ['mvp', 'champion', 'knife_master', 'demolition']
            }

            embed = discord.Embed(
                title="📜 All Available Titles",
                description="Unlock titles by achieving specific milestones!",
                color=0x3498DB
            )

            for category, title_ids in categories.items():
                titles_text = []
                for title_id in title_ids:
                    if title_id in self.bot.title_system.TITLES:
                        title_info = self.bot.title_system.TITLES[title_id]
                        titles_text.append(
                            f"**{title_info['title']}** `{title_id}`\n"
                            f"└ {title_info['description']}"
                        )

                if titles_text:
                    embed.add_field(
                        name=f"🎖️ {category}",
                        value="\n\n".join(titles_text),
                        inline=False
                    )

            embed.set_footer(text="💡 Use !title check to see which titles you can unlock")
            embed.timestamp = discord.utils.utcnow()

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error showing all titles: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving titles: {e}")


async def setup(bot):
    """Load the TitleCog"""
    await bot.add_cog(TitleCog(bot))
