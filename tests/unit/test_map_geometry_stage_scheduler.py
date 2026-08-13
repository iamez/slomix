"""S1 immutable scheduler-state and canonicalization contracts."""

from dataclasses import replace
from pathlib import Path

import pytest

from website.backend.map_geometry.entities import MapEntityCatalog
from website.backend.map_geometry.pk3_index import MapAssetKind, MapAssetProvider
from website.backend.map_geometry.stage import (
    EntityStateEffect,
    ObjectiveCatalog,
    StaticStageModel,
    compile_static_stage_graph,
    parse_map_script,
)
from website.backend.map_geometry.stage_possibilities import (
    StageEffectInstruction,
    SymbolicAccumulatorState,
    SymbolicIntegerDomain,
    SymbolicTemporalBoundaryState,
    build_ordered_stage_program_index,
)
from website.backend.map_geometry.stage_scheduler import (
    PendingDispatchContext,
    SuspendedContinuation,
    SymbolicAsyncMovementLifecycle,
    SymbolicEffectRecord,
    SymbolicEventOwner,
    SymbolicFrame,
    SymbolicFrameOrigin,
    SymbolicInvocationStep,
    SymbolicMovementBoundaryState,
    SymbolicMovementCommand,
    SymbolicNextFrameBoundaryState,
    SymbolicNextFrameCommand,
    SymbolicProgramCursor,
    SymbolicResumeMode,
    SymbolicScheduleDecision,
    SymbolicScheduleDecisionKind,
    SymbolicScheduleExhaustion,
    SymbolicScheduleResult,
    SymbolicScheduleState,
    SymbolicScheduleWorkBudget,
    SymbolicTagParentDisposition,
    SymbolicTagParentState,
    SymbolicWaitBoundaryState,
    SymbolicWaitBranch,
    SymbolicWakeConstraint,
    step_symbolic_schedule,
)
from website.backend.map_geometry.stage_semantics import (
    AccumulatorScope,
    build_entity_identity_index,
    link_w3_entity_catalog,
)


def _asset_provider(kind: MapAssetKind) -> MapAssetProvider:
    return MapAssetProvider(
        "test",
        kind,
        Path("/assets/test.pk3"),
        f"maps/test.{kind.value}",
        0,
        0,
        0,
        "0" * 64,
    )


def _program_index():
    script = parse_map_script(
        b"""
        caller
        {
            spawn
            {
                trigger target long
                trigger target long
                setstate gate invisible
            }
        }
        target
        {
            trigger long
            {
                wait 100
                setstate gate default
            }
            trigger replacement
            {
                wait 200
                setstate gate underconstruction
            }
        }
        """,
        source="maps/test.script",
    )
    model = StaticStageModel(
        "test",
        ObjectiveCatalog((), (), ()),
        script,
        compile_static_stage_graph(script, source="maps/test.script"),
        _asset_provider(MapAssetKind.SCRIPT),
        _asset_provider(MapAssetKind.OBJDATA),
    )
    identities = build_entity_identity_index(
        (
            {"classname": "script_mover", "scriptname": "caller"},
            {"classname": "script_mover", "scriptname": "target"},
            {"classname": "func_door", "targetname": "gate"},
            {"classname": "script_mover", "scriptname": "target"},
            {"classname": "script_mover", "scriptname": "target"},
        ),
        source="maps/test.bsp",
    )
    catalog = MapEntityCatalog("test", "maps/test.bsp", (), (), (), ())
    return build_ordered_stage_program_index(model, link_w3_entity_catalog(identities, catalog))


def _program(index, entity_name: str, event_parameters: str = ""):
    return next(
        program
        for program in index.programs
        if program.node.entity_name == entity_name and program.node.serialized_event_parameters == event_parameters
    )


def _frame(
    node_id: str,
    entity_index: int,
    instruction_offset: int,
    *,
    pending_dispatch: PendingDispatchContext | None = None,
    origin: SymbolicFrameOrigin = SymbolicFrameOrigin.ROOT_EVENT,
    invocation_path: tuple[SymbolicInvocationStep, ...] = (),
) -> SymbolicFrame:
    return SymbolicFrame(
        SymbolicProgramCursor(node_id, entity_index, instruction_offset),
        invocation_path=invocation_path,
        pending_dispatch=pending_dispatch,
        origin=origin,
    )


def _state(index, frame: SymbolicFrame, **changes) -> SymbolicScheduleState:
    return SymbolicScheduleState.create(
        index,
        accumulator_state=changes.pop("accumulator_state", SymbolicAccumulatorState.zeroed()),
        runnable=changes.pop("runnable", (frame,)),
        suspended=changes.pop("suspended", ()),
        event_owners=changes.pop("event_owners", (SymbolicEventOwner.from_frame(frame),)),
        **changes,
    )


def _pending(index, *, dispatch_offset=0, resume_offset=1, targets=(1,), target_cursor=0):
    caller = _program(index, "caller")
    target = _program(index, "target", "long")
    return PendingDispatchContext(
        SymbolicProgramCursor(caller.node.node_id, 0, dispatch_offset),
        SymbolicProgramCursor(caller.node.node_id, 0, resume_offset),
        target.node.node_id,
        targets,
        target_cursor,
    )


def test_equal_semantic_states_have_one_canonical_key():
    index = _program_index()
    target = _program(index, "target", "long")
    frame = _frame(target.node.node_id, 1, 0)
    zero = SymbolicIntegerDomain.exact(0)
    seven = SymbolicIntegerDomain.exact(7)

    left = _state(
        index,
        frame,
        accumulator_state=SymbolicAccumulatorState(
            ((1, 2, seven), (1, 0, zero)),
            ((3, zero),),
        ),
        tag_parent_states=(
            SymbolicTagParentState(4, SymbolicTagParentDisposition.UNKNOWN),
            SymbolicTagParentState(2, SymbolicTagParentDisposition.PROVEN_UNATTACHED),
        ),
        unknown_reasons=("wake_semantics_unverified", "wake_semantics_unverified"),
    )
    right = _state(
        index,
        frame,
        accumulator_state=SymbolicAccumulatorState(((1, 2, seven),)),
        tag_parent_states=(
            SymbolicTagParentState(2, SymbolicTagParentDisposition.PROVEN_UNATTACHED),
            SymbolicTagParentState(4, SymbolicTagParentDisposition.UNKNOWN),
        ),
        unknown_reasons=("wake_semantics_unverified",),
    )

    assert left == right
    assert left.canonical_key == right.canonical_key
    assert hash(left.canonical_key) == hash(right.canonical_key)


def test_effect_identity_includes_concrete_source_entity_and_instruction():
    script = parse_map_script(
        b"""
        shared
        {
            spawn
            {
                setstate gate invisible
                wait 100
            }
        }
        """,
        source="maps/test.script",
    )
    model = StaticStageModel(
        "test",
        ObjectiveCatalog((), (), ()),
        script,
        compile_static_stage_graph(script, source="maps/test.script"),
        _asset_provider(MapAssetKind.SCRIPT),
        _asset_provider(MapAssetKind.OBJDATA),
    )
    identities = build_entity_identity_index(
        (
            {"classname": "script_mover", "scriptname": "shared"},
            {"classname": "script_mover", "scriptname": "shared"},
            {"classname": "func_door", "targetname": "gate"},
        ),
        source="maps/test.bsp",
    )
    catalog = MapEntityCatalog("test", "maps/test.bsp", (), (), (), ())
    index = build_ordered_stage_program_index(model, link_w3_entity_catalog(identities, catalog))
    program = _program(index, "shared")
    projection = program.instructions[0].projection
    frame = _frame(program.node.node_id, 0, 1)

    left = _state(
        index,
        frame,
        effects=(SymbolicEffectRecord(projection, SymbolicProgramCursor(program.node.node_id, 0, 0)),),
    )
    right = _state(
        index,
        frame,
        effects=(SymbolicEffectRecord(projection, SymbolicProgramCursor(program.node.node_id, 1, 0)),),
    )

    assert left.canonical_key != right.canonical_key
    with pytest.raises(ValueError, match="does not identify a stage effect"):
        _state(
            index,
            frame,
            effects=(SymbolicEffectRecord(projection, SymbolicProgramCursor(program.node.node_id, 0, 1)),),
        )


def test_pending_dispatch_identity_cannot_drop_parent_cursor_target_cursor_or_order():
    index = _program_index()

    def key(pending):
        target_entity_index = pending.ordered_target_entity_indices[pending.target_cursor]
        invocation = SymbolicInvocationStep(
            pending.dispatch_cursor,
            pending.target_node_id,
            pending.target_cursor,
        )
        frame = _frame(
            pending.target_node_id,
            target_entity_index,
            0,
            pending_dispatch=pending,
            origin=SymbolicFrameOrigin.NESTED_DISPATCH,
            invocation_path=(invocation,),
        )
        return _state(index, frame).canonical_key

    baseline = _pending(index, targets=(1, 3, 4), target_cursor=0)
    variants = (
        _pending(index, dispatch_offset=1, resume_offset=2, targets=(1, 3, 4), target_cursor=0),
        _pending(index, targets=(1, 3, 4), target_cursor=1),
    )

    baseline_key = key(baseline)
    assert all(key(variant) != baseline_key for variant in variants)

    reordered = _pending(index, targets=(3, 1, 4), target_cursor=0)
    with pytest.raises(ValueError, match="target order does not match"):
        key(reordered)

    skipped_caller_suffix = _pending(index, resume_offset=2, targets=(1, 3, 4), target_cursor=0)
    with pytest.raises(ValueError, match="resume immediately after"):
        key(skipped_caller_suffix)

    mismatched_cursor = replace(baseline, target_cursor=2)
    target = _program(index, "target", "long")
    ordinal_zero = SymbolicInvocationStep(
        baseline.dispatch_cursor,
        target.node.node_id,
        0,
    )
    inconsistent_frame = _frame(
        target.node.node_id,
        1,
        0,
        pending_dispatch=mismatched_cursor,
        origin=SymbolicFrameOrigin.NESTED_DISPATCH,
        invocation_path=(ordinal_zero,),
    )
    with pytest.raises(ValueError, match="active nested target frame"):
        _state(index, inconsistent_frame)


def test_caller_suffix_completion_is_continuation_identity():
    index = _program_index()
    target = _program(index, "target", "long")
    pending = _pending(index, targets=(1, 3, 4), target_cursor=0)
    invocation = SymbolicInvocationStep(pending.dispatch_cursor, pending.target_node_id, 0)
    frame = _frame(
        target.node.node_id,
        1,
        0,
        pending_dispatch=pending,
        origin=SymbolicFrameOrigin.NESTED_DISPATCH,
        invocation_path=(invocation,),
    )
    continuation = SuspendedContinuation(
        frame,
        boundary_line=target.event.actions[0].line,
        resume_mode=SymbolicResumeMode.REENTER_BOUNDARY_ACTION,
        boundary_state=SymbolicWaitBoundaryState(("100",)),
        wake_constraint=SymbolicWakeConstraint.NEXT_FRAME,
    )

    before = _state(index, frame, runnable=(), suspended=(continuation,))
    after = _state(
        index,
        frame,
        runnable=(),
        suspended=(replace(continuation, caller_suffix_completed=True),),
    )
    assert before.canonical_key != after.canonical_key

    root = replace(frame, pending_dispatch=None, invocation_path=(), origin=SymbolicFrameOrigin.ROOT_EVENT)
    invalid = replace(continuation, frame=root, caller_suffix_completed=True)
    with pytest.raises(ValueError, match="nested dispatch continuation"):
        _state(index, root, runnable=(), suspended=(invalid,))


def test_invocation_ordinal_must_select_the_exact_dispatch_target_group():
    index = _program_index()
    caller = _program(index, "caller")
    target = _program(index, "target", "long")

    valid = SymbolicInvocationStep(
        SymbolicProgramCursor(caller.node.node_id, 0, 0),
        target.node.node_id,
        2,
    )
    valid.validate(index)

    matching_frame = _frame(
        target.node.node_id,
        4,
        0,
        invocation_path=(valid,),
        origin=SymbolicFrameOrigin.NESTED_DISPATCH,
    )
    _state(index, matching_frame)

    mismatched_frame = _frame(
        target.node.node_id,
        1,
        0,
        invocation_path=(valid,),
        origin=SymbolicFrameOrigin.NESTED_DISPATCH,
    )
    with pytest.raises(ValueError, match="does not terminate"):
        _state(index, mismatched_frame)

    with pytest.raises(ValueError, match="ordinal is outside"):
        SymbolicInvocationStep(
            SymbolicProgramCursor(caller.node.node_id, 0, 0),
            target.node.node_id,
            3,
        ).validate(index)


def test_self_dispatch_target_group_contains_only_the_concrete_caller():
    script = parse_map_script(
        b"""
        shared
        {
            spawn
            {
                trigger self go
            }
            trigger go
            {
                wait 100
            }
        }
        """,
        source="maps/test.script",
    )
    model = StaticStageModel(
        "test",
        ObjectiveCatalog((), (), ()),
        script,
        compile_static_stage_graph(script, source="maps/test.script"),
        _asset_provider(MapAssetKind.SCRIPT),
        _asset_provider(MapAssetKind.OBJDATA),
    )
    identities = build_entity_identity_index(
        (
            {"classname": "script_mover", "scriptname": "shared"},
            {"classname": "script_mover", "scriptname": "shared"},
        ),
        source="maps/test.bsp",
    )
    catalog = MapEntityCatalog("test", "maps/test.bsp", (), (), (), ())
    index = build_ordered_stage_program_index(model, link_w3_entity_catalog(identities, catalog))
    spawn = _program(index, "shared")
    target = _program(index, "shared", "go")
    pending = PendingDispatchContext(
        SymbolicProgramCursor(spawn.node.node_id, 1, 0),
        SymbolicProgramCursor(spawn.node.node_id, 1, 1),
        target.node.node_id,
        (1,),
        0,
    )

    pending.validate(index)
    SymbolicInvocationStep(pending.dispatch_cursor, target.node.node_id, 0).validate(index)
    with pytest.raises(ValueError, match="target order does not match"):
        replace(pending, ordered_target_entity_indices=(0, 1)).validate(index)


def test_heterogeneous_alert_dispatch_group_fails_closed():
    script = parse_map_script(
        b"""
        caller
        {
            spawn
            {
                alertentity shared_target
            }
        }
        victim
        {
            death
            {
                wait 100
            }
        }
        vehicle
        {
            rebirth
            {
                wait 100
            }
        }
        """,
        source="maps/test.script",
    )
    model = StaticStageModel(
        "test",
        ObjectiveCatalog((), (), ()),
        script,
        compile_static_stage_graph(script, source="maps/test.script"),
        _asset_provider(MapAssetKind.SCRIPT),
        _asset_provider(MapAssetKind.OBJDATA),
    )
    identities = build_entity_identity_index(
        (
            {"classname": "script_mover", "scriptname": "caller"},
            {
                "classname": "func_explosive",
                "scriptname": "victim",
                "targetname": "shared_target",
                "spawnflags": "4",
            },
            {
                "classname": "script_mover",
                "scriptname": "vehicle",
                "targetname": "shared_target",
                "spawnflags": "8",
                "health": "100",
            },
        ),
        source="maps/test.bsp",
    )
    catalog = MapEntityCatalog("test", "maps/test.bsp", (), (), (), ())
    index = build_ordered_stage_program_index(model, link_w3_entity_catalog(identities, catalog))
    caller = _program(index, "caller")
    victim = _program(index, "victim")
    pending = PendingDispatchContext(
        SymbolicProgramCursor(caller.node.node_id, 0, 0),
        SymbolicProgramCursor(caller.node.node_id, 0, 1),
        victim.node.node_id,
        (1,),
        0,
    )

    with pytest.raises(ValueError, match="heterogeneous alert dispatch order"):
        pending.validate(index)


def test_boundary_state_and_resume_mode_do_not_canonicalize():
    index = _program_index()
    target = _program(index, "target", "long")
    frame = _frame(target.node.node_id, 1, 0)

    def key(boundary_state, resume_mode=SymbolicResumeMode.REENTER_BOUNDARY_ACTION):
        suspended = SuspendedContinuation(
            frame,
            boundary_line=target.event.actions[0].line,
            resume_mode=resume_mode,
            boundary_state=boundary_state,
            wake_constraint=SymbolicWakeConstraint.NEXT_FRAME,
        )
        return _state(index, frame, runnable=(), suspended=(suspended,)).canonical_key

    wait_100 = SymbolicWaitBoundaryState(("100",))
    assert wait_100.branch is SymbolicWaitBranch.SUSPENDED_FALSE_RETURN
    with pytest.raises(ValueError, match="does not match its source action"):
        key(SymbolicWaitBoundaryState(("200",)))
    with pytest.raises(ValueError, match="must re-enter"):
        key(wait_100, "resume_target_group")
    movement = SymbolicMovementBoundaryState(
        SymbolicMovementCommand.GOTO_MARKER,
        ("destination", "100", "wait"),
        temporal_state=SymbolicTemporalBoundaryState.CURRENT_ACTION_WAITING,
        waits_for_completion=True,
        effect_started=True,
        effect_record_index=0,
    )
    assert movement.temporal_state is SymbolicTemporalBoundaryState.CURRENT_ACTION_WAITING


def _temporal_program_index():
    script = parse_map_script(
        b"""
        temporal
        {
            trigger wait_event
            {
                wait 100
            }
            trigger spline_wait
            {
                followspline 0 path 100 wait
            }
            trigger face_wait
            {
                faceangles 0 90 0 500
            }
            trigger spline_async
            {
                followspline 0 path 100
                setstate gate invisible
            }
            trigger marker_wait
            {
                gotomarker destination 100 wait
            }
            trigger marker_async
            {
                gotomarker destination 100
                setstate gate invisible
            }
            trigger reset_event
            {
                resetscript
            }
        }
        """,
        source="maps/test.script",
    )
    model = StaticStageModel(
        "test",
        ObjectiveCatalog((), (), ()),
        script,
        compile_static_stage_graph(script, source="maps/test.script"),
        _asset_provider(MapAssetKind.SCRIPT),
        _asset_provider(MapAssetKind.OBJDATA),
    )
    identities = build_entity_identity_index(
        (
            {"classname": "script_mover", "scriptname": "temporal"},
            {"classname": "func_door", "targetname": "gate"},
            {"classname": "path_corner_2", "targetname": "destination"},
        ),
        source="maps/test.bsp",
    )
    catalog = MapEntityCatalog("test", "maps/test.bsp", (), (), (), ())
    return build_ordered_stage_program_index(model, link_w3_entity_catalog(identities, catalog))


def _suspended_temporal_state(index, event_name, boundary_state, resume_mode):
    program = _program(index, "temporal", event_name)
    frame = _frame(program.node.node_id, 0, 0)
    continuation = SuspendedContinuation(
        frame,
        boundary_line=program.event.actions[0].line,
        resume_mode=resume_mode,
        boundary_state=boundary_state,
        wake_constraint=SymbolicWakeConstraint.NEXT_FRAME,
    )
    return _state(index, frame, runnable=(), suspended=(continuation,))


@pytest.mark.parametrize(
    ("event_name", "boundary_state"),
    (
        ("wait_event", SymbolicWaitBoundaryState(("100",))),
        (
            "spline_wait",
            SymbolicMovementBoundaryState(
                SymbolicMovementCommand.FOLLOW_SPLINE,
                ("0", "path", "100", "wait"),
                SymbolicTemporalBoundaryState.CURRENT_ACTION_WAITING,
                True,
                True,
            ),
        ),
        (
            "face_wait",
            SymbolicMovementBoundaryState(
                SymbolicMovementCommand.FACE_ANGLES,
                ("0", "90", "0", "500"),
                SymbolicTemporalBoundaryState.CURRENT_ACTION_WAITING,
                True,
                True,
            ),
        ),
    ),
)
def test_waiting_actions_reject_async_lifecycle_resume_mode(event_name, boundary_state):
    index = _temporal_program_index()

    with pytest.raises(ValueError, match="must re-enter"):
        _suspended_temporal_state(
            index,
            event_name,
            boundary_state,
            "advance_after_async_lifecycle",
        )


@pytest.mark.parametrize(
    "resume_mode",
    ("resume_caller_suffix", "resume_target_group"),
)
def test_current_action_boundary_rejects_group_or_caller_resume_mode(resume_mode):
    index = _temporal_program_index()

    with pytest.raises(ValueError, match="must re-enter"):
        _suspended_temporal_state(
            index,
            "wait_event",
            SymbolicWaitBoundaryState(("100",)),
            resume_mode,
        )


def test_nonwaiting_movement_is_async_lifecycle_not_suspended_script():
    index = _temporal_program_index()
    program = _program(index, "temporal", "spline_async")
    movement = SymbolicMovementBoundaryState(
        SymbolicMovementCommand.FOLLOW_SPLINE,
        ("0", "path", "100"),
        SymbolicTemporalBoundaryState.CURRENT_ACTION_WAITING,
        False,
        True,
    )
    with pytest.raises(ValueError, match="cannot suspend after its action starts"):
        _suspended_temporal_state(
            index,
            "spline_async",
            movement,
            SymbolicResumeMode.REENTER_BOUNDARY_ACTION,
        )

    lifecycle = SymbolicAsyncMovementLifecycle(
        SymbolicProgramCursor(program.node.node_id, 0, 0),
        SymbolicMovementCommand.FOLLOW_SPLINE,
        ("0", "path", "100"),
    )
    suffix = _frame(program.node.node_id, 0, 1, origin=SymbolicFrameOrigin.CALLER_SUFFIX)
    state = _state(index, suffix, async_lifecycles=(lifecycle,))
    assert state.async_lifecycles == (lifecycle,)

    waiting_program = _program(index, "temporal", "spline_wait")
    waiting = SymbolicAsyncMovementLifecycle(
        SymbolicProgramCursor(waiting_program.node.node_id, 0, 0),
        SymbolicMovementCommand.FOLLOW_SPLINE,
        ("0", "path", "100", "wait"),
    )
    with pytest.raises(ValueError, match="waiting movement cannot"):
        _state(index, suffix, async_lifecycles=(waiting,))

    waiting_frame = _frame(waiting_program.node.node_id, 0, 0)
    waiting_continuation = SuspendedContinuation(
        waiting_frame,
        boundary_line=waiting_program.event.actions[0].line,
        resume_mode=SymbolicResumeMode.REENTER_BOUNDARY_ACTION,
        boundary_state=SymbolicMovementBoundaryState(
            SymbolicMovementCommand.FOLLOW_SPLINE,
            ("0", "path", "100", "wait"),
            SymbolicTemporalBoundaryState.CURRENT_ACTION_WAITING,
            True,
            True,
        ),
        wake_constraint=SymbolicWakeConstraint.NEXT_FRAME,
    )
    with pytest.raises(ValueError, match="cannot start while"):
        _state(
            index,
            waiting_frame,
            runnable=(),
            suspended=(waiting_continuation,),
            async_lifecycles=(lifecycle,),
        )

    prior_motion_continuation = replace(
        waiting_continuation,
        boundary_state=replace(
            waiting_continuation.boundary_state,
            temporal_state=SymbolicTemporalBoundaryState.PRIOR_MOVEMENT_ACTIVE,
            effect_started=False,
        ),
    )
    prior_motion_state = _state(
        index,
        waiting_frame,
        runnable=(),
        suspended=(prior_motion_continuation,),
        async_lifecycles=(lifecycle,),
    )
    assert prior_motion_state.async_lifecycles == (lifecycle,)


def test_started_gotomarker_state_requires_its_exact_route_effect_record():
    index = _temporal_program_index()
    waiting_program = _program(index, "temporal", "marker_wait")
    waiting_frame = _frame(waiting_program.node.node_id, 0, 0)
    waiting_projection = waiting_program.instructions[0].projection
    waiting_effect = SymbolicEffectRecord(waiting_projection, waiting_frame.cursor)
    waiting = SuspendedContinuation(
        waiting_frame,
        boundary_line=waiting_program.event.actions[0].line,
        resume_mode=SymbolicResumeMode.REENTER_BOUNDARY_ACTION,
        boundary_state=SymbolicMovementBoundaryState(
            SymbolicMovementCommand.GOTO_MARKER,
            ("destination", "100", "wait"),
            SymbolicTemporalBoundaryState.CURRENT_ACTION_WAITING,
            True,
            True,
            0,
        ),
        wake_constraint=SymbolicWakeConstraint.NEXT_FRAME,
    )

    with pytest.raises(ValueError, match="outside scheduler effect history"):
        _state(index, waiting_frame, runnable=(), suspended=(waiting,))
    started = _state(index, waiting_frame, runnable=(), suspended=(waiting,), effects=(waiting_effect,))
    assert started.effects == (waiting_effect,)

    prior_motion = replace(
        waiting,
        boundary_state=replace(
            waiting.boundary_state,
            temporal_state=SymbolicTemporalBoundaryState.PRIOR_MOVEMENT_ACTIVE,
            effect_started=False,
            effect_record_index=None,
        ),
    )
    _state(index, waiting_frame, runnable=(), suspended=(prior_motion,))
    historical = _state(
        index,
        waiting_frame,
        runnable=(),
        suspended=(prior_motion,),
        effects=(waiting_effect,),
    )
    assert historical.effects == (waiting_effect,)

    async_program = _program(index, "temporal", "marker_async")
    async_cursor = SymbolicProgramCursor(async_program.node.node_id, 0, 0)
    async_effect = SymbolicEffectRecord(async_program.instructions[0].projection, async_cursor)
    lifecycle = SymbolicAsyncMovementLifecycle(
        async_cursor,
        SymbolicMovementCommand.GOTO_MARKER,
        ("destination", "100"),
        0,
    )
    suffix = _frame(async_program.node.node_id, 0, 1, origin=SymbolicFrameOrigin.CALLER_SUFFIX)
    with pytest.raises(ValueError, match="outside scheduler effect history"):
        _state(index, suffix, async_lifecycles=(lifecycle,))
    running = _state(index, suffix, async_lifecycles=(lifecycle,), effects=(async_effect,))
    assert running.async_lifecycles == (lifecycle,)


def test_next_frame_boundary_rejects_same_frame_wake():
    index = _temporal_program_index()
    program = _program(index, "temporal", "reset_event")
    frame = _frame(program.node.node_id, 0, 0)

    def continuation(wake_constraint):
        return SuspendedContinuation(
            frame,
            boundary_line=program.event.actions[0].line,
            resume_mode=SymbolicResumeMode.REENTER_BOUNDARY_ACTION,
            boundary_state=SymbolicNextFrameBoundaryState(SymbolicNextFrameCommand.RESET_SCRIPT),
            wake_constraint=wake_constraint,
        )

    _state(index, frame, runnable=(), suspended=(continuation(SymbolicWakeConstraint.NEXT_FRAME),))
    with pytest.raises(ValueError, match="requires a next-frame wake"):
        _state(
            index,
            frame,
            runnable=(),
            suspended=(continuation(SymbolicWakeConstraint.SAME_FRAME_LATER),),
        )


def test_r1_replacement_contract_keeps_exactly_one_deterministic_event_owner():
    index = _program_index()
    long_program = _program(index, "target", "long")
    replacement_program = _program(index, "target", "replacement")
    long_frame = _frame(long_program.node.node_id, 1, 0)
    replacement_frame = _frame(
        replacement_program.node.node_id,
        1,
        0,
        origin=SymbolicFrameOrigin.EVENT_REPLACEMENT,
    )

    def suspended_state(frame, duration):
        continuation = SuspendedContinuation(
            frame,
            boundary_line=index.program(frame.cursor.node_id).event.actions[0].line,
            resume_mode=SymbolicResumeMode.REENTER_BOUNDARY_ACTION,
            boundary_state=SymbolicWaitBoundaryState((str(duration),)),
            wake_constraint=SymbolicWakeConstraint.NEXT_FRAME,
        )
        return _state(index, frame, runnable=(), suspended=(continuation,))

    r1_sync = suspended_state(long_frame, 100)
    r1_wait = suspended_state(replacement_frame, 200)

    assert r1_sync.event_owners == (SymbolicEventOwner.from_frame(long_frame),)
    assert r1_wait.event_owners == (SymbolicEventOwner.from_frame(replacement_frame),)
    assert r1_sync.canonical_key != r1_wait.canonical_key
    with pytest.raises(ValueError, match="multiple active scheduler tasks"):
        SymbolicScheduleState.create(
            index,
            accumulator_state=SymbolicAccumulatorState.zeroed(),
            suspended=(r1_sync.suspended[0], r1_wait.suspended[0]),
            event_owners=(
                SymbolicEventOwner.from_frame(long_frame),
                SymbolicEventOwner.from_frame(replacement_frame),
            ),
        )


def test_t1_attached_unattached_and_unknown_tag_parent_states_never_canonicalize():
    index = _program_index()
    target = _program(index, "target", "long")
    frame = _frame(target.node.node_id, 1, 0)

    keys = {
        disposition: _state(
            index,
            frame,
            tag_parent_states=(
                SymbolicTagParentState(
                    4,
                    disposition,
                    7 if disposition is SymbolicTagParentDisposition.ATTACHED else None,
                ),
            ),
        ).canonical_key
        for disposition in SymbolicTagParentDisposition
    }

    assert len(set(keys.values())) == 3


def test_malformed_cursor_and_event_ownership_fail_at_state_boundary():
    index = _program_index()
    target = _program(index, "target", "long")

    wrong_entity = _frame(target.node.node_id, 0, 0)
    with pytest.raises(ValueError, match="not selected"):
        _state(index, wrong_entity)

    past_end = _frame(target.node.node_id, 1, len(target.instructions))
    with pytest.raises(ValueError, match="does not belong"):
        _state(index, past_end)

    valid = _frame(target.node.node_id, 1, 0)
    cross_entity_stack = replace(
        valid,
        call_stack=(SymbolicProgramCursor(target.node.node_id, 3, len(target.instructions)),),
        origin=SymbolicFrameOrigin.EVENT_REPLACEMENT,
    )
    with pytest.raises(ValueError, match="active frame entity"):
        _state(index, cross_entity_stack)

    caller = _program(index, "caller")
    invocation = SymbolicInvocationStep(
        SymbolicProgramCursor(caller.node.node_id, 0, 0),
        target.node.node_id,
        0,
    )
    for nested_origin in (
        SymbolicFrameOrigin.NESTED_DISPATCH,
        SymbolicFrameOrigin.TARGET_GROUP_RESUME,
    ):
        with pytest.raises(ValueError, match="requires invocation ancestry"):
            _state(index, replace(valid, origin=nested_origin))
    with pytest.raises(ValueError, match="root event frame"):
        _state(index, replace(valid, invocation_path=(invocation,)))

    with pytest.raises(ValueError, match="exactly match"):
        _state(index, valid, event_owners=())

    with pytest.raises(TypeError, match=r"SymbolicScheduleState\.create"):
        SymbolicScheduleState(
            (),
            SymbolicAccumulatorState.zeroed(),
            (wrong_entity,),
            (),
            (),
            (SymbolicEventOwner.from_frame(wrong_entity),),
            (),
            (),
            (),
            (),
            (),
            _creation_token=None,
        )


@pytest.mark.parametrize(
    "accumulator_state",
    (
        SymbolicAccumulatorState(entity_values=((1, 0, SymbolicIntegerDomain(2, 1)),)),
        SymbolicAccumulatorState(
            global_values=((0, SymbolicIntegerDomain(required_set_bits=1, required_clear_bits=1)),),
        ),
        SymbolicAccumulatorState(default_domain=SymbolicIntegerDomain(2, 1)),
        SymbolicAccumulatorState(entity_values=((1, 0, SymbolicIntegerDomain(2**31, 2**31)),)),
        SymbolicAccumulatorState(global_values=((0, SymbolicIntegerDomain(required_set_bits=1 << 40)),)),
        SymbolicAccumulatorState(default_domain=SymbolicIntegerDomain(excluded=frozenset({2**31}))),
    ),
)
def test_impossible_accumulator_domains_fail_at_state_boundary(accumulator_state):
    index = _program_index()
    target = _program(index, "target", "long")
    frame = _frame(target.node.node_id, 1, 0)

    with pytest.raises(ValueError, match="(has no possible value|outside.*ET|outside ET accumulator bits)"):
        _state(index, frame, accumulator_state=accumulator_state)


def test_redundant_accumulator_exclusions_canonicalize_away():
    index = _program_index()
    target = _program(index, "target", "long")
    frame = _frame(target.node.node_id, 1, 0)
    plain = SymbolicIntegerDomain(-10, -1)
    redundant = replace(plain, excluded=frozenset({5}))

    left = _state(index, frame, accumulator_state=SymbolicAccumulatorState(entity_values=((1, 0, plain),)))
    right = _state(
        index,
        frame,
        accumulator_state=SymbolicAccumulatorState(entity_values=((1, 0, redundant),)),
    )

    assert left.canonical_key == right.canonical_key


def test_global_work_budget_reports_named_exhaustion_without_overconsumption():
    index = _program_index()
    target = _program(index, "target", "long")
    frontier = _state(index, _frame(target.node.node_id, 1, 0))
    budget = SymbolicScheduleWorkBudget(2)

    assert budget.consume() is None
    assert budget.consume() is None
    exhaustion = budget.consume()

    assert exhaustion is SymbolicScheduleExhaustion.WORK_BUDGET_EXHAUSTED
    assert budget.consumed == 2
    assert budget.remaining == 0
    decision = SymbolicScheduleDecision(
        SymbolicScheduleDecisionKind.WORK_BUDGET_EXHAUSTED,
        frontier,
        reason=exhaustion.value,
    )
    result = SymbolicScheduleResult((decision,), 2, 2, exhaustion)
    assert result.exhaustion is exhaustion

    mismatched = replace(decision, reason="unrelated_exhaustion")
    with pytest.raises(ValueError, match="reason does not match"):
        SymbolicScheduleResult((mismatched,), 2, 2, exhaustion)
    with pytest.raises(ValueError, match="require their resulting frontier"):
        SymbolicScheduleDecision(
            SymbolicScheduleDecisionKind.WORK_BUDGET_EXHAUSTED,
            reason=exhaustion.value,
        )


def test_schedule_decision_kind_must_match_task_shape():
    index = _program_index()
    target = _program(index, "target", "long")
    frame = _frame(target.node.node_id, 1, 0)
    runnable = _state(index, frame)
    continuation = SuspendedContinuation(
        frame,
        boundary_line=target.event.actions[0].line,
        resume_mode=SymbolicResumeMode.REENTER_BOUNDARY_ACTION,
        boundary_state=SymbolicWaitBoundaryState(("100",)),
        wake_constraint=SymbolicWakeConstraint.NEXT_FRAME,
    )
    suspended = _state(index, frame, runnable=(), suspended=(continuation,))
    complete = SymbolicScheduleState.create(
        index,
        accumulator_state=SymbolicAccumulatorState.zeroed(),
    )

    SymbolicScheduleDecision(SymbolicScheduleDecisionKind.RUNNABLE, runnable)
    SymbolicScheduleDecision(SymbolicScheduleDecisionKind.SUSPENDED, suspended)
    SymbolicScheduleDecision(SymbolicScheduleDecisionKind.COMPLETE, complete)
    with pytest.raises(ValueError, match="requires runnable"):
        SymbolicScheduleDecision(SymbolicScheduleDecisionKind.RUNNABLE, suspended)
    with pytest.raises(ValueError, match="only suspended"):
        SymbolicScheduleDecision(SymbolicScheduleDecisionKind.SUSPENDED, runnable)
    with pytest.raises(ValueError, match="only suspended"):
        SymbolicScheduleDecision(SymbolicScheduleDecisionKind.SUSPENDED, complete)
    with pytest.raises(ValueError, match="cannot retain"):
        SymbolicScheduleDecision(SymbolicScheduleDecisionKind.COMPLETE, runnable)
    with pytest.raises(ValueError, match="cannot retain"):
        SymbolicScheduleDecision(SymbolicScheduleDecisionKind.COMPLETE, suspended)

    runnable_decision = SymbolicScheduleDecision(SymbolicScheduleDecisionKind.RUNNABLE, runnable)
    complete_decision = SymbolicScheduleDecision(SymbolicScheduleDecisionKind.COMPLETE, complete)
    left = SymbolicScheduleResult((runnable_decision, complete_decision), 1, 2)
    right = SymbolicScheduleResult((complete_decision, runnable_decision, runnable_decision), 1, 2)
    assert left.decisions == right.decisions
    with pytest.raises(ValueError, match="at least one decision"):
        SymbolicScheduleResult((), 0, 2)


@pytest.mark.parametrize("limit", [0, -1])
def test_global_work_budget_must_be_positive(limit):
    with pytest.raises(ValueError, match="must be positive"):
        SymbolicScheduleWorkBudget(limit)


def _s2_program_index(
    *,
    caller_first: bool = True,
    boundary_command: str = "resetscript",
    caller_suffix: str = "setstate caller_marker invisible",
    target_suffix: str = "setstate target_marker invisible",
):
    script = parse_map_script(
        f"""
        caller
        {{
            spawn
            {{
                trigger target long
                {caller_suffix}
            }}
        }}
        target
        {{
            trigger long
            {{
                {boundary_command}
                {target_suffix}
            }}
        }}
        """.encode(),
        source="maps/test.script",
    )
    model = StaticStageModel(
        "test",
        ObjectiveCatalog((), (), ()),
        script,
        compile_static_stage_graph(script, source="maps/test.script"),
        _asset_provider(MapAssetKind.SCRIPT),
        _asset_provider(MapAssetKind.OBJDATA),
    )
    mover_entities = (
        {"classname": "script_mover", "scriptname": "caller"},
        {"classname": "script_mover", "scriptname": "target"},
    )
    if not caller_first:
        mover_entities = tuple(reversed(mover_entities))
    identities = build_entity_identity_index(
        mover_entities
        + (
            {"classname": "func_door", "targetname": "caller_marker"},
            {"classname": "func_door", "targetname": "target_marker"},
        ),
        source="maps/test.bsp",
    )
    catalog = MapEntityCatalog("test", "maps/test.bsp", (), (), (), ())
    index = build_ordered_stage_program_index(model, link_w3_entity_catalog(identities, catalog))
    caller_entity_index = 0 if caller_first else 1
    target_entity_index = 1 if caller_first else 0
    caller = _program(index, "caller")
    frame = _frame(caller.node.node_id, caller_entity_index, 0)
    state = _state(
        index,
        frame,
        tag_parent_states=(
            SymbolicTagParentState(
                caller_entity_index,
                SymbolicTagParentDisposition.PROVEN_UNATTACHED,
            ),
            SymbolicTagParentState(
                target_entity_index,
                SymbolicTagParentDisposition.PROVEN_UNATTACHED,
            ),
        ),
    )
    return index, state, caller_entity_index, target_entity_index


def _scheduler_program_index(script_source: str, raw_entities: tuple[dict[str, str], ...]):
    script = parse_map_script(script_source.encode(), source="maps/test.script")
    model = StaticStageModel(
        "test",
        ObjectiveCatalog((), (), ()),
        script,
        compile_static_stage_graph(script, source="maps/test.script"),
        _asset_provider(MapAssetKind.SCRIPT),
        _asset_provider(MapAssetKind.OBJDATA),
    )
    identities = build_entity_identity_index(raw_entities, source="maps/test.bsp")
    catalog = MapEntityCatalog("test", "maps/test.bsp", (), (), (), ())
    return build_ordered_stage_program_index(model, link_w3_entity_catalog(identities, catalog))


def _decision(result, kind):
    return next(decision for decision in result.decisions if decision.kind is kind)


def _decision_with_suspended(result, kind):
    return next(
        decision
        for decision in result.decisions
        if decision.kind is kind and decision.state is not None and decision.state.suspended
    )


def test_s2_cross_entity_boundary_runs_caller_suffix_before_target_resume():
    index, initial, caller_entity_index, target_entity_index = _s2_program_index()

    dispatched = _decision_with_suspended(
        step_symbolic_schedule(index, initial),
        SymbolicScheduleDecisionKind.RUNNABLE,
    ).state
    assert dispatched is not None
    assert tuple(frame.cursor.entity_index for frame in dispatched.runnable) == (caller_entity_index,)
    assert tuple(item.frame.cursor.entity_index for item in dispatched.suspended) == (target_entity_index,)
    assert dispatched.suspended[0].caller_suffix_completed is False
    assert dispatched.effects == ()

    caller_completed = _decision(
        step_symbolic_schedule(index, dispatched),
        SymbolicScheduleDecisionKind.SUSPENDED,
    ).state
    assert caller_completed is not None
    assert caller_completed.suspended[0].caller_suffix_completed is True
    assert tuple(effect.source_cursor.entity_index for effect in caller_completed.effects) == (
        caller_entity_index,
    )

    completed = _decision(
        step_symbolic_schedule(index, caller_completed),
        SymbolicScheduleDecisionKind.COMPLETE,
    ).state
    assert completed is not None
    assert completed.runnable == ()
    assert completed.suspended == ()
    assert tuple(effect.source_cursor.entity_index for effect in completed.effects) == (
        caller_entity_index,
        target_entity_index,
    )
    assert completed.ordering_decisions[-2:] == (
        "caller_suffix_completed_before_target_resume",
        "target_reentered_after_caller_suffix",
    )


def test_s2_rejects_target_resume_before_caller_suffix_completion():
    index, initial, _, _ = _s2_program_index()
    dispatched = _decision_with_suspended(
        step_symbolic_schedule(index, initial),
        SymbolicScheduleDecisionKind.RUNNABLE,
    ).state
    assert dispatched is not None
    premature = SymbolicScheduleState.create(
        index,
        accumulator_state=dispatched.accumulator_state,
        suspended=dispatched.suspended,
        event_owners=(SymbolicEventOwner.from_frame(dispatched.suspended[0].frame),),
        tag_parent_states=dispatched.tag_parent_states,
        effects=dispatched.effects,
        provenance=dispatched.provenance,
        ordering_decisions=dispatched.ordering_decisions,
        unknown_reasons=dispatched.unknown_reasons,
    )

    blocked = _decision(
        step_symbolic_schedule(index, premature),
        SymbolicScheduleDecisionKind.BLOCKED,
    )
    assert blocked.reason == "s2_target_resume_before_caller_suffix"


@pytest.mark.parametrize(
    ("caller_first", "expected_wake"),
    (
        (True, SymbolicWakeConstraint.SAME_FRAME_LATER),
        (False, SymbolicWakeConstraint.NEXT_FRAME),
    ),
)
def test_s2_wait_wake_uses_proven_ordinary_entity_pass_order(caller_first, expected_wake):
    index, initial, _, _ = _s2_program_index(caller_first=caller_first, boundary_command="wait 100")
    dispatched = _decision_with_suspended(
        step_symbolic_schedule(index, initial),
        SymbolicScheduleDecisionKind.RUNNABLE,
    ).state
    assert dispatched is not None
    assert dispatched.suspended[0].wake_constraint is expected_wake

    caller_completed = _decision(
        step_symbolic_schedule(index, dispatched),
        SymbolicScheduleDecisionKind.SUSPENDED,
    ).state
    assert caller_completed is not None
    resumed = step_symbolic_schedule(index, caller_completed)
    if expected_wake is SymbolicWakeConstraint.SAME_FRAME_LATER:
        same_frame = _decision(resumed, SymbolicScheduleDecisionKind.SUSPENDED).state
        assert same_frame is not None
        assert same_frame.suspended[0].wake_constraint is SymbolicWakeConstraint.NEXT_FRAME
        assert same_frame.provenance[-1] == "boundary_action_reentered_same_frame"
    else:
        assert _decision(resumed, SymbolicScheduleDecisionKind.BLOCKED).reason == (
            "wait_completion_time_unverified"
        )


def test_s2_unknown_tag_parent_order_retains_named_wake_frontier():
    index, initial, caller_entity_index, target_entity_index = _s2_program_index(
        boundary_command="wait 100"
    )
    unknown_entry = SymbolicScheduleState.create(
        index,
        accumulator_state=initial.accumulator_state,
        runnable=initial.runnable,
        event_owners=initial.event_owners,
        tag_parent_states=(
            SymbolicTagParentState(
                caller_entity_index,
                SymbolicTagParentDisposition.PROVEN_UNATTACHED,
            ),
            SymbolicTagParentState(target_entity_index, SymbolicTagParentDisposition.UNKNOWN),
        ),
    )
    dispatched = _decision_with_suspended(
        step_symbolic_schedule(index, unknown_entry),
        SymbolicScheduleDecisionKind.RUNNABLE,
    ).state
    assert dispatched is not None
    assert dispatched.suspended[0].wake_constraint is SymbolicWakeConstraint.TAG_PARENT_ORDER_UNKNOWN
    caller_completed = _decision(
        step_symbolic_schedule(index, dispatched),
        SymbolicScheduleDecisionKind.SUSPENDED,
    ).state
    assert caller_completed is not None
    blocked = _decision(
        step_symbolic_schedule(index, caller_completed),
        SymbolicScheduleDecisionKind.BLOCKED,
    )
    assert blocked.reason == "wake_semantics_unverified"
    assert "tag_parent_state_unknown" in blocked.state.unknown_reasons


def test_s2_caller_parent_was_already_run_before_raw_later_target_index():
    index, initial, caller_entity_index, target_entity_index = _s2_program_index(
        boundary_command="wait 100",
    )
    attached_entry = SymbolicScheduleState.create(
        index,
        accumulator_state=initial.accumulator_state,
        runnable=initial.runnable,
        event_owners=initial.event_owners,
        tag_parent_states=(
            SymbolicTagParentState(
                caller_entity_index,
                SymbolicTagParentDisposition.ATTACHED,
                target_entity_index,
            ),
            SymbolicTagParentState(
                target_entity_index,
                SymbolicTagParentDisposition.PROVEN_UNATTACHED,
            ),
        ),
    )

    dispatched = _decision_with_suspended(
        step_symbolic_schedule(index, attached_entry),
        SymbolicScheduleDecisionKind.RUNNABLE,
    ).state
    assert dispatched is not None
    assert dispatched.suspended[0].wake_constraint is SymbolicWakeConstraint.NEXT_FRAME


def test_s2_transitive_caller_parent_was_already_run_before_later_target():
    index, initial, caller_entity_index, target_entity_index = _s2_program_index(
        boundary_command="wait 100",
    )
    intermediate_parent = 99
    attached_entry = SymbolicScheduleState.create(
        index,
        accumulator_state=initial.accumulator_state,
        runnable=initial.runnable,
        event_owners=initial.event_owners,
        tag_parent_states=(
            SymbolicTagParentState(
                caller_entity_index,
                SymbolicTagParentDisposition.ATTACHED,
                intermediate_parent,
            ),
            SymbolicTagParentState(
                intermediate_parent,
                SymbolicTagParentDisposition.ATTACHED,
                target_entity_index,
            ),
            SymbolicTagParentState(
                target_entity_index,
                SymbolicTagParentDisposition.PROVEN_UNATTACHED,
            ),
        ),
    )

    dispatched = _decision_with_suspended(
        step_symbolic_schedule(index, attached_entry),
        SymbolicScheduleDecisionKind.RUNNABLE,
    ).state
    assert dispatched is not None
    assert dispatched.suspended[0].wake_constraint is SymbolicWakeConstraint.NEXT_FRAME


def test_s2_missing_caller_tag_parent_state_does_not_fall_back_to_raw_order():
    index, initial, _, target_entity_index = _s2_program_index(boundary_command="wait 100")
    unknown_caller = SymbolicScheduleState.create(
        index,
        accumulator_state=initial.accumulator_state,
        runnable=initial.runnable,
        event_owners=initial.event_owners,
        tag_parent_states=(
            SymbolicTagParentState(
                target_entity_index,
                SymbolicTagParentDisposition.PROVEN_UNATTACHED,
            ),
        ),
    )

    dispatched = _decision_with_suspended(
        step_symbolic_schedule(index, unknown_caller),
        SymbolicScheduleDecisionKind.RUNNABLE,
    ).state
    assert dispatched is not None
    assert dispatched.suspended[0].wake_constraint is SymbolicWakeConstraint.TAG_PARENT_ORDER_UNKNOWN
    assert "caller_tag_parent_state_unknown" in dispatched.unknown_reasons


def test_s2_caller_suffix_blocker_retains_executed_prefix_effects_and_cursor():
    index, initial, caller_entity_index, target_entity_index = _s2_program_index(
        caller_suffix="""
                setstate caller_marker invisible
                accum 0 set 7
                wait 100
        """,
    )
    dispatched = _decision(
        step_symbolic_schedule(index, initial),
        SymbolicScheduleDecisionKind.RUNNABLE,
    ).state
    assert dispatched is not None
    blocked = _decision(
        step_symbolic_schedule(index, dispatched),
        SymbolicScheduleDecisionKind.BLOCKED,
    )
    assert blocked.state is not None
    assert tuple(effect.source_cursor.entity_index for effect in blocked.state.effects) == (
        caller_entity_index,
    )
    assert tuple(frame.cursor.entity_index for frame in blocked.state.runnable) == (caller_entity_index,)
    assert tuple(item.frame.cursor.entity_index for item in blocked.state.suspended) == (
        target_entity_index,
    )
    assert (
        blocked.state.accumulator_state.read(
            AccumulatorScope.ENTITY,
            0,
            source_entity_index=caller_entity_index,
        ).exact_value
        == 7
    )
    caller_program = _program(index, "caller")
    assert blocked.state.runnable[0].cursor.instruction_offset == len(caller_program.instructions) - 1


def test_s3_nested_blocker_retains_group_with_named_inexact_active_frontier():
    index = _scheduler_program_index(
        """
        caller
        {
            spawn
            {
                trigger shared outer
                setstate caller_done invisible
            }
        }
        shared
        {
            trigger outer
            {
                trigger helper inner
            }
        }
        helper
        {
            trigger inner
            {
                accum 0 set 7
                trigger missing absent
            }
        }
        """,
        (
            {"classname": "script_mover", "scriptname": "caller"},
            {"classname": "script_mover", "scriptname": "shared"},
            {"classname": "script_mover", "scriptname": "shared"},
            {"classname": "script_mover", "scriptname": "helper"},
            {"classname": "func_door", "targetname": "caller_done"},
        ),
    )
    caller = _program(index, "caller")
    initial = _state(index, _frame(caller.node.node_id, 0, 0))

    blocked = _decision(
        step_symbolic_schedule(index, initial),
        SymbolicScheduleDecisionKind.BLOCKED,
    )
    assert blocked.reason == "nested_dispatch_missing_handler"
    assert blocked.state is not None
    assert tuple(frame.cursor.entity_index for frame in blocked.state.runnable) == (1, 2, 0)
    assert "s3_blocker_frontier_identity_unresolved" in blocked.state.unknown_reasons
    assert (
        blocked.state.accumulator_state.read(
            AccumulatorScope.ENTITY,
            0,
            source_entity_index=3,
        ).exact_value
        == 7
    )


def test_s2_resumed_target_blocker_retains_executed_prefix_effects_and_cursor():
    index, initial, caller_entity_index, target_entity_index = _s2_program_index(
        target_suffix="""
                setstate target_marker invisible
                accum 1 set 9
                wait 100
        """,
    )
    dispatched = _decision(
        step_symbolic_schedule(index, initial),
        SymbolicScheduleDecisionKind.RUNNABLE,
    ).state
    assert dispatched is not None
    caller_completed = _decision(
        step_symbolic_schedule(index, dispatched),
        SymbolicScheduleDecisionKind.SUSPENDED,
    ).state
    assert caller_completed is not None
    blocked = _decision(
        step_symbolic_schedule(index, caller_completed),
        SymbolicScheduleDecisionKind.BLOCKED,
    )
    assert blocked.state is not None
    assert tuple(effect.source_cursor.entity_index for effect in blocked.state.effects) == (
        caller_entity_index,
        target_entity_index,
    )
    assert tuple(frame.cursor.entity_index for frame in blocked.state.runnable) == (target_entity_index,)
    assert blocked.state.suspended == ()
    assert (
        blocked.state.accumulator_state.read(
            AccumulatorScope.ENTITY,
            1,
            source_entity_index=target_entity_index,
        ).exact_value
        == 9
    )
    target_program = _program(index, "target", "long")
    assert blocked.state.runnable[0].cursor.instruction_offset == len(target_program.instructions) - 1


def test_s3_synchronous_target_state_returns_with_local_isolation_and_shared_global_state():
    index = _scheduler_program_index(
        """
        caller
        {
            spawn
            {
                trigger worker mutate
                accum 0 abort_if_not_equal 3
                globalaccum 0 abort_if_not_equal 7
                setstate success invisible
            }
        }
        worker
        {
            trigger mutate
            {
                accum 0 set 9
                globalaccum 0 set 7
            }
        }
        """,
        (
            {"classname": "script_mover", "scriptname": "caller"},
            {"classname": "script_mover", "scriptname": "worker"},
            {"classname": "func_door", "targetname": "success"},
        ),
    )
    caller = _program(index, "caller")
    initial_accumulators = SymbolicAccumulatorState.zeroed().write(
        AccumulatorScope.ENTITY,
        0,
        SymbolicIntegerDomain.exact(3),
        source_entity_index=0,
    )
    initial = _state(
        index,
        _frame(caller.node.node_id, 0, 0),
        accumulator_state=initial_accumulators,
    )

    returned = _decision(
        step_symbolic_schedule(index, initial),
        SymbolicScheduleDecisionKind.RUNNABLE,
    ).state
    assert returned is not None
    assert returned.accumulator_state.read(
        AccumulatorScope.ENTITY,
        0,
        source_entity_index=0,
    ).exact_value == 3
    assert returned.accumulator_state.read(
        AccumulatorScope.ENTITY,
        0,
        source_entity_index=1,
    ).exact_value == 9
    assert returned.accumulator_state.read(
        AccumulatorScope.GLOBAL,
        0,
        source_entity_index=0,
    ).exact_value == 7

    completed = _decision(
        step_symbolic_schedule(index, returned),
        SymbolicScheduleDecisionKind.COMPLETE,
    ).state
    assert completed is not None
    assert tuple(record.projection.effect.target for record in completed.effects) == ("success",)


def test_s3_same_entity_synchronous_replacement_restores_caller_with_exit_state():
    index = _scheduler_program_index(
        """
        caller
        {
            spawn
            {
                trigger caller mutate
                accum 0 abort_if_not_equal 7
                setstate restored invisible
            }
            trigger mutate
            {
                accum 0 set 7
            }
        }
        """,
        (
            {"classname": "script_mover", "scriptname": "caller"},
            {"classname": "func_door", "targetname": "restored"},
        ),
    )
    caller = _program(index, "caller")
    initial = _state(index, _frame(caller.node.node_id, 0, 0))

    restored = _decision(
        step_symbolic_schedule(index, initial),
        SymbolicScheduleDecisionKind.RUNNABLE,
    ).state
    assert restored is not None
    assert restored.suspended == ()
    assert restored.accumulator_state.read(
        AccumulatorScope.ENTITY,
        0,
        source_entity_index=0,
    ).exact_value == 7

    completed = _decision(
        step_symbolic_schedule(index, restored),
        SymbolicScheduleDecisionKind.COMPLETE,
    ).state
    assert completed is not None
    assert tuple(record.projection.effect.target for record in completed.effects) == ("restored",)


def test_s3_same_entity_temporal_replacement_abandons_caller_suffix():
    index = _scheduler_program_index(
        """
        caller
        {
            spawn
            {
                trigger caller replace
                setstate abandoned invisible
            }
            trigger replace
            {
                resetscript
                setstate replacement invisible
            }
        }
        """,
        (
            {"classname": "script_mover", "scriptname": "caller"},
            {"classname": "func_door", "targetname": "abandoned"},
            {"classname": "func_door", "targetname": "replacement"},
        ),
    )
    caller = _program(index, "caller")
    initial = _state(index, _frame(caller.node.node_id, 0, 0))

    replaced = _decision(
        step_symbolic_schedule(index, initial),
        SymbolicScheduleDecisionKind.SUSPENDED,
    ).state
    assert replaced is not None
    assert replaced.runnable == ()
    assert len(replaced.suspended) == 1
    assert replaced.suspended[0].caller_suffix_abandoned is True
    assert replaced.effects == ()

    completed = _decision(
        step_symbolic_schedule(index, replaced),
        SymbolicScheduleDecisionKind.COMPLETE,
    ).state
    assert completed is not None
    assert tuple(record.projection.effect.target for record in completed.effects) == ("replacement",)
    assert "target_reentered_after_caller_abandonment" in completed.ordering_decisions


def test_s3_shared_target_group_retains_concrete_order_and_every_suspension():
    index = _scheduler_program_index(
        """
        caller
        {
            spawn
            {
                trigger shared pause
                setstate caller_done invisible
            }
        }
        shared
        {
            trigger pause
            {
                globalaccum 0 inc 1
                resetscript
            }
        }
        """,
        (
            {"classname": "script_mover", "scriptname": "caller"},
            {"classname": "script_mover", "scriptname": "shared"},
            {"classname": "script_mover", "scriptname": "shared"},
            {"classname": "func_door", "targetname": "caller_done"},
        ),
    )
    caller = _program(index, "caller")
    initial = _state(index, _frame(caller.node.node_id, 0, 0))

    dispatched = next(
        decision.state
        for decision in step_symbolic_schedule(index, initial).decisions
        if decision.kind is SymbolicScheduleDecisionKind.RUNNABLE
        and decision.state is not None
        and len(decision.state.suspended) == 2
    )
    assert dispatched.accumulator_state.read(
        AccumulatorScope.GLOBAL,
        0,
        source_entity_index=0,
    ).exact_value == 2
    by_target = sorted(
        (
            continuation.frame.cursor.entity_index,
            continuation.frame.pending_dispatch.target_cursor,
            continuation.frame.pending_dispatch.ordered_target_entity_indices,
        )
        for continuation in dispatched.suspended
        if continuation.frame.pending_dispatch is not None
    )
    assert by_target == [(1, 0, (1, 2)), (2, 1, (1, 2))]
    assert dispatched.ordering_decisions[:2] == (
        "dispatch_target_0_in_entity_order",
        "dispatch_target_1_in_entity_order",
    )

    caller_completed = _decision(
        step_symbolic_schedule(index, dispatched),
        SymbolicScheduleDecisionKind.SUSPENDED,
    ).state
    assert caller_completed is not None
    assert all(item.caller_suffix_completed for item in caller_completed.suspended)
    assert tuple(record.projection.effect.target for record in caller_completed.effects) == ("caller_done",)


def test_s3_blocked_target_retains_target_group_and_caller_frontiers():
    index = _scheduler_program_index(
        """
        caller
        {
            spawn
            {
                trigger shared outer
                setstate caller_done invisible
            }
        }
        shared
        {
            trigger outer
            {
                accum 0 set 7
                trigger missing inner
                setstate target_done invisible
            }
        }
        """,
        (
            {"classname": "script_mover", "scriptname": "caller"},
            {"classname": "script_mover", "scriptname": "shared"},
            {"classname": "script_mover", "scriptname": "shared"},
            {"classname": "func_door", "targetname": "caller_done"},
            {"classname": "func_door", "targetname": "target_done"},
        ),
    )
    caller = _program(index, "caller")
    target = _program(index, "shared", "outer")
    initial = _state(index, _frame(caller.node.node_id, 0, 0))

    blocked = _decision(
        step_symbolic_schedule(index, initial),
        SymbolicScheduleDecisionKind.BLOCKED,
    )
    assert blocked.reason == "nested_dispatch_missing_handler"
    assert blocked.state is not None
    assert tuple(frame.cursor.entity_index for frame in blocked.state.runnable) == (1, 2, 0)
    assert tuple(frame.cursor.instruction_offset for frame in blocked.state.runnable) == (1, 0, 1)
    assert blocked.state.runnable[0].cursor.node_id == target.node.node_id
    assert blocked.state.runnable[1].cursor.node_id == target.node.node_id
    assert blocked.state.runnable[2].cursor.node_id == caller.node.node_id
    assert tuple(
        frame.pending_dispatch.target_cursor
        for frame in blocked.state.runnable[:2]
        if frame.pending_dispatch is not None
    ) == (0, 1)
    assert (
        blocked.state.accumulator_state.read(
            AccumulatorScope.ENTITY,
            0,
            source_entity_index=1,
        ).exact_value
        == 7
    )
    assert "s3_blocker_frontier_identity_unresolved" not in blocked.state.unknown_reasons


def test_s3_final_trigger_marks_suspended_target_caller_suffix_complete():
    index = _scheduler_program_index(
        """
        caller
        {
            spawn
            {
                trigger target pause
            }
        }
        target
        {
            trigger pause
            {
                resetscript
            }
        }
        """,
        (
            {"classname": "script_mover", "scriptname": "caller"},
            {"classname": "script_mover", "scriptname": "target"},
        ),
    )
    caller = _program(index, "caller")
    initial = _state(index, _frame(caller.node.node_id, 0, 0))

    suspended = _decision(
        step_symbolic_schedule(index, initial),
        SymbolicScheduleDecisionKind.SUSPENDED,
    ).state
    assert suspended is not None
    assert suspended.runnable == ()
    assert len(suspended.suspended) == 1
    assert suspended.suspended[0].caller_suffix_completed is True


@pytest.mark.parametrize(("replacement_body", "expected_event", "expected_global"), (
    ("globalaccum 0 set 7", "long", 7),
    ("globalaccum 0 set 9\nresetscript", "replacement", 9),
))
def test_s3_replacement_of_suspended_target_restores_or_replaces_exact_owner(
    replacement_body,
    expected_event,
    expected_global,
):
    index = _scheduler_program_index(
        f"""
        caller
        {{
            spawn
            {{
                trigger target long
                trigger target replacement
                setstate caller_done invisible
            }}
        }}
        target
        {{
            trigger long
            {{
                resetscript
            }}
            trigger replacement
            {{
                {replacement_body}
            }}
        }}
        """,
        (
            {"classname": "script_mover", "scriptname": "caller"},
            {"classname": "script_mover", "scriptname": "target"},
            {"classname": "func_door", "targetname": "caller_done"},
        ),
    )
    caller = _program(index, "caller")
    initial = _state(index, _frame(caller.node.node_id, 0, 0))
    long_suspended = _decision_with_suspended(
        step_symbolic_schedule(index, initial),
        SymbolicScheduleDecisionKind.RUNNABLE,
    ).state
    assert long_suspended is not None

    replaced = _decision_with_suspended(
        step_symbolic_schedule(index, long_suspended),
        SymbolicScheduleDecisionKind.RUNNABLE,
    ).state
    assert replaced is not None
    assert len(replaced.suspended) == 1
    retained_program = index.program(replaced.suspended[0].frame.cursor.node_id)
    assert retained_program.node.serialized_event_parameters == expected_event
    assert replaced.accumulator_state.read(
        AccumulatorScope.GLOBAL,
        0,
        source_entity_index=0,
    ).exact_value == expected_global


def test_s3_optional_death_dispatch_keeps_event_and_no_event_branches():
    index = _scheduler_program_index(
        """
        game_manager
        {
            spawn
            {
                kill victim_target
                setstate gate invisible
            }
        }
        victim
        {
            death
            {
                globalaccum 0 set 7
            }
        }
        """,
        (
            {"classname": "script_multiplayer"},
            {"classname": "script_mover", "scriptname": "victim", "targetname": "victim_target"},
            {"classname": "func_door", "targetname": "gate"},
        ),
    )
    caller = _program(index, "game_manager")
    initial = _state(index, _frame(caller.node.node_id, 0, 0))

    branches = tuple(
        decision.state
        for decision in step_symbolic_schedule(index, initial).decisions
        if decision.kind is SymbolicScheduleDecisionKind.RUNNABLE and decision.state is not None
    )
    assert {
        branch.accumulator_state.read(
            AccumulatorScope.GLOBAL,
            0,
            source_entity_index=0,
        ).exact_value
        for branch in branches
    } == {0, 7}


def test_s3_optional_death_no_event_branch_cannot_bypass_fatal_sibling_target():
    index = _scheduler_program_index(
        """
        game_manager
        {
            spawn
            {
                kill victim_target
                setstate gate invisible
            }
        }
        victim
        {
            death
            {
                globalaccum 0 set 7
            }
        }
        """,
        (
            {"classname": "script_multiplayer"},
            {
                "classname": "script_mover",
                "scriptname": "victim",
                "targetname": "victim_target",
            },
            {
                "classname": "func_constructible",
                "scriptname": "victim",
                "targetname": "victim_target",
            },
            {"classname": "func_door", "targetname": "gate"},
        ),
    )
    caller = _program(index, "game_manager")
    initial = _state(index, _frame(caller.node.node_id, 0, 0))

    result = step_symbolic_schedule(index, initial)
    assert tuple(decision.kind for decision in result.decisions) == (
        SymbolicScheduleDecisionKind.BLOCKED,
    )
    assert result.decisions[0].reason == "kill_constructible_runtime_event_not_modeled"


def test_s3_conditional_dispatch_keeps_refined_taken_and_not_taken_states():
    index = _scheduler_program_index(
        """
        caller
        {
            spawn
            {
                accum 0 trigger_if_equal 1 worker mutate
                setstate gate invisible
            }
        }
        worker
        {
            trigger mutate
            {
                globalaccum 0 set 7
            }
        }
        """,
        (
            {"classname": "script_mover", "scriptname": "caller"},
            {"classname": "script_mover", "scriptname": "worker"},
            {"classname": "func_door", "targetname": "gate"},
        ),
    )
    caller = _program(index, "caller")
    initial = _state(
        index,
        _frame(caller.node.node_id, 0, 0),
        accumulator_state=SymbolicAccumulatorState.unknown(),
    )

    branches = tuple(
        decision.state
        for decision in step_symbolic_schedule(index, initial).decisions
        if decision.kind is SymbolicScheduleDecisionKind.RUNNABLE and decision.state is not None
    )
    assert len(branches) == 2
    taken = next(
        branch
        for branch in branches
        if branch.accumulator_state.read(
            AccumulatorScope.GLOBAL,
            0,
            source_entity_index=0,
        ).exact_value
        == 7
    )
    not_taken = next(branch for branch in branches if branch is not taken)
    assert taken.accumulator_state.read(
        AccumulatorScope.ENTITY,
        0,
        source_entity_index=0,
    ).exact_value == 1
    assert not not_taken.accumulator_state.read(
        AccumulatorScope.ENTITY,
        0,
        source_entity_index=0,
    ).contains(1)


def test_s3_source_proven_alert_dispatch_enters_waiting_handler():
    index = _scheduler_program_index(
        """
        caller
        {
            spawn
            {
                alertentity vehicle
                setstate gate invisible
            }
        }
        vehicle
        {
            rebirth
            {
                wait 100
                accum 1 set 7
            }
        }
        """,
        (
            {"classname": "script_mover", "scriptname": "caller"},
            {
                "classname": "script_mover",
                "scriptname": "vehicle",
                "targetname": "vehicle",
                "spawnflags": "8",
                "health": "100",
            },
            {"classname": "func_door", "targetname": "gate"},
        ),
    )
    caller = _program(index, "caller")
    initial = _state(
        index,
        _frame(caller.node.node_id, 0, 0),
        tag_parent_states=(
            SymbolicTagParentState(1, SymbolicTagParentDisposition.PROVEN_UNATTACHED),
        ),
    )

    dispatched = _decision_with_suspended(
        step_symbolic_schedule(index, initial),
        SymbolicScheduleDecisionKind.RUNNABLE,
    ).state
    assert dispatched is not None
    assert dispatched.suspended[0].frame.cursor.entity_index == 1
    assert dispatched.suspended[0].frame.pending_dispatch is not None
    assert dispatched.suspended[0].frame.pending_dispatch.ordered_target_entity_indices == (1,)
    assert tuple(record.source_cursor.entity_index for record in dispatched.effects) == (0,)


@pytest.mark.parametrize(
    ("movement", "expected_command"),
    (
        ("gotomarker route 100", SymbolicMovementCommand.GOTO_MARKER),
        ("followspline 0 route 100", SymbolicMovementCommand.FOLLOW_SPLINE),
    ),
)
def test_s3_non_waiting_movement_advances_script_and_retains_async_lifecycle(
    movement,
    expected_command,
):
    index = _scheduler_program_index(
        f"""
        caller
        {{
            spawn
            {{
                trigger target move
                setstate caller_done invisible
            }}
        }}
        target
        {{
            trigger move
            {{
                {movement}
                setstate target_done invisible
            }}
        }}
        """,
        (
            {"classname": "script_mover", "scriptname": "caller"},
            {"classname": "script_mover", "scriptname": "target"},
            {"classname": "path_corner_2", "targetname": "route"},
            {"classname": "func_door", "targetname": "caller_done"},
            {"classname": "func_door", "targetname": "target_done"},
        ),
    )
    caller = _program(index, "caller")
    initial = _state(index, _frame(caller.node.node_id, 0, 0))

    advanced = next(
        decision.state
        for decision in step_symbolic_schedule(index, initial).decisions
        if decision.kind is SymbolicScheduleDecisionKind.RUNNABLE
        and decision.state is not None
        and not decision.state.suspended
    )
    assert len(advanced.async_lifecycles) == 1
    lifecycle = advanced.async_lifecycles[0]
    assert lifecycle.source_cursor.entity_index == 1
    assert lifecycle.command is expected_command
    assert tuple(
        record.projection.effect.target
        for record in advanced.effects
        if isinstance(record.projection.effect, EntityStateEffect)
    ) == ("target_done",)


def test_s3_waiting_gotomarker_without_active_movement_keeps_only_started_branch():
    index = _scheduler_program_index(
        """
        caller
        {
            spawn
            {
                trigger target move
                setstate caller_done invisible
            }
        }
        target
        {
            trigger move
            {
                gotomarker route 100 wait
            }
        }
        """,
        (
            {"classname": "script_mover", "scriptname": "caller"},
            {"classname": "script_mover", "scriptname": "target"},
            {"classname": "path_corner_2", "targetname": "route"},
            {"classname": "func_door", "targetname": "caller_done"},
        ),
    )
    caller = _program(index, "caller")
    initial = _state(index, _frame(caller.node.node_id, 0, 0))

    branches = tuple(
        decision.state
        for decision in step_symbolic_schedule(index, initial).decisions
        if decision.state is not None and decision.state.suspended
    )
    assert len(branches) == 1
    continuation = branches[0].suspended[0]
    assert isinstance(continuation.boundary_state, SymbolicMovementBoundaryState)
    assert (
        continuation.boundary_state.temporal_state
        is SymbolicTemporalBoundaryState.CURRENT_ACTION_WAITING
    )
    assert continuation.boundary_state.effect_started is True
    assert len(branches[0].effects) == 1


def test_s3_active_movement_keeps_only_prior_motion_branch_without_new_route_effect():
    index = _scheduler_program_index(
        """
        caller
        {
            spawn
            {
                trigger target replace
                setstate caller_done invisible
            }
        }
        target
        {
            trigger old
            {
                gotomarker old_route 100
            }
            trigger replace
            {
                gotomarker new_route 100 wait
            }
        }
        """,
        (
            {"classname": "script_mover", "scriptname": "caller"},
            {"classname": "script_mover", "scriptname": "target"},
            {"classname": "path_corner_2", "targetname": "old_route"},
            {"classname": "path_corner_2", "targetname": "new_route"},
            {"classname": "func_door", "targetname": "caller_done"},
        ),
    )
    caller = _program(index, "caller")
    old = _program(index, "target", "old")
    old_cursor = SymbolicProgramCursor(old.node.node_id, 1, 0)
    old_instruction = old.instructions[0]
    assert isinstance(old_instruction, StageEffectInstruction)
    old_effect = SymbolicEffectRecord(old_instruction.projection, old_cursor)
    lifecycle = SymbolicAsyncMovementLifecycle(
        old_cursor,
        SymbolicMovementCommand.GOTO_MARKER,
        old.event.actions[0].arguments,
        effect_record_index=0,
    )
    initial = _state(
        index,
        _frame(caller.node.node_id, 0, 0),
        async_lifecycles=(lifecycle,),
        effects=(old_effect,),
    )

    branches = tuple(
        decision.state
        for decision in step_symbolic_schedule(index, initial).decisions
        if decision.state is not None and decision.state.suspended
    )
    assert len(branches) == 1
    continuation = branches[0].suspended[0]
    assert isinstance(continuation.boundary_state, SymbolicMovementBoundaryState)
    assert (
        continuation.boundary_state.temporal_state
        is SymbolicTemporalBoundaryState.PRIOR_MOVEMENT_ACTIVE
    )
    assert continuation.boundary_state.effect_started is False
    assert branches[0].async_lifecycles == (lifecycle,)
    assert branches[0].effects == (old_effect,)


def test_s3_resumed_target_suffix_retains_new_async_movement_lifecycle():
    index, initial, _, target_entity_index = _s2_program_index(
        target_suffix="followspline 0 route 100",
    )
    dispatched = _decision_with_suspended(
        step_symbolic_schedule(index, initial),
        SymbolicScheduleDecisionKind.RUNNABLE,
    ).state
    assert dispatched is not None
    caller_completed = _decision(
        step_symbolic_schedule(index, dispatched),
        SymbolicScheduleDecisionKind.SUSPENDED,
    ).state
    assert caller_completed is not None

    completed = _decision(
        step_symbolic_schedule(index, caller_completed),
        SymbolicScheduleDecisionKind.COMPLETE,
    ).state
    assert completed is not None
    assert len(completed.async_lifecycles) == 1
    assert completed.async_lifecycles[0].source_cursor.entity_index == target_entity_index
    assert completed.async_lifecycles[0].command is SymbolicMovementCommand.FOLLOW_SPLINE


def test_s3_nested_non_waiting_movement_retains_concrete_callee_lifecycle():
    index = _scheduler_program_index(
        """
        caller
        {
            spawn
            {
                trigger target outer
            }
        }
        target
        {
            trigger outer
            {
                trigger worker move
            }
        }
        worker
        {
            trigger move
            {
                followspline 0 route 100
            }
        }
        """,
        (
            {"classname": "script_mover", "scriptname": "caller"},
            {"classname": "script_mover", "scriptname": "target"},
            {"classname": "script_mover", "scriptname": "worker"},
        ),
    )
    caller = _program(index, "caller")
    initial = _state(index, _frame(caller.node.node_id, 0, 0))

    completed = _decision(
        step_symbolic_schedule(index, initial),
        SymbolicScheduleDecisionKind.COMPLETE,
    ).state
    assert completed is not None
    assert len(completed.async_lifecycles) == 1
    assert completed.async_lifecycles[0].source_cursor.entity_index == 2
    assert completed.async_lifecycles[0].command is SymbolicMovementCommand.FOLLOW_SPLINE


def test_s3_faceangles_can_suspend_while_nonwaiting_translation_remains_active():
    index = _scheduler_program_index(
        """
        caller
        {
            spawn
            {
                trigger target move
            }
        }
        target
        {
            trigger move
            {
                followspline 0 route 100
                faceangles 0 90 0 100
            }
        }
        """,
        (
            {"classname": "script_mover", "scriptname": "caller"},
            {"classname": "script_mover", "scriptname": "target"},
        ),
    )
    caller = _program(index, "caller")
    initial = _state(index, _frame(caller.node.node_id, 0, 0))

    dispatched = _decision_with_suspended(
        step_symbolic_schedule(index, initial),
        SymbolicScheduleDecisionKind.SUSPENDED,
    ).state
    assert dispatched is not None
    assert len(dispatched.async_lifecycles) == 1
    assert dispatched.async_lifecycles[0].command is SymbolicMovementCommand.FOLLOW_SPLINE
    assert len(dispatched.suspended) == 1
    boundary = dispatched.suspended[0].boundary_state
    assert isinstance(boundary, SymbolicMovementBoundaryState)
    assert boundary.command is SymbolicMovementCommand.FACE_ANGLES
    assert boundary.temporal_state is SymbolicTemporalBoundaryState.CURRENT_ACTION_WAITING
