#!/usr/bin/env python3
"""Check database structure and sample data"""
import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

print("=" * 80)
print("DATABASE STRUCTURE CHECK")
print("=" * 80)

# Tables
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("\n📊 Tables:")
for t in tables:
    count = c.execute(f'SELECT COUNT(*) FROM {t[0]}').fetchone()[0]
    print(f"  • {t[0]}: {count:,} records")

# Check weapon stats structure if it exists
if any('weapon' in t[0].lower() for t in tables):
    print("\n🔫 Weapon Stats Columns:")
    weapon_cols = c.execute('PRAGMA table_info(weapon_comprehensive_stats)').fetchall()
    for col in weapon_cols:
        print(f"  {col[1]} ({col[2]})")

    # Sample weapon data
    print("\n🎯 Sample Weapon Data (vid):")
    sample = c.execute(
        '''
        SELECT weapon_name, kills, deaths, headshots, shots_fired, shots_hit
        FROM weapon_comprehensive_stats
        WHERE player_name LIKE '%vid%'
        LIMIT 5
    '''
    ).fetchall()
    for row in sample:
        print(f"  {row[0]}: {row[1]}K/{row[2]}D, {row[3]} HS, {row[4]} fired, {row[5]} hit")

# Check if we have accuracy/headshot data
print("\n📈 Sample Player Stats (vid - first record):")
vid_stats = c.execute(
    '''
    SELECT
        player_name, kills, deaths, headshot_kills,
        bullets_fired, accuracy, headshot_ratio,
        times_revived, gibs, denied_playtime
    FROM player_comprehensive_stats
    WHERE clean_name LIKE '%vid%'
    LIMIT 1
'''
).fetchone()

if vid_stats:
    print(f"  Player: {vid_stats[0]}")
    print(f"  K/D: {vid_stats[1]}/{vid_stats[2]}")
    print(f"  Headshot kills: {vid_stats[3]}")
    print(f"  Bullets fired: {vid_stats[4]}")
    print(f"  Accuracy: {vid_stats[5]}")
    print(f"  HS Ratio: {vid_stats[6]}")
    print(f"  Times revived: {vid_stats[7]}")
    print(f"  Gibs: {vid_stats[8]}")
    print(f"  Denied playtime: {vid_stats[9]}")

conn.close()
print("\n" + "=" * 80)
