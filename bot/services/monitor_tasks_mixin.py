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
from pathlib import Path

from discord.ext import tasks

from bot.automation import SSHHandler
from bot.core.dead_hours import DEAD_HOURS_END, is_dead_hour
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
                    time_since_notif = (datetime.now() - last_notif).total_seconds()  # noqa: DTZ005 naive datetime intentional — local/UTC mix is project convention (CET game server + UTC prod). See PR #216 rationale
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
            # ========== DEAD HOURS CHECK (bot/core/dead_hours.py) ==========
            try:
                import pytz
                cet = pytz.timezone("Europe/Paris")
            except ImportError:
                try:
                    from zoneinfo import ZoneInfo
                    cet = ZoneInfo("Europe/Paris")
                except ImportError:
                    cet = None

            now = datetime.now(cet) if cet else datetime.now()  # noqa: DTZ005 naive datetime intentional — local/UTC mix is project convention (CET game server + UTC prod). See PR #216 rationale
            hour = now.hour

            # Skip SSH check during dead hours. Window constants are shared
            # with the proximity relinker's permanent-orphan cutoff
            # (bot/core/dead_hours.py) — the two MUST agree or night rounds
            # get written off as orphans before imports resume.
            if is_dead_hour(hour):
                # Log once per hour instead of every 60s
                if not hasattr(self, '_last_dead_hour_log') or self._last_dead_hour_log != hour:
                    self._last_dead_hour_log = hour
                    # tzname() gives CET in winter / CEST in summer; the old
                    # hardcoded "CET" label was wrong half the year.
                    tz_label = now.tzname() or "local"
                    logger.info(
                        f"⏸️ Dead hours ({hour:02d}:00 {tz_label}) - SSH checks paused "
                        f"until {DEAD_HOURS_END:02d}:00"
                    )
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
                time_since_last_file = (datetime.now() - self.last_file_download_time).total_seconds()  # noqa: DTZ005 naive datetime intentional — local/UTC mix is project convention (CET game server + UTC prod). See PR #216 rationale
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
                        self.last_file_download_time = datetime.now()  # noqa: DTZ005 naive datetime intentional — local/UTC mix is project convention (CET game server + UTC prod). See PR #216 rationale

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
                            override_metadata = await self._pop_pending_metadata(filename)
                            result = await self.process_gamestats_file(local_path, filename, override_metadata=override_metadata)
                            process_time = time.time() - process_start

                            logger.info(f"⚙️ Processing completed in {process_time:.2f}s")

                            # 🆕 AUTO-POST to Discord after processing when enabled.
                            if result and result.get('success'):
                                logger.info(
                                    f"📊 Publishing stats if autopost enabled: {result.get('player_count', 0)} players"
                                )
                                try:
                                    posted = await self.round_publisher.publish_round_stats(filename, result)
                                    if posted:
                                        logger.info(f"✅ Successfully processed and posted: {filename}")
                                    else:
                                        logger.info(f"✅ Successfully processed; round stats autopost skipped: {filename}")
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
            from datetime import datetime, timezone

            # naive UTC preserves prior datetime.utcnow() behavior — the
            # `_cache_last_refresh` is passed to file_repository which expects
            # naive datetimes for comparison against TIMESTAMP columns.
            def _utcnow_naive() -> datetime:
                return datetime.now(timezone.utc).replace(tzinfo=None)

            if not hasattr(self, '_cache_last_refresh'):
                # First run: full load
                self.processed_files = await self.file_repository.get_processed_filenames()
                self._cache_last_refresh = _utcnow_naive()
            else:
                # Subsequent runs: incremental delta only
                new_files = await self.file_repository.get_newly_processed_filenames(
                    self._cache_last_refresh
                )
                if new_files:
                    self.processed_files.update(new_files)
                self._cache_last_refresh = _utcnow_naive()

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
                    self.session_end_timer = datetime.now()  # noqa: DTZ005 naive datetime intentional — local/UTC mix is project convention (CET game server + UTC prod). See PR #216 rationale
                    logger.info(
                        f"⏱️ Session end timer started "
                        f"({total_players} < {self.session_end_threshold})"
                    )

                elif self.session_end_timer:
                    # Check if timer expired
                    elapsed = (datetime.now() - self.session_end_timer).seconds  # noqa: DTZ005 naive datetime intentional — local/UTC mix is project convention (CET game server + UTC prod). See PR #216 rationale
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

    # ------------------------------------------------------------------
    # Idle-server watchdog: reload a neutral map when the server sits empty
    # so it doesn't stay on a stale map after a session (FM1/FM2). Reads the
    # player/voice counts that live_status_updater already writes to the
    # live_status table (no extra RCON poll). Dry-run by default.
    # NEVER uses map_restart — issues a FULL `map <name>` load (et_InitGame),
    # per docs + feedback_lua_restart (map_restart/lua_restart break the Lua).
    # ------------------------------------------------------------------

    # ── KIS coverage reconcile ─────────────────────────────────────────────
    #
    # Kill Impact Scores used to be computed ONLY as a side effect of a voice
    # session ending (voice_session_service -> _invalidate_kis_cache ->
    # warm_kis_cache). Every way that trigger can miss leaves a session with
    # no scores forever, because nothing ever reconciled afterwards:
    #
    #   * the bot restarts between session end and the warm — no retry;
    #   * INTERNAL_API_SECRET is unset, so the warm skips (the compute is
    #     gated behind an internal-token request);
    #   * the warm is a fire-and-forget task, so its exception is swallowed;
    #   * nobody was in voice — no session end fires at all;
    #   * rounds import LATE, after the warm already ran, leaving partial rows.
    #
    # Measured on production 2026-08-16: three sessions with kills but ZERO
    # scores (138: 1,396 kills, 127: 82, 124: 542) and one partial (144:
    # 490/507). Session 138 renders the Smart Stats page completely empty for a
    # 22-round night, even though every kill is sitting in
    # proximity_kill_outcome under the canonical round key.
    #
    # This loop closes the gap from the data side: it asks the only question
    # that matters — "does this session have fewer scores than it has kills?" —
    # and triggers the SAME internal compute the warm does. No scoring logic
    # lives here. It both prevents new gaps and heals old ones, so history
    # needs no hand-repair.
    # No lookback window. A 90-day one looked prudent and cost nothing but
    # coverage: production has gaps at 119 and 143 days old (sessions 112 and
    # 103) that it would never have healed. The whole-history query costs 51 ms
    # against 57 ms for the windowed one — the window bought nothing — and the
    # per-pass cap below is what actually bounds the work.
    _KIS_RECONCILE_MAX_PER_PASS = 3
    _KIS_RECONCILE_MAX_ATTEMPTS = 3

    @tasks.loop(seconds=900)
    async def kis_coverage_reconcile(self):
        """Recompute KIS for any session holding fewer scores than kills."""
        try:
            gaps = await self._find_kis_coverage_gaps()
        except Exception:
            logger.error("[KIS-RECONCILE] gap query failed", exc_info=True)
            return
        # A session that cannot be healed must not be retried forever: give up
        # after a few passes and say so once, rather than logging the same
        # failure every 15 minutes until someone notices the noise.
        attempts = getattr(self, "_kis_reconcile_attempts", None)
        if attempts is None:
            attempts = {}
            self._kis_reconcile_attempts = attempts
        abandoned = getattr(self, "_kis_reconcile_abandoned", None)
        if abandoned is None:
            abandoned = set()
            self._kis_reconcile_abandoned = abandoned

        # A session no longer in the gap list is scored: forget its retry count.
        # Kept, it would outlive the problem it counted — a LATER gap in the same
        # session (a late import adding kills to a night already scored, which is
        # one of the ways KIS went missing in the first place) would inherit an
        # exhausted counter and be abandoned without a single attempt. Runs
        # before the empty-gaps return, since "no gaps at all" is exactly the
        # pass that proves every tracked session healed.
        live = {row[0] for row in gaps}
        for gsid in [g for g in attempts if g not in live]:
            del attempts[gsid]
        abandoned.intersection_update(live)

        if not gaps:
            return

        healed = 0
        for gsid, first_date, prox_kills, kis_rows in gaps:
            if healed >= self._KIS_RECONCILE_MAX_PER_PASS:
                break
            tries = attempts.get(gsid, 0)
            if tries >= self._KIS_RECONCILE_MAX_ATTEMPTS:
                # Getting here means a LATER pass still found this session
                # short — the last recompute did not close the gap, which is
                # what makes the warning true. Warning right after firing the
                # final attempt would have claimed failure before the result
                # was known.
                if gsid not in abandoned:
                    abandoned.add(gsid)
                    logger.warning(
                        "[KIS-RECONCILE] session %s still short (%d scores for %d kills) after "
                        "%d attempts — giving up, investigate rather than retrying forever",
                        gsid, kis_rows, prox_kills, self._KIS_RECONCILE_MAX_ATTEMPTS,
                    )
                continue
            logger.info(
                "[KIS-RECONCILE] session %s (%s): %d scores for %d kills — recomputing (attempt %d)",
                gsid, first_date, kis_rows, prox_kills, tries + 1,
            )
            # The pass budget is spent either way — a failed call still costs a
            # request — but an ATTEMPT is only consumed when the compute really
            # ran. warm_kis_cache returns False without reaching it when the
            # secret is missing or the website is down; counting those would
            # burn all three attempts during a web restart and abandon the
            # session until the bot process itself restarts, which is the very
            # silent-failure mode this loop exists to end.
            healed += 1
            try:
                ran = await self.voice_session_service.warm_kis_cache(
                    first_date, gaming_session_id=gsid,
                )
            except Exception:
                logger.error("[KIS-RECONCILE] recompute failed for session %s", gsid, exc_info=True)
                continue
            if ran:
                attempts[gsid] = tries + 1
            else:
                logger.warning(
                    "[KIS-RECONCILE] session %s: recompute did not run (no secret, or the "
                    "website did not answer 200) — not counting it as an attempt", gsid,
                )

    @kis_coverage_reconcile.before_loop
    async def before_kis_coverage_reconcile(self):
        """Wait for bot to be ready"""
        await self.wait_until_ready()

    async def _find_kis_coverage_gaps(self):
        """Sessions whose KIS row count is below their proximity kill count.

        Aggregates each side by canonical round key ONCE and joins, rather than
        running a correlated subquery per round: measured 5,325 ms the naive way
        against 51 ms this way over ALL history, which is the difference between
        a loop that is free and one that is not.

        The canonical key (round_start_unix, map_name, round_number) is the same
        one the compute filters by, so a gap here is exactly a gap there.
        """
        rows = await self.db_adapter.fetch_all(
            """
            WITH scoped AS (
                SELECT gaming_session_id AS gsid, round_start_unix AS rsu,
                       map_name, round_number AS rn, round_date::date AS d
                FROM rounds
                WHERE gaming_session_id IS NOT NULL AND is_valid AND round_number > 0
                  AND is_bot_round IS DISTINCT FROM TRUE AND round_start_unix IS NOT NULL
            ), prox AS (
                SELECT ko.round_start_unix AS rsu, ko.map_name, ko.round_number AS rn,
                       COUNT(*) AS n
                FROM proximity_kill_outcome ko
                JOIN scoped s ON s.rsu = ko.round_start_unix AND s.map_name = ko.map_name
                             AND s.rn = ko.round_number
                GROUP BY 1, 2, 3
            ), kis AS (
                SELECT k.round_start_unix AS rsu, k.map_name, k.round_number AS rn,
                       COUNT(*) AS n
                FROM storytelling_kill_impact k
                JOIN scoped s ON s.rsu = k.round_start_unix AND s.map_name = k.map_name
                             AND s.rn = k.round_number
                GROUP BY 1, 2, 3
            )
            SELECT s.gsid, MIN(s.d)::text AS first_date,
                   SUM(COALESCE(p.n, 0)) AS prox_kills,
                   SUM(COALESCE(kk.n, 0)) AS kis_rows
            FROM scoped s
            LEFT JOIN prox p ON p.rsu = s.rsu AND p.map_name = s.map_name AND p.rn = s.rn
            LEFT JOIN kis kk ON kk.rsu = s.rsu AND kk.map_name = s.map_name AND kk.rn = s.rn
            GROUP BY s.gsid
            HAVING SUM(COALESCE(p.n, 0)) > 0
               AND SUM(COALESCE(kk.n, 0)) < SUM(COALESCE(p.n, 0))
            ORDER BY s.gsid DESC
            """
        )
        return [(int(r[0]), str(r[1]), int(r[2]), int(r[3])) for r in (rows or [])]

    @tasks.loop(seconds=300)
    async def idle_restart_watchdog(self):
        cfg = self.config
        if not getattr(cfg, 'idle_watchdog_enabled', False):
            return
        try:
            rows = await self.db_adapter.fetch_all(
                """
                SELECT status_type, status_data,
                       EXTRACT(EPOCH FROM (NOW() - updated_at)) AS age_seconds
                FROM live_status
                WHERE status_type IN ('game_server', 'voice_channel')
                """
            )
            gs = next((r for r in (rows or []) if r[0] == 'game_server'), None)
            vc = next((r for r in (rows or []) if r[0] == 'voice_channel'), None)

            # Need fresh game-server status (live_status_updater runs every 30s).
            # Stale (>3 min) or missing → don't act this tick.
            if not gs or gs[2] is None or float(gs[2]) > 180:
                return

            def _load(v):
                return json.loads(v) if isinstance(v, str) else (v or {})

            gdata = _load(gs[1])
            online = bool(gdata.get('online'))
            player_count = int(gdata.get('player_count', 0) or 0)
            voice_count = 0
            if vc:
                vdata = _load(vc[1])
                # live_status_updater writes voice count under 'count' (members list
                # may be sanitized/absent — see PR #338), so read 'count' first.
                voice_count = int(vdata.get('count') or len(vdata.get('members') or []) or 0)

            now = time.time()

            # Not idle: server offline (can't/shouldn't load), players in game, or
            # anyone in Discord voice (a session may be about to start).
            if not online or player_count > 0 or voice_count > 0:
                self._idle_since = None
                return

            if getattr(self, '_idle_since', None) is None:
                self._idle_since = now
                return

            idle_min = (now - self._idle_since) / 60.0
            if idle_min < cfg.idle_restart_minutes:
                return

            # Act once per idle period (cooldown until players return).
            if getattr(self, '_idle_handled_since', None) == self._idle_since:
                return
            self._idle_handled_since = self._idle_since

            mapname = re.sub(r'[^a-zA-Z0-9_]', '', cfg.idle_reload_map) or 'supply'
            if cfg.idle_watchdog_dry_run:
                logger.warning(
                    "[IDLE-WATCHDOG] DRY-RUN: server empty %.0f min — would load 'map %s' "
                    "(set IDLE_WATCHDOG_DRY_RUN=false to enable)", idle_min, mapname
                )
                await self.alert_admins(
                    "Idle watchdog (DRY-RUN)",
                    f"Game server empty {idle_min:.0f} min — **would** reload `{mapname}` "
                    f"(full map load, not map_restart). Set `IDLE_WATCHDOG_DRY_RUN=false` to act.",
                    "warning",
                )
            else:
                ok = await self._idle_reload_map(mapname)
                logger.warning("[IDLE-WATCHDOG] server empty %.0f min → map %s (ok=%s)", idle_min, mapname, ok)
                await self.alert_admins(
                    "Idle watchdog",
                    f"Game server empty {idle_min:.0f} min → loaded `{mapname}` "
                    f"({'OK' if ok else '**FAILED**'}).",
                    "warning",
                )
        except Exception:
            logger.error("idle_restart_watchdog error", exc_info=True)

    @idle_restart_watchdog.before_loop
    async def before_idle_restart_watchdog(self):
        """Wait for bot to be ready"""
        await self.wait_until_ready()

    async def _idle_reload_map(self, mapname: str) -> bool:
        """Issue a FULL `map <name>` load via RCON (never map_restart). Returns success."""
        try:
            server_cog = self.get_cog('ServerControl')
            if not (server_cog and getattr(server_cog, 'rcon_enabled', False) and getattr(server_cog, 'rcon_password', None)):
                logger.error("[IDLE-WATCHDOG] RCON not available — cannot reload map")
                return False
            from bot.cogs.server_control import ETLegacyRCON
            rcon = ETLegacyRCON(server_cog.rcon_host, server_cog.rcon_port, server_cog.rcon_password)
            try:
                loop = asyncio.get_running_loop()
                resp = await loop.run_in_executor(None, rcon.send_command, f"map {mapname}")
                return bool(resp) and 'Error' not in resp
            finally:
                try:
                    await asyncio.get_running_loop().run_in_executor(None, rcon.close)
                except Exception:
                    logger.debug("[IDLE-WATCHDOG] rcon close failed", exc_info=True)
        except Exception:
            logger.error("[IDLE-WATCHDOG] map load failed", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Lua console sentinel (P1 of the 2026-08-17 RCA)
    #
    # A Lua error printed into the game server's etconsole.log every supply
    # map load for three months and nothing noticed: the only grep with the
    # right pattern pointed at the local dev clone, the deploy runbook's "no
    # etconsole errors" was an adjective without a step, and every alert path
    # to Discord begins as a Python exception inside THIS process. This loop
    # is the missing reader: it tails the remote console over the SSH access
    # the bot already holds and alerts on the error classes we have actually
    # been bitten by.
    # ------------------------------------------------------------------

    _CONSOLE_ERROR_RE = re.compile(
        r"error running lua"
        r"|bad argument"
        r"|stack traceback"
        r"|attempt to (?:index|call|compare|perform|concatenate)"
        r"|\[PROX\].*FAILED",
        re.IGNORECASE,
    )
    # One alert per distinct error line per hour: the crash prints on EVERY
    # map load, and an alert channel that repeats itself gets muted, which
    # would recreate the very blindness this loop exists to end.
    _CONSOLE_ALERT_COOLDOWN_S = 3600
    # First run looks this far back so a bot restart re-surfaces a live,
    # still-unfixed error once instead of never.
    _CONSOLE_BACKSCAN_BYTES = 65536
    _CONSOLE_MAX_READ_BYTES = 512 * 1024

    def _fetch_console_span(self, offset: int | None):
        """Return (new_offset, text) of the remote console log from `offset`.

        Blocking (paramiko) — the caller runs it in a thread. Split out so
        tests can override it with a fake; everything above this line is pure
        bookkeeping that the tests pin.
        """
        import paramiko

        from bot.automation.ssh_handler import configure_ssh_host_key_policy

        ssh = paramiko.SSHClient()
        configure_ssh_host_key_policy(ssh)
        try:
            import os as _os
            ssh.connect(
                hostname=self.config.ssh_host,
                port=self.config.ssh_port,
                username=self.config.ssh_user,
                # the repo's .env convention writes the key as ~/.ssh/…, and
                # paramiko does NOT expand ~ — without this the sentinel
                # authenticates only when the config happens to be absolute
                key_filename=_os.path.expanduser(self.config.ssh_key_path),
                timeout=10,
            )
            sftp = ssh.open_sftp()
            # a hung remote read would otherwise block the worker thread
            # far beyond the loop interval
            sftp.get_channel().settimeout(20)
            path = self.config.game_console_log_path
            size = sftp.stat(path).st_size
            if offset is None:
                # first pass after (re)start: recent window, not all history
                offset = max(0, size - self._CONSOLE_BACKSCAN_BYTES)
            elif size < offset:
                # the engine truncates/rewrites the log on server restart —
                # and boot is exactly when init-time errors print, so start
                # over rather than skipping to the end
                offset = 0
            if size == offset:
                return size, ""
            with sftp.open(path, "rb") as fh:
                fh.seek(offset)
                data = fh.read(min(size - offset, self._CONSOLE_MAX_READ_BYTES))
            # Advance only past COMPLETE lines: a read can end mid-line —
            # at the chunk cap or because the writer is mid-append at EOF —
            # and an error whose text straddles the boundary would be split
            # across two scans and never match. The fragment stays unread for
            # the next pass. (A full-size read with no newline at all — not a
            # thing a console log does — falls through whole rather than stall.)
            cut = data.rfind(b"\n")
            if cut < 0:
                if len(data) < self._CONSOLE_MAX_READ_BYTES:
                    return offset, ""
            else:
                data = data[:cut + 1]
            return offset + len(data), data.decode("utf-8", errors="replace")
        finally:
            ssh.close()

    def _scan_console_chunk(self, text: str, now: float) -> list[str]:
        """New alert-worthy lines in `text`, deduped by content with a cooldown."""
        alerted = getattr(self, "_console_alerted", None)
        if alerted is None:
            alerted = {}
            self._console_alerted = alerted
        fresh: list[str] = []
        for line in text.splitlines():
            if not self._CONSOLE_ERROR_RE.search(line):
                continue
            key = line.strip()[-200:]
            last = alerted.get(key)
            if last is not None and now - last < self._CONSOLE_ALERT_COOLDOWN_S:
                continue
            alerted[key] = now
            fresh.append(line.strip())
        # keep the dedupe table bounded
        if len(alerted) > 500:
            cutoff = now - self._CONSOLE_ALERT_COOLDOWN_S
            for k in [k for k, t in alerted.items() if t < cutoff]:
                del alerted[k]
        return fresh

    @tasks.loop(seconds=120)
    async def lua_console_sentinel(self):
        cfg = self.config
        if not getattr(cfg, "ssh_enabled", False):
            return
        if not all([cfg.ssh_host, cfg.ssh_user, cfg.ssh_key_path,
                    getattr(cfg, "game_console_log_path", "")]):
            return
        try:
            offset = getattr(self, "_console_log_offset", None)
            new_offset, text = await asyncio.to_thread(self._fetch_console_span, offset)
            self._console_log_offset = new_offset
        except Exception:
            # transient SSH failure must not kill the loop; the endstats
            # monitor already alerts on sustained SSH breakage
            logger.debug("[LUA-SENTINEL] console fetch failed", exc_info=True)
            return
        if not text:
            return
        fresh = self._scan_console_chunk(text, time.monotonic())
        if not fresh:
            return
        shown = "\n".join(f"`{ln[:180]}`" for ln in fresh[:5])
        more = f"\n… in še {len(fresh) - 5} vrstic" if len(fresh) > 5 else ""
        logger.error("[LUA-SENTINEL] %d new game-server Lua error line(s):\n%s",
                     len(fresh), "\n".join(fresh[:5]))
        try:
            await self.alert_admins(
                "Lua napaka na igralnem strežniku",
                f"etconsole.log ({cfg.ssh_host}):\n{shown}{more}",
            )
        except Exception:
            logger.error("[LUA-SENTINEL] alert failed", exc_info=True)
            # A failed send must not consume the cooldown: un-mark these lines
            # so the next pass re-alerts them instead of silencing them for an
            # hour. The offset has already advanced — the dedupe map is the
            # only memory these lines have left.
            for ln in fresh:
                self._console_alerted.pop(ln.strip()[-200:], None)

    @lua_console_sentinel.before_loop
    async def before_lua_console_sentinel(self):
        await self.wait_until_ready()

    # ── Daily data-plausibility sentinel (Data Trust pillar B, permanent) ────
    #
    # scripts/data_plausibility_audit.py reports two classes. Per-row rules
    # fire on a row that is individually impossible (backfill noise excluded
    # by design); trend rules fire when a MONTHLY statistic departs from the
    # months before it — the class that stays invisible while every single
    # row is in range, which is how a halved dead-time measurement went five
    # months unnoticed. Green is the steady state since 2026-08-18; a finding
    # in either class means someone should look today, not at the next manual
    # run. Same sensor family as lua_console_sentinel: quiet when healthy,
    # loud in the admin channel when not.

    @staticmethod
    def _summarize_audit_payload(payload) -> str | None:
        """Return an alert body for live violations, or None when clean.

        Accepts the script's --json output: a list of rule dicts, or the
        wrapped {"rules": [...], "trends": [...]} form. Tolerant of shape
        drift: anything it cannot read is reported as such rather than
        swallowed.
        """
        rules = payload.get("rules") if isinstance(payload, dict) else payload
        if not isinstance(rules, list):
            return "audit --json vrnil nepričakovano obliko — preveri skript"
        # A rule carrying `acknowledged` fires on purpose: the reason is
        # written down in the rule and the repair is already tracked. Alerting
        # on it daily would train the reader to ignore this message, and the
        # next real finding would arrive into that habit.
        live = [(r.get("name", "?"), int(r.get("live", 0) or 0))
                for r in rules
                if isinstance(r, dict) and (r.get("live") or 0) > 0
                and not r.get("acknowledged")]

        # Aggregate rules report a monthly statistic that MOVED — the class no
        # per-row predicate can see (the 2026-03 dead-time fix halved the
        # median dead share with every single row still inside every bound).
        # A payload without a `trends` key is an older audit, not a clean one:
        # absent and empty are different, and only the second is good news.
        trends = payload.get("trends") if isinstance(payload, dict) else None
        shifted: list[tuple[str, str]] = []
        if isinstance(trends, list):
            for tr in trends:
                if not isinstance(tr, dict) or tr.get("acknowledged"):
                    continue
                months = [s.get("month", "?") for s in (tr.get("shifts") or [])
                          if isinstance(s, dict) and not s.get("explanation")]
                if months:
                    shifted.append((tr.get("name", "?"), ", ".join(months[:4])))

        if not live and not shifted:
            return None

        parts: list[str] = []
        if live:
            lines = "\n".join(f"• `{name}`: {n} živih kršitev" for name, n in live[:8])
            more = f"\n… in še {len(live) - 8} pravil" if len(live) > 8 else ""
            parts.append(f"{len(live)} pravil se je sprožilo na ŽIVIH vrsticah:\n{lines}{more}")
        if shifted:
            lines = "\n".join(f"• `{name}`: {months}" for name, months in shifted[:8])
            more = f"\n… in še {len(shifted) - 8} metrik" if len(shifted) > 8 else ""
            parts.append(f"{len(shifted)} metrik se je premaknilo brez razlage:\n{lines}{more}")
        parts.append("Podrobnosti: `python scripts/data_plausibility_audit.py`")
        return "\n".join(parts)

    @staticmethod
    def _run_audit_in_thread():
        """Load the audit tool from scripts/ and run its rules synchronously.

        In-process (no subprocess): the tool opens its own READ-ONLY psycopg2
        connection, so running it in a worker thread is safe next to the
        bot's asyncpg pool. Loaded by path because scripts/ is not a package.
        """
        import importlib.util
        import sys

        script = Path(__file__).resolve().parents[2] / "scripts" / "data_plausibility_audit.py"
        spec = importlib.util.spec_from_file_location("data_plausibility_audit", script)
        mod = importlib.util.module_from_spec(spec)
        # dataclass machinery looks the module up in sys.modules during class
        # creation — register it first or exec_module dies on @dataclass.
        sys.modules["data_plausibility_audit"] = mod
        spec.loader.exec_module(mod)
        conn = mod.get_connection()
        try:
            results = mod.run_audit(conn, mod.RULES, top_n=0)
            trends = mod.run_trend_audit(conn, mod.TREND_RULES)
        finally:
            conn.close()
        return {"rules": [r.to_dict() for r in results],
                "trends": [t.to_dict() for t in trends]}

    @tasks.loop(hours=24)
    async def data_plausibility_sentinel(self):
        cfg = self.config
        if not getattr(cfg, "data_audit_sentinel_enabled", True):
            return
        try:
            payload = await asyncio.wait_for(
                asyncio.to_thread(self._run_audit_in_thread), timeout=300)
        except TimeoutError:
            logger.error("[DATA-AUDIT] audit run timed out after 300s")
            return
        except Exception:
            logger.error("[DATA-AUDIT] audit run failed", exc_info=True)
            return
        body = self._summarize_audit_payload(payload)
        if body is None:
            logger.info("[DATA-AUDIT] daily audit clean — no live violations")
            return
        logger.error("[DATA-AUDIT] %s", body.replace("\n", " | "))
        try:
            await self.alert_admins("Data-plausibility audit: žive kršitve", body)
        except Exception:
            logger.error("[DATA-AUDIT] alert failed", exc_info=True)

    @data_plausibility_sentinel.before_loop
    async def before_data_plausibility_sentinel(self):
        await self.wait_until_ready()
