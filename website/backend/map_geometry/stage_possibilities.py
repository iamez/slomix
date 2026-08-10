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
    blocker_reason: str = "control_semantics_not_classified"


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
                instructions.append(RuntimeActionInstruction(action))
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
