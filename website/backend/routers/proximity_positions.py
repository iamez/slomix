"""Proximity position endpoints: hit-regions, hit-regions/by-weapon, hit-regions/headshot-rates, combat-positions/heatmap, player-heatmap (per-player, multi-mode), combat-positions/kill-lines, combat-positions/danger-zones, combat-position-stats."""

import json
import logging
import math
import re

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

# ===== Full Aim Analytics (Phase 1: positional/directional) =====
# Narrative thresholds (kept here so they are visible + unit-testable).
_AIM_YAW_BUCKETS = 16            # 16 x 22.5 deg
_AIM_YAW_BUCKET_DEG = 360.0 / _AIM_YAW_BUCKETS
_AIM_LOW_N = 40                  # below this the directional read is rough
_AIM_TIGHT_DEG = 25.0            # circular std < this -> "very tight"
_AIM_WIDE_DEG = 60.0             # circular std > this -> "wide"
_AIM_PITCH_FLAT_DEG = 8.0        # |mean pitch| <= this -> "level"
_AIM_SECTOR_MIN_FRAC = 0.22      # dominant sector must be >= this share
_AIM_RAYLEIGH_ALPHA = 0.05       # p < this -> aim is directional
# ET world yaw convention: 0 deg = +X (East), 90 = +Y (North),
# +/-180 = West, -90 = South. 8 sectors of 45 deg, centred on the axis.
_AIM_SECTORS = ("E", "NE", "N", "NW", "W", "SW", "S", "SE")


def _aim_yaw_bucket_center_deg(i: int) -> float:
    """Centre yaw (deg, in (-180,180]) of 0-based rose bucket *i*.

    The SQL bucketises ((yaw+180) mod 360) into 16 bands of 22.5 deg, so
    bucket i covers shifted-angle [i*22.5, (i+1)*22.5); original yaw =
    shifted - 180.
    """
    shifted_center = (i + 0.5) * _AIM_YAW_BUCKET_DEG
    yaw = shifted_center - 180.0
    if yaw > 180.0:
        yaw -= 360.0
    return yaw


def _rose_circular(rose: list[int]) -> tuple[float, float]:
    """Circular mean yaw (deg) + resultant length R (0..1) from a 16-bucket
    rose. Wrap-safe (unit-vector sum); never an arithmetic mean of angles."""
    total = sum(rose)
    if total <= 0:
        return 0.0, 0.0
    sx = 0.0
    sy = 0.0
    for i, c in enumerate(rose):
        if not c:
            continue
        th = math.radians(_aim_yaw_bucket_center_deg(i))
        sx += c * math.cos(th)
        sy += c * math.sin(th)
    cbar = sx / total
    sbar = sy / total
    r = math.hypot(cbar, sbar)
    mean_yaw = math.degrees(math.atan2(sbar, cbar))
    if mean_yaw > 180.0:
        mean_yaw -= 360.0
    elif mean_yaw <= -180.0:
        mean_yaw += 360.0
    return round(mean_yaw, 2), round(min(1.0, max(0.0, r)), 4)


def _circular_yaw_stats(sin_mean: float, cos_mean: float, n: int) -> dict:
    """Wrap-safe circular statistics for yaw (deg, wraps at +/-180).

    An arithmetic mean of yaw is WRONG: 170 and -170 average to 0 but the
    true mean direction is ~180. Standard unit-vector approach:
      mean angle = atan2(mean sin, mean cos)
      R (mean resultant length) = hypot(mean cos, mean sin) in [0,1]
      circular std (deg) ~= deg(sqrt(-2 ln R))
      Rayleigh test of uniformity: Z = n*R^2, p ~= exp(-Z) with the
        first-order small-sample correction (Zar, Biostatistical Analysis).
    `sin_mean`/`cos_mean` are AVG(SIN(RADIANS(yaw)))/AVG(COS(RADIANS(yaw))).
    pitch does NOT wrap ([-90,90]) — its arithmetic mean/std are correct and
    handled by the caller, not here.
    """
    if n <= 0:
        return {
            "n": 0, "mean_yaw_deg": 0.0, "resultant_length": 0.0,
            "circular_std_deg": 180.0, "rayleigh_p": 1.0,
        }
    mean_yaw = math.degrees(math.atan2(sin_mean, cos_mean))
    if mean_yaw > 180.0:
        mean_yaw -= 360.0
    elif mean_yaw <= -180.0:
        mean_yaw += 360.0
    r = min(1.0, math.hypot(cos_mean, sin_mean))   # hypot is already >= 0
    if r >= 1.0 - 1e-12:
        # Perfectly concentrated: std=0. Also avoids log(near-1) ~ 0
        # numerical noise via an explicit branch.
        circ_std = 0.0
    else:
        # Safe log via a floor; when r -> 0 the formula naturally produces
        # a huge value which `min(180, ...)` caps — that is the canonical
        # "fully uniform" answer (no separate elif branch needed).
        circ_std = min(180.0, math.degrees(math.sqrt(-2.0 * math.log(max(r, 1e-12)))))
    z = n * r * r
    try:
        p = math.exp(-z) * (1.0 + (2.0 * z - z * z) / (4.0 * n))
    except (OverflowError, ValueError):
        p = 0.0
    p = min(1.0, max(0.0, p))
    return {
        "n": int(n),
        "mean_yaw_deg": round(mean_yaw, 2),
        "resultant_length": round(r, 4),
        "circular_std_deg": round(circ_std, 2),
        "rayleigh_p": round(p, 6),
    }


def _aim_dominant_sector(global_rose: list[int]) -> tuple[str, float]:
    """Fold the 16-bucket global rose into 8 named 45 deg sectors; return
    (sector, fraction) of the strongest. ('', 0.0) if empty."""
    total = sum(global_rose)
    if total <= 0:
        return "", 0.0
    sect = [0] * 8
    for i, c in enumerate(global_rose):
        if not c:
            continue
        yaw = _aim_yaw_bucket_center_deg(i)
        # shift so E sector (centred on 0) maps cleanly: idx 0=E..7=SE
        idx = int(((yaw + 22.5) % 360.0) // 45.0)
        sect[idx] += c
    best = max(range(8), key=lambda k: sect[k])
    return _AIM_SECTORS[best], sect[best] / total


def _build_aim_narrative(
    circ: dict, pitch_mean: float, global_rose: list[int],
) -> list[str]:
    """Storytelling-with-numbers lines from real stats only (no fabricated
    'centre'); each line is defensible."""
    n = int(circ.get("n", 0))
    out = [f"{n:,} shots tracked"]
    if n <= 0:
        return out
    if n < _AIM_LOW_N:
        out.append("Low sample — directional read is rough.")
        return out
    p = float(circ.get("rayleigh_p", 1.0))
    if p < _AIM_RAYLEIGH_ALPHA:
        sector, frac = _aim_dominant_sector(global_rose)
        if sector and frac >= _AIM_SECTOR_MIN_FRAC:
            out.append(f"Most shots aimed {sector} ({frac:.0%} of fire)")
        else:
            out.append("Directional, but fire is spread across angles")
    else:
        out.append("No dominant aim direction (statistically uniform)")
    std = float(circ.get("circular_std_deg", 180.0))
    if std < _AIM_TIGHT_DEG:
        out.append(f"Very tight horizontal aim (±{std:.0f}°) — holds an angle")
    elif std > _AIM_WIDE_DEG:
        out.append(f"Wide horizontal coverage (±{std:.0f}°) — sweeps the area")
    else:
        out.append(f"Moderate horizontal spread (±{std:.0f}°)")
    if pitch_mean > _AIM_PITCH_FLAT_DEG:
        out.append(f"Tends to aim up (avg {pitch_mean:+.0f}° pitch)")
    elif pitch_mean < -_AIM_PITCH_FLAT_DEG:
        out.append(f"Tends to aim down (avg {pitch_mean:+.0f}° pitch)")
    else:
        out.append(f"Level aim (avg {pitch_mean:+.0f}° pitch)")
    return out


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
    # GUIDs are uppercase hex; strip anything else so the query bind can
    # never carry user-controlled chars. The user-derived value is NEVER
    # logged (only a fixed message + exc_info traceback) — closes the
    # CodeQL log-injection finding at the source rather than relying on a
    # sanitizer CodeQL's taint model doesn't recognize.
    safe = re.sub(r"[^A-Z0-9]", "", g)[:8]
    if len(g) >= 32:
        return g
    try:
        row = await db.fetch_val(
            f"SELECT {guid_col} FROM {table} {where_sql} "  # nosec B608 - guid_col/table are internal _PLAYER_HEATMAP_MODES constants; all user values are $N-bound
            f"AND LEFT({guid_col}, 8) = ${len(params) + 1} "
            f"ORDER BY {guid_col} LIMIT 1",  # deterministic on prefix collision
            tuple(list(params) + [safe]),
        )
    except Exception:
        logger.warning(
            "player-heatmap GUID resolution query failed (input len=%d)",
            len(g), exc_info=True,
        )
        row = None
    return str(row) if row else g


@router.get("/proximity/players")
@handle_router_errors("Proximity players error")
async def get_proximity_players(
    range_days: int = 365,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Scoped {guid,name} list for the Player Combat Map picker — viewers
    pick a name, not a GUID. One row per canonical player_guid in scope,
    sorted by name. Same scope source (player_track) as the heatmap."""
    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
    )
    rows = await db.fetch_all(
        "SELECT player_guid, MAX(player_name) AS name "
        f"FROM player_track {where_sql} "  # nosec B608 - where_sql is $N-parameterized by _build_proximity_where_clause; no user data interpolated
        "GROUP BY player_guid "
        "HAVING MAX(player_name) IS NOT NULL "
        "ORDER BY LOWER(MAX(player_name))",
        tuple(params),
    )
    players = [
        {"guid": str(r[0]), "name": str(r[1])}
        for r in (rows or [])
        if r and r[0] and r[1]
    ]
    return {"status": "ok", "scope": scope, "players": players}


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


@router.get("/proximity/push-deaths/heatmap")
@handle_router_errors("Proximity push-deaths heatmap error")
async def get_proximity_push_deaths_heatmap(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """"Where pushes die" — grid-binned death positions of the pushing team.

    Two point sources, binned together on the same 512u grid as
    /combat-positions/heatmap so the frontend renderer is reused as-is:
    1. deaths of the pushing team inside an objective-directed push window
       (proximity_team_push joined to proximity_combat_position on
       round_id + team + event_time; toward_objective='NO' rows are the
       non-objective pushes and are excluded), and
    2. carrier deaths (proximity_carrier_kill has no coordinates of its own,
       so each is located via the matching combat_position kill event).

    Proximity productization slice 2 (docs/research/PROXIMITY_IDEAS_2026-07.md B1).
    """
    if not map_name or not map_name.strip():
        raise HTTPException(status_code=400, detail="map_name is required")

    where_push, params_push, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
        alias="tp",
    )
    push_rows = await db.fetch_all(
        f"""
        SELECT FLOOR(cp.victim_x / 512.0)::int AS gx,
               FLOOR(cp.victim_y / 512.0)::int AS gy,
               COUNT(*) AS cnt
        FROM proximity_team_push tp
        JOIN proximity_combat_position cp
          ON cp.round_id = tp.round_id
         AND cp.victim_team = tp.team
         AND cp.event_time BETWEEN tp.start_time AND tp.end_time
        {where_push}
          AND tp.round_id IS NOT NULL
          AND tp.toward_objective IS NOT NULL
          AND tp.toward_objective NOT IN ('NO', '')
        GROUP BY gx, gy
        """,
        tuple(params_push),
    )

    where_carrier, params_carrier, _ = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
        alias="ck",
    )
    carrier_rows = await db.fetch_all(
        f"""
        SELECT FLOOR(cp.victim_x / 512.0)::int AS gx,
               FLOOR(cp.victim_y / 512.0)::int AS gy,
               COUNT(*) AS cnt
        FROM proximity_carrier_kill ck
        JOIN proximity_combat_position cp
          ON cp.round_id = ck.round_id
         AND cp.victim_guid = ck.carrier_guid
         AND ABS(cp.event_time - ck.kill_time) <= 1500
        {where_carrier}
          AND ck.round_id IS NOT NULL
        GROUP BY gx, gy
        """,
        tuple(params_carrier),
    )

    merged: dict[tuple[int, int], int] = {}
    for rows in (push_rows, carrier_rows):
        for r in (rows or []):
            key = (int(r[0] or 0), int(r[1] or 0))
            merged[key] = merged.get(key, 0) + int(r[2] or 0)

    return {
        "status": "ok",
        "map_name": map_name.strip(),
        "grid_size": 512,
        "perspective": "pushes",
        "scope": scope,
        "push_death_cells": len(push_rows or []),
        "carrier_death_cells": len(carrier_rows or []),
        "hotzones": [
            {"x": gx, "y": gy, "count": cnt}
            for (gx, gy), cnt in sorted(merged.items(), key=lambda kv: -kv[1])
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
    if weapon_id is not None and mode_key == "presence":
        # presence is positional (player_track path), it has no weapon
        # dimension — reject rather than silently ignore the filter.
        raise HTTPException(
            status_code=400,
            detail="weapon_id is not supported with mode=presence",
        )

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
            f"SELECT COALESCE(SUM(sample_count), 0) FROM player_track pt {where_sql}",  # nosec B608 - where_sql is $N-parameterized by _build_proximity_where_clause; no user data interpolated
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
            """,  # nosec B608 - g/stride are clamped ints, where_sql is $N-parameterized; no user data interpolated
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
            """,  # nosec B608 - x_col/y_col/table are internal _PLAYER_HEATMAP_MODES constants, g clamped int, where_sql $N-bound
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


@router.get("/proximity/player-aim")
@handle_router_errors("Proximity player-aim error")
async def get_proximity_player_aim(
    map_name: str | None = None,
    player_guid: str | None = None,
    range_days: int = 30,
    session_date: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    weapon_id: int | None = None,
    grid_size: int = 512,
    min_cell: int = 8,
    db: DatabaseAdapter = Depends(get_db),
):
    """Full Aim Analytics for one player on one map (v9 true-aim data).

    Reads ``proximity_shot_fired`` (origin + view_yaw/view_pitch). Returns,
    per the aim-analytics master plan: origin density hotzones each carrying
    a 16-bucket yaw rose + per-cell circular mean/R, a global pitch
    histogram, wrap-safe circular statistics (incl. a Rayleigh
    directional-vs-uniform test), and narrative one-liners.

    NEW + additive — does NOT touch the shared ``/proximity/player-heatmap``
    contract (kept for the simple density lenses).
    """
    if not map_name or not map_name.strip():
        raise HTTPException(status_code=400, detail="map_name is required")
    if not player_guid or not player_guid.strip():
        raise HTTPException(status_code=400, detail="player_guid is required")

    g = float(max(128, min(int(grid_size or 512), 1024)))
    g_int = int(g)
    min_cell = max(1, min(int(min_cell or 8), 200))
    table = "proximity_shot_fired"
    guid_col = "guid"

    base_where, base_params, _ = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
    )
    base_params_t = tuple(base_params)
    canonical = await _resolve_player_guid_canonical(
        db, player_guid, table, guid_col, base_where, base_params_t,
    )
    name_map = await _load_scoped_guid_name_map(db, base_where, base_params_t)
    player_name = _resolve_name_for_guid(canonical, name_map)

    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
        player_guid=canonical, player_guid_columns=[guid_col],
    )
    params_list = list(params)
    extra_sql = ""
    if weapon_id is not None:
        params_list.append(int(weapon_id))
        extra_sql = f"AND weapon_id = ${len(params_list)}"
    pt = tuple(params_list)

    # Q1: per-cell yaw rose. Shift yaw [-180,180] -> [0,360) then bucket.
    rose_rows = await db.fetch_all(
        f"""
        SELECT FLOOR(origin_x / {g})::int AS gx,
               FLOOR(origin_y / {g})::int AS gy,
               LEAST(width_bucket(
                   ((view_yaw::numeric + 180.0) % 360.0 + 360.0) % 360.0,
                   0.0, 360.0, {_AIM_YAW_BUCKETS}), {_AIM_YAW_BUCKETS}) AS yb,
               COUNT(*) AS cnt
        FROM {table} {where_sql}
        {extra_sql}
        GROUP BY gx, gy, yb
        """,  # nosec B608 - g/bucket consts are clamped ints, where_sql $N-bound, no user data interpolated
        pt,
    )
    # Q2: global pitch histogram, 6 even 30-deg bands over [-90,90].
    pitch_rows = await db.fetch_all(
        f"""
        SELECT LEAST(width_bucket(view_pitch::numeric, -90.0, 90.0, 6), 6) AS pb,
               COUNT(*) AS cnt
        FROM {table} {where_sql}
        {extra_sql}
        GROUP BY pb
        """,  # nosec B608 - constants only, where_sql $N-bound
        pt,
    )
    # Q3: wrap-safe circular aggregates + arithmetic pitch (pitch doesn't wrap).
    circ_rows = await db.fetch_all(
        f"""
        SELECT COUNT(*) AS n,
               AVG(SIN(RADIANS(view_yaw::float8))) AS sbar,
               AVG(COS(RADIANS(view_yaw::float8))) AS cbar,
               AVG(view_pitch::float8) AS pmean,
               COALESCE(STDDEV_POP(view_pitch::float8), 0) AS pstd
        FROM {table} {where_sql}
        {extra_sql}
        """,  # nosec B608 - no interpolated user data, where_sql $N-bound
        pt,
    )

    # Fold per-cell roses + a global rose (from ALL rows, pre-cap).
    cells: dict[tuple[int, int], list[int]] = {}
    global_rose = [0] * _AIM_YAW_BUCKETS
    for r in (rose_rows or []):
        gx, gy, yb, cnt = int(r[0] or 0), int(r[1] or 0), int(r[2] or 0), int(r[3] or 0)
        idx = min(max(yb, 1), _AIM_YAW_BUCKETS) - 1
        cell = cells.setdefault((gx, gy), [0] * _AIM_YAW_BUCKETS)
        cell[idx] += cnt
        global_rose[idx] += cnt

    hotzones = []
    for (gx, gy), rose in cells.items():
        c = sum(rose)
        if c < min_cell:
            continue
        mean_yaw, r_len = _rose_circular(rose)
        hotzones.append({
            "x": gx, "y": gy, "count": c, "rose": rose,
            "mean_yaw": mean_yaw, "r": r_len,
        })
    hotzones.sort(key=lambda z: z["count"], reverse=True)
    sampled = len(hotzones) > 120
    if sampled:
        hotzones = hotzones[:120]

    pitch_counts = [0] * 6
    for r in (pitch_rows or []):
        pb = int(r[0] or 0)
        if 1 <= pb <= 6:
            pitch_counts[pb - 1] = int(r[1] or 0)

    r3 = (circ_rows or [None])[0]
    n_total = int((r3[0] if r3 else 0) or 0)
    sbar = float((r3[1] if r3 else 0.0) or 0.0)
    cbar = float((r3[2] if r3 else 0.0) or 0.0)
    pitch_mean = round(float((r3[3] if r3 else 0.0) or 0.0), 2)
    pitch_std = round(float((r3[4] if r3 else 0.0) or 0.0), 2)
    circ = _circular_yaw_stats(sbar, cbar, n_total)
    circ["pitch_mean_deg"] = pitch_mean
    circ["pitch_std_deg"] = pitch_std

    return {
        "status": "ok",
        "map_name": map_name.strip(),
        "player_guid": canonical,
        "player_name": player_name,
        "grid_size": g_int,
        "total": n_total,
        "sampled": sampled,
        "scope": scope,
        "hotzones": hotzones,
        "yaw_buckets": _AIM_YAW_BUCKETS,
        "yaw_bucket_width_deg": _AIM_YAW_BUCKET_DEG,
        "pitch_hist": {
            "edges": [-90, -60, -30, 0, 30, 60, 90],
            "counts": pitch_counts,
        },
        "circular": circ,
        "narrative": _build_aim_narrative(circ, pitch_mean, global_rose),
    }


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
