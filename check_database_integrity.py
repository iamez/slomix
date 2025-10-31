#!/usr/bin/env python3
"""
Database integrity checker
"""
import sqlite3

def check_database_integrity():
    """Check for NULL values, orphaned records, and data inconsistencies"""
    conn = sqlite3.connect('etlegacy_production.db')
    c = conn.cursor()
    
    issues = []
    
    print("\n🔍 DATABASE INTEGRITY CHECK")
    print("=" * 80)
    
    # Check for NULL player_guid
    c.execute('''SELECT COUNT(*) FROM player_comprehensive_stats 
                 WHERE player_guid IS NULL OR player_guid = ""''')
    null_guids = c.fetchone()[0]
    if null_guids > 0:
        issues.append(f"❌ {null_guids} records with NULL/empty player_guid")
    else:
        print(f"✅ No NULL player_guid values")
    
    # Check for NULL player_name
    c.execute('''SELECT COUNT(*) FROM player_comprehensive_stats 
                 WHERE player_name IS NULL OR player_name = ""''')
    null_names = c.fetchone()[0]
    if null_names > 0:
        issues.append(f"❌ {null_names} records with NULL/empty player_name")
    else:
        print(f"✅ No NULL player_name values")
    
    # Check for orphaned player records
    # NOTE: sessions.session_date has timestamps (2025-01-01-211921)
    #       player_comprehensive_stats.session_date has dates (2025-01-01)
    #       So we need to use LIKE pattern matching
    c.execute('''SELECT COUNT(*) FROM player_comprehensive_stats p 
                 WHERE NOT EXISTS (
                     SELECT 1 FROM sessions s 
                     WHERE s.session_date LIKE p.session_date || '%'
                     AND s.map_name = p.map_name
                 )''')
    orphaned = c.fetchone()[0]
    if orphaned > 0:
        issues.append(f"❌ {orphaned} orphaned player records (no matching session)")
    else:
        print(f"✅ No orphaned player records")
    
    # Check for NULL weapon player_guid
    c.execute('''SELECT COUNT(*) FROM weapon_comprehensive_stats 
                 WHERE player_guid IS NULL OR player_guid = ""''')
    null_weapon_guids = c.fetchone()[0]
    if null_weapon_guids > 0:
        issues.append(f"❌ {null_weapon_guids} weapon records with NULL player_guid")
    else:
        print(f"✅ No NULL weapon player_guid values")
    
    # Check for weapon records without matching player
    c.execute('''SELECT COUNT(*) FROM weapon_comprehensive_stats w 
                 WHERE NOT EXISTS (
                     SELECT 1 FROM player_comprehensive_stats p 
                     WHERE p.player_guid = w.player_guid 
                     AND p.session_date = w.session_date 
                     AND p.map_name = w.map_name
                 )''')
    orphaned_weapons = c.fetchone()[0]
    if orphaned_weapons > 0:
        issues.append(f"⚠️ {orphaned_weapons} weapon records without matching player")
    else:
        print(f"✅ No orphaned weapon records")
    
    # Check sessions table
    c.execute('SELECT COUNT(*) FROM sessions WHERE map_name IS NULL OR map_name = ""')
    null_maps = c.fetchone()[0]
    if null_maps > 0:
        issues.append(f"❌ {null_maps} sessions with NULL/empty map_name")
    else:
        print(f"✅ No NULL map_name in sessions")
    
    # Check for duplicate sessions
    c.execute('''SELECT session_date, map_name, COUNT(*) as cnt 
                 FROM sessions 
                 GROUP BY session_date, map_name 
                 HAVING cnt > 1''')
    duplicates = c.fetchall()
    if duplicates:
        issues.append(f"⚠️ {len(duplicates)} duplicate session records")
        for dup in duplicates[:5]:
            print(f"  Duplicate: {dup[0]} - {dup[1]} ({dup[2]} times)")
    else:
        print(f"✅ No duplicate sessions")
    
    print("\n" + "=" * 80)
    
    if issues:
        print("\n⚠️ ISSUES FOUND:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("\n✅ DATABASE INTEGRITY: PERFECT!")
    
    conn.close()
    return len(issues) == 0

if __name__ == '__main__':
    check_database_integrity()
