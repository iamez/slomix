"""W5b source-ordered control-program projection contracts."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from website.backend.map_geometry.entities import MapEntityCatalog
from website.backend.map_geometry.stage import ObjectiveCatalog, compile_static_stage_graph, parse_map_script
from website.backend.map_geometry.stage_possibilities import (
    ControlBarrierInstruction,
    ControlBarrierKind,
    RuntimeActionInstruction,
    StageEffectInstruction,
    TriggerInstruction,
    project_ordered_stage_programs,
)
from website.backend.map_geometry.stage_semantics import (
    AccumulatorAbortGuard,
    AccumulatorMutation,
    EntityTargetEffectProjection,
    build_entity_identity_index,
    link_w3_entity_catalog,
)


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
    assert first.instructions[7].blocker_reason == "control_semantics_not_classified"


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
