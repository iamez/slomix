"""Immutable state contracts for bounded ET script scheduling.

The module owns validated state identity and the S3 transition runner. Bounded
multi-task search remains a later wave and must not weaken these construction
boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import TypeAlias

from website.backend.map_geometry.stage import (
    GotoMarkerEffect,
    ScriptAction,
    TriggerDispatch,
    TriggerResolution,
)
from website.backend.map_geometry.stage_possibilities import (
    AlertTargetDisposition,
    ControlBarrierInstruction,
    KillInstruction,
    KillTargetDisposition,
    OrderedEventProgram,
    OrderedStageProgramIndex,
    StageEffectInstruction,
    SymbolicAccumulatorState,
    SymbolicDispatchResolution,
    SymbolicEventPath,
    SymbolicIntegerDomain,
    SymbolicPathCompletion,
    SymbolicTemporalBoundaryState,
    TriggerInstruction,
    followspline_waits_for_completion,
    gotomarker_waits_for_completion,
    resolve_symbolic_nested_dispatch,
    walk_symbolic_event_program,
    walk_symbolic_stage_program,
)
from website.backend.map_geometry.stage_semantics import AccumulatorConditionalTrigger, StageEffectProjection

_STATE_CREATION_TOKEN = object()
_ET_SIGNED_INT_MIN = -(1 << 31)
_ET_SIGNED_INT_MAX = (1 << 31) - 1
_ET_ACCUMULATOR_BIT_MASK = (1 << 32) - 1


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
        dispatch_targets = tuple(target for target in instruction.alert_targets if target.event_handler_node_id)
        if any(target.event_handler_node_id != target_node_id for target in dispatch_targets):
            raise ValueError("heterogeneous alert dispatch order cannot be represented by one pending group")
        targets = tuple(target.entity_index for target in dispatch_targets)
        if not targets:
            raise ValueError("dispatch target program does not match its alert instruction")
        return targets
    if isinstance(instruction, KillInstruction):
        dispatch_targets = tuple(
            target
            for target in instruction.targets
            if target.disposition is KillTargetDisposition.SCRIPT_MOVER_OPTIONAL_DEATH_EVENT
            and target.death_handler_node_id
        )
        if len(dispatch_targets) != 1 or dispatch_targets[0].death_handler_node_id != target_node_id:
            raise ValueError("dispatch target program does not match its optional death instruction")
        return (dispatch_targets[0].entity_index,)
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
    caller_dispatches: tuple[PendingDispatchContext, ...] = ()
    origin: SymbolicFrameOrigin = SymbolicFrameOrigin.ROOT_EVENT

    def validate(self, index: OrderedStageProgramIndex) -> None:
        self.cursor.validate(index)
        if self.pending_dispatch is not None:
            self.pending_dispatch.validate(index)
        for caller_dispatch in self.caller_dispatches:
            caller_dispatch.validate(index)
        if len(set(self.caller_dispatches)) != len(self.caller_dispatches):
            raise ValueError("caller dispatch stack must not contain duplicate contexts")
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
        if self.origin is SymbolicFrameOrigin.ROOT_EVENT and self.invocation_path:
            raise ValueError("root event frame cannot carry nested invocation ancestry")
        if self.origin in {
            SymbolicFrameOrigin.NESTED_DISPATCH,
            SymbolicFrameOrigin.TARGET_GROUP_RESUME,
        } and not self.invocation_path:
            raise ValueError("nested frame origin requires invocation ancestry")
        if self.pending_dispatch is not None and self.caller_dispatches:
            raise ValueError("a frame cannot be both a dispatch target and its caller suffix")
        if self.caller_dispatches:
            if self.origin is not SymbolicFrameOrigin.CALLER_SUFFIX:
                raise ValueError("caller dispatch context requires a caller-suffix frame")
            for caller_dispatch in self.caller_dispatches:
                resume = caller_dispatch.caller_resume_cursor
                if (
                    self.cursor.node_id != resume.node_id
                    or self.cursor.entity_index != resume.entity_index
                    or self.cursor.instruction_offset < resume.instruction_offset
                ):
                    raise ValueError("caller suffix cursor precedes a completed dispatch resume point")
                if caller_dispatch.target_cursor != len(caller_dispatch.ordered_target_entity_indices) - 1:
                    raise ValueError("caller suffix may resume only after the complete target group")
        if self.pending_dispatch is not None:
            if self.origin not in {
                SymbolicFrameOrigin.NESTED_DISPATCH,
                SymbolicFrameOrigin.TARGET_GROUP_RESUME,
                SymbolicFrameOrigin.BOUNDARY_RESUME,
                SymbolicFrameOrigin.EVENT_REPLACEMENT,
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
    effect_record_index: int | None = None

    def __post_init__(self) -> None:
        if not self.arguments or any(not argument for argument in self.arguments):
            raise ValueError("movement boundary requires its non-empty source arguments")
        if self.effect_record_index is not None and self.effect_record_index < 0:
            raise ValueError("movement boundary effect record index must be non-negative")
        if self.command is SymbolicMovementCommand.GOTO_MARKER:
            if self.effect_started != (self.effect_record_index is not None):
                raise ValueError("gotomarker start state requires its current effect record index")
        elif self.effect_record_index is not None:
            raise ValueError("only gotomarker movement may reference a stage effect record")
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
    effect_record_index: int | None = None
    effect_footprint: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.arguments or any(not argument for argument in self.arguments):
            raise ValueError("asynchronous movement lifecycle requires its source arguments")
        if any(not item for item in self.effect_footprint):
            raise ValueError("asynchronous movement effect footprint entries must not be empty")
        if self.effect_record_index is not None and self.effect_record_index < 0:
            raise ValueError("asynchronous movement effect record index must be non-negative")
        if self.command is SymbolicMovementCommand.GOTO_MARKER:
            if self.effect_record_index is None:
                raise ValueError("started gotomarker lifecycle requires its current effect record index")
        elif self.effect_record_index is not None:
            raise ValueError("only gotomarker lifecycle may reference a stage effect record")

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
    caller_suffix_completed: bool = False
    caller_suffix_abandoned: bool = False

    def __post_init__(self) -> None:
        if self.boundary_line <= 0:
            raise ValueError("suspended continuation boundary line must be positive")
        if any(not item for item in self.effect_footprint):
            raise ValueError("suspended continuation effect footprint entries must not be empty")

    def validate(self, index: OrderedStageProgramIndex) -> None:
        self.frame.validate(index)
        if self.caller_suffix_completed and self.frame.pending_dispatch is None:
            raise ValueError("only a nested dispatch continuation may record caller suffix completion")
        if self.caller_suffix_abandoned and self.frame.pending_dispatch is None:
            raise ValueError("only a nested dispatch continuation may record caller suffix abandonment")
        if self.caller_suffix_completed and self.caller_suffix_abandoned:
            raise ValueError("a caller suffix cannot be both completed and abandoned")
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
            if self.wake_constraint is not SymbolicWakeConstraint.NEXT_FRAME:
                raise ValueError("next-frame boundary requires a next-frame wake constraint")
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


def _validate_accumulator_domain(domain: SymbolicIntegerDomain, *, label: str) -> None:
    if not _ET_SIGNED_INT_MIN <= domain.lower <= domain.upper <= _ET_SIGNED_INT_MAX:
        raise ValueError(f"{label} is outside the signed 32-bit ET accumulator range")
    if not 0 <= domain.required_set_bits <= _ET_ACCUMULATOR_BIT_MASK:
        raise ValueError(f"{label} has a required-set mask outside ET accumulator bits")
    if not 0 <= domain.required_clear_bits <= _ET_ACCUMULATOR_BIT_MASK:
        raise ValueError(f"{label} has a required-clear mask outside ET accumulator bits")
    if any(not _ET_SIGNED_INT_MIN <= value <= _ET_SIGNED_INT_MAX for value in domain.excluded):
        raise ValueError(f"{label} excludes a value outside the ET accumulator range")
    if not domain.has_candidate():
        raise ValueError(f"{label} has no possible value")


def _canonical_accumulator_domain(domain: SymbolicIntegerDomain, *, label: str) -> SymbolicIntegerDomain:
    _validate_accumulator_domain(domain, label=label)
    relevant_exclusions = frozenset(
        value
        for value in domain.excluded
        if domain.lower <= value <= domain.upper
        and value & domain.required_set_bits == domain.required_set_bits
        and not value & domain.required_clear_bits
    )
    return replace(domain, excluded=relevant_exclusions)


def _canonical_accumulator_state(state: SymbolicAccumulatorState) -> SymbolicAccumulatorState:
    default_domain = _canonical_accumulator_domain(
        state.default_domain,
        label="symbolic accumulator default domain",
    )
    entity_values = {}
    for entity_index, buffer_index, value in state.entity_values:
        if entity_index < 0 or not 0 <= buffer_index < 10:
            raise ValueError("symbolic entity accumulator key is outside ET bounds")
        value = _canonical_accumulator_domain(value, label="symbolic entity accumulator domain")
        key = (entity_index, buffer_index)
        if key in entity_values and entity_values[key] != value:
            raise ValueError("symbolic entity accumulator has conflicting duplicate values")
        entity_values[key] = value

    global_values = {}
    for buffer_index, value in state.global_values:
        if not 0 <= buffer_index < 10:
            raise ValueError("symbolic global accumulator key is outside ET bounds")
        value = _canonical_accumulator_domain(value, label="symbolic global accumulator domain")
        if buffer_index in global_values and global_values[buffer_index] != value:
            raise ValueError("symbolic global accumulator has conflicting duplicate values")
        global_values[buffer_index] = value

    return SymbolicAccumulatorState(
        tuple(
            (entity_index, buffer_index, value)
            for (entity_index, buffer_index), value in sorted(entity_values.items())
            if value != default_domain
        ),
        tuple(
            (buffer_index, value)
            for buffer_index, value in sorted(global_values.items())
            if value != default_domain
        ),
        default_domain,
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
        def effect_at(index_value: int, *, source_cursor: SymbolicProgramCursor) -> SymbolicEffectRecord:
            if index_value >= len(effects):
                raise ValueError("movement effect record index is outside scheduler effect history")
            effect = effects[index_value]
            if effect.source_cursor != source_cursor:
                raise ValueError("movement effect record does not match its current source cursor")
            return effect

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
                and continuation.boundary_state.command
                in {
                    SymbolicMovementCommand.GOTO_MARKER,
                    SymbolicMovementCommand.FOLLOW_SPLINE,
                }
                and continuation.boundary_state.temporal_state
                is not SymbolicTemporalBoundaryState.PRIOR_MOVEMENT_ACTIVE
            ):
                raise ValueError(
                    "a suspended translational movement cannot start while the entity has an active movement lifecycle"
                )
            if (
                isinstance(continuation.boundary_state, SymbolicMovementBoundaryState)
                and continuation.boundary_state.command is SymbolicMovementCommand.GOTO_MARKER
            ):
                effect_index = continuation.boundary_state.effect_record_index
                if effect_index is not None:
                    effect_at(effect_index, source_cursor=continuation.frame.cursor)
        for lifecycle in async_lifecycles:
            if lifecycle.command is SymbolicMovementCommand.GOTO_MARKER:
                effect_index = lifecycle.effect_record_index
                if effect_index is None:
                    raise AssertionError("validated gotomarker lifecycle lost its effect record index")
                effect_at(effect_index, source_cursor=lifecycle.source_cursor)

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
    caller_dispatch_key = tuple(
        (
            caller_dispatch.dispatch_cursor,
            caller_dispatch.caller_resume_cursor,
            caller_dispatch.target_node_id,
            caller_dispatch.ordered_target_entity_indices,
            caller_dispatch.target_cursor,
        )
        for caller_dispatch in frame.caller_dispatches
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
        caller_dispatch_key,
        continuation.caller_suffix_completed,
        continuation.caller_suffix_abandoned,
    )


def _lifecycle_sort_key(lifecycle: SymbolicAsyncMovementLifecycle) -> tuple[object, ...]:
    cursor = lifecycle.source_cursor
    return (
        cursor.entity_index,
        cursor.node_id,
        cursor.instruction_offset,
        lifecycle.command.value,
        lifecycle.arguments,
        lifecycle.effect_record_index,
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
        if self.state is None:
            raise ValueError("scheduler decisions require their resulting frontier state")
        if self.kind is SymbolicScheduleDecisionKind.RUNNABLE and not self.state.runnable:
            raise ValueError("runnable scheduler decision requires runnable work")
        if self.kind is SymbolicScheduleDecisionKind.SUSPENDED and (
            self.state.runnable or not self.state.suspended
        ):
            raise ValueError("suspended scheduler decision requires only suspended script work")
        if self.kind is SymbolicScheduleDecisionKind.COMPLETE and (
            self.state.runnable or self.state.suspended
        ):
            raise ValueError("complete scheduler decision cannot retain runnable or suspended script work")


@dataclass(frozen=True, slots=True)
class SymbolicScheduleResult:
    decisions: tuple[SymbolicScheduleDecision, ...]
    work_consumed: int
    work_limit: int
    exhaustion: SymbolicScheduleExhaustion | None = None

    def __post_init__(self) -> None:
        if not self.decisions:
            raise ValueError("symbolic schedule result requires at least one decision")
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
        if self.exhaustion is not None and any(
            decision.reason != self.exhaustion.value
            for decision in self.decisions
            if decision.kind is SymbolicScheduleDecisionKind.WORK_BUDGET_EXHAUSTED
        ):
            raise ValueError("symbolic schedule exhaustion decision reason does not match result metadata")
        ordered = tuple(sorted(set(self.decisions), key=_decision_sort_key))
        object.__setattr__(self, "decisions", ordered)


def _decision_sort_key(decision: SymbolicScheduleDecision) -> tuple[str, str, str]:
    return (
        decision.kind.value,
        decision.reason or "",
        repr(decision.state.canonical_key),
    )


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


def _state_for_index(index: OrderedStageProgramIndex, state: SymbolicScheduleState) -> None:
    expected_identity = (index.programs, tuple(sorted(index.opaque_script_names)))
    if state.program_identity != expected_identity:
        raise ValueError("symbolic schedule state does not belong to this ordered-program index")


def _rebuild_schedule_state(
    index: OrderedStageProgramIndex,
    state: SymbolicScheduleState,
    *,
    accumulator_state: SymbolicAccumulatorState | None = None,
    runnable: tuple[SymbolicFrame, ...] | None = None,
    suspended: tuple[SuspendedContinuation, ...] | None = None,
    async_lifecycles: tuple[SymbolicAsyncMovementLifecycle, ...] | None = None,
    effects: tuple[SymbolicEffectRecord, ...] | None = None,
    provenance: tuple[str, ...] | None = None,
    ordering_decisions: tuple[str, ...] | None = None,
    unknown_reasons: tuple[str, ...] | None = None,
) -> SymbolicScheduleState:
    next_runnable = state.runnable if runnable is None else runnable
    next_suspended = state.suspended if suspended is None else suspended
    active_frames = next_runnable + tuple(item.frame for item in next_suspended)
    return SymbolicScheduleState.create(
        index,
        accumulator_state=state.accumulator_state if accumulator_state is None else accumulator_state,
        runnable=next_runnable,
        suspended=next_suspended,
        async_lifecycles=(
            state.async_lifecycles if async_lifecycles is None else async_lifecycles
        ),
        event_owners=tuple(SymbolicEventOwner.from_frame(frame) for frame in active_frames),
        tag_parent_states=state.tag_parent_states,
        effects=state.effects if effects is None else effects,
        provenance=state.provenance if provenance is None else provenance,
        ordering_decisions=(
            state.ordering_decisions if ordering_decisions is None else ordering_decisions
        ),
        unknown_reasons=state.unknown_reasons if unknown_reasons is None else unknown_reasons,
    )


def _blocked_transition(
    index: OrderedStageProgramIndex,
    state: SymbolicScheduleState,
    reason: str,
) -> SymbolicScheduleResult:
    blocked = _rebuild_schedule_state(
        index,
        state,
        unknown_reasons=state.unknown_reasons + (reason,),
    )
    return SymbolicScheduleResult(
        (SymbolicScheduleDecision(SymbolicScheduleDecisionKind.BLOCKED, blocked, reason),),
        1,
        1,
    )


def _program_suffix(program: OrderedEventProgram, instruction_offset: int) -> OrderedEventProgram:
    return replace(program, instructions=program.instructions[instruction_offset:])


def _path_effect_records(
    program: OrderedEventProgram,
    *,
    instruction_offset: int,
    source_entity_index: int,
    projections: tuple[StageEffectProjection, ...],
    effect_entity_indices: tuple[int, ...],
) -> tuple[SymbolicEffectRecord, ...]:
    if len(projections) != len(effect_entity_indices):
        raise RuntimeError("symbolic path effect provenance is internally inconsistent")
    records: list[SymbolicEffectRecord] = []
    search_offset = instruction_offset
    for projection, entity_index in zip(projections, effect_entity_indices, strict=True):
        if entity_index != source_entity_index:
            raise RuntimeError("single-frame scheduler segment produced an effect for another entity")
        matched_offset = next(
            (
                offset
                for offset in range(search_offset, len(program.instructions))
                if isinstance(program.instructions[offset], StageEffectInstruction)
                and program.instructions[offset].projection == projection
            ),
            None,
        )
        if matched_offset is None:
            raise RuntimeError("symbolic path effect has no source instruction in its scheduler segment")
        records.append(
            SymbolicEffectRecord(
                projection,
                SymbolicProgramCursor(program.node.node_id, source_entity_index, matched_offset),
            )
        )
        search_offset = matched_offset + 1
    return tuple(records)


def _nested_path_effect_records(
    index: OrderedStageProgramIndex,
    *,
    projections: tuple[StageEffectProjection, ...],
    effect_entity_indices: tuple[int, ...],
) -> tuple[SymbolicEffectRecord, ...]:
    if len(projections) != len(effect_entity_indices):
        raise RuntimeError("symbolic path effect provenance is internally inconsistent")
    records: list[SymbolicEffectRecord] = []
    for projection, entity_index in zip(projections, effect_entity_indices, strict=True):
        line = projection.effect.line
        matches = tuple(
            SymbolicEffectRecord(
                projection,
                SymbolicProgramCursor(program.node.node_id, entity_index, offset),
            )
            for program in index.programs_for_instruction_line(line)
            if entity_index in program.source.lookup.selected_entity_indices
            for offset, instruction in enumerate(program.instructions)
            if isinstance(instruction, StageEffectInstruction)
            and instruction.projection == projection
        )
        if len(matches) != 1:
            raise RuntimeError("nested symbolic effect does not resolve to one source instruction")
        records.append(matches[0])
    return tuple(records)


def _path_async_lifecycles(
    index: OrderedStageProgramIndex,
    *,
    path: SymbolicEventPath,
    effects: tuple[SymbolicEffectRecord, ...],
    existing: tuple[SymbolicAsyncMovementLifecycle, ...],
) -> tuple[SymbolicAsyncMovementLifecycle, ...]:
    next_lifecycles = list(existing)
    for start in path.async_movement_starts:
        matches = tuple(
            SymbolicProgramCursor(program.node.node_id, start.source_entity_index, offset)
            for program in index.programs_for_instruction_line(start.line)
            if start.source_entity_index in program.source.lookup.selected_entity_indices
            for offset, action in enumerate(program.event.actions)
            if action.line == start.line
            and action.command == start.command
            and action.arguments == start.arguments
        )
        if len(matches) != 1:
            raise RuntimeError("asynchronous movement start does not resolve to one source instruction")
        cursor = matches[0]
        command = SymbolicMovementCommand(start.command)
        effect_index = None
        if command is SymbolicMovementCommand.GOTO_MARKER:
            effect_index = next(
                (
                    index_value
                    for index_value in range(len(effects) - 1, -1, -1)
                    if effects[index_value].source_cursor == cursor
                ),
                None,
            )
            if effect_index is None:
                raise RuntimeError("non-waiting gotomarker lost its route-effect record")
        lifecycle = SymbolicAsyncMovementLifecycle(
            cursor,
            command,
            start.arguments,
            effect_record_index=effect_index,
        )
        next_lifecycles = [
            item
            for item in next_lifecycles
            if item.source_cursor.entity_index != start.source_entity_index
        ]
        next_lifecycles.append(lifecycle)
    return tuple(next_lifecycles)


def _async_start_sequence_is_feasible(
    path: SymbolicEventPath,
    existing: tuple[SymbolicAsyncMovementLifecycle, ...],
) -> bool:
    active_entities = {item.source_cursor.entity_index for item in existing}
    for start in path.async_movement_starts:
        if start.source_entity_index in active_entities:
            return False
        active_entities.add(start.source_entity_index)
    return True


def _temporal_boundary_matches_lifecycle_state(
    index: OrderedStageProgramIndex,
    program: OrderedEventProgram,
    *,
    source_entity_index: int,
    path: SymbolicEventPath,
    lifecycles: tuple[SymbolicAsyncMovementLifecycle, ...],
) -> bool:
    boundary_line = path.temporal_boundary_lines[0]
    boundary_offset = index.instruction_offset(program, boundary_line)
    if boundary_offset is None:
        return False
    boundary_state = path.temporal_boundary_states[0]
    has_active_movement = any(
        lifecycle.source_cursor.entity_index == source_entity_index
        for lifecycle in lifecycles
    )
    if boundary_state is SymbolicTemporalBoundaryState.PRIOR_MOVEMENT_ACTIVE:
        return has_active_movement
    action = program.event.actions[boundary_offset]
    if action.command in {
        SymbolicMovementCommand.GOTO_MARKER.value,
        SymbolicMovementCommand.FOLLOW_SPLINE.value,
    }:
        return not has_active_movement
    return True


def _path_frontier_offset(
    index: OrderedStageProgramIndex,
    program: OrderedEventProgram,
    path: SymbolicEventPath,
) -> int:
    frontier_line = path.blocker_line
    if frontier_line is None and path.temporal_boundary_lines:
        frontier_line = path.temporal_boundary_lines[-1]
    if frontier_line is None:
        raise RuntimeError("non-completing scheduler path has no source frontier")
    frontier_offset = index.instruction_offset(program, frontier_line)
    if frontier_offset is None:
        raise RuntimeError("scheduler path frontier does not identify one ordered instruction")
    return frontier_offset


def _tag_parent_wake_constraint(
    state: SymbolicScheduleState,
    *,
    caller_entity_index: int,
    target_entity_index: int,
) -> tuple[SymbolicWakeConstraint, str | None]:
    by_child = {item.child_entity_index: item for item in state.tag_parent_states}
    current = caller_entity_index
    visited: set[int] = set()
    while current not in visited:
        visited.add(current)
        caller_relation = by_child.get(current)
        if (
            caller_relation is None
            or caller_relation.disposition is SymbolicTagParentDisposition.UNKNOWN
        ):
            return SymbolicWakeConstraint.TAG_PARENT_ORDER_UNKNOWN, "caller_tag_parent_state_unknown"
        if caller_relation.disposition is SymbolicTagParentDisposition.PROVEN_UNATTACHED:
            break
        parent = caller_relation.parent_entity_index
        if parent is None:
            raise AssertionError("validated attached tag-parent state lost its parent")
        if parent == target_entity_index:
            return SymbolicWakeConstraint.NEXT_FRAME, None
        current = parent
    else:
        return SymbolicWakeConstraint.TAG_PARENT_ORDER_UNKNOWN, "tag_parent_cycle_not_modeled"

    target_relation = by_child.get(target_entity_index)
    if (
        target_relation is None
        or target_relation.disposition is SymbolicTagParentDisposition.UNKNOWN
    ):
        return SymbolicWakeConstraint.TAG_PARENT_ORDER_UNKNOWN, "tag_parent_state_unknown"
    if target_relation.disposition is SymbolicTagParentDisposition.ATTACHED:
        return SymbolicWakeConstraint.TAG_PARENT_ORDER_UNKNOWN, "tag_parent_order_not_modeled"
    if target_entity_index > caller_entity_index:
        return SymbolicWakeConstraint.SAME_FRAME_LATER, None
    return SymbolicWakeConstraint.NEXT_FRAME, None


def _suspended_boundary(
    index: OrderedStageProgramIndex,
    state: SymbolicScheduleState,
    *,
    target_frame: SymbolicFrame,
    caller_entity_index: int,
    temporal_state: SymbolicTemporalBoundaryState,
    boundary_line: int,
    effects: tuple[SymbolicEffectRecord, ...],
) -> tuple[SuspendedContinuation, str | None]:
    program = index.program(target_frame.cursor.node_id)
    boundary_offset = index.instruction_offset(program, boundary_line)
    if boundary_offset is None:
        raise RuntimeError("temporal boundary does not identify one ordered instruction")
    boundary_cursor = replace(target_frame.cursor, instruction_offset=boundary_offset)
    boundary_frame = replace(target_frame, cursor=boundary_cursor)
    instruction = program.instructions[boundary_offset]
    action = program.event.actions[boundary_offset]

    if isinstance(instruction, ControlBarrierInstruction):
        if instruction.action.command == "wait":
            boundary_state: SymbolicBoundaryState = SymbolicWaitBoundaryState(instruction.action.arguments)
            wake_constraint, wake_reason = _tag_parent_wake_constraint(
                state,
                caller_entity_index=caller_entity_index,
                target_entity_index=target_frame.cursor.entity_index,
            )
        else:
            boundary_state = SymbolicNextFrameBoundaryState(SymbolicNextFrameCommand(instruction.action.command))
            wake_constraint = SymbolicWakeConstraint.NEXT_FRAME
            wake_reason = None
    elif action.command in {command.value for command in SymbolicMovementCommand}:
        command = SymbolicMovementCommand(action.command)
        effect_started = temporal_state is not SymbolicTemporalBoundaryState.PRIOR_MOVEMENT_ACTIVE
        effect_record_index = None
        if command is SymbolicMovementCommand.GOTO_MARKER and effect_started:
            effect_record_index = next(
                (
                    offset
                    for offset in range(len(effects) - 1, -1, -1)
                    if effects[offset].source_cursor == boundary_cursor
                ),
                None,
            )
            if effect_record_index is None:
                raise RuntimeError("started gotomarker boundary lost its route-effect record")
        boundary_state = SymbolicMovementBoundaryState(
            command,
            action.arguments,
            temporal_state,
            _movement_action_waits_for_completion(action),
            effect_started,
            effect_record_index,
        )
        wake_constraint = SymbolicWakeConstraint.AFTER_BOUNDARY_COMPLETION
        wake_reason = None
    else:
        raise RuntimeError("temporal path does not stop on a supported boundary instruction")

    return (
        SuspendedContinuation(
            boundary_frame,
            boundary_line,
            SymbolicResumeMode.REENTER_BOUNDARY_ACTION,
            boundary_state,
            wake_constraint,
        ),
        wake_reason,
    )


def _dispatch_target(
    index: OrderedStageProgramIndex,
    caller_program: OrderedEventProgram,
    caller_cursor: SymbolicProgramCursor,
) -> tuple[str, tuple[int, ...]] | SymbolicDispatchResolution:
    instruction = caller_program.instructions[caller_cursor.instruction_offset]
    if isinstance(instruction, (TriggerInstruction, AccumulatorConditionalTrigger)):
        dispatch = resolve_symbolic_nested_dispatch(
            index,
            caller_program,
            instruction,
            source_entity_index=caller_cursor.entity_index,
        )
        if dispatch.resolution is not SymbolicDispatchResolution.RESOLVED:
            return dispatch.resolution
        if dispatch.target_node_id is None:
            raise RuntimeError("resolved scheduler dispatch lost its target program")
        return dispatch.target_node_id, dispatch.target_entity_indices
    if isinstance(instruction, StageEffectInstruction):
        dispatch_targets = tuple(
            target
            for target in instruction.alert_targets
            if target.disposition is AlertTargetDisposition.SCRIPT_EVENT_DISPATCH
            and target.event_handler_node_id
        )
        node_ids = {target.event_handler_node_id for target in dispatch_targets}
        if not dispatch_targets or len(node_ids) != 1:
            return SymbolicDispatchResolution.RUNTIME_DISPATCH
        target_node_id = next(iter(node_ids))
        if target_node_id is None:
            raise AssertionError("filtered alert dispatch lost its handler node")
        return target_node_id, tuple(target.entity_index for target in dispatch_targets)
    if isinstance(instruction, KillInstruction):
        dispatch_targets = tuple(
            target
            for target in instruction.targets
            if target.disposition is KillTargetDisposition.SCRIPT_MOVER_OPTIONAL_DEATH_EVENT
            and target.death_handler_node_id
        )
        if len(dispatch_targets) != 1:
            return SymbolicDispatchResolution.RUNTIME_DISPATCH
        target = dispatch_targets[0]
        if target.death_handler_node_id is None:
            raise AssertionError("filtered death dispatch lost its handler node")
        return target.death_handler_node_id, (target.entity_index,)
    return SymbolicDispatchResolution.RUNTIME_DISPATCH


def _dispatch_blocker_reason(instruction: object) -> str | None:
    if isinstance(instruction, TriggerInstruction):
        return "trigger_dispatch_not_modeled"
    if isinstance(instruction, AccumulatorConditionalTrigger):
        return "conditional_trigger_dispatch_not_modeled"
    if isinstance(instruction, StageEffectInstruction):
        if any(
            target.disposition is AlertTargetDisposition.SCRIPT_EVENT_DISPATCH
            for target in instruction.alert_targets
        ):
            return "alertentity_dispatch_not_modeled"
        return None
    if isinstance(instruction, KillInstruction):
        optional_targets = tuple(
            target.disposition is KillTargetDisposition.SCRIPT_MOVER_OPTIONAL_DEATH_EVENT
            for target in instruction.targets
        )
        if optional_targets.count(True) == 1:
            return "kill_death_dispatch_not_modeled"
        return None
    return None


def _continuation_belongs_to_dispatch(
    continuation: SuspendedContinuation,
    caller_frame: SymbolicFrame,
    dispatch: PendingDispatchContext,
) -> bool:
    pending = continuation.frame.pending_dispatch
    if pending is None or not continuation.frame.invocation_path:
        return False
    return (
        pending.dispatch_cursor == dispatch.dispatch_cursor
        and pending.caller_resume_cursor == dispatch.caller_resume_cursor
        and pending.target_node_id == dispatch.target_node_id
        and pending.ordered_target_entity_indices == dispatch.ordered_target_entity_indices
        and continuation.frame.invocation_path[:-1] == caller_frame.invocation_path
    )


def _mark_dispatch_continuations(
    suspended: tuple[SuspendedContinuation, ...],
    caller_frame: SymbolicFrame,
    dispatch: PendingDispatchContext,
    *,
    completed: bool = False,
    abandoned: bool = False,
) -> tuple[SuspendedContinuation, ...]:
    return tuple(
        replace(
            continuation,
            caller_suffix_completed=completed,
            caller_suffix_abandoned=abandoned,
        )
        if _continuation_belongs_to_dispatch(continuation, caller_frame, dispatch)
        else continuation
        for continuation in suspended
    )


def _mark_dispatch_stack(
    suspended: tuple[SuspendedContinuation, ...],
    caller_frame: SymbolicFrame,
    dispatches: tuple[PendingDispatchContext, ...],
    *,
    completed: bool = False,
    abandoned: bool = False,
) -> tuple[SuspendedContinuation, ...]:
    retained = suspended
    for dispatch in dispatches:
        retained = _mark_dispatch_continuations(
            retained,
            caller_frame,
            dispatch,
            completed=completed,
            abandoned=abandoned,
        )
    return retained


def _continue_caller_without_dispatch(
    index: OrderedStageProgramIndex,
    state: SymbolicScheduleState,
    caller_frame: SymbolicFrame,
    *,
    accumulator_state: SymbolicAccumulatorState,
    effects: tuple[SymbolicEffectRecord, ...],
    provenance: tuple[str, ...],
) -> SymbolicScheduleDecision:
    caller_program = index.program(caller_frame.cursor.node_id)
    resume_offset = caller_frame.cursor.instruction_offset + 1
    if resume_offset >= len(caller_program.instructions):
        retained = _mark_dispatch_stack(
            state.suspended,
            caller_frame,
            caller_frame.caller_dispatches,
            completed=True,
        )
        completed = _rebuild_schedule_state(
            index,
            state,
            accumulator_state=accumulator_state,
            runnable=(),
            suspended=retained,
            effects=effects,
            provenance=provenance,
            ordering_decisions=(
                state.ordering_decisions
                if not caller_frame.caller_dispatches
                else state.ordering_decisions + ("caller_suffix_completed_before_target_resume",)
            ),
        )
        kind = (
            SymbolicScheduleDecisionKind.SUSPENDED
            if completed.suspended
            else SymbolicScheduleDecisionKind.COMPLETE
        )
        return SymbolicScheduleDecision(kind, completed)
    suffix = replace(
        caller_frame,
        cursor=replace(caller_frame.cursor, instruction_offset=resume_offset),
        pending_dispatch=None,
        origin=SymbolicFrameOrigin.CALLER_SUFFIX,
    )
    next_state = _rebuild_schedule_state(
        index,
        state,
        accumulator_state=accumulator_state,
        runnable=(suffix,),
        effects=effects,
        provenance=provenance,
    )
    return SymbolicScheduleDecision(SymbolicScheduleDecisionKind.RUNNABLE, next_state)


def _finish_s3_target_group(
    index: OrderedStageProgramIndex,
    state: SymbolicScheduleState,
    caller_frame: SymbolicFrame,
    dispatch: PendingDispatchContext,
    *,
    accumulator_state: SymbolicAccumulatorState,
    suspended: tuple[SuspendedContinuation, ...],
    async_lifecycles: tuple[SymbolicAsyncMovementLifecycle, ...],
    effects: tuple[SymbolicEffectRecord, ...],
    caller_abandoned: bool,
    provenance: tuple[str, ...],
    ordering_decisions: tuple[str, ...],
    unknown_reasons: tuple[str, ...],
) -> SymbolicScheduleDecision:
    completed_dispatch = replace(
        dispatch,
        target_cursor=len(dispatch.ordered_target_entity_indices) - 1,
    )
    dispatch_stack = caller_frame.caller_dispatches + (completed_dispatch,)
    if caller_abandoned:
        retained = _mark_dispatch_stack(
            suspended,
            caller_frame,
            dispatch_stack,
            abandoned=True,
        )
        next_state = _rebuild_schedule_state(
            index,
            state,
            accumulator_state=accumulator_state,
            runnable=(),
            suspended=retained,
            async_lifecycles=async_lifecycles,
            effects=effects,
            provenance=provenance + ("same_entity_caller_abandoned",),
            ordering_decisions=ordering_decisions + ("remaining_targets_before_caller_abandonment",),
            unknown_reasons=unknown_reasons,
        )
        kind = SymbolicScheduleDecisionKind.SUSPENDED if retained else SymbolicScheduleDecisionKind.COMPLETE
        return SymbolicScheduleDecision(kind, next_state)

    caller_program = index.program(caller_frame.cursor.node_id)
    if completed_dispatch.caller_resume_cursor.instruction_offset >= len(caller_program.instructions):
        retained = _mark_dispatch_stack(
            suspended,
            caller_frame,
            dispatch_stack,
            completed=True,
        )
        next_state = _rebuild_schedule_state(
            index,
            state,
            accumulator_state=accumulator_state,
            runnable=(),
            suspended=retained,
            async_lifecycles=async_lifecycles,
            effects=effects,
            provenance=provenance + ("caller_suffix_completed",),
            ordering_decisions=ordering_decisions + ("caller_suffix_completed_before_target_resume",),
            unknown_reasons=unknown_reasons,
        )
        kind = SymbolicScheduleDecisionKind.SUSPENDED if retained else SymbolicScheduleDecisionKind.COMPLETE
        return SymbolicScheduleDecision(kind, next_state)

    caller_suffix = replace(
        caller_frame,
        cursor=completed_dispatch.caller_resume_cursor,
        pending_dispatch=None,
        caller_dispatches=caller_frame.caller_dispatches + (completed_dispatch,),
        origin=SymbolicFrameOrigin.CALLER_SUFFIX,
    )
    next_state = _rebuild_schedule_state(
        index,
        state,
        accumulator_state=accumulator_state,
        runnable=(caller_suffix,),
        suspended=suspended,
        async_lifecycles=async_lifecycles,
        effects=effects,
        provenance=provenance,
        ordering_decisions=ordering_decisions + ("target_group_completed_before_caller_suffix",),
        unknown_reasons=unknown_reasons,
    )
    return SymbolicScheduleDecision(SymbolicScheduleDecisionKind.RUNNABLE, next_state)


def _blocked_s3_target_frames(
    index: OrderedStageProgramIndex,
    caller_frame: SymbolicFrame,
    dispatch: PendingDispatchContext,
    *,
    target_cursor: int,
    blocker_line: int | None,
    blocker_entity_index: int | None,
    caller_abandoned: bool,
) -> tuple[tuple[SymbolicFrame, ...], bool]:
    target_program = index.program(dispatch.target_node_id)
    frames: list[SymbolicFrame] = []
    active_target_entity_index = dispatch.ordered_target_entity_indices[target_cursor]
    blocker_offset = (
        index.instruction_offset(target_program, blocker_line)
        if blocker_line is not None
        and blocker_entity_index == active_target_entity_index
        else None
    )
    blocker_identity_unresolved = blocker_offset is None
    for ordinal in range(target_cursor, len(dispatch.ordered_target_entity_indices)):
        pending = replace(dispatch, target_cursor=ordinal)
        entity_index = pending.ordered_target_entity_indices[ordinal]
        offset = 0
        if ordinal == target_cursor and blocker_offset is not None:
            offset = blocker_offset
        invocation = SymbolicInvocationStep(
            pending.dispatch_cursor,
            pending.target_node_id,
            ordinal,
        )
        frames.append(
            SymbolicFrame(
                SymbolicProgramCursor(pending.target_node_id, entity_index, offset),
                invocation_path=caller_frame.invocation_path + (invocation,),
                pending_dispatch=pending,
                origin=(
                    SymbolicFrameOrigin.EVENT_REPLACEMENT
                    if entity_index == caller_frame.cursor.entity_index
                    else (
                        SymbolicFrameOrigin.NESTED_DISPATCH
                        if ordinal == target_cursor
                        else SymbolicFrameOrigin.TARGET_GROUP_RESUME
                    )
                ),
            )
        )

    caller_program = index.program(caller_frame.cursor.node_id)
    resume = dispatch.caller_resume_cursor
    active_entities = {frame.cursor.entity_index for frame in frames}
    if (
        not caller_abandoned
        and resume.instruction_offset < len(caller_program.instructions)
        and resume.entity_index not in active_entities
    ):
        frames.append(
            replace(
                caller_frame,
                cursor=resume,
                pending_dispatch=None,
                origin=SymbolicFrameOrigin.CALLER_SUFFIX,
            )
        )
    return tuple(frames), blocker_identity_unresolved


def _run_s3_target_group(
    index: OrderedStageProgramIndex,
    state: SymbolicScheduleState,
    caller_frame: SymbolicFrame,
    dispatch: PendingDispatchContext,
    *,
    target_cursor: int,
    accumulator_state: SymbolicAccumulatorState,
    suspended: tuple[SuspendedContinuation, ...],
    async_lifecycles: tuple[SymbolicAsyncMovementLifecycle, ...],
    effects: tuple[SymbolicEffectRecord, ...],
    caller_abandoned: bool,
    provenance: tuple[str, ...],
    ordering_decisions: tuple[str, ...],
    unknown_reasons: tuple[str, ...],
) -> list[SymbolicScheduleDecision]:
    pending = replace(dispatch, target_cursor=target_cursor)
    target_entity_index = pending.ordered_target_entity_indices[target_cursor]
    target_program = index.program(pending.target_node_id)
    invocation = SymbolicInvocationStep(pending.dispatch_cursor, pending.target_node_id, target_cursor)
    same_entity = target_entity_index == caller_frame.cursor.entity_index
    target_frame = SymbolicFrame(
        SymbolicProgramCursor(pending.target_node_id, target_entity_index, 0),
        invocation_path=caller_frame.invocation_path + (invocation,),
        pending_dispatch=pending,
        origin=(
            SymbolicFrameOrigin.EVENT_REPLACEMENT
            if same_entity
            else SymbolicFrameOrigin.NESTED_DISPATCH
        ),
    )
    target_paths = walk_symbolic_stage_program(
        index,
        target_program,
        source_entity_index=target_entity_index,
        initial_state=accumulator_state,
        stop_at_temporal_boundary=True,
    )
    decisions: list[SymbolicScheduleDecision] = []
    existing_target = next(
        (item for item in suspended if item.frame.cursor.entity_index == target_entity_index),
        None,
    )
    without_existing = tuple(
        item for item in suspended if item.frame.cursor.entity_index != target_entity_index
    )
    last_target = target_cursor == len(pending.ordered_target_entity_indices) - 1

    for path in target_paths:
        if not _async_start_sequence_is_feasible(path, async_lifecycles):
            continue
        added_effects = _nested_path_effect_records(
            index,
            projections=path.effects,
            effect_entity_indices=path.effect_entity_indices,
        )
        next_effects = effects + added_effects
        next_lifecycles = _path_async_lifecycles(
            index,
            path=path,
            effects=next_effects,
            existing=async_lifecycles,
        )
        next_provenance = provenance + (f"dispatch_target_{target_cursor}_executed",)
        next_ordering = ordering_decisions + (f"dispatch_target_{target_cursor}_in_entity_order",)
        if path.completion in {
            SymbolicPathCompletion.SYNCHRONOUS_COMPLETE,
            SymbolicPathCompletion.ABORTED_BY_GUARD,
        }:
            next_suspended = suspended if existing_target is not None else without_existing
            if last_target:
                decisions.append(
                    _finish_s3_target_group(
                        index,
                        state,
                        caller_frame,
                        pending,
                        accumulator_state=path.state,
                        suspended=next_suspended,
                        async_lifecycles=next_lifecycles,
                        effects=next_effects,
                        caller_abandoned=caller_abandoned,
                        provenance=next_provenance + ("synchronous_target_state_returned",),
                        ordering_decisions=next_ordering,
                        unknown_reasons=unknown_reasons,
                    )
                )
            else:
                decisions.extend(
                    _run_s3_target_group(
                        index,
                        state,
                        caller_frame,
                        dispatch,
                        target_cursor=target_cursor + 1,
                        accumulator_state=path.state,
                        suspended=next_suspended,
                        async_lifecycles=next_lifecycles,
                        effects=next_effects,
                        caller_abandoned=caller_abandoned,
                        provenance=next_provenance + ("synchronous_target_state_returned",),
                        ordering_decisions=next_ordering,
                        unknown_reasons=unknown_reasons,
                    )
                )
            continue

        if path.completion is SymbolicPathCompletion.TEMPORALLY_SUSPENDED:
            direct_boundary = (
                len(path.temporal_boundary_lines) == 1
                and len(path.temporal_boundary_states) == 1
                and path.temporal_boundary_entity_indices == (target_entity_index,)
                and index.instruction_offset(target_program, path.temporal_boundary_lines[0]) is not None
                and not path.caller_replacement_lines
            )
            if direct_boundary:
                if not _temporal_boundary_matches_lifecycle_state(
                    index,
                    target_program,
                    source_entity_index=target_entity_index,
                    path=path,
                    lifecycles=next_lifecycles,
                ):
                    continue
                continuation, wake_reason = _suspended_boundary(
                    index,
                    state,
                    target_frame=target_frame,
                    caller_entity_index=caller_frame.cursor.entity_index,
                    temporal_state=path.temporal_boundary_states[0],
                    boundary_line=path.temporal_boundary_lines[0],
                    effects=next_effects,
                )
                if same_entity:
                    continuation = replace(continuation, caller_suffix_abandoned=True)
                next_suspended = without_existing + (continuation,)
                next_unknowns = (
                    unknown_reasons
                    if wake_reason is None
                    else unknown_reasons + (wake_reason,)
                )
                if last_target:
                    decisions.append(
                        _finish_s3_target_group(
                            index,
                            state,
                            caller_frame,
                            pending,
                            accumulator_state=path.state,
                            suspended=next_suspended,
                            async_lifecycles=next_lifecycles,
                            effects=next_effects,
                            caller_abandoned=caller_abandoned or same_entity,
                            provenance=next_provenance + ("dispatch_target_suspended",),
                            ordering_decisions=next_ordering,
                            unknown_reasons=next_unknowns,
                        )
                    )
                else:
                    decisions.extend(
                        _run_s3_target_group(
                            index,
                            state,
                            caller_frame,
                            dispatch,
                            target_cursor=target_cursor + 1,
                            accumulator_state=path.state,
                            suspended=next_suspended,
                            async_lifecycles=next_lifecycles,
                            effects=next_effects,
                            caller_abandoned=caller_abandoned or same_entity,
                            provenance=next_provenance + ("dispatch_target_suspended",),
                            ordering_decisions=next_ordering,
                            unknown_reasons=next_unknowns,
                        )
                    )
                continue

        reason = path.blocker_reason or "s3_nested_temporal_replacement_not_modeled"
        retained = without_existing
        frontier_frames, blocker_identity_unresolved = _blocked_s3_target_frames(
            index,
            caller_frame,
            dispatch,
            target_cursor=target_cursor,
            blocker_line=path.blocker_line,
            blocker_entity_index=path.blocker_entity_index,
            caller_abandoned=caller_abandoned or same_entity,
        )
        next_unknown_reasons = unknown_reasons + (reason,)
        if blocker_identity_unresolved:
            next_unknown_reasons += ("s3_blocker_frontier_identity_unresolved",)
        blocked = _rebuild_schedule_state(
            index,
            state,
            accumulator_state=path.state,
            runnable=frontier_frames,
            suspended=retained,
            async_lifecycles=next_lifecycles,
            effects=next_effects,
            provenance=next_provenance,
            ordering_decisions=next_ordering,
            unknown_reasons=next_unknown_reasons,
        )
        decisions.append(SymbolicScheduleDecision(SymbolicScheduleDecisionKind.BLOCKED, blocked, reason))
    return decisions


def _start_s3_dispatch(
    index: OrderedStageProgramIndex,
    state: SymbolicScheduleState,
    caller_frame: SymbolicFrame,
) -> SymbolicScheduleResult:
    caller_cursor = caller_frame.cursor
    caller_program = index.program(caller_cursor.node_id)
    instruction = caller_program.instructions[caller_cursor.instruction_offset]
    expected_blocker = _dispatch_blocker_reason(instruction)
    if expected_blocker is None:
        return _blocked_transition(index, state, "s3_runnable_frame_is_not_a_dispatch")

    caller_resume_offset = caller_cursor.instruction_offset + 1
    segment = replace(caller_program, instructions=(instruction,))
    entry_paths = walk_symbolic_event_program(
        segment,
        source_entity_index=caller_cursor.entity_index,
        initial_state=state.accumulator_state,
        stop_at_temporal_boundary=True,
    )
    decisions: list[SymbolicScheduleDecision] = []
    for path in entry_paths:
        added_effects = _path_effect_records(
            caller_program,
            instruction_offset=caller_cursor.instruction_offset,
            source_entity_index=caller_cursor.entity_index,
            projections=path.effects,
            effect_entity_indices=path.effect_entity_indices,
        )
        effects = state.effects + added_effects
        is_dispatch = (
            path.completion is SymbolicPathCompletion.BLOCKED
            and path.blocker_reason == expected_blocker
            and path.blocker_line
            == caller_program.event.actions[caller_cursor.instruction_offset].line
        )
        if is_dispatch:
            if isinstance(instruction, KillInstruction):
                decisions.append(
                    _continue_caller_without_dispatch(
                        index,
                        state,
                        caller_frame,
                        accumulator_state=path.state,
                        effects=effects,
                        provenance=state.provenance
                        + ("optional_death_dispatch_not_delivered",),
                    )
                )
            target = _dispatch_target(index, caller_program, caller_cursor)
            if target is SymbolicDispatchResolution.NO_OP:
                decisions.append(
                    _continue_caller_without_dispatch(
                        index,
                        state,
                        caller_frame,
                        accumulator_state=path.state,
                        effects=effects,
                        provenance=state.provenance + ("dispatch_resolved_no_op",),
                    )
                )
                continue
            if isinstance(target, SymbolicDispatchResolution):
                reason = f"s3_nested_dispatch_{target.value}"
                blocked = _rebuild_schedule_state(
                    index,
                    state,
                    accumulator_state=path.state,
                    effects=effects,
                    unknown_reasons=state.unknown_reasons + (reason,),
                )
                decisions.append(
                    SymbolicScheduleDecision(SymbolicScheduleDecisionKind.BLOCKED, blocked, reason)
                )
                continue
            target_node_id, target_entities = target
            if not target_entities:
                reason = "s3_dispatch_has_no_concrete_targets"
                blocked = _rebuild_schedule_state(
                    index,
                    state,
                    accumulator_state=path.state,
                    effects=effects,
                    unknown_reasons=state.unknown_reasons + (reason,),
                )
                decisions.append(
                    SymbolicScheduleDecision(SymbolicScheduleDecisionKind.BLOCKED, blocked, reason)
                )
                continue
            pending = PendingDispatchContext(
                caller_cursor,
                SymbolicProgramCursor(
                    caller_cursor.node_id,
                    caller_cursor.entity_index,
                    caller_resume_offset,
                ),
                target_node_id,
                target_entities,
                0,
            )
            decisions.extend(
                _run_s3_target_group(
                    index,
                    state,
                    caller_frame,
                    pending,
                    target_cursor=0,
                    accumulator_state=path.state,
                    suspended=state.suspended,
                    async_lifecycles=state.async_lifecycles,
                    effects=effects,
                    caller_abandoned=False,
                    provenance=state.provenance + ("dispatch_group_started",),
                    ordering_decisions=state.ordering_decisions,
                    unknown_reasons=state.unknown_reasons,
                )
            )
            continue
        if path.completion in {
            SymbolicPathCompletion.SYNCHRONOUS_COMPLETE,
            SymbolicPathCompletion.ABORTED_BY_GUARD,
        }:
            decisions.append(
                _continue_caller_without_dispatch(
                    index,
                    state,
                    caller_frame,
                    accumulator_state=path.state,
                    effects=effects,
                    provenance=state.provenance + ("conditional_dispatch_not_taken",),
                )
            )
            continue
        reason = path.blocker_reason or "s3_dispatch_entry_not_modeled"
        blocked = _rebuild_schedule_state(
            index,
            state,
            accumulator_state=path.state,
            effects=effects,
            unknown_reasons=state.unknown_reasons + (reason,),
        )
        decisions.append(SymbolicScheduleDecision(SymbolicScheduleDecisionKind.BLOCKED, blocked, reason))
    return SymbolicScheduleResult(tuple(decisions), 1, 1)


def _complete_s3_caller_suffix(
    index: OrderedStageProgramIndex,
    state: SymbolicScheduleState,
    caller_frame: SymbolicFrame,
) -> SymbolicScheduleResult:
    dispatches = caller_frame.caller_dispatches
    group_continuations = tuple(
        continuation
        for continuation in state.suspended
        if any(
            _continuation_belongs_to_dispatch(continuation, caller_frame, dispatch)
            for dispatch in dispatches
        )
    )
    if any(
        continuation.caller_suffix_completed or continuation.caller_suffix_abandoned
        for continuation in group_continuations
    ):
        return _blocked_transition(index, state, "s3_caller_suffix_already_disposed")

    caller_program = index.program(caller_frame.cursor.node_id)
    next_dispatch_offset = next(
        (
            offset
            for offset in range(caller_frame.cursor.instruction_offset, len(caller_program.instructions))
            if _dispatch_blocker_reason(caller_program.instructions[offset]) is not None
        ),
        None,
    )
    segment_end = len(caller_program.instructions) if next_dispatch_offset is None else next_dispatch_offset
    segment = replace(
        caller_program,
        instructions=caller_program.instructions[caller_frame.cursor.instruction_offset:segment_end],
    )
    paths = walk_symbolic_event_program(
        segment,
        source_entity_index=caller_frame.cursor.entity_index,
        initial_state=state.accumulator_state,
        stop_at_temporal_boundary=True,
    )
    decisions: list[SymbolicScheduleDecision] = []
    for path in paths:
        if not _async_start_sequence_is_feasible(path, state.async_lifecycles):
            continue
        if path.completion not in {
            SymbolicPathCompletion.SYNCHRONOUS_COMPLETE,
            SymbolicPathCompletion.ABORTED_BY_GUARD,
        }:
            reason = path.blocker_reason or "s3_caller_suffix_temporal_interleaving_deferred_to_s4"
            added_effects = _nested_path_effect_records(
                index,
                projections=path.effects,
                effect_entity_indices=path.effect_entity_indices,
            )
            next_effects = state.effects + added_effects
            next_lifecycles = _path_async_lifecycles(
                index,
                path=path,
                effects=next_effects,
                existing=state.async_lifecycles,
            )
            frontier_offset = (
                index.instruction_offset(caller_program, path.blocker_line)
                if path.blocker_line is not None
                and path.blocker_entity_index == caller_frame.cursor.entity_index
                else None
            )
            if frontier_offset is None and path.temporal_boundary_lines:
                frontier_offset = index.instruction_offset(
                    caller_program,
                    path.temporal_boundary_lines[-1],
                )
            frontier_frame = replace(
                caller_frame,
                cursor=replace(
                    caller_frame.cursor,
                    instruction_offset=(
                        caller_frame.cursor.instruction_offset
                        if frontier_offset is None
                        else frontier_offset
                    ),
                ),
            )
            blocked = _rebuild_schedule_state(
                index,
                state,
                accumulator_state=path.state,
                runnable=(frontier_frame,),
                async_lifecycles=next_lifecycles,
                effects=next_effects,
                unknown_reasons=state.unknown_reasons + (reason,),
            )
            decisions.append(SymbolicScheduleDecision(SymbolicScheduleDecisionKind.BLOCKED, blocked, reason))
            continue
        added_effects = _nested_path_effect_records(
            index,
            projections=path.effects,
            effect_entity_indices=path.effect_entity_indices,
        )
        next_effects = state.effects + added_effects
        next_lifecycles = _path_async_lifecycles(
            index,
            path=path,
            effects=next_effects,
            existing=state.async_lifecycles,
        )
        if (
            path.completion is SymbolicPathCompletion.SYNCHRONOUS_COMPLETE
            and next_dispatch_offset is not None
        ):
            dispatch_frame = replace(
                caller_frame,
                cursor=replace(caller_frame.cursor, instruction_offset=next_dispatch_offset),
            )
            next_state = _rebuild_schedule_state(
                index,
                state,
                accumulator_state=path.state,
                runnable=(dispatch_frame,),
                async_lifecycles=next_lifecycles,
                effects=next_effects,
                provenance=state.provenance + ("caller_suffix_reached_nested_dispatch",),
            )
            decisions.append(SymbolicScheduleDecision(SymbolicScheduleDecisionKind.RUNNABLE, next_state))
            continue
        completed_suspended = (
            state.suspended
            if not dispatches
            else _mark_dispatch_stack(
                state.suspended,
                caller_frame,
                dispatches,
                completed=True,
            )
        )
        next_state = _rebuild_schedule_state(
            index,
            state,
            accumulator_state=path.state,
            runnable=(),
            suspended=completed_suspended,
            async_lifecycles=next_lifecycles,
            effects=next_effects,
            provenance=state.provenance + ("caller_suffix_completed",),
            ordering_decisions=state.ordering_decisions + ("caller_suffix_completed_before_target_resume",),
        )
        kind = (
            SymbolicScheduleDecisionKind.SUSPENDED
            if next_state.suspended
            else SymbolicScheduleDecisionKind.COMPLETE
        )
        decisions.append(SymbolicScheduleDecision(kind, next_state))
    return SymbolicScheduleResult(tuple(decisions), 1, 1)


def _resume_s3_continuation(
    index: OrderedStageProgramIndex,
    state: SymbolicScheduleState,
    continuation: SuspendedContinuation,
) -> SymbolicScheduleResult:
    if continuation.frame.pending_dispatch is None or not (
        continuation.caller_suffix_completed or continuation.caller_suffix_abandoned
    ):
        return _blocked_transition(index, state, "s2_target_resume_before_caller_suffix")
    ordering_reason = (
        "target_reentered_after_caller_abandonment"
        if continuation.caller_suffix_abandoned
        else "target_reentered_after_caller_suffix"
    )
    if continuation.wake_constraint is SymbolicWakeConstraint.TAG_PARENT_ORDER_UNKNOWN:
        return _blocked_transition(index, state, "wake_semantics_unverified")
    if isinstance(continuation.boundary_state, SymbolicWaitBoundaryState):
        if continuation.wake_constraint is SymbolicWakeConstraint.SAME_FRAME_LATER:
            delayed = replace(
                continuation,
                wake_constraint=SymbolicWakeConstraint.NEXT_FRAME,
            )
            next_state = _rebuild_schedule_state(
                index,
                state,
                suspended=(delayed,),
                provenance=state.provenance + ("boundary_action_reentered_same_frame",),
                ordering_decisions=state.ordering_decisions + (ordering_reason,),
            )
            return SymbolicScheduleResult(
                (SymbolicScheduleDecision(SymbolicScheduleDecisionKind.SUSPENDED, next_state),),
                1,
                1,
            )
        return _blocked_transition(index, state, "wait_completion_time_unverified")
    if not isinstance(continuation.boundary_state, SymbolicNextFrameBoundaryState):
        return _blocked_transition(index, state, "movement_completion_time_unverified")

    frame = continuation.frame
    suffix_offset = frame.cursor.instruction_offset + 1
    program = index.program(frame.cursor.node_id)
    if suffix_offset >= len(program.instructions):
        completed = _rebuild_schedule_state(
            index,
            state,
            runnable=(),
            suspended=(),
            provenance=state.provenance + ("target_boundary_reentered",),
            ordering_decisions=state.ordering_decisions + (ordering_reason,),
        )
        return SymbolicScheduleResult(
            (SymbolicScheduleDecision(SymbolicScheduleDecisionKind.COMPLETE, completed),),
            1,
            1,
        )

    suffix_frame = replace(
        frame,
        cursor=replace(frame.cursor, instruction_offset=suffix_offset),
        origin=SymbolicFrameOrigin.BOUNDARY_RESUME,
    )
    paths = walk_symbolic_event_program(
        _program_suffix(program, suffix_offset),
        source_entity_index=frame.cursor.entity_index,
        initial_state=state.accumulator_state,
        stop_at_temporal_boundary=True,
    )
    decisions: list[SymbolicScheduleDecision] = []
    for path in paths:
        if not _async_start_sequence_is_feasible(path, state.async_lifecycles):
            continue
        if path.completion not in {
            SymbolicPathCompletion.SYNCHRONOUS_COMPLETE,
            SymbolicPathCompletion.ABORTED_BY_GUARD,
        }:
            reason = path.blocker_reason or "s2_resumed_target_suffix_is_not_synchronously_complete"
            added_effects = _path_effect_records(
                program,
                instruction_offset=suffix_offset,
                source_entity_index=suffix_frame.cursor.entity_index,
                projections=path.effects,
                effect_entity_indices=path.effect_entity_indices,
            )
            next_effects = state.effects + added_effects
            next_lifecycles = _path_async_lifecycles(
                index,
                path=path,
                effects=next_effects,
                existing=state.async_lifecycles,
            )
            frontier_frame = replace(
                suffix_frame,
                cursor=replace(
                    suffix_frame.cursor,
                    instruction_offset=_path_frontier_offset(index, program, path),
                ),
            )
            blocked = _rebuild_schedule_state(
                index,
                state,
                accumulator_state=path.state,
                runnable=(frontier_frame,),
                suspended=(),
                async_lifecycles=next_lifecycles,
                effects=next_effects,
                provenance=state.provenance + ("target_boundary_reentered",),
                ordering_decisions=state.ordering_decisions + (ordering_reason,),
                unknown_reasons=state.unknown_reasons + (reason,),
            )
            decisions.append(SymbolicScheduleDecision(SymbolicScheduleDecisionKind.BLOCKED, blocked, reason))
            continue
        added_effects = _path_effect_records(
            program,
            instruction_offset=suffix_offset,
            source_entity_index=suffix_frame.cursor.entity_index,
            projections=path.effects,
            effect_entity_indices=path.effect_entity_indices,
        )
        next_effects = state.effects + added_effects
        next_lifecycles = _path_async_lifecycles(
            index,
            path=path,
            effects=next_effects,
            existing=state.async_lifecycles,
        )
        completed = _rebuild_schedule_state(
            index,
            state,
            accumulator_state=path.state,
            runnable=(),
            suspended=(),
            async_lifecycles=next_lifecycles,
            effects=next_effects,
            provenance=state.provenance + ("target_boundary_reentered", "target_suffix_completed"),
            ordering_decisions=state.ordering_decisions + (ordering_reason,),
        )
        decisions.append(SymbolicScheduleDecision(SymbolicScheduleDecisionKind.COMPLETE, completed))
    return SymbolicScheduleResult(tuple(decisions), 1, 1)


def step_symbolic_schedule(
    index: OrderedStageProgramIndex,
    state: SymbolicScheduleState,
) -> SymbolicScheduleResult:
    """Execute one source-ordered S3 scheduler transition.

    S3 adds exact synchronous nested-state return, concrete shared-target iteration
    and same-entity replacement. Multi-task wake selection and bounded search remain
    explicit S4 frontiers.
    """

    _state_for_index(index, state)
    if len(state.runnable) > 1:
        return _blocked_transition(index, state, "s2_multiple_runnable_frames_deferred_to_s4")
    if state.runnable:
        frame = state.runnable[0]
        instruction = index.program(frame.cursor.node_id).instructions[frame.cursor.instruction_offset]
        if _dispatch_blocker_reason(instruction) is not None:
            return _start_s3_dispatch(index, state, frame)
        if frame.origin is SymbolicFrameOrigin.CALLER_SUFFIX:
            return _complete_s3_caller_suffix(index, state, frame)
        return _blocked_transition(index, state, "s3_runnable_transition_not_modeled")
    if len(state.suspended) == 1:
        return _resume_s3_continuation(index, state, state.suspended[0])
    if not state.suspended:
        return SymbolicScheduleResult(
            (SymbolicScheduleDecision(SymbolicScheduleDecisionKind.COMPLETE, state),),
            0,
            1,
        )
    return _blocked_transition(index, state, "s3_multiple_suspended_frames_deferred_to_s4")
