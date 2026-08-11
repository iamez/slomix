"""Ordered W5b control-program projection and fail-closed symbolic paths.

The game runner evaluates event actions in source order. This module preserves that
order, classifies only source-verified control families and walks accumulator guards
without guessing nested dispatch. Runtime actions outside the approved subset remain
explicit blockers; they are not assumed to be harmless or executable.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from enum import StrEnum
from functools import cache
from typing import TypeAlias

from website.backend.map_geometry.stage import (
    STAGE_EFFECT_COMMANDS,
    ScriptAction,
    ScriptEvent,
    StageEventNode,
    StaticStageModel,
    TriggerEdge,
)
from website.backend.map_geometry.stage_semantics import (
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
    ABORTED_BY_GUARD = "aborted_by_guard"
    BLOCKED = "blocked"


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


_SIGNED_INT_MIN = -(2**31)
_SIGNED_INT_MAX = 2**31 - 1
_UNSIGNED_MODULUS = 2**32


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


@dataclass(frozen=True, slots=True)
class SymbolicEventPath:
    source_entity_index: int
    state: SymbolicAccumulatorState
    effects: tuple[StageEffectProjection, ...] = ()
    guard_decisions: tuple[SymbolicGuardDecision, ...] = ()
    temporal_boundary_lines: tuple[int, ...] = ()
    completion: SymbolicPathCompletion = SymbolicPathCompletion.SYNCHRONOUS_COMPLETE
    blocker_reason: str | None = None
    blocker_line: int | None = None


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
        value = SymbolicIntegerDomain.exact(instruction.operand)
    else:
        exact = current.exact_value
        if exact is None:
            return replace(
                path,
                completion=SymbolicPathCompletion.BLOCKED,
                blocker_reason="non_exact_accumulator_mutation",
                blocker_line=instruction.line,
            )
        if instruction.operation is AccumulatorOperation.INCREMENT:
            result = exact + instruction.operand
            if not _SIGNED_INT_MIN <= result <= _SIGNED_INT_MAX:
                return replace(
                    path,
                    completion=SymbolicPathCompletion.BLOCKED,
                    blocker_reason="signed_accumulator_overflow_unverified",
                    blocker_line=instruction.line,
                )
            value = SymbolicIntegerDomain.exact(result)
        elif instruction.operation is AccumulatorOperation.BIT_SET:
            value = SymbolicIntegerDomain.exact(exact | (1 << instruction.operand))
        elif instruction.operation is AccumulatorOperation.BIT_RESET:
            value = SymbolicIntegerDomain.exact(exact & ~(1 << instruction.operand))
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


def walk_symbolic_event_program(
    program: OrderedEventProgram,
    *,
    source_entity_index: int,
    initial_state: SymbolicAccumulatorState,
) -> tuple[SymbolicEventPath, ...]:
    """Walk one event without guessing nested dispatch or unsupported runtime control."""

    if source_entity_index not in program.source.lookup.selected_entity_indices:
        raise ValueError(f"entity {source_entity_index} is not selected by script block {program.node.entity_name!r}")
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
                        + (SymbolicGuardDecision(instruction, predicate_result),),
                    )
                    if predicate_result:
                        finished.append(replace(branch, completion=SymbolicPathCompletion.ABORTED_BY_GUARD))
                    else:
                        continuing.append(branch)
                continue
            if isinstance(instruction, AccumulatorConditionalTrigger):
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
                        + (SymbolicGuardDecision(instruction, predicate_result),),
                    )
                    if predicate_result:
                        finished.append(
                            replace(
                                branch,
                                completion=SymbolicPathCompletion.BLOCKED,
                                blocker_reason="conditional_trigger_dispatch_not_modeled",
                                blocker_line=instruction.line,
                            )
                        )
                    else:
                        continuing.append(branch)
                continue
            if isinstance(instruction, StageEffectInstruction):
                continuing.append(replace(path, effects=path.effects + (instruction.projection,)))
                continue
            if isinstance(instruction, ControlBarrierInstruction):
                if instruction.kind is ControlBarrierKind.WAIT:
                    # ET:Legacy skips waits during sudden death, so retain both
                    # the immediate and ordinary delayed continuations.
                    continuing.append(path)
                continuing.append(
                    replace(
                        path,
                        temporal_boundary_lines=path.temporal_boundary_lines + (instruction.action.line,),
                    )
                )
                continue
            if isinstance(instruction, TriggerInstruction):
                finished.append(
                    replace(
                        path,
                        completion=SymbolicPathCompletion.BLOCKED,
                        blocker_reason="trigger_dispatch_not_modeled",
                        blocker_line=instruction.edge.line,
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
                    )
                )
            elif instruction.control_disposition is RuntimeActionControlDisposition.CONDITIONAL_TEMPORAL_PAUSE:
                if instruction.action.command == "followspline" and not _followspline_has_wait(instruction.action):
                    continuing.append(path)
                continuing.append(
                    replace(
                        path,
                        temporal_boundary_lines=path.temporal_boundary_lines + (instruction.action.line,),
                    )
                )
            elif instruction.blocker_reason is None:
                continuing.append(path)
            else:
                finished.append(
                    replace(
                        path,
                        completion=SymbolicPathCompletion.BLOCKED,
                        blocker_reason=instruction.blocker_reason,
                        blocker_line=instruction.action.line,
                    )
                )
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
