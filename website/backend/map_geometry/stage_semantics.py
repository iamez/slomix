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
from typing import Literal

from website.backend.map_geometry.bsp import BspFile

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
class BspEntityIdentityIndex:
    entities: tuple[BspEntityIdentity, ...]
    source: str = ""
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
            entity.entity_index
            for entity in self.entities
            if _ascii_equal(_identity_value(entity, namespace), value)
        )


def _ascii_fold(value: str) -> str:
    return "".join(chr(ord(character) + 32) if "A" <= character <= "Z" else character for character in value)


def _ascii_equal(left: str | None, right: str) -> bool:
    return left is not None and _ascii_fold(left) == _ascii_fold(right)


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


def build_entity_identity_index(
    entities: tuple[dict[str, str], ...],
    *,
    source: str = "",
) -> BspEntityIdentityIndex:
    """Build a deterministic W5b identity index in BSP entity order."""

    return BspEntityIdentityIndex(
        entities=tuple(_entity_identity(index, entity) for index, entity in enumerate(entities)),
        source=source,
    )


def build_bsp_entity_identity_index(bsp: BspFile) -> BspEntityIdentityIndex:
    return build_entity_identity_index(bsp.entities, source=bsp.source)
