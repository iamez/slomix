"""
Round Replay Timeline Service

Merges all proximity events into one chronological timeline per round,
plus player positions from player_track.path JSONB.
"""
import json
from bisect import bisect_left
from collections import defaultdict

from website.backend.logging_config import get_app_logger
from website.backend.utils.et_constants import strip_et_colors

logger = get_app_logger("service.replay")


def _format_time(ms) -> str:
    """Format milliseconds to M:SS."""
    if ms is None:
        return "?:??"
    total_secs = int(ms) // 1000
    minutes = total_secs // 60
    seconds = total_secs % 60
    return f"{minutes}:{seconds:02d}"


def _safe_float(val) -> float | None:
    """Convert Decimal/numeric to float, or None."""
    if val is None:
        return None
    return float(val)


def _ensure_path_list(path) -> list:
    """Ensure path is a Python list (handle JSONB or text storage)."""
    if path is None:
        return []
    if isinstance(path, list):
        return path
    if isinstance(path, str):
        try:
            return json.loads(path)
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def _find_position_at_time(path: list, target_ms: int) -> dict | None:
    """Binary search path array for nearest sample to target time."""
    if not path:
        return None

    times = [s.get("time", 0) for s in path]
    idx = bisect_left(times, target_ms)

    if idx == 0:
        return path[0]
    if idx >= len(path):
        return path[-1]

    before = path[idx - 1]
    after = path[idx]
    if target_ms - before.get("time", 0) <= after.get("time", 0) - target_ms:
        return before
    return after


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

async def get_round_timeline(db, round_id: int) -> dict:
    """Merge all events from a round into one chronological timeline."""
    events: list[dict] = []

    # ---- 1. Kill outcomes + storytelling impact scores ----
    kill_rows = await db.fetch_all("""
        SELECT ko.kill_time, ko.victim_guid, ko.victim_name,
               ko.killer_guid, ko.killer_name, ko.kill_mod,
               ko.outcome, ko.outcome_time, ko.delta_ms,
               ko.gibber_guid, ko.gibber_name,
               ko.reviver_guid, ko.reviver_name,
               ski.total_impact,
               cp.attacker_x, cp.attacker_y,
               cp.victim_x, cp.victim_y
        FROM proximity_kill_outcome ko
        LEFT JOIN storytelling_kill_impact ski ON ski.kill_outcome_id = ko.id
        LEFT JOIN proximity_combat_position cp
          ON cp.round_id = ko.round_id
          AND cp.event_time = ko.kill_time
          AND cp.attacker_guid = ko.killer_guid
          AND cp.victim_guid = ko.victim_guid
        WHERE ko.round_id = $1
        ORDER BY ko.kill_time
    """, (round_id,))

    for r in kill_rows:
        kill_time = r[0]
        victim_guid, victim_raw = r[1], r[2]
        killer_guid, killer_raw, kill_mod = r[3], r[4], r[5]
        outcome, outcome_time, delta_ms = r[6], r[7], r[8]
        gibber_guid, gibber_raw = r[9], r[10]
        reviver_guid, reviver_raw = r[11], r[12]
        importance = _safe_float(r[13]) or 1.0

        killer = strip_et_colors(killer_raw)
        victim = strip_et_colors(victim_raw)
        gibber = strip_et_colors(gibber_raw)
        reviver = strip_et_colors(reviver_raw)

        # Kill event
        events.append({
            "t_ms": kill_time,
            "t_formatted": _format_time(kill_time),
            "type": "kill",
            "icon": "\U0001F480",
            "label": f"{killer} kills {victim} ({kill_mod})",
            "importance": round(importance, 2),
            "team": None,
            "players": [p for p in [killer, victim] if p],
            "detail": {
                "killer_guid": killer_guid,
                "victim_guid": victim_guid,
                "kill_mod": kill_mod,
                "outcome": outcome,
                "delta_ms": delta_ms,
                "killer_x": _safe_float(r[14]),
                "killer_y": _safe_float(r[15]),
                "victim_x": _safe_float(r[16]),
                "victim_y": _safe_float(r[17]),
            },
        })

        # Revive event
        if outcome == "revived" and outcome_time is not None:
            events.append({
                "t_ms": outcome_time,
                "t_formatted": _format_time(outcome_time),
                "type": "revive",
                "icon": "\U0001F489",
                "label": f"{reviver} revives {victim}" if reviver else f"{victim} revived",
                "importance": round(importance * 0.8, 2),
                "team": None,
                "players": [p for p in [reviver, victim] if p],
                "detail": {
                    "reviver_guid": reviver_guid,
                    "victim_guid": victim_guid,
                    "delta_ms": delta_ms,
                },
            })

        # Gib event
        elif outcome in ("tapped_out", "gibbed") and outcome_time is not None:
            if outcome == "tapped_out":
                label = f"{victim} taps out"
                players = [victim] if victim else []
            else:
                label = f"{gibber} gibs {victim}" if gibber else f"{victim} gibbed"
                players = [p for p in [gibber, victim] if p]
            events.append({
                "t_ms": outcome_time,
                "t_formatted": _format_time(outcome_time),
                "type": "gib",
                "icon": "\U0001FAA6",
                "label": label,
                "importance": 0.5,
                "team": None,
                "players": players,
                "detail": {
                    "gibber_guid": gibber_guid,
                    "victim_guid": victim_guid,
                    "outcome": outcome,
                },
            })

    # ---- 2. Trade kills ----
    trade_rows = await db.fetch_all("""
        SELECT original_kill_time, traded_kill_time, delta_ms,
               original_victim_guid, original_victim_name,
               original_killer_guid, original_killer_name,
               trader_guid, trader_name
        FROM proximity_lua_trade_kill
        WHERE round_id = $1
        ORDER BY traded_kill_time
    """, (round_id,))

    for r in trade_rows:
        trader = strip_et_colors(r[8])
        orig_killer = strip_et_colors(r[6])
        events.append({
            "t_ms": r[1],
            "t_formatted": _format_time(r[1]),
            "type": "trade",
            "icon": "\u2694\uFE0F",
            "label": f"{trader} trades {orig_killer} ({r[2]}ms)",
            "importance": 2.5,
            "team": None,
            "players": [p for p in [trader, orig_killer] if p],
            "detail": {
                "trader_guid": r[7],
                "original_killer_guid": r[5],
                "original_kill_time": r[0],
                "delta_ms": r[2],
            },
        })

    # ---- 3. Team pushes ----
    push_rows = await db.fetch_all("""
        SELECT start_time, end_time, team, avg_speed, alignment_score,
               push_quality, participant_count, toward_objective
        FROM proximity_team_push
        WHERE round_id = $1
        ORDER BY start_time
    """, (round_id,))

    for r in push_rows:
        team = r[2]
        quality = _safe_float(r[5]) or 0.0
        events.append({
            "t_ms": r[0],
            "t_formatted": _format_time(r[0]),
            "type": "push",
            "icon": "\U0001F3C3",
            "label": f"{team} push ({r[6]} players, quality {quality:.2f})",
            "importance": round(quality * 5, 2),
            "team": team,
            "players": [],
            "detail": {
                "end_time": r[1],
                "avg_speed": _safe_float(r[3]),
                "alignment_score": _safe_float(r[4]),
                "push_quality": quality,
                "participant_count": r[6],
                "toward_objective": r[7],
            },
        })

    # ---- 4. Carrier events ----
    carrier_rows = await db.fetch_all("""
        SELECT pickup_time, drop_time, carrier_guid, carrier_name,
               carrier_team, flag_team, outcome, duration_ms,
               carry_distance, efficiency,
               killer_guid, killer_name,
               pickup_x, pickup_y, pickup_z,
               drop_x, drop_y, drop_z
        FROM proximity_carrier_event
        WHERE round_id = $1
        ORDER BY pickup_time
    """, (round_id,))

    for r in carrier_rows:
        carrier = strip_et_colors(r[3])
        outcome = r[6] or "unknown"

        # Pickup event
        if r[0] is not None:
            events.append({
                "t_ms": r[0],
                "t_formatted": _format_time(r[0]),
                "type": "carrier_pickup",
                "icon": "\U0001F6A9",
                "label": f"{carrier} picks up objective",
                "importance": 3.0,
                "team": r[4],
                "players": [carrier] if carrier else [],
                "detail": {
                    "carrier_guid": r[2],
                    "flag_team": r[5],
                    "x": _safe_float(r[12]),
                    "y": _safe_float(r[13]),
                    "z": _safe_float(r[14]),
                },
            })

        # Outcome event (drop / secured / killed)
        if r[1] is not None:
            type_map = {
                "secured": ("carrier_secured", "\U0001F3C6", 5.0),
                "killed":  ("carrier_killed",  "\U0001F3AF", 3.5),
            }
            etype, icon, imp = type_map.get(outcome, ("carrier_drop", "\U0001F4CD", 1.5))
            killer = strip_et_colors(r[11])

            if outcome == "killed" and killer:
                label = f"{killer} kills carrier {carrier}"
            elif outcome == "secured":
                label = f"{carrier} secures objective"
            else:
                label = f"{carrier} drops objective"

            events.append({
                "t_ms": r[1],
                "t_formatted": _format_time(r[1]),
                "type": etype,
                "icon": icon,
                "label": label,
                "importance": imp,
                "team": r[4],
                "players": [p for p in [carrier, killer] if p],
                "detail": {
                    "carrier_guid": r[2],
                    "outcome": outcome,
                    "duration_ms": r[7],
                    "carry_distance": _safe_float(r[8]),
                    "efficiency": _safe_float(r[9]),
                    "x": _safe_float(r[15]),
                    "y": _safe_float(r[16]),
                    "z": _safe_float(r[17]),
                },
            })

    # ---- 5. Construction events ----
    build_rows = await db.fetch_all("""
        SELECT event_time, event_type, player_guid, player_name,
               player_team, track_name,
               player_x, player_y, player_z
        FROM proximity_construction_event
        WHERE round_id = $1
        ORDER BY event_time
    """, (round_id,))

    for r in build_rows:
        player = strip_et_colors(r[3])
        event_type = r[1] or "build"
        etype = "build" if "build" in event_type.lower() else "destroy"
        icon = "\U0001F528" if etype == "build" else "\U0001F4A5"
        track = r[5] or "structure"
        events.append({
            "t_ms": r[0],
            "t_formatted": _format_time(r[0]),
            "type": etype,
            "icon": icon,
            "label": f"{player} {etype}s {track}",
            "importance": 2.0,
            "team": r[4],
            "players": [player] if player else [],
            "detail": {
                "player_guid": r[2],
                "track_name": track,
                "x": _safe_float(r[6]),
                "y": _safe_float(r[7]),
                "z": _safe_float(r[8]),
            },
        })

    # NOTE: proximity_focus_fire omitted — no event timestamp column,
    # so events cannot be placed on the timeline.

    # ---- Sort all events chronologically ----
    events.sort(key=lambda e: (e["t_ms"] or 0, e["type"]))

    # ---- Round metadata ----
    meta = await db.fetch_one("""
        SELECT pt.map_name, MAX(pt.death_time_ms) AS duration_ms
        FROM player_track pt
        JOIN rounds r ON r.round_date::date = pt.session_date
                     AND r.round_number = pt.round_number
                     AND r.map_name = pt.map_name
        WHERE r.id = $1
        GROUP BY pt.map_name
        LIMIT 1
    """, (round_id,))

    map_name = meta[0] if meta else None
    duration_ms = meta[1] if meta else 0

    return {
        "round_id": round_id,
        "map_name": map_name,
        "duration_ms": duration_ms,
        "event_count": len(events),
        "events": events,
    }


# ---------------------------------------------------------------------------
# Player positions at time T
# ---------------------------------------------------------------------------

async def get_player_positions(db, round_id: int, time_ms: int) -> dict:
    """Get all player positions at a specific time T using player_track.path JSONB."""
    tracks = await db.fetch_all("""
        SELECT pt.player_guid, pt.player_name, pt.team, pt.player_class,
               pt.spawn_time_ms, pt.death_time_ms, pt.path, pt.map_name
        FROM player_track pt
        JOIN rounds r ON r.round_date::date = pt.session_date
                     AND r.round_number = pt.round_number
                     AND r.map_name = pt.map_name
        WHERE r.id = $1
        ORDER BY pt.player_guid, pt.spawn_time_ms
    """, (round_id,))

    # Group tracks by player
    player_tracks: dict[str, list] = defaultdict(list)
    map_name = None
    for t in tracks:
        guid = t[0]
        if not map_name and t[7]:
            map_name = t[7]
        player_tracks[guid].append(t)

    players = []
    for guid, track_list in player_tracks.items():
        active = None
        last_before_t = None

        for t in track_list:
            spawn_ms = t[4] or 0
            death_ms = t[5]

            # Track active at time T
            if spawn_ms <= time_ms and (death_ms is None or death_ms >= time_ms):
                active = t
                break

            # Most recent ended track before T (for limbo/dead players)
            if death_ms is not None and death_ms < time_ms:
                if last_before_t is None or death_ms > (last_before_t[5] or 0):
                    last_before_t = t

        track = active or last_before_t
        if track is None:
            continue

        alive = active is not None
        name = strip_et_colors(track[1])
        team = track[2]
        player_class = track[3]
        path = _ensure_path_list(track[6])

        # For dead players, find position at death time
        lookup_time = time_ms if alive else (track[5] or time_ms)
        pos = _find_position_at_time(path, lookup_time)

        if pos:
            players.append({
                "guid": guid,
                "name": name,
                "team": team,
                "class": player_class,
                "x": _safe_float(pos.get("x")),
                "y": _safe_float(pos.get("y")),
                "z": _safe_float(pos.get("z")),
                "health": pos.get("health", 0) if alive else 0,
                "weapon": pos.get("weapon"),
                "alive": alive,
                "stance": pos.get("stance"),
            })

    return {
        "t_ms": time_ms,
        "map_name": map_name,
        "player_count": len(players),
        "players": players,
    }


# ---------------------------------------------------------------------------
# Player paths for a time window
# ---------------------------------------------------------------------------

async def get_player_paths(db, round_id: int, from_ms: int, to_ms: int) -> dict:
    """Get player movement paths for a time window (for trail rendering)."""
    tracks = await db.fetch_all("""
        SELECT pt.player_guid, pt.player_name, pt.team, pt.player_class,
               pt.spawn_time_ms, pt.death_time_ms, pt.path, pt.map_name
        FROM player_track pt
        JOIN rounds r ON r.round_date::date = pt.session_date
                     AND r.round_number = pt.round_number
                     AND r.map_name = pt.map_name
        WHERE r.id = $1
          AND pt.spawn_time_ms <= $3
          AND (pt.death_time_ms >= $2 OR pt.death_time_ms IS NULL)
        ORDER BY pt.player_guid, pt.spawn_time_ms
    """, (round_id, from_ms, to_ms))

    map_name = None
    player_paths = []

    for t in tracks:
        if not map_name and t[7]:
            map_name = t[7]

        path = _ensure_path_list(t[6])
        if not path:
            continue

        # Extract sub-array within [from_ms, to_ms]
        sub_path = [s for s in path if from_ms <= s.get("time", 0) <= to_ms]
        if not sub_path:
            continue

        player_paths.append({
            "guid": t[0],
            "name": strip_et_colors(t[1]),
            "team": t[2],
            "class": t[3],
            "spawn_time_ms": t[4],
            "death_time_ms": t[5],
            "samples": sub_path,
        })

    return {
        "round_id": round_id,
        "map_name": map_name,
        "from_ms": from_ms,
        "to_ms": to_ms,
        "player_count": len(player_paths),
        "paths": player_paths,
    }
