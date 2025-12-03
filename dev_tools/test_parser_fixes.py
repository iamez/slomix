"""
Test that the fixes work by re-importing one session
"""
import sqlite3
import sys
from pathlib import Path

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent / 'bot'))

from community_stats_parser import C0RNP0RN3StatsParser

def test_reimport():
    """Test re-importing the problematic session"""
    
    # Parse the file
    parser = C0RNP0RN3StatsParser()
    file_path = 'local_stats/2025-10-28-212120-etl_adlernest-round-1.txt'
    
    print(f"Parsing: {file_path}")
    result = parser.parse_stats_file(file_path)
    
    if not result or 'players' not in result:
        print(f"❌ Parse failed: {result}")
        return
    
    print("✅ Parsed successfully")
    print(f"Players: {len(result['players'])}")
    
    # Check SuperBoyy's stats
    superboyy = None
    for p in result['players']:
        if 'SuperBoyy' in p['name']:
            superboyy = p
            break
    
    if not superboyy:
        print("❌ SuperBoyy not found!")
        return
    
    obj_stats = superboyy.get('objective_stats', {})
    
    print(f"\n{'='*80}")
    print("SuperBoyy's stats from parser:")
    print(f"{'='*80}")
    print(f"team_damage_given (from obj_stats): {obj_stats.get('team_damage_given', 'MISSING')}")
    print(f"team_damage_received (from obj_stats): {obj_stats.get('team_damage_received', 'MISSING')}")
    print(f"headshot_kills (from obj_stats): {obj_stats.get('headshot_kills', 'MISSING')}")
    print(f"useful_kills (from obj_stats): {obj_stats.get('useful_kills', 'MISSING')}")
    print(f"multikill_2x (from obj_stats): {obj_stats.get('multikill_2x', 'MISSING')}")
    print(f"repairs_constructions (from obj_stats): {obj_stats.get('repairs_constructions', 'MISSING')}")
    
    print(f"\n{'='*80}")
    print("Checking what OLD code would have done:")
    print(f"{'='*80}")
    print(f"team_damage_given (player.get): {superboyy.get('team_damage_given', 0)} ❌")
    print(f"team_damage_received (player.get): {superboyy.get('team_damage_received', 0)} ❌")
    print(f"headshots (player.get): {superboyy.get('headshots', 0)} (weapon total)")
    print(f"headshot_kills (obj_stats.get): {obj_stats.get('headshot_kills', 0)} ✅")
    
    print(f"\n{'='*80}")
    print("EXPECTED VALUES (from raw file check):")
    print(f"{'='*80}")
    print("team_damage_given: 85")
    print("team_damage_received: 18")
    print("headshot_kills: 4")
    print("useful_kills: 2")
    print("multikill_2x: 2")
    
    print(f"\n{'='*80}")
    print("VERIFICATION:")
    print(f"{'='*80}")
    
    checks = [
        ('team_damage_given', obj_stats.get('team_damage_given', 0), 85),
        ('team_damage_received', obj_stats.get('team_damage_received', 0), 18),
        ('headshot_kills', obj_stats.get('headshot_kills', 0), 4),
        ('useful_kills', obj_stats.get('useful_kills', 0), 2),
        ('multikill_2x', obj_stats.get('multikill_2x', 0), 2),
    ]
    
    all_good = True
    for field, actual, expected in checks:
        status = "✅" if actual == expected else "❌"
        print(f"{status} {field}: {actual} (expected {expected})")
        if actual != expected:
            all_good = False
    
    if all_good:
        print("\n🎉 ALL CHECKS PASSED! Parser is working correctly!")
    else:
        print("\n⚠️  Some checks failed. Parser may need additional fixes.")

if __name__ == '__main__':
    test_reimport()
