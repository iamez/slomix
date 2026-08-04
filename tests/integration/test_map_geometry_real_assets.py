"""Read-only W1/W2 acceptance checks against the developer's real ET assets."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from website.backend.map_geometry import (
    BspPointTracer,
    MapAssetKind,
    ObjectiveGeometrySource,
    Pk3GeometryIndex,
    PlayerStance,
    SurfaceType,
    TraceReason,
    TraceStatus,
    compile_bsp_patches,
    extract_entity_catalog,
)

ETMAIN = Path(os.environ.get("SLOMIX_ETMAIN_DIR", "/home/samba/share/etmain"))
RUN_REAL_ASSET_TESTS = os.environ.get("SLOMIX_RUN_REAL_ASSET_TESTS") == "1"

PLAYED_MAPS = {
    "adlernest",
    "braundorf_b4",
    "bremen_b3",
    "decay_sw",
    "erdenberg_t2",
    "et_brewdog",
    "etl_adlernest",
    "etl_frostbite",
    "etl_ice",
    "etl_sp_delivery",
    "et_beach",
    "etl_supply",
    "mp_sillyctf",
    "radar",
    "sp_delivery_te",
    "supply",
    "sw_goldrush_te",
    "sw_oasis_b3",
    "te_escape2",
}
MISSING_GEOMETRY = {
    "etl_frostbite",
    "et_beach",
    "etl_supply",
    "mp_sillyctf",
    "radar",
    "sp_delivery_te",
}

pytestmark = [
    pytest.mark.skipif(
        not RUN_REAL_ASSET_TESTS,
        reason="real ET map asset tests require SLOMIX_RUN_REAL_ASSET_TESTS=1",
    ),
    pytest.mark.skipif(not ETMAIN.is_dir(), reason="configured ET map asset directory is not installed"),
]


@pytest.fixture(scope="module")
def geometry_index() -> Pk3GeometryIndex:
    return Pk3GeometryIndex.scan(ETMAIN)


def test_every_observed_played_map_has_geometry_or_an_explicit_missing_result(geometry_index):
    manifest = geometry_index.manifest(PLAYED_MAPS)

    assert set(manifest["maps"]) == PLAYED_MAPS
    assert set(manifest["summary"]["missing_maps"]) == MISSING_GEOMETRY
    assert manifest["summary"]["with_geometry"] == 13
    assert manifest["summary"]["without_geometry"] == 6
    for kind in MapAssetKind:
        counts = manifest["summary"]["asset_status_counts"][kind.value]
        assert counts == {"resolved": 13, "missing": 6, "ambiguous": 0}


def test_te_escape2_duplicate_consumed_assets_are_byte_identical(geometry_index):
    for kind in MapAssetKind:
        providers = geometry_index.providers_for_asset("te_escape2", kind)
        assert [provider.pk3_path.name for provider in providers] == [
            "te_escape2_fixed.pk3",
            "te_escape2_fixed2.pk3",
            "te_escape2_fixed3.pk3",
        ]
        assert len({provider.sha256 for provider in providers}) == 1


def test_every_indexed_bsp_map_has_unambiguous_stage_inputs(geometry_index):
    assert len(geometry_index.map_names) == 20
    assert len(geometry_index.asset_map_names) == 22
    for map_name in geometry_index.map_names:
        assert geometry_index.resolve_asset(map_name, "script").status == "resolved", map_name
        assert geometry_index.resolve_asset(map_name, "objdata").status == "resolved", map_name


def test_all_indexed_map_bsps_strictly_parse_as_populated_ibsp_v47(geometry_index):
    assert len(geometry_index.map_names) == 20
    for map_name in geometry_index.map_names:
        bsp = geometry_index.load_bsp(map_name)
        assert bsp.magic == b"IBSP", map_name
        assert bsp.version == 47, map_name
        assert bsp.entities, map_name
        assert bsp.shaders, map_name
        assert bsp.planes, map_name
        assert bsp.nodes, map_name
        assert bsp.leafs, map_name
        assert bsp.leaf_surfaces, map_name
        assert bsp.leaf_brushes, map_name
        assert bsp.models, map_name
        assert bsp.brushes, map_name
        assert bsp.brush_sides, map_name
        assert bsp.draw_vertices, map_name
        assert bsp.draw_indexes, map_name
        assert bsp.surfaces, map_name


def test_w3_extracts_measured_objective_volumes_and_dynamic_inputs_for_every_bsp(
    geometry_index,
):
    totals = {
        "spawn_points": 0,
        "objective_volumes": 0,
        "objective_markers": 0,
        "collision_entities": 0,
    }
    for map_name in geometry_index.map_names:
        catalog = extract_entity_catalog(geometry_index.load_bsp(map_name), map_name)
        assert catalog.spawn_points, map_name
        assert catalog.objective_volumes, map_name
        assert catalog.objective_markers, map_name
        for volume in catalog.objective_volumes:
            assert volume.source is ObjectiveGeometrySource.MEASURED_BSP_VOLUME
            assert volume.brushes
            assert volume.contains_point(
                tuple(
                    (
                        volume.model.origin_translated_bounds.mins[index]
                        + volume.model.origin_translated_bounds.maxs[index]
                    )
                    / 2
                    for index in range(3)
                )
            ), (map_name, volume.entity_index)
        assert all(entity.runtime_state == "unresolved" for entity in catalog.collision_entities)
        totals["spawn_points"] += len(catalog.spawn_points)
        totals["objective_volumes"] += len(catalog.objective_volumes)
        totals["objective_markers"] += len(catalog.objective_markers)
        totals["collision_entities"] += len(catalog.collision_entities)

    assert totals == {
        "spawn_points": 2376,
        "objective_volumes": 158,
        "objective_markers": 96,
        "collision_entities": 1058,
    }


@pytest.mark.timeout(120)
def test_w4a2_compiles_every_real_patch_without_fail_open_gaps(geometry_index):
    totals = {
        "patches": 0,
        "facets": 0,
        "failures": 0,
        "wrapped": 0,
        "solid_wrapped": 0,
        "solid_nonsolid": 0,
        "solid_empty": 0,
    }
    for map_name in geometry_index.map_names:
        bsp = geometry_index.load_bsp(map_name)
        collisions = compile_bsp_patches(bsp)
        totals["patches"] += len(collisions)
        totals["facets"] += sum(len(collision.facets) for collision in collisions)
        totals["failures"] += sum(collision.error is not None for collision in collisions)
        totals["wrapped"] += sum(collision.wrap_width or collision.wrap_height for collision in collisions)
        totals["solid_wrapped"] += sum(
            (collision.wrap_width or collision.wrap_height) and bool(collision.content_flags & 1)
            for collision in collisions
        )
        totals["solid_nonsolid"] += sum(
            bool(bsp.shaders[surface.shader_index].surface_flags & 0x00004000)
            and bool(bsp.shaders[surface.shader_index].content_flags & 0x00000001)
            for surface in bsp.surfaces
            if surface.surface_type is SurfaceType.PATCH
        )
        totals["solid_empty"] += sum(
            bool(collision.content_flags & 1) and not collision.facets for collision in collisions
        )

    assert totals == {
        "patches": 4794,
        "facets": 22048,
        "failures": 0,
        "wrapped": 2718,
        "solid_wrapped": 2539,
        "solid_nonsolid": 0,
        "solid_empty": 0,
    }


@pytest.mark.timeout(120)
def test_w4a_real_spawn_segments_never_clear_with_unverified_runtime_collision(geometry_index):
    statuses = set()
    for map_name in geometry_index.map_names:
        bsp = geometry_index.load_bsp(map_name)
        catalog = extract_entity_catalog(bsp, map_name)
        axis_spawn = next(point for point in catalog.spawn_points if point.team == "AXIS")
        allies_spawn = next(point for point in catalog.spawn_points if point.team == "ALLIES")
        tracer = BspPointTracer(bsp, collision_entities=catalog.collision_entities)

        availability = tracer.trace_line_of_sight_availability(
            axis_spawn.origin,
            PlayerStance.STANDING,
            allies_spawn.origin,
            PlayerStance.STANDING,
        )

        statuses.add(availability.status)
        assert availability.status is not TraceStatus.CLEAR, map_name
        assert availability.interpretation == "line_of_sight_availability"
        assert availability.validation_status == "unvalidated_until_w6"
        if availability.status is TraceStatus.INDETERMINATE:
            assert any(
                TraceReason.RUNTIME_ENTITY_COMPLETENESS_UNVERIFIED in endpoint.result.uncertainty_reasons
                for endpoint in availability.endpoints
            ), map_name

    assert statuses <= {TraceStatus.BLOCKED, TraceStatus.INDETERMINATE}
