"""Fail-closed W4a point traces over static ET:L BSP collision inputs.

This module traces convex brushes and compiled quadratic-patch facets. Missing
patch compilation, runtime entity completeness, and runtime entity state remain
explicit uncertainty gates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from website.backend.map_geometry.bsp import BspFile, SurfaceType
from website.backend.map_geometry.entities import Bounds3D, CollisionBrushEntity
from website.backend.map_geometry.patch import (
    PatchCollision,
    compile_bsp_patches,
    patch_control_bounds,
    trace_patch_point,
)

Vector3 = tuple[float, float, float]

CONTENTS_SOLID: Final = 0x00000001
CONTENTS_PLAYERCLIP: Final = 0x00010000
SURFACE_CLIP_EPSILON: Final = 0.125
BSP_TREE_POINT_EPSILON: Final = 1.0


@dataclass(frozen=True, slots=True)
class TraceMask:
    """Named content-bit policy carried by every trace result."""

    name: str
    content_bits: int


LINE_OF_SIGHT_MASK: Final = TraceMask("line_of_sight_solid", CONTENTS_SOLID)
PLAYER_MOVEMENT_MASK: Final = TraceMask(
    "player_movement_solid_playerclip",
    CONTENTS_SOLID | CONTENTS_PLAYERCLIP,
)


class TraceStatus(StrEnum):
    BLOCKED = "blocked"
    CLEAR = "clear"
    INDETERMINATE = "indeterminate"


class TraceReason(StrEnum):
    SOLID_BRUSH = "solid_brush"
    SOLID_PATCH = "solid_patch"
    STATIC_GEOMETRY_BLOCKED = "static_geometry_blocked"
    STATIC_GEOMETRY_CLEAR = "static_geometry_clear"
    SOLID_PATCH_UNCOMPILED = "solid_patch_uncompiled"
    DYNAMIC_ENTITY_STATE_UNRESOLVED = "dynamic_entity_state_unresolved"
    RUNTIME_ENTITY_COMPLETENESS_UNVERIFIED = "runtime_entity_completeness_unverified"
    RUNTIME_ENTITY_STATE_UNVERIFIED = "runtime_entity_state_unverified"
    MISSING_BSP_TREE = "missing_bsp_tree"
    INVALID_BSP_TREE = "invalid_bsp_tree"
    MISSING_STANCE = "missing_stance"


class RuntimeGeometryCoverage(StrEnum):
    """Evidence flag for runtime coverage; it does not carry entity transforms."""

    UNVERIFIED = "unverified"
    VERIFIED = "verified"


class PlayerStance(StrEnum):
    STANDING = "standing"
    CROUCHING = "crouching"
    PRONE = "prone"


@dataclass(frozen=True, slots=True)
class PlayerBounds:
    mins: Vector3
    maxs: Vector3
    eye_height: float


# ET:L playerMins/playerMaxs use +/-18 XY and -24 Z. The stance maxima
# are playerMaxs[2], crouchMaxZ, and PRONE_BODYHEIGHT_BBOX respectively.
# Eye heights intentionally follow the live Slomix Lua trace contract.
PLAYER_BOUNDS: Final = {
    PlayerStance.STANDING: PlayerBounds((-18.0, -18.0, -24.0), (18.0, 18.0, 48.0), 56.0),
    PlayerStance.CROUCHING: PlayerBounds((-18.0, -18.0, -24.0), (18.0, 18.0, 24.0), 36.0),
    PlayerStance.PRONE: PlayerBounds((-18.0, -18.0, -24.0), (18.0, 18.0, 16.0), 12.0),
}


@dataclass(frozen=True, slots=True)
class TargetBodyPoint:
    label: str
    point: Vector3


@dataclass(frozen=True, slots=True)
class PointTraceResult:
    status: TraceStatus
    reason: TraceReason
    trace_mask: TraceMask
    fraction: float | None
    start_solid: bool
    all_solid: bool
    brush_index: int | None
    brush_side_index: int | None
    surface_index: int | None
    patch_facet_index: int | None
    uncertain_surface_indices: tuple[int, ...]
    uncertain_entity_indices: tuple[int, ...]
    uncertainty_reasons: tuple[TraceReason, ...]
    visited_leaf_count: int
    tested_brush_count: int
    tested_patch_count: int
    tested_patch_facet_count: int
    shape: str = "point"


@dataclass(frozen=True, slots=True)
class EndpointTrace:
    label: str
    point: Vector3
    result: PointTraceResult


@dataclass(frozen=True, slots=True)
class LineOfSightAvailability:
    status: TraceStatus
    reason: TraceReason
    observer_eye: Vector3 | None
    endpoints: tuple[EndpointTrace, ...]
    trace_mask: TraceMask
    availability_rule: str = "any_clear"
    interpretation: str = "line_of_sight_availability"
    validation_status: str = "unvalidated_until_w6"


@dataclass(frozen=True, slots=True)
class _BrushHit:
    fraction: float
    start_solid: bool
    all_solid: bool
    side_index: int | None


@dataclass(frozen=True, slots=True)
class _TraceBrush:
    content_flags: int
    sides: tuple[tuple[Vector3, float, int], ...]
    broadphase_bounds: Bounds3D | None


def _dot(left: Vector3, right: Vector3) -> float:
    return sum(left[index] * right[index] for index in range(3))


def _validate_point(point: Vector3, label: str) -> None:
    if len(point) != 3 or not all(math.isfinite(value) for value in point):
        raise ValueError(f"{label} must contain three finite coordinates")


def _translated(origin: Vector3, offset: Vector3) -> Vector3:
    return (
        origin[0] + offset[0],
        origin[1] + offset[1],
        origin[2] + offset[2],
    )


def _lerp(start: Vector3, end: Vector3, fraction: float) -> Vector3:
    return (
        start[0] + fraction * (end[0] - start[0]),
        start[1] + fraction * (end[1] - start[1]),
        start[2] + fraction * (end[2] - start[2]),
    )


def _brush_broadphase_bounds(sides: tuple[tuple[Vector3, float, int], ...]) -> Bounds3D | None:
    mins = [-math.inf, -math.inf, -math.inf]
    maxs = [math.inf, math.inf, math.inf]
    for normal, distance, _side_index in sides:
        # A tiny off-axis term is still unbounded at large coordinates. Only
        # exact axial planes can establish a conservative finite broad phase.
        nonzero_axes = [axis for axis, value in enumerate(normal) if value != 0.0]
        if len(nonzero_axes) != 1:
            continue
        axis = nonzero_axes[0]
        coefficient = normal[axis]
        # The clip epsilon is measured in plane-distance units. Convert it to
        # world coordinates so non-unit axial normals cannot make this bound
        # narrower than the exact brush trace.
        coordinate = (distance + SURFACE_CLIP_EPSILON) / coefficient
        if coefficient > 0.0:
            maxs[axis] = min(maxs[axis], coordinate)
        else:
            mins[axis] = max(mins[axis], coordinate)
    if not all(math.isfinite(value) for value in (*mins, *maxs)):
        return None
    return Bounds3D((mins[0], mins[1], mins[2]), (maxs[0], maxs[1], maxs[2]))


def player_eye_point(origin: Vector3, stance: PlayerStance) -> Vector3:
    """Return the observer/target eye endpoint used by the current live Lua."""
    _validate_point(origin, "origin")
    bounds = PLAYER_BOUNDS[stance]
    return (origin[0], origin[1], origin[2] + bounds.eye_height)


def target_body_points(origin: Vector3, stance: PlayerStance) -> tuple[TargetBodyPoint, ...]:
    """Return the frozen W4a target set over ET:L's axis-aligned stance bounds.

    The four side points use the engine-equivalent XY bounds. ``upper_torso``
    is eight units below the stance-specific collision maximum. Availability
    uses an any-clear rule; eye-to-eye remains separately labelled.
    """
    _validate_point(origin, "origin")
    bounds = PLAYER_BOUNDS[stance]
    torso_z = bounds.maxs[2] - 8.0
    return (
        TargetBodyPoint("eye_to_eye", player_eye_point(origin, stance)),
        TargetBodyPoint("upper_torso", _translated(origin, (0.0, 0.0, torso_z))),
        TargetBodyPoint("side_x_min", _translated(origin, (bounds.mins[0], 0.0, torso_z))),
        TargetBodyPoint("side_x_max", _translated(origin, (bounds.maxs[0], 0.0, torso_z))),
        TargetBodyPoint("side_y_min", _translated(origin, (0.0, bounds.mins[1], torso_z))),
        TargetBodyPoint("side_y_max", _translated(origin, (0.0, bounds.maxs[1], torso_z))),
    )


def _segment_bounds_fraction(
    start: Vector3,
    end: Vector3,
    bounds: Bounds3D,
    *,
    epsilon: float = 0.0,
) -> float | None:
    enter = 0.0
    leave = 1.0
    for axis in range(3):
        low = bounds.mins[axis] - epsilon
        high = bounds.maxs[axis] + epsilon
        delta = end[axis] - start[axis]
        if abs(delta) <= 1e-12:
            if start[axis] < low or start[axis] > high:
                return None
            continue
        first = (low - start[axis]) / delta
        second = (high - start[axis]) / delta
        if first > second:
            first, second = second, first
        enter = max(enter, first)
        leave = min(leave, second)
        if enter > leave:
            return None
    return max(0.0, enter)


class BspPointTracer:
    """Point-segment collision with explicit incomplete-geometry gates."""

    def __init__(
        self,
        bsp: BspFile,
        *,
        collision_entities: tuple[CollisionBrushEntity, ...] = (),
        patch_collisions: tuple[PatchCollision, ...] | None = None,
        runtime_entity_completeness: RuntimeGeometryCoverage | str = RuntimeGeometryCoverage.UNVERIFIED,
        runtime_entity_state: RuntimeGeometryCoverage | str = RuntimeGeometryCoverage.UNVERIFIED,
    ) -> None:
        self._bsp = bsp
        self._collision_entities = collision_entities
        self._runtime_entity_completeness = RuntimeGeometryCoverage(runtime_entity_completeness)
        self._runtime_entity_state = RuntimeGeometryCoverage(runtime_entity_state)
        compiled_patches = compile_bsp_patches(bsp) if patch_collisions is None else patch_collisions
        patch_by_surface: dict[int, PatchCollision] = {}
        for patch in compiled_patches:
            surface_index = patch.surface_index
            if not 0 <= surface_index < len(bsp.surfaces):
                raise ValueError(f"patch collision surface index {surface_index} is out of range")
            if bsp.surfaces[surface_index].surface_type is not SurfaceType.PATCH:
                raise ValueError(f"surface {surface_index} is not a BSP patch")
            if surface_index in patch_by_surface:
                raise ValueError(f"duplicate patch collision for surface {surface_index}")
            patch_by_surface[surface_index] = patch
        self._patch_collisions = patch_by_surface
        self._patch_control_bounds = {
            surface_index: patch_control_bounds(
                tuple(
                    vertex.position
                    for vertex in bsp.draw_vertices[
                        surface.first_vertex : surface.first_vertex + surface.num_vertices
                    ]
                )
            )
            for surface_index, surface in enumerate(bsp.surfaces)
            if surface.surface_type is SurfaceType.PATCH and surface_index not in patch_by_surface
        }
        self._trace_brushes = tuple(
            _TraceBrush(
                content_flags=bsp.shaders[brush.shader_index].content_flags,
                sides=sides,
                broadphase_bounds=_brush_broadphase_bounds(sides),
            )
            for brush in bsp.brushes
            for sides in (
                tuple(
                    (
                        bsp.planes[bsp.brush_sides[side_index].plane_index].normal,
                        bsp.planes[bsp.brush_sides[side_index].plane_index].distance,
                        side_index,
                    )
                    for side_index in range(brush.first_side, brush.first_side + brush.num_sides)
                ),
            )
        )

    def _candidate_leaf_indices(self, start: Vector3, end: Vector3) -> tuple[int, ...] | None:
        if not self._bsp.leafs:
            return ()
        if not self._bsp.nodes:
            return (0,) if len(self._bsp.leafs) == 1 else None

        leaves: list[int] = []
        seen_leaves: set[int] = set()
        stack: list[tuple[int, Vector3, Vector3]] = [(0, start, end)]
        visited_nodes: set[int] = set()
        while stack:
            node_index, segment_start, segment_end = stack.pop()
            while node_index >= 0:
                if node_index in visited_nodes or node_index >= len(self._bsp.nodes):
                    return None
                visited_nodes.add(node_index)
                node = self._bsp.nodes[node_index]
                plane = self._bsp.planes[node.plane_index]
                start_distance = _dot(segment_start, plane.normal) - plane.distance
                end_distance = _dot(segment_end, plane.normal) - plane.distance
                if (
                    start_distance >= BSP_TREE_POINT_EPSILON
                    and end_distance >= BSP_TREE_POINT_EPSILON
                ):
                    node_index = node.children[0]
                    continue
                if (
                    start_distance < -BSP_TREE_POINT_EPSILON
                    and end_distance < -BSP_TREE_POINT_EPSILON
                ):
                    node_index = node.children[1]
                    continue

                if start_distance < end_distance:
                    inverse_distance = 1.0 / (start_distance - end_distance)
                    side = 1
                    # ET:L CM_TraceThroughTree uses the same fraction twice in
                    # this direction when the traced shape is a point (offset=0).
                    near_fraction = (start_distance + SURFACE_CLIP_EPSILON) * inverse_distance
                    far_fraction = near_fraction
                elif start_distance > end_distance:
                    inverse_distance = 1.0 / (start_distance - end_distance)
                    side = 0
                    # ET:L deliberately overlaps the two point segments by the
                    # 2*epsilon slab here so boundary geometry cannot be missed.
                    near_fraction = (start_distance + SURFACE_CLIP_EPSILON) * inverse_distance
                    far_fraction = (start_distance - SURFACE_CLIP_EPSILON) * inverse_distance
                else:
                    side = 0
                    near_fraction = 1.0
                    far_fraction = 0.0

                near_fraction = min(1.0, max(0.0, near_fraction))
                far_fraction = min(1.0, max(0.0, far_fraction))
                near_point = _lerp(segment_start, segment_end, near_fraction)
                far_point = _lerp(segment_start, segment_end, far_fraction)
                stack.append((node.children[side ^ 1], far_point, segment_end))
                node_index = node.children[side]
                segment_end = near_point

            leaf_index = -node_index - 1
            if leaf_index >= len(self._bsp.leafs):
                return None
            if leaf_index not in seen_leaves:
                seen_leaves.add(leaf_index)
                leaves.append(leaf_index)
        return tuple(leaves)

    def _trace_brush(self, brush_index: int, start: Vector3, end: Vector3) -> _BrushHit | None:
        brush = self._trace_brushes[brush_index]
        # ET:L never traces zero-side brushes. Treating an empty conjunction as
        # solid would make a malformed/custom-map brush block the whole world.
        if not brush.sides:
            return None
        enter_fraction = -1.0
        leave_fraction = 1.0
        lead_side: int | None = None
        start_out = False
        get_out = False

        for normal, distance, side_index in brush.sides:
            start_distance = _dot(start, normal) - distance
            end_distance = _dot(end, normal) - distance
            get_out = get_out or end_distance > 0.0
            start_out = start_out or start_distance > 0.0

            if start_distance > 0.0 and (
                end_distance >= SURFACE_CLIP_EPSILON or end_distance >= start_distance
            ):
                return None
            if start_distance <= 0.0 and end_distance <= 0.0:
                continue

            denominator = start_distance - end_distance
            if start_distance > end_distance:
                fraction = max(0.0, (start_distance - SURFACE_CLIP_EPSILON) / denominator)
                if fraction > enter_fraction:
                    enter_fraction = fraction
                    lead_side = side_index
            else:
                fraction = min(1.0, (start_distance + SURFACE_CLIP_EPSILON) / denominator)
                leave_fraction = min(leave_fraction, fraction)

        if not start_out:
            return _BrushHit(0.0, start_solid=True, all_solid=not get_out, side_index=None)
        if enter_fraction < leave_fraction and -1.0 < enter_fraction < 1.0:
            return _BrushHit(max(0.0, enter_fraction), False, False, lead_side)
        return None

    def _candidate_references(
        self,
        leaf_indices: tuple[int, ...],
    ) -> tuple[tuple[str, int], ...]:
        references: list[tuple[str, int]] = []
        seen_brushes: set[int] = set()
        seen_surfaces: set[int] = set()
        for leaf_index in leaf_indices:
            leaf = self._bsp.leafs[leaf_index]
            for brush_index in self._bsp.leaf_brushes[
                leaf.first_leaf_brush : leaf.first_leaf_brush + leaf.num_leaf_brushes
            ]:
                if brush_index not in seen_brushes:
                    seen_brushes.add(brush_index)
                    references.append(("brush", brush_index))
            for surface_index in self._bsp.leaf_surfaces[
                leaf.first_leaf_surface : leaf.first_leaf_surface + leaf.num_leaf_surfaces
            ]:
                if surface_index not in seen_surfaces:
                    seen_surfaces.add(surface_index)
                    references.append(("surface", surface_index))
        return tuple(references)

    def _candidate_indices(
        self,
        leaf_indices: tuple[int, ...],
    ) -> tuple[tuple[int, ...], tuple[int, ...]]:
        references = self._candidate_references(leaf_indices)
        return (
            tuple(index for kind, index in references if kind == "brush"),
            tuple(index for kind, index in references if kind == "surface"),
        )

    def _trace_patch_surface(
        self,
        surface_index: int,
        start: Vector3,
        end: Vector3,
        trace_mask: TraceMask,
        max_fraction: float,
    ) -> tuple[tuple[float, int, int] | None, tuple[int, float | None] | None, int, int]:
        surface = self._bsp.surfaces[surface_index]
        if surface.surface_type is not SurfaceType.PATCH:
            return None, None, 0, 0
        shader = self._bsp.shaders[surface.shader_index]
        if not shader.content_flags & trace_mask.content_bits:
            return None, None, 0, 0
        collision = self._patch_collisions.get(surface_index)
        if collision is None:
            bounds = self._patch_control_bounds[surface_index]
            bounds_fraction = None if bounds is None else _segment_bounds_fraction(start, end, bounds)
            uncertain = (
                (surface_index, bounds_fraction)
                if bounds is None or bounds_fraction is not None
                else None
            )
            return None, uncertain, 1, 0
        if collision.bounds is None:
            return None, (surface_index, None), 1, 0
        bounds_fraction = _segment_bounds_fraction(start, end, collision.bounds)
        if bounds_fraction is None:
            return None, None, 1, 0
        if collision.error is not None:
            return None, (surface_index, bounds_fraction), 1, 0
        hit, facet_count = trace_patch_point(
            collision,
            start,
            end,
            surface_clip_epsilon=SURFACE_CLIP_EPSILON,
            max_fraction=max_fraction,
        )
        resolved_hit = (
            None if hit is None else (hit.fraction, surface_index, hit.facet_index)
        )
        return resolved_hit, None, 1, facet_count

    def trace_segment(
        self,
        start: Vector3,
        end: Vector3,
        *,
        trace_mask: TraceMask = LINE_OF_SIGHT_MASK,
    ) -> PointTraceResult:
        """Trace one point segment and fail closed on unresolved collision."""
        _validate_point(start, "start")
        _validate_point(end, "end")
        if not trace_mask.name or trace_mask.content_bits <= 0:
            raise ValueError("trace_mask must have a name and positive content bits")

        leaf_indices = self._candidate_leaf_indices(start, end)
        if leaf_indices is None:
            return PointTraceResult(
                status=TraceStatus.INDETERMINATE,
                reason=TraceReason.INVALID_BSP_TREE,
                trace_mask=trace_mask,
                fraction=None,
                start_solid=False,
                all_solid=False,
                brush_index=None,
                brush_side_index=None,
                surface_index=None,
                patch_facet_index=None,
                uncertain_surface_indices=(),
                uncertain_entity_indices=(),
                uncertainty_reasons=(TraceReason.INVALID_BSP_TREE,),
                visited_leaf_count=0,
                tested_brush_count=0,
                tested_patch_count=0,
                tested_patch_facet_count=0,
            )
        if not leaf_indices:
            return PointTraceResult(
                status=TraceStatus.INDETERMINATE,
                reason=TraceReason.MISSING_BSP_TREE,
                trace_mask=trace_mask,
                fraction=None,
                start_solid=False,
                all_solid=False,
                brush_index=None,
                brush_side_index=None,
                surface_index=None,
                patch_facet_index=None,
                uncertain_surface_indices=(),
                uncertain_entity_indices=(),
                uncertainty_reasons=(TraceReason.MISSING_BSP_TREE,),
                visited_leaf_count=0,
                tested_brush_count=0,
                tested_patch_count=0,
                tested_patch_facet_count=0,
            )

        candidate_references = self._candidate_references(leaf_indices)
        closest_fraction = 1.0
        selected_kind: str | None = None
        selected_brush: tuple[int, _BrushHit] | None = None
        selected_patch: tuple[int, int] | None = None
        uncertain_patch_indices: list[int] = []
        start_solid = False
        all_solid = False
        tested_brush_count = 0
        tested_patch_count = 0
        tested_patch_facet_count = 0
        for candidate_kind, candidate_index in candidate_references:
            if candidate_kind == "surface":
                patch_hit, uncertain, surface_count, facet_count = self._trace_patch_surface(
                    candidate_index,
                    start,
                    end,
                    trace_mask,
                    closest_fraction,
                )
                tested_patch_count += surface_count
                tested_patch_facet_count += facet_count
                if uncertain is not None:
                    surface_index, bounds_fraction = uncertain
                    if selected_kind is None or bounds_fraction is None or bounds_fraction <= closest_fraction:
                        uncertain_patch_indices.append(surface_index)
                if patch_hit is not None and patch_hit[0] < closest_fraction:
                    closest_fraction, surface_index, facet_index = patch_hit
                    selected_kind = "surface"
                    selected_patch = (surface_index, facet_index)
                    selected_brush = None
                continue

            brush_index = candidate_index
            brush = self._trace_brushes[brush_index]
            if not brush.content_flags & trace_mask.content_bits:
                continue
            if brush.broadphase_bounds is not None and _segment_bounds_fraction(
                start,
                end,
                brush.broadphase_bounds,
            ) is None:
                continue
            tested_brush_count += 1
            hit = self._trace_brush(brush_index, start, end)
            if hit is None:
                continue
            start_solid = start_solid or hit.start_solid
            all_solid = all_solid or hit.all_solid
            if hit.fraction < closest_fraction:
                closest_fraction = hit.fraction
                selected_kind = "brush"
                selected_brush = (brush_index, hit)
                selected_patch = None
            elif hit.fraction == closest_fraction == 0.0 and (
                selected_kind == "brush" or hit.all_solid
            ):
                if selected_brush is None or (hit.all_solid and not selected_brush[1].all_solid):
                    selected_brush = (brush_index, hit)
                selected_kind = "brush"
                selected_patch = None

        patch_indices = tuple(uncertain_patch_indices)
        if patch_indices and selected_kind is not None:
            return PointTraceResult(
                status=TraceStatus.BLOCKED,
                reason=TraceReason.STATIC_GEOMETRY_BLOCKED,
                trace_mask=trace_mask,
                fraction=None,
                start_solid=start_solid,
                all_solid=all_solid,
                brush_index=None,
                brush_side_index=None,
                surface_index=None,
                patch_facet_index=None,
                uncertain_surface_indices=patch_indices,
                uncertain_entity_indices=(),
                uncertainty_reasons=(TraceReason.SOLID_PATCH_UNCOMPILED,),
                visited_leaf_count=len(leaf_indices),
                tested_brush_count=tested_brush_count,
                tested_patch_count=tested_patch_count,
                tested_patch_facet_count=tested_patch_facet_count,
            )

        if selected_kind == "surface" and selected_patch is not None:
            surface_index, facet_index = selected_patch
            return PointTraceResult(
                status=TraceStatus.BLOCKED,
                reason=TraceReason.SOLID_PATCH,
                trace_mask=trace_mask,
                fraction=closest_fraction,
                start_solid=start_solid,
                all_solid=all_solid,
                brush_index=None,
                brush_side_index=None,
                surface_index=surface_index,
                patch_facet_index=facet_index,
                uncertain_surface_indices=(),
                uncertain_entity_indices=(),
                uncertainty_reasons=(),
                visited_leaf_count=len(leaf_indices),
                tested_brush_count=tested_brush_count,
                tested_patch_count=tested_patch_count,
                tested_patch_facet_count=tested_patch_facet_count,
            )

        if selected_kind == "brush" and selected_brush is not None:
            brush_index, hit = selected_brush
            return PointTraceResult(
                status=TraceStatus.BLOCKED,
                reason=TraceReason.SOLID_BRUSH,
                trace_mask=trace_mask,
                fraction=closest_fraction,
                start_solid=start_solid,
                all_solid=all_solid,
                brush_index=brush_index,
                brush_side_index=hit.side_index,
                surface_index=None,
                patch_facet_index=None,
                uncertain_surface_indices=(),
                uncertain_entity_indices=(),
                uncertainty_reasons=(),
                visited_leaf_count=len(leaf_indices),
                tested_brush_count=tested_brush_count,
                tested_patch_count=tested_patch_count,
                tested_patch_facet_count=tested_patch_facet_count,
            )
        # Catalog bounds are not timestamped world transforms. Until W5
        # supplies those transforms, every dynamic inline model can have moved
        # into the segment and must keep a non-blocked result indeterminate.
        entity_indices = tuple(entity.entity_index for entity in self._collision_entities)
        reasons: list[TraceReason] = []
        if patch_indices:
            reasons.append(TraceReason.SOLID_PATCH_UNCOMPILED)
        if entity_indices:
            reasons.append(TraceReason.DYNAMIC_ENTITY_STATE_UNRESOLVED)
        if self._runtime_entity_completeness is RuntimeGeometryCoverage.UNVERIFIED:
            reasons.append(TraceReason.RUNTIME_ENTITY_COMPLETENESS_UNVERIFIED)
        if self._collision_entities and self._runtime_entity_state is RuntimeGeometryCoverage.UNVERIFIED:
            reasons.append(TraceReason.RUNTIME_ENTITY_STATE_UNVERIFIED)

        if reasons:
            return PointTraceResult(
                status=TraceStatus.INDETERMINATE,
                reason=reasons[0],
                trace_mask=trace_mask,
                fraction=None,
                start_solid=False,
                all_solid=False,
                brush_index=None,
                brush_side_index=None,
                surface_index=None,
                patch_facet_index=None,
                uncertain_surface_indices=patch_indices,
                uncertain_entity_indices=entity_indices,
                uncertainty_reasons=tuple(reasons),
                visited_leaf_count=len(leaf_indices),
                tested_brush_count=tested_brush_count,
                tested_patch_count=tested_patch_count,
                tested_patch_facet_count=tested_patch_facet_count,
            )

        return PointTraceResult(
            status=TraceStatus.CLEAR,
            reason=TraceReason.STATIC_GEOMETRY_CLEAR,
            trace_mask=trace_mask,
            fraction=1.0,
            start_solid=False,
            all_solid=False,
            brush_index=None,
            brush_side_index=None,
            surface_index=None,
            patch_facet_index=None,
            uncertain_surface_indices=(),
            uncertain_entity_indices=(),
            uncertainty_reasons=(),
            visited_leaf_count=len(leaf_indices),
            tested_brush_count=tested_brush_count,
            tested_patch_count=tested_patch_count,
            tested_patch_facet_count=tested_patch_facet_count,
        )

    def trace_line_of_sight_availability(
        self,
        observer_origin: Vector3,
        observer_stance: PlayerStance | None,
        target_origin: Vector3,
        target_stance: PlayerStance | None,
    ) -> LineOfSightAvailability:
        """Trace the frozen target-body set using an any-clear availability rule."""
        _validate_point(observer_origin, "observer_origin")
        _validate_point(target_origin, "target_origin")
        if observer_stance is None or target_stance is None:
            return LineOfSightAvailability(
                status=TraceStatus.INDETERMINATE,
                reason=TraceReason.MISSING_STANCE,
                observer_eye=None,
                endpoints=(),
                trace_mask=LINE_OF_SIGHT_MASK,
            )

        observer_eye = player_eye_point(observer_origin, observer_stance)
        endpoints = tuple(
            EndpointTrace(
                label=target.label,
                point=target.point,
                result=self.trace_segment(observer_eye, target.point, trace_mask=LINE_OF_SIGHT_MASK),
            )
            for target in target_body_points(target_origin, target_stance)
        )
        if any(endpoint.result.status is TraceStatus.CLEAR for endpoint in endpoints):
            status = TraceStatus.CLEAR
            reason = TraceReason.STATIC_GEOMETRY_CLEAR
        elif all(endpoint.result.status is TraceStatus.BLOCKED for endpoint in endpoints):
            status = TraceStatus.BLOCKED
            reason = TraceReason.STATIC_GEOMETRY_BLOCKED
        else:
            status = TraceStatus.INDETERMINATE
            reason = next(
                endpoint.result.reason
                for endpoint in endpoints
                if endpoint.result.status is TraceStatus.INDETERMINATE
            )
        return LineOfSightAvailability(
            status=status,
            reason=reason,
            observer_eye=observer_eye,
            endpoints=endpoints,
            trace_mask=LINE_OF_SIGHT_MASK,
        )
