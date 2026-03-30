"""Proximity position endpoints: hit-regions, hit-regions/by-weapon, hit-regions/headshot-rates, combat-positions/heatmap, combat-positions/kill-lines, combat-positions/danger-zones, combat-position-stats."""

import json

from fastapi import APIRouter, Depends, HTTPException

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.routers.proximity_helpers import (
    _build_proximity_where_clause,
    _table_column_exists,
    logger,
)

router = APIRouter()


@router.get("/proximity/hit-regions")
async def get_proximity_hit_regions(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    player_guid: str | None = None,
    weapon_id: int | None = None,
    limit: int = 20,
    db: DatabaseAdapter = Depends(get_db),
):
    """Per-player hit region breakdown — head/arms/body/legs distribution."""
    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
        player_guid=player_guid, player_guid_columns=["attacker_guid", "victim_guid"],
    )
    if weapon_id is not None:
        params.append(int(weapon_id))
        where_sql += f" AND weapon_id = ${len(params)}"
        scope["weapon_id"] = int(weapon_id)
    query_params = tuple(params)
    safe_limit = max(1, min(limit, 50))
    try:
        rows = await db.fetch_all(
            f"""
            SELECT attacker_guid, MAX(attacker_name) AS name,
                   SUM(CASE WHEN hit_region = 0 THEN 1 ELSE 0 END) AS head,
                   SUM(CASE WHEN hit_region = 1 THEN 1 ELSE 0 END) AS arms,
                   SUM(CASE WHEN hit_region = 2 THEN 1 ELSE 0 END) AS body,
                   SUM(CASE WHEN hit_region = 3 THEN 1 ELSE 0 END) AS legs,
                   COUNT(*) AS total_hits,
                   SUM(damage) AS total_damage
            FROM proximity_hit_region {where_sql}
            GROUP BY attacker_guid
            HAVING COUNT(*) >= 10
            ORDER BY COUNT(*) DESC
            LIMIT {safe_limit}
            """,
            query_params,
        )

        players = []
        for r in (rows or []):
            total = int(r[6] or 0)
            head = int(r[2] or 0)
            players.append({
                "guid": r[0],
                "name": r[1],
                "head": head,
                "arms": int(r[3] or 0),
                "body": int(r[4] or 0),
                "legs": int(r[5] or 0),
                "head_pct": round(head * 100.0 / total, 1) if total > 0 else 0,
                "total_hits": total,
                "total_damage": int(r[7] or 0),
            })

        return {
            "status": "ok",
            "scope": scope,
            "players": players,
        }
    except Exception:
        logger.warning("Proximity hit-regions error", exc_info=True)
        return {"status": "error", "detail": "Internal error"}


@router.get("/proximity/hit-regions/by-weapon")
async def get_proximity_hit_regions_by_weapon(
    range_days: int = 30,
    player_guid: str = "",
    session_date: str | None = None,
    map_name: str | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Per-weapon hit region breakdown for a specific player."""
    if not player_guid or not player_guid.strip():
        return {"status": "error", "detail": "player_guid is required"}
    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, None, None,
        player_guid=player_guid, player_guid_columns=["attacker_guid"],
    )
    query_params = tuple(params)
    try:
        rows = await db.fetch_all(
            f"""
            SELECT weapon_id,
                   SUM(CASE WHEN hit_region = 0 THEN 1 ELSE 0 END) AS head,
                   SUM(CASE WHEN hit_region = 1 THEN 1 ELSE 0 END) AS arms,
                   SUM(CASE WHEN hit_region = 2 THEN 1 ELSE 0 END) AS body,
                   SUM(CASE WHEN hit_region = 3 THEN 1 ELSE 0 END) AS legs,
                   COUNT(*) AS total,
                   SUM(damage) AS total_damage
            FROM proximity_hit_region {where_sql}
            GROUP BY weapon_id
            ORDER BY COUNT(*) DESC
            """,
            query_params,
        )

        weapons = []
        for r in (rows or []):
            total = int(r[5] or 0)
            head = int(r[1] or 0)
            weapons.append({
                "weapon_id": int(r[0] or 0),
                "head": head,
                "body": int(r[3] or 0),
                "arms": int(r[2] or 0),
                "legs": int(r[4] or 0),
                "total": total,
                "headshot_pct": round(head * 100.0 / total, 1) if total > 0 else 0,
                "total_damage": int(r[6] or 0),
            })

        return {
            "status": "ok",
            "scope": scope,
            "weapons": weapons,
        }
    except Exception:
        logger.warning("Proximity hit-regions by-weapon error", exc_info=True)
        return {"status": "error", "detail": "Internal error"}


@router.get("/proximity/hit-regions/headshot-rates")
async def get_proximity_hit_regions_headshot_rates(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    limit: int = 20,
    db: DatabaseAdapter = Depends(get_db),
):
    """Headshot percentage leaderboard — minimum 50 hits required."""
    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, None, None,
    )
    query_params = tuple(params)
    safe_limit = max(1, min(limit, 50))
    try:
        rows = await db.fetch_all(
            f"""
            SELECT attacker_guid, MAX(attacker_name) AS name,
                   SUM(CASE WHEN hit_region = 0 THEN 1 ELSE 0 END) AS head_hits,
                   COUNT(*) AS total_hits
            FROM proximity_hit_region {where_sql}
            GROUP BY attacker_guid
            HAVING COUNT(*) >= 50
            ORDER BY (SUM(CASE WHEN hit_region = 0 THEN 1 ELSE 0 END)::float
                     / NULLIF(COUNT(*), 0)) DESC NULLS LAST
            LIMIT {safe_limit}
            """,
            query_params,
        )

        leaders = []
        for r in (rows or []):
            total = int(r[3] or 0)
            head = int(r[2] or 0)
            leaders.append({
                "guid": r[0],
                "name": r[1],
                "headshot_pct": round(head * 100.0 / total, 1) if total > 0 else 0,
                "head_hits": head,
                "total_hits": total,
            })

        return {
            "status": "ok",
            "scope": scope,
            "leaders": leaders,
        }
    except Exception:
        logger.warning("Proximity hit-regions headshot-rates error", exc_info=True)
        return {"status": "error", "detail": "Internal error"}


@router.get("/proximity/combat-positions/heatmap")
async def get_proximity_combat_positions_heatmap(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    weapon_id: int | None = None,
    victim_class: str | None = None,
    perspective: str = "kills",
    team: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Combat position heatmap — grid-binned kill/death positions for map overlay."""
    if not map_name or not map_name.strip():
        raise HTTPException(status_code=400, detail="map_name is required")
    if perspective not in ("kills", "deaths"):
        raise HTTPException(status_code=400, detail="perspective must be 'kills' or 'deaths'")

    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
    )
    query_params_list = list(params)

    # Extra filters
    extra_clauses = []
    if weapon_id is not None:
        query_params_list.append(int(weapon_id))
        extra_clauses.append(f"AND weapon_id = ${len(query_params_list)}")
    if victim_class and victim_class.strip():
        query_params_list.append(victim_class.strip())
        extra_clauses.append(f"AND victim_class = ${len(query_params_list)}")
    if team and team.strip():
        team_val = team.strip()
        query_params_list.append(team_val)
        if perspective == "kills":
            extra_clauses.append(f"AND attacker_team = ${len(query_params_list)}")
        else:
            extra_clauses.append(f"AND victim_team = ${len(query_params_list)}")

    extra_sql = " ".join(extra_clauses)

    if perspective == "kills":
        x_col, y_col = "attacker_x", "attacker_y"
    else:
        x_col, y_col = "victim_x", "victim_y"

    query_params = tuple(query_params_list)
    try:
        rows = await db.fetch_all(
            f"""
            SELECT FLOOR({x_col} / 512.0)::int AS gx,
                   FLOOR({y_col} / 512.0)::int AS gy,
                   COUNT(*) AS cnt
            FROM proximity_combat_position {where_sql}
            {extra_sql}
            GROUP BY gx, gy
            ORDER BY cnt DESC
            """,
            query_params,
        )

        return {
            "status": "ok",
            "map_name": map_name.strip(),
            "grid_size": 512,
            "perspective": perspective,
            "hotzones": [
                {"x": int(r[0] or 0), "y": int(r[1] or 0), "count": int(r[2] or 0)}
                for r in (rows or [])
            ],
        }
    except Exception:
        logger.warning("Proximity combat-positions heatmap error", exc_info=True)
        return {"status": "error", "detail": "Internal error"}


@router.get("/proximity/combat-positions/kill-lines")
async def get_proximity_combat_positions_kill_lines(
    range_days: int = 30,
    map_name: str | None = None,
    weapon_id: int | None = None,
    attacker_guid: str | None = None,
    session_date: str | None = None,
    limit: int = 100,
    db: DatabaseAdapter = Depends(get_db),
):
    """Raw kill position pairs for drawing kill arrows on map overlay."""
    if not map_name or not map_name.strip():
        raise HTTPException(status_code=400, detail="map_name is required")

    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, None, None,
    )
    query_params_list = list(params)

    extra_clauses = []
    if weapon_id is not None:
        query_params_list.append(int(weapon_id))
        extra_clauses.append(f"AND weapon_id = ${len(query_params_list)}")
    if attacker_guid and attacker_guid.strip():
        query_params_list.append(attacker_guid.strip())
        extra_clauses.append(f"AND attacker_guid = ${len(query_params_list)}")

    extra_sql = " ".join(extra_clauses)
    safe_limit = max(1, min(limit, 500))
    query_params = tuple(query_params_list)

    try:
        rows = await db.fetch_all(
            f"""
            SELECT attacker_x, attacker_y, victim_x, victim_y,
                   weapon_id, attacker_team
            FROM proximity_combat_position {where_sql}
            {extra_sql}
            ORDER BY session_date DESC, event_time DESC
            LIMIT {safe_limit}
            """,
            query_params,
        )

        return {
            "status": "ok",
            "map_name": map_name.strip(),
            "lines": [
                {
                    "ax": int(r[0] or 0), "ay": int(r[1] or 0),
                    "vx": int(r[2] or 0), "vy": int(r[3] or 0),
                    "weapon_id": int(r[4] or 0),
                    "attacker_team": r[5] or "",
                }
                for r in (rows or [])
            ],
        }
    except Exception:
        logger.warning("Proximity combat-positions kill-lines error", exc_info=True)
        return {"status": "error", "detail": "Internal error"}


@router.get("/proximity/combat-positions/danger-zones")
async def get_proximity_combat_positions_danger_zones(
    range_days: int = 30,
    map_name: str | None = None,
    victim_class: str | None = None,
    session_date: str | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Danger zones — grid-binned death positions ranked by death count with class breakdown."""
    if not map_name or not map_name.strip():
        raise HTTPException(status_code=400, detail="map_name is required")

    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, None, None,
    )
    query_params_list = list(params)

    extra_clauses = []
    if victim_class and victim_class.strip():
        query_params_list.append(victim_class.strip())
        extra_clauses.append(f"AND victim_class = ${len(query_params_list)}")

    extra_sql = " ".join(extra_clauses)
    query_params = tuple(query_params_list)

    try:
        # Grid-binned deaths with JSON-aggregated class breakdown
        rows = await db.fetch_all(
            f"""
            SELECT gx, gy, deaths, class_counts
            FROM (
                SELECT gx, gy,
                       SUM(class_cnt) AS deaths,
                       jsonb_object_agg(vc, class_cnt) AS class_counts
                FROM (
                    SELECT FLOOR(victim_x / 512.0)::int AS gx,
                           FLOOR(victim_y / 512.0)::int AS gy,
                           COALESCE(victim_class, 'UNKNOWN') AS vc,
                           COUNT(*) AS class_cnt
                    FROM proximity_combat_position {where_sql}
                    {extra_sql}
                    GROUP BY FLOOR(victim_x / 512.0)::int,
                             FLOOR(victim_y / 512.0)::int,
                             COALESCE(victim_class, 'UNKNOWN')
                ) class_grid
                GROUP BY gx, gy
            ) agg
            ORDER BY deaths DESC
            """,
            query_params,
        )

        zones = []
        for r in (rows or []):
            classes_raw = r[3]
            if isinstance(classes_raw, str):
                classes_dict = json.loads(classes_raw)
            elif isinstance(classes_raw, dict):
                classes_dict = classes_raw
            else:
                classes_dict = {}
            # Ensure all values are ints
            classes_dict = {k: int(v) for k, v in classes_dict.items()}
            zones.append({
                "x": int(r[0] or 0),
                "y": int(r[1] or 0),
                "deaths": int(r[2] or 0),
                "classes": classes_dict,
            })

        return {
            "status": "ok",
            "map_name": map_name.strip(),
            "grid_size": 512,
            "zones": zones,
        }
    except Exception:
        logger.warning("Proximity combat-positions danger-zones error", exc_info=True)
        return {"status": "error", "detail": "Internal error"}


@router.get("/proximity/combat-position-stats")
async def get_proximity_combat_position_stats(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Combat position aggregate stats — kill distances, class matchups."""
    try:
        if not await _table_column_exists(db, 'proximity_combat_position', 'attacker_guid'):
            return {"status": "ok", "summary": {}, "by_class": [], "by_map": []}

        where_parts: list = []
        params: list = []
        if session_date:
            from website.backend.routers.proximity_helpers import _parse_iso_date
            params.append(_parse_iso_date(session_date) if isinstance(session_date, str) else session_date)
            where_parts.append(f"session_date = ${len(params)}")
        else:
            params.append(range_days)
            where_parts.append(f"session_date >= CURRENT_DATE - ${len(params)} * INTERVAL '1 day'")
        if map_name:
            params.append(map_name)
            where_parts.append(f"map_name = ${len(params)}")

        where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

        # Summary with kill distance stats
        summary_row = await db.fetch_one(
            f"""
            SELECT COUNT(*) AS total_kills,
                   ROUND(AVG(SQRT(
                       POWER(attacker_x - victim_x, 2) +
                       POWER(attacker_y - victim_y, 2) +
                       POWER(attacker_z - victim_z, 2)
                   ))::numeric, 0) AS avg_kill_distance,
                   ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY SQRT(
                       POWER(attacker_x - victim_x, 2) +
                       POWER(attacker_y - victim_y, 2) +
                       POWER(attacker_z - victim_z, 2)
                   ))::numeric, 0) AS median_kill_distance,
                   COUNT(DISTINCT attacker_guid) AS unique_attackers,
                   COUNT(DISTINCT map_name) AS maps_tracked
            FROM proximity_combat_position {where_sql}
            """,
            tuple(params),
        )
        summary = {
            "total_kills": int(summary_row[0] or 0) if summary_row else 0,
            "avg_kill_distance": float(summary_row[1] or 0) if summary_row else 0,
            "median_kill_distance": float(summary_row[2] or 0) if summary_row else 0,
            "unique_attackers": int(summary_row[3] or 0) if summary_row else 0,
            "maps_tracked": int(summary_row[4] or 0) if summary_row else 0,
        }

        # By attacker class
        class_rows = await db.fetch_all(
            f"""
            SELECT attacker_class AS class,
                   COUNT(*) AS kills,
                   ROUND(AVG(SQRT(
                       POWER(attacker_x - victim_x, 2) +
                       POWER(attacker_y - victim_y, 2) +
                       POWER(attacker_z - victim_z, 2)
                   ))::numeric, 0) AS avg_distance
            FROM proximity_combat_position {where_sql}
            AND attacker_class IS NOT NULL AND attacker_class != ''
            GROUP BY attacker_class
            ORDER BY COUNT(*) DESC
            """,
            tuple(params),
        )
        by_class = [dict(r) for r in (class_rows or [])]

        # By map
        map_rows = await db.fetch_all(
            f"""
            SELECT map_name,
                   COUNT(*) AS kills,
                   ROUND(AVG(SQRT(
                       POWER(attacker_x - victim_x, 2) +
                       POWER(attacker_y - victim_y, 2) +
                       POWER(attacker_z - victim_z, 2)
                   ))::numeric, 0) AS avg_distance
            FROM proximity_combat_position {where_sql}
            GROUP BY map_name
            ORDER BY COUNT(*) DESC
            """,
            tuple(params),
        )
        by_map = [dict(r) for r in (map_rows or [])]

        return {"status": "ok", "summary": summary, "by_class": by_class, "by_map": by_map}
    except Exception:
        logger.error("combat-position-stats error", exc_info=True)
        return {"status": "error", "message": "Internal error", "summary": {}, "by_class": [], "by_map": []}
