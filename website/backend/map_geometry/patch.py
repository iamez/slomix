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


class PatchCollisionError(ValueError):
    """A patch cannot be converted into trustworthy collision facets."""


@dataclass(frozen=True, slots=True)
class PatchBorder:
    normal: Vector3
    distance: float
    inward: bool


@dataclass(frozen=True, slots=True)
class PatchFacet:
    normal: Vector3
    distance: float
    vertices: tuple[Vector3, ...]
    borders: tuple[PatchBorder, ...]


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
    error_squared = sum((curve_midpoint[axis] - line_midpoint[axis]) ** 2 for axis in range(3))
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
        if all(_points_close(columns[column][row], columns[column + 1][row]) for row in range(len(columns[0]))):
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
    columns = [[control_points[(row * width) + column] for row in range(height)] for column in range(width)]
    _subdivide_columns(columns)
    _remove_degenerate_columns(columns)
    # ET:L detects the second-axis wrap only after the first-axis flattening.
    # Removed control columns must not keep an otherwise closed axis open.
    wrap_height = all(_points_close(column[0], column[-1]) for column in columns)
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


def _find_plane(
    first: Vector3,
    second: Vector3,
    third: Vector3,
    planes: list[tuple[Vector3, float]],
) -> int | None:
    # ET:L patch planes point out of clockwise-ordered control-grid triangles.
    normal = _cross(_subtract(third, first), _subtract(second, first))
    length_squared = _dot(normal, normal)
    if length_squared <= _DEGENERATE_NORMAL_SQUARED:
        return None
    inverse_length = 1.0 / math.sqrt(length_squared)
    unit_normal = tuple(component * inverse_length for component in normal)
    distance = _dot(first, unit_normal)
    vertices = (first, second, third)
    for plane_index, (existing_normal, existing_distance) in enumerate(planes):
        if _dot(unit_normal, existing_normal) < 0.0:
            continue
        if all(abs(_dot(vertex, existing_normal) - existing_distance) <= PATCH_PLANE_EPSILON for vertex in vertices):
            return plane_index
    planes.append((unit_normal, distance))
    return len(planes) - 1


def _expanded_bounds(points: tuple[Vector3, ...], padding: float) -> Bounds3D:
    return Bounds3D(
        mins=tuple(min(point[axis] for point in points) - padding for axis in range(3)),
        maxs=tuple(max(point[axis] for point in points) + padding for axis in range(3)),
    )


def _grid_plane(
    grid_planes: list[list[tuple[int | None, int | None]]],
    column: int,
    row: int,
    triangle: int,
) -> int | None:
    plane = grid_planes[column][row][triangle]
    if plane is not None:
        return plane
    return grid_planes[column][row][1 - triangle]


def _edge_plane(
    grid: list[list[Vector3]],
    grid_planes: list[list[tuple[int | None, int | None]]],
    planes: list[tuple[Vector3, float]],
    column: int,
    row: int,
    edge: int,
) -> int | None:
    if edge == 0:  # top
        first = grid[column][row]
        second = grid[column + 1][row]
        surface = _grid_plane(grid_planes, column, row, 0)
    elif edge == 1:  # right
        first = grid[column + 1][row]
        second = grid[column + 1][row + 1]
        surface = _grid_plane(grid_planes, column, row, 0)
    elif edge == 2:  # bottom
        second = grid[column][row + 1]
        first = grid[column + 1][row + 1]
        surface = _grid_plane(grid_planes, column, row, 1)
    elif edge == 3:  # left
        second = grid[column][row]
        first = grid[column][row + 1]
        surface = _grid_plane(grid_planes, column, row, 1)
    elif edge == 4:  # diagonal out of triangle 0
        first = grid[column + 1][row + 1]
        second = grid[column][row]
        surface = _grid_plane(grid_planes, column, row, 0)
    elif edge == 5:  # diagonal out of triangle 1
        first = grid[column][row]
        second = grid[column + 1][row + 1]
        surface = _grid_plane(grid_planes, column, row, 1)
    else:
        raise PatchCollisionError(f"unsupported patch edge {edge}")
    if surface is None:
        return None
    normal, _ = planes[surface]
    up = tuple(first[axis] + (4.0 * normal[axis]) for axis in range(3))
    return _find_plane(first, second, up, planes)


def _facet(
    surface_plane: int | None,
    border_planes: tuple[int | None, ...],
    vertices: tuple[Vector3, ...],
    cell_vertices: tuple[Vector3, Vector3, Vector3, Vector3],
    planes: list[tuple[Vector3, float]],
) -> PatchFacet | None:
    if surface_plane is None:
        return None
    borders: list[PatchBorder] = []
    for border_plane in border_planes:
        if border_plane is None:
            return None
        normal, distance = planes[border_plane]
        front = False
        back = False
        for vertex in cell_vertices:
            offset = _dot(vertex, normal) - distance
            front |= offset > PATCH_PLANE_EPSILON
            back |= offset < -PATCH_PLANE_EPSILON
        if (front and back) or (not front and not back):
            return None
        borders.append(PatchBorder(normal, distance, front and not back))
    normal, distance = planes[surface_plane]
    return PatchFacet(normal, distance, vertices, tuple(borders))


def patch_control_bounds(control_points: tuple[Vector3, ...]) -> Bounds3D | None:
    """Return conservative finite control-hull bounds for a patch, if trustworthy."""
    if not control_points or not all(math.isfinite(value) for point in control_points for value in point):
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
    grid_planes: list[list[tuple[int | None, int | None]]] = []
    for column in range(len(grid) - 1):
        column_planes: list[tuple[int | None, int | None]] = []
        for row in range(len(grid[0]) - 1):
            top_left = grid[column][row]
            top_right = grid[column + 1][row]
            bottom_right = grid[column + 1][row + 1]
            bottom_left = grid[column][row + 1]
            column_planes.append(
                (
                    _find_plane(top_left, top_right, bottom_right, planes),
                    _find_plane(bottom_right, bottom_left, top_left, planes),
                )
            )
        grid_planes.append(column_planes)

    for column in range(len(grid) - 1):
        for row in range(len(grid[0]) - 1):
            first_plane, second_plane = grid_planes[column][row]
            top = grid_planes[column][row - 1][1] if row > 0 else grid_planes[column][-1][1] if wrap_width else None
            if top is None or top == first_plane:
                top = _edge_plane(grid, grid_planes, planes, column, row, 0)
            bottom = (
                grid_planes[column][row + 1][0]
                if row < len(grid[0]) - 2
                else grid_planes[column][0][0]
                if wrap_width
                else None
            )
            if bottom is None or bottom == second_plane:
                bottom = _edge_plane(grid, grid_planes, planes, column, row, 2)
            left = grid_planes[column - 1][row][0] if column > 0 else grid_planes[-1][row][0] if wrap_height else None
            if left is None or left == second_plane:
                left = _edge_plane(grid, grid_planes, planes, column, row, 3)
            right = (
                grid_planes[column + 1][row][1]
                if column < len(grid) - 2
                else grid_planes[0][row][1]
                if wrap_height
                else None
            )
            if right is None or right == first_plane:
                right = _edge_plane(grid, grid_planes, planes, column, row, 1)

            top_left = grid[column][row]
            top_right = grid[column + 1][row]
            bottom_right = grid[column + 1][row + 1]
            bottom_left = grid[column][row + 1]
            cell_vertices = (top_left, top_right, bottom_right, bottom_left)
            if first_plane is not None and first_plane == second_plane:
                facet = _facet(
                    first_plane,
                    (top, right, bottom, left),
                    cell_vertices,
                    cell_vertices,
                    planes,
                )
                if facet is not None:
                    facets.append(facet)
                continue

            first_diagonal = second_plane
            if first_diagonal is None:
                first_diagonal = bottom
                if first_diagonal is None:
                    first_diagonal = _edge_plane(grid, grid_planes, planes, column, row, 4)
            first_facet = _facet(
                first_plane,
                (top, right, first_diagonal),
                (top_left, top_right, bottom_right),
                cell_vertices,
                planes,
            )
            if first_facet is not None:
                facets.append(first_facet)

            second_diagonal = first_plane
            if second_diagonal is None:
                second_diagonal = top
                if second_diagonal is None:
                    second_diagonal = _edge_plane(grid, grid_planes, planes, column, row, 5)
            second_facet = _facet(
                second_plane,
                (bottom, left, second_diagonal),
                (bottom_right, bottom_left, top_left),
                cell_vertices,
                planes,
            )
            if second_facet is not None:
                facets.append(second_facet)

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


def _intersects_facet_borders(
    start: Vector3,
    end: Vector3,
    surface_intersection: float,
    facet: PatchFacet,
) -> bool:
    """Apply ET:L's border-plane ordering at the raw surface intersection."""
    for border in facet.borders:
        start_distance = _dot(start, border.normal) - border.distance
        end_distance = _dot(end, border.normal) - border.distance
        front_facing = start_distance > 0.0
        if start_distance == end_distance:
            border_intersection = math.inf
        else:
            border_intersection = start_distance / (start_distance - end_distance)
            if border_intersection <= 0.0:
                border_intersection = math.inf
        if front_facing != border.inward:
            if border_intersection > surface_intersection:
                return False
        elif border_intersection < surface_intersection:
            return False
    return True


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
        if not _intersects_facet_borders(start, end, intersection, facet):
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
            for vertex in bsp.draw_vertices[surface.first_vertex : surface.first_vertex + surface.num_vertices]
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
