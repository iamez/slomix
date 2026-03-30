"""Proximity round endpoints: round/{round_id}/timeline, round/{round_id}/tracks, round/{round_id}/team-comparison."""

from fastapi import APIRouter, Depends, HTTPException

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.routers.proximity_helpers import logger

router = APIRouter()


@router.get("/proximity/round/{round_id}/timeline")
async def get_proximity_round_timeline(
    round_id: int,
    db: DatabaseAdapter = Depends(get_db),
):
    """All events for a round sorted by time — for round replay UI."""
    try:
        # Get round info
        round_info = await db.fetch_one(
            "SELECT map_name, round_number, round_date, round_time FROM rounds WHERE id = $1",
            (round_id,),
        )
        if not round_info:
            raise HTTPException(status_code=404, detail="Round not found")

        # Engagements (kills/escapes)
        engagements = await db.fetch_all(
            """
            SELECT id, start_time_ms, end_time_ms, target_guid, target_name, target_team,
                   outcome, total_damage_taken, num_attackers, is_crossfire, attackers,
                   start_x, start_y, end_x, end_y
            FROM combat_engagement WHERE round_id = $1
            ORDER BY start_time_ms
            """,
            (round_id,),
        )
        # Spawn timing events
        spawn_events = await db.fetch_all(
            """
            SELECT kill_time, killer_guid, killer_name, victim_guid, victim_name,
                   spawn_timing_score
            FROM proximity_spawn_timing WHERE round_id = $1
            ORDER BY kill_time
            """,
            (round_id,),
        )
        # Trade kills
        trades = await db.fetch_all(
            """
            SELECT original_kill_time, traded_kill_time, delta_ms,
                   original_victim_guid, original_victim_name,
                   trader_guid, trader_name
            FROM proximity_lua_trade_kill WHERE round_id = $1
            ORDER BY traded_kill_time
            """,
            (round_id,),
        )
        # Team pushes
        pushes = await db.fetch_all(
            """
            SELECT start_time, end_time, team, avg_speed, alignment_score,
                   push_quality, participant_count, toward_objective
            FROM proximity_team_push WHERE round_id = $1
            ORDER BY start_time
            """,
            (round_id,),
        )

        # Round duration (ms) from actual_duration_seconds
        dur_row = await db.fetch_one(
            "SELECT actual_duration_seconds FROM rounds WHERE id = $1", (round_id,),
        )
        duration_ms = int((dur_row[0] or 0) * 1000) if dur_row and dur_row[0] else 0

        # Build unified event timeline — flat structure matching frontend TimelineEvent
        events = []
        for r in (engagements or []):
            events.append({
                "type": "engagement",
                "id": r[0],
                "time": int(r[1] or 0),
                "victim_name": r[4],
                "victim_team": r[5] or "",
                "outcome": r[6],
                "damage": int(r[7] or 0),
                "attackers": int(r[8] or 0),
            })
        for r in (spawn_events or []):
            events.append({
                "type": "spawn_timing_kill",
                "time": int(r[0] or 0),
                "attacker_name": r[2],
                "victim_name": r[4],
                "score": float(r[5] or 0),
            })
        for r in (trades or []):
            events.append({
                "type": "trade_kill",
                "time": int(r[1] or 0),
                "trader_name": r[6],
                "avenged_name": r[4],
                "delta_ms": int(r[2] or 0),
            })
        for r in (pushes or []):
            push_start = int(r[0] or 0)
            push_end = int(r[1] or 0)
            events.append({
                "type": "team_push",
                "time": push_start,
                "team": r[2],
                "quality": float(r[5] or 0),
                "alignment": float(r[4] or 0),
                "participants": int(r[6] or 0),
                "duration_ms": push_end - push_start if push_end > push_start else 0,
            })

        events.sort(key=lambda e: e["time"])

        return {
            "round_id": round_id,
            "map_name": round_info[0],
            "round_number": round_info[1],
            "round_date": str(round_info[2]) if round_info[2] else None,
            "duration_ms": duration_ms,
            "events": events,
        }
    except HTTPException:
        raise
    except Exception:
        logger.warning("Proximity endpoint error", exc_info=True)
        return {"status": "error", "detail": "Internal error"}


@router.get("/proximity/round/{round_id}/tracks")
async def get_proximity_round_tracks(
    round_id: int,
    db: DatabaseAdapter = Depends(get_db),
):
    """Player track paths for animated map view."""
    try:
        tracks = await db.fetch_all(
            """
            SELECT player_guid, MAX(player_name) AS name, team, player_class,
                   spawn_time, death_time, first_move_time, death_type,
                   path
            FROM player_track WHERE round_id = $1
            ORDER BY spawn_time
            """,
            (round_id,),
        )
        if not tracks:
            raise HTTPException(status_code=404, detail="No tracks for round")

        return {
            "status": "ok",
            "round_id": round_id,
            "track_count": len(tracks),
            "tracks": [
                {
                    "guid": r[0], "name": r[1], "team": r[2], "class": r[3],
                    "spawn_time": int(r[4] or 0), "death_time": int(r[5] or 0),
                    "first_move_time": int(r[6] or 0) if r[6] else None,
                    "death_type": r[7],
                    "path": r[8] or [],
                }
                for r in tracks
            ],
        }
    except HTTPException:
        raise
    except Exception:
        logger.warning("Proximity endpoint error", exc_info=True)
        return {"status": "error", "detail": "Internal error"}


@router.get("/proximity/round/{round_id}/team-comparison")
async def get_proximity_round_team_comparison(
    round_id: int,
    db: DatabaseAdapter = Depends(get_db),
):
    """Team vs team metrics for a specific round."""
    try:
        # Cohesion comparison
        cohesion = await db.fetch_all(
            """
            SELECT team,
                   ROUND(AVG(dispersion)::numeric, 1) AS avg_dispersion,
                   ROUND(AVG(max_spread)::numeric, 1) AS avg_max_spread,
                   ROUND(AVG(straggler_count)::numeric, 2) AS avg_stragglers,
                   COUNT(*) AS samples
            FROM proximity_team_cohesion WHERE round_id = $1
            GROUP BY team ORDER BY team
            """,
            (round_id,),
        )
        # Push quality
        pushes = await db.fetch_all(
            """
            SELECT team, COUNT(*) AS push_count,
                   ROUND(AVG(push_quality)::numeric, 3) AS avg_quality,
                   ROUND(AVG(alignment_score)::numeric, 3) AS avg_alignment
            FROM proximity_team_push WHERE round_id = $1
            GROUP BY team ORDER BY team
            """,
            (round_id,),
        )
        # Crossfire execution
        crossfire = await db.fetch_all(
            """
            SELECT target_team,
                   COUNT(*) AS total_opportunities,
                   SUM(CASE WHEN was_executed THEN 1 ELSE 0 END) AS executed
            FROM proximity_crossfire_opportunity WHERE round_id = $1
            GROUP BY target_team ORDER BY target_team
            """,
            (round_id,),
        )
        # Kill matchups query reserved for future kill-feed feature

        # Build {axis, allies} cohesion dict from array
        empty_cohesion = {"avg_dispersion": None, "avg_max_spread": None, "avg_stragglers": None, "samples": None}
        cohesion_dict = {"axis": dict(empty_cohesion), "allies": dict(empty_cohesion)}
        for r in (cohesion or []):
            team_key = (r[0] or "").lower()
            if team_key in ("axis", "allies"):
                cohesion_dict[team_key] = {
                    "avg_dispersion": float(r[1] or 0),
                    "avg_max_spread": float(r[2] or 0),
                    "avg_stragglers": float(r[3] or 0),
                    "samples": int(r[4] or 0),
                }

        # Build {axis, allies} pushes dict
        empty_push = {"push_count": None, "avg_quality": None, "avg_alignment": None}
        pushes_dict = {"axis": dict(empty_push), "allies": dict(empty_push)}
        for r in (pushes or []):
            team_key = (r[0] or "").lower()
            if team_key in ("axis", "allies"):
                pushes_dict[team_key] = {
                    "push_count": int(r[1] or 0),
                    "avg_quality": float(r[2] or 0),
                    "avg_alignment": float(r[3] or 0),
                }

        return {
            "cohesion": cohesion_dict,
            "pushes": pushes_dict,
            "crossfire": [
                {
                    "target_team": r[0],
                    "total_opportunities": int(r[1] or 0),
                    "executed": int(r[2] or 0),
                    "execution_rate": round(int(r[2] or 0) / max(int(r[1] or 0), 1) * 100, 1),
                }
                for r in (crossfire or [])
            ],
        }
    except Exception:
        logger.warning("Proximity endpoint error", exc_info=True)
        return {"status": "error", "detail": "Internal error"}
