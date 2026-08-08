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
    MapDescription,
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
wm_mapdescription axis "{Defend}: it"
wm_objective_axis_desc 1 "Primary Objective:**Defend it."
wm_objective_allied_desc 1 "} Capture it."
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
    assert catalog.map_descriptions[0].text == "{Defend}: it"
    assert catalog.objectives[1].text == "} Capture it."
    assert [command.command for command in catalog.other_commands] == ["custom_metadata", "retained"]


def test_objdata_uses_fixed_arity_tokens_across_physical_lines():
    catalog = parse_objdata(
        b"""ignored metadata
wm_mapdescription
axis
"Legacy map"
wm_objective_axis_desc
1
"Primary: Hold it"
"""
    )

    assert catalog.map_descriptions == (MapDescription("axis", "Legacy map", 2),)
    assert catalog.objectives[0].text == "Primary: Hold it"
    assert [command.command for command in catalog.other_commands] == ["ignored", "metadata"]


def test_objdata_uses_pc_escape_and_adjacent_string_semantics():
    catalog = parse_objdata(
        b'''wm_mapdescription axis "Line one\\n" /* joined */
"Line two"
wm_objective_axis_desc 1 "Primary:\\x20" "Hold\\33"
''',
        source="pc-strings.objdata",
    )

    assert catalog.map_descriptions == (MapDescription("axis", "Line one\nLine two", 1),)
    assert catalog.objectives[0].text == "Primary: Hold!"
    assert catalog.objectives[0].classification is ObjectiveClass.PRIMARY


def test_objdata_rejects_newlines_and_unrepresentable_pc_string_escapes():
    with pytest.raises(StageParseError, match="newline inside PC quoted string"):
        parse_objdata(b'wm_mapdescription axis "first\nsecond"', source="newline.objdata")
    with pytest.raises(StageParseError, match="unsupported PC string escape"):
        parse_objdata(b'wm_mapdescription axis "bad\\q"', source="escape.objdata")


def test_objdata_pc_path_preserves_an_empty_quoted_token():
    catalog = parse_objdata(b'wm_mapdescription axis ""', source="empty.objdata")

    assert catalog.map_descriptions == (MapDescription("axis", "", 1),)


@pytest.mark.parametrize(
    "raw",
    [
        b'#define AXIS_OBJECTIVE "Primary: Hold"\nwm_objective_axis_desc 1 AXIS_OBJECTIVE',
        b'#if 1\nwm_mapdescription axis "conditional"\n#endif',
        b'$evalint(1) wm_mapdescription axis "computed"',
    ],
)
def test_objdata_rejects_pc_preprocessing_instead_of_modeling_unexpanded_tokens(raw):
    with pytest.raises(StageParseError, match="PC preprocessing is unsupported"):
        parse_objdata(raw, source="preprocessed.objdata")


def test_objdata_preprocessor_markers_inside_strings_and_comments_remain_text():
    catalog = parse_objdata(
        b'// #define ignored\nwm_mapdescription axis "Price $5 #1"',
        source="literal-markers.objdata",
    )

    assert catalog.map_descriptions == (MapDescription("axis", "Price $5 #1", 2),)


def test_objdata_uses_last_write_for_team_slots_and_rejects_malformed_text():
    duplicate = b"""wm_mapdescription axis "First map text"
wm_objective_axis_desc 1 "Primary: First"
wm_mapdescription axis "Replacement map text"
wm_objective_axis_desc 1 "Primary: Second"
"""
    catalog = parse_objdata(duplicate, source="duplicate.objdata")

    assert catalog.map_descriptions == (MapDescription("axis", "Replacement map text", 3),)
    assert len(catalog.objectives) == 1
    assert (catalog.objectives[0].text, catalog.objectives[0].line) == ("Primary: Second", 4)
    with pytest.raises(StageParseError, match="unclosed quoted string"):
        parse_objdata(b'wm_objective_axis_desc 1 "broken', source="broken.objdata")
    with pytest.raises(StageParseError, match="NUL"):
        parse_objdata(b"wm_mapdescription axis nope\x00", source="nul.objdata")


def test_trailing_unclosed_block_comment_is_engine_eof_for_both_asset_kinds():
    catalog = parse_objdata(b'wm_objective_axis_desc 1 "Primary: Hold"\n/* trailing')
    script = parse_map_script(b"manager {\nspawn {\nhalt\n}\n}\n/* trailing")

    assert catalog.objectives[0].text == "Primary: Hold"
    assert script.entities[0].events[0].actions[0].command == "halt"


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


def test_normal_action_braces_make_only_their_entity_opaque():
    script = parse_map_script(
        b"""unused { spawn { wm_setwinner 0 } }
manager {
 spawn {
  wm_setwinner 1
 }
}
""",
        source="inline-close.script",
    )

    graph = compile_static_stage_graph(script, source="inline-close.script")

    assert [(node.entity_name, node.effects) for node in graph.nodes] == [("manager", (WinnerEffect(1, 4),))]
    assert len(graph.opaque_entities) == 1
    assert (graph.opaque_entities[0].entity_name, graph.opaque_entities[0].issue_kind) == ("unused", "syntax")
    assert "entity boundary depends on selected-block brace interpretation" in graph.opaque_entities[0].reason


@pytest.mark.parametrize(
    ("event", "action"),
    [
        ("spawn", "wm_announce {literal"),
        ("spawn", "wm_announce }literal"),
        ("trigger }literal", "halt"),
        ("spawn", "set { {literal key }"),
    ],
)
def test_selected_brace_prefix_ambiguity_is_opaque_not_asset_invalid(event, action):
    script = parse_map_script(
        f"""manager {{
 {event} {{
  {action}
 }}
}}
later {{
 spawn {{
  wm_setwinner 1
 }}
}}
""".encode(),
        source="brace-prefix.script",
    )

    graph = compile_static_stage_graph(script, source="brace-prefix.script")

    assert len(script.entities) == 1
    assert graph.nodes == ()
    assert len(graph.opaque_entities) == 1
    issue = graph.opaque_entities[0]
    assert (issue.entity_name, issue.issue_kind, issue.token) == ("manager", "syntax", "manager")
    assert "entity boundary depends on selected-block brace interpretation" in issue.reason


def test_balanced_action_brace_prefixes_retain_the_entity_when_boundaries_agree():
    script = parse_map_script(
        b"""manager {
 spawn {
  wm_announce {literal }literal
  wm_setwinner 1
 }
}
"""
    )

    graph = compile_static_stage_graph(script)

    assert script.entities[0].events[0].actions[0].arguments == ("{literal", "}literal")
    assert graph.opaque_entities == ()
    assert graph.nodes[0].effects == (WinnerEffect(1, 4),)


def test_map_script_matches_the_engine_entity_introducer():
    script = parse_map_script(b"entity manager {\nspawn {\nhalt\n}\n}\n")

    assert script.entities[0].name == "manager"
    with pytest.raises(StageParseError, match="an entity name after 'entity'"):
        parse_map_script(b"entity {\nspawn {\nhalt\n}\n}\n")


def test_map_script_preserves_engine_event_parameter_strings():
    script = parse_map_script(
        b"""target {
 trigger advance extra {
  halt
 }
}
manager {
 spawn {
  trigger target "advance extra"
 }
}
"""
    )

    assert script.entities[0].events[0].parameters == ("advance", "extra")
    graph = compile_static_stage_graph(script)
    assert graph.trigger_edges[0].resolution is TriggerResolution.RESOLVED
    assert graph.trigger_edges[0].candidate_node_ids == ("event:0",)


def test_balanced_backslash_quote_pairs_match_engine_string_in_string_tokens():
    script = parse_map_script(b'manager {\nspawn {\nwm_announce "say \\"hello\\""\n}\n}\n')

    assert script.entities[0].events[0].actions[0].arguments == ('say "hello"',)


def test_nested_backslash_quote_span_retains_ordinary_quotes():
    script = parse_map_script(b'manager {\nspawn {\nwm_announce "say \\"a"b\\" done"\n}\n}\n')

    assert script.entities[0].events[0].actions[0].arguments == ('say "a"b" done',)


def test_legacy_single_byte_asset_text_round_trips_losslessly():
    catalog = parse_objdata(b'wm_mapdescription axis "caf\xe9"\n')

    assert catalog.map_descriptions[0].text.encode("utf-8", errors="surrogateescape") == b"caf\xe9"


def test_unselected_inner_errors_make_only_their_entity_opaque():
    script = parse_map_script(
        b"""unused_action { spawn { wm_setwiner 1 } }
unused_event { triger advance { halt } }
unused_syntax { spawn { set broken } }
unused_event_syntax { spawn missing_action_block }
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
    syntax_issue = script.entities[2].syntax_issue
    assert syntax_issue is not None
    assert (syntax_issue.token, syntax_issue.line) == ("set", 3)
    assert "expected '{' after set" in syntax_issue.reason
    event_syntax_issue = script.entities[3].syntax_issue
    assert event_syntax_issue is not None
    assert (event_syntax_issue.token, event_syntax_issue.line) == ("unused_event_syntax", 4)
    assert "entity boundary depends on selected-block brace interpretation" in event_syntax_issue.reason
    assert script.entities[4].registry_issue is None
    assert script.entities[4].syntax_issue is None

    graph = compile_static_stage_graph(script)
    assert [(node.entity_name, node.effects) for node in graph.nodes] == [("manager", (WinnerEffect(1, 7),))]
    assert [(item.entity_name, item.issue_kind, item.token) for item in graph.opaque_entities] == [
        ("unused_action", "registry_action", "wm_setwiner"),
        ("unused_event", "registry_event", "triger"),
        ("unused_syntax", "syntax", "set"),
        ("unused_event_syntax", "syntax", "unused_event_syntax"),
    ]


def test_event_and_action_parameter_aggregates_respect_max_info_string():
    long_a = "a" * 600
    long_b = "b" * 600
    boundary_a = "a" * 511
    boundary_b = "b" * 511
    script = parse_map_script(
        f"""unused_action {{
 spawn {{
  wm_announce {long_a} {long_b}
 }}
}}
unused_event {{
 trigger {long_a} {long_b} {{
  halt
 }}
}}
exact_limit {{
 spawn {{
  wm_announce {boundary_a} {boundary_b}
 }}
}}
manager {{
 spawn {{
  wm_setwinner 1
 }}
}}
""".encode()
    )

    graph = compile_static_stage_graph(script)

    assert [node.entity_name for node in graph.nodes] == ["exact_limit", "manager"]
    assert [(item.entity_name, item.issue_kind) for item in graph.opaque_entities] == [
        ("unused_action", "syntax"),
        ("unused_event", "syntax"),
    ]
    assert all("1023-byte aggregate limit" in item.reason for item in graph.opaque_entities)


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


def test_invalid_typed_projection_makes_only_its_entity_opaque():
    script = parse_map_script(
        b"""unused {
 spawn {
  wm_setwinner 0_1
 }
}
manager {
 spawn {
  wm_setwinner 1
 }
}
"""
    )

    graph = compile_static_stage_graph(script)

    assert [(node.entity_name, node.effects) for node in graph.nodes] == [("manager", (WinnerEffect(1, 8),))]
    assert len(graph.opaque_entities) == 1
    issue = graph.opaque_entities[0]
    assert (issue.entity_name, issue.issue_kind, issue.token, issue.line) == (
        "unused",
        "projection",
        "wm_setwinner",
        3,
    )
    assert "winner team must be a canonical ASCII integer" in issue.reason


def test_trigger_dispatch_retains_a_projection_opaque_handler_candidate():
    graph = compile_static_stage_graph(
        parse_map_script(
            b"""manager {
 spawn {
  trigger target advance
 }
}
target {
 trigger advance {
  wm_setwinner 2
 }
}
"""
        )
    )

    edge = graph.trigger_edges[0]
    assert edge.resolution is TriggerResolution.OPAQUE
    assert edge.candidate_node_ids == ()
    assert edge.opaque_candidate_event_ids == ("opaque-event:1:0",)
    assert [(item.entity_name, item.issue_kind) for item in graph.opaque_entities] == [
        ("target", "projection")
    ]


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


def test_duplicate_trigger_handlers_follow_engine_first_match_order():
    graph = compile_static_stage_graph(
        parse_map_script(
            b"""manager {
 spawn {
  trigger target advance
 }
}
target {
 trigger advance {
  wm_setwinner 0
 }
 trigger advance {
  wm_setwinner 1
 }
}
"""
        )
    )

    assert graph.trigger_edges[0].resolution is TriggerResolution.RESOLVED
    assert graph.trigger_edges[0].candidate_node_ids == ("event:1",)
    assert graph.nodes[1].effects == (WinnerEffect(0, 8),)
    assert graph.nodes[2].effects == (WinnerEffect(1, 11),)


def test_parameterless_trigger_is_an_ordered_wildcard_handler():
    graph = compile_static_stage_graph(
        parse_map_script(
            b"""wildcard_first {
 trigger {
  wm_setwinner 0
 }
 trigger advance {
  wm_setwinner 1
 }
}
named_first {
 trigger advance {
  wm_setwinner 1
 }
 trigger {
  wm_setwinner 0
 }
}
manager {
 spawn {
  trigger wildcard_first advance
  trigger named_first advance
  trigger named_first other
 }
}
"""
        )
    )

    wildcard_first, named_first, named_fallback = graph.trigger_edges
    assert wildcard_first.candidate_node_ids == ("event:0",)
    assert named_first.candidate_node_ids == ("event:2",)
    assert named_fallback.candidate_node_ids == ("event:3",)
    assert all(edge.resolution is TriggerResolution.RESOLVED for edge in graph.trigger_edges)


def test_parameterless_trigger_order_applies_to_self_dispatch():
    graph = compile_static_stage_graph(
        parse_map_script(
            b"""wildcard_first {
 spawn {
  trigger self advance
 }
 trigger {
  halt
 }
 trigger advance {
  halt
 }
}
named_first {
 spawn {
  trigger self advance
 }
 trigger advance {
  halt
 }
 trigger {
  halt
 }
}
"""
        )
    )

    wildcard_first, named_first = graph.trigger_edges
    assert wildcard_first.candidate_node_ids == ("event:1",)
    assert named_first.candidate_node_ids == ("event:4",)
    assert all(edge.dispatch is TriggerDispatch.SELF for edge in graph.trigger_edges)
    assert all(edge.resolution is TriggerResolution.RESOLVED for edge in graph.trigger_edges)


def test_parameterless_trigger_order_applies_per_global_candidate():
    graph = compile_static_stage_graph(
        parse_map_script(
            b"""wildcard_first {
 trigger {
  halt
 }
 trigger advance {
  halt
 }
}
named_first {
 trigger advance {
  halt
 }
 trigger {
  halt
 }
}
manager {
 spawn {
  trigger global advance
 }
}
"""
        )
    )

    edge = graph.trigger_edges[0]
    assert edge.dispatch is TriggerDispatch.GLOBAL
    assert edge.resolution is TriggerResolution.RUNTIME_DISPATCH
    assert edge.candidate_node_ids == ("event:0", "event:2")


def test_later_duplicate_entity_block_cannot_supply_a_trigger_handler():
    graph = compile_static_stage_graph(
        parse_map_script(
            b"""manager {
 spawn {
  trigger target advance
 }
}
target {
 spawn {
  halt
 }
}
target {
 trigger advance {
  wm_setwinner 1
 }
}
"""
        )
    )

    assert graph.trigger_edges[0].resolution is TriggerResolution.MISSING
    assert graph.trigger_edges[0].candidate_node_ids == ()
    assert [(item.entity_name, item.issue_kind) for item in graph.opaque_entities] == [("target", "shadowed")]


def test_callback_reparse_controls_trigger_dispatch_and_typed_projection():
    graph = compile_static_stage_graph(
        parse_map_script(
            b"""manager {
 spawn {
  trigger "\\"target\\"" advance ignored
  wm_setwinner "\\"1\\"" ignored
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

    assert graph.nodes[0].effects == (WinnerEffect(1, 4),)
    assert graph.trigger_edges[0].target_entity == "target"
    assert graph.trigger_edges[0].resolution is TriggerResolution.RESOLVED
    assert graph.trigger_edges[0].candidate_node_ids == ("event:1",)


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
            "maps/duel.script": b"manager {\nspawn {\nwm_setwinner 1\n}\n",
            "maps/duel.objdata": b'wm_objective_axis_desc 1 "Primary: Defend"',
        },
    )
    result = load_static_stage(Pk3GeometryIndex.scan(tmp_path), "duel")

    assert result.status is StageLoadStatus.INVALID
    assert result.model is None
    assert "unclosed entity 'manager'" in (result.reason or "")
