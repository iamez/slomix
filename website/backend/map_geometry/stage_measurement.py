"""Deterministic, resumable W5b S5 installed-corpus measurement."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from website.backend.map_geometry.entities import extract_entity_catalog
from website.backend.map_geometry.pk3_index import Pk3GeometryIndex
from website.backend.map_geometry.stage import load_static_stage
from website.backend.map_geometry.stage_possibilities import (
    OrderedEventProgram,
    OrderedStageProgramIndex,
    SymbolicAccumulatorState,
    SymbolicEventPath,
    build_ordered_stage_program_index,
    walk_symbolic_stage_program,
)
from website.backend.map_geometry.stage_scheduler import (
    SymbolicFrontierScheduleAdaptation,
    SymbolicScheduleDecisionKind,
    SymbolicScheduleSearchMetrics,
    adapt_symbolic_temporal_frontier,
    search_symbolic_schedule,
)
from website.backend.map_geometry.stage_semantics import (
    build_indexed_entity_identity_index,
    link_w3_entity_catalog,
)

MEASUREMENT_PROTOCOL = "w5b-s5-installed-corpus-v2"
CROSS_TEMPORAL_REASON = "cross_entity_temporal_interleaving_not_modeled"
ORIGINAL_CROSS_FRONTIERS = 301
ORIGINAL_RELEVANT_CROSS_FRONTIERS = 244
POST_S0A_CROSS_FRONTIERS = 452
FULL_CORPUS_SCOPE = "full_installed_corpus"
FILTERED_CORPUS_SCOPE = "filtered"


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def content_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("ascii")).hexdigest()


def _semantic_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        if value.is_absolute():
            raise ValueError("absolute paths cannot enter the S5 semantic identity")
        return value.as_posix()
    if is_dataclass(value):
        return {
            field.name: _semantic_value(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        return {
            str(key): _semantic_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_semantic_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        converted = [_semantic_value(item) for item in value]
        return sorted(converted, key=canonical_json)
    raise TypeError(f"unsupported S5 semantic value: {type(value).__name__}")


def asset_manifest_sha256(index: Pk3GeometryIndex, map_names: tuple[str, ...]) -> str:
    manifest = index.manifest(map_names)
    return content_hash(manifest["maps"])


def validate_generated_artifact_paths(repo_root: Path, paths: tuple[Path, ...]) -> None:
    """Allow generated files only outside Git or under fully ignored paths."""

    root = repo_root.resolve()
    git_dir_raw = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    git_dir = (
        (root / git_dir_raw).resolve()
        if not Path(git_dir_raw).is_absolute()
        else Path(git_dir_raw).resolve()
    )
    for supplied in paths:
        candidate = supplied.resolve()
        try:
            candidate.relative_to(git_dir)
        except ValueError:
            pass
        else:
            raise ValueError(f"generated S5 artifact must not be inside Git metadata: {supplied}")
        try:
            relative = candidate.relative_to(root)
        except ValueError:
            continue
        relative_text = relative.as_posix()
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", relative_text],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", "--", relative_text],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
        if tracked or not ignored:
            raise ValueError(
                "generated S5 artifacts inside the repository must be untracked and Git-ignored: "
                f"{supplied}"
            )


def git_provenance(repo_root: Path) -> tuple[str, bool, str | None]:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain", "-z"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    ).stdout
    if not status:
        return head, True, None

    digest = hashlib.sha256()
    digest.update(
        subprocess.run(
            ["git", "diff", "--binary", "--no-ext-diff", "HEAD", "--", "."],
            cwd=repo_root,
            check=True,
            capture_output=True,
        ).stdout
    )
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")
    for encoded_path in sorted(path for path in untracked if path):
        relative_path = encoded_path.decode("utf-8", errors="surrogateescape")
        path = repo_root / relative_path
        payload = (
            b"symlink:\0" + str(path.readlink()).encode("utf-8", errors="surrogateescape")
            if path.is_symlink()
            else path.read_bytes()
        )
        digest.update(len(encoded_path).to_bytes(8, "big"))
        digest.update(encoded_path)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return head, False, digest.hexdigest()


def checkpoint_metadata(
    *,
    git_head: str,
    clean_tree: bool,
    worktree_state_sha256: str | None,
    asset_manifest: str,
    map_names: tuple[str, ...],
    measurement_scope: str,
    et_source_commit: str,
    work_limit: int,
    max_paths: int,
) -> dict[str, object]:
    if work_limit < 1 or max_paths < 1:
        raise ValueError("S5 work and path limits must be positive")
    if measurement_scope not in {FULL_CORPUS_SCOPE, FILTERED_CORPUS_SCOPE}:
        raise ValueError("S5 measurement scope is invalid")
    return {
        "protocol": MEASUREMENT_PROTOCOL,
        "git_head": git_head,
        "clean_tree": clean_tree,
        "worktree_state_sha256": worktree_state_sha256,
        "asset_manifest_sha256": asset_manifest,
        "map_names": list(map_names),
        "measurement_scope": measurement_scope,
        "et_source_commit": et_source_commit,
        "work_limit": work_limit,
        "max_paths": max_paths,
    }


def reusable_seed_results(
    publication: Mapping[str, object],
    current_metadata: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    semantic = publication.get("semantic")
    if not isinstance(semantic, dict):
        raise ValueError("S5 reuse input has no semantic payload")
    comparable_keys = {
        "protocol",
        "git_head",
        "clean_tree",
        "worktree_state_sha256",
        "asset_manifest_sha256",
        "map_names",
        "measurement_scope",
        "et_source_commit",
        "max_paths",
    }
    if any(semantic.get(key) != current_metadata.get(key) for key in comparable_keys):
        raise ValueError("S5 reuse input does not match this exact corpus and code identity")
    prior_limit = semantic.get("work_limit")
    current_limit = current_metadata.get("work_limit")
    if not isinstance(prior_limit, int) or not isinstance(current_limit, int):
        raise ValueError("S5 reuse input is missing a numeric work limit")
    if prior_limit >= current_limit:
        raise ValueError("S5 scout reuse requires a strictly higher current work limit")
    occurrences = semantic.get("occurrences")
    if not isinstance(occurrences, list):
        raise ValueError("S5 reuse input has no occurrence records")
    reusable: dict[str, dict[str, object]] = {}
    for occurrence in occurrences:
        if not isinstance(occurrence, dict):
            raise ValueError("S5 reuse occurrence is malformed")
        seed_id = occurrence.get("seed_id")
        result = occurrence.get("scheduler_result")
        if not isinstance(seed_id, str) or not isinstance(result, dict):
            continue
        if result.get("outcome") == "budget_exhausted":
            continue
        previous = reusable.setdefault(seed_id, result)
        if previous != result:
            raise ValueError("S5 reuse input has conflicting results for one scheduler seed")
    return reusable


def prepare_scout_reuse(
    publication: Mapping[str, object],
    current_metadata: Mapping[str, object],
) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    """Validate a scout publication and describe its exact reusable evidence."""
    semantic = publication.get("semantic")
    declared_hash = publication.get("semantic_sha256")
    if not isinstance(semantic, dict) or not isinstance(declared_hash, str):
        raise ValueError("S5 reuse input has no hashed semantic payload")
    if content_hash(semantic) != declared_hash:
        raise ValueError("S5 reuse input semantic hash does not match its payload")
    reusable = reusable_seed_results(publication, current_metadata)
    return reusable, {
        "prior_work_limit": semantic["work_limit"],
        "prior_semantic_sha256": declared_hash,
        "reused_seed_count": len(reusable),
    }


class MeasurementCheckpoint:
    """SQLite checkpoint that refuses cross-protocol or cross-input resume."""

    def __init__(self, path: Path, metadata: Mapping[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path)
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS metadata (id INTEGER PRIMARY KEY CHECK (id = 1), payload TEXT NOT NULL)"
        )
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS seed_results (seed_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
        )
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS occurrences (occurrence_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
        )
        encoded = canonical_json(dict(metadata))
        row = self._connection.execute("SELECT payload FROM metadata WHERE id = 1").fetchone()
        if row is None:
            with self._connection:
                self._connection.execute(
                    "INSERT INTO metadata (id, payload) VALUES (1, ?)",
                    (encoded,),
                )
        elif row[0] != encoded:
            self._connection.close()
            raise ValueError("S5 checkpoint metadata does not match this exact measurement run")

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> MeasurementCheckpoint:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def seed_result(self, seed_id: str) -> dict[str, object] | None:
        row = self._connection.execute(
            "SELECT payload FROM seed_results WHERE seed_id = ?",
            (seed_id,),
        ).fetchone()
        return None if row is None else json.loads(row[0])

    def put_seed_result(self, seed_id: str, payload: Mapping[str, object]) -> None:
        with self._connection:
            self._connection.execute(
                "INSERT OR REPLACE INTO seed_results (seed_id, payload) VALUES (?, ?)",
                (seed_id, canonical_json(dict(payload))),
            )

    def occurrence(self, occurrence_id: str) -> dict[str, object] | None:
        row = self._connection.execute(
            "SELECT payload FROM occurrences WHERE occurrence_id = ?",
            (occurrence_id,),
        ).fetchone()
        return None if row is None else json.loads(row[0])

    def put_occurrence(self, occurrence_id: str, payload: Mapping[str, object]) -> None:
        with self._connection:
            self._connection.execute(
                "INSERT OR REPLACE INTO occurrences (occurrence_id, payload) VALUES (?, ?)",
                (occurrence_id, canonical_json(dict(payload))),
            )


@dataclass(frozen=True, slots=True)
class CrossFrontierOccurrence:
    occurrence_id: str
    seed_id: str
    map_name: str
    root_id: str
    root_program: OrderedEventProgram
    source_entity_index: int
    path: SymbolicEventPath
    index: OrderedStageProgramIndex
    adaptation: SymbolicFrontierScheduleAdaptation


def _program_semantics(program: OrderedEventProgram) -> dict[str, object]:
    node = program.node
    return {
        "entity_name": node.entity_name,
        "event_name": node.event_name,
        "event_parameters": list(node.event_parameters),
        "serialized_event_parameters": node.serialized_event_parameters,
        "line": node.line,
    }


def _path_semantics(
    index: OrderedStageProgramIndex,
    path: SymbolicEventPath,
) -> dict[str, object]:
    snapshot = path.temporal_frontier_snapshot
    node_ids = {
        dispatch.source_node_id for dispatch in path.nested_dispatches
    } | {
        dispatch.target_node_id
        for dispatch in path.nested_dispatches
        if dispatch.target_node_id is not None
    }
    if snapshot is not None:
        node_ids.update(node_id for _, node_id in snapshot.active_frames)
        node_ids.update({snapshot.caller_node_id, snapshot.target_node_id})
    node_semantics = {
        node_id: _program_semantics(index.program(node_id))
        for node_id in sorted(node_ids)
    }
    return {
        "state": _semantic_value(path.state),
        "effects": _semantic_value(path.effects),
        "effect_entity_indices": list(path.effect_entity_indices),
        "async_movement_starts": _semantic_value(path.async_movement_starts),
        "async_movement_stops": _semantic_value(path.async_movement_stops),
        "tag_parent_mutation_entity_indices": list(path.tag_parent_mutation_entity_indices),
        "guard_decisions": _semantic_value(path.guard_decisions),
        "temporal_boundary_lines": list(path.temporal_boundary_lines),
        "temporal_boundary_entity_indices": list(path.temporal_boundary_entity_indices),
        "temporal_boundary_states": _semantic_value(path.temporal_boundary_states),
        "nested_dispatches": _semantic_value(path.nested_dispatches),
        "death_dispatches": _semantic_value(path.death_dispatches),
        "runtime_event_dispatches": _semantic_value(path.runtime_event_dispatches),
        "caller_replacement_lines": list(path.caller_replacement_lines),
        "caller_replacement_entity_indices": list(path.caller_replacement_entity_indices),
        "blocker_reason": path.blocker_reason,
        "blocker_line": path.blocker_line,
        "blocker_entity_index": path.blocker_entity_index,
        "frontier_relevance": _semantic_value(path.frontier_relevance),
        "temporal_frontier_snapshot": _semantic_value(snapshot),
        "node_semantics": node_semantics,
    }


def _scheduler_seed_semantics(
    index: OrderedStageProgramIndex,
    *,
    map_name: str,
    asset_manifest: str,
    adaptation: SymbolicFrontierScheduleAdaptation,
) -> dict[str, object]:
    state = adaptation.initial_state
    if state is None:
        raise ValueError("adaptation-blocked frontier has no scheduler seed semantics")
    node_ids = {
        frame.cursor.node_id for frame in state.runnable
    } | {
        continuation.frame.cursor.node_id for continuation in state.suspended
    } | {
        lifecycle.source_cursor.node_id for lifecycle in state.async_lifecycles
    } | {
        effect.source_cursor.node_id for effect in state.effects
    } | {
        owner.event_node_id for owner in state.event_owners
    }
    return {
        "map_name": map_name,
        "asset_manifest_sha256": asset_manifest,
        "accumulator_state": _semantic_value(state.accumulator_state),
        "runnable": _semantic_value(state.runnable),
        "suspended": _semantic_value(state.suspended),
        "async_lifecycles": _semantic_value(state.async_lifecycles),
        "event_owners": _semantic_value(state.event_owners),
        "tag_parent_states": _semantic_value(state.tag_parent_states),
        "effects": _semantic_value(state.effects),
        "provenance": list(state.provenance),
        "ordering_decisions": list(state.ordering_decisions),
        "unknown_reasons": list(state.unknown_reasons),
        "node_semantics": {
            node_id: _program_semantics(index.program(node_id))
            for node_id in sorted(node_ids)
        },
    }


def iter_cross_frontiers(
    geometry_index: Pk3GeometryIndex,
    map_names: tuple[str, ...],
    *,
    asset_manifest: str,
    max_paths: int,
) -> Iterator[CrossFrontierOccurrence]:
    duplicate_ordinals: Counter[str] = Counter()
    for map_name in map_names:
        bsp = geometry_index.load_bsp(map_name)
        linked = link_w3_entity_catalog(
            build_indexed_entity_identity_index(geometry_index, map_name, bsp=bsp),
            extract_entity_catalog(bsp, map_name),
        )
        stage = load_static_stage(geometry_index, map_name)
        if stage.model is None:
            raise RuntimeError(f"S5 map {map_name!r} has no resolved stage model")
        index = build_ordered_stage_program_index(stage.model, linked)
        for program in index.programs:
            root_semantics = _program_semantics(program)
            for source_entity_index in program.source.lookup.selected_entity_indices:
                root_id = content_hash(
                    {
                        "asset_manifest_sha256": asset_manifest,
                        "map_name": map_name,
                        "program": root_semantics,
                        "source_entity_index": source_entity_index,
                        "entry_accumulator_policy": "unknown",
                        "entry_tag_parent_policy": "unknown",
                    }
                )
                paths = walk_symbolic_stage_program(
                    index,
                    program,
                    source_entity_index=source_entity_index,
                    initial_state=SymbolicAccumulatorState.unknown(),
                    max_paths=max_paths,
                )
                for path in paths:
                    if path.blocker_reason != CROSS_TEMPORAL_REASON:
                        continue
                    path_semantics = _path_semantics(index, path)
                    base_id = content_hash({"root_id": root_id, "path": path_semantics})
                    ordinal = duplicate_ordinals[base_id]
                    duplicate_ordinals[base_id] += 1
                    occurrence_id = f"{base_id}:{ordinal}"
                    adaptation = adapt_symbolic_temporal_frontier(index, path)
                    if adaptation.ready:
                        seed_id = content_hash(
                            _scheduler_seed_semantics(
                                index,
                                map_name=map_name,
                                asset_manifest=asset_manifest,
                                adaptation=adaptation,
                            )
                        )
                    else:
                        seed_id = content_hash(
                            {
                                "root_id": root_id,
                                "adaptation_blocker": adaptation.blocker_reason,
                                "path": path_semantics,
                            }
                        )
                    yield CrossFrontierOccurrence(
                        occurrence_id,
                        seed_id,
                        map_name,
                        root_id,
                        program,
                        source_entity_index,
                        path,
                        index,
                        adaptation,
                    )


def _metrics_payload(metrics: SymbolicScheduleSearchMetrics) -> dict[str, int]:
    return {
        "states_created": metrics.states_created,
        "transitions_evaluated": metrics.transitions_evaluated,
        "maximum_runnable_tasks": metrics.maximum_runnable_tasks,
        "maximum_suspended_tasks": metrics.maximum_suspended_tasks,
        "maximum_frame_depth": metrics.maximum_frame_depth,
        "deduplicated_states": metrics.deduplicated_states,
        "cycle_frontiers": metrics.cycle_frontiers,
        "budget_frontiers": metrics.budget_frontiers,
        "independence_reductions": metrics.independence_reductions,
    }


def measure_seed(occurrence: CrossFrontierOccurrence, *, work_limit: int) -> dict[str, object]:
    initial_state = occurrence.adaptation.initial_state
    if initial_state is None:
        raise ValueError("cannot schedule an adaptation-blocked S5 frontier")
    result = search_symbolic_schedule(
        occurrence.index,
        initial_state,
        work_limit=work_limit,
    )
    decision_kinds = {decision.kind for decision in result.decisions}
    reasons: Counter[str] = Counter()
    for decision in result.decisions:
        decision_reasons = set(decision.state.unknown_reasons)
        if decision.reason is not None:
            decision_reasons.add(decision.reason)
        reasons.update(decision_reasons)
    if result.exhaustion is not None:
        outcome = "budget_exhausted"
    elif decision_kinds == {SymbolicScheduleDecisionKind.COMPLETE} and not reasons:
        outcome = "resolved"
    else:
        outcome = "still_blocked"
    return {
        "outcome": outcome,
        "exhaustion": None if result.exhaustion is None else result.exhaustion.value,
        "decision_kinds": sorted(kind.value for kind in decision_kinds),
        "reasons": dict(sorted(reasons.items())),
        "metrics": _metrics_payload(result.metrics),
    }


def occurrence_payload(
    occurrence: CrossFrontierOccurrence,
    *,
    seed_result: Mapping[str, object] | None,
) -> dict[str, object]:
    relevance = occurrence.path.frontier_relevance
    if relevance is None:
        raise RuntimeError("cross temporal S5 frontier lost its relevance classification")
    skip = (
        not relevance.domains
        and not relevance.unknown_domain_relevance
        and not relevance.mutates_accumulator_state
    )
    if skip:
        outcome = "skipped_empty_complete"
        adaptation_reason = None
        result = None
    elif not occurrence.adaptation.ready:
        outcome = "adaptation_blocked"
        adaptation_reason = occurrence.adaptation.blocker_reason
        result = None
    else:
        if seed_result is None:
            raise ValueError("ready S5 occurrence requires its scheduler seed result")
        outcome = str(seed_result["outcome"])
        adaptation_reason = None
        result = dict(seed_result)
    return {
        "occurrence_id": occurrence.occurrence_id,
        "seed_id": occurrence.seed_id,
        "map_name": occurrence.map_name,
        "root_id": occurrence.root_id,
        "root_program": _program_semantics(occurrence.root_program),
        "source_entity_index": occurrence.source_entity_index,
        "blocker_line": occurrence.path.blocker_line,
        "blocker_entity_index": occurrence.path.blocker_entity_index,
        "domains": [domain.value for domain in relevance.domains],
        "unknown_domain_relevance": relevance.unknown_domain_relevance,
        "unknown_reasons": list(relevance.unknown_reasons),
        "mutates_accumulator_state": relevance.mutates_accumulator_state,
        "outcome": outcome,
        "adaptation_reason": adaptation_reason,
        "scheduler_result": result,
    }


def summarize_occurrences(records: list[dict[str, object]]) -> dict[str, object]:
    outcome_counts = Counter(str(record["outcome"]) for record in records)
    map_counts = Counter(str(record["map_name"]) for record in records)
    domain_counts = Counter(
        tuple(record["domains"] if isinstance(record["domains"], list) else ())
        for record in records
    )
    adaptation_reasons = Counter(
        str(record["adaptation_reason"])
        for record in records
        if record["adaptation_reason"] is not None
    )
    remaining_reasons: Counter[str] = Counter()
    for record in records:
        scheduler = record["scheduler_result"]
        if not isinstance(scheduler, dict):
            continue
        for reason, count in scheduler["reasons"].items():
            remaining_reasons[str(reason)] += int(count)
    return {
        "original_cross_frontiers": ORIGINAL_CROSS_FRONTIERS,
        "original_relevant_cross_frontiers": ORIGINAL_RELEVANT_CROSS_FRONTIERS,
        "post_s0a_cross_frontiers": POST_S0A_CROSS_FRONTIERS,
        "measured_cross_frontiers": len(records),
        "unique_roots": len({record["root_id"] for record in records}),
        "unique_scheduler_seeds": len(
            {
                record["seed_id"]
                for record in records
                if record["outcome"] not in {"skipped_empty_complete", "adaptation_blocked"}
            }
        ),
        "outcomes": dict(sorted(outcome_counts.items())),
        "maps": dict(sorted(map_counts.items())),
        "domain_sets": {
            "+".join(domains) if domains else "none": count
            for domains, count in sorted(domain_counts.items())
        },
        "adaptation_reasons": dict(sorted(adaptation_reasons.items())),
        "remaining_scheduler_reasons": dict(sorted(remaining_reasons.items())),
    }


def validate_measured_denominator(measured: int, *, measurement_scope: str) -> None:
    if measured < 0:
        raise ValueError("S5 measured denominator must be non-negative")
    if measurement_scope == FULL_CORPUS_SCOPE and measured != POST_S0A_CROSS_FRONTIERS:
        raise RuntimeError(
            f"S5 installed-corpus denominator drifted from {POST_S0A_CROSS_FRONTIERS}"
        )
    if measurement_scope not in {FULL_CORPUS_SCOPE, FILTERED_CORPUS_SCOPE}:
        raise ValueError("S5 measurement scope is invalid")
