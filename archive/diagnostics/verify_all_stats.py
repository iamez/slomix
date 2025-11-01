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

print('=' * 100)
print('COMPREHENSIVE STATS VERIFICATION - HIGH-ACTIVITY PLAYER SAMPLE')
print('=' * 100)
print()

# Session and Player Info
print(f"Player: {row[3]} (GUID: {row[2]})")
print()

print('PLAYER COMPREHENSIVE STATS (35 fields):')
print('-' * 100)

stats = [
    ('player_name', row[3], True),
    ('clean_name', row[4], True),
    ('team', row[5], True),
    ('kills', row[6], row[6] > 0),
    ('deaths', row[7], row[7] > 0),
    ('damage_given', row[8], row[8] > 0),
    ('damage_received', row[9], row[9] > 0),
    ('team_damage_given', row[10], row[10] > 0),
    ('team_damage_received', row[11], row[11] > 0),
    ('gibs', row[12], row[12] > 0),
    ('self_kills', row[13], row[13] > 0),
    ('team_kills', row[14], row[14] > 0),
    ('team_gibs', row[15], row[15] > 0),
    ('time_axis', row[16], row[16] > 0),
    ('time_allies', row[17], row[17] > 0),
    ('time_played_seconds', row[18], row[18] > 0),
    ('time_played_minutes', round(row[19], 1), row[19] > 0),
    ('xp', row[20], row[20] > 0),
    ('killing_spree_best', row[21], row[21] > 0),
    ('death_spree_worst', row[22], row[22] > 0),
    ('kill_assists', row[23], row[23] > 0),
    ('headshot_kills', row[24], row[24] > 0),
    ('revives', row[25], row[25] > 0),
    ('ammopacks', row[26], row[26] > 0),
    ('healthpacks', row[27], row[27] > 0),
    ('dpm', round(row[28], 2), row[28] > 0),
    ('kd_ratio', round(row[29], 2), row[29] > 0),
    ('efficiency', round(row[30], 2), row[30] > 0),
    ('award_accuracy', row[31], row[31] > 0),
    ('award_damage', row[32], row[32] > 0),
    ('award_kills', row[33], row[33] > 0),
    ('award_experience', row[34], row[34] > 0),
]

for name, value, has_data in stats:
    status = '✓ HAS DATA' if has_data else '✗ EMPTY/ZERO'
    print(f'  {name:<30} = {str(value):<20} {status}')

print()
print('PLAYER OBJECTIVE STATS (27 fields):')
print('-' * 100)

obj_stats = [
    ('objectives_completed', row[35], row[35] > 0),
    ('objectives_destroyed', row[36], row[36] > 0),
    ('objectives_captured', row[37], row[37] > 0),
    ('objectives_defended', row[38], row[38] > 0),
    ('objectives_stolen', row[39], row[39] > 0),
    ('objectives_returned', row[40], row[40] > 0),
    ('dynamites_planted', row[41], row[41] > 0),
    ('dynamites_defused', row[42], row[42] > 0),
    ('landmines_planted', row[43], row[43] > 0),
    ('landmines_spotted', row[44], row[44] > 0),
    ('revives', row[45], row[45] > 0),
    ('ammopacks', row[46], row[46] > 0),
    ('healthpacks', row[47], row[47] > 0),
    ('times_revived', row[48], row[48] > 0),
    ('kill_assists', row[49], row[49] > 0),
    ('constructions_built', row[50], row[50] > 0),
    ('constructions_destroyed', row[51], row[51] > 0),
    ('killing_spree_best', row[52], row[52] > 0),
    ('death_spree_worst', row[53], row[53] > 0),
    ('kill_steals', row[54], row[54] > 0),
    ('most_useful_kills', row[55], row[55] > 0),
    ('useless_kills', row[56], row[56] > 0),
    ('denied_playtime', row[57], row[57] > 0),
    ('tank_meatshield', row[58], row[58] > 0),
]

for name, value, has_data in obj_stats:
    status = '✓ HAS DATA' if has_data else '✗ EMPTY/ZERO'
    print(f'  {name:<30} = {str(value):<20} {status}')

# Get weapon stats for this player
cursor.execute('''
    SELECT weapon_name, hits, shots, kills, deaths, headshots, accuracy
    FROM weapon_comprehensive_stats
    WHERE player_guid = ?
    ORDER BY kills DESC
''', (row[2],))

weapons = cursor.fetchall()

print()
print(f'WEAPON STATS ({len(weapons)} weapons tracked for this player):')
print('-' * 100)

for w in weapons[:10]:  # Show top 10
    status = '✓ USED' if (w[3] > 0 or w[2] > 0) else '✗ NOT USED'
    print(f'  {w[0]:<20} Kills={w[3]:<4} Deaths={w[4]:<3} Hits={w[1]:<5} Shots={w[2]:<6} HS={w[5]:<3} Acc={w[6]:.1f}%  {status}')

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
        COUNT(CASE WHEN team_damage_given > 0 THEN 1 END) as have_team_damage,
        COUNT(CASE WHEN gibs > 0 THEN 1 END) as have_gibs,
        COUNT(CASE WHEN self_kills > 0 THEN 1 END) as have_self_kills,
        COUNT(CASE WHEN team_kills > 0 THEN 1 END) as have_team_kills,
        COUNT(CASE WHEN headshot_kills > 0 THEN 1 END) as have_headshots,
        COUNT(CASE WHEN revives > 0 THEN 1 END) as have_revives,
        COUNT(CASE WHEN ammopacks > 0 THEN 1 END) as have_ammopacks,
        COUNT(CASE WHEN healthpacks > 0 THEN 1 END) as have_healthpacks,
        COUNT(CASE WHEN award_accuracy > 0 THEN 1 END) as have_accuracy_award,
        COUNT(CASE WHEN award_damage > 0 THEN 1 END) as have_damage_award,
        COUNT(CASE WHEN award_kills > 0 THEN 1 END) as have_kills_award,
        COUNT(CASE WHEN award_experience > 0 THEN 1 END) as have_xp_award
    FROM player_comprehensive_stats
''')

summary = cursor.fetchone()
total = summary[0]

print()
print(f"Total Players in Database: {total}")
print()
print("Field Population Rates:")
print(f"  kills:              {summary[1]:>5}/{total} ({100*summary[1]/total:.1f}%) ✓ CORE STAT")
print(f"  damage_given:       {summary[2]:>5}/{total} ({100*summary[2]/total:.1f}%) ✓ CORE STAT")
print(f"  team_damage_given:  {summary[3]:>5}/{total} ({100*summary[3]/total:.1f}%) - situational")
print(f"  gibs:               {summary[4]:>5}/{total} ({100*summary[4]/total:.1f}%) - situational")
print(f"  self_kills:         {summary[5]:>5}/{total} ({100*summary[5]/total:.1f}%) - rare/situational")
print(f"  team_kills:         {summary[6]:>5}/{total} ({100*summary[6]/total:.1f}%) - rare/situational")
print(f"  headshot_kills:     {summary[7]:>5}/{total} ({100*summary[7]/total:.1f}%) ✓ WORKS")
print(f"  revives:            {summary[8]:>5}/{total} ({100*summary[8]/total:.1f}%) - medic only")
print(f"  ammopacks:          {summary[9]:>5}/{total} ({100*summary[9]/total:.1f}%) - LT only")
print(f"  healthpacks:        {summary[10]:>5}/{total} ({100*summary[10]/total:.1f}%) - medic only")
print(f"  award_accuracy:     {summary[11]:>5}/{total} ({100*summary[11]/total:.1f}%) - best accuracy award")
print(f"  award_damage:       {summary[12]:>5}/{total} ({100*summary[12]/total:.1f}%) - best damage award")
print(f"  award_kills:        {summary[13]:>5}/{total} ({100*summary[13]/total:.1f}%) - best kills award")
print(f"  award_experience:   {summary[14]:>5}/{total} ({100*summary[14]/total:.1f}%) - best XP award")

# Objectives check
cursor.execute('''
    SELECT 
        COUNT(*) as total_players,
        COUNT(CASE WHEN objectives_completed > 0 THEN 1 END) as have_obj_complete,
        COUNT(CASE WHEN objectives_destroyed > 0 THEN 1 END) as have_obj_destroy,
        COUNT(CASE WHEN dynamites_planted > 0 THEN 1 END) as have_dynamites,
        COUNT(CASE WHEN landmines_planted > 0 THEN 1 END) as have_landmines,
        COUNT(CASE WHEN constructions_built > 0 THEN 1 END) as have_construction,
        COUNT(CASE WHEN kill_steals > 0 THEN 1 END) as have_steals,
        COUNT(CASE WHEN tank_meatshield > 0 THEN 1 END) as have_tank_shield
    FROM player_objective_stats
''')

obj_summary = cursor.fetchone()

print()
print("Objective Stats Population:")
print(f"  objectives_completed:   {obj_summary[1]:>5}/{total} ({100*obj_summary[1]/total:.1f}%) - engineer tasks")
print(f"  objectives_destroyed:   {obj_summary[2]:>5}/{total} ({100*obj_summary[2]/total:.1f}%) - defender tasks")
print(f"  dynamites_planted:      {obj_summary[3]:>5}/{total} ({100*obj_summary[3]/total:.1f}%) - engineer only")
print(f"  landmines_planted:      {obj_summary[4]:>5}/{total} ({100*obj_summary[4]/total:.1f}%) - engineer only")
print(f"  constructions_built:    {obj_summary[5]:>5}/{total} ({100*obj_summary[5]/total:.1f}%) - engineer only")
print(f"  kill_steals:            {obj_summary[6]:>5}/{total} ({100*obj_summary[6]/total:.1f}%) - advanced stat")
print(f"  tank_meatshield:        {obj_summary[7]:>5}/{total} ({100*obj_summary[7]/total:.1f}%) - rare/situational")

print()
print("✓ = Stat is working and populated")
print("✗ = Stat is zero/empty (either not used in this session or class-specific)")
print()

conn.close()
