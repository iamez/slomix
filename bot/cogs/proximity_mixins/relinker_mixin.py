"""ProximityCog mixin: Null-round relinker (fixes proximity rows linked to wrong rounds).

Extracted from bot/cogs/proximity_cog.py in Mega Audit v4 / Sprint 3.

All methods live on ProximityCog via mixin inheritance.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from discord.ext import tasks

from bot.core.dead_hours import awake_cutoff
from bot.services.lua_round_storage_mixin import _lua_exact_source_lock_key

logger = logging.getLogger("bot.cogs.proximity")

# Rounds whose target_dt is older than this are treated as permanent
# orphans: the stats file was never written (surrender crash, warmup map
# never paired, disk full, VPS network loss, …) and the round_id will never
# resolve. Skipping them stops the 5-minute cron from retrying them every
# cycle. Lowered 48h→6h (2026-06-09) to match the correlation saga's 6h
# timeout: a stats file that hasn't landed 6h after the round is never
# coming (the live race window is only 120min), and the old 48h kept warmup
# orphans like mp_sillyctf retrying for two days. Combined with quiet=True on
# the resolve_round_id call below (relinker retries log at DEBUG, not WARNING),
# this kills the `no_rows_for_map_round` log spam.
#
# Counted in importer-AWAKE hours, not wall hours (2026-08-11). The stats
# importer sleeps 02:00–11:00 CET (dead_hours.py) while proximity ingestion
# keeps landing rows, so a plain 6h wall clock wrote off every round played
# 02:00–05:00 CET before the importer could possibly create its `rounds`
# row (measured: 5 night-test rounds → 8,810 permanent orphans, relinker
# linked 0). awake_cutoff() skips the dead window when aging, preserving
# the #369 intent — 6h of *running importer* with nothing landing means the
# file is never coming — with a worst-case wall horizon of 15h, still far
# below the 48h that #369 lowered.
_PERMANENT_ORPHAN_AGE_HOURS = 6


# Tables the detection query scans for rounds that need (re-)linking. Hoisted
# to module scope so the fanout-coverage test can assert it against
# ProximityCog._PROXIMITY_ROUND_ID_TABLES: the two lists live in different
# files and are maintained by hand, which is how proximity_shot_fired came to
# be in neither for three months.
#
# Being in the fanout list alone is not enough. That list only says "update
# this table once some round is known to need work" — this one is what makes a
# round known. A table present in neither is invisible: its rows can be the
# only unlinked ones for a round and nothing will ever notice.
#
# lua_round_teams is deliberately absent: it has no session_date column, so it
# cannot use the generic leg shape and gets its own synthesized-date legs below.
_DETECTION_TABLES: tuple[str, ...] = (
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
    "combat_engagement", "player_track",
    # revive + weapon_accuracy gained the identity columns with migration 065.
    "proximity_revive", "proximity_weapon_accuracy",
    # shot_fired: added 2026-08-04. Its absence here was the load-bearing half
    # of the bug — the observed failure was a round whose kill_outcome linked
    # fine and whose shot_fired did not, so no leg ever flagged that round.
    # It carries all four identity columns, so no special-casing is needed.
    "proximity_shot_fired",
    # aim_lock/comm_event/skill_snapshot/spawn_select: added 2026-08-11
    # (FIX 9). Created by migration 058 (proximity v7) with a round_id and
    # all four identity columns, but never added to any relinker list — the
    # same hole as shot_fired, this time found by the schema coverage
    # contract (tests/unit/test_round_id_coverage_contract.py) rather than
    # by an incident. Partial unlinked indexes: migration 071.
    "proximity_aim_lock", "proximity_comm_event",
    "proximity_skill_snapshot", "proximity_spawn_select",
)


# round_id tables handled by DEDICATED SQL rather than the generic legs and
# templates above: lua_round_teams has no session_date column (it gets its
# own synthesized-date detection legs and the _RELINK_LUA_TEAMS_* templates),
# and lua_spawn_stats has neither round_start_unix nor session_date — it is
# healed by propagation from lua_round_teams keyed on match_id
# (_RELINK_LUA_SPAWN_FROM_TEAMS_TEMPLATE).
_SPECIAL_CASE_TABLES: tuple[str, ...] = ("lua_round_teams", "lua_spawn_stats")


# Tables that carry a round_id column but are DELIBERATELY outside both the
# generic legs and the special cases. The schema coverage contract
# (tests/unit/test_round_id_coverage_contract.py) derives the full set of
# round_id-bearing tables from tools/schema_postgresql.sql and fails when a
# table is neither detected, special-cased, nor listed here with a reason —
# so the next shot_fired-shaped omission cannot happen silently. None of
# these carries the four-column round identity the generic legs key on, and
# the contract test rejects an exemption for any table that does.
_DETECTION_EXEMPT_TABLES: dict[str, str] = {
    "player_comprehensive_stats": (
        "stats path: the importer assigns round_id while creating the rounds "
        "row itself (0 NULLs on dev); no round_start_unix/session_date "
        "columns for the generic leg shape"
    ),
    "weapon_comprehensive_stats": (
        "stats path, same shape and lifecycle as player_comprehensive_stats"
    ),
    "round_awards": (
        "stats path, same shape and lifecycle as player_comprehensive_stats"
    ),
    "round_vs_stats": (
        "stats path, same shape and lifecycle as player_comprehensive_stats"
    ),
    "round_assembly_events": (
        "assembly diagnostics ledger: rows describe the linking PROCESS and "
        "may legitimately precede their rounds row; no round_start_unix"
    ),
    "player_skill_history": (
        "derived rating history scoped by gaming session, not round "
        "identity; round_id is optional provenance and has never been "
        "populated (2,435/2,435 NULL on dev, 2026-08-11) — nothing "
        "round-scoped reads it"
    ),
    "processed_endstats_files": (
        "file-ingestion bookkeeping; round_id is best-effort provenance and "
        "the row carries no map/round identity columns to relink by"
    ),
}


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
# lua_round_teams has no session_date column (unlike every other table in
# the fanout), so it can't use _RELINK_PRIMARY_TEMPLATE as-is. This uses
# round_number + round_start_unix instead — still more precise than the
# generic fallback template below, which only has map_name + round_start_unix
# to work with (Codex §18/L3: lua_round_teams was excluded from the fanout
# entirely before this; it's one of the tables with the worst wrong-link
# rates precisely because a bad link here was never even retried).
_RELINK_LUA_TEAMS_TEMPLATE = (
    "UPDATE lua_round_teams SET round_id = $1 "
    "WHERE map_name = $2 AND round_number = $3 AND round_start_unix = $4 "
    "  AND (round_id IS NULL OR round_id != $1)"
)
_RELINK_LUA_TEAMS_EXACT_TEMPLATE = (
    "WITH source_state AS ("
    "  SELECT COUNT(*) AS source_count FROM lua_round_teams "
    "  WHERE LOWER(BTRIM(map_name)) = LOWER(BTRIM($1)) "
    "    AND round_number = $2 AND round_start_unix = $3 "
    "), target_state AS ("
    "  SELECT COUNT(*) AS target_count, MIN(id) AS target_id FROM rounds "
    "  WHERE LOWER(BTRIM(map_name)) = LOWER(BTRIM($1)) "
    "    AND round_number = $2 AND round_start_unix = $3 "
    ") "
    "UPDATE lua_round_teams l SET round_id = CASE "
    "  WHEN source_state.source_count = 1 AND target_state.target_count = 1 "
    "    THEN target_state.target_id ELSE NULL END "
    "FROM source_state, target_state "
    "WHERE LOWER(BTRIM(l.map_name)) = LOWER(BTRIM($1)) "
    "  AND l.round_number = $2 AND l.round_start_unix = $3 "
    "  AND l.round_id IS DISTINCT FROM CASE "
    "    WHEN source_state.source_count = 1 AND target_state.target_count = 1 "
    "      THEN target_state.target_id ELSE NULL END"
)
_RELINK_LUA_SPAWN_FROM_TEAMS_TEMPLATE = (
    "UPDATE lua_spawn_stats s SET round_id = l.round_id "
    "FROM lua_round_teams l "
    "WHERE LOWER(BTRIM(l.map_name)) = LOWER(BTRIM($1)) "
    "  AND l.round_number = $2 AND l.round_start_unix = $3 "
    "  AND s.match_id = l.match_id AND s.round_number = l.round_number "
    "  AND LOWER(BTRIM(s.map_name)) IS NOT DISTINCT FROM LOWER(BTRIM(l.map_name)) "
    "  AND s.round_id IS DISTINCT FROM l.round_id"
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
            # combat_engagement/player_track added (Codex §18/L3 — both have
            # a session_date column, so they fit the generic leg shape below
            # exactly). lua_round_teams is handled SEPARATELY: it has no
            # session_date column at all, so it needs its own leg pair that
            # synthesizes one from round_start_unix for the UNION.
            tables_with_round_number = _DETECTION_TABLES
            now = datetime.now(timezone.utc)
            # Dead-hours-aware: 6 importer-awake hours, not 6 wall hours
            # (see _PERMANENT_ORPHAN_AGE_HOURS comment above).
            cutoff = awake_cutoff(now, _PERMANENT_ORPHAN_AGE_HOURS)
            cutoff_unix = int(cutoff.timestamp())
            cutoff_date = cutoff.date()
            recent_source = (
                "(round_start_unix >= $1 OR "
                "((round_start_unix IS NULL OR round_start_unix <= 0) "
                "AND session_date >= $2))"
            )
            recent_source_alias = (
                "(pko.round_start_unix >= $1 OR "
                "((pko.round_start_unix IS NULL OR pko.round_start_unix <= 0) "
                "AND pko.session_date >= $2))"
            )
            # Each leg may report the same round many times. De-duplicate
            # once at the outer SELECT instead of forcing PostgreSQL to sort
            # and unique after every UNION node in this 50-leg query.
            null_legs = " UNION ALL ".join(
                f"SELECT map_name, round_number, round_start_unix, session_date "
                f"FROM {t} WHERE round_id IS NULL AND {recent_source}"
                for t in tables_with_round_number
            )
            mismatch_legs = " UNION ALL ".join(
                f"SELECT pko.map_name, pko.round_number, pko.round_start_unix, pko.session_date "
                f"FROM {t} pko JOIN rounds r ON r.id = pko.round_id "
                f"WHERE {recent_source_alias} "
                f"  AND r.round_start_unix IS NOT NULL "
                f"  AND pko.round_start_unix != r.round_start_unix"
                for t in tables_with_round_number
            )
            # lua_round_teams: no session_date column — synthesize one from
            # round_start_unix so this leg's column shape matches the UNION.
            lua_teams_null_leg = (
                "SELECT map_name, round_number, round_start_unix, "
                "CASE WHEN round_start_unix IS NOT NULL "
                "THEN TO_TIMESTAMP(round_start_unix)::date ELSE NULL END AS session_date "
                "FROM lua_round_teams WHERE round_id IS NULL "
                "AND round_start_unix >= $1"
            )
            lua_teams_mismatch_leg = (
                "SELECT pko.map_name, pko.round_number, pko.round_start_unix, "
                "CASE WHEN pko.round_start_unix IS NOT NULL "
                "THEN TO_TIMESTAMP(pko.round_start_unix)::date ELSE NULL END AS session_date "
                "FROM lua_round_teams pko JOIN rounds r ON r.id = pko.round_id "
                "WHERE pko.round_start_unix >= $1 "
                "  AND r.round_start_unix IS NOT NULL "
                "  AND pko.round_start_unix != r.round_start_unix"
            )
            null_legs = f"{null_legs} UNION ALL {lua_teams_null_leg}"
            mismatch_legs = f"{mismatch_legs} UNION ALL {lua_teams_mismatch_leg}"
            unlinked = await db.fetch_all(
                f"SELECT DISTINCT map_name, round_number, round_start_unix, session_date "
                f"FROM ({null_legs} UNION ALL {mismatch_legs}) sub "
                f"ORDER BY session_date DESC LIMIT 50",
                (cutoff_unix, cutoff_date),
            )

            if not unlinked:
                return

            linked = 0
            failed = 0
            stale_skipped = 0
            # Both `cutoff` and `target_dt` are tz-aware UTC so the staleness
            # comparison below isn't affected by the host's UTC offset.
            # Previously (P3 bug) `datetime.utcnow()` was compared against
            # `datetime.fromtimestamp(...)` which returns LOCAL naive —
            # the age calculation silently drifted by ±1–2h on the prod VPS.
            for row in unlinked:
                map_name = row[0] if isinstance(row, (list, tuple)) else row.get('map_name') or row['map_name']
                round_number = row[1] if isinstance(row, (list, tuple)) else row.get('round_number') or row['round_number']
                round_start_unix = row[2] if isinstance(row, (list, tuple)) else row.get('round_start_unix') or row['round_start_unix']
                session_date = row[3] if isinstance(row, (list, tuple)) else row.get('session_date') or row['session_date']

                # tz-aware UTC to match `cutoff` above and prevent drift.
                target_dt = None
                if round_start_unix:
                    try:
                        target_dt = datetime.fromtimestamp(int(round_start_unix), tz=timezone.utc)
                    except (ValueError, TypeError, OSError):
                        pass  # Invalid timestamp format; fall back to date-based resolution

                # Defensive boundary recheck. The discovery SQL already
                # removes permanent orphans; this protects the sub-second
                # edge between its integer cutoff and datetime comparison.
                # Compares against the same dead-hours-aware cutoff as the
                # discovery SQL — a plain wall-clock age here would undo
                # the awake_cutoff fix for rounds played during dead hours.
                if target_dt is not None and target_dt < cutoff:
                    stale_skipped += 1
                    continue

                round_date_str = str(session_date) if session_date else None

                try:
                    exact_start_unix = int(round_start_unix)
                    has_positive_start = exact_start_unix > 0
                except (TypeError, ValueError):
                    exact_start_unix = 0
                    has_positive_start = False

                if has_positive_start:
                    # Positive telemetry timestamps are source-native keys.
                    # Resolve this key before any fuzzy lookup; otherwise a
                    # whitespace/case variation in the source map can make
                    # the fuzzy resolver exit before Lua's normalized exact
                    # update gets a chance to run.
                    exact_rows = await db.fetch_all(
                        "SELECT id FROM rounds "
                        "WHERE LOWER(BTRIM(map_name)) = LOWER(BTRIM($1)) "
                        "  AND round_number = $2 AND round_start_unix = $3 "
                        "ORDER BY id LIMIT 2",
                        (map_name, round_number, exact_start_unix),
                    )
                    if len(exact_rows) == 1:
                        exact_row = exact_rows[0]
                        round_id = int(
                            exact_row[0]
                            if isinstance(exact_row, (list, tuple))
                            else exact_row["id"]
                        )
                    elif not exact_rows:
                        # round_number disagreement fallback (2026-08-11, live
                        # evidence): the engine's round counter can survive a
                        # fresh `map` load issued right after a delivery R2
                        # (stats/endstats/gametime all said R2) while
                        # proximity_tracker resets to round 1 on the new map —
                        # same physical round, two round_numbers. te_escape2,
                        # rounds id 11180: round_start_unix AND round_end_unix
                        # identical in both stores, yet the strict lookup above
                        # returns nothing forever (~159 rows permanently
                        # unlinked on a COVERED table; historically 2 of 643
                        # linkable rounds, 0.31%).
                        #
                        # When map_name (normalized, same as the strict lookup)
                        # + round_start_unix match EXACTLY — the existing exact
                        # path's tolerance is zero, kept here — and exactly ONE
                        # rounds row matches, the timestamps are trusted over
                        # round_number: one game server cannot start two rounds
                        # of the same map in the same second. Zero or multiple
                        # candidates keep the old behaviour (never guess).
                        relaxed_rows = await db.fetch_all(
                            "SELECT id, round_number FROM rounds "
                            "WHERE LOWER(BTRIM(map_name)) = LOWER(BTRIM($1)) "
                            "  AND round_start_unix = $2 "
                            "ORDER BY id LIMIT 2",
                            (map_name, exact_start_unix),
                        )
                        if len(relaxed_rows) == 1:
                            relaxed_row = relaxed_rows[0]
                            round_id = int(
                                relaxed_row[0]
                                if isinstance(relaxed_row, (list, tuple))
                                else relaxed_row["id"]
                            )
                            rounds_rn = (
                                relaxed_row[1]
                                if isinstance(relaxed_row, (list, tuple))
                                else relaxed_row["round_number"]
                            )
                            # WARNING (not DEBUG): this is a real disagreement
                            # between capture paths worth seeing — but it fires
                            # once per affected round, because the fanout below
                            # heals it in the same cycle.
                            logger.warning(
                                "Re-linker: round_number mismatch tolerated on "
                                "exact map+round_start_unix match: map=%s "
                                "source rn=%s, rounds rn=%s, unix=%d -> "
                                "round_id=%d",
                                map_name, round_number, rounds_rn,
                                exact_start_unix, round_id,
                            )
                        else:
                            round_id = None
                    else:
                        round_id = None
                else:
                    round_id = await resolve_round_id(
                        db,
                        map_name,
                        round_number,
                        target_dt=target_dt,
                        round_date=round_date_str,
                        window_minutes=120,
                        quiet=True,  # relinker retries every 5min — log at DEBUG, not WARNING
                    )

                if round_id is None:
                    failed += 1
                    continue

                # Fan out 21 independent table updates per round in parallel
                # (background task on backlog can be hundreds of rounds × 21
                # tables = thousands of sequential round-trips otherwise).
                # Semaphore caps peak pool pressure; per-table primary→fallback
                # retry semantics preserved inside the helper. Loop-locals
                # are bound as kwargs defaults to avoid late-binding (B023).
                _link_sem = asyncio.Semaphore(10)

                async def _link_table(
                    table: str,
                    rid: int = round_id,
                    mn: str = map_name,
                    rn: int = round_number,
                    sd: str = session_date,
                    rsu: int = round_start_unix,
                    sem: asyncio.Semaphore = _link_sem,
                    exact_start: bool = has_positive_start,
                ) -> None:
                    async with sem:
                        try:
                            if table == "lua_round_teams":
                                # No session_date column on this table — use
                                # the dedicated template (map+round_number+
                                # round_start_unix) instead of the generic
                                # primary one.
                                if exact_start:
                                    lock_key = _lua_exact_source_lock_key(
                                        mn, int(rn), int(rsu)
                                    )
                                    async with db.transaction():
                                        await db.fetch_val(
                                            "SELECT pg_advisory_xact_lock($1)",
                                            (lock_key,),
                                        )
                                        await db.execute(
                                            _RELINK_LUA_TEAMS_EXACT_TEMPLATE,
                                            (mn, rn, rsu),
                                        )
                                        await db.execute(
                                            _RELINK_LUA_SPAWN_FROM_TEAMS_TEMPLATE,
                                            (mn, rn, rsu),
                                        )
                                else:
                                    await db.execute(
                                        _RELINK_LUA_TEAMS_TEMPLATE,
                                        (rid, mn, rn, rsu),
                                    )
                            else:
                                await db.execute(
                                    _relink_sql(table),
                                    (rid, mn, rn, sd, rsu),
                                )
                        except Exception as e:
                            logger.warning("Re-linker: %s primary update failed: %s", table, e)
                            if table == "lua_round_teams":
                                return
                            try:
                                await db.execute(
                                    _relink_sql(table, fallback=True),
                                    (rid, mn, rsu),
                                )
                            except Exception as e2:
                                logger.warning(f"Re-linker: {table} fallback update failed: {e2}")

                await asyncio.gather(
                    *(_link_table(t) for t in self._PROXIMITY_ROUND_ID_TABLES)
                )

                linked += 1

            if linked > 0 or failed > 0 or stale_skipped > 0:
                logger.info(
                    "🔗 Proximity re-linker: %d linked, %d unresolved, "
                    "%d stale skipped (>%d awake-h) — of %d total",
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
