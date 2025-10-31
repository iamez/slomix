#!/usr/bin/env python3
"""
STATS DEBUGGING SCRIPT
======================
This script will help identify what's wrong with your bot's stats parsing.

Usage:
    python debug_stats.py <stats_file.txt>

Example:
    python debug_stats.py /mnt/project/2025-10-30-230944-braundorf_b4-round-2.txt
"""

import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def debug_stats_file(file_path):
    """Debug a stats file to see what the parser is extracting"""
    
    print(f"\n{'='*80}")
    print(f"DEBUGGING: {os.path.basename(file_path)}")
    print(f"{'='*80}\n")
    
    # Try to import the parser
    try:
        from community_stats_parser import C0RNP0RN3StatsParser
        print("✅ Successfully imported C0RNP0RN3StatsParser")
    except ImportError as e:
        print(f"❌ Failed to import parser: {e}")
        print("\n💡 The community_stats_parser.py file is missing!")
        print("   You need to copy it from your bot directory.")
        return
    
    # Parse the file
    print(f"\n📄 Parsing file: {file_path}\n")
    parser = C0RNP0RN3StatsParser()
    
    try:
        result = parser.parse_stats_file(file_path)
    except Exception as e:
        print(f"❌ Parser crashed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    if not result or result.get('error'):
        print(f"❌ Parser returned error: {result.get('error') if result else 'No data'}")
        return
    
    print("✅ File parsed successfully!\n")
    
    # Print basic info
    print(f"📊 BASIC INFO")
    print(f"{'─'*80}")
    print(f"Map: {result.get('map_name')}")
    print(f"Round: {result.get('round_num')}")
    print(f"Players: {len(result.get('players', []))}")
    print(f"MVP: {result.get('mvp', 'Unknown')}")
    print(f"Outcome: {result.get('round_outcome', 'Unknown')}")
    
    # Print detailed player stats
    players = result.get('players', [])
    if not players:
        print("\n❌ NO PLAYERS FOUND!")
        return
    
    print(f"\n\n👥 PLAYER STATS (First 3 players)")
    print(f"{'─'*80}\n")
    
    for idx, player in enumerate(players[:3], 1):
        print(f"PLAYER #{idx}: {player.get('name', 'Unknown')}")
        print(f"{'─'*40}")
        
        # Basic combat stats
        print(f"  GUID: {player.get('guid', 'N/A')}")
        print(f"  Team: {player.get('team', 'N/A')}")
        print(f"  Kills: {player.get('kills', 0)}")
        print(f"  Deaths: {player.get('deaths', 0)}")
        print(f"  K/D: {player.get('kd_ratio', 0):.2f}")
        print(f"  Headshots: {player.get('headshots', 0)}")
        
        # Damage stats
        print(f"  Damage Given: {player.get('damage_given', 0)}")
        print(f"  Damage Received: {player.get('damage_received', 0)}")
        print(f"  DPM: {player.get('dpm', 0):.1f}")
        
        # Check if objective_stats exists
        obj_stats = player.get('objective_stats', {})
        if not obj_stats:
            print(f"\n  ⚠️  WARNING: objective_stats is EMPTY or MISSING!")
            print(f"  This is likely why your bot is showing wrong stats!")
        else:
            print(f"\n  ✅ objective_stats EXISTS ({len(obj_stats)} fields)")
            print(f"     Gibs: {obj_stats.get('gibs', 'MISSING')}")
            print(f"     Self Kills: {obj_stats.get('self_kills', 'MISSING')}")
            print(f"     Team Kills: {obj_stats.get('team_kills', 'MISSING')}")
            print(f"     XP: {obj_stats.get('xp', 'MISSING')}")
            print(f"     Revives: {obj_stats.get('revives_given', 'MISSING')}")
            print(f"     Denied Playtime: {obj_stats.get('denied_playtime', 'MISSING')}")
        
        # Time stats
        print(f"\n  Time Played (seconds): {player.get('time_played_seconds', 'MISSING')}")
        print(f"  Time Played (minutes): {player.get('time_played_minutes', 'MISSING')}")
        
        # Weapon stats check
        weapon_stats = player.get('weapon_stats', {})
        if weapon_stats:
            print(f"\n  🔫 Weapon Stats: {len(weapon_stats)} weapons")
            for weapon_name, weapon_data in list(weapon_stats.items())[:3]:
                print(f"     - {weapon_name}: {weapon_data.get('kills', 0)}K / "
                      f"{weapon_data.get('deaths', 0)}D / "
                      f"{weapon_data.get('accuracy', 0):.1f}% ACC")
        else:
            print(f"\n  ⚠️  No weapon stats found!")
        
        print()
    
    # Summary
    print(f"\n{'='*80}")
    print("DIAGNOSTIC SUMMARY")
    print(f"{'='*80}")
    
    issues = []
    
    # Check for common issues
    for player in players:
        obj_stats = player.get('objective_stats', {})
        
        if not obj_stats:
            issues.append("❌ objective_stats is missing/empty")
            break
        
        if obj_stats.get('gibs') is None:
            issues.append("❌ gibs field is missing from objective_stats")
            break
        
        if player.get('dpm', 0) == 0 and player.get('damage_given', 0) > 0:
            issues.append("⚠️  DPM is 0 but damage_given exists (calculation issue?)")
            break
    
    if not issues:
        print("✅ No obvious issues found!")
        print("\n💡 If your bot is still showing wrong stats, the issue might be:")
        print("   - In the database insertion logic")
        print("   - In the query/display code")
        print("   - In how fields are mapped between parser and database")
    else:
        print("🔍 ISSUES FOUND:\n")
        for issue in issues:
            print(f"   {issue}")
        
        print("\n💡 NEXT STEPS:")
        print("   1. Check if community_stats_parser.py was recently changed")
        print("   2. Compare with the working version from your last chat")
        print("   3. Look for field name changes (e.g., 'gibs' vs 'objective_stats.gibs')")
        print("   4. Check if the TAB field order in c0rnp0rn3.lua changed")
    
    print()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_stats.py <stats_file.txt>")
        print("\nExample:")
        print("  python debug_stats.py /mnt/project/2025-10-30-230944-braundorf_b4-round-2.txt")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        sys.exit(1)
    
    debug_stats_file(file_path)
