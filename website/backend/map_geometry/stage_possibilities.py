"""Ordered W5b control-program projection and fail-closed symbolic paths.

The game runner evaluates event actions in source order. This module preserves that
order, classifies only source-verified control families and walks accumulator guards
without guessing nested dispatch. Runtime actions outside the approved subset remain
explicit blockers; they are not assumed to be harmless or executable.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
from enum import StrEnum
from functools import cache
from types import MappingProxyType
from typing import Mapping, TypeAlias

from website.backend.map_geometry.stage import (
    STAGE_EFFECT_COMMANDS,
    ScriptAction,
    ScriptEvent,
    StageEventNode,
    StaticStageModel,
    TriggerDispatch,
    TriggerEdge,
    TriggerResolution,
)
from website.backend.map_geometry.stage_semantics import (
    MAX_SIGNED_ACCUMULATOR_BIT_INDEX,
    AccumulatorAbortGuard,
    AccumulatorConditionalTrigger,
    AccumulatorMutation,
    AccumulatorOperation,
    AccumulatorScope,
    ControlProjectionIssue,
    EffectSourceIdentity,
    EntityIdentityNamespace,
    StageEffectProjection,
    W3LinkedIdentityIndex,
    project_accumulator_action,
    project_stage_effect,
)


class ControlBarrierKind(StrEnum):
    WAIT = "wait"
    RESET_SCRIPT = "resetscript"
    HALT = "halt"


class RuntimeActionControlDisposition(StrEnum):
    IMMEDIATE_CURRENT_EVENT_CONTINUE = "immediate_current_event_continue"
    CONDITIONAL_TEMPORAL_PAUSE = "conditional_temporal_pause"
    DEFERRED_SOURCE_REMOVAL = "deferred_source_removal"
    MAY_DISPATCH_DEATH_EVENT = "may_dispatch_death_event"
    MAY_REPLACE_SCRIPT_CONTEXT = "may_replace_script_context"
    MAY_STOP_ON_SPAWN_FAILURE = "may_stop_on_spawn_failure"
    UNCLASSIFIED = "unclassified"


class SymbolicPathCompletion(StrEnum):
    SYNCHRONOUS_COMPLETE = "synchronous_complete"
    EVENTUAL_COMPLETE = "eventual_complete"
    TEMPORALLY_SUSPENDED = "temporally_suspended"
    ABORTED_BY_GUARD = "aborted_by_guard"
    BLOCKED = "blocked"


class SymbolicDispatchResolution(StrEnum):
    RESOLVED = "resolved"
    MISSING_HANDLER = "missing_handler"
    OPAQUE_HANDLER = "opaque_handler"
    RUNTIME_DISPATCH = "runtime_dispatch"
    NO_OP = "no_op"
    TARGET_IDENTITY_MISSING = "target_identity_missing"


_IMMEDIATE_RUNTIME_ACTIONS = frozenset(
    {
        "attachtotag",
        "changemodel",
        "constructible_chargebarreq",
        "constructible_class",
        "constructible_constructxpbonus",
        "constructible_destructxpbonus",
        "constructible_duration",
        "constructible_health",
        "constructible_weaponclass",
        "disablespeaker",
        "enablespeaker",
        "playsound",
        "remapshader",
        "remapshaderflush",
        "repairmg42",
        "setchargetimefactor",
        "sethqstatus",
        "setrotation",
        "setspeed",
        "startanimation",
        "stoprotation",
        "stopsound",
        "togglespeaker",
        "wm_addteamvoiceannounce",
        "wm_allied_respawntime",
        "wm_announce",
        "wm_axis_respawntime",
        "wm_number_of_objectives",
        "wm_removeteamvoiceannounce",
        "wm_set_defending_team",
        "wm_set_round_timelimit",
        "wm_teamvoiceannounce",
    }
)
_SPECIAL_RUNTIME_ACTIONS = {
    "create": RuntimeActionControlDisposition.MAY_STOP_ON_SPAWN_FAILURE,
    "faceangles": RuntimeActionControlDisposition.CONDITIONAL_TEMPORAL_PAUSE,
    "followspline": RuntimeActionControlDisposition.CONDITIONAL_TEMPORAL_PAUSE,
    "kill": RuntimeActionControlDisposition.MAY_DISPATCH_DEATH_EVENT,
    "remove": RuntimeActionControlDisposition.DEFERRED_SOURCE_REMOVAL,
}
_ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


def _ascii_fold(value: str) -> str:
    return value.translate(_ASCII_LOWER)


def _set_may_dispatch_spawn(action: ScriptAction) -> bool:
    # etpro_ScriptAction_SetValues calls G_CallSpawn only for a changed
    # ``classname`` key. Any ``classname_nospawn`` pair latches suppression
    # for the complete callback, including another classname pair.
    keys = {_ascii_fold(action.arguments[index]) for index in range(0, len(action.arguments), 2)}
    return "classname" in keys and "classname_nospawn" not in keys


def _followspline_has_wait(action: ScriptAction) -> bool:
    return any(_ascii_fold(argument) == "wait" for argument in action.arguments)


def runtime_action_control_disposition(action: ScriptAction) -> RuntimeActionControlDisposition:
    """Return only source-verified current-event control behavior."""

    if action.command in _IMMEDIATE_RUNTIME_ACTIONS:
        return RuntimeActionControlDisposition.IMMEDIATE_CURRENT_EVENT_CONTINUE
    if action.command == "set":
        if _set_may_dispatch_spawn(action):
            return RuntimeActionControlDisposition.MAY_REPLACE_SCRIPT_CONTEXT
        return RuntimeActionControlDisposition.IMMEDIATE_CURRENT_EVENT_CONTINUE
    return _SPECIAL_RUNTIME_ACTIONS.get(action.command, RuntimeActionControlDisposition.UNCLASSIFIED)


@dataclass(frozen=True, slots=True)
class StageEffectInstruction:
    projection: StageEffectProjection


@dataclass(frozen=True, slots=True)
class TriggerInstruction:
    edge: TriggerEdge


@dataclass(frozen=True, slots=True)
class ControlBarrierInstruction:
    kind: ControlBarrierKind
    action: ScriptAction


@dataclass(frozen=True, slots=True)
class RuntimeActionInstruction:
    action: ScriptAction
    control_disposition: RuntimeActionControlDisposition

    @property
    def blocker_reason(self) -> str | None:
        if self.control_disposition in {
            RuntimeActionControlDisposition.IMMEDIATE_CURRENT_EVENT_CONTINUE,
            RuntimeActionControlDisposition.DEFERRED_SOURCE_REMOVAL,
        }:
            return None
        return self.control_disposition.value


OrderedEventInstruction: TypeAlias = (
    AccumulatorMutation
    | AccumulatorAbortGuard
    | AccumulatorConditionalTrigger
    | ControlProjectionIssue
    | StageEffectInstruction
    | TriggerInstruction
    | ControlBarrierInstruction
    | RuntimeActionInstruction
)


@dataclass(frozen=True, slots=True)
class OrderedEventProgram:
    node: StageEventNode
    event: ScriptEvent
    source: EffectSourceIdentity
    instructions: tuple[OrderedEventInstruction, ...]


@dataclass(frozen=True, slots=True)
class OrderedStageProgramIndex:
    programs: tuple[OrderedEventProgram, ...]
    opaque_script_names: frozenset[str]
    _programs_by_node_id: Mapping[str, OrderedEventProgram] = field(repr=False, compare=False)
    _trigger_handlers_by_script: Mapping[str, tuple[OrderedEventProgram, ...]] = field(repr=False, compare=False)

    def program(self, node_id: str) -> OrderedEventProgram:
        try:
            return self._programs_by_node_id[node_id]
        except KeyError as exc:
            raise ValueError(f"stage node {node_id!r} does not map to an ordered program") from exc

    def first_trigger_handler(self, script_name: str, trigger_name: str) -> OrderedEventProgram | None:
        folded_script = _ascii_fold(script_name)
        folded_trigger = _ascii_fold(trigger_name)
        return next(
            (
                program
                for program in self._trigger_handlers_by_script.get(folded_script, ())
                if (
                    not program.node.serialized_event_parameters
                    or _ascii_fold(program.node.serialized_event_parameters) == folded_trigger
                )
            ),
            None,
        )

    def has_opaque_script(self, script_name: str) -> bool:
        return _ascii_fold(script_name) in self.opaque_script_names


@dataclass(frozen=True, slots=True)
class SymbolicDispatchProjection:
    source_node_id: str
    source_entity_index: int
    target_script_name: str
    target_trigger: str
    dispatch: TriggerDispatch
    resolution: SymbolicDispatchResolution
    target_node_id: str | None
    target_entity_indices: tuple[int, ...]
    line: int
    reason: str | None = None


def _unresolved_dispatch(
    program: OrderedEventProgram,
    *,
    source_entity_index: int,
    target_script_name: str,
    target_trigger: str,
    dispatch: TriggerDispatch,
    resolution: SymbolicDispatchResolution,
    line: int,
    reason: str,
) -> SymbolicDispatchProjection:
    return SymbolicDispatchProjection(
        program.node.node_id,
        source_entity_index,
        target_script_name,
        target_trigger,
        dispatch,
        resolution,
        None,
        (),
        line,
        reason,
    )


def _resolved_dispatch(
    program: OrderedEventProgram,
    target: OrderedEventProgram,
    *,
    source_entity_index: int,
    target_script_name: str,
    target_trigger: str,
    dispatch: TriggerDispatch,
    target_entity_indices: tuple[int, ...],
    line: int,
) -> SymbolicDispatchProjection:
    if not target_entity_indices:
        return SymbolicDispatchProjection(
            program.node.node_id,
            source_entity_index,
            target_script_name,
            target_trigger,
            dispatch,
            SymbolicDispatchResolution.TARGET_IDENTITY_MISSING,
            target.node.node_id,
            (),
            line,
            "nested trigger handler has no concrete static entity identity",
        )
    return SymbolicDispatchProjection(
        program.node.node_id,
        source_entity_index,
        target_script_name,
        target_trigger,
        dispatch,
        SymbolicDispatchResolution.RESOLVED,
        target.node.node_id,
        target_entity_indices,
        line,
    )


def resolve_symbolic_nested_dispatch(
    index: OrderedStageProgramIndex,
    program: OrderedEventProgram,
    instruction: TriggerInstruction | AccumulatorConditionalTrigger,
    *,
    source_entity_index: int,
) -> SymbolicDispatchProjection:
    """Resolve one nested callback to concrete static entity candidates."""

    if index.program(program.node.node_id) is not program:
        raise ValueError(f"source program {program.node.node_id!r} does not belong to this ordered-program index")
    if not any(candidate is instruction for candidate in program.instructions):
        raise ValueError(f"nested instruction does not belong to source program {program.node.node_id!r}")
    if source_entity_index not in program.source.lookup.selected_entity_indices:
        raise ValueError(f"entity {source_entity_index} is not selected by script block {program.node.entity_name!r}")

    if isinstance(instruction, AccumulatorConditionalTrigger):
        target_script_name = instruction.target_script_name
        target_trigger = instruction.target_trigger
        dispatch = TriggerDispatch.SCRIPT_NAME
        line = instruction.line
        target = index.first_trigger_handler(target_script_name, target_trigger)
        if target is None:
            opaque = index.has_opaque_script(target_script_name)
            return _unresolved_dispatch(
                program,
                source_entity_index=source_entity_index,
                target_script_name=target_script_name,
                target_trigger=target_trigger,
                dispatch=dispatch,
                resolution=(
                    SymbolicDispatchResolution.OPAQUE_HANDLER if opaque else SymbolicDispatchResolution.MISSING_HANDLER
                ),
                line=line,
                reason=(
                    "conditional trigger target is hidden by an opaque script block"
                    if opaque
                    else "conditional trigger target has no matching handler"
                ),
            )
        return _resolved_dispatch(
            program,
            target,
            source_entity_index=source_entity_index,
            target_script_name=target_script_name,
            target_trigger=target_trigger,
            dispatch=dispatch,
            target_entity_indices=target.source.lookup.selected_entity_indices,
            line=line,
        )

    edge = instruction.edge
    if edge.resolution is TriggerResolution.NO_OP:
        return _unresolved_dispatch(
            program,
            source_entity_index=source_entity_index,
            target_script_name=edge.target_entity,
            target_trigger=edge.target_trigger,
            dispatch=edge.dispatch,
            resolution=SymbolicDispatchResolution.NO_OP,
            line=edge.line,
            reason="engine callback performs no nested dispatch for this target kind",
        )
    if edge.resolution is TriggerResolution.RUNTIME_DISPATCH:
        return _unresolved_dispatch(
            program,
            source_entity_index=source_entity_index,
            target_script_name=edge.target_entity,
            target_trigger=edge.target_trigger,
            dispatch=edge.dispatch,
            resolution=SymbolicDispatchResolution.RUNTIME_DISPATCH,
            line=edge.line,
            reason="nested target set depends on runtime entities",
        )
    if edge.resolution is not TriggerResolution.RESOLVED or len(edge.candidate_node_ids) != 1:
        opaque = edge.resolution is TriggerResolution.OPAQUE
        return _unresolved_dispatch(
            program,
            source_entity_index=source_entity_index,
            target_script_name=edge.target_entity,
            target_trigger=edge.target_trigger,
            dispatch=edge.dispatch,
            resolution=(
                SymbolicDispatchResolution.OPAQUE_HANDLER if opaque else SymbolicDispatchResolution.MISSING_HANDLER
            ),
            line=edge.line,
            reason=(
                "plain trigger target is hidden by an opaque script block"
                if opaque
                else f"plain trigger handler is not uniquely resolved: {edge.resolution.value}"
            ),
        )

    target = index.program(edge.candidate_node_ids[0])
    if edge.dispatch is TriggerDispatch.SELF:
        if source_entity_index not in target.source.lookup.selected_entity_indices:
            return _unresolved_dispatch(
                program,
                source_entity_index=source_entity_index,
                target_script_name=edge.target_entity,
                target_trigger=edge.target_trigger,
                dispatch=edge.dispatch,
                resolution=SymbolicDispatchResolution.TARGET_IDENTITY_MISSING,
                line=edge.line,
                reason="self trigger handler does not select the concrete caller entity",
            )
        target_entity_indices = (source_entity_index,)
    else:
        target_entity_indices = target.source.lookup.selected_entity_indices
    return _resolved_dispatch(
        program,
        target,
        source_entity_index=source_entity_index,
        target_script_name=edge.target_entity,
        target_trigger=edge.target_trigger,
        dispatch=edge.dispatch,
        target_entity_indices=target_entity_indices,
        line=edge.line,
    )


_SIGNED_INT_MIN = -(2**31)
_SIGNED_INT_MAX = 2**31 - 1
_UNSIGNED_MODULUS = 2**32
_DEFAULT_SYMBOLIC_PATH_BUDGET = 4096
_SYMBOLIC_ABORT_GUARDS = {
    AccumulatorOperation.ABORT_IF_LESS_THAN,
    AccumulatorOperation.ABORT_IF_GREATER_THAN,
    AccumulatorOperation.ABORT_IF_NOT_EQUAL,
    AccumulatorOperation.ABORT_IF_EQUAL,
    AccumulatorOperation.ABORT_IF_BIT_SET,
    AccumulatorOperation.ABORT_IF_NOT_BIT_SET,
}
_SYMBOLIC_BIT_GUARDS = {
    AccumulatorOperation.ABORT_IF_BIT_SET,
    AccumulatorOperation.ABORT_IF_NOT_BIT_SET,
}


def _valid_symbolic_guard_operand(operation: AccumulatorOperation, operand: int) -> bool:
    return _SIGNED_INT_MIN <= operand <= _SIGNED_INT_MAX and (
        operation not in _SYMBOLIC_BIT_GUARDS or 0 <= operand <= MAX_SIGNED_ACCUMULATOR_BIT_INDEX
    )


def _minimum_masked_unsigned(
    lower: int,
    upper: int,
    required_set_bits: int,
    required_clear_bits: int,
) -> int | None:
    @cache
    def search(bit: int, tight_lower: bool, tight_upper: bool) -> int | None:
        if bit < 0:
            return 0
        lower_bit = (lower >> bit) & 1 if tight_lower else 0
        upper_bit = (upper >> bit) & 1 if tight_upper else 1
        for candidate_bit in range(lower_bit, upper_bit + 1):
            mask = 1 << bit
            if required_set_bits & mask and candidate_bit == 0:
                continue
            if required_clear_bits & mask and candidate_bit == 1:
                continue
            suffix = search(
                bit - 1,
                tight_lower and candidate_bit == lower_bit,
                tight_upper and candidate_bit == upper_bit,
            )
            if suffix is not None:
                return (candidate_bit << bit) | suffix
        return None

    return search(31, True, True)


@dataclass(frozen=True, slots=True)
class SymbolicIntegerDomain:
    lower: int = _SIGNED_INT_MIN
    upper: int = _SIGNED_INT_MAX
    excluded: frozenset[int] = frozenset()
    required_set_bits: int = 0
    required_clear_bits: int = 0

    @classmethod
    def exact(cls, value: int) -> SymbolicIntegerDomain:
        if not _SIGNED_INT_MIN <= value <= _SIGNED_INT_MAX:
            raise ValueError("symbolic integer must fit a signed 32-bit ET accumulator")
        return cls(value, value)

    @property
    def exact_value(self) -> int | None:
        if self.lower == self.upper and self.contains(self.lower):
            return self.lower
        return None

    def contains(self, value: int) -> bool:
        return (
            self.lower <= value <= self.upper
            and value not in self.excluded
            and value & self.required_set_bits == self.required_set_bits
            and not value & self.required_clear_bits
        )

    def _unsigned_segments(self) -> tuple[tuple[int, int], ...]:
        if self.upper < 0:
            return ((self.lower + _UNSIGNED_MODULUS, self.upper + _UNSIGNED_MODULUS),)
        if self.lower >= 0:
            return ((self.lower, self.upper),)
        return (
            (self.lower + _UNSIGNED_MODULUS, _UNSIGNED_MODULUS - 1),
            (0, self.upper),
        )

    def has_candidate(self) -> bool:
        if self.lower > self.upper or self.required_set_bits & self.required_clear_bits:
            return False
        excluded_unsigned = {value % _UNSIGNED_MODULUS for value in self.excluded}
        for segment_lower, segment_upper in self._unsigned_segments():
            lower = segment_lower
            while lower <= segment_upper:
                candidate = _minimum_masked_unsigned(
                    lower,
                    segment_upper,
                    self.required_set_bits,
                    self.required_clear_bits,
                )
                if candidate is None:
                    break
                if candidate not in excluded_unsigned:
                    return True
                lower = candidate + 1
        return False

    def _validated(self, **changes) -> SymbolicIntegerDomain | None:
        candidate = replace(self, **changes)
        if not candidate.has_candidate():
            return None
        exact = candidate.exact_value
        return SymbolicIntegerDomain.exact(exact) if exact is not None else candidate

    def refine_guard(
        self,
        operation: AccumulatorOperation,
        operand: int,
        *,
        predicate_result: bool,
    ) -> SymbolicIntegerDomain | None:
        if operation not in _SYMBOLIC_ABORT_GUARDS or not _valid_symbolic_guard_operand(operation, operand):
            return None
        if operation is AccumulatorOperation.ABORT_IF_EQUAL:
            equal = predicate_result
        elif operation is AccumulatorOperation.ABORT_IF_NOT_EQUAL:
            equal = not predicate_result
        else:
            equal = None
        if equal is True:
            exact = SymbolicIntegerDomain.exact(operand)
            return exact if self.contains(operand) else None
        if equal is False:
            return self._validated(excluded=self.excluded | {operand})
        if operation is AccumulatorOperation.ABORT_IF_LESS_THAN:
            if predicate_result:
                return self._validated(upper=min(self.upper, operand - 1))
            return self._validated(lower=max(self.lower, operand))
        if operation is AccumulatorOperation.ABORT_IF_GREATER_THAN:
            if predicate_result:
                return self._validated(lower=max(self.lower, operand + 1))
            return self._validated(upper=min(self.upper, operand))
        bit = 1 << operand
        if operation is AccumulatorOperation.ABORT_IF_BIT_SET:
            bit_is_set = predicate_result
        elif operation is AccumulatorOperation.ABORT_IF_NOT_BIT_SET:
            bit_is_set = not predicate_result
        else:
            raise AssertionError(f"unsupported accumulator guard: {operation}")
        if bit_is_set:
            return self._validated(required_set_bits=self.required_set_bits | bit)
        return self._validated(required_clear_bits=self.required_clear_bits | bit)


_ZERO_DOMAIN = SymbolicIntegerDomain.exact(0)
_UNKNOWN_DOMAIN = SymbolicIntegerDomain()


@dataclass(frozen=True, slots=True)
class SymbolicAccumulatorState:
    entity_values: tuple[tuple[int, int, SymbolicIntegerDomain], ...] = ()
    global_values: tuple[tuple[int, SymbolicIntegerDomain], ...] = ()
    default_domain: SymbolicIntegerDomain = _ZERO_DOMAIN

    @classmethod
    def zeroed(cls) -> SymbolicAccumulatorState:
        return cls()

    @classmethod
    def unknown(cls) -> SymbolicAccumulatorState:
        return cls(default_domain=_UNKNOWN_DOMAIN)

    def read(
        self,
        scope: AccumulatorScope,
        buffer_index: int,
        *,
        source_entity_index: int,
    ) -> SymbolicIntegerDomain:
        if scope is AccumulatorScope.GLOBAL:
            return next(
                (value for index, value in self.global_values if index == buffer_index),
                self.default_domain,
            )
        return next(
            (
                value
                for entity_index, index, value in self.entity_values
                if entity_index == source_entity_index and index == buffer_index
            ),
            self.default_domain,
        )

    def write(
        self,
        scope: AccumulatorScope,
        buffer_index: int,
        value: SymbolicIntegerDomain,
        *,
        source_entity_index: int,
    ) -> SymbolicAccumulatorState:
        if scope is AccumulatorScope.GLOBAL:
            values = {index: current for index, current in self.global_values}
            values[buffer_index] = value
            return replace(self, global_values=tuple(sorted(values.items())))
        values = {(entity, index): current for entity, index, current in self.entity_values}
        values[(source_entity_index, buffer_index)] = value
        return replace(
            self,
            entity_values=tuple((entity, index, current) for (entity, index), current in sorted(values.items())),
        )


@dataclass(frozen=True, slots=True)
class SymbolicGuardDecision:
    instruction: AccumulatorAbortGuard | AccumulatorConditionalTrigger
    predicate_result: bool
    source_entity_index: int


@dataclass(frozen=True, slots=True)
class SymbolicEventPath:
    source_entity_index: int
    state: SymbolicAccumulatorState
    effects: tuple[StageEffectProjection, ...] = ()
    effect_entity_indices: tuple[int, ...] = ()
    guard_decisions: tuple[SymbolicGuardDecision, ...] = ()
    temporal_boundary_lines: tuple[int, ...] = ()
    temporal_boundary_entity_indices: tuple[int, ...] = ()
    nested_dispatches: tuple[SymbolicDispatchProjection, ...] = ()
    caller_replacement_lines: tuple[int, ...] = ()
    caller_replacement_entity_indices: tuple[int, ...] = ()
    completion: SymbolicPathCompletion = SymbolicPathCompletion.SYNCHRONOUS_COMPLETE
    blocker_reason: str | None = None
    blocker_line: int | None = None
    blocker_entity_index: int | None = None


def _write_refined_domain(
    path: SymbolicEventPath,
    instruction: AccumulatorAbortGuard | AccumulatorConditionalTrigger,
    domain: SymbolicIntegerDomain,
) -> SymbolicEventPath:
    return replace(
        path,
        state=path.state.write(
            instruction.scope,
            instruction.buffer_index,
            domain,
            source_entity_index=path.source_entity_index,
        ),
    )


def _apply_accumulator_mutation(
    path: SymbolicEventPath,
    instruction: AccumulatorMutation,
) -> SymbolicEventPath:
    current = path.state.read(
        instruction.scope,
        instruction.buffer_index,
        source_entity_index=path.source_entity_index,
    )
    if instruction.operation is AccumulatorOperation.SET:
        if not _SIGNED_INT_MIN <= instruction.operand <= _SIGNED_INT_MAX:
            return replace(
                path,
                completion=SymbolicPathCompletion.BLOCKED,
                blocker_reason="invalid_accumulator_operand",
                blocker_line=instruction.line,
                blocker_entity_index=path.source_entity_index,
            )
        value = SymbolicIntegerDomain.exact(instruction.operand)
    else:
        exact = current.exact_value
        if exact is None:
            return replace(
                path,
                completion=SymbolicPathCompletion.BLOCKED,
                blocker_reason="non_exact_accumulator_mutation",
                blocker_line=instruction.line,
                blocker_entity_index=path.source_entity_index,
            )
        if instruction.operation is AccumulatorOperation.INCREMENT:
            result = exact + instruction.operand
            if not _SIGNED_INT_MIN <= result <= _SIGNED_INT_MAX:
                return replace(
                    path,
                    completion=SymbolicPathCompletion.BLOCKED,
                    blocker_reason="signed_accumulator_overflow_unverified",
                    blocker_line=instruction.line,
                    blocker_entity_index=path.source_entity_index,
                )
            value = SymbolicIntegerDomain.exact(result)
        elif instruction.operation in {AccumulatorOperation.BIT_SET, AccumulatorOperation.BIT_RESET}:
            if not 0 <= instruction.operand <= MAX_SIGNED_ACCUMULATOR_BIT_INDEX:
                return replace(
                    path,
                    completion=SymbolicPathCompletion.BLOCKED,
                    blocker_reason="invalid_accumulator_bit_index",
                    blocker_line=instruction.line,
                    blocker_entity_index=path.source_entity_index,
                )
            bit = 1 << instruction.operand
            result = exact | bit if instruction.operation is AccumulatorOperation.BIT_SET else exact & ~bit
            value = SymbolicIntegerDomain.exact(result)
        else:
            raise AssertionError(f"unsupported accumulator mutation: {instruction.operation}")
    return replace(
        path,
        state=path.state.write(
            instruction.scope,
            instruction.buffer_index,
            value,
            source_entity_index=path.source_entity_index,
        ),
    )


def _instruction_line(instruction: OrderedEventInstruction) -> int:
    if isinstance(
        instruction,
        (AccumulatorMutation, AccumulatorAbortGuard, AccumulatorConditionalTrigger, ControlProjectionIssue),
    ):
        return instruction.line
    if isinstance(instruction, StageEffectInstruction):
        return instruction.projection.effect.line
    if isinstance(instruction, TriggerInstruction):
        return instruction.edge.line
    return instruction.action.line


def walk_symbolic_event_program(
    program: OrderedEventProgram,
    *,
    source_entity_index: int,
    initial_state: SymbolicAccumulatorState,
    max_paths: int = _DEFAULT_SYMBOLIC_PATH_BUDGET,
    stop_at_temporal_boundary: bool = False,
) -> tuple[SymbolicEventPath, ...]:
    """Walk one event without guessing nested dispatch or temporal interleaving."""

    if source_entity_index not in program.source.lookup.selected_entity_indices:
        raise ValueError(f"entity {source_entity_index} is not selected by script block {program.node.entity_name!r}")
    if max_paths < 1:
        raise ValueError("max_paths must be positive")
    paths = [
        SymbolicEventPath(
            source_entity_index,
            initial_state,
        )
    ]
    finished: list[SymbolicEventPath] = []
    for instruction in program.instructions:
        continuing: list[SymbolicEventPath] = []
        for path in paths:
            if isinstance(instruction, AccumulatorMutation):
                updated = _apply_accumulator_mutation(path, instruction)
                (finished if updated.completion is SymbolicPathCompletion.BLOCKED else continuing).append(updated)
                continue
            if isinstance(instruction, AccumulatorAbortGuard):
                if not _valid_symbolic_guard_operand(instruction.operation, instruction.operand):
                    finished.append(
                        replace(
                            path,
                            completion=SymbolicPathCompletion.BLOCKED,
                            blocker_reason="invalid_accumulator_guard_operand",
                            blocker_line=instruction.line,
                            blocker_entity_index=source_entity_index,
                        )
                    )
                    continue
                current = path.state.read(
                    instruction.scope,
                    instruction.buffer_index,
                    source_entity_index=source_entity_index,
                )
                for predicate_result in (True, False):
                    domain = current.refine_guard(
                        instruction.operation,
                        instruction.operand,
                        predicate_result=predicate_result,
                    )
                    if domain is None:
                        continue
                    branch = _write_refined_domain(path, instruction, domain)
                    branch = replace(
                        branch,
                        guard_decisions=branch.guard_decisions
                        + (SymbolicGuardDecision(instruction, predicate_result, source_entity_index),),
                    )
                    if predicate_result:
                        finished.append(replace(branch, completion=SymbolicPathCompletion.ABORTED_BY_GUARD))
                    else:
                        continuing.append(branch)
                continue
            if isinstance(instruction, AccumulatorConditionalTrigger):
                if not _valid_symbolic_guard_operand(instruction.operation, instruction.operand):
                    finished.append(
                        replace(
                            path,
                            completion=SymbolicPathCompletion.BLOCKED,
                            blocker_reason="invalid_accumulator_guard_operand",
                            blocker_line=instruction.line,
                            blocker_entity_index=source_entity_index,
                        )
                    )
                    continue
                current = path.state.read(
                    instruction.scope,
                    instruction.buffer_index,
                    source_entity_index=source_entity_index,
                )
                equal_guard = AccumulatorOperation.ABORT_IF_EQUAL
                for predicate_result in (True, False):
                    domain = current.refine_guard(
                        equal_guard,
                        instruction.operand,
                        predicate_result=predicate_result,
                    )
                    if domain is None:
                        continue
                    branch = _write_refined_domain(path, instruction, domain)
                    branch = replace(
                        branch,
                        guard_decisions=branch.guard_decisions
                        + (SymbolicGuardDecision(instruction, predicate_result, source_entity_index),),
                    )
                    if predicate_result:
                        finished.append(
                            replace(
                                branch,
                                completion=SymbolicPathCompletion.BLOCKED,
                                blocker_reason="conditional_trigger_dispatch_not_modeled",
                                blocker_line=instruction.line,
                                blocker_entity_index=source_entity_index,
                            )
                        )
                    else:
                        continuing.append(branch)
                continue
            if isinstance(instruction, StageEffectInstruction):
                continuing.append(
                    replace(
                        path,
                        effects=path.effects + (instruction.projection,),
                        effect_entity_indices=path.effect_entity_indices + (source_entity_index,),
                    )
                )
                continue
            if isinstance(instruction, ControlBarrierInstruction):
                if instruction.kind is ControlBarrierKind.WAIT:
                    # ET:Legacy skips waits during sudden death, so retain both
                    # the immediate and ordinary delayed continuations.
                    continuing.append(path)
                delayed = replace(
                    path,
                    temporal_boundary_lines=path.temporal_boundary_lines + (instruction.action.line,),
                    temporal_boundary_entity_indices=path.temporal_boundary_entity_indices + (source_entity_index,),
                )
                if stop_at_temporal_boundary:
                    finished.append(replace(delayed, completion=SymbolicPathCompletion.TEMPORALLY_SUSPENDED))
                else:
                    continuing.append(delayed)
                continue
            if isinstance(instruction, TriggerInstruction):
                finished.append(
                    replace(
                        path,
                        completion=SymbolicPathCompletion.BLOCKED,
                        blocker_reason="trigger_dispatch_not_modeled",
                        blocker_line=instruction.edge.line,
                        blocker_entity_index=source_entity_index,
                    )
                )
                continue
            if isinstance(instruction, ControlProjectionIssue):
                finished.append(
                    replace(
                        path,
                        completion=SymbolicPathCompletion.BLOCKED,
                        blocker_reason=instruction.reason,
                        blocker_line=instruction.line,
                        blocker_entity_index=source_entity_index,
                    )
                )
                continue
            if instruction.control_disposition is RuntimeActionControlDisposition.MAY_STOP_ON_SPAWN_FAILURE:
                continuing.append(path)
                finished.append(
                    replace(
                        path,
                        completion=SymbolicPathCompletion.BLOCKED,
                        blocker_reason="spawn_failure_frontier",
                        blocker_line=instruction.action.line,
                        blocker_entity_index=source_entity_index,
                    )
                )
            elif instruction.control_disposition is RuntimeActionControlDisposition.CONDITIONAL_TEMPORAL_PAUSE:
                if instruction.action.command == "followspline" and not _followspline_has_wait(instruction.action):
                    continuing.append(path)
                delayed = replace(
                    path,
                    temporal_boundary_lines=path.temporal_boundary_lines + (instruction.action.line,),
                    temporal_boundary_entity_indices=path.temporal_boundary_entity_indices + (source_entity_index,),
                )
                if stop_at_temporal_boundary:
                    finished.append(replace(delayed, completion=SymbolicPathCompletion.TEMPORALLY_SUSPENDED))
                else:
                    continuing.append(delayed)
            elif instruction.blocker_reason is None:
                continuing.append(path)
            else:
                finished.append(
                    replace(
                        path,
                        completion=SymbolicPathCompletion.BLOCKED,
                        blocker_reason=instruction.blocker_reason,
                        blocker_line=instruction.action.line,
                        blocker_entity_index=source_entity_index,
                    )
                )
        if len(continuing) + len(finished) > max_paths:
            exemplar = continuing[0] if continuing else finished[-1]
            budget_frontier = replace(
                exemplar,
                completion=SymbolicPathCompletion.BLOCKED,
                blocker_reason="symbolic_path_budget_exhausted",
                blocker_line=_instruction_line(instruction),
                blocker_entity_index=source_entity_index,
            )
            return tuple(finished[: max_paths - 1]) + (budget_frontier,)
        paths = continuing
        if not paths:
            break
    for path in paths:
        completion = (
            SymbolicPathCompletion.EVENTUAL_COMPLETE
            if path.temporal_boundary_lines
            else SymbolicPathCompletion.SYNCHRONOUS_COMPLETE
        )
        finished.append(replace(path, completion=completion))
    return tuple(finished)


def _merge_symbolic_segment(
    prefix: SymbolicEventPath,
    segment: SymbolicEventPath,
) -> SymbolicEventPath:
    temporal_lines = prefix.temporal_boundary_lines + segment.temporal_boundary_lines
    completion = segment.completion
    if completion is SymbolicPathCompletion.SYNCHRONOUS_COMPLETE and temporal_lines:
        completion = SymbolicPathCompletion.EVENTUAL_COMPLETE
    return replace(
        prefix,
        state=segment.state,
        effects=prefix.effects + segment.effects,
        effect_entity_indices=prefix.effect_entity_indices + segment.effect_entity_indices,
        guard_decisions=prefix.guard_decisions + segment.guard_decisions,
        temporal_boundary_lines=temporal_lines,
        temporal_boundary_entity_indices=(
            prefix.temporal_boundary_entity_indices + segment.temporal_boundary_entity_indices
        ),
        nested_dispatches=prefix.nested_dispatches + segment.nested_dispatches,
        caller_replacement_lines=prefix.caller_replacement_lines + segment.caller_replacement_lines,
        caller_replacement_entity_indices=(
            prefix.caller_replacement_entity_indices + segment.caller_replacement_entity_indices
        ),
        completion=completion,
        blocker_reason=segment.blocker_reason,
        blocker_line=segment.blocker_line,
        blocker_entity_index=segment.blocker_entity_index,
    )


def _resume_symbolic_path(path: SymbolicEventPath) -> SymbolicEventPath:
    return replace(
        path,
        completion=SymbolicPathCompletion.SYNCHRONOUS_COMPLETE,
        blocker_reason=None,
        blocker_line=None,
        blocker_entity_index=None,
    )


def _blocked_symbolic_path(
    path: SymbolicEventPath,
    *,
    reason: str,
    line: int,
    entity_index: int,
) -> SymbolicEventPath:
    return replace(
        path,
        completion=SymbolicPathCompletion.BLOCKED,
        blocker_reason=reason,
        blocker_line=line,
        blocker_entity_index=entity_index,
    )


def _record_caller_replacement(
    path: SymbolicEventPath,
    *,
    line: int,
    entity_index: int,
) -> SymbolicEventPath:
    return replace(
        path,
        caller_replacement_lines=path.caller_replacement_lines + (line,),
        caller_replacement_entity_indices=path.caller_replacement_entity_indices + (entity_index,),
    )


def _temporal_nested_outcome(
    path: SymbolicEventPath,
    *,
    caller_entity_index: int,
    target_entity_index: int,
    last_target: bool,
    dispatch_line: int,
) -> SymbolicEventPath:
    if target_entity_index == caller_entity_index and last_target:
        return _record_caller_replacement(
            path,
            line=dispatch_line,
            entity_index=target_entity_index,
        )
    return _blocked_symbolic_path(
        path,
        reason=(
            "same_entity_temporal_group_order_not_modeled"
            if target_entity_index == caller_entity_index
            else "cross_entity_temporal_interleaving_not_modeled"
        ),
        line=dispatch_line,
        entity_index=target_entity_index,
    )


def _bounded_stage_paths(
    paths: list[SymbolicEventPath],
    *,
    max_paths: int,
    line: int,
    entity_index: int,
) -> tuple[SymbolicEventPath, ...]:
    budget_frontiers = [path for path in paths if path.blocker_reason == "symbolic_path_budget_exhausted"]
    if len(paths) <= max_paths and len(budget_frontiers) <= 1:
        return tuple(paths)
    non_budget_paths = [path for path in paths if path.blocker_reason != "symbolic_path_budget_exhausted"]
    exemplar = budget_frontiers[0] if budget_frontiers else paths[min(len(paths), max_paths) - 1]
    frontier = _blocked_symbolic_path(
        exemplar,
        reason="symbolic_path_budget_exhausted",
        line=line,
        entity_index=entity_index,
    )
    return tuple(non_budget_paths[: max_paths - 1]) + (frontier,)


def _walk_symbolic_stage_from(
    index: OrderedStageProgramIndex,
    program: OrderedEventProgram,
    *,
    current_entity_index: int,
    instruction_offset: int,
    prefix: SymbolicEventPath,
    active_frames: tuple[tuple[int, str], ...],
    max_paths: int,
    max_depth: int,
    stop_at_temporal_boundary: bool,
) -> tuple[SymbolicEventPath, ...]:
    nested_index = next(
        (
            position
            for position in range(instruction_offset, len(program.instructions))
            if isinstance(program.instructions[position], (TriggerInstruction, AccumulatorConditionalTrigger))
        ),
        None,
    )
    segment_end = len(program.instructions) if nested_index is None else nested_index + 1
    segment = replace(program, instructions=program.instructions[instruction_offset:segment_end])
    segment_results = walk_symbolic_event_program(
        segment,
        source_entity_index=current_entity_index,
        initial_state=prefix.state,
        max_paths=max_paths,
        stop_at_temporal_boundary=stop_at_temporal_boundary,
    )
    merged = [_merge_symbolic_segment(prefix, result) for result in segment_results]
    if nested_index is None:
        line = _instruction_line(program.instructions[-1]) if program.instructions else program.node.line
        return _bounded_stage_paths(merged, max_paths=max_paths, line=line, entity_index=current_entity_index)

    instruction = program.instructions[nested_index]
    assert isinstance(instruction, (TriggerInstruction, AccumulatorConditionalTrigger))
    dispatch_line = _instruction_line(instruction)
    expected_blocker = (
        "conditional_trigger_dispatch_not_modeled"
        if isinstance(instruction, AccumulatorConditionalTrigger)
        else "trigger_dispatch_not_modeled"
    )
    outcomes: list[SymbolicEventPath] = []
    for path in merged:
        is_dispatch_branch = (
            path.completion is SymbolicPathCompletion.BLOCKED
            and path.blocker_reason == expected_blocker
            and path.blocker_line == dispatch_line
            and path.blocker_entity_index == current_entity_index
        )
        if not is_dispatch_branch:
            if path.completion in {
                SymbolicPathCompletion.SYNCHRONOUS_COMPLETE,
                SymbolicPathCompletion.EVENTUAL_COMPLETE,
            }:
                outcomes.extend(
                    _walk_symbolic_stage_from(
                        index,
                        program,
                        current_entity_index=current_entity_index,
                        instruction_offset=nested_index + 1,
                        prefix=_resume_symbolic_path(path),
                        active_frames=active_frames,
                        max_paths=max_paths,
                        max_depth=max_depth,
                        stop_at_temporal_boundary=stop_at_temporal_boundary,
                    )
                )
            else:
                outcomes.append(path)
            continue

        dispatch = resolve_symbolic_nested_dispatch(
            index,
            program,
            instruction,
            source_entity_index=current_entity_index,
        )
        dispatched_path = replace(path, nested_dispatches=path.nested_dispatches + (dispatch,))
        if dispatch.resolution is SymbolicDispatchResolution.NO_OP:
            outcomes.extend(
                _walk_symbolic_stage_from(
                    index,
                    program,
                    current_entity_index=current_entity_index,
                    instruction_offset=nested_index + 1,
                    prefix=_resume_symbolic_path(dispatched_path),
                    active_frames=active_frames,
                    max_paths=max_paths,
                    max_depth=max_depth,
                    stop_at_temporal_boundary=stop_at_temporal_boundary,
                )
            )
            continue
        if dispatch.resolution is not SymbolicDispatchResolution.RESOLVED:
            outcomes.append(
                _blocked_symbolic_path(
                    dispatched_path,
                    reason=f"nested_dispatch_{dispatch.resolution.value}",
                    line=dispatch_line,
                    entity_index=current_entity_index,
                )
            )
            continue

        assert dispatch.target_node_id is not None
        target_program = index.program(dispatch.target_node_id)
        outcomes.extend(
            _walk_symbolic_target_group(
                index,
                caller_program=program,
                caller_entity_index=current_entity_index,
                caller_instruction_offset=nested_index + 1,
                target_program=target_program,
                target_entity_indices=dispatch.target_entity_indices,
                target_offset=0,
                dispatch_line=dispatch_line,
                prefix=_resume_symbolic_path(dispatched_path),
                active_frames=active_frames,
                max_paths=max_paths,
                max_depth=max_depth,
                stop_at_temporal_boundary=stop_at_temporal_boundary,
            )
        )
    return _bounded_stage_paths(
        outcomes,
        max_paths=max_paths,
        line=dispatch_line,
        entity_index=current_entity_index,
    )


def _walk_symbolic_target_group(
    index: OrderedStageProgramIndex,
    *,
    caller_program: OrderedEventProgram,
    caller_entity_index: int,
    caller_instruction_offset: int,
    target_program: OrderedEventProgram,
    target_entity_indices: tuple[int, ...],
    target_offset: int,
    dispatch_line: int,
    prefix: SymbolicEventPath,
    active_frames: tuple[tuple[int, str], ...],
    max_paths: int,
    max_depth: int,
    stop_at_temporal_boundary: bool,
) -> tuple[SymbolicEventPath, ...]:
    target_entity_index = target_entity_indices[target_offset]
    target_frame = (target_entity_index, target_program.node.node_id)
    if target_frame in active_frames:
        return (
            _blocked_symbolic_path(
                prefix,
                reason="nested_dispatch_cycle",
                line=dispatch_line,
                entity_index=target_entity_index,
            ),
        )
    if len(active_frames) >= max_depth:
        return (
            _blocked_symbolic_path(
                prefix,
                reason="nested_dispatch_depth_exhausted",
                line=dispatch_line,
                entity_index=target_entity_index,
            ),
        )

    temporal_count = len(prefix.temporal_boundary_lines)
    last_target = target_offset == len(target_entity_indices) - 1
    target_stop_at_temporal_boundary = stop_at_temporal_boundary or (
        target_entity_index != caller_entity_index or not last_target
    )
    target_results = _walk_symbolic_stage_from(
        index,
        target_program,
        current_entity_index=target_entity_index,
        instruction_offset=0,
        prefix=prefix,
        active_frames=active_frames + (target_frame,),
        max_paths=max_paths,
        max_depth=max_depth,
        stop_at_temporal_boundary=target_stop_at_temporal_boundary,
    )
    outcomes: list[SymbolicEventPath] = []
    for path in target_results:
        target_paused = len(path.temporal_boundary_lines) > temporal_count
        if path.completion is SymbolicPathCompletion.BLOCKED:
            outcomes.append(
                _record_caller_replacement(
                    path,
                    line=dispatch_line,
                    entity_index=target_entity_index,
                )
                if target_paused and target_entity_index == caller_entity_index and last_target
                else path
            )
            continue
        if path.completion is SymbolicPathCompletion.TEMPORALLY_SUSPENDED:
            outcomes.append(
                _temporal_nested_outcome(
                    path,
                    caller_entity_index=caller_entity_index,
                    target_entity_index=target_entity_index,
                    last_target=last_target,
                    dispatch_line=dispatch_line,
                )
            )
            continue
        if target_paused:
            outcomes.append(
                _temporal_nested_outcome(
                    path,
                    caller_entity_index=caller_entity_index,
                    target_entity_index=target_entity_index,
                    last_target=last_target,
                    dispatch_line=dispatch_line,
                )
            )
            continue

        resumed = _resume_symbolic_path(path)
        if not last_target:
            outcomes.extend(
                _walk_symbolic_target_group(
                    index,
                    caller_program=caller_program,
                    caller_entity_index=caller_entity_index,
                    caller_instruction_offset=caller_instruction_offset,
                    target_program=target_program,
                    target_entity_indices=target_entity_indices,
                    target_offset=target_offset + 1,
                    dispatch_line=dispatch_line,
                    prefix=resumed,
                    active_frames=active_frames,
                    max_paths=max_paths,
                    max_depth=max_depth,
                    stop_at_temporal_boundary=stop_at_temporal_boundary,
                )
            )
        else:
            outcomes.extend(
                _walk_symbolic_stage_from(
                    index,
                    caller_program,
                    current_entity_index=caller_entity_index,
                    instruction_offset=caller_instruction_offset,
                    prefix=resumed,
                    active_frames=active_frames,
                    max_paths=max_paths,
                    max_depth=max_depth,
                    stop_at_temporal_boundary=stop_at_temporal_boundary,
                )
            )
    return _bounded_stage_paths(
        outcomes,
        max_paths=max_paths,
        line=dispatch_line,
        entity_index=caller_entity_index,
    )


def walk_symbolic_stage_program(
    index: OrderedStageProgramIndex,
    program: OrderedEventProgram,
    *,
    source_entity_index: int,
    initial_state: SymbolicAccumulatorState,
    max_paths: int = _DEFAULT_SYMBOLIC_PATH_BUDGET,
    max_depth: int = 64,
) -> tuple[SymbolicEventPath, ...]:
    """Walk statically resolved nested events with bounded fail-closed recursion."""

    if index.program(program.node.node_id) is not program:
        raise ValueError(f"source program {program.node.node_id!r} does not belong to this ordered-program index")
    if source_entity_index not in program.source.lookup.selected_entity_indices:
        raise ValueError(f"entity {source_entity_index} is not selected by script block {program.node.entity_name!r}")
    if max_paths < 1:
        raise ValueError("max_paths must be positive")
    if max_depth < 1:
        raise ValueError("max_depth must be positive")
    root = SymbolicEventPath(source_entity_index, initial_state)
    return _walk_symbolic_stage_from(
        index,
        program,
        current_entity_index=source_entity_index,
        instruction_offset=0,
        prefix=root,
        active_frames=((source_entity_index, program.node.node_id),),
        max_paths=max_paths,
        max_depth=max_depth,
        stop_at_temporal_boundary=False,
    )


def _event_for_node(model: StaticStageModel, node: StageEventNode) -> ScriptEvent:
    matches = tuple(
        event
        for entity in model.script.entities
        if entity.name == node.entity_name
        for event in entity.events
        if event.line == node.line
        and event.name == node.event_name
        and event.parameters == node.event_parameters
        and event.serialized_parameters == node.serialized_event_parameters
    )
    if len(matches) != 1:
        raise ValueError(f"stage node {node.node_id!r} does not map to exactly one parsed script event")
    return matches[0]


def _take_line_item(items_by_line, line: int, *, kind: str, node_id: str):
    items = items_by_line.get(line)
    if not items:
        raise ValueError(f"{kind} action at line {line} has no projection in stage node {node_id!r}")
    return items.pop(0)


def project_ordered_stage_programs(
    model: StaticStageModel,
    linked: W3LinkedIdentityIndex,
) -> tuple[OrderedEventProgram, ...]:
    """Project every eligible event into source-ordered, non-executed instructions."""

    if linked.map_name != model.map_name:
        raise ValueError(f"linked W3 map {linked.map_name!r} does not match stage model {model.map_name!r}")

    edges_by_node: dict[str, list[TriggerEdge]] = defaultdict(list)
    for edge in model.graph.trigger_edges:
        edges_by_node[edge.source_node_id].append(edge)

    programs: list[OrderedEventProgram] = []
    for node in model.graph.nodes:
        event = _event_for_node(model, node)
        effects_by_line = defaultdict(list)
        for effect in node.effects:
            effects_by_line[effect.line].append(effect)
        edges_by_line = defaultdict(list)
        for edge in edges_by_node[node.node_id]:
            edges_by_line[edge.line].append(edge)

        instructions: list[OrderedEventInstruction] = []
        for action in event.actions:
            accumulator = project_accumulator_action(action)
            if accumulator is not None:
                instructions.append(accumulator)
                continue
            if effects_by_line.get(action.line):
                effect = _take_line_item(
                    effects_by_line,
                    action.line,
                    kind="stage-effect",
                    node_id=node.node_id,
                )
                instructions.append(
                    StageEffectInstruction(
                        project_stage_effect(
                            effect,
                            source_script_name=node.entity_name,
                            linked=linked,
                            objectives=model.objectives,
                        )
                    )
                )
                continue
            if action.command in STAGE_EFFECT_COMMANDS:
                raise ValueError(
                    f"stage-effect action {action.command!r} at line {action.line} "
                    f"has no projection in stage node {node.node_id!r}"
                )
            if action.command == "trigger":
                edge = _take_line_item(
                    edges_by_line,
                    action.line,
                    kind="trigger",
                    node_id=node.node_id,
                )
                instructions.append(TriggerInstruction(edge))
                continue
            try:
                barrier_kind = ControlBarrierKind(action.command)
            except ValueError:
                instructions.append(RuntimeActionInstruction(action, runtime_action_control_disposition(action)))
            else:
                instructions.append(ControlBarrierInstruction(barrier_kind, action))

        remaining_effects = sum(len(items) for items in effects_by_line.values())
        remaining_edges = sum(len(items) for items in edges_by_line.values())
        if remaining_effects or remaining_edges:
            raise ValueError(
                f"stage node {node.node_id!r} left {remaining_effects} effects and {remaining_edges} triggers unprojected"
            )
        programs.append(
            OrderedEventProgram(
                node,
                event,
                EffectSourceIdentity(
                    node.entity_name,
                    linked.identities.lookup_all(EntityIdentityNamespace.SCRIPT_NAME, node.entity_name),
                ),
                tuple(instructions),
            )
        )

    return tuple(programs)


def build_ordered_stage_program_index(
    model: StaticStageModel,
    linked: W3LinkedIdentityIndex,
) -> OrderedStageProgramIndex:
    """Index ordered programs and opaque script names for nested dispatch."""

    programs = project_ordered_stage_programs(model, linked)
    programs_by_node_id = {program.node.node_id: program for program in programs}
    if len(programs_by_node_id) != len(programs):
        raise ValueError("ordered stage programs contain duplicate node ids")
    trigger_handlers_by_script: dict[str, list[OrderedEventProgram]] = defaultdict(list)
    for program in programs:
        if program.node.event_name == "trigger":
            trigger_handlers_by_script[_ascii_fold(program.node.entity_name)].append(program)
    projected_names = {_ascii_fold(program.node.entity_name) for program in programs}
    opaque_names = frozenset(
        folded
        for item in model.graph.opaque_entities
        if (folded := _ascii_fold(item.entity_name)) not in projected_names
    )
    return OrderedStageProgramIndex(
        programs,
        opaque_names,
        MappingProxyType(programs_by_node_id),
        MappingProxyType({name: tuple(handlers) for name, handlers in trigger_handlers_by_script.items()}),
    )
