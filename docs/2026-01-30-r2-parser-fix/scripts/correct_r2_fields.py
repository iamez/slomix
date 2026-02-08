#!/usr/bin/env python3
"""
Determine correct R2_ONLY_FIELDS set based on parser field names.

From parser mapping (lines 904-932):
TAB[9] → 'xp'
TAB[10] → 'killing_spree'
TAB[11] → 'death_spree'
TAB[12] → 'kill_assists'
TAB[13] → 'kill_steals'
TAB[14] → 'headshot_kills'
TAB[15] → 'objectives_stolen'
TAB[16] → 'objectives_returned'
TAB[19] → 'times_revived' (same as revives_received)
TAB[24] → 'time_dead_ratio'
TAB[25] → 'time_dead_minutes'
TAB[27] → 'useful_kills'
TAB[28] → 'denied_playtime'
TAB[37] → 'revives_given'

From our file analysis (R2 < R1 = R2-only):
TAB[9]: 86 → 79 (efficiency/xp)
TAB[11]: 5 → 4 (death_spree)
TAB[12]: 7 → 3 (kill_assists)
TAB[14]: 3 → 1 (revives_received... wait, this doesn't match)
TAB[15]: 3 → 0 (ammo_given... but parser says objectives_stolen)
TAB[17]: 1 → 0 (objectives_captured... but parser says dynamites_planted)
TAB[19]: 5 → 0 (objectives_returned... but parser says times_revived)
TAB[24]: 53.2 → 9.8 (time_dead_ratio) ✓
TAB[25]: 4.4 → 1.6 (time_dead_minutes) ✓
TAB[27]: 7 → 4 (useful_kills) ✓
TAB[28]: 106 → 105 (denied_playtime) ✓

WAIT - there's a mismatch between our field counting and the parser's mapping!

Let me recount SuperBoyy's R1 extended section:
"""

r1_extended = "3252\t3547\t40\t36\t3\t1\t0\t1\t73.7\t86\t3\t5\t7\t0\t3\t3\t0\t1\t0\t5\t348\t0.0\t8.3\t0.0\t53.2\t4.4\t0.6\t7\t106\t0\t0\t0\t0\t0\t2\t0\t0\t4"
r2_extended = "5780\t5282\t40\t72\t10\t5\t0\t1\t81.0\t79\t4\t4\t3\t1\t1\t0\t0\t0\t0\t0\t626\t0.0\t16.6\t0.0\t9.8\t1.6\t0.9\t4\t105\t1\t0\t0\t0\t0\t4\t0\t0\t0"

r1 = r1_extended.split('\t')
r2 = r2_extended.split('\t')

print("TAB INDEX → PARSER FIELD → R1 VALUE → R2 VALUE → BEHAVIOR")
print("=" * 80)

parser_map = {
    0: "damage_given",
    1: "damage_received",
    2: "team_damage_given",
    3: "team_damage_received",
    4: "gibs",
    5: "self_kills",
    6: "team_kills",
    7: "team_gibs",
    8: "time_played_percent",
    9: "xp",
    10: "killing_spree",
    11: "death_spree",
    12: "kill_assists",
    13: "kill_steals",
    14: "headshot_kills",
    15: "objectives_stolen",
    16: "objectives_returned",
    17: "dynamites_planted",
    18: "dynamites_defused",
    19: "times_revived",
    20: "bullets_fired",
    21: "dpm",
    22: "time_played_minutes",
    23: "tank_meatshield",
    24: "time_dead_ratio",
    25: "time_dead_minutes",
    26: "kd_ratio",
    27: "useful_kills",
    28: "denied_playtime",
    29: "multikill_2x",
    30: "multikill_3x",
    31: "multikill_4x",
    32: "multikill_5x",
    33: "multikill_6x",
    34: "useless_kills",
    35: "full_selfkills",
    36: "repairs_constructions",
    37: "revives_given",
}

r2_only = set()

for idx in range(len(r1)):
    r1_val = float(r1[idx])
    r2_val = float(r2[idx])
    field = parser_map.get(idx, f"unknown_{idx}")

    if r2_val < r1_val:
        behavior = "R2-ONLY ❌"
        r2_only.add(field)
    else:
        behavior = "CUMULATIVE ✅"

    if r2_val < r1_val or abs(r2_val - r1_val) < 0.01:  # Show interesting ones
        print(f"[{idx:2d}] {field:25s} {r1_val:8.2f} → {r2_val:8.2f}  {behavior}")

print("\n" + "=" * 80)
print("CORRECT R2_ONLY_FIELDS SET FOR PARSER:")
print("=" * 80)
print("R2_ONLY_FIELDS = {")
for field in sorted(r2_only):
    print(f"    '{field}',")
print("}")
