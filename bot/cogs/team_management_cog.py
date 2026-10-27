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

from bot.core.checks import is_admin
from bot.core.guid_utils import short_guid
from bot.core.utils import sanitize_error_message
from shared.team_write_guard import team_write_transaction

logger = logging.getLogger("UltimateBot.TeamManagementCog")


class _TeamCommandNotice(Exception):
    """Expected command rejection, reported only after transaction rollback."""


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

    async def _team_conflict_target(self) -> str:
        """Use a static conflict target matching the relation's identity schema."""
        row = await self.bot.db_adapter.fetch_one(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'session_teams'
                  AND column_name = 'session_identity'
            )
            """
        )
        if row and row[0]:
            return "(session_identity, map_name, team_name)"
        return "(session_start_date, map_name, team_name)"

    async def _set_team_rows(self, team1_name: str, team2_name: str) -> str | None:
        """Preserve date-only command semantics, but commit the pair together."""
        async with self.bot.db_adapter.transaction() as conn, team_write_transaction(conn):
            await self._ensure_session_teams_table()

            # Determine latest session date (YYYY-MM-DD)
            row = await self.bot.db_adapter.fetch_one(
                "SELECT DISTINCT substr(round_date,1,10) as d FROM rounds ORDER BY d DESC LIMIT 1"
            )
            if not row:
                return None
            round_date = row[0]

            conflict_target = await self._team_conflict_target()

            # Upsert two team rows with map_name='ALL' and empty rosters initially
            empty = json.dumps([])
            for tname in (team1_name, team2_name):
                await self.bot.db_adapter.execute(
                    f"""
                    INSERT INTO session_teams (session_start_date, map_name, team_name, player_guids, player_names)
                    VALUES (?, 'ALL', ?, ?, ?)
                    ON CONFLICT {conflict_target}
                    DO UPDATE SET team_name=excluded.team_name
                    """,
                    (round_date, tname, empty, empty)
                )
            return round_date

    @is_admin()
    @commands.command(name="set_teams")
    async def set_teams(self, ctx, team1_name: str, team2_name: str):
        """👥 Manually set persistent team names for the latest session date

        Usage: !set_teams "Team A" "Team B"

        This creates team entries for the most recent session date.
        After setting teams, use !assign_player to add players to each team.
        """
        try:
            round_date = await self._set_team_rows(team1_name, team2_name)
            if round_date is None:
                await ctx.send("❌ No rounds found to set teams for.")
                return

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

    async def _assign_player_row(self, player_name: str, team_name: str):
        """Guard lookup, optional creation and roster update before any response."""
        async with self.bot.db_adapter.transaction() as conn, team_write_transaction(conn):
            await self._ensure_session_teams_table()

            # Resolve latest session date
            row = await self.bot.db_adapter.fetch_one(
                "SELECT DISTINCT substr(round_date,1,10) as d FROM rounds ORDER BY d DESC LIMIT 1"
            )
            if not row:
                raise _TeamCommandNotice("❌ No rounds found.")
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
                raise _TeamCommandNotice(f"❌ Player '{player_name}' not found in aliases.")
            player_guid, resolved_alias = pa

            # Ensure team row exists for this date (map_name='ALL')
            conflict_target = await self._team_conflict_target()
            empty = json.dumps([])
            await self.bot.db_adapter.execute(
                f"""
                INSERT INTO session_teams (session_start_date, map_name, team_name, player_guids, player_names)
                VALUES (?, 'ALL', ?, ?, ?)
                ON CONFLICT {conflict_target}
                DO NOTHING
                """,
                (round_date, team_name, empty, empty)
            )

            # Reject ambiguous date/name matches rather than overwrite several sessions.
            rows = await self.bot.db_adapter.fetch_all(
                """
                SELECT player_guids, player_names
                FROM session_teams
                WHERE session_start_date = ? AND map_name = 'ALL' AND team_name = ?
                """,
                (round_date, team_name)
            )

            if not rows:
                raise _TeamCommandNotice(
                    f"❌ Team '{team_name}' not found for {round_date}. Use `!set_teams` first."
                )
            if len(rows) != 1:
                raise _TeamCommandNotice(
                    "❌ Multiple sessions match this date and team name; no players were changed."
                )
            row = rows[0]

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
                        json.dumps(sorted(guids)),
                        json.dumps(sorted(names)),
                        round_date,
                        team_name,
                    )
                )
            return round_date, player_guid, resolved_alias, updated

    @is_admin()
    @commands.command(name="assign_player")
    async def assign_player(self, ctx, player_name: str, team_name: str):
        """👤 Assign a player to a persistent team for the latest session date

        Usage: !assign_player "PlayerName" "Team A"

        Assigns a player to a specific team. The player name is fuzzy-matched
        against known player aliases. Use !set_teams first to create the teams.
        """
        try:
            round_date, player_guid, resolved_alias, updated = await self._assign_player_row(
                player_name, team_name
            )
            if updated:
                embed = discord.Embed(
                    title="✅ Player Assigned!",
                    description=f"**{resolved_alias}** assigned to **{team_name}**",
                    color=0x00FF00,
                )
                embed.add_field(name="Session Date", value=round_date, inline=True)
                embed.add_field(name="Player GUID", value=f"`{short_guid(player_guid)}...`", inline=True)

                await ctx.send(embed=embed)
                logger.info(f"✅ Assigned {resolved_alias} to {team_name} for {round_date}")
            else:
                await ctx.send(f"ℹ️ **{resolved_alias}** is already on **{team_name}**")

        except _TeamCommandNotice as e:
            await ctx.send(str(e))
        except Exception as e:
            logger.error(f"Error in assign_player: {e}", exc_info=True)
            await ctx.send(f"❌ Error assigning player: {sanitize_error_message(e)}")


async def setup(bot):
    """Load the Team Management Cog"""
    await bot.add_cog(TeamManagementCog(bot))
