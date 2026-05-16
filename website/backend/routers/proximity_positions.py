"""Proximity position endpoints: hit-regions, hit-regions/by-weapon, hit-regions/headshot-rates, combat-positions/heatmap, player-heatmap (per-player, multi-mode), combat-positions/kill-lines, combat-positions/danger-zones, combat-position-stats."""

import json
import logging
import math

from fastapi import APIRouter, Depends, HTTPException

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.routers.api_helpers import handle_router_errors
from website.backend.routers.proximity_helpers import (
    ProximityQueryBuilder,
    _build_proximity_where_clause,
    _load_scoped_guid_name_map,
    _resolve_name_for_guid,
    _table_column_exists,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Per-player heatmap mode -> (source table, x column, y column, guid column, coverage note).
# Names are internal constants (never user input) -> safe to interpolate into SQL.
_PLAYER_HEATMAP_MODES: dict[str, dict[str, str | None]] = {
    "kills_from": {
        "table": "proximity_combat_position",
        "x": "attacker_x", "y": "attacker_y",
        "guid_col": "attacker_guid", "coverage": None,
    },
    "victims_die": {
        "table": "proximity_combat_position",
        "x": "victim_x", "y": "victim_y",
        "guid_col": "attacker_guid", "coverage": None,
    },
    "player_dies": {
        "table": "proximity_combat_position",
        "x": "victim_x", "y": "victim_y",
        "guid_col": "victim_guid", "coverage": "kills_only",
    },
    "presence": {
        "table": "player_track",
        "x": None, "y": None,
        "guid_col": "player_guid", "coverage": None,
    },
    # v9 true-aim (Lua 6.02). Empty until the Lua feature is enabled +
    # deployed (separate HARD STOP) — handled by the combat branch.
    "aim": {
        "table": "proximity_shot_fired",
        "x": "origin_x", "y": "origin_y",
        "guid_col": "guid", "coverage": None,
    },
}


async def _resolve_player_guid_canonical(
    db: DatabaseAdapter,
    raw_guid: str,
    table: str,
    guid_col: str,
    where_sql: str,
    params: tuple,
) -> str:
    """Resolve an 8-char short (or partial) GUID to the 32-char canonical form
    stored in the proximity tables. Accepts an already-canonical 32-char input
    as-is. Falls back to the raw prefix on miss (yields an empty result set
    rather than a 500). `table`/`guid_col` come from `_PLAYER_HEATMAP_MODES`
    (internal constants), so interpolation here is safe."""
    g = (raw_guid or "").strip().upper()
    if len(g) >= 32:
        return g
    try:
        row = await db.fetch_val(
            f"SELECT {guid_col} FROM {table} {where_sql} "
            f"AND LEFT({guid_col}, 8) = ${len(params) + 1} LIMIT 1",
            tuple(list(params) + [g[:8]]),
        )
    except Exception:
        logger.warning("player-heatmap GUID resolution failed for %s", g[:8], exc_info=True)
        row = None
    return str(row) if row else g


@router.get("/proximity/hit-regions")
@handle_router_errors("Proximity hit-regions error")
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


@router.get("/proximity/hit-regions/by-weapon")
@handle_router_errors("Proximity hit-regions by-weapon error")
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


@router.get("/proximity/hit-regions/headshot-rates")
@handle_router_errors("Proximity hit-regions headshot-rates error")
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


@router.get("/proximity/combat-positions/heatmap")
@handle_router_errors("Proximity combat-positions heatmap error")
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


@router.get("/proximity/player-heatmap")
@handle_router_errors("Proximity player-heatmap error")
async def get_proximity_player_heatmap(
    map_name: str | None = None,
    mode: str | None = None,
    player_guid: str | None = None,
    range_days: int = 30,
    session_date: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    weapon_id: int | None = None,
    grid_size: int = 512,
    db: DatabaseAdapter = Depends(get_db),
):
    """Per-player, multi-perspective combat heatmap for a single map.

    modes:
      - kills_from   : where this player is standing when they get kills
      - victims_die  : where this player's victims die (player = attacker)
      - player_dies  : where this player dies (kills-by-enemy only; world/
                       suicide deaths are NOT tracked -> coverage="kills_only")
      - presence     : where this player spends time (player_track path,
                       server-side stride-downsampled, never raw)

    Response intentionally mirrors /proximity/combat-positions/heatmap
    ({x,y,count} / grid_size) so the React HeatmapCanvas and the legacy
    renderer can consume it unchanged.
    """
    if not map_name or not map_name.strip():
        raise HTTPException(status_code=400, detail="map_name is required")
    mode_key = (mode or "").strip()
    if mode_key not in _PLAYER_HEATMAP_MODES:
        raise HTTPException(
            status_code=400,
            detail="mode must be one of: kills_from, victims_die, player_dies, presence, aim",
        )
    if not player_guid or not player_guid.strip():
        raise HTTPException(status_code=400, detail="player_guid is required")

    cfg = _PLAYER_HEATMAP_MODES[mode_key]
    table = str(cfg["table"])
    guid_col = str(cfg["guid_col"])
    g = float(max(128, min(int(grid_size or 512), 1024)))
    g_int = int(g)

    # Base scope WHERE (no player filter) — used for GUID resolution + name map.
    # Unaliased: the resolver and _load_scoped_guid_name_map both query the
    # source table without an alias; the presence query aliases player_track
    # as `pt` but the WHERE columns stay unambiguous (only pt has them).
    base_where, base_params, _ = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
    )
    base_params_t = tuple(base_params)

    canonical = await _resolve_player_guid_canonical(
        db, player_guid, table, guid_col, base_where, base_params_t,
    )
    name_map = await _load_scoped_guid_name_map(db, base_where, base_params_t)
    player_name = _resolve_name_for_guid(canonical, name_map)

    # Final WHERE with the per-player filter routed through the helper's
    # built-in player_guid binding (A2 fix: the old heatmap never did this).
    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
        player_guid=canonical, player_guid_columns=[guid_col],
    )
    params_list = list(params)
    sampled = False

    if mode_key == "presence":
        total_samples = await db.fetch_val(
            f"SELECT COALESCE(SUM(sample_count), 0) FROM player_track pt {where_sql}",
            tuple(params_list),
        )
        total_samples = int(total_samples or 0)
        stride = max(1, math.ceil(total_samples / 8000)) if total_samples else 1
        sampled = stride > 1
        rows = await db.fetch_all(
            f"""
            SELECT FLOOR((elem->>'x')::numeric / {g})::int AS gx,
                   FLOOR((elem->>'y')::numeric / {g})::int AS gy,
                   COUNT(*) AS cnt
            FROM player_track pt,
                 LATERAL jsonb_array_elements(pt.path) WITH ORDINALITY AS t(elem, ord)
            {where_sql}
              AND (t.ord % {stride}) = 0
              AND (elem->>'x') IS NOT NULL AND (elem->>'y') IS NOT NULL
            GROUP BY gx, gy
            ORDER BY cnt DESC
            """,
            tuple(params_list),
        )
    else:
        x_col, y_col = str(cfg["x"]), str(cfg["y"])
        extra_sql = ""
        if weapon_id is not None:
            params_list.append(int(weapon_id))
            extra_sql = f"AND weapon_id = ${len(params_list)}"
        rows = await db.fetch_all(
            f"""
            SELECT FLOOR({x_col} / {g})::int AS gx,
                   FLOOR({y_col} / {g})::int AS gy,
                   COUNT(*) AS cnt
            FROM {table} {where_sql}
            {extra_sql}
            GROUP BY gx, gy
            ORDER BY cnt DESC
            """,
            tuple(params_list),
        )

    hotzones = [
        {"x": int(r[0] or 0), "y": int(r[1] or 0), "count": int(r[2] or 0)}
        for r in (rows or [])
    ]
    total = sum(z["count"] for z in hotzones)

    result = {
        "status": "ok",
        "map_name": map_name.strip(),
        "mode": mode_key,
        "grid_size": g_int,
        "player_guid": canonical,
        "player_name": player_name,
        "hotzones": hotzones,
        "total": total,
        "sampled": sampled,
        "scope": scope,
    }
    if cfg["coverage"]:
        result["coverage"] = cfg["coverage"]
    return result


@router.get("/proximity/combat-positions/kill-lines")
@handle_router_errors("Proximity combat-positions kill-lines error")
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


@router.get("/proximity/combat-positions/danger-zones")
@handle_router_errors("Proximity combat-positions danger-zones error")
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


@router.get("/proximity/combat-position-stats")
@handle_router_errors("combat-position-stats error")
async def get_proximity_combat_position_stats(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Combat position aggregate stats — kill distances, class matchups."""
    if not await _table_column_exists(db, 'proximity_combat_position', 'attacker_guid'):
        return {"status": "ok", "summary": {}, "by_class": [], "by_map": []}

    where_sql, params = (
        ProximityQueryBuilder()
        .with_session_scope(session_date, range_days)
        .with_map_name(map_name)
        .build()
    )

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
