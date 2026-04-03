"""Proximity objective endpoints: carrier-events, carrier-kills, carrier-returns, vehicle-progress, escort-credits, construction-events, objective-runs, objective-focus."""

from fastapi import APIRouter, Depends, HTTPException

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.routers.proximity_helpers import (
    _parse_iso_date,
    _table_column_exists,
    logger,
)

router = APIRouter()


@router.get("/proximity/carrier-events")
async def get_proximity_carrier_events(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    limit: int = 10,
    db: DatabaseAdapter = Depends(get_db),
):
    """Carrier leaderboard + recent events from proximity_carrier_event."""
    where_parts: list = []
    params: list = []

    if session_date:
        params.append(_parse_iso_date(session_date) if isinstance(session_date, str) else session_date)
        where_parts.append(f"session_date = ${len(params)}")
    else:
        params.append(range_days)
        where_parts.append(f"session_date >= CURRENT_DATE - ${len(params)} * INTERVAL '1 day'")
    if map_name:
        params.append(map_name)
        where_parts.append(f"map_name = ${len(params)}")
    if round_number is not None:
        params.append(round_number)
        where_parts.append(f"round_number = ${len(params)}")
    if round_start_unix is not None:
        params.append(round_start_unix)
        where_parts.append(f"round_start_unix = ${len(params)}")

    where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    safe_limit = max(1, min(limit, 50))
    scope = {"session_date": session_date, "map_name": map_name, "round_number": round_number}

    try:
        exists = await _table_column_exists(db, "proximity_carrier_event", "carrier_guid")
        if not exists:
            return {"status": "ok", "carriers": [], "events": [], "summary": {}}

        # Carrier leaderboard
        carriers_rows = await db.fetch_all(
            f"""
            SELECT carrier_guid, MAX(carrier_name) AS name,
                   COUNT(*) AS carries,
                   SUM(CASE WHEN outcome = 'secured' THEN 1 ELSE 0 END) AS secures,
                   SUM(CASE WHEN outcome = 'killed' THEN 1 ELSE 0 END) AS killed,
                   SUM(CASE WHEN outcome = 'dropped' THEN 1 ELSE 0 END) AS dropped,
                   ROUND(SUM(carry_distance)::numeric, 0) AS total_distance,
                   ROUND(AVG(efficiency)::numeric, 3) AS avg_efficiency,
                   ROUND(AVG(duration_ms)::numeric, 0) AS avg_duration_ms
            FROM proximity_carrier_event {where_sql}
            GROUP BY carrier_guid
            HAVING COUNT(*) >= 1
            ORDER BY SUM(CASE WHEN outcome = 'secured' THEN 1 ELSE 0 END) DESC, SUM(carry_distance) DESC
            LIMIT {safe_limit}
            """,
            tuple(params),
        )

        carriers = []
        for r in (carriers_rows or []):
            carries = int(r[2] or 0)
            secures = int(r[3] or 0)
            carriers.append({
                "guid": r[0],
                "name": r[1],
                "carries": carries,
                "secures": secures,
                "killed": int(r[4] or 0),
                "dropped": int(r[5] or 0),
                "total_distance": float(r[6] or 0),
                "avg_efficiency": float(r[7] or 0),
                "avg_duration_ms": float(r[8] or 0),
                "secure_rate": round(secures * 100 / carries, 1) if carries > 0 else 0,
            })

        # Recent events
        events_rows = await db.fetch_all(
            f"""
            SELECT carrier_name, carrier_team, flag_team, outcome,
                   carry_distance, beeline_distance, efficiency,
                   duration_ms, map_name, killer_name, pickup_time
            FROM proximity_carrier_event {where_sql}
            ORDER BY session_date DESC, pickup_time DESC
            LIMIT 20
            """,
            tuple(params),
        )

        events = []
        for r in (events_rows or []):
            events.append({
                "carrier_name": r[0],
                "carrier_team": r[1],
                "flag_team": r[2],
                "outcome": r[3],
                "carry_distance": float(r[4] or 0),
                "beeline_distance": float(r[5] or 0),
                "efficiency": float(r[6] or 0),
                "duration_ms": int(r[7] or 0),
                "map_name": r[8],
                "killer_name": r[9] or "",
                "pickup_time": int(r[10] or 0),
            })

        # Summary
        summary_row = await db.fetch_one(
            f"""
            SELECT COUNT(*),
                   SUM(CASE WHEN outcome = 'secured' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN outcome = 'killed' THEN 1 ELSE 0 END),
                   ROUND(AVG(carry_distance)::numeric, 0),
                   ROUND(AVG(efficiency)::numeric, 3)
            FROM proximity_carrier_event {where_sql}
            """,
            tuple(params),
        )
        total = int(summary_row[0] or 0) if summary_row else 0
        total_secures = int(summary_row[1] or 0) if summary_row else 0
        summary = {
            "total_carries": total,
            "total_secures": total_secures,
            "total_killed": int(summary_row[2] or 0) if summary_row else 0,
            "avg_distance": float(summary_row[3] or 0) if summary_row else 0,
            "avg_efficiency": float(summary_row[4] or 0) if summary_row else 0,
            "secure_rate": round(total_secures * 100 / total, 1) if total > 0 else 0,
        }

        return {"status": "ok", "scope": scope, "carriers": carriers, "events": events, "summary": summary}
    except Exception:
        logger.exception("Carrier events error")
        raise HTTPException(status_code=500, detail="Carrier events error")


@router.get("/proximity/carrier-kills")
async def get_proximity_carrier_kills(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    limit: int = 10,
    db: DatabaseAdapter = Depends(get_db),
):
    """Carrier killer leaderboard from proximity_carrier_kill."""
    where_parts: list = []
    params: list = []

    if session_date:
        params.append(_parse_iso_date(session_date) if isinstance(session_date, str) else session_date)
        where_parts.append(f"session_date = ${len(params)}")
    else:
        params.append(range_days)
        where_parts.append(f"session_date >= CURRENT_DATE - ${len(params)} * INTERVAL '1 day'")
    if map_name:
        params.append(map_name)
        where_parts.append(f"map_name = ${len(params)}")
    if round_number is not None:
        params.append(round_number)
        where_parts.append(f"round_number = ${len(params)}")
    if round_start_unix is not None:
        params.append(round_start_unix)
        where_parts.append(f"round_start_unix = ${len(params)}")

    where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    safe_limit = max(1, min(limit, 50))

    try:
        exists = await _table_column_exists(db, "proximity_carrier_kill", "killer_guid")
        if not exists:
            return {"status": "ok", "killers": []}

        rows = await db.fetch_all(
            f"""
            SELECT killer_guid, MAX(killer_name) AS name,
                   COUNT(*) AS carrier_kills,
                   ROUND(AVG(carrier_distance_at_kill)::numeric, 0) AS avg_distance_stopped
            FROM proximity_carrier_kill {where_sql}
            GROUP BY killer_guid
            HAVING COUNT(*) >= 1
            ORDER BY COUNT(*) DESC
            LIMIT {safe_limit}
            """,
            tuple(params),
        )

        killers = []
        for r in (rows or []):
            killers.append({
                "guid": r[0],
                "name": r[1],
                "carrier_kills": int(r[2] or 0),
                "avg_distance_stopped": float(r[3] or 0),
            })

        return {"status": "ok", "killers": killers}
    except Exception:
        logger.exception("Carrier kills error")
        raise HTTPException(status_code=500, detail="Carrier kills error")


@router.get("/proximity/carrier-returns")
async def get_proximity_carrier_returns(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    limit: int = 10,
    db: DatabaseAdapter = Depends(get_db),
):
    """Carrier return intelligence — Phase 1.5"""
    try:
        if not await _table_column_exists(db, 'proximity_carrier_return', 'returner_guid'):
            return {"status": "ok", "returners": [], "events": [], "summary": {}}

        where_parts: list = []
        params: list = []
        if session_date:
            params.append(_parse_iso_date(session_date) if isinstance(session_date, str) else session_date)
            where_parts.append(f"session_date = ${len(params)}")
        else:
            params.append(range_days)
            where_parts.append(f"session_date >= CURRENT_DATE - ${len(params)} * INTERVAL '1 day'")
        if map_name:
            params.append(map_name)
            where_parts.append(f"map_name = ${len(params)}")
        if round_number is not None:
            params.append(round_number)
            where_parts.append(f"round_number = ${len(params)}")
        if round_start_unix is not None:
            params.append(round_start_unix)
            where_parts.append(f"round_start_unix = ${len(params)}")

        where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
        scope = {"range_days": range_days, "session_date": session_date, "map_name": map_name}
        safe_limit = max(1, min(limit, 50))

        # Returner leaderboard
        returner_rows = await db.fetch_all(
            f"""
            SELECT returner_guid AS guid, MAX(returner_name) AS name,
                   COUNT(*) AS returns,
                   ROUND(AVG(return_delay_ms)::numeric, 0) AS avg_delay_ms
            FROM proximity_carrier_return
            {where_sql}
            GROUP BY returner_guid
            HAVING COUNT(*) >= 1
            ORDER BY COUNT(*) DESC
            LIMIT {safe_limit}
            """,
            tuple(params),
        )
        returners = [dict(r) for r in (returner_rows or [])]

        # Recent events
        event_rows = await db.fetch_all(
            f"""
            SELECT returner_name, returner_team, flag_team, original_carrier_guid,
                   return_delay_ms, map_name, drop_x, drop_y, drop_z, return_time
            FROM proximity_carrier_return
            {where_sql}
            ORDER BY session_date DESC, return_time DESC
            LIMIT 20
            """,
            tuple(params),
        )
        events = [dict(r) for r in (event_rows or [])]

        # Summary
        summary_row = await db.fetch_one(
            f"""
            SELECT COUNT(*) AS total_returns,
                   ROUND(AVG(return_delay_ms)::numeric, 0) AS avg_delay_ms
            FROM proximity_carrier_return
            {where_sql}
            """,
            tuple(params),
        )
        summary = dict(summary_row) if summary_row else {"total_returns": 0, "avg_delay_ms": 0}

        return {"status": "ok", "scope": scope, "returners": returners, "events": events, "summary": summary}
    except Exception:
        logger.exception("carrier-returns error")
        raise HTTPException(status_code=500, detail="carrier-returns error")


@router.get("/proximity/vehicle-progress")
async def get_proximity_vehicle_progress(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Vehicle progress intelligence — Phase 2"""
    try:
        if not await _table_column_exists(db, 'proximity_vehicle_progress', 'vehicle_name'):
            return {"status": "ok", "vehicles": []}

        where_parts: list = []
        params: list = []
        if session_date:
            params.append(_parse_iso_date(session_date) if isinstance(session_date, str) else session_date)
            where_parts.append(f"session_date = ${len(params)}")
        else:
            params.append(range_days)
            where_parts.append(f"session_date >= CURRENT_DATE - ${len(params)} * INTERVAL '1 day'")
        if map_name:
            params.append(map_name)
            where_parts.append(f"map_name = ${len(params)}")
        if round_number is not None:
            params.append(round_number)
            where_parts.append(f"round_number = ${len(params)}")
        if round_start_unix is not None:
            params.append(round_start_unix)
            where_parts.append(f"round_start_unix = ${len(params)}")

        where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

        rows = await db.fetch_all(
            f"""
            SELECT vehicle_name, vehicle_type, map_name, session_date, round_number,
                   total_distance, max_health, final_health, destroyed_count,
                   start_x, start_y, start_z, end_x, end_y, end_z
            FROM proximity_vehicle_progress
            {where_sql}
            ORDER BY session_date DESC, round_number DESC
            LIMIT 50
            """,
            tuple(params),
        )
        vehicles = [dict(r) for r in (rows or [])]

        return {"status": "ok", "vehicles": vehicles}
    except Exception:
        logger.exception("vehicle-progress error")
        raise HTTPException(status_code=500, detail="vehicle-progress error")


@router.get("/proximity/escort-credits")
async def get_proximity_escort_credits(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    limit: int = 10,
    db: DatabaseAdapter = Depends(get_db),
):
    """Escort credit intelligence — Phase 2"""
    try:
        if not await _table_column_exists(db, 'proximity_escort_credit', 'player_guid'):
            return {"status": "ok", "escorts": []}

        where_parts: list = []
        params: list = []
        if session_date:
            params.append(_parse_iso_date(session_date) if isinstance(session_date, str) else session_date)
            where_parts.append(f"session_date = ${len(params)}")
        else:
            params.append(range_days)
            where_parts.append(f"session_date >= CURRENT_DATE - ${len(params)} * INTERVAL '1 day'")
        if map_name:
            params.append(map_name)
            where_parts.append(f"map_name = ${len(params)}")
        if round_number is not None:
            params.append(round_number)
            where_parts.append(f"round_number = ${len(params)}")
        if round_start_unix is not None:
            params.append(round_start_unix)
            where_parts.append(f"round_start_unix = ${len(params)}")

        where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
        safe_limit = max(1, min(limit, 50))

        rows = await db.fetch_all(
            f"""
            SELECT player_guid AS guid, MAX(player_name) AS name,
                   ROUND(SUM(credit_distance)::numeric, 0) AS total_credit_distance,
                   SUM(mounted_time_ms) AS total_mounted_ms,
                   SUM(proximity_time_ms) AS total_proximity_ms,
                   ROUND(SUM(total_escort_distance)::numeric, 0) AS total_escort_distance,
                   SUM(samples) AS total_samples
            FROM proximity_escort_credit
            {where_sql}
            GROUP BY player_guid
            HAVING SUM(samples) >= 1
            ORDER BY SUM(credit_distance) DESC
            LIMIT {safe_limit}
            """,
            tuple(params),
        )
        escorts = [dict(r) for r in (rows or [])]

        return {"status": "ok", "escorts": escorts}
    except Exception:
        logger.exception("escort-credits error")
        raise HTTPException(status_code=500, detail="escort-credits error")


@router.get("/proximity/construction-events")
async def get_proximity_construction_events(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    limit: int = 10,
    db: DatabaseAdapter = Depends(get_db),
):
    """Construction/destruction event intelligence — Phase 3"""
    try:
        if not await _table_column_exists(db, 'proximity_construction_event', 'player_guid'):
            return {"status": "ok", "engineers": [], "events": []}

        where_parts: list = []
        params: list = []
        if session_date:
            params.append(_parse_iso_date(session_date) if isinstance(session_date, str) else session_date)
            where_parts.append(f"session_date = ${len(params)}")
        else:
            params.append(range_days)
            where_parts.append(f"session_date >= CURRENT_DATE - ${len(params)} * INTERVAL '1 day'")
        if map_name:
            params.append(map_name)
            where_parts.append(f"map_name = ${len(params)}")
        if round_number is not None:
            params.append(round_number)
            where_parts.append(f"round_number = ${len(params)}")
        if round_start_unix is not None:
            params.append(round_start_unix)
            where_parts.append(f"round_start_unix = ${len(params)}")

        where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
        safe_limit = max(1, min(limit, 50))

        # Engineer leaderboard with per-type breakdown
        engineer_rows = await db.fetch_all(
            f"""
            SELECT player_guid AS guid, MAX(player_name) AS name,
                   COUNT(*) AS total_events,
                   COUNT(*) FILTER (WHERE event_type = 'dynamite_plant') AS plants,
                   COUNT(*) FILTER (WHERE event_type = 'dynamite_defuse') AS defuses,
                   COUNT(*) FILTER (WHERE event_type = 'objective_destroyed') AS destructions,
                   COUNT(*) FILTER (WHERE event_type = 'construction_complete') AS constructions
            FROM proximity_construction_event
            {where_sql}
            GROUP BY player_guid
            HAVING COUNT(*) >= 1
            ORDER BY COUNT(*) DESC
            LIMIT {safe_limit}
            """,
            tuple(params),
        )
        engineers = [dict(r) for r in (engineer_rows or [])]

        # Recent events
        event_rows = await db.fetch_all(
            f"""
            SELECT event_type, player_name, player_team, track_name, map_name,
                   session_date, round_number, event_time
            FROM proximity_construction_event
            {where_sql}
            ORDER BY session_date DESC, event_time DESC
            LIMIT 20
            """,
            tuple(params),
        )
        events = [dict(r) for r in (event_rows or [])]

        return {"status": "ok", "engineers": engineers, "events": events}
    except Exception:
        logger.exception("construction-events error")
        raise HTTPException(status_code=500, detail="construction-events error")


@router.get("/proximity/objective-runs")
async def get_proximity_objective_runs(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Objective run intelligence — engineer runs with path clearing attribution"""
    try:
        if not await _table_column_exists(db, 'proximity_objective_run', 'engineer_guid'):
            return {"status": "ok", "objective_runners": [], "recent_runs": [], "summary": None}

        where_parts: list = []
        params: list = []
        if session_date:
            params.append(_parse_iso_date(session_date) if isinstance(session_date, str) else session_date)
            where_parts.append(f"session_date = ${len(params)}")
        else:
            params.append(range_days)
            where_parts.append(f"session_date >= CURRENT_DATE - ${len(params)} * INTERVAL '1 day'")
        if map_name:
            params.append(map_name)
            where_parts.append(f"map_name = ${len(params)}")
        if round_number is not None:
            params.append(round_number)
            where_parts.append(f"round_number = ${len(params)}")
        if round_start_unix is not None:
            params.append(round_start_unix)
            where_parts.append(f"round_start_unix = ${len(params)}")

        where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

        # Top objective runners grouped by engineer
        runner_rows = await db.fetch_all(
            f"""
            SELECT engineer_guid, MAX(engineer_name) AS engineer_name,
                   COUNT(*) AS total_runs,
                   COUNT(*) FILTER (WHERE run_type != 'denied') AS successful_runs,
                   COUNT(*) FILTER (WHERE run_type = 'denied') AS denied_runs,
                   COUNT(*) FILTER (WHERE run_type = 'solo') AS solo_runs,
                   COUNT(*) FILTER (WHERE run_type = 'assisted') AS assisted_runs,
                   COUNT(*) FILTER (WHERE run_type = 'team_effort') AS team_effort_runs,
                   COUNT(*) FILTER (WHERE run_type = 'unopposed') AS unopposed_runs,
                   SUM(self_kills) AS total_self_kills,
                   SUM(team_kills) AS total_team_kills,
                   AVG(NULLIF(path_efficiency, 0)) AS avg_path_efficiency,
                   COUNT(*) FILTER (WHERE action_type = 'dynamite_plant') AS plants,
                   COUNT(*) FILTER (WHERE action_type = 'objective_destroyed') AS destroys,
                   COUNT(*) FILTER (WHERE action_type = 'construction_complete') AS builds,
                   COUNT(*) FILTER (WHERE action_type = 'dynamite_defuse') AS defuses
            FROM proximity_objective_run
            {where_sql}
            GROUP BY engineer_guid
            ORDER BY COUNT(*) DESC
            LIMIT 20
            """,
            tuple(params),
        )
        objective_runners = [dict(r) for r in (runner_rows or [])]

        # Recent runs
        recent_rows = await db.fetch_all(
            f"""
            SELECT engineer_name, action_type, track_name, run_type,
                   self_kills, team_kills, nearby_teammates,
                   approach_time_ms, path_efficiency,
                   map_name, session_date, killer_name
            FROM proximity_objective_run
            {where_sql}
            ORDER BY session_date DESC, action_time DESC
            LIMIT 20
            """,
            tuple(params),
        )
        recent_runs = [dict(r) for r in (recent_rows or [])]
        for r in recent_runs:
            if r.get('session_date'):
                r['session_date'] = str(r['session_date'])

        # Summary aggregates
        summary_rows = await db.fetch_all(
            f"""
            SELECT COUNT(*) AS total_runs,
                   COUNT(*) FILTER (WHERE run_type = 'denied') AS total_denied,
                   COUNT(*) FILTER (WHERE run_type = 'solo') AS total_solo,
                   COUNT(*) FILTER (WHERE run_type = 'assisted') AS total_assisted,
                   COUNT(*) FILTER (WHERE run_type = 'team_effort') AS total_team_effort,
                   COUNT(*) FILTER (WHERE run_type = 'unopposed') AS total_unopposed,
                   AVG(NULLIF(path_efficiency, 0)) AS avg_path_efficiency
            FROM proximity_objective_run
            {where_sql}
            """,
            tuple(params),
        )
        summary = dict(summary_rows[0]) if summary_rows else {}

        # Most active objective
        top_track_rows = await db.fetch_all(
            f"""
            SELECT track_name, COUNT(*) AS cnt
            FROM proximity_objective_run
            {where_sql}
            AND track_name != ''
            GROUP BY track_name
            ORDER BY cnt DESC
            LIMIT 1
            """,
            tuple(params),
        )
        summary['most_active_objective'] = top_track_rows[0]['track_name'] if top_track_rows else None

        return {"status": "ok", "objective_runners": objective_runners, "recent_runs": recent_runs, "summary": summary}
    except Exception:
        logger.exception("objective-runs error")
        raise HTTPException(status_code=500, detail="objective-runs error")


@router.get("/proximity/objective-focus")
async def get_proximity_objective_focus(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    limit: int = 20,
    db: DatabaseAdapter = Depends(get_db),
):
    """Objective focus — time players spend near objectives."""
    try:
        if not await _table_column_exists(db, 'proximity_objective_focus', 'player_guid'):
            return {"status": "ok", "summary": {}, "players": [], "objectives": []}

        where_parts: list = []
        params: list = []
        if session_date:
            params.append(_parse_iso_date(session_date) if isinstance(session_date, str) else session_date)
            where_parts.append(f"session_date = ${len(params)}")
        else:
            params.append(range_days)
            where_parts.append(f"session_date >= CURRENT_DATE - ${len(params)} * INTERVAL '1 day'")
        if map_name:
            params.append(map_name)
            where_parts.append(f"map_name = ${len(params)}")
        if round_number is not None:
            params.append(round_number)
            where_parts.append(f"round_number = ${len(params)}")
        if round_start_unix is not None:
            params.append(round_start_unix)
            where_parts.append(f"round_start_unix = ${len(params)}")

        where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
        safe_limit = max(1, min(limit, 50))

        # Summary
        summary_row = await db.fetch_one(
            f"""
            SELECT COUNT(DISTINCT player_guid) AS unique_players,
                   COUNT(DISTINCT objective) AS objectives_tracked,
                   ROUND(AVG(time_within_radius_ms)::numeric / 1000, 1) AS avg_time_near_obj_s,
                   ROUND(AVG(avg_distance)::numeric, 0) AS avg_distance
            FROM proximity_objective_focus {where_sql}
            """,
            tuple(params),
        )
        summary = {
            "unique_players": int(summary_row[0] or 0) if summary_row else 0,
            "objectives_tracked": int(summary_row[1] or 0) if summary_row else 0,
            "avg_time_near_obj_s": float(summary_row[2] or 0) if summary_row else 0,
            "avg_distance": float(summary_row[3] or 0) if summary_row else 0,
        }

        # Player leaderboard — most objective-focused players
        player_rows = await db.fetch_all(
            f"""
            SELECT player_guid AS guid, MAX(player_name) AS name,
                   SUM(time_within_radius_ms) AS total_time_ms,
                   ROUND(AVG(avg_distance)::numeric, 0) AS avg_dist,
                   COUNT(DISTINCT objective) AS objectives_played,
                   SUM(samples) AS total_samples
            FROM proximity_objective_focus {where_sql}
            GROUP BY player_guid
            ORDER BY SUM(time_within_radius_ms) DESC
            LIMIT {safe_limit}
            """,
            tuple(params),
        )
        players = [
            {
                **dict(r),
                "total_time_s": round(int(r["total_time_ms"] or 0) / 1000, 1),
            }
            for r in (player_rows or [])
        ]

        # Per-objective breakdown
        obj_rows = await db.fetch_all(
            f"""
            SELECT objective, map_name,
                   COUNT(DISTINCT player_guid) AS players,
                   ROUND(AVG(time_within_radius_ms)::numeric / 1000, 1) AS avg_time_s,
                   ROUND(AVG(avg_distance)::numeric, 0) AS avg_dist
            FROM proximity_objective_focus {where_sql}
            GROUP BY objective, map_name
            ORDER BY AVG(time_within_radius_ms) DESC
            LIMIT 20
            """,
            tuple(params),
        )
        objectives = [dict(r) for r in (obj_rows or [])]

        return {"status": "ok", "summary": summary, "players": players, "objectives": objectives}
    except Exception:
        logger.exception("objective-focus error")
        raise HTTPException(status_code=500, detail="objective-focus error")
