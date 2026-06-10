"""Parser unit tests for the v7 draft sections (Lua 6.10, dormant).

AIM_LOCK / SPAWN_SELECT / SKILL_SNAPSHOT / COMM_EVENTS. Asserts field
mapping on synthetic lines and backward compatibility: files without the
sections keep empty lists, malformed lines are skipped without raising
(so v6.0x files are unaffected).
"""

from proximity.parser.parser import (
    AimLock,
    CommEvent,
    ProximityParserV4,
    SkillSnapshot,
    SpawnSelect,
)

GUID_A = "ABCDEF0123456789ABCDEF0123456789"
GUID_B = "FEDCBA9876543210FEDCBA9876543210"


def _parser() -> ProximityParserV4:
    return ProximityParserV4(db_adapter=None)


def test_aim_lock_line_parses_fields():
    p = _parser()
    # start;end;duration;guid;name;team;target_guid;target_name;avg_err;avg_dist;samples
    p._parse_aim_lock_line(
        f"10000;12400;2400;{GUID_A};Aimer;AXIS;{GUID_B};Target;4.5;820;6"
    )
    assert len(p.aim_locks) == 1
    al = p.aim_locks[0]
    assert isinstance(al, AimLock)
    assert (al.start_time, al.end_time, al.duration_ms) == (10000, 12400, 2400)
    assert al.guid == GUID_A and al.target_guid == GUID_B
    assert al.team == "AXIS"
    assert al.avg_err_deg == 4.5
    assert al.avg_dist == 820
    assert al.samples == 6


def test_spawn_select_line_parses_fields():
    p = _parser()
    p._parse_spawn_select_line(f"31000;{GUID_A};Picker;ALLIES;3;28000")
    assert len(p.spawn_selects) == 1
    ss = p.spawn_selects[0]
    assert isinstance(ss, SpawnSelect)
    assert ss.time == 31000
    assert ss.spawn_index == 3
    assert ss.last_spawn_time == 28000


def test_skill_snapshot_line_parses_fields():
    p = _parser()
    p._parse_skill_snapshot_line(f"{GUID_A};Vet;AXIS;4;2;3;1;4;0;2")
    assert len(p.skill_snapshots) == 1
    sk = p.skill_snapshots[0]
    assert isinstance(sk, SkillSnapshot)
    assert sk.battle_sense == 4
    assert sk.engineering == 2
    assert sk.first_aid == 3
    assert sk.signals == 1
    assert sk.light_weapons == 4
    assert sk.heavy_weapons == 0
    assert sk.covertops == 2


def test_comm_event_line_parses_fields():
    p = _parser()
    p._parse_comm_event_line(f"45000;{GUID_A};Caller;ALLIES;vsay_team;Medic")
    assert len(p.comm_events) == 1
    cm = p.comm_events[0]
    assert isinstance(cm, CommEvent)
    assert cm.cmd == "vsay_team"
    assert cm.arg == "Medic"


def test_malformed_v7_lines_skipped_no_raise():
    p = _parser()
    p._parse_aim_lock_line("1;2;3")                       # too few
    p._parse_aim_lock_line("x;y;z;a;b;c;d;e;f;g;h")       # non-numeric
    p._parse_spawn_select_line("1;G;n;t")                  # too few
    p._parse_skill_snapshot_line("G;n;t;1;2;3")            # too few
    p._parse_comm_event_line("")                           # empty
    assert p.aim_locks == []
    assert p.spawn_selects == []
    assert p.skill_snapshots == []
    assert p.comm_events == []


def test_backward_compat_no_sections_means_empty_lists():
    p = _parser()
    assert p.aim_locks == []
    assert p.spawn_selects == []
    assert p.skill_snapshots == []
    assert p.comm_events == []
