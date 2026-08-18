"""Single source of truth for round DURATION (bot + website).

``rounds.actual_time`` is NOT a measured duration. It is header field f8
written by c0rnp0rn8.lua, i.e. the ``g_nextTimeLimit`` cvar — the stopwatch
TARGET for the next round. On attacker surrender the game never sets a new
target, the Lua fallback writes the full timelimit, and the stored value
overstates the round by up to +362 s. RCA 2026-08-18 measured this on the
last 3 months: 67/448 valid rounds (15.0%) inflated, always upward, and the
error is fully predicted by ``round_outcome='Fullhold' AND
lua_round_teams.surrender_team > 0``.

The measured truth is ``rounds.actual_duration_seconds`` (Lua webhook wall
clock minus pauses, mirrored from ``lua_round_teams``): verified 100%
(max |delta| = 2 s) against 213 demo-recorded matches.

Any code that means "how long did this round actually last" must go through
:func:`round_duration_seconds` (Python) or :func:`round_duration_sql` (SQL).
Read ``actual_time`` directly only when you really mean the stopwatch clock
value itself (e.g. displaying the time an attack set).
"""
from __future__ import annotations

import re

_MMSS_RE = re.compile(r"^(\d+):(\d{2})$")


def parse_mmss(text: object) -> int | None:
    """Parse an ``M:SS`` / ``MM:SS`` text clock into seconds.

    Returns None for anything unparsable (None, '', '0', garbage) — callers
    must treat that as "unknown", never as zero-length round.
    """
    if text is None:
        return None
    m = _MMSS_RE.match(str(text).strip())
    if not m:
        return None
    return int(m.group(1)) * 60 + int(m.group(2))


def round_duration_seconds(
    actual_duration_seconds: object, actual_time: object
) -> int | None:
    """Best available duration of a round, in seconds.

    Preference order:
    1. ``actual_duration_seconds`` (Lua webhook measurement; exact),
    2. parsed ``actual_time`` (legacy fallback for rounds that predate the
       webhook — beware: inflated on surrender rounds, see module docstring).
    """
    try:
        dur = int(actual_duration_seconds)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        dur = 0
    if dur > 0:
        return dur
    return parse_mmss(actual_time)


def round_duration_mmss_sql(alias: str = "r") -> str:
    """SQL expression (PostgreSQL) for the measured duration as 'M:SS' text,
    falling back to the raw actual_time header text where no measurement
    exists. Drop-in replacement for a bare ``actual_time`` in SELECT lists
    that feed displays."""
    a = f"{alias}." if alias else ""
    return (
        f"CASE WHEN COALESCE({a}actual_duration_seconds, 0) > 0 "
        f"THEN ({a}actual_duration_seconds / 60)::text || ':' || "
        f"lpad(({a}actual_duration_seconds % 60)::text, 2, '0') "
        f"ELSE {a}actual_time END"
    )


def round_duration_sql(alias: str = "r") -> str:
    """SQL expression (PostgreSQL) mirroring :func:`round_duration_seconds`.

    Pure expression, no bind parameters — safe to interpolate into any query
    regardless of the adapter's placeholder style.
    """
    a = f"{alias}." if alias else ""
    return (
        f"COALESCE(NULLIF({a}actual_duration_seconds, 0), "
        f"CASE WHEN {a}actual_time ~ '^[0-9]+:[0-9]{{2}}$' "
        f"THEN split_part({a}actual_time, ':', 1)::int * 60 "
        f"+ split_part({a}actual_time, ':', 2)::int END)"
    )
