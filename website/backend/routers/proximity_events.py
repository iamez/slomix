"""Proximity event endpoints: events, event/{event_id}."""

from fastapi import APIRouter, Depends, HTTPException

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.routers.proximity_helpers import (
    _build_proximity_where_clause,
    _compute_strafe_metrics,
    _parse_json_field,
    _proximity_stub_meta,
    _table_column_exists,
    logger,
)

router = APIRouter()


@router.get("/proximity/events")
async def get_proximity_events(
    range_days: int = 30,
    limit: int = 250,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Raw proximity engagement events (latest first, scoped).
    """
    payload = _proximity_stub_meta(range_days)
    safe_limit = max(1, min(int(limit or 250), 1000))
    where_sql, params, scope = _build_proximity_where_clause(
        range_days,
        session_date,
        map_name,
        round_number,
        round_start_unix,
        alias="e",
    )
    scoped_params = list(params)
    scoped_params.append(safe_limit)
    limit_placeholder = len(scoped_params)
    try:
        has_round_id_column = await _table_column_exists(
            db, "combat_engagement", "round_id"
        )
        if has_round_id_column:
            query = """
                SELECT e.id,
                       e.session_date, e.round_number, e.map_name, e.target_name, e.outcome,
                       e.duration_ms, e.distance_traveled, e.num_attackers, e.is_crossfire,
                       COALESCE(r_exact.id, r_fallback.id) AS round_id,
                       COALESCE(r_exact.round_date, r_fallback.round_date) AS round_date,
                       COALESCE(r_exact.round_time, r_fallback.round_time) AS round_time
                FROM combat_engagement e
                LEFT JOIN rounds r_exact
                  ON r_exact.id = e.round_id
                LEFT JOIN LATERAL (
                    SELECT id, round_date, round_time
                    FROM rounds r
                    WHERE r_exact.id IS NULL
                      AND r.map_name = e.map_name
                      AND r.round_number = e.round_number
                      AND e.round_start_unix > 0
                      AND r.round_start_unix > 0
                      AND ABS(r.round_start_unix - e.round_start_unix) <= 120
                    ORDER BY ABS(r.round_start_unix - e.round_start_unix)
                    LIMIT 1
                ) r_fallback ON true
            """
        else:
            query = """
                SELECT e.id,
                       e.session_date, e.round_number, e.map_name, e.target_name, e.outcome,
                       e.duration_ms, e.distance_traveled, e.num_attackers, e.is_crossfire,
                       r.id AS round_id, r.round_date, r.round_time
                FROM combat_engagement e
                LEFT JOIN LATERAL (
                    SELECT id, round_date, round_time
                    FROM rounds r
                    WHERE r.map_name = e.map_name
                      AND r.round_number = e.round_number
                      AND e.round_start_unix > 0
                      AND r.round_start_unix > 0
                      AND ABS(r.round_start_unix - e.round_start_unix) <= 120
                    ORDER BY ABS(r.round_start_unix - e.round_start_unix)
                    LIMIT 1
                ) r ON true
            """

        rows = await db.fetch_all(
            query
            + f" {where_sql} "
            + "ORDER BY e.session_date DESC, e.round_number DESC, e.start_time_ms DESC "
            + f"LIMIT ${limit_placeholder}",
            tuple(scoped_params),
        )
        payload.update(
            {
                "status": "ok" if rows else "prototype",
                "ready": bool(rows),
                "message": None if rows else payload["message"],
                "scope": scope,
                "limit": safe_limit,
                "events": [
                    {
                        "id": row[0],
                        "date": row[1].isoformat(),
                        "round": row[2],
                        "map": row[3],
                        "target_name": row[4],
                        "target": row[4],
                        "attacker_name": "",
                        "target_team": "",
                        "attacker_team": "",
                        "outcome": row[5],
                        "reaction_ms": row[6],
                        "duration_ms": row[6],
                        "distance": row[7],
                        "distance_traveled": row[7],
                        "attackers": row[8],
                        "crossfire": bool(row[9]),
                        "round_id": row[10],
                        "round_date": row[11],
                        "round_time": row[12],
                    }
                    for row in rows
                ],
            }
        )
    except Exception:
        logger.exception("Proximity events query failed")
        payload.update(
            {
                "status": "error",
                "ready": False,
                "message": "Proximity query failed",
                "scope": scope,
                "limit": safe_limit,
                "events": [],
            }
        )
    return payload


@router.get("/proximity/event/{event_id}")
async def get_proximity_event(event_id: int, db: DatabaseAdapter = Depends(get_db)):
    """
    Fetch a single engagement with position path + attacker details.
    """
    has_round_id_column = await _table_column_exists(db, "combat_engagement", "round_id")
    if has_round_id_column:
        query = """
            SELECT e.id,
                   e.session_date, e.round_number, e.round_start_unix, e.round_end_unix,
                   e.map_name, e.target_guid, e.target_name, e.target_team, e.outcome, e.total_damage_taken,
                   e.start_time_ms, e.end_time_ms,
                   e.duration_ms, e.num_attackers, e.is_crossfire,
                   e.position_path, e.attackers, e.start_x, e.start_y, e.end_x, e.end_y, e.distance_traveled,
                   COALESCE(r_exact.id, r_fallback.id) AS round_id,
                   COALESCE(r_exact.round_date, r_fallback.round_date) AS round_date,
                   COALESCE(r_exact.round_time, r_fallback.round_time) AS round_time
            FROM combat_engagement e
            LEFT JOIN rounds r_exact
              ON r_exact.id = e.round_id
            LEFT JOIN LATERAL (
                SELECT id, round_date, round_time
                FROM rounds r
                WHERE r_exact.id IS NULL
                  AND r.map_name = e.map_name
                  AND r.round_number = e.round_number
                  AND e.round_start_unix > 0
                  AND r.round_start_unix > 0
                  AND ABS(r.round_start_unix - e.round_start_unix) <= 120
                ORDER BY ABS(r.round_start_unix - e.round_start_unix)
                LIMIT 1
            ) r_fallback ON true
            WHERE e.id = $1
        """
    else:
        query = """
            SELECT e.id,
                   e.session_date, e.round_number, e.round_start_unix, e.round_end_unix,
                   e.map_name, e.target_guid, e.target_name, e.target_team, e.outcome, e.total_damage_taken,
                   e.start_time_ms, e.end_time_ms,
                   e.duration_ms, e.num_attackers, e.is_crossfire,
                   e.position_path, e.attackers, e.start_x, e.start_y, e.end_x, e.end_y, e.distance_traveled,
                   r.id AS round_id, r.round_date, r.round_time
            FROM combat_engagement e
            LEFT JOIN LATERAL (
                SELECT id, round_date, round_time
                FROM rounds r
                WHERE r.map_name = e.map_name
                  AND r.round_number = e.round_number
                  AND e.round_start_unix > 0
                  AND r.round_start_unix > 0
                  AND ABS(r.round_start_unix - e.round_start_unix) <= 120
                ORDER BY ABS(r.round_start_unix - e.round_start_unix)
                LIMIT 1
            ) r ON true
            WHERE e.id = $1
        """
    row = await db.fetch_one(query, (event_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Event not found")

    response = {
        "id": row[0],
        "session_date": row[1].isoformat(),
        "round_number": row[2],
        "round_start_unix": row[3],
        "round_end_unix": row[4],
        "map_name": row[5],
        "target_guid": row[6],
        "target_name": row[7],
        "target_team": row[8],
        "outcome": row[9],
        "total_damage": row[10],
        "start_time_ms": row[11],
        "end_time_ms": row[12],
        "duration_ms": row[13],
        "num_attackers": row[14],
        "is_crossfire": bool(row[15]),
        "position_path": row[16] or [],
        "attackers": row[17] or [],
        "start_x": row[18],
        "start_y": row[19],
        "end_x": row[20],
        "end_y": row[21],
        "distance_traveled": row[22],
        "round_id": row[23],
        "round_date": row[24],
        "round_time": row[25],
    }

    # Strafe / dodge metrics (target + primary attacker)
    try:
        start_time = response.get("start_time_ms") or 0
        end_time = response.get("end_time_ms") or 0
        if start_time and end_time and end_time > start_time:
            session_date = row[1]
            map_name = row[5]
            round_num = row[2]
            round_start_unix = row[3]

            async def load_track(guid: str):
                if not guid:
                    return None
                if round_start_unix and round_start_unix > 0:
                    track_row = await db.fetch_one(
                        "SELECT path FROM player_track "
                        "WHERE session_date = $1 AND map_name = $2 AND round_number = $3 "
                        "AND round_start_unix = $4 AND player_guid = $5 "
                        "ORDER BY spawn_time_ms ASC LIMIT 1",
                        (session_date, map_name, round_num, round_start_unix, guid),
                    )
                else:
                    track_row = await db.fetch_one(
                        "SELECT path FROM player_track "
                        "WHERE session_date = $1 AND map_name = $2 AND round_number = $3 "
                        "AND player_guid = $4 "
                        "ORDER BY ABS(spawn_time_ms - $5) ASC LIMIT 1",
                        (session_date, map_name, round_num, guid, start_time),
                    )
                if not track_row:
                    return None
                path = _parse_json_field(track_row[0]) or []
                sliced = [p for p in path if p.get("time") is not None and start_time <= p["time"] <= end_time]
                return sliced

            target_path = await load_track(response.get("target_guid"))

            attackers_raw = response.get("attackers")
            attackers = _parse_json_field(attackers_raw) or []
            response["attackers"] = attackers

            killer_guid = None
            killer_name = None
            if isinstance(attackers, list):
                for attacker in attackers:
                    if attacker.get("got_kill"):
                        killer_guid = attacker.get("guid")
                        killer_name = attacker.get("name")
                        break

            response["attacker_guid"] = killer_guid
            response["attacker_name"] = killer_name

            attacker_path = await load_track(killer_guid)

            response["target_path"] = target_path or []
            response["attacker_path"] = attacker_path or []

            response["strafe"] = {
                "target": _compute_strafe_metrics(target_path or []),
                "attacker": _compute_strafe_metrics(attacker_path or []),
            }
    except Exception:
        logger.debug("Strafe metrics computation failed", exc_info=True)
        response["strafe"] = None

    return response
