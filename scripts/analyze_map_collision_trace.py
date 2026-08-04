#!/usr/bin/env python3
"""Measure the W4a trace kernel against deterministic real-map spawn segments."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path
from time import perf_counter_ns

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from website.backend.map_geometry import (  # noqa: E402
    BspPointTracer,
    Pk3GeometryIndex,
    PlayerStance,
    RuntimeGeometryCoverage,
    SurfaceType,
    TraceStatus,
    compile_bsp_patches,
    extract_entity_catalog,
    player_eye_point,
    target_body_points,
)


def _percentile(values: list[int], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[rank] / 1_000.0


def _spawn_pairs(catalog, limit: int):
    axis = tuple(point for point in catalog.spawn_points if point.team == "AXIS")
    allies = tuple(point for point in catalog.spawn_points if point.team == "ALLIES")
    if not axis or not allies:
        return ()
    return tuple(
        (axis[index % len(axis)], allies[(index * 7) % len(allies)])
        for index in range(min(limit, max(len(axis), len(allies))))
    )


def _aggregate_status(statuses: tuple[TraceStatus, ...]) -> TraceStatus:
    if any(status is TraceStatus.CLEAR for status in statuses):
        return TraceStatus.CLEAR
    if all(status is TraceStatus.BLOCKED for status in statuses):
        return TraceStatus.BLOCKED
    return TraceStatus.INDETERMINATE


def analyze(etmain: Path, *, map_names: tuple[str, ...] | None, pairs_per_map: int) -> dict:
    index = Pk3GeometryIndex.scan(etmain)
    selected_maps = tuple(sorted(map_names or index.map_names))
    endpoint_times_ns: list[int] = []
    static_statuses: Counter[str] = Counter()
    fail_closed_statuses: Counter[str] = Counter()
    endpoint_statuses: Counter[str] = Counter()
    endpoint_reasons: Counter[str] = Counter()
    leaf_counts: list[int] = []
    brush_counts: list[int] = []
    patch_counts: list[int] = []
    patch_facet_counts: list[int] = []
    patch_compile_times_ns: list[int] = []
    inventory = Counter()
    per_map: dict[str, dict] = {}

    for map_name in selected_maps:
        bsp = index.load_bsp(map_name)
        catalog = extract_entity_catalog(bsp, map_name)
        patch_compile_started = perf_counter_ns()
        patch_collisions = compile_bsp_patches(bsp)
        patch_compile_times_ns.append(perf_counter_ns() - patch_compile_started)
        inventory.update(
            maps=1,
            brushes=len(bsp.brushes),
            empty_brushes=sum(brush.num_sides == 0 for brush in bsp.brushes),
            planes=len(bsp.planes),
            nonfinite_planes=sum(
                not all(math.isfinite(value) for value in (*plane.normal, plane.distance))
                for plane in bsp.planes
            ),
            zero_normal_planes=sum(
                sum(component * component for component in plane.normal) == 0.0
                for plane in bsp.planes
            ),
            patches=sum(surface.surface_type is SurfaceType.PATCH for surface in bsp.surfaces),
            solid_patches=sum(
                surface.surface_type is SurfaceType.PATCH
                and bool(bsp.shaders[surface.shader_index].content_flags & 1)
                for surface in bsp.surfaces
            ),
            patch_facets=sum(len(collision.facets) for collision in patch_collisions),
            solid_patch_facets=sum(
                len(collision.facets)
                for collision in patch_collisions
                if collision.content_flags & 1
            ),
            patch_compile_failures=sum(collision.error is not None for collision in patch_collisions),
            collision_entities=len(catalog.collision_entities),
        )
        static_tracer = BspPointTracer(
            bsp,
            patch_collisions=patch_collisions,
            runtime_entity_completeness=RuntimeGeometryCoverage.VERIFIED,
            runtime_entity_state=RuntimeGeometryCoverage.VERIFIED,
        )
        fail_closed_tracer = BspPointTracer(
            bsp,
            collision_entities=catalog.collision_entities,
            patch_collisions=patch_collisions,
        )
        map_static: Counter[str] = Counter()
        map_fail_closed: Counter[str] = Counter()
        map_endpoint_reasons: Counter[str] = Counter()
        pairs = _spawn_pairs(catalog, pairs_per_map)
        for observer, target in pairs:
            observer_eye = player_eye_point(observer.origin, PlayerStance.STANDING)
            results = []
            for endpoint in target_body_points(target.origin, PlayerStance.STANDING):
                started = perf_counter_ns()
                result = static_tracer.trace_segment(observer_eye, endpoint.point)
                endpoint_times_ns.append(perf_counter_ns() - started)
                results.append(result)
                endpoint_statuses[result.status.value] += 1
                endpoint_reasons[result.reason.value] += 1
                map_endpoint_reasons[result.reason.value] += 1
                leaf_counts.append(result.visited_leaf_count)
                brush_counts.append(result.tested_brush_count)
                patch_counts.append(result.tested_patch_count)
                patch_facet_counts.append(result.tested_patch_facet_count)

            static_status = _aggregate_status(tuple(result.status for result in results))
            fail_closed_status = fail_closed_tracer.trace_line_of_sight_availability(
                observer.origin,
                PlayerStance.STANDING,
                target.origin,
                PlayerStance.STANDING,
            ).status
            static_statuses[static_status.value] += 1
            fail_closed_statuses[fail_closed_status.value] += 1
            map_static[static_status.value] += 1
            map_fail_closed[fail_closed_status.value] += 1

        per_map[map_name] = {
            "sample_pairs": len(pairs),
            "static_only_statuses": dict(sorted(map_static.items())),
            "fail_closed_statuses": dict(sorted(map_fail_closed.items())),
            "static_only_endpoint_reasons": dict(sorted(map_endpoint_reasons.items())),
        }

    endpoint_count = len(endpoint_times_ns)
    return {
        "contract": {
            "sample": "deterministic_cross_team_spawn_pairs",
            "stance": "standing",
            "target_endpoints": 6,
            "availability_rule": "any_clear",
            "trace_shape": "point",
            "trace_mask": "line_of_sight_solid",
            "static_only_clear_meaning": "kernel_result_only_not_engine_validated",
            "fail_closed_context": "runtime_entity_completeness_state_and_transforms_unverified",
        },
        "inventory": dict(inventory),
        "sample_pairs": sum(item["sample_pairs"] for item in per_map.values()),
        "endpoint_traces": endpoint_count,
        "static_only_pair_statuses": dict(sorted(static_statuses.items())),
        "fail_closed_pair_statuses": dict(sorted(fail_closed_statuses.items())),
        "static_only_endpoint_statuses": dict(sorted(endpoint_statuses.items())),
        "static_only_endpoint_reasons": dict(sorted(endpoint_reasons.items())),
        "timing_microseconds_per_endpoint": {
            "p50": round(_percentile(endpoint_times_ns, 0.50), 3),
            "p95": round(_percentile(endpoint_times_ns, 0.95), 3),
            "max": round(max(endpoint_times_ns, default=0) / 1_000.0, 3),
        },
        "patch_compile_milliseconds_per_map": {
            "mean": round(sum(patch_compile_times_ns) / len(patch_compile_times_ns) / 1_000_000.0, 3)
            if patch_compile_times_ns
            else 0.0,
            "max": round(max(patch_compile_times_ns, default=0) / 1_000_000.0, 3),
        },
        "candidate_work_per_endpoint": {
            "mean_leafs": round(sum(leaf_counts) / endpoint_count, 3) if endpoint_count else 0.0,
            "max_leafs": max(leaf_counts, default=0),
            "mean_exact_brush_tests": round(sum(brush_counts) / endpoint_count, 3) if endpoint_count else 0.0,
            "max_exact_brush_tests": max(brush_counts, default=0),
            "mean_patch_aabb_tests": round(sum(patch_counts) / endpoint_count, 3) if endpoint_count else 0.0,
            "max_patch_aabb_tests": max(patch_counts, default=0),
            "mean_patch_facet_tests": round(sum(patch_facet_counts) / endpoint_count, 3)
            if endpoint_count
            else 0.0,
            "max_patch_facet_tests": max(patch_facet_counts, default=0),
        },
        "maps": per_map,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--etmain", type=Path, default=Path("/home/samba/share/etmain"))
    parser.add_argument("--map", action="append", dest="maps")
    parser.add_argument("--pairs-per-map", type=int, default=16)
    args = parser.parse_args()
    if args.pairs_per_map <= 0:
        parser.error("--pairs-per-map must be positive")
    if not args.etmain.is_dir():
        parser.error(f"ET asset directory does not exist: {args.etmain}")

    report = analyze(
        args.etmain,
        map_names=tuple(args.maps) if args.maps else None,
        pairs_per_map=args.pairs_per_map,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
