"""W5b engine-identity lookup contracts."""

from types import SimpleNamespace

import pytest

from website.backend.map_geometry.entities import MapEntityCatalog
from website.backend.map_geometry.stage import ScriptAction
from website.backend.map_geometry.stage_semantics import (
    ETLEGACY_SEMANTICS_COMMIT,
    AccumulatorAbortGuard,
    AccumulatorConditionalTrigger,
    AccumulatorMutation,
    AccumulatorOperation,
    AccumulatorScope,
    ControlProjectionIssue,
    EntityIdentityNamespace,
    EntityIdentityResolution,
    ScriptNameSource,
    W3EntityKind,
    build_entity_identity_index,
    link_w3_entity_catalog,
    project_accumulator_action,
)


def test_generic_identity_fields_use_et_ascii_case_and_last_assignment():
    index = build_entity_identity_index(
        (
            {
                "ClassName": "script_mover",
                "SCRIPTNAME": "DoorOne",
                "TargetName": "First",
                "targetname": "Final",
                "MESSAGE": "Initial",
                "shortname": "Final message",
            },
        )
    )

    entity = index.entities[0]
    assert index.semantics_source_commit == ETLEGACY_SEMANTICS_COMMIT
    assert index.runtime_entity_completeness == "unverified"
    assert entity.classname == "script_mover"
    assert entity.script_name == "DoorOne"
    assert entity.script_name_source is ScriptNameSource.BSP_FIELD
    assert entity.target_name == "Final"
    assert entity.message == "Final message"
    assert index.lookup_all(EntityIdentityNamespace.SCRIPT_NAME, "doorone").selected_entity_indices == (0,)


def test_et_ascii_matching_does_not_apply_unicode_case_folding():
    index = build_entity_identity_index(({"classname": "script_mover", "scriptname": "Straße"},))

    assert index.lookup_all(EntityIdentityNamespace.SCRIPT_NAME, "STRASSE").resolution is (
        EntityIdentityResolution.MISSING
    )


def test_script_multiplayer_assigns_game_manager_before_script_selection():
    index = build_entity_identity_index(
        (
            {
                "classname": "script_multiplayer",
                "scriptname": "ignored_asset_value",
            },
        )
    )

    entity = index.entities[0]
    assert entity.script_name == "game_manager"
    assert entity.script_name_source is ScriptNameSource.CLASS_OVERRIDE
    assert index.lookup_all(EntityIdentityNamespace.SCRIPT_NAME, "ignored_asset_value").resolution is (
        EntityIdentityResolution.MISSING
    )


def test_script_dispatch_retains_every_entity_in_a_shared_script_group():
    index = build_entity_identity_index(
        (
            {"classname": "script_mover", "scriptname": "shared"},
            {"classname": "func_constructible", "scriptname": "other"},
            {"classname": "misc_gamemodel", "scriptname": "SHARED"},
        )
    )

    result = index.lookup_all(EntityIdentityNamespace.SCRIPT_NAME, "shared")

    assert result.resolution is EntityIdentityResolution.GROUP
    assert result.match_semantics == "all"
    assert result.candidate_entity_indices == (0, 2)
    assert result.selected_entity_indices == (0, 2)


def test_targetname_supports_distinct_all_and_first_engine_lookups():
    index = build_entity_identity_index(
        (
            {"classname": "func_static", "targetname": "shared"},
            {"classname": "func_door", "targetname": "shared"},
        )
    )

    all_matches = index.lookup_all(EntityIdentityNamespace.TARGET_NAME, "shared")
    first_match = index.lookup_first(EntityIdentityNamespace.TARGET_NAME, "shared")

    assert all_matches.resolution is EntityIdentityResolution.GROUP
    assert all_matches.selected_entity_indices == (0, 1)
    assert first_match.resolution is EntityIdentityResolution.FIRST_MATCH
    assert first_match.candidate_entity_indices == (0, 1)
    assert first_match.selected_entity_indices == (0,)


def test_team_wolf_objective_description_overrides_runtime_message_exactly():
    index = build_entity_identity_index(
        (
            {
                "classname": "team_WOLF_objective",
                "message": "generic",
                "Description": "wrong case for G_SpawnString",
            },
            {
                "classname": "team_WOLF_objective",
                "message": "generic",
                "description": "Forward Spawn",
            },
        )
    )

    assert index.entities[0].message == "WARNING: No objective description set"
    assert index.entities[1].message == "Forward Spawn"
    result = index.lookup_first(EntityIdentityNamespace.MESSAGE, "forward spawn")
    assert result.resolution is EntityIdentityResolution.UNIQUE
    assert result.selected_entity_indices == (1,)


def test_first_message_lookup_keeps_shadowed_candidates_as_provenance():
    index = build_entity_identity_index(
        (
            {"classname": "team_WOLF_objective", "description": "CP Spawn"},
            {"classname": "team_WOLF_objective", "description": "cp spawn"},
        )
    )

    result = index.lookup_first(EntityIdentityNamespace.MESSAGE, "CP Spawn")

    assert result.resolution is EntityIdentityResolution.FIRST_MATCH
    assert result.candidate_entity_indices == (0, 1)
    assert result.selected_entity_indices == (0,)


def test_gotomarker_prefers_registered_path_corner_over_targetname():
    index = build_entity_identity_index(
        (
            {"classname": "path_corner", "targetname": "destination"},
            {"classname": "path_corner_2", "targetname": "destination"},
            {"classname": "info_train_spline_control", "targetname": "destination"},
        )
    )

    result = index.lookup_gotomarker("destination")

    assert result.namespace is EntityIdentityNamespace.PATH_CORNER
    assert result.resolution is EntityIdentityResolution.FIRST_MATCH
    assert result.candidate_entity_indices == (1, 2)
    assert result.selected_entity_indices == (1,)


def test_gotomarker_falls_back_to_first_retained_targetname():
    index = build_entity_identity_index(
        (
            {"classname": "path_corner", "targetname": "destination"},
            {"classname": "info_notnull", "targetname": "destination"},
        )
    )

    result = index.lookup_gotomarker("destination")

    assert result.namespace is EntityIdentityNamespace.TARGET_NAME
    assert result.resolution is EntityIdentityResolution.FIRST_MATCH
    assert result.candidate_entity_indices == (0, 1)
    assert result.selected_entity_indices == (0,)


def test_missing_lookup_has_no_candidates_or_selection():
    index = build_entity_identity_index(({"classname": "worldspawn"},))

    result = index.lookup_all(EntityIdentityNamespace.TARGET, "absent")

    assert result.resolution is EntityIdentityResolution.MISSING
    assert result.candidate_entity_indices == ()
    assert result.selected_entity_indices == ()


def _action(command: str, *arguments: str, line: int = 7) -> ScriptAction:
    return ScriptAction(command, arguments, " ".join(arguments), line)


def test_projects_entity_and_global_accumulator_mutations_separately():
    entity = project_accumulator_action(_action("accum", "2", "set", "-4"))
    global_value = project_accumulator_action(_action("globalaccum", "2", "inc", "+3"))

    assert entity == AccumulatorMutation(
        AccumulatorScope.ENTITY,
        2,
        AccumulatorOperation.SET,
        -4,
        7,
    )
    assert global_value == AccumulatorMutation(
        AccumulatorScope.GLOBAL,
        2,
        AccumulatorOperation.INCREMENT,
        3,
        7,
    )


def test_projects_all_abort_predicates_without_inverting_them():
    operations = {
        "abort_if_less_than": AccumulatorOperation.ABORT_IF_LESS_THAN,
        "abort_if_greater_than": AccumulatorOperation.ABORT_IF_GREATER_THAN,
        "abort_if_not_equal": AccumulatorOperation.ABORT_IF_NOT_EQUAL,
        "abort_if_not_equals": AccumulatorOperation.ABORT_IF_NOT_EQUAL,
        "abort_if_equal": AccumulatorOperation.ABORT_IF_EQUAL,
        "abort_if_bitset": AccumulatorOperation.ABORT_IF_BIT_SET,
        "abort_if_not_bitset": AccumulatorOperation.ABORT_IF_NOT_BIT_SET,
    }

    for source_name, expected in operations.items():
        result = project_accumulator_action(_action("accum", "1", source_name, "3"))
        assert result == AccumulatorAbortGuard(AccumulatorScope.ENTITY, 1, expected, 3, 7)


def test_projects_conditional_trigger_with_script_name_namespace():
    result = project_accumulator_action(_action("globalaccum", "4", "trigger_if_equal", "2", "door_group", "open"))

    assert result == AccumulatorConditionalTrigger(
        AccumulatorScope.GLOBAL,
        4,
        AccumulatorOperation.TRIGGER_IF_EQUAL,
        2,
        "door_group",
        "open",
        7,
    )


def test_non_accumulator_action_has_no_accumulator_projection():
    assert project_accumulator_action(_action("setstate", "door", "default")) is None


def test_unapproved_runtime_dependent_operations_fail_closed():
    for operation in ("random", "wait_while_equal", "set_to_dynamitecount"):
        result = project_accumulator_action(_action("accum", "0", operation, "1"))
        assert isinstance(result, ControlProjectionIssue)
        assert result.operation == operation
        assert "outside the approved" in result.reason


def test_invalid_buffer_operand_bit_and_arity_are_structured_issues():
    actions = (
        _action("accum", "-1", "set", "0"),
        _action("accum", "10", "set", "0"),
        _action("accum", "zero", "set", "0"),
        _action("accum", "0", "set", "1tail"),
        _action("accum", "0", "bitset", "31"),
        _action("accum", "0", "set"),
        _action("accum", "0", "trigger_if_equal", "1", "target"),
    )

    for action in actions:
        assert isinstance(project_accumulator_action(action), ControlProjectionIssue)


def _w3_catalog(
    *,
    source: str = "maps/test.bsp",
    spawn_points: tuple[SimpleNamespace, ...] = (),
    objective_volumes: tuple[SimpleNamespace, ...] = (),
    objective_markers: tuple[SimpleNamespace, ...] = (),
    collision_entities: tuple[SimpleNamespace, ...] = (),
) -> MapEntityCatalog:
    return MapEntityCatalog(
        map_name="test",
        bsp_source=source,
        spawn_points=spawn_points,
        objective_volumes=objective_volumes,
        objective_markers=objective_markers,
        collision_entities=collision_entities,
    )


def _w3_entity(entity_index: int, classname: str) -> SimpleNamespace:
    return SimpleNamespace(entity_index=entity_index, classname=classname)


def test_links_w3_groups_to_full_identities_only_by_bsp_entity_index():
    identities = build_entity_identity_index(
        (
            {"classname": "worldspawn"},
            {"classname": "team_CTF_redspawn", "scriptname": "axis_spawn"},
            {"classname": "trigger_objective_info", "targetname": "objective"},
            {"classname": "func_door", "targetname": "door"},
        ),
        source="maps/test.bsp",
    )
    catalog = _w3_catalog(
        spawn_points=(_w3_entity(1, "team_CTF_redspawn"),),
        objective_markers=(_w3_entity(2, "trigger_objective_info"),),
        collision_entities=(_w3_entity(3, "func_door"),),
    )

    linked = link_w3_entity_catalog(identities, catalog)

    assert linked.map_name == "test"
    assert linked.runtime_entity_completeness == "unverified"
    assert tuple((reference.entity_index, reference.kind) for reference in linked.references) == (
        (1, W3EntityKind.SPAWN_POINT),
        (2, W3EntityKind.OBJECTIVE_MARKER),
        (3, W3EntityKind.COLLISION_ENTITY),
    )
    assert linked.identity(linked.references[1]).target_name == "objective"
    assert linked.typed_reference(0) is None
    assert linked.typed_reference(3) == linked.references[2]


@pytest.mark.parametrize(
    ("identities", "catalog", "message"),
    (
        (
            build_entity_identity_index(({"classname": "func_door"},), source="a.bsp"),
            _w3_catalog(source="b.bsp", collision_entities=(_w3_entity(0, "func_door"),)),
            "does not match W3 source",
        ),
        (
            build_entity_identity_index(({"classname": "worldspawn"},), source="maps/test.bsp"),
            _w3_catalog(collision_entities=(_w3_entity(1, "func_door"),)),
            "unknown BSP entity index",
        ),
        (
            build_entity_identity_index(({"classname": "func_door"},), source="maps/test.bsp"),
            _w3_catalog(
                objective_volumes=(_w3_entity(0, "func_door"),),
                collision_entities=(_w3_entity(0, "func_door"),),
            ),
            "multiple W3 entity groups",
        ),
        (
            build_entity_identity_index(({"classname": "func_door"},), source="maps/test.bsp"),
            _w3_catalog(collision_entities=(_w3_entity(0, "func_static"),)),
            "does not match BSP identity",
        ),
    ),
)
def test_w3_identity_link_rejects_source_index_group_and_class_drift(identities, catalog, message):
    with pytest.raises(ValueError, match=message):
        link_w3_entity_catalog(identities, catalog)
