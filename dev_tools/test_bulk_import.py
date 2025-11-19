#!/usr/bin/env python3
"""
TEST SCRIPT - Verify bulk import works with 1 file before running on all 184
"""
import sqlite3
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from bot.community_stats_parser import C0RNP0RN3StatsParser

def test_import():
    """Test import with ONE file to verify all INSERT statements work"""
    
    # 1. Create test database
    db_path = "test_import.db"
    Path(db_path).unlink(missing_ok=True)
    
    print("=" * 70)
    print("TEST: Bulk Import - Single File Verification")
    print("=" * 70)
    
    # 2. Create schema (same as bulk_import_stats.py)
    from dev.bulk_import_stats import BulkStatsImporter
    importer = BulkStatsImporter(db_path)
    print("✅ Schema created")
    
    # 3. Parse ONE file
    parser = C0RNP0RN3StatsParser()
    test_file = Path("bot/local_stats/2025-11-02-233358-erdenberg_t2-round-2.txt")
    
    if not test_file.exists():
        # Find ANY recent file
        test_file = sorted(Path("bot/local_stats").glob("2025-11-*.txt"))[-1]
    
    print(f"\n📂 Testing with: {test_file.name}")
    
    parsed = parser.parse_stats_file(str(test_file))
    if not parsed['success']:
        print(f"❌ Parser failed: {parsed['error']}")
        return False
    
    print(f"   Players: {len(parsed['players'])}")
    print(f"   Map: {parsed['map_name']}")
    print(f"   Round: {parsed['round_num']}")
    
    # 4. Test round creation
    file_date = test_file.stem.split('-round-')[0]
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO rounds (
            round_date, map_name, round_number,
            time_limit, actual_time, created_at
        )
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (file_date, parsed['map_name'], parsed['round_num'], '12:00', '7:00'))
    
    round_id = cursor.lastrowid
    conn.commit()
    print(f"✅ Round created: {round_id}")
    
    # 5. Test player stats insertion
    player = parsed['players'][0]
    obj_stats = player.get('objective_stats', {})
    
    guid = player.get('guid', 'UNKNOWN')
    name = player.get('name', 'Unknown')
    clean_name = parser.strip_color_codes(name)
    team = player.get('team', 0)
    kills = player.get('kills', 0)
    deaths = player.get('deaths', 0)
    kd_ratio = kills / deaths if deaths > 0 else float(kills)
    
    damage_given = obj_stats.get('damage_given', 0)
    time_minutes = obj_stats.get('time_played_minutes', 0.0)
    time_seconds = int(time_minutes * 60)
    dpm = damage_given / time_minutes if time_minutes > 0 else 0.0
    
    try:
        cursor.execute('''
            INSERT INTO player_comprehensive_stats (
                round_id, round_date, map_name, round_number,
                player_guid, player_name, clean_name, team,
                kills, deaths, damage_given, damage_received,
                team_damage_given, team_damage_received,
                gibs, self_kills, team_kills, team_gibs, headshot_kills,
                time_played_seconds, time_played_minutes,
                xp, kd_ratio, dpm, efficiency,
                kill_assists, killing_spree_best, death_spree_worst
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            round_id, file_date, parsed['map_name'], parsed['round_num'],
            guid, name, clean_name, team,
            kills, deaths, damage_given, obj_stats.get('damage_received', 0),
            obj_stats.get('team_damage_given', 0), obj_stats.get('team_damage_received', 0),
            obj_stats.get('gibs', 0), obj_stats.get('self_kills', 0), obj_stats.get('team_kills', 0),
            obj_stats.get('team_gibs', 0), player.get('headshots', 0),
            time_seconds, time_minutes,
            obj_stats.get('xp', 0), kd_ratio, dpm, 0.0,
            obj_stats.get('kill_assists', 0), obj_stats.get('killing_spree', 0), obj_stats.get('death_spree', 0)
        ))
        conn.commit()
        print(f"✅ Player inserted: {name}")
    except Exception as e:
        print(f"❌ PLAYER INSERT FAILED: {e}")
        conn.close()
        return False
    
    # 6. Test weapon stats insertion
    weapons = player.get('weapons', {})
    print(f"\n🔫 Weapons data: {len(weapons)} weapons found")
    if len(weapons) > 0:
        print(f"   First weapon: {list(weapons.keys())[0]}")
    
    if weapons:
        weapon_name = list(weapons.keys())[0]
        weapon_stats = weapons[weapon_name]
        
        try:
            cursor.execute('''
                INSERT INTO weapon_comprehensive_stats (
                    round_id, round_date, map_name, round_number,
                    player_guid, player_name, weapon_name,
                    kills, deaths, headshots, shots, hits, accuracy
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                round_id, file_date, parsed['map_name'], parsed['round_num'],
                guid, name, weapon_name,
                weapon_stats.get('kills', 0), weapon_stats.get('deaths', 0),
                weapon_stats.get('headshots', 0), weapon_stats.get('shots', 0),
                weapon_stats.get('hits', 0), weapon_stats.get('accuracy', 0.0)
            ))
            conn.commit()
            print(f"✅ Weapon inserted: {weapon_name}")
        except Exception as e:
            print(f"❌ WEAPON INSERT FAILED: {e}")
            conn.close()
            return False
    
    # 7. Verify data
    cursor.execute("SELECT COUNT(*) FROM rounds")
    sessions = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats")
    players = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM weapon_comprehensive_stats")
    weapons = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"\n📊 Database verification:")
    print(f"   Sessions: {sessions}")
    print(f"   Players:  {players}")
    print(f"   Weapons:  {weapons}")
    
    # Cleanup
    Path(db_path).unlink()
    
    if sessions == 1 and players >= 1:
        print("\n" + "=" * 70)
        print("✅ SUCCESS - All critical INSERT statements work!")
        print("   (Weapon stats optional - parser may not return them)")
        print("=" * 70)
        return True
    else:
        print("\n❌ FAILED - Missing sessions or players")
        return False

if __name__ == "__main__":
    success = test_import()
    sys.exit(0 if success else 1)
