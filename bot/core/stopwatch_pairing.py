"""Deterministic stopwatch round pairing — the single source of truth for
which Round 1 belongs to which Round 2.

## Why this module exists

ET:Legacy *stopwatch* is fully deterministic (see the game manual): a map is
played twice. Round 1, one team attacks; then a `map_restart` + short warmup;
then Round 2, the teams swap sides. The winner is the faster offense (or a
full-hold tie). Crucially:

  * **R1 always precedes R2** of the same map, separated only by a warmup —
    so R2 starts within seconds-to-minutes of R1 ending, never hours.
  * Only **one** match is in progress at a time on a server.

That gives us a deterministic pairing algorithm that does **not** need to guess
from filenames. Historically `match_id` was derived from the stats filename
(`YYYY-MM-DD-HHMMSS-map-round-N`), which embeds the *per-file* timestamp — so
R1 and R2 of the same match got **different** `match_id`s and never paired
(937 legacy rounds, 2025-01-01 → 2026-02-21). The live path later switched to
"R1's `date-HHMMSS`" (`stats_import_mixin`), which pairs correctly; this module
encodes that same key deterministically and lets us backfill the legacy rows.

## The algorithm (per gaming session, chronological walk)

Walk a session's play-rounds (round_number 1 or 2) in time order, keyed by
`round_start_unix` (Lua-exact) with a `round_date`+`round_time` fallback.
Maintain a single "open R1" slot (one match at a time):

  * see **R1** → if a previous R1 is still open, that previous match was
    *abandoned* (its R2 never came → moved on to a new map/match); record it as
    a lonely R1 and open the new one.
  * see **R2** → if an R1 is open, of the *same map*, within the window →
    **pair** them (shared `match_id` = R1's `date-HHMMSS`); else this R2 has no
    R1 → *anomaly* (R1 lost / never imported).
  * end of session → any still-open R1 is a lonely R1 (map not finished).

This is exactly the user-stated invariant: "R1 then R2; R2 with no R1 in
history → something is wrong; R1 with no R2 → the map wasn't played to the end."

The module is pure (stdlib only) so it is trivially unit-testable; callers
(backfill script, correlation/diagnostics) feed it plain dicts.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("stopwatch_pairing")

# Max gap allowed between an R1 and its R2 before we refuse to pair them.
# In stopwatch the real gap (R1 end → R2 start) is just the warmup (~20-40s);
# 45 min mirrors ROUND_MATCH_WINDOW_MINUTES and is generous enough to absorb
# pauses/timeouts while still rejecting an R2 that clearly belongs to a later
# session or a different match.
DEFAULT_WINDOW_MINUTES = 45

PLAY_ROUNDS = (1, 2)


@dataclass(frozen=True)
class RoundRec:
    """Minimal projection of a `rounds` row needed for pairing.

    `round_start_unix` / `round_end_unix` are the authoritative time source
    when present (Lua-exact). `round_date` ('YYYY-MM-DD') + `round_time`
    ('HHMMSS') are the always-present fallback parsed from the stats filename.
    """

    id: int
    gaming_session_id: int | None
    map_name: str
    round_number: int
    round_start_unix: int | None = None
    round_end_unix: int | None = None
    round_date: str | None = None
    round_time: str | None = None


@dataclass(frozen=True)
class Match:
    """A paired (or half-paired) stopwatch match."""

    match_id: str
    map_name: str
    gaming_session_id: int | None
    r1: RoundRec | None
    r2: RoundRec | None

    @property
    def status(self) -> str:
        if self.r1 is not None and self.r2 is not None:
            return "complete"
        if self.r1 is not None:
            return "abandoned_r1"  # R1 played, R2 never finished/imported
        return "orphan_r2"  # R2 with no R1 in history — anomaly (lost R1)


@dataclass
class PairingResult:
    matches: list[Match] = field(default_factory=list)

    @property
    def complete(self) -> list[Match]:
        return [m for m in self.matches if m.status == "complete"]

    @property
    def abandoned_r1(self) -> list[Match]:
        return [m for m in self.matches if m.status == "abandoned_r1"]

    @property
    def orphan_r2(self) -> list[Match]:
        return [m for m in self.matches if m.status == "orphan_r2"]

    def summary(self) -> dict[str, int]:
        return {
            "matches_total": len(self.matches),
            "complete": len(self.complete),
            "abandoned_r1": len(self.abandoned_r1),
            "orphan_r2": len(self.orphan_r2),
        }


def derive_match_id(r1: RoundRec) -> str:
    """Canonical pairing key = R1's `date-HHMMSS`.

    Mirrors `stats_import_mixin` (`match_id = f"{r1_date}-{r1_time}"`) so that
    backfilled legacy rows are byte-identical in format to the live path.
    Falls back to the stable `r1:<id>` form only if the R1 lacks date/time
    (never expected for real rounds, but keeps the key non-empty + unique).
    """
    if r1.round_date and r1.round_time:
        return f"{r1.round_date}-{r1.round_time}"
    return f"r1:{r1.id}"


def _sort_key(r: RoundRec) -> tuple[int, float]:
    """Chronological sort key within a session.

    Prefer `round_start_unix` (group 0, exact). Fall back to parsed
    `round_date`+`round_time` (group 0 too, so unix and parsed rounds
    interleave correctly on the same timeline). Rounds with no usable time
    sink to the end (group 1) ordered by id, so they never wedge between two
    timed rounds.
    """
    if r.round_start_unix and r.round_start_unix > 0:
        return (0, float(r.round_start_unix))
    parsed = _parse_dt_unix(r.round_date, r.round_time)
    if parsed is not None:
        return (0, float(parsed))
    return (1, float(r.id))


def _parse_dt_unix(round_date: str | None, round_time: str | None) -> int | None:
    """Parse 'YYYY-MM-DD' + 'HHMMSS' into a naive epoch used only for ordering
    and gap math (consistent within a session — absolute offset is irrelevant).
    """
    if not round_date or not round_time:
        return None
    t = str(round_time).zfill(6)
    try:
        dt = datetime.strptime(f"{round_date} {t}", "%Y-%m-%d %H%M%S")  # noqa: DTZ007 ordering-only, naive is fine
    except (ValueError, TypeError):
        return None
    return int(dt.timestamp())


def _gap_seconds(r1: RoundRec, r2: RoundRec) -> float | None:
    """Best-available time gap between R1 and R2 (R2 start − R1 end/start)."""
    r1_end = r1.round_end_unix if (r1.round_end_unix and r1.round_end_unix > 0) else None
    r1_start = r1.round_start_unix if (r1.round_start_unix and r1.round_start_unix > 0) else None
    r2_start = r2.round_start_unix if (r2.round_start_unix and r2.round_start_unix > 0) else None

    if r2_start is not None and r1_end is not None:
        return float(r2_start - r1_end)
    if r2_start is not None and r1_start is not None:
        return float(r2_start - r1_start)
    # Both via parsed fallback.
    p1 = _parse_dt_unix(r1.round_date, r1.round_time)
    p2 = _parse_dt_unix(r2.round_date, r2.round_time)
    if p1 is not None and p2 is not None:
        return float(p2 - p1)
    return None  # no usable time on either side — caller decides


def pair_rounds(
    rounds: list[RoundRec],
    *,
    window_minutes: int = DEFAULT_WINDOW_MINUTES,
) -> PairingResult:
    """Pair stopwatch R1↔R2 deterministically. See module docstring.

    Input may contain any round_number; only 1 and 2 participate (R0 summaries
    and others are ignored). Order of the input list does not matter — rounds
    are sorted per session by time.
    """
    window_seconds = window_minutes * 60
    result = PairingResult()

    # Group by session. None-session rounds are paired among themselves (a
    # degraded but deterministic bucket) rather than silently dropped.
    by_session: dict[int | None, list[RoundRec]] = {}
    for r in rounds:
        if r.round_number not in PLAY_ROUNDS:
            continue
        by_session.setdefault(r.gaming_session_id, []).append(r)

    for session_id, sess_rounds in by_session.items():
        sess_rounds.sort(key=_sort_key)
        open_r1: RoundRec | None = None

        for r in sess_rounds:
            if r.round_number == 1:
                if open_r1 is not None:
                    # Previous R1 never got its R2 → abandoned match.
                    result.matches.append(
                        Match(derive_match_id(open_r1), open_r1.map_name, session_id, open_r1, None)
                    )
                open_r1 = r
                continue

            # round_number == 2
            if open_r1 is None:
                # R2 with no R1 in history → anomaly (lost/never-imported R1).
                result.matches.append(
                    Match(derive_match_id(r), r.map_name, session_id, None, r)
                )
                continue

            same_map = _norm_map(open_r1.map_name) == _norm_map(r.map_name)
            gap = _gap_seconds(open_r1, r)
            # Pair only if same map and (gap unknown OR within window and not
            # negative-large). A small negative gap (clock jitter) is tolerated.
            in_window = gap is None or (-60 <= gap <= window_seconds)

            if same_map and in_window:
                result.matches.append(
                    Match(derive_match_id(open_r1), open_r1.map_name, session_id, open_r1, r)
                )
                open_r1 = None
            else:
                # The open R1 doesn't match this R2 (different map, or R2 too far
                # away). The R1 is abandoned; the R2 is an orphan. Do NOT consume
                # the slot's match for the R2.
                result.matches.append(
                    Match(derive_match_id(open_r1), open_r1.map_name, session_id, open_r1, None)
                )
                result.matches.append(
                    Match(derive_match_id(r), r.map_name, session_id, None, r)
                )
                open_r1 = None

        if open_r1 is not None:
            result.matches.append(
                Match(derive_match_id(open_r1), open_r1.map_name, session_id, open_r1, None)
            )

    return result


def _norm_map(map_name: str | None) -> str:
    return (map_name or "").strip().lower()
