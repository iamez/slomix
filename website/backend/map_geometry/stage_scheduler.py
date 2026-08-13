"""Immutable state contracts for bounded ET script scheduling.

This module deliberately contains no transition runner yet.  It owns the state that
later W5b scheduler waves will transition, validates every program cursor against one
ordered-program index and provides deterministic visited-state identity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TypeAlias

from website.backend.map_geometry.stage import (
    GotoMarkerEffect,
    ScriptAction,
    TriggerDispatch,
    TriggerResolution,
)
from website.backend.map_geometry.stage_possibilities import (
    OrderedStageProgramIndex,
    StageEffectInstruction,
    SymbolicAccumulatorState,
    SymbolicTemporalBoundaryState,
    TriggerInstruction,
    followspline_waits_for_completion,
    gotomarker_waits_for_completion,
)
from website.backend.map_geometry.stage_semantics import AccumulatorConditionalTrigger, StageEffectProjection

_STATE_CREATION_TOKEN = object()


def _dispatch_target_group(
    index: OrderedStageProgramIndex,
    dispatch_cursor: SymbolicProgramCursor,
    target_node_id: str,
) -> tuple[int, ...]:
    dispatch_cursor.validate(index)
    source = index.program(dispatch_cursor.node_id)
    instruction = source.instructions[dispatch_cursor.instruction_offset]
    if isinstance(instruction, TriggerInstruction):
        if (
            instruction.edge.resolution is not TriggerResolution.RESOLVED
            or len(instruction.edge.candidate_node_ids) != 1
            or instruction.edge.candidate_node_ids[0] != target_node_id
        ):
            raise ValueError("dispatch target program does not match its trigger instruction")
        target = index.program(target_node_id)
        if instruction.edge.dispatch is TriggerDispatch.SELF:
            if dispatch_cursor.entity_index not in target.source.lookup.selected_entity_indices:
                raise ValueError("self dispatch target program does not select the concrete caller entity")
            return (dispatch_cursor.entity_index,)
        return target.source.lookup.selected_entity_indices
    if isinstance(instruction, AccumulatorConditionalTrigger):
        handler = index.first_trigger_handler(
            instruction.target_script_name,
            instruction.target_trigger,
        )
        if handler is None or handler.node.node_id != target_node_id:
            raise ValueError("dispatch target program does not match its conditional trigger")
        return handler.source.lookup.selected_entity_indices
    if isinstance(instruction, StageEffectInstruction):
        targets = tuple(
            target.entity_index
            for target in instruction.alert_targets
            if target.event_handler_node_id == target_node_id
        )
        if not targets:
            raise ValueError("dispatch target program does not match its alert instruction")
        return targets
    raise ValueError("dispatch cursor does not identify a dispatch instruction")


class SymbolicFrameOrigin(StrEnum):
    ROOT_EVENT = "root_event"
    NESTED_DISPATCH = "nested_dispatch"
    CALLER_SUFFIX = "caller_suffix"
    TARGET_GROUP_RESUME = "target_group_resume"
    BOUNDARY_RESUME = "boundary_resume"
    EVENT_REPLACEMENT = "event_replacement"


class SymbolicResumeMode(StrEnum):
    REENTER_BOUNDARY_ACTION = "reenter_boundary_action"


class SymbolicWakeConstraint(StrEnum):
    AFTER_BOUNDARY_COMPLETION = "after_boundary_completion"
    SAME_FRAME_LATER = "same_frame_later"
    NEXT_FRAME = "next_frame"
    TAG_PARENT_ORDER_UNKNOWN = "tag_parent_order_unknown"


class SymbolicTagParentDisposition(StrEnum):
    PROVEN_UNATTACHED = "proven_unattached"
    ATTACHED = "attached"
    UNKNOWN = "unknown"


class SymbolicWaitBranch(StrEnum):
    SUSPENDED_FALSE_RETURN = "suspended_false_return"


class SymbolicNextFrameCommand(StrEnum):
    RESET_SCRIPT = "resetscript"
    HALT = "halt"


class SymbolicMovementCommand(StrEnum):
    GOTO_MARKER = "gotomarker"
    FOLLOW_SPLINE = "followspline"
    FACE_ANGLES = "faceangles"


def _movement_action_waits_for_completion(action: ScriptAction) -> bool:
    if action.command == SymbolicMovementCommand.GOTO_MARKER:
        if len(action.arguments) < 2:
            raise ValueError("gotomarker action is missing its target or speed")
        return gotomarker_waits_for_completion(GotoMarkerEffect(action.arguments[0], action.arguments[1:], action.line))
    if action.command == SymbolicMovementCommand.FOLLOW_SPLINE:
        return followspline_waits_for_completion(action)
    if action.command == SymbolicMovementCommand.FACE_ANGLES:
        return True
    raise ValueError("movement boundary cursor does not identify a movement action")


class SymbolicScheduleDecisionKind(StrEnum):
    RUNNABLE = "runnable"
    SUSPENDED = "suspended"
    COMPLETE = "complete"
    BLOCKED = "blocked"
    WORK_BUDGET_EXHAUSTED = "work_budget_exhausted"


class SymbolicScheduleExhaustion(StrEnum):
    WORK_BUDGET_EXHAUSTED = "symbolic_schedule_work_budget_exhausted"


@dataclass(frozen=True, slots=True, order=True)
class SymbolicProgramCursor:
    node_id: str
    entity_index: int
    instruction_offset: int

    def __post_init__(self) -> None:
        if not self.node_id:
            raise ValueError("symbolic program cursor requires a node id")
        if self.entity_index < 0:
            raise ValueError("symbolic program cursor entity index must be non-negative")
        if self.instruction_offset < 0:
            raise ValueError("symbolic program cursor instruction offset must be non-negative")

    def validate(
        self,
        index: OrderedStageProgramIndex,
        *,
        allow_complete: bool = False,
    ) -> None:
        program = index.program(self.node_id)
        if self.entity_index not in program.source.lookup.selected_entity_indices:
            raise ValueError(f"entity {self.entity_index} is not selected by ordered program {self.node_id!r}")
        upper_bound = len(program.instructions) if allow_complete else len(program.instructions) - 1
        if self.instruction_offset > upper_bound:
            suffix = " or its completion cursor" if allow_complete else ""
            raise ValueError(
                f"instruction offset {self.instruction_offset} does not belong to ordered program "
                f"{self.node_id!r}{suffix}"
            )


@dataclass(frozen=True, slots=True)
class SymbolicInvocationStep:
    dispatch_cursor: SymbolicProgramCursor
    target_node_id: str
    target_ordinal: int

    def __post_init__(self) -> None:
        if not self.target_node_id:
            raise ValueError("symbolic invocation step requires a target node id")
        if self.target_ordinal < 0:
            raise ValueError("symbolic invocation target ordinal must be non-negative")

    def validate(self, index: OrderedStageProgramIndex) -> None:
        targets = _dispatch_target_group(index, self.dispatch_cursor, self.target_node_id)
        if self.target_ordinal >= len(targets):
            raise ValueError("symbolic invocation target ordinal is outside its dispatch target group")

    def target_entity_index(self, index: OrderedStageProgramIndex) -> int:
        self.validate(index)
        return _dispatch_target_group(index, self.dispatch_cursor, self.target_node_id)[self.target_ordinal]


def _validate_invocation_path(
    index: OrderedStageProgramIndex,
    invocation_path: tuple[SymbolicInvocationStep, ...],
    *,
    terminal_node_id: str,
    terminal_entity_index: int,
) -> None:
    for step in invocation_path:
        step.validate(index)
    for parent, child in zip(invocation_path, invocation_path[1:], strict=False):
        if (
            child.dispatch_cursor.node_id != parent.target_node_id
            or child.dispatch_cursor.entity_index != parent.target_entity_index(index)
        ):
            raise ValueError("symbolic invocation path contains a disconnected dispatch step")
    if invocation_path:
        final = invocation_path[-1]
        if final.target_node_id != terminal_node_id or final.target_entity_index(index) != terminal_entity_index:
            raise ValueError("symbolic invocation path does not terminate at its current event owner")


@dataclass(frozen=True, slots=True)
class PendingDispatchContext:
    dispatch_cursor: SymbolicProgramCursor
    caller_resume_cursor: SymbolicProgramCursor
    target_node_id: str
    ordered_target_entity_indices: tuple[int, ...]
    target_cursor: int

    def __post_init__(self) -> None:
        if not self.target_node_id:
            raise ValueError("pending dispatch requires a target node id")
        if not self.ordered_target_entity_indices:
            raise ValueError("pending dispatch requires at least one selected target")
        if any(entity_index < 0 for entity_index in self.ordered_target_entity_indices):
            raise ValueError("pending dispatch target indices must be non-negative")
        if len(set(self.ordered_target_entity_indices)) != len(self.ordered_target_entity_indices):
            raise ValueError("pending dispatch target order must not contain duplicate entities")
        if not 0 <= self.target_cursor < len(self.ordered_target_entity_indices):
            raise ValueError("pending dispatch target cursor must select an unexecuted target")

    def validate(self, index: OrderedStageProgramIndex) -> None:
        self.dispatch_cursor.validate(index)
        self.caller_resume_cursor.validate(index, allow_complete=True)
        if (
            self.caller_resume_cursor.node_id != self.dispatch_cursor.node_id
            or self.caller_resume_cursor.entity_index != self.dispatch_cursor.entity_index
        ):
            raise ValueError("pending dispatch caller resume cursor does not belong to its dispatch frame")
        if self.caller_resume_cursor.instruction_offset != self.dispatch_cursor.instruction_offset + 1:
            raise ValueError("pending dispatch caller must resume immediately after its dispatch instruction")
        expected_targets = _dispatch_target_group(index, self.dispatch_cursor, self.target_node_id)
        if self.ordered_target_entity_indices != expected_targets:
            raise ValueError(
                f"pending dispatch target order does not match the resolved group for {self.target_node_id!r}"
            )


@dataclass(frozen=True, slots=True)
class SymbolicFrame:
    cursor: SymbolicProgramCursor
    invocation_path: tuple[SymbolicInvocationStep, ...] = ()
    call_stack: tuple[SymbolicProgramCursor, ...] = ()
    pending_dispatch: PendingDispatchContext | None = None
    origin: SymbolicFrameOrigin = SymbolicFrameOrigin.ROOT_EVENT

    def validate(self, index: OrderedStageProgramIndex) -> None:
        self.cursor.validate(index)
        if self.pending_dispatch is not None:
            self.pending_dispatch.validate(index)
        _validate_invocation_path(
            index,
            self.invocation_path,
            terminal_node_id=self.cursor.node_id,
            terminal_entity_index=self.cursor.entity_index,
        )
        for cursor in self.call_stack:
            cursor.validate(index, allow_complete=True)
            if cursor.entity_index != self.cursor.entity_index:
                raise ValueError("saved call-stack cursors must belong to the active frame entity")
        if self.pending_dispatch is not None:
            if self.origin not in {
                SymbolicFrameOrigin.NESTED_DISPATCH,
                SymbolicFrameOrigin.TARGET_GROUP_RESUME,
                SymbolicFrameOrigin.BOUNDARY_RESUME,
            }:
                raise ValueError("pending dispatch context requires a nested-target frame origin")
            if not self.invocation_path:
                raise ValueError("pending dispatch context requires its target invocation step")
            terminal = self.invocation_path[-1]
            pending = self.pending_dispatch
            expected_entity = pending.ordered_target_entity_indices[pending.target_cursor]
            if self.cursor.node_id != pending.target_node_id or self.cursor.entity_index != expected_entity:
                raise ValueError("pending dispatch cursor does not identify the active nested target frame")
            if (
                terminal.dispatch_cursor != pending.dispatch_cursor
                or terminal.target_node_id != pending.target_node_id
                or terminal.target_ordinal != pending.target_cursor
            ):
                raise ValueError("pending dispatch context does not match its terminal invocation step")


@dataclass(frozen=True, slots=True)
class SymbolicWaitBoundaryState:
    arguments: tuple[str, ...]
    branch: SymbolicWaitBranch = SymbolicWaitBranch.SUSPENDED_FALSE_RETURN

    def __post_init__(self) -> None:
        if not self.arguments or any(not argument for argument in self.arguments):
            raise ValueError("wait boundary requires its non-empty source arguments")


@dataclass(frozen=True, slots=True)
class SymbolicMovementBoundaryState:
    command: SymbolicMovementCommand
    arguments: tuple[str, ...]
    temporal_state: SymbolicTemporalBoundaryState
    waits_for_completion: bool
    effect_started: bool

    def __post_init__(self) -> None:
        if not self.arguments or any(not argument for argument in self.arguments):
            raise ValueError("movement boundary requires its non-empty source arguments")
        if self.temporal_state is SymbolicTemporalBoundaryState.PRIOR_MOVEMENT_ACTIVE:
            if self.effect_started:
                raise ValueError("a prior-movement boundary cannot claim the new route started")
            return
        if not self.effect_started:
            raise ValueError("a current-action movement boundary must record its started effect")


@dataclass(frozen=True, slots=True)
class SymbolicNextFrameBoundaryState:
    command: SymbolicNextFrameCommand


SymbolicBoundaryState: TypeAlias = (
    SymbolicWaitBoundaryState | SymbolicMovementBoundaryState | SymbolicNextFrameBoundaryState
)


@dataclass(frozen=True, slots=True)
class SymbolicAsyncMovementLifecycle:
    source_cursor: SymbolicProgramCursor
    command: SymbolicMovementCommand
    arguments: tuple[str, ...]
    effect_footprint: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.arguments or any(not argument for argument in self.arguments):
            raise ValueError("asynchronous movement lifecycle requires its source arguments")
        if any(not item for item in self.effect_footprint):
            raise ValueError("asynchronous movement effect footprint entries must not be empty")

    def validate(self, index: OrderedStageProgramIndex) -> None:
        self.source_cursor.validate(index)
        program = index.program(self.source_cursor.node_id)
        action = program.event.actions[self.source_cursor.instruction_offset]
        if action.command != self.command.value or action.arguments != self.arguments:
            raise ValueError("asynchronous movement lifecycle does not match its source action")
        if self.command is SymbolicMovementCommand.FACE_ANGLES:
            raise ValueError("faceangles cannot advance while its movement lifecycle remains active")
        if _movement_action_waits_for_completion(action):
            raise ValueError("waiting movement cannot be represented as an asynchronous lifecycle")


@dataclass(frozen=True, slots=True)
class SuspendedContinuation:
    frame: SymbolicFrame
    boundary_line: int
    resume_mode: SymbolicResumeMode
    boundary_state: SymbolicBoundaryState
    wake_constraint: SymbolicWakeConstraint
    effect_footprint: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.boundary_line <= 0:
            raise ValueError("suspended continuation boundary line must be positive")
        if any(not item for item in self.effect_footprint):
            raise ValueError("suspended continuation effect footprint entries must not be empty")

    def validate(self, index: OrderedStageProgramIndex) -> None:
        self.frame.validate(index)
        program = index.program(self.frame.cursor.node_id)
        action = program.event.actions[self.frame.cursor.instruction_offset]
        if self.resume_mode is not SymbolicResumeMode.REENTER_BOUNDARY_ACTION:
            raise ValueError("suspended script continuation must re-enter its boundary action")
        if self.boundary_line != action.line:
            raise ValueError("re-entered boundary line does not match the frame instruction cursor")
        if isinstance(self.boundary_state, SymbolicWaitBoundaryState):
            if action.command != "wait" or action.arguments != self.boundary_state.arguments:
                raise ValueError("wait boundary state does not match its source action")
            return
        if isinstance(self.boundary_state, SymbolicNextFrameBoundaryState):
            if action.command != self.boundary_state.command.value:
                raise ValueError("next-frame boundary state does not match its source action")
            return
        if action.command != self.boundary_state.command.value or action.arguments != self.boundary_state.arguments:
            raise ValueError("movement boundary state does not match its source action")
        waits_for_completion = _movement_action_waits_for_completion(action)
        if self.boundary_state.waits_for_completion != waits_for_completion:
            raise ValueError("movement boundary wait state does not match its source action")
        if self.boundary_state.temporal_state is SymbolicTemporalBoundaryState.CURRENT_ACTION_WAITING:
            if not waits_for_completion:
                raise ValueError("non-waiting movement cannot suspend after its action starts")
        elif self.boundary_state.temporal_state is not SymbolicTemporalBoundaryState.PRIOR_MOVEMENT_ACTIVE:
            raise ValueError("suspended movement has an invalid temporal boundary state")
        if (
            self.boundary_state.command is SymbolicMovementCommand.FACE_ANGLES
            and self.boundary_state.temporal_state is not SymbolicTemporalBoundaryState.CURRENT_ACTION_WAITING
        ):
            raise ValueError("faceangles may suspend only on its current waiting action")


@dataclass(frozen=True, slots=True)
class SymbolicEventOwner:
    entity_index: int
    event_node_id: str
    invocation_path: tuple[SymbolicInvocationStep, ...] = ()

    def __post_init__(self) -> None:
        if self.entity_index < 0:
            raise ValueError("event owner entity index must be non-negative")
        if not self.event_node_id:
            raise ValueError("event owner requires a node id")

    @classmethod
    def from_frame(cls, frame: SymbolicFrame) -> SymbolicEventOwner:
        return cls(frame.cursor.entity_index, frame.cursor.node_id, frame.invocation_path)

    def validate(self, index: OrderedStageProgramIndex) -> None:
        program = index.program(self.event_node_id)
        if self.entity_index not in program.source.lookup.selected_entity_indices:
            raise ValueError(f"event owner does not belong to ordered program {self.event_node_id!r}")
        _validate_invocation_path(
            index,
            self.invocation_path,
            terminal_node_id=self.event_node_id,
            terminal_entity_index=self.entity_index,
        )


@dataclass(frozen=True, slots=True, order=True)
class SymbolicTagParentState:
    child_entity_index: int
    disposition: SymbolicTagParentDisposition
    parent_entity_index: int | None = None

    def __post_init__(self) -> None:
        if self.child_entity_index < 0:
            raise ValueError("tag-parent child entity index must be non-negative")
        if self.disposition is SymbolicTagParentDisposition.ATTACHED:
            if self.parent_entity_index is None or self.parent_entity_index < 0:
                raise ValueError("attached tag-parent state requires a non-negative parent index")
            if self.parent_entity_index == self.child_entity_index:
                raise ValueError("tag-parent child and parent must be different entities")
        elif self.parent_entity_index is not None:
            raise ValueError("only attached tag-parent state may name a parent entity")


@dataclass(frozen=True, slots=True)
class SymbolicEffectRecord:
    projection: StageEffectProjection
    source_cursor: SymbolicProgramCursor

    def validate(self, index: OrderedStageProgramIndex) -> None:
        self.source_cursor.validate(index)
        program = index.program(self.source_cursor.node_id)
        instruction = program.instructions[self.source_cursor.instruction_offset]
        if not isinstance(instruction, StageEffectInstruction):
            raise ValueError("symbolic effect source cursor does not identify a stage effect")
        if instruction.projection != self.projection:
            raise ValueError("symbolic effect projection does not match its source cursor")


def _canonical_accumulator_state(state: SymbolicAccumulatorState) -> SymbolicAccumulatorState:
    if not state.default_domain.has_candidate():
        raise ValueError("symbolic accumulator default domain has no possible value")
    entity_values = {}
    for entity_index, buffer_index, value in state.entity_values:
        if entity_index < 0 or not 0 <= buffer_index < 10:
            raise ValueError("symbolic entity accumulator key is outside ET bounds")
        if not value.has_candidate():
            raise ValueError("symbolic entity accumulator domain has no possible value")
        key = (entity_index, buffer_index)
        if key in entity_values and entity_values[key] != value:
            raise ValueError("symbolic entity accumulator has conflicting duplicate values")
        entity_values[key] = value

    global_values = {}
    for buffer_index, value in state.global_values:
        if not 0 <= buffer_index < 10:
            raise ValueError("symbolic global accumulator key is outside ET bounds")
        if not value.has_candidate():
            raise ValueError("symbolic global accumulator domain has no possible value")
        if buffer_index in global_values and global_values[buffer_index] != value:
            raise ValueError("symbolic global accumulator has conflicting duplicate values")
        global_values[buffer_index] = value

    return SymbolicAccumulatorState(
        tuple(
            (entity_index, buffer_index, value)
            for (entity_index, buffer_index), value in sorted(entity_values.items())
            if value != state.default_domain
        ),
        tuple(
            (buffer_index, value)
            for buffer_index, value in sorted(global_values.items())
            if value != state.default_domain
        ),
        state.default_domain,
    )


@dataclass(frozen=True, slots=True, init=False)
class SymbolicScheduleState:
    program_identity: tuple[object, ...]
    accumulator_state: SymbolicAccumulatorState
    runnable: tuple[SymbolicFrame, ...]
    suspended: tuple[SuspendedContinuation, ...]
    async_lifecycles: tuple[SymbolicAsyncMovementLifecycle, ...]
    event_owners: tuple[SymbolicEventOwner, ...]
    tag_parent_states: tuple[SymbolicTagParentState, ...] = ()
    effects: tuple[SymbolicEffectRecord, ...] = ()
    provenance: tuple[str, ...] = ()
    ordering_decisions: tuple[str, ...] = ()
    unknown_reasons: tuple[str, ...] = ()

    def __init__(
        self,
        program_identity: tuple[object, ...],
        accumulator_state: SymbolicAccumulatorState,
        runnable: tuple[SymbolicFrame, ...],
        suspended: tuple[SuspendedContinuation, ...],
        async_lifecycles: tuple[SymbolicAsyncMovementLifecycle, ...],
        event_owners: tuple[SymbolicEventOwner, ...],
        tag_parent_states: tuple[SymbolicTagParentState, ...],
        effects: tuple[SymbolicEffectRecord, ...],
        provenance: tuple[str, ...],
        ordering_decisions: tuple[str, ...],
        unknown_reasons: tuple[str, ...],
        *,
        _creation_token: object,
    ) -> None:
        if _creation_token is not _STATE_CREATION_TOKEN:
            raise TypeError("use SymbolicScheduleState.create() to validate scheduler state")
        object.__setattr__(self, "program_identity", program_identity)
        object.__setattr__(self, "accumulator_state", accumulator_state)
        object.__setattr__(self, "runnable", runnable)
        object.__setattr__(self, "suspended", suspended)
        object.__setattr__(self, "async_lifecycles", async_lifecycles)
        object.__setattr__(self, "event_owners", event_owners)
        object.__setattr__(self, "tag_parent_states", tag_parent_states)
        object.__setattr__(self, "effects", effects)
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "ordering_decisions", ordering_decisions)
        object.__setattr__(self, "unknown_reasons", unknown_reasons)

    @classmethod
    def create(
        cls,
        index: OrderedStageProgramIndex,
        *,
        accumulator_state: SymbolicAccumulatorState,
        runnable: tuple[SymbolicFrame, ...] = (),
        suspended: tuple[SuspendedContinuation, ...] = (),
        async_lifecycles: tuple[SymbolicAsyncMovementLifecycle, ...] = (),
        event_owners: tuple[SymbolicEventOwner, ...] = (),
        tag_parent_states: tuple[SymbolicTagParentState, ...] = (),
        effects: tuple[SymbolicEffectRecord, ...] = (),
        provenance: tuple[str, ...] = (),
        ordering_decisions: tuple[str, ...] = (),
        unknown_reasons: tuple[str, ...] = (),
    ) -> SymbolicScheduleState:
        for frame in runnable:
            frame.validate(index)
        for continuation in suspended:
            continuation.validate(index)
        for lifecycle in async_lifecycles:
            lifecycle.validate(index)
        for owner in event_owners:
            owner.validate(index)
        for effect in effects:
            effect.validate(index)

        active_frames = tuple(runnable) + tuple(item.frame for item in suspended)
        active_entities = [frame.cursor.entity_index for frame in active_frames]
        if len(set(active_entities)) != len(active_entities):
            raise ValueError("a symbolic entity cannot own multiple active scheduler tasks")
        lifecycle_entities = [lifecycle.source_cursor.entity_index for lifecycle in async_lifecycles]
        if len(set(lifecycle_entities)) != len(lifecycle_entities):
            raise ValueError("a symbolic entity cannot own multiple asynchronous movement lifecycles")
        lifecycle_entity_set = set(lifecycle_entities)
        for continuation in suspended:
            if (
                continuation.frame.cursor.entity_index in lifecycle_entity_set
                and isinstance(continuation.boundary_state, SymbolicMovementBoundaryState)
                and continuation.boundary_state.temporal_state
                is not SymbolicTemporalBoundaryState.PRIOR_MOVEMENT_ACTIVE
            ):
                raise ValueError("a suspended movement cannot start while the entity has an active movement lifecycle")

        owners_by_entity = {owner.entity_index: owner for owner in event_owners}
        if len(owners_by_entity) != len(event_owners):
            raise ValueError("symbolic schedule has duplicate event owners")
        expected_owners = {frame.cursor.entity_index: SymbolicEventOwner.from_frame(frame) for frame in active_frames}
        if owners_by_entity != expected_owners:
            raise ValueError("symbolic event owners must exactly match active scheduler frames")

        tag_states_by_child = {state.child_entity_index: state for state in tag_parent_states}
        if len(tag_states_by_child) != len(tag_parent_states):
            raise ValueError("symbolic schedule has duplicate tag-parent states")
        for collection_name, values in (
            ("provenance", provenance),
            ("ordering decision", ordering_decisions),
            ("unknown reason", unknown_reasons),
        ):
            if any(not value for value in values):
                raise ValueError(f"symbolic schedule {collection_name} entries must not be empty")

        return cls(
            (index.programs, tuple(sorted(index.opaque_script_names))),
            _canonical_accumulator_state(accumulator_state),
            tuple(runnable),
            tuple(sorted(suspended, key=_continuation_sort_key)),
            tuple(sorted(async_lifecycles, key=_lifecycle_sort_key)),
            tuple(sorted(event_owners, key=lambda owner: owner.entity_index)),
            tuple(sorted(tag_parent_states, key=lambda state: state.child_entity_index)),
            tuple(effects),
            tuple(provenance),
            tuple(ordering_decisions),
            tuple(sorted(set(unknown_reasons))),
            _creation_token=_STATE_CREATION_TOKEN,
        )

    @property
    def canonical_key(self) -> tuple[object, ...]:
        return (
            self.program_identity,
            self.accumulator_state,
            self.runnable,
            self.suspended,
            self.async_lifecycles,
            self.event_owners,
            self.tag_parent_states,
            self.effects,
            self.provenance,
            self.ordering_decisions,
            self.unknown_reasons,
        )


def _continuation_sort_key(continuation: SuspendedContinuation) -> tuple[object, ...]:
    frame = continuation.frame
    invocation_path = tuple(
        (
            step.dispatch_cursor.node_id,
            step.dispatch_cursor.entity_index,
            step.dispatch_cursor.instruction_offset,
            step.target_node_id,
            step.target_ordinal,
        )
        for step in frame.invocation_path
    )
    pending = frame.pending_dispatch
    pending_key: tuple[object, ...] = (
        (0,)
        if pending is None
        else (
            1,
            pending.dispatch_cursor,
            pending.caller_resume_cursor,
            pending.target_node_id,
            pending.ordered_target_entity_indices,
            pending.target_cursor,
        )
    )
    return (
        continuation.wake_constraint.value,
        frame.cursor.entity_index,
        frame.cursor.node_id,
        frame.cursor.instruction_offset,
        continuation.boundary_line,
        continuation.resume_mode.value,
        repr(continuation.boundary_state),
        invocation_path,
        tuple((cursor.node_id, cursor.entity_index, cursor.instruction_offset) for cursor in frame.call_stack),
        pending_key,
    )


def _lifecycle_sort_key(lifecycle: SymbolicAsyncMovementLifecycle) -> tuple[object, ...]:
    cursor = lifecycle.source_cursor
    return (
        cursor.entity_index,
        cursor.node_id,
        cursor.instruction_offset,
        lifecycle.command.value,
        lifecycle.arguments,
        lifecycle.effect_footprint,
    )


@dataclass(frozen=True, slots=True)
class SymbolicScheduleDecision:
    kind: SymbolicScheduleDecisionKind
    state: SymbolicScheduleState | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        needs_reason = self.kind in {
            SymbolicScheduleDecisionKind.BLOCKED,
            SymbolicScheduleDecisionKind.WORK_BUDGET_EXHAUSTED,
        }
        if needs_reason != (self.reason is not None):
            raise ValueError("symbolic schedule decision reason does not match its kind")
        if self.reason == "":
            raise ValueError("symbolic schedule decision reason must not be empty")
        if self.kind is not SymbolicScheduleDecisionKind.WORK_BUDGET_EXHAUSTED and self.state is None:
            raise ValueError("non-exhaustion scheduler decisions require their resulting state")


@dataclass(frozen=True, slots=True)
class SymbolicScheduleResult:
    decisions: tuple[SymbolicScheduleDecision, ...]
    work_consumed: int
    work_limit: int
    exhaustion: SymbolicScheduleExhaustion | None = None

    def __post_init__(self) -> None:
        if self.work_limit <= 0:
            raise ValueError("symbolic schedule work limit must be positive")
        if not 0 <= self.work_consumed <= self.work_limit:
            raise ValueError("symbolic schedule work consumption is outside its global budget")
        has_exhausted_decision = any(
            decision.kind is SymbolicScheduleDecisionKind.WORK_BUDGET_EXHAUSTED for decision in self.decisions
        )
        if has_exhausted_decision != (self.exhaustion is not None):
            raise ValueError("symbolic schedule exhaustion metadata does not match its decisions")
        if self.exhaustion is not None and self.work_consumed != self.work_limit:
            raise ValueError("symbolic schedule can exhaust only after consuming its global budget")


@dataclass(slots=True)
class SymbolicScheduleWorkBudget:
    limit: int
    consumed: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.limit <= 0:
            raise ValueError("symbolic schedule work budget must be positive")

    @property
    def remaining(self) -> int:
        return self.limit - self.consumed

    def consume(self) -> SymbolicScheduleExhaustion | None:
        if self.consumed >= self.limit:
            return SymbolicScheduleExhaustion.WORK_BUDGET_EXHAUSTED
        self.consumed += 1
        return None
