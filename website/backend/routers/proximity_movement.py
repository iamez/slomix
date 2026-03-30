"""Proximity movement endpoints: movers, reactions."""

from fastapi import APIRouter, Depends

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.routers.proximity_helpers import (
    _build_proximity_where_clause,
    _proximity_stub_meta,
    logger,
)

router = APIRouter()


@router.get("/proximity/movers")
async def get_proximity_movers(
    range_days: int = 30,
    limit: int = 5,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    player_guid: str | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Movement and reaction leaders from scoped player_track rows.
    """
    payload = _proximity_stub_meta(range_days)
    safe_limit = max(1, min(int(limit or 5), 25))
    where_sql, params, scope = _build_proximity_where_clause(
        range_days,
        session_date,
        map_name,
        round_number,
        round_start_unix,
        player_guid=player_guid, player_guid_columns=["player_guid"],
    )

    try:
        base_params = list(params)
        limit_placeholder = len(base_params) + 1
        query_params = tuple(base_params + [safe_limit])

        distance_rows = await db.fetch_all(
            "SELECT player_guid, player_name, SUM(total_distance) AS total_distance, COUNT(*) AS tracks "
            f"FROM player_track {where_sql} "
            "GROUP BY player_guid, player_name "
            f"ORDER BY total_distance DESC NULLS LAST LIMIT ${limit_placeholder}",
            query_params,
        )
        sprint_rows = await db.fetch_all(
            "SELECT player_guid, player_name, AVG(sprint_percentage) AS sprint_pct, COUNT(*) AS tracks "
            f"FROM player_track {where_sql} AND sprint_percentage IS NOT NULL "
            "GROUP BY player_guid, player_name "
            f"ORDER BY sprint_pct DESC NULLS LAST LIMIT ${limit_placeholder}",
            query_params,
        )
        reaction_rows = await db.fetch_all(
            "SELECT player_guid, player_name, AVG(time_to_first_move_ms) AS reaction_ms, COUNT(*) AS tracks "
            f"FROM player_track {where_sql} AND time_to_first_move_ms IS NOT NULL AND spawn_time_ms >= 0 "
            "GROUP BY player_guid, player_name "
            f"ORDER BY reaction_ms ASC NULLS LAST LIMIT ${limit_placeholder}",
            query_params,
        )
        survival_rows = await db.fetch_all(
            "SELECT player_guid, player_name, AVG(duration_ms) AS duration_ms, COUNT(*) AS tracks "
            f"FROM player_track {where_sql} AND duration_ms IS NOT NULL "
            "GROUP BY player_guid, player_name "
            f"ORDER BY duration_ms DESC NULLS LAST LIMIT ${limit_placeholder}",
            query_params,
        )

        ready = bool(distance_rows or sprint_rows or reaction_rows or survival_rows)
        payload.update(
            {
                "status": "ok" if ready else "prototype",
                "ready": ready,
                "message": None if ready else payload["message"],
                "scope": scope,
                "limit": safe_limit,
                "distance": [
                    {
                        "guid": row[0],
                        "name": row[1],
                        "total_distance": round(row[2], 1) if row[2] is not None else None,
                        "tracks": int(row[3] or 0),
                    }
                    for row in distance_rows
                ],
                "sprint": [
                    {
                        "guid": row[0],
                        "name": row[1],
                        "sprint_pct": round(row[2], 1) if row[2] is not None else None,
                        "tracks": int(row[3] or 0),
                    }
                    for row in sprint_rows
                ],
                "reaction": [
                    {
                        "guid": row[0],
                        "name": row[1],
                        "reaction_ms": round(row[2], 0) if row[2] is not None else None,
                        "tracks": int(row[3] or 0),
                    }
                    for row in reaction_rows
                ],
                "survival": [
                    {
                        "guid": row[0],
                        "name": row[1],
                        "duration_ms": round(row[2], 0) if row[2] is not None else None,
                        "tracks": int(row[3] or 0),
                    }
                    for row in survival_rows
                ],
            }
        )
    except Exception:
        logger.exception("Proximity movers query failed")
        payload.update(
            {
                "status": "error",
                "ready": False,
                "message": "Proximity query failed",
                "scope": scope,
                "limit": safe_limit,
                "distance": [],
                "sprint": [],
                "reaction": [],
                "survival": [],
            }
        )
    return payload


@router.get("/proximity/reactions")
async def get_proximity_reactions(
    range_days: int = 30,
    limit: int = 5,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    player_guid: str | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Combat reaction leaders from proximity_reaction_metric (return fire / dodge / support).
    """
    payload = _proximity_stub_meta(range_days)
    safe_limit = max(1, min(int(limit or 5), 25))
    where_sql, params, scope = _build_proximity_where_clause(
        range_days,
        session_date,
        map_name,
        round_number,
        round_start_unix,
        alias="r",
        player_guid=player_guid, player_guid_columns=["target_guid"],
    )
    query_params = tuple(params)
    try:
        table_exists = await db.fetch_val(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = 'proximity_reaction_metric'
            )
            """
        )
        if not table_exists:
            payload.update(
                {
                    "status": "prototype",
                    "ready": False,
                    "scope": scope,
                    "limit": safe_limit,
                    "message": "Reaction telemetry table not migrated yet.",
                    "return_fire": [],
                    "dodge": [],
                    "support": [],
                    "class_summary": [],
                }
            )
            return payload

        scoped_params = list(params)
        scoped_params.append(safe_limit)
        limit_placeholder = len(scoped_params)

        return_rows = await db.fetch_all(
            "SELECT r.target_guid, r.target_name, r.target_class, "
            "AVG(r.return_fire_ms) AS avg_return_fire_ms, "
            "COUNT(r.return_fire_ms) AS samples "
            "FROM proximity_reaction_metric r "
            f"{where_sql} AND r.return_fire_ms IS NOT NULL "
            "GROUP BY r.target_guid, r.target_name, r.target_class "
            "ORDER BY avg_return_fire_ms ASC NULLS LAST "
            f"LIMIT ${limit_placeholder}",
            tuple(scoped_params),
        )
        dodge_rows = await db.fetch_all(
            "SELECT r.target_guid, r.target_name, r.target_class, "
            "AVG(r.dodge_reaction_ms) AS avg_dodge_reaction_ms, "
            "COUNT(r.dodge_reaction_ms) AS samples "
            "FROM proximity_reaction_metric r "
            f"{where_sql} AND r.dodge_reaction_ms IS NOT NULL "
            "GROUP BY r.target_guid, r.target_name, r.target_class "
            "ORDER BY avg_dodge_reaction_ms ASC NULLS LAST "
            f"LIMIT ${limit_placeholder}",
            tuple(scoped_params),
        )
        support_rows = await db.fetch_all(
            "SELECT r.target_guid, r.target_name, r.target_class, "
            "AVG(r.support_reaction_ms) AS avg_support_reaction_ms, "
            "COUNT(r.support_reaction_ms) AS samples "
            "FROM proximity_reaction_metric r "
            f"{where_sql} AND r.support_reaction_ms IS NOT NULL "
            "GROUP BY r.target_guid, r.target_name, r.target_class "
            "ORDER BY avg_support_reaction_ms ASC NULLS LAST "
            f"LIMIT ${limit_placeholder}",
            tuple(scoped_params),
        )
        class_rows = await db.fetch_all(
            "SELECT r.target_class, "
            "COUNT(*) AS events, "
            "COUNT(r.return_fire_ms) AS return_samples, AVG(r.return_fire_ms) AS avg_return_fire_ms, "
            "COUNT(r.dodge_reaction_ms) AS dodge_samples, AVG(r.dodge_reaction_ms) AS avg_dodge_reaction_ms, "
            "COUNT(r.support_reaction_ms) AS support_samples, AVG(r.support_reaction_ms) AS avg_support_reaction_ms "
            "FROM proximity_reaction_metric r "
            f"{where_sql} "
            "GROUP BY r.target_class "
            "ORDER BY events DESC, r.target_class ASC",
            query_params,
        )

        ready = bool(return_rows or dodge_rows or support_rows or class_rows)
        payload.update(
            {
                "status": "ok" if ready else "prototype",
                "ready": ready,
                "message": None if ready else payload["message"],
                "scope": scope,
                "limit": safe_limit,
                "return_fire": [
                    {
                        "guid": row[0],
                        "name": row[1],
                        "player_class": row[2] or "UNKNOWN",
                        "reaction_ms": round(row[3], 0) if row[3] is not None else None,
                        "samples": int(row[4] or 0),
                    }
                    for row in return_rows
                ],
                "dodge": [
                    {
                        "guid": row[0],
                        "name": row[1],
                        "player_class": row[2] or "UNKNOWN",
                        "reaction_ms": round(row[3], 0) if row[3] is not None else None,
                        "samples": int(row[4] or 0),
                    }
                    for row in dodge_rows
                ],
                "support": [
                    {
                        "guid": row[0],
                        "name": row[1],
                        "player_class": row[2] or "UNKNOWN",
                        "reaction_ms": round(row[3], 0) if row[3] is not None else None,
                        "samples": int(row[4] or 0),
                    }
                    for row in support_rows
                ],
                "class_summary": [
                    {
                        "player_class": row[0] or "UNKNOWN",
                        "events": int(row[1] or 0),
                        "return_samples": int(row[2] or 0),
                        "avg_return_fire_ms": round(row[3], 0) if row[3] is not None else None,
                        "dodge_samples": int(row[4] or 0),
                        "avg_dodge_reaction_ms": round(row[5], 0) if row[5] is not None else None,
                        "support_samples": int(row[6] or 0),
                        "avg_support_reaction_ms": round(row[7], 0) if row[7] is not None else None,
                    }
                    for row in class_rows
                ],
            }
        )
    except Exception:
        logger.exception("Proximity reactions query failed")
        payload.update(
            {
                "status": "error",
                "ready": False,
                "message": "Proximity query failed",
                "scope": scope,
                "limit": safe_limit,
                "return_fire": [],
                "dodge": [],
                "support": [],
                "class_summary": [],
            }
        )
    return payload
