"""Synthetic W4a contracts for fail-closed BSP point traces."""

from __future__ import annotations

from dataclasses import replace

import pytest

from website.backend.map_geometry import (
    BspBrush,
    BspBrushSide,
    BspDrawVertex,
    BspFile,
    BspLeaf,
    BspModel,
    BspNode,
    BspPlane,
    BspShader,
    BspSurface,
    RuntimeGeometryCoverage,
    SurfaceType,
    extract_entity_catalog,
)
from website.backend.map_geometry.trace import (
    CONTENTS_PLAYERCLIP,
    CONTENTS_SOLID,
    LINE_OF_SIGHT_MASK,
    PLAYER_BOUNDS,
    PLAYER_MOVEMENT_MASK,
    BspPointTracer,
    PlayerStance,
    TraceReason,
    TraceStatus,
    player_eye_point,
    target_body_points,
)


def _vertex(position: tuple[float, float, float]) -> BspDrawVertex:
    return BspDrawVertex(position, (0.0, 0.0), (0.0, 0.0), (0.0, 0.0, 1.0), (255, 255, 255, 255))


def _box_planes(mins=(-1.0, -2.0, -3.0), maxs=(1.0, 2.0, 3.0)) -> tuple[BspPlane, ...]:
    return (
        BspPlane((1.0, 0.0, 0.0), maxs[0]),
        BspPlane((-1.0, 0.0, 0.0), -mins[0]),
        BspPlane((0.0, 1.0, 0.0), maxs[1]),
        BspPlane((0.0, -1.0, 0.0), -mins[1]),
        BspPlane((0.0, 0.0, 1.0), maxs[2]),
        BspPlane((0.0, 0.0, -1.0), -mins[2]),
    )


def _trace_bsp(*, brush_contents=CONTENTS_SOLID, with_patch=False) -> BspFile:
    patch_positions = (
        (-0.2, -4.0, -4.0),
        (0.0, -4.0, 0.0),
        (0.2, -4.0, 4.0),
        (-0.2, 0.0, -4.0),
        (0.0, 0.0, 0.0),
        (0.2, 0.0, 4.0),
        (-0.2, 4.0, -4.0),
        (0.0, 4.0, 0.0),
        (0.2, 4.0, 4.0),
    )
    surfaces = (
        BspSurface(
            shader_index=0,
            fog_index=-1,
            surface_type=SurfaceType.PATCH,
            first_vertex=0,
            num_vertices=9,
            first_index=0,
            num_indexes=0,
            lightmap_index=-1,
            lightmap_x=0,
            lightmap_y=0,
            lightmap_width=0,
            lightmap_height=0,
            lightmap_origin=(0.0, 0.0, 0.0),
            lightmap_vectors=((0.0, 0.0, 0.0),) * 3,
            patch_width=3,
            patch_height=3,
        ),
    ) if with_patch else ()
    leaf_surfaces = (0, 0) if with_patch else ()
    return BspFile(
        source="synthetic.bsp",
        byte_length=1,
        lumps=(),
        entity_text="",
        entities=({"classname": "worldspawn"},),
        shaders=(BspShader("textures/test/collision", 0, brush_contents),),
        planes=(BspPlane((1.0, 0.0, 0.0), 0.0), *_box_planes()),
        nodes=(BspNode(0, (-1, -2), (-100, -100, -100), (100, 100, 100)),),
        leafs=(
            BspLeaf(0, 0, (-100, -100, -100), (100, 100, 100), 0, int(with_patch), 0, 1),
            BspLeaf(0, 0, (-100, -100, -100), (100, 100, 100), int(with_patch), int(with_patch), 1, 1),
        ),
        leaf_surfaces=leaf_surfaces,
        leaf_brushes=(0, 0),
        models=(BspModel((-100.0,) * 3, (100.0,) * 3, 0, len(surfaces), 0, 1),),
        brushes=(BspBrush(0, 6, 0),),
        brush_sides=tuple(BspBrushSide(index + 1, 0) for index in range(6)),
        draw_vertices=tuple(_vertex(position) for position in patch_positions) if with_patch else (),
        draw_indexes=(),
        surfaces=surfaces,
    )


def _verified_tracer(bsp: BspFile) -> BspPointTracer:
    return BspPointTracer(
        bsp,
        runtime_entity_completeness=RuntimeGeometryCoverage.VERIFIED,
        runtime_entity_state=RuntimeGeometryCoverage.VERIFIED,
    )


def test_exact_convex_brush_blocks_and_reports_engine_clip_fraction():
    tracer = _verified_tracer(_trace_bsp())
    result = tracer.trace_segment((-5.0, 0.0, 0.0), (5.0, 0.0, 0.0))
    reverse = tracer.trace_segment((5.0, 0.0, 0.0), (-5.0, 0.0, 0.0))

    assert result.status is TraceStatus.BLOCKED
    assert result.reason is TraceReason.SOLID_BRUSH
    assert result.brush_index == 0
    assert result.brush_side_index == 1
    assert result.fraction == pytest.approx((4.0 - 0.125) / 10.0)
    assert result.visited_leaf_count == 2
    assert result.tested_brush_count == 1  # Deduplicated across leaf references.
    assert reverse.status is TraceStatus.BLOCKED
    assert reverse.fraction == result.fraction
    assert reverse.visited_leaf_count == 2


def test_slanted_convex_half_space_rejects_aabb_style_false_positive():
    bsp = _trace_bsp()
    slanted = (
        BspPlane((1.0, 1.0, 0.0), 0.0),
        BspPlane((-1.0, 0.0, 0.0), 4.0),
        BspPlane((0.0, -1.0, 0.0), 4.0),
        BspPlane((0.0, 0.0, 1.0), 4.0),
        BspPlane((0.0, 0.0, -1.0), 4.0),
    )
    bsp = replace(
        bsp,
        planes=(bsp.planes[0], *slanted),
        brush_sides=tuple(BspBrushSide(index + 1, 0) for index in range(5)),
        brushes=(BspBrush(0, 5, 0),),
    )

    result = _verified_tracer(bsp).trace_segment((2.0, 2.0, 0.0), (3.0, 3.0, 0.0))

    assert result.status is TraceStatus.CLEAR


def test_nearly_axial_plane_cannot_create_a_nonconservative_broadphase_bound():
    bsp = _trace_bsp()
    planes = (
        BspPlane((1.0, 1e-7, 0.0), 1.0),
        BspPlane((-1.0, 0.0, 0.0), 4.0),
        BspPlane((0.0, 1.0, 0.0), -9_999_999.0),
        BspPlane((0.0, -1.0, 0.0), 10_000_001.0),
        BspPlane((0.0, 0.0, 1.0), 1.0),
        BspPlane((0.0, 0.0, -1.0), 1.0),
    )
    bsp = replace(
        bsp,
        planes=(bsp.planes[0], *planes),
        brush_sides=tuple(BspBrushSide(index + 1, 0) for index in range(6)),
    )

    result = _verified_tracer(bsp).trace_segment(
        (2.0, -10_000_000.0, 0.0),
        (2.0, -10_000_000.0, 0.0),
    )

    assert result.status is TraceStatus.BLOCKED
    assert result.all_solid is True


def test_nonunit_axial_normal_scales_broadphase_clip_padding():
    bsp = _trace_bsp()
    planes = (
        BspPlane((0.5, 0.0, 0.0), 0.5),
        *bsp.planes[2:7],
    )
    bsp = replace(bsp, planes=(bsp.planes[0], *planes))

    result = _verified_tracer(bsp).trace_segment((1.3, 0.0, 0.0), (1.2, 0.0, 0.0))

    assert result.status is TraceStatus.BLOCKED
    assert result.fraction == pytest.approx(0.5)


def test_empty_brush_is_ignored_like_etl_instead_of_blocking_every_segment():
    bsp = _trace_bsp()
    bsp = replace(bsp, brushes=(replace(bsp.brushes[0], num_sides=0),))

    result = _verified_tracer(bsp).trace_segment((-5.0, 0.0, 0.0), (5.0, 0.0, 0.0))

    assert result.status is TraceStatus.CLEAR
    assert result.tested_brush_count == 1


def test_start_inside_brush_is_blocked_and_exposes_startsolid():
    result = _verified_tracer(_trace_bsp()).trace_segment((0.0, 0.0, 0.0), (5.0, 0.0, 0.0))

    assert result.status is TraceStatus.BLOCKED
    assert result.fraction == 0.0
    assert result.start_solid is True
    assert result.all_solid is False


def test_equal_zero_fraction_hits_accumulate_allsolid_across_overlapping_brushes():
    bsp = _trace_bsp()
    enclosing_planes = _box_planes((-2.0, -3.0, -4.0), (10.0, 3.0, 4.0))
    second_side = len(bsp.brush_sides)
    second_plane = len(bsp.planes)
    bsp = replace(
        bsp,
        planes=(*bsp.planes, *enclosing_planes),
        brushes=(bsp.brushes[0], BspBrush(second_side, 6, 0)),
        brush_sides=(
            *bsp.brush_sides,
            *(BspBrushSide(second_plane + index, 0) for index in range(6)),
        ),
        leaf_brushes=(0, 1, 0, 1),
        leafs=(
            replace(bsp.leafs[0], first_leaf_brush=0, num_leaf_brushes=2),
            replace(bsp.leafs[1], first_leaf_brush=2, num_leaf_brushes=2),
        ),
        models=(replace(bsp.models[0], num_brushes=2),),
    )

    result = _verified_tracer(bsp).trace_segment((0.0, 0.0, 0.0), (5.0, 0.0, 0.0))

    assert result.status is TraceStatus.BLOCKED
    assert result.start_solid is True
    assert result.all_solid is True
    assert result.brush_index == 1
    assert result.tested_brush_count == 2


def test_named_masks_distinguish_playerclip_from_line_of_sight():
    bsp = _trace_bsp(brush_contents=CONTENTS_PLAYERCLIP)
    tracer = _verified_tracer(bsp)

    line_of_sight = tracer.trace_segment((-5.0, 0.0, 0.0), (5.0, 0.0, 0.0))
    movement_contents = tracer.trace_segment(
        (-5.0, 0.0, 0.0),
        (5.0, 0.0, 0.0),
        trace_mask=PLAYER_MOVEMENT_MASK,
    )

    assert line_of_sight.status is TraceStatus.CLEAR
    assert line_of_sight.trace_mask == LINE_OF_SIGHT_MASK
    assert movement_contents.status is TraceStatus.BLOCKED
    assert movement_contents.trace_mask == PLAYER_MOVEMENT_MASK


def test_intersecting_solid_patch_is_indeterminate_until_facets_exist():
    bsp = replace(_trace_bsp(with_patch=True), brushes=(), brush_sides=(), leaf_brushes=())
    bsp = replace(
        bsp,
        leafs=tuple(replace(leaf, first_leaf_brush=0, num_leaf_brushes=0) for leaf in bsp.leafs),
        models=(replace(bsp.models[0], first_brush=0, num_brushes=0),),
    )

    result = _verified_tracer(bsp).trace_segment((-5.0, 0.0, 0.0), (5.0, 0.0, 0.0))

    assert result.status is TraceStatus.INDETERMINATE
    assert result.reason is TraceReason.SOLID_PATCH_UNCOMPILED
    assert result.uncertain_surface_indices == (0,)


def test_nonintersecting_patch_does_not_poison_an_otherwise_clear_segment():
    bsp = replace(_trace_bsp(with_patch=True), brushes=(), brush_sides=(), leaf_brushes=())
    bsp = replace(
        bsp,
        leafs=tuple(replace(leaf, first_leaf_brush=0, num_leaf_brushes=0) for leaf in bsp.leafs),
        models=(replace(bsp.models[0], first_brush=0, num_brushes=0),),
    )

    result = _verified_tracer(bsp).trace_segment((-5.0, 20.0, 0.0), (5.0, 20.0, 0.0))

    assert result.status is TraceStatus.CLEAR
    assert result.tested_patch_count == 1


def test_runtime_completeness_is_a_required_clear_gate():
    result = BspPointTracer(_trace_bsp()).trace_segment((-5.0, 20.0, 0.0), (5.0, 20.0, 0.0))

    assert result.status is TraceStatus.INDETERMINATE
    assert result.reason is TraceReason.RUNTIME_ENTITY_COMPLETENESS_UNVERIFIED
    assert result.fraction is None


def test_dynamic_inline_model_crossing_is_indeterminate_not_aabb_blocked():
    source = _trace_bsp()
    source = replace(
        source,
        entities=({"classname": "func_door", "model": "*1"},),
        models=(source.models[0], BspModel((-1.0, -2.0, -3.0), (1.0, 2.0, 3.0), 0, 0, 0, 1)),
    )
    catalog = extract_entity_catalog(source, "synthetic")
    world_without_brush = replace(
        source,
        brushes=(),
        brush_sides=(),
        leaf_brushes=(),
        leafs=tuple(replace(leaf, first_leaf_brush=0, num_leaf_brushes=0) for leaf in source.leafs),
        models=(replace(source.models[0], first_brush=0, num_brushes=0),),
    )
    tracer = BspPointTracer(
        world_without_brush,
        collision_entities=catalog.collision_entities,
        runtime_entity_completeness=RuntimeGeometryCoverage.VERIFIED,
    )

    result = tracer.trace_segment((-5.0, 0.0, 0.0), (5.0, 0.0, 0.0))

    assert result.status is TraceStatus.INDETERMINATE
    assert result.reason is TraceReason.DYNAMIC_ENTITY_STATE_UNRESOLVED
    assert result.uncertain_entity_indices == (0,)
    assert TraceReason.RUNTIME_ENTITY_STATE_UNVERIFIED in result.uncertainty_reasons


def test_verified_flags_cannot_clear_without_observed_dynamic_transforms():
    source = _trace_bsp()
    source = replace(
        source,
        entities=({"classname": "func_door", "model": "*1"},),
        models=(source.models[0], BspModel((-1.0, -2.0, -3.0), (1.0, 2.0, 3.0), 0, 0, 0, 1)),
    )
    catalog = extract_entity_catalog(source, "synthetic")
    world_without_brush = replace(
        source,
        brushes=(),
        brush_sides=(),
        leaf_brushes=(),
        leafs=tuple(replace(leaf, first_leaf_brush=0, num_leaf_brushes=0) for leaf in source.leafs),
        models=(replace(source.models[0], first_brush=0, num_brushes=0),),
    )
    tracer = BspPointTracer(
        world_without_brush,
        collision_entities=catalog.collision_entities,
        runtime_entity_completeness=RuntimeGeometryCoverage.VERIFIED,
        runtime_entity_state=RuntimeGeometryCoverage.VERIFIED,
    )

    result = tracer.trace_segment((-5.0, 20.0, 0.0), (5.0, 20.0, 0.0))

    assert result.status is TraceStatus.INDETERMINATE
    assert result.reason is TraceReason.DYNAMIC_ENTITY_STATE_UNRESOLVED
    assert result.uncertain_entity_indices == (0,)


def test_missing_tree_and_missing_stance_fail_closed():
    bsp = replace(_trace_bsp(), nodes=(), leafs=())
    tracer = _verified_tracer(bsp)

    segment = tracer.trace_segment((0.0, 0.0, 0.0), (5.0, 0.0, 0.0))
    availability = tracer.trace_line_of_sight_availability(
        (0.0, 0.0, 0.0),
        None,
        (100.0, 0.0, 0.0),
        PlayerStance.STANDING,
    )

    assert segment.status is TraceStatus.INDETERMINATE
    assert segment.reason is TraceReason.MISSING_BSP_TREE
    assert availability.status is TraceStatus.INDETERMINATE
    assert availability.reason is TraceReason.MISSING_STANCE
    assert availability.endpoints == ()


def test_cyclic_bsp_tree_is_indeterminate_instead_of_partially_traced():
    bsp = replace(
        _trace_bsp(),
        nodes=(BspNode(0, (0, -1), (-100, -100, -100), (100, 100, 100)),),
        leafs=(_trace_bsp().leafs[0],),
        leaf_brushes=(0,),
    )

    result = _verified_tracer(bsp).trace_segment((-5.0, 20.0, 0.0), (5.0, 20.0, 0.0))

    assert result.status is TraceStatus.INDETERMINATE
    assert result.reason is TraceReason.INVALID_BSP_TREE


def test_frozen_stance_bounds_and_target_endpoints_match_contract():
    assert PLAYER_BOUNDS[PlayerStance.STANDING].maxs == (18.0, 18.0, 48.0)
    assert PLAYER_BOUNDS[PlayerStance.CROUCHING].maxs == (18.0, 18.0, 24.0)
    assert PLAYER_BOUNDS[PlayerStance.PRONE].maxs == (18.0, 18.0, 16.0)
    assert player_eye_point((1.0, 2.0, 3.0), PlayerStance.PRONE) == (1.0, 2.0, 15.0)

    points = target_body_points((10.0, 20.0, 30.0), PlayerStance.CROUCHING)

    assert [point.label for point in points] == [
        "eye_to_eye",
        "upper_torso",
        "side_x_min",
        "side_x_max",
        "side_y_min",
        "side_y_max",
    ]
    assert points[0].point == (10.0, 20.0, 66.0)
    assert points[1].point == (10.0, 20.0, 46.0)
    assert points[2].point == (-8.0, 20.0, 46.0)
    assert points[3].point == (28.0, 20.0, 46.0)


def test_body_availability_uses_any_clear_and_never_claims_sight():
    bsp = replace(_trace_bsp(), brushes=(), brush_sides=(), leaf_brushes=())
    bsp = replace(
        bsp,
        leafs=tuple(replace(leaf, first_leaf_brush=0, num_leaf_brushes=0) for leaf in bsp.leafs),
        models=(replace(bsp.models[0], first_brush=0, num_brushes=0),),
    )
    availability = _verified_tracer(bsp).trace_line_of_sight_availability(
        (0.0, 0.0, 0.0),
        PlayerStance.STANDING,
        (100.0, 0.0, 0.0),
        PlayerStance.CROUCHING,
    )

    assert availability.status is TraceStatus.CLEAR
    assert availability.availability_rule == "any_clear"
    assert availability.interpretation == "line_of_sight_availability"
    assert availability.validation_status == "unvalidated_until_w6"
    assert len(availability.endpoints) == 6
