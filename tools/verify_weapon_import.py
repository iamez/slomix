#!/usr/bin/env python3
"""Verify weapon stats import"""
import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

print("=" * 80)
print("WEAPON STATS VERIFICATION")
print("=" * 80)

# Count weapon stats
count = c.execute('SELECT COUNT(*) FROM weapon_comprehensive_stats').fetchone()[0]
print(f"\n✅ Weapon stats records: {count:,}")

# Count player stats
player_count = c.execute('SELECT COUNT(*) FROM player_comprehensive_stats').fetchone()[0]
print(f"✅ Player stats records: {player_count:,}")

# Get vid's weapon stats
print("\n🔫 vid's Weapon Stats:")
rows = c.execute(
    '''
    SELECT w.weapon_name,
           SUM(w.kills) as kills,
           SUM(w.shots) as shots,
           SUM(w.hits) as hits,
           SUM(w.headshots) as headshots,
           CASE WHEN SUM(w.shots) > 0
                THEN (SUM(w.hits) * 100.0 / SUM(w.shots))
                ELSE 0 END as accuracy
    FROM weapon_comprehensive_stats w
    WHERE w.player_guid IN (
        SELECT DISTINCT player_guid
        FROM player_comprehensive_stats
        WHERE clean_name LIKE '%vid%'
    )
    GROUP BY w.weapon_name
    ORDER BY kills DESC
    LIMIT 10
'''
).fetchall()

for row in rows:
    print(
        f"  {row[0]:<20} {row[1]:>3}K  {row[2]:>5} shots  {row[3]:>5} hits  "
        + f"{row[4]:>3} HS  {row[5]:>5.1f}% acc"
    )

# Check aggregated player stats
print("\n📊 vid's Aggregated Stats:")
stats = c.execute(
    '''
    SELECT
        SUM(kills) as total_kills,
        SUM(headshot_kills) as total_headshots,
        SUM(bullets_fired) as total_shots,
        CASE WHEN SUM(bullets_fired) > 0
             THEN (SUM(damage_given) * 100.0 / SUM(bullets_fired))
             ELSE 0 END as avg_accuracy,
        SUM(times_revived) as revives,
        SUM(gibs) as gibs,
        SUM(denied_playtime) as time_denied
    FROM player_comprehensive_stats
    WHERE clean_name LIKE '%vid%'
'''
).fetchone()

print(f"  Total kills: {stats[0]}")
print(f"  Headshot kills: {stats[1]}")
print(f"  Total shots: {stats[2]}")
print(f"  Accuracy: {stats[3]:.2f}%")
print(f"  Revives: {stats[4]}")
print(f"  Gibs: {stats[5]}")
print(f"  Time denied (seconds): {stats[6]}")

conn.close()
print("\n" + "=" * 80)
