"""Synthetic contract tests for the strict Enemy Territory BSP v47 reader."""

from __future__ import annotations

import struct

import pytest

from website.backend.map_geometry.bsp import (
    BspFormatError,
    LumpType,
    UnsupportedBspError,
    parse_bsp,
)

HEADER_SIZE = 8 + (17 * 8)


def _valid_lumps() -> dict[int, bytes]:
    entities = b'{\n"classname" "worldspawn"\n"message" "A \\"quoted\\" value"\n}\n\0'
    shader_name = b"textures/common/caulk".ljust(64, b"\0")
    return {
        LumpType.ENTITIES: entities,
        LumpType.SHADERS: struct.pack("<64sII", shader_name, 0x10, 0x80000001),
        LumpType.PLANES: struct.pack("<4f", 1.0, 0.0, 0.0, 64.0),
        LumpType.NODES: struct.pack("<9i", 0, -1, -1, -128, -128, -128, 128, 128, 128),
        LumpType.LEAFS: struct.pack("<12i", 0, 0, -128, -128, -128, 128, 128, 128, 0, 0, 0, 1),
        LumpType.LEAF_BRUSHES: struct.pack("<i", 0),
        LumpType.MODELS: struct.pack("<6f4i", -128, -128, -128, 128, 128, 128, 0, 0, 0, 1),
        LumpType.BRUSHES: struct.pack("<3i", 0, 1, 0),
        LumpType.BRUSH_SIDES: struct.pack("<2i", 0, 0),
    }


def _build_bsp(
    *,
    magic: bytes = b"IBSP",
    version: int = 47,
    lumps: dict[int, bytes] | None = None,
) -> bytes:
    payloads = _valid_lumps() if lumps is None else lumps
    body = bytearray()
    descriptors: list[tuple[int, int]] = []
    for index in range(17):
        payload = payloads.get(index, b"")
        descriptors.append((HEADER_SIZE + len(body), len(payload)))
        body.extend(payload)

    header = bytearray(struct.pack("<4si", magic, version))
    for offset, length in descriptors:
        header.extend(struct.pack("<ii", offset, length))
    return bytes(header + body)


def test_parse_bsp_decodes_every_w2_structure_and_raw_shader_flags():
    bsp = parse_bsp(_build_bsp(), source="synthetic.bsp")

    assert bsp.magic == b"IBSP"
    assert bsp.version == 47
    assert bsp.entities == ({"classname": "worldspawn", "message": 'A "quoted" value'},)
    assert bsp.shaders[0].name == "textures/common/caulk"
    assert bsp.shaders[0].surface_flags == 0x10
    assert bsp.shaders[0].content_flags == 0x80000001
    assert bsp.planes[0].normal == (1.0, 0.0, 0.0)
    assert bsp.nodes[0].children == (-1, -1)
    assert bsp.leafs[0].num_leaf_brushes == 1
    assert bsp.leaf_brushes == (0,)
    assert bsp.models[0].num_brushes == 1
    assert bsp.brushes[0].shader_index == 0
    assert bsp.brush_sides[0].plane_index == 0


@pytest.mark.parametrize(
    ("magic", "version", "expected"),
    [
        (b"RBSP", 47, "magic"),
        (b"IBSP", 46, "version"),
        (b"IBSP", 48, "version"),
    ],
)
def test_parse_bsp_refuses_unknown_magic_or_version(magic, version, expected):
    with pytest.raises(UnsupportedBspError, match=expected):
        parse_bsp(_build_bsp(magic=magic, version=version))


def test_parse_bsp_refuses_truncated_header():
    with pytest.raises(BspFormatError, match="header requires"):
        parse_bsp(b"IBSP" + struct.pack("<i", 47))


def test_parse_bsp_refuses_out_of_bounds_lump():
    raw = bytearray(_build_bsp())
    struct.pack_into("<ii", raw, 8, len(raw) - 2, 100)
    with pytest.raises(BspFormatError, match="exceeds the file bounds"):
        parse_bsp(raw)


def test_parse_bsp_refuses_misaligned_structured_lump():
    lumps = _valid_lumps()
    lumps[LumpType.SHADERS] += b"x"
    with pytest.raises(BspFormatError, match="shaders lump length"):
        parse_bsp(_build_bsp(lumps=lumps))


def test_parse_bsp_refuses_invalid_internal_reference():
    lumps = _valid_lumps()
    lumps[LumpType.BRUSH_SIDES] = struct.pack("<2i", 99, 0)
    with pytest.raises(BspFormatError, match="invalid plane 99"):
        parse_bsp(_build_bsp(lumps=lumps))


def test_parse_bsp_refuses_malformed_entity_text():
    lumps = _valid_lumps()
    lumps[LumpType.ENTITIES] = b'{ "classname" "worldspawn"\0'
    with pytest.raises(BspFormatError, match="unterminated entity"):
        parse_bsp(_build_bsp(lumps=lumps))
