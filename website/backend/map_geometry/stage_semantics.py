"""Engine-compatible BSP identity lookups for W5b static stage mapping.

The ET game module does not use one common namespace for script actions.
``trigger`` dispatches to every matching ``scriptName``; ``setstate`` and
``alertentity`` use every matching ``targetname``; ``setautospawn`` uses the
first matching runtime ``message``; and ``gotomarker`` prefers the registered
path-corner table before the first matching ``targetname``.

This module models only those static identity rules. It does not claim that a
raw BSP entity survives every game-mode/custom-entity load path, that an action
ran in a historical round, or that runtime entity coverage is complete.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, TypeAlias

from website.backend.map_geometry.bsp import BspFile, parse_entities
from website.backend.map_geometry.entities import MapEntityCatalog
from website.backend.map_geometry.pk3_index import MapAssetKind, Pk3GeometryIndex, Pk3IndexError
from website.backend.map_geometry.stage import (
    AlertEntityEffect,
    AutoSpawnEffect,
    EntityStateEffect,
    GotoMarkerEffect,
    MainObjectiveEffect,
    MainObjectiveSelectorForm,
    ObjectiveCatalog,
    ObjectiveDescription,
    ObjectiveStatusEffect,
    ObjectiveTeam,
    RoundEndEffect,
    ScriptAction,
    StageEffect,
    WinnerEffect,
)

ETLEGACY_SEMANTICS_COMMIT = "732518efb1c479dcd29b13361f30a2e92df1cf2a"


class EntityIdentityNamespace(StrEnum):
    SCRIPT_NAME = "script_name"
    TARGET_NAME = "target_name"
    TARGET = "target"
    MESSAGE = "message"
    PATH_CORNER = "path_corner"


class EntityIdentityResolution(StrEnum):
    MISSING = "missing"
    UNIQUE = "unique"
    GROUP = "group"
    FIRST_MATCH = "first_match"


class ScriptNameSource(StrEnum):
    BSP_FIELD = "bsp_field"
    CLASS_OVERRIDE = "class_override"


class EntitySourceKind(StrEnum):
    BSP_LUMP = "bsp_lump"
    ENT_OVERRIDE = "ent_override"


class AccumulatorScope(StrEnum):
    ENTITY = "entity"
    GLOBAL = "global"


class AccumulatorOperation(StrEnum):
    SET = "set"
    INCREMENT = "inc"
    BIT_SET = "bitset"
    BIT_RESET = "bitreset"
    ABORT_IF_LESS_THAN = "abort_if_less_than"
    ABORT_IF_GREATER_THAN = "abort_if_greater_than"
    ABORT_IF_NOT_EQUAL = "abort_if_not_equal"
    ABORT_IF_EQUAL = "abort_if_equal"
    ABORT_IF_BIT_SET = "abort_if_bitset"
    ABORT_IF_NOT_BIT_SET = "abort_if_not_bitset"
    TRIGGER_IF_EQUAL = "trigger_if_equal"


class W3EntityKind(StrEnum):
    SPAWN_POINT = "spawn_point"
    OBJECTIVE_VOLUME = "objective_volume"
    OBJECTIVE_MARKER = "objective_marker"
    COLLISION_ENTITY = "collision_entity"


@dataclass(frozen=True, slots=True)
class BspEntityIdentity:
    entity_index: int
    classname: str
    script_name: str | None
    script_name_source: ScriptNameSource | None
    target_name: str | None
    target: str | None
    message: str | None
    path_corner_name: str | None
    path_corner_source: str | None
    properties: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class EntityIdentityLookup:
    namespace: EntityIdentityNamespace
    requested_value: str
    match_semantics: Literal["all", "first"]
    candidate_entity_indices: tuple[int, ...]
    selected_entity_indices: tuple[int, ...]
    resolution: EntityIdentityResolution


@dataclass(frozen=True, slots=True)
class AccumulatorMutation:
    scope: AccumulatorScope
    buffer_index: int
    operation: Literal[
        AccumulatorOperation.SET,
        AccumulatorOperation.INCREMENT,
        AccumulatorOperation.BIT_SET,
        AccumulatorOperation.BIT_RESET,
    ]
    operand: int
    line: int


@dataclass(frozen=True, slots=True)
class AccumulatorAbortGuard:
    scope: AccumulatorScope
    buffer_index: int
    operation: Literal[
        AccumulatorOperation.ABORT_IF_LESS_THAN,
        AccumulatorOperation.ABORT_IF_GREATER_THAN,
        AccumulatorOperation.ABORT_IF_NOT_EQUAL,
        AccumulatorOperation.ABORT_IF_EQUAL,
        AccumulatorOperation.ABORT_IF_BIT_SET,
        AccumulatorOperation.ABORT_IF_NOT_BIT_SET,
    ]
    operand: int
    line: int


@dataclass(frozen=True, slots=True)
class AccumulatorConditionalTrigger:
    scope: AccumulatorScope
    buffer_index: int
    operation: Literal[AccumulatorOperation.TRIGGER_IF_EQUAL]
    operand: int
    target_script_name: str
    target_trigger: str
    line: int


@dataclass(frozen=True, slots=True)
class ControlProjectionIssue:
    action_command: str
    operation: str | None
    arguments: tuple[str, ...]
    line: int
    reason: str


@dataclass(frozen=True, slots=True)
class W3EntityReference:
    entity_index: int
    classname: str
    kind: W3EntityKind


@dataclass(frozen=True, slots=True)
class W3LinkedIdentityIndex:
    """W3 geometry identities joined to the full BSP identity namespace."""

    map_name: str
    identities: BspEntityIdentityIndex
    catalog: MapEntityCatalog
    references: tuple[W3EntityReference, ...]
    runtime_entity_completeness: str = "unverified"

    def identity(self, reference: W3EntityReference) -> BspEntityIdentity:
        return self.identities.entities[reference.entity_index]

    def typed_reference(self, entity_index: int) -> W3EntityReference | None:
        return next(
            (reference for reference in self.references if reference.entity_index == entity_index),
            None,
        )


@dataclass(frozen=True, slots=True)
class EffectSourceIdentity:
    script_name: str
    lookup: EntityIdentityLookup


@dataclass(frozen=True, slots=True)
class EntityTargetEffectProjection:
    effect: EntityStateEffect | AlertEntityEffect
    source: EffectSourceIdentity
    target_lookup: EntityIdentityLookup
    selected_w3_references: tuple[W3EntityReference, ...]
    runtime_entity_completeness: str = "unverified"


@dataclass(frozen=True, slots=True)
class GotoMarkerEffectProjection:
    effect: GotoMarkerEffect
    source: EffectSourceIdentity
    destination_lookup: EntityIdentityLookup
    destination_w3_references: tuple[W3EntityReference, ...]
    relative_lookups: tuple[EntityIdentityLookup, ...]
    relative_w3_references: tuple[tuple[W3EntityReference, ...], ...]
    runtime_entity_completeness: str = "unverified"


@dataclass(frozen=True, slots=True)
class AutoSpawnEffectProjection:
    effect: AutoSpawnEffect
    source: EffectSourceIdentity
    marker_lookup: EntityIdentityLookup
    marker_w3_references: tuple[W3EntityReference, ...]
    team_spawn_candidates: tuple[W3EntityReference, ...]
    blocked_reason: str | None
    selection_semantics: str = "runtime_active_ownership_proximity_unverified"


@dataclass(frozen=True, slots=True)
class ObjectiveStatusEffectProjection:
    effect: ObjectiveStatusEffect
    source: EffectSourceIdentity
    descriptions: tuple[ObjectiveDescription, ...]


@dataclass(frozen=True, slots=True)
class MainObjectiveEffectProjection:
    effect: MainObjectiveEffect
    source: EffectSourceIdentity
    target_lookup: EntityIdentityLookup | None
    selected_w3_references: tuple[W3EntityReference, ...]
    blocked_reason: str | None
    runtime_entity_completeness: str = "unverified"


@dataclass(frozen=True, slots=True)
class GlobalStageEffectProjection:
    effect: WinnerEffect | RoundEndEffect
    source: EffectSourceIdentity


@dataclass(frozen=True, slots=True)
class EffectProjectionIssue:
    effect: StageEffect
    source: EffectSourceIdentity
    reason: str


StageEffectProjection: TypeAlias = (
    EntityTargetEffectProjection
    | GotoMarkerEffectProjection
    | AutoSpawnEffectProjection
    | ObjectiveStatusEffectProjection
    | MainObjectiveEffectProjection
    | GlobalStageEffectProjection
    | EffectProjectionIssue
)


AccumulatorInstruction: TypeAlias = AccumulatorMutation | AccumulatorAbortGuard | AccumulatorConditionalTrigger
AccumulatorProjection: TypeAlias = AccumulatorInstruction | ControlProjectionIssue

_MUTATION_OPERATIONS = {
    AccumulatorOperation.SET,
    AccumulatorOperation.INCREMENT,
    AccumulatorOperation.BIT_SET,
    AccumulatorOperation.BIT_RESET,
}
_ABORT_OPERATIONS = {
    AccumulatorOperation.ABORT_IF_LESS_THAN,
    AccumulatorOperation.ABORT_IF_GREATER_THAN,
    AccumulatorOperation.ABORT_IF_NOT_EQUAL,
    AccumulatorOperation.ABORT_IF_EQUAL,
    AccumulatorOperation.ABORT_IF_BIT_SET,
    AccumulatorOperation.ABORT_IF_NOT_BIT_SET,
}
_BIT_OPERATIONS = {
    AccumulatorOperation.BIT_SET,
    AccumulatorOperation.BIT_RESET,
    AccumulatorOperation.ABORT_IF_BIT_SET,
    AccumulatorOperation.ABORT_IF_NOT_BIT_SET,
}
_MAX_ACCUMULATOR_BUFFERS = 10
_MAX_SAFE_SIGNED_BIT_INDEX = 30


@dataclass(frozen=True, slots=True)
class BspEntityIdentityIndex:
    entities: tuple[BspEntityIdentity, ...]
    source: str = ""
    source_kind: EntitySourceKind = EntitySourceKind.BSP_LUMP
    semantics_source_commit: str = ETLEGACY_SEMANTICS_COMMIT
    runtime_entity_completeness: str = "unverified"

    def lookup_all(self, namespace: EntityIdentityNamespace, value: str) -> EntityIdentityLookup:
        """Return every entity selected by an engine all-match lookup."""

        candidates = self._candidate_indices(namespace, value)
        if not candidates:
            resolution = EntityIdentityResolution.MISSING
        elif len(candidates) == 1:
            resolution = EntityIdentityResolution.UNIQUE
        else:
            resolution = EntityIdentityResolution.GROUP
        return EntityIdentityLookup(
            namespace=namespace,
            requested_value=value,
            match_semantics="all",
            candidate_entity_indices=candidates,
            selected_entity_indices=candidates,
            resolution=resolution,
        )

    def lookup_first(self, namespace: EntityIdentityNamespace, value: str) -> EntityIdentityLookup:
        """Return the first entity selected by an engine first-match lookup."""

        candidates = self._candidate_indices(namespace, value)
        if not candidates:
            selected: tuple[int, ...] = ()
            resolution = EntityIdentityResolution.MISSING
        elif len(candidates) == 1:
            selected = candidates
            resolution = EntityIdentityResolution.UNIQUE
        else:
            selected = candidates[:1]
            resolution = EntityIdentityResolution.FIRST_MATCH
        return EntityIdentityLookup(
            namespace=namespace,
            requested_value=value,
            match_semantics="first",
            candidate_entity_indices=candidates,
            selected_entity_indices=selected,
            resolution=resolution,
        )

    def lookup_gotomarker(self, value: str) -> EntityIdentityLookup:
        """Apply ET's path-corner-first ``gotomarker`` lookup order."""

        path_corner = self.lookup_first(EntityIdentityNamespace.PATH_CORNER, value)
        if path_corner.resolution is not EntityIdentityResolution.MISSING:
            return path_corner
        return self.lookup_first(EntityIdentityNamespace.TARGET_NAME, value)

    def _candidate_indices(self, namespace: EntityIdentityNamespace, value: str) -> tuple[int, ...]:
        if not value:
            return ()
        return tuple(
            entity.entity_index for entity in self.entities if _ascii_equal(_identity_value(entity, namespace), value)
        )


def _ascii_fold(value: str) -> str:
    return "".join(chr(ord(character) + 32) if "A" <= character <= "Z" else character for character in value)


def _ascii_equal(left: str | None, right: str) -> bool:
    return left is not None and _ascii_fold(left) == _ascii_fold(right)


def _canonical_int(value: str) -> int | None:
    if not value:
        return None
    digits = value[1:] if value[0] in {"+", "-"} else value
    if not digits or any(character < "0" or character > "9" for character in digits):
        return None
    parsed = int(value)
    if parsed < -(2**31) or parsed > 2**31 - 1:
        return None
    return parsed


def _generic_field(entity: dict[str, str], *field_names: str) -> str | None:
    """Reproduce the case-insensitive, last-assignment generic field parser."""

    folded_names = {_ascii_fold(name) for name in field_names}
    result = None
    for key, value in entity.items():
        if _ascii_fold(key) in folded_names:
            result = value
    return result


def _identity_value(entity: BspEntityIdentity, namespace: EntityIdentityNamespace) -> str | None:
    if namespace is EntityIdentityNamespace.SCRIPT_NAME:
        return entity.script_name
    if namespace is EntityIdentityNamespace.TARGET_NAME:
        return entity.target_name
    if namespace is EntityIdentityNamespace.TARGET:
        return entity.target
    if namespace is EntityIdentityNamespace.MESSAGE:
        return entity.message
    if namespace is EntityIdentityNamespace.PATH_CORNER:
        return entity.path_corner_name
    raise AssertionError(f"unsupported entity identity namespace: {namespace}")


def _entity_identity(entity_index: int, entity: dict[str, str]) -> BspEntityIdentity:
    classname = _generic_field(entity, "classname") or ""
    script_name = _generic_field(entity, "scriptName")
    script_name_source = ScriptNameSource.BSP_FIELD if script_name is not None else None

    # SP_script_multiplayer overwrites any map-provided value before script parse.
    if classname == "script_multiplayer":
        script_name = "game_manager"
        script_name_source = ScriptNameSource.CLASS_OVERRIDE

    message = _generic_field(entity, "message", "popup", "book", "shortname")
    # SP_team_WOLF_objective reads this key with the case-sensitive spawn-var
    # helper and overwrites the generic message field.
    if classname == "team_WOLF_objective":
        message = entity.get("description", "WARNING: No objective description set")

    target_name = _generic_field(entity, "targetname")
    path_corner_name = None
    path_corner_source = None
    if classname in {"path_corner_2", "info_train_spline_control"} and target_name:
        path_corner_name = target_name
        path_corner_source = classname

    return BspEntityIdentity(
        entity_index=entity_index,
        classname=classname,
        script_name=script_name,
        script_name_source=script_name_source,
        target_name=target_name,
        target=_generic_field(entity, "target"),
        message=message,
        path_corner_name=path_corner_name,
        path_corner_source=path_corner_source,
        properties=tuple(entity.items()),
    )


def _control_issue(action: ScriptAction, operation: str | None, reason: str) -> ControlProjectionIssue:
    return ControlProjectionIssue(
        action_command=action.command,
        operation=operation,
        arguments=action.arguments,
        line=action.line,
        reason=reason,
    )


def project_accumulator_action(action: ScriptAction) -> AccumulatorProjection | None:
    """Project the installed, deterministic accumulator subset or fail closed."""

    command = _ascii_fold(action.command)
    if command == "accum":
        scope = AccumulatorScope.ENTITY
    elif command == "globalaccum":
        scope = AccumulatorScope.GLOBAL
    else:
        return None

    if len(action.arguments) < 2:
        return _control_issue(action, None, "accumulator action requires a buffer index and operation")

    buffer_index = _canonical_int(action.arguments[0])
    if buffer_index is None or not 0 <= buffer_index < _MAX_ACCUMULATOR_BUFFERS:
        return _control_issue(action, action.arguments[1], "buffer index must be a canonical integer from 0 to 9")

    operation_name = _ascii_fold(action.arguments[1])
    if operation_name == "abort_if_not_equals":
        operation_name = AccumulatorOperation.ABORT_IF_NOT_EQUAL.value
    try:
        operation = AccumulatorOperation(operation_name)
    except ValueError:
        return _control_issue(action, operation_name, "operation is outside the approved W5b accumulator subset")

    required_arguments = 5 if operation is AccumulatorOperation.TRIGGER_IF_EQUAL else 3
    if len(action.arguments) != required_arguments:
        return _control_issue(
            action,
            operation.value,
            f"{operation.value} requires exactly {required_arguments} callback arguments",
        )

    operand = _canonical_int(action.arguments[2])
    if operand is None:
        return _control_issue(action, operation.value, "operand must be a canonical signed 32-bit integer")
    if operation in _BIT_OPERATIONS and not 0 <= operand <= _MAX_SAFE_SIGNED_BIT_INDEX:
        return _control_issue(action, operation.value, "bit index must be in the defined signed-int range 0 to 30")

    if operation in _MUTATION_OPERATIONS:
        return AccumulatorMutation(scope, buffer_index, operation, operand, action.line)
    if operation in _ABORT_OPERATIONS:
        return AccumulatorAbortGuard(scope, buffer_index, operation, operand, action.line)
    if operation is AccumulatorOperation.TRIGGER_IF_EQUAL:
        target_script_name, target_trigger = action.arguments[3:]
        if not target_script_name or not target_trigger:
            return _control_issue(action, operation.value, "conditional trigger requires non-empty target and event")
        return AccumulatorConditionalTrigger(
            scope,
            buffer_index,
            operation,
            operand,
            target_script_name,
            target_trigger,
            action.line,
        )
    raise AssertionError(f"unhandled approved accumulator operation: {operation}")


def _effect_source(identities: BspEntityIdentityIndex, script_name: str) -> EffectSourceIdentity:
    return EffectSourceIdentity(
        script_name,
        identities.lookup_all(EntityIdentityNamespace.SCRIPT_NAME, script_name),
    )


def _selected_w3_references(
    linked: W3LinkedIdentityIndex,
    lookup: EntityIdentityLookup,
) -> tuple[W3EntityReference, ...]:
    selected = set(lookup.selected_entity_indices)
    return tuple(reference for reference in linked.references if reference.entity_index in selected)


def _goto_relative_targets(effect: GotoMarkerEffect) -> tuple[str, ...] | None:
    targets: list[str] = []
    for index, argument in enumerate(effect.arguments):
        if _ascii_fold(argument) != "relative":
            continue
        if index + 1 >= len(effect.arguments):
            return None
        targets.append(effect.arguments[index + 1])
    return tuple(targets)


def _objective_descriptions(
    objectives: ObjectiveCatalog,
    effect: ObjectiveStatusEffect,
) -> tuple[ObjectiveDescription, ...]:
    team = ObjectiveTeam.AXIS if effect.team_code == 0 else ObjectiveTeam.ALLIES
    return tuple(
        description
        for description in objectives.objectives
        if description.team is team and description.number == effect.objective_number
    )


def project_stage_effect(
    effect: StageEffect,
    *,
    source_script_name: str,
    linked: W3LinkedIdentityIndex,
    objectives: ObjectiveCatalog,
) -> StageEffectProjection:
    """Map one typed W5a effect to exact static candidates without claiming runtime state."""

    identities = linked.identities
    source = _effect_source(identities, source_script_name)

    if isinstance(effect, (EntityStateEffect, AlertEntityEffect)):
        lookup = identities.lookup_all(EntityIdentityNamespace.TARGET_NAME, effect.target)
        return EntityTargetEffectProjection(
            effect,
            source,
            lookup,
            _selected_w3_references(linked, lookup),
        )

    if isinstance(effect, GotoMarkerEffect):
        destination = identities.lookup_gotomarker(effect.target)
        relative_targets = _goto_relative_targets(effect)
        if relative_targets is None:
            return EffectProjectionIssue(effect, source, "gotomarker relative option has no target")
        relative_lookups = tuple(identities.lookup_gotomarker(target) for target in relative_targets)
        return GotoMarkerEffectProjection(
            effect,
            source,
            destination,
            _selected_w3_references(linked, destination),
            relative_lookups,
            tuple(_selected_w3_references(linked, lookup) for lookup in relative_lookups),
        )

    if isinstance(effect, AutoSpawnEffect):
        marker = identities.lookup_first(EntityIdentityNamespace.MESSAGE, effect.spawn_description)
        selected_marker = (
            identities.entities[marker.selected_entity_indices[0]] if marker.selected_entity_indices else None
        )
        if selected_marker is None:
            blocked_reason = "no_static_message_candidate"
        elif selected_marker.classname != "team_WOLF_objective":
            blocked_reason = "first_static_message_candidate_is_not_team_WOLF_objective"
        else:
            blocked_reason = None
        team = "AXIS" if effect.team_code == 0 else "ALLIES"
        spawn_indices = {spawn.entity_index for spawn in linked.catalog.spawn_points if spawn.team == team}
        return AutoSpawnEffectProjection(
            effect,
            source,
            marker,
            _selected_w3_references(linked, marker),
            tuple(reference for reference in linked.references if reference.entity_index in spawn_indices),
            blocked_reason=blocked_reason,
        )

    if isinstance(effect, ObjectiveStatusEffect):
        return ObjectiveStatusEffectProjection(effect, source, _objective_descriptions(objectives, effect))

    if isinstance(effect, MainObjectiveEffect):
        if effect.selector_form is MainObjectiveSelectorForm.LEGACY_NUMERIC:
            return MainObjectiveEffectProjection(
                effect,
                source,
                None,
                (),
                "legacy_numeric_selector_is_unverified_for_the_live_build",
            )
        lookup = identities.lookup_first(EntityIdentityNamespace.TARGET, effect.selector)
        selected = identities.entities[lookup.selected_entity_indices[0]] if lookup.selected_entity_indices else None
        if selected is None:
            blocked_reason = "no_static_target_field_candidate"
        elif selected.classname != "trigger_objective_info":
            blocked_reason = "first_static_target_field_candidate_is_not_trigger_objective_info"
        else:
            blocked_reason = None
        return MainObjectiveEffectProjection(
            effect,
            source,
            lookup,
            _selected_w3_references(linked, lookup),
            blocked_reason,
        )

    if isinstance(effect, (WinnerEffect, RoundEndEffect)):
        return GlobalStageEffectProjection(effect, source)

    return EffectProjectionIssue(effect, source, f"unsupported W5b stage effect type {type(effect).__name__}")


def build_entity_identity_index(
    entities: tuple[dict[str, str], ...],
    *,
    source: str = "",
    source_kind: EntitySourceKind = EntitySourceKind.BSP_LUMP,
) -> BspEntityIdentityIndex:
    """Build a deterministic W5b identity index in BSP entity order."""

    return BspEntityIdentityIndex(
        entities=tuple(_entity_identity(index, entity) for index, entity in enumerate(entities)),
        source=source,
        source_kind=source_kind,
    )


def build_bsp_entity_identity_index(bsp: BspFile) -> BspEntityIdentityIndex:
    return build_entity_identity_index(bsp.entities, source=bsp.source)


def build_indexed_entity_identity_index(
    geometry_index: Pk3GeometryIndex,
    map_name: str,
    *,
    bsp: BspFile | None = None,
) -> BspEntityIdentityIndex:
    """Apply ET:Legacy's maps/<map>.ent-before-BSP identity source rule."""

    override = geometry_index.resolve_asset(map_name, MapAssetKind.ENTITY_OVERRIDE)
    if override.status == "ambiguous":
        raise Pk3IndexError(
            f"map {override.map_name!r} has ambiguous entity overrides and no verified live VFS precedence: "
            f"{override.reason}"
        )
    if override.selected is None:
        if bsp is None:
            bsp = geometry_index.load_bsp(map_name)
        else:
            geometry = geometry_index.resolve(map_name)
            if geometry.selected is None or geometry.selected.source != bsp.source:
                raise Pk3IndexError(
                    f"provided BSP source {bsp.source!r} does not match indexed map {geometry.map_name!r} provider"
                )
        return build_bsp_entity_identity_index(bsp)

    raw = geometry_index.read_provider(override.selected)
    text = raw.split(b"\0", 1)[0].decode("latin-1")
    entities = parse_entities(text, source=override.selected.source)
    return build_entity_identity_index(
        entities,
        source=override.selected.source,
        source_kind=EntitySourceKind.ENT_OVERRIDE,
    )


def link_w3_entity_catalog(
    identities: BspEntityIdentityIndex,
    catalog: MapEntityCatalog,
) -> W3LinkedIdentityIndex:
    """Join W3 typed entities by their stable BSP entity index or fail closed."""

    if identities.source != catalog.bsp_source:
        raise ValueError(f"identity source {identities.source!r} does not match W3 source {catalog.bsp_source!r}")

    grouped_entities = (
        (W3EntityKind.SPAWN_POINT, catalog.spawn_points),
        (W3EntityKind.OBJECTIVE_VOLUME, catalog.objective_volumes),
        (W3EntityKind.OBJECTIVE_MARKER, catalog.objective_markers),
        (W3EntityKind.COLLISION_ENTITY, catalog.collision_entities),
    )
    references: list[W3EntityReference] = []
    seen_indices: set[int] = set()
    for kind, entities in grouped_entities:
        for entity in entities:
            entity_index = entity.entity_index
            if entity_index < 0 or entity_index >= len(identities.entities):
                raise ValueError(f"W3 {kind.value} references unknown BSP entity index {entity_index}")
            if entity_index in seen_indices:
                raise ValueError(f"BSP entity index {entity_index} appears in multiple W3 entity groups")

            identity = identities.entities[entity_index]
            if identity.entity_index != entity_index:
                raise ValueError(
                    f"identity tuple position {entity_index} contains entity index {identity.entity_index}"
                )
            if identity.classname != entity.classname:
                raise ValueError(
                    f"W3 entity {entity_index} classname {entity.classname!r} does not match "
                    f"BSP identity {identity.classname!r}"
                )

            seen_indices.add(entity_index)
            references.append(W3EntityReference(entity_index, entity.classname, kind))

    return W3LinkedIdentityIndex(
        map_name=catalog.map_name,
        identities=identities,
        catalog=catalog,
        references=tuple(sorted(references, key=lambda reference: reference.entity_index)),
    )
