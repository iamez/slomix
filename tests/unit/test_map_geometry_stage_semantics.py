"""W5b engine-identity lookup contracts."""

from website.backend.map_geometry.stage_semantics import (
    ETLEGACY_SEMANTICS_COMMIT,
    EntityIdentityNamespace,
    EntityIdentityResolution,
    ScriptNameSource,
    build_entity_identity_index,
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
