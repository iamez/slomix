"""Ordered W5b control-program projection without path execution.

The game runner evaluates event actions in source order. This module preserves that
order and classifies only the control families already verified against the pinned
ET:Legacy source. Runtime actions outside that subset remain explicit instructions;
they are not assumed to be harmless or executable.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
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
    ControlProjectionIssue,
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
    "set": RuntimeActionControlDisposition.MAY_REPLACE_SCRIPT_CONTEXT,
}


def runtime_action_control_disposition(command: str) -> RuntimeActionControlDisposition:
    """Return only source-verified current-event control behavior."""

    if command in _IMMEDIATE_RUNTIME_ACTIONS:
        return RuntimeActionControlDisposition.IMMEDIATE_CURRENT_EVENT_CONTINUE
    return _SPECIAL_RUNTIME_ACTIONS.get(command, RuntimeActionControlDisposition.UNCLASSIFIED)


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
        if self.control_disposition is RuntimeActionControlDisposition.IMMEDIATE_CURRENT_EVENT_CONTINUE:
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
    instructions: tuple[OrderedEventInstruction, ...]


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
                instructions.append(
                    RuntimeActionInstruction(action, runtime_action_control_disposition(action.command))
                )
            else:
                instructions.append(ControlBarrierInstruction(barrier_kind, action))

        remaining_effects = sum(len(items) for items in effects_by_line.values())
        remaining_edges = sum(len(items) for items in edges_by_line.values())
        if remaining_effects or remaining_edges:
            raise ValueError(
                f"stage node {node.node_id!r} left {remaining_effects} effects and {remaining_edges} triggers unprojected"
            )
        programs.append(OrderedEventProgram(node, event, tuple(instructions)))

    return tuple(programs)
