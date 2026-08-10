"""W5b engine-identity lookup contracts."""

from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from website.backend.map_geometry.bsp import parse_entities
from website.backend.map_geometry.entities import MapEntityCatalog
from website.backend.map_geometry.pk3_index import Pk3GeometryIndex, Pk3IndexError
from website.backend.map_geometry.stage import (
    AlertEntityEffect,
    AutoSpawnEffect,
    EntityStateEffect,
    GotoMarkerEffect,
    MainObjectiveEffect,
    MainObjectiveSelectorForm,
    ObjectiveCatalog,
    ObjectiveClass,
    ObjectiveDescription,
    ObjectiveStatusEffect,
    ObjectiveTeam,
    RoundEndEffect,
    ScriptAction,
)
from website.backend.map_geometry.stage_semantics import (
    ETLEGACY_SEMANTICS_COMMIT,
    AccumulatorAbortGuard,
    AccumulatorConditionalTrigger,
    AccumulatorMutation,
    AccumulatorOperation,
    AccumulatorScope,
    AutoSpawnEffectProjection,
    ControlProjectionIssue,
    EffectProjectionIssue,
    EntityIdentityNamespace,
    EntityIdentityResolution,
    EntitySourceKind,
    EntityTargetEffectProjection,
    GlobalStageEffectProjection,
    GotoMarkerEffectProjection,
    MainObjectiveEffectProjection,
    ObjectiveStatusEffectProjection,
    ScriptNameSource,
    W3EntityKind,
    build_entity_identity_index,
    build_indexed_entity_identity_index,
    link_w3_entity_catalog,
    project_accumulator_action,
    project_stage_effect,
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


def test_generic_alias_resolution_follows_interleaved_duplicate_source_order():
    entities = parse_entities(
        '{ "classname" "misc_gamemodel" "message" "first" '
        '"shortname" "second" "message" "third" }'
    )

    index = build_entity_identity_index(entities)

    assert index.entities[0].message == "third"
    assert index.entities[0].properties == entities[0].ordered_pairs


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


def test_team_wolf_objective_uses_first_duplicate_exact_description():
    entities = parse_entities(
        '{ "classname" "team_WOLF_objective" "description" "First Spawn" '
        '"description" "Second Spawn" }'
    )

    index = build_entity_identity_index(entities)

    assert index.entities[0].message == "First Spawn"
    assert index.lookup_first(EntityIdentityNamespace.MESSAGE, "second spawn").resolution is (
        EntityIdentityResolution.MISSING
    )


def test_team_wolf_objective_preserves_present_empty_description():
    entities = parse_entities('{ "classname" "team_WOLF_objective" "description" "" }')

    index = build_entity_identity_index(entities)

    assert index.entities[0].message == ""


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


def test_indexed_identity_uses_ent_override_before_requiring_a_bsp(tmp_path):
    archive = tmp_path / "override.pk3"
    with ZipFile(archive, "w") as pk3:
        pk3.writestr(
            "maps/test.ent",
            '{ "classname" "script_multiplayer" "scriptname" "ignored" }',
        )
    geometry_index = Pk3GeometryIndex.scan(tmp_path)

    identities = build_indexed_entity_identity_index(geometry_index, "test")

    assert identities.source_kind is EntitySourceKind.ENT_OVERRIDE
    assert identities.source.endswith("override.pk3!/maps/test.ent")
    assert identities.lookup_all(EntityIdentityNamespace.SCRIPT_NAME, "game_manager").selected_entity_indices == (0,)


def test_indexed_identity_rejects_conflicting_ent_overrides_without_live_vfs_precedence(tmp_path):
    for name, marker in (("a.pk3", "one"), ("b.pk3", "two")):
        with ZipFile(tmp_path / name, "w") as pk3:
            pk3.writestr("maps/test.ent", f'{{ "classname" "worldspawn" "message" "{marker}" }}')
    geometry_index = Pk3GeometryIndex.scan(tmp_path)

    with pytest.raises(Pk3IndexError, match="ambiguous entity overrides"):
        build_indexed_entity_identity_index(geometry_index, "test")


def test_indexed_identity_falls_back_to_bsp_lump_when_no_ent_override_exists():
    geometry_index = SimpleNamespace(
        resolve_asset=lambda *_args: SimpleNamespace(status="missing", selected=None),
        load_bsp=lambda _map_name: SimpleNamespace(
            entities=({"classname": "script_multiplayer"},),
            source="maps/test.bsp",
        ),
    )

    identities = build_indexed_entity_identity_index(geometry_index, "test")

    assert identities.source_kind is EntitySourceKind.BSP_LUMP
    assert identities.source == "maps/test.bsp"


def test_indexed_identity_rejects_a_cached_bsp_from_a_different_provider():
    geometry_index = SimpleNamespace(
        resolve_asset=lambda *_args: SimpleNamespace(status="missing", selected=None),
        resolve=lambda _map_name: SimpleNamespace(
            map_name="test",
            selected=SimpleNamespace(source="indexed.pk3!/maps/test.bsp"),
        ),
    )
    cached_bsp = SimpleNamespace(
        entities=({"classname": "script_multiplayer"},),
        source="other.pk3!/maps/test.bsp",
    )

    with pytest.raises(Pk3IndexError, match="does not match indexed map"):
        build_indexed_entity_identity_index(geometry_index, "test", bsp=cached_bsp)


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


def _w3_entity(entity_index: int, classname: str, **fields) -> SimpleNamespace:
    return SimpleNamespace(entity_index=entity_index, classname=classname, **fields)


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
        objective_volumes=(_w3_entity(2, "trigger_objective_info"),),
        collision_entities=(_w3_entity(3, "func_door"),),
    )

    linked = link_w3_entity_catalog(identities, catalog)

    assert linked.map_name == "test"
    assert linked.runtime_entity_completeness == "unverified"
    assert tuple((reference.entity_index, reference.kind) for reference in linked.references) == (
        (1, W3EntityKind.SPAWN_POINT),
        (2, W3EntityKind.OBJECTIVE_VOLUME),
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


def _linked(entities, **catalog_groups):
    identities = build_entity_identity_index(tuple(entities), source="maps/test.bsp")
    return link_w3_entity_catalog(identities, _w3_catalog(**catalog_groups))


def _objectives(*descriptions: ObjectiveDescription) -> ObjectiveCatalog:
    return ObjectiveCatalog((), descriptions, ())


def test_projects_all_match_entity_target_and_retains_only_typed_w3_subset():
    linked = _linked(
        (
            {"classname": "script_multiplayer"},
            {"classname": "func_door", "targetname": "gate"},
            {"classname": "target_speaker", "targetname": "GATE"},
        ),
        collision_entities=(_w3_entity(1, "func_door"),),
    )

    projection = project_stage_effect(
        EntityStateEffect("gate", "invisible", 8),
        source_script_name="game_manager",
        linked=linked,
        objectives=_objectives(),
    )

    assert isinstance(projection, EntityTargetEffectProjection)
    assert projection.source.lookup.selected_entity_indices == (0,)
    assert projection.target_lookup.resolution is EntityIdentityResolution.GROUP
    assert projection.target_lookup.selected_entity_indices == (1, 2)
    assert tuple(reference.entity_index for reference in projection.selected_w3_references) == (1,)
    assert projection.runtime_entity_completeness == "unverified"

    alert = project_stage_effect(
        AlertEntityEffect("gate", 9),
        source_script_name="game_manager",
        linked=linked,
        objectives=_objectives(),
    )
    assert isinstance(alert, EntityTargetEffectProjection)
    assert alert.target_lookup.selected_entity_indices == (1, 2)


def test_projects_gotomarker_destination_and_each_relative_reference_with_first_match_rules():
    linked = _linked(
        (
            {"classname": "script_mover", "scriptname": "truck"},
            {"classname": "path_corner_2", "targetname": "destination"},
            {"classname": "info_notnull", "targetname": "destination"},
            {"classname": "func_door", "targetname": "origin_ref"},
        ),
        collision_entities=(_w3_entity(0, "script_mover"), _w3_entity(3, "func_door")),
    )

    projection = project_stage_effect(
        GotoMarkerEffect("destination", ("100", "relative", "origin_ref", "wait"), 9),
        source_script_name="truck",
        linked=linked,
        objectives=_objectives(),
    )

    assert isinstance(projection, GotoMarkerEffectProjection)
    assert projection.destination_lookup.namespace is EntityIdentityNamespace.PATH_CORNER
    assert projection.destination_lookup.selected_entity_indices == (1,)
    assert projection.relative_lookups[0].selected_entity_indices == (3,)
    assert tuple(reference.entity_index for reference in projection.relative_w3_references[0]) == (3,)


def test_gotomarker_trailing_relative_is_a_structured_projection_issue():
    linked = _linked(({"classname": "script_mover", "scriptname": "truck"},))

    projection = project_stage_effect(
        GotoMarkerEffect("missing", ("100", "relative"), 10),
        source_script_name="truck",
        linked=linked,
        objectives=_objectives(),
    )

    assert isinstance(projection, EffectProjectionIssue)
    assert "has no target" in projection.reason


def test_gotomarker_does_not_reinterpret_a_consumed_relative_target_as_an_option():
    linked = _linked(
        (
            {"classname": "script_mover", "scriptname": "truck"},
            {"classname": "path_corner_2", "targetname": "destination"},
            {"classname": "path_corner_2", "targetname": "relative"},
        )
    )

    projection = project_stage_effect(
        GotoMarkerEffect("destination", ("100", "relative", "relative", "wait"), 10),
        source_script_name="truck",
        linked=linked,
        objectives=_objectives(),
    )

    assert isinstance(projection, GotoMarkerEffectProjection)
    assert tuple(lookup.requested_value for lookup in projection.relative_lookups) == ("relative",)
    assert projection.relative_lookups[0].selected_entity_indices == (2,)


def test_autospawn_retains_first_marker_and_every_team_spawn_as_runtime_candidates():
    linked = _linked(
        (
            {"classname": "script_multiplayer"},
            {"classname": "team_WOLF_objective", "description": "Forward Spawn"},
            {"classname": "team_WOLF_objective", "description": "forward spawn"},
            {"classname": "team_CTF_redspawn"},
            {"classname": "team_CTF_bluespawn"},
            {"classname": "team_CTF_bluespawn"},
        ),
        objective_markers=(
            _w3_entity(1, "team_WOLF_objective"),
            _w3_entity(2, "team_WOLF_objective"),
        ),
        spawn_points=(
            _w3_entity(3, "team_CTF_redspawn", team="AXIS"),
            _w3_entity(4, "team_CTF_bluespawn", team="ALLIES"),
            _w3_entity(5, "team_CTF_bluespawn", team="ALLIES"),
        ),
    )

    projection = project_stage_effect(
        AutoSpawnEffect("Forward Spawn", 1, 11),
        source_script_name="game_manager",
        linked=linked,
        objectives=_objectives(),
    )

    assert isinstance(projection, AutoSpawnEffectProjection)
    assert projection.marker_lookup.resolution is EntityIdentityResolution.FIRST_MATCH
    assert projection.marker_lookup.selected_entity_indices == (1,)
    assert tuple(reference.entity_index for reference in projection.marker_w3_references) == (1,)
    assert tuple(reference.entity_index for reference in projection.team_spawn_candidates) == (4, 5)
    assert projection.blocked_reason is None
    assert projection.selection_semantics == "runtime_active_ownership_proximity_unverified"


def test_autospawn_rejects_a_first_message_candidate_without_spawn_marker_contract():
    linked = _linked(
        (
            {"classname": "script_multiplayer"},
            {"classname": "target_speaker", "message": "Forward Spawn"},
            {"classname": "team_WOLF_objective", "description": "Forward Spawn"},
        ),
        objective_markers=(_w3_entity(2, "team_WOLF_objective"),),
    )

    projection = project_stage_effect(
        AutoSpawnEffect("Forward Spawn", 0, 12),
        source_script_name="game_manager",
        linked=linked,
        objectives=_objectives(),
    )

    assert isinstance(projection, AutoSpawnEffectProjection)
    assert projection.marker_lookup.selected_entity_indices == (1,)
    assert projection.blocked_reason == "first_static_message_candidate_is_not_team_WOLF_objective"


def test_objective_status_uses_exact_team_and_number_without_text_matching():
    linked = _linked(({"classname": "script_multiplayer"},))
    axis = ObjectiveDescription(ObjectiveTeam.AXIS, 2, ObjectiveClass.PRIMARY, "Destroy it", 4)
    allies = ObjectiveDescription(ObjectiveTeam.ALLIES, 2, ObjectiveClass.PRIMARY, "Defend it", 5)

    projection = project_stage_effect(
        ObjectiveStatusEffect(2, 1, 0, 13),
        source_script_name="game_manager",
        linked=linked,
        objectives=_objectives(axis, allies),
    )

    assert isinstance(projection, ObjectiveStatusEffectProjection)
    assert projection.descriptions == (allies,)


def test_main_objective_legacy_is_blocked_and_target_form_uses_target_field_first_match():
    linked = _linked(
        (
            {"classname": "script_multiplayer"},
            {"classname": "trigger_objective_info", "target": "main_obj"},
            {"classname": "trigger_objective_info", "target": "MAIN_OBJ"},
        ),
        objective_volumes=(
            _w3_entity(1, "trigger_objective_info"),
            _w3_entity(2, "trigger_objective_info"),
        ),
    )

    legacy = project_stage_effect(
        MainObjectiveEffect("2", MainObjectiveSelectorForm.LEGACY_NUMERIC, 0, 14),
        source_script_name="game_manager",
        linked=linked,
        objectives=_objectives(),
    )
    target = project_stage_effect(
        MainObjectiveEffect("main_obj", MainObjectiveSelectorForm.TARGET_NAME, 0, 15),
        source_script_name="game_manager",
        linked=linked,
        objectives=_objectives(),
    )

    assert isinstance(legacy, MainObjectiveEffectProjection)
    assert legacy.target_lookup is None
    assert legacy.blocked_reason == "legacy_numeric_selector_is_unverified_for_the_live_build"
    assert isinstance(target, MainObjectiveEffectProjection)
    assert target.target_lookup is not None
    assert target.target_lookup.namespace is EntityIdentityNamespace.TARGET
    assert target.target_lookup.selected_entity_indices == (1,)
    assert tuple(reference.entity_index for reference in target.selected_w3_references) == (1,)
    assert target.blocked_reason is None


def test_main_objective_does_not_skip_an_engine_first_target_of_the_wrong_class():
    linked = _linked(
        (
            {"classname": "script_multiplayer"},
            {"classname": "target_speaker", "target": "main_obj"},
            {"classname": "trigger_objective_info", "target": "main_obj"},
        ),
        objective_volumes=(_w3_entity(2, "trigger_objective_info"),),
    )

    projection = project_stage_effect(
        MainObjectiveEffect("main_obj", MainObjectiveSelectorForm.TARGET_NAME, 0, 15),
        source_script_name="game_manager",
        linked=linked,
        objectives=_objectives(),
    )

    assert isinstance(projection, MainObjectiveEffectProjection)
    assert projection.target_lookup is not None
    assert projection.target_lookup.candidate_entity_indices == (1, 2)
    assert projection.target_lookup.selected_entity_indices == (1,)
    assert projection.selected_w3_references == ()
    assert projection.blocked_reason == "first_static_target_field_candidate_is_not_trigger_objective_info"


def test_round_end_is_retained_as_a_global_effect_with_source_identity():
    linked = _linked(({"classname": "script_multiplayer"},))

    projection = project_stage_effect(
        RoundEndEffect(16),
        source_script_name="game_manager",
        linked=linked,
        objectives=_objectives(),
    )

    assert isinstance(projection, GlobalStageEffectProjection)
    assert projection.source.lookup.selected_entity_indices == (0,)
