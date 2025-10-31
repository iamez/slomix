#!/usr/bin/env python3
"""
🎯 COMPREHENSIVE ET:Legacy Discord Bot
====================================
Created in G:\VisualStudio\Python\stats\dev\ 

This bot captures and displays ALL data from C0RNP0RN3.lua including:
- All 28 weapons with individual kill/death/hit/attempt stats
- Killing sprees, death sprees, multikills (2-6 kills)
- Headshots, accuracy, damage given/received
- Team damage, self kills, playtime, XP
- DPM (Damage Per Minute), K/D ratios
- Hit regions (head, arms, body, legs)
- Objectives (flags, dynamite, revives, repairs)
- Tank/meatshield stats, death time ratios
- All the comprehensive data from the LUA script

Commands:
- !stats @user - Overall comprehensive stats
- !stats @user 30.9.2025 - Date-specific stats
- !session_stats 30.9 - All players from that session
- !link playername - Link Discord to ET:Legacy GUID
"""

import discord
from discord.ext import commands
import sqlite3
import os
import asyncio
from datetime import datetime, date
import logging
from typing import Optional, Dict, Any, List
import sys
import re

# Add the bot directory to path to import our parser
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'bot'))

try:
    from community_stats_parser import C0RNP0RN3StatsParser
except ImportError:
    print("❌ Could not import C0RNP0RN3StatsParser from bot directory")
    print("💡 Make sure community_stats_parser.py exists in the bot/ folder")
    sys.exit(1)

# Setup logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ComprehensiveETBot')

class ComprehensiveETLegacyBot(commands.Bot):
    """Main Discord bot that captures ALL C0RNP0RN3.lua data"""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
        
        # Database configuration
        self.db_path = "etlegacy_comprehensive.db"
        self.parser = C0RNP0RN3StatsParser()

    async def on_ready(self):
        logger.info(f'🤖 {self.user} is connected to Discord!')
        logger.info(f'📊 Using comprehensive database: {self.db_path}')
        
        # Initialize comprehensive database
        await self.initialize_comprehensive_database()

    async def initialize_comprehensive_database(self):
        """Create comprehensive database schema for ALL C0RNP0RN3.lua data"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Sessions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_date DATE NOT NULL,
                    map_name TEXT NOT NULL,
                    round_number INTEGER NOT NULL,
                    server_name TEXT,
                    config_name TEXT,
                    defender_team INTEGER,
                    winner_team INTEGER,
                    time_limit TEXT,
                    next_time_limit TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Comprehensive player stats - captures EVERYTHING from C0RNP0RN3.lua
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS player_comprehensive_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    player_guid TEXT NOT NULL,
                    player_name TEXT NOT NULL,
                    clean_name TEXT NOT NULL,
                    team INTEGER NOT NULL,
                    rounds INTEGER DEFAULT 0,
                    
                    -- Basic combat stats
                    kills INTEGER DEFAULT 0,
                    deaths INTEGER DEFAULT 0,
                    damage_given INTEGER DEFAULT 0,
                    damage_received INTEGER DEFAULT 0,
                    team_damage_given INTEGER DEFAULT 0,
                    team_damage_received INTEGER DEFAULT 0,
                    gibs INTEGER DEFAULT 0,
                    self_kills INTEGER DEFAULT 0,
                    team_kills INTEGER DEFAULT 0,
                    team_gibs INTEGER DEFAULT 0,
                    
                    -- Time and XP
                    time_axis INTEGER DEFAULT 0,
                    time_allies INTEGER DEFAULT 0,
                    time_played REAL DEFAULT 0.0,
                    time_played_minutes REAL DEFAULT 0.0,
                    xp INTEGER DEFAULT 0,
                    
                    -- Advanced analytics from topshots array
                    killing_spree_best INTEGER DEFAULT 0,          -- topshots[1]
                    death_spree_worst INTEGER DEFAULT 0,           -- topshots[2]
                    kill_assists INTEGER DEFAULT 0,               -- topshots[3]
                    kill_steals INTEGER DEFAULT 0,                -- topshots[4]
                    headshot_kills INTEGER DEFAULT 0,             -- topshots[5]
                    objectives_stolen INTEGER DEFAULT 0,          -- topshots[6]
                    objectives_returned INTEGER DEFAULT 0,        -- topshots[7]
                    dynamites_planted INTEGER DEFAULT 0,          -- topshots[8]
                    dynamites_defused INTEGER DEFAULT 0,          -- topshots[9]
                    times_revived INTEGER DEFAULT 0,              -- topshots[10]
                    bullets_fired INTEGER DEFAULT 0,              -- topshots[11]
                    dpm REAL DEFAULT 0.0,                         -- topshots[12]
                    tank_meatshield REAL DEFAULT 0.0,            -- topshots[13]
                    time_dead_ratio REAL DEFAULT 0.0,            -- topshots[14]
                    most_useful_kills INTEGER DEFAULT 0,          -- topshots[15]
                    denied_playtime INTEGER DEFAULT 0,            -- topshots[16] (ms)
                    useless_kills INTEGER DEFAULT 0,              -- topshots[17]
                    full_selfkills INTEGER DEFAULT 0,             -- topshots[18]
                    repairs_constructions INTEGER DEFAULT 0,      -- topshots[19]
                    
                    -- Multikills from multikills array
                    double_kills INTEGER DEFAULT 0,               -- multikills[1]
                    triple_kills INTEGER DEFAULT 0,               -- multikills[2]
                    quad_kills INTEGER DEFAULT 0,                 -- multikills[3]
                    penta_kills INTEGER DEFAULT 0,                -- multikills[4]
                    hexa_kills INTEGER DEFAULT 0,                 -- multikills[5]
                    
                    -- Calculated stats
                    kd_ratio REAL DEFAULT 0.0,
                    accuracy REAL DEFAULT 0.0,
                    headshot_percentage REAL DEFAULT 0.0,
                    efficiency REAL DEFAULT 0.0,
                    
                    -- Meta
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
            ''')
            
            # Comprehensive weapon stats - ALL 28 weapons from C0RNP0RN3.lua
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS weapon_comprehensive_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_stats_id INTEGER,
                    weapon_id INTEGER NOT NULL,
                    weapon_name TEXT NOT NULL,
                    
                    -- Weapon stats from aWeaponStats[j]
                    hits INTEGER DEFAULT 0,        -- atts in original (confusing naming)
                    attempts INTEGER DEFAULT 0,    -- atts in original 
                    kills INTEGER DEFAULT 0,
                    deaths INTEGER DEFAULT 0,
                    headshots INTEGER DEFAULT 0,
                    
                    -- Calculated weapon stats
                    accuracy REAL DEFAULT 0.0,
                    damage_dealt INTEGER DEFAULT 0,
                    
                    FOREIGN KEY (player_stats_id) REFERENCES player_comprehensive_stats (id)
                )
            ''')
            
            # Player linking for Discord integration
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS player_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    et_guid TEXT UNIQUE NOT NULL,
                    discord_id TEXT UNIQUE NOT NULL,
                    discord_username TEXT,
                    player_name TEXT,
                    linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Processed files tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processed_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT UNIQUE NOT NULL,
                    file_hash TEXT,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info("✅ Comprehensive database schema created successfully")
            
        except Exception as e:
            logger.error(f"❌ Error creating comprehensive database: {e}")

class ComprehensiveStatsCommands(commands.Cog):
    """Discord commands for comprehensive ET:Legacy stats"""

    def __init__(self, bot):
        self.bot = bot
        self.db_path = bot.db_path

    def get_player_guid_by_mention(self, user_mention: str) -> Optional[str]:
        """Convert Discord mention to ET:Legacy GUID"""
        try:
            # Extract user ID from mention
            user_id = user_mention.replace('<@', '').replace('>', '').replace('!', '')
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT et_guid FROM player_links WHERE discord_id = ?", (user_id,))
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"Error getting GUID for mention {user_mention}: {e}")
            return None

    def get_comprehensive_player_stats(self, player_guid: str, date_filter: Optional[str] = None) -> Dict[str, Any]:
        """Get ALL comprehensive player statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Base query for comprehensive stats
            base_query = """
                SELECT 
                    clean_name,
                    COUNT(*) as sessions_played,
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths,
                    SUM(damage_given) as total_damage_given,
                    SUM(damage_received) as total_damage_received,
                    SUM(headshot_kills) as total_headshots,
                    SUM(bullets_fired) as total_shots,
                    AVG(dpm) as avg_dpm,
                    AVG(accuracy) as avg_accuracy,
                    AVG(kd_ratio) as avg_kd,
                    MAX(killing_spree_best) as best_killing_spree,
                    MAX(death_spree_worst) as worst_death_spree,
                    SUM(kill_assists) as total_assists,
                    SUM(kill_steals) as total_steals,
                    SUM(objectives_stolen) as total_obj_stolen,
                    SUM(objectives_returned) as total_obj_returned,
                    SUM(dynamites_planted) as total_dynamites_planted,
                    SUM(dynamites_defused) as total_dynamites_defused,
                    SUM(times_revived) as total_revived,
                    SUM(double_kills) as total_double_kills,
                    SUM(triple_kills) as total_triple_kills,
                    SUM(quad_kills) as total_quad_kills,
                    SUM(penta_kills) as total_penta_kills,
                    SUM(hexa_kills) as total_hexa_kills,
                    SUM(most_useful_kills) as total_useful_kills,
                    SUM(useless_kills) as total_useless_kills,
                    SUM(repairs_constructions) as total_repairs,
                    AVG(time_dead_ratio) as avg_time_dead_ratio,
                    AVG(tank_meatshield) as avg_tank_rating,
                    MAX(processed_at) as last_played
                FROM player_comprehensive_stats pcs
                JOIN sessions s ON pcs.session_id = s.id
                WHERE player_guid = ?
            """
            
            params = [player_guid]
            
            if date_filter:
                base_query += " AND DATE(s.session_date) = ?"
                params.append(date_filter)
            
            base_query += " GROUP BY player_guid"
            
            cursor.execute(base_query, params)
            result = cursor.fetchone()
            
            if not result:
                conn.close()
                return None
            
            # Get weapon stats
            weapon_query = """
                SELECT 
                    weapon_name,
                    SUM(kills) as weapon_kills,
                    SUM(hits) as weapon_hits,
                    SUM(attempts) as weapon_attempts,
                    SUM(headshots) as weapon_headshots,
                    AVG(accuracy) as weapon_accuracy
                FROM weapon_comprehensive_stats wcs
                JOIN player_comprehensive_stats pcs ON wcs.player_stats_id = pcs.id
                JOIN sessions s ON pcs.session_id = s.id
                WHERE pcs.player_guid = ?
            """
            
            if date_filter:
                weapon_query += " AND DATE(s.session_date) = ?"
            
            weapon_query += " GROUP BY weapon_name ORDER BY SUM(kills) DESC LIMIT 5"
            
            cursor.execute(weapon_query, params)
            weapons = cursor.fetchall()
            
            conn.close()
            
            # Calculate additional stats
            headshot_percentage = 0
            if result[2] > 0:  # total_kills
                headshot_percentage = (result[6] / result[2]) * 100
            
            # Build comprehensive stats object
            stats = {
                'player_name': result[0],
                'sessions_played': result[1],
                'total_kills': result[2],
                'total_deaths': result[3],
                'total_damage_given': result[4],
                'total_damage_received': result[5],
                'total_headshots': result[6],
                'total_shots': result[7],
                'avg_dpm': result[8] or 0,
                'avg_accuracy': result[9] or 0,
                'avg_kd': result[10] or 0,
                'best_killing_spree': result[11] or 0,
                'worst_death_spree': result[12] or 0,
                'total_assists': result[13] or 0,
                'total_steals': result[14] or 0,
                'total_obj_stolen': result[15] or 0,
                'total_obj_returned': result[16] or 0,
                'total_dynamites_planted': result[17] or 0,
                'total_dynamites_defused': result[18] or 0,
                'total_revived': result[19] or 0,
                'total_double_kills': result[20] or 0,
                'total_triple_kills': result[21] or 0,
                'total_quad_kills': result[22] or 0,
                'total_penta_kills': result[23] or 0,
                'total_hexa_kills': result[24] or 0,
                'total_useful_kills': result[25] or 0,
                'total_useless_kills': result[26] or 0,
                'total_repairs': result[27] or 0,
                'avg_time_dead_ratio': result[28] or 0,
                'avg_tank_rating': result[29] or 0,
                'last_played': result[30],
                'headshot_percentage': headshot_percentage,
                'top_weapons': weapons
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting comprehensive player stats: {e}")
            return None

    @commands.command(name='stats')
    async def comprehensive_stats_command(self, ctx, target: str = None, date: str = None):
        """
        Show comprehensive player statistics with ALL data from C0RNP0RN3.lua
        Usage: 
        !stats @username - Overall comprehensive stats
        !stats @username 30.9.2025 - Stats for specific date
        !stats playername - Stats by name
        """
        
        if not target:
            await ctx.send("❌ Please specify a player: `!stats @username` or `!stats playername`")
            return
        
        # Handle date parameter
        if target and not target.startswith('<@') and '.' in target and date is None:
            # Check if target contains a date
            parts = target.split()
            if len(parts) == 2:
                target, date = parts
        
        # Determine if it's a mention or name
        player_guid = None
        
        if target.startswith('<@'):
            # Discord mention
            player_guid = self.get_player_guid_by_mention(target)
            if not player_guid:
                await ctx.send(f"❌ {target} is not linked to any ET:Legacy player. Use `!link` command first.")
                return
        else:
            # Player name - look up GUID
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT player_guid FROM player_comprehensive_stats 
                    WHERE LOWER(clean_name) LIKE LOWER(?) 
                    GROUP BY player_guid
                    ORDER BY COUNT(*) DESC
                    LIMIT 1
                """, (f"%{target}%",))
                
                result = cursor.fetchone()
                conn.close()
                
                if not result:
                    await ctx.send(f"❌ Player '{target}' not found in database.")
                    return
                    
                player_guid = result[0]
                
            except Exception as e:
                logger.error(f"Error looking up player by name: {e}")
                await ctx.send("❌ Error looking up player.")
                return
        
        # Format date if provided
        date_filter = None
        if date:
            try:
                # Convert DD.MM.YYYY to YYYY-MM-DD
                if '.' in date:
                    parts = date.split('.')
                    if len(parts) == 2:
                        day, month = parts
                        year = str(datetime.now().year)  # Use current year
                    else:
                        day, month, year = parts
                    date_filter = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                else:
                    await ctx.send("❌ Invalid date format. Use DD.MM.YYYY or DD.MM")
                    return
            except ValueError:
                await ctx.send("❌ Invalid date format. Use DD.MM.YYYY (e.g., 30.9.2025)")
                return
        
        # Get comprehensive player stats
        stats = self.get_comprehensive_player_stats(player_guid, date_filter)
        
        if not stats:
            date_text = f" for {date}" if date else ""
            await ctx.send(f"❌ No stats found{date_text}.")
            return
        
        # Create comprehensive embed with ALL data
        embed = discord.Embed(
            title=f"📊 {stats['player_name']} - Comprehensive Stats",
            color=0x00ff00,
            timestamp=datetime.now()
        )
        
        if date:
            embed.description = f"Stats for {date}"
        else:
            embed.description = "Overall Comprehensive Statistics"
        
        # Main combat stats
        embed.add_field(
            name="⚔️ Combat Performance",
            value=f"**Kills:** {stats['total_kills']:,}\n"
                  f"**Deaths:** {stats['total_deaths']:,}\n"
                  f"**K/D Ratio:** {stats['avg_kd']:.2f}\n"
                  f"**Damage Given:** {stats['total_damage_given']:,}\n"
                  f"**DPM:** {stats['avg_dpm']:.1f}",
            inline=True
        )
        
        # Accuracy and headshots
        embed.add_field(
            name="🎯 Accuracy & Precision",
            value=f"**Headshots:** {stats['total_headshots']:,}\n"
                  f"**HS%:** {stats['headshot_percentage']:.1f}%\n"
                  f"**Accuracy:** {stats['avg_accuracy']:.1f}%\n"
                  f"**Shots Fired:** {stats['total_shots']:,}",
            inline=True
        )
        
        # Sprees and multikills
        embed.add_field(
            name="🔥 Sprees & Multikills",
            value=f"**Best Killing Spree:** {stats['best_killing_spree']}\n"
                  f"**Double Kills:** {stats['total_double_kills']}\n"
                  f"**Triple Kills:** {stats['total_triple_kills']}\n"
                  f"**Quad+ Kills:** {stats['total_quad_kills'] + stats['total_penta_kills'] + stats['total_hexa_kills']}",
            inline=True
        )
        
        # Objectives and teamwork
        embed.add_field(
            name="🏆 Objectives & Teamwork",
            value=f"**Assists:** {stats['total_assists']}\n"
                  f"**Dynamites Planted:** {stats['total_dynamites_planted']}\n"
                  f"**Dynamites Defused:** {stats['total_dynamites_defused']}\n"
                  f"**Times Revived:** {stats['total_revived']}\n"
                  f"**Repairs/Constructions:** {stats['total_repairs']}",
            inline=True
        )
        
        # Advanced analytics
        embed.add_field(
            name="📈 Advanced Analytics",
            value=f"**Useful Kills:** {stats['total_useful_kills']}\n"
                  f"**Kill Steals:** {stats['total_steals']}\n"
                  f"**Tank Rating:** {stats['avg_tank_rating']:.1f}\n"
                  f"**Sessions Played:** {stats['sessions_played']}",
            inline=True
        )
        
        # Top weapons
        if stats['top_weapons']:
            weapon_text = ""
            for weapon_name, kills, hits, attempts, hs, acc in stats['top_weapons'][:3]:
                weapon_text += f"**{weapon_name}:** {kills} kills\n"
            
            embed.add_field(
                name="🔫 Top Weapons",
                value=weapon_text,
                inline=True
            )
        
        # Footer
        if stats['last_played']:
            embed.set_footer(text=f"Last played: {stats['last_played'][:10]}")
        
        await ctx.send(embed=embed)

    @commands.command(name='link')
    async def link_command(self, ctx, *, player_name: str):
        """Link Discord account to ET:Legacy player"""
        
        try:
            # Find the player GUID
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT DISTINCT player_guid, clean_name 
                FROM player_comprehensive_stats 
                WHERE LOWER(clean_name) LIKE LOWER(?)
                GROUP BY player_guid
                ORDER BY COUNT(*) DESC
                LIMIT 5
            """, (f"%{player_name}%",))
            
            matches = cursor.fetchall()
            
            if not matches:
                await ctx.send(f"❌ No player found matching '{player_name}'")
                conn.close()
                return
            
            if len(matches) > 1:
                # Multiple matches, show options
                match_list = '\n'.join([f"• {match[1]}" for match in matches[:5]])
                await ctx.send(f"❌ Multiple players found. Be more specific:\n{match_list}")
                conn.close()
                return
            
            # Single match - create link
            player_guid, exact_name = matches[0]
            discord_id = str(ctx.author.id)
            discord_username = str(ctx.author)
            
            # Check if already linked
            cursor.execute("SELECT * FROM player_links WHERE discord_id = ?", (discord_id,))
            if cursor.fetchone():
                await ctx.send("❌ You are already linked to a player. Contact admin to change.")
                conn.close()
                return
            
            # Create link
            cursor.execute("""
                INSERT INTO player_links (et_guid, discord_id, discord_username, player_name, linked_at)
                VALUES (?, ?, ?, ?, ?)
            """, (player_guid, discord_id, discord_username, exact_name, datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
            await ctx.send(f"✅ Successfully linked {ctx.author.mention} to **{exact_name}**")
            
        except Exception as e:
            logger.error(f"Error linking player: {e}")
            await ctx.send("❌ Error creating link.")

    @commands.command(name='session_stats')
    async def session_stats_command(self, ctx, date: str = None):
        """
        Show session statistics for all players on a specific date
        Usage: !session_stats 30.9 or !session_stats 30.9.2025
        """
        
        if not date:
            await ctx.send("❌ Please specify a date: `!session_stats 30.9` or `!session_stats 30.9.2025`")
            return
        
        # Format date
        try:
            parts = date.split('.')
            if len(parts) == 2:
                day, month = parts
                year = str(datetime.now().year)
            else:
                day, month, year = parts
            
            date_filter = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            
        except ValueError:
            await ctx.send("❌ Invalid date format. Use DD.MM or DD.MM.YYYY")
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get session overview
            cursor.execute("""
                SELECT 
                    s.map_name,
                    s.round_number,
                    COUNT(DISTINCT pcs.player_guid) as player_count,
                    AVG(pcs.dpm) as avg_session_dpm,
                    SUM(pcs.kills) as total_kills,
                    s.winner_team
                FROM sessions s
                JOIN player_comprehensive_stats pcs ON s.id = pcs.session_id
                WHERE DATE(s.session_date) = ?
                GROUP BY s.id
                ORDER BY s.map_name, s.round_number
            """, (date_filter,))
            
            sessions = cursor.fetchall()
            
            if not sessions:
                await ctx.send(f"❌ No sessions found for {date}")
                conn.close()
                return
            
            # Create session summary embed
            embed = discord.Embed(
                title=f"📅 Session Stats for {date}",
                color=0x3498db,
                timestamp=datetime.now()
            )
            
            total_maps = len(sessions)
            total_players = sum(session[2] for session in sessions)
            avg_dpm = sum(session[3] for session in sessions) / len(sessions)
            total_kills = sum(session[4] for session in sessions)
            
            embed.description = f"**{total_maps}** maps played • **{total_players}** total players • **{avg_dpm:.1f}** avg DPM"
            
            # Show maps played
            maps_text = ""
            for map_name, round_num, players, dpm, kills, winner in sessions:
                team_text = "🔴 Axis" if winner == 1 else "🔵 Allies" if winner == 2 else "🤝 Draw"
                maps_text += f"**{map_name}** R{round_num} - {players}p, {dpm:.1f} DPM ({team_text})\n"
            
            embed.add_field(
                name="🗺️ Maps Played",
                value=maps_text[:1024],  # Discord field limit
                inline=False
            )
            
            # Get top performers
            cursor.execute("""
                SELECT 
                    clean_name,
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths,
                    AVG(dpm) as avg_dpm,
                    AVG(kd_ratio) as avg_kd
                FROM player_comprehensive_stats pcs
                JOIN sessions s ON pcs.session_id = s.id
                WHERE DATE(s.session_date) = ?
                GROUP BY player_guid
                ORDER BY total_kills DESC
                LIMIT 5
            """, (date_filter,))
            
            top_players = cursor.fetchall()
            
            if top_players:
                top_text = ""
                for i, (name, kills, deaths, dpm, kd) in enumerate(top_players, 1):
                    medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                    top_text += f"{medal} **{name}** - {kills}K/{deaths}D ({kd:.2f} K/D, {dpm:.1f} DPM)\n"
                
                embed.add_field(
                    name="🏆 Top Performers",
                    value=top_text,
                    inline=False
                )
            
            conn.close()
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting session stats: {e}")
            await ctx.send("❌ Error retrieving session stats.")

async def main():
    """Main bot runner"""
    
    # Load Discord token - check multiple locations
    token = None
    
    # Try environment variable first
    token = os.getenv('DISCORD_BOT_TOKEN')
    
    # Try loading from slomix_discord .env file
    if not token:
        env_path = os.path.join('..', 'slomix_discord', '.env')
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    if 'DISCORD_BOT_TOKEN=' in line and not line.strip().startswith('#'):
                        token = line.split('=', 1)[1].strip()
                        break
    
    if not token:
        logger.error("❌ DISCORD_BOT_TOKEN not found")
        logger.info("💡 Make sure the token is set as environment variable or in slomix_discord/.env file")
        return
    
    # Create and run comprehensive bot
    bot = ComprehensiveETLegacyBot()
    
    # Add comprehensive commands cog
    await bot.add_cog(ComprehensiveStatsCommands(bot))
    
    try:
        await bot.start(token)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot error: {e}")
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())