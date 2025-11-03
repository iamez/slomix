"""
Team Management Commands

Discord commands for managing teams, viewing lineups, and tracking team statistics.
"""

import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import logging
from typing import Optional
from datetime import datetime

from bot.core.team_manager import TeamManager
from tools.stopwatch_scoring import StopwatchScoring

logger = logging.getLogger(__name__)


class TeamCog(commands.Cog):
    """Commands for team management and statistics"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "bot/etlegacy_production.db"
        self.team_manager = TeamManager(self.db_path)
        self.scorer = StopwatchScoring(self.db_path)
    
    def get_db(self) -> sqlite3.Connection:
        """Get database connection"""
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        return db
    
    def format_team_roster(self, team_name: str, team_data: dict) -> str:
        """Format team roster for display"""
        players = team_data.get('names', [])
        count = team_data.get('count', len(players))
        
        roster_text = f"**{team_name}** ({count} players)\n"
        roster_text += "```\n"
        for i, player in enumerate(players, 1):
            roster_text += f"{i:2d}. {player}\n"
        roster_text += "```"
        
        return roster_text
    
    @app_commands.command(name="teams", description="Show teams for current or specified session")
    @app_commands.describe(
        date="Session date (YYYY-MM-DD). Leave empty for latest session."
    )
    async def teams_command(self, interaction: discord.Interaction, date: Optional[str] = None):
        """Show team rosters for a session"""
        await interaction.response.defer()
        
        try:
            db = self.get_db()
            
            # Get session date
            if not date:
                cursor = db.cursor()
                cursor.execute(
                    "SELECT DISTINCT SUBSTR(session_date, 1, 10) as date "
                    "FROM sessions ORDER BY date DESC LIMIT 1"
                )
                row = cursor.fetchone()
                if not row:
                    await interaction.followup.send("❌ No sessions found in database.")
                    return
                date = row[0]
            
            # Validate date format
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                await interaction.followup.send(
                    "❌ Invalid date format. Use YYYY-MM-DD (e.g., 2025-10-28)"
                )
                return
            
            # Get teams
            teams = self.team_manager.get_session_teams(db, date, auto_detect=True)
            
            if not teams:
                await interaction.followup.send(
                    f"❌ No team data found for {date}. "
                    "Make sure there's session data for this date."
                )
                return
            
            # Build response
            embed = discord.Embed(
                title=f"🎮 Teams - {date}",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            # Add team rosters
            for team_name in sorted(teams.keys()):
                roster = self.format_team_roster(team_name, teams[team_name])
                embed.add_field(name=team_name, value=roster, inline=False)
            
            # Add footer with detection info
            embed.set_footer(text="Teams auto-detected from session data")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in teams command: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error: {str(e)}")
        finally:
            if 'db' in locals():
                db.close()
    
    @app_commands.command(name="set_team_names", description="Set custom names for teams")
    @app_commands.describe(
        date="Session date (YYYY-MM-DD)",
        team_a="Custom name for Team A",
        team_b="Custom name for Team B"
    )
    async def set_team_names_command(
        self,
        interaction: discord.Interaction,
        date: str,
        team_a: str,
        team_b: str
    ):
        """Set custom team names for a session"""
        await interaction.response.defer()
        
        try:
            # Validate date format
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                await interaction.followup.send(
                    "❌ Invalid date format. Use YYYY-MM-DD (e.g., 2025-10-28)"
                )
                return
            
            db = self.get_db()
            
            # Check if teams exist for this date
            teams = self.team_manager.get_session_teams(db, date, auto_detect=True)
            if not teams:
                await interaction.followup.send(
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
                    title=f"✅ Team Names Updated - {date}",
                    color=discord.Color.green(),
                    description=f"**{team_a}** vs **{team_b}**"
                )
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("❌ Failed to update team names.")
            
        except Exception as e:
            logger.error(f"Error in set_team_names command: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error: {str(e)}")
        finally:
            if 'db' in locals():
                db.close()
    
    @app_commands.command(name="lineup_changes", description="Show lineup changes between sessions")
    @app_commands.describe(
        current_date="Current session date (YYYY-MM-DD). Leave empty for latest.",
        previous_date="Previous session date (YYYY-MM-DD). Leave empty for automatic."
    )
    async def lineup_changes_command(
        self,
        interaction: discord.Interaction,
        current_date: Optional[str] = None,
        previous_date: Optional[str] = None
    ):
        """Show lineup changes between two sessions"""
        await interaction.response.defer()
        
        try:
            db = self.get_db()
            
            # Get current session date
            if not current_date:
                cursor = db.cursor()
                cursor.execute(
                    "SELECT DISTINCT SUBSTR(session_date, 1, 10) as date "
                    "FROM sessions ORDER BY date DESC LIMIT 1"
                )
                row = cursor.fetchone()
                if not row:
                    await interaction.followup.send("❌ No sessions found in database.")
                    return
                current_date = row[0]
            
            # Validate dates
            try:
                datetime.strptime(current_date, "%Y-%m-%d")
                if previous_date:
                    datetime.strptime(previous_date, "%Y-%m-%d")
            except ValueError:
                await interaction.followup.send(
                    "❌ Invalid date format. Use YYYY-MM-DD (e.g., 2025-10-28)"
                )
                return
            
            # Detect lineup changes
            changes = self.team_manager.detect_lineup_changes(
                db, current_date, previous_date
            )
            
            if not changes.get('previous'):
                await interaction.followup.send(
                    f"ℹ️ No previous session data found for comparison.\n"
                    f"Current session: {current_date}"
                )
                return
            
            # Build response
            embed = discord.Embed(
                title=f"📊 Lineup Changes",
                description=f"**{changes.get('previous_date')}** → **{current_date}**",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            
            # Add summary
            embed.add_field(
                name="Summary",
                value=f"```{changes.get('summary', 'No changes')}```",
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
                        change_text += f"  • {player}\n"
                
                if removed:
                    change_text += f"**➖ Removed ({len(removed)}):**\n"
                    for player in removed:
                        change_text += f"  • {player}\n"
                
                if not added and not removed:
                    change_text = f"✅ No changes ({len(unchanged)} players)"
                else:
                    change_text += f"\n🔄 Unchanged: {len(unchanged)} players"
                
                embed.add_field(name=team_name, value=change_text, inline=False)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in lineup_changes command: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error: {str(e)}")
        finally:
            if 'db' in locals():
                db.close()
    
    @app_commands.command(name="session_score", description="Show session score and team matchup")
    @app_commands.describe(
        date="Session date (YYYY-MM-DD). Leave empty for latest session."
    )
    async def session_score_command(
        self,
        interaction: discord.Interaction,
        date: Optional[str] = None
    ):
        """Show final score for a session"""
        await interaction.response.defer()
        
        try:
            db = self.get_db()
            
            # Get session date
            if not date:
                cursor = db.cursor()
                cursor.execute(
                    "SELECT DISTINCT SUBSTR(session_date, 1, 10) as date "
                    "FROM sessions ORDER BY date DESC LIMIT 1"
                )
                row = cursor.fetchone()
                if not row:
                    await interaction.followup.send("❌ No sessions found in database.")
                    return
                date = row[0]
            
            # Validate date
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                await interaction.followup.send(
                    "❌ Invalid date format. Use YYYY-MM-DD (e.g., 2025-10-28)"
                )
                return
            
            # Get teams
            teams = self.team_manager.get_session_teams(db, date, auto_detect=True)
            if not teams:
                await interaction.followup.send(f"❌ No team data found for {date}.")
                return
            
            # Calculate scores
            scores = self.scorer.calculate_session_scores(date)
            if not scores:
                await interaction.followup.send(
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
                color = discord.Color.green()
            elif score_b > score_a:
                winner = team_b
                color = discord.Color.red()
            else:
                winner = "TIE"
                color = discord.Color.gold()
            
            embed = discord.Embed(
                title=f"🏆 Session Score - {date}",
                color=color,
                timestamp=datetime.utcnow()
            )
            
            # Score display
            score_text = f"```\n{team_a:20s}  {score_a:2d}\n{team_b:20s}  {score_b:2d}\n```"
            embed.add_field(name="Final Score", value=score_text, inline=False)
            
            # Winner
            if winner != "TIE":
                embed.add_field(
                    name="Winner",
                    value=f"🎉 **{winner}**",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Result",
                    value="🤝 **TIE GAME**",
                    inline=False
                )
            
            # Map breakdown
            if 'maps' in scores:
                map_text = "```\n"
                for map_name, map_scores in scores.get('maps', {}).items():
                    map_text += f"{map_name:20s}  {map_scores.get(team_a, 0)}-{map_scores.get(team_b, 0)}\n"
                map_text += "```"
                embed.add_field(name="Map Breakdown", value=map_text, inline=False)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in session_score command: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error: {str(e)}")
        finally:
            if 'db' in locals():
                db.close()


async def setup(bot):
    """Setup function for loading the cog"""
    await bot.add_cog(TeamCog(bot))
