# Adapted redesigned last_session implementation as a callable helper
# Use as: await last_session_main(self, ctx, subcommand)

import asyncio
import discord
import aiosqlite
from datetime import datetime
import logging

logger = logging.getLogger('UltimateBot')


async def last_session_main(self, ctx, subcommand: str = None):
    """Main entrypoint for redesigned last_session behavior.
    This function is intended to be called from the Cog method as:
        await last_session_main(self, ctx, subcommand)
    """
    try:
        # Normalize subcommand
        if subcommand:
            subcommand = subcommand.lower()

        async with aiosqlite.connect(self.bot.db_path) as db:
            # Get most recent session date
            async with db.execute('''
                SELECT DISTINCT DATE(session_date) as date
                FROM player_comprehensive_stats
                ORDER BY date DESC
                LIMIT 1
            ''') as cursor:
                row = await cursor.fetchone()
                if not row:
                    await ctx.send("❌ No sessions found")
                    return

                latest_date = row[0]

            # Get all session IDs for this date
            async with db.execute(
                '''
                SELECT id, map_name, round_number, session_date
                FROM sessions
                WHERE DATE(session_date) = ?
                ORDER BY id ASC
                ''',
                (latest_date,),
            ) as cursor:
                sessions = await cursor.fetchall()

            if not sessions:
                await ctx.send("❌ No sessions found for latest date")
                return

            session_ids = [s[0] for s in sessions]
            session_ids_str = ','.join('?' * len(session_ids))

            # Route directly to requested view
            if subcommand == "obj" or subcommand == "objective" or subcommand == "objectives":
                await _last_session_obj_view(self, ctx, db, session_ids, session_ids_str, latest_date)

            elif subcommand == "combat":
                await _last_session_combat_view(self, ctx, db, session_ids, session_ids_str, latest_date)

            elif subcommand == "weapons" or subcommand == "weapon" or subcommand == "weap":
                await _last_session_weapons_view(self, ctx, db, session_ids, session_ids_str, latest_date)

            elif subcommand == "graphs" or subcommand == "graph" or subcommand == "charts":
                await _last_session_graphs_view(self, ctx, db, session_ids, session_ids_str, latest_date)

            elif subcommand is None:
                # Default clean view
                await _last_session_clean_default_view(self, ctx, db, session_ids, session_ids_str, latest_date, sessions)

            else:
                await ctx.send(
                    f"❌ Unknown view: `{subcommand}`\n"
                    f"Available: `obj`, `combat`, `weapons`, `graphs`"
                )

    except Exception as e:
        logger.error(f"Error in redesigned last_session_main: {e}", exc_info=True)
        await ctx.send(f"❌ Error retrieving last session: {e}")


# ---------------------------------------------------------------------------
# Button view and helper views (copied/adapted from redesign)
# Note: these helpers expect a Cog instance as `self` and will reference
#       self.bot.db_path and other Cog helpers as needed.
# ---------------------------------------------------------------------------

from discord.ui import View, Button

class SessionButtonView(View):
    def __init__(self, bot, ctx, session_ids, session_ids_str, latest_date):
        super().__init__(timeout=300)
        self.bot = bot
        self.ctx = ctx
        self.session_ids = session_ids
        self.session_ids_str = session_ids_str
        self.latest_date = latest_date

    @discord.ui.button(label="Objectives", style=discord.ButtonStyle.primary, emoji="🎯")
    async def objectives_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        async with aiosqlite.connect(self.bot.db_path) as db:
            await self.bot._last_session_obj_view(self.ctx, db, self.session_ids, self.session_ids_str, self.latest_date)

    @discord.ui.button(label="Combat", style=discord.ButtonStyle.danger, emoji="⚔️")
    async def combat_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        async with aiosqlite.connect(self.bot.db_path) as db:
            await self.bot._last_session_combat_view(self.ctx, db, self.session_ids, self.session_ids_str, self.latest_date)

    @discord.ui.button(label="Weapons", style=discord.ButtonStyle.secondary, emoji="🔫")
    async def weapons_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        async with aiosqlite.connect(self.bot.db_path) as db:
            await self.bot._last_session_weapons_view(self.ctx, db, self.session_ids, self.session_ids_str, self.latest_date)

    @discord.ui.button(label="Graphs", style=discord.ButtonStyle.success, emoji="📊")
    async def graphs_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        async with aiosqlite.connect(self.bot.db_path) as db:
            await self.bot._last_session_graphs_view(self.ctx, db, self.session_ids, self.session_ids_str, self.latest_date)


# The helper views below are simplified/adapted and intentionally safe (no heavy graphs by default)

async def _last_session_clean_default_view(self, ctx, db, session_ids, session_ids_str, latest_date, sessions):
    # (Implementation copied/adapted from redesign - truncated for brevity here)
    # For full implementation, see test_suite file. This stub is conservative and safe.
    # Count players
    query = f'''SELECT COUNT(DISTINCT player_guid) FROM player_comprehensive_stats WHERE session_id IN ({session_ids_str})'''
    async with db.execute(query, session_ids) as cursor:
        player_count_row = await cursor.fetchone()
        player_count = player_count_row[0] if player_count_row else 0

    # Build a minimal embed summary
    embed = discord.Embed(
        title=f"📊 Session Summary",
        description=f"**{latest_date}** • {player_count} players",
        color=0x5865F2,
        timestamp=datetime.now()
    )
    embed.set_footer(text="Use buttons for more views: Objectives / Combat / Weapons / Graphs")

    view = SessionButtonView(self.bot, ctx, session_ids, session_ids_str, latest_date)
    await ctx.send(embed=embed, view=view)


async def _last_session_obj_view(self, ctx, db, session_ids, session_ids_str, latest_date):
    query = f'''SELECT p.player_name, SUM(p.kills) as kills, SUM(p.revives_given) as revives_given
                FROM player_comprehensive_stats p
                WHERE p.session_id IN ({session_ids_str})
                GROUP BY p.player_guid, p.player_name
                ORDER BY revives_given DESC'''
    async with db.execute(query, session_ids) as cursor:
        players = await cursor.fetchall()
    if not players:
        await ctx.send("❌ No objective data found")
        return
    embed = discord.Embed(title=f"🎯 Objectives - {latest_date}", color=0xF1C40F, timestamp=datetime.now())
    text = "\n".join([f"**{p[0]}** • Revives: {p[2]} • Kills: {p[1]}" for p in players])
    embed.add_field(name="Players", value=text[:1000], inline=False)
    await ctx.send(embed=embed)


async def _last_session_combat_view(self, ctx, db, session_ids, session_ids_str, latest_date):
    query = f'''SELECT p.player_name, SUM(p.kills) as kills, SUM(p.deaths) as deaths
                FROM player_comprehensive_stats p
                WHERE p.session_id IN ({session_ids_str})
                GROUP BY p.player_guid, p.player_name
                ORDER BY kills DESC'''
    async with db.execute(query, session_ids) as cursor:
        players = await cursor.fetchall()
    if not players:
        await ctx.send("❌ No combat data found")
        return
    embed = discord.Embed(title=f"⚔️ Combat Stats - {latest_date}", color=0xE74C3C, timestamp=datetime.now())
    text = "\n".join([f"**{p[0]}** • {p[1]}K/{p[2]}D" for p in players])
    embed.add_field(name="Players", value=text[:1000], inline=False)
    await ctx.send(embed=embed)


async def _last_session_weapons_view(self, ctx, db, session_ids, session_ids_str, latest_date):
    await ctx.send(f"🔫 Weapons view - showing breakdown for {latest_date} (placeholder)")


async def _last_session_graphs_view(self, ctx, db, session_ids, session_ids_str, latest_date):
    await ctx.send(f"📊 Graphs view - generating charts for {latest_date} (placeholder)")
