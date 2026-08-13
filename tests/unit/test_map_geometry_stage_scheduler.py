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
    SymbolicEventOwner,
    SymbolicFrame,
    SymbolicFrameOrigin,
    SymbolicInvocationStep,
    SymbolicMovementBoundaryState,
    SymbolicMovementCommand,
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


def test_pending_dispatch_identity_cannot_drop_parent_cursor_target_cursor_or_order():
    index = _program_index()
    caller = _program(index, "caller")

    def key(pending):
        frame = _frame(
            caller.node.node_id,
            0,
            pending.dispatch_cursor.instruction_offset,
            pending_dispatch=pending,
            origin=SymbolicFrameOrigin.NESTED_DISPATCH,
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

    wait_100 = SymbolicWaitBoundaryState(100)
    assert wait_100.branch is SymbolicWaitBranch.SUSPENDED_FALSE_RETURN
    assert key(wait_100) != key(SymbolicWaitBoundaryState(200))
    assert key(wait_100) != key(wait_100, SymbolicResumeMode.RESUME_TARGET_GROUP)
    movement = SymbolicMovementBoundaryState(
        SymbolicMovementCommand.GOTO_MARKER,
        temporal_state=SymbolicTemporalBoundaryState.CURRENT_ACTION_WAITING,
        waits_for_completion=True,
        effect_started=True,
    )
    assert movement.temporal_state is SymbolicTemporalBoundaryState.CURRENT_ACTION_WAITING


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
            boundary_state=SymbolicWaitBoundaryState(duration),
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
    with pytest.raises(ValueError, match="exactly match"):
        _state(index, valid, event_owners=())

    with pytest.raises(TypeError, match=r"SymbolicScheduleState\.create"):
        SymbolicScheduleState(
            (),
            SymbolicAccumulatorState.zeroed(),
            (wrong_entity,),
            (),
            (SymbolicEventOwner.from_frame(wrong_entity),),
            (),
            (),
            (),
            (),
            (),
            _creation_token=None,
        )


def test_global_work_budget_reports_named_exhaustion_without_overconsumption():
    budget = SymbolicScheduleWorkBudget(2)

    assert budget.consume() is None
    assert budget.consume() is None
    exhaustion = budget.consume()

    assert exhaustion is SymbolicScheduleExhaustion.WORK_BUDGET_EXHAUSTED
    assert budget.consumed == 2
    assert budget.remaining == 0
    decision = SymbolicScheduleDecision(
        SymbolicScheduleDecisionKind.WORK_BUDGET_EXHAUSTED,
        reason=exhaustion.value,
    )
    result = SymbolicScheduleResult((decision,), 2, 2, exhaustion)
    assert result.exhaustion is exhaustion


@pytest.mark.parametrize("limit", [0, -1])
def test_global_work_budget_must_be_positive(limit):
    with pytest.raises(ValueError, match="must be positive"):
        SymbolicScheduleWorkBudget(limit)
