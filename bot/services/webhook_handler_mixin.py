"""UltimateETLegacyBot mixin: Webhook trigger dispatch + filename validation.

Extracted from ultimate_bot.py in P3e Sprint 7 / C.3.

All methods live on UltimateETLegacyBot via mixin inheritance. Runtime
attributes consumed here are set in the main class ``__init__``:
``self.db_adapter``, ``self.config``, ``self.bot_startup_time``,
``self.file_tracker``, ``self.processed_endstats_files``, and the
rate-limit helpers defined in the bot base class.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta

import discord

from bot.core.utils import validate_stats_filename
from bot.logging_config import get_logger

logger = get_logger("bot.core")
webhook_logger = get_logger("bot.webhook")


class _WebhookHandlerMixin:
    """Webhook trigger dispatch + filename validation for UltimateETLegacyBot."""

    def _webhook_trigger_mode(self) -> str:
        mode = str(getattr(self.config, "webhook_trigger_mode", "stats_ready_only") or "").strip().lower()
        if mode in {"stats_ready_only", "dual", "filename_only"}:
            return mode
        return "stats_ready_only"

    def _webhook_mode_allows_stats_ready(self) -> bool:
        return self._webhook_trigger_mode() in {"stats_ready_only", "dual"}

    def _webhook_mode_allows_filename_triggers(self) -> bool:
        return self._webhook_trigger_mode() in {"dual", "filename_only"}

    def _validate_stats_filename(self, filename: str) -> bool:
        """
        Strict validation for stats filenames.

        Delegates to the shared utility function in bot.core.utils.
        """
        return validate_stats_filename(filename)

    def _validate_endstats_filename(self, filename: str) -> bool:
        """
        Strict validation for endstats filenames.

        Valid format: YYYY-MM-DD-HHMMSS-mapname-round-N-endstats.txt
        Example: 2026-01-12-224606-te_escape2-round-2-endstats.txt

        Security: Prevents path traversal, injection, null bytes
        """
        # Length check (prevent DoS)
        if len(filename) > 255:
            logger.warning(f"🚨 Endstats filename too long: {len(filename)} chars")
            return False

        # Path traversal checks
        if any(char in filename for char in ['/', '\\', '\0']):
            logger.warning(f"🚨 Invalid characters in endstats filename: {filename}")
            return False

        if '..' in filename:
            logger.warning(f"🚨 Parent directory reference in endstats: {filename}")
            return False

        # Strict pattern: YYYY-MM-DD-HHMMSS-mapname-round-N-endstats.txt
        pattern = r'^(\d{4})-(\d{2})-(\d{2})-(\d{6})-([a-zA-Z0-9_-]+)-round-(\d+)-endstats\.txt$'
        match = re.match(pattern, filename)

        if not match:
            logger.debug(f"Filename doesn't match endstats pattern: {filename}")
            return False

        # Validate components
        year, month, day, timestamp, map_name, round_num = match.groups()

        if not (2020 <= int(year) <= 2035):
            return False
        if not (1 <= int(month) <= 12):
            return False
        if not (1 <= int(day) <= 31):
            return False
        if not (1 <= int(round_num) <= 10):
            return False
        if len(map_name) > 50:
            return False

        # Validate timestamp (HHMMSS)
        hour = int(timestamp[0:2])
        minute = int(timestamp[2:4])
        second = int(timestamp[4:6])
        if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
            return False

        logger.debug(f"✅ Endstats filename validated: {filename}")
        return True

    async def _should_process_endstats_file(self, filename: str) -> bool:
        """
        Decide whether an endstats file should be processed.

        Uses processed_endstats_files for dedupe and applies startup lookback
        to avoid reprocessing very old files after a restart.
        """
        if not self._validate_endstats_filename(filename):
            return False

        # Startup lookback (mirrors FileTracker behavior, but endstats-specific)
        try:
            datetime_str = filename[:17]  # YYYY-MM-DD-HHMMSS
            file_datetime = datetime.strptime(datetime_str, "%Y-%m-%d-%H%M%S")
            lookback_hours = getattr(self.config, 'STARTUP_LOOKBACK_HOURS', 168)
            cutoff_time = self.bot_startup_time - timedelta(hours=lookback_hours)

            if file_datetime < cutoff_time:
                logger.debug(
                    f"⏭️ Endstats {filename} older than lookback window "
                    f"({lookback_hours}h before startup) - skipping"
                )
                return False
        except ValueError:
            logger.warning(f"⚠️ Could not parse datetime from endstats filename: {filename}")

        if filename in self.processed_endstats_files:
            return False

        check_query = "SELECT 1 FROM processed_endstats_files WHERE filename = $1"
        result = await self.db_adapter.fetch_one(check_query, (filename,))
        if result:
            self.processed_endstats_files.add(filename)
            return False

        return True

    async def _handle_webhook_trigger(self, message) -> bool:
        """
        Handle webhook trigger messages from VPS.

        VPS webhook posts to control channel with filename.
        Bot extracts filename, downloads via SSH, processes, and posts stats.

        Returns True if message was handled as webhook trigger.
        """
        def _debug_webhook(note: str):
            if not getattr(message, "webhook_id", None):
                return
            try:
                content = message.content or ""
                if len(content) > 160:
                    content = content[:157] + "..."
                author = getattr(getattr(message, "author", None), "name", "unknown")
                embed_count = len(message.embeds) if getattr(message, "embeds", None) else 0
                webhook_logger.debug(
                    f"[WEBHOOK DEBUG] {note} | "
                    f"channel={message.channel.id} webhook_id={message.webhook_id} "
                    f"user={author} embeds={embed_count} content={content!r}"
                )
            except Exception:
                logger.debug("Failed to format webhook debug info", exc_info=True)

        # Check if webhook trigger is configured
        trigger_channel_id = self.config.webhook_trigger_channel_id
        if not trigger_channel_id:
            _debug_webhook("ignored: trigger channel not configured")
            return False

        # Check if message is in the trigger channel
        if message.channel.id != trigger_channel_id:
            _debug_webhook("ignored: channel mismatch")
            return False

        # Check if message is from a webhook (webhooks have webhook_id)
        if not message.webhook_id:
            return False

        # CRITICAL: Webhook ID whitelist enforcement
        webhook_whitelist = self.config.webhook_trigger_whitelist
        if not webhook_whitelist:
            webhook_logger.error("⚠️ Webhook trigger disabled: WEBHOOK_TRIGGER_WHITELIST not configured")
            _debug_webhook("ignored: whitelist missing")
            return False

        if str(message.webhook_id) not in webhook_whitelist:
            webhook_logger.warning(
                f"🚨 SECURITY: Unauthorized webhook {message.webhook_id} "
                f"attempted trigger in channel {message.channel.id}"
            )
            _debug_webhook("ignored: webhook not in whitelist")
            return False

        # Check username (additional layer)
        expected_username = self.config.webhook_trigger_username
        if expected_username and message.author.name != expected_username:
            webhook_logger.warning(f"🚨 Username mismatch: {message.author.name}")
            _debug_webhook(f"ignored: username mismatch (expected={expected_username})")
            return False

        if not self._register_processed_webhook_message_id(getattr(message, "id", None)):
            _debug_webhook("ignored: duplicate webhook message id")
            return True

        webhook_mode = self._webhook_trigger_mode()
        allow_stats_ready = self._webhook_mode_allows_stats_ready()
        allow_filename_triggers = self._webhook_mode_allows_filename_triggers()

        # ===== Handle STATS_READY webhook with embedded metadata =====
        # Lua script sends "STATS_READY" with embeds containing timing/winner data
        if message.content and message.content.strip() == "STATS_READY":
            if not allow_stats_ready:
                _debug_webhook(f"ignored: STATS_READY disabled by mode={webhook_mode}")
                return False
            if message.embeds:
                if not self._check_stats_ready_rate_limit(message.webhook_id):
                    _debug_webhook("ignored: STATS_READY rate limited")
                    return False
                webhook_logger.info("📥 Received STATS_READY webhook with metadata")
                _debug_webhook("accepted: STATS_READY with embeds")
                self._safe_create_task(self._process_stats_ready_webhook(message), name="stats_ready_webhook")
                return True
            else:
                webhook_logger.warning("STATS_READY webhook received but no embeds found")
                _debug_webhook("ignored: STATS_READY missing embeds")
                return False

        if not allow_filename_triggers:
            _debug_webhook(f"ignored: filename trigger disabled by mode={webhook_mode}")
            return False

        # HIGH: Rate limit check (applies to filename/endstats triggers only).
        # STATS_READY carries authoritative round metadata and should not be
        # suppressed by bursts of regular file-trigger messages.
        if not self._check_webhook_rate_limit(message.webhook_id):
            _debug_webhook("ignored: rate limited")
            return False

        # ===== EXISTING: Handle filename-based webhook trigger =====
        # Extract filename from message content
        # Format: 📊 `2025-12-09-221829-etl_sp_delivery-round-1.txt`
        filename = None
        if message.content:
            match = re.search(r'`([^`]+\.txt)`', message.content)
            if match:
                filename = match.group(1)

        if not filename:
            webhook_logger.debug("No filename found in webhook message")
            _debug_webhook("ignored: no filename in content")
            return False

        # CRITICAL: Validate filename for security
        # Check for both regular stats files and endstats files
        is_endstats = filename.endswith('-endstats.txt')

        if is_endstats:
            if not self._validate_endstats_filename(filename):
                webhook_logger.error(f"🚨 SECURITY: Invalid endstats filename from webhook: {filename}")
                return False
            webhook_logger.info(f"📥 Endstats webhook trigger validated: {filename}")
            # Process endstats file in background
            self._safe_create_task(self._process_webhook_triggered_endstats(filename, message), name=f"webhook_endstats_{filename}")
        else:
            if not self._validate_stats_filename(filename):
                webhook_logger.error(f"🚨 SECURITY: Invalid filename from webhook: {filename}")
                return False
            webhook_logger.info(f"📥 Webhook trigger validated: {filename}")
            # Process regular stats file in background
            self._safe_create_task(self._process_webhook_triggered_file(filename, message), name=f"webhook_file_{filename}")

        return True

    async def _process_webhook_triggered_file(self, filename: str, trigger_message):
        """
        Process a file triggered by webhook notification.

        Downloads file via SSH, parses, imports to DB, and posts stats.
        """
        added_processing_marker = False
        try:
            webhook_logger.info(f"⚡ Processing webhook-triggered file: {filename}")

            # Check if already processed (prevent duplicates)
            if not await self.file_tracker.should_process_file(filename):
                webhook_logger.debug(f"⏭️ File already processed: {filename}")
                # Optionally delete the trigger message
                try:
                    await trigger_message.delete()
                except discord.DiscordException:
                    logger.debug("Discord notification failed (non-critical)")
                return

            # IMMEDIATELY mark as being processed to prevent race with polling
            self.file_tracker.processed_files.add(filename)
            added_processing_marker = True

            # Build SSH config
            ssh_config = {
                "host": self.config.ssh_host,
                "port": self.config.ssh_port,
                "user": self.config.ssh_user,
                "key_path": self.config.ssh_key_path,
                "remote_path": self.config.ssh_remote_path,
            }

            # Download file via SSH
            from bot.automation.ssh_handler import SSHHandler
            local_path = await SSHHandler.download_file(
                ssh_config, filename, self.config.stats_directory
            )

            if not local_path:
                webhook_logger.error(f"❌ Failed to download: {filename}")
                if added_processing_marker:
                    self.file_tracker.processed_files.discard(filename)
                # React to trigger with failure indicator
                try:
                    await trigger_message.add_reaction('❌')
                    await trigger_message.reply(f"⚠️ Failed to download `{filename}` from server.")
                except discord.DiscordException:
                    logger.debug("Discord notification failed (non-critical)")
                return

            webhook_logger.info(f"✅ Downloaded: {local_path}")

            # Wait for file to fully write
            await asyncio.sleep(2)

            # Check for pending Lua metadata (from STATS_READY or gametime)
            override_metadata = self._pop_pending_metadata(filename)

            # Process the file (parse and import to DB)
            result = await self.process_gamestats_file(local_path, filename, override_metadata=override_metadata)

            if result and result.get('success'):
                # Post to production stats channel
                webhook_logger.info(f"📊 Posting stats: {result.get('player_count', 0)} players")
                try:
                    await self.round_publisher.publish_round_stats(filename, result)
                    webhook_logger.info(f"✅ Successfully processed and posted: {filename}")
                except Exception as post_err:
                    webhook_logger.error(f"❌ Discord post FAILED for {filename}: {post_err}", exc_info=True)
                    await self.track_error("discord_posting", f"Failed to post {filename}: {post_err}", max_consecutive=2)

                # Delete the trigger message (clean up control channel)
                try:
                    await trigger_message.delete()
                    webhook_logger.debug("🗑️ Deleted trigger message")
                except Exception as e:
                    webhook_logger.debug(f"Could not delete trigger message: {e}")
            else:
                error_msg = result.get('error', 'Unknown error') if result else 'No result'
                webhook_logger.warning(f"⚠️ Processing failed for {filename}: {error_msg}")
                if added_processing_marker:
                    self.file_tracker.processed_files.discard(filename)
                # Notify trigger channel of processing failure
                try:
                    await trigger_message.add_reaction('⚠️')
                    # Sanitize error message for Discord (remove sensitive paths)
                    safe_error = error_msg.replace(str(self.config.stats_directory), "[stats_dir]")
                    await trigger_message.reply(
                        f"⚠️ Failed to process `{filename}`\n"
                        f"Error: {safe_error[:200]}"
                    )
                except discord.DiscordException:
                    logger.debug("Discord notification failed (non-critical)")

        except Exception as e:
            if added_processing_marker:
                self.file_tracker.processed_files.discard(filename)
            webhook_logger.error(f"❌ Error processing webhook-triggered file: {e}", exc_info=True)
            # Notify trigger channel of critical error
            try:
                await trigger_message.add_reaction('🚨')
                await trigger_message.reply(f"🚨 Critical error processing `{filename}`. Check logs.")
            except discord.DiscordException:
                # Reaction/reply failure is non-critical — error itself is already logged above
                logger.debug("Failed to post webhook-processing error reaction (non-critical)")
            # Track for admin alerts
            await self.track_error("webhook_processing", str(e), max_consecutive=3)
