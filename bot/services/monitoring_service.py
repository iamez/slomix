"""
Monitoring Service - Records server and voice activity for website analytics

This service runs in the Discord bot and periodically records:
- Game server status (via UDP query)
- Voice channel activity (from Discord API)

Data is stored in PostgreSQL for the website to display historical charts.
"""

import asyncio
import json
import logging
import sys
import os
from datetime import datetime
from typing import Optional, List, Dict

# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)

from bot.core.database_adapter import DatabaseAdapter
from website.backend.services.game_server_query import query_game_server

logger = logging.getLogger("MonitoringService")


class MonitoringService:
    """Records game server and voice channel activity to database"""

    def __init__(self, bot, db_adapter: DatabaseAdapter, config):
        """
        Initialize monitoring service.

        Args:
            bot: Discord bot instance
            db_adapter: Database adapter for recording data
            config: Bot configuration object
        """
        self.bot = bot
        self.db = db_adapter
        self.config = config
        self.recording_task = None

        # Server config
        self.server_host = getattr(config, "server_host", "puran.hehe.si")
        self.server_port = int(getattr(config, "server_port", 27960))
        self.record_interval = 600  # 10 minutes

        logger.info(
            f"📊 Monitoring service initialized: {self.server_host}:{self.server_port}"
        )

    async def start(self):
        """Start monitoring background task"""
        if self.recording_task is None:
            self.recording_task = asyncio.create_task(self._recording_loop())
            logger.info(
                f"📊 Monitoring service started (interval: {self.record_interval}s)"
            )

    async def stop(self):
        """Stop monitoring background task"""
        if self.recording_task:
            self.recording_task.cancel()
            try:
                await self.recording_task
            except asyncio.CancelledError:
                pass
            logger.info("📊 Monitoring service stopped")

    async def _recording_loop(self):
        """Main recording loop - runs every 10 minutes"""
        # Wait a bit before first recording (let bot fully start)
        await asyncio.sleep(30)

        while True:
            try:
                # Record both server and voice status
                await self._record_server_status()
                await self._record_voice_status()

                # Wait for next interval
                await asyncio.sleep(self.record_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait 1 min before retry on error

    async def _record_server_status(self):
        """Record game server status via UDP query"""
        try:
            status = query_game_server(self.server_host, self.server_port)

            await self.db.execute(
                """
                INSERT INTO server_status_history
                (player_count, max_players, map_name, hostname, players, ping_ms, online)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                status.player_count,
                status.max_players,
                status.map_name,
                status.clean_hostname,
                json.dumps(
                    [
                        {"name": p.name, "score": p.score, "ping": p.ping}
                        for p in status.players
                    ]
                ),
                status.ping_ms,
                status.online,
            )

            logger.debug(
                f"📊 Server recorded: {status.player_count}/{status.max_players} players "
                f"on {status.map_name} ({'online' if status.online else 'offline'})"
            )

        except Exception as e:
            logger.error(f"Failed to record server status: {e}")

    async def _record_voice_status(self):
        """Record voice channel activity from Discord"""
        try:
            members_data = []
            total_members = 0
            first_joiner_id = None
            first_joiner_name = None
            channel_id = None
            channel_name = None

            # Get members from gaming voice channels
            if (
                hasattr(self.config, "gaming_voice_channels")
                and self.config.gaming_voice_channels
            ):
                for ch_id in self.config.gaming_voice_channels:
                    channel = self.bot.get_channel(ch_id)
                    if channel and hasattr(channel, "members"):
                        # Store channel info (use first active channel)
                        if not channel_id and len(channel.members) > 0:
                            channel_id = channel.id
                            channel_name = channel.name

                        for member in channel.members:
                            members_data.append(
                                {"discord_id": member.id, "name": member.display_name}
                            )
                        total_members += len(channel.members)

            # Determine first joiner (simplified - just first in list)
            if members_data:
                first_joiner_id = members_data[0]["discord_id"]
                first_joiner_name = members_data[0]["name"]

            # Record to database
            await self.db.execute(
                """
                INSERT INTO voice_status_history
                (member_count, channel_id, channel_name, members, first_joiner_id, first_joiner_name)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                total_members,
                channel_id,
                channel_name,
                json.dumps(members_data),
                first_joiner_id,
                first_joiner_name,
            )

            logger.debug(f"📊 Voice recorded: {total_members} members in voice")

        except Exception as e:
            logger.error(f"Failed to record voice status: {e}")

    async def record_now(self):
        """Manually trigger recording (for testing/debugging)"""
        logger.info("📊 Manual recording triggered")
        await self._record_server_status()
        await self._record_voice_status()
