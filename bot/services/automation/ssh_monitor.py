"""
🔄 SSH File Monitor Service
============================

Clean refactored service for monitoring remote SSH directory for new stats files.

This service handles:
- SSH connection and file listing
- New file detection (compares with processed_files cache)
- File downloading via SSH/SFTP
- Delegating parsing/import to bot
- Auto-posting round stats to Discord

Usage:
    from bot.services.automation.ssh_monitor import SSHMonitor
    
    monitor = SSHMonitor(bot)
    await monitor.check_and_process_new_files()
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
import discord

logger = logging.getLogger("UltimateBot.SSHMonitor")


class SSHMonitor:
    """
    SSH File Monitor Service
    
    Handles SSH connections, file detection, downloading, and coordination
    with the bot for processing and Discord posting.
    
    This is a SERVICE class - it doesn't contain business logic for parsing
    or database operations. It delegates those to the bot.
    """
    
    def __init__(self, bot):
        """
        Initialize SSH monitor service.
        
        Args:
            bot: Discord bot instance (UltimateETLegacyBot)
        """
        self.bot = bot
        
        # SSH configuration from environment
        self.ssh_enabled = os.getenv("SSH_ENABLED", "false").lower() == "true"
        self.ssh_config = {
            "host": os.getenv("SSH_HOST", ""),
            "port": int(os.getenv("SSH_PORT", "22")),
            "user": os.getenv("SSH_USER", ""),
            "key_path": os.getenv("SSH_KEY_PATH", ""),
            "remote_path": os.getenv("REMOTE_STATS_PATH", "")
        }
        
        # Discord configuration
        stats_channel_env = os.getenv("STATS_CHANNEL_ID", "0")
        self.stats_channel_id = int(stats_channel_env) if stats_channel_env.isdigit() else 0
        
        # Statistics (for monitoring health)
        self.last_check_time: Optional[datetime] = None
        self.files_processed_count = 0
        self.errors_count = 0
        self.last_error: Optional[str] = None
        
        logger.info("🔄 SSH Monitor service initialized")
    
    async def start_monitoring(self):
        """Start the SSH monitoring task"""
        if not self.ssh_enabled:
            logger.warning("⚠️ SSH monitoring disabled in configuration")
            return
        
        if not self._validate_config():
            logger.error("❌ SSH configuration invalid, cannot start monitoring")
            return
        
        self.is_monitoring = True
        logger.info("✅ SSH monitoring started")
        
        # Load previously processed files from database
        await self._load_processed_files()
        
        # Start monitoring loop
        asyncio.create_task(self._monitoring_loop())
    
    async def stop_monitoring(self):
        """Stop the SSH monitoring task"""
        self.is_monitoring = False
        logger.info("🛑 SSH monitoring stopped")
    
    def _validate_config(self) -> bool:
        """Validate SSH configuration"""
        required = [
            self.ssh_host,
            self.ssh_user,
            self.ssh_key_path,
            self.remote_stats_dir
        ]
        
        if not all(required):
            logger.error("❌ Missing SSH configuration:")
            if not self.ssh_host: logger.error("  - SSH_HOST")
            if not self.ssh_user: logger.error("  - SSH_USER")
            if not self.ssh_key_path: logger.error("  - SSH_KEY_PATH")
            if not self.remote_stats_dir: logger.error("  - REMOTE_STATS_PATH")
            return False
        
        return True
    
    async def _load_processed_files(self):
        """Load list of previously processed files from database"""
        try:
            rows = await self.bot.db_adapter.fetch_all(
                "SELECT filename FROM processed_files WHERE success = 1",
                ()
            )
            self.processed_files = {row[0] for row in rows}
            logger.info(f"📋 Loaded {len(self.processed_files)} previously processed files")
        except Exception as e:
            logger.error(f"❌ Failed to load processed files: {e}")
    
    async def _monitoring_loop(self):
        """Main monitoring loop - runs continuously"""
        logger.info("🔁 Monitoring loop started")
        
        while self.is_monitoring:
            try:
                start_time = datetime.now()
                
                # Check for new files
                await self._check_for_new_files()
                
                # Track check time
                check_duration = (datetime.now() - start_time).total_seconds()
                self.check_times.append(check_duration)
                if len(self.check_times) > 100:
                    self.check_times.pop(0)  # Keep last 100
                
                self.last_check_time = datetime.now()
                
                # Wait before next check
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                self.errors_count += 1
                self.last_error = str(e)
                logger.error(f"❌ Monitoring loop error: {e}", exc_info=True)
                
                # Exponential backoff on errors
                wait_time = min(300, 30 * (2 ** min(self.errors_count, 5)))
                logger.info(f"⏳ Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)
        
        logger.info("🛑 Monitoring loop stopped")
    
    async def _check_for_new_files(self):
        """Check remote directory for new stats files"""
        try:
            # List remote files
            remote_files = await self._list_remote_files()
            
            if not remote_files:
                logger.debug("No files found on remote server")
                return
            
            # Filter for .stats files only
            stats_files = [f for f in remote_files if f.endswith('.stats') or f.endswith('.txt')]
            
            # Find new files (not in processed set)
            new_files = [f for f in stats_files if f not in self.processed_files]
            
            if new_files:
                logger.info(f"🆕 Found {len(new_files)} new file(s): {new_files}")
                
                # Process each new file
                for filename in new_files:
                    await self._process_new_file(filename)
            else:
                logger.debug(f"✓ No new files (checked {len(stats_files)} files)")
                
        except Exception as e:
            logger.error(f"❌ Error checking for new files: {e}", exc_info=True)
            raise
    
    async def _list_remote_files(self) -> list:
        """List files in remote SSH directory"""
        try:
            import paramiko
            
            # Create SSH client
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect
            ssh.connect(
                hostname=self.ssh_host,
                port=self.ssh_port,
                username=self.ssh_user,
                key_filename=os.path.expanduser(self.ssh_key_path),
                timeout=10
            )
            
            # List files
            stdin, stdout, stderr = ssh.exec_command(f"ls -1 {self.remote_stats_dir}")
            files = stdout.read().decode().strip().split('\n')
            
            ssh.close()
            
            return [f.strip() for f in files if f.strip()]
            
        except Exception as e:
            logger.error(f"❌ SSH list files error: {e}")
            raise
    
    async def _process_new_file(self, filename: str):
        """
        Process a newly detected stats file.
        
        Steps:
        1. Download file
        2. Parse stats
        3. Import to database
        4. Post to Discord
        5. Mark as processed
        """
        try:
            logger.info(f"📥 Processing new file: {filename}")
            start_time = datetime.now()
            
            # Download file
            local_path = await self._download_file(filename)
            
            if not local_path:
                logger.error(f"❌ Failed to download: {filename}")
                return
            
            # Wait a moment for file to fully write
            await asyncio.sleep(2)
            
            # Parse and import to database
            success = await self._import_file_to_db(local_path, filename)
            
            if not success:
                logger.error(f"❌ Failed to import: {filename}")
                return
            
            # Post stats to Discord
            await self._post_round_stats(filename)
            
            # 🆕 If this is Round 2, also post match summary
            if '-round-2.txt' in filename:
                logger.info("🏁 Round 2 detected - posting match summary...")
                await self._post_match_summary(filename)
            
            # Mark as processed
            self.processed_files.add(filename)
            self.files_processed_count += 1
            
            # Track processing time
            process_duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"✅ Processed {filename} in {process_duration:.2f}s")
            
            # Reset error count on success
            if self.errors_count > 0:
                self.errors_count = max(0, self.errors_count - 1)
            
        except Exception as e:
            self.errors_count += 1
            self.last_error = str(e)
            logger.error(f"❌ Error processing {filename}: {e}", exc_info=True)
    
    async def _download_file(self, filename: str) -> Optional[str]:
        """Download file from remote server"""
        try:
            import paramiko
            from scp import SCPClient
            
            download_start = datetime.now()
            
            # Create SSH client
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect
            ssh.connect(
                hostname=self.ssh_host,
                port=self.ssh_port,
                username=self.ssh_user,
                key_filename=os.path.expanduser(self.ssh_key_path),
                timeout=10
            )
            
            # Download using SCP
            local_dir = "bot/local_stats"
            os.makedirs(local_dir, exist_ok=True)
            
            local_path = os.path.join(local_dir, filename)
            remote_path = f"{self.remote_stats_dir}/{filename}"
            
            with SCPClient(ssh.get_transport()) as scp:
                scp.get(remote_path, local_path)
            
            ssh.close()
            
            # Track download time
            download_duration = (datetime.now() - download_start).total_seconds()
            self.download_times.append(download_duration)
            if len(self.download_times) > 100:
                self.download_times.pop(0)
            
            logger.info(f"✅ Downloaded {filename} in {download_duration:.2f}s")
            return local_path
            
        except Exception as e:
            logger.error(f"❌ Download error for {filename}: {e}")
            return None
    
    async def _import_file_to_db(self, local_path: str, filename: str) -> bool:
        """Import stats file to database"""
        try:
            # Use bot's existing parser
            # This assumes the bot has a method to parse and import files
            if hasattr(self.bot, 'process_gamestats_file'):
                await self.bot.process_gamestats_file(local_path, filename)
                return True
            else:
                logger.error("❌ Bot missing process_gamestats_file method")
                return False
                
        except Exception as e:
            logger.error(f"❌ Import error for {filename}: {e}")
            return False
    
    async def _post_round_stats(self, filename: str):
        """Post round statistics to Discord channel"""
        try:
            channel = self.bot.get_channel(self.stats_channel_id)
            
            if not channel:
                logger.error(f"❌ Stats channel {self.stats_channel_id} not found")
                return
            
            # Get the round data from database (most recent round)
            round_data = await self._get_latest_round_data()
            
            if not round_data:
                logger.warning(f"⚠️ No round data found for {filename}")
                return
            
            # Create embed
            embed = await self._create_round_embed(round_data, filename)
            
            # Post to channel
            await channel.send(embed=embed)
            logger.info(f"📊 Posted stats for {filename} to channel")
            
        except Exception as e:
            logger.error(f"❌ Error posting stats: {e}", exc_info=True)
    
    async def _get_latest_round_data(self) -> Optional[Dict[str, Any]]:
        """Get data for the most recently imported round"""
        try:
            # Get latest session and round
            row = await self.bot.db_adapter.fetch_one("""
                SELECT 
                    session_id,
                    round_num,
                    map_name,
                    COUNT(*) as player_count,
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths,
                    MAX(timestamp) as round_time
                FROM player_comprehensive_stats
                GROUP BY session_id, round_num
                ORDER BY timestamp DESC
                LIMIT 1
            """, ())
            
            if not row:
                return None
            
            session_id, round_num, map_name, player_count, kills, deaths, timestamp = row
            
            # Get top 5 players
            top_players = await self.bot.db_adapter.fetch_all("""
                SELECT 
                    player_name,
                    kills,
                    deaths,
                    damage_given,
                    accuracy
                FROM player_comprehensive_stats
                WHERE session_id = ? AND round_num = ?
                ORDER BY kills DESC
                LIMIT 5
            """, (session_id, round_num))
            
            return {
                'session_id': session_id,
                'round_num': round_num,
                'map_name': map_name,
                'player_count': player_count,
                'total_kills': kills,
                'total_deaths': deaths,
                'timestamp': timestamp,
                'top_players': top_players
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting round data: {e}")
            return None
    
    async def _create_round_embed(self, data: Dict[str, Any], filename: str) -> discord.Embed:
        """Create Discord embed for round stats"""
        embed = discord.Embed(
            title=f"🎮 Round {data['round_num']} Complete!",
            description=f"**Map:** {data['map_name']}\n**Players:** {data['player_count']}",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        # Top players
        if data['top_players']:
            top_text = []
            for i, (name, kills, deaths, dmg, acc) in enumerate(data['top_players'], 1):
                kd = f"{kills}/{deaths}"
                top_text.append(f"{i}. **{name}** - {kd} K/D | {int(dmg)} DMG | {acc:.1f}% ACC")
            
            embed.add_field(
                name="🏆 Top Players",
                value="\n".join(top_text),
                inline=False
            )
        
        # Stats summary
        embed.add_field(
            name="📊 Round Summary",
            value=f"Total Kills: {data['total_kills']}\nTotal Deaths: {data['total_deaths']}",
            inline=True
        )
        
        embed.set_footer(text=f"File: {filename}")
        
        return embed
    
    async def _post_match_summary(self, filename: str):
        """
        Post match summary (cumulative R1+R2 stats) to Discord
        
        This queries round_number=0 which contains the cumulative stats
        from the Round 2 file (R1+R2 combined).
        """
        try:
            channel = self.bot.get_channel(self.stats_channel_id)
            
            if not channel:
                logger.error(f"❌ Stats channel {self.stats_channel_id} not found")
                return
            
            # Extract map name from filename
            parts = filename.split('-')
            if len(parts) < 5:
                logger.error(f"❌ Invalid filename format: {filename}")
                return
            
            map_name = '-'.join(parts[4:-2])  # Everything between timestamp and "round-N.txt"
            
            # Get match summary data (round_number = 0)
            match_data = await self._get_match_summary_data(map_name)
            
            if not match_data:
                logger.warning(f"⚠️ No match summary found for {map_name}")
                return
            
            # Create embed
            embed = await self._create_match_summary_embed(match_data, filename, map_name)
            
            # Post to channel
            await channel.send(embed=embed)
            logger.info(f"🏁 Posted match summary for {map_name}")
            
        except Exception as e:
            logger.error(f"❌ Error posting match summary: {e}", exc_info=True)
    
    async def _get_match_summary_data(self, map_name: str) -> Optional[Dict[str, Any]]:
        """Get match summary data (round_number=0) from database"""
        try:
            # Get the match summary round (round_number = 0)
            row = await self.bot.db_adapter.fetch_one("""
                SELECT 
                    id,
                    time_limit,
                    actual_time,
                    winner_team,
                    round_outcome,
                    COUNT(*) as player_count
                FROM rounds
                WHERE map_name = ? AND round_number = 0
                ORDER BY round_date DESC, round_time DESC
                LIMIT 1
            """, (map_name,))
            
            if not row:
                return None
            
            round_id, time_limit, actual_time, winner_team, round_outcome, _ = row
            
            # Get aggregated player stats from match summary
            player_stats = await self.bot.db_adapter.fetch_all("""
                SELECT 
                    player_name,
                    kills,
                    deaths,
                    damage_given,
                    accuracy,
                    headshots
                FROM player_comprehensive_stats
                WHERE round_id = ?
                ORDER BY kills DESC
                LIMIT 10
            """, (round_id,))
            
            # Calculate totals
            total_query = await self.bot.db_adapter.fetch_one("""
                SELECT 
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths,
                    SUM(damage_given) as total_damage,
                    COUNT(DISTINCT player_guid) as player_count
                FROM player_comprehensive_stats
                WHERE round_id = ?
            """, (round_id,))
            
            total_kills, total_deaths, total_damage, player_count = total_query
            
            return {
                'time_limit': time_limit,
                'actual_time': actual_time,
                'winner_team': winner_team,
                'round_outcome': round_outcome,
                'total_kills': total_kills or 0,
                'total_deaths': total_deaths or 0,
                'total_damage': total_damage or 0,
                'player_count': player_count or 0,
                'top_players': player_stats
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting match summary: {e}")
            return None
    
    async def _create_match_summary_embed(self, data: Dict[str, Any], filename: str, map_name: str) -> discord.Embed:
        """Create Discord embed for match summary"""
        embed = discord.Embed(
            title=f"🏆 Match Complete - {map_name}",
            description="**Stopwatch Mode** - Combined stats from both rounds",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        
        # Match outcome with stopwatch times
        outcome_text = f"**Round 1 Time:** {data['time_limit']}\n"
        outcome_text += f"**Round 2 Time:** {data['actual_time']}\n"
        
        if data['round_outcome']:
            outcome_text += f"**Result:** {data['round_outcome']}"
        
        embed.add_field(
            name="⏱️ Match Result",
            value=outcome_text,
            inline=False
        )
        
        # Top players (cumulative stats)
        if data['top_players']:
            top_text = []
            for i, (name, kills, deaths, dmg, acc, hs) in enumerate(data['top_players'][:5], 1):
                kd = f"{kills}/{deaths}"
                top_text.append(
                    f"{i}. **{name}** - {kd} K/D | {int(dmg):,} DMG | {acc:.1f}% ACC | {hs} HS"
                )
            
            embed.add_field(
                name="🏅 Top Performers (Both Rounds)",
                value="\n".join(top_text),
                inline=False
            )
        
        # Match totals
        embed.add_field(
            name="📊 Match Totals",
            value=(
                f"Players: {data['player_count']}\n"
                f"Total Kills: {data['total_kills']:,}\n"
                f"Total Deaths: {data['total_deaths']:,}\n"
                f"Total Damage: {int(data['total_damage']):,}"
            ),
            inline=True
        )
        
        embed.set_footer(text=f"Match summary from {filename}")
        
        return embed
    
    def get_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics"""
        avg_check_time = sum(self.check_times) / len(self.check_times) if self.check_times else 0
        avg_download_time = sum(self.download_times) / len(self.download_times) if self.download_times else 0
        
        return {
            'is_monitoring': self.is_monitoring,
            'files_processed': self.files_processed_count,
            'files_tracked': len(self.processed_files),
            'errors_count': self.errors_count,
            'last_error': self.last_error,
            'last_check': self.last_check_time,
            'avg_check_time_ms': avg_check_time * 1000,
            'avg_download_time_ms': avg_download_time * 1000,
            'check_interval': self.check_interval,
        }
