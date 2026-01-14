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
import shlex
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List
import discord

# Import services for comprehensive stats display
from bot.services.player_badge_service import PlayerBadgeService
from bot.services.player_display_name_service import PlayerDisplayNameService

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
        
        # SSH configuration from bot config object
        self.ssh_enabled = bot.config.ssh_enabled
        self.ssh_config = {
            "host": bot.config.ssh_host,
            "port": bot.config.ssh_port,
            "user": bot.config.ssh_user,
            "key_path": bot.config.ssh_key_path,
            "remote_path": bot.config.ssh_remote_path
        }
        
        # Discord configuration - use production channel for all match posts
        self.production_channel_id = bot.production_channel_id if hasattr(bot, 'production_channel_id') else 0
        self.admin_channel_id = bot.admin_channel_id if hasattr(bot, 'admin_channel_id') else 0

        # Statistics (for monitoring health)
        self.last_check_time: Optional[datetime] = None
        self.files_processed_count = 0
        self.errors_count = 0
        self.last_error: Optional[str] = None

        # Monitoring state
        self.is_monitoring = False
        self.processed_files = set()
        self.check_times = []
        self.download_times = []
        self.check_interval = bot.config.ssh_check_interval  # seconds

        # Startup optimization: only check recent files on first check

        # Initialize services for comprehensive stats display
        self.badge_service = PlayerBadgeService(bot.db_adapter)
        self.display_name_service = PlayerDisplayNameService(bot.db_adapter)
        self._is_first_check = True
        self.startup_lookback_hours = bot.config.ssh_startup_lookback_hours

        # Voice-conditional monitoring: only check SSH when players are in voice channels
        self.voice_conditional = bot.config.ssh_voice_conditional

        # Grace period: continue checking SSH for X minutes after players leave voice
        # (catches files that appear shortly after game ends)
        self.grace_period_minutes = bot.config.ssh_grace_period_minutes
        self.last_voice_activity_time: Optional[datetime] = None

        logger.info("🔄 SSH Monitor service initialized")
        if self.voice_conditional:
            logger.info(f"🎙️ Voice-conditional mode: SSH checks only when players in voice (grace period: {self.grace_period_minutes}min)")
    
    async def start_monitoring(self):
        """Start the SSH monitoring task"""
        logger.info(f"🔍 start_monitoring() called - ssh_enabled={self.ssh_enabled}")

        if not self.ssh_enabled:
            logger.warning("⚠️ SSH monitoring disabled in configuration (SSH_ENABLED=false or not set)")
            return

        logger.info("🔍 SSH enabled, validating configuration...")
        if not self._validate_config():
            logger.error("❌ SSH configuration invalid, cannot start monitoring")
            return

        self.is_monitoring = True
        logger.info("✅ SSH monitoring started")

        # Load previously processed files from database
        await self._load_processed_files()

        # Start monitoring loop
        logger.info("🔁 Starting monitoring loop...")
        asyncio.create_task(self._monitoring_loop())
    
    async def stop_monitoring(self):
        """Stop the SSH monitoring task"""
        self.is_monitoring = False
        logger.info("🛑 SSH monitoring stopped")
    
    def _validate_config(self) -> bool:
        """Validate SSH configuration"""
        required = [
            self.ssh_config['host'],
            self.ssh_config['user'],
            self.ssh_config['key_path'],
            self.ssh_config['remote_path']
        ]

        if not all(required):
            logger.error("❌ Missing SSH configuration:")
            if not self.ssh_config['host']: logger.error("  - SSH_HOST")
            if not self.ssh_config['user']: logger.error("  - SSH_USER")
            if not self.ssh_config['key_path']: logger.error("  - SSH_KEY_PATH")
            if not self.ssh_config['remote_path']: logger.error("  - REMOTE_STATS_PATH")
            return False

        return True
    
    async def _load_processed_files(self):
        """Load list of previously processed files from database"""
        try:
            rows = await self.bot.db_adapter.fetch_all(
                "SELECT filename FROM processed_files WHERE success = true",
                ()
            )
            self.processed_files = {row[0] for row in rows}
            logger.info(f"📋 Loaded {len(self.processed_files)} previously processed files")
        except Exception as e:
            logger.error(f"❌ Failed to load processed files: {e}")
    
    def _get_voice_player_count(self) -> int:
        """
        Get current number of players in gaming voice channels.

        Returns:
            int: Number of players in voice, or -1 if voice monitoring disabled
        """
        try:
            # Check if bot has gaming voice channels configured
            if not hasattr(self.bot, 'gaming_voice_channels') or not self.bot.gaming_voice_channels:
                return -1  # Voice monitoring disabled

            total_players = 0
            for channel_id in self.bot.gaming_voice_channels:
                channel = self.bot.get_channel(channel_id)
                if channel and isinstance(channel, discord.VoiceChannel):
                    total_players += len(channel.members)

            return total_players
        except Exception as e:
            logger.debug(f"Could not get voice player count: {e}")
            return -1  # Error means we should check anyway

    def _detect_match_type(self) -> str:
        """
        Detect if match is 3v3, 6v6, or regular based on voice channel player counts.

        Returns:
            str: "3v3", "6v6", or "regular"
        """
        try:
            if not hasattr(self.bot, 'gaming_voice_channels') or not self.bot.gaming_voice_channels:
                return "regular"

            # Count players in each voice channel
            channel_counts = []
            for channel_id in self.bot.gaming_voice_channels:
                channel = self.bot.get_channel(channel_id)
                if channel and isinstance(channel, discord.VoiceChannel):
                    player_count = len(channel.members)
                    if player_count > 0:
                        channel_counts.append(player_count)

            # Detect match type based on player distribution
            if len(channel_counts) == 2:
                if channel_counts[0] == 3 and channel_counts[1] == 3:
                    return "3v3"
                elif channel_counts[0] == 6 and channel_counts[1] == 6:
                    return "6v6"

            return "regular"
        except Exception as e:
            logger.debug(f"Could not detect match type: {e}")
            return "regular"

    async def _monitoring_loop(self):
        """Main monitoring loop - runs continuously"""
        logger.info("🔁 Monitoring loop started")

        while self.is_monitoring:
            try:
                start_time = datetime.now()

                # Voice-conditional check: only check SSH if players are in voice
                if self.voice_conditional:
                    voice_count = self._get_voice_player_count()

                    if voice_count > 0:
                        # Players in voice - update activity time and check SSH
                        self.last_voice_activity_time = datetime.now()
                        logger.info(f"🎙️ {voice_count} player(s) in voice - checking SSH")

                    elif voice_count == 0:
                        # No players in voice - check if we're in grace period
                        if self.last_voice_activity_time:
                            time_since_activity = (datetime.now() - self.last_voice_activity_time).total_seconds() / 60

                            if time_since_activity < self.grace_period_minutes:
                                # Still in grace period - continue checking
                                remaining = self.grace_period_minutes - time_since_activity
                                logger.info(f"⏳ Grace period: checking SSH ({remaining:.1f}min remaining)")
                            else:
                                # Grace period expired - skip SSH check
                                logger.info("⏭️ Skipping SSH check: no players in voice (grace period expired)")
                                await asyncio.sleep(self.check_interval)
                                continue
                        else:
                            # Never had voice activity yet - skip SSH check
                            logger.info("⏭️ Skipping SSH check: no players in voice channels")
                            await asyncio.sleep(self.check_interval)
                            continue

                    # voice_count == -1 means voice monitoring disabled, proceed with check

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
    
    def _parse_file_timestamp(self, filename: str) -> Optional[datetime]:
        """
        Parse timestamp from filename.

        Expected format: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
        Example: 2025-11-16-142030-supply-round-1.txt

        Returns:
            datetime object if parsing succeeds, None otherwise
        """
        try:
            parts = filename.split('-')
            if len(parts) < 5:
                return None

            # Extract date and time parts
            year = int(parts[0])
            month = int(parts[1])
            day = int(parts[2])
            time_str = parts[3]  # HHMMSS format

            # Parse time
            if len(time_str) != 6:
                return None

            hour = int(time_str[0:2])
            minute = int(time_str[2:4])
            second = int(time_str[4:6])

            return datetime(year, month, day, hour, minute, second)

        except (ValueError, IndexError) as e:
            logger.debug(f"Could not parse timestamp from filename {filename}: {e}")
            return None

    async def _check_for_new_files(self):
        """Check remote directory for new stats files"""
        try:
            # List remote files
            remote_files = await self._list_remote_files()

            if not remote_files:
                logger.debug("No files found on remote server")
                return

            # Filter for .stats files and .txt files (but exclude _ws.txt files)
            stats_files = [
                f for f in remote_files
                if (f.endswith('.stats') or f.endswith('.txt')) and not f.endswith('_ws.txt')
            ]

            # ALWAYS filter by time to avoid processing old files (not just first check)
            # This prevents re-processing thousands of old files if processed_files table gets cleared
            if self.startup_lookback_hours > 0:
                cutoff_time = datetime.now() - timedelta(hours=self.startup_lookback_hours)
                time_filtered_files = []

                for f in stats_files:
                    file_time = self._parse_file_timestamp(f)
                    if file_time and file_time >= cutoff_time:
                        time_filtered_files.append(f)
                    elif not file_time:
                        # If we can't parse the timestamp, skip it
                        logger.debug(f"Skipping file with unparseable timestamp: {f}")

                if self._is_first_check:
                    logger.info(f"📅 First check: filtered {len(stats_files)} files to {len(time_filtered_files)} from last {self.startup_lookback_hours}h")
                    self._is_first_check = False
                stats_files = time_filtered_files

            # Find new files (not in processed set)
            new_files = [f for f in stats_files if f not in self.processed_files]

            if new_files:
                logger.info(f"🆕 Found {len(new_files)} new file(s)")

                # Process each new file
                for filename in new_files:
                    await self._process_new_file(filename)
            else:
                # Use DEBUG level for routine "no new files" checks to reduce log noise
                logger.debug(f"✓ No new files (checked {len(stats_files)} files)")

        except Exception as e:
            logger.error(f"❌ Error checking for new files: {e}", exc_info=True)
            raise
    
    def _list_remote_files_sync(self) -> list:
        """List files in remote SSH directory (synchronous - use in executor)"""
        import paramiko
        from bot.automation.ssh_handler import configure_ssh_host_key_policy

        ssh = None
        try:
            # Create SSH client
            ssh = paramiko.SSHClient()
            configure_ssh_host_key_policy(ssh)

            # Connect
            ssh.connect(
                hostname=self.ssh_config['host'],
                port=self.ssh_config['port'],
                username=self.ssh_config['user'],
                key_filename=os.path.expanduser(self.ssh_config['key_path']),
                timeout=10
            )

            # List files (use shlex.quote to prevent shell injection)
            # remote_path is sanitized with shlex.quote before use in command
            safe_path = shlex.quote(self.ssh_config['remote_path'])
            # Safe to use in f-string: safe_path is properly quoted with shlex.quote
            stdin, stdout, stderr = ssh.exec_command(f"ls -1 {safe_path}")  # nosec B601
            files = stdout.read().decode().strip().split('\n')

            return [f.strip() for f in files if f.strip()]

        except Exception as e:
            logger.error(f"❌ SSH list files error: {e}")
            raise
        finally:
            if ssh:
                try:
                    ssh.close()
                except Exception as e:
                    # Log SSH close errors during cleanup (debug level only)
                    logger.debug(f"SSH close error during cleanup: {e}")

    async def _list_remote_files(self) -> list:
        """List files in remote SSH directory (async wrapper)"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._list_remote_files_sync)
    
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
            
            # NOTE: Discord posting is handled by endstats_monitor + RoundPublisherService
            # in ultimate_bot.py. SSHMonitor only handles file download and DB import.
            # The duplicate posting code below was removed to prevent:
            # 1. Double-posting (both systems were posting)
            # 2. Embed field overflow errors (SSHMonitor didn't handle 1024 char limit)
            
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
    
    def _download_file_sync(self, filename: str) -> Tuple[Optional[str], float]:
        """Download file from remote server (synchronous - use in executor)"""
        import paramiko
        from scp import SCPClient
        from bot.automation.ssh_handler import configure_ssh_host_key_policy

        download_start = datetime.now()
        ssh = None

        try:
            # Create SSH client
            ssh = paramiko.SSHClient()
            configure_ssh_host_key_policy(ssh)

            # Connect
            ssh.connect(
                hostname=self.ssh_config['host'],
                port=self.ssh_config['port'],
                username=self.ssh_config['user'],
                key_filename=os.path.expanduser(self.ssh_config['key_path']),
                timeout=10
            )

            # Download using SCP
            local_dir = "bot/local_stats"
            os.makedirs(local_dir, exist_ok=True)

            local_path = os.path.join(local_dir, filename)
            remote_path = f"{self.ssh_config['remote_path']}/{filename}"

            with SCPClient(ssh.get_transport()) as scp:
                scp.get(remote_path, local_path)

            # Calculate download time
            download_duration = (datetime.now() - download_start).total_seconds()

            return local_path, download_duration

        except Exception as e:
            logger.error(f"❌ Download error for {filename}: {e}")
            return None, 0.0
        finally:
            if ssh:
                try:
                    ssh.close()
                except Exception as e:
                    # Log SSH close errors during cleanup (debug level only)
                    logger.debug(f"SSH close error during cleanup: {e}")

    async def _download_file(self, filename: str) -> Optional[str]:
        """Download file from remote server (async wrapper)"""
        loop = asyncio.get_event_loop()
        local_path, download_duration = await loop.run_in_executor(
            None, self._download_file_sync, filename
        )

        if local_path:
            # Track download time
            if not hasattr(self, 'download_times'):
                self.download_times = []
            self.download_times.append(download_duration)
            if len(self.download_times) > 100:
                self.download_times.pop(0)

            logger.info(f"✅ Downloaded {filename} in {download_duration:.2f}s")

        return local_path
    
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
            channel = self.bot.get_channel(self.production_channel_id)

            if not channel:
                logger.error(f"❌ Production channel {self.production_channel_id} not found")
                # Notify admin channel about configuration issue
                admin_channel = self.bot.get_channel(self.admin_channel_id)
                if admin_channel:
                    await admin_channel.send(
                        f"⚠️ **Config Issue:** Production channel {self.production_channel_id} not found. "
                        f"Stats for `{filename}` could not be posted."
                    )
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
            # Get latest round from rounds table (exclude R0 match summaries)
            round_row = await self.bot.db_adapter.fetch_one("""
                SELECT
                    id,
                    round_number,
                    map_name,
                    round_date,
                    round_time
                FROM rounds
                WHERE round_number IN (1, 2)
                  AND (round_status = 'completed' OR round_status IS NULL)
                ORDER BY round_date DESC, round_time DESC
                LIMIT 1
            """, ())

            if not round_row:
                return None

            round_id, round_number, map_name, round_date, round_time = round_row

            # Get aggregated stats for this round
            totals = await self.bot.db_adapter.fetch_one("""
                SELECT
                    COUNT(DISTINCT player_guid) as player_count,
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths
                FROM player_comprehensive_stats
                WHERE round_id = $1
            """, (round_id,))

            player_count, kills, deaths = totals if totals else (0, 0, 0)

            # Get ALL players with comprehensive stats for this round
            top_players = await self.bot.db_adapter.fetch_all("""
                SELECT
                    p.player_name,
                    p.player_guid,
                    p.kills,
                    p.deaths,
                    p.gibs,
                    p.damage_given,
                    p.damage_received,
                    p.accuracy,
                    p.headshots,
                    p.headshot_kills,
                    p.time_played_seconds,
                    p.time_dead_ratio,
                    p.denied_playtime,
                    p.most_useful_kills,
                    p.revives_given,
                    p.times_revived,
                    p.double_kills,
                    p.triple_kills,
                    p.quad_kills,
                    p.multi_kills,
                    p.mega_kills
                FROM player_comprehensive_stats p
                LEFT JOIN (
                    SELECT round_id, player_guid, SUM(hits) as hits, SUM(shots) as shots
                    FROM weapon_comprehensive_stats
                    WHERE weapon_name NOT IN ('WS_GRENADE', 'WS_SYRINGE', 'WS_DYNAMITE', 'WS_AIRSTRIKE', 'WS_ARTILLERY', 'WS_SATCHEL', 'WS_LANDMINE')
                    GROUP BY round_id, player_guid
                ) w ON p.round_id = w.round_id AND p.player_guid = w.player_guid
                WHERE p.round_id = $1
                ORDER BY p.kills DESC
            """, (round_id,))

            return {
                'round_id': round_id,
                'round_num': round_number,
                'map_name': map_name,
                'player_count': player_count,
                'total_kills': kills or 0,
                'total_deaths': deaths or 0,
                'round_date': round_date,
                'round_time': round_time,
                'top_players': top_players
            }

        except Exception as e:
            logger.error(f"❌ Error getting round data: {e}", exc_info=True)
            return None
    
    async def _create_round_embed(self, data: Dict[str, Any], filename: str) -> discord.Embed:
        """Create Discord embed for round stats with comprehensive 3-line format"""
        embed = discord.Embed(
            title=f"🎮 Round {data['round_num']} Complete!",
            description=f"**Map:** {data['map_name']}\n**Players:** {data['player_count']}",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )

        # Get all players with comprehensive stats
        if data['top_players']:
            # Fetch badges and display names for all players
            player_guids = [player[1] for player in data['top_players']]  # player_guid is at index 1
            player_badges = await self.badge_service.get_player_badges_batch(player_guids)
            display_names = await self.display_name_service.get_display_names_batch(player_guids)

            # Build player display with 3-line format
            medals = ["🥇", "🥈", "🥉"]
            field_text = ""

            for i, player_data in enumerate(data['top_players']):
                # Unpack comprehensive player data
                (name, player_guid, kills, deaths, gibs, dmg_given, dmg_recv, acc,
                 total_hs, hsk, time_played, time_dead_ratio, denied, useful_kills,
                 revives, times_revived, double, triple, quad, multi, mega) = player_data

                # Use display name if available
                display_name = display_names.get(player_guid, name)

                # Handle NULL values
                kills = kills or 0
                deaths = deaths or 0
                gibs = gibs or 0
                dmg_given = dmg_given or 0
                dmg_recv = dmg_recv or 0
                total_hs = total_hs or 0
                time_played = time_played or 0
                time_dead_ratio = time_dead_ratio or 0
                denied = denied or 0
                useful_kills = useful_kills or 0
                revives = revives or 0
                times_revived = times_revived or 0

                # Calculate metrics
                kd_ratio = kills / deaths if deaths > 0 else kills
                hs_rate = (total_hs / kills * 100) if kills > 0 else 0

                # Calculate DPM (damage per minute)
                dpm = (dmg_given * 60.0) / time_played if time_played > 0 else 0

                # Format times
                minutes = int(time_played // 60)
                seconds = int(time_played % 60)
                time_display = f"{minutes}:{seconds:02d}"

                time_dead = int(time_played * time_dead_ratio / 100.0)
                dead_minutes = int(time_dead // 60)
                dead_seconds = int(time_dead % 60)
                time_dead_display = f"{dead_minutes}:{dead_seconds:02d}"

                denied_minutes = int(denied // 60)
                denied_seconds = int(denied % 60)
                time_denied_display = f"{denied_minutes}:{denied_seconds:02d}"

                # Format damage (show in K if over 1000)
                dmg_given_display = f"{dmg_given/1000:.1f}K" if dmg_given >= 1000 else f"{dmg_given}"
                dmg_recv_display = f"{dmg_recv/1000:.1f}K" if dmg_recv >= 1000 else f"{dmg_recv}"

                # Medal (top 3)
                if i < len(medals):
                    medal = medals[i]
                else:
                    # Generate number emoji for ranks beyond 3
                    rank_num = str(i + 1)
                    emoji_digits = {'0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
                                   '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'}
                    medal = ''.join(emoji_digits[d] for d in rank_num)

                # Get achievement badges
                badges = ""
                if player_guid in player_badges:
                    badges = f" {player_badges[player_guid]}"

                # Build multikills string
                multikills_parts = []
                if double: multikills_parts.append(f"{double}DBL")
                if triple: multikills_parts.append(f"{triple}TPL")
                if quad: multikills_parts.append(f"{quad}QD")
                if multi: multikills_parts.append(f"{multi}PNT")
                if mega: multikills_parts.append(f"{mega}MGA")
                multikills_display = f" • {' '.join(multikills_parts)}" if multikills_parts else ""

                # Three-line format
                # Line 1: Medal + Name + Badges
                field_text += f"{medal} **{display_name}**{badges}\n"

                # Line 2: Combat essentials (K/D/G, DPM, damage, accuracy, headshots)
                field_text += (
                    f"   {kills}K/{deaths}D/{gibs}G ({kd_ratio:.2f}) • "
                    f"{dpm:.0f} DPM • {dmg_given_display}⬆/{dmg_recv_display}⬇ • "
                    f"{acc:.1f}% ACC • {total_hs} HS ({hs_rate:.1f}%)\n"
                )

                # Line 3: Support/meta stats (UK, revives, times, multikills)
                field_text += (
                    f"   {useful_kills} UK • {revives}↑/{times_revived}↓ • "
                    f"⏱{time_display} 💀{time_dead_display} ⏳{time_denied_display}{multikills_display}\n\n"
                )

            embed.add_field(
                name="🏆 All Players",
                value=field_text.rstrip(),
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
            channel = self.bot.get_channel(self.production_channel_id)

            if not channel:
                logger.error(f"❌ Production channel {self.production_channel_id} not found")
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
                    round_outcome
                FROM rounds
                WHERE map_name = ? AND round_number = 0
                ORDER BY round_date DESC, round_time DESC
                LIMIT 1
            """, (map_name,))

            if not row:
                return None

            round_id, time_limit, actual_time, winner_team, round_outcome = row
            
            # Get ALL player stats with comprehensive data from match summary
            player_stats = await self.bot.db_adapter.fetch_all("""
                SELECT
                    player_name,
                    player_guid,
                    kills,
                    deaths,
                    gibs,
                    damage_given,
                    damage_received,
                    accuracy,
                    headshots,
                    headshot_kills,
                    time_played_seconds,
                    time_dead_ratio,
                    denied_playtime,
                    most_useful_kills,
                    revives_given,
                    times_revived,
                    double_kills,
                    triple_kills,
                    quad_kills,
                    multi_kills,
                    mega_kills
                FROM player_comprehensive_stats
                WHERE round_id = ?
                ORDER BY kills DESC
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
        """Create Discord embed for match summary with comprehensive 3-line format"""
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

        # ALL players (cumulative stats) with comprehensive 3-line format
        if data['top_players']:
            # Fetch badges and display names for all players
            player_guids = [player[1] for player in data['top_players']]  # player_guid at index 1
            player_badges = await self.badge_service.get_player_badges_batch(player_guids)
            display_names = await self.display_name_service.get_display_names_batch(player_guids)

            # Build player display with 3-line format
            medals = ["🥇", "🥈", "🥉"]
            field_text = ""

            for i, player_data in enumerate(data['top_players']):
                # Unpack comprehensive player data
                (name, player_guid, kills, deaths, gibs, dmg_given, dmg_recv, acc,
                 total_hs, hsk, time_played, time_dead_ratio, denied, useful_kills,
                 revives, times_revived, double, triple, quad, multi, mega) = player_data

                # Use display name if available
                display_name = display_names.get(player_guid, name)

                # Handle NULL values
                kills = kills or 0
                deaths = deaths or 0
                gibs = gibs or 0
                dmg_given = dmg_given or 0
                dmg_recv = dmg_recv or 0
                total_hs = total_hs or 0
                time_played = time_played or 0
                time_dead_ratio = time_dead_ratio or 0
                denied = denied or 0
                useful_kills = useful_kills or 0
                revives = revives or 0
                times_revived = times_revived or 0

                # Calculate metrics
                kd_ratio = kills / deaths if deaths > 0 else kills
                hs_rate = (total_hs / kills * 100) if kills > 0 else 0

                # Calculate DPM (damage per minute)
                dpm = (dmg_given * 60.0) / time_played if time_played > 0 else 0

                # Format times
                minutes = int(time_played // 60)
                seconds = int(time_played % 60)
                time_display = f"{minutes}:{seconds:02d}"

                time_dead = int(time_played * time_dead_ratio / 100.0)
                dead_minutes = int(time_dead // 60)
                dead_seconds = int(time_dead % 60)
                time_dead_display = f"{dead_minutes}:{dead_seconds:02d}"

                denied_minutes = int(denied // 60)
                denied_seconds = int(denied % 60)
                time_denied_display = f"{denied_minutes}:{denied_seconds:02d}"

                # Format damage (show in K if over 1000)
                dmg_given_display = f"{dmg_given/1000:.1f}K" if dmg_given >= 1000 else f"{dmg_given}"
                dmg_recv_display = f"{dmg_recv/1000:.1f}K" if dmg_recv >= 1000 else f"{dmg_recv}"

                # Medal (top 3)
                if i < len(medals):
                    medal = medals[i]
                else:
                    # Generate number emoji for ranks beyond 3
                    rank_num = str(i + 1)
                    emoji_digits = {'0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
                                   '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'}
                    medal = ''.join(emoji_digits[d] for d in rank_num)

                # Get achievement badges
                badges = ""
                if player_guid in player_badges:
                    badges = f" {player_badges[player_guid]}"

                # Build multikills string
                multikills_parts = []
                if double: multikills_parts.append(f"{double}DBL")
                if triple: multikills_parts.append(f"{triple}TPL")
                if quad: multikills_parts.append(f"{quad}QD")
                if multi: multikills_parts.append(f"{multi}PNT")
                if mega: multikills_parts.append(f"{mega}MGA")
                multikills_display = f" • {' '.join(multikills_parts)}" if multikills_parts else ""

                # Three-line format
                # Line 1: Medal + Name + Badges
                field_text += f"{medal} **{display_name}**{badges}\n"

                # Line 2: Combat essentials (K/D/G, DPM, damage, accuracy, headshots)
                field_text += (
                    f"   {kills}K/{deaths}D/{gibs}G ({kd_ratio:.2f}) • "
                    f"{dpm:.0f} DPM • {dmg_given_display}⬆/{dmg_recv_display}⬇ • "
                    f"{acc:.1f}% ACC • {total_hs} HS ({hs_rate:.1f}%)\n"
                )

                # Line 3: Support/meta stats (UK, revives, times, multikills)
                field_text += (
                    f"   {useful_kills} UK • {revives}↑/{times_revived}↓ • "
                    f"⏱{time_display} 💀{time_dead_display} ⏳{time_denied_display}{multikills_display}\n\n"
                )

            embed.add_field(
                name="🏅 All Performers (Both Rounds)",
                value=field_text.rstrip(),
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
