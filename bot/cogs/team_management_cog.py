"""
👥 Team Management Cog - Team Assignment Commands
Handles manual team name setting and player assignment to teams.

Commands:
- set_teams: Set persistent team names for latest session
- assign_player: Assign a player to a team

These commands allow manual override of team assignments for proper
team tracking in session analytics.
"""

import json
import logging

# import aiosqlite  # Removed - using database adapter
import discord
from discord.ext import commands

from bot.core.checks import is_admin_channel
from bot.core.utils import sanitize_error_message

logger = logging.getLogger("UltimateBot.TeamManagementCog")


class TeamManagementCog(commands.Cog, name="Team Management"):
    """👥 Team assignment commands"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("👥 TeamManagementCog initializing...")

    async def _ensure_session_teams_table(self):
        """Ensure session_teams table exists"""
        await self.bot.db_adapter.execute(
            """
            CREATE TABLE IF NOT EXISTS session_teams (
                session_start_date TEXT NOT NULL,
                map_name TEXT NOT NULL,
                team_name TEXT NOT NULL,
                player_guids TEXT,
                player_names TEXT,
                PRIMARY KEY (session_start_date, map_name, team_name)
            )
        """
        )

    @is_admin_channel()
    @commands.command(name="set_teams")
    async def set_teams(self, ctx, team1_name: str, team2_name: str):
        """👥 Manually set persistent team names for the latest session date
        
        Usage: !set_teams "Team A" "Team B"
        
        This creates team entries for the most recent session date.
        After setting teams, use !assign_player to add players to each team.
        """
        try:
            await self._ensure_session_teams_table()

            # Determine latest session date (YYYY-MM-DD)
            row = await self.bot.db_adapter.fetch_one(
                "SELECT DISTINCT substr(round_date,1,10) as d FROM rounds ORDER BY d DESC LIMIT 1"
            )
            if not row:
                await ctx.send("❌ No rounds found to set teams for.")
                return
            round_date = row[0]

            # Upsert two team rows with map_name='ALL' and empty rosters initially
            empty = json.dumps([])
            for tname in (team1_name, team2_name):
                await self.bot.db_adapter.execute(
                    """
                    INSERT INTO session_teams (session_start_date, map_name, team_name, player_guids, player_names)
                    VALUES (?, 'ALL', ?, ?, ?)
                    ON CONFLICT(session_start_date, map_name, team_name)
                    DO UPDATE SET team_name=excluded.team_name
                    """,
                    (round_date, tname, empty, empty)
                )

            embed = discord.Embed(
                title="✅ Teams Set Successfully!",
                description=f"Teams configured for session: **{round_date}**",
                color=0x00FF00,
            )
            embed.add_field(name="Team 1", value=f"**{team1_name}**", inline=True)
            embed.add_field(name="Team 2", value=f"**{team2_name}**", inline=True)
            embed.add_field(
                name="Next Step",
                value="Use `!assign_player <name> <team>` to add players to teams",
                inline=False,
            )

            await ctx.send(embed=embed)
            logger.info(f"✅ Teams set for {round_date}: {team1_name} vs {team2_name}")

        except Exception as e:
            logger.error(f"Error in set_teams: {e}", exc_info=True)
            await ctx.send(f"❌ Error setting teams: {sanitize_error_message(e)}")

    @is_admin_channel()
    @commands.command(name="assign_player")
    async def assign_player(self, ctx, player_name: str, team_name: str):
        """👤 Assign a player to a persistent team for the latest session date
        
        Usage: !assign_player "PlayerName" "Team A"
        
        Assigns a player to a specific team. The player name is fuzzy-matched
        against known player aliases. Use !set_teams first to create the teams.
        """
        try:
            await self._ensure_session_teams_table()

            # Resolve latest session date
            row = await self.bot.db_adapter.fetch_one(
                "SELECT DISTINCT substr(round_date,1,10) as d FROM rounds ORDER BY d DESC LIMIT 1"
            )
            if not row:
                await ctx.send("❌ No rounds found.")
                return
            round_date = row[0]

            # Resolve most recent GUID for the player (fuzzy match by alias)
            pa = await self.bot.db_adapter.fetch_one(
                """
                SELECT guid, alias
                FROM player_aliases
                WHERE lower(alias) LIKE lower(?)
                ORDER BY last_seen DESC
                LIMIT 1
                """,
                (f"%{player_name}%",)
            )
            if not pa:
                await ctx.send(f"❌ Player '{player_name}' not found in aliases.")
                return
            player_guid, resolved_alias = pa

            # Ensure team row exists for this date (map_name='ALL')
            empty = json.dumps([])
            await self.bot.db_adapter.execute(
                """
                INSERT INTO session_teams (session_start_date, map_name, team_name, player_guids, player_names)
                VALUES (?, 'ALL', ?, ?, ?)
                ON CONFLICT(session_start_date, map_name, team_name)
                DO NOTHING
                """,
                (round_date, team_name, empty, empty)
            )

            # Fetch current roster
            row = await self.bot.db_adapter.fetch_one(
                """
                SELECT player_guids, player_names
                FROM session_teams
                WHERE session_start_date = ? AND map_name = 'ALL' AND team_name = ?
                """,
                (round_date, team_name)
            )

            if not row:
                await ctx.send(
                    f"❌ Team '{team_name}' not found for {round_date}. Use `!set_teams` first."
                )
                return

            # Update roster
            guids = set(json.loads(row[0] or "[]"))
            names = set(json.loads(row[1] or "[]"))
            updated = False
            
            if player_guid not in guids:
                guids.add(player_guid)
                updated = True
            if resolved_alias not in names:
                names.add(resolved_alias)
                updated = True

            if updated:
                await self.bot.db_adapter.execute(
                    """
                    UPDATE session_teams
                    SET player_guids = ?, player_names = ?
                    WHERE session_start_date = ? AND map_name = 'ALL' AND team_name = ?
                    """,
                    (
                        json.dumps(sorted(list(guids))),
                        json.dumps(sorted(list(names))),
                        round_date,
                        team_name,
                    )
                )

                embed = discord.Embed(
                    title="✅ Player Assigned!",
                    description=f"**{resolved_alias}** assigned to **{team_name}**",
                    color=0x00FF00,
                )
                embed.add_field(name="Session Date", value=round_date, inline=True)
                embed.add_field(name="Player GUID", value=f"`{player_guid[:8]}...`", inline=True)

                await ctx.send(embed=embed)
                logger.info(f"✅ Assigned {resolved_alias} to {team_name} for {round_date}")
            else:
                await ctx.send(f"ℹ️ **{resolved_alias}** is already on **{team_name}**")

        except Exception as e:
            logger.error(f"Error in assign_player: {e}", exc_info=True)
            await ctx.send(f"❌ Error assigning player: {sanitize_error_message(e)}")


async def setup(bot):
    """Load the Team Management Cog"""
    await bot.add_cog(TeamManagementCog(bot))
