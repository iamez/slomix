#!/usr/bin/env python3
"""
🚀 ULTIMATE ET:LEGACY DISCORD BOT - COG-BASED VERSION
====================================================

Fixed version using proper Cog patt          embed.add_field(
            name="📊 Stats Commands",
            value=(
                "• `!stats [player]` - Player statistics\\n"
                "• `!leaderboard [type]` - Rankings (kills/kd/dpm/acc/hs)\\n"
                "• `!session [date]` - Match details"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔗 Account",
            value="• `!link <name>` - Link your account\\n• `!unlink` - Unlink",
            inline=False
        )
        
        embed.add_field(
            name="🔧 System",
            value="• `!ping` - Bot status\\n• `!session_start/end` - Manage sessions",
            inline=False
        )
        
        await ctx.send(embed=embed)ld(
            name="📊 Stats Commands",
            value=(
                "• `!stats [player]` - Player statistics\\n"
                "• `!leaderboard [type]` - Top players (kills/kd/dpm/acc/hs)\\n"
                "• `!session [date]` - Session details"
            ),
            inline=False
        )or discord.py 2.3.x
All commands now properly register and work correctly.
"""

import os
import asyncio
import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiosqlite
import logging
import paramiko
import datetime
import time
import re
import glob
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Union

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️  python-dotenv not installed. Using environment variables directly.")

# Setup comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/ultimate_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('UltimateBot')


class ETLegacyCommands(commands.Cog):
    """🎮 ET:Legacy Bot Commands Cog"""
    
    def __init__(self, bot):
        self.bot = bot
    
    # 🎮 SESSION MANAGEMENT COMMANDS
    
    @commands.command(name='session_start')
    async def session_start(self, ctx, *, map_name: str = "Unknown"):
        """🎬 Start a new gaming session"""
        try:
            if self.bot.current_session:
                await ctx.send("❌ A session is already active. End it first with `!session_end`")
                return
                
            now = datetime.now()
            date_str = now.strftime('%Y-%m-%d')
            time_str = now.strftime('%H:%M:%S')
            
            async with aiosqlite.connect(self.bot.db_path) as db:
                cursor = await db.execute('''
                    INSERT INTO sessions (start_time, date, map_name, status)
                    VALUES (?, ?, ?, 'active')
                ''', (time_str, date_str, map_name))
                
                session_id = cursor.lastrowid
                self.bot.current_session = session_id
                await db.commit()
                
            embed = discord.Embed(
                title="🎬 Session Started!",
                description=f"**Map:** {map_name}\\n**Started:** {time_str}\\n**Session ID:** {session_id}",
                color=0x00ff00,
                timestamp=now
            )
            await ctx.send(embed=embed)
            logger.info(f"Session {session_id} started on {map_name}")
            
        except Exception as e:
            logger.error(f"Error starting session: {e}")
            await ctx.send(f"❌ Error starting session: {e}")

    @commands.command(name='session_end')
    async def session_end(self, ctx):
        """🏁 End the current gaming session"""
        try:
            if not self.bot.current_session:
                await ctx.send("❌ No active session to end.")
                return
                
            now = datetime.now()
            time_str = now.strftime('%H:%M:%S')
            
            async with aiosqlite.connect(self.bot.db_path) as db:
                # Update session end time
                await db.execute('''
                    UPDATE sessions 
                    SET end_time = ?, status = 'completed'
                    WHERE id = ?
                ''', (time_str, self.bot.current_session))
                
                # Get session stats
                async with db.execute('''
                    SELECT COUNT(*) as rounds, map_name, start_time
                    FROM sessions s
                    LEFT JOIN player_stats ps ON s.id = ps.session_id
                    WHERE s.id = ?
                ''', (self.bot.current_session,)) as cursor:
                    session_data = await cursor.fetchone()
                
                await db.commit()
                
            embed = discord.Embed(
                title="🏁 Session Ended!",
                description=f"**Session ID:** {self.bot.current_session}\\n**Duration:** {session_data[2]} - {time_str}\\n**Rounds Played:** {session_data[0] or 0}",
                color=0xff0000,
                timestamp=now
            )
            
            self.bot.current_session = None
            await ctx.send(embed=embed)
            logger.info(f"Session ended at {time_str}")
            
        except Exception as e:
            logger.error(f"Error ending session: {e}")
            await ctx.send(f"❌ Error ending session: {e}")

    @commands.command(name='ping')
    async def ping(self, ctx):
        """🏓 Check bot status and performance"""
        try:
            start_time = time.time()
            
            # Test database connection
            async with aiosqlite.connect(self.bot.db_path) as db:
                await db.execute('SELECT 1')
                
            db_latency = (time.time() - start_time) * 1000
            
            embed = discord.Embed(
                title="🏓 Ultimate Bot Status",
                color=0x00ff00
            )
            embed.add_field(name="Bot Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
            embed.add_field(name="DB Latency", value=f"{round(db_latency)}ms", inline=True)
            embed.add_field(name="Active Session", value="Yes" if self.bot.current_session else "No", inline=True)
            embed.add_field(name="Commands", value=f"{len(list(self.bot.commands))}", inline=True)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in ping command: {e}")
            await ctx.send(f"❌ Bot error: {e}")

    @commands.command(name='help_command')
    async def help_command(self, ctx):
        """📚 Show all available commands"""
        embed = discord.Embed(
            title="🚀 Ultimate ET:Legacy Bot Commands",
            description="**Use `!` prefix for all commands** (e.g., `!ping`, not `/ping`)",
            color=0x0099ff
        )
        
        embed.add_field(
            name="🎬 Session Management",
            value="• `!session_start [map]` - Start new session\\n• `!session_end` - End current session",
            inline=False
        )
        
        embed.add_field(
            name="� Stats Commands",
            value="• `!stats [player]` - Player statistics\\n• `!leaderboard [type]` - Top players\\n• `!session [date]` - Session details",
            inline=False
        )
        
        embed.add_field(
            name="�🔧 System",
            value="• `!ping` - Bot status\\n• `!help_command` - This help",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @commands.command(name='stats')
    async def stats(self, ctx, *, player_name: str = None):
        """📊 Show detailed player statistics"""
        try:
            # If no player specified, try to use their linked account
            if not player_name:
                discord_id = str(ctx.author.id)
                async with aiosqlite.connect(self.bot.db_path) as db:
                    async with db.execute('''
                        SELECT player_name FROM player_links 
                        WHERE discord_id = ?
                    ''', (discord_id,)) as cursor:
                        result = await cursor.fetchone()
                        if not result:
                            await ctx.send("❌ Please specify a player name or link your account with `!link [name]`")
                            return
                        player_name = result[0]
            
            # Search for player in database
            async with aiosqlite.connect(self.bot.db_path) as db:
                # Try exact match on primary name first
                async with db.execute('''
                    SELECT player_guid, player_name FROM player_links 
                    WHERE LOWER(player_name) = LOWER(?)
                    LIMIT 1
                ''', (player_name,)) as cursor:
                    link = await cursor.fetchone()
                
                if link:
                    player_guid = link[0]
                    primary_name = link[1]
                else:
                    # Search in actual stats (handles aliases)
                    async with db.execute('''
                        SELECT player_guid, player_name 
                        FROM player_comprehensive_stats
                        WHERE LOWER(player_name) LIKE LOWER(?)
                        GROUP BY player_guid
                        LIMIT 1
                    ''', (f'%{player_name}%',)) as cursor:
                        result = await cursor.fetchone()
                        if not result:
                            await ctx.send(f"❌ Player '{player_name}' not found in database.")
                            return
                        player_guid = result[0]
                        primary_name = result[1]
                
                # Get overall stats
                async with db.execute('''
                    SELECT 
                        COUNT(DISTINCT session_id) as total_games,
                        SUM(kills) as total_kills,
                        SUM(deaths) as total_deaths,
                        SUM(damage_given) as total_damage,
                        SUM(damage_received) as total_damage_received,
                        SUM(headshot_kills) as total_headshots,
                        CASE 
                            WHEN SUM(time_played_seconds) > 0 
                            THEN (SUM(damage_given) * 60.0) / SUM(time_played_seconds)
                            ELSE 0 
                        END as weighted_dpm,
                        AVG(kd_ratio) as avg_kd
                    FROM player_comprehensive_stats
                    WHERE player_guid = ?
                ''', (player_guid,)) as cursor:
                    overall = await cursor.fetchone()
                
                # Get weapon stats with accuracy
                async with db.execute('''
                    SELECT 
                        SUM(w.hits) as total_hits,
                        SUM(w.shots) as total_shots,
                        SUM(w.headshots) as total_hs
                    FROM weapon_comprehensive_stats w
                    WHERE w.player_guid = ?
                ''', (player_guid,)) as cursor:
                    weapon_overall = await cursor.fetchone()
                
                # Get favorite weapons
                async with db.execute('''
                    SELECT weapon_name, SUM(kills) as total_kills
                    FROM weapon_comprehensive_stats
                    WHERE player_guid = ?
                    GROUP BY weapon_name
                    ORDER BY total_kills DESC
                    LIMIT 3
                ''', (player_guid,)) as cursor:
                    fav_weapons = await cursor.fetchall()
                
                # Get recent activity
                async with db.execute('''
                    SELECT s.session_date, s.map_name, p.kills, p.deaths
                    FROM player_comprehensive_stats p
                    JOIN sessions s ON p.session_id = s.id
                    WHERE p.player_guid = ?
                    ORDER BY s.session_date DESC
                    LIMIT 3
                ''', (player_guid,)) as cursor:
                    recent = await cursor.fetchall()
            
            # Calculate stats
            games, kills, deaths, dmg, dmg_recv, hs, avg_dpm, avg_kd = overall
            hits, shots, hs_weapon = weapon_overall if weapon_overall else (0, 0, 0)
            
            kd_ratio = kills / deaths if deaths > 0 else kills
            accuracy = (hits / shots * 100) if shots > 0 else 0
            hs_pct = (hs / hits * 100) if hits > 0 else 0
            
            # Get special flag if exists
            async with aiosqlite.connect(self.bot.db_path) as db:
                async with db.execute('''
                    SELECT special_flag FROM player_links 
                    WHERE player_guid = ?
                ''', (player_guid,)) as cursor:
                    flag_result = await cursor.fetchone()
                    special_flag = flag_result[0] if flag_result and flag_result[0] else ""
            
            # Build embed
            embed = discord.Embed(
                title=f"📊 Stats for {primary_name} {special_flag}",
                color=0x0099ff,
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="🎮 Overview",
                value=f"**Games Played:** {games:,}\\n**K/D Ratio:** {kd_ratio:.2f}\\n**Avg DPM:** {avg_dpm:.1f}" if avg_dpm else "0.0",
                inline=True
            )
            
            embed.add_field(
                name="⚔️ Combat",
                value=f"**Kills:** {kills:,}\\n**Deaths:** {deaths:,}\\n**Headshots:** {hs:,} ({hs_pct:.1f}%)",
                inline=True
            )
            
            embed.add_field(
                name="🎯 Accuracy",
                value=f"**Overall:** {accuracy:.1f}%\\n**Damage Given:** {dmg:,}\\n**Damage Taken:** {dmg_recv:,}",
                inline=True
            )
            
            if fav_weapons:
                weapons_text = "\\n".join([f"**{w[0].replace('WS_', '').title()}:** {w[1]:,} kills" for w in fav_weapons])
                embed.add_field(
                    name="🔫 Favorite Weapons",
                    value=weapons_text,
                    inline=False
                )
            
            if recent:
                recent_text = "\\n".join([f"`{r[0]}` **{r[1]}** - {r[2]}K/{r[3]}D" for r in recent])
                embed.add_field(
                    name="📅 Recent Matches",
                    value=recent_text,
                    inline=False
                )
            
            embed.set_footer(text=f"GUID: {player_guid}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in stats command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving stats: {e}")

    @commands.command(name='leaderboard', aliases=['lb', 'top'])
    async def leaderboard(self, ctx, stat_type: str = 'kills'):
        """🏆 Show top 10 players leaderboard
        
        Available stat types:
        - kills: Total kills
        - kd: Kill/Death ratio
        - dpm: Damage per minute
        - accuracy/acc: Overall accuracy
        - headshots/hs: Headshot percentage
        - games: Games played
        """
        try:
            stat_type = stat_type.lower()
            
            # Map aliases to stat types
            stat_aliases = {
                'k': 'kills',
                'kill': 'kills',
                'kd': 'kd',
                'ratio': 'kd',
                'dpm': 'dpm',
                'damage': 'dpm',
                'acc': 'accuracy',
                'accuracy': 'accuracy',
                'hs': 'headshots',
                'headshot': 'headshots',
                'headshots': 'headshots',
                'games': 'games',
                'played': 'games'
            }
            
            stat_type = stat_aliases.get(stat_type, 'kills')
            
            async with aiosqlite.connect(self.bot.db_path) as db:
                if stat_type == 'kills':
                    query = '''
                        SELECT p.player_name,
                               SUM(p.kills) as total_kills,
                               SUM(p.deaths) as total_deaths,
                               COUNT(DISTINCT p.session_id) as games
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid, p.player_name
                        HAVING games > 10
                        ORDER BY total_kills DESC
                        LIMIT 10
                    '''
                    title = "🏆 Top 10 Players by Kills"
                    
                elif stat_type == 'kd':
                    query = '''
                        SELECT p.player_name,
                               SUM(p.kills) as total_kills,
                               SUM(p.deaths) as total_deaths,
                               COUNT(DISTINCT p.session_id) as games
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid, p.player_name
                        HAVING games > 50 AND total_deaths > 0
                        ORDER BY (CAST(total_kills AS FLOAT) / total_deaths) DESC
                        LIMIT 10
                    '''
                    title = "🏆 Top 10 Players by K/D Ratio"
                    
                elif stat_type == 'dpm':
                    query = '''
                        SELECT p.player_name,
                               CASE 
                                   WHEN SUM(p.time_played_seconds) > 0 
                                   THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                                   ELSE 0 
                               END as weighted_dpm,
                               SUM(p.kills) as total_kills,
                               COUNT(DISTINCT p.session_id) as games
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid, p.player_name
                        HAVING games > 50
                        ORDER BY weighted_dpm DESC
                        LIMIT 10
                    '''
                    title = "🏆 Top 10 Players by DPM"
                    
                elif stat_type == 'accuracy':
                    query = '''
                        SELECT p.player_name,
                               SUM(w.hits) as total_hits,
                               SUM(w.shots) as total_shots,
                               SUM(p.kills) as total_kills,
                               COUNT(DISTINCT p.session_id) as games
                        FROM player_comprehensive_stats p
                        JOIN weapon_comprehensive_stats w 
                            ON p.session_id = w.session_id 
                            AND p.player_guid = w.player_guid
                        GROUP BY p.player_guid, p.player_name
                        HAVING games > 50 AND total_shots > 1000
                        ORDER BY (CAST(total_hits AS FLOAT) / total_shots) DESC
                        LIMIT 10
                    '''
                    title = "🏆 Top 10 Players by Accuracy"
                    
                elif stat_type == 'headshots':
                    query = '''
                        SELECT p.player_name,
                               SUM(p.headshot_kills) as total_hs,
                               SUM(w.hits) as total_hits,
                               SUM(p.kills) as total_kills,
                               COUNT(DISTINCT p.session_id) as games
                        FROM player_comprehensive_stats p
                        JOIN weapon_comprehensive_stats w 
                            ON p.session_id = w.session_id 
                            AND p.player_guid = w.player_guid
                        GROUP BY p.player_guid, p.player_name
                        HAVING games > 50 AND total_hits > 1000
                        ORDER BY (CAST(total_hs AS FLOAT) / total_hits) DESC
                        LIMIT 10
                    '''
                    title = "🏆 Top 10 Players by Headshot %"
                    
                elif stat_type == 'games':
                    query = '''
                        SELECT p.player_name,
                               COUNT(DISTINCT p.session_id) as games,
                               SUM(p.kills) as total_kills,
                               SUM(p.deaths) as total_deaths
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid, p.player_name
                        ORDER BY games DESC
                        LIMIT 10
                    '''
                    title = "🏆 Top 10 Most Active Players"
                
                async with db.execute(query) as cursor:
                    results = await cursor.fetchall()
            
            if not results:
                await ctx.send(f"❌ No data found for leaderboard type: {stat_type}")
                return
            
            # Build embed
            embed = discord.Embed(
                title=title,
                color=0xFFD700,  # Gold color
                timestamp=datetime.now()
            )
            
            # Format results based on stat type
            leaderboard_text = ""
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
            
            for i, row in enumerate(results):
                medal = medals[i]
                name = row[0]
                
                if stat_type == 'kills':
                    kills, deaths, games = row[1], row[2], row[3]
                    kd = kills / deaths if deaths > 0 else kills
                    leaderboard_text += f"{medal} **{name}** - {kills:,}K ({kd:.2f} K/D, {games} games)\\n"
                    
                elif stat_type == 'kd':
                    kills, deaths, games = row[1], row[2], row[3]
                    kd = kills / deaths if deaths > 0 else kills
                    leaderboard_text += f"{medal} **{name}** - {kd:.2f} K/D ({kills:,}K/{deaths:,}D, {games} games)\\n"
                    
                elif stat_type == 'dpm':
                    avg_dpm, kills, games = row[1], row[2], row[3]
                    leaderboard_text += f"{medal} **{name}** - {avg_dpm:.1f} DPM ({kills:,}K, {games} games)\\n"
                    
                elif stat_type == 'accuracy':
                    hits, shots, kills, games = row[1], row[2], row[3], row[4]
                    acc = (hits / shots * 100) if shots > 0 else 0
                    leaderboard_text += f"{medal} **{name}** - {acc:.1f}% Acc ({kills:,}K, {games} games)\\n"
                    
                elif stat_type == 'headshots':
                    hs, hits, kills, games = row[1], row[2], row[3], row[4]
                    hs_pct = (hs / hits * 100) if hits > 0 else 0
                    leaderboard_text += f"{medal} **{name}** - {hs_pct:.1f}% HS ({hs:,} HS, {games} games)\\n"
                    
                elif stat_type == 'games':
                    games, kills, deaths = row[1], row[2], row[3]
                    kd = kills / deaths if deaths > 0 else kills
                    leaderboard_text += f"{medal} **{name}** - {games:,} games ({kills:,}K, {kd:.2f} K/D)\\n"
            
            embed.description = leaderboard_text
            
            # Add usage footer
            embed.set_footer(text="💡 Use !leaderboard [kills|kd|dpm|accuracy|headshots|games]")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in leaderboard command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving leaderboard: {e}")

    @commands.command(name='session', aliases=['match', 'game'])
    async def session(self, ctx, date_filter: str = None):
        """📅 Show detailed session/match statistics
        
        Usage:
        - !session 2025-09-30  (show sessions from specific date)
        - !session  (show most recent sessions)
        """
        try:
            if not date_filter:
                # Get most recent date
                async with aiosqlite.connect(self.bot.db_path) as db:
                    async with db.execute('''
                        SELECT session_date FROM sessions 
                        ORDER BY session_date DESC LIMIT 1
                    ''') as cursor:
                        result = await cursor.fetchone()
                        if not result:
                            await ctx.send("❌ No sessions found in database")
                            return
                        date_filter = result[0][:10]  # Get YYYY-MM-DD part
            
            async with aiosqlite.connect(self.bot.db_path) as db:
                # Get sessions for the date
                async with db.execute('''
                    SELECT id, session_date, map_name, round_number, 
                           time_limit, actual_time
                    FROM sessions
                    WHERE session_date LIKE ?
                    ORDER BY session_date DESC
                    LIMIT 5
                ''', (f'{date_filter}%',)) as cursor:
                    sessions = await cursor.fetchall()
                
                if not sessions:
                    await ctx.send(f"❌ No sessions found for date: {date_filter}")
                    return
                
                # Show first session in detail (limit message size)
                session = sessions[0]
                session_id, date, map_name, round_num, time_limit, actual_time = session
                
                # Get player count
                async with db.execute('''
                    SELECT COUNT(*) FROM player_comprehensive_stats
                    WHERE session_id = ?
                ''', (session_id,)) as cursor:
                    player_count = (await cursor.fetchone())[0]
                
                # Get top 5 players
                async with db.execute('''
                    SELECT p.player_name, p.kills, p.deaths, p.dpm,
                           SUM(w.hits) as total_hits, SUM(w.shots) as total_shots,
                           p.headshot_kills
                    FROM player_comprehensive_stats p
                    LEFT JOIN weapon_comprehensive_stats w 
                        ON p.session_id = w.session_id 
                        AND p.player_guid = w.player_guid
                    WHERE p.session_id = ?
                    GROUP BY p.player_name, p.kills, p.deaths, p.dpm, p.headshot_kills
                    ORDER BY p.kills DESC
                    LIMIT 5
                ''', (session_id,)) as cursor:
                    top_players = await cursor.fetchall()
                
                # Get team stats
                async with db.execute('''
                    SELECT team, SUM(kills) as total_kills, SUM(deaths) as total_deaths,
                           SUM(damage_given) as total_damage
                    FROM player_comprehensive_stats
                    WHERE session_id = ?
                    GROUP BY team
                ''', (session_id,)) as cursor:
                    team_stats = await cursor.fetchall()
            
            # Build embed
            embed = discord.Embed(
                title=f"📍 Session #{session_id}: {map_name}",
                description=f"**Round {round_num}** • {actual_time} duration • {player_count} players",
                color=0x00ff88,
                timestamp=datetime.now()
            )
            
            # Top performers
            if top_players:
                top_text = ""
                medals = ["🥇", "🥈", "🥉", "4.", "5."]
                for i, (name, kills, deaths, dpm, hits, shots, hs) in enumerate(top_players):
                    kd_str = f"{kills}/{deaths}"
                    acc = (hits / shots * 100) if shots and shots > 0 else 0
                    hs_pct = (hs / hits * 100) if hits and hits > 0 else 0
                    dpm_str = f"{dpm:.0f}" if dpm else "0"
                    top_text += f"{medals[i]} **{name}** - {kd_str} K/D ({dpm_str} DPM, {acc:.1f}% acc, {hs_pct:.1f}% HS)\\n"
                
                embed.add_field(
                    name="🏆 Top 5 Players",
                    value=top_text,
                    inline=False
                )
            
            # Team stats
            if len(team_stats) > 1:
                team_text = ""
                for team, kills, deaths, damage in team_stats:
                    if team == 1:
                        team_name = "Axis"
                        emoji = "🔴"
                    elif team == 2:
                        team_name = "Allies"
                        emoji = "🔵"
                    else:
                        team_name = f"Team {team}"
                        emoji = "⚪"
                    team_text += f"{emoji} **{team_name}**: {kills}K / {deaths}D ({damage:,} dmg)\\n"
                
                embed.add_field(
                    name="⚔️ Team Statistics",
                    value=team_text,
                    inline=False
                )
            
            # Show count of other sessions
            if len(sessions) > 1:
                other_sessions = "\\n".join([
                    f"• Session #{s[0]}: {s[2]} (Round {s[3]})" 
                    for s in sessions[1:]
                ])
                embed.add_field(
                    name=f"📋 Other Sessions on {date_filter}",
                    value=other_sessions,
                    inline=False
                )
            
            embed.set_footer(text=f"Date: {date}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in session command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving session: {e}")

    @commands.command(name='last_session', aliases=['last', 'latest', 'recent'])
    async def last_session(self, ctx):
        """🎮 Show the most recent session/match
        
        Displays detailed stats for the latest played session (full day).
        A session = one day of gaming with all maps/rounds.
        """
        try:
            async with aiosqlite.connect(self.bot.db_path) as db:
                # Get the most recent date
                async with db.execute('''
                    SELECT DISTINCT session_date as date
                    FROM sessions
                    ORDER BY date DESC
                    LIMIT 1
                ''') as cursor:
                    result = await cursor.fetchone()
                
                if not result:
                    await ctx.send("❌ No sessions found in database")
                    return
                
                latest_date = result[0]
                
                # Get all session IDs for this date
                async with db.execute('''
                    SELECT id, map_name, round_number, actual_time
                    FROM sessions
                    WHERE session_date = ?
                    ORDER BY session_date
                ''', (latest_date,)) as cursor:
                    sessions = await cursor.fetchall()
                
                if not sessions:
                    await ctx.send("❌ No sessions found for latest date")
                    return
                
                session_ids = [s[0] for s in sessions]
                session_ids_str = ','.join('?' * len(session_ids))
                
                # Get unique player count across all sessions
                query = f'''
                    SELECT COUNT(DISTINCT player_guid) 
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                '''
                async with db.execute(query, session_ids) as cursor:
                    player_count = (await cursor.fetchone())[0]
                
                # Get top 5 players (aggregated across all rounds)
                # Calculate WEIGHTED DPM using actual playtime per round
                query = f'''
                    SELECT p.player_name, 
                           SUM(p.kills) as kills, 
                           SUM(p.deaths) as deaths,
                           CASE 
                               WHEN SUM(p.time_played_seconds) > 0 
                               THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                               ELSE 0 
                           END as weighted_dpm,
                           COALESCE(SUM(w.hits), 0) as total_hits, 
                           COALESCE(SUM(w.shots), 0) as total_shots,
                           COALESCE(SUM(w.headshots), 0) as total_headshots,
                           SUM(p.headshot_kills) as headshot_kills,
                           SUM(p.time_played_seconds) as total_seconds
                    FROM player_comprehensive_stats p
                    LEFT JOIN (
                        SELECT session_id, player_guid, 
                               SUM(hits) as hits, 
                               SUM(shots) as shots, 
                               SUM(headshots) as headshots
                        FROM weapon_comprehensive_stats
                        GROUP BY session_id, player_guid
                    ) w ON p.session_id = w.session_id AND p.player_guid = w.player_guid
                    WHERE p.session_id IN ({session_ids_str})
                    GROUP BY p.player_name
                    ORDER BY kills DESC
                    LIMIT 5
                '''
                async with db.execute(query, session_ids) as cursor:
                    top_players = await cursor.fetchall()
                
                # Get team stats (aggregated)
                query = f'''
                    SELECT team, 
                           SUM(kills) as total_kills, 
                           SUM(deaths) as total_deaths,
                           SUM(damage_given) as total_damage
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                    GROUP BY team
                '''
                async with db.execute(query, session_ids) as cursor:
                    team_stats = await cursor.fetchall()
                
                # Get detailed weapon stats (individual weapons)
                query = f'''
                    SELECT weapon_name,
                           SUM(kills) as total_kills,
                           SUM(deaths) as total_deaths,
                           SUM(hits) as total_hits,
                           SUM(shots) as total_shots,
                           SUM(headshots) as total_headshots
                    FROM weapon_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                    GROUP BY weapon_name
                    HAVING total_kills > 0
                    ORDER BY total_kills DESC
                '''
                async with db.execute(query, session_ids) as cursor:
                    weapon_details = await cursor.fetchall()
                
                # Get per-player weapon mastery
                query = f'''
                    SELECT p.player_name,
                           w.weapon_name,
                           SUM(w.kills) as weapon_kills,
                           SUM(w.hits) as weapon_hits,
                           SUM(w.shots) as weapon_shots,
                           SUM(w.headshots) as weapon_headshots
                    FROM weapon_comprehensive_stats w
                    JOIN player_comprehensive_stats p
                        ON w.session_id = p.session_id
                        AND w.player_guid = p.player_guid
                    WHERE w.session_id IN ({session_ids_str})
                    GROUP BY p.player_name, w.weapon_name
                    HAVING weapon_kills > 0
                    ORDER BY p.player_name, weapon_kills DESC
                '''
                async with db.execute(query, session_ids) as cursor:
                    player_weapons = await cursor.fetchall()
                
                # Get DPM leaderboard (weighted by actual playtime)
                query = f'''
                    SELECT player_name, 
                           CASE 
                               WHEN SUM(time_played_seconds) > 0 
                               THEN (SUM(damage_given) * 60.0) / SUM(time_played_seconds)
                               ELSE 0 
                           END as weighted_dpm,
                           SUM(kills) as total_kills,
                           SUM(deaths) as total_deaths
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                    GROUP BY player_name
                    ORDER BY weighted_dpm DESC
                    LIMIT 10
                '''
                async with db.execute(query, session_ids) as cursor:
                    dpm_leaders = await cursor.fetchall()
                
                # Get team composition - who played for which team
                query = f'''
                    SELECT player_name, team, COUNT(*) as rounds_played
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                    GROUP BY player_name, team
                    ORDER BY player_name, rounds_played DESC
                '''
                async with db.execute(query, session_ids) as cursor:
                    team_composition = await cursor.fetchall()
                
                # Assign random team names
                import random
                team_name_pool = [
                    'puran', 'insAne', 'sWat', 'maDdogs', 'slomix', 'slo'
                ]
                
                # Get all unique players and their primary team
                player_primary_teams = {}
                for player, team, rounds in team_composition:
                    if player not in player_primary_teams:
                        player_primary_teams[player] = team
                
                # Separate players by team
                team_1_players_list = [
                    p for p, t in player_primary_teams.items() if t == 1
                ]
                team_2_players_list = [
                    p for p, t in player_primary_teams.items() if t == 2
                ]
                
                # Randomly assign team names
                random.shuffle(team_name_pool)
                team_1_name = team_name_pool[0] if team_name_pool else 'Team 1'
                team_2_name = team_name_pool[1] if len(team_name_pool) > 1 else 'Team 2'
                
                # Detect team swaps - players who played for multiple teams
                player_teams = {}
                for player, team, rounds in team_composition:
                    if player not in player_teams:
                        player_teams[player] = []
                    player_teams[player].append((team, rounds))
                
                team_swappers = {
                    player: teams
                    for player, teams in player_teams.items()
                    if len(teams) > 1
                }
                
                # Get MVP per team
                query = f'''
                    SELECT team, player_name, SUM(kills) as total_kills
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                    GROUP BY team, player_name
                    ORDER BY team, total_kills DESC
                '''
                async with db.execute(query, session_ids) as cursor:
                    team_mvps_raw = await cursor.fetchall()
                
                # Get top player per team
                team_mvps = {}
                for team, player, kills in team_mvps_raw:
                    if team not in team_mvps:
                        team_mvps[team] = (player, kills)
                
                # Get MVP stats for both teams NOW (before closing connection)
                axis_mvp_stats = None
                allies_mvp_stats = None
                
                if 1 in team_mvps:
                    player, kills = team_mvps[1]
                    query = f'''
                        SELECT 
                            CASE 
                                WHEN SUM(time_played_seconds) > 0 
                                THEN (SUM(damage_given) * 60.0) / SUM(time_played_seconds)
                                ELSE 0 
                            END as weighted_dpm,
                            SUM(deaths),
                            SUM(times_revived),
                            SUM(gibs)
                        FROM player_comprehensive_stats
                        WHERE session_id IN ({session_ids_str})
                        AND player_name = ? AND team = 1
                    '''
                    async with db.execute(query, session_ids + [player]) as cursor:
                        result = await cursor.fetchone()
                        if result:
                            axis_mvp_stats = (player, kills, result[0], result[1], result[2], result[3])
                
                if 2 in team_mvps:
                    player, kills = team_mvps[2]
                    query = f'''
                        SELECT 
                            CASE 
                                WHEN SUM(time_played_seconds) > 0 
                                THEN (SUM(damage_given) * 60.0) / SUM(time_played_seconds)
                                ELSE 0 
                            END as weighted_dpm,
                            SUM(deaths),
                            SUM(times_revived),
                            SUM(gibs)
                        FROM player_comprehensive_stats
                        WHERE session_id IN ({session_ids_str})
                        AND player_name = ? AND team = 2
                    '''
                    async with db.execute(query, session_ids + [player]) as cursor:
                        result = await cursor.fetchone()
                        if result:
                            allies_mvp_stats = (player, kills, result[0], result[1], result[2], result[3])
                
                # Count rounds won by each team (winners determined by session data)
                # For now, we'll count based on team performance
                # This is a simplified version - you might want to track actual round winners
                axis_rounds = sum(1 for s in sessions if s[2] % 2 == 1)  # Odd rounds
                allies_rounds = sum(1 for s in sessions if s[2] % 2 == 0)  # Even rounds
                
                # Fetch awards/objective stats data (MUST BE BEFORE CONNECTION CLOSES)
                query = f'''
                    SELECT clean_name, xp, kill_assists, objectives_stolen, objectives_returned,
                           dynamites_planted, dynamites_defused, times_revived,
                           double_kills, triple_kills, quad_kills
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                '''
                async with db.execute(query, session_ids) as cursor:
                    awards_data = await cursor.fetchall()
                
                # Fetch player revives for weapon mastery embed
                query = f'''
                    SELECT player_name, SUM(times_revived) as revives
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                    GROUP BY player_name
                '''
                async with db.execute(query, session_ids) as cursor:
                    player_revives_raw = await cursor.fetchall()
            
            # ═══════════════════════════════════════════════════════
            # All database queries complete - connection closed
            # Now build and send embeds
            # ═══════════════════════════════════════════════════════
            
            # ═══════════════════════════════════════════════════════
            # MESSAGE 1: Session Overview
            # ═══════════════════════════════════════════════════════
            maps_played = len(set(s[1] for s in sessions))
            rounds_played = len(sessions)
            
            embed1 = discord.Embed(
                title=f"📊 Session Summary: {latest_date}",
                description=(
                    f"**{maps_played} maps** • **{rounds_played} rounds** • "
                    f"**{player_count} players**"
                ),
                color=0x5865F2,
                timestamp=datetime.now()
            )
            
            # Maps list
            maps_text = ""
            for map_name, count in sorted(
                [(m, len([s for s in sessions if s[1] == m])) 
                 for m in set(s[1] for s in sessions)],
                key=lambda x: x[1], reverse=True
            ):
                maps_text += f"• **{map_name}** ({count} round{'s' if count > 1 else ''})\n"
            
            if maps_text:
                embed1.add_field(
                    name="🗺️ Maps Played",
                    value=maps_text,
                    inline=False
                )
            
            # Top performers on embed1
            if top_players:
                top_text = ""
                medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
                for i, player in enumerate(top_players):
                    name, kills, deaths, dpm, hits, shots = player[0:6]
                    total_hs, hsk, total_seconds = player[6:9]
                    
                    # Handle NULL values from database
                    kills = kills or 0
                    deaths = deaths or 0
                    dpm = dpm or 0
                    hits = hits or 0
                    shots = shots or 0
                    total_hs = total_hs or 0
                    hsk = hsk or 0
                    total_seconds = total_seconds or 0
                    
                    # Convert seconds to MM:SS format
                    minutes = int(total_seconds // 60)
                    seconds = int(total_seconds % 60)
                    time_display = f"{minutes}:{seconds:02d}"
                    
                    # Calculate metrics
                    kd_ratio = kills / deaths if deaths > 0 else kills
                    acc = (hits / shots * 100) if shots and shots > 0 else 0
                    # HSK rate = headshot kills / total kills
                    hsk_rate = (hsk / kills * 100) if kills and kills > 0 else 0
                    # HS rate = headshots / hits
                    hs_rate = (total_hs / hits * 100) if hits and hits > 0 else 0
                    
                    top_text += f"{medals[i]} **{name}**\n"
                    # Line 1: Core combat stats
                    top_text += (
                        f"`{kills}K/{deaths}D ({kd_ratio:.2f})` • "
                        f"`{dpm:.0f} DPM` • "
                        f"`{acc:.1f}% ACC ({hits}/{shots})`\n"
                    )
                    # Line 2: Advanced stats (with playtime, no XP for now)
                    top_text += (
                        f"`{hsk} HSK ({hsk_rate:.1f}%)` • "
                        f"`{total_hs} HS ({hs_rate:.1f}%)` • "
                        f"`{time_display}`\n\n"
                    )
                
                embed1.add_field(
                    name="🏆 Top 5 Players",
                    value=top_text.rstrip(),
                    inline=False
                )
            
            embed1.set_footer(text=f"Session: {latest_date}")
            await ctx.send(embed=embed1)
            await asyncio.sleep(2)  # Rate limit protection
            
            # ═══════════════════════════════════════════════════════
            # GENERATE BEAUTIFUL SESSION OVERVIEW IMAGE
            # ═══════════════════════════════════════════════════════
            try:
                from image_generator import StatsImageGenerator
                
                generator = StatsImageGenerator()
                
                # Prepare session data
                session_info = {
                    'date': latest_date,
                    'maps': maps_played,
                    'rounds': rounds_played,
                    'players': player_count
                }
                
                # Prepare top players data
                top_players_data = []
                for player in top_players:
                    name, kills, deaths, dpm, hits, shots = player[0:6]
                    total_hs, hsk, total_seconds = player[6:9]
                    
                    kd_ratio = kills / deaths if deaths and deaths > 0 else (kills or 0)
                    acc = (hits / shots * 100) if shots and shots > 0 else 0
                    hsk_rate = (hsk / kills * 100) if kills and kills > 0 else 0
                    hs_rate = (total_hs / hits * 100) if hits and hits > 0 else 0
                    
                    # Convert seconds to minutes for playtime display
                    playtime_minutes = (total_seconds or 0) / 60.0
                    
                    top_players_data.append({
                        'name': name,
                        'kills': kills,
                        'deaths': deaths,
                        'kd': kd_ratio,
                        'dpm': dpm,
                        'acc': acc,
                        'hits': hits,
                        'shots': shots,
                        'hsk': hsk,
                        'hsk_rate': hsk_rate,
                        'hs': total_hs,
                        'hs_rate': hs_rate,
                        'playtime': playtime_minutes
                    })
                
                # Prepare team data for image
                team_data_for_img = {'team1': {}, 'team2': {}}
                
                for team, kills, deaths, damage in team_stats:
                    kd = kills / deaths if deaths > 0 else kills
                    team_info = {
                        'kills': kills,
                        'deaths': deaths,
                        'kd': kd,
                        'damage': damage
                    }
                    
                    if team == 1:
                        team_data_for_img['team1'] = team_info
                        if axis_mvp_stats:
                            p, k, dpm, d, revived, gibs = axis_mvp_stats
                            team_data_for_img['team1']['mvp'] = {
                                'name': p,
                                'kd': k / d if d else k,
                                'dpm': dpm
                            }
                    elif team == 2:
                        team_data_for_img['team2'] = team_info
                        if allies_mvp_stats:
                            p, k, dpm, d, revived, gibs = allies_mvp_stats
                            team_data_for_img['team2']['mvp'] = {
                                'name': p,
                                'kd': k / d if d else k,
                                'dpm': dpm
                            }
                
                # Generate the beautiful image!
                img_buf = generator.create_session_overview(
                    session_info,
                    top_players_data,
                    team_data_for_img,
                    (team_1_name, team_2_name)
                )
                
                file = discord.File(img_buf, filename='session_overview.png')
                await ctx.send(
                    "🎨 **Session Overview**",
                    file=file
                )
                
            except Exception as e:
                logger.error(f"Error generating session image: {e}",
                           exc_info=True)
            
            # ═══════════════════════════════════════════════════════
            # MESSAGE 2: Team Analytics
            # ═══════════════════════════════════════════════════════
            embed2 = discord.Embed(
                title=f"⚔️ Team Analytics - {team_1_name} vs {team_2_name}",
                description="Enhanced team performance with proper scoring",
                color=0xED4245,
                timestamp=datetime.now()
            )
            
            # Team stats
            if len(team_stats) > 1:
                team_text = ""
                for team, kills, deaths, damage in team_stats:
                    if team == 1:
                        current_team_name = team_1_name
                        emoji = "🔴"
                    elif team == 2:
                        current_team_name = team_2_name
                        emoji = "🔵"
                    else:
                        continue
                    kd_ratio = kills / deaths if deaths > 0 else kills
                    team_text += f"{emoji} **{current_team_name}**\n"
                    team_text += (
                        f"`{kills:,} Kills` • `{deaths:,} Deaths` • "
                        f"`{kd_ratio:.2f} K/D` • `{damage:,} DMG`\n\n"
                    )
                
                embed2.add_field(
                    name="📊 Final Score",
                    value=team_text.rstrip(),
                    inline=False
                )
            
            # Team MVPs (using pre-fetched stats)
            if axis_mvp_stats:
                player, kills, dpm, deaths, revives, gibs = axis_mvp_stats
                kd = kills / deaths if deaths else kills
                axis_mvp_text = (
                    f"**{player}**\n"
                    f"💀 `{kd:.1f} K/D` ({kills}K/{deaths}D)\n"
                    f"💥 `{dpm:.0f} DPM`\n"
                    f"💉 `{revives} Revives` • 🦴 `{gibs} Gibs`"
                )
                embed2.add_field(
                    name=f"🔴 {team_1_name} MVP",
                    value=axis_mvp_text,
                    inline=True
                )
            
            if allies_mvp_stats:
                player, kills, dpm, deaths, revives, gibs = allies_mvp_stats
                kd = kills / deaths if deaths else kills
                allies_mvp_text = (
                    f"**{player}**\n"
                    f"💀 `{kd:.1f} K/D` ({kills}K/{deaths}D)\n"
                    f"💥 `{dpm:.0f} DPM`\n"
                    f"💉 `{revives} Revives` • 🦴 `{gibs} Gibs`"
                )
                embed2.add_field(
                    name=f"🔵 {team_2_name} MVP",
                    value=allies_mvp_text,
                    inline=True
                )
            
            embed2.set_footer(text=f"Session: {latest_date}")
            await ctx.send(embed=embed2)
            await asyncio.sleep(4)  # Rate limit protection
            
            # ═══════════════════════════════════════════════════════
            # MESSAGE 3: Team Composition
            # ═══════════════════════════════════════════════════════
            embed3 = discord.Embed(
                title="👥 Team Composition",
                description=(
                    f"Who played for {team_1_name} and {team_2_name} "
                    "(🔄 = swapped teams)"
                ),
                color=0x57F287,
                timestamp=datetime.now()
            )
            
            # Organize players by primary team
            axis_players = []
            allies_players = []
            
            for player, teams in player_teams.items():
                primary_team, primary_rounds = teams[0]
                
                if primary_team == 1:
                    axis_players.append((player, primary_rounds, len(teams) > 1))
                elif primary_team == 2:
                    allies_players.append((player, primary_rounds, len(teams) > 1))
            
            axis_players.sort(key=lambda x: x[1], reverse=True)
            allies_players.sort(key=lambda x: x[1], reverse=True)
            
            # Axis team
            if axis_players:
                axis_text = ""
                for player, rounds, swapped in axis_players[:15]:
                    swap_indicator = " 🔄" if swapped else ""
                    axis_text += f"• {player}{swap_indicator}\n"
                if len(axis_players) > 15:
                    axis_text += f"*...and {len(axis_players) - 15} more*"
                embed3.add_field(
                    name="� Axis Team",
                    value=axis_text.rstrip(),
                    inline=True
                )
            
            # Allies team
            if allies_players:
                allies_text = ""
                for player, rounds, swapped in allies_players[:15]:
                    swap_indicator = " 🔄" if swapped else ""
                    allies_text += f"• {player}{swap_indicator}\n"
                if len(allies_players) > 15:
                    allies_text += f"*...and {len(allies_players) - 15} more*"
                embed3.add_field(
                    name="� Allies Team",
                    value=allies_text.rstrip(),
                    inline=True
                )
            
            # Team swaps
            if team_swappers:
                swap_text = ""
                for player, teams in list(team_swappers.items())[:10]:
                    team_names = []
                    for team, rounds in teams:
                        if team == 1:
                            team_names.append(f"🔴({rounds}r)")
                        elif team == 2:
                            team_names.append(f"🔵({rounds}r)")
                    swap_text += f"• **{player}**: {' → '.join(team_names)}\n"
                embed3.add_field(
                    name="🔄 Team Swaps",
                    value=swap_text.rstrip(),
                    inline=False
                )
            
            embed3.set_footer(text=f"Session: {latest_date}")
            await ctx.send(embed=embed3)
            await asyncio.sleep(8)  # Rate limit protection
            
            # ═══════════════════════════════════════════════════════
            # MESSAGE 4: DPM Analytics
            # ═══════════════════════════════════════════════════════
            embed4 = discord.Embed(
                title="💥 DPM Analytics - Damage Per Minute",
                description="Enhanced DPM with Kill/Death Details",
                color=0xFEE75C,
                timestamp=datetime.now()
            )
            
            # DPM Leaderboard
            if dpm_leaders:
                dpm_text = ""
                for i, (player, dpm, kills, deaths) in enumerate(dpm_leaders[:10], 1):
                    kd = kills / deaths if deaths else kills
                    dpm_text += f"{i}. **{player}**\n"
                    dpm_text += f"   💥 `{dpm:.0f} DPM` • 💀 `{kd:.1f} K/D` ({kills}K/{deaths}D)\n"
                
                embed4.add_field(
                    name="🏆 Enhanced DPM Leaderboard",
                    value=dpm_text.rstrip(),
                    inline=False
                )
            
            # DPM Insights
            if dpm_leaders:
                avg_dpm = sum(p[1] for p in dpm_leaders) / len(dpm_leaders)
                highest_dpm = dpm_leaders[0][1] if dpm_leaders else 0
                leader_name = dpm_leaders[0][0] if dpm_leaders else "N/A"
                
                insights = (
                    f"📊 **Enhanced Session DPM Stats:**\n"
                    f"• Average DPM: `{avg_dpm:.1f}`\n"
                    f"• Highest DPM: `{highest_dpm:.0f}`\n"
                    f"• DPM Leader: **{leader_name}**"
                )
                embed4.add_field(
                    name="💥 DPM Insights",
                    value=insights,
                    inline=False
                )
            
            embed4.set_footer(text="💥 Enhanced with Kill/Death Details")
            await ctx.send(embed=embed4)
            await asyncio.sleep(16)  # Rate limit protection
            
            # ═══════════════════════════════════════════════════════
            # MESSAGE 5: Weapon Mastery Breakdown (Text)
            # ═══════════════════════════════════════════════════════
            
            # Group by player and get their top weapons
            player_weapon_map = {}
            for player, weapon, kills, hits, shots, hs in player_weapons:
                if player not in player_weapon_map:
                    player_weapon_map[player] = []
                acc = (hits / shots * 100) if shots > 0 else 0
                hs_pct = (hs / hits * 100) if hits > 0 else 0
                weapon_clean = weapon.replace('WS_', '').replace('_', ' ').title()
                player_weapon_map[player].append(
                    (weapon_clean, kills, acc, hs_pct, hs, hits, shots)
                )
            
            # Convert revives data (already fetched before connection closed)
            player_revives = {player: revives for player, revives in player_revives_raw}
            
            # Sort players by total kills and take top 5
            player_totals = []
            for player, weapons in player_weapon_map.items():
                total_kills = sum(w[1] for w in weapons)
                player_totals.append((player, total_kills))
            player_totals.sort(key=lambda x: x[1], reverse=True)
            
            # Create text-based weapon breakdown
            embed5 = discord.Embed(
                title="🔫 Weapon Mastery Breakdown",
                description="Top weapons and combat statistics",
                color=0x5865F2,
                timestamp=datetime.now()
            )
            
            for player, total_kills in player_totals[:5]:
                weapons = player_weapon_map[player][:3]  # Top 3 weapons
                revives = player_revives.get(player, 0)
                
                weapon_text = ""
                for weapon, kills, acc, hs_pct, hs, hits, shots in weapons:
                    weapon_text += f"**{weapon}**: `{kills}K` • `{acc:.1f}% ACC` • `{hs} HS ({hs_pct:.1f}%)`\n"
                
                weapon_text += f"\n💉 **Revives**: `{revives}`"
                
                embed5.add_field(
                    name=f"{player} ({total_kills} total kills)",
                    value=weapon_text,
                    inline=False
                )
            
            embed5.set_footer(text=f"Session: {latest_date}")
            await ctx.send(embed=embed5)
            await asyncio.sleep(2)
            
            # ═══════════════════════════════════════════════════════
            # MESSAGE 6: Objective & Support Stats
            # ═══════════════════════════════════════════════════════
            # Use awards_data that was already fetched before connection closed
            if awards_data:
                embed6 = discord.Embed(
                    title="🎯 Objective & Support Stats",
                    description="Comprehensive battlefield contributions",
                    color=0x00D166,
                    timestamp=datetime.now()
                )
                
                # Aggregate stats across all rounds per player
                # awards_data format: (clean_name, xp, kill_assists, obj_stolen, obj_returned,
                #                      dyn_planted, dyn_defused, times_revived, double, triple, quad)
                player_objectives = {}
                for row in awards_data:
                    player_name = row[0]
                    if player_name not in player_objectives:
                        player_objectives[player_name] = {
                            'xp': 0, 'assists': 0, 'obj_stolen': 0, 
                            'obj_returned': 0, 'dyn_planted': 0, 'dyn_defused': 0,
                            'revived': 0, 'multi_2x': 0, 'multi_3x': 0, 'multi_4x': 0
                        }
                    
                    # Accumulate stats from each round
                    player_objectives[player_name]['xp'] += row[1] or 0
                    player_objectives[player_name]['assists'] += row[2] or 0
                    player_objectives[player_name]['obj_stolen'] += row[3] or 0
                    player_objectives[player_name]['obj_returned'] += row[4] or 0
                    player_objectives[player_name]['dyn_planted'] += row[5] or 0
                    player_objectives[player_name]['dyn_defused'] += row[6] or 0
                    player_objectives[player_name]['revived'] += row[7] or 0
                    player_objectives[player_name]['multi_2x'] += row[8] or 0
                    player_objectives[player_name]['multi_3x'] += row[9] or 0
                    player_objectives[player_name]['multi_4x'] += row[10] or 0
                
                # Sort players by XP and show top 6
                sorted_players = sorted(
                    player_objectives.items(),
                    key=lambda x: x[1]['xp'],
                    reverse=True
                )[:6]
                
                for i, (player, stats) in enumerate(sorted_players, 1):
                    obj_text = f"**XP:** `{stats['xp']}`\n"
                    obj_text += f"**Assists:** `{stats['assists']}`\n"
                    
                    # Objectives
                    if stats['obj_stolen'] > 0 or stats['obj_returned'] > 0:
                        obj_text += f"**Objectives:** `{stats['obj_stolen']}/{stats['obj_returned']}` S/R\n"
                    
                    # Dynamites
                    if stats['dyn_planted'] > 0 or stats['dyn_defused'] > 0:
                        obj_text += f"**Dynamites:** `{stats['dyn_planted']}/{stats['dyn_defused']}` P/D\n"
                    
                    # Revived
                    if stats['revived'] > 0:
                        obj_text += f"**Revived:** `{stats['revived']}` times\n"
                    
                    # Multikills
                    multikills = []
                    if stats['multi_2x'] > 0:
                        multikills.append(f"2x: {stats['multi_2x']}")
                    if stats['multi_3x'] > 0:
                        multikills.append(f"3x: {stats['multi_3x']}")
                    if stats['multi_4x'] > 0:
                        multikills.append(f"4x: {stats['multi_4x']}")
                    if multikills:
                        obj_text += f"**Multikills:** `{', '.join(multikills)}`\n"
                    
                    embed6.add_field(
                        name=f"{i}. {player}",
                        value=obj_text.rstrip(),
                        inline=True
                    )
                
                embed6.set_footer(text="🎯 S/R = Stolen/Returned | P/D = Planted/Defused")
                await ctx.send(embed=embed6)
            
            # ═══════════════════════════════════════════════════════
            # MESSAGE 7: Visual Stats Graph
            # ═══════════════════════════════════════════════════════
            try:
                import matplotlib
                matplotlib.use('Agg')  # Non-interactive backend
                import matplotlib.pyplot as plt
                import io
                
                # Create a figure with 2 subplots
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
                fig.patch.set_facecolor('#2b2d31')
                
                # Get top 6 players for graphs
                top_6_players = player_totals[:6]
                names = [p[0] for p in top_6_players]
                
                # Gather data for each player
                player_data = {}
                for player_name in names:
                    # Get player's aggregated stats
                    query = f'''
                        SELECT SUM(p.kills) as kills,
                               SUM(p.deaths) as deaths,
                               SUM(p.damage_given) as damage,
                               CASE 
                                   WHEN SUM(p.time_played_seconds) > 0 
                                   THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                                   ELSE 0 
                               END as weighted_dpm,
                               SUM(w.hits) as hits
                        FROM player_comprehensive_stats p
                        LEFT JOIN weapon_comprehensive_stats w
                            ON p.session_id = w.session_id
                            AND p.player_guid = w.player_guid
                        WHERE p.session_id IN ({session_ids_str})
                        AND p.player_name = ?
                    '''
                    # Note: Can't execute query here as connection is closed
                    # We'll use data we already have
                    pass
                
                # Use data from top_players if available
                graph_data = []
                for player_name, total_kills in top_6_players:
                    # Find in top_players
                    player_stats = next(
                        (p for p in top_players if p[0] == player_name),
                        None
                    )
                    if player_stats:
                        name, kills, deaths, dpm, hits, shots, hs = player_stats
                        acc = (hits / shots * 100) if shots > 0 else 0
                        graph_data.append({
                            'name': name,
                            'kills': kills,
                            'deaths': deaths,
                            'dpm': dpm,
                            'accuracy': acc
                        })
                
                if graph_data:
                    names = [d['name'] for d in graph_data]
                    kills_data = [d['kills'] for d in graph_data]
                    deaths_data = [d['deaths'] for d in graph_data]
                    dpm_data = [d['dpm'] for d in graph_data]
                    
                    # Graph 1: Kills vs Deaths vs DPM
                    x = range(len(names))
                    width = 0.25
                    
                    ax1.bar([i - width for i in x], kills_data, width,
                           label='Kills', color='#5865f2', alpha=0.8)
                    ax1.bar(x, deaths_data, width,
                           label='Deaths', color='#ed4245', alpha=0.8)
                    ax1.bar([i + width for i in x], dpm_data, width,
                           label='DPM', color='#fee75c', alpha=0.8)
                    
                    ax1.set_ylabel('Value', color='white', fontsize=12)
                    ax1.set_title('Player Performance - Kills, Deaths, DPM',
                                 color='white', fontsize=14, fontweight='bold')
                    ax1.set_xticks(x)
                    ax1.set_xticklabels(names, rotation=15, ha='right',
                                       color='white')
                    ax1.legend(facecolor='#1e1f22', edgecolor='white',
                              labelcolor='white')
                    ax1.set_facecolor('#1e1f22')
                    ax1.tick_params(colors='white')
                    ax1.spines['bottom'].set_color('white')
                    ax1.spines['left'].set_color('white')
                    ax1.spines['top'].set_visible(False)
                    ax1.spines['right'].set_visible(False)
                    ax1.grid(True, alpha=0.2, color='white')
                    
                    # Add value labels on bars
                    for i, (k, d, dpm) in enumerate(zip(kills_data,
                                                        deaths_data,
                                                        dpm_data)):
                        ax1.text(i - width, k, str(int(k)), ha='center',
                                va='bottom', color='white', fontsize=9)
                        ax1.text(i, d, str(int(d)), ha='center',
                                va='bottom', color='white', fontsize=9)
                        ax1.text(i + width, dpm, str(int(dpm)), ha='center',
                                va='bottom', color='white', fontsize=9)
                    
                    # Graph 2: K/D Ratio and Accuracy
                    kd_ratios = [
                        d['kills'] / d['deaths'] if d['deaths'] > 0
                        else d['kills']
                        for d in graph_data
                    ]
                    accuracy_data = [d['accuracy'] for d in graph_data]
                    
                    ax2_twin = ax2.twinx()
                    
                    bars1 = ax2.bar([i - width/2 for i in x], kd_ratios,
                                   width, label='K/D Ratio',
                                   color='#57f287', alpha=0.8)
                    bars2 = ax2_twin.bar([i + width/2 for i in x],
                                        accuracy_data, width,
                                        label='Accuracy %',
                                        color='#eb459e', alpha=0.8)
                    
                    ax2.set_ylabel('K/D Ratio', color='white', fontsize=12)
                    ax2_twin.set_ylabel('Accuracy %', color='white',
                                       fontsize=12)
                    ax2.set_title('Player Efficiency - K/D and Accuracy',
                                 color='white', fontsize=14, fontweight='bold')
                    ax2.set_xticks(x)
                    ax2.set_xticklabels(names, rotation=15, ha='right',
                                       color='white')
                    
                    # Combine legends
                    lines1, labels1 = ax2.get_legend_handles_labels()
                    lines2, labels2 = ax2_twin.get_legend_handles_labels()
                    ax2.legend(lines1 + lines2, labels1 + labels2,
                              facecolor='#1e1f22', edgecolor='white',
                              labelcolor='white')
                    
                    ax2.set_facecolor('#1e1f22')
                    ax2.tick_params(colors='white')
                    ax2_twin.tick_params(colors='white')
                    ax2.spines['bottom'].set_color('white')
                    ax2.spines['left'].set_color('white')
                    ax2_twin.spines['right'].set_color('white')
                    ax2.spines['top'].set_visible(False)
                    ax2.grid(True, alpha=0.2, color='white', axis='y')
                    
                    # Add value labels
                    for i, (kd, acc) in enumerate(zip(kd_ratios,
                                                      accuracy_data)):
                        ax2.text(i - width/2, kd, f'{kd:.2f}',
                                ha='center', va='bottom',
                                color='white', fontsize=9)
                        ax2_twin.text(i + width/2, acc, f'{acc:.1f}%',
                                     ha='center', va='bottom',
                                     color='white', fontsize=9)
                    
                    plt.tight_layout()
                    
                    # Save to bytes buffer
                    buf = io.BytesIO()
                    plt.savefig(buf, format='png', facecolor='#2b2d31',
                               dpi=100, bbox_inches='tight')
                    buf.seek(0)
                    plt.close()
                    
                    # Send as Discord file
                    file = discord.File(buf, filename='session_stats.png')
                    await ctx.send(
                        "📊 **Visual Performance Analytics**",
                        file=file
                    )
                else:
                    logger.warning("No graph data available")
                    
            except ImportError:
                logger.warning("matplotlib not installed, skipping graphs")
            except Exception as e:
                logger.error(f"Error generating graphs: {e}", exc_info=True)
            
        except Exception as e:
            logger.error(f"Error in last_session command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving last session: {e}")

    @commands.command(name='link')
    async def link(self, ctx, *, player_name: str):
        """🔗 Link your Discord account to your in-game profile
        
        Usage: !link YourPlayerName
        """
        try:
            discord_id = str(ctx.author.id)
            
            # Check if already linked
            async with aiosqlite.connect(self.bot.db_path) as db:
                async with db.execute('''
                    SELECT player_name, player_guid FROM player_links 
                    WHERE discord_id = ?
                ''', (discord_id,)) as cursor:
                    existing = await cursor.fetchone()
                
                if existing:
                    await ctx.send(
                        f"⚠️ You're already linked to **{existing[0]}**\\n"
                        f"Use `!unlink` first to change your linked account."
                    )
                    return
                
                # Search for player
                async with db.execute('''
                    SELECT player_guid, player_name, 
                           SUM(kills) as total_kills,
                           COUNT(DISTINCT session_id) as games
                    FROM player_comprehensive_stats
                    WHERE LOWER(player_name) LIKE LOWER(?)
                    GROUP BY player_guid, player_name
                    ORDER BY games DESC
                    LIMIT 5
                ''', (f'%{player_name}%',)) as cursor:
                    matches = await cursor.fetchall()
                
                if not matches:
                    await ctx.send(
                        f"❌ No player found matching '{player_name}'\\n"
                        f"Make sure you've played at least one game!"
                    )
                    return
                
                if len(matches) > 1:
                    # Multiple matches - show options
                    match_list = "\\n".join([
                        f"{i+1}. **{m[1]}** ({m[3]} games, {m[2]:,} kills)" 
                        for i, m in enumerate(matches)
                    ])
                    await ctx.send(
                        f"🔍 Found multiple players matching '{player_name}'. Please be more specific or use exact name:\\n{match_list}"
                    )
                    return
                
                # Single match - link it
                player_guid, found_name, kills, games = matches[0]
                
                # Insert link
                await db.execute('''
                    INSERT OR REPLACE INTO player_links 
                    (discord_id, player_guid, player_name, linked_at)
                    VALUES (?, ?, ?, datetime('now'))
                ''', (discord_id, player_guid, found_name))
                
                await db.commit()
            
            # Success message
            embed = discord.Embed(
                title="🔗 Account Linked!",
                description=f"Successfully linked to **{found_name}**",
                color=0x00ff00
            )
            embed.add_field(
                name="Stats Preview",
                value=f"**Games:** {games:,}\\n**Kills:** {kills:,}",
                inline=True
            )
            embed.add_field(
                name="Quick Access",
                value="Use `!stats` without arguments to see your stats!",
                inline=False
            )
            embed.set_footer(text=f"GUID: {player_guid}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in link command: {e}", exc_info=True)
            await ctx.send(f"❌ Error linking account: {e}")

    @commands.command(name='unlink')
    async def unlink(self, ctx):
        """🔓 Unlink your Discord account from your in-game profile"""
        try:
            discord_id = str(ctx.author.id)
            
            async with aiosqlite.connect(self.bot.db_path) as db:
                # Check if linked
                async with db.execute('''
                    SELECT player_name FROM player_links 
                    WHERE discord_id = ?
                ''', (discord_id,)) as cursor:
                    existing = await cursor.fetchone()
                
                if not existing:
                    await ctx.send("❌ You don't have a linked account.")
                    return
                
                # Remove link
                await db.execute('''
                    UPDATE player_links 
                    SET discord_id = NULL 
                    WHERE discord_id = ?
                ''', (discord_id,))
                
                await db.commit()
            
            await ctx.send(f"✅ Unlinked from **{existing[0]}**")
            
        except Exception as e:
            logger.error(f"Error in unlink command: {e}", exc_info=True)
            await ctx.send(f"❌ Error unlinking account: {e}")


class UltimateETLegacyBot(commands.Bot):
    """🚀 Ultimate consolidated ET:Legacy Discord bot with proper Cog structure"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
        
        # 📊 Database Configuration
        # Use parent directory database (main stats database)
        import os
        bot_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(bot_dir)
        self.db_path = os.path.join(parent_dir, 'etlegacy_production.db')
        
        # 🔒 Safety check: Verify official database
        marker_file = self.db_path + '.OFFICIAL'
        if not os.path.exists(marker_file):
            logger.warning(f"⚠️  Official database marker not found!")
            logger.warning(f"   Expected: {marker_file}")
            logger.warning(f"   Run migrate_database.py to create fresh database")
        else:
            logger.info(f"✅ Using official database: {self.db_path}")
        
        # 🎮 Bot State
        self.current_session = None
        self.monitoring = False
        self.processed_files = set()
        self.auto_link_enabled = True
        self.gather_queue = {"3v3": [], "6v6": []}
        
        # 🏆 Awards and achievements tracking
        self.awards_cache = {}
        self.mvp_cache = {}
        
        # 📈 Performance tracking
        self.command_stats = {}
        self.error_count = 0
        
    async def setup_hook(self):
        """🔧 Initialize all bot components"""
        logger.info("🚀 Initializing Ultimate ET:Legacy Bot...")
        
        # Add the commands cog
        await self.add_cog(ETLegacyCommands(self))
        
        # Initialize database
        await self.initialize_database()
        
        # Start background tasks
        self.endstats_monitor.start()
        self.cache_refresher.start()
        
        logger.info("✅ Ultimate Bot initialization complete!")
        logger.info(f"📋 Commands available: {[cmd.name for cmd in self.commands]}")
        
    async def initialize_database(self):
        """📊 Initialize the ultimate database with all tables"""
        async with aiosqlite.connect(self.db_path) as db:
            # Core tables
            await db.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    date TEXT NOT NULL,
                    map_name TEXT,
                    status TEXT DEFAULT 'active',
                    total_rounds INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Player linking system
            await db.execute('''
                CREATE TABLE IF NOT EXISTS player_links (
                    discord_id TEXT PRIMARY KEY,
                    etlegacy_name TEXT NOT NULL,
                    display_name TEXT,
                    link_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    verified INTEGER DEFAULT 0,
                    total_matches INTEGER DEFAULT 0
                )
            ''')
            
            # Player stats
            await db.execute('''
                CREATE TABLE IF NOT EXISTS player_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    player_name TEXT NOT NULL,
                    discord_id TEXT,
                    round_type TEXT,
                    team TEXT,
                    kills INTEGER DEFAULT 0,
                    deaths INTEGER DEFAULT 0,
                    damage INTEGER DEFAULT 0,
                    time_played TEXT DEFAULT '0:00',
                    time_minutes REAL DEFAULT 0,
                    dpm REAL DEFAULT 0,
                    kd_ratio REAL DEFAULT 0,
                    mvp_points INTEGER DEFAULT 0,
                    weapon_stats TEXT,
                    achievements TEXT,
                    awards TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
            ''')
            
            await db.commit()
            logger.info("📊 Database tables initialized successfully")

    # 🔄 BACKGROUND TASKS

    @tasks.loop(seconds=30)
    async def endstats_monitor(self):
        """🔄 Monitor for new EndStats files"""
        if not self.monitoring:
            return
            
        try:
            # SSH connection logic here
            pass
            
        except Exception as e:
            logger.error(f"EndStats monitoring error: {e}")

    @tasks.loop(minutes=10)
    async def cache_refresher(self):
        """🔄 Refresh performance caches"""
        try:
            # Refresh awards and MVP caches
            self.awards_cache.clear()
            self.mvp_cache.clear()
            
        except Exception as e:
            logger.error(f"Cache refresh error: {e}")

    async def on_ready(self):
        """✅ Bot startup message"""
        logger.info(f'🚀 Ultimate ET:Legacy Bot logged in as {self.user}')
        logger.info(f'📊 Connected to database: {self.db_path}')
        logger.info(f'🎮 Bot ready with {len(list(self.commands))} commands!')
        
        # Clear any old slash commands to avoid confusion
        try:
            self.tree.clear_commands(guild=None)
            await self.tree.sync()
            logger.info("🧹 Cleared old slash commands")
        except Exception as e:
            logger.warning(f"Could not clear slash commands: {e}")

    async def on_command_error(self, ctx, error):
        """🚨 Handle command errors"""
        self.error_count += 1
        
        if isinstance(error, commands.CommandNotFound):
            await ctx.send("❌ Command not found. Use `!help_command` for available commands.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing argument: {error.param}. Use `!help_command` for usage.")
        else:
            logger.error(f"Command error: {error}")
            await ctx.send(f"❌ An error occurred: {error}")


# 🚀 BOT STARTUP
def main():
    """🚀 Start the Ultimate ET:Legacy Discord Bot"""
    
    # Get Discord token
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        logger.error("❌ DISCORD_BOT_TOKEN not found in environment variables!")
        logger.info("Please set your Discord bot token in the .env file")
        return
    
    # Create and run bot
    bot = UltimateETLegacyBot()
    
    try:
        logger.info("🚀 Starting Ultimate ET:Legacy Bot...")
        bot.run(token)
    except discord.LoginFailure:
        logger.error("❌ Invalid Discord token!")
    except Exception as e:
        logger.error(f"❌ Bot startup failed: {e}")


if __name__ == "__main__":
    main()

