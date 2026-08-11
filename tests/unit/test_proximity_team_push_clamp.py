"""FIX 7 regression: push_quality must be clamped to [0, 1] on import.

The Lua tracker computes `push_quality = alignment * (avg_speed / 300)`
with no upper bound; sprint speed exceeds 300 ups, so ~5% of historical
rows exceed 1.0 (observed max 2.158) while every sibling score field
(alignment_score, path_efficiency, focus_score, spawn_timing_score)
tops out at exactly 1.000. The import clamp in `_parse_team_push_line`
is the only write-path guard — the tracker Lua is a no-edit zone.

Scale fix only: the metric is measured as inverse to kills (kis-v5
dropped its multiplier); the clamp does not make it predictive.
"""

from proximity.parser.parser import ProximityParserV4


def _parser() -> ProximityParserV4:
    return ProximityParserV4(db_adapter=None)


def _line(quality: str) -> str:
    # start;end;team;avg_speed;dir_x;dir_y;alignment;push_quality;participants;toward
    return f"10000;14000;AXIS;280.5;0.7;0.7;0.85;{quality};4;flag"


def test_in_range_quality_is_unchanged():
    p = _parser()
    p._parse_team_push_line(_line("0.594"))
    assert len(p.team_pushes) == 1
    push = p.team_pushes[0]
    assert push.push_quality == 0.594
    assert push.alignment_score == 0.85
    assert push.participant_count == 4


def test_sprint_overshoot_is_clamped_to_one():
    """alignment 1.0 x speed 647/300 -> Lua reports 2.158."""
    p = _parser()
    p._parse_team_push_line(_line("2.158"))
    assert p.team_pushes[0].push_quality == 1.0


def test_exactly_one_is_untouched():
    p = _parser()
    p._parse_team_push_line(_line("1.0"))
    assert p.team_pushes[0].push_quality == 1.0


def test_other_fields_not_clamped():
    """avg_speed legitimately exceeds 300; only push_quality is bounded."""
    p = _parser()
    p._parse_team_push_line("10000;14000;ALLIES;352.9;0.1;0.9;0.99;1.164;5;depot")
    push = p.team_pushes[0]
    assert push.avg_speed == 352.9
    assert push.push_quality == 1.0


def test_negative_quality_floored_to_zero():
    """alignment and speed are non-negative, so a negative push_quality
    is a mangled dump line — floored rather than stored."""
    p = _parser()
    p._parse_team_push_line(_line("-0.5"))
    assert p.team_pushes[0].push_quality == 0.0


def test_malformed_line_still_skipped():
    p = _parser()
    p._parse_team_push_line("too;few")
    p._parse_team_push_line("a;b;AXIS;x;y;z;q;w;e;r")
    assert p.team_pushes == []
