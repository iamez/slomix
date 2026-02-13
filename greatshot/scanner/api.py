"""High-level scanner API for ET:Legacy demo analysis."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List

from greatshot.config import CONFIG
from greatshot.contracts.profiles.profile_detector import detect_profile
from greatshot.contracts.types import AnalysisResult, DemoEvent, Highlight
from greatshot.highlights.detectors import detect_highlights
from greatshot.scanner.adapters import run_udt_json_parser
from greatshot.scanner.errors import DemoScanError, UnsupportedDemoError


def sniff_demo_header_bytes(header_bytes: bytes) -> Dict[str, int]:
    """
    Basic ET-family demo sniffing.

    ET/W:ET demo files are binary and begin with little-endian ints for message
    sequence/size. This is not a perfect signature, but useful for rejecting
    obvious bad uploads.
    """
    if len(header_bytes) < 8:
        raise UnsupportedDemoError("Demo file is too short to contain a valid header.")

    sequence = int.from_bytes(header_bytes[0:4], "little", signed=True)
    first_message_size = int.from_bytes(header_bytes[4:8], "little", signed=True)

    if first_message_size <= 0 or first_message_size > 2_000_000:
        raise UnsupportedDemoError(
            f"Invalid first message size in demo header: {first_message_size}"
        )

    return {
        "sequence": sequence,
        "first_message_size": first_message_size,
    }


def _canonical_name(value: Any, fallback: str = "unknown") -> str:
    if value is None:
        return fallback
    raw = str(value).strip()
    return raw if raw else fallback


def _normalize_players(
    game_states: Iterable[Dict[str, Any]],
    player_stats: Iterable[Dict[str, Any]],
    profile,
) -> List[Dict[str, Any]]:
    players: Dict[int, Dict[str, Any]] = {}

    for state in game_states:
        for row in state.get("players", []) or []:
            client_num = int(row.get("clientNumber", -1))
            if client_num < 0:
                continue
            item = players.setdefault(
                client_num,
                {
                    "client_num": client_num,
                    "name": _canonical_name(row.get("cleanName")),
                    "name_history": [],
                    "teams": set(),
                    "team_history": [],
                    "first_seen_ms": row.get("startTime"),
                    "last_seen_ms": row.get("endTime"),
                },
            )

            clean_name = _canonical_name(row.get("cleanName"), item["name"])
            if clean_name not in item["name_history"]:
                item["name_history"].append(clean_name)
            item["name"] = clean_name

            team = profile.canonical_team(row.get("team"))
            if team and team != "unknown":
                item["teams"].add(team)
                item["team_history"].append(
                    {
                        "team": team,
                        "start_ms": int(row.get("startTime") or 0),
                        "end_ms": int(row.get("endTime") or 0),
                    }
                )

            start = row.get("startTime")
            end = row.get("endTime")
            if start is not None:
                item["first_seen_ms"] = min(int(item["first_seen_ms"] or start), int(start))
            if end is not None:
                item["last_seen_ms"] = max(int(item["last_seen_ms"] or end), int(end))

    for row in player_stats:
        client_num = int(row.get("clientNumber", -1))
        if client_num < 0:
            continue
        item = players.setdefault(
            client_num,
            {
                "client_num": client_num,
                "name": _canonical_name(row.get("cleanName")),
                "name_history": [],
                "teams": set(),
                "team_history": [],
                "first_seen_ms": None,
                "last_seen_ms": None,
            },
        )
        clean_name = _canonical_name(row.get("cleanName"), item["name"])
        if clean_name not in item["name_history"]:
            item["name_history"].append(clean_name)
        item["name"] = clean_name

        team = profile.canonical_team(row.get("team"))
        if team and team != "unknown":
            item["teams"].add(team)

    normalized: List[Dict[str, Any]] = []
    for _, item in sorted(players.items(), key=lambda pair: pair[0]):
        normalized.append(
            {
                "client_num": item["client_num"],
                "name": item["name"],
                "name_history": item["name_history"],
                "teams": sorted(item["teams"]),
                "team_history": sorted(
                    item["team_history"],
                    key=lambda row: (row.get("start_ms", 0), row.get("team", "")),
                ),
                "first_seen_ms": item["first_seen_ms"],
                "last_seen_ms": item["last_seen_ms"],
            }
        )
    return normalized


def _normalize_timeline(
    raw_chat: Iterable[Dict[str, Any]],
    raw_obits: Iterable[Dict[str, Any]],
    profile,
) -> List[DemoEvent]:
    timeline: List[DemoEvent] = []

    for chat in raw_chat:
        t_ms = int(chat.get("serverTime") or 0)
        player = _canonical_name(chat.get("cleanPlayerName") or chat.get("playerName"), "unknown")
        message = _canonical_name(chat.get("cleanMessage") or chat.get("message"), "")
        timeline.append(
            DemoEvent(
                t_ms=t_ms,
                type="chat",
                attacker=player,
                message=message,
                meta={
                    "team_chat": bool(chat.get("teamChat")),
                },
            )
        )

    for death in raw_obits:
        t_ms = int(death.get("serverTime") or 0)
        attacker = _canonical_name(death.get("attackerCleanName") or death.get("attackerName"), "world")
        victim = _canonical_name(death.get("targetCleanName") or death.get("targetName"), "unknown")
        raw_weapon = _canonical_name(death.get("causeOfDeath"), "unknown")
        weapon = profile.canonical_weapon(raw_weapon)

        hit_region = None
        if "HEAD" in raw_weapon.upper():
            hit_region = "head"

        timeline.append(
            DemoEvent(
                t_ms=t_ms,
                type="kill",
                attacker=attacker,
                victim=victim,
                weapon=weapon,
                hit_region=hit_region,
                team=profile.canonical_team(death.get("attackerTeam")),
                meta={
                    "attacker_team": profile.canonical_team(death.get("attackerTeam")),
                    "victim_team": profile.canonical_team(death.get("targetTeam")),
                    "raw_weapon": raw_weapon,
                },
            )
        )

    timeline.sort(
        key=lambda event: (
            int(event.t_ms),
            event.type,
            event.attacker or "",
            event.victim or "",
            event.message or "",
        )
    )
    return timeline


def _extract_player_stats(
    match_stats: List[Dict[str, Any]],
    timeline: List[DemoEvent],
) -> Dict[str, Dict[str, Any]]:
    """Extract per-player performance stats from matchStats and timeline events."""
    def _coerce_int(value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def _coerce_float(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _pick_number(row: Dict[str, Any], keys: tuple[str, ...], as_float: bool = False):
        for key in keys:
            if key not in row:
                continue
            value = _coerce_float(row.get(key)) if as_float else _coerce_int(row.get(key))
            if value is not None:
                return value
        return None

    def _extract_time_fields(row: Dict[str, Any]) -> tuple[float | None, int | None]:
        minutes_val = _pick_number(row, ("time_played_minutes", "timePlayedMinutes"), as_float=True)
        if minutes_val is not None and minutes_val >= 0:
            seconds_val = int(round(minutes_val * 60.0))
            return float(minutes_val), seconds_val

        seconds_val = _pick_number(row, ("time_played_seconds", "timePlayedSeconds"))
        if seconds_val is not None and seconds_val >= 0:
            return round(seconds_val / 60.0, 2), int(seconds_val)

        ms_val = _pick_number(row, ("time_played_ms", "timePlayedMs"))
        if ms_val is not None and ms_val >= 0:
            sec_from_ms = int(round(ms_val / 1000.0))
            return round(sec_from_ms / 60.0, 2), sec_from_ms

        return None, None

    stats: Dict[str, Dict[str, Any]] = {}

    # Seed from matchStats playerStats (UDT may include kills/deaths/etc.)
    primary = match_stats[0] if match_stats else {}
    for row in primary.get("playerStats", []) or []:
        name = _canonical_name(row.get("cleanName"))
        if name == "unknown":
            continue
        entry = stats.setdefault(
            name,
            {
                "kills": 0,
                "deaths": 0,
                "damage_given": 0,
                "damage_received": 0,
                "accuracy": None,
                "time_played_minutes": None,
                "time_played_seconds": None,
                "tpm": None,
                "headshots": 0,
            },
        )

        numeric_map = (
            ("kills", ("kills",)),
            ("deaths", ("deaths",)),
            ("damage_given", ("damage_given", "damageGiven", "damage")),
            ("damage_received", ("damage_received", "damageReceived", "damageTaken")),
            ("headshots", ("headshots", "headshot_kills", "headshotKills")),
        )
        for target_key, source_keys in numeric_map:
            value = _pick_number(row, source_keys)
            if value is not None:
                entry[target_key] = value

        accuracy_value = _pick_number(row, ("accuracy", "acc"), as_float=True)
        if accuracy_value is not None:
            entry["accuracy"] = round(accuracy_value, 2)
        else:
            hits = _pick_number(row, ("hits", "shotsHit"), as_float=True)
            shots = _pick_number(row, ("shots", "shotsFired"), as_float=True)
            if hits is not None and shots and shots > 0:
                entry["accuracy"] = round((hits / shots) * 100.0, 2)

        minutes, seconds = _extract_time_fields(row)
        if minutes is not None and seconds is not None:
            entry["time_played_minutes"] = round(minutes, 2)
            entry["time_played_seconds"] = int(seconds)
            # TPM = time played minutes (for UI parity with existing docs terminology).
            entry["tpm"] = round(minutes, 2)

    # Compute from timeline to fill gaps or override zero values
    kills_by: Dict[str, int] = defaultdict(int)
    deaths_by: Dict[str, int] = defaultdict(int)
    headshots_by: Dict[str, int] = defaultdict(int)
    for event in timeline:
        if event.type != "kill":
            continue
        if event.attacker and event.attacker != "world":
            kills_by[event.attacker] += 1
            if event.hit_region == "head":
                headshots_by[event.attacker] += 1
        if event.victim:
            deaths_by[event.victim] += 1

    for name in set(list(kills_by) + list(deaths_by)):
        entry = stats.setdefault(
            name,
            {
                "kills": 0,
                "deaths": 0,
                "damage_given": 0,
                "damage_received": 0,
                "accuracy": None,
                "time_played_minutes": None,
                "time_played_seconds": None,
                "tpm": None,
                "headshots": 0,
            },
        )
        # Use timeline-derived counts if matchStats didn't provide them
        if entry["kills"] == 0 and kills_by.get(name, 0) > 0:
            entry["kills"] = kills_by[name]
        if entry["deaths"] == 0 and deaths_by.get(name, 0) > 0:
            entry["deaths"] = deaths_by[name]
        if entry.get("headshots", 0) == 0 and headshots_by.get(name, 0) > 0:
            entry["headshots"] = headshots_by.get(name, 0)

    return stats


def _summarize_stats(timeline: Iterable[DemoEvent], players: List[Dict[str, Any]]) -> Dict[str, Any]:
    timeline = list(timeline)
    kill_count = 0
    headshot_count = 0
    chat_count = 0
    kills_by_player: Dict[str, int] = defaultdict(int)

    for event in timeline:
        if event.type == "kill":
            kill_count += 1
            if event.attacker:
                kills_by_player[event.attacker] += 1
            if event.hit_region == "head":
                headshot_count += 1
        elif event.type == "chat":
            chat_count += 1

    top_killers = [
        {"player": player, "kills": kills}
        for player, kills in sorted(kills_by_player.items(), key=lambda row: (-row[1], row[0]))[:10]
    ]

    return {
        "player_count": len(players),
        "event_count": len(timeline),
        "kill_count": kill_count,
        "headshot_count": headshot_count,
        "chat_count": chat_count,
        "top_killers": top_killers,
    }


def analyze_demo(
    demo_path: str | Path,
    scanner_options: Dict[str, Any] | None = None,
) -> AnalysisResult:
    opts = scanner_options or {}
    demo_path = Path(demo_path)

    if not demo_path.exists():
        raise DemoScanError(f"Demo file not found: {demo_path}")

    extension = demo_path.suffix.lower()
    allowed = set(CONFIG.allow_extensions)
    if extension not in allowed:
        raise UnsupportedDemoError(
            f"Unsupported demo extension '{extension}'. Allowed: {sorted(allowed)}"
        )

    with demo_path.open("rb") as handle:
        header = sniff_demo_header_bytes(handle.read(32))

    timeout_seconds = int(opts.get("timeout_seconds", CONFIG.scanner_timeout_seconds))
    max_output_bytes = int(opts.get("max_output_bytes", CONFIG.scanner_max_output_bytes))
    max_events = int(opts.get("max_events", CONFIG.scanner_max_events))

    raw = run_udt_json_parser(
        demo_path=demo_path,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        binary_path=opts.get("udt_json_bin"),
    )

    game_states = raw.get("gameStates", []) or []
    chat = raw.get("chat", []) or []
    obituaries = raw.get("obituaries", []) or []
    match_stats = raw.get("matchStats", []) or []
    primary_match = match_stats[0] if match_stats else {}
    primary_state = game_states[0] if game_states else {}
    config_values = primary_state.get("configStringValues") or {}

    profile = detect_profile(config_values, primary_match)

    players = _normalize_players(
        game_states=game_states,
        player_stats=primary_match.get("playerStats", []) or [],
        profile=profile,
    )

    timeline = _normalize_timeline(chat, obituaries, profile)
    warnings: List[str] = []
    if len(timeline) > max_events:
        warnings.append(
            f"Timeline truncated to {max_events} events (received {len(timeline)})."
        )
        timeline = timeline[:max_events]

    stats = _summarize_stats(timeline, players)
    player_stats = _extract_player_stats(match_stats, timeline)

    rounds = []
    for item in match_stats:
        rounds.append(
            {
                "start_ms": int(item.get("startTime") or 0),
                "end_ms": int(item.get("endTime") or 0),
                "duration_ms": int(item.get("duration") or 0),
                "winner": item.get("winner"),
                "first_place_score": item.get("firstPlaceScore"),
                "second_place_score": item.get("secondPlaceScore"),
            }
        )

    duration_ms = int(primary_match.get("duration") or 0)
    if duration_ms <= 0:
        duration_ms = max(0, int(primary_state.get("endTime") or 0) - int(primary_state.get("startTime") or 0))

    metadata = {
        "filename": demo_path.name,
        "file_size_bytes": demo_path.stat().st_size,
        "extension": extension,
        "profile": profile.profile_id,
        "profile_name": profile.profile_name,
        "map": primary_match.get("map") or config_values.get("mapname") or "unknown",
        "gametype": primary_match.get("gameType")
        or config_values.get("g_gametype")
        or "unknown",
        "gametype_short": primary_match.get("gameTypeShort") or "--",
        "mod": primary_match.get("mod") or config_values.get("gamename") or "unknown",
        "mod_version": primary_match.get("modVersion") or config_values.get("mod_version"),
        "duration_ms": duration_ms,
        "start_ms": int(primary_state.get("startTime") or primary_match.get("startTime") or 0),
        "end_ms": int(primary_state.get("endTime") or primary_match.get("endTime") or 0),
        "rounds": rounds,
        "header": header,
    }

    highlight_dicts = [
        item.to_dict()
        for item in detect_highlights(
            [event.to_dict() for event in timeline],
            player_stats=player_stats,
        )
    ]
    highlights = [
        Highlight(
            highlight_type=item["type"],
            player=item["player"],
            start_ms=int(item["start_ms"]),
            end_ms=int(item["end_ms"]),
            score=float(item["score"]),
            explanation=item.get("explanation", ""),
            meta=item.get("meta") or {},
        )
        for item in highlight_dicts
    ]

    return AnalysisResult(
        metadata=metadata,
        players=players,
        timeline=timeline,
        stats=stats,
        highlights=highlights,
        warnings=warnings,
        parser={
            "name": "UDT_json",
            "raw_sections": {
                "game_states": len(game_states),
                "chat": len(chat),
                "obituaries": len(obituaries),
                "match_stats": len(match_stats),
            },
            "timeout_seconds": timeout_seconds,
        },
        player_stats=player_stats,
    )
