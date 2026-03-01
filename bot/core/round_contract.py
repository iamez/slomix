"""
Round contract helpers for side/winner confidence and end-reason normalization.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Optional


END_REASON_ENUM = {
    "NORMAL",
    "SURRENDER",
    "MAP_CHANGE",
    "MAP_RESTART",
    "SERVER_RESTART",
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
    reasons: Optional[Iterable[str]] = None,
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


def parse_time_to_seconds(value: Any) -> Optional[int]:
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
    round_stopwatch_state: Optional[str] = None,
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
