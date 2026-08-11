"""W5b source-ordered control-program projection contracts."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from website.backend.map_geometry.entities import MapEntityCatalog
from website.backend.map_geometry.stage import (
    ObjectiveCatalog,
    ScriptAction,
    compile_static_stage_graph,
    parse_map_script,
)
from website.backend.map_geometry.stage_possibilities import (
    ControlBarrierInstruction,
    ControlBarrierKind,
    RuntimeActionControlDisposition,
    RuntimeActionInstruction,
    StageEffectInstruction,
    TriggerInstruction,
    project_ordered_stage_programs,
    runtime_action_control_disposition,
)
from website.backend.map_geometry.stage_semantics import (
    AccumulatorAbortGuard,
    AccumulatorMutation,
    EntitySourceKind,
    EntityTargetEffectProjection,
    W3EntityIndexLinkDisposition,
    build_entity_identity_index,
    link_w3_entity_catalog,
)


def _action(command, *arguments):
    return ScriptAction(command, arguments, "", 1)


def _model_and_linked():
    script = parse_map_script(
        b"""
        game_manager
        {
            spawn
            {
                accum 0 set 1
                accum 0 abort_if_equal 2
                setstate gate invisible
                wait 100
                trigger helper go
                resetscript
                halt
                wm_announce ready
            }
        }
        helper
        {
            trigger go
            {
                setstate gate default
            }
        }
        """,
        source="maps/test.script",
    )
    graph = compile_static_stage_graph(script, source="maps/test.script")
    model = SimpleNamespace(
        map_name="test",
        script=script,
        graph=graph,
        objectives=ObjectiveCatalog((), (), ()),
    )
    identities = build_entity_identity_index(
        (
            {"classname": "script_multiplayer"},
            {"classname": "func_door", "targetname": "gate"},
            {"classname": "script_mover", "scriptname": "helper"},
        ),
        source="maps/test.bsp",
    )
    catalog = MapEntityCatalog("test", "maps/test.bsp", (), (), (), ())
    return model, link_w3_entity_catalog(identities, catalog)


def test_projects_event_actions_in_source_order_without_executing_paths():
    model, linked = _model_and_linked()

    programs = project_ordered_stage_programs(model, linked)

    assert len(programs) == 2
    first = programs[0]
    assert first.node.entity_name == "game_manager"
    assert tuple(type(instruction) for instruction in first.instructions) == (
        AccumulatorMutation,
        AccumulatorAbortGuard,
        StageEffectInstruction,
        ControlBarrierInstruction,
        TriggerInstruction,
        ControlBarrierInstruction,
        ControlBarrierInstruction,
        RuntimeActionInstruction,
    )
    stage = first.instructions[2]
    assert isinstance(stage, StageEffectInstruction)
    assert isinstance(stage.projection, EntityTargetEffectProjection)
    assert stage.projection.target_lookup.selected_entity_indices == (1,)
    assert isinstance(first.instructions[3], ControlBarrierInstruction)
    assert first.instructions[3].kind is ControlBarrierKind.WAIT
    assert isinstance(first.instructions[4], TriggerInstruction)
    assert first.instructions[4].edge.candidate_node_ids == (programs[1].node.node_id,)
    assert isinstance(first.instructions[5], ControlBarrierInstruction)
    assert first.instructions[5].kind is ControlBarrierKind.RESET_SCRIPT
    assert isinstance(first.instructions[6], ControlBarrierInstruction)
    assert first.instructions[6].kind is ControlBarrierKind.HALT
    assert isinstance(first.instructions[7], RuntimeActionInstruction)
    assert first.instructions[7].control_disposition is RuntimeActionControlDisposition.IMMEDIATE_CURRENT_EVENT_CONTINUE
    assert first.instructions[7].blocker_reason is None


@pytest.mark.parametrize(
    ("action", "expected"),
    (
        (_action("wm_announce"), RuntimeActionControlDisposition.IMMEDIATE_CURRENT_EVENT_CONTINUE),
        (
            _action("followspline", "0", "path", "100", "wait"),
            RuntimeActionControlDisposition.CONDITIONAL_TEMPORAL_PAUSE,
        ),
        (
            _action("followspline", "0", "path", "100"),
            RuntimeActionControlDisposition.CONDITIONAL_TEMPORAL_PAUSE,
        ),
        (
            _action("faceangles", "0", "90", "0", "500"),
            RuntimeActionControlDisposition.CONDITIONAL_TEMPORAL_PAUSE,
        ),
        (_action("remove"), RuntimeActionControlDisposition.DEFERRED_SOURCE_REMOVAL),
        (_action("kill", "target"), RuntimeActionControlDisposition.MAY_DISPATCH_DEATH_EVENT),
        (
            _action("set", "classname", "script_mover"),
            RuntimeActionControlDisposition.MAY_REPLACE_SCRIPT_CONTEXT,
        ),
        (
            _action("set", "ClassName", "script_mover"),
            RuntimeActionControlDisposition.MAY_REPLACE_SCRIPT_CONTEXT,
        ),
        (_action("create", "classname", "func_fakebrush"), RuntimeActionControlDisposition.MAY_STOP_ON_SPAWN_FAILURE),
        (_action("future_command"), RuntimeActionControlDisposition.UNCLASSIFIED),
    ),
)
def test_runtime_control_dispositions_fail_closed(action, expected):
    assert runtime_action_control_disposition(action) is expected


@pytest.mark.parametrize(
    "action",
    (
        _action("set", "origin", "1 2 3"),
        _action("set", "contents", "32", "clipmask", "32"),
        _action("set", "classname_nospawn", "script_mover"),
        _action("set", "classname", "script_mover", "classname_nospawn", "script_mover"),
        _action("set", "scriptName", "new_identity"),
    ),
)
def test_set_without_a_spawn_dispatch_continues_the_current_event(action):
    assert (
        runtime_action_control_disposition(action) is RuntimeActionControlDisposition.IMMEDIATE_CURRENT_EVENT_CONTINUE
    )


def test_only_actual_current_event_blockers_publish_a_blocker_reason():
    remove = RuntimeActionInstruction(
        _action("remove"),
        RuntimeActionControlDisposition.DEFERRED_SOURCE_REMOVAL,
    )
    faceangles = RuntimeActionInstruction(
        _action("faceangles", "0", "90", "0", "500"),
        RuntimeActionControlDisposition.CONDITIONAL_TEMPORAL_PAUSE,
    )

    assert remove.blocker_reason is None
    assert faceangles.blocker_reason == "conditional_temporal_pause"


def test_rejects_stage_and_geometry_models_from_different_maps():
    model, linked = _model_and_linked()
    mismatched = SimpleNamespace(
        map_name="other",
        script=model.script,
        graph=model.graph,
        objectives=model.objectives,
    )

    with pytest.raises(ValueError, match="does not match stage model"):
        project_ordered_stage_programs(mismatched, linked)


def test_rejects_drift_between_a_stage_action_and_its_typed_effect():
    model, linked = _model_and_linked()
    first_node = replace(model.graph.nodes[0], effects=())
    drifted = SimpleNamespace(
        map_name=model.map_name,
        script=model.script,
        graph=replace(model.graph, nodes=(first_node, *model.graph.nodes[1:])),
        objectives=model.objectives,
    )

    with pytest.raises(ValueError, match="stage-effect action.*has no projection"):
        project_ordered_stage_programs(drifted, linked)


def test_ent_override_projects_identity_effects_without_reusing_bsp_entity_indices():
    model, _linked = _model_and_linked()
    identities = build_entity_identity_index(
        (
            {"classname": "script_multiplayer"},
            {"classname": "func_door", "targetname": "gate"},
            {"classname": "script_mover", "scriptname": "helper"},
        ),
        source="override.pk3!/maps/test.ent",
        source_kind=EntitySourceKind.ENT_OVERRIDE,
    )
    bsp_catalog = MapEntityCatalog(
        "test",
        "geometry.pk3!/maps/test.bsp",
        (),
        (),
        (),
        (SimpleNamespace(entity_index=1, classname="func_door"),),
    )
    context = link_w3_entity_catalog(identities, bsp_catalog)

    programs = project_ordered_stage_programs(model, context)
    projection = programs[0].instructions[2]

    assert context.catalog is None
    assert context.references == ()
    assert context.entity_index_link_disposition is W3EntityIndexLinkDisposition.UNPROVEN_IDENTITY_OVERRIDE
    assert isinstance(projection, StageEffectInstruction)
    assert isinstance(projection.projection, EntityTargetEffectProjection)
    assert projection.projection.target_lookup.selected_entity_indices == (1,)
    assert projection.projection.selected_w3_references == ()
    assert (
        projection.projection.entity_index_link_disposition is W3EntityIndexLinkDisposition.UNPROVEN_IDENTITY_OVERRIDE
    )
