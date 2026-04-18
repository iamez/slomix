"""Proximity teamplay endpoints: teamplay, spawn-timing, cohesion, crossfire-angles, pushes, lua-trades, focus-fire."""

from fastapi import APIRouter, Depends

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.routers.api_helpers import handle_router_errors
from website.backend.routers.proximity_helpers import (
    _build_proximity_where_clause,
    _compute_scoped_teamplay,
    _load_scoped_guid_name_map,
    _parse_iso_date,
    _proximity_stub_meta,
    _table_column_exists,
    logger,
)

router = APIRouter()


@router.get("/proximity/teamplay")
async def get_proximity_teamplay(
    range_days: int = 30,
    limit: int = 5,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Teamplay leaders computed from scoped combat engagements.
    """
    payload = _proximity_stub_meta(range_days)
    safe_limit = max(1, min(int(limit or 5), 25))
    where_sql, params, scope = _build_proximity_where_clause(
        range_days,
        session_date,
        map_name,
        round_number,
        round_start_unix,
    )

    try:
        guid_name_map = await _load_scoped_guid_name_map(db, where_sql, tuple(params))
        scoped_params = list(params)
        scoped_params.append(6000)
        rows = await db.fetch_all(
            "SELECT target_guid, target_name, outcome, num_attackers, is_crossfire, "
            "crossfire_delay_ms, attackers, crossfire_participants "
            f"FROM combat_engagement {where_sql} "
            "ORDER BY session_date DESC, round_start_unix DESC, start_time_ms DESC "
            f"LIMIT ${len(scoped_params)}",
            tuple(scoped_params),
        )

        computed = _compute_scoped_teamplay(rows, safe_limit, guid_name_map=guid_name_map)
        ready = bool(
            computed["crossfire_kills"] or computed["sync"] or computed["focus_survival"]
        )
        payload.update(
            {
                "status": "ok" if ready else "prototype",
                "ready": ready,
                "message": None if ready else payload["message"],
                "scope": scope,
                "limit": safe_limit,
                "sampled_engagements": len(rows),
                "crossfire_kills": computed["crossfire_kills"],
                "sync": computed["sync"],
                "focus_survival": computed["focus_survival"],
            }
        )
    except Exception:
        logger.exception("Proximity teamplay query failed")
        payload.update(
            {
                "status": "error",
                "ready": False,
                "message": "Proximity query failed",
                "scope": scope,
                "limit": safe_limit,
                "crossfire_kills": [],
                "sync": [],
                "focus_survival": [],
            }
        )
    return payload


@router.get("/proximity/spawn-timing")
@handle_router_errors("Proximity endpoint error")
async def get_proximity_spawn_timing(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    player_guid: str | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Spawn timing efficiency leaderboard and team averages."""
    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
        player_guid=player_guid, player_guid_columns=["killer_guid", "victim_guid"],
    )
    query_params = tuple(params)
    leaders = await db.fetch_all(
        f"""
        SELECT killer_guid, MAX(killer_name) AS name,
               ROUND(AVG(spawn_timing_score)::numeric, 3) AS avg_score,
               COUNT(*) AS kills,
               ROUND(AVG(time_to_next_spawn)::numeric, 0) AS avg_denial_ms
        FROM proximity_spawn_timing {where_sql}
        GROUP BY killer_guid
        HAVING COUNT(*) >= 3
        ORDER BY avg_score DESC
        LIMIT 20
        """,
        query_params,
    )
    team_avgs = await db.fetch_all(
        f"""
        SELECT killer_team AS team,
               ROUND(AVG(spawn_timing_score)::numeric, 3) AS avg_score,
               COUNT(*) AS total_kills
        FROM proximity_spawn_timing {where_sql}
        GROUP BY killer_team
        ORDER BY killer_team
        """,
        query_params,
    )
    total_row = await db.fetch_one(
        f"SELECT COUNT(*) FROM proximity_spawn_timing {where_sql}",
        query_params,
    )
    return {
        "status": "ok",
        "scope": scope,
        "total_events": int(total_row[0]) if total_row else 0,
        "leaders": [
            {
                "guid": r[0], "name": r[1],
                "avg_score": float(r[2] or 0), "kills": int(r[3] or 0),
                "avg_denial_ms": int(r[4] or 0),
            }
            for r in (leaders or [])
        ],
        "team_averages": [
            {"team": r[0], "avg_score": float(r[1] or 0), "total_kills": int(r[2] or 0)}
            for r in (team_avgs or [])
        ],
    }

@router.get("/proximity/cohesion")
@handle_router_errors("Proximity endpoint error")
async def get_proximity_cohesion(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Team cohesion: dispersion summary, timeline, and buddy pairs."""
    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
    )
    query_params = tuple(params)
    team_summary = await db.fetch_all(
        f"""
        SELECT team,
               ROUND(AVG(dispersion)::numeric, 1) AS avg_dispersion,
               ROUND(AVG(max_spread)::numeric, 1) AS avg_max_spread,
               ROUND(AVG(straggler_count)::numeric, 2) AS avg_stragglers,
               ROUND(AVG(alive_count)::numeric, 1) AS avg_alive,
               COUNT(*) AS samples
        FROM proximity_team_cohesion {where_sql}
        GROUP BY team ORDER BY team
        """,
        query_params,
    )
    # Sampled timeline (limit to avoid huge payloads)
    timeline = await db.fetch_all(
        f"""
        SELECT sample_time, team, dispersion
        FROM proximity_team_cohesion {where_sql}
        ORDER BY sample_time
        LIMIT 2000
        """,
        query_params,
    )
    buddy_pairs = await db.fetch_all(
        f"""
        SELECT buddy_pair_guids, COUNT(*) AS times_paired,
               ROUND(AVG(buddy_distance)::numeric, 1) AS avg_distance
        FROM proximity_team_cohesion {where_sql}
        AND buddy_pair_guids IS NOT NULL AND buddy_pair_guids != ''
        GROUP BY buddy_pair_guids
        ORDER BY times_paired DESC
        LIMIT 10
        """,
        query_params,
    )
    return {
        "status": "ok",
        "scope": scope,
        "team_summary": [
            {
                "team": r[0],
                "avg_dispersion": float(r[1] or 0),
                "avg_max_spread": float(r[2] or 0),
                "avg_stragglers": float(r[3] or 0),
                "avg_alive": float(r[4] or 0),
                "samples": int(r[5] or 0),
            }
            for r in (team_summary or [])
        ],
        "timeline": [
            {"time": int(r[0] or 0), "team": r[1], "dispersion": float(r[2] or 0)}
            for r in (timeline or [])
        ],
        "buddy_pairs": [
            {"guids": r[0], "times_paired": int(r[1] or 0), "avg_distance": float(r[2] or 0)}
            for r in (buddy_pairs or [])
        ],
    }

@router.get("/proximity/crossfire-angles")
@handle_router_errors("Proximity endpoint error")
async def get_proximity_crossfire_angles(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    player_guid: str | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Crossfire opportunity analysis: utilization rate, angle buckets, top duos."""
    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
        player_guid=player_guid, player_guid_columns=["teammate1_guid", "teammate2_guid"],
    )
    query_params = tuple(params)
    summary = await db.fetch_one(
        f"""
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN was_executed THEN 1 ELSE 0 END) AS executed,
               ROUND(AVG(angular_separation)::numeric, 1) AS avg_angle,
               ROUND(AVG(damage_within_window)::numeric, 0) AS avg_damage
        FROM proximity_crossfire_opportunity {where_sql}
        """,
        query_params,
    )
    total = int(summary[0] or 0) if summary else 0
    executed = int(summary[1] or 0) if summary else 0
    avg_angle = float(summary[2] or 0) if summary else 0
    avg_damage = int(summary[3] or 0) if summary else 0
    util_rate = round(executed / total * 100, 1) if total > 0 else 0

    angle_buckets = await db.fetch_all(
        f"""
        SELECT
            CASE
                WHEN angular_separation < 60 THEN 'narrow (< 60)'
                WHEN angular_separation < 90 THEN 'medium (60-90)'
                WHEN angular_separation < 120 THEN 'wide (90-120)'
                ELSE 'flanking (120+)'
            END AS bucket,
            COUNT(*) AS count,
            SUM(CASE WHEN was_executed THEN 1 ELSE 0 END) AS executed
        FROM proximity_crossfire_opportunity {where_sql}
        GROUP BY 1
        ORDER BY MIN(angular_separation)
        """,
        query_params,
    )
    top_duos = await db.fetch_all(
        f"""
        SELECT teammate1_guid, teammate2_guid,
               COUNT(*) AS executions,
               ROUND(AVG(angular_separation)::numeric, 1) AS avg_angle
        FROM proximity_crossfire_opportunity {where_sql}
        AND was_executed = TRUE
        GROUP BY teammate1_guid, teammate2_guid
        ORDER BY executions DESC
        LIMIT 10
        """,
        query_params,
    )
    return {
        "status": "ok",
        "scope": scope,
        "total_opportunities": total,
        "executed": executed,
        "utilization_rate_pct": util_rate,
        "avg_angle": avg_angle,
        "avg_damage": avg_damage,
        "angle_buckets": [
            {"bucket": r[0], "count": int(r[1] or 0), "executed": int(r[2] or 0)}
            for r in (angle_buckets or [])
        ],
        "top_duos": [
            {
                "teammate1_guid": r[0], "teammate2_guid": r[1],
                "executions": int(r[2] or 0), "avg_angle": float(r[3] or 0),
            }
            for r in (top_duos or [])
        ],
    }

@router.get("/proximity/pushes")
@handle_router_errors("Proximity endpoint error")
async def get_proximity_pushes(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    player_guid: str | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Team push analysis: per-team summary and quality distribution."""
    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
        player_guid=player_guid, player_guid_columns=["team"],
    )
    query_params = tuple(params)
    team_summary = await db.fetch_all(
        f"""
        SELECT team,
               COUNT(*) AS pushes,
               ROUND(AVG(push_quality)::numeric, 3) AS avg_quality,
               ROUND(AVG(alignment_score)::numeric, 3) AS avg_alignment,
               ROUND(AVG(avg_speed)::numeric, 1) AS avg_speed,
               ROUND(AVG(participant_count)::numeric, 1) AS avg_participants,
               SUM(CASE WHEN toward_objective NOT IN ('NO', 'N/A') THEN 1 ELSE 0 END) AS obj_pushes
        FROM proximity_team_push {where_sql}
        GROUP BY team ORDER BY team
        """,
        query_params,
    )
    quality_dist = await db.fetch_all(
        f"""
        SELECT
            CASE
                WHEN push_quality < 0.2 THEN 'low (< 0.2)'
                WHEN push_quality < 0.5 THEN 'medium (0.2-0.5)'
                WHEN push_quality < 0.8 THEN 'high (0.5-0.8)'
                ELSE 'excellent (0.8+)'
            END AS tier,
            team, COUNT(*) AS count
        FROM proximity_team_push {where_sql}
        GROUP BY 1, team
        ORDER BY MIN(push_quality), team
        """,
        query_params,
    )
    return {
        "status": "ok",
        "scope": scope,
        "team_summary": [
            {
                "team": r[0], "pushes": int(r[1] or 0),
                "avg_quality": float(r[2] or 0),
                "avg_alignment": float(r[3] or 0),
                "avg_speed": float(r[4] or 0),
                "avg_participants": float(r[5] or 0),
                "objective_pushes": int(r[6] or 0),
            }
            for r in (team_summary or [])
        ],
        "quality_distribution": [
            {"tier": r[0], "team": r[1], "count": int(r[2] or 0)}
            for r in (quality_dist or [])
        ],
    }

@router.get("/proximity/lua-trades")
@handle_router_errors("Proximity endpoint error")
async def get_proximity_lua_trades(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    player_guid: str | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Lua-detected trade kill analysis."""
    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
        player_guid=player_guid, player_guid_columns=["trader_guid", "original_killer_guid", "original_victim_guid"],
    )
    query_params = tuple(params)
    leaders = await db.fetch_all(
        f"""
        SELECT trader_guid, MAX(trader_name) AS name,
               COUNT(*) AS trades,
               ROUND(AVG(delta_ms)::numeric, 0) AS avg_reaction,
               MIN(delta_ms) AS fastest
        FROM proximity_lua_trade_kill {where_sql}
        GROUP BY trader_guid
        ORDER BY trades DESC
        LIMIT 20
        """,
        query_params,
    )
    recent = await db.fetch_all(
        f"""
        SELECT original_victim_name, original_killer_name, trader_name,
               delta_ms, map_name, session_date
        FROM proximity_lua_trade_kill {where_sql}
        ORDER BY session_date DESC, traded_kill_time DESC
        LIMIT 10
        """,
        query_params,
    )
    speed_dist = await db.fetch_all(
        f"""
        SELECT
            CASE
                WHEN delta_ms < 500 THEN 'instant (< 500ms)'
                WHEN delta_ms < 1000 THEN 'fast (500-1000ms)'
                WHEN delta_ms < 2000 THEN 'normal (1-2s)'
                ELSE 'slow (2s+)'
            END AS tier,
            COUNT(*) AS count
        FROM proximity_lua_trade_kill {where_sql}
        GROUP BY 1
        ORDER BY MIN(delta_ms)
        """,
        query_params,
    )
    return {
        "status": "ok",
        "scope": scope,
        "leaders": [
            {
                "guid": r[0], "name": r[1],
                "trades": int(r[2] or 0),
                "avg_reaction_ms": int(r[3] or 0),
                "fastest_ms": int(r[4] or 0),
            }
            for r in (leaders or [])
        ],
        "recent_trades": [
            {
                "victim": r[0], "killer": r[1], "trader": r[2],
                "delta_ms": int(r[3] or 0), "map": r[4],
                "date": str(r[5]) if r[5] else None,
            }
            for r in (recent or [])
        ],
        "speed_distribution": [
            {"tier": r[0], "count": int(r[1] or 0)}
            for r in (speed_dist or [])
        ],
    }

@router.get("/proximity/focus-fire")
@handle_router_errors("focus-fire error")
async def get_proximity_focus_fire(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    limit: int = 20,
    db: DatabaseAdapter = Depends(get_db),
):
    """Focus fire intelligence — coordinated multi-attacker damage bursts."""
    if not await _table_column_exists(db, 'proximity_focus_fire', 'target_guid'):
        return {"status": "ok", "summary": {}, "targets": [], "recent": []}

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
        SELECT COUNT(*) AS total_events,
               ROUND(AVG(focus_score)::numeric, 2) AS avg_score,
               ROUND(AVG(attacker_count)::numeric, 1) AS avg_attackers,
               ROUND(AVG(total_damage)::numeric, 0) AS avg_damage,
               ROUND(AVG(duration)::numeric, 0) AS avg_duration_ms
        FROM proximity_focus_fire {where_sql}
        """,
        tuple(params),
    )
    summary = {
        "total_events": int(summary_row[0] or 0) if summary_row else 0,
        "avg_score": float(summary_row[1] or 0) if summary_row else 0,
        "avg_attackers": float(summary_row[2] or 0) if summary_row else 0,
        "avg_damage": float(summary_row[3] or 0) if summary_row else 0,
        "avg_duration_ms": float(summary_row[4] or 0) if summary_row else 0,
    }

    # Most targeted players
    target_rows = await db.fetch_all(
        f"""
        SELECT target_guid AS guid, MAX(target_name) AS name,
               COUNT(*) AS times_focused,
               ROUND(AVG(focus_score)::numeric, 2) AS avg_score,
               SUM(total_damage) AS total_damage_taken,
               ROUND(AVG(attacker_count)::numeric, 1) AS avg_attackers
        FROM proximity_focus_fire {where_sql}
        GROUP BY target_guid
        ORDER BY COUNT(*) DESC
        LIMIT {safe_limit}
        """,
        tuple(params),
    )
    targets = [dict(r) for r in (target_rows or [])]

    # Recent high-score events
    recent_rows = await db.fetch_all(
        f"""
        SELECT target_name, attacker_count, total_damage, duration,
               focus_score, map_name, session_date
        FROM proximity_focus_fire {where_sql}
        ORDER BY focus_score DESC, session_date DESC
        LIMIT 15
        """,
        tuple(params),
    )
    recent = [dict(r) for r in (recent_rows or [])]

    return {"status": "ok", "summary": summary, "targets": targets, "recent": recent}
