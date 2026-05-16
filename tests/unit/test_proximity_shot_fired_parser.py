"""Phase 5.2 — parser unit tests for the v9 true-aim SHOT_FIRED section.

Asserts: (a) a synthetic v9 line parses into a ShotFired with correct
field mapping; (b) backward compatibility — a parser that never sees a
SHOT_FIRED section keeps an empty list, and malformed/legacy lines are
skipped without raising (so v6.01 files are unaffected).
"""

from proximity.parser.parser import ProximityParserV4, ShotFired


def _parser() -> ProximityParserV4:
    return ProximityParserV4(db_adapter=None)


def test_shot_fired_line_parses_fields():
    p = _parser()
    # time;guid;weapon;ox;oy;oz;yaw;pitch
    p._parse_shot_fired_line("12345;ABCDEF0123456789ABCDEF0123456789;8;-3772;1168;153;91.50;-4.25")
    assert len(p.shot_fired) == 1
    sf = p.shot_fired[0]
    assert isinstance(sf, ShotFired)
    assert sf.time == 12345
    assert sf.guid == "ABCDEF0123456789ABCDEF0123456789"
    assert sf.weapon == 8
    assert (sf.origin_x, sf.origin_y, sf.origin_z) == (-3772, 1168, 153)
    assert sf.view_yaw == 91.50
    assert sf.view_pitch == -4.25


def test_shot_fired_float_origin_is_coerced():
    p = _parser()
    p._parse_shot_fired_line("1;G;3;-3772.0;1168.9;153.4;0;0")
    assert len(p.shot_fired) == 1
    assert (p.shot_fired[0].origin_x, p.shot_fired[0].origin_y) == (-3772, 1168)


def test_short_or_malformed_line_skipped_no_raise():
    p = _parser()
    p._parse_shot_fired_line("1;G;3;0;0")          # too few fields
    p._parse_shot_fired_line("not;a;number;x;y;z;a;b")  # non-numeric
    p._parse_shot_fired_line("")                    # empty
    assert p.shot_fired == []  # all skipped, no exception


def test_backward_compat_no_section_means_empty_list():
    """A v6.01 file has no SHOT_FIRED section -> list stays empty and
    nothing else is disturbed."""
    p = _parser()
    assert p.shot_fired == []
    # parsing a combat-position line must not leak into shot_fired
    p._parse_combat_position_line(
        "100;kill;A;an;AXIS;med;B;bn;ALLIES;eng;1;2;3;4;5;6;7;8"
    )
    assert p.shot_fired == []
