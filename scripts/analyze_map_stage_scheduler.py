#!/usr/bin/env python3
"""Run deterministic W5b S5 scheduler measurement over installed ET assets."""

from __future__ import annotations

import argparse
import json
import resource
import time
from pathlib import Path

from website.backend.map_geometry.pk3_index import Pk3GeometryIndex
from website.backend.map_geometry.stage_measurement import (
    MeasurementCheckpoint,
    asset_manifest_sha256,
    checkpoint_metadata,
    content_hash,
    git_provenance,
    iter_cross_frontiers,
    measure_seed,
    occurrence_payload,
    prepare_scout_reuse,
    summarize_occurrences,
)

PINNED_ET_SOURCE_COMMIT = "732518efb1c479dcd29b13361f30a2e92df1cf2a"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--etmain-dir", type=Path, default=Path("/home/samba/share/etmain"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--work-limit", type=int, required=True)
    parser.add_argument("--max-paths", type=int, default=16)
    parser.add_argument("--map", dest="maps", action="append", default=[])
    parser.add_argument(
        "--reuse-from",
        type=Path,
        help="Prior lower-budget scout JSON; only its non-exhausted seed results are reused",
    )
    parser.add_argument("--allow-dirty", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    started = time.perf_counter()
    repo_root = Path(__file__).resolve().parents[1]
    git_head, clean_tree, worktree_state_sha256 = git_provenance(repo_root)
    if not clean_tree and not args.allow_dirty:
        raise SystemExit("refusing S5 evidence run from a dirty worktree; pass --allow-dirty only for scouting")

    geometry_index = Pk3GeometryIndex.scan(args.etmain_dir)
    map_names = tuple(sorted(args.maps or geometry_index.map_names))
    manifest = asset_manifest_sha256(geometry_index, map_names)
    metadata = checkpoint_metadata(
        git_head=git_head,
        clean_tree=clean_tree,
        worktree_state_sha256=worktree_state_sha256,
        asset_manifest=manifest,
        map_names=map_names,
        et_source_commit=PINNED_ET_SOURCE_COMMIT,
        work_limit=args.work_limit,
        max_paths=args.max_paths,
    )

    records: list[dict[str, object]] = []
    scout_reuse: dict[str, object] | None = None
    reusable: dict[str, dict[str, object]] = {}
    if args.reuse_from is not None:
        prior = json.loads(args.reuse_from.read_text(encoding="utf-8"))
        reusable, scout_reuse = prepare_scout_reuse(prior, metadata)
    checkpoint_identity = {**metadata, "scout_reuse": scout_reuse}
    with MeasurementCheckpoint(args.checkpoint, checkpoint_identity) as checkpoint:
        for seed_id, result in reusable.items():
            if checkpoint.seed_result(seed_id) is None:
                checkpoint.put_seed_result(seed_id, result)
        for occurrence in iter_cross_frontiers(
            geometry_index,
            map_names,
            asset_manifest=manifest,
            max_paths=args.max_paths,
        ):
            cached_occurrence = checkpoint.occurrence(occurrence.occurrence_id)
            if cached_occurrence is not None:
                records.append(cached_occurrence)
                continue
            relevance = occurrence.path.frontier_relevance
            if relevance is None:
                raise RuntimeError("S5 cross frontier lost relevance")
            skip = (
                not relevance.domains
                and not relevance.unknown_domain_relevance
                and not relevance.mutates_accumulator_state
            )
            seed_result = None
            if not skip and occurrence.adaptation.ready:
                seed_result = checkpoint.seed_result(occurrence.seed_id)
                if seed_result is None:
                    seed_result = measure_seed(occurrence, work_limit=args.work_limit)
                    checkpoint.put_seed_result(occurrence.seed_id, seed_result)
            record = occurrence_payload(occurrence, seed_result=seed_result)
            checkpoint.put_occurrence(occurrence.occurrence_id, record)
            records.append(record)

    records.sort(key=lambda record: str(record["occurrence_id"]))
    semantic = {
        **checkpoint_identity,
        "summary": summarize_occurrences(records),
        "occurrences": records,
    }
    if semantic["summary"]["measured_cross_frontiers"] != 452:
        raise RuntimeError("S5 installed-corpus denominator drifted from 452")
    publication = {
        "semantic": semantic,
        "semantic_sha256": content_hash(semantic),
        "runtime": {
            "elapsed_seconds": round(time.perf_counter() - started, 6),
            "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(publication, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(semantic["summary"], indent=2, sort_keys=True))
    print(f"semantic_sha256={publication['semantic_sha256']}")


if __name__ == "__main__":
    main()
