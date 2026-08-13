"""Live-view S0: parser contract over the 2026-08-11 bot-test fixture.

The fixture is a verbatim slice of puran's ``legacy3.log`` from the
supervised bot test (bots only, no human chat, no IPs/GUIDs — verified at
capture time). It pins the grammar from LIVE_VIEW_RESEARCH §A.3 to real
engine output, so an engine or c0rnp0rn upgrade that changes the log
format fails here instead of silently blinding the future live tailer.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from vps_scripts.liveview_parser import LiveEvent, parse_line, parse_lines, strip_colors

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "liveview" / "legacy3_bot_test_2026-08-11.txt"


def _events() -> list[LiveEvent]:
    return parse_lines(FIXTURE.read_text(encoding="utf-8", errors="ignore").splitlines())


def test_fixture_parses_round_boundaries():
    counts = Counter(e.type for e in _events())
    assert counts["ROUND_START"] >= 2
    assert counts["ROUND_END"] >= 1
    assert counts["MAP"] >= 1
    assert counts["GAMETIME"] >= 1  # edini absolutni čas


def test_kills_carry_slots_names_and_mod():
    kills = [e for e in _events() if e.type == "KILL"]
    assert kills, "bot test mora vsebovati kille"
    for k in kills:
        assert isinstance(k.fields["killer_slot"], int)
        assert isinstance(k.fields["victim_slot"], int)
        assert k.fields["mod"].startswith("MOD_")
        assert "^" not in k.fields["killer"] + k.fields["victim"]


def test_team_changes_use_engine_team_space():
    teams = [e.fields["team"] for e in _events() if e.type == "TEAM_CHANGE"]
    assert teams, "userinfo vrstice morajo obstajati"
    assert {t for t in teams if t is not None} <= {1, 2, 3}


def test_popup_grammar_is_closed():
    popups = [e for e in _events() if e.type == "POPUP"]
    for p in popups:
        assert p.fields["verb"] in {"stole", "returned", "planted", "defused"}
        assert p.fields["team"] in {"allies", "axis"}


def test_team_xp_is_not_a_score():
    for e in _events():
        if e.type == "TEAM_XP":
            assert "axis_xp" in e.fields and "allies_xp" in e.fields


def test_team_chat_text_is_redacted():
    line = " 9509300 sayteam: ^7player^7: tajna taktika"
    ev = parse_line(line)
    assert ev is not None and ev.type == "TEAM_CHAT_REDACTED"
    assert ev.fields == {} and ev.raw == ""
    assert "tajna" not in repr(ev)


def test_announce_text_passes_through_stripped():
    ev = parse_line('13656500 legacy announce: "^7The Allies have captured the forward bunker!"')
    assert ev is not None and ev.type == "ANNOUNCE"
    assert ev.fields["text"] == "The Allies have captured the forward bunker!"


def test_exit_and_surrender_reasons():
    assert parse_line(" 8814050 Exit: Wolf EndRound.").fields["reason"] == "Wolf EndRound."
    assert parse_line("11079275 Exit: Allies Surrender").fields["reason"] == "Allies Surrender"


def test_strip_colors():
    assert strip_colors("^o[BOT]^7lagger") == "[BOT]lagger"


def test_coverage_no_dominant_unparsed_class():
    """Nobena množična vrsta vrstic ne sme ostati nemodelirana (razen
    Endstats ASCII tabel, ki so namerno izpuščene)."""
    unparsed: Counter[str] = Counter()
    for line in FIXTURE.read_text(encoding="utf-8", errors="ignore").splitlines():
        if parse_line(line) is None and line.strip():
            key = line.strip().split(":")[0].split(" ")[-1][:20]
            unparsed[key] += 1
    for key, n in unparsed.items():
        if n > 50:
            assert key == "Endstats", f"nemodelirana množična vrsta: {key} ×{n}"



# ---- LIVEX grammar (live_events.lua → slomix-live.log) --------------------

def test_livex_enriched_kill():
    ev = parse_line("K 1786480914123 3 5 34 1024,-512,64 900,-480,64 88 137")
    assert ev is not None and ev.type == "LIVE_KILL"
    assert ev.fields["killer_slot"] == 3 and ev.fields["victim_slot"] == 5
    assert ev.fields["mod_id"] == 34
    assert ev.fields["killer_pos"] == {"x": 1024, "y": -512, "z": 64}
    assert ev.fields["victim_pos"]["y"] == -480
    assert ev.fields["killer_health"] == 88 and ev.fields["distance"] == 137


def test_livex_aggregate():
    ev = parse_line("A 1786480914123 5 640 210 2 1")
    assert ev is not None and ev.type == "LIVE_AGGREGATE"
    assert ev.fields == {"slot": 5, "damage_given": 640,
                         "damage_received": 210, "kills": 2, "deaths": 1}


def test_livex_movement_with_and_without_yaw():
    ev = parse_line("M 1786480914123 3:1024,-512,270 5:900,-480")
    assert ev is not None and ev.type == "LIVE_MOVEMENT"
    p0, p1 = ev.fields["players"]
    assert p0 == {"slot": 3, "x": 1024, "y": -512, "yaw": 270}
    assert p1 == {"slot": 5, "x": 900, "y": -480} and "yaw" not in p1


def test_livex_map():
    ev = parse_line("I 1786480914123 map supply")
    assert ev is not None and ev.type == "LIVE_MAP" and ev.fields["map_name"] == "supply"


def test_livex_malformed_returns_none():
    assert parse_line("K 123 3") is None           # too few fields
    assert parse_line("Z 123 whatever") is None     # unknown kind
    assert parse_line("K notanumber 3 5") is None   # non-numeric ms
