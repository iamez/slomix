#!/usr/bin/env python3
"""Measure trajectory time lost after revives without trusting stored round links.

The Lua writer ends a player track in ``et_Obituary`` but does not resume it
when ``et_ClientSpawn(..., revived=1)`` fires. This read-only tool measures the
resulting unavailable interval directly from raw proximity capture files:

* ``REVIVES`` is the primary callback source, but only captures with a later
  ``KILL_OUTCOME`` section prove that the writer completed the relevant
  output prefix.
* ``KILL_OUTCOME outcome=revived`` is only an enemy-kill subset cross-check.
* a gap starts at a revive and ends at the next normal player-track spawn, or
  at the exact in-game round end when no later spawn exists.

The tool never writes to PostgreSQL. By default it reads the ``rounds`` table
only to apply the established validity gate through exact source start/end
identity. Use ``--skip-db-gates`` only for fixtures or explicitly degraded
raw-capture exploration.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import re
import sys
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SECTION_HEADER_RE = re.compile(r"^# ([A-Z][A-Z0-9_]*)$")
BOT_GUID_PREFIXES = ("OMNIBOT",)
ROUND_END_JITTER_MS = 1
MIN_REVIVE_TRACKER_VERSION = 5
ALLOWED_ROUND_STATUSES = {"completed", "substitution", None}
KNOWN_DEATH_TYPES = {
    "killed",
    "selfkill",
    "fallen",
    "world",
    "teamkill",
    "round_end",
    "disconnect",
    "unknown",
}


class CaptureParseError(ValueError):
    """A relevant raw-capture row cannot be measured safely."""


@dataclass(frozen=True)
class RoundIdentity:
    map_name: str
    round_number: int
    round_start_unix: int
    round_end_unix: int


@dataclass(frozen=True)
class Track:
    guid: str
    spawn_time_ms: int
    death_time_ms: int | None
    death_type: str | None


@dataclass(frozen=True)
class Revive:
    time_ms: int
    revived_guid: str


@dataclass(frozen=True)
class RevivedOutcome:
    outcome_time_ms: int
    victim_guid: str


@dataclass(frozen=True)
class RawCapture:
    path: Path
    identity: RoundIdentity
    tracker_version: int
    tracks: tuple[Track, ...]
    revives: tuple[Revive, ...]
    revived_outcomes: tuple[RevivedOutcome, ...]
    sections: tuple[str, ...]

    @property
    def exact_round_end_ms(self) -> int | None:
        values = [
            track.death_time_ms
            for track in self.tracks
            if track.death_type == "round_end" and track.death_time_ms is not None
        ]
        if not values or max(values) - min(values) > ROUND_END_JITTER_MS:
            return None
        return max(values)


@dataclass(frozen=True)
class RoundGate:
    round_id: int
    identity: RoundIdentity
    is_valid: bool | None
    is_bot_round: bool | None
    round_status: str | None

    @property
    def passes(self) -> bool:
        return (
            self.is_valid is not False and self.is_bot_round is not True and self.round_status in ALLOWED_ROUND_STATUSES
        )


class RoundGateMatcher:
    """Match raw captures to one canonical round without fuzzy/date joins."""

    def __init__(self, gates: Iterable[RoundGate]):
        self._by_start: dict[tuple[str, int, int], list[RoundGate]] = defaultdict(list)
        self._by_end: dict[tuple[str, int, int], list[RoundGate]] = defaultdict(list)
        for gate in gates:
            identity = gate.identity
            if identity.round_start_unix > 0:
                self._by_start[(identity.map_name, identity.round_number, identity.round_start_unix)].append(gate)
            if identity.round_end_unix > 0:
                self._by_end[(identity.map_name, identity.round_number, identity.round_end_unix)].append(gate)

    def classify(self, identity: RoundIdentity) -> tuple[str, RoundGate | None]:
        start_matches = self._by_start.get(
            (identity.map_name, identity.round_number, identity.round_start_unix),
            [],
        )
        end_matches = self._by_end.get(
            (identity.map_name, identity.round_number, identity.round_end_unix),
            [],
        )
        matches = {gate.round_id: gate for gate in (*start_matches, *end_matches)}
        if not matches:
            return "unmatched_exact_identity", None
        if len(matches) != 1:
            return "ambiguous_exact_identity", None

        gate = next(iter(matches.values()))
        if not gate.passes:
            return "rejected_by_round_quality_gate", gate
        if start_matches and end_matches:
            return "matched_start_and_end", gate
        if start_matches:
            return "matched_start", gate
        return "matched_end", gate


def _is_bot_guid(guid: str) -> bool:
    normalized = guid.strip().upper()
    return any(normalized.startswith(prefix) for prefix in BOT_GUID_PREFIXES)


def _required_int(value: str, field: str, path: Path, line_number: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise CaptureParseError(f"{path.name}:{line_number}: invalid {field}={value!r}") from exc


def parse_capture(path: Path) -> RawCapture:
    """Parse only the sections needed for the coverage measurement."""
    metadata: dict[str, int | str] = {
        "map_name": "",
        "round_number": 0,
        "round_start_unix": 0,
        "round_end_unix": 0,
        "tracker_version": 0,
    }
    tracks: list[Track] = []
    revives: list[Revive] = []
    revived_outcomes: list[RevivedOutcome] = []
    sections: list[str] = []
    section: str | None = None

    with path.open(encoding="utf-8", errors="replace") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("# PROXIMITY_TRACKER_V"):
                metadata["tracker_version"] = _required_int(
                    line.rsplit("V", 1)[1], "tracker_version", path, line_number
                )
                section = None
                continue
            if line.startswith("# map="):
                metadata["map_name"] = line.split("=", 1)[1].strip().lower()
                continue
            if line.startswith("# round="):
                metadata["round_number"] = _required_int(line.split("=", 1)[1], "round", path, line_number)
                continue
            if line.startswith("# round_start_unix="):
                metadata["round_start_unix"] = _required_int(
                    line.split("=", 1)[1], "round_start_unix", path, line_number
                )
                continue
            if line.startswith("# round_end_unix="):
                metadata["round_end_unix"] = _required_int(line.split("=", 1)[1], "round_end_unix", path, line_number)
                continue

            section_match = SECTION_HEADER_RE.fullmatch(line)
            if section_match:
                section_name = section_match.group(1)
                sections.append(section_name)
                section = {
                    "PLAYER_TRACKS": "tracks",
                    "REVIVES": "revives",
                    "KILL_OUTCOME": "kill_outcomes",
                }.get(section_name)
                continue
            if line.startswith("#"):
                continue

            if section == "tracks":
                parts = line.split(";", 9)
                if len(parts) < 9:
                    raise CaptureParseError(f"{path.name}:{line_number}: malformed PLAYER_TRACKS row")
                # Zero is a real boundary value in raw captures: old
                # warmup-crossing lives can end exactly when the round clock
                # starts. The DB parser maps 0 to NULL for storage, but doing
                # that here would discard a measurable player-round.
                death_time = _required_int(parts[5], "death_time", path, line_number) if parts[5] else None
                # V4 rows use field 7 for the numeric sample count. V4.1+
                # uses it for death_type, even when an empty trailing path
                # column was omitted and the row therefore has only 9 fields.
                death_type = parts[7] if parts[7] in KNOWN_DEATH_TYPES else None
                tracks.append(
                    Track(
                        guid=parts[0].strip(),
                        spawn_time_ms=_required_int(parts[4], "spawn_time", path, line_number),
                        death_time_ms=death_time,
                        death_type=death_type or None,
                    )
                )
            elif section == "revives":
                parts = line.split(";")
                if len(parts) < 11:
                    raise CaptureParseError(f"{path.name}:{line_number}: malformed REVIVES row")
                revives.append(
                    Revive(
                        time_ms=_required_int(parts[0], "revive_time", path, line_number),
                        revived_guid=parts[3].strip(),
                    )
                )
            elif section == "kill_outcomes":
                parts = line.split(";")
                if len(parts) < 14:
                    raise CaptureParseError(f"{path.name}:{line_number}: malformed KILL_OUTCOME row")
                if parts[6] == "revived":
                    revived_outcomes.append(
                        RevivedOutcome(
                            outcome_time_ms=_required_int(parts[7], "outcome_time", path, line_number),
                            victim_guid=parts[1].strip(),
                        )
                    )

    identity = RoundIdentity(
        map_name=str(metadata["map_name"]),
        round_number=int(metadata["round_number"]),
        round_start_unix=int(metadata["round_start_unix"]),
        round_end_unix=int(metadata["round_end_unix"]),
    )
    if (
        not identity.map_name
        or identity.round_number not in (1, 2)
        or identity.round_start_unix <= 0
        or identity.round_end_unix <= 0
    ):
        raise CaptureParseError(f"{path.name}: incomplete or invalid round identity")
    if not tracks:
        raise CaptureParseError(f"{path.name}: PLAYER_TRACKS is empty")

    return RawCapture(
        path=path,
        identity=identity,
        tracker_version=int(metadata["tracker_version"]),
        tracks=tuple(tracks),
        revives=tuple(revives),
        revived_outcomes=tuple(revived_outcomes),
        sections=tuple(sections),
    )


def _merge_intervals(intervals: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
            continue
        merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def _nearest_rank(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _round_player_intervals(
    capture: RawCapture,
    round_end_ms: int,
) -> tuple[
    dict[str, list[tuple[int, int]]],
    dict[str, tuple[int, int]],
    Counter[str],
    Counter[str],
]:
    tracks_by_guid: dict[str, list[Track]] = defaultdict(list)
    revives_by_guid: dict[str, list[Revive]] = defaultdict(list)
    for track in capture.tracks:
        if not _is_bot_guid(track.guid):
            tracks_by_guid[track.guid].append(track)
    for revive in capture.revives:
        if not _is_bot_guid(revive.revived_guid):
            revives_by_guid[revive.revived_guid].append(revive)

    player_exclusions: Counter[str] = Counter()
    raw_window_endings: Counter[str] = Counter()
    intervals_by_guid: dict[str, list[tuple[int, int]]] = {}
    participation_by_guid: dict[str, tuple[int, int]] = {}

    orphan_guids = set(revives_by_guid) - set(tracks_by_guid)
    if orphan_guids:
        player_exclusions["orphan_revive_guid"] += len(orphan_guids)

    for guid, tracks in tracks_by_guid.items():
        # Old captures can contain complete warmup lives on the same clock.
        # A life ending at or before t=0 contributes no in-round state and
        # cannot bound a positive-time revive gap.
        ordered_tracks = sorted(
            (track for track in tracks if track.death_time_ms is None or track.death_time_ms > 0),
            key=lambda item: item.spawn_time_ms,
        )
        if not ordered_tracks:
            player_exclusions["no_in_round_track"] += 1
            continue
        invalid_track = any(
            track.death_time_ms is None
            or track.spawn_time_ms > round_end_ms
            or track.death_time_ms < track.spawn_time_ms
            or track.death_time_ms > round_end_ms + ROUND_END_JITTER_MS
            for track in ordered_tracks
        )
        if invalid_track:
            player_exclusions["invalid_track_interval"] += 1
            continue

        if any(
            max(0, current.spawn_time_ms) < previous.death_time_ms  # type: ignore[operator]
            for previous, current in zip(ordered_tracks, ordered_tracks[1:])
        ):
            player_exclusions["overlapping_lives"] += 1
            continue

        participation_start = max(0, ordered_tracks[0].spawn_time_ms)
        participation_end = round_end_ms
        final_track = ordered_tracks[-1]
        if final_track.death_type == "disconnect" and final_track.death_time_ms is not None:
            participation_end = min(participation_end, final_track.death_time_ms)
        if participation_start >= participation_end:
            player_exclusions["no_observed_participation"] += 1
            continue

        player_revives = sorted(revives_by_guid.get(guid, []), key=lambda item: item.time_ms)
        invalid_revive = False
        raw_intervals: list[tuple[int, int]] = []
        # Negative starts are warmup-crossing lives on this same clock. Their
        # observable in-round interval begins at t=0.
        spawn_times = [max(0, track.spawn_time_ms) for track in ordered_tracks]
        for revive in player_revives:
            if revive.time_ms < 0 or revive.time_ms > round_end_ms:
                player_exclusions["revive_outside_round"] += 1
                invalid_revive = True
                break
            if any(
                max(0, track.spawn_time_ms) <= revive.time_ms
                and track.death_time_ms is not None
                and revive.time_ms < track.death_time_ms
                for track in ordered_tracks
            ):
                player_exclusions["revive_inside_recorded_life"] += 1
                invalid_revive = True
                break
            if not any(
                track.death_time_ms is not None and track.death_time_ms <= revive.time_ms for track in ordered_tracks
            ):
                player_exclusions["revive_without_prior_track"] += 1
                invalid_revive = True
                break

            next_spawn_index = bisect_right(spawn_times, revive.time_ms)
            if next_spawn_index < len(spawn_times):
                gap_end = spawn_times[next_spawn_index]
                raw_window_endings["next_normal_spawn"] += 1
            else:
                gap_end = round_end_ms
                raw_window_endings["round_end"] += 1
            clipped_start = max(revive.time_ms, participation_start)
            clipped_end = min(gap_end, participation_end)
            if clipped_end > clipped_start:
                raw_intervals.append((clipped_start, clipped_end))

        if not invalid_revive:
            intervals_by_guid[guid] = _merge_intervals(raw_intervals)
            participation_by_guid[guid] = (participation_start, participation_end)

    return intervals_by_guid, participation_by_guid, player_exclusions, raw_window_endings


def _manifest_digest(captures: Iterable[RawCapture]) -> str:
    digest = hashlib.sha256()
    for capture in sorted(captures, key=lambda item: item.path.name):
        identity = capture.identity
        content_digest = hashlib.sha256()
        with capture.path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                content_digest.update(chunk)
        digest.update(
            (
                f"{capture.path.name}|{identity.map_name}|{identity.round_number}|"
                f"{identity.round_start_unix}|{identity.round_end_unix}|"
                f"{content_digest.hexdigest()}\n"
            ).encode()
        )
    return digest.hexdigest()


def analyze_captures(
    captures: Iterable[RawCapture],
    *,
    gate_matcher: RoundGateMatcher | None,
    clock_anchor_not_before_unix: int,
    files_seen: int | None = None,
    parse_exclusions: Counter[str] | None = None,
) -> dict[str, Any]:
    parsed = list(captures)
    capture_exclusions = Counter(parse_exclusions or {})
    gate_matches: Counter[str] = Counter()

    identities: dict[RoundIdentity, list[RawCapture]] = defaultdict(list)
    for capture in parsed:
        identities[capture.identity].append(capture)
    duplicate_identities = {identity for identity, grouped in identities.items() if len(grouped) > 1}
    duplicate_capture_count = sum(len(identities[identity]) for identity in duplicate_identities)
    if duplicate_capture_count:
        capture_exclusions["duplicate_raw_identity"] += duplicate_capture_count

    candidate_captures: list[tuple[RawCapture, int | None]] = []
    for capture in parsed:
        if capture.identity in duplicate_identities:
            continue
        canonical_round_id = None
        if gate_matcher is not None:
            classification, gate = gate_matcher.classify(capture.identity)
            gate_matches[classification] += 1
            if classification not in {
                "matched_start_and_end",
                "matched_start",
                "matched_end",
            }:
                capture_exclusions[classification] += 1
                continue
            assert gate is not None
            canonical_round_id = gate.round_id
        else:
            gate_matches["skipped"] += 1

        # Git history verifies that REVIVES was introduced with the V5
        # artifact. V4 explicitly ignored revived spawns, so an absent event
        # there means "unsupported", not a measured zero.
        if capture.tracker_version < MIN_REVIVE_TRACKER_VERSION:
            capture_exclusions["revive_capability_not_proven"] += 1
            continue

        # V5/V6 is too coarse to prove the round-live clock fix. Historical
        # captures must be bounded by an independently verified deployment
        # timestamp for an artifact containing the re-anchor.
        if capture.identity.round_start_unix < clock_anchor_not_before_unix:
            capture_exclusions["clock_anchor_not_proven"] += 1
            continue

        # REVIVES is optional when there were zero callbacks, and historical
        # files have no EOF marker. KILL_OUTCOME is emitted later in the same
        # synchronous writer. Its presence proves that the writer completed
        # the entire measurement-relevant REVIVES branch, including a genuine
        # zero when no REVIVES header was emitted.
        kill_outcome_index = (
            capture.sections.index("KILL_OUTCOME")
            if "KILL_OUTCOME" in capture.sections
            else None
        )
        revive_index = (
            capture.sections.index("REVIVES")
            if "REVIVES" in capture.sections
            else None
        )
        if kill_outcome_index is None or (
            revive_index is not None and kill_outcome_index <= revive_index
        ):
            capture_exclusions["revive_section_completion_not_proven"] += 1
            continue

        exact_end = capture.exact_round_end_ms
        if exact_end is None:
            capture_exclusions["missing_or_inconsistent_exact_round_end"] += 1
            continue
        if exact_end <= 0:
            capture_exclusions["invalid_exact_round_end"] += 1
            continue
        candidate_captures.append((capture, canonical_round_id))

    canonical_groups: dict[int, list[RawCapture]] = defaultdict(list)
    for capture, canonical_round_id in candidate_captures:
        if canonical_round_id is not None:
            canonical_groups[canonical_round_id].append(capture)
    duplicate_canonical_ids = {round_id for round_id, grouped in canonical_groups.items() if len(grouped) > 1}
    if duplicate_canonical_ids:
        capture_exclusions["duplicate_canonical_round"] += sum(
            len(canonical_groups[round_id]) for round_id in duplicate_canonical_ids
        )
    included = [
        capture
        for capture, canonical_round_id in candidate_captures
        if canonical_round_id not in duplicate_canonical_ids
    ]

    total_gap_ms = 0
    total_player_round_ms = 0
    total_snapshot_gap_ms = 0
    total_round_ms = 0
    eligible_human_rounds = 0
    eligible_player_rounds = 0
    affected_player_rounds = 0
    affected_rounds = 0
    complete_roster_rounds_excluded = 0
    merged_windows = 0
    raw_window_endings: Counter[str] = Counter()
    player_exclusions: Counter[str] = Counter()
    affected_fractions: list[float] = []
    all_player_fractions: list[float] = []
    human_guids: set[str] = set()
    primary_revives: Counter[tuple[RoundIdentity, str, int]] = Counter()
    subset_outcomes: Counter[tuple[RoundIdentity, str, int]] = Counter()
    observation_starts: list[int] = []
    observation_ends: list[int] = []

    for capture in included:
        round_end_ms = capture.exact_round_end_ms
        assert round_end_ms is not None
        observation_starts.append(capture.identity.round_start_unix)
        observation_ends.append(capture.identity.round_end_unix)

        (
            intervals_by_guid,
            participation_by_guid,
            round_player_exclusions,
            endings,
        ) = _round_player_intervals(capture, round_end_ms)
        player_exclusions.update(round_player_exclusions)
        raw_window_endings.update(endings)

        for revive in capture.revives:
            if not _is_bot_guid(revive.revived_guid):
                primary_revives[(capture.identity, revive.revived_guid, revive.time_ms)] += 1
        for outcome in capture.revived_outcomes:
            if not _is_bot_guid(outcome.victim_guid):
                subset_outcomes[(capture.identity, outcome.victim_guid, outcome.outcome_time_ms)] += 1

        round_intervals: list[tuple[int, int]] = []
        round_affected = False
        for guid, intervals in intervals_by_guid.items():
            participation_start, participation_end = participation_by_guid[guid]
            participation_ms = participation_end - participation_start
            human_guids.add(guid)
            eligible_player_rounds += 1
            total_player_round_ms += participation_ms
            player_gap_ms = sum(end - start for start, end in intervals)
            total_gap_ms += player_gap_ms
            fraction = player_gap_ms / participation_ms
            all_player_fractions.append(fraction)
            if intervals:
                affected_player_rounds += 1
                affected_fractions.append(fraction)
                merged_windows += len(intervals)
                round_intervals.extend(intervals)
                round_affected = True

        # Historical bot-only rounds can predate the is_bot_round backfill.
        # The negative per-GUID filter is authoritative for this denominator:
        # a round with no eligible human participant contributes no "human
        # complete-roster" time.
        if intervals_by_guid and not round_player_exclusions:
            eligible_human_rounds += 1
            if round_affected:
                affected_rounds += 1
            total_snapshot_gap_ms += sum(end - start for start, end in _merge_intervals(round_intervals))
            total_round_ms += round_end_ms
        elif intervals_by_guid:
            complete_roster_rounds_excluded += 1

    matched_cross_check = sum(min(count, subset_outcomes[key]) for key, count in primary_revives.items())
    unmatched_subset = sum(max(0, count - primary_revives[key]) for key, count in subset_outcomes.items())
    primary_count = sum(primary_revives.values())
    subset_count = sum(subset_outcomes.values())

    def ratio(numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    return {
        "schema_version": 1,
        "measurement": "post_revive_trajectory_gap",
        "input": {
            "files_seen": files_seen if files_seen is not None else len(parsed),
            "files_parsed": len(parsed),
            "files_included": len(included),
            "files_excluded": sum(capture_exclusions.values()),
            "capture_manifest_sha256": _manifest_digest(parsed),
            "tracker_versions": dict(sorted(Counter(capture.tracker_version for capture in parsed).items())),
            "minimum_revive_capable_tracker_version": MIN_REVIVE_TRACKER_VERSION,
            "clock_anchor_not_before_unix": clock_anchor_not_before_unix,
            "revive_section_completion_rule": (
                "KILL_OUTCOME must be present after REVIVES when REVIVES is present"
            ),
            "observation_start_utc": (
                datetime.fromtimestamp(min(observation_starts), timezone.utc).isoformat()
                if observation_starts
                else None
            ),
            "observation_end_utc": (
                datetime.fromtimestamp(max(observation_ends), timezone.utc).isoformat() if observation_ends else None
            ),
        },
        "quality_gate": {
            "mode": "exact_db_start_or_end" if gate_matcher is not None else "skipped",
            "matches": dict(sorted(gate_matches.items())),
            "allowed_round_numbers": [1, 2],
            "allowed_statuses": ["completed", "substitution", None],
            "requires_is_valid_not_false": True,
            "requires_is_bot_round_not_true": True,
        },
        "population": {
            "capture_rounds_included": len(included),
            "eligible_human_rounds": eligible_human_rounds,
            "complete_roster_rounds_excluded_for_invalid_participant": complete_roster_rounds_excluded,
            "affected_rounds": affected_rounds,
            "eligible_human_player_rounds": eligible_player_rounds,
            "affected_human_player_rounds": affected_player_rounds,
            "unique_human_guids": len(human_guids),
            "bot_guid_prefixes_excluded": list(BOT_GUID_PREFIXES),
        },
        "revive_cross_check": {
            "primary_revive_callbacks": primary_count,
            "enemy_kill_revived_outcomes": subset_count,
            "matched_enemy_kill_subset": matched_cross_check,
            "enemy_kill_subset_without_callback": unmatched_subset,
            "primary_callbacks_covered_by_enemy_kill_subset_fraction": ratio(matched_cross_check, primary_count),
        },
        "trajectory_gap": {
            "raw_revive_windows": sum(raw_window_endings.values()),
            "raw_window_endings": dict(sorted(raw_window_endings.items())),
            "merged_player_windows": merged_windows,
            "unavailable_ms": total_gap_ms,
            "eligible_player_round_ms": total_player_round_ms,
            "unavailable_fraction": ratio(total_gap_ms, total_player_round_ms),
            "unavailable_percent": (100 * total_gap_ms / total_player_round_ms if total_player_round_ms else None),
            "affected_player_round_fraction": ratio(affected_player_rounds, eligible_player_rounds),
            "affected_player_round_gap_fraction_median": (median(affected_fractions) if affected_fractions else None),
            "affected_player_round_gap_fraction_p95_nearest_rank": _nearest_rank(affected_fractions, 0.95),
            "all_player_round_gap_fraction_median": (median(all_player_fractions) if all_player_fractions else None),
            "all_player_round_gap_fraction_p95_nearest_rank": _nearest_rank(all_player_fractions, 0.95),
        },
        "complete_roster_snapshot_unavailability": {
            "unavailable_ms": total_snapshot_gap_ms,
            "eligible_round_ms": total_round_ms,
            "unavailable_fraction": ratio(total_snapshot_gap_ms, total_round_ms),
            "unavailable_percent": (100 * total_snapshot_gap_ms / total_round_ms if total_round_ms else None),
            "rule": "a timestamp is unavailable when any eligible human has an open post-revive gap",
            "invalid_participant_rule": (
                "a round with any excluded human participant is omitted from this denominator"
            ),
        },
        "exclusions": {
            "captures": dict(sorted(capture_exclusions.items())),
            "human_player_rounds": dict(sorted(player_exclusions.items())),
        },
        "interpretation": {
            "gap_semantics": (
                "Known-or-unresolved state/trajectory unavailability from revive "
                "until next normal track spawn or exact in-game round end; it is "
                "not a claim that the player remained alive for the whole window."
            ),
            "weighting": (
                "Coverage measurement only. It defines no player score or metric "
                "weight and therefore does not bypass the specification section 8 gate."
            ),
        },
    }


async def load_round_gate_matcher() -> RoundGateMatcher:
    """Read canonical round quality metadata without mutating the database."""
    from bot.config import load_config
    from bot.core.database_adapter import create_adapter

    config = load_config()
    adapter = create_adapter(**config.get_database_adapter_kwargs())
    await adapter.connect()
    try:
        rows = await adapter.fetch_all(
            """
            SELECT id, LOWER(map_name), round_number,
                   COALESCE(round_start_unix, 0),
                   COALESCE(round_end_unix, 0),
                   is_valid, is_bot_round, round_status
            FROM rounds
            WHERE round_number IN (1, 2)
            """
        )
    finally:
        await adapter.close()

    gates = [
        RoundGate(
            round_id=int(row[0]),
            identity=RoundIdentity(
                map_name=str(row[1]),
                round_number=int(row[2]),
                round_start_unix=int(row[3]),
                round_end_unix=int(row[4]),
            ),
            is_valid=row[5],
            is_bot_round=row[6],
            round_status=row[7],
        )
        for row in rows
    ]
    return RoundGateMatcher(gates)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("local_proximity"),
        help="Directory containing *_engagements.txt raw captures.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write JSON to this path instead of stdout.",
    )
    parser.add_argument(
        "--skip-db-gates",
        action="store_true",
        help="Skip canonical round validity gates (degraded; intended for fixtures only).",
    )
    parser.add_argument(
        "--clock-anchor-not-before-unix",
        type=int,
        required=True,
        help=(
            "Earliest round_start_unix covered by an independently verified "
            "round-live clock re-anchor deployment."
        ),
    )
    return parser.parse_args()


async def _run() -> int:
    args = _parse_args()
    paths = sorted(args.input_dir.glob("*_engagements.txt"))
    if not paths:
        raise SystemExit(f"no *_engagements.txt files found in {args.input_dir}")

    captures: list[RawCapture] = []
    parse_exclusions: Counter[str] = Counter()
    for path in paths:
        try:
            captures.append(parse_capture(path))
        except (CaptureParseError, OSError):
            parse_exclusions["parse_or_identity_error"] += 1

    gate_matcher = None if args.skip_db_gates else await load_round_gate_matcher()
    result = analyze_captures(
        captures,
        gate_matcher=gate_matcher,
        clock_anchor_not_before_unix=args.clock_anchor_not_before_unix,
        files_seen=len(paths),
        parse_exclusions=parse_exclusions,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


def main() -> int:
    try:
        return asyncio.run(_run())
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
