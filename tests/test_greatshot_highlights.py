from __future__ import annotations

from greatshot.highlights.detectors import detect_highlights


def test_detect_highlights_multikill_spree_and_aim_chain():
    events = [
        {"t_ms": 1000, "type": "kill", "attacker": "A", "victim": "B", "weapon": "mp40", "hit_region": "head"},
        {"t_ms": 2200, "type": "kill", "attacker": "A", "victim": "C", "weapon": "mp40", "hit_region": "head"},
        {"t_ms": 2900, "type": "kill", "attacker": "A", "victim": "D", "weapon": "mp40", "hit_region": "head"},
        {"t_ms": 5200, "type": "kill", "attacker": "A", "victim": "E", "weapon": "mp40"},
        {"t_ms": 9000, "type": "kill", "attacker": "F", "victim": "A", "weapon": "thompson"},
    ]

    highlights = detect_highlights(events)
    kinds = {item.highlight_type for item in highlights}

    assert "multi_kill" in kinds
    assert "spree" in kinds
    assert "aim_moment" in kinds
