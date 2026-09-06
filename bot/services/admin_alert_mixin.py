"""UltimateETLegacyBot mixin: Admin alerts + error tracking (alert_admins, track_error).

Extracted from ultimate_bot.py in P3e Sprint 7 / C.5.

All methods live on UltimateETLegacyBot via mixin inheritance.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import discord

from bot.logging_config import get_logger

#: How long a failure streak may be idle before the next failure starts a new
#: one. Six of the nine tracked keys have no success path that clears their
#: counter, so without a window "3 consecutive failures" means "the 3rd failure
#: since the bot booted" — which can span days, and which is not what anyone
#: reads it as.
#:
#: ⚠️ Not free: a service failing once every 40 minutes will now never reach a
#: threshold. That is deliberate. A fault that rare is not an outage, and the
#: right instrument for it is the log, not a pager.
STREAK_WINDOW = timedelta(minutes=30)

logger = get_logger("bot.core")
webhook_logger = get_logger("bot.webhook")


class _AdminAlertMixin:
    """Admin alerts + error tracking (alert_admins, track_error) for UltimateETLegacyBot."""

    async def alert_admins(self, title: str, description: str, severity: str = "warning"):
        """
        Send critical error notifications to every configured admin channel.

        Args:
            title: Short title for the alert
            description: Detailed description of the issue
            severity: One of "info", "warning", "error", "critical"

        Returns:
            True if the alert was sent to at least one admin channel, False otherwise
        """
        # bot/config.py:104 defaults ADMIN_CHANNEL_ID to '0' when unset, so
        # an unconfigured bot has admin_channels == [0] — a non-empty list
        # that would otherwise slip past `if not self.admin_channels` and
        # try to send to channel 0. Filter falsy IDs out before deciding
        # whether anything is actually configured (Copilot review on #620).
        channel_ids = [cid for cid in self.admin_channels if cid]
        if not channel_ids:
            logger.warning(f"Cannot send admin alert (no admin_channels configured): {title}")
            return False

        # Color based on severity
        colors = {
            "info": 0x3498DB,      # Blue
            "warning": 0xF39C12,   # Orange
            "error": 0xE74C3C,     # Red
            "critical": 0x8B0000,  # Dark Red
        }
        color = colors.get(severity, colors["warning"])

        # Emoji based on severity
        emojis = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "critical": "🚨",
        }
        emoji = emojis.get(severity, "⚠️")

        embed = discord.Embed(
            title=f"{emoji} {title}",
            description=description[:4000],  # Discord limit
            color=color,
            timestamp=datetime.now()  # noqa: DTZ005 naive datetime intentional — local/UTC mix is project convention (CET game server + UTC prod). See PR #216 rationale
        )
        embed.set_footer(text=f"Severity: {severity.upper()}")

        # Best-effort per channel: one misconfigured admin channel (e.g. the
        # bot was removed from it) must not stop the alert reaching the
        # others. Each admin_channels entry belongs to whichever guild this
        # bot process is actually running against (dev or production have
        # separate .env files, so this never crosses between them).
        sent = False
        for channel_id in channel_ids:
            try:
                channel = self.get_channel(channel_id)
                if not channel:
                    logger.error(f"Admin channel {channel_id} not found")
                    continue
                await channel.send(embed=embed)
                sent = True
            except discord.Forbidden:
                logger.error(f"Permission denied to send to admin channel {channel_id}")
            except Exception as e:
                logger.error(f"Failed to send admin alert to channel {channel_id}: {e}")

        if sent:
            logger.info(f"Admin alert sent: {title} ({severity})")
        return sent

    async def track_error(self, error_key: str, error_msg: str, max_consecutive: int = 3):
        """
        Track consecutive errors and alert admins when threshold is reached.

        Args:
            error_key: Unique identifier for this error type (e.g., "ssh_monitor")
            error_msg: Human-readable error message
            max_consecutive: Number of consecutive errors before alerting

        Returns:
            Current consecutive error count for this key
        """
        now = datetime.now(timezone.utc)

        # ⛔⛔ A STREAK THAT NEVER ENDS IS NOT A STREAK. `ssh_monitor`,
        # `file_processing` and `proximity_ssh` clear their counters on
        # success; the other six — discord_posting, endstats_processing,
        # webhook_processing, stats_ready_webhook, stats_ready_worker,
        # voice_session — have no success path that calls the reset at all, so
        # their counters were monotonic for the life of the process. An idle
        # gap longer than STREAK_WINDOW ends the streak here, which fixes all
        # nine at one place rather than inventing six notions of "success" in
        # six unrelated subsystems.
        last = self._error_last_seen.get(error_key)
        if last is not None and now - last > STREAK_WINDOW:
            self._consecutive_errors[error_key] = 0
            self._alerted_keys.discard(error_key)
            self._error_streak_started.pop(error_key, None)

        self._error_last_seen[error_key] = now
        self._consecutive_errors[error_key] = self._consecutive_errors.get(error_key, 0) + 1
        count = self._consecutive_errors[error_key]

        # When a streak begins, remember when — the recovery notice says how
        # long the service was down, and "it is back" without "for how long"
        # is barely more useful than silence.
        if count == 1:
            self._error_streak_started[error_key] = now

        if count == max_consecutive:
            await self.alert_admins(
                f"{error_key.replace('_', ' ').title()} Failing",
                f"**{count} consecutive failures detected.**\n\n"
                f"Latest error: {error_msg}\n\n"
                f"This service may need attention.",
                severity="error"
            )
            # ⛔ Only a key that actually woke somebody may announce recovery.
            # Without this, every quiet reset would page the admins to say
            # nothing happened.
            self._alerted_keys.add(error_key)
        elif count > max_consecutive and count % 10 == 0:
            # Reminder every 10 failures after threshold
            await self.alert_admins(
                f"{error_key.replace('_', ' ').title()} Still Failing",
                f"**{count} total consecutive failures.**\n\n"
                f"Latest error: {error_msg}",
                severity="critical"
            )

        return count

    async def reset_error_tracking(self, error_key: str):
        """Clear the counter and, if this key alerted, say that it recovered.

        ⛔⛔ THE MISSING HALF OF THE STATE MACHINE. Until 2026-09-06 this
        method was silent: it set the counter to 0 and told nobody. The owner
        therefore saw an ERROR at 14:56 and never learnt that the service was
        healthy again by 15:02 — from Discord alone, the outage is still
        running. An alerting path with only the failing edge instrumented does
        not report a service's state; it reports a monotonically growing list
        of complaints.

        ⛔ Recovery is announced ONLY for a key that actually alerted. A reset
        happens on every healthy cycle, and pinging admins to say nothing
        happened would train them to ignore the channel — which costs more
        than the missing notice did.
        """
        count = self._consecutive_errors.get(error_key, 0)
        started = self._error_streak_started.pop(error_key, None)
        self._error_last_seen.pop(error_key, None)
        had_alerted = error_key in self._alerted_keys

        # ⛔ Only zero a key that exists. A reset for a key never tracked must
        # NOT create an entry — resets run on every healthy cycle for several
        # services, and inventing keys would grow this dict without bound.
        # (Pinned since before this change: test_reset_error_tracking_no_op_
        # for_unknown_key. I dropped the guard while adding recovery and the
        # test caught it.)
        if error_key in self._consecutive_errors:
            self._consecutive_errors[error_key] = 0
        self._alerted_keys.discard(error_key)

        if not had_alerted:
            return

        if started is not None:
            elapsed = datetime.now(timezone.utc) - started
            minutes = max(1, round(elapsed.total_seconds() / 60))
            span = f"after {minutes} minute{'s' if minutes != 1 else ''}"
        else:
            # The streak began before this process did (the counters live in
            # memory only), so the duration is genuinely unknown — say so
            # rather than print a number that would be a guess.
            span = "after an unknown period"

        await self.alert_admins(
            f"{error_key.replace('_', ' ').title()} Recovered",
            f"**Back to normal {span}.**\n\n"
            f"{count} consecutive failure{'s' if count != 1 else ''} before this cycle succeeded.",
            severity="info",
        )
