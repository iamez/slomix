"""Read-only W1/W2 acceptance checks against the developer's real ET assets."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from website.backend.map_geometry import MapAssetKind, Pk3GeometryIndex

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
