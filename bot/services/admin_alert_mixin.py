"""UltimateETLegacyBot mixin: Admin alerts + error tracking (alert_admins, track_error).

Extracted from ultimate_bot.py in P3e Sprint 7 / C.5.

All methods live on UltimateETLegacyBot via mixin inheritance.
"""
from __future__ import annotations

from datetime import datetime

import discord

from bot.logging_config import get_logger

logger = get_logger("bot.core")
webhook_logger = get_logger("bot.webhook")


class _AdminAlertMixin:
    """Admin alerts + error tracking (alert_admins, track_error) for UltimateETLegacyBot."""

    async def alert_admins(self, title: str, description: str, severity: str = "warning"):
        """
        Send critical error notifications to admin channel.

        Args:
            title: Short title for the alert
            description: Detailed description of the issue
            severity: One of "info", "warning", "error", "critical"

        Returns:
            True if notification was sent, False otherwise
        """
        if not self.admin_channel_id:
            logger.warning(f"Cannot send admin alert (no admin_channel_id configured): {title}")
            return False

        try:
            channel = self.get_channel(self.admin_channel_id)
            if not channel:
                logger.error(f"Admin channel {self.admin_channel_id} not found")
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
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"Severity: {severity.upper()}")

            await channel.send(embed=embed)
            logger.info(f"Admin alert sent: {title} ({severity})")
            return True

        except discord.Forbidden:
            logger.error(f"Permission denied to send to admin channel {self.admin_channel_id}")
            return False
        except Exception as e:
            logger.error(f"Failed to send admin alert: {e}")
            return False

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
        self._consecutive_errors[error_key] = self._consecutive_errors.get(error_key, 0) + 1
        count = self._consecutive_errors[error_key]

        if count == max_consecutive:
            await self.alert_admins(
                f"{error_key.replace('_', ' ').title()} Failing",
                f"**{count} consecutive failures detected.**\n\n"
                f"Latest error: {error_msg}\n\n"
                f"This service may need attention.",
                severity="error"
            )
        elif count > max_consecutive and count % 10 == 0:
            # Reminder every 10 failures after threshold
            await self.alert_admins(
                f"{error_key.replace('_', ' ').title()} Still Failing",
                f"**{count} total consecutive failures.**\n\n"
                f"Latest error: {error_msg}",
                severity="critical"
            )

        return count

    def reset_error_tracking(self, error_key: str):
        """Reset consecutive error count for a key (call on success)."""
        if error_key in self._consecutive_errors:
            self._consecutive_errors[error_key] = 0
