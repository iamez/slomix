"""scripts/build_bot_twin_profiles.py — the pure functions behind a bot's
"twin" profile (docs/design/22 slice 3), with the controls that must fail:
a player who holds everywhere has NO distinctive goal, and shuffled
sessions erase distinctiveness."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))
import build_bot_twin_profiles as bt  # noqa: E402
from slomix_rcon import render_botnames  # noqa: E402

GOALS_GM = """global _MG =
{
\tATTACK_bCp1 =
\t{
\t\tAimVectors =
\t\t{
\t\t\tVec3(1.000, 0.000, 0.000),
\t\t},
\t\tGroupName = "bcp",
\t\tMaxCampTime = 20,
\t\tMinCampTime = 10,
\t\tPosition = Vec3(1000.000, 1000.000, 0.000),
\t},
\tDEFEND_rGate7 =
\t{
\t\tPosition = Vec3(5000.000, 5000.000, 64.000),
\t},
\tROUTE_eastgate =
\t{
\t\tPosition = Vec3(1000.000, 1100.000, 0.000),
\t},
\tCHECKPOINT_flag =
\t{
\t\tPosition = Vec3(9000.000, 9000.000, 0.000),
\t},
};
"""


def test_parse_goals_keeps_positioned_places_and_drops_routes():
    goals = bt.parse_goals(GOALS_GM)
    assert [g.name for g in goals] == ["ATTACK_bCp1", "DEFEND_rGate7", "CHECKPOINT_flag"]
    cp = goals[0]
    assert (cp.x, cp.y, cp.z, cp.has_camp_times, cp.kind) == (1000.0, 1000.0, 0.0, True, "ATTACK")
    assert goals[1].has_camp_times is False


def test_nearest_goal_uses_the_cell_centre_on_the_camp_grid():
    goals = bt.parse_goals(GOALS_GM)
    g, d = bt.nearest_goal((1, 1), goals)   # centre (768, 768) → ATTACK_bCp1 at (1000, 1000)
    assert g.name == "ATTACK_bCp1" and abs(d - 328.1) < 0.5
    assert bt.GRID == 512


def _three_players():
    """A camps at the CP, B at the gate, C holds everywhere (and at the
    shared flag most of all, like everyone)."""
    cp, gate, flag = (1, 1), (9, 9), (17, 17)
    return {
        "A": {cp: 60_000, flag: 40_000},
        "B": {gate: 60_000, flag: 40_000},
        "C": {cp: 20_000, gate: 20_000, flag: 60_000},
    }


def test_distinctive_goals_are_where_a_player_holds_more_than_the_others():
    goals = bt.parse_goals(GOALS_GM)
    shares = bt.goal_shares(_three_players(), goals)
    assert abs(shares["A"]["ATTACK_bCp1"] - 0.6) < 1e-9 and abs(shares["A"]["CHECKPOINT_flag"] - 0.4) < 1e-9
    a = bt.distinctive_goals(shares, "A")
    assert [g for g, _, _ in a] == ["ATTACK_bCp1"]
    assert a[0][1] == 0.6 and abs(a[0][2] - 0.1) < 1e-9      # group mean over the OTHERS (B 0, C 0.2)
    assert [g for g, _, _ in bt.distinctive_goals(shares, "B")] == ["DEFEND_rGate7"]
    # C holds everywhere: nothing lifts 1.5× above the others → no distinctive goal.
    assert bt.distinctive_goals(shares, "C") == []
    # The shared flag is nobody's personality even though it tops C's raw time.
    for p in ("A", "B", "C"):
        assert "CHECKPOINT_flag" not in [g for g, _, _ in bt.distinctive_goals(shares, p)]


def test_ranking_is_by_lift_over_the_group_not_by_raw_share_and_tiny_shares_are_noise():
    # D: 30 % at G1 where the others average 18 % (lift 1.7, +12 points) and
    # 20 % at G2 where the others average 5 % (lift 4, +15 points). Raw share
    # would put G1 first; personality puts G2 first.
    shares = {
        "D": {"G1": 0.30, "G2": 0.20, "G3": 0.01},
        "E": {"G1": 0.18, "G2": 0.05},
        "F": {"G1": 0.18, "G2": 0.05},
    }
    assert [g for g, _, _ in bt.distinctive_goals(shares, "D")] == ["G2", "G1"]
    # G3: nobody else was ever there (lift = infinity) but 1 % of D's hold
    # time is a sample, not a spot — the share floor keeps it out.
    assert "G3" not in [g for g, _, _ in bt.distinctive_goals(shares, "D")]


def test_the_control_must_fail_shuffled_sessions_erase_distinctiveness():
    goals = bt.parse_goals(GOALS_GM)
    cp, gate = (1, 1), (9, 9)
    rows = []
    for i in range(12):
        # A life: spawn wait (skipped for spots), then a 10 s hold at the spot.
        rows.append(("A", f"2026-01-{i + 1:02d}", [(0, 0.0, 0.0, 0.0), (4_000, (cp[0] + .5) * 512, (cp[1] + .5) * 512, 0.0), (14_000, (cp[0] + .5) * 512, (cp[1] + .5) * 512, 0.0)]))
        rows.append(("B", f"2026-01-{i + 1:02d}", [(0, 0.0, 0.0, 0.0), (4_000, (gate[0] + .5) * 512, (gate[1] + .5) * 512, 0.0), (14_000, (gate[0] + .5) * 512, (gate[1] + .5) * 512, 0.0)]))
    real = bt.measure_map(rows, goals)
    assert [g for g, _, _ in real["A"]["distinctive"]] == ["ATTACK_bCp1"]
    assert [g for g, _, _ in real["B"]["distinctive"]] == ["DEFEND_rGate7"]
    ctrl = bt.measure_map(bt.shuffle_sessions(rows, seed=3), goals)
    n_ctrl = sum(len(r["distinctive"]) for r in ctrl.values())
    assert n_ctrl <= 1, ctrl   # 24 sessions shuffled: at most a fluke survives the 1.5× lift
    # The control keeps every session and point, only the labels move.
    assert sorted(s for _, s, _ in rows) == sorted(s for _, s, _ in bt.shuffle_sessions(rows, seed=3))


def test_camp_times_are_the_quartiles_clamped_to_camp_seconds():
    assert bt.camp_times([8, 12, 20, 30, 45]) == (10.0, 37.5)
    assert bt.camp_times([200, 300, 400]) == (60.0, 60.0)        # a stalemate is not a camp order
    assert bt.camp_times([1, 1, 2]) == (5.0, 6.0)                 # never below 5 s, max > min
    assert bt.camp_times([]) == (5.0, 10.0)


def test_role_heuristic_reads_the_distinctive_kinds_and_the_hold_share():
    assert bt.role_for(15.0, 12.0, [("DEFEND_rGate7", .2, .05), ("DEFEND_rGate8", .1, .05)]) == "DEFENDER"
    assert bt.role_for(15.0, 12.0, [("ATTACK_bCp1", .2, .05)]) == "ATTACKER"
    assert bt.role_for(9.0, 12.0, []) == "ROAMER"
    assert bt.role_for(15.0, 12.0, []) == "AMBUSHER"
    assert bt.role_for(9.0, 12.0, [("DEFEND_rGate7", .2, .05)]) == "AMBUSHER"   # defends spots, but a low hold share


def test_tempo_is_relative_to_the_group_and_clamped():
    assert bt.tempo(250, 250) == 1.0
    assert bt.tempo(191, 250) == 0.76
    assert bt.tempo(50, 250) == 0.6 and bt.tempo(2000, 250) == 1.5
    assert bt.tempo(None, 250) == 1.0 and bt.tempo(250, None) == 1.0


def test_rendered_gm_is_balanced_names_are_quote_free_and_only_twins_get_a_profile_table():
    t = bt.Twin(alias='ol"z', guid="5D989160", reaction_ms=250.0, reaction_time=1.0)
    t.sessions["supply"] = 30
    t.hold_pct["supply"] = 14.0
    t.distinctive["supply"] = [("ATTACK_bCp1", 0.128, 0.028)]
    t.camp_times["supply"] = {"ATTACK_bCp1": (10.0, 37.5)}
    t.role["supply"] = "ATTACKER"
    prof = bt.render_profile(t.alias, t, "2026-09-06")
    assert "this.ReactionTime = 1.0;" in prof and 'ol"z' not in prof and "olz.gm" in prof
    snippet = bt.render_map_twins("supply", [t], "^o[BOT]^7", "2026-09-06")
    assert bt.balanced(snippet)
    assert 'bot.Name == "^o[BOT]^7olz"' in snippet and "ROLE.ATTACKER" in snippet
    assert 'SetMapGoalProperties( "ATTACK_bCp1", { MinCampTime = 10, MaxCampTime = 37.5 } );' in snippet
    assert "12.8 %, group 2.8 %" in snippet
    assert not bt.balanced("{ ( }")

    axis = {"COVERTOPS": [], "ENGINEER": [], "FIELDOPS": [], "MEDIC": ["olz", "vid"], "SOLDIER": []}
    allies = {"COVERTOPS": [], "ENGINEER": [], "FIELDOPS": [], "MEDIC": ["bronze"], "SOLDIER": []}
    table = render_botnames(axis, allies, "^o[BOT]^7", ["ExtraOne"], profiles={"olz": "twins/olz.gm"})
    assert 'AxisBots["olz"] = { class=CLASS.MEDIC, weapon=0, profile="twins/olz.gm" };' in table
    assert 'AxisBots["vid"] = t;' in table and 'AlliedBots["bronze"] = t;' in table
    # Without profiles the stock shape is untouched.
    assert 'AxisBots["olz"] = t;' in render_botnames(axis, allies, "^o[BOT]^7", ["ExtraOne"])
    assert bt.bot_aliases_from_table(table) == ["olz", "vid", "bronze"]
