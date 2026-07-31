"""Tests for the deterministic W3 entity inventory publisher."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.analyze_map_entity_geometry import build_inventory
from website.backend.map_geometry import (
    BspBrush,
    BspBrushSide,
    BspFile,
    BspModel,
    BspPlane,
    BspShader,
    GeometryResolution,
    MapAssetKind,
    MapAssetProvider,
)


class _Index:
    etmain_dir = Path("/maps")
    map_names = ("covered",)

    def __init__(self, bsp):
        self.bsp = bsp

    def resolve(self, map_name):
        if map_name == "covered":
            provider = MapAssetProvider(
                map_name="covered",
                asset_kind=MapAssetKind.BSP,
                pk3_path=Path("/maps/covered.pk3"),
                member="maps/covered.bsp",
                member_index=0,
                size=123,
                crc32=1,
                sha256="a" * 64,
            )
            return GeometryResolution("covered", "geometry", provider, (provider,))  # type: ignore[arg-type]
        return GeometryResolution(
            map_name,
            "no_geometry",
            None,
            (),
            "no maps/<map>.bsp provider found",
        )

    def resolve_many(self, map_names):
        normalised = sorted(
            {
                name.strip().casefold().removesuffix(".bsp")
                for name in map_names
            }
        )
        return tuple(self.resolve(name) for name in normalised)

    def load_bsp(self, map_name):
        assert map_name == "covered"
        return self.bsp


def _bsp():
    return BspFile(
        source="/maps/covered.pk3!/maps/covered.bsp",
        byte_length=1,
        lumps=(),
        entity_text="",
        entities=(
            {
                "classname": "trigger_objective_info",
                "model": "*1",
                "shortname": "Objective",
            },
        ),
        shaders=(BspShader("trigger", 0, 1),),
        planes=(
            BspPlane((1.0, 0.0, 0.0), 1.0),
            BspPlane((-1.0, 0.0, 0.0), 1.0),
            BspPlane((0.0, 1.0, 0.0), 1.0),
            BspPlane((0.0, -1.0, 0.0), 1.0),
            BspPlane((0.0, 0.0, 1.0), 1.0),
            BspPlane((0.0, 0.0, -1.0), 1.0),
        ),
        nodes=(),
        leafs=(),
        leaf_surfaces=(),
        leaf_brushes=(),
        models=(
            BspModel((-2.0, -2.0, -2.0), (2.0, 2.0, 2.0), 0, 0, 0, 0),
            BspModel((-1.0, -1.0, -1.0), (1.0, 1.0, 1.0), 0, 0, 0, 1),
        ),
        brushes=(BspBrush(0, 6, 0),),
        brush_sides=tuple(BspBrushSide(index, 0) for index in range(6)),
        draw_vertices=(),
        draw_indexes=(),
        surfaces=(),
    )


def test_build_inventory_marks_missing_geometry_null_and_hashes_content():
    result = build_inventory(
        _Index(_bsp()),
        ["covered", "covered.bsp", "missing"],
    )  # type: ignore[arg-type]

    assert result["maps"]["covered"]["status"] == "measured"
    assert (
        result["maps"]["covered"]["objective_volumes"][0]["source"]
        == "measured_bsp_volume"
    )
    assert result["maps"]["missing"]["status"] == "no_geometry"
    assert result["maps"]["missing"]["spawn_points"] is None
    assert result["maps"]["missing"]["objective_volumes"] is None
    assert result["maps"]["missing"]["objective_markers"] is None
    assert result["maps"]["missing"]["collision_entities"] is None
    assert result["summary"]["status_counts"] == {
        "measured": 1,
        "no_geometry": 1,
        "ambiguous_geometry": 0,
    }
    assert result["summary"]["requested_maps"] == 2

    manifest = result.pop("content_manifest_sha256")
    result.pop("etmain_dir")
    encoded = json.dumps(
        result,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    assert manifest == hashlib.sha256(encoded).hexdigest()
