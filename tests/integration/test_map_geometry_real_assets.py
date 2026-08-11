"""Read-only W1/W2 acceptance checks against the developer's real ET assets."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path

import pytest

from website.backend.map_geometry import (
    AccumulatorAbortGuard,
    AccumulatorConditionalTrigger,
    AccumulatorMutation,
    AlertEntityEffect,
    AutoSpawnEffectProjection,
    BspPointTracer,
    ControlBarrierInstruction,
    ControlProjectionIssue,
    EffectProjectionIssue,
    EntityIdentityNamespace,
    EntityIdentityResolution,
    EntityTargetDisposition,
    EntityTargetEffectProjection,
    GlobalStageEffectProjection,
    GotoMarkerEffectProjection,
    KillInstruction,
    KillTargetDisposition,
    MainObjectiveEffect,
    MainObjectiveEffectProjection,
    MainObjectiveSelectorForm,
    MapAssetKind,
    ObjectiveGeometrySource,
    ObjectiveStatusEffectProjection,
    ObjectiveWorldLinkDisposition,
    Pk3GeometryIndex,
    PlayerStance,
    RuntimeActionControlDisposition,
    RuntimeActionInstruction,
    StageLoadStatus,
    SurfaceType,
    SymbolicAccumulatorState,
    SymbolicDispatchResolution,
    SymbolicPathCompletion,
    TraceReason,
    TraceStatus,
    TriggerInstruction,
    TriggerResolution,
    build_indexed_entity_identity_index,
    build_ordered_stage_program_index,
    compile_bsp_patches,
    extract_entity_catalog,
    link_w3_entity_catalog,
    load_static_stage,
    project_accumulator_action,
    project_ordered_stage_programs,
    project_stage_effect,
    resolve_symbolic_nested_dispatch,
    walk_symbolic_stage_program,
)

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
    # Full-corpus checks parse up to 20 large BSPs. Repo-wide coverage tracing
    # can more than double their runtime; this remains a hang guard, not a
    # production performance threshold.
    pytest.mark.timeout(90),
    pytest.mark.skipif(
        not RUN_REAL_ASSET_TESTS,
        reason="real ET map asset tests require SLOMIX_RUN_REAL_ASSET_TESTS=1",
    ),
    pytest.mark.skipif(not ETMAIN.is_dir(), reason="configured ET map asset directory is not installed"),
]


@pytest.fixture(scope="module")
def geometry_index() -> Pk3GeometryIndex:
    return Pk3GeometryIndex.scan(ETMAIN)


def _has_temporal_control(instructions) -> bool:
    return any(
        isinstance(instruction, ControlBarrierInstruction)
        or (
            isinstance(instruction, RuntimeActionInstruction)
            and instruction.control_disposition is RuntimeActionControlDisposition.CONDITIONAL_TEMPORAL_PAUSE
        )
        for instruction in instructions
    )


def _nested_instructions(instructions):
    return tuple(
        instruction
        for instruction in instructions
        if isinstance(instruction, (TriggerInstruction, AccumulatorConditionalTrigger))
    )


def test_every_observed_played_map_has_geometry_or_an_explicit_missing_result(geometry_index):
    manifest = geometry_index.manifest(PLAYED_MAPS)

    assert set(manifest["maps"]) == PLAYED_MAPS
    assert set(manifest["summary"]["missing_maps"]) == MISSING_GEOMETRY
    assert manifest["summary"]["with_geometry"] == 13
    assert manifest["summary"]["without_geometry"] == 6
    for kind in MapAssetKind:
        counts = manifest["summary"]["asset_status_counts"][kind.value]
        expected = (
            {"resolved": 0, "missing": 19, "ambiguous": 0}
            if kind is MapAssetKind.ENTITY_OVERRIDE
            else {"resolved": 13, "missing": 6, "ambiguous": 0}
        )
        assert counts == expected


def test_te_escape2_duplicate_consumed_assets_are_byte_identical(geometry_index):
    for kind in (MapAssetKind.BSP, MapAssetKind.SCRIPT, MapAssetKind.OBJDATA):
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


def test_w5b_asset_evidence_manifest_is_content_sensitive_and_deterministic(geometry_index):
    manifest = geometry_index.manifest(geometry_index.map_names)
    canonical_maps = json.dumps(
        manifest["maps"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()

    assert len(manifest["maps"]) == 20
    assert hashlib.sha256(canonical_maps).hexdigest() == (
        "86ddd0ec23b3c6120136195af34aa633ad249eb358ea0fb6cd6e490dd81b220d"
    )


def test_w5a_parses_every_resolved_stage_asset_and_exposes_partial_static_coverage(geometry_index):
    totals = {
        "entities": 0,
        "events": 0,
        "actions": 0,
        "registry_issues": 0,
        "opaque_entities": 0,
        "objectives": 0,
        "known_objective_classes": 0,
        "unknown_objective_classes": 0,
        "effects": 0,
        "trigger_edges": 0,
        "resolved_trigger_edges": 0,
        "missing_trigger_edges": 0,
        "ambiguous_trigger_edges": 0,
        "opaque_trigger_edges": 0,
        "runtime_dispatch_trigger_edges": 0,
        "no_op_trigger_edges": 0,
        "legacy_numeric_main_objectives": 0,
    }
    maps_with_complete_trigger_closure = 0
    maps_with_complete_objective_classes = 0

    for map_name in geometry_index.map_names:
        result = load_static_stage(geometry_index, map_name)
        assert result.status is StageLoadStatus.RESOLVED, (map_name, result.reason)
        assert result.model is not None
        model = result.model
        assert model.script_provider == result.script_resolution.selected
        assert model.objdata_provider == result.objdata_resolution.selected

        events = tuple(event for entity in model.script.entities for event in entity.events)
        unknown_classes = sum(item.classification == "unknown" for item in model.objectives.objectives)
        edge_counts = {
            resolution: sum(edge.resolution is resolution for edge in model.graph.trigger_edges)
            for resolution in TriggerResolution
        }
        totals["entities"] += len(model.script.entities)
        totals["events"] += len(events)
        totals["actions"] += sum(len(event.actions) for event in events)
        totals["registry_issues"] += sum(entity.registry_issue is not None for entity in model.script.entities)
        totals["opaque_entities"] += len(model.graph.opaque_entities)
        totals["objectives"] += len(model.objectives.objectives)
        totals["known_objective_classes"] += len(model.objectives.objectives) - unknown_classes
        totals["unknown_objective_classes"] += unknown_classes
        totals["effects"] += sum(len(node.effects) for node in model.graph.nodes)
        totals["trigger_edges"] += len(model.graph.trigger_edges)
        totals["resolved_trigger_edges"] += edge_counts[TriggerResolution.RESOLVED]
        totals["missing_trigger_edges"] += edge_counts[TriggerResolution.MISSING]
        totals["ambiguous_trigger_edges"] += edge_counts[TriggerResolution.AMBIGUOUS]
        totals["opaque_trigger_edges"] += edge_counts[TriggerResolution.OPAQUE]
        totals["runtime_dispatch_trigger_edges"] += edge_counts[TriggerResolution.RUNTIME_DISPATCH]
        totals["no_op_trigger_edges"] += edge_counts[TriggerResolution.NO_OP]
        totals["legacy_numeric_main_objectives"] += sum(
            isinstance(effect, MainObjectiveEffect) and effect.selector_form is MainObjectiveSelectorForm.LEGACY_NUMERIC
            for node in model.graph.nodes
            for effect in node.effects
        )
        maps_with_complete_trigger_closure += edge_counts[TriggerResolution.RESOLVED] == len(model.graph.trigger_edges)
        maps_with_complete_objective_classes += unknown_classes == 0

    assert totals == {
        "entities": 583,
        "events": 2153,
        "actions": 10057,
        "registry_issues": 0,
        "opaque_entities": 0,
        "objectives": 250,
        "known_objective_classes": 232,
        "unknown_objective_classes": 18,
        "effects": 2929,
        "trigger_edges": 1315,
        "resolved_trigger_edges": 1304,
        "missing_trigger_edges": 11,
        "ambiguous_trigger_edges": 0,
        "opaque_trigger_edges": 0,
        "runtime_dispatch_trigger_edges": 0,
        "no_op_trigger_edges": 0,
        "legacy_numeric_main_objectives": 42,
    }
    assert maps_with_complete_trigger_closure == 13
    assert maps_with_complete_objective_classes == 18


def test_w5b_indexes_engine_effective_script_identities_without_inventing_missing_blocks(geometry_index):
    totals = {
        "blocks": 0,
        "unique": 0,
        "group": 0,
        "missing": 0,
        "selected_entities": 0,
    }
    missing_by_map = {}
    maps_with_every_block_in_the_bsp_identity_scope = 0

    for map_name in geometry_index.map_names:
        bsp = geometry_index.load_bsp(map_name)
        identities = build_indexed_entity_identity_index(geometry_index, map_name, bsp=bsp)
        assert identities.source_kind.value == "bsp_lump", map_name
        assert geometry_index.resolve_asset(map_name, MapAssetKind.ENTITY_OVERRIDE).status == "missing", map_name
        model = load_static_stage(geometry_index, map_name).model
        assert model is not None

        game_manager = identities.lookup_all(EntityIdentityNamespace.SCRIPT_NAME, "game_manager")
        assert len(game_manager.selected_entity_indices) == 1, map_name
        game_manager_entity = identities.entities[game_manager.selected_entity_indices[0]]
        assert game_manager_entity.classname == "script_multiplayer", map_name

        missing = []
        for script_entity in model.script.entities:
            lookup = identities.lookup_all(EntityIdentityNamespace.SCRIPT_NAME, script_entity.name)
            totals["blocks"] += 1
            totals[lookup.resolution.value] += 1
            totals["selected_entities"] += len(lookup.selected_entity_indices)
            if lookup.resolution is EntityIdentityResolution.MISSING:
                missing.append(script_entity.name)

        if missing:
            missing_by_map[map_name] = sorted(missing)
        else:
            maps_with_every_block_in_the_bsp_identity_scope += 1

    assert totals == {
        "blocks": 583,
        "unique": 510,
        "group": 50,
        "missing": 23,
        "selected_entities": 1025,
    }
    assert maps_with_every_block_in_the_bsp_identity_scope == 13
    assert missing_by_map == {
        "adlernest": ["allied_spawn_flag"],
        "braundorf_b4": ["cp_spawn"],
        "bremen_b3": ["allied3spawn_spawns", "axis1spawn_spawns", "mtd_sm", "mtd_td"],
        "erdenberg_t2": ["flak88_1_toi", "flak88_2_toi"],
        "etl_beach": [
            "allied_compost_built_lms",
            "allied_compost_built_model_lms",
            "allied_obj1",
            "axis_compost_built_lms",
            "axis_compost_built_model_lms",
            "neutral_compost_clip_lms",
            "neutral_compost_closed_clip_lms",
            "neutral_compost_closed_model_lms",
            "neutral_compost_toi_lms",
        ],
        "sw_battery": ["lighthouse_light", "mg42_clip_1", "reardoor_trigger1"],
        "sw_goldrush_te": ["defense2", "defense2_toi", "defense4"],
    }


def test_w5b_projects_every_installed_accumulator_action_without_expanding_the_approved_subset(geometry_index):
    projection_counts = {
        "mutation": 0,
        "abort_guard": 0,
        "conditional_trigger": 0,
        "issue": 0,
    }
    operations = {}

    for map_name in geometry_index.map_names:
        model = load_static_stage(geometry_index, map_name).model
        assert model is not None
        for script_entity in model.script.entities:
            for event in script_entity.events:
                for action in event.actions:
                    if action.command.casefold() not in {"accum", "globalaccum"}:
                        continue
                    projection = project_accumulator_action(action)
                    if isinstance(projection, AccumulatorMutation):
                        projection_counts["mutation"] += 1
                    elif isinstance(projection, AccumulatorAbortGuard):
                        projection_counts["abort_guard"] += 1
                    elif isinstance(projection, AccumulatorConditionalTrigger):
                        projection_counts["conditional_trigger"] += 1
                    elif isinstance(projection, ControlProjectionIssue):
                        projection_counts["issue"] += 1
                    else:
                        raise AssertionError((map_name, action))
                    operation = projection.operation
                    operations[operation] = operations.get(operation, 0) + 1

    assert projection_counts == {
        "mutation": 994,
        "abort_guard": 313,
        "conditional_trigger": 299,
        "issue": 0,
    }
    assert {operation.value: count for operation, count in operations.items()} == {
        "abort_if_bitset": 39,
        "abort_if_equal": 149,
        "abort_if_greater_than": 5,
        "abort_if_less_than": 9,
        "abort_if_not_bitset": 33,
        "abort_if_not_equal": 78,
        "bitreset": 267,
        "bitset": 289,
        "inc": 24,
        "set": 414,
        "trigger_if_equal": 299,
    }


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


def test_w3_extracts_measured_objective_volumes_and_dynamic_inputs_for_every_bsp(
    geometry_index,
):
    totals = {
        "spawn_points": 0,
        "objective_volumes": 0,
        "objective_markers": 0,
        "collision_entities": 0,
    }
    for map_name in geometry_index.map_names:
        catalog = extract_entity_catalog(geometry_index.load_bsp(map_name), map_name)
        assert catalog.spawn_points, map_name
        assert catalog.objective_volumes, map_name
        assert catalog.objective_markers, map_name
        for volume in catalog.objective_volumes:
            assert volume.source is ObjectiveGeometrySource.MEASURED_BSP_VOLUME
            assert volume.brushes
            assert volume.contains_point(
                tuple(
                    (
                        volume.model.origin_translated_bounds.mins[index]
                        + volume.model.origin_translated_bounds.maxs[index]
                    )
                    / 2
                    for index in range(3)
                )
            ), (map_name, volume.entity_index)
        assert all(entity.runtime_state == "unresolved" for entity in catalog.collision_entities)
        totals["spawn_points"] += len(catalog.spawn_points)
        totals["objective_volumes"] += len(catalog.objective_volumes)
        totals["objective_markers"] += len(catalog.objective_markers)
        totals["collision_entities"] += len(catalog.collision_entities)

    assert totals == {
        "spawn_points": 2376,
        "objective_volumes": 158,
        "objective_markers": 96,
        "collision_entities": 1058,
    }


def test_w5b_links_every_w3_entity_to_the_exact_bsp_identity(geometry_index):
    totals = {
        "spawn_point": 0,
        "objective_volume": 0,
        "objective_marker": 0,
        "collision_entity": 0,
    }

    for map_name in geometry_index.map_names:
        bsp = geometry_index.load_bsp(map_name)
        catalog = extract_entity_catalog(bsp, map_name)
        linked = link_w3_entity_catalog(
            build_indexed_entity_identity_index(geometry_index, map_name, bsp=bsp),
            catalog,
        )

        assert linked.map_name == map_name
        assert linked.runtime_entity_completeness == "unverified"
        for reference in linked.references:
            identity = linked.identity(reference)
            assert identity.entity_index == reference.entity_index
            assert identity.classname == reference.classname
            totals[reference.kind.value] += 1

    assert totals == {
        "spawn_point": 2376,
        "objective_volume": 158,
        "objective_marker": 96,
        "collision_entity": 1058,
    }


def test_w5b_projects_every_typed_stage_effect_to_action_specific_static_candidates(geometry_index):
    projection_counts = Counter()
    details = Counter()
    missing_source_effects = Counter()
    missing_source_alerts = []
    target_dispositions = Counter()
    missing_objectives = []
    blocked_autospawns = []

    for map_name in geometry_index.map_names:
        bsp = geometry_index.load_bsp(map_name)
        linked = link_w3_entity_catalog(
            build_indexed_entity_identity_index(geometry_index, map_name, bsp=bsp),
            extract_entity_catalog(bsp, map_name),
        )
        model = load_static_stage(geometry_index, map_name).model
        assert model is not None

        for node in model.graph.nodes:
            for effect in node.effects:
                projection = project_stage_effect(
                    effect,
                    source_script_name=node.entity_name,
                    linked=linked,
                    objectives=model.objectives,
                )
                projection_counts[type(projection).__name__] += 1
                if projection.source.lookup.resolution is EntityIdentityResolution.MISSING:
                    missing_source_effects[type(effect).__name__] += 1
                    if isinstance(effect, AlertEntityEffect):
                        missing_source_alerts.append((map_name, node.entity_name, effect.target, effect.line))

                if isinstance(projection, EntityTargetEffectProjection):
                    target_dispositions[projection.disposition] += 1
                    details[(type(effect).__name__, projection.target_lookup.resolution.value)] += 1
                    details[(type(effect).__name__, "w3_references")] += len(projection.selected_w3_references)
                elif isinstance(projection, GotoMarkerEffectProjection):
                    details[
                        (
                            "gotomarker",
                            projection.destination_lookup.namespace.value,
                            projection.destination_lookup.resolution.value,
                        )
                    ] += 1
                    details[("gotomarker", "relative_lookups")] += len(projection.relative_lookups)
                elif isinstance(projection, AutoSpawnEffectProjection):
                    details[("autospawn", projection.marker_lookup.resolution.value)] += 1
                    details[("autospawn", "marker_w3_references")] += len(projection.marker_w3_references)
                    details[("autospawn", "team_spawn_candidates")] += len(projection.team_spawn_candidates)
                    if projection.blocked_reason:
                        blocked_autospawns.append(
                            (map_name, effect.spawn_description, effect.team_code, projection.blocked_reason)
                        )
                elif isinstance(projection, ObjectiveStatusEffectProjection):
                    details[("objective_status", len(projection.descriptions))] += 1
                    details[("objective_status", projection.world_link_disposition.value)] += 1
                    assert projection.world_entity_candidates == ()
                    if not projection.descriptions:
                        missing_objectives.append((map_name, effect.objective_number, effect.team_code, effect.line))
                elif isinstance(projection, MainObjectiveEffectProjection):
                    details[("main_objective", projection.blocked_reason)] += 1
                elif isinstance(projection, GlobalStageEffectProjection):
                    details[("global", type(effect).__name__)] += 1
                elif isinstance(projection, EffectProjectionIssue):
                    details[("issue", projection.reason)] += 1

    assert projection_counts == {
        "EntityTargetEffectProjection": 1864,
        "ObjectiveStatusEffectProjection": 672,
        "GotoMarkerEffectProjection": 172,
        "AutoSpawnEffectProjection": 115,
        "GlobalStageEffectProjection": 64,
        "MainObjectiveEffectProjection": 42,
    }
    assert missing_source_effects == {"EntityStateEffect": 96, "AlertEntityEffect": 1}
    assert missing_source_alerts == [("sw_goldrush_te", "defense2_toi", "rubble3", 2570)]
    assert target_dispositions == {
        EntityTargetDisposition.STATIC_SOURCE_AND_TARGET: 1709,
        EntityTargetDisposition.STATIC_SOURCE_MISSING: 3,
        EntityTargetDisposition.STATIC_TARGET_MISSING: 58,
        EntityTargetDisposition.STATIC_SOURCE_AND_TARGET_MISSING: 94,
    }
    assert details == {
        ("AlertEntityEffect", "group"): 64,
        ("AlertEntityEffect", "unique"): 72,
        ("AlertEntityEffect", "w3_references"): 1636,
        ("EntityStateEffect", "group"): 182,
        ("EntityStateEffect", "missing"): 152,
        ("EntityStateEffect", "unique"): 1394,
        ("EntityStateEffect", "w3_references"): 1928,
        ("autospawn", "first_match"): 5,
        ("autospawn", "marker_w3_references"): 114,
        ("autospawn", "missing"): 1,
        ("autospawn", "team_spawn_candidates"): 7951,
        ("autospawn", "unique"): 109,
        ("global", "RoundEndEffect"): 22,
        ("global", "WinnerEffect"): 42,
        ("gotomarker", "path_corner", "first_match"): 1,
        ("gotomarker", "path_corner", "unique"): 93,
        ("gotomarker", "relative_lookups"): 0,
        ("gotomarker", "target_name", "unique"): 78,
        ("main_objective", "legacy_numeric_selector_is_unverified_for_the_live_build"): 42,
        ("objective_status", 0): 2,
        ("objective_status", 1): 670,
        ("objective_status", ObjectiveWorldLinkDisposition.UNPROVEN_ENGINE_KEY.value): 672,
    }
    assert missing_objectives == [
        ("etl_beach", 7, 0, 53),
        ("etl_beach", 7, 1, 54),
    ]
    assert blocked_autospawns == [("erdenberg_t2", "the Command Post", 1, "no_static_message_candidate")]


def test_w5b_projects_every_eligible_action_into_an_ordered_nonexecuted_program(geometry_index):
    counts = Counter()
    barriers = Counter()
    runtime_commands = Counter()
    runtime_controls = Counter()
    kill_dispositions = Counter()

    for map_name in geometry_index.map_names:
        bsp = geometry_index.load_bsp(map_name)
        linked = link_w3_entity_catalog(
            build_indexed_entity_identity_index(geometry_index, map_name, bsp=bsp),
            extract_entity_catalog(bsp, map_name),
        )
        model = load_static_stage(geometry_index, map_name).model
        assert model is not None

        programs = project_ordered_stage_programs(model, linked)
        counts["programs"] += len(programs)
        for program in programs:
            counts["instructions"] += len(program.instructions)
            for instruction in program.instructions:
                counts[type(instruction).__name__] += 1
                if isinstance(instruction, ControlBarrierInstruction):
                    barriers[instruction.kind.value] += 1
                elif isinstance(instruction, RuntimeActionInstruction):
                    runtime_commands[instruction.action.command] += 1
                    runtime_controls[instruction.control_disposition.value] += 1
                elif isinstance(instruction, KillInstruction):
                    kill_dispositions.update(target.disposition for target in instruction.targets)

    assert counts == {
        "programs": 2153,
        "instructions": 10057,
        "RuntimeActionInstruction": 3400,
        "KillInstruction": 13,
        "StageEffectInstruction": 2929,
        "TriggerInstruction": 1315,
        "AccumulatorMutation": 994,
        "ControlBarrierInstruction": 794,
        "AccumulatorAbortGuard": 313,
        "AccumulatorConditionalTrigger": 299,
    }
    assert barriers == {"wait": 745, "resetscript": 25, "halt": 24}
    assert runtime_commands == {
        "wm_teamvoiceannounce": 589,
        "setchargetimefactor": 420,
        "followspline": 302,
        "wm_announce": 274,
        "playsound": 241,
        "wm_addteamvoiceannounce": 239,
        "wm_removeteamvoiceannounce": 222,
        "faceangles": 143,
        "constructible_class": 110,
        "disablespeaker": 110,
        "stopsound": 99,
        "remove": 91,
        "sethqstatus": 85,
        "enablespeaker": 71,
        "remapshader": 70,
        "attachtotag": 43,
        "remapshaderflush": 35,
        "togglespeaker": 35,
        "setrotation": 31,
        "startanimation": 27,
        "wm_axis_respawntime": 20,
        "wm_allied_respawntime": 20,
        "wm_number_of_objectives": 20,
        "wm_set_round_timelimit": 20,
        "wm_set_defending_team": 17,
        "stoprotation": 13,
        "setspeed": 10,
        "set": 9,
        "changemodel": 8,
        "repairmg42": 7,
        "constructible_constructxpbonus": 5,
        "constructible_destructxpbonus": 4,
        "create": 4,
        "constructible_health": 3,
        "constructible_chargebarreq": 1,
        "constructible_weaponclass": 1,
        "constructible_duration": 1,
    }
    assert runtime_controls == {
        RuntimeActionControlDisposition.IMMEDIATE_CURRENT_EVENT_CONTINUE.value: 2860,
        RuntimeActionControlDisposition.CONDITIONAL_TEMPORAL_PAUSE.value: 445,
        RuntimeActionControlDisposition.DEFERRED_SOURCE_REMOVAL.value: 91,
        RuntimeActionControlDisposition.MAY_STOP_ON_SPAWN_FAILURE.value: 4,
    }
    assert kill_dispositions == {
        KillTargetDisposition.DIRECT_REMOVE_NO_SCRIPT_EVENT: 8,
        KillTargetDisposition.CONSTRUCTIBLE_NO_HANDLED_EVENT: 3,
        KillTargetDisposition.SCRIPT_MOVER_OPTIONAL_DEATH_EVENT: 2,
    }


def test_w5b_resolves_nested_dispatch_to_concrete_static_targets(geometry_index):
    instruction_resolutions = Counter()
    concrete_resolutions = Counter()
    target_group_sizes = Counter()
    resolved_pairs = Counter()
    same_entity_pairs = Counter()
    program_shapes = Counter()
    resolved_pair_shapes = Counter()

    for map_name in geometry_index.map_names:
        bsp = geometry_index.load_bsp(map_name)
        linked = link_w3_entity_catalog(
            build_indexed_entity_identity_index(geometry_index, map_name, bsp=bsp),
            extract_entity_catalog(bsp, map_name),
        )
        model = load_static_stage(geometry_index, map_name).model
        assert model is not None
        index = build_ordered_stage_program_index(model, linked)

        for program in index.programs:
            direct_temporal = _has_temporal_control(program.instructions)
            nested = _nested_instructions(program.instructions)
            program_shapes[(direct_temporal, bool(nested))] += 1
            for instruction in nested:
                kind = "conditional" if isinstance(instruction, AccumulatorConditionalTrigger) else "plain"
                source_indices = program.source.lookup.selected_entity_indices
                if not source_indices:
                    instruction_resolutions[(kind, "source_identity_missing")] += 1
                    continue

                resolutions = set()
                for source_index in source_indices:
                    dispatch = resolve_symbolic_nested_dispatch(
                        index,
                        program,
                        instruction,
                        source_entity_index=source_index,
                    )
                    resolutions.add(dispatch.resolution.value)
                    concrete_resolutions[(kind, dispatch.resolution.value)] += 1
                    if dispatch.resolution is SymbolicDispatchResolution.RESOLVED:
                        assert dispatch.target_node_id is not None
                        target_program = index.program(dispatch.target_node_id)
                        target_temporal = _has_temporal_control(target_program.instructions)
                        target_nested = bool(_nested_instructions(target_program.instructions))
                        target_group_sizes[(kind, len(dispatch.target_entity_indices))] += 1
                        resolved_pairs[kind] += len(dispatch.target_entity_indices)
                        same_entity_pairs[kind] += sum(
                            target_index == source_index for target_index in dispatch.target_entity_indices
                        )
                        for target_index in dispatch.target_entity_indices:
                            resolved_pair_shapes[
                                (
                                    "same" if target_index == source_index else "other",
                                    "temporal" if target_temporal else "immediate",
                                    "nested" if target_nested else "leaf",
                                )
                            ] += 1
                assert len(resolutions) == 1
                instruction_resolutions[(kind, resolutions.pop())] += 1

    assert instruction_resolutions == {
        ("plain", "resolved"): 1291,
        ("plain", "source_identity_missing"): 10,
        ("plain", "target_identity_missing"): 3,
        ("plain", "missing_handler"): 11,
        ("conditional", "resolved"): 299,
    }
    assert concrete_resolutions == {
        ("plain", "resolved"): 1588,
        ("plain", "target_identity_missing"): 3,
        ("plain", "missing_handler"): 11,
        ("conditional", "resolved"): 299,
    }
    assert target_group_sizes == {
        ("plain", 1): 1447,
        ("plain", 2): 13,
        ("plain", 3): 104,
        ("plain", 4): 15,
        ("plain", 6): 2,
        ("plain", 8): 6,
        ("plain", 32): 1,
        ("conditional", 1): 299,
    }
    assert resolved_pairs == {"plain": 1937, "conditional": 299}
    assert same_entity_pairs == {"plain": 669, "conditional": 289}
    assert program_shapes == {
        (False, False): 926,
        (False, True): 304,
        (True, False): 459,
        (True, True): 464,
    }
    assert resolved_pair_shapes == {
        ("other", "immediate", "leaf"): 899,
        ("other", "immediate", "nested"): 85,
        ("other", "temporal", "leaf"): 214,
        ("other", "temporal", "nested"): 80,
        ("same", "immediate", "leaf"): 235,
        ("same", "immediate", "nested"): 278,
        ("same", "temporal", "leaf"): 28,
        ("same", "temporal", "nested"): 417,
    }


@pytest.mark.timeout(120)
def test_w5b_bounded_nested_executor_smokes_every_concrete_event_entry(geometry_index):
    counts = Counter()
    frontier_counts = Counter()
    cross_frontier_counts = Counter()
    max_result_paths = 0

    for map_name in geometry_index.map_names:
        bsp = geometry_index.load_bsp(map_name)
        linked = link_w3_entity_catalog(
            build_indexed_entity_identity_index(geometry_index, map_name, bsp=bsp),
            extract_entity_catalog(bsp, map_name),
        )
        model = load_static_stage(geometry_index, map_name).model
        assert model is not None
        index = build_ordered_stage_program_index(model, linked)

        for program in index.programs:
            if not program.source.lookup.selected_entity_indices:
                counts["entries_missing_identity"] += 1
                continue
            for entity_index in program.source.lookup.selected_entity_indices:
                paths = walk_symbolic_stage_program(
                    index,
                    program,
                    source_entity_index=entity_index,
                    initial_state=SymbolicAccumulatorState.unknown(),
                    max_paths=16,
                )
                assert paths
                assert all(len(path.effects) == len(path.effect_entity_indices) for path in paths)
                assert all(
                    len(path.temporal_boundary_lines) == len(path.temporal_boundary_entity_indices) for path in paths
                )
                assert all(
                    len(path.caller_replacement_lines) == len(path.caller_replacement_entity_indices) for path in paths
                )
                assert sum(path.blocker_reason == "symbolic_path_budget_exhausted" for path in paths) <= 1
                counts["entries_walked"] += 1
                counts["paths"] += len(paths)
                max_result_paths = max(max_result_paths, len(paths))
                for path in paths:
                    counts["effects"] += len(path.effects)
                    counts["guard_decisions"] += len(path.guard_decisions)
                    counts["nested_dispatches"] += len(path.nested_dispatches)
                    counts["death_dispatches"] += len(path.death_dispatches)
                    counts["temporal_boundaries"] += len(path.temporal_boundary_lines)
                    counts["caller_replacements"] += len(path.caller_replacement_lines)
                    counts[("completion", path.completion.value)] += 1
                    if path.blocker_reason:
                        counts[("blocker", path.blocker_reason)] += 1
                        assert path.frontier_relevance is not None
                        relevance = path.frontier_relevance
                        domain_values = tuple(domain.value for domain in relevance.domains)
                        frontier_counts[("domain_set", domain_values)] += 1
                        frontier_counts[("unknown", relevance.unknown_domain_relevance)] += 1
                        for reason in relevance.unknown_reasons:
                            frontier_counts[("unknown_reason", reason)] += 1
                        if path.blocker_reason == "cross_entity_temporal_interleaving_not_modeled":
                            cross_frontier_counts[("domain_set", domain_values)] += 1
                            cross_frontier_counts[("unknown", relevance.unknown_domain_relevance)] += 1
                            for reason in relevance.unknown_reasons:
                                cross_frontier_counts[("unknown_reason", reason)] += 1
                    else:
                        assert path.frontier_relevance is None

    assert counts == {
        "entries_walked": 2790,
        "entries_missing_identity": 48,
        "paths": 4645,
        "effects": 7911,
        "guard_decisions": 2187,
        "nested_dispatches": 2782,
        "death_dispatches": 4,
        "temporal_boundaries": 2695,
        "caller_replacements": 360,
        ("completion", SymbolicPathCompletion.SYNCHRONOUS_COMPLETE.value): 2084,
        ("completion", SymbolicPathCompletion.EVENTUAL_COMPLETE.value): 1157,
        ("completion", SymbolicPathCompletion.ABORTED_BY_GUARD.value): 314,
        ("completion", SymbolicPathCompletion.BLOCKED.value): 1090,
        ("blocker", "cross_entity_temporal_interleaving_not_modeled"): 301,
        ("blocker", "nested_dispatch_cycle"): 200,
        ("blocker", "nested_dispatch_missing_handler"): 28,
        ("blocker", "nested_dispatch_target_identity_missing"): 3,
        ("blocker", "non_exact_accumulator_mutation"): 451,
        ("blocker", "spawn_failure_frontier"): 4,
        ("blocker", "symbolic_path_budget_exhausted"): 103,
    }
    assert frontier_counts == {
        ("domain_set", ()): 370,
        ("domain_set", ("dynamic_route",)): 372,
        ("domain_set", ("dynamic_route", "objective")): 211,
        ("domain_set", ("dynamic_route", "objective", "spawn")): 98,
        ("domain_set", ("dynamic_route", "spawn")): 22,
        ("domain_set", ("objective",)): 15,
        ("domain_set", ("objective", "spawn")): 1,
        ("domain_set", ("spawn",)): 1,
        ("unknown", False): 310,
        ("unknown", True): 780,
        ("unknown_reason", "effect_target_identity_missing"): 101,
        ("unknown_reason", "frontier:nested_dispatch_target_identity_missing"): 3,
        ("unknown_reason", "frontier:symbolic_path_budget_exhausted"): 103,
        ("unknown_reason", "frontier_relevance_nested_accumulator_state_unpropagated"): 435,
        ("unknown_reason", "frontier_relevance_stateful_cycle_cut"): 337,
        ("unknown_reason", "gotomarker_route_identity_unproven"): 4,
        ("unknown_reason", "nested_dispatch_target_identity_missing"): 2,
        ("unknown_reason", "runtime_route_source_not_w3_linked:attachtotag"): 110,
        ("unknown_reason", "runtime_route_source_not_w3_linked:faceangles"): 303,
        ("unknown_reason", "runtime_route_source_not_w3_linked:remove"): 136,
        ("unknown_reason", "runtime_route_source_not_w3_linked:setrotation"): 14,
        ("unknown_reason", "runtime_route_source_not_w3_linked:setspeed"): 24,
        ("unknown_reason", "runtime_route_source_not_w3_linked:stoprotation"): 236,
    }
    assert cross_frontier_counts == {
        ("domain_set", ()): 57,
        ("domain_set", ("dynamic_route",)): 171,
        ("domain_set", ("dynamic_route", "objective")): 49,
        ("domain_set", ("dynamic_route", "objective", "spawn")): 4,
        ("domain_set", ("dynamic_route", "spawn")): 18,
        ("domain_set", ("objective",)): 2,
        ("unknown", False): 175,
        ("unknown", True): 126,
        ("unknown_reason", "effect_target_identity_missing"): 5,
        ("unknown_reason", "frontier_relevance_nested_accumulator_state_unpropagated"): 50,
        ("unknown_reason", "frontier_relevance_stateful_cycle_cut"): 9,
        ("unknown_reason", "gotomarker_route_identity_unproven"): 4,
        ("unknown_reason", "runtime_route_source_not_w3_linked:attachtotag"): 11,
        ("unknown_reason", "runtime_route_source_not_w3_linked:faceangles"): 37,
        ("unknown_reason", "runtime_route_source_not_w3_linked:remove"): 41,
        ("unknown_reason", "runtime_route_source_not_w3_linked:setrotation"): 1,
        ("unknown_reason", "runtime_route_source_not_w3_linked:setspeed"): 22,
        ("unknown_reason", "runtime_route_source_not_w3_linked:stoprotation"): 1,
    }
    assert max_result_paths == 16


@pytest.mark.timeout(120)
def test_w4a2_compiles_every_real_patch_without_fail_open_gaps(geometry_index):
    totals = {
        "patches": 0,
        "facets": 0,
        "failures": 0,
        "wrapped": 0,
        "solid_wrapped": 0,
        "solid_nonsolid": 0,
        "solid_empty": 0,
    }
    for map_name in geometry_index.map_names:
        bsp = geometry_index.load_bsp(map_name)
        collisions = compile_bsp_patches(bsp)
        totals["patches"] += len(collisions)
        totals["facets"] += sum(len(collision.facets) for collision in collisions)
        totals["failures"] += sum(collision.error is not None for collision in collisions)
        totals["wrapped"] += sum(collision.wrap_width or collision.wrap_height for collision in collisions)
        totals["solid_wrapped"] += sum(
            (collision.wrap_width or collision.wrap_height) and bool(collision.content_flags & 1)
            for collision in collisions
        )
        totals["solid_nonsolid"] += sum(
            bool(bsp.shaders[surface.shader_index].surface_flags & 0x00004000)
            and bool(bsp.shaders[surface.shader_index].content_flags & 0x00000001)
            for surface in bsp.surfaces
            if surface.surface_type is SurfaceType.PATCH
        )
        totals["solid_empty"] += sum(
            bool(collision.content_flags & 1) and not collision.facets for collision in collisions
        )

    assert totals == {
        "patches": 4794,
        "facets": 22048,
        "failures": 0,
        "wrapped": 2718,
        "solid_wrapped": 2539,
        "solid_nonsolid": 0,
        "solid_empty": 0,
    }


@pytest.mark.timeout(120)
def test_w4a_real_spawn_segments_never_clear_with_unverified_runtime_collision(geometry_index):
    statuses = set()
    for map_name in geometry_index.map_names:
        bsp = geometry_index.load_bsp(map_name)
        catalog = extract_entity_catalog(bsp, map_name)
        axis_spawn = next(point for point in catalog.spawn_points if point.team == "AXIS")
        allies_spawn = next(point for point in catalog.spawn_points if point.team == "ALLIES")
        tracer = BspPointTracer(bsp, collision_entities=catalog.collision_entities)

        availability = tracer.trace_line_of_sight_availability(
            axis_spawn.origin,
            PlayerStance.STANDING,
            allies_spawn.origin,
            PlayerStance.STANDING,
        )

        statuses.add(availability.status)
        assert availability.status is not TraceStatus.CLEAR, map_name
        assert availability.interpretation == "line_of_sight_availability"
        assert availability.validation_status == "unvalidated_until_w6"
        if availability.status is TraceStatus.INDETERMINATE:
            assert any(
                TraceReason.RUNTIME_ENTITY_COMPLETENESS_UNVERIFIED in endpoint.result.uncertainty_reasons
                for endpoint in availability.endpoints
            ), map_name

    assert statuses <= {TraceStatus.BLOCKED, TraceStatus.INDETERMINATE}
