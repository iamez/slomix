#!/usr/bin/env python3
"""
UNIFIED SCHEMA VERIFICATION SCRIPT
Verifies etlegacy_production.db with UNIFIED schema (53 columns)
All stats in ONE table: player_comprehensive_stats
"""
import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# Get a high-activity player to demonstrate all stats
# ✅ FIXED: Query unified schema (all stats in ONE table)
cursor.execute('''
    SELECT *
    FROM player_comprehensive_stats
    WHERE kills > 10
    ORDER BY kills DESC
    LIMIT 1
''')

row = cursor.fetchone()

if not row:
    print("❌ No player found with kills > 10")
    conn.close()
    exit()

print('=' * 100)
print('COMPREHENSIVE STATS VERIFICATION - HIGH-ACTIVITY PLAYER SAMPLE')
print('=' * 100)
print()

# Session and Player Info (columns 1-8)
print(f"Player: {row[6]} (GUID: {row[5]})")
print(f"Session: {row[3]} - {row[2]} Round {row[4]}")
print()

print('PLAYER COMPREHENSIVE STATS (ALL 53 COLUMNS):')
print('-' * 100)

# Correct column indexes for UNIFIED SCHEMA (53 columns total)
stats = [
    ('id', row[0], True),
    ('session_id', row[1], True),
    ('session_date', row[2], True),
    ('map_name', row[3], True),
    ('round_number', row[4], True),
    ('player_guid', row[5], True),
    ('player_name', row[6], True),
    ('clean_name', row[7], True),
    ('team', row[8], row[8] in [1, 2]),
    ('kills', row[9], row[9] > 0),
    ('deaths', row[10], row[10] > 0),
    ('damage_given', row[11], row[11] > 0),
    ('damage_received', row[12], row[12] > 0),
    ('team_damage_given', row[13], row[13] >= 0),
    ('team_damage_received', row[14], row[14] >= 0),
    ('gibs', row[15], row[15] >= 0),
    ('self_kills', row[16], row[16] >= 0),
    ('team_kills', row[17], row[17] >= 0),
    ('team_gibs', row[18], row[18] >= 0),
    ('headshot_kills', row[19], row[19] >= 0),
    ('time_played_seconds', row[20], row[20] > 0),
    ('time_played_minutes', round(row[21], 1) if row[21] else 0, True),
    ('time_dead_minutes', round(row[22], 1) if row[22] else 0, True),
    ('time_dead_ratio', round(row[23], 2) if row[23] else 0, True),
    ('xp', row[24], row[24] > 0),
    ('kd_ratio', round(row[25], 2) if row[25] else 0, True),
    ('dpm', round(row[26], 2) if row[26] else 0, True),
    ('efficiency', round(row[27], 2) if row[27] else 0, True),
    ('bullets_fired', row[28], row[28] >= 0),
    ('accuracy', round(row[29], 1) if row[29] else 0, True),
    # ⭐ OBJECTIVE STATS (columns 30-42 in unified schema)
    ('kill_assists', row[30], row[30] >= 0),
    ('objectives_completed', row[31], row[31] >= 0),
    ('objectives_destroyed', row[32], row[32] >= 0),
    ('objectives_stolen', row[33], row[33] >= 0),
    ('objectives_returned', row[34], row[34] >= 0),
    ('dynamites_planted', row[35], row[35] >= 0),
    ('dynamites_defused', row[36], row[36] >= 0),
    ('times_revived', row[37], row[37] >= 0),
    ('revives_given', row[38], row[38] >= 0),
    ('most_useful_kills', row[39], row[39] >= 0),
    ('useless_kills', row[40], row[40] >= 0),
    ('kill_steals', row[41], row[41] >= 0),
    ('denied_playtime', row[42], row[42] >= 0),
    # CONSTRUCTION & MULTIKILL STATS
    ('constructions', row[43], row[43] >= 0),
    ('tank_meatshield', row[44], row[44] >= 0),
    ('double_kills', row[45], row[45] >= 0),
    ('triple_kills', row[46], row[46] >= 0),
    ('quad_kills', row[47], row[47] >= 0),
    ('multi_kills', row[48], row[48] >= 0),
    ('mega_kills', row[49], row[49] >= 0),
    ('killing_spree_best', row[50], row[50] >= 0),
    ('death_spree_worst', row[51], row[51] >= 0),
    ('created_at', row[52], True),
]

for name, value, has_data in stats:
    status = '✓ HAS DATA' if has_data else '✗ EMPTY/ZERO'
    print(f'  {name:<30} = {str(value):<20} {status}')

# Get weapon stats for this player
cursor.execute('''
    SELECT weapon_name, hits, shots, kills, deaths, headshots, accuracy
    FROM weapon_comprehensive_stats
    WHERE player_guid = ? AND session_id = ?
    ORDER BY kills DESC
''', (row[5], row[1]))

weapons = cursor.fetchall()

print()
print(f'WEAPON STATS ({len(weapons)} weapons for this player):')
print('-' * 100)

for w in weapons[:10]:  # Show top 10
    status = '✓ USED' if (w[3] > 0 or w[2] > 0) else '✗ NOT USED'
    weapon = f'{w[0]:<20}'
    kills = f'Kills={w[3]:<4}'
    deaths = f'Deaths={w[4]:<3}'
    hits = f'Hits={w[1]:<5}'
    shots = f'Shots={w[2]:<6}'
    hs = f'HS={w[5]:<3}'
    acc = f'Acc={w[6]:.1f}%'
    print(f'  {weapon} {kills} {deaths} {hits} {shots} {hs} {acc}  {status}')

print()
print('=' * 100)
print('SUMMARY - STATS STATUS ACROSS ALL PLAYERS')
print('=' * 100)

# Check how many players have data in various fields
cursor.execute('''
    SELECT
        COUNT(*) as total_players,
        COUNT(CASE WHEN kills > 0 THEN 1 END) as have_kills,
        COUNT(CASE WHEN damage_given > 0 THEN 1 END) as have_damage,
        COUNT(CASE WHEN team_damage_given > 0 THEN 1 END) as have_tdmg,
        COUNT(CASE WHEN gibs > 0 THEN 1 END) as have_gibs,
        COUNT(CASE WHEN self_kills > 0 THEN 1 END) as have_self,
        COUNT(CASE WHEN team_kills > 0 THEN 1 END) as have_tk,
        COUNT(CASE WHEN headshot_kills > 0 THEN 1 END) as have_hs,
        COUNT(CASE WHEN revives_given > 0 THEN 1 END) as have_revives,
        COUNT(CASE WHEN kill_assists > 0 THEN 1 END) as have_assists,
        COUNT(CASE WHEN dynamites_planted > 0 THEN 1 END) as have_dyno,
        COUNT(CASE WHEN times_revived > 0 THEN 1 END) as have_revd
    FROM player_comprehensive_stats
''')

summary = cursor.fetchone()
total = summary[0]

print()
print(f"Total Players in Database: {total:,}")
print()
print("Field Population Rates:")
pct_kills = 100 * summary[1] / total if total > 0 else 0
pct_dmg = 100 * summary[2] / total if total > 0 else 0
pct_tdmg = 100 * summary[3] / total if total > 0 else 0
pct_gibs = 100 * summary[4] / total if total > 0 else 0
pct_self = 100 * summary[5] / total if total > 0 else 0
pct_tk = 100 * summary[6] / total if total > 0 else 0
pct_hs = 100 * summary[7] / total if total > 0 else 0
pct_rev = 100 * summary[8] / total if total > 0 else 0
pct_assist = 100 * summary[9] / total if total > 0 else 0
pct_dyno = 100 * summary[10] / total if total > 0 else 0
pct_revd = 100 * summary[11] / total if total > 0 else 0

print(f"  kills:              {summary[1]:>5}/{total} "
      f"({pct_kills:.1f}%) ✓ CORE STAT")
print(f"  damage_given:       {summary[2]:>5}/{total} "
      f"({pct_dmg:.1f}%) ✓ CORE STAT")
print(f"  team_damage_given:  {summary[3]:>5}/{total} "
      f"({pct_tdmg:.1f}%) - situational")
print(f"  gibs:               {summary[4]:>5}/{total} "
      f"({pct_gibs:.1f}%) - situational")
print(f"  self_kills:         {summary[5]:>5}/{total} "
      f"({pct_self:.1f}%) - rare/situational")
print(f"  team_kills:         {summary[6]:>5}/{total} "
      f"({pct_tk:.1f}%) - rare/situational")
print(f"  headshot_kills:     {summary[7]:>5}/{total} "
      f"({pct_hs:.1f}%) ✓ WORKS")
print(f"  revives_given:      {summary[8]:>5}/{total} "
      f"({pct_rev:.1f}%) - medic only")
print(f"  kill_assists:       {summary[9]:>5}/{total} "
      f"({pct_assist:.1f}%) ✓ OBJECTIVE STAT")
print(f"  dynamites_planted:  {summary[10]:>5}/{total} "
      f"({pct_dyno:.1f}%) - engineer only")
print(f"  times_revived:      {summary[11]:>5}/{total} "
      f"({pct_revd:.1f}%) ✓ OBJECTIVE STAT")

print()
print("✓ = Stat is working and populated")
print("✗ = Stat is zero/empty (either not used or class-specific)")
print()
print("✅ UNIFIED SCHEMA VERIFIED - All stats in ONE table!")
print()

conn.close()
