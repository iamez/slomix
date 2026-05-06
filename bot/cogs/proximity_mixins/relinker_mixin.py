"""ProximityCog mixin: Null-round relinker (fixes proximity rows linked to wrong rounds).

Extracted from bot/cogs/proximity_cog.py in Mega Audit v4 / Sprint 3.

All methods live on ProximityCog via mixin inheritance.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from discord.ext import tasks

logger = logging.getLogger("bot.cogs.proximity")

# Rounds whose target_dt is older than this are treated as permanent
# orphans: the stats file was never written (surrender crash, disk full,
# VPS network loss, …) and the round_id will never resolve. Skipping them
# stops the 5-minute cron from spamming `no_rows_for_map_round` warnings
# every cycle. Tuned against production logs where orphans aged 400 h-1600 h
# repeated every 5 min forever.
_PERMANENT_ORPHAN_AGE_HOURS = 48


# Relink SQL templates hoisted to module scope (audit P4). Previously
# built anew for every unresolved round every 5 min (50 rounds × 21 tables
# × 2 dicts ≈ 2 100 string constructions/cycle). Both dicts are built
# once at import time from the table list defined on ProximityCog.
#
# We keep the table list in one place (ProximityCog._PROXIMITY_ROUND_ID_TABLES)
# and materialize the dicts lazily on first call so the mixin doesn't need
# to import the cog itself (which would be circular).
_RELINK_PRIMARY_TEMPLATE = (
    "UPDATE {table} SET round_id = $1 "
    "WHERE map_name = $2 AND round_number = $3 AND session_date = $4 "
    "  AND round_start_unix = $5 "
    "  AND (round_id IS NULL OR round_id != $1)"
)
_RELINK_FALLBACK_TEMPLATE = (
    "UPDATE {table} SET round_id = $1 "
    "WHERE map_name = $2 AND round_start_unix = $3 "
    "  AND (round_id IS NULL OR round_id != $1)"
)
_relink_primary_cache: dict[str, str] = {}
_relink_fallback_cache: dict[str, str] = {}


def _relink_sql(table: str, *, fallback: bool = False) -> str:
    """Return (and cache) the relink SQL for a given proximity table."""
    cache = _relink_fallback_cache if fallback else _relink_primary_cache
    if table not in cache:
        template = _RELINK_FALLBACK_TEMPLATE if fallback else _RELINK_PRIMARY_TEMPLATE
        cache[table] = template.format(table=table)
    return cache[table]


class _ProximityRelinkerMixin:
    """Null-round relinker (fixes proximity rows linked to wrong rounds) for ProximityCog."""

    async def _relink_null_round_ids(self) -> None:
        """Find proximity rows with NULL round_id and attempt to resolve them."""
        try:
            from bot.core.round_linker import resolve_round_id

            db = self.bot.db_adapter

            # Find distinct proximity rounds that need (re-)linking: NULL round_id
            # OR round_id pointing to a row whose round_start_unix differs from
            # the proximity row's round_start_unix (back-to-back match race fix).
            # Tables without round_number column rely on map+round_start_unix fallback.
            #
            # Mismatch leg specifically catches: proximity arrived BEFORE stats,
            # round_linker picked nearest-neighbour round (wrong match), then
            # stats arrived later creating the correct round but proximity stayed
            # linked to the wrong one. Without re-linking these, KIS / momentum /
            # BOX score for the mis-routed round are silently corrupted.
            tables_with_round_number = [
                "proximity_reaction_metric", "proximity_spawn_timing",
                "proximity_team_cohesion", "proximity_kill_outcome",
                "proximity_carrier_event", "proximity_carrier_kill",
                "proximity_carrier_return", "proximity_combat_position",
                "proximity_construction_event", "proximity_crossfire_opportunity",
                "proximity_escort_credit", "proximity_focus_fire",
                "proximity_hit_region", "proximity_lua_trade_kill",
                "proximity_objective_focus", "proximity_objective_run",
                "proximity_support_summary", "proximity_team_push",
                "proximity_trade_event", "proximity_vehicle_progress",
            ]
            null_legs = " UNION ".join(
                f"SELECT map_name, round_number, round_start_unix, session_date "
                f"FROM {t} WHERE round_id IS NULL"
                for t in tables_with_round_number
            )
            mismatch_legs = " UNION ".join(
                f"SELECT pko.map_name, pko.round_number, pko.round_start_unix, pko.session_date "
                f"FROM {t} pko JOIN rounds r ON r.id = pko.round_id "
                f"WHERE pko.round_start_unix IS NOT NULL "
                f"  AND r.round_start_unix IS NOT NULL "
                f"  AND pko.round_start_unix != r.round_start_unix"
                for t in tables_with_round_number
            )
            unlinked = await db.fetch_all(
                f"SELECT DISTINCT map_name, round_number, round_start_unix, session_date "
                f"FROM ({null_legs} UNION {mismatch_legs}) sub "
                f"ORDER BY session_date DESC LIMIT 50"
            )

            if not unlinked:
                return

            linked = 0
            failed = 0
            stale_skipped = 0
            # Both `now` and `target_dt` are tz-aware UTC so the 48-h
            # cutoff below isn't affected by the host's UTC offset.
            # Previously (P3 bug) `datetime.utcnow()` was compared against
            # `datetime.fromtimestamp(...)` which returns LOCAL naive —
            # the age calculation silently drifted by ±1–2h on the prod VPS.
            now = datetime.now(timezone.utc)

            for row in unlinked:
                map_name = row[0] if isinstance(row, (list, tuple)) else row.get('map_name') or row['map_name']
                round_number = row[1] if isinstance(row, (list, tuple)) else row.get('round_number') or row['round_number']
                round_start_unix = row[2] if isinstance(row, (list, tuple)) else row.get('round_start_unix') or row['round_start_unix']
                session_date = row[3] if isinstance(row, (list, tuple)) else row.get('session_date') or row['session_date']

                # tz-aware UTC to match `now` above and prevent drift.
                target_dt = None
                if round_start_unix:
                    try:
                        target_dt = datetime.fromtimestamp(int(round_start_unix), tz=timezone.utc)
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

                for table in self._PROXIMITY_ROUND_ID_TABLES:
                    try:
                        await db.execute(
                            _relink_sql(table),
                            (round_id, map_name, round_number, session_date, round_start_unix),
                        )
                    except Exception as e:
                        logger.warning("Re-linker: %s primary update failed: %s", table, e)
                        try:
                            await db.execute(
                                _relink_sql(table, fallback=True),
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
