from __future__ import annotations

import scripts.proximity_objective_coords_gate as gate


def test_parse_top_maps_arg_normalizes_and_deduplicates():
    parsed = gate.parse_top_maps_arg("Te_Escape2, supply, ,SUPPLY,te_escape2")
    assert parsed == ["te_escape2", "supply"]


def test_evaluate_gate_passes_for_fully_covered_static_and_runtime_maps():
    template = {
        "maps": {
            "supply": [
                {"name": "command_post", "x": 1, "y": 2, "z": 3},
                {"name": "truck", "x": 4, "y": 5, "z": 6},
            ]
        }
    }
    config = {
        "static_guard_maps": ["supply"],
        "runtime": {"top_n": 1, "allow_todo_maps": []},
    }

    result = gate.evaluate_gate(template, config, runtime_top_maps=["supply"])

    assert result["ok"] is True
    assert result["errors"] == []
    assert result["warnings"] == []


def test_evaluate_gate_fails_static_guard_when_entries_are_incomplete():
    template = {
        "maps": {
            "supply": [
                {"name": "command_post", "x": None, "y": 2, "z": 3},
            ]
        }
    }
    config = {
        "static_guard_maps": ["supply"],
        "runtime": {"top_n": 0, "allow_todo_maps": []},
    }

    result = gate.evaluate_gate(template, config, runtime_top_maps=[])

    assert result["ok"] is False
    assert any("static_guard:supply" in msg for msg in result["errors"])


def test_evaluate_gate_runtime_respects_allowlist_and_flags_unknown_missing_maps():
    template = {
        "maps": {
            "te_escape2": [
                {"name": "secret_exit", "x": 1, "y": 2, "z": 3},
            ]
        }
    }
    config = {
        "static_guard_maps": ["te_escape2"],
        "runtime": {"top_n": 3, "allow_todo_maps": ["etl_frostbite"]},
    }

    result = gate.evaluate_gate(
        template,
        config,
        runtime_top_maps=["te_escape2", "etl_frostbite", "et_brewdog"],
    )

    assert result["ok"] is False
    assert any("runtime_top_map:et_brewdog" in msg for msg in result["errors"])
    assert any("runtime_top_map:etl_frostbite" in msg for msg in result["warnings"])
