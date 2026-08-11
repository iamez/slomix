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
    SymbolicAccumulatorState,
    SymbolicIntegerDomain,
    SymbolicPathCompletion,
    TriggerInstruction,
    project_ordered_stage_programs,
    runtime_action_control_disposition,
    walk_symbolic_event_program,
)
from website.backend.map_geometry.stage_semantics import (
    AccumulatorAbortGuard,
    AccumulatorMutation,
    AccumulatorOperation,
    AccumulatorScope,
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


def _programs(raw_script, raw_entities=None):
    script = parse_map_script(raw_script, source="maps/test.script")
    model = SimpleNamespace(
        map_name="test",
        script=script,
        graph=compile_static_stage_graph(script, source="maps/test.script"),
        objectives=ObjectiveCatalog((), (), ()),
    )
    identities = build_entity_identity_index(
        raw_entities
        or (
            {"classname": "script_multiplayer"},
            {"classname": "func_door", "targetname": "gate"},
            {"classname": "script_mover", "scriptname": "helper"},
        ),
        source="maps/test.bsp",
    )
    catalog = MapEntityCatalog("test", "maps/test.bsp", (), (), (), ())
    return project_ordered_stage_programs(model, link_w3_entity_catalog(identities, catalog))


def test_projects_event_actions_in_source_order_without_executing_paths():
    model, linked = _model_and_linked()

    programs = project_ordered_stage_programs(model, linked)

    assert len(programs) == 2
    first = programs[0]
    assert first.node.entity_name == "game_manager"
    assert first.source.script_name == "game_manager"
    assert first.source.lookup.selected_entity_indices == (0,)
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


def test_known_abort_guard_suppresses_a_later_stage_effect():
    program = _programs(
        b"""
        game_manager
        {
            spawn
            {
                accum 0 set 1
                accum 0 abort_if_equal 1
                setstate gate invisible
            }
        }
        """
    )[0]

    paths = walk_symbolic_event_program(
        program,
        source_entity_index=0,
        initial_state=SymbolicAccumulatorState.zeroed(),
    )

    assert len(paths) == 1
    assert paths[0].completion is SymbolicPathCompletion.ABORTED_BY_GUARD
    assert paths[0].effects == ()
    assert paths[0].guard_decisions[0].predicate_result is True


def test_unknown_abort_guard_splits_and_refines_both_legal_paths():
    program = _programs(
        b"""
        game_manager
        {
            spawn
            {
                accum 0 abort_if_equal 1
                setstate gate invisible
            }
        }
        """
    )[0]

    paths = walk_symbolic_event_program(
        program,
        source_entity_index=0,
        initial_state=SymbolicAccumulatorState.unknown(),
    )

    assert {path.completion for path in paths} == {
        SymbolicPathCompletion.ABORTED_BY_GUARD,
        SymbolicPathCompletion.SYNCHRONOUS_COMPLETE,
    }
    aborted = next(path for path in paths if path.completion is SymbolicPathCompletion.ABORTED_BY_GUARD)
    continued = next(path for path in paths if path.completion is SymbolicPathCompletion.SYNCHRONOUS_COMPLETE)
    assert aborted.state.read(AccumulatorScope.ENTITY, 0, source_entity_index=0).exact_value == 1
    assert not continued.state.read(AccumulatorScope.ENTITY, 0, source_entity_index=0).contains(1)
    assert len(continued.effects) == 1


def test_contradictory_guard_constraints_do_not_publish_an_impossible_path():
    domain = SymbolicIntegerDomain()
    equal = domain.refine_guard(
        AccumulatorOperation.ABORT_IF_EQUAL,
        5,
        predicate_result=True,
    )
    assert equal is not None

    impossible = equal.refine_guard(
        AccumulatorOperation.ABORT_IF_NOT_EQUAL,
        5,
        predicate_result=True,
    )

    assert impossible is None


def test_bit_constraints_find_candidates_across_the_signed_zero_boundary():
    domain = SymbolicIntegerDomain(lower=-2, upper=1)

    bit_set = domain.refine_guard(
        AccumulatorOperation.ABORT_IF_BIT_SET,
        0,
        predicate_result=True,
    )
    bit_clear = domain.refine_guard(
        AccumulatorOperation.ABORT_IF_BIT_SET,
        0,
        predicate_result=False,
    )

    assert bit_set is not None
    assert bit_clear is not None
    assert bit_set.contains(-1)
    assert bit_set.contains(1)
    assert not bit_set.contains(0)
    assert bit_clear.contains(-2)
    assert bit_clear.contains(0)
    assert not bit_clear.contains(1)


@pytest.mark.parametrize(
    ("operation", "value", "operand", "expected_predicate"),
    (
        (AccumulatorOperation.ABORT_IF_LESS_THAN, 4, 5, True),
        (AccumulatorOperation.ABORT_IF_LESS_THAN, 5, 5, False),
        (AccumulatorOperation.ABORT_IF_GREATER_THAN, 6, 5, True),
        (AccumulatorOperation.ABORT_IF_GREATER_THAN, 5, 5, False),
        (AccumulatorOperation.ABORT_IF_NOT_EQUAL, 4, 5, True),
        (AccumulatorOperation.ABORT_IF_NOT_EQUAL, 5, 5, False),
        (AccumulatorOperation.ABORT_IF_EQUAL, 5, 5, True),
        (AccumulatorOperation.ABORT_IF_EQUAL, 4, 5, False),
        (AccumulatorOperation.ABORT_IF_BIT_SET, 4, 2, True),
        (AccumulatorOperation.ABORT_IF_BIT_SET, 0, 2, False),
        (AccumulatorOperation.ABORT_IF_NOT_BIT_SET, 0, 2, True),
        (AccumulatorOperation.ABORT_IF_NOT_BIT_SET, 4, 2, False),
    ),
)
def test_every_supported_abort_predicate_refines_the_exact_branch(
    operation,
    value,
    operand,
    expected_predicate,
):
    domain = SymbolicIntegerDomain.exact(value)

    matching = domain.refine_guard(operation, operand, predicate_result=expected_predicate)
    rejected = domain.refine_guard(operation, operand, predicate_result=not expected_predicate)

    assert matching == domain
    assert rejected is None


def test_entity_accumulators_are_isolated_while_global_accumulators_are_shared():
    state = SymbolicAccumulatorState.zeroed()
    state = state.write(
        AccumulatorScope.ENTITY,
        2,
        SymbolicIntegerDomain.exact(7),
        source_entity_index=10,
    )
    state = state.write(
        AccumulatorScope.GLOBAL,
        2,
        SymbolicIntegerDomain.exact(9),
        source_entity_index=10,
    )

    assert state.read(AccumulatorScope.ENTITY, 2, source_entity_index=10).exact_value == 7
    assert state.read(AccumulatorScope.ENTITY, 2, source_entity_index=11).exact_value == 0
    assert state.read(AccumulatorScope.GLOBAL, 2, source_entity_index=11).exact_value == 9


def test_wait_preserves_sudden_death_and_ordinary_temporal_paths():
    program = _programs(
        b"""
        game_manager
        {
            spawn
            {
                wait 100
                setstate gate invisible
            }
        }
        """
    )[0]

    paths = walk_symbolic_event_program(
        program,
        source_entity_index=0,
        initial_state=SymbolicAccumulatorState.zeroed(),
    )

    assert {path.completion for path in paths} == {
        SymbolicPathCompletion.SYNCHRONOUS_COMPLETE,
        SymbolicPathCompletion.EVENTUAL_COMPLETE,
    }
    assert all(len(path.effects) == 1 for path in paths)
    immediate = next(path for path in paths if path.completion is SymbolicPathCompletion.SYNCHRONOUS_COMPLETE)
    delayed = next(path for path in paths if path.completion is SymbolicPathCompletion.EVENTUAL_COMPLETE)
    assert immediate.temporal_boundary_lines == ()
    assert delayed.temporal_boundary_lines


@pytest.mark.parametrize("command", ("resetscript", "halt"))
def test_first_pass_barriers_only_preserve_the_eventual_continuation(command):
    program = _programs(
        f"""
        game_manager
        {{
            spawn
            {{
                {command}
                setstate gate invisible
            }}
        }}
        """.encode()
    )[0]

    paths = walk_symbolic_event_program(
        program,
        source_entity_index=0,
        initial_state=SymbolicAccumulatorState.zeroed(),
    )

    assert len(paths) == 1
    assert paths[0].completion is SymbolicPathCompletion.EVENTUAL_COMPLETE
    assert len(paths[0].effects) == 1
    assert paths[0].temporal_boundary_lines


def test_nonwaiting_spline_preserves_immediate_and_prior_motion_pause_paths():
    program = _programs(
        b"""
        game_manager
        {
            spawn
            {
                followspline 0 path 100
                setstate gate invisible
            }
        }
        """
    )[0]

    paths = walk_symbolic_event_program(
        program,
        source_entity_index=0,
        initial_state=SymbolicAccumulatorState.zeroed(),
    )

    assert {path.completion for path in paths} == {
        SymbolicPathCompletion.SYNCHRONOUS_COMPLETE,
        SymbolicPathCompletion.EVENTUAL_COMPLETE,
    }
    assert all(len(path.effects) == 1 for path in paths)


def test_create_preserves_success_path_and_spawn_failure_frontier():
    program = _programs(
        b"""
        game_manager
        {
            spawn
            {
                create
                {
                    classname func_fakebrush
                    origin "1 2 3"
                }
                setstate gate invisible
            }
        }
        """
    )[0]

    paths = walk_symbolic_event_program(
        program,
        source_entity_index=0,
        initial_state=SymbolicAccumulatorState.zeroed(),
    )

    assert {path.completion for path in paths} == {
        SymbolicPathCompletion.SYNCHRONOUS_COMPLETE,
        SymbolicPathCompletion.BLOCKED,
    }
    succeeded = next(path for path in paths if path.completion is SymbolicPathCompletion.SYNCHRONOUS_COMPLETE)
    failed = next(path for path in paths if path.completion is SymbolicPathCompletion.BLOCKED)
    assert len(succeeded.effects) == 1
    assert failed.effects == ()
    assert failed.blocker_reason == "spawn_failure_frontier"
    assert failed.blocker_line == 6


@pytest.mark.parametrize(
    ("accumulator_value", "completion", "effect_count"),
    (
        (0, SymbolicPathCompletion.SYNCHRONOUS_COMPLETE, 1),
        (1, SymbolicPathCompletion.BLOCKED, 0),
    ),
)
def test_conditional_trigger_only_blocks_the_dispatching_branch(
    accumulator_value,
    completion,
    effect_count,
):
    program = _programs(
        f"""
        game_manager
        {{
            spawn
            {{
                accum 0 set {accumulator_value}
                accum 0 trigger_if_equal 1 helper go
                setstate gate invisible
            }}
        }}
        helper
        {{
            trigger go
            {{
                wm_announce nested
            }}
        }}
        """.encode()
    )[0]

    paths = walk_symbolic_event_program(
        program,
        source_entity_index=0,
        initial_state=SymbolicAccumulatorState.zeroed(),
    )

    assert len(paths) == 1
    assert paths[0].completion is completion
    assert len(paths[0].effects) == effect_count
    assert paths[0].blocker_reason == (
        "conditional_trigger_dispatch_not_modeled" if completion is SymbolicPathCompletion.BLOCKED else None
    )


def test_plain_trigger_blocks_instead_of_skipping_a_nested_dispatch():
    program = _programs(
        b"""
        game_manager
        {
            spawn
            {
                trigger helper go
                setstate gate invisible
            }
        }
        helper
        {
            trigger go
            {
                wm_announce nested
            }
        }
        """
    )[0]

    paths = walk_symbolic_event_program(
        program,
        source_entity_index=0,
        initial_state=SymbolicAccumulatorState.zeroed(),
    )

    assert len(paths) == 1
    assert paths[0].completion is SymbolicPathCompletion.BLOCKED
    assert paths[0].effects == ()
    assert paths[0].blocker_reason == "trigger_dispatch_not_modeled"
    assert paths[0].blocker_line == 6


def test_non_exact_increment_fails_closed_until_symbolic_arithmetic_is_supported():
    program = _programs(
        b"""
        game_manager
        {
            spawn
            {
                accum 0 inc 1
            }
        }
        """
    )[0]

    paths = walk_symbolic_event_program(
        program,
        source_entity_index=0,
        initial_state=SymbolicAccumulatorState.unknown(),
    )

    assert paths[0].completion is SymbolicPathCompletion.BLOCKED
    assert paths[0].blocker_reason == "non_exact_accumulator_mutation"
    assert paths[0].blocker_line == 6


def test_signed_accumulator_overflow_fails_closed():
    program = _programs(
        b"""
        game_manager
        {
            spawn
            {
                accum 0 set 2147483647
                accum 0 inc 1
            }
        }
        """
    )[0]

    paths = walk_symbolic_event_program(
        program,
        source_entity_index=0,
        initial_state=SymbolicAccumulatorState.zeroed(),
    )

    assert paths[0].completion is SymbolicPathCompletion.BLOCKED
    assert paths[0].blocker_reason == "signed_accumulator_overflow_unverified"
    assert paths[0].blocker_line == 7


def test_walker_rejects_a_concrete_entity_outside_the_script_group():
    program = _programs(
        b"""
        helper
        {
            spawn
            {
                accum 0 set 1
            }
        }
        """,
        raw_entities=(
            {"classname": "script_mover", "scriptname": "helper"},
            {"classname": "script_mover", "scriptname": "helper"},
            {"classname": "script_mover", "scriptname": "other"},
        ),
    )[0]
    assert program.source.lookup.selected_entity_indices == (0, 1)

    with pytest.raises(ValueError, match="is not selected"):
        walk_symbolic_event_program(
            program,
            source_entity_index=2,
            initial_state=SymbolicAccumulatorState.zeroed(),
        )


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
