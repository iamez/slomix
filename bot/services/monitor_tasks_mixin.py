"""UltimateETLegacyBot mixin: Discord.ext.tasks background loops.

Extracted from ultimate_bot.py in P3e Sprint 7 / C.4b.

Contains the 4 long-running task loops:
- endstats_monitor (SSH poll for stats files, 60s)
- cache_refresher (stats_cache TTL refresh, 30s)
- voice_session_monitor (auto-end session on voice empty, 30s)
- live_status_updater (website live status push, 30s)

Each has a paired before_loop helper. `_auto_end_session` is called by
voice_session_monitor and lives here for locality.

⚠️  NOTE ON MIXIN INHERITANCE FOR discord.ext.tasks.Loop:
@tasks.loop(seconds=N) returns a Loop OBJECT (not a function). The Loop
lives as a class attribute on this mixin. When UltimateETLegacyBot is
instantiated, `self.endstats_monitor.start()` (called from the main
class setup_hook) resolves via MRO to the Loop on this mixin, but the
Loop is still the same class-level object. This works the same as if
the loop lived directly on the main class.

All methods live on UltimateETLegacyBot via mixin inheritance. Runtime
attributes consumed here are set in the main class ``__init__``:
``self.db_adapter``, ``self.config``, ``self.file_tracker``,
``self.voice_session_service``, the voice tracker state, etc.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime

from discord.ext import tasks

from bot.automation import SSHHandler
from bot.logging_config import get_logger

logger = get_logger("bot.core")


class _MonitorTasksMixin:
    """Discord.ext.tasks background loops for UltimateETLegacyBot."""

    @tasks.loop(seconds=60)
    async def endstats_monitor(self):
        """
        🔄 SSH Monitoring Task - Optimized Performance with Grace Period

        **Performance Optimization with File Loss Prevention:**
        - Dead Hours (02:00-11:00 CET): No SSH checks
        - Active Mode: 6+ players in voice → check every 60s
        - Grace Period: Within 30min of last file → check every 60s (prevents file loss during player drops)
        - Idle Mode: No players + no recent files → check every 10min (reduced from 6hr to prevent file loss)
        - Uses counter-based intervals with grace period logic

        Monitors remote game server for new stats files:
        1. Lists files on remote server via SSH
        2. Compares with processed_files tracking
        3. Downloads new files
        4. Parses and imports to database
        5. Posts Discord round summaries automatically
        6. Detects and marks round restarts/cancellations

        **Old system:** ~2,880 SSH checks/day (every 30s continuously)
        **New system:** ~200 SSH checks/day (with grace period + 10min idle)
        **File loss prevention:** Grace period keeps checking for 30min after last file
        """
        if not self.monitoring or not self.ssh_enabled:
            return

        # ========== WEBSOCKET STATUS CHECK ==========
        # WebSocket support is DEPRECATED (Dec 2025) - Discord Webhook approach replaces it
        # Keeping this check for backwards compatibility only
        # VPS now uses stats_webhook_notify.py to POST directly to Discord
        ws_active = False
        if hasattr(self, 'ws_client') and self.ws_client and self.config.ws_enabled:
            ws_active = getattr(self.ws_client, 'is_connected', False)
            # Also check if we've received data recently (within 5 min)
            if ws_active and hasattr(self.ws_client, 'last_notification'):
                last_notif = self.ws_client.last_notification
                if last_notif:
                    time_since_notif = (datetime.now() - last_notif).total_seconds()
                    # If no notification in 5 min, WebSocket might be stale
                    if time_since_notif > 300:
                        ws_active = False
                        logger.info(
                            f"⚠️ WebSocket connected but no data in {time_since_notif:.0f}s - using SSH fallback"
                        )

        if ws_active:
            # WebSocket is working - skip SSH polling
            logger.debug("🔌 WebSocket active - skipping SSH polling this cycle")
            return

        try:
            # ========== DEAD HOURS CHECK (02:00-11:00 CET) ==========
            try:
                import pytz
                cet = pytz.timezone("Europe/Paris")
            except ImportError:
                try:
                    from zoneinfo import ZoneInfo
                    cet = ZoneInfo("Europe/Paris")
                except ImportError:
                    cet = None

            now = datetime.now(cet) if cet else datetime.now()
            hour = now.hour

            # Skip SSH check during dead hours (02:00-11:00)
            if 2 <= hour < 11:
                # Log once per hour instead of every 60s
                if not hasattr(self, '_last_dead_hour_log') or self._last_dead_hour_log != hour:
                    self._last_dead_hour_log = hour
                    logger.info(f"⏸️ Dead hours ({hour:02d}:00 CET) - SSH checks paused until 11:00")
                return

            # ========== VOICE DETECTION (Player Count Check) ==========
            total_players = 0
            for channel_id in self.gaming_voice_channels:
                channel = self.get_channel(channel_id)
                if channel and hasattr(channel, "members"):
                    total_players += sum(1 for m in channel.members if not m.bot)

            # ========== INTERVAL-BASED CHECKING (Counter System with Grace Period) ==========
            self.ssh_check_counter += 1

            # Calculate time since last file was downloaded
            grace_period_active = False
            grace_period_seconds = self.config.monitoring_grace_period_minutes * 60
            if hasattr(self, 'last_file_download_time') and self.last_file_download_time:
                time_since_last_file = (datetime.now() - self.last_file_download_time).total_seconds()
                grace_period_active = time_since_last_file < grace_period_seconds

            if total_players >= 6 or grace_period_active:
                # ACTIVE MODE: Check every 60 seconds (every 1 cycle)
                # Triggered by: 6+ players in voice OR within grace period of last file
                interval = 1
                mode = "ACTIVE (players)" if total_players >= 6 else "ACTIVE (grace period)"
            else:
                # IDLE MODE: Check every 10 minutes (10 cycles at 60s each)
                # 🔧 REDUCED from 6 hours to 10 minutes to prevent file loss
                interval = 10
                mode = "IDLE"

            # Only perform SSH check when counter reaches interval
            if self.ssh_check_counter < interval:
                logger.debug(
                    f"⏭️  Skipping SSH check ({mode} mode: "
                    f"{self.ssh_check_counter}/{interval}, "
                    f"{total_players} players in voice)"
                )
                return

            # Reset counter and perform check
            self.ssh_check_counter = 0
            logger.info(
                f"🔍 SSH check triggered ({mode} mode, "
                f"{total_players} players in voice)"
            )

            # ========== SSH CHECK EXECUTION ==========
            # Build SSH config from config object
            ssh_config = {
                "host": self.config.ssh_host,
                "port": self.config.ssh_port,
                "user": self.config.ssh_user,
                "key_path": self.config.ssh_key_path,
                "remote_path": self.config.ssh_remote_path,
            }

            # Validate SSH config
            if not all([
                ssh_config["host"],
                ssh_config["user"],
                ssh_config["key_path"],
                ssh_config["remote_path"],
            ]):
                logger.warning(
                    "⚠️ SSH config incomplete - monitoring disabled\n"
                    f"   Host: {ssh_config['host']}\n"
                    f"   User: {ssh_config['user']}\n"
                    f"   Key: {ssh_config['key_path']}\n"
                    f"   Path: {ssh_config['remote_path']}"
                )
                return

            # List remote files
            logger.debug(f"📡 Connecting to SSH: {ssh_config['user']}@{ssh_config['host']}:{ssh_config['port']}")
            remote_files = await SSHHandler.list_remote_files(ssh_config)

            if not remote_files:
                logger.debug("📂 No remote files found or SSH connection failed")
                return

            logger.debug(f"📂 Found {len(remote_files)} total files on remote server")

            # Check each file
            new_files_count = 0
            for filename in sorted(remote_files):
                is_endstats = filename.endswith('-endstats.txt')

                if is_endstats:
                    should_process = await self._should_process_endstats_file(filename)
                else:
                    # Check if already processed (4-layer check)
                    should_process = await self.file_tracker.should_process_file(filename)

                if should_process:
                    new_files_count += 1
                    logger.info("=" * 60)
                    logger.info(f"📥 NEW FILE DETECTED: {filename}")
                    logger.info("=" * 60)

                    # Download file
                    download_start = time.time()
                    local_path = await SSHHandler.download_file(
                        ssh_config, filename, "local_stats"
                    )
                    download_time = time.time() - download_start

                    if local_path:
                        logger.info(f"✅ Downloaded in {download_time:.2f}s: {local_path}")

                        # Track download time for grace period logic
                        self.last_file_download_time = datetime.now()

                        # Wait 3 seconds for file to fully write
                        logger.debug("⏳ Waiting 3s for file to fully write...")
                        await asyncio.sleep(3)

                        # Process the file (imports to DB)
                        logger.info(f"⚙️ Processing file: {filename}")
                        process_start = time.time()

                        # Route endstats files to dedicated processor
                        if is_endstats:
                            logger.info("🏆 Detected endstats file, using endstats processor")
                            await self._process_endstats_file(local_path, filename)
                            process_time = time.time() - process_start
                            logger.info(f"⚙️ Processing completed in {process_time:.2f}s")
                        else:
                            # Regular stats file processing
                            override_metadata = self._pop_pending_metadata(filename)
                            result = await self.process_gamestats_file(local_path, filename, override_metadata=override_metadata)
                            process_time = time.time() - process_start

                            logger.info(f"⚙️ Processing completed in {process_time:.2f}s")

                            # 🆕 AUTO-POST to Discord after processing!
                            if result and result.get('success'):
                                logger.info(f"📊 Posting to Discord: {result.get('player_count', 0)} players")
                                try:
                                    await self.round_publisher.publish_round_stats(filename, result)
                                    logger.info(f"✅ Successfully processed and posted: {filename}")
                                except Exception as post_err:
                                    logger.error(f"❌ Discord post FAILED for {filename}: {post_err}", exc_info=True)
                                    await self.track_error(
                                        "discord_posting",
                                        f"Failed to post {filename}: {post_err}",
                                        max_consecutive=2,
                                    )

                                # 👥 AUTO-DETECT TEAMS after R2 import (FIX 2026-02-01)
                                # Trigger team detection when we have both rounds of data
                                await self._trigger_team_detection(filename)
                            else:
                                error_msg = result.get('error', 'Unknown error') if result else 'No result'
                                logger.warning(f"⚠️ Processing failed for {filename}: {error_msg}")
                                logger.warning("⚠️ Skipping Discord post")
                    else:
                        logger.error(f"❌ Download failed for {filename}")

            # Process Lua gametimes fallback files (JSON) if enabled
            await self._process_remote_gametimes_files()

            # Retroactively apply timing from lua_round_teams to rounds that were
            # processed before gametime data arrived (backlog replay scenario)
            await self._reconcile_missing_round_timing()

            if new_files_count == 0:
                logger.debug(f"✅ All {len(remote_files)} files already processed")
            else:
                logger.info(f"🎉 Processed {new_files_count} new file(s) this check")

            # Reset error tracking on successful cycle
            self.reset_error_tracking("ssh_monitor")

        except Exception as e:
            logger.error(f"❌ endstats_monitor error: {e}", exc_info=True)
            # Track consecutive errors and alert admins if threshold reached
            await self.track_error("ssh_monitor", str(e), max_consecutive=3)

    @endstats_monitor.before_loop
    async def before_endstats_monitor(self):
        """Wait for bot to be ready before starting SSH monitoring"""
        await self.wait_until_ready()
        logger.info("✅ SSH monitoring task ready (optimized with voice detection)")

    @tasks.loop(seconds=30)
    async def cache_refresher(self):
        """
        🔄 Cache Refresh Task - Runs every 30 seconds

        Keeps in-memory cache in sync with database.
        Uses incremental delta queries after the initial full load
        to avoid fetching all 4000+ rows every cycle.
        """
        try:
            from datetime import datetime

            if not hasattr(self, '_cache_last_refresh'):
                # First run: full load
                self.processed_files = await self.file_repository.get_processed_filenames()
                self._cache_last_refresh = datetime.utcnow()
            else:
                # Subsequent runs: incremental delta only
                new_files = await self.file_repository.get_newly_processed_filenames(
                    self._cache_last_refresh
                )
                if new_files:
                    self.processed_files.update(new_files)
                self._cache_last_refresh = datetime.utcnow()

        except Exception as e:
            logger.debug(f"Cache refresh error: {e}")

    @cache_refresher.before_loop
    async def before_cache_refresher(self):
        """Wait for bot to be ready"""
        await self.wait_until_ready()

    @tasks.loop(seconds=30)
    async def voice_session_monitor(self):
        """
        🎙️ Voice Session Monitor - Runs every 30 seconds

        Monitors voice channels for session end:
        - Counts players in gaming voice channels
        - Starts 3-minute timer when players drop below threshold
        - Auto-ends session and posts summary
        - Cancels timer if players return
        """
        if not self.automation_enabled:
            return

        try:
            # Count players in gaming voice channels
            total_players = 0
            for channel_id in self.gaming_voice_channels:
                channel = self.get_channel(channel_id)
                if channel and hasattr(channel, "members"):
                    # Count non-bot members
                    total_players += sum(
                        1 for m in channel.members if not m.bot
                    )

            # Check if below threshold
            if total_players < self.session_end_threshold:
                if self.session_active and not self.session_end_timer:
                    # Start timer
                    self.session_end_timer = datetime.now()
                    logger.info(
                        f"⏱️ Session end timer started "
                        f"({total_players} < {self.session_end_threshold})"
                    )

                elif self.session_end_timer:
                    # Check if timer expired
                    elapsed = (datetime.now() - self.session_end_timer).seconds
                    if elapsed >= self.session_end_delay:
                        logger.info(
                            "🏁 3 minutes elapsed - auto-ending session"
                        )
                        await self._auto_end_session()
            else:
                # Players returned - cancel timer
                if self.session_end_timer:
                    logger.info(
                        f"⏰ Session end cancelled - players returned "
                        f"({total_players})"
                    )
                    self.session_end_timer = None

        except Exception as e:
            logger.error(f"Voice monitor error: {e}")

    async def _auto_end_session(self):
        """Auto-end session via voice session service.

        Delegates to VoiceSessionService which handles:
        - Session state cleanup
        - Discord notification
        - Session results finalization (team W/L tracking)
        """
        try:
            if hasattr(self, 'voice_session_service') and self.voice_session_service:
                await self.voice_session_service.auto_end_session()
            else:
                logger.warning("Voice session service not available for auto-end")

            # Reset local state
            self.session_active = False
            self.session_end_timer = None
        except Exception as e:
            logger.error(f"Error in _auto_end_session: {e}", exc_info=True)
            self.session_active = False
            self.session_end_timer = None

    @voice_session_monitor.before_loop
    async def before_voice_monitor(self):
        """Wait for bot to be ready"""
        await self.wait_until_ready()

    @tasks.loop(seconds=30)
    async def live_status_updater(self):
        """
        🌐 Website Live Status Updater - Runs every 30 seconds

        Updates the live_status database table with:
        - Voice channel members (who's in gaming voice)
        - Game server status (online/offline, map, player count)

        This data is consumed by the website's /api/live-status endpoint.
        """
        rcon = None  # Track RCON connection for cleanup
        try:
            # Skip if database not ready or bot is closing
            if not hasattr(self, 'db_adapter') or not self.db_adapter:
                return
            if self.is_closed():
                return

            # ========== VOICE CHANNEL STATUS ==========
            voice_members = []
            voice_count = 0

            if hasattr(self, 'gaming_voice_channels') and self.gaming_voice_channels:
                for channel_id in self.gaming_voice_channels:
                    channel = self.get_channel(channel_id)
                    if channel and hasattr(channel, 'members'):
                        for member in channel.members:
                            if not member.bot:
                                voice_members.append({
                                    'id': member.id,
                                    'name': member.display_name,
                                    'avatar': str(member.display_avatar.url) if member.display_avatar else None
                                })
                                voice_count += 1

            voice_data = {
                'count': voice_count,
                'members': voice_members,
                'channel_name': 'Gaming',
            }

            # ========== GAME SERVER STATUS ==========
            server_data = {
                'online': False,
                'map': None,
                'player_count': 0,
                'max_players': 20,
                'players': [],
            }

            # Try to get server status via RCON (from ServerControl cog)
            try:
                server_cog = self.get_cog('ServerControl')
                if server_cog and server_cog.rcon_enabled and server_cog.rcon_password:
                    from bot.cogs.server_control import ETLegacyRCON
                    rcon = ETLegacyRCON(
                        server_cog.rcon_host,
                        server_cog.rcon_port,
                        server_cog.rcon_password
                    )
                    try:
                        # Run RCON in executor to avoid blocking event loop
                        loop = asyncio.get_running_loop()
                        status_response = await loop.run_in_executor(
                            None, rcon.send_command, 'status'
                        )
                        await loop.run_in_executor(None, rcon.close)
                        rcon = None

                        if status_response and 'Error' not in status_response:
                            server_data['online'] = True

                            # Parse map name
                            for line in status_response.split('\n'):
                                if line.startswith('map:'):
                                    server_data['map'] = line.split(':', 1)[1].strip()
                                    break

                            # Parse players (each line after header has: num score ping name)
                            player_lines = []
                            in_player_section = False
                            for line in status_response.split('\n'):
                                if 'num score ping' in line.lower():
                                    in_player_section = True
                                    continue
                                if in_player_section and line.strip():
                                    parts = line.split()
                                    if len(parts) >= 4:
                                        # Extract player name (may contain spaces)
                                        name = ' '.join(parts[3:])
                                        # Remove color codes ^1, ^2, etc.
                                        clean_name = re.sub(r'\^[0-9]', '', name)
                                        player_lines.append({'name': clean_name.strip()})

                            server_data['players'] = player_lines
                            server_data['player_count'] = len(player_lines)
                    except Exception:
                        if rcon:
                            rcon.close()
                            rcon = None
            except Exception as e:
                logger.debug(f"RCON status check failed: {e}")
                if rcon:
                    rcon.close()
                    rcon = None

            # ========== UPDATE DATABASE ==========
            # Update voice channel status
            await self.db_adapter.execute(
                """
                INSERT INTO live_status (status_type, status_data, updated_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT (status_type) DO UPDATE SET
                    status_data = $2,
                    updated_at = NOW()
                """,
                ('voice_channel', json.dumps(voice_data))
            )

            # Update game server status
            await self.db_adapter.execute(
                """
                INSERT INTO live_status (status_type, status_data, updated_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT (status_type) DO UPDATE SET
                    status_data = $2,
                    updated_at = NOW()
                """,
                ('game_server', json.dumps(server_data))
            )

            logger.debug(
                f"🌐 Live status updated: {voice_count} in voice, "
                f"server {'online' if server_data['online'] else 'offline'}"
            )

        except asyncio.CancelledError:
            # Graceful shutdown - clean up RCON if needed
            if rcon:
                try:
                    rcon.close()
                except Exception:
                    logger.debug("RCON cleanup failed during shutdown", exc_info=True)
            logger.info("Live status updater stopped (shutdown)")
            raise  # Re-raise to properly cancel the task

        except Exception as e:
            # Clean up RCON on any error
            if rcon:
                try:
                    rcon.close()
                except Exception:
                    logger.debug("RCON cleanup failed after error", exc_info=True)
            logger.error(f"Live status update error: {e}", exc_info=True)

    @live_status_updater.before_loop
    async def before_live_status_updater(self):
        """Wait for bot to be ready"""
        await self.wait_until_ready()
