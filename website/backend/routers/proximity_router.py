import asyncio
import time
import math
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from collections import defaultdict
from itertools import combinations
from fastapi import APIRouter, Depends, HTTPException
from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger

router = APIRouter()
logger = get_app_logger("api.proximity")


# ========================================
# PROXIMITY (PROTOTYPE)
# ========================================

def _proximity_stub_meta(range_days: int) -> dict:
    return {
        "status": "prototype",
        "ready": False,
        "message": "Proximity pipeline not connected.",
        "range_days": range_days,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


def _parse_iso_date(value: Optional[str]) -> Optional[Any]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid session_date format. Use YYYY-MM-DD.",
        )


def _build_proximity_where_clause(
    range_days: int,
    session_date: Optional[str],
    map_name: Optional[str],
    round_number: Optional[int],
    round_start_unix: Optional[int],
    alias: Optional[str] = None,
    player_guid: Optional[str] = None,
    player_guid_columns: Optional[List[str]] = None,
) -> Tuple[str, List[Any], Dict[str, Any]]:
    prefix = f"{alias}." if alias else ""
    params: List[Any] = []
    clauses: List[str] = []

    parsed_session_date = _parse_iso_date(session_date)
    normalized_map = (map_name or "").strip() or None

    if round_number is not None and round_number < 0:
        raise HTTPException(status_code=400, detail="round_number must be >= 0")
    if round_start_unix is not None and round_start_unix < 0:
        raise HTTPException(status_code=400, detail="round_start_unix must be >= 0")

    if parsed_session_date is not None:
        params.append(parsed_session_date)
        clauses.append(f"{prefix}session_date = ${len(params)}")
    else:
        safe_range = max(1, min(int(range_days or 30), 3650))
        since = datetime.utcnow().date() - timedelta(days=safe_range)
        params.append(since)
        clauses.append(f"{prefix}session_date >= ${len(params)}")

    if normalized_map is not None:
        params.append(normalized_map)
        clauses.append(f"{prefix}map_name = ${len(params)}")

    if round_number is not None:
        params.append(int(round_number))
        clauses.append(f"{prefix}round_number = ${len(params)}")

    if round_start_unix is not None and int(round_start_unix) > 0:
        params.append(int(round_start_unix))
        clauses.append(f"{prefix}round_start_unix = ${len(params)}")

    # Player GUID filter — supports OR across multiple column names
    if player_guid and player_guid.strip():
        guid_val = player_guid.strip()
        params.append(guid_val)
        pidx = len(params)
        if player_guid_columns and len(player_guid_columns) > 1:
            or_parts = [f"{prefix}{col} = ${pidx}" for col in player_guid_columns]
            clauses.append(f"({' OR '.join(or_parts)})")
        elif player_guid_columns:
            clauses.append(f"{prefix}{player_guid_columns[0]} = ${pidx}")
        else:
            # Default: target_guid (engagement tables)
            clauses.append(f"{prefix}target_guid = ${pidx}")

    scope = {
        "session_date": parsed_session_date.isoformat() if parsed_session_date else None,
        "map_name": normalized_map,
        "round_number": int(round_number) if round_number is not None else None,
        "round_start_unix": int(round_start_unix)
        if round_start_unix is not None and int(round_start_unix) > 0
        else None,
        "player_guid": player_guid.strip() if player_guid and player_guid.strip() else None,
    }
    return "WHERE " + " AND ".join(clauses), params, scope


async def _table_column_exists(db: DatabaseAdapter, table_name: str, column_name: str) -> bool:
    try:
        return bool(
            await db.fetch_val(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = $1
                      AND column_name = $2
                )
                """,
                (table_name, column_name),
            )
        )
    except Exception as e:
        logger.warning("_table_column_exists check failed for %s.%s: %s", table_name, column_name, e)
        return False


def _iter_attackers(attackers_raw: Any) -> List[Dict[str, Any]]:
    parsed = _parse_json_field(attackers_raw)
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    if isinstance(parsed, dict):
        return [item for item in parsed.values() if isinstance(item, dict)]
    return []


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y")
    return False


def _short_guid(guid: str) -> str:
    token = str(guid or "").strip()
    return token[:8] if token else "unknown"


def _resolve_name_for_guid(
    guid: str,
    guid_name_map: Optional[Dict[str, str]] = None,
    local_map: Optional[Dict[str, str]] = None,
) -> str:
    token = str(guid or "").strip()
    if not token:
        return "unknown"
    if local_map and token in local_map and local_map[token]:
        return str(local_map[token])
    if guid_name_map and token in guid_name_map and guid_name_map[token]:
        return str(guid_name_map[token])
    return f"#{_short_guid(token)}"


async def _load_scoped_guid_name_map(
    db: DatabaseAdapter,
    where_sql: str,
    params: tuple,
) -> Dict[str, str]:
    """
    Build guid -> display name mapping for the active scope.
    Uses player_track (same scope columns as combat_engagement).
    """
    try:
        rows = await db.fetch_all(
            "SELECT player_guid, MAX(player_name) AS player_name "
            f"FROM player_track {where_sql} "
            "GROUP BY player_guid",
            params,
        )
        return {
            str(row[0]): str(row[1])
            for row in rows
            if row and row[0] and row[1]
        }
    except Exception:
        logger.warning("_load_scoped_guid_name_map failed", exc_info=True)
        return {}


def _compute_scoped_duos(
    engagement_rows: List[Any],
    limit: int,
    guid_name_map: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    pair_stats: Dict[Tuple[str, str], Dict[str, float]] = {}

    for row in engagement_rows:
        attackers_raw, participants_raw, crossfire_delay_ms, outcome = row
        attackers = _iter_attackers(attackers_raw)

        guid_to_name: Dict[str, str] = {}
        fallback_names: List[str] = []
        for attacker in attackers:
            guid = str(attacker.get("guid") or "").strip()
            name = str(attacker.get("name") or guid or "").strip()
            if not name:
                continue
            fallback_names.append(name)
            if guid:
                guid_to_name[guid] = name

        participants = _parse_json_field(participants_raw) or []
        names: List[str] = []
        participant_guids: List[str] = []
        if isinstance(participants, list) and participants:
            for guid in participants:
                guid_str = str(guid or "").strip()
                if not guid_str:
                    continue
                participant_guids.append(guid_str)
                mapped = _resolve_name_for_guid(guid_str, guid_name_map, guid_to_name)
                if mapped:
                    names.append(mapped)

        if len(names) < 2:
            names = fallback_names

        if len(names) < 2 and len(participant_guids) >= 2:
            names = [_resolve_name_for_guid(guid, guid_name_map, guid_to_name) for guid in participant_guids]

        unique_names = sorted({name for name in names if name})
        if len(unique_names) < 2:
            continue

        for p1, p2 in combinations(unique_names, 2):
            key = (p1, p2)
            if key not in pair_stats:
                pair_stats[key] = {
                    "crossfire_count": 0,
                    "crossfire_kills": 0,
                    "delay_sum": 0.0,
                    "delay_count": 0,
                }
            pair_stats[key]["crossfire_count"] += 1
            if str(outcome or "").lower() == "killed":
                pair_stats[key]["crossfire_kills"] += 1
            if crossfire_delay_ms is not None:
                pair_stats[key]["delay_sum"] += float(crossfire_delay_ms)
                pair_stats[key]["delay_count"] += 1

    sorted_pairs = sorted(
        pair_stats.items(),
        key=lambda item: (
            item[1]["crossfire_kills"],
            item[1]["crossfire_count"],
        ),
        reverse=True,
    )

    return [
        {
            "player1": pair[0],
            "player2": pair[1],
            "crossfire_kills": int(stats["crossfire_kills"]),
            "crossfire_count": int(stats["crossfire_count"]),
            "avg_delay_ms": round(stats["delay_sum"] / stats["delay_count"], 1)
            if stats["delay_count"]
            else None,
        }
        for pair, stats in sorted_pairs[: max(1, min(limit, 50))]
    ]


def _compute_scoped_teamplay(
    engagement_rows: List[Any],
    limit: int,
    guid_name_map: Optional[Dict[str, str]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    stats: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "guid": None,
            "name": "Unknown",
            "crossfire_participations": 0,
            "crossfire_kills": 0,
            "crossfire_final_blows": 0,
            "crossfire_delay_sum": 0.0,
            "crossfire_delay_count": 0,
            "times_focused": 0,
            "focus_escapes": 0,
        }
    )

    def ensure_player(guid: Optional[str], name: Optional[str]) -> str:
        key = (guid or name or "unknown").strip() or "unknown"
        entry = stats[key]
        entry["guid"] = guid or key
        if name:
            entry["name"] = name
        return key

    for row in engagement_rows:
        (
            target_guid,
            target_name,
            outcome,
            num_attackers,
            is_crossfire,
            crossfire_delay_ms,
            attackers_raw,
            participants_raw,
        ) = row

        target_key = ensure_player(
            str(target_guid) if target_guid is not None else None,
            str(target_name) if target_name is not None else None,
        )
        target_stats = stats[target_key]
        if int(num_attackers or 0) >= 2:
            target_stats["times_focused"] += 1
            if str(outcome or "").lower() == "escaped":
                target_stats["focus_escapes"] += 1

        if not is_crossfire:
            continue

        attackers = _iter_attackers(attackers_raw)
        attacker_by_guid = {
            str(attacker.get("guid") or "").strip(): attacker
            for attacker in attackers
            if str(attacker.get("guid") or "").strip()
        }

        participant_guids = set()
        parsed_participants = _parse_json_field(participants_raw) or []
        if isinstance(parsed_participants, list):
            participant_guids = {
                str(guid).strip()
                for guid in parsed_participants
                if str(guid).strip()
            }

        if participant_guids:
            for guid in participant_guids:
                attacker = attacker_by_guid.get(guid, {})
                name = str(attacker.get("name") or _resolve_name_for_guid(guid, guid_name_map) or guid).strip() or "Unknown"
                player_key = ensure_player(guid, name)
                player_stats = stats[player_key]
                player_stats["crossfire_participations"] += 1
                if str(outcome or "").lower() == "killed":
                    player_stats["crossfire_kills"] += 1
                if attacker and _to_bool(attacker.get("got_kill")):
                    player_stats["crossfire_final_blows"] += 1
                if crossfire_delay_ms is not None:
                    player_stats["crossfire_delay_sum"] += float(crossfire_delay_ms)
                    player_stats["crossfire_delay_count"] += 1
        else:
            for attacker in attackers:
                guid = str(attacker.get("guid") or "").strip()
                name = str(attacker.get("name") or guid or "").strip() or "Unknown"
                player_key = ensure_player(guid or None, name)
                player_stats = stats[player_key]
                player_stats["crossfire_participations"] += 1
                if str(outcome or "").lower() == "killed":
                    player_stats["crossfire_kills"] += 1
                if _to_bool(attacker.get("got_kill")):
                    player_stats["crossfire_final_blows"] += 1
                if crossfire_delay_ms is not None:
                    player_stats["crossfire_delay_sum"] += float(crossfire_delay_ms)
                    player_stats["crossfire_delay_count"] += 1

    normalized = []
    for values in stats.values():
        delays = values["crossfire_delay_count"]
        avg_delay = values["crossfire_delay_sum"] / delays if delays else None
        normalized.append(
            {
                "guid": values["guid"],
                "name": values["name"],
                "crossfire_kills": int(values["crossfire_kills"]),
                "crossfire_participations": int(values["crossfire_participations"]),
                "crossfire_final_blows": int(values["crossfire_final_blows"]),
                "avg_delay_ms": round(avg_delay, 1) if avg_delay is not None else None,
                "times_focused": int(values["times_focused"]),
                "focus_escapes": int(values["focus_escapes"]),
            }
        )

    normalized = [row for row in normalized if row["guid"] and row["name"]]

    crossfire_rows = sorted(
        [row for row in normalized if row["crossfire_participations"] > 0],
        key=lambda row: (row["crossfire_kills"], row["crossfire_participations"]),
        reverse=True,
    )[: max(1, min(limit, 25))]

    sync_rows = sorted(
        [row for row in normalized if row["avg_delay_ms"] is not None],
        key=lambda row: (row["avg_delay_ms"], -row["crossfire_kills"]),
    )[: max(1, min(limit, 25))]

    focus_rows = sorted(
        [row for row in normalized if row["times_focused"] > 0],
        key=lambda row: (
            (row["focus_escapes"] / row["times_focused"]) if row["times_focused"] else 0,
            row["times_focused"],
        ),
        reverse=True,
    )[: max(1, min(limit, 25))]

    return {
        "crossfire_kills": [
            {
                **row,
                "kill_rate_pct": round(
                    (row["crossfire_kills"] * 100.0) / row["crossfire_participations"],
                    1,
                )
                if row["crossfire_participations"]
                else None,
            }
            for row in crossfire_rows
        ],
        "sync": sync_rows,
        "focus_survival": [
            {
                **row,
                "survival_rate_pct": round(
                    (row["focus_escapes"] * 100.0) / row["times_focused"],
                    1,
                )
                if row["times_focused"]
                else None,
            }
            for row in focus_rows
        ],
    }


def _normalize_angle(delta: float) -> float:
    """Normalize angle delta to [-pi, pi]."""
    while delta > math.pi:
        delta -= 2 * math.pi
    while delta < -math.pi:
        delta += 2 * math.pi
    return delta


def _parse_json_field(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return None
    return None


def _compute_strafe_metrics(path: List[Dict[str, Any]], min_step: float = 5.0, angle_threshold_deg: float = 40.0) -> Dict[str, Any]:
    """
    Compute simple strafe/dodge metrics from a list of points with time,x,y.
    Returns turn events with timestamps for visualization.
    """
    if not path or len(path) < 3:
        return {
            "duration_ms": 0,
            "total_distance": 0.0,
            "avg_speed": 0.0,
            "turn_count": 0,
            "turn_rate": 0.0,
            "events": [],
        }

    points = [
        p for p in path
        if p and p.get("x") is not None and p.get("y") is not None and p.get("time") is not None
    ]
    if len(points) < 3:
        return {
            "duration_ms": 0,
            "total_distance": 0.0,
            "avg_speed": 0.0,
            "turn_count": 0,
            "turn_rate": 0.0,
            "events": [],
        }

    angle_threshold = math.radians(angle_threshold_deg)
    total_distance = 0.0
    headings: List[Dict[str, Any]] = []

    for idx in range(1, len(points)):
        p1 = points[idx - 1]
        p2 = points[idx]
        dx = float(p2["x"]) - float(p1["x"])
        dy = float(p2["y"]) - float(p1["y"])
        step = math.hypot(dx, dy)
        if step < min_step:
            continue
        total_distance += step
        heading = math.atan2(dy, dx)
        headings.append({
            "time": p2["time"],
            "heading": heading,
            "x": p2["x"],
            "y": p2["y"],
        })

    if len(headings) < 3:
        duration_ms = int(points[-1]["time"] - points[0]["time"])
        duration_s = max(duration_ms / 1000.0, 0.001)
        return {
            "duration_ms": duration_ms,
            "total_distance": round(total_distance, 1),
            "avg_speed": round(total_distance / duration_s, 2),
            "turn_count": 0,
            "turn_rate": 0.0,
            "events": [],
        }

    turn_events = []
    turn_count = 0

    for idx in range(1, len(headings)):
        prev = headings[idx - 1]
        curr = headings[idx]
        delta = _normalize_angle(curr["heading"] - prev["heading"])
        if abs(delta) >= angle_threshold:
            turn_count += 1
            turn_events.append({
                "time": curr["time"],
                "angle_deg": round(math.degrees(delta), 1),
                "x": curr["x"],
                "y": curr["y"],
            })

    duration_ms = int(points[-1]["time"] - points[0]["time"])
    duration_s = max(duration_ms / 1000.0, 0.001)
    turn_rate = round(turn_count / duration_s, 2)

    return {
        "duration_ms": duration_ms,
        "total_distance": round(total_distance, 1),
        "avg_speed": round(total_distance / duration_s, 2),
        "turn_count": turn_count,
        "turn_rate": turn_rate,
        "events": turn_events,
    }



# ========================================
# COMPOSITE DASHBOARD ENDPOINT
# ========================================
# Replaces 29+ individual HTTP calls with a single asyncio.gather.
# Individual endpoints remain unchanged for backward compatibility.

DASHBOARD_SECTION_GROUPS = {
    "critical": ["summary", "engagements", "hotzones", "movers", "teamplay", "classes", "events"],
    "combat": ["reactions", "trades_summary", "trades_events", "weapon_accuracy", "revives", "movement_stats"],
    "teamplay_v5": ["spawn_timing", "cohesion", "crossfire_angles", "pushes", "lua_trades"],
    "analytics": ["kill_outcomes", "kill_outcome_stats", "hit_regions", "headshot_rates"],
    "objectives": ["carrier_events", "carrier_kills", "carrier_returns", "vehicle_progress", "escort_credits", "construction_events"],
    "scoring": ["prox_scores", "prox_formula"],
}
DASHBOARD_ALL_SECTIONS = [s for g in DASHBOARD_SECTION_GROUPS.values() for s in g]


async def _timed_section(name: str, coro):
    """Wrap a section coroutine with timing and error handling."""
    t0 = time.monotonic()
    try:
        result = await coro
        ms = round((time.monotonic() - t0) * 1000, 1)
        if isinstance(result, dict):
            result["_timing_ms"] = ms
        return result
    except Exception as e:
        ms = round((time.monotonic() - t0) * 1000, 1)
        logger.warning("Dashboard section %s failed in %.1fms: %s", name, ms, e)
        return {"_error": str(e), "status": "error", "_timing_ms": ms}


@router.get("/proximity/dashboard")
async def get_proximity_dashboard(
    sections: str = "all",
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Composite endpoint: fetches multiple proximity sections in a single request.
    Replaces 29+ individual HTTP calls with one asyncio.gather.

    sections: "all", a group name (critical/combat/teamplay_v5/analytics/objectives/scoring),
              or comma-separated section keys.
    """
    t0_total = time.monotonic()

    # Parse requested sections
    requested = set()
    for part in sections.split(","):
        part = part.strip()
        if part == "all":
            requested = set(DASHBOARD_ALL_SECTIONS)
            break
        elif part in DASHBOARD_SECTION_GROUPS:
            requested.update(DASHBOARD_SECTION_GROUPS[part])
        elif part in DASHBOARD_ALL_SECTIONS:
            requested.add(part)

    if not requested:
        return {"status": "error", "detail": "No valid sections requested"}

    # Pre-parse session_date so all downstream functions receive a date object.
    parsed_date = _parse_iso_date(session_date)

    # Full scope kwargs (for endpoints that accept all 5 scope params)
    full = dict(range_days=range_days, session_date=parsed_date, map_name=map_name,
                round_number=round_number, round_start_unix=round_start_unix)

    # Section dispatchers
    dispatchers = {
        "summary": lambda: get_proximity_summary(**full, db=db),
        "engagements": lambda: get_proximity_engagements(**full, db=db),
        "hotzones": lambda: get_proximity_hotzones(**full, db=db),
        "movers": lambda: get_proximity_movers(**full, db=db),
        "teamplay": lambda: get_proximity_teamplay(**full, limit=6, db=db),
        "classes": lambda: get_proximity_classes(**full, db=db),
        "events": lambda: get_proximity_events(**full, limit=20, db=db),
        "trades_summary": lambda: get_proximity_trades_summary(**full, db=db),
        "trades_events": lambda: get_proximity_trade_events(**full, limit=10, db=db),
        "spawn_timing": lambda: get_proximity_spawn_timing(**full, db=db),
        "cohesion": lambda: get_proximity_cohesion(**full, db=db),
        "crossfire_angles": lambda: get_proximity_crossfire_angles(**full, db=db),
        "pushes": lambda: get_proximity_pushes(**full, db=db),
        "lua_trades": lambda: get_proximity_lua_trades(**full, db=db),
        "kill_outcomes": lambda: get_proximity_kill_outcomes(**full, db=db),
        "hit_regions": lambda: get_proximity_hit_regions(**full, db=db),
        "carrier_events": lambda: get_proximity_carrier_events(**full, db=db),
        "carrier_kills": lambda: get_proximity_carrier_kills(**full, db=db),
        "carrier_returns": lambda: get_proximity_carrier_returns(**full, db=db),
        "vehicle_progress": lambda: get_proximity_vehicle_progress(**full, db=db),
        "escort_credits": lambda: get_proximity_escort_credits(**full, db=db),
        "construction_events": lambda: get_proximity_construction_events(**full, db=db),
        "reactions": lambda: get_proximity_reactions(**full, limit=6, db=db),
        "kill_outcome_stats": lambda: get_proximity_kill_outcomes_player_stats(
            range_days=range_days, session_date=parsed_date, map_name=map_name, db=db),
        "headshot_rates": lambda: get_proximity_hit_regions_headshot_rates(
            range_days=range_days, session_date=parsed_date, map_name=map_name, db=db),
        "movement_stats": lambda: get_proximity_movement_stats(
            range_days=range_days, session_date=parsed_date, map_name=map_name, db=db),
        "revives": lambda: get_proximity_revives(
            range_days=range_days, session_date=parsed_date, map_name=map_name, db=db),
        "weapon_accuracy": lambda: get_proximity_weapon_accuracy(
            range_days=range_days, map_name=map_name, db=db),
        "prox_scores": lambda: get_prox_scores(range_days=range_days, db=db),
        "prox_formula": lambda: get_prox_scores_formula(),
    }

    keys = [s for s in DASHBOARD_ALL_SECTIONS if s in requested and s in dispatchers]
    coros = [_timed_section(k, dispatchers[k]()) for k in keys]

    results = await asyncio.gather(*coros, return_exceptions=True)

    sections_dict = {}
    ok_count = 0
    err_count = 0
    for key, result in zip(keys, results):
        if isinstance(result, Exception):
            sections_dict[key] = {"_error": str(result), "status": "error"}
            err_count += 1
        elif isinstance(result, dict) and result.get("status") == "error":
            sections_dict[key] = result
            err_count += 1
        else:
            sections_dict[key] = result
            ok_count += 1

    total_ms = round((time.monotonic() - t0_total) * 1000, 1)

    return {
        "status": "ok",
        "sections_requested": len(keys),
        "sections_ok": ok_count,
        "sections_error": err_count,
        "total_ms": total_ms,
        "sections": sections_dict,
    }


@router.get("/proximity/scopes")
async def get_proximity_scopes(
    range_days: int = 60,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Discover session -> map -> round hierarchy from scoped proximity rows.
    """
    payload = _proximity_stub_meta(range_days)
    safe_range = max(1, min(int(range_days or 60), 3650))
    since = datetime.utcnow().date() - timedelta(days=safe_range)

    try:
        rows = await db.fetch_all(
            """
            SELECT session_date, map_name, round_number, round_start_unix, round_end_unix,
                   COUNT(*) AS engagements
            FROM combat_engagement
            WHERE session_date >= $1
            GROUP BY session_date, map_name, round_number, round_start_unix, round_end_unix
            ORDER BY session_date DESC, map_name ASC, round_number ASC, round_start_unix ASC
            """,
            (since,),
        )

        sessions_by_date: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            session_date_val = row[0]
            map_name_val = str(row[1] or "unknown")
            round_number_val = int(row[2] or 0)
            round_start_val = int(row[3] or 0)
            round_end_val = int(row[4] or 0)
            engagements = int(row[5] or 0)

            session_key = (
                session_date_val.isoformat()
                if hasattr(session_date_val, "isoformat")
                else str(session_date_val)
            )
            session_entry = sessions_by_date.setdefault(
                session_key,
                {
                    "session_date": session_key,
                    "engagements": 0,
                    "_maps": {},
                },
            )
            session_entry["engagements"] += engagements

            map_entry = session_entry["_maps"].setdefault(
                map_name_val,
                {
                    "map_name": map_name_val,
                    "engagements": 0,
                    "rounds": [],
                    "_first_round_start": None,
                },
            )
            map_entry["engagements"] += engagements
            map_entry["rounds"].append(
                {
                    "round_number": round_number_val,
                    "round_start_unix": round_start_val if round_start_val > 0 else None,
                    "round_end_unix": round_end_val if round_end_val > 0 else None,
                    "engagements": engagements,
                }
            )
            if round_start_val > 0:
                first = map_entry["_first_round_start"]
                if first is None or round_start_val < first:
                    map_entry["_first_round_start"] = round_start_val

        sessions: List[Dict[str, Any]] = []
        for session in sorted(
            sessions_by_date.values(),
            key=lambda item: item["session_date"],
            reverse=True,
        ):
            maps = []
            for map_item in session["_maps"].values():
                rounds_sorted = sorted(
                    map_item["rounds"],
                    key=lambda r: (
                        r["round_start_unix"] if r["round_start_unix"] is not None else 10**12,
                        r["round_number"],
                    ),
                )
                maps.append(
                    {
                        "map_name": map_item["map_name"],
                        "engagements": map_item["engagements"],
                        "round_count": len(rounds_sorted),
                        "rounds": rounds_sorted,
                        "_first_round_start": map_item["_first_round_start"],
                    }
                )

            maps_sorted = sorted(
                maps,
                key=lambda m: (
                    m["_first_round_start"] if m["_first_round_start"] is not None else 10**12,
                    m["map_name"],
                ),
            )
            for item in maps_sorted:
                item.pop("_first_round_start", None)

            sessions.append(
                {
                    "session_date": session["session_date"],
                    "engagements": session["engagements"],
                    "map_count": len(maps_sorted),
                    "round_count": sum(map_item["round_count"] for map_item in maps_sorted),
                    "maps": maps_sorted,
                }
            )

        default_scope = {
            "session_date": sessions[0]["session_date"] if sessions else None,
            "map_name": None,
            "round_number": None,
            "round_start_unix": None,
        }

        payload.update(
            {
                "status": "ok" if sessions else "prototype",
                "ready": bool(sessions),
                "message": None if sessions else payload["message"],
                "sessions": sessions,
                "scope": default_scope,
            }
        )
    except Exception:
        payload.update(
            {
                "status": "error",
                "ready": False,
                "message": "Proximity query failed",
                "sessions": [],
                "scope": {
                    "session_date": None,
                    "map_name": None,
                    "round_number": None,
                    "round_start_unix": None,
                },
            }
        )
    return payload


@router.get("/proximity/summary")
async def get_proximity_summary(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Summary for proximity analytics scoped by session/map/round filters.
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
        engagement_row = await db.fetch_one(
            "SELECT COUNT(*) AS total_engagements, "
            "AVG(distance_traveled) AS avg_distance, "
            "AVG(duration_ms) AS avg_duration_ms, "
            "AVG(num_attackers) AS avg_attackers, "
            "SUM(CASE WHEN is_crossfire THEN 1 ELSE 0 END) AS crossfire_events, "
            "SUM(CASE WHEN outcome = 'escaped' THEN 1 ELSE 0 END) AS escapes, "
            "SUM(CASE WHEN outcome = 'killed' THEN 1 ELSE 0 END) AS kills "
            f"FROM combat_engagement {where_sql}",
            query_params,
        )
        total_engagements = engagement_row[0] if engagement_row else 0
        avg_distance = engagement_row[1] if engagement_row else None
        avg_duration = engagement_row[2] if engagement_row else None
        avg_attackers = engagement_row[3] if engagement_row else None
        crossfire_events = engagement_row[4] if engagement_row else 0
        escapes = engagement_row[5] if engagement_row else 0
        kills = engagement_row[6] if engagement_row else 0

        sample_rounds = await db.fetch_val(
            "SELECT COUNT(DISTINCT (session_date, round_number, round_start_unix)) "
            f"FROM combat_engagement {where_sql}",
            query_params,
        )

        hotzones = await db.fetch_val(
            """
            SELECT COUNT(*)
            FROM (
                SELECT FLOOR(COALESCE(end_x, start_x) / 256.0)::int AS grid_x,
                       FLOOR(COALESCE(end_y, start_y) / 256.0)::int AS grid_y
                FROM combat_engagement
            """
            + f" {where_sql} "
            + """
                  AND COALESCE(end_x, start_x) IS NOT NULL
                  AND COALESCE(end_y, start_y) IS NOT NULL
                GROUP BY 1, 2
            ) hz
            """,
            query_params,
        )

        track_row = None
        try:
            track_row = await db.fetch_one(
                "SELECT COUNT(*) AS tracks, "
                "COUNT(DISTINCT player_guid) AS unique_players, "
                "AVG(total_distance) AS avg_track_distance, "
                "AVG(avg_speed) AS avg_speed, "
                "AVG(sprint_percentage) AS avg_sprint_pct, "
                "AVG(CASE WHEN spawn_time_ms >= 0 THEN time_to_first_move_ms END) AS avg_time_to_first_move_ms "
                f"FROM player_track {where_sql}",
                query_params,
            )
        except Exception:
            track_row = None

        duo_rows = await db.fetch_all(
            "SELECT attackers, crossfire_participants, crossfire_delay_ms, outcome "
            f"FROM combat_engagement {where_sql} "
            "AND is_crossfire = TRUE "
            "ORDER BY session_date DESC, round_start_unix DESC, start_time_ms DESC "
            "LIMIT 5000",
            query_params,
        )
        guid_name_map = await _load_scoped_guid_name_map(db, where_sql, query_params)
        top_duos = _compute_scoped_duos(duo_rows, 10, guid_name_map=guid_name_map)

        # v5 teamplay counts
        v5_counts = {}
        for tbl in ['proximity_spawn_timing', 'proximity_team_cohesion',
                     'proximity_crossfire_opportunity', 'proximity_team_push',
                     'proximity_lua_trade_kill']:
            try:
                cnt = await db.fetch_val(
                    f"SELECT COUNT(*) FROM {tbl} {where_sql}", query_params
                )
                v5_counts[tbl] = int(cnt or 0)
            except Exception:
                v5_counts[tbl] = 0

        payload.update(
            {
                "status": "ok" if (total_engagements or 0) > 0 else "prototype",
                "ready": (total_engagements or 0) > 0,
                "message": None if (total_engagements or 0) > 0 else payload["message"],
                "scope": scope,
                "total_engagements": int(total_engagements or 0),
                "avg_distance_m": round(avg_distance, 1) if avg_distance is not None else None,
                "crossfire_events": int(crossfire_events or 0),
                "hotzones": int(hotzones or 0),
                "avg_duration_ms": round(avg_duration, 0) if avg_duration is not None else None,
                "avg_attackers": round(avg_attackers, 2) if avg_attackers is not None else None,
                "escape_rate_pct": round((escapes or 0) * 100 / total_engagements, 1)
                if total_engagements
                else None,
                "kill_rate_pct": round((kills or 0) * 100 / total_engagements, 1)
                if total_engagements
                else None,
                "unique_players": int(track_row[1]) if track_row else None,
                "avg_track_distance_m": round(track_row[2], 1)
                if track_row and track_row[2] is not None
                else None,
                "avg_speed": round(track_row[3], 2)
                if track_row and track_row[3] is not None
                else None,
                "avg_sprint_pct": round(track_row[4], 1)
                if track_row and track_row[4] is not None
                else None,
                "avg_time_to_first_move_ms": round(track_row[5], 0)
                if track_row and track_row[5] is not None
                else None,
                "sample_rounds": int(sample_rounds or 0),
                "top_duos": top_duos,
                "v5_counts": v5_counts,
            }
        )
    except Exception:
        payload.update(
            {
                "status": "error",
                "ready": False,
                "message": "Proximity query failed",
                "scope": scope,
                "total_engagements": None,
                "avg_distance_m": None,
                "crossfire_events": None,
                "hotzones": None,
                "sample_rounds": 0,
                "top_duos": [],
            }
        )
    return payload


@router.get("/proximity/engagements")
async def get_proximity_engagements(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
    player_guid: Optional[str] = None,
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
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
    player_guid: Optional[str] = None,
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
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
    player_guid: Optional[str] = None,
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


@router.get("/proximity/movers")
async def get_proximity_movers(
    range_days: int = 30,
    limit: int = 5,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
    player_guid: Optional[str] = None,
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


@router.get("/proximity/classes")
async def get_proximity_classes(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
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


@router.get("/proximity/reactions")
async def get_proximity_reactions(
    range_days: int = 30,
    limit: int = 5,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
    player_guid: Optional[str] = None,
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


@router.get("/proximity/teamplay")
async def get_proximity_teamplay(
    range_days: int = 30,
    limit: int = 5,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
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


@router.get("/proximity/trades/summary")
async def get_proximity_trades_summary(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Trade summary for scoped proximity analytics.
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
        row = await db.fetch_one(
            "SELECT COUNT(*) AS events, "
            "SUM(opportunity_count) AS opportunities, "
            "SUM(attempt_count) AS attempts, "
            "SUM(success_count) AS successes, "
            "SUM(missed_count) AS missed, "
            "SUM(CASE WHEN is_isolation_death THEN 1 ELSE 0 END) AS isolation_deaths "
            f"FROM proximity_trade_event {where_sql}",
            query_params,
        )
        events = row[0] if row else 0
        support_row = await db.fetch_one(
            "SELECT SUM(support_samples) AS support_samples, "
            "SUM(total_samples) AS total_samples "
            f"FROM proximity_support_summary {where_sql}",
            query_params,
        )
        support_samples = support_row[0] if support_row else None
        total_samples = support_row[1] if support_row else None
        support_pct = None
        if support_samples is not None and total_samples:
            support_pct = round(support_samples * 100 / total_samples, 2)
        payload.update(
            {
                "status": "ok" if (events or 0) > 0 else "prototype",
                "ready": (events or 0) > 0,
                "message": None if (events or 0) > 0 else payload["message"],
                "scope": scope,
                "events": int(events or 0),
                "trade_opportunities": int(row[1] or 0) if row else 0,
                "trade_attempts": int(row[2] or 0) if row else 0,
                "trade_success": int(row[3] or 0) if row else 0,
                "missed_trade_candidates": int(row[4] or 0) if row else 0,
                "support_uptime_pct": support_pct,
                "isolation_deaths": int(row[5] or 0) if row else 0,
            }
        )
    except Exception:
        payload.update(
            {
                "status": "error",
                "ready": False,
                "message": "Proximity query failed",
                "scope": scope,
                "events": 0,
                "trade_opportunities": 0,
                "trade_attempts": 0,
                "trade_success": 0,
                "missed_trade_candidates": 0,
                "support_uptime_pct": None,
                "isolation_deaths": None,
            }
        )
    return payload


@router.get("/proximity/trades/player-stats")
async def get_proximity_trades_player_stats(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Per-player trade kill stats for session detail views.
    Returns aggregated trade success/attempt/avenged counts per player.
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
        # Victim-side stats: how often were this player's deaths traded by teammates
        victim_query = f"""
            SELECT victim_guid AS guid, victim_name AS name,
                   SUM(opportunity_count) AS trade_opps,
                   SUM(attempt_count) AS trade_attempts,
                   SUM(success_count) AS trade_success,
                   SUM(missed_count) AS trade_missed,
                   SUM(CASE WHEN is_isolation_death THEN 1 ELSE 0 END) AS isolation_deaths
            FROM proximity_trade_event {where_sql}
            GROUP BY victim_guid, victim_name
        """
        victim_rows = await db.fetch_all(victim_query, query_params)

        # Avenger-side stats: how often did this player avenge a teammate's death
        # successes JSON array contains trader info: each element has trader_guid
        avenger_where, avenger_params, _ = _build_proximity_where_clause(
            range_days, session_date, map_name, round_number, round_start_unix,
            alias="e",
        )
        avenger_query = f"""
            SELECT
                s->>'guid' AS guid,
                s->>'name' AS name,
                COUNT(*) AS avenged_count,
                COUNT(DISTINCT e.id) AS avenger_attempt_events,
                COALESCE(SUM(CASE WHEN s->>'damage' IS NOT NULL THEN (s->>'damage')::numeric ELSE 0 END), 0) AS avenger_attempt_damage
            FROM proximity_trade_event e
            CROSS JOIN LATERAL jsonb_array_elements(
                COALESCE(e.successes, '[]'::jsonb)
            ) AS s
            {avenger_where}
            GROUP BY s->>'guid', s->>'name'
        """
        avenger_rows = await db.fetch_all(avenger_query, tuple(avenger_params))

        # Merge victim + avenger stats per player
        players_map = {}
        for row in victim_rows:
            guid = row[0] or ""
            short_guid = guid[:8] if len(guid) > 8 else guid
            key = short_guid or row[1]
            players_map[key] = {
                "guid": short_guid,
                "name": row[1],
                "trade_opps": int(row[2] or 0),
                "trade_attempts": int(row[3] or 0),
                "trade_success": int(row[4] or 0),
                "trade_missed": int(row[5] or 0),
                "isolation_deaths": int(row[6] or 0),
                "avenged_count": 0,
                "avenger_attempt_events": 0,
                "avenger_attempt_damage": 0,
            }
        for row in avenger_rows:
            guid = row[0] or ""
            short_guid = guid[:8] if len(guid) > 8 else guid
            key = short_guid or row[1]
            if key not in players_map:
                players_map[key] = {
                    "guid": short_guid,
                    "name": row[1],
                    "trade_opps": 0,
                    "trade_attempts": 0,
                    "trade_success": 0,
                    "trade_missed": 0,
                    "isolation_deaths": 0,
                    "avenged_count": 0,
                    "avenger_attempt_events": 0,
                    "avenger_attempt_damage": 0,
                }
            players_map[key]["avenged_count"] = int(row[2] or 0)
            players_map[key]["avenger_attempt_events"] = int(row[3] or 0)
            players_map[key]["avenger_attempt_damage"] = float(row[4] or 0)

        payload.update({
            "status": "ok" if players_map else "prototype",
            "ready": bool(players_map),
            "message": None if players_map else payload["message"],
            "scope": scope,
            "players": list(players_map.values()),
        })
    except Exception:
        payload.update({
            "status": "error",
            "ready": False,
            "message": "Proximity query failed",
            "scope": scope,
            "players": [],
        })
    return payload


@router.get("/proximity/trades/events")
async def get_proximity_trade_events(
    range_days: int = 30,
    limit: int = 50,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Latest trade events (scoped).
    """
    payload = _proximity_stub_meta(range_days)
    safe_limit = max(1, min(int(limit or 50), 250))
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
            db, "proximity_trade_event", "round_id"
        )
        if has_round_id_column:
            query = """
                SELECT e.session_date, e.round_number, e.map_name, e.victim_name, e.killer_name,
                       e.opportunity_count, e.attempt_count, e.success_count, e.missed_count,
                       COALESCE(r_exact.id, r_fallback.id) AS round_id,
                       COALESCE(r_exact.round_date, r_fallback.round_date) AS round_date,
                       COALESCE(r_exact.round_time, r_fallback.round_time) AS round_time
                FROM proximity_trade_event e
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
                SELECT e.session_date, e.round_number, e.map_name, e.victim_name, e.killer_name,
                       e.opportunity_count, e.attempt_count, e.success_count, e.missed_count,
                       r.id AS round_id, r.round_date, r.round_time
                FROM proximity_trade_event e
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
            + "ORDER BY e.session_date DESC, e.round_number DESC, e.death_time_ms DESC "
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
                        "date": row[0].isoformat(),
                        "round": row[1],
                        "map": row[2],
                        "victim": row[3],
                        "killer": row[4],
                        "opportunities": int(row[5] or 0),
                        "attempts": int(row[6] or 0),
                        "success": int(row[7] or 0),
                        "missed": int(row[8] or 0),
                        "round_id": row[9],
                        "round_date": row[10],
                        "round_time": row[11],
                        "outcome": (
                            "trade_success"
                            if (row[7] or 0) > 0
                            else "trade_attempt"
                            if (row[6] or 0) > 0
                            else "missed_candidate"
                            if (row[8] or 0) > 0
                            else "trade_event"
                        ),
                    }
                    for row in rows
                ],
            }
        )
    except Exception:
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


@router.get("/proximity/spawn-timing")
async def get_proximity_spawn_timing(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
    player_guid: Optional[str] = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Spawn timing efficiency leaderboard and team averages."""
    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
        player_guid=player_guid, player_guid_columns=["killer_guid", "victim_guid"],
    )
    query_params = tuple(params)
    try:
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
    except Exception:
        logger.warning("Proximity endpoint error", exc_info=True)
        return {"status": "error", "detail": "Internal error"}


@router.get("/proximity/cohesion")
async def get_proximity_cohesion(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Team cohesion: dispersion summary, timeline, and buddy pairs."""
    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
    )
    query_params = tuple(params)
    try:
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
    except Exception:
        logger.warning("Proximity endpoint error", exc_info=True)
        return {"status": "error", "detail": "Internal error"}


@router.get("/proximity/crossfire-angles")
async def get_proximity_crossfire_angles(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
    player_guid: Optional[str] = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Crossfire opportunity analysis: utilization rate, angle buckets, top duos."""
    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
        player_guid=player_guid, player_guid_columns=["teammate1_guid", "teammate2_guid"],
    )
    query_params = tuple(params)
    try:
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
    except Exception:
        logger.warning("Proximity endpoint error", exc_info=True)
        return {"status": "error", "detail": "Internal error"}


@router.get("/proximity/pushes")
async def get_proximity_pushes(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
    player_guid: Optional[str] = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Team push analysis: per-team summary and quality distribution."""
    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
        player_guid=player_guid, player_guid_columns=["team"],
    )
    query_params = tuple(params)
    try:
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
    except Exception:
        logger.warning("Proximity endpoint error", exc_info=True)
        return {"status": "error", "detail": "Internal error"}


@router.get("/proximity/lua-trades")
async def get_proximity_lua_trades(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
    player_guid: Optional[str] = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Lua-detected trade kill analysis."""
    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
        player_guid=player_guid, player_guid_columns=["trader_guid", "original_killer_guid", "original_victim_guid"],
    )
    query_params = tuple(params)
    try:
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
    except Exception:
        logger.warning("Proximity endpoint error", exc_info=True)
        return {"status": "error", "detail": "Internal error"}


@router.get("/proximity/events")
async def get_proximity_events(
    range_days: int = 30,
    limit: int = 250,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
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
        response["strafe"] = None

    return response


# ========================================
# PROXIMITY — PLAYER PROFILE & ROUND TIMELINE
# ========================================


@router.get("/proximity/player/{guid}/profile")
async def get_proximity_player_profile(
    guid: str,
    range_days: int = 90,
    db: DatabaseAdapter = Depends(get_db),
):
    """Aggregated player proximity stats for profile page."""
    since = datetime.utcnow().date() - timedelta(days=max(1, min(range_days, 3650)))
    try:
        # Engagement stats
        eng_stats = await db.fetch_one(
            """
            SELECT COUNT(*) AS total_engagements,
                   SUM(CASE WHEN outcome = 'escaped' THEN 1 ELSE 0 END) AS escapes,
                   SUM(CASE WHEN outcome = 'killed' THEN 1 ELSE 0 END) AS deaths,
                   ROUND(AVG(duration_ms)::numeric, 0) AS avg_duration,
                   ROUND(AVG(total_damage_taken)::numeric, 0) AS avg_damage_taken,
                   ROUND(AVG(distance_traveled)::numeric, 0) AS avg_distance,
                   SUM(CASE WHEN is_crossfire THEN 1 ELSE 0 END) AS crossfire_count
            FROM combat_engagement
            WHERE target_guid = $1 AND session_date >= $2
            """,
            (guid, since),
        )
        # Kill stats (as attacker)
        kill_stats = await db.fetch_one(
            """
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
            """,
            (guid, since),
        )
        # Spawn timing
        spawn_timing = await db.fetch_one(
            """
            SELECT ROUND(AVG(spawn_timing_score)::numeric, 3) AS avg_score,
                   COUNT(*) AS timed_kills,
                   ROUND(AVG(time_to_next_spawn)::numeric, 0) AS avg_denial_ms
            FROM proximity_spawn_timing
            WHERE killer_guid = $1 AND session_date >= $2
            """,
            (guid, since),
        )
        # Reaction metrics
        reactions = await db.fetch_one(
            """
            SELECT ROUND(AVG(return_fire_ms)::numeric, 0) AS avg_return_fire,
                   ROUND(AVG(dodge_reaction_ms)::numeric, 0) AS avg_dodge,
                   ROUND(AVG(support_reaction_ms)::numeric, 0) AS avg_support,
                   COUNT(*) AS reaction_samples
            FROM proximity_reaction_metric
            WHERE target_guid = $1 AND session_date >= $2
            """,
            (guid, since),
        )
        # Movement stats
        movement = await db.fetch_one(
            """
            SELECT ROUND(AVG(avg_speed)::numeric, 1) AS avg_speed,
                   ROUND(AVG(sprint_percentage)::numeric, 1) AS avg_sprint_pct,
                   ROUND(AVG(total_distance)::numeric, 0) AS avg_distance_per_life,
                   COUNT(*) AS tracks
            FROM player_track
            WHERE player_guid = $1 AND session_date >= $2
            """,
            (guid, since),
        )
        # Trade kills
        trade_stats = await db.fetch_one(
            """
            SELECT COUNT(*) AS trades_made
            FROM proximity_lua_trade_kill
            WHERE trader_guid = $1 AND session_date >= $2
            """,
            (guid, since),
        )

        # Player name lookup
        name_row = await db.fetch_one(
            "SELECT player_name FROM player_track WHERE player_guid = $1 ORDER BY session_date DESC LIMIT 1",
            (guid,),
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
        logger.warning("Proximity endpoint error", exc_info=True)
        return {"status": "error", "detail": "Internal error"}


@router.get("/proximity/player/{guid}/radar")
async def get_proximity_player_radar(
    guid: str,
    range_days: int = 90,
    db: DatabaseAdapter = Depends(get_db),
):
    """5-axis radar data: Aggression, Awareness, Teamplay, Timing, Mechanical."""
    since = datetime.utcnow().date() - timedelta(days=max(1, min(range_days, 3650)))
    try:
        # Aggression: sprint %, avg speed, distance per life
        aggression_row = await db.fetch_one(
            """
            SELECT ROUND(AVG(sprint_percentage)::numeric, 1),
                   ROUND(AVG(avg_speed)::numeric, 1)
            FROM player_track WHERE player_guid = $1 AND session_date >= $2
            """, (guid, since),
        )
        sprint_pct = float(aggression_row[0] or 0) if aggression_row else 0
        avg_speed = float(aggression_row[1] or 0) if aggression_row else 0
        aggression = min(100, (sprint_pct * 0.6) + (min(avg_speed / 300, 1) * 100 * 0.4))

        # Awareness: escape rate + dodge reaction
        awareness_row = await db.fetch_one(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN outcome = 'escaped' THEN 1 ELSE 0 END) AS escapes
            FROM combat_engagement WHERE target_guid = $1 AND session_date >= $2
            """, (guid, since),
        )
        dodge_row = await db.fetch_one(
            """
            SELECT ROUND(AVG(dodge_reaction_ms)::numeric, 0)
            FROM proximity_reaction_metric
            WHERE target_guid = $1 AND dodge_reaction_ms IS NOT NULL AND session_date >= $2
            """, (guid, since),
        )
        total_eng = int(awareness_row[0] or 0) if awareness_row else 0
        escapes = int(awareness_row[1] or 0) if awareness_row else 0
        escape_rate = escapes / max(total_eng, 1) * 100
        dodge_ms = int(dodge_row[0] or 5000) if dodge_row and dodge_row[0] else 5000
        dodge_score = max(0, 100 - (dodge_ms / 50))  # Lower dodge = better
        awareness = min(100, escape_rate * 0.5 + dodge_score * 0.5)

        # Teamplay: crossfire participation + trade kills (per-session average)
        cf_row = await db.fetch_one(
            """
            SELECT COUNT(*),
                   COUNT(DISTINCT session_date)
            FROM proximity_crossfire_opportunity
            WHERE (teammate1_guid = $1 OR teammate2_guid = $1) AND was_executed = true
            AND session_date >= $2
            """, (guid, since),
        )
        trade_row = await db.fetch_one(
            """
            SELECT COUNT(*),
                   COUNT(DISTINCT session_date)
            FROM proximity_lua_trade_kill WHERE trader_guid = $1 AND session_date >= $2
            """, (guid, since),
        )
        cf_total = int(cf_row[0] or 0) if cf_row else 0
        cf_sessions = max(1, int(cf_row[1] or 1) if cf_row else 1)
        trade_total = int(trade_row[0] or 0) if trade_row else 0
        trade_sessions = max(1, int(trade_row[1] or 1) if trade_row else 1)
        # Per-session rates with saturation at 5 crossfires/session and 3 trades/session
        cf_per_session = cf_total / cf_sessions
        trade_per_session = trade_total / trade_sessions
        teamplay = min(100, (min(cf_per_session / 5, 1) * 50) + (min(trade_per_session / 3, 1) * 50))

        # Timing: spawn timing score
        timing_row = await db.fetch_one(
            """
            SELECT ROUND(AVG(spawn_timing_score)::numeric, 3), COUNT(*)
            FROM proximity_spawn_timing WHERE killer_guid = $1 AND session_date >= $2
            """, (guid, since),
        )
        avg_timing = float(timing_row[0] or 0) if timing_row else 0
        timing_count = int(timing_row[1] or 0) if timing_row else 0
        timing = min(100, avg_timing * 100 * min(timing_count / 5, 1))

        # Mechanical: return fire speed + kills
        rf_row = await db.fetch_one(
            """
            SELECT ROUND(AVG(return_fire_ms)::numeric, 0)
            FROM proximity_reaction_metric
            WHERE target_guid = $1 AND return_fire_ms IS NOT NULL AND session_date >= $2
            """, (guid, since),
        )
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
        logger.warning("Proximity endpoint error", exc_info=True)
        return {"status": "error", "detail": "Internal error"}


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


@router.get("/proximity/weapon-accuracy")
async def get_proximity_weapon_accuracy(
    range_days: int = 30,
    player_guid: Optional[str] = None,
    map_name: Optional[str] = None,
    limit: int = 20,
    db: DatabaseAdapter = Depends(get_db),
):
    """Weapon accuracy leaderboard or per-player breakdown."""
    safe_limit = max(1, min(limit, 50))
    try:
        clauses = ["shots_fired >= 10"]
        params: list = []

        if player_guid:
            params.append(player_guid.strip())
            clauses.append(f"player_guid = ${len(params)}")
        if map_name:
            params.append(map_name.strip())
            clauses.append(f"map_name = ${len(params)}")

        where = "WHERE " + " AND ".join(clauses)

        rows = await db.fetch_all(
            f"""
            SELECT player_guid, MAX(player_name) AS name,
                   SUM(shots_fired) AS total_shots,
                   SUM(hits) AS total_hits,
                   SUM(kills) AS total_kills,
                   SUM(headshots) AS total_hs,
                   ROUND((SUM(hits)::numeric / NULLIF(SUM(shots_fired), 0)) * 100, 1) AS accuracy
            FROM proximity_weapon_accuracy {where}
            GROUP BY player_guid
            ORDER BY accuracy DESC
            LIMIT ${len(params) + 1}
            """,
            tuple(params) + (safe_limit,),
        )

        # Per-weapon breakdown (if player_guid specified)
        weapon_breakdown = []
        if player_guid:
            wrows = await db.fetch_all(
                """
                SELECT weapon_id, SUM(shots_fired), SUM(hits), SUM(kills), SUM(headshots),
                       ROUND((SUM(hits)::numeric / NULLIF(SUM(shots_fired), 0)) * 100, 1)
                FROM proximity_weapon_accuracy
                WHERE player_guid = $1 AND shots_fired > 0
                GROUP BY weapon_id ORDER BY SUM(kills) DESC
                """,
                (player_guid.strip(),),
            )
            weapon_breakdown = [
                {
                    "weapon_id": r[0],
                    "shots": int(r[1] or 0), "hits": int(r[2] or 0),
                    "kills": int(r[3] or 0), "headshots": int(r[4] or 0),
                    "accuracy": float(r[5] or 0),
                }
                for r in (wrows or [])
            ]

        return {
            "status": "ok",
            "leaders": [
                {
                    "guid": r[0], "name": r[1],
                    "shots": int(r[2] or 0), "hits": int(r[3] or 0),
                    "kills": int(r[4] or 0), "headshots": int(r[5] or 0),
                    "accuracy": float(r[6] or 0),
                }
                for r in (rows or [])
            ],
            "weapon_breakdown": weapon_breakdown,
        }
    except Exception:
        logger.warning("Proximity endpoint error", exc_info=True)
        return {"status": "error", "detail": "Internal error"}


@router.get("/proximity/revives")
async def get_proximity_revives(
    range_days: int = 30,
    map_name: Optional[str] = None,
    player_guid: Optional[str] = None,
    limit: int = 20,
    db: DatabaseAdapter = Depends(get_db),
):
    """Revive summary and medic leaderboard from proximity_revive table."""
    safe_limit = max(1, min(limit, 50))
    try:
        clauses: list[str] = []
        params: list = []

        if map_name:
            params.append(map_name.strip())
            clauses.append(f"map_name = ${len(params)}")
        if player_guid:
            params.append(player_guid.strip())
            clauses.append(f"medic_guid = ${len(params)}")

        # Apply range_days filter
        params.append(range_days)
        clauses.append(f"session_date >= CURRENT_DATE - ${len(params)} * INTERVAL '1 day'")

        where_sql = "WHERE " + " AND ".join(clauses)
        medic_filter = "medic_guid IS NOT NULL AND medic_guid != ''"
        medic_where = "WHERE " + " AND ".join(clauses + [medic_filter])
        query_params = tuple(params)

        # Summary
        summary_row = await db.fetch_one(
            f"""
            SELECT COUNT(*) AS total_revives,
                   ROUND(AVG(distance_to_enemy)::numeric, 0) AS avg_enemy_distance,
                   ROUND(100.0 * SUM(CASE WHEN under_fire THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS under_fire_pct
            FROM proximity_revive {where_sql}
            """,
            query_params,
        )

        summary = {
            "total_revives": int(summary_row[0] or 0) if summary_row else 0,
            "avg_enemy_distance": float(summary_row[1] or 0) if summary_row else 0,
            "under_fire_pct": float(summary_row[2] or 0) if summary_row else 0,
        }

        # Medic leaderboard
        rows = await db.fetch_all(
            f"""
            SELECT medic_guid, MAX(medic_name) AS name,
                   COUNT(*) AS revives,
                   SUM(CASE WHEN under_fire THEN 1 ELSE 0 END) AS under_fire_count,
                   ROUND(AVG(distance_to_enemy)::numeric, 0) AS avg_enemy_dist
            FROM proximity_revive {medic_where}
            GROUP BY medic_guid
            HAVING COUNT(*) >= 2
            ORDER BY COUNT(*) DESC
            LIMIT ${len(params) + 1}
            """,
            query_params + (safe_limit,),
        )

        leaders = [
            {
                "guid": r[0], "name": r[1],
                "revives": int(r[2] or 0),
                "under_fire_count": int(r[3] or 0),
                "avg_enemy_dist": float(r[4] or 0),
            }
            for r in (rows or [])
        ]

        return {"status": "ok", "summary": summary, "leaders": leaders}
    except Exception:
        logger.warning("Proximity revives endpoint error", exc_info=True)
        return {"status": "error", "detail": "Internal error"}


@router.get("/proximity/session-scores")
async def get_proximity_session_scores(
    session_date: Optional[str] = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Per-session composite proximity combat scores (0-100) across 7 categories."""
    try:
        from bot.services.proximity_session_score_service import ProximitySessionScoreService
        svc = ProximitySessionScoreService(db)

        if not session_date:
            session_date = await svc.get_latest_session_date()
        if not session_date:
            return {"status": "ok", "session_date": None, "players": []}

        results = await svc.compute_session_scores(session_date)
        return {"status": "ok", "session_date": session_date, "players": results}
    except Exception:
        logger.warning("Proximity endpoint error", exc_info=True)
        return {"status": "error", "detail": "Internal error"}


@router.get("/proximity/leaderboards")
async def get_proximity_leaderboards(
    category: str = "power",
    range_days: int = 30,
    limit: int = 10,
    db: DatabaseAdapter = Depends(get_db),
):
    """Multi-category proximity leaderboards."""
    safe_limit = max(1, min(limit, 50))
    since = datetime.utcnow().date() - timedelta(days=max(1, min(range_days, 3650)))

    try:
        if category == "power":
            # Composite radar score — batch queries (7 queries total, not per-player)
            # 1. Engagement stats + names per player
            eng_rows = await db.fetch_all(
                """
                SELECT target_guid, MAX(target_name) AS name,
                       COUNT(*) AS total,
                       SUM(CASE WHEN outcome = 'escaped' THEN 1 ELSE 0 END) AS escapes
                FROM combat_engagement
                WHERE session_date >= $1
                GROUP BY target_guid
                HAVING COUNT(*) >= 5
                ORDER BY COUNT(*) DESC
                LIMIT 100
                """,
                (since,),
            )
            if not eng_rows:
                return {"status": "ok", "category": "power", "entries": []}

            guid_set = {r[0] for r in eng_rows}
            eng_map: Dict[str, dict] = {}
            for r in eng_rows:
                eng_map[r[0]] = {"name": r[1] or r[0][:8], "total": int(r[2] or 0), "escapes": int(r[3] or 0)}

            # 2. Movement (aggression axis)
            move_rows = await db.fetch_all(
                """
                SELECT player_guid,
                       ROUND(AVG(sprint_percentage)::numeric, 1) AS sp,
                       ROUND(AVG(avg_speed)::numeric, 1) AS spd
                FROM player_track
                WHERE session_date >= $1
                GROUP BY player_guid
                """,
                (since,),
            )
            move_map: Dict[str, Tuple[float, float]] = {}
            for r in (move_rows or []):
                if r[0] in guid_set:
                    move_map[r[0]] = (float(r[1] or 0), float(r[2] or 0))

            # 3. Dodge reaction (awareness axis)
            dodge_rows = await db.fetch_all(
                """
                SELECT target_guid,
                       ROUND(AVG(dodge_reaction_ms)::numeric, 0) AS avg_dodge
                FROM proximity_reaction_metric
                WHERE dodge_reaction_ms IS NOT NULL AND session_date >= $1
                GROUP BY target_guid
                """,
                (since,),
            )
            dodge_map: Dict[str, int] = {}
            for r in (dodge_rows or []):
                if r[0] in guid_set:
                    dodge_map[r[0]] = int(r[1] or 5000)

            # 4. Crossfire participation (teamplay axis)
            cf_rows = await db.fetch_all(
                """
                SELECT guid, SUM(cnt) AS total FROM (
                    SELECT teammate1_guid AS guid, COUNT(*) AS cnt
                    FROM proximity_crossfire_opportunity
                    WHERE was_executed = true AND session_date >= $1
                    GROUP BY teammate1_guid
                    UNION ALL
                    SELECT teammate2_guid AS guid, COUNT(*) AS cnt
                    FROM proximity_crossfire_opportunity
                    WHERE was_executed = true AND session_date >= $1
                    GROUP BY teammate2_guid
                ) sub GROUP BY guid
                """,
                (since,),
            )
            cf_map: Dict[str, int] = {}
            for r in (cf_rows or []):
                if r[0] in guid_set:
                    cf_map[r[0]] = int(r[1] or 0)

            # 5. Trade kills (teamplay axis)
            trade_rows = await db.fetch_all(
                """
                SELECT trader_guid, COUNT(*) AS cnt
                FROM proximity_lua_trade_kill
                WHERE session_date >= $1
                GROUP BY trader_guid
                """,
                (since,),
            )
            trade_map: Dict[str, int] = {}
            for r in (trade_rows or []):
                if r[0] in guid_set:
                    trade_map[r[0]] = int(r[1] or 0)

            # 6. Spawn timing (timing axis)
            timing_rows = await db.fetch_all(
                """
                SELECT killer_guid,
                       ROUND(AVG(spawn_timing_score)::numeric, 3) AS avg_score,
                       COUNT(*) AS cnt
                FROM proximity_spawn_timing
                WHERE session_date >= $1
                GROUP BY killer_guid
                """,
                (since,),
            )
            timing_map: Dict[str, Tuple[float, int]] = {}
            for r in (timing_rows or []):
                if r[0] in guid_set:
                    timing_map[r[0]] = (float(r[1] or 0), int(r[2] or 0))

            # 7. Return fire (mechanical axis)
            rf_rows = await db.fetch_all(
                """
                SELECT target_guid,
                       ROUND(AVG(return_fire_ms)::numeric, 0) AS avg_rf
                FROM proximity_reaction_metric
                WHERE return_fire_ms IS NOT NULL AND session_date >= $1
                GROUP BY target_guid
                """,
                (since,),
            )
            rf_map: Dict[str, int] = {}
            for r in (rf_rows or []):
                if r[0] in guid_set:
                    rf_map[r[0]] = int(r[1] or 3000)

            # Compute composite scores
            results = []
            for g, info in eng_map.items():
                sp, spd = move_map.get(g, (0.0, 0.0))
                aggression = min(100, sp * 0.6 + min(spd / 300, 1) * 100 * 0.4)

                esc_rate = info["escapes"] / max(info["total"], 1) * 100
                d_ms = dodge_map.get(g, 5000)
                awareness = min(100, esc_rate * 0.5 + max(0, 100 - d_ms / 50) * 0.5)

                cf_c = cf_map.get(g, 0)
                tr_c = trade_map.get(g, 0)
                teamplay = min(100, min(cf_c / 5, 1) * 50 + min(tr_c / 3, 1) * 50)

                avg_tm, tm_cnt = timing_map.get(g, (0.0, 0))
                timing = min(100, avg_tm * 100 * min(tm_cnt / 5, 1))

                rf_ms = rf_map.get(g, 3000)
                mechanical = min(100, max(0, 100 - rf_ms / 30))

                composite = round((aggression + awareness + teamplay + timing + mechanical) / 5, 1)
                results.append({
                    "guid": g, "name": info["name"], "value": composite,
                    "axes": {
                        "aggression": round(aggression, 1), "awareness": round(awareness, 1),
                        "teamplay": round(teamplay, 1), "timing": round(timing, 1),
                        "mechanical": round(mechanical, 1),
                    },
                })

            results.sort(key=lambda x: x["value"], reverse=True)
            return {"status": "ok", "category": "power", "entries": results[:safe_limit]}

        elif category == "spawn":
            rows = await db.fetch_all(
                """
                SELECT killer_guid, MAX(killer_name) AS name,
                       COUNT(*) AS timed_kills,
                       ROUND(AVG(spawn_timing_score)::numeric, 3) AS avg_score,
                       ROUND(AVG(time_to_next_spawn)::numeric, 0) AS avg_denial_ms
                FROM proximity_spawn_timing
                WHERE session_date >= $1
                GROUP BY killer_guid
                HAVING COUNT(*) >= 3
                ORDER BY avg_score DESC
                LIMIT $2
                """,
                (since, safe_limit),
            )
            return {
                "status": "ok", "category": "spawn",
                "entries": [
                    {"guid": r[0], "name": r[1], "timed_kills": int(r[2] or 0),
                     "value": float(r[3] or 0), "avg_denial_ms": int(r[4] or 0)}
                    for r in (rows or [])
                ],
            }

        elif category == "crossfire":
            rows = await db.fetch_all(
                """
                SELECT guid, name, SUM(cnt) AS total, ROUND(AVG(avg_angle)::numeric, 1) AS avg_angle
                FROM (
                    SELECT teammate1_guid AS guid, MAX(teammate1_guid) AS name,
                           COUNT(*) AS cnt, AVG(angular_separation) AS avg_angle
                    FROM proximity_crossfire_opportunity
                    WHERE was_executed = true AND session_date >= $1
                    GROUP BY teammate1_guid
                    UNION ALL
                    SELECT teammate2_guid AS guid, MAX(teammate2_guid) AS name,
                           COUNT(*) AS cnt, AVG(angular_separation) AS avg_angle
                    FROM proximity_crossfire_opportunity
                    WHERE was_executed = true AND session_date >= $1
                    GROUP BY teammate2_guid
                ) sub GROUP BY guid, name
                ORDER BY total DESC
                LIMIT $2
                """,
                (since, safe_limit),
            )
            return {
                "status": "ok", "category": "crossfire",
                "entries": [
                    {"guid": r[0], "name": r[1], "value": int(r[2] or 0),
                     "avg_angle": float(r[3] or 0)}
                    for r in (rows or [])
                ],
            }

        elif category == "trades":
            rows = await db.fetch_all(
                """
                SELECT trader_guid, MAX(trader_name) AS name,
                       COUNT(*) AS trades,
                       ROUND(AVG(delta_ms)::numeric, 0) AS avg_reaction
                FROM proximity_lua_trade_kill
                WHERE session_date >= $1
                GROUP BY trader_guid
                HAVING COUNT(*) >= 2
                ORDER BY trades DESC
                LIMIT $2
                """,
                (since, safe_limit),
            )
            return {
                "status": "ok", "category": "trades",
                "entries": [
                    {"guid": r[0], "name": r[1], "value": int(r[2] or 0),
                     "avg_reaction_ms": int(r[3] or 0)}
                    for r in (rows or [])
                ],
            }

        elif category == "reactions":
            rows = await db.fetch_all(
                """
                SELECT target_guid, MAX(target_name) AS name,
                       ROUND(AVG(return_fire_ms)::numeric, 0) AS avg_rf,
                       COUNT(*) AS samples
                FROM proximity_reaction_metric
                WHERE return_fire_ms IS NOT NULL AND session_date >= $1
                GROUP BY target_guid
                HAVING COUNT(*) >= 3
                ORDER BY avg_rf ASC
                LIMIT $2
                """,
                (since, safe_limit),
            )
            return {
                "status": "ok", "category": "reactions",
                "entries": [
                    {"guid": r[0], "name": r[1], "value": int(r[2] or 0),
                     "samples": int(r[3] or 0)}
                    for r in (rows or [])
                ],
            }

        elif category == "survivors":
            rows = await db.fetch_all(
                """
                SELECT target_guid, MAX(target_name) AS name,
                       ROUND(SUM(CASE WHEN outcome = 'escaped' THEN 1 ELSE 0 END)::numeric * 100
                             / NULLIF(COUNT(*), 0), 1) AS escape_pct,
                       COUNT(*) AS total_engagements,
                       ROUND(AVG(duration_ms)::numeric, 0) AS avg_duration
                FROM combat_engagement
                WHERE session_date >= $1
                GROUP BY target_guid
                HAVING COUNT(*) >= 5
                ORDER BY escape_pct DESC
                LIMIT $2
                """,
                (since, safe_limit),
            )
            return {
                "status": "ok", "category": "survivors",
                "entries": [
                    {"guid": r[0], "name": r[1], "value": float(r[2] or 0),
                     "total_engagements": int(r[3] or 0), "avg_duration_ms": int(r[4] or 0)}
                    for r in (rows or [])
                ],
            }

        elif category == "movement":
            rows = await db.fetch_all(
                """
                SELECT player_guid, MAX(player_name) AS name,
                       ROUND(AVG(avg_speed)::numeric, 1) AS avg_speed,
                       ROUND(AVG(sprint_percentage)::numeric, 1) AS sprint_pct,
                       SUM(total_distance)::int AS total_distance,
                       COUNT(*) AS tracks
                FROM player_track
                WHERE session_date >= $1
                GROUP BY player_guid
                HAVING COUNT(*) >= 3
                ORDER BY avg_speed DESC
                LIMIT $2
                """,
                (since, safe_limit),
            )
            return {
                "status": "ok", "category": "movement",
                "entries": [
                    {"guid": r[0], "name": r[1], "value": float(r[2] or 0),
                     "sprint_pct": float(r[3] or 0), "total_distance": int(r[4] or 0),
                     "tracks": int(r[5] or 0)}
                    for r in (rows or [])
                ],
            }

        elif category == "focus_fire":
            rows = await db.fetch_all(
                """
                SELECT target_guid, MAX(target_name) AS name,
                       COUNT(*) AS times_focused,
                       ROUND(AVG(focus_score)::numeric, 3) AS avg_score,
                       ROUND(AVG(attacker_count)::numeric, 1) AS avg_attackers,
                       ROUND(AVG(total_damage)::numeric, 0) AS avg_damage
                FROM proximity_focus_fire
                WHERE session_date >= $1
                GROUP BY target_guid
                HAVING COUNT(*) >= 2
                ORDER BY avg_score DESC
                LIMIT $2
                """,
                (since, safe_limit),
            )
            return {
                "status": "ok", "category": "focus_fire",
                "entries": [
                    {"guid": r[0], "name": r[1], "times_focused": int(r[2] or 0),
                     "value": float(r[3] or 0), "avg_attackers": float(r[4] or 0),
                     "avg_damage": int(r[5] or 0)}
                    for r in (rows or [])
                ],
            }

        else:
            return {"status": "error", "detail": f"Unknown category: {category}. Valid: power, spawn, crossfire, trades, reactions, survivors, movement, focus_fire"}

    except Exception:
        logger.warning("Proximity endpoint error", exc_info=True)
        return {"status": "error", "detail": "Internal error"}


# ===== KILL OUTCOMES (v5.2) =====


@router.get("/proximity/kill-outcomes")
async def get_proximity_kill_outcomes(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
    player_guid: Optional[str] = None,
    limit: int = 200,
    db: DatabaseAdapter = Depends(get_db),
):
    """Kill outcome summary and events — gib/revive/tapout breakdown."""
    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
        player_guid=player_guid, player_guid_columns=["victim_guid", "killer_guid"],
    )
    query_params = tuple(params)
    try:
        # Summary by outcome type
        summary_rows = await db.fetch_all(
            f"""
            SELECT outcome, COUNT(*) AS cnt,
                   ROUND(AVG(delta_ms)::numeric, 0) AS avg_delta,
                   ROUND(AVG(effective_denied_ms)::numeric, 0) AS avg_denied
            FROM proximity_kill_outcome {where_sql}
            GROUP BY outcome
            ORDER BY cnt DESC
            """,
            query_params,
        )
        total = sum(int(r[1] or 0) for r in (summary_rows or []))
        outcome_map = {}
        for r in (summary_rows or []):
            outcome_map[r[0]] = {
                "count": int(r[1] or 0),
                "avg_delta_ms": int(r[2] or 0),
                "avg_denied_ms": int(r[3] or 0),
            }
        gibbed = outcome_map.get("gibbed", {}).get("count", 0)
        revived = outcome_map.get("revived", {}).get("count", 0)
        tapped = outcome_map.get("tapped_out", {}).get("count", 0)

        # Recent events
        safe_limit = max(1, min(limit, 500))
        events = await db.fetch_all(
            f"""
            SELECT kill_time, victim_guid, victim_name, killer_guid, killer_name,
                   kill_mod, outcome, delta_ms, effective_denied_ms,
                   gibber_guid, gibber_name, reviver_guid, reviver_name,
                   session_date, map_name, round_number
            FROM proximity_kill_outcome {where_sql}
            ORDER BY session_date DESC, kill_time DESC
            LIMIT {safe_limit}
            """,
            query_params,
        )

        return {
            "status": "ok",
            "scope": scope,
            "summary": {
                "total_kills": total,
                "gibbed": gibbed,
                "revived": revived,
                "tapped_out": tapped,
                "expired": outcome_map.get("expired", {}).get("count", 0),
                "round_end": outcome_map.get("round_end", {}).get("count", 0),
                "gib_rate": round(gibbed * 100.0 / total, 1) if total > 0 else 0,
                "revive_rate": round(revived * 100.0 / total, 1) if total > 0 else 0,
                "avg_delta_ms": outcome_map.get("gibbed", {}).get("avg_delta_ms", 0),
                "avg_denied_ms": outcome_map.get("gibbed", {}).get("avg_denied_ms", 0),
            },
            "outcomes": outcome_map,
            "events": [
                {
                    "kill_time": int(r[0] or 0),
                    "victim_guid": r[1], "victim_name": r[2],
                    "killer_guid": r[3], "killer_name": r[4],
                    "kill_mod": int(r[5] or 0),
                    "outcome": r[6],
                    "delta_ms": int(r[7] or 0),
                    "effective_denied_ms": int(r[8] or 0),
                    "gibber_guid": r[9] or "", "gibber_name": r[10] or "",
                    "reviver_guid": r[11] or "", "reviver_name": r[12] or "",
                    "session_date": r[13].isoformat() if r[13] else None,
                    "map_name": r[14], "round_number": int(r[15] or 0),
                }
                for r in (events or [])
            ],
        }
    except Exception:
        logger.warning("Proximity kill-outcomes error", exc_info=True)
        return {"status": "error", "detail": "Internal error"}


@router.get("/proximity/kill-outcomes/player-stats")
async def get_proximity_kill_outcomes_player_stats(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    player_guid: Optional[str] = None,
    limit: int = 20,
    db: DatabaseAdapter = Depends(get_db),
):
    """Per-player kill outcome stats — Kill Permanence Rate (KPR) and revive rates."""
    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, None, None,
    )
    query_params = tuple(params)
    safe_limit = max(1, min(limit, 50))
    try:
        # As killer: how permanent are their kills?
        killer_rows = await db.fetch_all(
            f"""
            SELECT killer_guid, MAX(killer_name) AS name,
                   COUNT(*) AS total_kills,
                   SUM(CASE WHEN outcome = 'gibbed' THEN 1 ELSE 0 END) AS gibs,
                   SUM(CASE WHEN outcome = 'revived' THEN 1 ELSE 0 END) AS revives,
                   SUM(CASE WHEN outcome = 'tapped_out' THEN 1 ELSE 0 END) AS tapouts,
                   ROUND(AVG(effective_denied_ms)::numeric, 0) AS avg_denied_ms
            FROM proximity_kill_outcome {where_sql}
            AND killer_guid != ''
            GROUP BY killer_guid
            HAVING COUNT(*) >= 3
            ORDER BY (SUM(CASE WHEN outcome = 'gibbed' THEN 1 ELSE 0 END)::float
                     / NULLIF(SUM(CASE WHEN outcome IN ('gibbed','revived') THEN 1 ELSE 0 END), 0)) DESC NULLS LAST
            LIMIT {safe_limit}
            """,
            query_params,
        )
        # As victim: how often are they revived?
        victim_rows = await db.fetch_all(
            f"""
            SELECT victim_guid, MAX(victim_name) AS name,
                   COUNT(*) AS times_killed,
                   SUM(CASE WHEN outcome = 'gibbed' THEN 1 ELSE 0 END) AS times_gibbed,
                   SUM(CASE WHEN outcome = 'revived' THEN 1 ELSE 0 END) AS times_revived,
                   SUM(CASE WHEN outcome = 'tapped_out' THEN 1 ELSE 0 END) AS times_tapped,
                   ROUND(AVG(delta_ms)::numeric, 0) AS avg_wait_ms
            FROM proximity_kill_outcome {where_sql}
            GROUP BY victim_guid
            HAVING COUNT(*) >= 3
            ORDER BY (SUM(CASE WHEN outcome = 'revived' THEN 1 ELSE 0 END)::float
                     / NULLIF(COUNT(*), 0)) DESC NULLS LAST
            LIMIT {safe_limit}
            """,
            query_params,
        )

        def _killer_stats(r):
            total = int(r[2] or 0)
            gibs = int(r[3] or 0)
            revs = int(r[4] or 0)
            contested = gibs + revs
            return {
                "guid": r[0], "name": r[1],
                "total_kills": total,
                "gibs": gibs, "revives_against": revs, "tapouts": int(r[5] or 0),
                "kpr": round(gibs / contested, 3) if contested > 0 else 0,
                "avg_denied_ms": int(r[6] or 0),
            }

        def _victim_stats(r):
            total = int(r[2] or 0)
            gibbed = int(r[3] or 0)
            revived = int(r[4] or 0)
            return {
                "guid": r[0], "name": r[1],
                "times_killed": total,
                "times_gibbed": gibbed, "times_revived": revived,
                "times_tapped": int(r[5] or 0),
                "revive_rate": round(revived / total, 3) if total > 0 else 0,
                "gib_rate": round(gibbed / total, 3) if total > 0 else 0,
                "avg_wait_ms": int(r[6] or 0),
            }

        # If specific player requested, filter
        as_killer = [_killer_stats(r) for r in (killer_rows or [])]
        as_victim = [_victim_stats(r) for r in (victim_rows or [])]
        if player_guid and player_guid.strip():
            g = player_guid.strip()
            as_killer = [s for s in as_killer if s["guid"] == g] or as_killer[:1]
            as_victim = [s for s in as_victim if s["guid"] == g] or as_victim[:1]

        return {
            "status": "ok",
            "scope": scope,
            "kill_permanence_leaders": as_killer,
            "revive_rate_leaders": as_victim,
        }
    except Exception:
        logger.warning("Proximity kill-outcomes player-stats error", exc_info=True)
        return {"status": "error", "detail": "Internal error"}


# ===== HIT REGIONS (v5.2) =====


@router.get("/proximity/hit-regions")
async def get_proximity_hit_regions(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
    player_guid: Optional[str] = None,
    weapon_id: Optional[int] = None,
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
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
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
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
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


# ===== COMBAT POSITIONS (v5.2) =====


@router.get("/proximity/combat-positions/heatmap")
async def get_proximity_combat_positions_heatmap(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    weapon_id: Optional[int] = None,
    victim_class: Optional[str] = None,
    perspective: str = "kills",
    team: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
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
    map_name: Optional[str] = None,
    weapon_id: Optional[int] = None,
    attacker_guid: Optional[str] = None,
    session_date: Optional[str] = None,
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
    map_name: Optional[str] = None,
    victim_class: Optional[str] = None,
    session_date: Optional[str] = None,
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


# ===== MOVEMENT ANALYTICS (Phase A) =====

@router.get("/proximity/movement-stats")
async def get_proximity_movement_stats(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    player_guid: Optional[str] = None,
    limit: int = 20,
    db: DatabaseAdapter = Depends(get_db),
):
    """Per-player aggregated movement analytics from path samples."""
    where_parts = ["peak_speed IS NOT NULL"]
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
    if player_guid:
        params.append(player_guid)
        where_parts.append(f"player_guid = ${len(params)}")

    where_sql = "WHERE " + " AND ".join(where_parts)
    safe_limit = max(1, min(limit, 50))
    scope = {"session_date": session_date, "map_name": map_name, "player_guid": player_guid}

    try:
        rows = await db.fetch_all(
            f"""
            SELECT player_guid, MAX(player_name) AS name,
                   COUNT(*) AS tracks,
                   ROUND(SUM(duration_ms)::numeric / 1000, 1) AS alive_sec,
                   ROUND(AVG(peak_speed)::numeric, 1) AS avg_peak_speed,
                   ROUND(MAX(peak_speed)::numeric, 1) AS max_peak_speed,
                   ROUND(AVG(avg_speed)::numeric, 1) AS avg_speed,
                   ROUND(SUM(total_distance)::numeric, 0) AS total_distance,
                   ROUND(SUM(stance_standing_sec)::numeric, 1) AS standing_sec,
                   ROUND(SUM(stance_crouching_sec)::numeric, 1) AS crouching_sec,
                   ROUND(SUM(stance_prone_sec)::numeric, 1) AS prone_sec,
                   ROUND(SUM(sprint_sec)::numeric, 1) AS sprint_sec,
                   ROUND(AVG(sprint_percentage)::numeric, 1) AS avg_sprint_pct,
                   ROUND(AVG(post_spawn_distance)::numeric, 0) AS avg_post_spawn_dist,
                   ROUND(AVG(CASE WHEN duration_ms > 0 THEN total_distance / (duration_ms::real / 1000) ELSE 0 END)::numeric, 1) AS avg_distance_per_sec
            FROM player_track {where_sql}
            GROUP BY player_guid
            HAVING COUNT(*) >= 3
            ORDER BY SUM(total_distance) DESC
            LIMIT {safe_limit}
            """,
            tuple(params),
        )

        players = []
        for r in (rows or []):
            alive = float(r[3] or 0)
            standing = float(r[8] or 0)
            crouching = float(r[9] or 0)
            prone = float(r[10] or 0)
            stance_total = standing + crouching + prone
            players.append({
                "guid": r[0],
                "name": r[1],
                "tracks": int(r[2] or 0),
                "alive_sec": alive,
                "avg_peak_speed": float(r[4] or 0),
                "max_peak_speed": float(r[5] or 0),
                "avg_speed": float(r[6] or 0),
                "total_distance": float(r[7] or 0),
                "standing_sec": standing,
                "crouching_sec": crouching,
                "prone_sec": prone,
                "standing_pct": round(standing * 100 / stance_total, 1) if stance_total > 0 else 0,
                "crouching_pct": round(crouching * 100 / stance_total, 1) if stance_total > 0 else 0,
                "prone_pct": round(prone * 100 / stance_total, 1) if stance_total > 0 else 0,
                "sprint_sec": float(r[11] or 0),
                "avg_sprint_pct": float(r[12] or 0),
                "avg_post_spawn_dist": float(r[13] or 0),
                "avg_distance_per_sec": float(r[14] or 0),
            })

        return {
            "status": "ok",
            "scope": scope,
            "players": players,
        }
    except Exception:
        logger.warning("Proximity movement-stats error", exc_info=True)
        return {"status": "error", "detail": "Internal error"}


# ===== PROXIMITY COMPOSITE SCORES (v5.2) =======================================

@router.get("/proximity/prox-scores")
async def get_prox_scores(
    range_days: int = 30,
    player_guid: Optional[str] = None,
    limit: int = 50,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Proximity composite scores: prox_combat, prox_team, prox_gamesense, prox_overall.
    Percentile-based scoring across all proximity metrics.
    """
    from website.backend.services.prox_scoring import compute_prox_scores
    try:
        results = await compute_prox_scores(db, range_days, player_guid)
        return {
            "status": "ok",
            "version": "1.0",
            "range_days": range_days,
            "player_count": len(results),
            "players": results[:limit],
        }
    except Exception:
        logger.warning("Proximity prox-scores error", exc_info=True)
        return {"status": "error", "detail": "Internal error"}


@router.get("/proximity/prox-scores/formula")
async def get_prox_scores_formula():
    """Return current formula config (weights, metrics, categories) for transparency."""
    from website.backend.services.prox_scoring import get_formula_config
    return {"status": "ok", **get_formula_config()}


# ========================================
# v6.0 CARRIER INTELLIGENCE
# ========================================

@router.get("/proximity/carrier-events")
async def get_proximity_carrier_events(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
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
        logger.error("Carrier events error", exc_info=True)
        return {"status": "error", "detail": "Internal error", "carriers": [], "events": [], "summary": {}}


@router.get("/proximity/carrier-kills")
async def get_proximity_carrier_kills(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
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
        logger.error("Carrier kills error", exc_info=True)
        return {"status": "error", "detail": "Internal error", "killers": []}


# ========================================
# v6.0 Phase 1.5: CARRIER RETURNS
# ========================================

@router.get("/proximity/carrier-returns")
async def get_proximity_carrier_returns(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
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
        logger.error("carrier-returns error", exc_info=True)
        return {"status": "error", "message": "Internal error", "returners": [], "events": [], "summary": {}}


# ========================================
# v6.0 Phase 2: VEHICLE & ESCORT
# ========================================

@router.get("/proximity/vehicle-progress")
async def get_proximity_vehicle_progress(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
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
        logger.error("vehicle-progress error", exc_info=True)
        return {"status": "error", "message": "Internal error", "vehicles": []}


@router.get("/proximity/escort-credits")
async def get_proximity_escort_credits(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
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
        logger.error("escort-credits error", exc_info=True)
        return {"status": "error", "message": "Internal error", "escorts": []}


# ========================================
# v6.0 Phase 3: CONSTRUCTION EVENTS
# ========================================

@router.get("/proximity/construction-events")
async def get_proximity_construction_events(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
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
        logger.error("construction-events error", exc_info=True)
        return {"status": "error", "message": "Internal error", "engineers": [], "events": []}


# ========================================
# v6.5: OBJECTIVE RUN INTELLIGENCE
# ========================================

@router.get("/proximity/objective-runs")
async def get_proximity_objective_runs(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
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
        logger.error("objective-runs error", exc_info=True)
        return {"status": "error", "message": "Internal error", "objective_runners": [], "recent_runs": [], "summary": None}


# ========================================
# FOCUS FIRE INTELLIGENCE
# ========================================

@router.get("/proximity/focus-fire")
async def get_proximity_focus_fire(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
    limit: int = 20,
    db: DatabaseAdapter = Depends(get_db),
):
    """Focus fire intelligence — coordinated multi-attacker damage bursts."""
    try:
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
    except Exception:
        logger.error("focus-fire error", exc_info=True)
        return {"status": "error", "message": "Internal error", "summary": {}, "targets": [], "recent": []}


# ========================================
# OBJECTIVE FOCUS (time near objectives)
# ========================================

@router.get("/proximity/objective-focus")
async def get_proximity_objective_focus(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    round_number: Optional[int] = None,
    round_start_unix: Optional[int] = None,
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
        logger.error("objective-focus error", exc_info=True)
        return {"status": "error", "message": "Internal error", "summary": {}, "players": [], "objectives": []}


# ========================================
# SUPPORT SUMMARY (medic support uptime)
# ========================================

@router.get("/proximity/support-summary")
async def get_proximity_support_summary(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Support summary — medic support uptime per round."""
    try:
        if not await _table_column_exists(db, 'proximity_support_summary', 'support_uptime_pct'):
            return {"status": "ok", "summary": {}, "rounds": [], "by_map": []}

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

        where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

        # Summary
        summary_row = await db.fetch_one(
            f"""
            SELECT COUNT(*) AS total_rounds,
                   ROUND(AVG(support_uptime_pct)::numeric, 1) AS avg_uptime_pct,
                   ROUND(MAX(support_uptime_pct)::numeric, 1) AS max_uptime_pct,
                   ROUND(AVG(CASE WHEN total_samples > 0
                        THEN support_samples::numeric / total_samples * 100 ELSE 0 END), 1) AS avg_coverage_pct
            FROM proximity_support_summary {where_sql}
            """,
            tuple(params),
        )
        summary = {
            "total_rounds": int(summary_row[0] or 0) if summary_row else 0,
            "avg_uptime_pct": float(summary_row[1] or 0) if summary_row else 0,
            "max_uptime_pct": float(summary_row[2] or 0) if summary_row else 0,
            "avg_coverage_pct": float(summary_row[3] or 0) if summary_row else 0,
        }

        # Per-map breakdown
        map_rows = await db.fetch_all(
            f"""
            SELECT map_name,
                   COUNT(*) AS rounds,
                   ROUND(AVG(support_uptime_pct)::numeric, 1) AS avg_uptime_pct,
                   ROUND(MAX(support_uptime_pct)::numeric, 1) AS max_uptime_pct,
                   SUM(support_samples) AS total_support_samples,
                   SUM(total_samples) AS total_samples
            FROM proximity_support_summary {where_sql}
            GROUP BY map_name
            ORDER BY AVG(support_uptime_pct) DESC
            """,
            tuple(params),
        )
        by_map = [dict(r) for r in (map_rows or [])]

        # Recent rounds
        recent_rows = await db.fetch_all(
            f"""
            SELECT map_name, round_number, support_uptime_pct,
                   support_samples, total_samples, session_date
            FROM proximity_support_summary {where_sql}
            ORDER BY session_date DESC, round_start_unix DESC
            LIMIT 15
            """,
            tuple(params),
        )
        rounds = [dict(r) for r in (recent_rows or [])]

        return {"status": "ok", "summary": summary, "by_map": by_map, "rounds": rounds}
    except Exception:
        logger.error("support-summary error", exc_info=True)
        return {"status": "error", "message": "Internal error", "summary": {}, "by_map": [], "rounds": []}


# ========================================
# COMBAT POSITION STATS (aggregate overview)
# ========================================

@router.get("/proximity/combat-position-stats")
async def get_proximity_combat_position_stats(
    range_days: int = 30,
    session_date: Optional[str] = None,
    map_name: Optional[str] = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Combat position aggregate stats — kill distances, class matchups."""
    try:
        if not await _table_column_exists(db, 'proximity_combat_position', 'attacker_guid'):
            return {"status": "ok", "summary": {}, "by_class": [], "by_map": []}

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
