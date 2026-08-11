"""Single source of truth for the stats importer's dead-hours window.

The endstats monitor (``bot/services/monitor_tasks_mixin.py``) pauses all
SSH polling between 02:00 and 11:00 CET. This is a deliberate operational
gate (skip SSH churn during the low-activity window), NOT a guarantee that
nobody plays then — bot tests and late gathers do produce rounds inside the
window, and no stats file can be imported nor ``rounds`` row created for
them on the SSH-poll path until the gate lifts. Proximity ingestion is
deliberately NOT gated (telemetry should land in real time), so any round
played inside the window has its proximity rows sitting parentless until
the importer wakes.

Historically the window lived as a bare ``2 <= hour < 11`` in the monitor
while the proximity relinker aged orphans on a plain 6h wall clock
(``_PERMANENT_ORPHAN_AGE_HOURS``, lowered 48h->6h in PR #369 to stop
retry/log churn). 6h wall < 9h window, so every round played 02:00-05:00
CET was written off as a permanent orphan minutes-to-hours before the
importer could possibly have produced its ``rounds`` row (measured live
2026-08-11: 5 night-test rounds -> 8,810 permanent dev orphans).

``awake_cutoff`` fixes that class of bug: staleness deadlines that exist
to bound *importer* retries are computed in importer-awake hours, so time
the importer spends asleep never counts against a round.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# Local (game-server) hours during which the stats importer is paused.
# Inclusive start, exclusive end — mirrors the monitor's historical
# `2 <= hour < 11` check.
DEAD_HOURS_START = 2
DEAD_HOURS_END = 11

# The game server runs on CET/CEST; Europe/Paris is the project-wide
# spelling of that zone (same as monitor_tasks_mixin).
DEAD_HOURS_TZNAME = "Europe/Paris"

# awake_cutoff walks backwards one awake-block per iteration (at most a
# few per day). 200 iterations ≈ several months of walk-back — far past
# any meaningful staleness horizon, so hitting it means bad input.
_MAX_WALK_ITERATIONS = 200


def is_dead_hour(hour: int) -> bool:
    """True if a local wall-clock hour falls inside the dead window."""
    return DEAD_HOURS_START <= hour < DEAD_HOURS_END


def awake_cutoff(now: datetime, awake_hours: float) -> datetime:
    """Instant T such that importer-awake time between T and ``now`` is
    ``awake_hours``.

    Anything with a timestamp older than T has had at least
    ``awake_hours`` hours of *running importer* in which to be resolved;
    anything newer has not, no matter how old it is on the wall clock.
    Use T wherever a staleness deadline previously used
    ``now - timedelta(hours=awake_hours)``.

    ``now`` must be timezone-aware (the relinker passes UTC). The walk
    happens in local wall-clock time; the result is returned in UTC.
    DST transitions inside the walked range can skew the accounting by
    up to an hour — irrelevant at the accuracy staleness cutoffs need.
    """
    if now.tzinfo is None:
        raise ValueError("awake_cutoff requires a timezone-aware 'now'")
    if awake_hours < 0:
        raise ValueError(f"awake_hours must be >= 0, got {awake_hours!r}")

    tz = ZoneInfo(DEAD_HOURS_TZNAME)
    # Naive local wall clock: the window is defined in wall-clock hours,
    # and naive arithmetic can't accidentally mix in UTC offsets.
    cur = now.astimezone(tz).replace(tzinfo=None)
    remaining = timedelta(hours=awake_hours)

    iterations = 0
    while remaining > timedelta(0):
        iterations += 1
        if iterations > _MAX_WALK_ITERATIONS:
            raise ValueError(
                f"awake_cutoff walked {_MAX_WALK_ITERATIONS} blocks without "
                f"satisfying awake_hours={awake_hours!r} — bad input?"
            )
        day_start = cur.replace(hour=0, minute=0, second=0, microsecond=0)
        dead_start = day_start + timedelta(hours=DEAD_HOURS_START)
        dead_end = day_start + timedelta(hours=DEAD_HOURS_END)

        if cur > dead_end:
            # Inside the evening awake block (dead_end, midnight].
            block_lo = dead_end
        elif cur > dead_start:
            # Inside the dead window (or exactly at its end): jump to its
            # start; asleep time consumes nothing.
            cur = dead_start
            continue
        elif cur > day_start:
            # Inside the early-morning awake block (midnight, dead_start].
            block_lo = day_start
        else:
            # Exactly midnight: the previous awake block is the previous
            # day's evening (prev dead_end, midnight].
            block_lo = day_start - timedelta(days=1) + timedelta(hours=DEAD_HOURS_END)

        available = cur - block_lo
        if remaining <= available:
            cur = cur - remaining
            remaining = timedelta(0)
        else:
            remaining -= available
            cur = block_lo

    return cur.replace(tzinfo=tz).astimezone(timezone.utc)
