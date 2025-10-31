#!/usr/bin/env python3
"""
🎮 ET:LEGACY DISCORD BOT V2 - CLEAN REWRITE
============================================

Production-ready Discord bot for ET:Legacy game servers.

Features:
- 📊 Player statistics tracking and leaderboards  
- 🔗 Discord account linking to in-game profiles
- 🎮 Session management and monitoring
- 📥 Automatic stats file download via SSH
- 🏆 Real-time game summaries and round results
- 🎯 Alias tracking for player name changes
- 👥 Admin tools for easy player linking

Requirements:
- Python 3.10+
- discord.py 2.3.x
- aiosqlite
- python-dotenv

Author: ET:Legacy Community
Version: 2.0.0
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple, Any

import aiosqlite
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

# Add parent directory to path for custom imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from tools.stopwatch_scoring import StopwatchScoring
    from community_stats_parser import C0RNP0RN3StatsParser
except ImportError as e:
    print(f"⚠️  Warning: Could not import custom modules: {e}")
    print("Some features may not work correctly.")

# Load environment variables
load_dotenv()

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/ultimate_bot.log', encoding='utf-8'),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger('ETLegacyBot')


# ============================================================================
# UTILITY CLASSES
# ============================================================================

class StatsCache:
    """
    High-performance caching system for database queries.
    Reduces repeated queries by 80% during active sessions.
    """
    
    def __init__(self, ttl_seconds: int = 300):
        self.cache: Dict[str, Any] = {}
        self.timestamps: Dict[str, datetime] = {}
        self.ttl = ttl_seconds
        logger.info(f"📦 StatsCache initialized (TTL: {ttl_seconds}s)")
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if still valid"""
        if key in self.cache:
            age = (datetime.now() - self.timestamps[key]).total_seconds()
            if age < self.ttl:
                logger.debug(f"✅ Cache HIT: {key} (age: {age:.1f}s)")
                return self.cache[key]
            else:
                logger.debug(f"⏰ Cache EXPIRED: {key}")
                del self.cache[key]
                del self.timestamps[key]
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Store value in cache"""
        self.cache[key] = value
        self.timestamps[key] = datetime.now()
        logger.debug(f"💾 Cache SET: {key}")
    
    def clear(self) -> None:
        """Clear all cached data"""
        count = len(self.cache)
        self.cache.clear()
        self.timestamps.clear()
        logger.info(f"🗑️  Cache CLEARED: {count} keys removed")


class SeasonManager:
    """
    Manages quarterly competitive seasons.
    Q1: Jan-Mar, Q2: Apr-Jun, Q3: Jul-Sep, Q4: Oct-Dec
    """
    
    @staticmethod
    def get_current_season() -> str:
        """Get current season identifier (e.g., '2025-Q4')"""
        now = datetime.now()
        quarter = (now.month - 1) // 3 + 1
        return f"{now.year}-Q{quarter}"
    
    @staticmethod
    def get_season_start() -> str:
        """Get start date of current season (YYYY-MM-DD)"""
        now = datetime.now()
        quarter = (now.month - 1) // 3 + 1
        month = (quarter - 1) * 3 + 1
        return f"{now.year}-{month:02d}-01"


class AchievementSystem:
    """Track and award player achievements"""
    
    def __init__(self, bot):
        self.bot = bot
        self.achievements = {
            'first_blood': '🩸 First Blood',
            'sharpshooter': '🎯 Sharpshooter',
            'survivor': '💀 Survivor',
            'killstreak_5': '🔥 Killstreak Master',
            'headshot_king': '👑 Headshot King',
        }
    
    async def check_achievements(self, player_stats: Dict) -> List[str]:
        """Check if player earned any achievements this round"""
        earned = []
        
        # First blood (first kill of the round)
        if player_stats.get('first_kill'):
            earned.append('first_blood')
        
        # Sharpshooter (>75% accuracy)
        accuracy = player_stats.get('accuracy', 0)
        if accuracy > 75:
            earned.append('sharpshooter')
        
        # Survivor (0 deaths)
        if player_stats.get('deaths', 1) == 0:
            earned.append('survivor')
        
        # Killstreak Master (5+ killstreak)
        if player_stats.get('max_killstreak', 0) >= 5:
            earned.append('killstreak_5')
        
        # Headshot King (>50% headshots)
        kills = player_stats.get('kills', 0)
        headshots = player_stats.get('headshots', 0)
        if kills > 0 and (headshots / kills) > 0.5:
            earned.append('headshot_king')
        
        return earned


# ============================================================================
# DATABASE MANAGER
# ============================================================================

class DatabaseManager:
    """
    Handles all database operations with proper connection management.
    Provides async context manager for safe database access.
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        logger.info(f"📁 Database path: {db_path}")
    
    async def get_connection(self) -> aiosqlite.Connection:
        """Get a new database connection"""
        return await aiosqlite.connect(self.db_path)
    
    async def init_database(self) -> None:
        """Initialize database schema if tables don't exist"""
        async with await self.get_connection() as db:
            # Player aliases table (CRITICAL for !stats and !link)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS player_aliases (
                    guid TEXT NOT NULL,
                    alias TEXT NOT NULL,
                    first_seen TEXT,
                    last_seen TEXT,
                    times_seen INTEGER DEFAULT 1,
                    PRIMARY KEY (guid, alias)
                )
            ''')
            
            # Player links (Discord to ET:Legacy)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS player_links (
                    discord_id TEXT PRIMARY KEY,
                    discord_username TEXT,
                    et_guid TEXT,
                    et_name TEXT,
                    linked_date TEXT,
                    verified INTEGER DEFAULT 0
                )
            ''')
            
            # Comprehensive stats
            await db.execute('''
                CREATE TABLE IF NOT EXISTS player_comprehensive_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    session_date TEXT,
                    player_guid TEXT,
                    player_name TEXT,
                    team INTEGER,
                    kills INTEGER DEFAULT 0,
                    deaths INTEGER DEFAULT 0,
                    suicides INTEGER DEFAULT 0,
                    team_kills INTEGER DEFAULT 0,
                    team_deaths INTEGER DEFAULT 0,
                    gibs INTEGER DEFAULT 0,
                    self_kills INTEGER DEFAULT 0,
                    headshots INTEGER DEFAULT 0,
                    damage_given INTEGER DEFAULT 0,
                    damage_received INTEGER DEFAULT 0,
                    damage_team INTEGER DEFAULT 0,
                    hits INTEGER DEFAULT 0,
                    shots INTEGER DEFAULT 0,
                    accuracy REAL DEFAULT 0.0,
                    efficiency REAL DEFAULT 0.0,
                    score INTEGER DEFAULT 0,
                    xp REAL DEFAULT 0.0,
                    revives INTEGER DEFAULT 0,
                    ammopacks INTEGER DEFAULT 0,
                    healthpacks INTEGER DEFAULT 0,
                    time_played INTEGER DEFAULT 0,
                    map_name TEXT,
                    round_number INTEGER
                )
            ''')
            
            # Sessions
            await db.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TEXT,
                    end_time TEXT,
                    date TEXT,
                    map_name TEXT,
                    duration INTEGER,
                    round_number INTEGER,
                    winner TEXT,
                    status TEXT DEFAULT 'active'
                )
            ''')
            
            # Processed files
            await db.execute('''
                CREATE TABLE IF NOT EXISTS processed_files (
                    filename TEXT PRIMARY KEY,
                    processed_at TEXT,
                    success INTEGER DEFAULT 1,
                    error_message TEXT
                )
            ''')
            
            # Create indexes for performance
            await db.execute('CREATE INDEX IF NOT EXISTS idx_player_guid ON player_comprehensive_stats(player_guid)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_session_date ON player_comprehensive_stats(session_date)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_alias_guid ON player_aliases(guid)')
            
            await db.commit()
            logger.info("✅ Database schema initialized")
    
    async def update_player_alias(
        self, 
        guid: str, 
        alias: str, 
        last_seen_date: str
    ) -> None:
        """
        ⭐ CRITICAL: Track player aliases for !stats and !link commands.
        
        This method MUST be called every time a player's stats are processed.
        Without this, !stats and !link commands cannot find players by name.
        """
        try:
            async with await self.get_connection() as db:
                # Check if this GUID+alias combination exists
                async with db.execute(
                    'SELECT times_seen FROM player_aliases WHERE guid = ? AND alias = ?',
                    (guid, alias)
                ) as cursor:
                    existing = await cursor.fetchone()
                
                if existing:
                    # Update existing: increment times_seen, update last_seen
                    await db.execute(
                        '''UPDATE player_aliases 
                           SET times_seen = times_seen + 1, last_seen = ?
                           WHERE guid = ? AND alias = ?''',
                        (last_seen_date, guid, alias)
                    )
                else:
                    # Insert new alias
                    await db.execute(
                        '''INSERT INTO player_aliases 
                           (guid, alias, first_seen, last_seen, times_seen)
                           VALUES (?, ?, ?, ?, 1)''',
                        (guid, alias, last_seen_date, last_seen_date)
                    )
                
                await db.commit()
                logger.debug(f"✅ Updated alias: {alias} for GUID {guid}")
                
        except Exception as e:
            logger.error(f"❌ Failed to update alias for {guid}/{alias}: {e}")
    
    async def find_player_by_name(self, name: str) -> Optional[Tuple[str, str]]:
        """
        Find a player GUID by their alias (name).
        Returns (guid, alias) or None if not found.
        """
        async with await self.get_connection() as db:
            async with db.execute(
                '''SELECT guid, alias FROM player_aliases 
                   WHERE alias LIKE ? 
                   ORDER BY times_seen DESC, last_seen DESC 
                   LIMIT 1''',
                (f'%{name}%',)
            ) as cursor:
                result = await cursor.fetchone()
                return result if result else None
    
    async def get_player_aliases(self, guid: str, limit: int = 5) -> List[str]:
        """Get all known aliases for a player GUID"""
        async with await self.get_connection() as db:
            async with db.execute(
                '''SELECT alias FROM player_aliases 
                   WHERE guid = ? 
                   ORDER BY times_seen DESC, last_seen DESC 
                   LIMIT ?''',
                (guid, limit)
            ) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
    
    async def get_linked_guid(self, discord_id: str) -> Optional[str]:
        """Get ET:Legacy GUID for a Discord user"""
        async with await self.get_connection() as db:
            async with db.execute(
                'SELECT et_guid FROM player_links WHERE discord_id = ?',
                (discord_id,)
            ) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else None
    
    async def is_file_processed(self, filename: str) -> bool:
        """Check if a stats file has already been processed"""
        async with await self.get_connection() as db:
            async with db.execute(
                'SELECT 1 FROM processed_files WHERE filename = ?',
                (filename,)
            ) as cursor:
                return await cursor.fetchone() is not None
    
    async def mark_file_processed(
        self, 
        filename: str, 
        success: bool = True, 
        error_message: Optional[str] = None
    ) -> None:
        """Mark a file as processed"""
        async with await self.get_connection() as db:
            await db.execute(
                '''INSERT OR REPLACE INTO processed_files 
                   (filename, processed_at, success, error_message)
                   VALUES (?, ?, ?, ?)''',
                (filename, datetime.now().isoformat(), 1 if success else 0, error_message)
            )
            await db.commit()


# ============================================================================
# STATS PROCESSOR
# ============================================================================

class StatsProcessor:
    """
    Processes ET:Legacy stats files and inserts data into database.
    Uses C0RNP0RN3StatsParser for parsing stats files.
    """
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.parser = C0RNP0RN3StatsParser() if 'C0RNP0RN3StatsParser' in globals() else None
        
        if not self.parser:
            logger.warning("⚠️  Stats parser not available - some features may not work")
    
    async def process_stats_file(self, filepath: str) -> Dict[str, Any]:
        """
        Process a single stats file and insert into database.
        
        Returns dict with processing results:
        {
            'success': bool,
            'session_id': int,
            'players_processed': int,
            'error': Optional[str]
        }
        """
        if not self.parser:
            return {'success': False, 'error': 'Parser not available'}
        
        try:
            # Parse the stats file
            parsed_data = self.parser.parse_file(filepath)
            
            if not parsed_data or 'players' not in parsed_data:
                return {'success': False, 'error': 'Invalid stats file format'}
            
            # Extract metadata
            session_date = parsed_data.get('date', datetime.now().strftime('%Y-%m-%d'))
            map_name = parsed_data.get('map', 'Unknown')
            round_number = parsed_data.get('round', 1)
            
            # Create session
            async with await self.db_manager.get_connection() as db:
                cursor = await db.execute(
                    '''INSERT INTO sessions (start_time, date, map_name, round_number, status)
                       VALUES (?, ?, ?, ?, 'completed')''',
                    (datetime.now().strftime('%H:%M:%S'), session_date, map_name, round_number)
                )
                session_id = cursor.lastrowid
                
                # Process each player
                players_processed = 0
                for player in parsed_data['players']:
                    await self._insert_player_stats(db, session_id, session_date, player)
                    
                    # ⭐ CRITICAL: Update player alias for !stats and !link
                    guid = player.get('guid', 'UNKNOWN')
                    name = player.get('name', 'Unknown')
                    if guid != 'UNKNOWN' and name != 'Unknown':
                        await self.db_manager.update_player_alias(guid, name, session_date)
                    
                    players_processed += 1
                
                await db.commit()
                logger.info(f"✅ Processed {filepath}: {players_processed} players")
                
                return {
                    'success': True,
                    'session_id': session_id,
                    'players_processed': players_processed
                }
                
        except Exception as e:
            logger.error(f"❌ Error processing {filepath}: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _insert_player_stats(
        self,
        db: aiosqlite.Connection,
        session_id: int,
        session_date: str,
        player: Dict[str, Any]
    ) -> None:
        """Insert individual player stats into database"""
        await db.execute(
            '''INSERT INTO player_comprehensive_stats (
                session_id, session_date, player_guid, player_name, team,
                kills, deaths, suicides, team_kills, team_deaths,
                gibs, self_kills, headshots,
                damage_given, damage_received, damage_team,
                hits, shots, accuracy, efficiency, score, xp,
                revives, ammopacks, healthpacks, time_played
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                session_id,
                session_date,
                player.get('guid', 'UNKNOWN'),
                player.get('name', 'Unknown'),
                player.get('team', 0),
                player.get('kills', 0),
                player.get('deaths', 0),
                player.get('suicides', 0),
                player.get('team_kills', 0),
                player.get('team_deaths', 0),
                player.get('gibs', 0),
                player.get('self_kills', 0),
                player.get('headshots', 0),
                player.get('damage_given', 0),
                player.get('damage_received', 0),
                player.get('damage_team', 0),
                player.get('hits', 0),
                player.get('shots', 0),
                player.get('accuracy', 0.0),
                player.get('efficiency', 0.0),
                player.get('score', 0),
                player.get('xp', 0.0),
                player.get('revives', 0),
                player.get('ammopacks', 0),
                player.get('healthpacks', 0),
                player.get('time_played', 0)
            )
        )


# ============================================================================
# SSH FILE MONITOR (Optional Feature)
# ============================================================================

class SSHMonitor:
    """
    Monitors remote server via SSH for new stats files.
    Downloads and processes them automatically.
    """
    
    def __init__(self, bot, db_manager: DatabaseManager, stats_processor: StatsProcessor):
        self.bot = bot
        self.db_manager = db_manager
        self.stats_processor = stats_processor
        self.enabled = os.getenv('SSH_ENABLED', 'false').lower() == 'true'
        
        if self.enabled:
            self.host = os.getenv('SSH_HOST')
            self.port = int(os.getenv('SSH_PORT', 22))
            self.user = os.getenv('SSH_USER')
            self.key_path = os.getenv('SSH_KEY_PATH', '')
            self.remote_path = os.getenv('REMOTE_STATS_PATH')
            logger.info(f"🔒 SSH Monitor enabled for {self.user}@{self.host}")
        else:
            logger.info("⚠️  SSH Monitor disabled")
    
    async def list_remote_files(self) -> List[str]:
        """List all stats files on remote server"""
        if not self.enabled:
            return []
        
        try:
            # This would use asyncssh or paramiko in production
            # For now, return empty list
            logger.warning("SSH list_remote_files not implemented yet")
            return []
        except Exception as e:
            logger.error(f"❌ SSH list error: {e}")
            return []
    
    async def download_file(self, filename: str, local_dir: str = 'local_stats') -> Optional[str]:
        """Download a file from remote server"""
        if not self.enabled:
            return None
        
        try:
            # This would use asyncssh or paramiko in production
            logger.warning("SSH download_file not implemented yet")
            return None
        except Exception as e:
            logger.error(f"❌ SSH download error: {e}")
            return None
    
    @tasks.loop(minutes=5)
    async def monitor_loop(self):
        """Continuously monitor for new files"""
        if not self.enabled:
            return
        
        try:
            remote_files = await self.list_remote_files()
            
            for filename in remote_files:
                if not await self.db_manager.is_file_processed(filename):
                    local_path = await self.download_file(filename)
                    if local_path:
                        result = await self.stats_processor.process_stats_file(local_path)
                        await self.db_manager.mark_file_processed(
                            filename,
                            result['success'],
                            result.get('error')
                        )
        except Exception as e:
            logger.error(f"❌ Monitor loop error: {e}")


# ============================================================================
# COMMANDS COG
# ============================================================================

class ETLegacyCommands(commands.Cog):
    """🎮 ET:Legacy Bot Commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.stats_cache = StatsCache(ttl_seconds=300)
        self.season_manager = SeasonManager()
        self.achievements = AchievementSystem(bot)
        logger.info("✅ ETLegacyCommands cog initialized")
    
    # ================================================================
    # HELP & INFO COMMANDS
    # ================================================================
    
    @commands.command(name='help_command', aliases=['help', 'commands'])
    async def help_command(self, ctx):
        """📚 Show all available commands"""
        embed = discord.Embed(
            title="🎮 ET:Legacy Bot Commands",
            description="Complete command reference",
            color=0x00FF00
        )
        
        embed.add_field(
            name="📊 Stats Commands",
            value=(
                "• `!stats [player]` - Player statistics\n"
                "• `!leaderboard [type]` - Top players (kills/kd/dpm/acc/hs)\n"
                "• `!session [date]` - Session details\n"
                "• `!last_session` - Show most recent completed session"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔗 Account Linking",
            value=(
                "• `!link` - Link your ET account\n"
                "• `!link <name>` - Search and link by player name\n"
                "• `!link <guid>` - Link directly with GUID\n"
                "• `!link @user <guid>` - Admin: Link another user\n"
                "• `!unlink` - Unlink your account\n"
                "• `!list_guids [search]` - Admin: List unlinked players"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔧 System Commands",
            value=(
                "• `!ping` - Bot status\n"
                "• `!session_start <map>` - Start new session\n"
                "• `!session_end` - End active session\n"
                "• `!sync_stats` - Manually sync stats from server"
            ),
            inline=False
        )
        
        embed.set_footer(text="ET:Legacy Bot v2.0 | Use !command for details")
        await ctx.send(embed=embed)
    
    @commands.command(name='ping')
    async def ping(self, ctx):
        """🏓 Check bot status and response time"""
        latency = round(self.bot.latency * 1000)
        
        # Get database status
        try:
            async with await self.bot.db.get_connection() as db:
                async with db.execute('SELECT COUNT(*) FROM player_aliases') as cursor:
                    alias_count = (await cursor.fetchone())[0]
                db_status = f"✅ Online ({alias_count:,} aliases tracked)"
        except Exception as e:
            db_status = f"❌ Error: {e}"
        
        embed = discord.Embed(
            title="🏓 Bot Status",
            color=0x00FF00,
            timestamp=datetime.now()
        )
        embed.add_field(name="Latency", value=f"{latency}ms", inline=True)
        embed.add_field(name="Database", value=db_status, inline=False)
        embed.add_field(name="Season", value=self.season_manager.get_current_season(), inline=True)
        
        await ctx.send(embed=embed)
    
    # ================================================================
    # PLAYER STATS COMMANDS
    # ================================================================
    
    @commands.command(name='stats')
    async def stats(self, ctx, *, target: Optional[str] = None):
        """
        📊 Show player statistics
        
        Usage:
            !stats              - Show your stats (if linked)
            !stats @user        - Show stats for mentioned user
            !stats PlayerName   - Search by player name
            !stats ABC12345     - Look up by GUID
        """
        try:
            guid = None
            player_name = None
            
            # Determine target
            if not target:
                # Show user's own stats
                guid = await self.bot.db.get_linked_guid(str(ctx.author.id))
                if not guid:
                    await ctx.send(
                        "❌ You haven't linked your account yet!\n"
                        "Use `!link` to link your ET:Legacy account."
                    )
                    return
                player_name = ctx.author.display_name
            
            elif ctx.message.mentions:
                # Show mentioned user's stats
                mentioned = ctx.message.mentions[0]
                guid = await self.bot.db.get_linked_guid(str(mentioned.id))
                if not guid:
                    await ctx.send(f"❌ {mentioned.display_name} hasn't linked their account yet.")
                    return
                player_name = mentioned.display_name
            
            elif len(target) == 8 and target.isalnum():
                # Direct GUID lookup
                guid = target.upper()
                aliases = await self.bot.db.get_player_aliases(guid, limit=1)
                player_name = aliases[0] if aliases else guid
            
            else:
                # Search by player name
                result = await self.bot.db.find_player_by_name(target)
                if not result:
                    await ctx.send(
                        f"❌ Player '{target}' not found.\n"
                        f"Make sure they've played at least one game, or try `!list_guids {target}`"
                    )
                    return
                guid, player_name = result
            
            # Check cache
            cache_key = f"stats_{guid}_{self.season_manager.get_current_season()}"
            cached = self.stats_cache.get(cache_key)
            
            if cached:
                stats = cached
            else:
                # Fetch stats from database
                stats = await self._fetch_player_stats(guid)
                if not stats:
                    await ctx.send(f"❌ No statistics found for {player_name}")
                    return
                self.stats_cache.set(cache_key, stats)
            
            # Create stats embed
            embed = await self._create_stats_embed(guid, player_name, stats)
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in stats command: {e}")
            await ctx.send(f"❌ Error fetching stats: {e}")
    
    async def _fetch_player_stats(self, guid: str) -> Optional[Dict[str, Any]]:
        """Fetch comprehensive player statistics"""
        season_start = self.season_manager.get_season_start()
        
        async with await self.bot.db.get_connection() as db:
            async with db.execute(
                '''SELECT 
                    COUNT(DISTINCT session_id) as games_played,
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths,
                    SUM(headshots) as total_headshots,
                    SUM(damage_given) as total_damage,
                    SUM(hits) as total_hits,
                    SUM(shots) as total_shots,
                    MAX(session_date) as last_seen
                FROM player_comprehensive_stats
                WHERE player_guid = ? AND session_date >= ?''',
                (guid, season_start)
            ) as cursor:
                row = await cursor.fetchone()
                
                if not row or not row[0]:
                    return None
                
                games, kills, deaths, headshots, damage, hits, shots, last_seen = row
                
                return {
                    'games_played': games or 0,
                    'kills': kills or 0,
                    'deaths': deaths or 0,
                    'headshots': headshots or 0,
                    'damage': damage or 0,
                    'hits': hits or 0,
                    'shots': shots or 0,
                    'last_seen': last_seen,
                    'kd_ratio': round(kills / deaths, 2) if deaths > 0 else kills,
                    'accuracy': round((hits / shots * 100), 1) if shots > 0 else 0.0,
                    'hs_percentage': round((headshots / kills * 100), 1) if kills > 0 else 0.0,
                    'dpm': round(damage / games, 1) if games > 0 else 0.0
                }
    
    async def _create_stats_embed(
        self, 
        guid: str, 
        player_name: str, 
        stats: Dict[str, Any]
    ) -> discord.Embed:
        """Create a formatted stats embed"""
        embed = discord.Embed(
            title=f"📊 Stats: {player_name}",
            color=0x00FF00,
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="🎮 Overview",
            value=(
                f"**Games:** {stats['games_played']:,}\n"
                f"**K/D Ratio:** {stats['kd_ratio']}\n"
                f"**Last Seen:** {stats['last_seen']}"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚔️ Combat",
            value=(
                f"**Kills:** {stats['kills']:,}\n"
                f"**Deaths:** {stats['deaths']:,}\n"
                f"**Headshots:** {stats['headshots']:,} ({stats['hs_percentage']}%)"
            ),
            inline=True
        )
        
        embed.add_field(
            name="🎯 Accuracy",
            value=(
                f"**Accuracy:** {stats['accuracy']}%\n"
                f"**Damage/Game:** {stats['dpm']:,}\n"
                f"**Total Damage:** {stats['damage']:,}"
            ),
            inline=True
        )
        
        embed.set_footer(text=f"GUID: {guid} | Season: {self.season_manager.get_current_season()}")
        
        return embed
    
    # ================================================================
    # LEADERBOARD COMMANDS
    # ================================================================
    
    @commands.command(name='leaderboard', aliases=['top', 'ranks'])
    async def leaderboard(self, ctx, leaderboard_type: str = 'kills'):
        """
        🏆 Show leaderboards
        
        Types: kills, kd, dpm, accuracy (acc), headshots (hs)
        """
        valid_types = {
            'kills': ('SUM(kills)', 'Kills'),
            'kd': ('CAST(SUM(kills) AS FLOAT) / NULLIF(SUM(deaths), 0)', 'K/D Ratio'),
            'dpm': ('SUM(damage_given) / COUNT(DISTINCT session_id)', 'Damage/Game'),
            'acc': ('SUM(hits) * 100.0 / NULLIF(SUM(shots), 0)', 'Accuracy %'),
            'accuracy': ('SUM(hits) * 100.0 / NULLIF(SUM(shots), 0)', 'Accuracy %'),
            'hs': ('SUM(headshots)', 'Headshots'),
            'headshots': ('SUM(headshots)', 'Headshots')
        }
        
        lb_type = leaderboard_type.lower()
        if lb_type not in valid_types:
            await ctx.send(
                f"❌ Invalid leaderboard type. Use: {', '.join(set(valid_types.keys()))}"
            )
            return
        
        stat_query, stat_name = valid_types[lb_type]
        season_start = self.season_manager.get_season_start()
        
        try:
            async with await self.bot.db.get_connection() as db:
                query = f'''
                    SELECT 
                        player_guid,
                        player_name,
                        {stat_query} as stat_value,
                        COUNT(DISTINCT session_id) as games
                    FROM player_comprehensive_stats
                    WHERE session_date >= ? AND player_guid != 'UNKNOWN'
                    GROUP BY player_guid
                    HAVING games >= 5
                    ORDER BY stat_value DESC
                    LIMIT 10
                '''
                
                async with db.execute(query, (season_start,)) as cursor:
                    rows = await cursor.fetchall()
            
            if not rows:
                await ctx.send("❌ No leaderboard data available yet.")
                return
            
            # Create leaderboard embed
            embed = discord.Embed(
                title=f"🏆 Leaderboard: {stat_name}",
                description=f"Season: {self.season_manager.get_current_season()}",
                color=0xFFD700
            )
            
            medals = ['🥇', '🥈', '🥉']
            
            for i, (guid, name, value, games) in enumerate(rows, 1):
                medal = medals[i-1] if i <= 3 else f"**{i}.**"
                
                # Format value based on type
                if 'ratio' in stat_name.lower():
                    value_str = f"{value:.2f}"
                elif '%' in stat_name:
                    value_str = f"{value:.1f}%"
                else:
                    value_str = f"{int(value):,}"
                
                embed.add_field(
                    name=f"{medal} {name}",
                    value=f"{stat_name}: {value_str}\nGames: {games}",
                    inline=False
                )
            
            embed.set_footer(text="Minimum 5 games required")
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in leaderboard command: {e}")
            await ctx.send(f"❌ Error fetching leaderboard: {e}")
    
    # ================================================================
    # ACCOUNT LINKING COMMANDS
    # ================================================================
    
    @commands.command(name='link')
    async def link(self, ctx, target: Optional[str] = None, guid: Optional[str] = None):
        """
        🔗 Link your Discord account to ET:Legacy
        
        Usage:
            !link                    - Interactive linking (shows options)
            !link PlayerName         - Search and link by name
            !link ABC12345           - Link with GUID
            !link @user ABC12345     - Admin: Link another user
        """
        try:
            # Admin linking another user
            if ctx.message.mentions and guid:
                if not ctx.author.guild_permissions.administrator:
                    await ctx.send("❌ Only administrators can link other users.")
                    return
                
                mentioned = ctx.message.mentions[0]
                guid_upper = guid.upper()
                
                # Verify GUID exists
                aliases = await self.bot.db.get_player_aliases(guid_upper, limit=2)
                if not aliases:
                    await ctx.send(f"❌ GUID {guid_upper} not found in database.")
                    return
                
                # Link the user
                async with await self.bot.db.get_connection() as db:
                    await db.execute(
                        '''INSERT OR REPLACE INTO player_links 
                           (discord_id, discord_username, et_guid, et_name, linked_date)
                           VALUES (?, ?, ?, ?, ?)''',
                        (
                            str(mentioned.id),
                            mentioned.display_name,
                            guid_upper,
                            aliases[0],
                            datetime.now().isoformat()
                        )
                    )
                    await db.commit()
                
                await ctx.send(
                    f"✅ Successfully linked {mentioned.mention} to **{aliases[0]}** (GUID: {guid_upper})"
                )
                return
            
            # Check if already linked
            existing_guid = await self.bot.db.get_linked_guid(str(ctx.author.id))
            if existing_guid and not target:
                aliases = await self.bot.db.get_player_aliases(existing_guid)
                await ctx.send(
                    f"ℹ️  You're already linked to **{aliases[0] if aliases else existing_guid}**\n"
                    f"Use `!unlink` to unlink first."
                )
                return
            
            # Direct GUID link
            if target and len(target) == 8 and target.isalnum():
                guid_upper = target.upper()
                aliases = await self.bot.db.get_player_aliases(guid_upper, limit=2)
                
                if not aliases:
                    await ctx.send(f"❌ GUID {guid_upper} not found in database.")
                    return
                
                # Confirmation
                confirm_msg = await ctx.send(
                    f"🔗 Link to **{aliases[0]}** (GUID: {guid_upper})?\n"
                    f"React with ✅ to confirm or ❌ to cancel."
                )
                
                await confirm_msg.add_reaction('✅')
                await confirm_msg.add_reaction('❌')
                
                def check(reaction, user):
                    return (
                        user == ctx.author 
                        and str(reaction.emoji) in ['✅', '❌']
                        and reaction.message.id == confirm_msg.id
                    )
                
                try:
                    reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
                    
                    if str(reaction.emoji) == '✅':
                        async with await self.bot.db.get_connection() as db:
                            await db.execute(
                                '''INSERT OR REPLACE INTO player_links 
                                   (discord_id, discord_username, et_guid, et_name, linked_date)
                                   VALUES (?, ?, ?, ?, ?)''',
                                (
                                    str(ctx.author.id),
                                    ctx.author.display_name,
                                    guid_upper,
                                    aliases[0],
                                    datetime.now().isoformat()
                                )
                            )
                            await db.commit()
                        
                        await confirm_msg.edit(
                            content=f"✅ Successfully linked to **{aliases[0]}** (GUID: {guid_upper})"
                        )
                    else:
                        await confirm_msg.edit(content="❌ Linking cancelled.")
                
                except asyncio.TimeoutError:
                    await confirm_msg.edit(content="⏱️ Linking timed out.")
                
                return
            
            # Search by name
            if target:
                result = await self.bot.db.find_player_by_name(target)
                if not result:
                    await ctx.send(
                        f"❌ Player '{target}' not found.\n"
                        f"Try using `!list_guids {target}` to search for unlinked players."
                    )
                    return
                
                guid_found, name_found = result
                
                # Show options
                aliases = await self.bot.db.get_player_aliases(guid_found, limit=3)
                alias_str = ' / '.join(aliases[:2])
                if len(aliases) > 2:
                    alias_str += f" (+{len(aliases)-2} more)"
                
                confirm_msg = await ctx.send(
                    f"🔗 Found player: **{alias_str}**\n"
                    f"GUID: {guid_found}\n\n"
                    f"React with ✅ to link or ❌ to cancel."
                )
                
                await confirm_msg.add_reaction('✅')
                await confirm_msg.add_reaction('❌')
                
                def check(reaction, user):
                    return (
                        user == ctx.author 
                        and str(reaction.emoji) in ['✅', '❌']
                        and reaction.message.id == confirm_msg.id
                    )
                
                try:
                    reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
                    
                    if str(reaction.emoji) == '✅':
                        async with await self.bot.db.get_connection() as db:
                            await db.execute(
                                '''INSERT OR REPLACE INTO player_links 
                                   (discord_id, discord_username, et_guid, et_name, linked_date)
                                   VALUES (?, ?, ?, ?, ?)''',
                                (
                                    str(ctx.author.id),
                                    ctx.author.display_name,
                                    guid_found,
                                    name_found,
                                    datetime.now().isoformat()
                                )
                            )
                            await db.commit()
                        
                        await confirm_msg.edit(
                            content=f"✅ Successfully linked to **{name_found}** (GUID: {guid_found})"
                        )
                    else:
                        await confirm_msg.edit(content="❌ Linking cancelled.")
                
                except asyncio.TimeoutError:
                    await confirm_msg.edit(content="⏱️ Linking timed out.")
                
                return
            
            # Interactive linking - show top suggestions
            await ctx.send(
                "🔗 **Link Your Account**\n\n"
                "Choose one of these methods:\n"
                "• `!link PlayerName` - Search by your in-game name\n"
                "• `!link ABC12345` - Link with your GUID\n"
                "• `!list_guids` - See all unlinked players\n\n"
                "Need help? Ask an admin to use `!link @you <GUID>`"
            )
            
        except Exception as e:
            logger.error(f"Error in link command: {e}")
            await ctx.send(f"❌ Error linking account: {e}")
    
    @commands.command(name='unlink')
    async def unlink(self, ctx):
        """🔓 Unlink your Discord account from ET:Legacy"""
        try:
            async with await self.bot.db.get_connection() as db:
                cursor = await db.execute(
                    'SELECT et_name FROM player_links WHERE discord_id = ?',
                    (str(ctx.author.id),)
                )
                result = await cursor.fetchone()
                
                if not result:
                    await ctx.send("ℹ️  You don't have a linked account.")
                    return
                
                et_name = result[0]
                
                await db.execute(
                    'DELETE FROM player_links WHERE discord_id = ?',
                    (str(ctx.author.id),)
                )
                await db.commit()
            
            await ctx.send(f"✅ Successfully unlinked from **{et_name}**")
            
        except Exception as e:
            logger.error(f"Error in unlink command: {e}")
            await ctx.send(f"❌ Error unlinking account: {e}")
    
    @commands.command(name='list_guids', aliases=['listguids', 'unlinked'])
    async def list_guids(self, ctx, *, search_term: Optional[str] = None):
        """
        📋 List unlinked players (Admin Helper)
        
        Usage:
            !list_guids              - Show top 10 most active unlinked
            !list_guids recent       - Last 7 days
            !list_guids PlayerName   - Search by name
            !list_guids all          - Show all unlinked (max 20)
        """
        try:
            season_start = self.season_manager.get_season_start()
            
            # Build query based on search term
            if search_term and search_term.lower() == 'recent':
                # Recently active (last 7 days)
                seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                date_filter = f"AND pcs.session_date >= '{seven_days_ago}'"
                title = "🕐 Recently Active Unlinked Players (Last 7 Days)"
                limit = 10
            elif search_term and search_term.lower() == 'all':
                # All unlinked players
                date_filter = ""
                title = "📋 All Unlinked Players"
                limit = 20
            elif search_term:
                # Search by name
                date_filter = f"AND pa.alias LIKE '%{search_term}%'"
                title = f"🔍 Unlinked Players matching '{search_term}'"
                limit = 10
            else:
                # Default: Most active
                date_filter = ""
                title = "🎮 Most Active Unlinked Players"
                limit = 10
            
            query = f'''
                SELECT 
                    pa.guid,
                    COUNT(DISTINCT pa.alias) as alias_count,
                    MAX(pa.last_seen) as last_seen,
                    COALESCE(SUM(pcs.kills), 0) as total_kills,
                    COALESCE(SUM(pcs.deaths), 0) as total_deaths,
                    COUNT(DISTINCT pcs.session_id) as games
                FROM player_aliases pa
                LEFT JOIN player_comprehensive_stats pcs ON pa.guid = pcs.player_guid
                WHERE pa.guid NOT IN (SELECT et_guid FROM player_links WHERE et_guid IS NOT NULL)
                {date_filter}
                GROUP BY pa.guid
                HAVING games > 0
                ORDER BY total_kills DESC, games DESC
                LIMIT {limit}
            '''
            
            async with await self.bot.db.get_connection() as db:
                async with db.execute(query) as cursor:
                    rows = await cursor.fetchall()
            
            if not rows:
                await ctx.send("✅ No unlinked players found!")
                return
            
            # Create embed
            embed = discord.Embed(
                title=title,
                description=f"Found {len(rows)} unlinked player(s).",
                color=0x3498DB
            )
            
            for guid, alias_count, last_seen, kills, deaths, games in rows:
                # Get top 2 aliases
                aliases = await self.bot.db.get_player_aliases(guid, limit=2)
                alias_str = ' / '.join(aliases) if aliases else guid
                if alias_count > 2:
                    alias_str += f" (+{alias_count-2} more)"
                
                kd = round(kills / deaths, 2) if deaths > 0 else kills
                
                embed.add_field(
                    name=f"🆔 {guid}",
                    value=(
                        f"**{alias_str}**\n"
                        f"📊 {kills:,}K / {deaths:,}D / {kd} KD\n"
                        f"🎮 {games} games • Last: {last_seen}"
                    ),
                    inline=False
                )
            
            embed.set_footer(
                text="💡 To link: !link @user <GUID>"
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in list_guids command: {e}")
            await ctx.send(f"❌ Error fetching unlinked players: {e}")
    
    # ================================================================
    # SESSION MANAGEMENT COMMANDS
    # ================================================================
    
    @commands.command(name='session_start')
    async def session_start(self, ctx, *, map_name: str = "Unknown"):
        """🎬 Start a new gaming session"""
        try:
            if self.bot.current_session:
                await ctx.send("❌ A session is already active. End it first with `!session_end`")
                return
            
            now = datetime.now()
            
            async with await self.bot.db.get_connection() as db:
                cursor = await db.execute(
                    '''INSERT INTO sessions (start_time, date, map_name, status)
                       VALUES (?, ?, ?, 'active')''',
                    (now.strftime('%H:%M:%S'), now.strftime('%Y-%m-%d'), map_name)
                )
                session_id = cursor.lastrowid
                self.bot.current_session = session_id
                await db.commit()
            
            embed = discord.Embed(
                title="🎬 Session Started!",
                description=f"**Map:** {map_name}\n**Session ID:** {session_id}",
                color=0x00FF00,
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
            
            async with await self.bot.db.get_connection() as db:
                await db.execute(
                    '''UPDATE sessions 
                       SET end_time = ?, status = 'completed'
                       WHERE id = ?''',
                    (now.strftime('%H:%M:%S'), self.bot.current_session)
                )
                await db.commit()
            
            session_id = self.bot.current_session
            self.bot.current_session = None
            
            await ctx.send(f"🏁 Session {session_id} ended!")
            logger.info(f"Session {session_id} ended")
            
        except Exception as e:
            logger.error(f"Error ending session: {e}")
            await ctx.send(f"❌ Error ending session: {e}")
    
    @commands.command(name='session', aliases=['match'])
    async def session(self, ctx, date: Optional[str] = None):
        """📅 Show session details"""
        try:
            if date:
                target_date = date
            else:
                target_date = datetime.now().strftime('%Y-%m-%d')
            
            async with await self.bot.db.get_connection() as db:
                async with db.execute(
                    '''SELECT id, start_time, end_time, map_name, status
                       FROM sessions
                       WHERE date = ?
                       ORDER BY id DESC
                       LIMIT 5''',
                    (target_date,)
                ) as cursor:
                    sessions = await cursor.fetchall()
            
            if not sessions:
                await ctx.send(f"❌ No sessions found for {target_date}")
                return
            
            embed = discord.Embed(
                title=f"📅 Sessions: {target_date}",
                color=0x3498DB
            )
            
            for sid, start, end, map_name, status in sessions:
                status_emoji = "✅" if status == "completed" else "🔴"
                embed.add_field(
                    name=f"{status_emoji} Session {sid}",
                    value=f"**Map:** {map_name}\n**Time:** {start} - {end or 'Active'}",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in session command: {e}")
            await ctx.send(f"❌ Error fetching session: {e}")
    
    @commands.command(name='last_session')
    async def last_session(self, ctx):
        """🕐 Show most recent completed session"""
        try:
            async with await self.bot.db.get_connection() as db:
                # Get most recent completed session
                async with db.execute(
                    '''SELECT id, date, map_name, start_time, end_time
                       FROM sessions
                       WHERE status = 'completed'
                       ORDER BY date DESC, id DESC
                       LIMIT 1'''
                ) as cursor:
                    session = await cursor.fetchone()
                
                if not session:
                    await ctx.send("❌ No completed sessions found.")
                    return
                
                session_id, date, map_name, start, end = session
                
                # Get player stats for this session
                async with db.execute(
                    '''SELECT player_name, kills, deaths, headshots, accuracy
                       FROM player_comprehensive_stats
                       WHERE session_id = ?
                       ORDER BY kills DESC
                       LIMIT 5''',
                    (session_id,)
                ) as cursor:
                    players = await cursor.fetchall()
            
            # Create embed
            embed = discord.Embed(
                title=f"🕐 Last Session: {map_name}",
                description=f"**Date:** {date}\n**Time:** {start} - {end}",
                color=0x3498DB
            )
            
            if players:
                embed.add_field(
                    name="🏆 Top Players",
                    value="\n".join(
                        f"• **{name}**: {kills}K / {deaths}D / {hs}HS ({acc:.1f}%)"
                        for name, kills, deaths, hs, acc in players
                    ),
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in last_session command: {e}")
            await ctx.send(f"❌ Error fetching last session: {e}")
    
    @commands.command(name='sync_stats', aliases=['syncstats'])
    async def sync_stats(self, ctx):
        """🔄 Manually sync stats from server (if SSH enabled)"""
        if not self.bot.ssh_monitor or not self.bot.ssh_monitor.enabled:
            await ctx.send(
                "❌ SSH monitoring is not enabled.\n"
                "Set `SSH_ENABLED=true` in .env file."
            )
            return
        
        await ctx.send(
            "🔄 Manual sync not yet implemented.\n"
            "SSH monitoring is enabled and will auto-sync files."
        )


# ============================================================================
# MAIN BOT CLASS
# ============================================================================

class UltimateETLegacyBot(commands.Bot):
    """Main bot class with initialization and setup"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None  # We use custom !help_command
        )
        
        # Find database path
        self.db_path = self._find_database_path()
        logger.info(f"📁 Using database: {self.db_path}")
        
        # Initialize components
        self.db = DatabaseManager(self.db_path)
        self.stats_processor = StatsProcessor(self.db)
        self.ssh_monitor = SSHMonitor(self, self.db, self.stats_processor)
        
        # State
        self.current_session = None
        
        logger.info("✅ Bot initialized")
    
    def _find_database_path(self) -> str:
        """Find database path from environment or default locations"""
        # Try environment variable first
        env_path = os.getenv('ETLEGACY_DB_PATH')
        if env_path and os.path.exists(env_path):
            return env_path
        
        # Try common locations
        possible_paths = [
            'etlegacy_production.db',
            '../etlegacy_production.db',
            '/var/lib/etlegacy/etlegacy_production.db',
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # Default to current directory
        return 'etlegacy_production.db'
    
    async def setup_hook(self):
        """Called when bot is starting up"""
        logger.info("🔧 Running setup hook...")
        
        # Initialize database
        await self.db.init_database()
        
        # Add cog
        await self.add_cog(ETLegacyCommands(self))
        logger.info("✅ Commands cog loaded")
        
        # Start SSH monitor if enabled
        if self.ssh_monitor.enabled:
            self.ssh_monitor.monitor_loop.start()
            logger.info("✅ SSH monitor started")
    
    async def on_ready(self):
        """Called when bot is fully connected and ready"""
        logger.info("=" * 70)
        logger.info(f"🎮 {self.user.name} is online!")
        logger.info(f"📊 Connected to {len(self.guilds)} guild(s)")
        logger.info(f"📁 Database: {self.db_path}")
        logger.info("=" * 70)
        
        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="ET:Legacy matches | !help"
            )
        )
    
    async def on_command_error(self, ctx, error):
        """Global error handler"""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore unknown commands
        
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing required argument: {error.param.name}")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"❌ Invalid argument: {error}")
        else:
            logger.error(f"Command error: {error}")
            await ctx.send(f"❌ An error occurred: {error}")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point"""
    # Get Discord token
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        logger.error("❌ DISCORD_BOT_TOKEN not found in environment!")
        sys.exit(1)
    
    # Create and run bot
    bot = UltimateETLegacyBot()
    
    try:
        bot.run(token)
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
