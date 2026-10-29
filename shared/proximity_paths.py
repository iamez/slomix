"""Explicit discontinuities in ordered proximity paths, not inferred pause time.

Readers without an event declaration keep their legacy behaviour. A resume
marker breaks the incoming segment for its ENTIRE timestamp group: duplicate
points cannot hide a gap by appearing just before the marker. Callers needing
chronological sorting must sort stably before splitting; never sort away events.
"""

from itertools import groupby


def _timestamp(point: dict) -> int:
    time_ms = point.get("time", 0)
    if point.get("event") == "capture_resume" and (
        "time" not in point or type(time_ms) is not int
    ):
        raise ValueError("capture_resume requires an integer timestamp")
    return time_ms


def capture_segments(path: list[dict]) -> list[list[dict]]:
    """Split an ordered path without mutating points; retain baseline markers."""
    segments: list[list[dict]] = []
    current: list[dict] = []
    for _, group in groupby(path, key=_timestamp):
        points = list(group)
        if any(p.get("event") == "capture_resume" for p in points):
            if current:
                segments.append(current)
            # Each coincident boundary point stands alone. Otherwise a normal
            # duplicate before the marker could draw the very jump we rejected.
            segments.extend([[p] for p in points[:-1]])
            current = [points[-1]]
        else:
            current.extend(points)
    if current:
        segments.append(current)
    return segments


def in_capture_gap(path: list[dict], target_ms: int) -> bool:
    """Offline replay ONLY: refuse times strictly inside an explicit gap.

Uses a later boundary as hindsight, so must NOT be used to revise a causal
information-state/Spiderweb belief. Both measured endpoints remain available.
An initial boundary also forbids inventing a position before the first capture.
"""
    previous_time = None
    for time_ms, group in groupby(path, key=_timestamp):
        boundary = any(p.get("event") == "capture_resume" for p in group)
        if boundary and target_ms < time_ms and (
            previous_time is None or previous_time < target_ms
        ):
            return True
        previous_time = time_ms
    return False
