"""
Team Management Commands

Discord commands for managing teams, viewing lineups, and tracking team statistics.
"""

import discord
from discord.ext import commands
from discord import app_commands
import logging
import sqlite3
from typing import Optional, List, Tuple
from datetime import datetime

from bot.core.team_manager import TeamManager
from bot.services.player_formatter import PlayerFormatter
from tools.stopwatch_scoring import StopwatchScoring

logger = logging.getLogger(__name__)


class TeamCog(commands.Cog):
    """Commands for team management and statistics"""

    def __init__(self, bot):
        self.bot = bot
        self.db_path = "bot/etlegacy_production.db"
        self.team_manager = TeamManager(self.db_path)
        self.scorer = StopwatchScoring(self.db_path)
        self.player_formatter = PlayerFormatter(bot.db_adapter)

    def get_db(self) -> sqlite3.Connection:
        """Get database connection"""
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        return db

    async def format_team_roster(self, team_name: str, team_data: dict) -> str:
        """Format team roster for display with badges"""
        players = team_data.get('names', [])
        guids = team_data.get('guids', [])
        count = team_data.get('count', len(players))

        roster_text = f"**{team_name}** (`{count}` players)\n"

        # If we have GUIDs, fetch badges for all players
        if guids and len(guids) == len(players):
            player_tuples = [(guid, name) for guid, name in zip(guids, players)]
            formatted_names = await self.player_formatter.format_players_batch(
                player_tuples, include_badges=True
            )

            for i, (guid, name) in enumerate(player_tuples, 1):
                formatted_name = formatted_names.get(guid, name)
                roster_text += f"`{i:2d}.` {formatted_name}\n"
        else:
            # Fallback to plain names if no GUIDs available
            for i, player in enumerate(players, 1):
                roster_text += f"`{i:2d}.` {player}\n"

        return roster_text
    
    @commands.command(name="teams")
    async def teams_command(self, ctx, date: Optional[str] = None):
        """Show team rosters for a session
        
        Usage:
        !teams              → Show teams for latest session
        !teams 2025-11-02   → Show teams for specific date
        """
        
        try:
            db = self.get_db()
            
            # Get round date
            if not date:
                cursor = db.cursor()
                cursor.execute(
                    "SELECT DISTINCT SUBSTR(round_date, 1, 10) as date "
                    "FROM rounds ORDER BY date DESC LIMIT 1"
                )
                row = cursor.fetchone()
                if not row:
                    await ctx.send("❌ No rounds found in database.")
                    return
                date = row[0]
            
            # Validate date format
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                await ctx.send(
                    "❌ Invalid date format. Use YYYY-MM-DD (e.g., 2025-10-28)"
                )
                return
            
            # Get teams
            teams = self.team_manager.get_session_teams(db, date, auto_detect=True)
            
            if not teams:
                await ctx.send(
                    f"❌ No team data found for {date}. "
                    "Make sure there's session data for this date."
                )
                return
            
            # Build response
            embed = discord.Embed(
                title=f"🎮 Team Rosters - {date}",
                description="Achievement badges shown next to player names",
                color=0x5865F2,  # Discord Blurple
                timestamp=datetime.now()
            )

            # Add team rosters with badges
            for team_name in sorted(teams.keys()):
                roster = await self.format_team_roster(team_name, teams[team_name])
                embed.add_field(name=f"═══ {team_name} ═══", value=roster, inline=False)

            # Add footer with detection info
            total_players = sum(team.get('count', 0) for team in teams.values())
            embed.set_footer(
                text=f"🔍 Auto-detected • {total_players} total players • Requested by {ctx.author.name}"
            )

            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in teams command: {e}", exc_info=True)
            await ctx.send(f"❌ Error: {str(e)}")
        finally:
            if 'db' in locals():
                db.close()
    
    @commands.command(name="set_team_names")
    async def set_team_names_command(self, ctx, date: str, team_a: str, team_b: str):
        """Set custom team names for a session
        
        Usage:
        !set_team_names 2025-11-02 "Red Devils" "Blue Lightning"
        """
        
        try:
            # Validate date format
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                await ctx.send(
                    "❌ Invalid date format. Use YYYY-MM-DD (e.g., 2025-10-28)"
                )
                return
            
            db = self.get_db()
            
            # Check if teams exist for this date
            teams = self.team_manager.get_session_teams(db, date, auto_detect=True)
            if not teams:
                await ctx.send(
                    f"❌ No team data found for {date}. "
                    "Teams must be detected before setting custom names."
                )
                return
            
            # Set custom names
            success = self.team_manager.set_custom_team_names(
                db, date, team_a, team_b
            )

            if success:
                embed = discord.Embed(
                    title=f"✅ Team Names Updated",
                    description=f"**{team_a}** ⚔️ **{team_b}**",
                    color=0x57F287,  # Green
                    timestamp=datetime.now()
                )
                embed.add_field(
                    name="📅 Session Date",
                    value=f"`{date}`",
                    inline=False
                )
                embed.set_footer(text=f"Updated by {ctx.author.name}")
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ Failed to update team names.")
            
        except Exception as e:
            logger.error(f"Error in set_team_names command: {e}", exc_info=True)
            await ctx.send(f"❌ Error: {str(e)}")
        finally:
            if 'db' in locals():
                db.close()
    
    @commands.command(name="lineup_changes")
    async def lineup_changes_command(self, ctx, current_date: Optional[str] = None, previous_date: Optional[str] = None):
        """Show lineup changes between two sessions
        
        Usage:
        !lineup_changes                      → Compare latest session with previous
        !lineup_changes 2025-11-02           → Compare specified date with previous
        !lineup_changes 2025-11-02 2025-11-01 → Compare two specific dates
        """
        
        try:
            db = self.get_db()
            
            # Get current session date
            if not current_date:
                cursor = db.cursor()
                cursor.execute(
                    "SELECT DISTINCT SUBSTR(round_date, 1, 10) as date "
                    "FROM rounds ORDER BY date DESC LIMIT 1"
                )
                row = cursor.fetchone()
                if not row:
                    await ctx.send("❌ No rounds found in database.")
                    return
                current_date = row[0]
            
            # Validate dates
            try:
                datetime.strptime(current_date, "%Y-%m-%d")
                if previous_date:
                    datetime.strptime(previous_date, "%Y-%m-%d")
            except ValueError:
                await ctx.send(
                    "❌ Invalid date format. Use YYYY-MM-DD (e.g., 2025-10-28)"
                )
                return
            
            # Detect lineup changes
            changes = self.team_manager.detect_lineup_changes(
                db, current_date, previous_date
            )
            
            if not changes.get('previous'):
                await ctx.send(
                    f"ℹ️ No previous session data found for comparison.\n"
                    f"Current session: {current_date}"
                )
                return
            
            # Build response
            embed = discord.Embed(
                title=f"📊 Lineup Changes",
                description=f"`{changes.get('previous_date')}` ➜ `{current_date}`",
                color=0xF26522,  # Orange
                timestamp=datetime.now()
            )

            # Add summary with better formatting
            summary = changes.get('summary', 'No changes')
            embed.add_field(
                name="📈 Summary",
                value=f"```\n{summary}\n```",
                inline=False
            )

            # Add detailed changes for each team
            for team_name, team_changes in changes.get('changes', {}).items():
                added = team_changes.get('added', [])
                removed = team_changes.get('removed', [])
                unchanged = team_changes.get('unchanged', [])

                change_text = ""

                if added:
                    change_text += f"**➕ Added ({len(added)}):**\n"
                    for player in added:
                        change_text += f"  • `{player}`\n"

                if removed:
                    change_text += f"**➖ Removed ({len(removed)}):**\n"
                    for player in removed:
                        change_text += f"  • `{player}`\n"

                if not added and not removed:
                    change_text = f"✅ **No changes** • `{len(unchanged)}` players unchanged"
                else:
                    change_text += f"\n🔄 **Unchanged:** `{len(unchanged)}` players"

                embed.add_field(
                    name=f"═══ {team_name} ═══",
                    value=change_text,
                    inline=False
                )

            embed.set_footer(text=f"Comparison requested by {ctx.author.name}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in lineup_changes command: {e}", exc_info=True)
            await ctx.send(f"❌ Error: {str(e)}")
        finally:
            if 'db' in locals():
                db.close()
    
    @commands.command(name="session_score")
    async def session_score_command(self, ctx, date: Optional[str] = None):
        """Show final score for a session
        
        Usage:
        !session_score              → Show score for latest session
        !session_score 2025-11-02   → Show score for specific date
        """
        
        try:
            db = self.get_db()
            
            # Get round date
            if not date:
                cursor = db.cursor()
                cursor.execute(
                    "SELECT DISTINCT SUBSTR(round_date, 1, 10) as date "
                    "FROM rounds ORDER BY date DESC LIMIT 1"
                )
                row = cursor.fetchone()
                if not row:
                    await ctx.send("❌ No rounds found in database.")
                    return
                date = row[0]
            
            # Validate date
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                await ctx.send(
                    "❌ Invalid date format. Use YYYY-MM-DD (e.g., 2025-10-28)"
                )
                return
            
            # Get teams
            teams = self.team_manager.get_session_teams(db, date, auto_detect=True)
            if not teams:
                await ctx.send(f"❌ No team data found for {date}.")
                return
            
            # Calculate scores
            scores = self.scorer.calculate_session_scores(date)
            if not scores:
                await ctx.send(
                    f"❌ No scoring data found for {date}. "
                    "Ensure session has complete round data."
                )
                return
            
            # Build response
            team_names = list(teams.keys())
            team_a = team_names[0] if len(team_names) > 0 else "Team A"
            team_b = team_names[1] if len(team_names) > 1 else "Team B"
            
            score_a = scores.get(team_a, 0)
            score_b = scores.get(team_b, 0)
            
            # Determine winner
            if score_a > score_b:
                winner = team_a
                color = 0x57F287  # Green
                winner_emoji = "🏆"
            elif score_b > score_a:
                winner = team_b
                color = 0xED4245  # Red
                winner_emoji = "🏆"
            else:
                winner = "TIE"
                color = 0xFFD700  # Gold
                winner_emoji = "🤝"

            # Build description
            if winner != "TIE":
                description = f"{winner_emoji} **{winner}** wins the session!"
            else:
                description = f"{winner_emoji} Evenly matched - it's a tie!"

            embed = discord.Embed(
                title=f"🏆 Session Score",
                description=description,
                color=color,
                timestamp=datetime.now()
            )

            # Score display with better formatting
            score_text = (
                f"**{team_a}**\n"
                f"```\n{score_a:>3d} points\n```\n"
                f"**{team_b}**\n"
                f"```\n{score_b:>3d} points\n```"
            )
            embed.add_field(
                name="📊 Final Score",
                value=score_text,
                inline=True
            )

            # Map breakdown
            if 'maps' in scores and scores.get('maps'):
                map_text = ""
                for map_name, map_scores in scores.get('maps', {}).items():
                    score_a_map = map_scores.get(team_a, 0)
                    score_b_map = map_scores.get(team_b, 0)
                    # Determine map winner emoji
                    if score_a_map > score_b_map:
                        map_emoji = "🟢"
                    elif score_b_map > score_a_map:
                        map_emoji = "🔴"
                    else:
                        map_emoji = "⚪"

                    map_text += f"{map_emoji} **{map_name}**\n`{score_a_map}-{score_b_map}`\n\n"

                embed.add_field(
                    name="🗺️ Map Breakdown",
                    value=map_text.strip(),
                    inline=True
                )

            # Session info
            embed.add_field(
                name="📅 Session Date",
                value=f"`{date}`",
                inline=False
            )

            embed.set_footer(text=f"Score requested by {ctx.author.name}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in session_score command: {e}", exc_info=True)
            await ctx.send(f"❌ Error: {str(e)}")
        finally:
            if 'db' in locals():
                db.close()


async def setup(bot):
    """Setup function for loading the cog"""
    await bot.add_cog(TeamCog(bot))
