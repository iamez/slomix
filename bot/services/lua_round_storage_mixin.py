"""UltimateETLegacyBot mixin: Lua webhook round-data persistence (teams, spawn stats).

Extracted from ultimate_bot.py in P3e Sprint 7 / C.3.

All methods live on UltimateETLegacyBot via mixin inheritance. Database
access goes through ``self.db_adapter`` and configuration values are read
from ``self.config``.
"""
from __future__ import annotations

import json
from datetime import datetime

from bot.core.round_contract import normalize_end_reason, normalize_side_value
from bot.core.round_linker import _parse_round_datetime
from bot.logging_config import get_logger

logger = get_logger("bot.core")
webhook_logger = get_logger("bot.webhook")


class _LuaRoundStorageMixin:
    """Lua webhook round-data persistence (teams, spawn stats) for UltimateETLegacyBot."""

    async def _link_lua_round_teams(self, round_id: int, metadata: dict) -> None:
        """
        Link lua_round_teams rows to a round_id using map + round + time proximity.
        """
        try:
            if not await self._has_lua_round_teams_round_id():
                return

            map_name = metadata.get('map_name')
            round_number = metadata.get('round_number')
            if not map_name or not round_number:
                return

            try:
                round_number = int(round_number)
            except (TypeError, ValueError):
                return

            target_unix = metadata.get('round_end_unix') or metadata.get('round_start_unix')
            try:
                target_unix = int(target_unix)
            except (TypeError, ValueError):
                target_unix = 0

            # Fallback: derive target_unix from round_date + round_time when Lua
            # metadata is missing (e.g. bot restart lost in-memory webhook data).
            # The rounds table ALWAYS has round_date+round_time from the filename.
            if not target_unix:
                round_row = await self.db_adapter.fetch_one(
                    "SELECT round_date, round_time FROM rounds WHERE id = ?",
                    (round_id,),
                )
                if round_row:
                    dt = _parse_round_datetime(
                        round_row[0] if isinstance(round_row, (list, tuple)) else round_row.get('round_date'),
                        round_row[1] if isinstance(round_row, (list, tuple)) else round_row.get('round_time'),
                    )
                    if dt:
                        target_unix = int(dt.timestamp())

            if not target_unix:
                return

            window_seconds = getattr(self.config, "round_match_window_minutes", 45) * 60
            candidates_query = """
                SELECT id, round_end_unix, round_start_unix
                FROM lua_round_teams
                WHERE round_id IS NULL
                  AND map_name = ?
                  AND round_number = ?
                  AND (
                        (round_end_unix IS NOT NULL AND ABS(round_end_unix - ?) <= ?)
                     OR (round_start_unix IS NOT NULL AND ABS(round_start_unix - ?) <= ?)
                  )
                ORDER BY captured_at DESC
                LIMIT 10
            """
            rows = await self.db_adapter.fetch_all(
                candidates_query,
                (map_name, round_number, target_unix, window_seconds, target_unix, window_seconds),
            )
            if not rows:
                return

            # Pick the closest candidate to avoid linking multiple rows
            best_id = None
            best_diff = None
            for row in rows:
                lua_id, round_end_unix, round_start_unix = row
                diffs = []
                if round_end_unix:
                    diffs.append(abs(int(round_end_unix) - target_unix))
                if round_start_unix:
                    diffs.append(abs(int(round_start_unix) - target_unix))
                if not diffs:
                    continue
                diff = min(diffs)
                if best_diff is None or diff < best_diff:
                    best_diff = diff
                    best_id = lua_id

            if best_id is not None:
                await self.db_adapter.execute(
                    "UPDATE lua_round_teams SET round_id = ? WHERE id = ?",
                    (round_id, best_id),
                )
                logger.debug(
                    "Lua round link (NULL pass): lua_id=%s → round_id=%s (diff=%ss)",
                    best_id, round_id, best_diff,
                )

            # --- Second pass: fix stale linkages ---
            # When the same map is played multiple times in a session, the initial
            # insert may link a Lua record to a wrong round (race condition: the
            # correct round hadn't been imported yet). Now that THIS round exists,
            # check if any Lua records currently linked to OTHER rounds are actually
            # a closer temporal match for THIS round.
            stale_query = """
                SELECT lrt.id, lrt.round_end_unix, lrt.round_start_unix, lrt.round_id
                FROM lua_round_teams lrt
                WHERE lrt.map_name = ?
                  AND lrt.round_number = ?
                  AND lrt.round_id IS NOT NULL
                  AND lrt.round_id != ?
                  AND (
                        (lrt.round_end_unix IS NOT NULL AND ABS(lrt.round_end_unix - ?) <= ?)
                     OR (lrt.round_start_unix IS NOT NULL AND ABS(lrt.round_start_unix - ?) <= ?)
                  )
                ORDER BY captured_at DESC
                LIMIT 10
            """
            stale_rows = await self.db_adapter.fetch_all(
                stale_query,
                (map_name, round_number, round_id, target_unix, window_seconds, target_unix, window_seconds),
            )
            for row in stale_rows:
                lua_id, lua_end_unix, lua_start_unix, current_rid = row
                lua_ts = int(lua_end_unix or lua_start_unix or 0)
                if not lua_ts:
                    continue

                # Get the currently-linked round's timestamp for comparison
                current_round = await self.db_adapter.fetch_one(
                    "SELECT round_date, round_time FROM rounds WHERE id = ?",
                    (current_rid,),
                )
                if not current_round:
                    continue
                current_round_dt = _parse_round_datetime(current_round[0], current_round[1])
                if not current_round_dt:
                    continue
                current_round_unix = int(current_round_dt.timestamp())

                dist_to_this = abs(lua_ts - target_unix)
                dist_to_current = abs(lua_ts - current_round_unix)

                if dist_to_this < dist_to_current:
                    await self.db_adapter.execute(
                        "UPDATE lua_round_teams SET round_id = ? WHERE id = ?",
                        (round_id, lua_id),
                    )
                    logger.info(
                        "🔗 Lua round re-link (stale fix): lua_id=%s moved %s → %s "
                        "(dist: %ss→%ss, map=%s R%s)",
                        lua_id, current_rid, round_id,
                        dist_to_current, dist_to_this, map_name, round_number,
                    )
        except Exception as e:
            logger.debug(f"Lua round link failed: {e}")

    async def _has_lua_round_teams_round_id(self) -> bool:
        """
        Check if lua_round_teams.round_id exists (cached).
        """
        if hasattr(self, "_lua_round_teams_has_round_id"):
            return bool(self._lua_round_teams_has_round_id)

        try:
            result = await self.db_adapter.fetch_one(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'lua_round_teams' AND column_name = 'round_id'"
            )
            self._lua_round_teams_has_round_id = bool(result)
        except Exception:
            self._lua_round_teams_has_round_id = False
        return bool(self._lua_round_teams_has_round_id)

    async def _has_lua_spawn_stats_table(self) -> bool:
        """
        Check if lua_spawn_stats table exists (cached).
        """
        if hasattr(self, "_lua_spawn_stats_exists"):
            return bool(self._lua_spawn_stats_exists)
        try:
            result = await self.db_adapter.fetch_val(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'lua_spawn_stats'
                )
                """
            )
            self._lua_spawn_stats_exists = bool(result)
        except Exception:
            self._lua_spawn_stats_exists = False
        return bool(self._lua_spawn_stats_exists)

    async def _trigger_team_detection(self, filename: str):
        """
        DEPRECATED: Team detection now happens in _handle_team_tracking()
        during round import.

        This method is kept for backwards compatibility but does nothing.
        Teams are now created on R1 and updated with new players on each round.
        """
        # No-op - team tracking is now handled by _handle_team_tracking()
        # which is called during _import_stats_to_db() for every round
        logger.debug(f"_trigger_team_detection called but handled by new system: {filename}")

    async def _store_lua_round_teams(self, round_metadata: dict):
        """
        Store Lua-captured team composition and timing data in database.

        This data is kept separate from stats file parsing - it's real-time capture
        from the game engine, labeled as such. Useful for:
        - Accurate team composition at exact round end (before disconnects)
        - Surrender timing fix (actual_duration_seconds)
        - Pause tracking
        - Cross-referencing with stats file data for debugging

        Data stored in lua_round_teams table with match_id + round_number key.
        """
        try:
            # Generate match_id from timestamp and map (same pattern used elsewhere)
            round_end = round_metadata.get('round_end_unix', 0)
            map_name = round_metadata.get('map_name', 'unknown')
            round_number = round_metadata.get('round_number', 0)

            if round_end == 0:
                webhook_logger.warning("Cannot store Lua teams: missing round_end_unix")
                return None

            # Create match_id in same format as rounds table
            # Format: YYYY-MM-DD-HHMMSS (timestamp only, NO map name)
            # This matches how postgresql_database_manager stores match_id
            timestamp = datetime.fromtimestamp(round_end)
            match_id = timestamp.strftime('%Y-%m-%d-%H%M%S')

            # Try to resolve round_id for direct linking (may be None if stats not imported yet)
            round_id = await self._resolve_round_id_for_metadata(None, round_metadata)
            try:
                fallback_round_number = int(round_number or 0)
            except (TypeError, ValueError):
                fallback_round_number = 0
            corr_match_id, corr_map_name, corr_round_number = await self._resolve_round_correlation_context(
                round_id,
                fallback_match_id=match_id,
                fallback_map_name=map_name,
                fallback_round_number=fallback_round_number,
            )

            # Serialize team data as JSON
            axis_players = round_metadata.get('axis_players', [])
            allies_players = round_metadata.get('allies_players', [])

            # Get Lua version from footer if available (we'll default to unknown)
            lua_version = round_metadata.get('lua_version', 'unknown')
            normalized_end_reason = normalize_end_reason(round_metadata.get('end_reason'))
            normalized_winner_team = normalize_side_value(
                round_metadata.get('winner_team'),
                allow_unknown=True,
            )
            normalized_defender_team = normalize_side_value(
                round_metadata.get('defender_team'),
                allow_unknown=True,
            )

            # Insert or update (upsert on conflict)
            # v1.2.0: Added warmup timing columns (lua_warmup_seconds, lua_warmup_start_unix)
            # v1.3.0: Added lua_pause_events JSONB column for detailed pause timestamps
            # v1.4.0: Added surrender tracking and match score columns
            has_round_id = await self._has_lua_round_teams_round_id()
            if has_round_id:
                query = """
                    INSERT INTO lua_round_teams (
                        match_id, round_number, round_id, axis_players, allies_players,
                        round_start_unix, round_end_unix, actual_duration_seconds,
                        total_pause_seconds, pause_count, end_reason,
                        winner_team, defender_team, map_name, time_limit_minutes,
                        lua_warmup_seconds, lua_warmup_start_unix,
                        lua_pause_events,
                        surrender_team, surrender_caller_guid, surrender_caller_name,
                        axis_score, allies_score,
                        lua_version
                    ) VALUES (
                        $1, $2, $3, $4::jsonb, $5::jsonb,
                        $6, $7, $8,
                        $9, $10, $11,
                        $12, $13, $14, $15,
                        $16, $17,
                        $18::jsonb,
                        $19, $20, $21,
                        $22, $23,
                        $24
                    )
                    ON CONFLICT (match_id, round_number) DO UPDATE SET
                        axis_players = EXCLUDED.axis_players,
                        allies_players = EXCLUDED.allies_players,
                        round_id = COALESCE(EXCLUDED.round_id, lua_round_teams.round_id),
                        round_start_unix = EXCLUDED.round_start_unix,
                        round_end_unix = EXCLUDED.round_end_unix,
                        actual_duration_seconds = EXCLUDED.actual_duration_seconds,
                        total_pause_seconds = EXCLUDED.total_pause_seconds,
                        pause_count = EXCLUDED.pause_count,
                        end_reason = EXCLUDED.end_reason,
                        winner_team = EXCLUDED.winner_team,
                        defender_team = EXCLUDED.defender_team,
                        map_name = EXCLUDED.map_name,
                        time_limit_minutes = EXCLUDED.time_limit_minutes,
                        lua_warmup_seconds = EXCLUDED.lua_warmup_seconds,
                        lua_warmup_start_unix = EXCLUDED.lua_warmup_start_unix,
                        lua_pause_events = EXCLUDED.lua_pause_events,
                        surrender_team = EXCLUDED.surrender_team,
                        surrender_caller_guid = EXCLUDED.surrender_caller_guid,
                        surrender_caller_name = EXCLUDED.surrender_caller_name,
                        axis_score = EXCLUDED.axis_score,
                        allies_score = EXCLUDED.allies_score,
                        lua_version = EXCLUDED.lua_version,
                        captured_at = CURRENT_TIMESTAMP
                """
            else:
                query = """
                    INSERT INTO lua_round_teams (
                        match_id, round_number, axis_players, allies_players,
                        round_start_unix, round_end_unix, actual_duration_seconds,
                        total_pause_seconds, pause_count, end_reason,
                        winner_team, defender_team, map_name, time_limit_minutes,
                        lua_warmup_seconds, lua_warmup_start_unix,
                        lua_pause_events,
                        surrender_team, surrender_caller_guid, surrender_caller_name,
                        axis_score, allies_score,
                        lua_version
                    ) VALUES (
                        $1, $2, $3::jsonb, $4::jsonb,
                        $5, $6, $7,
                        $8, $9, $10,
                        $11, $12, $13, $14,
                        $15, $16,
                        $17::jsonb,
                        $18, $19, $20,
                        $21, $22,
                        $23
                    )
                    ON CONFLICT (match_id, round_number) DO UPDATE SET
                        axis_players = EXCLUDED.axis_players,
                        allies_players = EXCLUDED.allies_players,
                        round_start_unix = EXCLUDED.round_start_unix,
                        round_end_unix = EXCLUDED.round_end_unix,
                        actual_duration_seconds = EXCLUDED.actual_duration_seconds,
                        total_pause_seconds = EXCLUDED.total_pause_seconds,
                        pause_count = EXCLUDED.pause_count,
                        end_reason = EXCLUDED.end_reason,
                        winner_team = EXCLUDED.winner_team,
                        defender_team = EXCLUDED.defender_team,
                        map_name = EXCLUDED.map_name,
                        time_limit_minutes = EXCLUDED.time_limit_minutes,
                        lua_warmup_seconds = EXCLUDED.lua_warmup_seconds,
                        lua_warmup_start_unix = EXCLUDED.lua_warmup_start_unix,
                        lua_pause_events = EXCLUDED.lua_pause_events,
                        surrender_team = EXCLUDED.surrender_team,
                        surrender_caller_guid = EXCLUDED.surrender_caller_guid,
                        surrender_caller_name = EXCLUDED.surrender_caller_name,
                        axis_score = EXCLUDED.axis_score,
                        allies_score = EXCLUDED.allies_score,
                        lua_version = EXCLUDED.lua_version,
                        captured_at = CURRENT_TIMESTAMP
                """

            # Get pause events array (v1.3.0)
            pause_events = round_metadata.get('lua_pause_events', [])

            if has_round_id:
                params = (
                    match_id,
                    round_number,
                    round_id,
                    json.dumps(axis_players),
                    json.dumps(allies_players),
                    round_metadata.get('round_start_unix'),
                    round_metadata.get('round_end_unix'),
                    round_metadata.get('actual_duration_seconds'),
                    round_metadata.get('total_pause_seconds', 0),
                    round_metadata.get('pause_count', 0),
                    normalized_end_reason,
                    normalized_winner_team,
                    normalized_defender_team,
                    map_name,
                    round_metadata.get('time_limit_minutes'),
                    round_metadata.get('lua_warmup_seconds', 0),
                    round_metadata.get('lua_warmup_start_unix', 0),
                    json.dumps(pause_events),  # v1.3.0: Pause event timestamps
                    round_metadata.get('surrender_team', 0),  # v1.4.0
                    round_metadata.get('surrender_caller_guid', ''),  # v1.4.0
                    round_metadata.get('surrender_caller_name', ''),  # v1.4.0
                    round_metadata.get('axis_score', 0),  # v1.4.0
                    round_metadata.get('allies_score', 0),  # v1.4.0
                    lua_version,
                )
            else:
                params = (
                    match_id,
                    round_number,
                    json.dumps(axis_players),
                    json.dumps(allies_players),
                    round_metadata.get('round_start_unix'),
                    round_metadata.get('round_end_unix'),
                    round_metadata.get('actual_duration_seconds'),
                    round_metadata.get('total_pause_seconds', 0),
                    round_metadata.get('pause_count', 0),
                    normalized_end_reason,
                    normalized_winner_team,
                    normalized_defender_team,
                    map_name,
                    round_metadata.get('time_limit_minutes'),
                    round_metadata.get('lua_warmup_seconds', 0),
                    round_metadata.get('lua_warmup_start_unix', 0),
                    json.dumps(pause_events),  # v1.3.0: Pause event timestamps
                    round_metadata.get('surrender_team', 0),  # v1.4.0
                    round_metadata.get('surrender_caller_guid', ''),  # v1.4.0
                    round_metadata.get('surrender_caller_name', ''),  # v1.4.0
                    round_metadata.get('axis_score', 0),  # v1.4.0
                    round_metadata.get('allies_score', 0),  # v1.4.0
                    lua_version,
                )

            await self.db_adapter.execute(query, params)

            axis_count = len(axis_players)
            allies_count = len(allies_players)
            webhook_logger.info(
                f"💾 Stored Lua round data: {match_id} R{round_number} "
                f"(Axis: {axis_count}, Allies: {allies_count})"
            )

            # 🔗 CORRELATION: notify of lua teams arrival
            if hasattr(self, 'correlation_service') and self.correlation_service:
                try:
                    # Fetch the lua_round_teams id for this upsert
                    lua_row = await self.db_adapter.fetch_one(
                        "SELECT id FROM lua_round_teams WHERE match_id = $1 AND round_number = $2",
                        (match_id, round_number),
                    )
                    lua_teams_id = lua_row[0] if lua_row else None
                    if lua_teams_id:
                        await self.correlation_service.on_lua_teams_stored(
                            match_id=corr_match_id,
                            round_number=corr_round_number,
                            lua_teams_id=lua_teams_id,
                            map_name=corr_map_name,
                        )
                except Exception as corr_err:
                    webhook_logger.warning(f"[CORRELATION] lua_teams hook error (non-fatal): {corr_err}")
            return round_id

        except Exception as e:
            # Non-fatal: log warning but don't fail the webhook processing
            # This could fail if table doesn't exist (migration not run)
            webhook_logger.warning(f"⚠️ Could not store Lua team data: {e}")
            return None

    async def _store_lua_spawn_stats(self, round_metadata: dict, spawn_stats: list) -> None:
        """
        Store per-player spawn/death timing stats captured by Lua webhook.

        Expected spawn_stats format (list of dicts):
          {guid, name, spawns, deaths, dead_seconds, avg_respawn, max_respawn}
        """
        if not spawn_stats:
            return
        try:
            if not await self._has_lua_spawn_stats_table():
                webhook_logger.warning("⚠️ lua_spawn_stats table missing (migration not run).")
                return

            round_end = round_metadata.get('round_end_unix', 0)
            map_name = round_metadata.get('map_name', 'unknown')
            round_number = round_metadata.get('round_number', 0)

            if round_end == 0:
                webhook_logger.warning("Cannot store spawn stats: missing round_end_unix")
                return

            timestamp = datetime.fromtimestamp(round_end)
            match_id = timestamp.strftime('%Y-%m-%d-%H%M%S')
            round_id = await self._resolve_round_id_for_metadata(None, round_metadata)

            query = """
                INSERT INTO lua_spawn_stats (
                    match_id, round_number, round_id, map_name, round_end_unix,
                    player_guid, player_name,
                    spawn_count, death_count, dead_seconds,
                    avg_respawn_seconds, max_respawn_seconds
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    $6, $7,
                    $8, $9, $10,
                    $11, $12
                )
                ON CONFLICT (match_id, round_number, player_guid) DO UPDATE SET
                    round_id = COALESCE(EXCLUDED.round_id, lua_spawn_stats.round_id),
                    player_name = EXCLUDED.player_name,
                    spawn_count = EXCLUDED.spawn_count,
                    death_count = EXCLUDED.death_count,
                    dead_seconds = EXCLUDED.dead_seconds,
                    avg_respawn_seconds = EXCLUDED.avg_respawn_seconds,
                    max_respawn_seconds = EXCLUDED.max_respawn_seconds,
                    captured_at = CURRENT_TIMESTAMP
            """

            for entry in spawn_stats:
                guid = (entry.get("guid") or "")[:32]
                name = entry.get("name") or "unknown"
                spawns = int(entry.get("spawns") or 0)
                deaths = int(entry.get("deaths") or 0)
                dead_seconds = int(entry.get("dead_seconds") or 0)
                avg_respawn = int(entry.get("avg_respawn") or 0)
                max_respawn = int(entry.get("max_respawn") or 0)

                if not guid:
                    continue

                params = (
                    match_id,
                    round_number,
                    round_id,
                    map_name,
                    round_end,
                    guid,
                    name,
                    spawns,
                    deaths,
                    dead_seconds,
                    avg_respawn,
                    max_respawn,
                )
                await self.db_adapter.execute(query, params)

            webhook_logger.info(
                f"💾 Stored Lua spawn stats: {match_id} R{round_number} "
                f"(players: {len(spawn_stats)})"
            )

        except Exception as e:
            webhook_logger.warning(f"⚠️ Could not store Lua spawn stats: {e}")
