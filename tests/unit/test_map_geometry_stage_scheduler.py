"""S1 immutable scheduler-state and canonicalization contracts."""

from dataclasses import replace
from pathlib import Path

import pytest

from website.backend.map_geometry.entities import MapEntityCatalog
from website.backend.map_geometry.pk3_index import MapAssetKind, MapAssetProvider
from website.backend.map_geometry.stage import (
    ObjectiveCatalog,
    StaticStageModel,
    compile_static_stage_graph,
    parse_map_script,
)
from website.backend.map_geometry.stage_possibilities import (
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
)
from website.backend.map_geometry.stage_semantics import build_entity_identity_index, link_w3_entity_catalog


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
