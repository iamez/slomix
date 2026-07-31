"""Synthetic contracts for W3 BSP entity extraction."""

from __future__ import annotations

import pytest

from website.backend.map_geometry import (
    BspBrush,
    BspBrushSide,
    BspFile,
    BspModel,
    BspPlane,
    BspShader,
    EntityExtractionError,
    ObjectiveGeometrySource,
    entity_catalog_manifest,
    extract_entity_catalog,
)


def _synthetic_bsp(entities: tuple[dict[str, str], ...]) -> BspFile:
    planes = (
        BspPlane((1.0, 0.0, 0.0), 2.0),
        BspPlane((-1.0, 0.0, 0.0), 2.0),
        BspPlane((0.0, 1.0, 0.0), 3.0),
        BspPlane((0.0, -1.0, 0.0), 3.0),
        BspPlane((0.0, 0.0, 1.0), 4.0),
        BspPlane((0.0, 0.0, -1.0), 4.0),
    )
    return BspFile(
        source="synthetic.pk3!/maps/test_map.bsp",
        byte_length=1,
        lumps=(),
        entity_text="",
        entities=entities,
        shaders=(BspShader("textures/common/trigger", 128, 0x20000001),),
        planes=planes,
        nodes=(),
        leafs=(),
        leaf_surfaces=(),
        leaf_brushes=(),
        models=(
            BspModel((-100.0, -100.0, -100.0), (100.0, 100.0, 100.0), 0, 0, 0, 0),
            BspModel((-2.0, -3.0, -4.0), (2.0, 3.0, 4.0), 0, 0, 0, 1),
        ),
        brushes=(BspBrush(0, 6, 0),),
        brush_sides=tuple(BspBrushSide(index, 0) for index in range(6)),
        draw_vertices=(),
        draw_indexes=(),
        surfaces=(),
    )


def test_extracts_typed_w3_entities_and_exact_translated_objective_volume():
    bsp = _synthetic_bsp(
        (
            {
                "classname": "team_CTF_bluespawn",
                "origin": "1 2 3",
                "angle": "90",
                "spawnflags": "3",
                "targetname": "allied_spawn",
            },
            {
                "classname": "team_CTF_redspawn",
                "origin": "-1 -2 -3",
            },
            {
                "classname": "trigger_objective_info",
                "model": "*1",
                "origin": "10 20 30",
                "shortname": "Documents",
                "track": "the documents",
                "spawnflags": "17",
                "objflags": "32",
            },
            {
                "classname": "team_WOLF_objective",
                "origin": "11 22 33",
                "description": "Forward spawn",
                "spawnflags": "2",
            },
            {
                "classname": "func_door_rotating",
                "model": "*1",
                "origin": "5 6 7",
                "degrees": "-90",
            },
            {"classname": "worldspawn"},
        )
    )

    catalog = extract_entity_catalog(bsp, "TEST_MAP")

    assert catalog.map_name == "test_map"
    assert [point.team for point in catalog.spawn_points] == ["ALLIES", "AXIS"]
    assert catalog.spawn_points[0].origin == (1.0, 2.0, 3.0)
    assert catalog.spawn_points[1].spawn_flags == 0

    volume = catalog.objective_volumes[0]
    assert volume.source is ObjectiveGeometrySource.MEASURED_BSP_VOLUME
    assert volume.model.local_bounds.mins == (-2.0, -3.0, -4.0)
    assert volume.model.origin_translated_bounds.maxs == (12.0, 23.0, 34.0)
    assert volume.contains_point((10.0, 20.0, 30.0))
    assert volume.contains_point((12.0, 23.0, 34.0))
    assert not volume.contains_point((12.01, 20.0, 30.0))
    assert volume.brushes[0].planes[0].distance == 12.0
    assert volume.brushes[0].planes[1].distance == -8.0

    assert catalog.objective_markers[0].description == "Forward spawn"
    assert catalog.collision_entities[0].runtime_state == "unresolved"
    assert catalog.collision_entities[0].degrees == -90.0

    manifest = entity_catalog_manifest(catalog)
    assert manifest["objective_volumes"][0]["source"] == "measured_bsp_volume"
    assert manifest["runtime_entity_completeness"] == "unverified"
    assert manifest["collision_entities"][0]["runtime_state"] == "unresolved"


@pytest.mark.parametrize(
    ("classname", "kind"),
    [
        ("func_door", "door"),
        ("func_door_rotating", "door"),
        ("script_mover", "mover"),
        ("func_rotating", "mover"),
        ("func_bobbing", "mover"),
        ("func_button", "mover"),
        ("func_static", "conditional_static"),
        ("func_leaky", "static_brush"),
        ("func_constructible", "constructible"),
        ("func_explosive", "destructible"),
    ],
)
def test_classifies_collision_relevant_inline_brush_entities(classname, kind):
    catalog = extract_entity_catalog(
        _synthetic_bsp(({"classname": classname, "model": "*1"},)),
        "test_map",
    )

    assert len(catalog.collision_entities) == 1
    assert catalog.collision_entities[0].kind == kind
    assert catalog.collision_entities[0].runtime_state == "unresolved"


@pytest.mark.parametrize(
    ("entity", "expected"),
    [
        ({"classname": "team_CTF_bluespawn"}, "missing required origin"),
        (
            {"classname": "team_CTF_redspawn", "origin": "NaN 0 0"},
            "origin\\[0\\] is not finite",
        ),
        (
            {"classname": "trigger_objective_info", "model": "*9"},
            "inline model 9 is outside",
        ),
        (
            {
                "classname": "trigger_objective_info",
                "model": "*1",
                "angle": "45",
            },
            "rotated objective brush volumes are unsupported",
        ),
        (
            {"classname": "script_mover", "model": "models/mapobjects/truck.md3"},
            "invalid inline model reference",
        ),
    ],
)
def test_targeted_entity_defects_fail_closed(entity, expected):
    with pytest.raises(EntityExtractionError, match=expected):
        extract_entity_catalog(_synthetic_bsp((entity,)), "test_map")


def test_geometry_map_without_objective_trigger_has_no_measured_volume():
    bsp = _synthetic_bsp(
        (
            {
                "classname": "team_WOLF_objective",
                "origin": "1 2 3",
                "description": "Marker only",
            },
        )
    )

    catalog = extract_entity_catalog(bsp, "test_map")

    assert catalog.objective_markers
    assert catalog.objective_volumes == ()
