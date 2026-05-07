from greatshot.highlights.detectors import detect_highlights


def test_detector_finds_multikill():
    events = [
        {"t_ms": 1000, "type": "kill", "attacker": "P1", "victim": "P2"},
        {"t_ms": 2000, "type": "kill", "attacker": "P1", "victim": "P3"},
        {"t_ms": 3000, "type": "kill", "attacker": "P1", "victim": "P4"},
    ]
    highlights = detect_highlights(events)
    assert any(item.highlight_type == "multi_kill" for item in highlights)
