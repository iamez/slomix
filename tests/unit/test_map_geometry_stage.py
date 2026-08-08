"""W5a parser and static command-graph contracts."""

from __future__ import annotations

import zipfile
import zlib

import pytest

from website.backend.map_geometry.pk3_index import AssetContentChangedError, Pk3GeometryIndex
from website.backend.map_geometry.stage import (
    AutoSpawnEffect,
    EntityStateEffect,
    MainObjectiveEffect,
    MainObjectiveSelectorForm,
    ObjectiveClass,
    ObjectiveStatusEffect,
    ObjectiveTeam,
    StageLoadStatus,
    StageParseError,
    TriggerDispatch,
    TriggerResolution,
    WinnerEffect,
    compile_static_stage_graph,
    load_static_stage,
    parse_map_script,
    parse_objdata,
)


def _write_pk3(path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)


def test_objdata_preserves_team_text_and_does_not_invent_missing_classification():
    catalog = parse_objdata(
        b"""// map copy
wm_mapdescription axis "Defend it"
wm_objective_axis_desc 1 "Primary Objective:**Defend it."
wm_objective_allied_desc 1 "Capture it."
wm_objective_allied_desc 2 "Additional: Open a route."
custom_metadata retained
""",
        source="fixture.objdata",
    )

    assert catalog.map_descriptions[0].audience == "axis"
    assert [(item.team, item.number, item.classification) for item in catalog.objectives] == [
        (ObjectiveTeam.AXIS, 1, ObjectiveClass.PRIMARY),
        (ObjectiveTeam.ALLIES, 1, ObjectiveClass.UNKNOWN),
        (ObjectiveTeam.ALLIES, 2, ObjectiveClass.ADDITIONAL),
    ]
    assert catalog.objectives[1].text == "Capture it."
    assert catalog.other_commands[0].command == "custom_metadata"


def test_objdata_rejects_duplicate_identity_and_malformed_text():
    duplicate = b"""wm_objective_axis_desc 1 "Primary: First"
wm_objective_axis_desc 1 "Primary: Second"
"""
    with pytest.raises(StageParseError, match="duplicate axis objective 1"):
        parse_objdata(duplicate, source="duplicate.objdata")
    with pytest.raises(StageParseError, match="unclosed quoted string"):
        parse_objdata(b'wm_objective_axis_desc 1 "broken', source="broken.objdata")
    with pytest.raises(StageParseError, match="NUL"):
        parse_objdata(b"wm_mapdescription axis nope\x00", source="nul.objdata")


def test_map_script_uses_newlines_as_action_boundaries_and_preserves_braced_actions():
    script = parse_map_script(
        b"""game_manager
{
  spawn
  {
    wm_setwinner 0 // comment
    setstate first default
    set { origin "1 2 3" model *7 }
    trigger self advance
  }
  trigger advance
  {
    wm_objective_status 1 1 1
  }
}
""",
        source="fixture.script",
    )

    entity = script.entities[0]
    assert entity.name == "game_manager"
    assert [(event.name, event.parameters) for event in entity.events] == [
        ("spawn", ()),
        ("trigger", ("advance",)),
    ]
    assert [(action.command, action.arguments) for action in entity.events[0].actions] == [
        ("wm_setwinner", ("0",)),
        ("setstate", ("first", "default")),
        ("set", ("origin", "1 2 3", "model", "*7")),
        ("trigger", ("self", "advance")),
    ]
    assert entity.events[0].actions[2].uses_braced_arguments is True


def test_map_script_matches_regular_word_punctuation_and_rejects_structural_attached_braces():
    script = parse_map_script(
        'manager {\nspawn {\nwm_announce prefix"suffix" marker{phase} alpha\N{NO-BREAK SPACE}beta\n}\n}\n'.encode(),
        source="punctuation.script",
    )

    assert script.entities[0].events[0].actions[0].arguments == (
        'prefix"suffix"',
        "marker{phase}",
        "alpha\N{NO-BREAK SPACE}beta",
    )
    with pytest.raises(StageParseError, match=r"expected '\{' after the entity name"):
        parse_map_script(b"manager{ spawn { halt } }", source="attached.script")


def test_map_script_rejects_inline_event_close_consumed_as_an_action_argument():
    with pytest.raises(StageParseError, match="unclosed entity"):
        parse_map_script(
            b"""manager {
 spawn { wm_setwinner 0 }
}
""",
            source="inline-close.script",
        )


def test_map_script_matches_the_engine_entity_introducer():
    script = parse_map_script(b"entity manager {\nspawn {\nhalt\n}\n}\n")

    assert script.entities[0].name == "manager"
    with pytest.raises(StageParseError, match="an entity name after 'entity'"):
        parse_map_script(b"entity {\nspawn {\nhalt\n}\n}\n")


def test_map_script_preserves_engine_event_parameter_strings():
    script = parse_map_script(b"manager {\ntrigger advance extra {\nhalt\n}\n}\n")

    assert script.entities[0].events[0].parameters == ("advance", "extra")


def test_unknown_registry_names_make_only_their_entity_opaque():
    script = parse_map_script(
        b"""unused_action { spawn { wm_setwiner 1 } }
unused_event { triger advance { halt } }
manager {
 spawn {
  wm_setwinner 1
 }
}
"""
    )

    action_issue = script.entities[0].registry_issue
    event_issue = script.entities[1].registry_issue
    assert action_issue is not None
    assert (action_issue.kind, action_issue.name, action_issue.line) == ("action", "wm_setwiner", 1)
    assert event_issue is not None
    assert (event_issue.kind, event_issue.name, event_issue.line) == ("event", "triger", 2)
    assert script.entities[2].registry_issue is None

    graph = compile_static_stage_graph(script)
    assert [(node.entity_name, node.effects) for node in graph.nodes] == [("manager", (WinnerEffect(1, 5),))]


def test_quoted_braces_keep_engine_structural_semantics_in_braced_actions():
    script = parse_map_script(b'manager {\nspawn {\nset "{" key "}"\n}\n}\n')

    action = script.entities[0].events[0].actions[0]
    assert action.uses_braced_arguments is True
    assert action.arguments == ("key",)


def test_map_script_rejects_empty_quoted_tokens_as_engine_boundaries():
    with pytest.raises(StageParseError, match="empty quoted tokens are engine control boundaries"):
        parse_map_script(
            b'manager {\nspawn {\nwm_announce "" suffix\n}\n}\n',
            source="empty-token.script",
        )


def test_static_graph_projects_only_defensible_effects_and_resolves_trigger_edges():
    script = parse_map_script(
        b"""game_manager {
 spawn {
  wm_objective_status 1 1 0
  wm_set_main_objective objective_target 1
  setautospawn "Forward Spawn" 1
  setstate gate invisible
  trigger self advance
  trigger absent event
 }
 trigger advance {
  wm_setwinner 1
 }
}
"""
    )
    graph = compile_static_stage_graph(script)

    assert len(graph.nodes) == 2
    assert graph.nodes[0].effects == (
        ObjectiveStatusEffect(1, 1, 0, 3),
        MainObjectiveEffect("objective_target", MainObjectiveSelectorForm.TARGET_NAME, 1, 4),
        AutoSpawnEffect("Forward Spawn", 1, 5),
        EntityStateEffect("gate", "invisible", 6),
    )
    assert graph.nodes[1].effects == (WinnerEffect(1, 11),)
    assert graph.trigger_edges[0].resolution is TriggerResolution.RESOLVED
    assert graph.trigger_edges[0].dispatch is TriggerDispatch.SELF
    assert graph.trigger_edges[0].candidate_node_ids == ("event:1",)
    assert graph.trigger_edges[1].resolution is TriggerResolution.MISSING
    assert graph.trigger_edges[1].dispatch is TriggerDispatch.SCRIPT_NAME
    assert graph.trigger_edges[1].candidate_node_ids == ()


def test_legacy_numeric_main_objective_is_marked_instead_of_treated_as_a_target_name():
    graph = compile_static_stage_graph(
        parse_map_script(
            b"""manager {
 spawn {
  wm_set_main_objective 2 1
 }
}
"""
        )
    )

    assert graph.nodes[0].effects == (MainObjectiveEffect("2", MainObjectiveSelectorForm.LEGACY_NUMERIC, 1, 3),)


def test_effect_projection_rejects_noncanonical_integer_syntax():
    script = parse_map_script(b"manager {\nspawn {\nwm_setwinner 0_1\n}\n}\n")

    with pytest.raises(StageParseError, match="winner team must be a canonical ASCII integer"):
        compile_static_stage_graph(script)


def test_command_and_trigger_folding_is_ascii_only():
    unknown_command = parse_map_script(
        "manager {\nspawn {\nwm_\N{LATIN SMALL LETTER LONG S}etwinner 1\n}\n}\n".encode()
    )

    issue = unknown_command.entities[0].registry_issue
    assert issue is not None
    assert (issue.kind, issue.name) == ("action", "wm_\N{LATIN SMALL LETTER LONG S}etwinner")
    assert compile_static_stage_graph(unknown_command).nodes == ()

    graph = compile_static_stage_graph(
        parse_map_script(
            """manager {
 spawn {
  trigger \N{LATIN SMALL LETTER LONG S}elf advance
 }
 trigger advance {
  halt
 }
}
""".encode()
        )
    )

    assert graph.nodes[0].effects == ()
    assert graph.trigger_edges[0].dispatch is TriggerDispatch.SCRIPT_NAME
    assert graph.trigger_edges[0].resolution is TriggerResolution.MISSING


def test_duplicate_trigger_handlers_are_retained_as_ambiguous_instead_of_selected():
    graph = compile_static_stage_graph(
        parse_map_script(
            b"""manager {
 spawn {
  trigger target advance
 }
}
target {
 trigger advance {
  halt
 }
}
target {
 trigger advance {
  halt
 }
}
"""
        )
    )

    assert graph.trigger_edges[0].resolution is TriggerResolution.AMBIGUOUS
    assert graph.trigger_edges[0].candidate_node_ids == ("event:1", "event:2")


def test_self_trigger_resolution_is_scoped_to_the_source_entity_block():
    with_local_handler = compile_static_stage_graph(
        parse_map_script(
            b"""duplicate {
 spawn {
  trigger self advance
 }
 trigger advance {
  halt
 }
}
duplicate {
 trigger advance {
  halt
 }
}
"""
        )
    )
    without_local_handler = compile_static_stage_graph(
        parse_map_script(
            b"""duplicate {
 spawn {
  trigger self advance
 }
}
duplicate {
 trigger advance {
  halt
 }
}
"""
        )
    )

    assert with_local_handler.trigger_edges[0].resolution is TriggerResolution.RESOLVED
    assert with_local_handler.trigger_edges[0].candidate_node_ids == ("event:1",)
    assert without_local_handler.trigger_edges[0].resolution is TriggerResolution.MISSING
    assert without_local_handler.trigger_edges[0].candidate_node_ids == ()


def test_runtime_trigger_dispatch_is_not_misreported_as_a_missing_script_name():
    graph = compile_static_stage_graph(
        parse_map_script(
            b"""manager {
 spawn {
  trigger global advance
  trigger player notify
  trigger activator notify
 }
 trigger advance {
  halt
 }
}
other {
 trigger advance {
  halt
 }
}
"""
        )
    )

    global_edge, player_edge, activator_edge = graph.trigger_edges
    assert global_edge.dispatch is TriggerDispatch.GLOBAL
    assert global_edge.resolution is TriggerResolution.RUNTIME_DISPATCH
    assert global_edge.candidate_node_ids == ("event:1", "event:2")
    assert player_edge.dispatch is TriggerDispatch.PLAYER
    assert player_edge.resolution is TriggerResolution.RUNTIME_DISPATCH
    assert player_edge.candidate_node_ids == ()
    assert activator_edge.dispatch is TriggerDispatch.ACTIVATOR
    assert activator_edge.resolution is TriggerResolution.NO_OP
    assert activator_edge.candidate_node_ids == ()


def test_stage_load_requires_independent_unambiguous_script_and_objdata(tmp_path):
    _write_pk3(
        tmp_path / "one.pk3",
        {
            "maps/duel.script": b"manager {\nspawn {\nwm_setwinner 0\n}\n}\n",
            "maps/duel.objdata": b'wm_objective_axis_desc 1 "Primary: Defend"',
        },
    )
    _write_pk3(tmp_path / "two.pk3", {"maps/duel.script": b"manager {\nspawn {\nwm_setwinner 1\n}\n}\n"})
    index = Pk3GeometryIndex.scan(tmp_path)

    result = load_static_stage(index, "duel")

    assert result.status is StageLoadStatus.AMBIGUOUS
    assert result.model is None
    assert result.script_resolution.status == "ambiguous"
    assert result.objdata_resolution.status == "resolved"


def test_stage_load_returns_a_model_with_both_selected_providers(tmp_path):
    _write_pk3(
        tmp_path / "one.pk3",
        {
            "maps/duel.script": b"manager {\nspawn {\nwm_setwinner 0\n}\n}\n",
            "maps/duel.objdata": b'wm_objective_axis_desc 1 "Primary: Defend"',
        },
    )
    result = load_static_stage(Pk3GeometryIndex.scan(tmp_path), "duel")

    assert result.status is StageLoadStatus.RESOLVED
    assert result.model is not None
    assert result.model.map_name == "duel"
    assert result.model.script_provider == result.script_resolution.selected
    assert result.model.objdata_provider == result.objdata_resolution.selected
    assert result.model.graph.nodes[0].effects == (WinnerEffect(0, 3),)


def test_stage_load_requires_objdata_instead_of_returning_a_partial_model(tmp_path):
    _write_pk3(
        tmp_path / "one.pk3",
        {"maps/duel.script": b"manager {\nspawn {\nwm_setwinner 0\n}\n}\n"},
    )
    result = load_static_stage(Pk3GeometryIndex.scan(tmp_path), "duel")

    assert result.status is StageLoadStatus.MISSING
    assert result.model is None
    assert result.objdata_resolution.status == "missing"


def test_stage_load_returns_invalid_when_indexed_asset_changes(tmp_path, monkeypatch):
    _write_pk3(
        tmp_path / "one.pk3",
        {
            "maps/duel.script": b"manager {\nspawn {\nwm_setwinner 0\n}\n}\n",
            "maps/duel.objdata": b'wm_objective_axis_desc 1 "Primary: Defend"',
        },
    )
    index = Pk3GeometryIndex.scan(tmp_path)

    def changed(_provider):
        raise AssetContentChangedError("indexed bytes changed")

    monkeypatch.setattr(index, "read_provider", changed)
    result = load_static_stage(index, "duel")

    assert result.status is StageLoadStatus.INVALID
    assert result.model is None
    assert result.reason == "indexed bytes changed"


def test_stage_load_wraps_unsupported_zip_compression_as_invalid(tmp_path, monkeypatch):
    _write_pk3(
        tmp_path / "one.pk3",
        {
            "maps/duel.script": b"manager {\nspawn {\nwm_setwinner 0\n}\n}\n",
            "maps/duel.objdata": b'wm_objective_axis_desc 1 "Primary: Defend"',
        },
    )
    index = Pk3GeometryIndex.scan(tmp_path)

    def unsupported_compression(*_args, **_kwargs):
        raise NotImplementedError("unsupported compression")

    monkeypatch.setattr(zipfile.ZipFile, "open", unsupported_compression)
    result = load_static_stage(index, "duel")

    assert result.status is StageLoadStatus.INVALID
    assert result.model is None
    assert "cannot read indexed asset" in (result.reason or "")
    assert "unsupported compression" in (result.reason or "")


def test_stage_load_wraps_corrupt_zip_payload_as_invalid(tmp_path, monkeypatch):
    _write_pk3(
        tmp_path / "one.pk3",
        {
            "maps/duel.script": b"manager {\nspawn {\nwm_setwinner 0\n}\n}\n",
            "maps/duel.objdata": b'wm_objective_axis_desc 1 "Primary: Defend"',
        },
    )
    index = Pk3GeometryIndex.scan(tmp_path)

    def corrupt_payload(*_args, **_kwargs):
        raise zlib.error("corrupt compressed payload")

    monkeypatch.setattr(zipfile.ZipExtFile, "read", corrupt_payload)
    result = load_static_stage(index, "duel")

    assert result.status is StageLoadStatus.INVALID
    assert result.model is None
    assert "cannot read indexed asset" in (result.reason or "")
    assert "corrupt compressed payload" in (result.reason or "")


def test_stage_load_returns_invalid_instead_of_a_partial_model(tmp_path):
    _write_pk3(
        tmp_path / "one.pk3",
        {
            "maps/duel.script": b"manager {\nspawn {\nwm_setwinner invalid\n}\n}\n",
            "maps/duel.objdata": b'wm_objective_axis_desc 1 "Primary: Defend"',
        },
    )
    result = load_static_stage(Pk3GeometryIndex.scan(tmp_path), "duel")

    assert result.status is StageLoadStatus.INVALID
    assert result.model is None
    assert "winner team must be a canonical ASCII integer" in (result.reason or "")
