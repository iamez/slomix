#!/usr/bin/env python3
"""
Check for duplicate player records in sessions
"""
import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

print("="*70)
print("DUPLICATE PLAYER RECORDS CHECK")
print("="*70)

# Check for duplicate players in same session
duplicates = c.execute('''
    SELECT session_id, player_name, COUNT(*) as count
    FROM player_comprehensive_stats
    GROUP BY session_id, player_name
    HAVING COUNT(*) > 1
    ORDER BY count DESC, session_id
    LIMIT 20
''').fetchall()

if duplicates:
    print(f"\n⚠️  Found {len(duplicates)} instances of duplicate players:")
    print("\nTop duplicates:")
    for sess_id, name, count in duplicates[:10]:
        print(f"  Session {sess_id}: '{name}' appears {count} times")
    
    # Check a specific example
    if duplicates:
        sess_id, name, count = duplicates[0]
        print(f"\n{'='*70}")
        print(f"DETAILED VIEW: Session {sess_id}, Player '{name}'")
        print(f"{'='*70}")
        
        records = c.execute('''
            SELECT id, player_guid, team, kills, deaths, damage_given, xp
            FROM player_comprehensive_stats
            WHERE session_id = ? AND player_name = ?
        ''', (sess_id, name)).fetchall()
        
        print(f"\nFound {len(records)} records for this player:")
        for rec in records:
            rec_id, guid, team, kills, deaths, dmg, xp = rec
            team_name = {1:'Axis', 2:'Allies', 3:'Spec'}.get(team, '?')
            print(f"  ID {rec_id}: GUID={guid[:16]}... Team={team_name} "
                  f"K={kills} D={deaths} Dmg={dmg} XP={xp}")
else:
    print("\n✅ No duplicate player records found!")

# Check total duplicate count
total_dupes = c.execute('''
    SELECT COUNT(*) 
    FROM (
        SELECT session_id, player_name, COUNT(*) as cnt
        FROM player_comprehensive_stats
        GROUP BY session_id, player_name
        HAVING COUNT(*) > 1
    )
''').fetchone()[0]

print(f"\nTotal sessions with duplicate players: {total_dupes}")

# Check how many "extra" records exist
total_records = c.execute(
    'SELECT COUNT(*) FROM player_comprehensive_stats'
).fetchone()[0]
unique_combos = c.execute('''
    SELECT COUNT(DISTINCT session_id || player_name)
    FROM player_comprehensive_stats
''').fetchone()[0]

extra_records = total_records - unique_combos
print(f"\nTotal player records: {total_records:,}")
print(f"Unique (session + player) combinations: {unique_combos:,}")
print(f"Extra/duplicate records: {extra_records:,}")

if extra_records > 0:
    pct = (extra_records / total_records * 100)
    print(f"Duplicate percentage: {pct:.1f}%")

conn.close()
