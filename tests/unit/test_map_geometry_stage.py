"""W5a parser and static command-graph contracts."""

from __future__ import annotations

import zipfile

import pytest

from website.backend.map_geometry.pk3_index import Pk3GeometryIndex
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


def test_map_script_rejects_engine_incompatible_attached_braces_and_quotes():
    with pytest.raises(StageParseError, match="braces must begin at a token boundary"):
        parse_map_script(b"manager{ spawn { halt } }", source="attached.script")
    with pytest.raises(StageParseError, match="quote must begin at a token boundary"):
        parse_map_script(b'manager { trigger bad { wm_announce prefix"suffix" } }', source="attached.script")


def test_map_script_rejects_event_close_on_a_normal_action_line():
    with pytest.raises(StageParseError, match="normal action must end at a newline"):
        parse_map_script(
            b"""manager {
 spawn { wm_setwinner 0 }
}
""",
            source="inline-close.script",
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
    assert "winner team must be an integer" in (result.reason or "")
