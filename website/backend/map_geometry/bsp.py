"""Strict, dependency-free reader for the collision-relevant ET:L ``IBSP`` v47 subset.

The binary layouts mirror ET:Legacy's compatibility-preserving ``qfiles.h``.
Content and surface flags are exposed as raw 32-bit bitfields; deciding which
contents block a particular trace is intentionally deferred to the trace
implementation.
"""

from __future__ import annotations

import struct
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

BSP_MAGIC = b"IBSP"
BSP_VERSION = 47

_HEADER = struct.Struct("<4si")
# ET:Legacy qfiles.h declares fileofs as int and filelen as unsigned int.
_LUMP = struct.Struct("<iI")
_HEADER_SIZE = _HEADER.size + (17 * _LUMP.size)

_SHADER = struct.Struct("<64sII")
_PLANE = struct.Struct("<4f")
_NODE = struct.Struct("<9i")
_LEAF = struct.Struct("<12i")
_MODEL = struct.Struct("<6f4i")
_BRUSH = struct.Struct("<3i")
_BRUSH_SIDE = struct.Struct("<2i")
_DRAW_VERTEX = struct.Struct("<10f4B")
_SURFACE = struct.Struct("<12i12f2i")
_INT32 = struct.Struct("<i")

_MAX_PATCH_VERTICES = 1024
_MAX_PATCH_GRID_SIZE = 129


class BspFormatError(ValueError):
    """The BSP is truncated, internally inconsistent, or malformed."""


class UnsupportedBspError(BspFormatError):
    """The file is not an Enemy Territory ``IBSP`` v47 BSP."""


class EntityProperties(dict[str, str]):
    """Mapping-compatible entity fields with source-ordered duplicate pairs."""

    def __init__(self, ordered_pairs: Iterable[tuple[str, str]]) -> None:
        self.ordered_pairs = tuple(ordered_pairs)
        super().__init__(self.ordered_pairs)


class LumpType(IntEnum):
    ENTITIES = 0
    SHADERS = 1
    PLANES = 2
    NODES = 3
    LEAFS = 4
    LEAF_SURFACES = 5
    LEAF_BRUSHES = 6
    MODELS = 7
    BRUSHES = 8
    BRUSH_SIDES = 9
    DRAW_VERTS = 10
    DRAW_INDEXES = 11
    FOGS = 12
    SURFACES = 13
    LIGHTMAPS = 14
    LIGHTGRID = 15
    VISIBILITY = 16


class SurfaceType(IntEnum):
    BAD = 0
    PLANAR = 1
    PATCH = 2
    TRIANGLE_SOUP = 3
    FLARE = 4
    FOLIAGE = 5


@dataclass(frozen=True, slots=True)
class BspLump:
    offset: int
    length: int


@dataclass(frozen=True, slots=True)
class BspShader:
    name: str
    surface_flags: int
    content_flags: int


@dataclass(frozen=True, slots=True)
class BspPlane:
    normal: tuple[float, float, float]
    distance: float


@dataclass(frozen=True, slots=True)
class BspNode:
    plane_index: int
    children: tuple[int, int]
    mins: tuple[int, int, int]
    maxs: tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class BspLeaf:
    cluster: int
    area: int
    mins: tuple[int, int, int]
    maxs: tuple[int, int, int]
    first_leaf_surface: int
    num_leaf_surfaces: int
    first_leaf_brush: int
    num_leaf_brushes: int


@dataclass(frozen=True, slots=True)
class BspModel:
    mins: tuple[float, float, float]
    maxs: tuple[float, float, float]
    first_surface: int
    num_surfaces: int
    first_brush: int
    num_brushes: int


@dataclass(frozen=True, slots=True)
class BspBrush:
    first_side: int
    num_sides: int
    shader_index: int


@dataclass(frozen=True, slots=True)
class BspBrushSide:
    plane_index: int
    shader_index: int


@dataclass(frozen=True, slots=True)
class BspDrawVertex:
    position: tuple[float, float, float]
    texture_coords: tuple[float, float]
    lightmap_coords: tuple[float, float]
    normal: tuple[float, float, float]
    color: tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class BspSurface:
    shader_index: int
    fog_index: int
    surface_type: SurfaceType
    first_vertex: int
    num_vertices: int
    first_index: int
    num_indexes: int
    lightmap_index: int
    lightmap_x: int
    lightmap_y: int
    lightmap_width: int
    lightmap_height: int
    lightmap_origin: tuple[float, float, float]
    lightmap_vectors: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ]
    patch_width: int
    patch_height: int


@dataclass(frozen=True, slots=True)
class BspFile:
    source: str
    byte_length: int
    lumps: tuple[BspLump, ...]
    entity_text: str
    entities: tuple[EntityProperties, ...]
    shaders: tuple[BspShader, ...]
    planes: tuple[BspPlane, ...]
    nodes: tuple[BspNode, ...]
    leafs: tuple[BspLeaf, ...]
    leaf_surfaces: tuple[int, ...]
    leaf_brushes: tuple[int, ...]
    models: tuple[BspModel, ...]
    brushes: tuple[BspBrush, ...]
    brush_sides: tuple[BspBrushSide, ...]
    draw_vertices: tuple[BspDrawVertex, ...]
    draw_indexes: tuple[int, ...]
    surfaces: tuple[BspSurface, ...]
    magic: bytes = BSP_MAGIC
    version: int = BSP_VERSION


def _context(source: str, message: str) -> str:
    return f"{source}: {message}" if source else message


def _lump_data(data: memoryview, lumps: tuple[BspLump, ...], lump_type: LumpType) -> memoryview:
    lump = lumps[lump_type]
    return data[lump.offset : lump.offset + lump.length]


def _records(
    data: memoryview,
    record: struct.Struct,
    lump_type: LumpType,
    source: str,
) -> Iterator[tuple]:
    if len(data) % record.size:
        raise BspFormatError(
            _context(
                source,
                f"{lump_type.name.lower()} lump length {len(data)} is not a multiple of {record.size}",
            )
        )
    yield from record.iter_unpack(data)


def _decode_shader_name(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("latin-1")


def _tokenize_entities(text: str, source: str) -> Iterator[str]:
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char.isspace() or char == "\0":
            index += 1
            continue
        if text.startswith("//", index):
            newline = text.find("\n", index + 2)
            index = length if newline < 0 else newline + 1
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            if end < 0:
                raise BspFormatError(_context(source, "unterminated entity comment"))
            index = end + 2
            continue
        if char in "{}":
            yield char
            index += 1
            continue
        if char == '"':
            index += 1
            value: list[str] = []
            while index < length:
                char = text[index]
                if char == '"':
                    index += 1
                    yield "".join(value)
                    break
                if char == "\\" and index + 1 < length and text[index + 1] == '"':
                    value.append('"')
                    index += 2
                    continue
                value.append(char)
                index += 1
            else:
                raise BspFormatError(_context(source, "unterminated quoted entity token"))
            continue

        start = index
        while index < length and not text[index].isspace() and text[index] not in '{}"\0':
            index += 1
        if index == start:
            raise BspFormatError(_context(source, f"unexpected entity character at offset {index}"))
        yield text[start:index]


def parse_entities(text: str, *, source: str = "") -> tuple[EntityProperties, ...]:
    """Parse Quake entities while retaining duplicate fields in source order."""
    tokens = iter(_tokenize_entities(text, source))
    entities: list[EntityProperties] = []

    while True:
        try:
            piece = next(tokens)
        except StopIteration:
            break
        if piece != "{":
            raise BspFormatError(_context(source, f"expected '{{', got {piece!r}"))

        ordered_pairs: list[tuple[str, str]] = []
        while True:
            try:
                key = next(tokens)
            except StopIteration as exc:
                raise BspFormatError(_context(source, "unterminated entity")) from exc
            if key == "}":
                entities.append(EntityProperties(ordered_pairs))
                break
            if key == "{":
                raise BspFormatError(_context(source, "nested entity opening brace"))
            try:
                value = next(tokens)
            except StopIteration as exc:
                raise BspFormatError(_context(source, f"missing value for entity key {key!r}")) from exc
            if value in {"{", "}"}:
                raise BspFormatError(_context(source, f"invalid value for entity key {key!r}"))
            ordered_pairs.append((key, value))

    return tuple(entities)


def _parse_surfaces(data: memoryview, source: str) -> tuple[BspSurface, ...]:
    surfaces: list[BspSurface] = []
    for index, values in enumerate(_records(data, _SURFACE, LumpType.SURFACES, source)):
        try:
            surface_type = SurfaceType(values[2])
        except ValueError as exc:
            raise BspFormatError(_context(source, f"surface {index} has unknown type {values[2]}")) from exc

        surfaces.append(
            BspSurface(
                shader_index=values[0],
                fog_index=values[1],
                surface_type=surface_type,
                first_vertex=values[3],
                num_vertices=values[4],
                first_index=values[5],
                num_indexes=values[6],
                lightmap_index=values[7],
                lightmap_x=values[8],
                lightmap_y=values[9],
                lightmap_width=values[10],
                lightmap_height=values[11],
                lightmap_origin=(values[12], values[13], values[14]),
                lightmap_vectors=(
                    (values[15], values[16], values[17]),
                    (values[18], values[19], values[20]),
                    (values[21], values[22], values[23]),
                ),
                patch_width=values[24],
                patch_height=values[25],
            )
        )
    return tuple(surfaces)


def _validate_span(first: int, count: int, total: int, label: str, source: str) -> None:
    if first < 0 or count < 0 or first + count > total:
        raise BspFormatError(_context(source, f"{label} span ({first}, {count}) exceeds available count {total}"))


def _validate_references(bsp: BspFile) -> None:
    source = bsp.source
    for index, side in enumerate(bsp.brush_sides):
        if not 0 <= side.plane_index < len(bsp.planes):
            raise BspFormatError(_context(source, f"brush side {index} has invalid plane {side.plane_index}"))
        if not 0 <= side.shader_index < len(bsp.shaders):
            raise BspFormatError(_context(source, f"brush side {index} has invalid shader {side.shader_index}"))

    for index, brush in enumerate(bsp.brushes):
        _validate_span(brush.first_side, brush.num_sides, len(bsp.brush_sides), f"brush {index} sides", source)
        if not 0 <= brush.shader_index < len(bsp.shaders):
            raise BspFormatError(_context(source, f"brush {index} has invalid shader {brush.shader_index}"))

    for index, leaf_brush in enumerate(bsp.leaf_brushes):
        if not 0 <= leaf_brush < len(bsp.brushes):
            raise BspFormatError(_context(source, f"leaf brush {index} references invalid brush {leaf_brush}"))

    for index, leaf_surface in enumerate(bsp.leaf_surfaces):
        if not 0 <= leaf_surface < len(bsp.surfaces):
            raise BspFormatError(_context(source, f"leaf surface {index} references invalid surface {leaf_surface}"))

    for index, leaf in enumerate(bsp.leafs):
        _validate_span(
            leaf.first_leaf_surface,
            leaf.num_leaf_surfaces,
            len(bsp.leaf_surfaces),
            f"leaf {index} surfaces",
            source,
        )
        _validate_span(
            leaf.first_leaf_brush,
            leaf.num_leaf_brushes,
            len(bsp.leaf_brushes),
            f"leaf {index} brushes",
            source,
        )

    for index, node in enumerate(bsp.nodes):
        if not 0 <= node.plane_index < len(bsp.planes):
            raise BspFormatError(_context(source, f"node {index} has invalid plane {node.plane_index}"))
        for child in node.children:
            if child >= 0 and child >= len(bsp.nodes):
                raise BspFormatError(_context(source, f"node {index} references invalid node {child}"))
            if child < 0 and (-child - 1) >= len(bsp.leafs):
                raise BspFormatError(_context(source, f"node {index} references invalid leaf {-child - 1}"))

    for index, model in enumerate(bsp.models):
        _validate_span(model.first_brush, model.num_brushes, len(bsp.brushes), f"model {index} brushes", source)
        _validate_span(
            model.first_surface,
            model.num_surfaces,
            len(bsp.surfaces),
            f"model {index} surfaces",
            source,
        )

    for index, surface in enumerate(bsp.surfaces):
        if not 0 <= surface.shader_index < len(bsp.shaders):
            raise BspFormatError(_context(source, f"surface {index} has invalid shader {surface.shader_index}"))
        _validate_span(
            surface.first_vertex,
            surface.num_vertices,
            len(bsp.draw_vertices),
            f"surface {index} vertices",
            source,
        )
        _validate_span(
            surface.first_index,
            surface.num_indexes,
            len(bsp.draw_indexes),
            f"surface {index} indexes",
            source,
        )
        for draw_index in bsp.draw_indexes[surface.first_index : surface.first_index + surface.num_indexes]:
            if not 0 <= draw_index < surface.num_vertices:
                raise BspFormatError(
                    _context(
                        source,
                        f"surface {index} draw index {draw_index} exceeds vertex count {surface.num_vertices}",
                    )
                )

        if surface.surface_type is not SurfaceType.PATCH:
            continue
        width = surface.patch_width
        height = surface.patch_height
        control_points = width * height
        if width <= 2 or height <= 2 or not width % 2 or not height % 2:
            raise BspFormatError(_context(source, f"patch surface {index} has invalid dimensions {width}x{height}"))
        if width > _MAX_PATCH_GRID_SIZE or height > _MAX_PATCH_GRID_SIZE:
            raise BspFormatError(
                _context(
                    source,
                    f"patch surface {index} dimensions {width}x{height} exceed grid maximum {_MAX_PATCH_GRID_SIZE}",
                )
            )
        if control_points > _MAX_PATCH_VERTICES:
            raise BspFormatError(
                _context(
                    source,
                    f"patch surface {index} has {control_points} control points; maximum is {_MAX_PATCH_VERTICES}",
                )
            )
        if control_points != surface.num_vertices:
            raise BspFormatError(
                _context(
                    source,
                    f"patch surface {index} dimensions require {control_points} vertices, found {surface.num_vertices}",
                )
            )


def parse_bsp(raw: bytes | bytearray | memoryview, *, source: str = "") -> BspFile:
    """Decode an ET BSP, refusing any layout other than ``IBSP`` v47."""
    data = memoryview(raw)
    if len(data) < _HEADER_SIZE:
        raise BspFormatError(_context(source, f"file is {len(data)} bytes; header requires {_HEADER_SIZE}"))

    magic, version = _HEADER.unpack_from(data)
    if magic != BSP_MAGIC:
        raise UnsupportedBspError(_context(source, f"unsupported BSP magic {magic!r}; expected {BSP_MAGIC!r}"))
    if version != BSP_VERSION:
        raise UnsupportedBspError(_context(source, f"unsupported BSP version {version}; expected {BSP_VERSION}"))

    lumps = tuple(BspLump(*_LUMP.unpack_from(data, _HEADER.size + (index * _LUMP.size))) for index in range(17))
    for index, lump in enumerate(lumps):
        if lump.offset < 0 or lump.length < 0:
            raise BspFormatError(_context(source, f"lump {LumpType(index).name} has a negative offset or length"))
        if lump.length and lump.offset < _HEADER_SIZE:
            raise BspFormatError(_context(source, f"lump {LumpType(index).name} overlaps the BSP header"))
        if lump.offset > len(data) or lump.length > len(data) - lump.offset:
            raise BspFormatError(_context(source, f"lump {LumpType(index).name} exceeds the file bounds"))

    entity_bytes = bytes(_lump_data(data, lumps, LumpType.ENTITIES))
    entity_text = entity_bytes.split(b"\0", 1)[0].decode("latin-1")
    entities = parse_entities(entity_text, source=source)

    shaders = tuple(
        BspShader(_decode_shader_name(name), surface_flags, content_flags)
        for name, surface_flags, content_flags in _records(
            _lump_data(data, lumps, LumpType.SHADERS), _SHADER, LumpType.SHADERS, source
        )
    )
    planes = tuple(
        BspPlane((nx, ny, nz), distance)
        for nx, ny, nz, distance in _records(_lump_data(data, lumps, LumpType.PLANES), _PLANE, LumpType.PLANES, source)
    )
    nodes = tuple(
        BspNode(plane, (child0, child1), (min_x, min_y, min_z), (max_x, max_y, max_z))
        for plane, child0, child1, min_x, min_y, min_z, max_x, max_y, max_z in _records(
            _lump_data(data, lumps, LumpType.NODES), _NODE, LumpType.NODES, source
        )
    )
    leafs = tuple(
        BspLeaf(
            cluster,
            area,
            (min_x, min_y, min_z),
            (max_x, max_y, max_z),
            first_surface,
            num_surfaces,
            first_brush,
            num_brushes,
        )
        for (
            cluster,
            area,
            min_x,
            min_y,
            min_z,
            max_x,
            max_y,
            max_z,
            first_surface,
            num_surfaces,
            first_brush,
            num_brushes,
        ) in _records(_lump_data(data, lumps, LumpType.LEAFS), _LEAF, LumpType.LEAFS, source)
    )
    leaf_surfaces = tuple(
        value
        for (value,) in _records(
            _lump_data(data, lumps, LumpType.LEAF_SURFACES),
            _INT32,
            LumpType.LEAF_SURFACES,
            source,
        )
    )
    leaf_brushes = tuple(
        value
        for (value,) in _records(_lump_data(data, lumps, LumpType.LEAF_BRUSHES), _INT32, LumpType.LEAF_BRUSHES, source)
    )
    models = tuple(
        BspModel((min_x, min_y, min_z), (max_x, max_y, max_z), first_surface, num_surfaces, first_brush, num_brushes)
        for (
            min_x,
            min_y,
            min_z,
            max_x,
            max_y,
            max_z,
            first_surface,
            num_surfaces,
            first_brush,
            num_brushes,
        ) in _records(_lump_data(data, lumps, LumpType.MODELS), _MODEL, LumpType.MODELS, source)
    )
    brushes = tuple(
        BspBrush(first_side, num_sides, shader)
        for first_side, num_sides, shader in _records(
            _lump_data(data, lumps, LumpType.BRUSHES), _BRUSH, LumpType.BRUSHES, source
        )
    )
    brush_sides = tuple(
        BspBrushSide(plane, shader)
        for plane, shader in _records(
            _lump_data(data, lumps, LumpType.BRUSH_SIDES), _BRUSH_SIDE, LumpType.BRUSH_SIDES, source
        )
    )
    draw_vertices = tuple(
        BspDrawVertex(
            position=(x, y, z),
            texture_coords=(texture_s, texture_t),
            lightmap_coords=(lightmap_s, lightmap_t),
            normal=(normal_x, normal_y, normal_z),
            color=(red, green, blue, alpha),
        )
        for (
            x,
            y,
            z,
            texture_s,
            texture_t,
            lightmap_s,
            lightmap_t,
            normal_x,
            normal_y,
            normal_z,
            red,
            green,
            blue,
            alpha,
        ) in _records(
            _lump_data(data, lumps, LumpType.DRAW_VERTS),
            _DRAW_VERTEX,
            LumpType.DRAW_VERTS,
            source,
        )
    )
    draw_indexes = tuple(
        value
        for (value,) in _records(
            _lump_data(data, lumps, LumpType.DRAW_INDEXES),
            _INT32,
            LumpType.DRAW_INDEXES,
            source,
        )
    )
    surfaces = _parse_surfaces(_lump_data(data, lumps, LumpType.SURFACES), source)

    bsp = BspFile(
        source=source,
        byte_length=len(data),
        lumps=lumps,
        entity_text=entity_text,
        entities=entities,
        shaders=shaders,
        planes=planes,
        nodes=nodes,
        leafs=leafs,
        leaf_surfaces=leaf_surfaces,
        leaf_brushes=leaf_brushes,
        models=models,
        brushes=brushes,
        brush_sides=brush_sides,
        draw_vertices=draw_vertices,
        draw_indexes=draw_indexes,
        surfaces=surfaces,
    )
    _validate_references(bsp)
    return bsp


def parse_bsp_file(path: str | Path) -> BspFile:
    bsp_path = Path(path)
    return parse_bsp(bsp_path.read_bytes(), source=str(bsp_path))
