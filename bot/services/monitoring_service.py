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
from datetime import datetime, timedelta
from typing import Optional

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
        self.server_task = None
        self.voice_task = None
        self.cleanup_task = None
        self._db_user: Optional[str] = None

        # Server config
        self.server_host = getattr(config, "server_host", "puran.hehe.si")
        self.server_port = int(getattr(config, "server_port", 27960))
        self.server_interval = int(
            getattr(config, "monitoring_server_interval_seconds", 300)
        )
        self.voice_interval = int(
            getattr(config, "monitoring_voice_interval_seconds", 300)
        )
        # Data retention: delete records older than this many days (default 30)
        self.retention_days = int(
            getattr(config, "monitoring_retention_days", 30)
        )

        logger.info(
            f"📊 Monitoring service initialized: {self.server_host}:{self.server_port}"
        )

    async def start(self):
        """Start monitoring background tasks"""
        await self._ensure_history_tables()
        if self.server_task is None:
            self.server_task = asyncio.create_task(self._server_loop())
        if self.voice_task is None:
            self.voice_task = asyncio.create_task(self._voice_loop())
        if self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info(
            "📊 Monitoring service started "
            f"(server: {self.server_interval}s, voice: {self.voice_interval}s, "
            f"retention: {self.retention_days} days)"
        )
        # Fire an immediate snapshot so history populates quickly
        asyncio.create_task(self._record_server_status())
        asyncio.create_task(self._record_voice_status())

    async def _ensure_history_tables(self):
        """Create history tables if they don't exist yet."""
        await self._ensure_table(
            "server_status_history table",
            """
            CREATE TABLE IF NOT EXISTS server_status_history (
                id SERIAL PRIMARY KEY,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                player_count INTEGER DEFAULT 0,
                max_players INTEGER DEFAULT 0,
                map_name TEXT,
                hostname TEXT,
                players JSONB,
                ping_ms INTEGER DEFAULT 0,
                online BOOLEAN DEFAULT FALSE
            )
            """,
        )
        await self._ensure_table(
            "voice_status_history table",
            """
            CREATE TABLE IF NOT EXISTS voice_status_history (
                id SERIAL PRIMARY KEY,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                member_count INTEGER DEFAULT 0,
                channel_id BIGINT,
                channel_name TEXT,
                members JSONB,
                first_joiner_id BIGINT,
                first_joiner_name TEXT
            )
            """,
        )

        # Avoid CREATE INDEX IF NOT EXISTS on tables owned by another role.
        # PostgreSQL still checks table ownership even if the index already exists.
        await self._ensure_index(
            table_name="server_status_history",
            index_name="idx_server_status_history_recorded_at",
            index_expr="recorded_at",
        )
        await self._ensure_index(
            table_name="voice_status_history",
            index_name="idx_voice_status_history_recorded_at",
            index_expr="recorded_at",
        )

    async def _ensure_table(self, step_name: str, query: str) -> None:
        try:
            await self.db.execute(query)
        except Exception as e:
            if self._is_insufficient_privilege_error(e):
                logger.warning(
                    "Skipping monitoring DDL for %s due to insufficient DB privileges: %s",
                    step_name,
                    e,
                )
                return
            logger.error(f"Failed to ensure {step_name}: {e}", exc_info=True)

    _MONITORING_TABLES = frozenset({"server_status_history", "voice_status_history", "voice_members", "live_status"})

    async def _ensure_index(
        self,
        table_name: str,
        index_name: str,
        index_expr: str,
    ) -> None:
        if table_name not in self._MONITORING_TABLES:
            logger.error("Refusing to create index on non-monitoring table: %s", table_name)
            return
        if not await self._table_exists(table_name):
            logger.warning(
                "Skipping monitoring DDL for %s index: table does not exist",
                table_name,
            )
            return

        if await self._index_exists(table_name, index_name):
            return

        owner = await self._table_owner(table_name)
        db_user = await self._current_db_user()
        if owner and db_user and owner != db_user:
            logger.warning(
                "Skipping monitoring DDL for %s index because table owner is %s (current role: %s)",
                table_name,
                owner,
                db_user,
            )
            return

        try:
            await self.db.execute(
                f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({index_expr})"
            )
        except Exception as e:
            if self._is_insufficient_privilege_error(e):
                logger.warning(
                    "Skipping monitoring DDL for %s index due to insufficient DB privileges: %s",
                    table_name,
                    e,
                )
                return
            logger.error(f"Failed to ensure {table_name} index {index_name}: {e}", exc_info=True)

    async def _table_exists(self, table_name: str) -> bool:
        query = """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = $1
            LIMIT 1
        """
        try:
            row = await self.db.fetch_one(query, (table_name,))
            return bool(row)
        except Exception:
            return False

    async def _index_exists(self, table_name: str, index_name: str) -> bool:
        query = """
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = $1
              AND indexname = $2
            LIMIT 1
        """
        try:
            row = await self.db.fetch_one(query, (table_name, index_name))
            return bool(row)
        except Exception:
            return False

    async def _table_owner(self, table_name: str) -> Optional[str]:
        query = """
            SELECT tableowner
            FROM pg_tables
            WHERE schemaname = 'public' AND tablename = $1
            LIMIT 1
        """
        try:
            row = await self.db.fetch_one(query, (table_name,))
            return str(row[0]) if row and row[0] else None
        except Exception:
            return None

    async def _current_db_user(self) -> Optional[str]:
        if self._db_user:
            return self._db_user
        try:
            row = await self.db.fetch_one("SELECT current_user")
            if row and row[0]:
                self._db_user = str(row[0])
        except Exception:
            return None
        return self._db_user

    @staticmethod
    def _is_insufficient_privilege_error(exc: Exception) -> bool:
        msg = str(exc).lower()
        return (
            "insufficientprivilege" in exc.__class__.__name__.lower()
            or "must be owner of table" in msg
            or "permission denied" in msg
        )

    async def stop(self):
        """Stop monitoring background tasks"""
        for task in [self.server_task, self.voice_task, self.cleanup_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        logger.info("📊 Monitoring service stopped")

    async def _server_loop(self):
        """Server status loop"""
        await asyncio.sleep(15)
        while True:
            try:
                await self._record_server_status()
                await asyncio.sleep(self.server_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Server monitoring loop error: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def _voice_loop(self):
        """Voice status loop"""
        await asyncio.sleep(20)
        while True:
            try:
                await self._record_voice_status()
                await asyncio.sleep(self.voice_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Voice monitoring loop error: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def _cleanup_loop(self):
        """Cleanup old history records daily"""
        # Wait 1 hour before first cleanup (let bot stabilize)
        await asyncio.sleep(3600)
        while True:
            try:
                await self._cleanup_old_records()
                # Run cleanup once per day
                await asyncio.sleep(86400)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}", exc_info=True)
                await asyncio.sleep(3600)

    async def _cleanup_old_records(self):
        """Delete history records older than retention_days"""
        cutoff = datetime.utcnow() - timedelta(days=self.retention_days)
        await self._cleanup_table("server_status_history", cutoff)
        await self._cleanup_table("voice_status_history", cutoff)
        logger.info(
            f"📊 Cleanup: checked monitoring retention for {self.retention_days} days "
            f"(cutoff: {cutoff.isoformat()})"
        )

    async def _cleanup_table(self, table_name: str, cutoff: datetime) -> None:
        if table_name not in self._MONITORING_TABLES:
            logger.error("Refusing to cleanup non-monitoring table: %s", table_name)
            return
        try:
            await self.db.execute(
                f"DELETE FROM {table_name} WHERE recorded_at < $1",
                (cutoff,),
            )
        except Exception as e:
            if self._is_insufficient_privilege_error(e):
                logger.warning(
                    "Skipping monitoring cleanup for %s due to insufficient DB privileges: %s",
                    table_name,
                    e,
                )
                return
            logger.error(f"Failed to cleanup {table_name}: {e}")

    async def _record_server_status(self):
        """Record game server status via UDP query"""
        try:
            # Run blocking UDP query in thread pool to avoid blocking event loop
            loop = asyncio.get_event_loop()
            status = await loop.run_in_executor(
                None, query_game_server, self.server_host, self.server_port
            )

            await self.db.execute(
                """
                INSERT INTO server_status_history
                (player_count, max_players, map_name, hostname, players, ping_ms, online)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                (
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
                ),
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
                (
                    total_members,
                    channel_id,
                    channel_name,
                    json.dumps(members_data),
                    first_joiner_id,
                    first_joiner_name,
                ),
            )

            logger.debug(f"📊 Voice recorded: {total_members} members in voice")

        except Exception as e:
            logger.error(f"Failed to record voice status: {e}")

    async def record_now(self):
        """Manually trigger recording (for testing/debugging)"""
        logger.info("📊 Manual recording triggered")
        await self._record_server_status()
        await self._record_voice_status()
