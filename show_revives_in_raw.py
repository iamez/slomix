"""Parse carniee's raw stats line to show revives fields"""

# carniee's raw line from Round 1
line = r"0A26D447\^7carniee\0\2\134236216 4 12 0 0 0 0 0 0 9 0 56 202 3 0 8 0 3 0 0 0 0 1 0 0 0 2 2 0 0 0	1196	1438	97	18	1	3	1	0	79.8	22	0	7	3	0	1	0	0	10	2	220	0.0	4.3	0.0	27.5	1.2	0.3	2	23	0	0	0	0	0	0	0	0	2"

# Split by backslash to get header
parts = line.split('\\')
guid = parts[0]
name = parts[1]
rounds = parts[2]
team = parts[3]

# Get the stats part (after team field)
stats_section = parts[4]

# Split by TAB to get extended stats
if '\t' in stats_section:
    weapon_section, *tab_fields = stats_section.split('\t')
    
    print(f"Player: {name}")
    print(f"GUID: {guid}")
    print(f"\nTAB-separated fields (37 fields):")
    print(f"{'Field #':<10} {'Value':<15} {'Field Name'}")
    print("="*60)
    
    field_names = [
        "damage_given",           # 0
        "damage_received",        # 1
        "gibs",                   # 2
        "self_kills",             # 3
        "team_kills",             # 4
        "team_gibs",              # 5
        "team_damage_given",      # 6
        "team_damage_received",   # 7
        "time_played",            # 8
        "xp",                     # 9
        "killing_spree",          # 10
        "death_spree",            # 11
        "kill_assists",           # 12
        "kill_steals",            # 13
        "headshot_kills",         # 14
        "objectives_stolen",      # 15
        "objectives_returned",    # 16
        "dynamites_planted",      # 17
        "dynamites_defused",      # 18
        "times_revived",          # 19 ← HERE
        "bullets_fired",          # 20
        "dpm",                    # 21
        "time_minutes",           # 22
        "tank_meatshield",        # 23
        "time_dead_ratio",        # 24
        "time_dead_minutes",      # 25
        "kd_ratio",               # 26
        "useful_kills",           # 27
        "denied_playtime",        # 28
        "multikill_2x",           # 29
        "multikill_3x",           # 30
        "multikill_4x",           # 31
        "multikill_5x",           # 32
        "multikill_6x",           # 33
        "useless_kills",          # 34
        "full_selfkills",         # 35
        "repairs_constructions",  # 36
        "revives_given"           # 37 ← HERE
    ]
    
    for i, value in enumerate(tab_fields):
        field_name = field_names[i] if i < len(field_names) else f"unknown_{i}"
        marker = " ← REVIVE FIELD" if 'revive' in field_name else ""
        print(f"{i:<10} {value:<15} {field_name}{marker}")
