#!/usr/bin/env python3
"""Read-only §5 reinforcement-clock validation against PostgreSQL telemetry."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import psycopg2
from psycopg2.extras import RealDictCursor

from website.backend.services.reinforcement_clock import (
    CLOCK_PROTOCOL_VERSION,
    LANDING_CLUSTER_JITTER_MS,
    MIN_INTERNAL_OBSERVATIONS,
    MIN_VALIDATION_LANDINGS,
    MIN_VALIDATION_PASS_RATIO,
    VALIDATION_RESIDUAL_TOLERANCE_MS,
    PlayerLife,
    ReviveObservation,
    TimingObservation,
    cluster_spawn_landings,
    infer_clock,
    qualify_normal_spawns,
    timing_exclusion_reason,
    validate_clock,
)

# Frozen before the final query. The preliminary feasibility result in spec
# revision 8 used data available through 2026-07-27. Later rounds are the
# chronological confirmation block and are never used to tune these constants.
CONFIRMATION_START_DATE = date(2026, 7, 28)

ROUND_QUALITY_STATUSES = frozenset({None, "completed", "substitution"})

TIMING_SQL = """
SELECT pst.id, pst.round_id, pst.session_date, pst.map_name, pst.victim_team,
       pst.victim_guid, pst.victim_name, pst.kill_time,
       pst.enemy_spawn_interval, pst.time_to_next_spawn,
       pst.spawn_timing_score, pst.created_at,
       r.round_number AS linked_round_number, r.is_valid, r.is_bot_round,
       r.round_status
FROM proximity_spawn_timing pst
LEFT JOIN rounds r ON r.id = pst.round_id
ORDER BY pst.id
"""

LIFE_SQL = """
SELECT pt.id, pt.round_id, pt.session_date, pt.map_name, pt.player_guid,
       pt.player_name, pt.team, pt.spawn_time_ms, pt.death_time_ms,
       pt.path -> -1 ->> 'event' AS death_type, pt.created_at,
       r.round_number AS linked_round_number, r.is_valid, r.is_bot_round,
       r.round_status
FROM player_track pt
LEFT JOIN rounds r ON r.id = pt.round_id
ORDER BY pt.id
"""

REVIVE_SQL = """
SELECT pr.id, pr.round_id, pr.session_date, pr.revived_guid, pr.revived_name,
       pr.revive_time, pr.created_at,
       r.round_number AS linked_round_number, r.is_valid, r.is_bot_round,
       r.round_status
FROM proximity_revive pr
LEFT JOIN rounds r ON r.id = pr.round_id
ORDER BY pr.id
"""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="JSON evidence path")
    return parser.parse_args()


def _connect():
    required = (
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DATABASE",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    )
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise SystemExit(f"Missing database environment variables: {', '.join(missing)}")
    connection = psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        dbname=os.environ["POSTGRES_DATABASE"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )
    connection.set_session(
        isolation_level="REPEATABLE READ",
        readonly=True,
        autocommit=False,
    )
    return connection


def _fetch_all(connection, sql: str) -> list[dict[str, Any]]:
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(sql)
        return [dict(row) for row in cursor.fetchall()]


def _is_quality_round(row: dict[str, Any]) -> bool:
    return (
        row["round_id"] is not None
        and row["linked_round_number"] in (1, 2)
        and row["is_valid"] is not False
        and row["is_bot_round"] is not True
        and row["round_status"] in ROUND_QUALITY_STATUSES
    )


def _is_bot(guid: str | None, name: str | None) -> bool:
    return (guid or "").upper().startswith("OMNIBOT") or (name or "").upper().startswith("[BOT]")


def _manifest_hash(*row_sets: Iterable[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for rows in row_sets:
        for row in rows:
            digest.update(
                json.dumps(
                    row,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                ).encode("utf-8")
            )
            digest.update(b"\n")
    return digest.hexdigest()


def _percentile(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * percentile)
    return ordered[index]


def _cohort_name(session_date: date) -> str:
    return "confirmation" if session_date >= CONFIRMATION_START_DATE else "discovery"


def _raw_internal_consistency(timing_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Reproduce the ungated historical diagnostic before quality exclusions."""
    by_group: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in timing_rows:
        if row["round_id"] is not None:
            by_group[(int(row["round_id"]), str(row["victim_team"] or ""))].append(row)

    statuses: Counter[str] = Counter()
    inconsistent: list[dict[str, Any]] = []
    for (round_id, team), rows in sorted(by_group.items()):
        observations = [
            TimingObservation(
                team=team,
                kill_time_ms=int(row["kill_time"] or 0),
                interval_ms=int(row["enemy_spawn_interval"] or 0),
                time_to_next_spawn_ms=(
                    int(row["time_to_next_spawn"])
                    if row["time_to_next_spawn"] is not None
                    else None
                ),
                spawn_timing_score=(
                    float(row["spawn_timing_score"])
                    if row["spawn_timing_score"] is not None
                    else None
                ),
            )
            for row in rows
        ]
        inference = infer_clock(team, observations)
        statuses[inference.status] += 1
        if inference.status != "inconsistent":
            continue
        usable_rows = [
            row
            for row, observation in zip(rows, observations)
            if observation.interval_ms > 0
            and observation.time_to_next_spawn_ms is not None
            and (
                observation.spawn_timing_score is None
                or observation.spawn_timing_score > 0
            )
        ]
        inconsistent.append(
            {
                "round_id": round_id,
                "session_date": rows[0]["session_date"].isoformat(),
                "map_name": rows[0]["map_name"],
                "team": team,
                "observation_count": inference.observation_count,
                "bot_observation_count": sum(
                    _is_bot(row["victim_guid"], row["victim_name"])
                    for row in usable_rows
                ),
                "all_observations_are_bots": bool(usable_rows)
                and all(
                    _is_bot(row["victim_guid"], row["victim_name"])
                    for row in usable_rows
                ),
                "round_quality_gate_passes": _is_quality_round(rows[0]),
                "intervals_ms": inference.distinct_intervals_ms,
                "candidate_offsets_ms": inference.distinct_candidates_ms,
            }
        )
    return {
        "round_team_groups": len(by_group),
        "status_counts": dict(sorted(statuses.items())),
        "inconsistent_group_count": len(inconsistent),
        "inconsistent_bot_only_count": sum(
            item["all_observations_are_bots"] for item in inconsistent
        ),
        "inconsistent_groups": inconsistent,
    }


def _summarize(validations: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(item["status"] for item in validations)
    supported = [
        item
        for item in validations
        if item["status"] in {"validated", "validation_failed"}
    ]
    residuals = [
        residual
        for item in supported
        for residual in item["residuals_ms"]
    ]
    passing_residuals = sum(
        residual <= VALIDATION_RESIDUAL_TOLERANCE_MS
        for residual in residuals
    )
    consistent = sum(
        item["inference_status"] == "internally_consistent_unvalidated"
        for item in validations
    )
    return {
        "round_team_groups": len(validations),
        "status_counts": dict(sorted(status_counts.items())),
        "internally_consistent_groups": consistent,
        "independently_supported_groups": len(supported),
        "validated_groups": status_counts["validated"],
        "validated_share_of_supported": (
            round(status_counts["validated"] / len(supported), 6)
            if supported
            else None
        ),
        "validated_share_of_internally_consistent": (
            round(status_counts["validated"] / consistent, 6)
            if consistent
            else None
        ),
        "independent_landing_clusters": sum(item["landing_count"] for item in supported),
        "independent_spawn_callbacks": sum(
            item["spawn_observation_count"] for item in supported
        ),
        "post_revive_spawn_callbacks": sum(
            item["post_revive_spawn_count"] for item in supported
        ),
        "residual_count": len(residuals),
        "residual_median_ms": _percentile(residuals, 0.50),
        "residual_p95_ms": _percentile(residuals, 0.95),
        "residual_within_tolerance": passing_residuals,
        "residual_within_tolerance_share": (
            round(passing_residuals / len(residuals), 6)
            if residuals
            else None
        ),
        "sensitivity_without_post_revive_status_counts": dict(
            sorted(Counter(
                item["without_post_revive_status"]
                for item in validations
            ).items())
        ),
        "sensitivity_multi_spawn_landings_status_counts": dict(
            sorted(Counter(
                item["multi_spawn_landings_status"]
                for item in validations
            ).items())
        ),
    }


def analyze(
    timing_rows: list[dict[str, Any]],
    life_rows: list[dict[str, Any]],
    revive_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    filter_counts: Counter[str] = Counter()
    timing_value_exclusions: Counter[str] = Counter()
    timings_by_group: dict[tuple[int, str], list[TimingObservation]] = defaultdict(list)
    lives_by_round: dict[int, list[PlayerLife]] = defaultdict(list)
    revives_by_round: dict[int, list[ReviveObservation]] = defaultdict(list)
    round_metadata: dict[int, dict[str, Any]] = {}

    for row in timing_rows:
        if row["round_id"] is None:
            filter_counts["timing_unlinked"] += 1
            continue
        if not _is_quality_round(row):
            filter_counts["timing_rejected_round"] += 1
            continue
        if _is_bot(row["victim_guid"], row["victim_name"]):
            filter_counts["timing_bot_player"] += 1
            continue
        round_id = int(row["round_id"])
        team = str(row["victim_team"] or "")
        round_metadata[round_id] = {
            "session_date": row["session_date"],
            "map_name": row["map_name"],
        }
        observation = TimingObservation(
            team=team,
            kill_time_ms=int(row["kill_time"] or 0),
            interval_ms=int(row["enemy_spawn_interval"] or 0),
            time_to_next_spawn_ms=(
                int(row["time_to_next_spawn"])
                if row["time_to_next_spawn"] is not None
                else None
            ),
            spawn_timing_score=(
                float(row["spawn_timing_score"])
                if row["spawn_timing_score"] is not None
                else None
            ),
        )
        reason = timing_exclusion_reason(observation)
        if reason is not None:
            timing_value_exclusions[reason] += 1
        timings_by_group[(round_id, team)].append(observation)

    for row in life_rows:
        if row["round_id"] is None:
            filter_counts["life_unlinked"] += 1
            continue
        if not _is_quality_round(row):
            filter_counts["life_rejected_round"] += 1
            continue
        if _is_bot(row["player_guid"], row["player_name"]):
            filter_counts["life_bot_player"] += 1
            continue
        round_id = int(row["round_id"])
        round_metadata.setdefault(
            round_id,
            {"session_date": row["session_date"], "map_name": row["map_name"]},
        )
        lives_by_round[round_id].append(
            PlayerLife(
                row_id=int(row["id"]),
                player_guid=str(row["player_guid"]),
                team=str(row["team"] or ""),
                spawn_time_ms=int(row["spawn_time_ms"]),
                death_time_ms=(
                    int(row["death_time_ms"])
                    if row["death_time_ms"] is not None
                    else None
                ),
                death_type=row["death_type"],
            )
        )

    for row in revive_rows:
        if row["round_id"] is None:
            filter_counts["revive_unlinked"] += 1
            continue
        if not _is_quality_round(row):
            filter_counts["revive_rejected_round"] += 1
            continue
        if _is_bot(row["revived_guid"], row["revived_name"]):
            filter_counts["revive_bot_player"] += 1
            continue
        revives_by_round[int(row["round_id"])].append(
            ReviveObservation(
                player_guid=str(row["revived_guid"]),
                time_ms=int(row["revive_time"]),
            )
        )

    qualification_exclusions: Counter[str] = Counter()
    clustering_exclusions: Counter[str] = Counter()
    landings_by_round: dict[int, tuple] = {}
    for round_id, lives in lives_by_round.items():
        qualification = qualify_normal_spawns(lives, revives_by_round.get(round_id, ()))
        qualification_exclusions.update(dict(qualification.exclusions))
        clustering = cluster_spawn_landings(qualification.spawns)
        clustering_exclusions.update(dict(clustering.exclusions))
        landings_by_round[round_id] = clustering.landings

    validations: list[dict[str, Any]] = []
    inconsistent_groups: list[dict[str, Any]] = []
    for (round_id, team), observations in sorted(timings_by_group.items()):
        inference = infer_clock(team, observations)
        round_landings = landings_by_round.get(round_id, ())
        validation = validate_clock(inference, round_landings)
        without_post_revive = validate_clock(
            inference,
            (
                landing
                for landing in round_landings
                if landing.post_revive_spawn_count == 0
            ),
        )
        multi_spawn_landings = validate_clock(
            inference,
            (
                landing
                for landing in round_landings
                if landing.spawn_count >= 2
            ),
        )
        metadata = round_metadata[round_id]
        record = {
            "round_id": round_id,
            "session_date": metadata["session_date"].isoformat(),
            "map_name": metadata["map_name"],
            "team": team,
            "cohort": _cohort_name(metadata["session_date"]),
            "inference_status": inference.status,
            "without_post_revive_status": without_post_revive.status,
            "multi_spawn_landings_status": multi_spawn_landings.status,
            **asdict(validation),
        }
        validations.append(record)
        if inference.status == "inconsistent":
            inconsistent_groups.append(
                {
                    "round_id": round_id,
                    "session_date": metadata["session_date"].isoformat(),
                    "map_name": metadata["map_name"],
                    "team": team,
                    "observation_count": inference.observation_count,
                    "intervals_ms": inference.distinct_intervals_ms,
                    "candidate_offsets_ms": inference.distinct_candidates_ms,
                }
            )

    discovery = [item for item in validations if item["cohort"] == "discovery"]
    confirmation = [item for item in validations if item["cohort"] == "confirmation"]
    return {
        "protocol": {
            "version": CLOCK_PROTOCOL_VERSION,
            "confirmation_start_date": CONFIRMATION_START_DATE.isoformat(),
            "min_internal_observations": MIN_INTERNAL_OBSERVATIONS,
            "landing_cluster_jitter_ms": LANDING_CLUSTER_JITTER_MS,
            "min_validation_landings": MIN_VALIDATION_LANDINGS,
            "validation_residual_tolerance_ms": VALIDATION_RESIDUAL_TOLERANCE_MS,
            "min_validation_pass_ratio": MIN_VALIDATION_PASS_RATIO,
            "selection_rule": "exact unanimity; never average, quantize, or select a mode",
        },
        "raw_rows": {
            "timing": len(timing_rows),
            "player_life": len(life_rows),
            "revive": len(revive_rows),
        },
        "filter_counts": dict(sorted(filter_counts.items())),
        "timing_value_exclusions": dict(sorted(timing_value_exclusions.items())),
        "spawn_qualification_exclusions": dict(sorted(qualification_exclusions.items())),
        "spawn_clustering_exclusions": dict(sorted(clustering_exclusions.items())),
        "raw_internal_consistency": _raw_internal_consistency(timing_rows),
        "all": _summarize(validations),
        "discovery": _summarize(discovery),
        "confirmation": _summarize(confirmation),
        "inconsistent_groups": inconsistent_groups,
        "groups": validations,
    }


def main() -> int:
    args = _parse_args()
    connection = _connect()
    try:
        timing_rows = _fetch_all(connection, TIMING_SQL)
        life_rows = _fetch_all(connection, LIFE_SQL)
        revive_rows = _fetch_all(connection, REVIVE_SQL)
        result = analyze(timing_rows, life_rows, revive_rows)
        result["evidence"] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "transaction": "REPEATABLE READ, READ ONLY",
            "input_manifest_sha256": _manifest_hash(timing_rows, life_rows, revive_rows),
            "queries": {
                "timing": "TIMING_SQL",
                "player_life": "LIFE_SQL",
                "revive": "REVIVE_SQL",
            },
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({  # noqa: T201 - CLI evidence summary
            "output": str(args.output),
            "manifest": result["evidence"]["input_manifest_sha256"],
            "all": result["all"],
            "confirmation": result["confirmation"],
        }, indent=2, sort_keys=True))
        connection.rollback()
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
