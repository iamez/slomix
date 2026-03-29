"""Shared helpers, constants, and utilities for proximity sub-routers."""

import json
import math
import time
from collections import defaultdict
from datetime import datetime, timedelta
from itertools import combinations
from typing import Any

from fastapi import HTTPException

from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger

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


def _parse_iso_date(value: str | None) -> Any | None:
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
    session_date: str | None,
    map_name: str | None,
    round_number: int | None,
    round_start_unix: int | None,
    alias: str | None = None,
    player_guid: str | None = None,
    player_guid_columns: list[str] | None = None,
) -> tuple[str, list[Any], dict[str, Any]]:
    prefix = f"{alias}." if alias else ""
    params: list[Any] = []
    clauses: list[str] = []

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


def _iter_attackers(attackers_raw: Any) -> list[dict[str, Any]]:
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
    guid_name_map: dict[str, str] | None = None,
    local_map: dict[str, str] | None = None,
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
) -> dict[str, str]:
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
    engagement_rows: list[Any],
    limit: int,
    guid_name_map: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    pair_stats: dict[tuple[str, str], dict[str, float]] = {}

    for row in engagement_rows:
        attackers_raw, participants_raw, crossfire_delay_ms, outcome = row
        attackers = _iter_attackers(attackers_raw)

        guid_to_name: dict[str, str] = {}
        fallback_names: list[str] = []
        for attacker in attackers:
            guid = str(attacker.get("guid") or "").strip()
            name = str(attacker.get("name") or guid or "").strip()
            if not name:
                continue
            fallback_names.append(name)
            if guid:
                guid_to_name[guid] = name

        participants = _parse_json_field(participants_raw) or []
        names: list[str] = []
        participant_guids: list[str] = []
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
    engagement_rows: list[Any],
    limit: int,
    guid_name_map: dict[str, str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    stats: dict[str, dict[str, Any]] = defaultdict(
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

    def ensure_player(guid: str | None, name: str | None) -> str:
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
        except (json.JSONDecodeError, ValueError):
            logger.debug("Failed to parse JSON field: %.100s", value)
            return None
    return None


def _compute_strafe_metrics(path: list[dict[str, Any]], min_step: float = 5.0, angle_threshold_deg: float = 40.0) -> dict[str, Any]:
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
    headings: list[dict[str, Any]] = []

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
