"""ProximityCog mixin: Null-round relinker (fixes proximity rows linked to wrong rounds).

Extracted from bot/cogs/proximity_cog.py in Mega Audit v4 / Sprint 3.

All methods live on ProximityCog via mixin inheritance.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from discord.ext import tasks

logger = logging.getLogger("bot.cogs.proximity")

# Rounds whose target_dt is older than this are treated as permanent
# orphans: the stats file was never written (surrender crash, disk full,
# VPS network loss, …) and the round_id will never resolve. Skipping them
# stops the 5-minute cron from spamming `no_rows_for_map_round` warnings
# every cycle. Tuned against production logs where orphans aged 400 h-1600 h
# repeated every 5 min forever.
_PERMANENT_ORPHAN_AGE_HOURS = 48


class _ProximityRelinkerMixin:
    """Null-round relinker (fixes proximity rows linked to wrong rounds) for ProximityCog."""

    async def _relink_null_round_ids(self) -> None:
        """Find proximity rows with NULL round_id and attempt to resolve them."""
        try:
            from bot.core.round_linker import resolve_round_id

            db = self.bot.db_adapter

            # Find distinct unlinked proximity rounds across all tables that
            # carry session_date + round_number + round_start_unix.
            # Tables without those columns (proximity_revive, proximity_weapon_accuracy)
            # are excluded; they rely on map_name + round_start_unix fallback only.
            unlinked = await db.fetch_all(
                "SELECT DISTINCT map_name, round_number, round_start_unix, session_date FROM ("
                "  SELECT map_name, round_number, round_start_unix, session_date FROM proximity_reaction_metric WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_spawn_timing WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_team_cohesion WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_kill_outcome WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_carrier_event WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_carrier_kill WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_carrier_return WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_combat_position WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_construction_event WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_crossfire_opportunity WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_escort_credit WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_focus_fire WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_hit_region WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_lua_trade_kill WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_objective_focus WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_objective_run WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_support_summary WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_team_push WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_trade_event WHERE round_id IS NULL"
                "  UNION SELECT map_name, round_number, round_start_unix, session_date FROM proximity_vehicle_progress WHERE round_id IS NULL"
                ") sub ORDER BY session_date DESC LIMIT 50"
            )

            if not unlinked:
                return

            linked = 0
            failed = 0
            stale_skipped = 0
            now = datetime.utcnow()

            for row in unlinked:
                map_name = row[0] if isinstance(row, (list, tuple)) else row.get('map_name') or row['map_name']
                round_number = row[1] if isinstance(row, (list, tuple)) else row.get('round_number') or row['round_number']
                round_start_unix = row[2] if isinstance(row, (list, tuple)) else row.get('round_start_unix') or row['round_start_unix']
                session_date = row[3] if isinstance(row, (list, tuple)) else row.get('session_date') or row['session_date']

                # Build target_dt from unix timestamp if available.
                # Use fromtimestamp() WITHOUT tz to get LOCAL naive datetime,
                # matching the round_linker's candidate convention.
                target_dt = None
                if round_start_unix:
                    try:
                        target_dt = datetime.fromtimestamp(int(round_start_unix))
                    except (ValueError, TypeError, OSError):
                        pass  # Invalid timestamp format; fall back to date-based resolution

                # Skip permanent orphans — rows whose target time is older
                # than the configured threshold will never resolve and
                # only spam the log. Counted separately so an operator can
                # still see them in the summary line.
                if target_dt is not None:
                    age_hours = (now - target_dt).total_seconds() / 3600.0
                    if age_hours > _PERMANENT_ORPHAN_AGE_HOURS:
                        stale_skipped += 1
                        continue

                round_date_str = str(session_date) if session_date else None

                round_id = await resolve_round_id(
                    db,
                    map_name,
                    round_number,
                    target_dt=target_dt,
                    round_date=round_date_str,
                    window_minutes=120,
                )

                if round_id is None:
                    failed += 1
                    continue

                # Pre-built parameterized relink queries per table (no string concat in SQL)
                _RELINK_PRIMARY = {
                    "proximity_carrier_event": "UPDATE proximity_carrier_event SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_number = $3 AND session_date = $4",
                    "proximity_carrier_kill": "UPDATE proximity_carrier_kill SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_number = $3 AND session_date = $4",
                    "proximity_carrier_return": "UPDATE proximity_carrier_return SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_number = $3 AND session_date = $4",
                    "proximity_combat_position": "UPDATE proximity_combat_position SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_number = $3 AND session_date = $4",
                    "proximity_construction_event": "UPDATE proximity_construction_event SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_number = $3 AND session_date = $4",
                    "proximity_crossfire_opportunity": "UPDATE proximity_crossfire_opportunity SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_number = $3 AND session_date = $4",
                    "proximity_escort_credit": "UPDATE proximity_escort_credit SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_number = $3 AND session_date = $4",
                    "proximity_focus_fire": "UPDATE proximity_focus_fire SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_number = $3 AND session_date = $4",
                    "proximity_hit_region": "UPDATE proximity_hit_region SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_number = $3 AND session_date = $4",
                    "proximity_kill_outcome": "UPDATE proximity_kill_outcome SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_number = $3 AND session_date = $4",
                    "proximity_lua_trade_kill": "UPDATE proximity_lua_trade_kill SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_number = $3 AND session_date = $4",
                    "proximity_objective_focus": "UPDATE proximity_objective_focus SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_number = $3 AND session_date = $4",
                    "proximity_objective_run": "UPDATE proximity_objective_run SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_number = $3 AND session_date = $4",
                    "proximity_reaction_metric": "UPDATE proximity_reaction_metric SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_number = $3 AND session_date = $4",
                    "proximity_spawn_timing": "UPDATE proximity_spawn_timing SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_number = $3 AND session_date = $4",
                    "proximity_support_summary": "UPDATE proximity_support_summary SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_number = $3 AND session_date = $4",
                    "proximity_team_cohesion": "UPDATE proximity_team_cohesion SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_number = $3 AND session_date = $4",
                    "proximity_team_push": "UPDATE proximity_team_push SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_number = $3 AND session_date = $4",
                    "proximity_trade_event": "UPDATE proximity_trade_event SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_number = $3 AND session_date = $4",
                    "proximity_vehicle_progress": "UPDATE proximity_vehicle_progress SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_number = $3 AND session_date = $4",
                }
                _RELINK_FALLBACK = {
                    "proximity_carrier_event": "UPDATE proximity_carrier_event SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_start_unix = $3",
                    "proximity_carrier_kill": "UPDATE proximity_carrier_kill SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_start_unix = $3",
                    "proximity_carrier_return": "UPDATE proximity_carrier_return SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_start_unix = $3",
                    "proximity_combat_position": "UPDATE proximity_combat_position SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_start_unix = $3",
                    "proximity_construction_event": "UPDATE proximity_construction_event SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_start_unix = $3",
                    "proximity_crossfire_opportunity": "UPDATE proximity_crossfire_opportunity SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_start_unix = $3",
                    "proximity_escort_credit": "UPDATE proximity_escort_credit SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_start_unix = $3",
                    "proximity_focus_fire": "UPDATE proximity_focus_fire SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_start_unix = $3",
                    "proximity_hit_region": "UPDATE proximity_hit_region SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_start_unix = $3",
                    "proximity_kill_outcome": "UPDATE proximity_kill_outcome SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_start_unix = $3",
                    "proximity_lua_trade_kill": "UPDATE proximity_lua_trade_kill SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_start_unix = $3",
                    "proximity_objective_focus": "UPDATE proximity_objective_focus SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_start_unix = $3",
                    "proximity_objective_run": "UPDATE proximity_objective_run SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_start_unix = $3",
                    "proximity_reaction_metric": "UPDATE proximity_reaction_metric SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_start_unix = $3",
                    "proximity_spawn_timing": "UPDATE proximity_spawn_timing SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_start_unix = $3",
                    "proximity_support_summary": "UPDATE proximity_support_summary SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_start_unix = $3",
                    "proximity_team_cohesion": "UPDATE proximity_team_cohesion SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_start_unix = $3",
                    "proximity_team_push": "UPDATE proximity_team_push SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_start_unix = $3",
                    "proximity_trade_event": "UPDATE proximity_trade_event SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_start_unix = $3",
                    "proximity_vehicle_progress": "UPDATE proximity_vehicle_progress SET round_id = $1 WHERE round_id IS NULL AND map_name = $2 AND round_start_unix = $3",
                }
                for table in self._PROXIMITY_ROUND_ID_TABLES:
                    try:
                        await db.execute(
                            _RELINK_PRIMARY[table],
                            (round_id, map_name, round_number, session_date),
                        )
                    except Exception as e:
                        logger.warning("Re-linker: %s primary update failed: %s", table, e)
                        try:
                            await db.execute(
                                _RELINK_FALLBACK[table],
                                (round_id, map_name, round_start_unix),
                            )
                        except Exception as e:
                            logger.warning(f"Re-linker: {table} fallback update failed: {e}")

                linked += 1

            if linked > 0 or failed > 0 or stale_skipped > 0:
                logger.info(
                    "🔗 Proximity re-linker: %d linked, %d unresolved, "
                    "%d stale skipped (>%dh) — of %d total",
                    linked, failed, stale_skipped,
                    _PERMANENT_ORPHAN_AGE_HOURS, len(unlinked),
                )

        except Exception as e:
            logger.error(f"Re-linker error: {e}", exc_info=True)

    @tasks.loop(minutes=5)
    async def relink_null_rounds(self):
        """Periodically attempt to link NULL round_id rows in proximity tables."""
        await self._relink_null_round_ids()

    @relink_null_rounds.before_loop
    async def before_relink(self):
        """Wait for bot to be ready + 60s before starting re-linker."""
        await self.bot.wait_until_ready()
        await asyncio.sleep(60)
