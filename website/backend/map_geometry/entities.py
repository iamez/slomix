"""Typed W3 extraction from an ET BSP entity lump.

Objective geometry is retained as the exact union of convex BSP brushes. The
model AABB is retained as provenance, but it is not substituted for or allowed
to reject the brush-plane result. Dynamic entity state is deliberately not
inferred here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from website.backend.map_geometry.bsp import BspFile

Vector3 = tuple[float, float, float]
CollisionEntityKind = Literal[
    "door",
    "mover",
    "conditional_static",
    "static_brush",
    "constructible",
    "destructible",
]

_SPAWN_TEAMS = {
    "team_CTF_bluespawn": "ALLIES",
    "team_CTF_redspawn": "AXIS",
}
_DYNAMIC_CLASSES = {
    "func_door": "door",
    "func_door_rotating": "door",
    "script_mover": "mover",
    "func_rotating": "mover",
    "func_bobbing": "mover",
    "func_button": "mover",
    "func_static": "conditional_static",
    "func_leaky": "static_brush",
    "func_constructible": "constructible",
    "func_explosive": "destructible",
}


class EntityExtractionError(ValueError):
    """A W3 entity cannot be represented without inventing geometry."""


class ObjectiveGeometrySource(StrEnum):
    """Whether an objective shape is measured or a display-only legacy guess."""

    MEASURED_BSP_VOLUME = "measured_bsp_volume"
    LEGACY_GUESS = "legacy_guess"


@dataclass(frozen=True, slots=True)
class Bounds3D:
    mins: Vector3
    maxs: Vector3

    def translated(self, offset: Vector3) -> Bounds3D:
        return Bounds3D(
            mins=tuple(self.mins[index] + offset[index] for index in range(3)),
            maxs=tuple(self.maxs[index] + offset[index] for index in range(3)),
        )

    def contains(self, point: Vector3, *, epsilon: float = 1e-6) -> bool:
        return all(self.mins[index] - epsilon <= point[index] <= self.maxs[index] + epsilon for index in range(3))


@dataclass(frozen=True, slots=True)
class VolumePlane:
    """World-space half-space: points inside satisfy ``normal · p <= distance``."""

    source_plane_index: int
    normal: Vector3
    distance: float

    def contains(self, point: Vector3, *, epsilon: float = 1e-6) -> bool:
        projection = sum(self.normal[index] * point[index] for index in range(3))
        return projection <= self.distance + epsilon


@dataclass(frozen=True, slots=True)
class ConvexBrushVolume:
    brush_index: int
    shader_index: int
    shader_name: str
    content_flags: int
    planes: tuple[VolumePlane, ...]

    def contains(self, point: Vector3, *, epsilon: float = 1e-6) -> bool:
        return bool(self.planes) and all(plane.contains(point, epsilon=epsilon) for plane in self.planes)


@dataclass(frozen=True, slots=True)
class InlineModelGeometry:
    """BSP-local geometry plus its entity-lump origin translation.

    ``origin_translated_bounds`` is not a runtime world-space AABB for an entity
    that rotates or moves. W4 must apply the observed runtime transform or
    return an indeterminate collision result.
    """

    model_index: int
    origin: Vector3
    local_bounds: Bounds3D
    origin_translated_bounds: Bounds3D
    brush_indices: tuple[int, ...]
    surface_indices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class SpawnPoint:
    entity_index: int
    classname: str
    team: Literal["AXIS", "ALLIES"]
    origin: Vector3
    angle_degrees: float | None
    spawn_flags: int
    entity_id: str | None
    target_name: str | None
    script_name: str | None
    description: str | None
    properties: tuple[tuple[str, str], ...]
    source: str = "bsp_entity_lump"


@dataclass(frozen=True, slots=True)
class ObjectiveVolume:
    entity_index: int
    classname: str
    model: InlineModelGeometry
    brushes: tuple[ConvexBrushVolume, ...]
    spawn_flags: int
    objective_flags: int
    short_name: str | None
    track: str | None
    target: str | None
    target_name: str | None
    script_name: str | None
    properties: tuple[tuple[str, str], ...]
    source: ObjectiveGeometrySource = ObjectiveGeometrySource.MEASURED_BSP_VOLUME

    def contains_point(self, point: Vector3, *, epsilon: float = 1e-6) -> bool:
        """Return exact point containment in the union of entity brushes."""

        return any(brush.contains(point, epsilon=epsilon) for brush in self.brushes)


@dataclass(frozen=True, slots=True)
class ObjectiveMarker:
    entity_index: int
    classname: str
    origin: Vector3
    spawn_flags: int
    description: str | None
    objective: str | None
    target: str | None
    target_name: str | None
    script_name: str | None
    properties: tuple[tuple[str, str], ...]
    source: str = "bsp_entity_lump"


@dataclass(frozen=True, slots=True)
class CollisionBrushEntity:
    entity_index: int
    classname: str
    kind: CollisionEntityKind
    model: InlineModelGeometry
    spawn_flags: int
    angle_degrees: float | None
    angles: Vector3 | None
    degrees: float | None
    target: str | None
    target_name: str | None
    script_name: str | None
    properties: tuple[tuple[str, str], ...]
    source: str = "bsp_entity_lump"
    runtime_state: str = "unresolved"


@dataclass(frozen=True, slots=True)
class MapEntityCatalog:
    map_name: str
    bsp_source: str
    spawn_points: tuple[SpawnPoint, ...]
    objective_volumes: tuple[ObjectiveVolume, ...]
    objective_markers: tuple[ObjectiveMarker, ...]
    collision_entities: tuple[CollisionBrushEntity, ...]
    entity_source: str = "bsp_entity_lump"
    runtime_entity_completeness: str = "unverified"


def _error(bsp: BspFile, entity_index: int, classname: str, message: str) -> EntityExtractionError:
    source = f"{bsp.source}: " if bsp.source else ""
    return EntityExtractionError(f"{source}entity {entity_index} ({classname}): {message}")


def _properties(entity: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(entity.items())


def _parse_float(
    bsp: BspFile,
    entity_index: int,
    classname: str,
    key: str,
    raw: str,
) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise _error(bsp, entity_index, classname, f"{key} is not numeric: {raw!r}") from exc
    if not math.isfinite(value):
        raise _error(bsp, entity_index, classname, f"{key} is not finite: {raw!r}")
    return value


def _parse_optional_float(
    bsp: BspFile,
    entity_index: int,
    entity: dict[str, str],
    key: str,
) -> float | None:
    raw = entity.get(key)
    if raw is None:
        return None
    return _parse_float(bsp, entity_index, entity.get("classname", ""), key, raw)


def _parse_vector(
    bsp: BspFile,
    entity_index: int,
    entity: dict[str, str],
    key: str,
    *,
    required: bool,
    default: Vector3 = (0.0, 0.0, 0.0),
) -> Vector3:
    raw = entity.get(key)
    classname = entity.get("classname", "")
    if raw is None:
        if required:
            raise _error(bsp, entity_index, classname, f"missing required {key}")
        return default
    pieces = raw.split()
    if len(pieces) != 3:
        raise _error(bsp, entity_index, classname, f"{key} must contain three coordinates: {raw!r}")
    return tuple(
        _parse_float(bsp, entity_index, classname, f"{key}[{index}]", piece) for index, piece in enumerate(pieces)
    )


def _parse_int(
    bsp: BspFile,
    entity_index: int,
    entity: dict[str, str],
    key: str,
    *,
    default: int = 0,
) -> int:
    raw = entity.get(key)
    if raw is None:
        return default
    try:
        return int(raw, 10)
    except ValueError as exc:
        raise _error(
            bsp,
            entity_index,
            entity.get("classname", ""),
            f"{key} is not a base-10 integer: {raw!r}",
        ) from exc


def _inline_model(
    bsp: BspFile,
    entity_index: int,
    entity: dict[str, str],
) -> InlineModelGeometry:
    classname = entity.get("classname", "")
    raw_model = entity.get("model")
    if raw_model is None or not raw_model.startswith("*") or not raw_model[1:].isdigit():
        raise _error(bsp, entity_index, classname, f"invalid inline model reference: {raw_model!r}")
    model_index = int(raw_model[1:])
    if model_index == 0 or model_index >= len(bsp.models):
        raise _error(
            bsp,
            entity_index,
            classname,
            f"inline model {model_index} is outside entity model range 1..{len(bsp.models) - 1}",
        )

    origin = _parse_vector(bsp, entity_index, entity, "origin", required=False)
    model = bsp.models[model_index]
    local_bounds = Bounds3D(model.mins, model.maxs)
    if any(not math.isfinite(value) for value in (*local_bounds.mins, *local_bounds.maxs)):
        raise _error(bsp, entity_index, classname, "inline model bounds are not finite")
    if any(local_bounds.mins[index] >= local_bounds.maxs[index] for index in range(3)):
        raise _error(bsp, entity_index, classname, "inline model has empty or inverted bounds")

    return InlineModelGeometry(
        model_index=model_index,
        origin=origin,
        local_bounds=local_bounds,
        origin_translated_bounds=local_bounds.translated(origin),
        brush_indices=tuple(range(model.first_brush, model.first_brush + model.num_brushes)),
        surface_indices=tuple(range(model.first_surface, model.first_surface + model.num_surfaces)),
    )


def _brush_volume(
    bsp: BspFile,
    entity_index: int,
    classname: str,
    brush_index: int,
    origin: Vector3,
) -> ConvexBrushVolume:
    brush = bsp.brushes[brush_index]
    if brush.num_sides < 4:
        raise _error(
            bsp,
            entity_index,
            classname,
            f"brush {brush_index} has only {brush.num_sides} sides",
        )

    planes: list[VolumePlane] = []
    for side_index in range(brush.first_side, brush.first_side + brush.num_sides):
        plane_index = bsp.brush_sides[side_index].plane_index
        plane = bsp.planes[plane_index]
        values = (*plane.normal, plane.distance)
        if any(not math.isfinite(value) for value in values):
            raise _error(
                bsp,
                entity_index,
                classname,
                f"brush {brush_index} plane {plane_index} is not finite",
            )
        translated_distance = plane.distance + sum(plane.normal[index] * origin[index] for index in range(3))
        planes.append(
            VolumePlane(
                source_plane_index=plane_index,
                normal=plane.normal,
                distance=translated_distance,
            )
        )

    shader = bsp.shaders[brush.shader_index]
    return ConvexBrushVolume(
        brush_index=brush_index,
        shader_index=brush.shader_index,
        shader_name=shader.name,
        content_flags=shader.content_flags,
        planes=tuple(planes),
    )


def _extract_spawn(
    bsp: BspFile,
    entity_index: int,
    entity: dict[str, str],
) -> SpawnPoint:
    classname = entity["classname"]
    return SpawnPoint(
        entity_index=entity_index,
        classname=classname,
        team=_SPAWN_TEAMS[classname],
        origin=_parse_vector(bsp, entity_index, entity, "origin", required=True),
        angle_degrees=_parse_optional_float(bsp, entity_index, entity, "angle"),
        spawn_flags=_parse_int(bsp, entity_index, entity, "spawnflags"),
        entity_id=entity.get("id"),
        target_name=entity.get("targetname"),
        script_name=entity.get("scriptname"),
        description=entity.get("description"),
        properties=_properties(entity),
    )


def _extract_objective_volume(
    bsp: BspFile,
    entity_index: int,
    entity: dict[str, str],
) -> ObjectiveVolume:
    classname = entity["classname"]
    angle = _parse_optional_float(bsp, entity_index, entity, "angle")
    angles = _parse_vector(bsp, entity_index, entity, "angles", required=False) if "angles" in entity else None
    if (angle is not None and angle != 0.0) or (angles is not None and any(value != 0.0 for value in angles)):
        raise _error(
            bsp,
            entity_index,
            classname,
            "rotated objective brush volumes are unsupported",
        )

    model = _inline_model(bsp, entity_index, entity)
    if not model.brush_indices:
        raise _error(bsp, entity_index, classname, "objective inline model has no brushes")
    brushes = tuple(
        _brush_volume(bsp, entity_index, classname, brush_index, model.origin) for brush_index in model.brush_indices
    )
    return ObjectiveVolume(
        entity_index=entity_index,
        classname=classname,
        model=model,
        brushes=brushes,
        spawn_flags=_parse_int(bsp, entity_index, entity, "spawnflags"),
        objective_flags=_parse_int(bsp, entity_index, entity, "objflags"),
        short_name=entity.get("shortname"),
        track=entity.get("track"),
        target=entity.get("target"),
        target_name=entity.get("targetname"),
        script_name=entity.get("scriptname"),
        properties=_properties(entity),
    )


def _extract_objective_marker(
    bsp: BspFile,
    entity_index: int,
    entity: dict[str, str],
) -> ObjectiveMarker:
    return ObjectiveMarker(
        entity_index=entity_index,
        classname=entity["classname"],
        origin=_parse_vector(bsp, entity_index, entity, "origin", required=True),
        spawn_flags=_parse_int(bsp, entity_index, entity, "spawnflags"),
        description=entity.get("description"),
        objective=entity.get("objective"),
        target=entity.get("target"),
        target_name=entity.get("targetname"),
        script_name=entity.get("scriptname"),
        properties=_properties(entity),
    )


def _extract_collision_entity(
    bsp: BspFile,
    entity_index: int,
    entity: dict[str, str],
) -> CollisionBrushEntity:
    classname = entity["classname"]
    angles = _parse_vector(bsp, entity_index, entity, "angles", required=False) if "angles" in entity else None
    return CollisionBrushEntity(
        entity_index=entity_index,
        classname=classname,
        kind=_DYNAMIC_CLASSES[classname],
        model=_inline_model(bsp, entity_index, entity),
        spawn_flags=_parse_int(bsp, entity_index, entity, "spawnflags"),
        angle_degrees=_parse_optional_float(bsp, entity_index, entity, "angle"),
        angles=angles,
        degrees=_parse_optional_float(bsp, entity_index, entity, "degrees"),
        target=entity.get("target"),
        target_name=entity.get("targetname"),
        script_name=entity.get("scriptname"),
        properties=_properties(entity),
    )


def extract_entity_catalog(bsp: BspFile, map_name: str) -> MapEntityCatalog:
    """Extract W3 entities from one already validated BSP."""

    normalised_map_name = map_name.strip().casefold().removesuffix(".bsp")
    if not normalised_map_name or "/" in normalised_map_name or "\\" in normalised_map_name:
        raise ValueError(f"invalid ET map name: {map_name!r}")

    spawn_points: list[SpawnPoint] = []
    objective_volumes: list[ObjectiveVolume] = []
    objective_markers: list[ObjectiveMarker] = []
    collision_entities: list[CollisionBrushEntity] = []

    for entity_index, entity in enumerate(bsp.entities):
        classname = entity.get("classname")
        if classname in _SPAWN_TEAMS:
            spawn_points.append(_extract_spawn(bsp, entity_index, entity))
        elif classname == "trigger_objective_info":
            objective_volumes.append(_extract_objective_volume(bsp, entity_index, entity))
        elif classname == "team_WOLF_objective":
            objective_markers.append(_extract_objective_marker(bsp, entity_index, entity))
        elif classname in _DYNAMIC_CLASSES:
            collision_entities.append(_extract_collision_entity(bsp, entity_index, entity))

    return MapEntityCatalog(
        map_name=normalised_map_name,
        bsp_source=bsp.source,
        spawn_points=tuple(spawn_points),
        objective_volumes=tuple(objective_volumes),
        objective_markers=tuple(objective_markers),
        collision_entities=tuple(collision_entities),
    )


def entity_catalog_manifest(catalog: MapEntityCatalog) -> dict:
    """Return a JSON-compatible W3 publication with raw BSP provenance.

    Callers producing cross-machine hashes must replace ``bsp_source`` with a
    stable path relative to the indexed asset root, as the W3 analyzer does.
    """

    def vector(value: Vector3) -> list[float]:
        return list(value)

    def bounds(value: Bounds3D) -> dict:
        return {"mins": vector(value.mins), "maxs": vector(value.maxs)}

    def model(value: InlineModelGeometry) -> dict:
        return {
            "model_index": value.model_index,
            "origin": vector(value.origin),
            "local_bounds": bounds(value.local_bounds),
            "origin_translated_bounds": bounds(value.origin_translated_bounds),
            "brush_indices": list(value.brush_indices),
            "surface_indices": list(value.surface_indices),
        }

    return {
        "map_name": catalog.map_name,
        "status": "measured",
        "bsp_source": catalog.bsp_source,
        "entity_source": catalog.entity_source,
        "runtime_entity_completeness": catalog.runtime_entity_completeness,
        "spawn_points": [
            {
                "entity_index": item.entity_index,
                "source": item.source,
                "classname": item.classname,
                "team": item.team,
                "origin": vector(item.origin),
                "angle_degrees": item.angle_degrees,
                "spawn_flags": item.spawn_flags,
                "id": item.entity_id,
                "target_name": item.target_name,
                "script_name": item.script_name,
                "description": item.description,
                "properties": dict(item.properties),
            }
            for item in catalog.spawn_points
        ],
        "objective_volumes": [
            {
                "entity_index": item.entity_index,
                "source": item.source.value,
                "classname": item.classname,
                "model": model(item.model),
                "brushes": [
                    {
                        "brush_index": brush.brush_index,
                        "shader_index": brush.shader_index,
                        "shader_name": brush.shader_name,
                        "content_flags": brush.content_flags,
                        "planes": [
                            {
                                "source_plane_index": plane.source_plane_index,
                                "normal": vector(plane.normal),
                                "distance": plane.distance,
                            }
                            for plane in brush.planes
                        ],
                    }
                    for brush in item.brushes
                ],
                "spawn_flags": item.spawn_flags,
                "objective_flags": item.objective_flags,
                "short_name": item.short_name,
                "track": item.track,
                "target": item.target,
                "target_name": item.target_name,
                "script_name": item.script_name,
                "properties": dict(item.properties),
            }
            for item in catalog.objective_volumes
        ],
        "objective_markers": [
            {
                "entity_index": item.entity_index,
                "source": item.source,
                "classname": item.classname,
                "origin": vector(item.origin),
                "spawn_flags": item.spawn_flags,
                "description": item.description,
                "objective": item.objective,
                "target": item.target,
                "target_name": item.target_name,
                "script_name": item.script_name,
                "properties": dict(item.properties),
            }
            for item in catalog.objective_markers
        ],
        "collision_entities": [
            {
                "entity_index": item.entity_index,
                "source": item.source,
                "runtime_state": item.runtime_state,
                "classname": item.classname,
                "kind": item.kind,
                "model": model(item.model),
                "spawn_flags": item.spawn_flags,
                "angle_degrees": item.angle_degrees,
                "angles": vector(item.angles) if item.angles is not None else None,
                "degrees": item.degrees,
                "target": item.target,
                "target_name": item.target_name,
                "script_name": item.script_name,
                "properties": dict(item.properties),
            }
            for item in catalog.collision_entities
        ],
    }
