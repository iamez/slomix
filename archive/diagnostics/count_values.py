# Test to count tuple items
values = (
    # Line 130: 4 items
    "session_id",
    "session_date",
    "map_name",
    "round_num",
    # Line 131-132: 4 items
    "guid",
    "name1",
    "name2",
    "team",
    # Line 133-134: 4 items
    "kills",
    "deaths",
    "damage_given",
    "damage_received",
    # Line 135-136: 2 items
    "team_damage_given",
    "team_damage_received",
    # Line 137-138: 4 items
    "gibs",
    "self_kills",
    "team_kills",
    "team_gibs",
    # Line 139: 3 items
    "time_seconds",
    "time_minutes",
    "time_display",
    # Line 140: 3 items
    "xp",
    "dpm",
    "kd_ratio",
    # Line 141-142: 2 items
    "killing_spree",
    "death_spree",
    # Line 143-145: 3 items
    "kill_assists",
    "kill_steals",
    "headshots",
    # Line 146-147: 2 items
    "objectives_stolen",
    "objectives_returned",
    # Line 148-151: 4 items
    "dynamites_planted",
    "dynamites_defused",
    "times_revived",
    "revives_given",
    # Line 152-154: 3 items
    "bullets_fired",
    "tank_meatshield",
    "time_dead_ratio",
    # Line 155-156: 2 items
    "most_useful_kills",
    "denied_playtime",
    # Line 157-159: 3 items
    "useless_kills",
    "full_selfkills",
    "repairs_constructions",
    # Line 160-164: 5 items
    "double_kills",
    "triple_kills",
    "quad_kills",
    "multi_kills",
    "mega_kills",
)

print(f"Total VALUES: {len(values)}")
# Expected: 4+4+4+2+4+3+3+2+3+2+4+3+2+3+5 = 48
