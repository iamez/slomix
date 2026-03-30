"""Proximity combat endpoints: engagements, hotzones, duos, classes."""

from fastapi import APIRouter, Depends

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.routers.proximity_helpers import (
    _build_proximity_where_clause,
    _compute_scoped_duos,
    _load_scoped_guid_name_map,
    _proximity_stub_meta,
    logger,
)

router = APIRouter()


@router.get("/proximity/engagements")
async def get_proximity_engagements(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    player_guid: str | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Engagement timeline buckets.
    """
    payload = _proximity_stub_meta(range_days)
    where_sql, params, scope = _build_proximity_where_clause(
        range_days,
        session_date,
        map_name,
        round_number,
        round_start_unix,
        player_guid=player_guid,
        player_guid_columns=["target_guid"],
    )
    query_params = tuple(params)
    try:
        rows = await db.fetch_all(
            "SELECT session_date, COUNT(*) AS engagements, "
            "SUM(CASE WHEN is_crossfire THEN 1 ELSE 0 END) AS crossfires "
            f"FROM combat_engagement {where_sql} "
            "GROUP BY session_date ORDER BY session_date",
            query_params,
        )
        payload.update(
            {
                "status": "ok" if rows else "prototype",
                "ready": bool(rows),
                "message": None if rows else payload["message"],
                "scope": scope,
                "buckets": [
                    {
                        "date": row[0].isoformat(),
                        "engagements": int(row[1] or 0),
                        "crossfires": int(row[2] or 0),
                    }
                    for row in rows
                ],
            }
        )
    except Exception:
        logger.exception("Proximity engagements query failed")
        payload.update(
            {
                "status": "error",
                "ready": False,
                "message": "Proximity query failed",
                "scope": scope,
                "buckets": [],
            }
        )
    return payload


@router.get("/proximity/hotzones")
async def get_proximity_hotzones(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    player_guid: str | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Hotzone bins generated from scoped combat engagements.
    """
    payload = _proximity_stub_meta(range_days)
    normalized_map = (map_name or "").strip() or None

    where_sql, params, scope = _build_proximity_where_clause(
        range_days,
        session_date,
        None,
        round_number,
        round_start_unix,
        alias="e",
        player_guid=player_guid, player_guid_columns=["target_guid"],
    )
    scope["map_name"] = normalized_map
    query_params = tuple(params)

    try:
        selected_map = normalized_map
        if not selected_map:
            selected_map = await db.fetch_val(
                "SELECT e.map_name "
                f"FROM combat_engagement e {where_sql} "
                "GROUP BY e.map_name "
                "ORDER BY COUNT(*) DESC NULLS LAST "
                "LIMIT 1",
                query_params,
            )

        if not selected_map:
            payload.update(
                {
                    "status": "prototype",
                    "ready": False,
                    "scope": scope,
                    "map_name": None,
                    "hotzones": [],
                }
            )
            return payload

        scoped_params = list(params)
        scoped_params.append(selected_map)
        map_filter = f"{where_sql} AND e.map_name = ${len(scoped_params)}"

        rows = await db.fetch_all(
            """
            SELECT FLOOR(COALESCE(e.end_x, e.start_x) / 256.0)::int AS grid_x,
                   FLOOR(COALESCE(e.end_y, e.start_y) / 256.0)::int AS grid_y,
                   SUM(CASE WHEN e.outcome = 'killed' THEN 1 ELSE 0 END) AS kills,
                   COUNT(*) AS total_events
            FROM combat_engagement e
            """
            + f" {map_filter} "
            + """
              AND COALESCE(e.end_x, e.start_x) IS NOT NULL
              AND COALESCE(e.end_y, e.start_y) IS NOT NULL
            GROUP BY 1, 2
            ORDER BY kills DESC, total_events DESC
            LIMIT 200
            """,
            tuple(scoped_params),
        )

        scope["map_name"] = selected_map
        payload.update(
            {
                "status": "ok" if rows else "prototype",
                "ready": bool(rows),
                "message": None if rows else payload["message"],
                "scope": scope,
                "source": "combat_engagement",
                "map_name": selected_map,
                "hotzones": [
                    {
                        "x": row[0],
                        "y": row[1],
                        "count": int(row[3] or 0),
                        "kills": int(row[2] or 0),
                        "deaths": max(int(row[3] or 0) - int(row[2] or 0), 0),
                    }
                    for row in rows
                ],
            }
        )
    except Exception:
        logger.exception("Proximity hotzones query failed")
        payload.update(
            {
                "status": "error",
                "ready": False,
                "message": "Proximity query failed",
                "scope": scope,
                "map_name": normalized_map,
                "hotzones": [],
            }
        )
    return payload


@router.get("/proximity/duos")
async def get_proximity_duos(
    range_days: int = 30,
    limit: int = 10,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    player_guid: str | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Duo synergy list computed from scoped combat engagements.
    """
    payload = _proximity_stub_meta(range_days)
    safe_limit = max(1, min(int(limit or 10), 50))
    where_sql, params, scope = _build_proximity_where_clause(
        range_days,
        session_date,
        map_name,
        round_number,
        round_start_unix,
    )
    query_params = tuple(params)

    try:
        guid_name_map = await _load_scoped_guid_name_map(db, where_sql, query_params)
        rows = await db.fetch_all(
            "SELECT attackers, crossfire_participants, crossfire_delay_ms, outcome "
            f"FROM combat_engagement {where_sql} "
            "AND is_crossfire = TRUE "
            "ORDER BY session_date DESC, round_start_unix DESC, start_time_ms DESC "
            "LIMIT 5000",
            query_params,
        )
        duos = _compute_scoped_duos(rows, safe_limit, guid_name_map=guid_name_map)
        payload.update(
            {
                "status": "ok" if duos else "prototype",
                "ready": bool(duos),
                "message": None if duos else payload["message"],
                "scope": scope,
                "limit": safe_limit,
                "duos": duos,
            }
        )
    except Exception:
        logger.exception("Proximity duos query failed")
        payload.update(
            {
                "status": "error",
                "ready": False,
                "message": "Proximity query failed",
                "scope": scope,
                "limit": safe_limit,
                "duos": [],
            }
        )
    return payload


@router.get("/proximity/classes")
async def get_proximity_classes(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Class composition and class-level movement summary from scoped player_track rows.
    """
    payload = _proximity_stub_meta(range_days)
    where_sql, params, scope = _build_proximity_where_clause(
        range_days,
        session_date,
        map_name,
        round_number,
        round_start_unix,
    )
    query_params = tuple(params)
    try:
        rows = await db.fetch_all(
            "SELECT player_class, "
            "COUNT(*) AS track_count, "
            "COUNT(DISTINCT player_guid) AS unique_players, "
            "AVG(duration_ms) AS avg_duration_ms, "
            "AVG(total_distance) AS avg_distance, "
            "AVG(sprint_percentage) AS avg_sprint_pct, "
            "AVG(CASE WHEN spawn_time_ms >= 0 THEN time_to_first_move_ms END) AS avg_spawn_reaction_ms "
            f"FROM player_track {where_sql} "
            "GROUP BY player_class "
            "ORDER BY track_count DESC, player_class ASC",
            query_params,
        )

        payload.update(
            {
                "status": "ok" if rows else "prototype",
                "ready": bool(rows),
                "message": None if rows else payload["message"],
                "scope": scope,
                "classes": [
                    {
                        "player_class": row[0] or "UNKNOWN",
                        "tracks": int(row[1] or 0),
                        "players": int(row[2] or 0),
                        "avg_duration_ms": round(row[3], 0) if row[3] is not None else None,
                        "avg_distance": round(row[4], 1) if row[4] is not None else None,
                        "avg_sprint_pct": round(row[5], 1) if row[5] is not None else None,
                        "avg_spawn_reaction_ms": round(row[6], 0) if row[6] is not None else None,
                    }
                    for row in rows
                ],
            }
        )
    except Exception:
        logger.exception("Proximity classes query failed")
        payload.update(
            {
                "status": "error",
                "ready": False,
                "message": "Proximity query failed",
                "scope": scope,
                "classes": [],
            }
        )
    return payload
