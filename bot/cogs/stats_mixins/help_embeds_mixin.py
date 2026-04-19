"""StatsCog mixin: !help category embed builders (9 static embed factories).

Extracted from bot/cogs/stats_cog.py in Mega Audit v4 / Sprint 2.

All methods live on StatsCog via mixin inheritance.
"""
from __future__ import annotations

import logging

import discord

logger = logging.getLogger("bot.cogs.stats")


class _StatsHelpEmbedsMixin:
    """!help category embed builders (9 static embed factories) for StatsCog."""

    def _help_stats(self) -> discord.Embed:
        """Generate stats category help embed"""
        embed = discord.Embed(
            title="🎯 Player Stats Commands",
            description="View individual player statistics and comparisons",
            color=0xFF6B6B,
        )
        embed.add_field(
            name="`!stats <player>`",
            value="View comprehensive player statistics\n└ Example: `!stats carniee`",
            inline=False,
        )
        embed.add_field(
            name="`!leaderboard [stat] [page]`",
            value="Top players by stat (kills, accuracy, kd, revives, xp, etc.)\n└ Aliases: `!lb`, `!top`\n└ Example: `!lb accuracy 2`",
            inline=False,
        )
        embed.add_field(
            name="`!compare <player1> <player2>`",
            value="Head-to-head player comparison\n└ Example: `!compare carniee superboyy`",
            inline=False,
        )
        embed.add_field(
            name="`!achievements [player]`",
            value="View player achievements and badges\n└ Aliases: `!medals`, `!achievement`",
            inline=False,
        )
        embed.add_field(
            name="`!check_achievements [player]`",
            value="Check achievement progress",
            inline=False,
        )
        embed.add_field(
            name="`!badges`",
            value="Show achievement badge legend\n└ Aliases: `!badge_legend`, `!achievements_legend`",
            inline=False,
        )
        embed.add_field(
            name="`!season_info`",
            value="Current season statistics\n└ Aliases: `!season`, `!seasons`",
            inline=False,
        )
        return embed

    def _help_sessions(self) -> discord.Embed:
        """Generate sessions category help embed"""
        embed = discord.Embed(
            title="📊 Session Commands",
            description="View gaming sessions and rounds",
            color=0x4ECDC4,
        )
        embed.add_field(
            name="`!last_session [subcommand]`",
            value=(
                "View latest gaming session with 5 performance graphs\n"
                "└ Aliases: `!last`, `!latest`, `!recent`, `!last_round`\n"
                "└ Subcommands: `graphs`, `stats`, `weapons`, `teams`"
            ),
            inline=False,
        )
        embed.add_field(
            name="`!session <date>`",
            value="View specific date session\n└ Aliases: `!match`, `!game`\n└ Example: `!session 2025-11-02`",
            inline=False,
        )
        embed.add_field(
            name="`!sessions [month]`",
            value="List all gaming sessions, optionally filtered by month\n└ Aliases: `!rounds`, `!list_sessions`, `!ls`\n└ Example: `!sessions 10` or `!sessions october`",
            inline=False,
        )
        embed.add_field(
            name="`!team_history <player>`",
            value="View a player's team history across sessions",
            inline=False,
        )
        embed.add_field(
            name="`!session_start`",
            value="🔒 Admin: Mark start of new gaming session",
            inline=False,
        )
        embed.add_field(
            name="`!session_end`",
            value="🔒 Admin: Mark end of current gaming session",
            inline=False,
        )
        return embed

    def _help_teams(self) -> discord.Embed:
        """Generate teams category help embed"""
        embed = discord.Embed(
            title="👥 Team Commands",
            description="View and manage team information",
            color=0x45B7D1,
        )
        embed.add_field(
            name="`!teams [date]`",
            value="Show team rosters for a session\n└ Example: `!teams 2025-11-02`",
            inline=False,
        )
        embed.add_field(
            name="`!session_score [date]`",
            value="Team scores with map-by-map breakdown",
            inline=False,
        )
        embed.add_field(
            name="`!lineup_changes [current] [previous]`",
            value="Show who switched teams between sessions\n└ Example: `!lineup_changes 2025-11-02`",
            inline=False,
        )
        embed.add_field(
            name="`!set_team_names <date> <team_a> <team_b>`",
            value="🔒 Admin: Set custom team names for a session\n└ Example: `!set_team_names 2025-11-02 Alpha Bravo`",
            inline=False,
        )
        embed.add_field(
            name="`!set_teams`",
            value="🔒 Admin: Manually set team assignments",
            inline=False,
        )
        embed.add_field(
            name="`!assign_player <player> <team>`",
            value="🔒 Admin: Assign player to a team",
            inline=False,
        )
        return embed

    def _help_predictions(self) -> discord.Embed:
        """Generate predictions category help embed"""
        embed = discord.Embed(
            title="🎲 Prediction Commands",
            description="Match predictions and betting system",
            color=0xF7DC6F,
        )
        embed.add_field(
            name="`!predictions`",
            value="View available predictions and place bets",
            inline=False,
        )
        embed.add_field(
            name="`!prediction_stats`",
            value="Your prediction statistics and accuracy\n└ Aliases: `!pred_stats`",
            inline=False,
        )
        embed.add_field(
            name="`!my_predictions`",
            value="View your prediction history",
            inline=False,
        )
        embed.add_field(
            name="`!prediction_trends`",
            value="Analyze prediction trends over time",
            inline=False,
        )
        embed.add_field(
            name="`!prediction_leaderboard`",
            value="Top predictors by accuracy",
            inline=False,
        )
        embed.add_field(
            name="`!map_predictions`",
            value="Predictions by map statistics",
            inline=False,
        )
        embed.add_field(
            name="`!prediction_help`",
            value="Detailed prediction system help",
            inline=False,
        )
        return embed

    def _help_synergy(self) -> discord.Embed:
        """Generate synergy & analytics help embed"""
        embed = discord.Embed(
            title="🤝 Synergy & Analytics Commands",
            description="Player chemistry and team building tools",
            color=0xBB8FCE,
        )
        embed.add_field(
            name="`!synergy <player1> <player2>`",
            value="Analyze duo chemistry and performance\n└ Aliases: `!chemistry`, `!duo`\n└ Example: `!synergy carniee superboyy`",
            inline=False,
        )
        embed.add_field(
            name="`!best_duos [count]`",
            value="Show top performing player pairs\n└ Aliases: `!top_duos`, `!best_pairs`\n└ Example: `!best_duos 10`",
            inline=False,
        )
        embed.add_field(
            name="`!team_builder <players...>`",
            value="Build optimal teams from player list\n└ Aliases: `!tb`, `!build_teams`",
            inline=False,
        )
        embed.add_field(
            name="`!suggest_teams`",
            value="Auto-suggest balanced team compositions\n└ Aliases: `!suggest`, `!balance`, `!st`",
            inline=False,
        )
        embed.add_field(
            name="`!player_impact <player>`",
            value="Analyze player's impact on teammates\n└ Aliases: `!teammates`, `!partners`",
            inline=False,
        )
        embed.add_field(
            name="`!recalculate_synergies`",
            value="🔒 Admin: Recalculate synergy data",
            inline=False,
        )
        return embed

    def _help_server(self) -> discord.Embed:
        """Generate server control help embed"""
        embed = discord.Embed(
            title="🖥️ Server Control Commands",
            description="Game server management (requires permissions)",
            color=0xE74C3C,
        )
        embed.add_field(
            name="`!server_status`",
            value="View game server status\n└ Aliases: `!status`, `!srv_status`",
            inline=False,
        )
        embed.add_field(
            name="`!server_start`",
            value="🔒 Start the game server\n└ Aliases: `!start`, `!srv_start`",
            inline=False,
        )
        embed.add_field(
            name="`!server_stop`",
            value="🔒 Stop the game server\n└ Aliases: `!stop`, `!srv_stop`",
            inline=False,
        )
        embed.add_field(
            name="`!server_restart`",
            value="🔒 Restart the game server\n└ Aliases: `!restart`, `!srv_restart`",
            inline=False,
        )
        embed.add_field(
            name="`!list_maps`",
            value="List available maps\n└ Aliases: `!map_list`, `!listmaps`",
            inline=False,
        )
        embed.add_field(
            name="`!addmap`",
            value="🔒 Upload a new map (attach .pk3)\n└ Aliases: `!map_add`, `!upload_map`",
            inline=False,
        )
        embed.add_field(
            name="`!changemap <mapname>`",
            value="🔒 Change current map\n└ Aliases: `!map_change`, `!map`",
            inline=False,
        )
        embed.add_field(
            name="`!rcon <command>`",
            value="🔒 Execute RCON command",
            inline=False,
        )
        embed.add_field(
            name="`!kick <player>` / `!say <message>`",
            value="🔒 Kick player / Send server message",
            inline=False,
        )
        return embed

    def _help_players(self) -> discord.Embed:
        """Generate player linking help embed"""
        embed = discord.Embed(
            title="👤 Player Linking Commands",
            description="Link your Discord account to your ET player name",
            color=0x3498DB,
        )
        embed.add_field(
            name="`!list_players [page]`",
            value="Show all registered players\n└ Aliases: `!players`, `!lp`",
            inline=False,
        )
        embed.add_field(
            name="`!find_player <name>`",
            value="Search for a player by name\n└ Aliases: `!findplayer`, `!fp`, `!search_player`",
            inline=False,
        )
        embed.add_field(
            name="`!link <guid|name>`",
            value="Link your Discord to an ET player",
            inline=False,
        )
        embed.add_field(
            name="`!unlink`",
            value="Unlink your Discord from ET player",
            inline=False,
        )
        embed.add_field(
            name="`!select <number>`",
            value="Select player when multiple matches found",
            inline=False,
        )
        embed.add_field(
            name="`!setname <newname>`",
            value="Set your preferred display name",
            inline=False,
        )
        embed.add_field(
            name="`!myaliases`",
            value="View all your linked player aliases\n└ Aliases: `!aliases`, `!mynames`",
            inline=False,
        )
        return embed

    def _help_admin(self) -> discord.Embed:
        """Generate admin commands help embed"""
        embed = discord.Embed(
            title="⚙️ Admin Commands",
            description="🔒 Requires administrator permissions",
            color=0x95A5A6,
        )
        embed.add_field(
            name="**Sync Commands**",
            value=(
                "`!sync_stats` - Sync stats from game server\n"
                "`!sync_today` - Sync last 24 hours\n"
                "`!sync_week` - Sync last 7 days\n"
                "`!sync_month` - Sync last 30 days\n"
                "`!sync_all` - Full sync (slow)"
            ),
            inline=False,
        )
        embed.add_field(
            name="**Cache & System**",
            value=(
                "`!cache_clear` - Clear stats cache\n"
                "`!reload <cog>` - Reload a cog module\n"
                "`!weapon_diag` - Weapon diagnostics"
            ),
            inline=False,
        )
        embed.add_field(
            name="**Prediction Admin**",
            value=(
                "`!admin_predictions` - Admin prediction panel\n"
                "`!update_prediction_outcome` - Update results\n"
                "`!recalculate_predictions` - Recalc all predictions\n"
                "`!prediction_performance` - System performance"
            ),
            inline=False,
        )
        embed.add_field(
            name="**FiveEyes System**",
            value=(
                "`!fiveeyes_enable` - Enable FiveEyes tracking\n"
                "`!fiveeyes_disable` - Disable FiveEyes"
            ),
            inline=False,
        )
        return embed

    def _help_automation(self) -> discord.Embed:
        """Generate automation commands help embed"""
        embed = discord.Embed(
            title="🤖 Automation Commands",
            description="Bot health and automated systems",
            color=0x1ABC9C,
        )
        embed.add_field(
            name="`!health`",
            value="View bot health and system status",
            inline=False,
        )
        embed.add_field(
            name="`!ssh_stats`",
            value="SSH connection statistics",
            inline=False,
        )
        embed.add_field(
            name="`!automation_status`",
            value="View all automation services status",
            inline=False,
        )
        embed.add_field(
            name="`!start_monitoring`",
            value="🔒 Start SSH monitoring service",
            inline=False,
        )
        embed.add_field(
            name="`!stop_monitoring`",
            value="🔒 Stop SSH monitoring service",
            inline=False,
        )
        embed.add_field(
            name="`!metrics_report`",
            value="Detailed metrics report",
            inline=False,
        )
        embed.add_field(
            name="`!metrics_summary`",
            value="Quick metrics overview",
            inline=False,
        )
        embed.add_field(
            name="`!backup_db`",
            value="🔒 Create database backup",
            inline=False,
        )
        embed.add_field(
            name="`!vacuum_db`",
            value="🔒 Optimize database (vacuum)",
            inline=False,
        )
        embed.add_field(
            name="`!ping`",
            value="Check bot latency",
            inline=False,
        )
        return embed
