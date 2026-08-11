"""FIX 3 regression: weapon-accuracy hits must never exceed shots_fired.

`proximity_weapon_accuracy.accuracy_pct` is a GENERATED column
(hits / shots_fired * 100), so rows imported with hits > shots_fired
render as impossible >100% accuracy (observed max: 1000%). The Lua
tracker counts shots per et_WeaponFire event but hits per et_Damage
VICTIM event (splash weapons hit N victims per shot; airstrike/arty
damage has no matching fire event under the same weapon id), so raw
dump lines can legitimately carry hits > shots. The import clamp in
`_parse_weapon_accuracy_line` is the only write-path guard — the
tracker Lua itself is a no-edit zone (live drift).
"""

from proximity.parser.parser import ProximityParserV4

GUID = "ABCDEF0123456789ABCDEF0123456789"


def _parser() -> ProximityParserV4:
    return ProximityParserV4(db_adapter=None)


def test_normal_line_is_unchanged():
    p = _parser()
    # guid;name;team;weapon_id;shots_fired;hits;kills;headshots
    p._parse_weapon_accuracy_line(f"{GUID};Rifleman;AXIS;3;50;12;3;2")
    assert len(p.weapon_accuracy) == 1
    wa = p.weapon_accuracy[0]
    assert (wa.shots_fired, wa.hits, wa.kills, wa.headshots) == (50, 12, 3, 2)


def test_splash_overcount_is_clamped_to_shots():
    """One grenade, three victims: Lua reports 3 hits on 1 shot."""
    p = _parser()
    p._parse_weapon_accuracy_line(f"{GUID};Nader;ALLIES;4;1;3;1;0")
    wa = p.weapon_accuracy[0]
    assert wa.shots_fired == 1
    assert wa.hits == 1  # clamped: accuracy_pct generates to 100, not 300
    assert wa.kills == 1  # kills/headshots untouched


def test_zero_shot_phantom_hits_are_clamped_to_zero():
    """Airstrike/arty damage remaps to a weapon id with no fire events."""
    p = _parser()
    p._parse_weapon_accuracy_line(f"{GUID};FieldOps;AXIS;55;0;4;2;0")
    wa = p.weapon_accuracy[0]
    assert wa.shots_fired == 0
    assert wa.hits == 0  # no longer inflates SUM(hits) aggregates
    assert wa.kills == 2


def test_hits_equal_to_shots_not_touched():
    p = _parser()
    p._parse_weapon_accuracy_line(f"{GUID};Sniper;ALLIES;23;7;7;5;4")
    wa = p.weapon_accuracy[0]
    assert (wa.shots_fired, wa.hits) == (7, 7)


def test_malformed_line_still_skipped():
    p = _parser()
    p._parse_weapon_accuracy_line("too;few;fields")
    p._parse_weapon_accuracy_line(f"{GUID};X;AXIS;a;b;c;d;e")
    assert p.weapon_accuracy == []


def test_negative_counts_are_dropped():
    """shots=-1/hits=-2 would slip past the clamp (-2 > -1 is false) and
    still generate 200% accuracy — corrupt lines add no row at all."""
    p = _parser()
    p._parse_weapon_accuracy_line(f"{GUID};X;AXIS;3;-1;-2;0;0")
    p._parse_weapon_accuracy_line(f"{GUID};X;AXIS;3;5;-1;0;0")
    p._parse_weapon_accuracy_line(f"{GUID};X;AXIS;3;-5;1;0;0")
    assert p.weapon_accuracy == []
