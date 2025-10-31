import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

print("=" * 80)
print("VID'S OCTOBER 2ND STATS COMPARISON")
print("=" * 80)

# Get vid's aggregated stats from database for October 2nd
c.execute(
    '''
    SELECT
        SUM(kills) as total_kills,
        SUM(deaths) as total_deaths,
        SUM(gibs) as total_gibs,
        SUM(self_kills) as total_selfkills,
        SUM(team_kills) as total_teamkills,
        SUM(damage_given) as total_damage_given,
        SUM(damage_received) as total_damage_received,
        SUM(team_damage_given) as total_team_damage_given,
        SUM(team_damage_received) as total_team_damage_received,
        SUM(xp) as total_xp,
        SUM(kill_assists) as total_assists,
        SUM(times_revived) as total_revived,
        SUM(dynamites_planted) as total_dyn_planted,
        SUM(dynamites_defused) as total_dyn_defused
    FROM player_comprehensive_stats
    WHERE player_name = 'vid' AND session_date = '2025-10-02'
'''
)

db_stats = c.fetchone()

print("\n=== DATABASE STATS (All October 2nd Sessions) ===")
print(f"Kills:          {db_stats[0]}")
print(f"Deaths:         {db_stats[1]}")
print(f"Gibs:           {db_stats[2]}")
print(f"Self Kills:     {db_stats[3]}")
print(f"Team Kills:     {db_stats[4]}")
print(f"Damage Given:   {db_stats[5]}")
print(f"Damage Recvd:   {db_stats[6]}")
print(f"Team Dmg Given: {db_stats[7]}")
print(f"Team Dmg Recvd: {db_stats[8]}")
print(f"XP:             {db_stats[9]}")
print(f"Assists:        {db_stats[10]}")
print(f"Times Revived:  {db_stats[11]}")
print(f"Dyn Planted:    {db_stats[12]}")
print(f"Dyn Defused:    {db_stats[13]}")

print("\n=== EXPECTED FROM ATTACHMENTS (Human-Readable Files) ===")
print("Based on the 13 attachment files provided:")
print()

# Manual extraction from attachment files
expected = {
    'etl_adlernest_r1': {
        'kills': 9,
        'deaths': 3,
        'gibs': 3,
        'sk': 3,
        'xp': 48,
        'assists': 1,
        'dg': 1328,
        'dr': 1105,
        'tdg': 18,
        'tdr': 0,
    },
    'etl_adlernest_r2': {
        'kills': 16,
        'deaths': 5,
        'gibs': 9,
        'sk': 9,
        'xp': 51,
        'assists': 2,
        'dg': 2775,
        'dr': 1800,
        'tdg': 18,
        'tdr': 0,
    },
    'supply_r1': {
        'kills': 20,
        'deaths': 12,
        'gibs': 8,
        'sk': 7,
        'xp': 95,
        'assists': 3,
        'dg': 2646,
        'dr': 2349,
        'tdg': 72,
        'tdr': 92,
    },
    'supply_r2': {
        'kills': 30,
        'deaths': 19,
        'gibs': 12,
        'sk': 13,
        'xp': 111,
        'assists': 3,
        'dg': 4838,
        'dr': 4309,
        'tdg': 72,
        'tdr': 92,
    },
    'etl_sp_delivery_r2': {
        'kills': 10,
        'deaths': 6,
        'gibs': 6,
        'sk': 6,
        'xp': 16,
        'assists': 8,
        'dg': 2192,
        'dr': 1960,
        'tdg': 36,
        'tdr': 49,
    },
    'et_brewdog_r1': {
        'kills': 7,
        'deaths': 7,
        'gibs': 1,
        'sk': 1,
        'xp': 54,
        'assists': 1,
        'dg': 1113,
        'dr': 1290,
        'tdg': 31,
        'tdr': 0,
    },
    'et_brewdog_r2': {
        'kills': 13,
        'deaths': 10,
        'gibs': 3,
        'sk': 3,
        'xp': 30,
        'assists': 3,
        'dg': 2276,
        'dr': 2029,
        'tdg': 31,
        'tdr': 36,
    },
    'etl_frostbite_r1': {
        'kills': 5,
        'deaths': 4,
        'gibs': 1,
        'sk': 3,
        'xp': 35,
        'assists': 1,
        'dg': 738,
        'dr': 714,
        'tdg': 0,
        'tdr': 0,
    },
    'etl_frostbite_r2': {
        'kills': 8,
        'deaths': 10,
        'gibs': 2,
        'sk': 5,
        'xp': 23,
        'assists': 3,
        'dg': 1491,
        'dr': 1914,
        'tdg': 0,
        'tdr': 18,
    },
    'braundorf_b4_r1': {
        'kills': 8,
        'deaths': 8,
        'gibs': 4,
        'sk': 6,
        'xp': 85,
        'assists': 4,
        'dg': 1466,
        'dr': 1622,
        'tdg': 72,
        'tdr': 89,
    },
    'braundorf_b4_r2': {
        'kills': 20,
        'deaths': 11,
        'gibs': 11,
        'sk': 10,
        'xp': 64,
        'assists': 10,
        'dg': 3081,
        'dr': 2586,
        'tdg': 122,
        'tdr': 138,
    },
    'erdenberg_t2_r1': {
        'kills': 11,
        'deaths': 6,
        'gibs': 3,
        'sk': 5,
        'xp': 76,
        'assists': 6,
        'dg': 2426,
        'dr': 1996,
        'tdg': 18,
        'tdr': 78,
    },
    'erdenberg_t2_r2': {
        'kills': 16,
        'deaths': 12,
        'gibs': 5,
        'sk': 10,
        'xp': 37,
        'assists': 9,
        'dg': 3561,
        'dr': 3252,
        'tdg': 54,
        'tdr': 78,
    },
}

# Calculate totals
total_kills = sum(m['kills'] for m in expected.values())
total_deaths = sum(m['deaths'] for m in expected.values())
total_gibs = sum(m['gibs'] for m in expected.values())
total_sk = sum(m['sk'] for m in expected.values())
total_xp = sum(m['xp'] for m in expected.values())
total_assists = sum(m['assists'] for m in expected.values())
total_dg = sum(m['dg'] for m in expected.values())
total_dr = sum(m['dr'] for m in expected.values())
total_tdg = sum(m['tdg'] for m in expected.values())
total_tdr = sum(m['tdr'] for m in expected.values())

print(f"Kills:          {total_kills}")
print(f"Deaths:         {total_deaths}")
print(f"Gibs:           {total_gibs}")
print(f"Self Kills:     {total_sk}")
print(f"XP:             {total_xp}")
print(f"Assists:        {total_assists}")
print(f"Damage Given:   {total_dg}")
print(f"Damage Recvd:   {total_dr}")
print(f"Team Dmg Given: {total_tdg}")
print(f"Team Dmg Recvd: {total_tdr}")

print("\n=== COMPARISON ===")
print(f"{'Stat':<20} {'Database':<15} {'Expected':<15} {'Match?':<10}")
print("-" * 60)

comparisons = [
    ('Kills', db_stats[0], total_kills),
    ('Deaths', db_stats[1], total_deaths),
    ('Gibs', db_stats[2], total_gibs),
    ('Self Kills', db_stats[3], total_sk),
    ('XP', db_stats[9], total_xp),
    ('Assists', db_stats[10], total_assists),
    ('Damage Given', db_stats[5], total_dg),
    ('Damage Recvd', db_stats[6], total_dr),
    ('Team Dmg Given', db_stats[7], total_tdg),
    ('Team Dmg Recvd', db_stats[8], total_tdr),
]

all_match = True
for stat_name, db_val, expected_val in comparisons:
    match = "✅ YES" if db_val == expected_val else "❌ NO"
    if db_val != expected_val:
        all_match = False
    print(f"{stat_name:<20} {db_val:<15} {expected_val:<15} {match:<10}")

print("\n" + "=" * 80)
if all_match:
    print("🎉 ALL STATS MATCH! Database is 1:1 with actual game stats!")
else:
    print("⚠️  MISMATCH DETECTED! Some stats don't match!")
print("=" * 80)

# Now check weapon stats
print("\n=== WEAPON STATS COMPARISON ===")

c.execute(
    '''
    SELECT weapon_name, SUM(kills), SUM(deaths), SUM(headshots), SUM(hits), SUM(shots)
    FROM weapon_comprehensive_stats
    WHERE player_name = 'vid' AND session_date = '2025-10-02'
    GROUP BY weapon_name
    ORDER BY weapon_name
'''
)

print(f"\n{'Weapon':<20} {'Kills':<8} {'Deaths':<8} {'HS':<6} {'Hits':<8} {'Shots':<8}")
print("-" * 70)
for row in c.fetchall():
    print(f"{row[0]:<20} {row[1]:<8} {row[2]:<8} {row[3]:<6} {row[4]:<8} {row[5]:<8}")

conn.close()
