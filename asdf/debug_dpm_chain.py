#!/usr/bin/env python3
"""
Debug DPM calculation chain from pa            # What ratio difference?
            if player.get('dpm') and manual_dpm:
                ratio = player['dpm'] / manual_dpm
                print(f"   Ratio (parser/manual): {ratio:.2f}") to database
"""
import sys
sys.path.append('./bot')

from community_stats_parser import C0RNP0RN3StatsParser

def debug_dpm_calculation():
    """Debug the complete DPM calculation chain"""
    
    print("🔍 DEBUG: DPM Calculation Chain")
    print("=" * 60)
    
    parser = C0RNP0RN3StatsParser()
    test_file = "./test_files/2025-09-24-233255-te_escape2-round-1.txt"
    
    # Step 1: Parse the file
    result = parser.parse_stats_file(test_file)
    
    if result['success']:
        print("📁 File parsed successfully")
        print(f"🗺️  Map: {result['map_name']}")
        print(f"⏱️  Map time: {result['map_time']}")
        print(f"⏱️  Actual time: {result['actual_time']}")
        print()
        
        # Convert time to minutes
        map_time = result['map_time']
        actual_time = result['actual_time']
        
        print(f"🔍 Time Analysis:")
        print(f"   Map time: {map_time}")
        print(f"   Actual time: {actual_time}")
        
        # Try to parse the actual time like the import system does
        try:
            if ':' in actual_time:
                parts = actual_time.split(':')
                round_duration = int(parts[0]) + int(parts[1]) / 60.0
            else:
                round_duration = 5.0
        except (ValueError, IndexError, TypeError):
            round_duration = 5.0
            
        print(f"   Calculated round duration: {round_duration} minutes")
        print()
        
        # Step 2: Check first few players
        players = result['players']
        
        for i, player in enumerate(players[:3], 1):
            print(f"👤 Player {i}: {player['name']}")
            print(f"   Parser DPM: {player.get('dpm', 'N/A')}")
            
            # Manual calculation like the import system
            damage_given = player.get('damage_given', 0)
            manual_dpm = damage_given / round_duration if round_duration > 0 else 0
            
            print(f"   Damage given: {damage_given}")
            print(f"   Round duration: {round_duration} min")
            print(f"   Manual DPM (import style): {manual_dpm:.1f}")
            
            # What ratio difference?
            if player.get('dpm') and manual_dmp:
                ratio = player['dpm'] / manual_dpm
                print(f"   Ratio (parser/manual): {ratio:.2f}")
            
            print()
    else:
        print(f"❌ Parse failed: {result}")

if __name__ == "__main__":
    debug_dpm_calculation()