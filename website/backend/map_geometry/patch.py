"""Independent quadratic-patch collision facets for ET:L BSP point traces.

The implementation follows the documented ET:L patch contract without
copying engine source: quadratic control grids are adaptively flattened, then
each grid cell becomes one-sided planar facets for point-segment traces.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from website.backend.map_geometry.bsp import BspFile, SurfaceType
from website.backend.map_geometry.entities import Bounds3D

Vector3 = tuple[float, float, float]

PATCH_SUBDIVIDE_DISTANCE = 16.0
PATCH_POINT_EPSILON = 0.1
PATCH_BOUNDS_PADDING = 1.0
PATCH_MAX_GRID_SIZE = 129
PATCH_PLANE_EPSILON = 0.1
_DEGENERATE_NORMAL_SQUARED = 1e-20
_BARYCENTRIC_EPSILON = 1e-7


class PatchCollisionError(ValueError):
    """A patch cannot be converted into trustworthy collision facets."""


@dataclass(frozen=True, slots=True)
class PatchFacet:
    normal: Vector3
    distance: float
    vertices: tuple[Vector3, ...]
    containment_variants: tuple[tuple[Vector3, ...], ...] = ()


@dataclass(frozen=True, slots=True)
class PatchCollision:
    surface_index: int
    content_flags: int
    bounds: Bounds3D | None
    facets: tuple[PatchFacet, ...]
    grid_width: int
    grid_height: int
    wrap_width: bool = False
    wrap_height: bool = False
    error: str | None = None


@dataclass(frozen=True, slots=True)
class PatchHit:
    fraction: float
    facet_index: int


def _midpoint(left: Vector3, right: Vector3) -> Vector3:
    return tuple((left[axis] + right[axis]) * 0.5 for axis in range(3))


def _quadratic_midpoint(start: Vector3, control: Vector3, end: Vector3) -> Vector3:
    first = _midpoint(start, control)
    second = _midpoint(control, end)
    return _midpoint(first, second)


def _needs_subdivision(start: Vector3, control: Vector3, end: Vector3) -> bool:
    curve_midpoint = _quadratic_midpoint(start, control, end)
    line_midpoint = _midpoint(start, end)
    error_squared = sum(
        (curve_midpoint[axis] - line_midpoint[axis]) ** 2 for axis in range(3)
    )
    return error_squared >= PATCH_SUBDIVIDE_DISTANCE**2


def _subdivide_columns(columns: list[list[Vector3]]) -> None:
    column = 0
    while column < len(columns) - 2:
        if not any(
            _needs_subdivision(columns[column][row], columns[column + 1][row], columns[column + 2][row])
            for row in range(len(columns[0]))
        ):
            del columns[column + 1]
            column += 1
            continue

        if len(columns) + 2 > PATCH_MAX_GRID_SIZE:
            raise PatchCollisionError("adaptive patch grid exceeds 129 columns")
        first: list[Vector3] = []
        middle: list[Vector3] = []
        third: list[Vector3] = []
        for row in range(len(columns[0])):
            start = columns[column][row]
            control = columns[column + 1][row]
            end = columns[column + 2][row]
            first.append(_midpoint(start, control))
            middle.append(_quadratic_midpoint(start, control, end))
            third.append(_midpoint(control, end))
        columns[column + 1 : column + 2] = [first, middle, third]


def _points_close(left: Vector3, right: Vector3) -> bool:
    return all(abs(left[axis] - right[axis]) <= PATCH_POINT_EPSILON for axis in range(3))


def _remove_degenerate_columns(columns: list[list[Vector3]]) -> None:
    column = 0
    while column < len(columns) - 1:
        if all(
            _points_close(columns[column][row], columns[column + 1][row])
            for row in range(len(columns[0]))
        ):
            del columns[column + 1]
        else:
            column += 1


def _transpose(columns: list[list[Vector3]]) -> list[list[Vector3]]:
    return [[columns[column][row] for column in range(len(columns))] for row in range(len(columns[0]))]


def _flatten_grid(
    control_points: tuple[Vector3, ...],
    width: int,
    height: int,
) -> tuple[list[list[Vector3]], bool, bool]:
    if width <= 2 or height <= 2 or width % 2 == 0 or height % 2 == 0:
        raise PatchCollisionError(f"invalid quadratic patch dimensions {width}x{height}")
    if width > PATCH_MAX_GRID_SIZE or height > PATCH_MAX_GRID_SIZE:
        raise PatchCollisionError(f"patch dimensions {width}x{height} exceed 129")
    if len(control_points) != width * height:
        raise PatchCollisionError(
            f"patch dimensions {width}x{height} require {width * height} control points; found {len(control_points)}"
        )
    if not all(math.isfinite(value) for point in control_points for value in point):
        raise PatchCollisionError("patch control points must be finite")

    wrap_width = all(
        _points_close(
            control_points[row * width],
            control_points[(row * width) + width - 1],
        )
        for row in range(height)
    )
    wrap_height = all(
        _points_close(control_points[column], control_points[((height - 1) * width) + column])
        for column in range(width)
    )

    columns = [
        [control_points[(row * width) + column] for row in range(height)]
        for column in range(width)
    ]
    _subdivide_columns(columns)
    _remove_degenerate_columns(columns)
    columns = _transpose(columns)
    _subdivide_columns(columns)
    _remove_degenerate_columns(columns)

    return columns, wrap_width, wrap_height


def _subtract(left: Vector3, right: Vector3) -> Vector3:
    return tuple(left[axis] - right[axis] for axis in range(3))


def _dot(left: Vector3, right: Vector3) -> float:
    return sum(left[axis] * right[axis] for axis in range(3))


def _cross(left: Vector3, right: Vector3) -> Vector3:
    return (
        (left[1] * right[2]) - (left[2] * right[1]),
        (left[2] * right[0]) - (left[0] * right[2]),
        (left[0] * right[1]) - (left[1] * right[0]),
    )


def _surface_plane(
    first: Vector3,
    second: Vector3,
    third: Vector3,
    planes: list[tuple[Vector3, float]],
) -> tuple[Vector3, float] | None:
    # ET:L patch planes point out of clockwise-ordered control-grid triangles.
    normal = _cross(_subtract(third, first), _subtract(second, first))
    length_squared = _dot(normal, normal)
    if length_squared <= _DEGENERATE_NORMAL_SQUARED:
        return None
    inverse_length = 1.0 / math.sqrt(length_squared)
    unit_normal = tuple(component * inverse_length for component in normal)
    distance = _dot(first, unit_normal)
    vertices = (first, second, third)
    for existing_normal, existing_distance in planes:
        if _dot(unit_normal, existing_normal) < 0.0:
            continue
        if all(
            abs(_dot(vertex, existing_normal) - existing_distance) <= PATCH_PLANE_EPSILON
            for vertex in vertices
        ):
            return existing_normal, existing_distance
    planes.append((unit_normal, distance))
    return unit_normal, distance


def _expanded_bounds(points: tuple[Vector3, ...], padding: float) -> Bounds3D:
    return Bounds3D(
        mins=tuple(min(point[axis] for point in points) - padding for axis in range(3)),
        maxs=tuple(max(point[axis] for point in points) + padding for axis in range(3)),
    )


def _containment_variants(
    grid: list[list[Vector3]],
    grid_coordinates: tuple[tuple[int, int], ...],
    *,
    width_boundary_row: int | None,
    height_boundary_column: int | None,
) -> tuple[tuple[Vector3, ...], ...]:
    """Return alternate seam-border polygons without moving surface vertices."""
    variants: list[tuple[Vector3, ...]] = []
    for use_width_seam, use_height_seam in (
        (True, False),
        (False, True),
        (True, True),
    ):
        if use_width_seam and width_boundary_row is None:
            continue
        if use_height_seam and height_boundary_column is None:
            continue
        points: list[Vector3] = []
        for grid_column, grid_row in grid_coordinates:
            if use_width_seam and grid_row == width_boundary_row:
                grid_row = len(grid[0]) - 1 if width_boundary_row == 0 else 0
            if use_height_seam and grid_column == height_boundary_column:
                grid_column = len(grid) - 1 if height_boundary_column == 0 else 0
            points.append(grid[grid_column][grid_row])
        variant = tuple(points)
        if variant not in variants:
            variants.append(variant)
    return tuple(variants)


def patch_control_bounds(control_points: tuple[Vector3, ...]) -> Bounds3D | None:
    """Return conservative finite control-hull bounds for a patch, if trustworthy."""
    if not control_points or not all(
        math.isfinite(value) for point in control_points for value in point
    ):
        return None
    return _expanded_bounds(control_points, PATCH_BOUNDS_PADDING)


def build_patch_collision(
    control_points: tuple[Vector3, ...],
    width: int,
    height: int,
    *,
    surface_index: int = 0,
    content_flags: int = 0,
) -> PatchCollision:
    """Build deterministic one-sided point-collision facets for one patch."""
    grid, wrap_width, wrap_height = _flatten_grid(control_points, width, height)
    facets: list[PatchFacet] = []
    planes: list[tuple[Vector3, float]] = []
    for column in range(len(grid) - 1):
        for row in range(len(grid[0]) - 1):
            top_left = grid[column][row]
            top_right = grid[column + 1][row]
            bottom_right = grid[column + 1][row + 1]
            bottom_left = grid[column][row + 1]
            first_vertices = (top_left, top_right, bottom_right)
            second_vertices = (bottom_right, bottom_left, top_left)
            width_boundary_row = (
                0
                if wrap_width and row == 0
                else len(grid[0]) - 1
                if wrap_width and row == len(grid[0]) - 2
                else None
            )
            height_boundary_column = (
                0
                if wrap_height and column == 0
                else len(grid) - 1
                if wrap_height and column == len(grid) - 2
                else None
            )
            quad_coordinates = (
                (column, row),
                (column + 1, row),
                (column + 1, row + 1),
                (column, row + 1),
            )
            quad_variants = _containment_variants(
                grid,
                quad_coordinates,
                width_boundary_row=width_boundary_row,
                height_boundary_column=height_boundary_column,
            )
            first_plane = _surface_plane(*first_vertices, planes)
            second_plane = _surface_plane(*second_vertices, planes)
            if first_plane is not None and first_plane == second_plane:
                facets.append(
                    PatchFacet(
                        *first_plane,
                        (top_left, top_right, bottom_right, bottom_left),
                        quad_variants,
                    )
                )
                continue
            if first_plane is not None:
                first_variants = _containment_variants(
                    grid,
                    (quad_coordinates[0], quad_coordinates[1], quad_coordinates[2]),
                    width_boundary_row=0 if width_boundary_row == 0 else None,
                    height_boundary_column=(
                        len(grid) - 1
                        if height_boundary_column == len(grid) - 1
                        else None
                    ),
                )
                facets.append(
                    PatchFacet(
                        *first_plane,
                        first_vertices,
                        first_variants,
                    )
                )
            if second_plane is not None:
                second_variants = _containment_variants(
                    grid,
                    (quad_coordinates[2], quad_coordinates[3], quad_coordinates[0]),
                    width_boundary_row=(
                        len(grid[0]) - 1
                        if width_boundary_row == len(grid[0]) - 1
                        else None
                    ),
                    height_boundary_column=0 if height_boundary_column == 0 else None,
                )
                facets.append(
                    PatchFacet(
                        *second_plane,
                        second_vertices,
                        second_variants,
                    )
                )

    flattened_points = tuple(point for column in grid for point in column)
    return PatchCollision(
        surface_index=surface_index,
        content_flags=content_flags,
        bounds=_expanded_bounds(flattened_points, PATCH_BOUNDS_PADDING),
        facets=tuple(facets),
        # _flatten_grid returns the once-transposed engine working grid.
        # Metadata remains in the BSP patch's original parameter orientation.
        grid_width=len(grid[0]),
        grid_height=len(grid),
        wrap_width=wrap_width,
        wrap_height=wrap_height,
    )


def _point_in_triangle(point: Vector3, vertices: tuple[Vector3, Vector3, Vector3]) -> bool:
    first, second, third = vertices
    edge0 = _subtract(second, first)
    edge1 = _subtract(third, first)
    relative = _subtract(point, first)
    dot00 = _dot(edge0, edge0)
    dot01 = _dot(edge0, edge1)
    dot11 = _dot(edge1, edge1)
    dot20 = _dot(relative, edge0)
    dot21 = _dot(relative, edge1)
    denominator = (dot00 * dot11) - (dot01 * dot01)
    if abs(denominator) <= _DEGENERATE_NORMAL_SQUARED:
        return False
    first_weight = ((dot11 * dot20) - (dot01 * dot21)) / denominator
    second_weight = ((dot00 * dot21) - (dot01 * dot20)) / denominator
    return (
        first_weight >= -_BARYCENTRIC_EPSILON
        and second_weight >= -_BARYCENTRIC_EPSILON
        and first_weight + second_weight <= 1.0 + _BARYCENTRIC_EPSILON
    )


def _point_in_polygon(point: Vector3, vertices: tuple[Vector3, ...]) -> bool:
    if len(vertices) == 3:
        return _point_in_triangle(point, (vertices[0], vertices[1], vertices[2]))
    if len(vertices) == 4:
        return _point_in_triangle(point, (vertices[0], vertices[1], vertices[2])) or _point_in_triangle(
            point,
            (vertices[2], vertices[3], vertices[0]),
        )
    raise PatchCollisionError(f"unsupported patch facet vertex count {len(vertices)}")


def _point_in_facet(point: Vector3, facet: PatchFacet) -> bool:
    return any(
        _point_in_polygon(point, vertices)
        for vertices in (facet.vertices, *facet.containment_variants)
    )


def trace_patch_point(
    collision: PatchCollision,
    start: Vector3,
    end: Vector3,
    *,
    surface_clip_epsilon: float,
    max_fraction: float = 1.0,
) -> tuple[PatchHit | None, int]:
    """Trace one point segment through compiled one-sided patch facets."""
    closest: PatchHit | None = None
    tested = 0
    direction = _subtract(end, start)
    for facet_index, facet in enumerate(collision.facets):
        tested += 1
        start_distance = _dot(start, facet.normal) - facet.distance
        if start_distance <= 0.0:
            continue
        end_distance = _dot(end, facet.normal) - facet.distance
        denominator = start_distance - end_distance
        if denominator <= 0.0:
            continue
        intersection = start_distance / denominator
        limit = closest.fraction if closest is not None else max_fraction
        # ET:L rejects a patch surface plane against the current trace fraction
        # before applying this facet's pushoff. This intentionally means a raw
        # intersection just beyond an earlier pushed brush hit does not replace it.
        if intersection <= 0.0 or intersection > limit or intersection > 1.0:
            continue
        point = tuple(start[axis] + (intersection * direction[axis]) for axis in range(3))
        # ET:L tests facet border-plane intersections against the raw surface
        # intersection. Its 0.125 pushoff is calculated only after the facet hit
        # is accepted, so containment must not use the tangentially shifted point.
        if not _point_in_facet(point, facet):
            continue
        pushed_fraction = max(0.0, (start_distance - surface_clip_epsilon) / denominator)
        if pushed_fraction <= limit:
            closest = PatchHit(pushed_fraction, facet_index)
    return closest, tested


def compile_bsp_patches(bsp: BspFile) -> tuple[PatchCollision, ...]:
    """Compile every BSP patch independently, preserving fail-closed errors."""
    compiled: list[PatchCollision] = []
    for surface_index, surface in enumerate(bsp.surfaces):
        if surface.surface_type is not SurfaceType.PATCH:
            continue
        control_points = tuple(
            vertex.position
            for vertex in bsp.draw_vertices[
                surface.first_vertex : surface.first_vertex + surface.num_vertices
            ]
        )
        content_flags = bsp.shaders[surface.shader_index].content_flags
        try:
            collision = build_patch_collision(
                control_points,
                surface.patch_width,
                surface.patch_height,
                surface_index=surface_index,
                content_flags=content_flags,
            )
        except PatchCollisionError as exc:
            collision = PatchCollision(
                surface_index=surface_index,
                content_flags=content_flags,
                bounds=patch_control_bounds(control_points),
                facets=(),
                grid_width=surface.patch_width,
                grid_height=surface.patch_height,
                error=str(exc),
            )
        compiled.append(collision)
    return tuple(compiled)
