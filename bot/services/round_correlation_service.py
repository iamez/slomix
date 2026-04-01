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

Mode is config-driven:
- `dry_run=True` logs only (no DB writes)
- `dry_run=False` requests live writes, gated by schema preflight and
  automatic rollback guardrails
"""

import logging
from datetime import datetime

logger = logging.getLogger('RoundCorrelation')


class RoundCorrelationService:
    """Tracks data arrival and completeness for R1+R2 match pairs."""

    REQUIRED_COLUMNS = {
        "correlation_id",
        "match_id",
        "map_name",
        "r1_round_id",
        "r2_round_id",
        "summary_round_id",
        "r1_lua_teams_id",
        "r2_lua_teams_id",
        "has_r1_stats",
        "has_r2_stats",
        "has_r1_lua_teams",
        "has_r2_lua_teams",
        "has_r1_gametime",
        "has_r2_gametime",
        "has_r1_endstats",
        "has_r2_endstats",
        "status",
        "completeness_pct",
        "r1_arrived_at",
        "r2_arrived_at",
        "completed_at",
        "created_at",
    }

    def __init__(
        self,
        db_adapter,
        dry_run: bool = True,
        *,
        require_schema_check: bool = True,
        write_error_threshold: int = 5,
    ):
        self.db = db_adapter
        self.dry_run = dry_run
        self.live_requested = not dry_run
        self.require_schema_check = require_schema_check
        self.write_error_threshold = max(1, int(write_error_threshold or 1))
        self.write_error_count = 0
        self.preflight_checked = False
        self.preflight_ok = False
        self.guardrail_reason = None
        self._initialized = False

        mode = "DRY-RUN" if dry_run else "LIVE_REQUESTED"
        logger.info(
            f"[CORRELATION] Service initialized ({mode}, "
            f"schema_check={self.require_schema_check}, "
            f"write_error_threshold={self.write_error_threshold})"
        )

    async def initialize(self):
        """
        Initialize live-write guardrails once the DB is connected.
        Safe to call multiple times.
        """
        if self._initialized:
            return
        self._initialized = True

        if self.dry_run:
            logger.info("[CORRELATION] Running in dry-run mode by configuration")
            return

        if not self.require_schema_check:
            self.preflight_ok = True
            logger.warning(
                "[CORRELATION] LIVE mode enabled without schema preflight "
                "(CORRELATION_REQUIRE_SCHEMA_CHECK=false)"
            )
            return

        ok, reason = await self._run_schema_preflight()
        self.preflight_checked = True
        self.preflight_ok = ok
        if not ok:
            self._enter_dry_run(reason)
            return

        logger.info("[CORRELATION] LIVE mode enabled (schema preflight passed)")

    async def _run_schema_preflight(self):
        try:
            rows = await self.db.fetch_all(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'round_correlations'
                """
            )
        except Exception as e:
            logger.error("Schema preflight query failed: %s", e, exc_info=True)
            return False, f"schema_preflight_query_failed:{type(e).__name__}"

        if not rows:
            return False, "schema_preflight_table_missing:round_correlations"

        available = {str(row[0]) for row in rows}
        missing = sorted(self.REQUIRED_COLUMNS - available)
        if missing:
            missing_text = ",".join(missing[:8])
            if len(missing) > 8:
                missing_text += ",..."
            return False, f"schema_preflight_missing_columns:{missing_text}"
        return True, "ok"

    def _enter_dry_run(self, reason: str):
        reason_text = str(reason or "unknown_guardrail_reason")
        if not self.dry_run or self.guardrail_reason != reason_text:
            logger.warning(
                f"[CORRELATION] Guardrail active -> DRY-RUN mode (reason={reason_text})"
            )
        self.dry_run = True
        self.guardrail_reason = reason_text

    def _record_write_failure(self, context: str, error: Exception):
        self.write_error_count += 1
        logger.warning(
            f"[CORRELATION] Write error {self.write_error_count}/"
            f"{self.write_error_threshold} in {context}: {error}"
        )
        if self.write_error_count >= self.write_error_threshold:
            self._enter_dry_run(
                f"write_error_threshold_reached:{context}"
            )

    def _record_write_success(self):
        if self.write_error_count:
            logger.info("[CORRELATION] Write path recovered; resetting error counter")
        self.write_error_count = 0

    async def _allow_live_write(self) -> bool:
        if self.dry_run:
            return False
        if not self._initialized:
            await self.initialize()
        return not self.dry_run

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
            if not await self._allow_live_write():
                return
            await self._link_summary(match_id, round_id)
            return

        r_label = f"R{round_number}"
        logger.info(
            f"[CORRELATION] {map_name} match_id={match_id}: "
            f"{r_label} stats arrived, round_id={round_id}"
        )

        if not await self._allow_live_write():
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

    async def _find_nearby_correlation_id(self, match_id: str, map_name: str,
                                          round_number: int = 0,
                                          window_seconds: int = 30) -> str | None:
        """Find an existing correlation for the same map to merge into.

        Two merge strategies:
        1. Timestamp proximity (±30s): Lua R1 vs stats match_id differ by 2-3s.
        2. Semantic R2 match (round_number=2): Find the most recent correlation
           for this map that has R1 data but is missing R2 Lua data. This handles
           the R1→R2 gap (100-750s) which exceeds any safe timestamp window.
        """
        try:
            from datetime import datetime as dt_cls
            from datetime import timedelta

            parts = match_id.split('-')
            if len(parts) < 4:
                return None
            ts_str = '-'.join(parts[:3]) + ' ' + parts[3]
            try:
                target_dt = dt_cls.strptime(ts_str, "%Y-%m-%d %H%M%S")
            except ValueError:
                return None

            # Strategy 1: Timestamp proximity (works for R1 Lua vs stats, ~2-3s diff)
            rows = await self.db.fetch_all(
                """SELECT correlation_id, match_id, r1_round_id
                   FROM round_correlations
                   WHERE map_name = ?
                   ORDER BY created_at DESC
                   LIMIT 20""",
                (map_name,),
            )
            best_id = None
            best_diff = timedelta(seconds=window_seconds + 1)
            for row in (rows or []):
                cid = row[0] if isinstance(row, (list, tuple)) else row.get('correlation_id')
                mid = row[1] if isinstance(row, (list, tuple)) else row.get('match_id')
                has_round = row[2] if isinstance(row, (list, tuple)) else row.get('r1_round_id')
                if mid == match_id:
                    return None  # Exact match already exists
                try:
                    cparts = mid.split('-')
                    cts = '-'.join(cparts[:3]) + ' ' + cparts[3]
                    candidate_dt = dt_cls.strptime(cts, "%Y-%m-%d %H%M%S")
                except (ValueError, IndexError):
                    continue
                diff = abs(candidate_dt - target_dt)
                if diff <= timedelta(seconds=window_seconds) and diff < best_diff:
                    if has_round or best_id is None:
                        best_diff = diff
                        best_id = cid

            if best_id:
                logger.info(
                    "[CORRELATION] Merging %s:%s into existing %s (diff=%ds, strategy=timestamp)",
                    match_id, map_name, best_id, int(best_diff.total_seconds()),
                )
                return best_id

            # Strategy 2: Semantic R2 merge — find the most recent correlation
            # that has R1 data but no R2 Lua data yet. Only applies when round_number=2.
            if round_number == 2:
                r2_rows = await self.db.fetch_all(
                    """SELECT correlation_id, match_id, r1_round_id
                       FROM round_correlations
                       WHERE map_name = ?
                         AND (has_r1_stats = TRUE OR r1_round_id IS NOT NULL)
                         AND has_r2_lua_teams = FALSE
                       ORDER BY created_at DESC
                       LIMIT 5""",
                    (map_name,),
                )
                for row in (r2_rows or []):
                    cid = row[0] if isinstance(row, (list, tuple)) else row.get('correlation_id')
                    mid = row[1] if isinstance(row, (list, tuple)) else row.get('match_id')
                    if mid == match_id:
                        return None
                    try:
                        cparts = mid.split('-')
                        cts = '-'.join(cparts[:3]) + ' ' + cparts[3]
                        candidate_dt = dt_cls.strptime(cts, "%Y-%m-%d %H%M%S")
                    except (ValueError, IndexError):
                        continue
                    diff = target_dt - candidate_dt  # R2 is always AFTER R1
                    # R2 must be 30s-900s after R1 (halftime + round duration)
                    if timedelta(seconds=30) <= diff <= timedelta(seconds=900):
                        logger.info(
                            "[CORRELATION] Merging R2 %s:%s into %s (diff=%ds, strategy=semantic_r2)",
                            match_id, map_name, cid, int(diff.total_seconds()),
                        )
                        return cid

            return None
        except Exception as e:
            logger.debug(f"[CORRELATION] Nearby search failed: {e}")
            return None

    def _resolve_correlation_id(self, match_id: str, map_name: str,
                                existing_cid: str | None) -> tuple[str, str]:
        """Return (correlation_id, effective_match_id) using a nearby merge when available."""
        if existing_cid:
            return existing_cid, existing_cid.split(':')[0]
        return f"{match_id}:{map_name}", match_id

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

        if not await self._allow_live_write():
            return

        existing_cid = await self._find_nearby_correlation_id(match_id, map_name, round_number)
        correlation_id, effective_mid = self._resolve_correlation_id(match_id, map_name, existing_cid)

        await self._upsert_correlation(
            correlation_id=correlation_id,
            match_id=effective_mid,
            map_name=map_name,
            updates={
                f"has_r{round_number}_lua_teams": True,
                f"r{round_number}_lua_teams_id": lua_teams_id,
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

        if not await self._allow_live_write():
            return

        existing_cid = await self._find_nearby_correlation_id(match_id, map_name, round_number)
        correlation_id, effective_mid = self._resolve_correlation_id(match_id, map_name, existing_cid)

        await self._upsert_correlation(
            correlation_id=correlation_id,
            match_id=effective_mid,
            map_name=map_name,
            updates={f"has_r{round_number}_gametime": True},
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

        if not await self._allow_live_write():
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

    # Columns that have FK constraints and need pre-validation
    _FK_COLUMNS = {
        'r1_round_id': ('rounds', 'id'),
        'r2_round_id': ('rounds', 'id'),
        'summary_round_id': ('rounds', 'id'),
        'r1_lua_teams_id': ('lua_round_teams', 'id'),
        'r2_lua_teams_id': ('lua_round_teams', 'id'),
    }

    async def _validate_fk_references(self, updates: dict) -> tuple[dict, dict]:
        """Split updates into safe (validated) and deferred (FK target missing).

        Returns (safe_updates, deferred_updates).
        """
        fk_cols = {k: v for k, v in updates.items() if k in self._FK_COLUMNS}
        if not fk_cols:
            return updates, {}

        safe = dict(updates)
        deferred = {}

        # Pre-built FK existence check queries (no string concat in SQL)
        _FK_CHECK_QUERIES = {
            ("rounds", "id"): "SELECT 1 FROM rounds WHERE id = ?",
            ("lua_round_teams", "id"): "SELECT 1 FROM lua_round_teams WHERE id = ?",
        }
        for col, val in fk_cols.items():
            if val is None:
                continue
            table, pk = self._FK_COLUMNS[col]
            fk_query = _FK_CHECK_QUERIES.get((table, pk))
            if not fk_query:
                logger.warning("FK pre-check: table %s.%s not in whitelist, skipping", table, pk)
                continue
            try:
                exists = await self.db.fetch_one(fk_query, (val,))
            except Exception as e:
                logger.warning(
                    "FK pre-check DB error for %s.%s=%s: %s (treating as deferred)",
                    table, pk, val, e,
                )
                exists = None

            if not exists:
                logger.warning(
                    f"[CORRELATION] FK pre-check: {col}={val} not found in "
                    f"{table}.{pk}, deferring"
                )
                deferred[col] = safe.pop(col)

        return safe, deferred

    async def _upsert_correlation(self, correlation_id: str, match_id: str,
                                  map_name: str, updates: dict):
        """Create or update a correlation row, then recalculate completeness."""
        try:
            # Ensure row exists
            await self.db.execute(
                """
                INSERT INTO round_correlations (correlation_id, match_id, map_name)
                VALUES (?, ?, ?)
                ON CONFLICT (correlation_id) DO NOTHING
                """,
                (correlation_id, match_id, map_name),
            )

            # Validate FK references before UPDATE to avoid FK violations
            # that would roll back the entire UPDATE (including boolean flags)
            safe_updates, deferred = await self._validate_fk_references(updates)

            if deferred:
                logger.warning(
                    f"[CORRELATION] {correlation_id}: deferred FK columns "
                    f"{list(deferred.keys())} (targets not yet in DB)"
                )

            # Apply safe updates (boolean flags + validated FKs)
            set_clauses = []
            params = []
            for col, val in safe_updates.items():
                set_clauses.append(f"{col} = ?")
                params.append(val)
            params.append(correlation_id)

            if set_clauses:
                sql = (
                    f"UPDATE round_correlations SET {', '.join(set_clauses)} "
                    f"WHERE correlation_id = ?"
                )
                await self.db.execute(sql, tuple(params))

            # Recalculate completeness
            await self._recalculate_completeness(correlation_id)
            self._record_write_success()

        except Exception as e:
            self._record_write_failure(f"_upsert_correlation:{correlation_id}", e)
            logger.warning(f"[CORRELATION] Error upserting {correlation_id}: {e}")

    async def _recalculate_completeness(self, correlation_id: str):
        """Update status and completeness_pct based on current flags."""
        row = await self.db.fetch_one(
            """
            SELECT has_r1_stats, has_r2_stats,
                   has_r1_lua_teams, has_r2_lua_teams,
                   has_r1_gametime, has_r2_gametime,
                   has_r1_endstats, has_r2_endstats
            FROM round_correlations
            WHERE correlation_id = ?
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
                SET status = ?, completeness_pct = ?, completed_at = ?
                WHERE correlation_id = ?
                """,
                (status, pct, completed_at, correlation_id),
            )
        else:
            await self.db.execute(
                """
                UPDATE round_correlations
                SET status = ?, completeness_pct = ?
                WHERE correlation_id = ?
                """,
                (status, pct, correlation_id),
            )

        logger.info(
            f"[CORRELATION] {correlation_id}: "
            f"status={status}, completeness={pct}%"
        )

    async def _link_summary(self, match_id: str, round_id: int):
        """Link a match summary (round_number=0) to its correlation row."""
        try:
            await self.db.execute(
                """
                UPDATE round_correlations
                SET summary_round_id = ?
                WHERE match_id = ?
                """,
                (round_id, match_id),
            )
            self._record_write_success()
        except Exception as e:
            self._record_write_failure(f"_link_summary:{match_id}", e)
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
                'live_requested': self.live_requested,
                'guardrail_reason': self.guardrail_reason,
                'write_error_count': self.write_error_count,
                'write_error_threshold': self.write_error_threshold,
                'preflight_checked': self.preflight_checked,
                'preflight_ok': self.preflight_ok,
            }
        except Exception as e:
            logger.error(f"[CORRELATION] Error getting status: {e}")
            return {
                'counts': {},
                'total': 0,
                'recent': [],
                'dry_run': self.dry_run,
                'live_requested': self.live_requested,
                'guardrail_reason': self.guardrail_reason,
                'write_error_count': self.write_error_count,
                'write_error_threshold': self.write_error_threshold,
                'preflight_checked': self.preflight_checked,
                'preflight_ok': self.preflight_ok,
            }
