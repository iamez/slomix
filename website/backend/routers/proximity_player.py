"""Proximity player endpoints: player/{guid}/profile, player/{guid}/radar."""

import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.routers.proximity_helpers import logger

router = APIRouter()


@router.get("/proximity/player/{guid}/profile")
async def get_proximity_player_profile(
    guid: str,
    range_days: int = 90,
    db: DatabaseAdapter = Depends(get_db),
):
    """Aggregated player proximity stats for profile page."""
    since = datetime.now(timezone.utc).replace(tzinfo=None).date() - timedelta(days=max(1, min(range_days, 3650)))
    try:
        # All 7 queries below hit different tables with no ordering
        # dependency. Parallelising them turns 7 × RTT into 1 × RTT
        # — on production (remote DB) this dominates the profile
        # endpoint latency.
        eng_query = """
            SELECT COUNT(*) AS total_engagements,
                   SUM(CASE WHEN outcome = 'escaped' THEN 1 ELSE 0 END) AS escapes,
                   SUM(CASE WHEN outcome = 'killed' THEN 1 ELSE 0 END) AS deaths,
                   ROUND(AVG(duration_ms)::numeric, 0) AS avg_duration,
                   ROUND(AVG(total_damage_taken)::numeric, 0) AS avg_damage_taken,
                   ROUND(AVG(distance_traveled)::numeric, 0) AS avg_distance,
                   SUM(CASE WHEN is_crossfire THEN 1 ELSE 0 END) AS crossfire_count
            FROM combat_engagement
            WHERE target_guid = $1 AND session_date >= $2
        """
        kill_query = """
            SELECT COUNT(*) AS total_kills
            FROM combat_engagement e
            WHERE e.outcome = 'killed'
              AND e.session_date >= $2
              AND EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(COALESCE(e.attackers, '[]'::jsonb)) AS attacker
                    WHERE attacker->>'guid' = $1
                      AND COALESCE((attacker->>'got_kill')::boolean, FALSE)
              )
        """
        spawn_query = """
            SELECT ROUND(AVG(spawn_timing_score)::numeric, 3) AS avg_score,
                   COUNT(*) AS timed_kills,
                   ROUND(AVG(time_to_next_spawn)::numeric, 0) AS avg_denial_ms
            FROM proximity_spawn_timing
            WHERE killer_guid = $1 AND session_date >= $2
        """
        reactions_query = """
            SELECT ROUND(AVG(return_fire_ms)::numeric, 0) AS avg_return_fire,
                   ROUND(AVG(dodge_reaction_ms)::numeric, 0) AS avg_dodge,
                   ROUND(AVG(support_reaction_ms)::numeric, 0) AS avg_support,
                   COUNT(*) AS reaction_samples
            FROM proximity_reaction_metric
            WHERE target_guid = $1 AND session_date >= $2
        """
        movement_query = """
            SELECT ROUND(AVG(avg_speed)::numeric, 1) AS avg_speed,
                   ROUND(AVG(sprint_percentage)::numeric, 1) AS avg_sprint_pct,
                   ROUND(AVG(total_distance)::numeric, 0) AS avg_distance_per_life,
                   COUNT(*) AS tracks
            FROM player_track
            WHERE player_guid = $1 AND session_date >= $2
        """
        trade_query = """
            SELECT COUNT(*) AS trades_made
            FROM proximity_lua_trade_kill
            WHERE trader_guid = $1 AND session_date >= $2
        """
        name_query = "SELECT player_name FROM player_track WHERE player_guid = $1 ORDER BY session_date DESC LIMIT 1"

        (
            eng_stats, kill_stats, spawn_timing,
            reactions, movement, trade_stats, name_row,
        ) = await asyncio.gather(
            db.fetch_one(eng_query, (guid, since)),
            db.fetch_one(kill_query, (guid, since)),
            db.fetch_one(spawn_query, (guid, since)),
            db.fetch_one(reactions_query, (guid, since)),
            db.fetch_one(movement_query, (guid, since)),
            db.fetch_one(trade_query, (guid, since)),
            db.fetch_one(name_query, (guid,)),
        )
        player_name = name_row[0] if name_row else guid

        # Flat response matching frontend ProfileData interface
        return {
            "player_name": player_name,
            "guid": guid,
            "total_engagements": int(eng_stats[0] or 0) if eng_stats else 0,
            "escapes": int(eng_stats[1] or 0) if eng_stats else 0,
            "deaths": int(eng_stats[2] or 0) if eng_stats else 0,
            "escape_rate": round(int(eng_stats[1] or 0) / max(int(eng_stats[0] or 0), 1) * 100, 1) if eng_stats else 0,
            "avg_duration_ms": int(eng_stats[3] or 0) if eng_stats else 0,
            "total_kills": int(kill_stats[0] or 0) if kill_stats else 0,
            "crossfire_count": int(eng_stats[6] or 0) if eng_stats else 0,
            "avg_speed": float(movement[0] or 0) if movement else 0,
            "sprint_pct": float(movement[1] or 0) if movement else 0,
            "avg_distance_per_life": int(movement[2] or 0) if movement else 0,
            "avg_return_fire_ms": int(reactions[0] or 0) if reactions else 0,
            "avg_dodge_ms": int(reactions[1] or 0) if reactions else 0,
            "avg_support_reaction_ms": int(reactions[2] or 0) if reactions else 0,
            "spawn_avg_score": float(spawn_timing[0] or 0) if spawn_timing else 0,
            "timed_kills": int(spawn_timing[1] or 0) if spawn_timing else 0,
            "avg_denial_ms": int(spawn_timing[2] or 0) if spawn_timing else 0,
            "trades_made": int(trade_stats[0] or 0) if trade_stats else 0,
        }
    except Exception:
        logger.exception("Proximity endpoint error")
        raise HTTPException(status_code=500, detail="Proximity endpoint error")


@router.get("/proximity/player/{guid}/radar")
async def get_proximity_player_radar(
    guid: str,
    range_days: int = 90,
    db: DatabaseAdapter = Depends(get_db),
):
    """5-axis radar data: Aggression, Awareness, Teamplay, Timing, Mechanical."""
    since = datetime.now(timezone.utc).replace(tzinfo=None).date() - timedelta(days=max(1, min(range_days, 3650)))
    try:
        # 5 independent axis queries — parallelise. Teamplay axis stays
        # below since it branches on awareness_row's engagement count and
        # may call the separate prox_scoring service.
        aggression_query = """
            SELECT ROUND(AVG(sprint_percentage)::numeric, 1),
                   ROUND(AVG(avg_speed)::numeric, 1)
            FROM player_track WHERE player_guid = $1 AND session_date >= $2
        """
        awareness_query = """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN outcome = 'escaped' THEN 1 ELSE 0 END) AS escapes
            FROM combat_engagement WHERE target_guid = $1 AND session_date >= $2
        """
        dodge_query = """
            SELECT ROUND(AVG(dodge_reaction_ms)::numeric, 0)
            FROM proximity_reaction_metric
            WHERE target_guid = $1 AND dodge_reaction_ms IS NOT NULL AND session_date >= $2
        """
        timing_query = """
            SELECT ROUND(AVG(spawn_timing_score)::numeric, 3), COUNT(*)
            FROM proximity_spawn_timing WHERE killer_guid = $1 AND session_date >= $2
        """
        rf_query = """
            SELECT ROUND(AVG(return_fire_ms)::numeric, 0)
            FROM proximity_reaction_metric
            WHERE target_guid = $1 AND return_fire_ms IS NOT NULL AND session_date >= $2
        """
        aggression_row, awareness_row, dodge_row, timing_row, rf_row = await asyncio.gather(
            db.fetch_one(aggression_query, (guid, since)),
            db.fetch_one(awareness_query, (guid, since)),
            db.fetch_one(dodge_query, (guid, since)),
            db.fetch_one(timing_query, (guid, since)),
            db.fetch_one(rf_query, (guid, since)),
        )

        sprint_pct = float(aggression_row[0] or 0) if aggression_row else 0
        avg_speed = float(aggression_row[1] or 0) if aggression_row else 0
        aggression = min(100, (sprint_pct * 0.6) + (min(avg_speed / 300, 1) * 100 * 0.4))

        total_eng = int(awareness_row[0] or 0) if awareness_row else 0
        escapes = int(awareness_row[1] or 0) if awareness_row else 0
        escape_rate = escapes / max(total_eng, 1) * 100
        dodge_ms = int(dodge_row[0] or 5000) if dodge_row and dodge_row[0] else 5000
        dodge_score = max(0, 100 - (dodge_ms / 50))  # Lower dodge = better
        awareness = min(100, escape_rate * 0.5 + dodge_score * 0.5)

        # Teamplay: reuse percentile-normalized prox_team score (6 metrics).
        # Only call compute_prox_scores when player has enough engagements (>=10),
        # otherwise the player gets neutral 0.5 percentiles → meaningless 50.0 score.
        # total_eng is already computed above (line 169) from combat_engagement.
        teamplay = None
        if total_eng >= 10:
            from website.backend.services.prox_scoring import compute_prox_scores
            prox_scores = await compute_prox_scores(db, range_days=range_days, player_guid=guid)
            if prox_scores and prox_scores[0].get("prox_team") is not None:
                teamplay = prox_scores[0]["prox_team"]

        if teamplay is None:
            # Fallback: lightweight CF+TR queries with raised thresholds
            cf_row = await db.fetch_one(
                """
                SELECT COUNT(*), COUNT(DISTINCT session_date)
                FROM proximity_crossfire_opportunity
                WHERE (teammate1_guid = $1 OR teammate2_guid = $1) AND was_executed = true
                AND session_date >= $2
                """, (guid, since),
            )
            trade_row = await db.fetch_one(
                """
                SELECT COUNT(*), COUNT(DISTINCT session_date)
                FROM proximity_lua_trade_kill WHERE trader_guid = $1 AND session_date >= $2
                """, (guid, since),
            )
            cf_total = int(cf_row[0] or 0) if cf_row else 0
            cf_sessions = max(1, int(cf_row[1] or 1) if cf_row else 1)
            trade_total = int(trade_row[0] or 0) if trade_row else 0
            trade_sessions = max(1, int(trade_row[1] or 1) if trade_row else 1)
            cf_per_session = cf_total / cf_sessions
            trade_per_session = trade_total / trade_sessions
            teamplay = min(100, (min(cf_per_session / 20, 1) * 50) + (min(trade_per_session / 10, 1) * 50))

        # Timing + Mechanical rows already fetched in the gather() above.
        avg_timing = float(timing_row[0] or 0) if timing_row else 0
        timing_count = int(timing_row[1] or 0) if timing_row else 0
        timing = min(100, avg_timing * 100 * min(timing_count / 5, 1))

        rf_ms = int(rf_row[0] or 3000) if rf_row and rf_row[0] else 3000
        rf_score = max(0, 100 - (rf_ms / 30))
        mechanical = min(100, rf_score)

        return {
            "axes": [
                {"label": "Aggression", "value": round(aggression, 1)},
                {"label": "Awareness", "value": round(awareness, 1)},
                {"label": "Teamplay", "value": round(teamplay, 1)},
                {"label": "Timing", "value": round(timing, 1)},
                {"label": "Mechanical", "value": round(mechanical, 1)},
            ],
            "composite": round((aggression + awareness + teamplay + timing + mechanical) / 5, 1),
        }
    except Exception:
        logger.exception("Proximity endpoint error")
        raise HTTPException(status_code=500, detail="Proximity endpoint error")
