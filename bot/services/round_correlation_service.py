"""
Round Correlation Service
=========================
Event-driven service that tracks data completeness for each match (R1+R2).

Data arrives from multiple sources at different times:
  1. Lua webhook (~1s after round end)  → lua_round_teams
  2. Stats file  (~30-60s via SSH)      → rounds + player_comprehensive_stats
  3. Endstats    (~30-60s via SSH)      → round_awards + round_vs_stats
  4. Gametime    (fallback for webhook) → lua_round_teams

This service is called from each insertion point and maintains a
round_correlations row that tracks which pieces have arrived.

Starts in DRY-RUN mode (logging only, no DB writes). Set dry_run=False
to enable actual DB writes after verification.
"""

import logging
from datetime import datetime

logger = logging.getLogger('RoundCorrelation')


class RoundCorrelationService:
    """Tracks data arrival and completeness for R1+R2 match pairs."""

    def __init__(self, db_adapter, dry_run: bool = True):
        self.db = db_adapter
        self.dry_run = dry_run
        mode = "DRY-RUN" if dry_run else "LIVE"
        logger.info(f"[CORRELATION] Service initialized ({mode} mode)")

    async def on_round_imported(self, match_id: str, round_number: int,
                                round_id: int, map_name: str):
        """Called after rounds INSERT in postgresql_database_manager.py or ultimate_bot.py."""
        if round_number not in (0, 1, 2):
            return

        if round_number == 0:
            # Match summary - just link it if correlation exists
            logger.info(
                f"[CORRELATION] {map_name} match_id={match_id}: "
                f"summary (round_number=0) arrived, round_id={round_id}"
            )
            if self.dry_run:
                return
            await self._link_summary(match_id, round_id)
            return

        r_label = f"R{round_number}"
        logger.info(
            f"[CORRELATION] {map_name} match_id={match_id}: "
            f"{r_label} stats arrived, round_id={round_id}"
        )

        if self.dry_run:
            return

        correlation_id = f"{match_id}:{map_name}"
        flag_col = f"has_r{round_number}_stats"
        id_col = f"r{round_number}_round_id"
        arrived_col = f"r{round_number}_arrived_at"

        await self._upsert_correlation(
            correlation_id=correlation_id,
            match_id=match_id,
            map_name=map_name,
            updates={
                flag_col: True,
                id_col: round_id,
                arrived_col: datetime.now(),
            },
        )

    async def on_lua_teams_stored(self, match_id: str, round_number: int,
                                  lua_teams_id: int, map_name: str):
        """Called after lua_round_teams INSERT in ultimate_bot.py."""
        if round_number not in (1, 2):
            return

        r_label = f"R{round_number}"
        logger.info(
            f"[CORRELATION] {map_name} match_id={match_id}: "
            f"{r_label} lua_teams arrived, lua_teams_id={lua_teams_id}"
        )

        if self.dry_run:
            return

        correlation_id = f"{match_id}:{map_name}"
        flag_col = f"has_r{round_number}_lua_teams"
        id_col = f"r{round_number}_lua_teams_id"

        await self._upsert_correlation(
            correlation_id=correlation_id,
            match_id=match_id,
            map_name=map_name,
            updates={
                flag_col: True,
                id_col: lua_teams_id,
            },
        )

    async def on_gametime_processed(self, match_id: str, round_number: int,
                                    map_name: str):
        """Called after gametime file processing in ultimate_bot.py."""
        if round_number not in (1, 2):
            return

        r_label = f"R{round_number}"
        logger.info(
            f"[CORRELATION] {map_name} match_id={match_id}: "
            f"{r_label} gametime arrived"
        )

        if self.dry_run:
            return

        correlation_id = f"{match_id}:{map_name}"
        flag_col = f"has_r{round_number}_gametime"

        await self._upsert_correlation(
            correlation_id=correlation_id,
            match_id=match_id,
            map_name=map_name,
            updates={flag_col: True},
        )

    async def on_endstats_processed(self, match_id: str, round_number: int,
                                    map_name: str):
        """Called after successful endstats store in ultimate_bot.py."""
        if round_number not in (1, 2):
            return

        r_label = f"R{round_number}"
        logger.info(
            f"[CORRELATION] {map_name} match_id={match_id}: "
            f"{r_label} endstats arrived"
        )

        if self.dry_run:
            return

        correlation_id = f"{match_id}:{map_name}"
        flag_col = f"has_r{round_number}_endstats"

        await self._upsert_correlation(
            correlation_id=correlation_id,
            match_id=match_id,
            map_name=map_name,
            updates={flag_col: True},
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _upsert_correlation(self, correlation_id: str, match_id: str,
                                  map_name: str, updates: dict):
        """Create or update a correlation row, then recalculate completeness."""
        try:
            # Ensure row exists
            await self.db.execute(
                """
                INSERT INTO round_correlations (correlation_id, match_id, map_name)
                VALUES ($1, $2, $3)
                ON CONFLICT (correlation_id) DO NOTHING
                """,
                (correlation_id, match_id, map_name),
            )

            # Apply updates
            set_clauses = []
            params = []
            idx = 1
            for col, val in updates.items():
                set_clauses.append(f"{col} = ${idx}")
                params.append(val)
                idx += 1
            params.append(correlation_id)

            if set_clauses:
                sql = (
                    f"UPDATE round_correlations SET {', '.join(set_clauses)} "
                    f"WHERE correlation_id = ${idx}"
                )
                await self.db.execute(sql, tuple(params))

            # Recalculate completeness
            await self._recalculate_completeness(correlation_id)

        except Exception as e:
            logger.warning(f"[CORRELATION] Error upserting {correlation_id}: {e}")

    async def _recalculate_completeness(self, correlation_id: str):
        """Update status and completeness_pct based on current flags."""
        try:
            row = await self.db.fetch_one(
                """
                SELECT has_r1_stats, has_r2_stats,
                       has_r1_lua_teams, has_r2_lua_teams,
                       has_r1_gametime, has_r2_gametime,
                       has_r1_endstats, has_r2_endstats
                FROM round_correlations
                WHERE correlation_id = $1
                """,
                (correlation_id,),
            )
            if not row:
                return

            (has_r1_stats, has_r2_stats,
             has_r1_lua, has_r2_lua,
             has_r1_gt, has_r2_gt,
             has_r1_es, has_r2_es) = row

            # Core completeness: R1 stats (25%) + R2 stats (25%) = 50% for "complete"
            # Bonus: lua (10% each), gametime (5% each), endstats (10% each) = up to 50% bonus
            pct = 0
            if has_r1_stats:
                pct += 25
            if has_r2_stats:
                pct += 25
            if has_r1_lua:
                pct += 10
            if has_r2_lua:
                pct += 10
            if has_r1_gt:
                pct += 5
            if has_r2_gt:
                pct += 5
            if has_r1_es:
                pct += 10
            if has_r2_es:
                pct += 10

            # Status determination
            if has_r1_stats and has_r2_stats:
                status = 'complete'
                completed_at = datetime.now()
            elif has_r1_stats or has_r2_stats:
                status = 'partial'
                completed_at = None
            else:
                status = 'pending'
                completed_at = None

            if completed_at:
                await self.db.execute(
                    """
                    UPDATE round_correlations
                    SET status = $1, completeness_pct = $2, completed_at = $3
                    WHERE correlation_id = $4
                    """,
                    (status, pct, completed_at, correlation_id),
                )
            else:
                await self.db.execute(
                    """
                    UPDATE round_correlations
                    SET status = $1, completeness_pct = $2
                    WHERE correlation_id = $3
                    """,
                    (status, pct, correlation_id),
                )

            logger.info(
                f"[CORRELATION] {correlation_id}: "
                f"status={status}, completeness={pct}%"
            )

        except Exception as e:
            logger.warning(
                f"[CORRELATION] Error recalculating {correlation_id}: {e}"
            )

    async def _link_summary(self, match_id: str, round_id: int):
        """Link a match summary (round_number=0) to its correlation row."""
        try:
            await self.db.execute(
                """
                UPDATE round_correlations
                SET summary_round_id = $1
                WHERE match_id = $2
                """,
                (round_id, match_id),
            )
        except Exception as e:
            logger.warning(
                f"[CORRELATION] Error linking summary for {match_id}: {e}"
            )

    async def get_status_summary(self) -> dict:
        """Return counts by status for the admin command."""
        try:
            rows = await self.db.fetch_all(
                """
                SELECT status, COUNT(*) as cnt
                FROM round_correlations
                GROUP BY status
                ORDER BY status
                """
            )
            summary = {r[0]: r[1] for r in rows}

            recent = await self.db.fetch_all(
                """
                SELECT correlation_id, match_id, map_name, status,
                       completeness_pct, created_at
                FROM round_correlations
                ORDER BY created_at DESC
                LIMIT 10
                """
            )

            return {
                'counts': summary,
                'total': sum(summary.values()),
                'recent': recent,
                'dry_run': self.dry_run,
            }
        except Exception as e:
            logger.error(f"[CORRELATION] Error getting status: {e}")
            return {'counts': {}, 'total': 0, 'recent': [], 'dry_run': self.dry_run}
