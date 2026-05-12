"""StorytellingService mixin: KIS server-side SQL shadow path (Audit A5, Phase 1).

This module adds a *shadow* SQL-only re-implementation of `_score_kill` /
`compute_session_kis`. The Python path remains authoritative; the shadow
path runs alongside, computes the same KIS impact in a single SQL query,
and writes the top-N worst per-kill deltas to `storytelling_kis_shadow_audit`
for human review.

Phase 2 (cutover) replaces the Python path with the SQL path once the
user has approved the audited divergence band. Until then this code is
behind an env feature flag (`KIS_SHADOW_MODE_ENABLED`, default off).

--------------------------------------------------------------------------
Which multipliers move to SQL (full re-implementation in this module):

- carrier_multiplier         (carrier kill detect + chain window check)
- push_multiplier            (quality-gated, tightest matching push)
- crossfire_multiplier       (±3s window around any crossfire event)
- spawn_multiplier           (best score across matching spawn_timing rows)
- reinf_multiplier           (graduated tier lookup via CASE)
- outcome_multiplier         (gibbed / revived / tapped out)
- class_multiplier           (CLASS_WEIGHTS lookup, joined on first
                              proximity_reaction_metric row per victim/round)
- distance_multiplier        (constant 1.0 — same as Python path)
- health_multiplier          (LOW_HEALTH_MULTIPLIER if killer_health < 30)
- alive_multiplier           (solo clutch / outnumbered)
- soft cap                   (linear 25% compression above 5.0)

Which multipliers stay Python-only / Python-joined:
- None. Every multiplier is reproduced in SQL. The shadow path is a
  full re-implementation. If a divergence shows up it is either:
    (a) rounding (banker's vs half-away-from-zero), or
    (b) a contract drift in the Python code that the SQL didn't follow.
  Both surface as a row in `storytelling_kis_shadow_audit`.

--------------------------------------------------------------------------
Rounding strategy:

Python uses banker's rounding (`round(2.125, 2)` == 2.12) while PostgreSQL
`ROUND(numeric, 2)` uses half-away-from-zero (== 2.13). Replicating
banker's rounding exactly in SQL is possible but verbose and slower than
the eventual cutover query would tolerate. Instead, this module:

  - Computes `total_impact` in SQL using NUMERIC arithmetic with
    `ROUND(x::numeric, 2)` (half-away-from-zero) to match the eventual
    production-cutover behavior.
  - Surfaces every divergent row in the audit. The user reviews the
    distribution histogram and decides whether ±0.01 tolerance is
    acceptable.

This is intentional: the *purpose* of Phase 1 is exactly to expose this
rounding-band so the user can make an informed cutover decision.
"""
from __future__ import annotations

import os

from .base import (
    CARRIER_CHAIN_MULTIPLIER,
    CARRIER_KILL_MULTIPLIER,
    CARRIER_RETURN_WINDOW_MS,
    CROSSFIRE_MULTIPLIER,
    CROSSFIRE_TIMING_WINDOW_MS,
    DISTANCE_NORMAL,
    LOW_HEALTH_MULTIPLIER,
    LOW_HEALTH_THRESHOLD,
    OUTCOME_GIBBED,
    OUTCOME_REVIVED,
    OUTNUMBERED_MULTIPLIER,
    PUSH_BUFFER_MS,
    PUSH_QUALITY_THRESHOLD,
    SOLO_CLUTCH_MULTIPLIER,
    SOLO_CLUTCH_THRESHOLD,
    SPAWN_TIMING_WINDOW_MS,
    _to_date,
    date,
    logger,
)

# Audit storage knobs. Centralised so tests can override via monkeypatch.
SHADOW_AUDIT_TOP_N = 20            # worst deltas to persist per session
SHADOW_AUDIT_DELTA_FLOOR = 0.005   # ignore deltas below this — they round to 0


def _shadow_mode_enabled() -> bool:
    """Phase 1 feature flag. Default off so production code path is unchanged."""
    return os.environ.get("KIS_SHADOW_MODE_ENABLED", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


# ---------------------------------------------------------------------------
# SQL re-implementation of _score_kill
# ---------------------------------------------------------------------------
#
# Built as one query against `proximity_kill_outcome ko` plus LATERAL
# joins/aggregations for each context. Parameters are passed positionally
# so the asyncpg-style adapter ($1 binding) works unchanged.
#
# Constants are interpolated as literals because they are module-level
# Python floats — never user input. Inline values keep the EXPLAIN plan
# readable and avoid parameter-count bloat.

def _build_shadow_kis_query() -> str:
    """Compose the shadow KIS SQL query, embedding tunable constants."""
    return f"""
    WITH ck AS (
        -- carrier kill keyed by (killer_guid, round_start_unix, round_number, kill_time)
        SELECT killer_guid, round_start_unix, round_number, kill_time
        FROM proximity_carrier_kill
        WHERE session_date = $1
    ),
    cr AS (
        -- carrier return events keyed by round
        SELECT round_start_unix, round_number, return_time
        FROM proximity_carrier_return
        WHERE session_date = $1
    ),
    pu AS (
        SELECT round_start_unix, round_number, start_time, end_time,
               COALESCE(push_quality, 0)::numeric AS push_quality,
               COALESCE(toward_objective, '') AS toward_objective
        FROM proximity_team_push
        WHERE session_date = $1
    ),
    cf AS (
        SELECT round_start_unix, round_number, event_time
        FROM proximity_crossfire_opportunity
        WHERE was_executed = TRUE AND session_date = $1
    ),
    st AS (
        SELECT id, killer_guid, round_start_unix, round_number, kill_time,
               COALESCE(spawn_timing_score, 0.5)::numeric AS score,
               COALESCE(victim_reinf, 0)::numeric AS victim_reinf
        FROM proximity_spawn_timing
        WHERE session_date = $1
    ),
    vc AS (
        -- victim class: keep first row per (target_guid, round_start_unix, round_number)
        SELECT DISTINCT ON (target_guid, round_start_unix, round_number)
               target_guid, round_start_unix, round_number,
               COALESCE(UPPER(target_class), '') AS target_class
        FROM proximity_reaction_metric
        WHERE session_date = $1
        ORDER BY target_guid, round_start_unix, round_number, id
    ),
    cp AS (
        -- Dedup to one row per (attacker_guid, round_start_unix, round_number,
        -- event_time) — the join key — so a kill outcome cannot fan out into
        -- multiple shadow rows when the same attacker has duplicate position
        -- entries at the same timestamp. Stable selection via row id.
        SELECT DISTINCT ON (attacker_guid, round_start_unix, round_number, event_time)
               attacker_guid, round_start_unix, round_number, event_time,
               COALESCE(killer_health, 0)::int AS killer_health,
               COALESCE(axis_alive, 0)::int AS axis_alive,
               COALESCE(allies_alive, 0)::int AS allies_alive,
               COALESCE(UPPER(attacker_team), '') AS attacker_team
        FROM proximity_combat_position
        WHERE session_date = $1 AND event_type = 'kill'
        ORDER BY attacker_guid, round_start_unix, round_number, event_time, id
    )
    SELECT
        ko.id AS kill_outcome_id,

        -- carrier_mult
        CASE
            WHEN ck_match.kill_time IS NOT NULL THEN
                CASE
                    WHEN cr_chain.return_time IS NOT NULL THEN {CARRIER_CHAIN_MULTIPLIER}::numeric
                    ELSE {CARRIER_KILL_MULTIPLIER}::numeric
                END
            ELSE 1.0::numeric
        END AS carrier_mult,

        -- push_mult: 1.0 + min(best_pq * 0.5, 1.0); skip pushes failing quality / excluded objective
        COALESCE(
            (
                SELECT 1.0::numeric + LEAST(MAX(pu.push_quality) * 0.5, 1.0::numeric)
                FROM pu
                WHERE pu.round_start_unix = ko.round_start_unix
                  AND pu.round_number = ko.round_number
                  AND ko.kill_time BETWEEN pu.start_time AND pu.end_time + {PUSH_BUFFER_MS}
                  AND pu.push_quality >= {PUSH_QUALITY_THRESHOLD}::numeric
                  AND pu.toward_objective NOT IN ('NO', 'N/A', '')
            ),
            1.0::numeric
        ) AS push_mult,

        -- crossfire_mult: any cf event within ±CROSSFIRE_TIMING_WINDOW_MS
        CASE
            WHEN EXISTS (
                SELECT 1 FROM cf
                WHERE cf.round_start_unix = ko.round_start_unix
                  AND cf.round_number = ko.round_number
                  AND ABS(cf.event_time - ko.kill_time) <= {CROSSFIRE_TIMING_WINDOW_MS}
            ) THEN {CROSSFIRE_MULTIPLIER}::numeric
            ELSE 1.0::numeric
        END AS crossfire_mult,

        -- spawn_mult: 1.0 + best matching score
        COALESCE(
            (
                SELECT 1.0::numeric + MAX(st.score)
                FROM st
                WHERE st.round_start_unix = ko.round_start_unix
                  AND st.round_number = ko.round_number
                  AND st.killer_guid = ko.killer_guid
                  AND ABS(st.kill_time - ko.kill_time) <= {SPAWN_TIMING_WINDOW_MS}
            ),
            1.0::numeric
        ) AS spawn_mult,

        -- reinf_mult: graduated tier lookup using first matching st row by kill_time
        COALESCE(
            (
                SELECT
                    CASE
                        WHEN st.victim_reinf <= 2.0  THEN 0.70::numeric
                        WHEN st.victim_reinf <= 5.0  THEN 0.85::numeric
                        WHEN st.victim_reinf <= 10.0 THEN 1.00::numeric
                        WHEN st.victim_reinf <= 15.0 THEN 1.10::numeric
                        WHEN st.victim_reinf <= 20.0 THEN 1.20::numeric
                        WHEN st.victim_reinf <= 25.0 THEN 1.30::numeric
                        ELSE 1.40::numeric
                    END
                FROM st
                WHERE st.round_start_unix = ko.round_start_unix
                  AND st.round_number = ko.round_number
                  AND st.killer_guid = ko.killer_guid
                  AND ABS(st.kill_time - ko.kill_time) <= {SPAWN_TIMING_WINDOW_MS}
                -- Deterministic match: closest spawn-timing by time delta,
                -- then by row id for stability. Python "first match" is
                -- iteration-order from an unsorted load; surfacing any
                -- ordering divergence in the audit is the point of shadow.
                ORDER BY ABS(st.kill_time - ko.kill_time), st.id
                LIMIT 1
            ),
            1.0::numeric
        ) AS reinf_mult,

        -- outcome_mult
        CASE
            WHEN COALESCE(ko.outcome, 'tapped_out') = 'gibbed' THEN {OUTCOME_GIBBED}::numeric
            WHEN COALESCE(ko.outcome, 'tapped_out') = 'revived' THEN {OUTCOME_REVIVED}::numeric
            ELSE 1.0::numeric
        END AS outcome_mult,

        -- class_mult: lookup against CLASS_WEIGHTS
        COALESCE(
            CASE vc.target_class
                WHEN 'MEDIC'     THEN 1.5::numeric
                WHEN 'ENGINEER'  THEN 1.3::numeric
                WHEN 'FIELDOPS'  THEN 1.1::numeric
                WHEN 'SOLDIER'   THEN 1.0::numeric
                WHEN 'COVERTOPS' THEN 1.0::numeric
                ELSE 1.0::numeric
            END,
            1.0::numeric
        ) AS class_mult,

        -- distance_mult: constant for now (matches Python path)
        {DISTANCE_NORMAL}::numeric AS distance_mult,

        -- health_mult: low-HP clutch bonus
        CASE
            WHEN cp.killer_health > 0 AND cp.killer_health < {LOW_HEALTH_THRESHOLD}
                THEN {LOW_HEALTH_MULTIPLIER}::numeric
            ELSE 1.0::numeric
        END AS health_mult,

        -- alive_mult: solo clutch / outnumbered. Matches Python's dynamic threshold.
        CASE
            WHEN cp.attacker_team IS NULL THEN 1.0::numeric
            ELSE
                CASE
                    -- compute my_alive / enemy_alive based on attacker team
                    WHEN cp.attacker_team IN ('AXIS', '1') THEN
                        CASE
                            WHEN cp.axis_alive = 1 AND cp.allies_alive >= {SOLO_CLUTCH_THRESHOLD}
                                THEN {SOLO_CLUTCH_MULTIPLIER}::numeric
                            WHEN cp.axis_alive > 0
                                 AND (cp.allies_alive - cp.axis_alive)
                                     >= GREATEST(
                                         1,
                                         CASE WHEN (cp.axis_alive + cp.allies_alive) > 0
                                              THEN (cp.axis_alive + cp.allies_alive) / 3
                                              ELSE 2 END
                                     )
                                THEN {OUTNUMBERED_MULTIPLIER}::numeric
                            ELSE 1.0::numeric
                        END
                    ELSE
                        CASE
                            WHEN cp.allies_alive = 1 AND cp.axis_alive >= {SOLO_CLUTCH_THRESHOLD}
                                THEN {SOLO_CLUTCH_MULTIPLIER}::numeric
                            WHEN cp.allies_alive > 0
                                 AND (cp.axis_alive - cp.allies_alive)
                                     >= GREATEST(
                                         1,
                                         CASE WHEN (cp.axis_alive + cp.allies_alive) > 0
                                              THEN (cp.axis_alive + cp.allies_alive) / 3
                                              ELSE 2 END
                                     )
                                THEN {OUTNUMBERED_MULTIPLIER}::numeric
                            ELSE 1.0::numeric
                        END
                END
        END AS alive_mult
    FROM proximity_kill_outcome ko
    LEFT JOIN LATERAL (
        SELECT ck.kill_time
        FROM ck
        WHERE ck.killer_guid = ko.killer_guid
          AND ck.round_start_unix = ko.round_start_unix
          AND ck.round_number = ko.round_number
          AND ck.kill_time = ko.kill_time
        LIMIT 1
    ) ck_match ON TRUE
    LEFT JOIN LATERAL (
        SELECT cr.return_time
        FROM cr
        WHERE cr.round_start_unix = ko.round_start_unix
          AND cr.round_number = ko.round_number
          AND ck_match.kill_time IS NOT NULL
          AND (cr.return_time - ko.kill_time) > 0
          AND (cr.return_time - ko.kill_time) <= {CARRIER_RETURN_WINDOW_MS}
        ORDER BY cr.return_time
        LIMIT 1
    ) cr_chain ON TRUE
    LEFT JOIN vc
        ON vc.target_guid = ko.victim_guid
       AND vc.round_start_unix = ko.round_start_unix
       AND vc.round_number = ko.round_number
    LEFT JOIN cp
        ON cp.attacker_guid = ko.killer_guid
       AND cp.round_start_unix = ko.round_start_unix
       AND cp.round_number = ko.round_number
       AND cp.event_time = ko.kill_time
    WHERE ko.session_date = $1
    ORDER BY ko.round_start_unix, ko.kill_time
    """


def _apply_soft_cap_and_round(raw: float) -> float:
    """Mirror of Python's soft-cap + rounding at the end of _score_kill.

    Used by `compute_kis_session_sql_shadow` when the SQL adapter returns
    the raw multipliers; we apply the cap in Python so the SQL doesn't
    have to special-case the `<= 5.0` branch in NUMERIC.
    """
    capped = raw if raw <= 5.0 else 5.0 + (raw - 5.0) * 0.25
    return round(capped, 2)


class _KisShadowMixin:
    """Shadow audit methods for the KIS jsonb_agg cutover (A5 Phase 1)."""

    async def compute_kis_session_sql_shadow(self, sd: str | date) -> list[dict]:
        """Run the SQL-only KIS computation. Returns one dict per kill.

        Does NOT write to `storytelling_kill_impact`. Pure read.

        Each row: {
            "kill_outcome_id": int,
            "total_impact": float (rounded, capped),
            "multipliers": {carrier, push, crossfire, spawn, reinf,
                            outcome, class, distance, health, alive}
        }
        """
        sd = _to_date(sd)
        rows = await self.db.fetch_all(_build_shadow_kis_query(), (sd,))
        if not rows:
            return []

        results: list[dict] = []
        for r in rows:
            (
                ko_id,
                carrier_mult,
                push_mult,
                crossfire_mult,
                spawn_mult,
                reinf_mult,
                outcome_mult,
                class_mult,
                distance_mult,
                health_mult,
                alive_mult,
            ) = (float(v) if v is not None else 1.0 for v in r)
            ko_id = int(r[0])

            raw = (
                1.0 * carrier_mult * push_mult * crossfire_mult
                * spawn_mult * outcome_mult * class_mult * distance_mult
                * health_mult * alive_mult * reinf_mult
            )
            total = _apply_soft_cap_and_round(raw)
            results.append({
                "kill_outcome_id": ko_id,
                "total_impact": total,
                "multipliers": {
                    "carrier": carrier_mult,
                    "push": push_mult,
                    "crossfire": crossfire_mult,
                    "spawn": spawn_mult,
                    "reinf": reinf_mult,
                    "outcome": outcome_mult,
                    "class": class_mult,
                    "distance": distance_mult,
                    "health": health_mult,
                    "alive": alive_mult,
                },
            })
        return results

    async def kis_compute_with_shadow(self, sd: str | date, force: bool = False) -> dict:
        """Run the production Python KIS path, then (if shadow enabled) run the
        SQL re-implementation and log per-kill deltas.

        Returns the same summary dict as `compute_session_kis`, with an
        added `shadow` block when shadow mode is enabled.
        """
        # Always execute the production path. It is authoritative.
        prod_summary = await self.compute_session_kis(sd, force=force)

        if not _shadow_mode_enabled():
            return prod_summary

        try:
            shadow_summary = await self._run_kis_shadow_audit(sd)
            prod_summary = {**prod_summary, "shadow": shadow_summary}
        except Exception as exc:
            logger.error("KIS shadow audit failed for %s: %s", sd, exc, exc_info=True)
            prod_summary = {**prod_summary, "shadow": {"status": "error", "error": str(exc)}}

        return prod_summary

    async def _run_kis_shadow_audit(self, sd: str | date) -> dict:
        """Compute deltas, persist top-N worst rows, return histogram summary."""
        sd_date = _to_date(sd)

        sql_rows = await self.compute_kis_session_sql_shadow(sd_date)
        if not sql_rows:
            return {"status": "no_data", "compared": 0}

        py_rows = await self.db.fetch_all(
            "SELECT kill_outcome_id, total_impact "
            "FROM storytelling_kill_impact "
            "WHERE session_date = $1",
            (sd_date,),
        )
        py_by_id = {int(r[0]): float(r[1]) for r in (py_rows or []) if r[0] is not None}

        # Build delta records joined on kill_outcome_id.
        deltas: list[tuple[int, float, float, float]] = []  # (id, py, sql, delta)
        for srow in sql_rows:
            ko_id = srow["kill_outcome_id"]
            py_impact = py_by_id.get(ko_id)
            if py_impact is None:
                continue  # python path didn't score this kill — different surface
            sql_impact = srow["total_impact"]
            delta = sql_impact - py_impact
            deltas.append((ko_id, py_impact, sql_impact, delta))

        if not deltas:
            return {"status": "no_overlap", "compared": 0}

        # Distribution histogram (absolute deltas)
        buckets = {"<0.005": 0, "0.005-0.01": 0, "0.01-0.05": 0, ">0.05": 0}
        abs_deltas: list[float] = []
        worst = 0.0
        delta_sum = 0.0
        divergent = 0
        for _ko_id, _py, _sql, d in deltas:
            ad = abs(d)
            abs_deltas.append(ad)
            delta_sum += d
            if ad > worst:
                worst = ad
            if ad >= SHADOW_AUDIT_DELTA_FLOOR:
                divergent += 1
            if ad < 0.005:
                buckets["<0.005"] += 1
            elif ad < 0.01:
                buckets["0.005-0.01"] += 1
            elif ad < 0.05:
                buckets["0.01-0.05"] += 1
            else:
                buckets[">0.05"] += 1

        # Persist top-N worst rows for human review.
        deltas.sort(key=lambda t: abs(t[3]), reverse=True)
        top_n = [d for d in deltas if abs(d[3]) >= SHADOW_AUDIT_DELTA_FLOOR][:SHADOW_AUDIT_TOP_N]

        # Always clear prior audit rows for this session so a clean rerun
        # (zero divergences) doesn't leave stale rows from an earlier run
        # surfacing through the diagnostics endpoint.
        await self.db.execute(
            "DELETE FROM storytelling_kis_shadow_audit WHERE session_date = $1",
            (sd_date,),
        )
        if top_n:
            batch = [(sd_date, ko_id, py, sql_, d) for (ko_id, py, sql_, d) in top_n]
            await self.db.executemany(
                "INSERT INTO storytelling_kis_shadow_audit "
                "(session_date, kill_outcome_id, python_impact, sql_impact, delta) "
                "VALUES ($1, $2, $3, $4, $5)",
                batch,
            )

        compared = len(deltas)
        mean_delta = delta_sum / compared if compared else 0.0
        min_abs = min(abs_deltas) if abs_deltas else 0.0
        max_abs = max(abs_deltas) if abs_deltas else 0.0

        logger.info(
            "KIS shadow audit for %s: compared=%d divergent=%d worst=%.4f mean_signed=%.6f hist=%s",
            sd_date, compared, divergent, worst, mean_delta, buckets,
        )

        return {
            "status": "ok",
            "compared": compared,
            "divergent": divergent,
            "min_abs_delta": min_abs,
            "max_abs_delta": max_abs,
            "mean_signed_delta": mean_delta,
            "histogram": buckets,
            "persisted_rows": len(top_n),
        }
