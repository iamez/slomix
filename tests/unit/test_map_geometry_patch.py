"""Hand-checked W4a2 contracts for quadratic patch point collision."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from website.backend.map_geometry import (
    PatchCollisionError,
    build_patch_collision,
    trace_patch_point,
)


def _planar_grid() -> tuple[tuple[float, float, float], ...]:
    return tuple((0.0, y, z) for y in (-1.0, 0.0, 1.0) for z in (-1.0, 0.0, 1.0))


def _curved_grid() -> tuple[tuple[float, float, float], ...]:
    return tuple(
        (64.0 if y == 0.0 and z == 0.0 else 0.0, y, z)
        for y in (-1.0, 0.0, 1.0)
        for z in (-1.0, 0.0, 1.0)
    )


def _single_axis_bulge(control_deviation: float) -> tuple[tuple[float, float, float], ...]:
    return tuple(
        (control_deviation if column == 1 else 0.0, float(row), float(column))
        for row in range(3)
        for column in range(3)
    )


def test_planar_patch_flattens_to_one_quad_facet_and_uses_engine_pushoff():
    collision = build_patch_collision(_planar_grid(), 3, 3)

    hit, tested = trace_patch_point(
        collision,
        (-2.0, 0.0, 0.0),
        (2.0, 0.0, 0.0),
        surface_clip_epsilon=0.125,
    )

    assert collision.grid_width == 2
    assert collision.grid_height == 2
    assert len(collision.facets) == 1
    assert len(collision.facets[0].vertices) == 4
    assert tested == 1
    assert hit is not None
    assert hit.fraction == pytest.approx((2.0 - 0.125) / 4.0)


def test_point_patch_trace_is_one_sided_and_bounded_at_edges():
    collision = build_patch_collision(_planar_grid(), 3, 3)

    reverse, _ = trace_patch_point(
        collision,
        (2.0, 0.0, 0.0),
        (-2.0, 0.0, 0.0),
        surface_clip_epsilon=0.125,
    )
    outside, _ = trace_patch_point(
        collision,
        (-2.0, 1.01, 0.0),
        (2.0, 1.01, 0.0),
        surface_clip_epsilon=0.125,
    )
    edge, _ = trace_patch_point(
        collision,
        (-2.0, 1.0, 1.0),
        (2.0, 1.0, 1.0),
        surface_clip_epsilon=0.125,
    )

    assert reverse is None
    assert outside is None
    assert edge is not None


def test_existing_pushed_hit_limits_raw_patch_intersection_before_patch_pushoff():
    collision = build_patch_collision(_planar_grid(), 3, 3)

    hit, _ = trace_patch_point(
        collision,
        (-2.0, 0.0, 0.0),
        (2.0, 0.0, 0.0),
        surface_clip_epsilon=0.125,
        max_fraction=0.49,
    )

    # The raw plane intersection is 0.5 and is rejected against the existing
    # trace fraction, even though applying this facet's pushoff would yield 0.46875.
    assert hit is None


def test_oblique_edge_containment_uses_raw_intersection_before_pushoff():
    collision = build_patch_collision(_planar_grid(), 3, 3)

    hit, _ = trace_patch_point(
        collision,
        (-2.0, 1.3, 0.0),
        (2.0, 0.7, 0.0),
        surface_clip_epsilon=0.125,
    )

    assert hit is not None
    assert hit.fraction == pytest.approx((2.0 - 0.125) / 4.0)
    pushed_y = 1.3 + (hit.fraction * (0.7 - 1.3))
    assert pushed_y > 1.0


def test_on_plane_start_is_not_a_front_side_patch_contact():
    collision = build_patch_collision(_planar_grid(), 3, 3)

    hit, _ = trace_patch_point(
        collision,
        (0.0, 0.0, 0.0),
        (2.0, 0.0, 0.0),
        surface_clip_epsilon=0.125,
    )

    assert hit is None


def test_curved_patch_subdivides_and_hits_its_exact_quadratic_midpoint():
    collision = build_patch_collision(_curved_grid(), 3, 3)

    hit, tested = trace_patch_point(
        collision,
        (-10.0, 0.0, 0.0),
        (30.0, 0.0, 0.0),
        surface_clip_epsilon=0.125,
    )

    assert collision.grid_width > 2
    assert collision.grid_height > 2
    assert len(collision.facets) > 2
    assert tested == len(collision.facets)
    assert hit is not None
    facet = collision.facets[hit.facet_index]
    start_distance = (-10.0 * facet.normal[0]) - facet.distance
    end_distance = (30.0 * facet.normal[0]) - facet.distance
    assert start_distance / (start_distance - end_distance) == pytest.approx(26.0 / 40.0)
    assert hit.fraction == pytest.approx(
        (start_distance - 0.125) / (start_distance - end_distance)
    )


def test_subdivision_threshold_uses_quadratic_midpoint_not_raw_control_deviation():
    below_threshold = build_patch_collision(_single_axis_bulge(20.0), 3, 3)
    at_threshold = build_patch_collision(_single_axis_bulge(32.0), 3, 3)

    # Quadratic t=0.5 halves the middle control-point deviation: 20 -> 10
    # collapses, while 32 -> 16 reaches ET:L's inclusive threshold.
    assert (below_threshold.grid_width, below_threshold.grid_height) == (2, 2)
    assert max(at_threshold.grid_width, at_threshold.grid_height) > 2


def test_flattened_grid_metadata_retains_input_axis_orientation():
    control_points = tuple(
        (0.0, float(column), float(row))
        for row in range(3)
        for column in range(5)
    )

    collision = build_patch_collision(control_points, 5, 3)

    assert (collision.grid_width, collision.grid_height) == (3, 2)


def test_nearly_coplanar_triangles_reuse_tolerance_matched_surface_plane():
    control_points = list(_planar_grid())
    control_points[0] = (0.05, -1.0, -1.0)

    collision = build_patch_collision(tuple(control_points), 3, 3)

    assert len(collision.facets) == 1
    assert len(collision.facets[0].vertices) == 4


def test_tolerance_matched_wrap_seam_preserves_coordinates_and_adds_topology():
    control_points = []
    for row in range(3):
        for column in range(5):
            if column == 4:
                point = (0.05, 0.0, float(row))
            else:
                angle_points = (
                    (0.0, 0.0),
                    (64.0, 64.0),
                    (128.0, 0.0),
                    (64.0, -64.0),
                )
                x, y = angle_points[column]
                point = (x, y, float(row))
            control_points.append(point)

    collision = build_patch_collision(tuple(control_points), 5, 3)

    assert collision.wrap_width is True
    assert collision.wrap_height is False
    seam_vertices = {
        vertex
        for facet in collision.facets
        for vertex in facet.vertices
        if abs(vertex[0]) <= 0.1 and abs(vertex[1]) <= 0.1
    }
    assert seam_vertices == {
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 2.0),
        (0.05, 0.0, 0.0),
        (0.05, 0.0, 2.0),
    }
    assert any(facet.containment_variants for facet in collision.facets)
    alternate_seam_vertices = {
        vertex
        for facet in collision.facets
        for variant in facet.containment_variants
        for vertex in variant
        if abs(vertex[0]) <= 0.1 and abs(vertex[1]) <= 0.1
    }
    assert alternate_seam_vertices == seam_vertices
    without_seam_topology = replace(
        collision,
        facets=tuple(replace(facet, containment_variants=()) for facet in collision.facets),
    )
    open_hit, _ = trace_patch_point(
        without_seam_topology,
        (-0.2, 0.13, 1.0),
        (0.03, 0.01, 1.0),
        surface_clip_epsilon=0.125,
    )
    wrapped_hit, _ = trace_patch_point(
        collision,
        (-0.2, 0.13, 1.0),
        (0.03, 0.01, 1.0),
        surface_clip_epsilon=0.125,
    )
    assert open_hit is None
    assert wrapped_hit is not None


def test_degenerate_patch_has_no_facets_and_malformed_inputs_are_rejected():
    collision = build_patch_collision(((0.0, 0.0, 0.0),) * 9, 3, 3)
    hit, tested = trace_patch_point(
        collision,
        (1.0, 0.0, 0.0),
        (-1.0, 0.0, 0.0),
        surface_clip_epsilon=0.125,
    )

    assert collision.facets == ()
    assert hit is None
    assert tested == 0
    with pytest.raises(PatchCollisionError, match="must be finite"):
        build_patch_collision((*_planar_grid()[:-1], (math.nan, 0.0, 0.0)), 3, 3)
    with pytest.raises(PatchCollisionError, match="invalid quadratic patch dimensions"):
        build_patch_collision(_planar_grid(), 2, 3)
