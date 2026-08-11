"""
Round contract helpers for side/winner confidence and end-reason normalization.
"""

from __future__ import annotations

import math
from typing import Any, Iterable

END_REASON_ENUM = {
    "NORMAL",
    "SURRENDER",
    "MAP_CHANGE",
    "MAP_RESTART",
    "SERVER_RESTART",
}


def is_filler_map(map_name: str | None, excluded_maps: Iterable[str]) -> bool:
    """Return True if a map is a non-competitive "filler" (e.g. mp_sillyctf).

    Filler maps are run while waiting for a substitution and must not count
    toward stats; the importer flags such rounds with is_valid = FALSE.
    Matching is case-insensitive. `excluded_maps` is the configured set
    (`config.excluded_maps`); callers pass it explicitly so this stays pure
    and unit-testable.
    """
    if not map_name:
        return False
    name = map_name.strip().lower()
    return any(name == str(m).strip().lower() for m in excluded_maps)


def is_bot_player(player: dict | None) -> bool:
    """Single bot classifier for one parsed player.

    Used for BOTH the bot/human counts and the validity gate so the two can
    never disagree (review on #640: counting only the is_bot flag while the
    gate also matched OMNIBOT guids let a guid-only bot yield is_valid=FALSE
    with bot_player_count=0).
    """
    if not player:
        return False
    if player.get("is_bot"):
        return True
    if str(player.get("guid", "")).upper().startswith("OMNIBOT"):
        return True
    return str(player.get("name", "")).startswith("[BOT]")


def round_has_bots(players: Iterable[dict] | None) -> bool:
    """Return True if any participant is an Omni-bot.

    Detects bots from the parsed player list directly — NOT from the
    round-level bot_player_count, which prod showed can be 0 even for an
    all-bot session (the 2026-06-11 session-123 incident). Owner intent:
    bot/testmode rounds never count for stats, so the importer flags them
    is_valid = FALSE. Pure + unit-testable; callers pass the players list.
    """
    return any(is_bot_player(p) for p in players or [])


def derive_round_validity(
    parsed_data: dict[str, Any],
    map_name: str | None,
    excluded_maps: Iterable[str],
) -> dict[str, Any]:
    """Derive the round validity/bot flags the importer must persist.

    Exists because the production import path (PostgreSQLDatabaseManager)
    historically inserted rounds WITHOUT these columns, so is_bot_round was
    never true and the is_valid bot/filler/orphan gates never fired in either
    database's history — proven live by the 2026-08-11 Omni-bot test, whose
    rounds landed is_valid=TRUE and had to be quarantined by hand.

    This is the ONE shared implementation — stats_import_mixin calls it too
    (aligned on #640 review), so both import paths persist identical flags:
    - is_bot_round: majority rule (parser's value when present; recomputed
      from the player list otherwise — bots-only OR strict bot majority).
    - is_valid: FALSE when the map is a configured filler, when ANY bot
      participated (stricter than the majority rule — owner intent: bots
      never count for stats), or when the round is an orphan R2 (raw
      cumulative stats, no R1 to subtract).

    Pure and unit-testable; callers pass excluded_maps explicitly.
    """
    players = parsed_data.get("players") or []
    bot_count = int(parsed_data.get("bot_player_count", 0) or 0)
    human_count = int(parsed_data.get("human_player_count", 0) or 0)
    if players and bot_count == 0 and human_count == 0:
        # Counts absent on this path — recompute from the player list, the
        # same defensive fallback the mixin grew after session 123 (all-bot
        # session with bot_player_count=0). Uses the SAME classifier as the
        # validity gate (is_bot_player) so counts and gate cannot disagree.
        bot_count = sum(1 for p in players if is_bot_player(p))
        human_count = max(0, len(players) - bot_count)

    is_bot_round = bool(parsed_data.get("is_bot_round", False))
    if not is_bot_round and bot_count > 0:
        # Majority rule, kept in sync with
        # community_stats_parser.is_bot_dominated_round (inlined to avoid a
        # core -> parser import cycle).
        is_bot_round = human_count == 0 or bot_count > human_count

    has_bots = bot_count > 0 or round_has_bots(players)
    is_orphan_r2 = bool(parsed_data.get("is_orphan_r2"))
    is_valid = (
        not is_filler_map(map_name, excluded_maps)
        and not has_bots
        and not is_orphan_r2
    )
    return {
        "is_bot_round": is_bot_round,
        "bot_player_count": bot_count,
        "human_player_count": human_count,
        "is_valid": is_valid,
        "is_orphan_r2": is_orphan_r2,
    }


_SIDE_VALUE_MAP = {
    "axis": 1,
    "1": 1,
    "allies": 2,
    "2": 2,
    "draw": 0,
    "unknown": 0,
    "0": 0,
}


_END_REASON_MAP = {
    "": "NORMAL",
    "unknown": "NORMAL",
    "normal": "NORMAL",
    "objective": "NORMAL",
    "time_expired": "NORMAL",
    "timelimit": "NORMAL",
    "time limit": "NORMAL",
    "surrender": "SURRENDER",
    "forfeit": "SURRENDER",
    "map_change": "MAP_CHANGE",
    "map change": "MAP_CHANGE",
    "mapchange": "MAP_CHANGE",
    "map_restart": "MAP_RESTART",
    "map restart": "MAP_RESTART",
    "maprestart": "MAP_RESTART",
    "server_restart": "SERVER_RESTART",
    "server restart": "SERVER_RESTART",
    "serverrestart": "SERVER_RESTART",
}


def normalize_side_value(value: Any, allow_unknown: bool = True) -> int:
    """
    Normalize side values to canonical int space:
    - 1: Axis
    - 2: Allies
    - 0: Unknown/Draw
    """
    if value is None:
        return 0 if allow_unknown else -1

    text = str(value).strip().lower()
    if not text:
        return 0 if allow_unknown else -1

    if text in _SIDE_VALUE_MAP:
        return _SIDE_VALUE_MAP[text]

    if text.isdigit():
        parsed = int(text)
        if parsed in (1, 2):
            return parsed
        if parsed == 0 and allow_unknown:
            return 0

    return 0 if allow_unknown else -1


def score_confidence_state(
    defender_team: Any,
    winner_team: Any,
    reasons: Iterable[str] | None = None,
    fallback_used: bool = False,
) -> str:
    """
    Canonical score confidence states:
    - verified_header
    - time_fallback
    - ambiguous
    - missing
    """
    reason_list = [str(r) for r in (reasons or []) if str(r)]
    defender = normalize_side_value(defender_team, allow_unknown=True)
    winner = normalize_side_value(winner_team, allow_unknown=True)

    if fallback_used and defender in (1, 2) and winner in (1, 2):
        return "time_fallback"

    if any(("out_of_range" in r or "non_numeric" in r) for r in reason_list):
        return "ambiguous"

    if defender in (1, 2) and winner in (1, 2) and not reason_list:
        return "verified_header"

    if defender == 0 or winner == 0:
        return "missing"

    return "ambiguous"


def normalize_end_reason(value: Any) -> str:
    """
    Normalize raw end-reason values to strict enum values.
    """
    if value is None:
        return "NORMAL"

    text = str(value).strip().lower()
    if text in _END_REASON_MAP:
        return _END_REASON_MAP[text]

    return "NORMAL"


def parse_time_to_seconds(value: Any) -> int | None:
    """
    Parse time values (MM:SS / HH:MM:SS / decimal minutes / numeric seconds).
    """
    if value is None:
        return None

    try:
        text = str(value).strip()
        if not text:
            return None

        if ":" in text:
            parts = text.split(":")
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            return None

        if "." in text:
            return int(float(text) * 60)

        return int(float(text))
    except (ValueError, TypeError):
        return None


def derive_stopwatch_contract(
    round_number: Any,
    time_limit_value: Any,
    actual_time_value: Any,
    end_reason: Any = "NORMAL",
) -> dict:
    """
    Derive stopwatch contract fields:
    - round_stopwatch_state: FULL_HOLD | TIME_SET | None
    - time_to_beat_seconds
    - next_timelimit_minutes
    """
    round_num = int(round_number or 0)
    limit_seconds = parse_time_to_seconds(time_limit_value)
    actual_seconds = parse_time_to_seconds(actual_time_value)
    normalized_end = normalize_end_reason(end_reason)

    state = None
    if normalized_end == "NORMAL" and limit_seconds is not None and actual_seconds is not None:
        # Treat near time-limit completion as a hold.
        hold_threshold = max(limit_seconds - 30, 0)
        state = "FULL_HOLD" if actual_seconds >= hold_threshold else "TIME_SET"

    result = {
        "round_stopwatch_state": state,
        "time_to_beat_seconds": None,
        "next_timelimit_minutes": None,
    }

    if round_num == 1 and state == "TIME_SET" and actual_seconds is not None:
        result["time_to_beat_seconds"] = actual_seconds
        result["next_timelimit_minutes"] = max(1, int(math.ceil(actual_seconds / 60.0)))
    elif round_num == 1 and state == "FULL_HOLD" and limit_seconds is not None:
        result["next_timelimit_minutes"] = max(1, int(math.ceil(limit_seconds / 60.0)))

    return result


def derive_end_reason_display(
    end_reason: Any,
    round_stopwatch_state: str | None = None,
) -> str:
    """
    Derive display classification for end-reason + stopwatch state.
    """
    normalized = normalize_end_reason(end_reason)

    if normalized == "SURRENDER":
        return "SURRENDER_END"
    if normalized == "MAP_CHANGE":
        return "MAP_CHANGE_END"
    if normalized == "MAP_RESTART":
        return "MAP_RESTART_END"
    if normalized == "SERVER_RESTART":
        return "SERVER_RESTART_END"

    if round_stopwatch_state == "FULL_HOLD":
        return "FULL_HOLD"
    if round_stopwatch_state == "TIME_SET":
        return "TIME_SET"

    # Normal fallback without stopwatch context.
    return "TIME_SET"
