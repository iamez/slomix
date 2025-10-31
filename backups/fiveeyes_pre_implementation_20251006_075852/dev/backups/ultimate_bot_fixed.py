#!/usr/bin/env python3
"""
🚀 ULTIMATE ET:LEGACY DISCORD BOT - COG-BASED VERSION
====================================================

Fixed version using proper Cog pattern for discord.py 2.3.x
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
            name="🔧 System",
            value="• `!ping` - Bot status\\n• `!help_command` - This help",
            inline=False
        )
        
        await ctx.send(embed=embed)


class UltimateETLegacyBot(commands.Bot):
    """🚀 Ultimate consolidated ET:Legacy Discord bot with proper Cog structure"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
        
        # 📊 Database Configuration
        self.db_path = './etlegacy_perfect.db'
        
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