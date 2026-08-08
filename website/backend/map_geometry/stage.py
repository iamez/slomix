"""Fail-closed W5a parsing for independently resolved ET stage assets.

This module exposes the possible script transitions. It does not claim that a
transition happened in a historical round, nor does it select one objective,
spawn or route as the live state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, NoReturn, TypeAlias

from website.backend.map_geometry.pk3_index import (
    AssetContentChangedError,
    MapAssetKind,
    MapAssetProvider,
    MapAssetResolution,
    Pk3GeometryIndex,
    Pk3IndexError,
)

# ET:Legacy q_shared.h: MAX_TOKEN_CHARS includes the trailing NUL byte.
_MAX_ET_TOKEN_LENGTH = 1023
# ET:Legacy G_ScriptAction_ObjectiveStatus accepts objective numbers 1..8.
_MAX_OBJECTIVES = 8
_BLOCK_ACTIONS = frozenset({"create", "delete", "set"})


class StageParseError(ValueError):
    """A stage asset cannot be represented without changing its semantics."""


class ObjectiveClass(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    ADDITIONAL = "additional"
    UNKNOWN = "unknown"


class ObjectiveTeam(StrEnum):
    AXIS = "axis"
    ALLIES = "allies"


class TriggerResolution(StrEnum):
    RESOLVED = "resolved"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    RUNTIME_DISPATCH = "runtime_dispatch"
    NO_OP = "no_op"


class TriggerDispatch(StrEnum):
    SELF = "self"
    SCRIPT_NAME = "script_name"
    GLOBAL = "global"
    PLAYER = "player"
    ACTIVATOR = "activator"


class StageLoadStatus(StrEnum):
    RESOLVED = "resolved"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    INVALID = "invalid"


class MainObjectiveSelectorForm(StrEnum):
    LEGACY_NUMERIC = "legacy_numeric"
    TARGET_NAME = "target_name"


@dataclass(frozen=True, slots=True)
class AssetCommand:
    command: str
    arguments: tuple[str, ...]
    line: int


@dataclass(frozen=True, slots=True)
class MapDescription:
    audience: str
    text: str
    line: int


@dataclass(frozen=True, slots=True)
class ObjectiveDescription:
    team: ObjectiveTeam
    number: int
    classification: ObjectiveClass
    text: str
    line: int


@dataclass(frozen=True, slots=True)
class ObjectiveCatalog:
    map_descriptions: tuple[MapDescription, ...]
    objectives: tuple[ObjectiveDescription, ...]
    other_commands: tuple[AssetCommand, ...]


@dataclass(frozen=True, slots=True)
class ScriptAction:
    command: str
    arguments: tuple[str, ...]
    line: int
    uses_braced_arguments: bool = False


@dataclass(frozen=True, slots=True)
class ScriptEvent:
    name: str
    parameters: tuple[str, ...]
    actions: tuple[ScriptAction, ...]
    line: int


@dataclass(frozen=True, slots=True)
class ScriptEntity:
    name: str
    events: tuple[ScriptEvent, ...]
    line: int


@dataclass(frozen=True, slots=True)
class MapScript:
    entities: tuple[ScriptEntity, ...]


@dataclass(frozen=True, slots=True)
class ObjectiveStatusEffect:
    objective_number: int
    team_code: int
    status_code: int
    line: int


@dataclass(frozen=True, slots=True)
class MainObjectiveEffect:
    """Possible selection whose legacy numeric form still needs live-build verification."""

    selector: str
    selector_form: MainObjectiveSelectorForm
    team_code: int
    line: int


@dataclass(frozen=True, slots=True)
class WinnerEffect:
    team_code: int
    line: int


@dataclass(frozen=True, slots=True)
class AutoSpawnEffect:
    spawn_description: str
    team_code: int
    line: int


@dataclass(frozen=True, slots=True)
class EntityStateEffect:
    target: str
    state: Literal["default", "invisible", "underconstruction"]
    line: int


@dataclass(frozen=True, slots=True)
class GotoMarkerEffect:
    target: str
    arguments: tuple[str, ...]
    line: int


@dataclass(frozen=True, slots=True)
class AlertEntityEffect:
    target: str
    line: int


@dataclass(frozen=True, slots=True)
class RoundEndEffect:
    line: int


StageEffect: TypeAlias = (
    ObjectiveStatusEffect
    | MainObjectiveEffect
    | WinnerEffect
    | AutoSpawnEffect
    | EntityStateEffect
    | GotoMarkerEffect
    | AlertEntityEffect
    | RoundEndEffect
)


@dataclass(frozen=True, slots=True)
class StageEventNode:
    node_id: str
    entity_name: str
    event_name: str
    event_parameters: tuple[str, ...]
    effects: tuple[StageEffect, ...]
    line: int


@dataclass(frozen=True, slots=True)
class TriggerEdge:
    source_node_id: str
    target_entity: str
    target_trigger: str
    candidate_node_ids: tuple[str, ...]
    dispatch: TriggerDispatch
    resolution: TriggerResolution
    line: int


@dataclass(frozen=True, slots=True)
class StaticStageGraph:
    nodes: tuple[StageEventNode, ...]
    trigger_edges: tuple[TriggerEdge, ...]


@dataclass(frozen=True, slots=True)
class StaticStageModel:
    map_name: str
    objectives: ObjectiveCatalog
    script: MapScript
    graph: StaticStageGraph
    script_provider: MapAssetProvider
    objdata_provider: MapAssetProvider


@dataclass(frozen=True, slots=True)
class StageLoadResult:
    map_name: str
    status: StageLoadStatus
    model: StaticStageModel | None
    script_resolution: MapAssetResolution
    objdata_resolution: MapAssetResolution
    reason: str | None = None


class _TokenKind(StrEnum):
    WORD = "word"
    NEWLINE = "newline"
    LEFT_BRACE = "left_brace"
    RIGHT_BRACE = "right_brace"


@dataclass(frozen=True, slots=True)
class _Token:
    kind: _TokenKind
    value: str
    line: int
    column: int


class _TokenStream:
    def __init__(self, tokens: tuple[_Token, ...], source: str) -> None:
        self.tokens = tokens
        self.source = source
        self.index = 0

    def peek(self) -> _Token | None:
        if self.index >= len(self.tokens):
            return None
        return self.tokens[self.index]

    def take(self) -> _Token:
        token = self.peek()
        if token is None:
            self.fail("unexpected end of file")
        self.index += 1
        return token

    def skip_newlines(self) -> None:
        while (token := self.peek()) is not None and token.kind is _TokenKind.NEWLINE:
            self.index += 1

    def expect(self, kind: _TokenKind, description: str) -> _Token:
        token = self.take()
        if token.kind is not kind:
            self.fail(f"expected {description}, found {token.value!r}", token)
        return token

    def fail(self, message: str, token: _Token | None = None) -> NoReturn:
        current = token or self.peek()
        location = f"{self.source}:{current.line}:{current.column}" if current else f"{self.source}:EOF"
        raise StageParseError(f"{location}: {message}")


def _decode_asset(raw: bytes, source: str) -> str:
    if b"\x00" in raw:
        raise StageParseError(f"{source}: NUL bytes are not valid stage text")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StageParseError(f"{source}: stage text is not valid UTF-8: {exc}") from exc


def _is_et_whitespace(character: str) -> bool:
    return ord(character) <= 32


def _lex(raw: bytes, source: str) -> tuple[_Token, ...]:
    text = _decode_asset(raw, source)
    tokens: list[_Token] = []
    index = 0
    line = 1
    column = 1

    def advance(character: str) -> None:
        nonlocal line, column
        if character == "\n":
            line += 1
            column = 1
        else:
            column += 1

    while index < len(text):
        character = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""

        if character == "\n":
            tokens.append(_Token(_TokenKind.NEWLINE, "\n", line, column))
            advance(character)
            index += 1
            continue
        if _is_et_whitespace(character):
            advance(character)
            index += 1
            continue
        if character == "/" and following == "/":
            while index < len(text) and text[index] != "\n":
                advance(text[index])
                index += 1
            continue
        if character == "/" and following == "*":
            start_line, start_column = line, column
            advance(character)
            advance(following)
            index += 2
            while index < len(text) and not (text[index] == "*" and index + 1 < len(text) and text[index + 1] == "/"):
                advance(text[index])
                index += 1
            if index >= len(text):
                raise StageParseError(f"{source}:{start_line}:{start_column}: unclosed block comment")
            advance(text[index])
            advance(text[index + 1])
            index += 2
            continue
        if character == '"':
            start_line, start_column = line, column
            advance(character)
            index += 1
            value: list[str] = []
            while index < len(text):
                character = text[index]
                following = text[index + 1] if index + 1 < len(text) else ""
                if character == "\\" and following == '"':
                    value.append('"')
                    advance(character)
                    advance(following)
                    index += 2
                    continue
                if character == '"':
                    advance(character)
                    index += 1
                    break
                value.append(character)
                advance(character)
                index += 1
            else:
                raise StageParseError(f"{source}:{start_line}:{start_column}: unclosed quoted string")
            joined = "".join(value)
            if len(joined.encode("utf-8")) > _MAX_ET_TOKEN_LENGTH:
                raise StageParseError(f"{source}:{start_line}:{start_column}: token exceeds ET's 1023-byte limit")
            tokens.append(_Token(_TokenKind.WORD, joined, start_line, start_column))
            continue

        start = index
        start_line, start_column = line, column
        # COM_ParseExt regular words include punctuation until ASCII whitespace.
        while index < len(text) and not _is_et_whitespace(text[index]):
            advance(text[index])
            index += 1
        word = text[start:index]
        if len(word.encode("utf-8")) > _MAX_ET_TOKEN_LENGTH:
            raise StageParseError(f"{source}:{start_line}:{start_column}: token exceeds ET's 1023-byte limit")
        kind = {
            "{": _TokenKind.LEFT_BRACE,
            "}": _TokenKind.RIGHT_BRACE,
        }.get(word, _TokenKind.WORD)
        tokens.append(_Token(kind, word, start_line, start_column))

    return tuple(tokens)


def _classification(text: str) -> ObjectiveClass:
    prefix = text.casefold().lstrip()
    if prefix.startswith(("primary objective:", "primary:")):
        return ObjectiveClass.PRIMARY
    if prefix.startswith(("secondary objective:", "secondary:")):
        return ObjectiveClass.SECONDARY
    if prefix.startswith(("additional objective:", "additional:")):
        return ObjectiveClass.ADDITIONAL
    return ObjectiveClass.UNKNOWN


def parse_objdata(raw: bytes, *, source: str = "<objdata>") -> ObjectiveCatalog:
    stream = _TokenStream(_lex(raw, source), source)
    commands: list[AssetCommand] = []
    current: list[_Token] = []
    while token := stream.peek():
        stream.index += 1
        if token.kind is _TokenKind.NEWLINE:
            if current:
                commands.append(
                    AssetCommand(
                        current[0].value.casefold(), tuple(item.value for item in current[1:]), current[0].line
                    )
                )
                current = []
            continue
        if token.kind is not _TokenKind.WORD:
            stream.fail("braces are not valid in objdata", token)
        current.append(token)
    if current:
        commands.append(
            AssetCommand(current[0].value.casefold(), tuple(item.value for item in current[1:]), current[0].line)
        )

    descriptions: list[MapDescription] = []
    objectives: list[ObjectiveDescription] = []
    other: list[AssetCommand] = []
    seen: dict[tuple[ObjectiveTeam, int], ObjectiveDescription] = {}
    objective_commands = {
        "wm_objective_axis_desc": ObjectiveTeam.AXIS,
        "wm_objective_allied_desc": ObjectiveTeam.ALLIES,
    }
    for command in commands:
        if command.command == "wm_mapdescription":
            if len(command.arguments) != 2:
                raise StageParseError(f"{source}:{command.line}: wm_mapdescription requires exactly 2 arguments")
            descriptions.append(MapDescription(command.arguments[0].casefold(), command.arguments[1], command.line))
            continue
        team = objective_commands.get(command.command)
        if team is None:
            other.append(command)
            continue
        if len(command.arguments) != 2:
            raise StageParseError(f"{source}:{command.line}: {command.command} requires exactly 2 arguments")
        try:
            number = int(command.arguments[0])
        except ValueError as exc:
            raise StageParseError(f"{source}:{command.line}: objective number must be an integer") from exc
        if not 1 <= number <= _MAX_OBJECTIVES:
            raise StageParseError(f"{source}:{command.line}: objective number must be between 1 and {_MAX_OBJECTIVES}")
        objective = ObjectiveDescription(
            team, number, _classification(command.arguments[1]), command.arguments[1], command.line
        )
        identity = (team, number)
        if identity in seen:
            raise StageParseError(f"{source}:{command.line}: duplicate {team.value} objective {number}")
        seen[identity] = objective
        objectives.append(objective)

    return ObjectiveCatalog(tuple(descriptions), tuple(objectives), tuple(other))


def parse_map_script(raw: bytes, *, source: str = "<script>") -> MapScript:
    stream = _TokenStream(_lex(raw, source), source)
    entities: list[ScriptEntity] = []
    while True:
        stream.skip_newlines()
        if stream.peek() is None:
            break
        name = stream.expect(_TokenKind.WORD, "an entity name")
        if name.value.casefold() == "entity":
            stream.skip_newlines()
            name = stream.expect(_TokenKind.WORD, "an entity name after 'entity'")
        stream.skip_newlines()
        stream.expect(_TokenKind.LEFT_BRACE, "'{' after the entity name")
        events: list[ScriptEvent] = []
        while True:
            stream.skip_newlines()
            token = stream.peek()
            if token is None:
                stream.fail(f"unclosed entity {name.value!r}")
            if token.kind is _TokenKind.RIGHT_BRACE:
                stream.index += 1
                break
            event_name = stream.expect(_TokenKind.WORD, "an event name")
            parameters: list[str] = []
            while True:
                token = stream.take()
                if token.kind is _TokenKind.LEFT_BRACE:
                    break
                if token.kind is _TokenKind.RIGHT_BRACE:
                    stream.fail("event parameters ended with '}' instead of '{'", token)
                if token.kind is _TokenKind.WORD:
                    parameters.append(token.value)
            actions: list[ScriptAction] = []
            while True:
                stream.skip_newlines()
                token = stream.peek()
                if token is None:
                    stream.fail(f"unclosed event {event_name.value!r}")
                if token.kind is _TokenKind.RIGHT_BRACE:
                    stream.index += 1
                    break
                action_name = stream.expect(_TokenKind.WORD, "an action name")
                command = action_name.value.casefold()
                arguments: list[str] = []
                braced = command in _BLOCK_ACTIONS
                if braced:
                    stream.skip_newlines()
                    stream.expect(_TokenKind.LEFT_BRACE, "'{' after set/create/delete")
                    while True:
                        token = stream.take()
                        if token.kind is _TokenKind.RIGHT_BRACE:
                            break
                        if token.kind is _TokenKind.LEFT_BRACE:
                            stream.fail("nested action argument blocks are not supported by ET", token)
                        if token.kind is _TokenKind.WORD:
                            arguments.append(token.value)
                else:
                    while token := stream.peek():
                        if token.kind is _TokenKind.NEWLINE:
                            break
                        if token.kind is _TokenKind.RIGHT_BRACE:
                            stream.fail("normal action must end at a newline before '}'", token)
                        if token.kind is _TokenKind.LEFT_BRACE:
                            stream.fail("unexpected '{' in action arguments", token)
                        arguments.append(stream.take().value)
                actions.append(ScriptAction(command, tuple(arguments), action_name.line, braced))
            events.append(ScriptEvent(event_name.value.casefold(), tuple(parameters), tuple(actions), event_name.line))
        entities.append(ScriptEntity(name.value, tuple(events), name.line))

    return MapScript(tuple(entities))


def _integer(argument: str, *, source: str, line: int, field: str) -> int:
    try:
        return int(argument)
    except ValueError as exc:
        raise StageParseError(f"{source}:{line}: {field} must be an integer") from exc


def _exact_arguments(action: ScriptAction, count: int, source: str) -> None:
    if len(action.arguments) != count:
        raise StageParseError(f"{source}:{action.line}: {action.command} requires exactly {count} arguments")


def _effect_for(action: ScriptAction, source: str) -> StageEffect | None:
    if action.command == "wm_objective_status":
        _exact_arguments(action, 3, source)
        number = _integer(action.arguments[0], source=source, line=action.line, field="objective number")
        team = _integer(action.arguments[1], source=source, line=action.line, field="objective team")
        status = _integer(action.arguments[2], source=source, line=action.line, field="objective status")
        if not 1 <= number <= _MAX_OBJECTIVES or team not in {0, 1} or status not in {0, 1, 2}:
            raise StageParseError(f"{source}:{action.line}: invalid wm_objective_status codes {action.arguments!r}")
        return ObjectiveStatusEffect(number, team, status, action.line)
    if action.command == "wm_set_main_objective":
        _exact_arguments(action, 2, source)
        team = _integer(action.arguments[1], source=source, line=action.line, field="main-objective team")
        if team not in {0, 1}:
            raise StageParseError(f"{source}:{action.line}: invalid main-objective team {team}")
        selector = action.arguments[0]
        selector_form = (
            MainObjectiveSelectorForm.LEGACY_NUMERIC
            if selector.lstrip("-").isdigit()
            else MainObjectiveSelectorForm.TARGET_NAME
        )
        return MainObjectiveEffect(selector, selector_form, team, action.line)
    if action.command == "wm_setwinner":
        _exact_arguments(action, 1, source)
        team = _integer(action.arguments[0], source=source, line=action.line, field="winner team")
        if team not in {-1, 0, 1}:
            raise StageParseError(f"{source}:{action.line}: invalid winner team {team}")
        return WinnerEffect(team, action.line)
    if action.command == "setautospawn":
        _exact_arguments(action, 2, source)
        team = _integer(action.arguments[1], source=source, line=action.line, field="autospawn team")
        if team not in {0, 1}:
            raise StageParseError(f"{source}:{action.line}: invalid autospawn team {team}")
        return AutoSpawnEffect(action.arguments[0], team, action.line)
    if action.command == "setstate":
        _exact_arguments(action, 2, source)
        state = action.arguments[1].casefold()
        if state not in {"default", "invisible", "underconstruction"}:
            raise StageParseError(f"{source}:{action.line}: invalid setstate state {state!r}")
        return EntityStateEffect(action.arguments[0], state, action.line)
    if action.command == "gotomarker":
        if len(action.arguments) < 2:
            raise StageParseError(f"{source}:{action.line}: gotomarker requires a target and speed")
        return GotoMarkerEffect(action.arguments[0], action.arguments[1:], action.line)
    if action.command == "alertentity":
        _exact_arguments(action, 1, source)
        return AlertEntityEffect(action.arguments[0], action.line)
    if action.command == "wm_endround":
        _exact_arguments(action, 0, source)
        return RoundEndEffect(action.line)
    return None


def compile_static_stage_graph(script: MapScript, *, source: str = "<script>") -> StaticStageGraph:
    nodes: list[StageEventNode] = []
    events_by_trigger: dict[tuple[str, str], list[str]] = {}
    indexed_events: list[tuple[ScriptEntity, ScriptEvent, str]] = []
    for entity in script.entities:
        for event in entity.events:
            node_id = f"event:{len(indexed_events)}"
            effects = tuple(effect for action in event.actions if (effect := _effect_for(action, source)) is not None)
            nodes.append(StageEventNode(node_id, entity.name, event.name, event.parameters, effects, event.line))
            indexed_events.append((entity, event, node_id))
            if event.name == "trigger" and len(event.parameters) == 1:
                key = (entity.name.casefold(), event.parameters[0].casefold())
                events_by_trigger.setdefault(key, []).append(node_id)

    edges: list[TriggerEdge] = []
    for entity, event, node_id in indexed_events:
        for action in event.actions:
            if action.command != "trigger":
                continue
            _exact_arguments(action, 2, source)
            raw_target = action.arguments[0]
            target_kind = raw_target.casefold()
            target_trigger = action.arguments[1]
            if target_kind == "self":
                dispatch = TriggerDispatch.SELF
                target_entity = entity.name
                candidates = tuple(events_by_trigger.get((target_entity.casefold(), target_trigger.casefold()), ()))
            elif target_kind == "global":
                dispatch = TriggerDispatch.GLOBAL
                target_entity = raw_target
                candidates = tuple(
                    candidate
                    for (candidate_entity, candidate_trigger), node_ids in events_by_trigger.items()
                    if candidate_trigger == target_trigger.casefold()
                    for candidate in node_ids
                )
            elif target_kind in {"player", "activator"}:
                dispatch = TriggerDispatch(target_kind)
                target_entity = raw_target
                candidates = ()
            else:
                dispatch = TriggerDispatch.SCRIPT_NAME
                target_entity = raw_target
                candidates = tuple(events_by_trigger.get((target_entity.casefold(), target_trigger.casefold()), ()))

            if dispatch is TriggerDispatch.ACTIVATOR:
                resolution = TriggerResolution.NO_OP
            elif dispatch in {TriggerDispatch.GLOBAL, TriggerDispatch.PLAYER}:
                resolution = TriggerResolution.RUNTIME_DISPATCH
            elif len(candidates) == 1:
                resolution = TriggerResolution.RESOLVED
            elif candidates:
                resolution = TriggerResolution.AMBIGUOUS
            else:
                resolution = TriggerResolution.MISSING
            edges.append(
                TriggerEdge(
                    node_id,
                    target_entity,
                    target_trigger,
                    candidates,
                    dispatch,
                    resolution,
                    action.line,
                )
            )

    return StaticStageGraph(tuple(nodes), tuple(edges))


def load_static_stage(index: Pk3GeometryIndex, map_name: str) -> StageLoadResult:
    script_resolution = index.resolve_asset(map_name, MapAssetKind.SCRIPT)
    objdata_resolution = index.resolve_asset(map_name, MapAssetKind.OBJDATA)
    normalised = script_resolution.map_name
    resolutions = (script_resolution, objdata_resolution)
    if any(item.status == "ambiguous" for item in resolutions):
        return StageLoadResult(
            normalised,
            StageLoadStatus.AMBIGUOUS,
            None,
            script_resolution,
            objdata_resolution,
            "script or objdata has byte-distinct providers without verified live precedence",
        )
    if any(item.status == "missing" for item in resolutions):
        return StageLoadResult(
            normalised,
            StageLoadStatus.MISSING,
            None,
            script_resolution,
            objdata_resolution,
            "script and objdata must both resolve independently",
        )

    script_provider = script_resolution.selected
    objdata_provider = objdata_resolution.selected
    if script_provider is None or objdata_provider is None:
        raise RuntimeError("resolved stage assets must have selected providers")
    try:
        script = parse_map_script(index.read_provider(script_provider), source=script_provider.source)
        objectives = parse_objdata(index.read_provider(objdata_provider), source=objdata_provider.source)
        graph = compile_static_stage_graph(script, source=script_provider.source)
    except (StageParseError, AssetContentChangedError, Pk3IndexError) as exc:
        return StageLoadResult(
            normalised,
            StageLoadStatus.INVALID,
            None,
            script_resolution,
            objdata_resolution,
            str(exc),
        )
    model = StaticStageModel(normalised, objectives, script, graph, script_provider, objdata_provider)
    return StageLoadResult(
        normalised,
        StageLoadStatus.RESOLVED,
        model,
        script_resolution,
        objdata_resolution,
    )
