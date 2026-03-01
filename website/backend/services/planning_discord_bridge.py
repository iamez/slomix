"""Best-effort Discord thread creation for planning sessions."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date

import httpx

from website.backend.logging_config import get_app_logger

logger = get_app_logger("planning.discord_bridge")


@dataclass
class PlanningDiscordBridge:
    enabled: bool
    bot_token: str
    parent_channel_id: int
    api_base_url: str = "https://discord.com/api/v10"
    timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "PlanningDiscordBridge":
        enabled = os.getenv("AVAILABILITY_PLANNING_DISCORD_CREATE_THREAD", "false").lower() == "true"
        bot_token = (
            os.getenv("AVAILABILITY_PLANNING_DISCORD_BOT_TOKEN", "").strip()
            or os.getenv("DISCORD_BOT_TOKEN", "").strip()
        )
        parent_raw = os.getenv("AVAILABILITY_PLANNING_THREAD_PARENT_CHANNEL_ID", "").strip()
        try:
            parent_channel_id = int(parent_raw) if parent_raw else 0
        except ValueError:
            parent_channel_id = 0

        return cls(
            enabled=enabled,
            bot_token=bot_token,
            parent_channel_id=parent_channel_id,
        )

    async def create_private_thread(self, *, session_date: date, participant_count: int) -> str | None:
        """Create a private Discord thread and return thread/channel id, or None."""
        if not self.enabled:
            return None
        if self.parent_channel_id <= 0:
            logger.warning("Planning thread create enabled but parent channel id is not configured")
            return None
        if not self.bot_token:
            logger.warning("Planning thread create enabled but Discord bot token is missing")
            return None

        thread_name = f"planning-{session_date.isoformat()}-{max(0, int(participant_count))}p"
        payload = {
            "name": thread_name[:100],
            "type": 12,  # private thread
            "auto_archive_duration": 1440,
            "invitable": True,
        }
        headers = {
            "Authorization": f"Bot {self.bot_token}",
            "Content-Type": "application/json",
            "X-Audit-Log-Reason": "Planning room thread auto-create",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.api_base_url}/channels/{self.parent_channel_id}/threads",
                    json=payload,
                    headers=headers,
                )
        except Exception as exc:
            logger.warning("Planning thread creation request failed: %s", exc)
            return None

        if response.status_code not in {200, 201}:
            error_preview = response.text[:200]
            logger.warning(
                "Planning thread creation failed (status=%s, body=%s)",
                response.status_code,
                error_preview,
            )
            return None

        try:
            data = response.json()
        except Exception:
            logger.warning("Planning thread creation succeeded but response JSON was invalid")
            return None

        thread_id = str(data.get("id") or "").strip()
        if not thread_id:
            logger.warning("Planning thread creation succeeded but thread id missing in response")
            return None

        return thread_id
