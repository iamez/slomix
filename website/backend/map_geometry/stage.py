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
# ET:Legacy q_shared.h: MAX_INFO_STRING includes the trailing NUL byte.
_MAX_ET_PARAMETER_LENGTH = 1023
# ET:Legacy G_ScriptAction_ObjectiveStatus accepts objective numbers 1..8.
_MAX_OBJECTIVES = 8
_BLOCK_ACTIONS = frozenset({"create", "delete", "set"})
_ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
_ET_WHITESPACE = "".join(chr(value) for value in range(33))
# ET:Legacy g_script.c: gScriptEvents and gScriptActions.
_ET_SCRIPT_EVENTS = frozenset(
    {
        "spawn",
        "trigger",
        "pain",
        "death",
        "activate",
        "stopcam",
        "playerstart",
        "built",
        "buildstart",
        "decayed",
        "destroyed",
        "rebirth",
        "failed",
        "dynamited",
        "defused",
        "mg42",
        "message",
        "exploded",
    }
)
_ET_SCRIPT_ACTIONS = frozenset(
    {
        "gotomarker",
        "playsound",
        "playanim",
        "wait",
        "trigger",
        "alertentity",
        "togglespeaker",
        "disablespeaker",
        "enablespeaker",
        "accum",
        "globalaccum",
        "print",
        "faceangles",
        "resetscript",
        "attachtotag",
        "halt",
        "stopsound",
        "entityscriptname",
        "wm_axis_respawntime",
        "wm_allied_respawntime",
        "wm_number_of_objectives",
        "wm_setwinner",
        "wm_set_defending_team",
        "wm_announce",
        "wm_teamvoiceannounce",
        "wm_addteamvoiceannounce",
        "wm_removeteamvoiceannounce",
        "wm_announce_icon",
        "wm_endround",
        "wm_set_round_timelimit",
        "wm_voiceannounce",
        "wm_objective_status",
        "wm_set_main_objective",
        "remove",
        "setstate",
        "followspline",
        "followpath",
        "abortmove",
        "setspeed",
        "setrotation",
        "stoprotation",
        "startanimation",
        "attatchtotrain",
        "freezeanimation",
        "unfreezeanimation",
        "remapshader",
        "remapshaderflush",
        "changemodel",
        "setchargetimefactor",
        "setdamagable",
        "repairmg42",
        "sethqstatus",
        "printaccum",
        "printglobalaccum",
        "cvar",
        "abortifwarmup",
        "abortifnotsingleplayer",
        "mu_start",
        "mu_play",
        "mu_stop",
        "mu_queue",
        "mu_fade",
        "setdebuglevel",
        "setposition",
        "setautospawn",
        "setmodelfrombrushmodel",
        "fadeallsounds",
        "construct",
        "spawnrubble",
        "setglobalfog",
        "allowtankexit",
        "allowtankenter",
        "settankammo",
        "addtankammo",
        "kill",
        "disablemessage",
        "set",
        "create",
        "delete",
        "constructible_class",
        "constructible_chargebarreq",
        "constructible_constructxpbonus",
        "constructible_destructxpbonus",
        "constructible_health",
        "constructible_weaponclass",
        "constructible_duration",
    }
)


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
    serialized_parameters: str
    line: int
    uses_braced_arguments: bool = False


@dataclass(frozen=True, slots=True)
class ScriptEvent:
    name: str
    parameters: tuple[str, ...]
    actions: tuple[ScriptAction, ...]
    line: int


@dataclass(frozen=True, slots=True)
class ScriptRegistryIssue:
    kind: Literal["event", "action"]
    name: str
    line: int


@dataclass(frozen=True, slots=True)
class ScriptSyntaxIssue:
    token: str
    line: int
    reason: str


@dataclass(frozen=True, slots=True)
class ScriptEntity:
    name: str
    events: tuple[ScriptEvent, ...]
    line: int
    registry_issue: ScriptRegistryIssue | None = None
    syntax_issue: ScriptSyntaxIssue | None = None


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
class OpaqueScriptEntity:
    entity_index: int
    entity_name: str
    issue_kind: Literal["registry_event", "registry_action", "syntax", "projection", "shadowed"]
    token: str
    line: int
    reason: str


@dataclass(frozen=True, slots=True)
class StaticStageGraph:
    nodes: tuple[StageEventNode, ...]
    trigger_edges: tuple[TriggerEdge, ...]
    opaque_entities: tuple[OpaqueScriptEntity, ...] = ()


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


@dataclass(frozen=True, slots=True)
class _ScriptEntityParse:
    entity: ScriptEntity
    consumed: int | None
    boundary_ambiguous: bool


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
    return raw.decode("utf-8", errors="surrogateescape")


def _encode_asset(text: str) -> bytes:
    return text.encode("utf-8", errors="surrogateescape")


def _et_byte_length(text: str) -> int:
    return len(_encode_asset(text))


def _is_et_whitespace(character: str) -> bool:
    return ord(character) <= 32


def _ascii_fold(value: str) -> str:
    return value.translate(_ASCII_LOWER)


def _is_ascii_decimal(value: str) -> bool:
    digits = value[1:] if value[:1] in {"+", "-"} else value
    return bool(digits) and all("0" <= character <= "9" for character in digits)


def _serialized_parameter_length(values: list[str], *, quote_embedded_spaces: bool) -> int:
    total = max(0, len(values) - 1)
    for value in values:
        total += _et_byte_length(value)
        if quote_embedded_spaces and " " in value:
            total += 2
    return total


def _serialize_action_parameters(values: list[str]) -> str:
    return " ".join(f'"{value}"' if " " in value else value for value in values)


def _token_kind(value: str) -> _TokenKind:
    if value.startswith("{"):
        return _TokenKind.LEFT_BRACE
    if value.startswith("}"):
        return _TokenKind.RIGHT_BRACE
    return _TokenKind.WORD


def _lex(raw: bytes, source: str, *, structural_braces: bool) -> tuple[_Token, ...]:
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
            nested = False
            while index < len(text):
                character = text[index]
                following = text[index + 1] if index + 1 < len(text) else ""
                if character == "\\" and following == '"':
                    value.append('"')
                    advance(character)
                    advance(following)
                    index += 2
                    nested = not nested
                    continue
                if character == '"' and not nested:
                    advance(character)
                    index += 1
                    break
                value.append(character)
                advance(character)
                index += 1
            else:
                raise StageParseError(f"{source}:{start_line}:{start_column}: unclosed quoted string")
            joined = "".join(value)
            if not joined:
                raise StageParseError(
                    f"{source}:{start_line}:{start_column}: empty quoted tokens are engine control boundaries"
                )
            if _et_byte_length(joined) > _MAX_ET_TOKEN_LENGTH:
                raise StageParseError(f"{source}:{start_line}:{start_column}: token exceeds ET's 1023-byte limit")
            kind = _token_kind(joined) if structural_braces else _TokenKind.WORD
            tokens.append(_Token(kind, joined, start_line, start_column))
            continue

        start = index
        start_line, start_column = line, column
        # COM_ParseExt regular words include punctuation until ASCII whitespace.
        while index < len(text) and not _is_et_whitespace(text[index]):
            advance(text[index])
            index += 1
        word = text[start:index]
        if _et_byte_length(word) > _MAX_ET_TOKEN_LENGTH:
            raise StageParseError(f"{source}:{start_line}:{start_column}: token exceeds ET's 1023-byte limit")
        kind = _token_kind(word) if structural_braces else _TokenKind.WORD
        tokens.append(_Token(kind, word, start_line, start_column))

    return tuple(tokens)


def _classification(text: str) -> ObjectiveClass:
    prefix = _ascii_fold(text).lstrip(_ET_WHITESPACE)
    if prefix.startswith(("primary objective:", "primary:")):
        return ObjectiveClass.PRIMARY
    if prefix.startswith(("secondary objective:", "secondary:")):
        return ObjectiveClass.SECONDARY
    if prefix.startswith(("additional objective:", "additional:")):
        return ObjectiveClass.ADDITIONAL
    return ObjectiveClass.UNKNOWN


def parse_objdata(raw: bytes, *, source: str = "<objdata>") -> ObjectiveCatalog:
    stream = _TokenStream(_lex(raw, source, structural_braces=False), source)
    commands: list[AssetCommand] = []
    command_arities = {
        "wm_mapdescription": 2,
        "wm_objective_axis_desc": 2,
        "wm_objective_allied_desc": 2,
    }

    def take_word(description: str) -> _Token:
        stream.skip_newlines()
        return stream.expect(_TokenKind.WORD, description)

    while True:
        stream.skip_newlines()
        if stream.peek() is None:
            break
        command_token = stream.expect(_TokenKind.WORD, "an objdata command")
        command = _ascii_fold(command_token.value)
        arguments = tuple(
            take_word(f"argument {index + 1} for {command}").value
            for index in range(command_arities.get(command, 0))
        )
        commands.append(AssetCommand(command, arguments, command_token.line))

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
            descriptions.append(MapDescription(_ascii_fold(command.arguments[0]), command.arguments[1], command.line))
            continue
        team = objective_commands.get(command.command)
        if team is None:
            other.append(command)
            continue
        if len(command.arguments) != 2:
            raise StageParseError(f"{source}:{command.line}: {command.command} requires exactly 2 arguments")
        try:
            if not _is_ascii_decimal(command.arguments[0]):
                raise ValueError
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


def _parse_script_entity(name: _Token, tokens: tuple[_Token, ...], source: str) -> _ScriptEntityParse:
    stream = _TokenStream(tokens, source)
    events: list[ScriptEvent] = []
    issue_token = name
    boundary_ambiguous = False
    try:
        while True:
            stream.skip_newlines()
            token = stream.peek()
            if token is None:
                stream.fail(f"unclosed entity {name.value!r}", name)
            if token.kind is _TokenKind.RIGHT_BRACE:
                stream.index += 1
                return _ScriptEntityParse(
                    ScriptEntity(name.value, tuple(events), name.line),
                    stream.index,
                    boundary_ambiguous,
                )

            event_name = stream.expect(_TokenKind.WORD, "an event name")
            issue_token = event_name
            event = _ascii_fold(event_name.value)
            if event not in _ET_SCRIPT_EVENTS:
                return _ScriptEntityParse(
                    ScriptEntity(
                        name.value,
                        tuple(events),
                        name.line,
                        ScriptRegistryIssue("event", event_name.value, event_name.line),
                    ),
                    None,
                    boundary_ambiguous,
                )

            parameters: list[str] = []
            while True:
                if stream.peek() is None:
                    stream.fail(f"event {event_name.value!r} reached the entity boundary before '{{'", event_name)
                token = stream.take()
                if token.kind is _TokenKind.LEFT_BRACE:
                    break
                if token.kind is _TokenKind.RIGHT_BRACE:
                    boundary_ambiguous = True
                if token.kind is not _TokenKind.NEWLINE:
                    parameters.append(token.value)
            if _serialized_parameter_length(parameters, quote_embedded_spaces=False) > _MAX_ET_PARAMETER_LENGTH:
                stream.fail("event parameters exceed ET's 1023-byte aggregate limit", event_name)

            actions: list[ScriptAction] = []
            while True:
                stream.skip_newlines()
                token = stream.peek()
                if token is None:
                    stream.fail(f"unclosed event {event_name.value!r}", event_name)
                if token.kind is _TokenKind.RIGHT_BRACE:
                    stream.index += 1
                    break

                action_name = stream.expect(_TokenKind.WORD, "an action name")
                issue_token = action_name
                command = _ascii_fold(action_name.value)
                if command not in _ET_SCRIPT_ACTIONS:
                    return _ScriptEntityParse(
                        ScriptEntity(
                            name.value,
                            tuple(events),
                            name.line,
                            ScriptRegistryIssue("action", action_name.value, action_name.line),
                        ),
                        None,
                        boundary_ambiguous,
                    )

                arguments: list[str] = []
                braced = command in _BLOCK_ACTIONS
                if braced:
                    stream.skip_newlines()
                    stream.expect(_TokenKind.LEFT_BRACE, f"'{{' after {command}")
                    while True:
                        token = stream.take()
                        if token.kind is _TokenKind.RIGHT_BRACE:
                            break
                        if token.kind is _TokenKind.LEFT_BRACE:
                            boundary_ambiguous = True
                        if token.kind is not _TokenKind.NEWLINE:
                            arguments.append(token.value)
                else:
                    while token := stream.peek():
                        if token.kind is _TokenKind.NEWLINE:
                            break
                        if token.kind in {_TokenKind.LEFT_BRACE, _TokenKind.RIGHT_BRACE}:
                            boundary_ambiguous = True
                        arguments.append(stream.take().value)
                if _serialized_parameter_length(arguments, quote_embedded_spaces=True) > _MAX_ET_PARAMETER_LENGTH:
                    stream.fail("action parameters exceed ET's 1023-byte aggregate limit", action_name)
                actions.append(
                    ScriptAction(
                        command,
                        tuple(arguments),
                        _serialize_action_parameters(arguments),
                        action_name.line,
                        braced,
                    )
                )
            events.append(ScriptEvent(event, tuple(parameters), tuple(actions), event_name.line))
    except StageParseError as exc:
        return _ScriptEntityParse(
            ScriptEntity(
                name.value,
                tuple(events),
                name.line,
                syntax_issue=ScriptSyntaxIssue(issue_token.value, issue_token.line, str(exc)),
            ),
            None,
            boundary_ambiguous,
        )


def _skipped_entity_end(tokens: tuple[_Token, ...], start: int) -> int | None:
    depth = 1
    index = start
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if token.kind is _TokenKind.LEFT_BRACE:
            depth += 1
        elif token.kind is _TokenKind.RIGHT_BRACE:
            depth -= 1
            if depth == 0:
                return index
    return None


def _with_boundary_issue(entity: ScriptEntity, name: _Token, source: str) -> ScriptEntity:
    return ScriptEntity(
        entity.name,
        entity.events,
        entity.line,
        syntax_issue=ScriptSyntaxIssue(
            name.value,
            name.line,
            f"{source}:{name.line}:{name.column}: entity boundary depends on selected-block brace interpretation",
        ),
    )


def parse_map_script(raw: bytes, *, source: str = "<script>") -> MapScript:
    stream = _TokenStream(_lex(raw, source, structural_braces=True), source)
    entities: list[ScriptEntity] = []
    while True:
        stream.skip_newlines()
        if stream.peek() is None:
            break
        name = stream.expect(_TokenKind.WORD, "an entity name")
        while _ascii_fold(name.value) == "entity":
            stream.skip_newlines()
            name = stream.expect(_TokenKind.WORD, "an entity name after 'entity'")
        stream.skip_newlines()
        stream.expect(_TokenKind.LEFT_BRACE, "'{' after the entity name")

        body_start = stream.index
        skipped_end = _skipped_entity_end(stream.tokens, body_start)
        selected = _parse_script_entity(name, stream.tokens[body_start:], source)
        selected_end = body_start + selected.consumed if selected.consumed is not None else None

        if selected.boundary_ambiguous:
            if selected_end is not None and skipped_end == selected_end:
                entities.append(selected.entity)
                stream.index = selected_end
                continue
            entities.append(_with_boundary_issue(selected.entity, name, source))
            if selected_end is None and skipped_end is not None:
                stream.index = skipped_end
                continue
            break

        if selected_end is not None:
            if skipped_end != selected_end:
                entities.append(_with_boundary_issue(selected.entity, name, source))
                break
            entities.append(selected.entity)
            stream.index = selected_end
            continue

        if skipped_end is None:
            stream.fail(f"unclosed entity {name.value!r}", name)
        entities.append(selected.entity)
        stream.index = skipped_end

    return MapScript(tuple(entities))


def _integer(argument: str, *, source: str, line: int, field: str) -> int:
    if not _is_ascii_decimal(argument):
        raise StageParseError(f"{source}:{line}: {field} must be a canonical ASCII integer")
    try:
        return int(argument)
    except ValueError as exc:
        raise StageParseError(f"{source}:{line}: {field} must be an integer") from exc


def _callback_arguments(action: ScriptAction, source: str) -> tuple[str, ...]:
    tokens = _lex(
        _encode_asset(action.serialized_parameters),
        f"{source}:{action.line}:{action.command}:params",
        structural_braces=False,
    )
    allow_line_breaks = action.command in {"wm_objective_status", "wm_set_main_objective", "wm_setwinner"}
    arguments: list[str] = []
    for token in tokens:
        if token.kind is _TokenKind.NEWLINE:
            if allow_line_breaks:
                continue
            break
        arguments.append(token.value)
    return tuple(arguments)


def _required_arguments(action: ScriptAction, arguments: tuple[str, ...], count: int, source: str) -> None:
    if len(arguments) < count:
        raise StageParseError(f"{source}:{action.line}: {action.command} requires at least {count} arguments")


def _effect_for(action: ScriptAction, source: str) -> StageEffect | None:
    if action.command == "alertentity":
        if not action.serialized_parameters:
            raise StageParseError(f"{source}:{action.line}: alertentity requires a target")
        return AlertEntityEffect(action.serialized_parameters, action.line)
    if action.command == "wm_endround":
        return RoundEndEffect(action.line)
    if action.command not in {
        "gotomarker",
        "setautospawn",
        "setstate",
        "wm_objective_status",
        "wm_set_main_objective",
        "wm_setwinner",
    }:
        return None

    arguments = _callback_arguments(action, source)
    if action.command == "wm_objective_status":
        _required_arguments(action, arguments, 3, source)
        number = _integer(arguments[0], source=source, line=action.line, field="objective number")
        team = _integer(arguments[1], source=source, line=action.line, field="objective team")
        status = _integer(arguments[2], source=source, line=action.line, field="objective status")
        if not 1 <= number <= _MAX_OBJECTIVES or team not in {0, 1} or status not in {0, 1, 2}:
            raise StageParseError(f"{source}:{action.line}: invalid wm_objective_status codes {arguments!r}")
        return ObjectiveStatusEffect(number, team, status, action.line)
    if action.command == "wm_set_main_objective":
        _required_arguments(action, arguments, 2, source)
        team = _integer(arguments[1], source=source, line=action.line, field="main-objective team")
        if team not in {0, 1}:
            raise StageParseError(f"{source}:{action.line}: invalid main-objective team {team}")
        selector = arguments[0]
        selector_form = (
            MainObjectiveSelectorForm.LEGACY_NUMERIC
            if _is_ascii_decimal(selector)
            else MainObjectiveSelectorForm.TARGET_NAME
        )
        return MainObjectiveEffect(selector, selector_form, team, action.line)
    if action.command == "wm_setwinner":
        _required_arguments(action, arguments, 1, source)
        team = _integer(arguments[0], source=source, line=action.line, field="winner team")
        if team not in {-1, 0, 1}:
            raise StageParseError(f"{source}:{action.line}: invalid winner team {team}")
        return WinnerEffect(team, action.line)
    if action.command == "setautospawn":
        _required_arguments(action, arguments, 2, source)
        team = _integer(arguments[1], source=source, line=action.line, field="autospawn team")
        if team not in {0, 1}:
            raise StageParseError(f"{source}:{action.line}: invalid autospawn team {team}")
        return AutoSpawnEffect(arguments[0], team, action.line)
    if action.command == "setstate":
        _required_arguments(action, arguments, 2, source)
        state = _ascii_fold(arguments[1])
        if state not in {"default", "invisible", "underconstruction"}:
            raise StageParseError(f"{source}:{action.line}: invalid setstate state {state!r}")
        return EntityStateEffect(arguments[0], state, action.line)
    if action.command == "gotomarker":
        _required_arguments(action, arguments, 2, source)
        return GotoMarkerEffect(arguments[0], arguments[1:], action.line)
    return None


def _first_trigger_handler(handlers: list[tuple[str | None, str]], trigger_name: str) -> str | None:
    folded_trigger = _ascii_fold(trigger_name)
    for handler_name, node_id in handlers:
        if handler_name is None or handler_name == folded_trigger:
            return node_id
    return None


def compile_static_stage_graph(script: MapScript, *, source: str = "<script>") -> StaticStageGraph:
    eligible_entities: set[int] = set()
    effects_by_event: dict[tuple[int, int], tuple[StageEffect, ...]] = {}
    opaque_entities: list[OpaqueScriptEntity] = []
    seen_entity_names: set[str] = set()
    for entity_index, entity in enumerate(script.entities):
        folded_entity_name = _ascii_fold(entity.name)
        if folded_entity_name in seen_entity_names:
            opaque_entities.append(
                OpaqueScriptEntity(
                    entity_index,
                    entity.name,
                    "shadowed",
                    entity.name,
                    entity.line,
                    f"{source}:{entity.line}: later duplicate entity block is unreachable by ET's first-match parser",
                )
            )
            continue
        seen_entity_names.add(folded_entity_name)
        if issue := entity.registry_issue:
            issue_kind: Literal["registry_event", "registry_action"] = (
                "registry_event" if issue.kind == "event" else "registry_action"
            )
            opaque_entities.append(
                OpaqueScriptEntity(
                    entity_index,
                    entity.name,
                    issue_kind,
                    issue.name,
                    issue.line,
                    f"{source}:{issue.line}: unknown ET script {issue.kind} {issue.name!r}",
                )
            )
            continue
        if issue := entity.syntax_issue:
            opaque_entities.append(
                OpaqueScriptEntity(
                    entity_index,
                    entity.name,
                    "syntax",
                    issue.token,
                    issue.line,
                    issue.reason,
                )
            )
            continue

        projection_issue: OpaqueScriptEntity | None = None
        for event_index, event in enumerate(entity.events):
            effects: list[StageEffect] = []
            for action in event.actions:
                try:
                    if effect := _effect_for(action, source):
                        effects.append(effect)
                    if action.command == "trigger":
                        _required_arguments(action, _callback_arguments(action, source), 2, source)
                except StageParseError as exc:
                    projection_issue = OpaqueScriptEntity(
                        entity_index,
                        entity.name,
                        "projection",
                        action.command,
                        action.line,
                        str(exc),
                    )
                    break
            if projection_issue is not None:
                break
            effects_by_event[(entity_index, event_index)] = tuple(effects)

        if projection_issue is not None:
            opaque_entities.append(projection_issue)
        else:
            eligible_entities.add(entity_index)

    nodes: list[StageEventNode] = []
    handlers_by_entity: dict[str, list[tuple[str | None, str]]] = {}
    self_handlers: dict[int, list[tuple[str | None, str]]] = {}
    indexed_events: list[tuple[int, ScriptEntity, ScriptEvent, str]] = []
    for entity_index, entity in enumerate(script.entities):
        if entity_index not in eligible_entities:
            continue
        for event_index, event in enumerate(entity.events):
            node_id = f"event:{len(indexed_events)}"
            effects = effects_by_event[(entity_index, event_index)]
            nodes.append(StageEventNode(node_id, entity.name, event.name, event.parameters, effects, event.line))
            indexed_events.append((entity_index, entity, event, node_id))
            if event.name == "trigger":
                trigger_name = _ascii_fold(" ".join(event.parameters)) if event.parameters else None
                handlers_by_entity.setdefault(_ascii_fold(entity.name), []).append((trigger_name, node_id))
                self_handlers.setdefault(entity_index, []).append((trigger_name, node_id))

    edges: list[TriggerEdge] = []
    for entity_index, entity, event, node_id in indexed_events:
        for action in event.actions:
            if action.command != "trigger":
                continue
            callback_arguments = _callback_arguments(action, source)
            raw_target = callback_arguments[0]
            target_kind = _ascii_fold(raw_target)
            target_trigger = callback_arguments[1]
            if target_kind == "self":
                dispatch = TriggerDispatch.SELF
                target_entity = entity.name
                candidate = _first_trigger_handler(self_handlers.get(entity_index, []), target_trigger)
                candidates = (candidate,) if candidate is not None else ()
            elif target_kind == "global":
                dispatch = TriggerDispatch.GLOBAL
                target_entity = raw_target
                candidates = tuple(
                    candidate
                    for handlers in handlers_by_entity.values()
                    if (candidate := _first_trigger_handler(handlers, target_trigger)) is not None
                )
            elif target_kind in {"player", "activator"}:
                dispatch = TriggerDispatch(target_kind)
                target_entity = raw_target
                candidates = ()
            else:
                dispatch = TriggerDispatch.SCRIPT_NAME
                target_entity = raw_target
                candidate = _first_trigger_handler(
                    handlers_by_entity.get(_ascii_fold(target_entity), []),
                    target_trigger,
                )
                candidates = (candidate,) if candidate is not None else ()

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

    return StaticStageGraph(tuple(nodes), tuple(edges), tuple(opaque_entities))


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
