cols_insert = """session_id, session_date, map_name, round_number,
player_guid, player_name, clean_name, team,
kills, deaths, damage_given, damage_received,
team_damage_given, team_damage_received,
gibs, self_kills, team_kills, team_gibs, headshot_kills,
time_played_seconds, time_played_minutes,
time_dead_minutes, time_dead_ratio,
xp, kd_ratio, dpm, efficiency,
bullets_fired, accuracy,
kill_assists,
objectives_completed, objectives_destroyed,
objectives_stolen, objectives_returned,
dynamites_planted, dynamites_defused,
times_revived, revives_given,
most_useful_kills, useless_kills, kill_steals,
denied_playtime, constructions, tank_meatshield,
double_kills, triple_kills, quad_kills,
multi_kills, mega_kills,
killing_spree_best, death_spree_worst"""

cols_list = [c.strip() for c in cols_insert.replace('\n', '').split(',')]
print(f"INSERT statement column count: {len(cols_list)}")

# Check for duplicates
from collections import Counter
dup = [item for item, count in Counter(cols_list).items() if count > 1]
print(f"Duplicates: {dup if dup else 'None'}")

# Print all
for i, col in enumerate(cols_list, 1):
    print(f"{i:2d}. {col}")
