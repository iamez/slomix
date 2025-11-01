import sqlite3

db_path = "etlegacy_production.db"

# Define expected stats from attachment files (13 sessions)
# These are the actual files we have attachments for
expected_sessions = {
    'etl_adlernest_r1': {'kills': 9, 'deaths': 3, 'gibs': 3, 'xp': 48, 'assists': 1},
    'etl_adlernest_r2': {'kills': 16, 'deaths': 5, 'gibs': 9, 'xp': 51, 'assists': 2},  # CUMULATIVE
    'supply_r1': {'kills': 20, 'deaths': 12, 'gibs': 8, 'xp': 95, 'assists': 3},
    'supply_r2': {'kills': 30, 'deaths': 19, 'gibs': 12, 'xp': 111, 'assists': 3},  # CUMULATIVE
    # CUMULATIVE (no r1 attachment)
    'etl_sp_delivery_r2': {'kills': 10, 'deaths': 6, 'gibs': 6, 'xp': 16, 'assists': 8},
    'et_brewdog_r1': {'kills': 7, 'deaths': 7, 'gibs': 1, 'xp': 54, 'assists': 1},
    'et_brewdog_r2': {'kills': 13, 'deaths': 10, 'gibs': 3, 'xp': 30, 'assists': 3},  # CUMULATIVE
    'etl_frostbite_r1': {'kills': 5, 'deaths': 4, 'gibs': 1, 'xp': 35, 'assists': 1},
    'etl_frostbite_r2': {'kills': 8, 'deaths': 10, 'gibs': 2, 'xp': 23, 'assists': 3},  # CUMULATIVE
    'braundorf_b4_r1': {'kills': 8, 'deaths': 8, 'gibs': 4, 'xp': 85, 'assists': 4},
    # CUMULATIVE
    'braundorf_b4_r2': {'kills': 20, 'deaths': 11, 'gibs': 11, 'xp': 64, 'assists': 10},
    'erdenberg_t2_r1': {'kills': 11, 'deaths': 6, 'gibs': 3, 'xp': 76, 'assists': 6},
    'erdenberg_t2_r2': {'kills': 16, 'deaths': 12, 'gibs': 5, 'xp': 37, 'assists': 9},  # CUMULATIVE
}

# Calculate expected totals
expected_totals = {
    'kills': sum(s['kills'] for s in expected_sessions.values()),
    'deaths': sum(s['deaths'] for s in expected_sessions.values()),
    'gibs': sum(s['gibs'] for s in expected_sessions.values()),
    'xp': sum(s['xp'] for s in expected_sessions.values()),
    'assists': sum(s['assists'] for s in expected_sessions.values()),
}

print("=" * 80)
print("VID'S STATS COMPARISON - ACCOUNTING FOR CUMULATIVE VS DIFFERENTIAL")
print("=" * 80)
print()

print("=== EXPECTED FROM ATTACHMENTS (13 Sessions) ===")
for key, value in expected_totals.items():
    print(f"{key.upper()}: {value}")
print()

# Now get database stats for ONLY the sessions we have attachments for
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get database stats by map/round
maps_to_check = [
    ('etl_adlernest', 1),
    ('etl_adlernest', 2),
    ('supply', 1),
    ('supply', 2),
    ('etl_sp_delivery', 2),  # Only Round 2 attachment
    ('et_brewdog', 1),
    ('et_brewdog', 2),
    ('etl_frostbite', 1),
    ('etl_frostbite', 2),
    ('braundorf_b4', 1),
    ('braundorf_b4', 2),
    ('erdenberg_t2', 1),
    ('erdenberg_t2', 2),
]

print("=== DATABASE STATS (Session by Session) ===")
db_totals = {'kills': 0, 'deaths': 0, 'gibs': 0, 'xp': 0, 'assists': 0}

for map_name, round_num in maps_to_check:
    query = """
    SELECT p.kills, p.deaths, p.gibs, p.xp, p.kill_assists
    FROM player_comprehensive_stats p
    JOIN sessions s ON p.session_id = s.id
    WHERE p.player_name = 'vid'
    AND s.session_date = '2025-10-02'
    AND s.map_name = ?
    AND s.round_number = ?
    """

    cursor.execute(query, (map_name, round_num))
    result = cursor.fetchone()

    if result:
        kills, deaths, gibs, xp, assists = result
        print(f"{map_name} Round {round_num}: K:{kills} D:{deaths} G:{gibs} XP:{xp} A:{assists}")

        # For Round 2, we need to add Round 1 stats to get cumulative
        if round_num == 2:
            # Get Round 1 stats
            cursor.execute(query, (map_name, 1))
            r1_result = cursor.fetchone()
            if r1_result:
                r1_kills, r1_deaths, r1_gibs, r1_xp, r1_assists = r1_result
                # Database stores differential, so add R1 to get cumulative
                kills += r1_kills
                deaths += r1_deaths
                gibs += r1_gibs
                xp += r1_xp
                assists += r1_assists
                print(f"  -> Cumulative R2: K:{kills} D:{deaths} G:{gibs} XP:{xp} A:{assists}")

        db_totals['kills'] += kills
        db_totals['deaths'] += deaths
        db_totals['gibs'] += gibs
        db_totals['xp'] += xp
        db_totals['assists'] += assists
    else:
        print(f"{map_name} Round {round_num}: NOT FOUND IN DATABASE")

print()
print("=== DATABASE TOTALS (Cumulative for R2 sessions) ===")
for key, value in db_totals.items():
    print(f"{key.upper()}: {value}")
print()

print("=== COMPARISON ===")
print(f"{'Stat':<15} {'Expected':<12} {'Database':<12} {'Match?'}")
print("-" * 60)
for stat in ['kills', 'deaths', 'gibs', 'xp', 'assists']:
    expected = expected_totals[stat]
    actual = db_totals[stat]
    match = "✅ YES" if expected == actual else "❌ NO"
    print(f"{stat.upper():<15} {expected:<12} {actual:<12} {match}")

print()
if all(expected_totals[s] == db_totals[s] for s in ['kills', 'deaths', 'gibs', 'xp', 'assists']):
    print("🎉 ALL STATS MATCH (accounting for cumulative R2)!")
else:
    print("⚠️  MISMATCH - Need to investigate further")

conn.close()
