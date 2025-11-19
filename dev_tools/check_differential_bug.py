#!/usr/bin/env python3
"""
Check if Round 2 differentials are being calculated correctly
Verifies that R2 stats = (Cumulative R1+R2) - (R1 only)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from bot.community_stats_parser import C0RNP0RN3StatsParser

def check_differential():
    parser = C0RNP0RN3StatsParser()
    stats_dir = Path("local_stats")
    
    # Find a recent Round 2 file
    round2_files = sorted([f for f in stats_dir.glob("*-round-2.txt") if "2025-11" in f.name])
    
    if not round2_files:
        print("❌ No Round 2 files found from November 2025")
        return
    
    test_file = round2_files[-1]  # Get latest
    print(f"🧪 Testing with: {test_file.name}")
    
    # Parse the Round 2 file
    result = parser.parse_stats_file(str(test_file))
    
    print(f"\n{'='*70}")
    print(f"📊 PARSER OUTPUT ANALYSIS")
    print(f"{'='*70}")
    
    # Check field names
    print(f"\n🔍 Field Name Check:")
    print(f"  ✓ Has 'round_num' field: {('round_num' in result)}")
    print(f"  ✓ Has 'round_number' field: {('round_number' in result)}")
    
    if 'round_num' in result:
        print(f"  → round_num value: {result['round_num']}")
    if 'round_number' in result:
        print(f"  → round_number value: {result['round_number']}")
    
    # Check match summary
    print(f"\n🎯 Match Summary Check:")
    has_match_summary = 'match_summary' in result
    print(f"  ✓ Has match_summary: {has_match_summary}")
    
    if has_match_summary:
        ms = result['match_summary']
        print(f"  → Match summary round_num: {ms.get('round_num', 'MISSING!')}")
        print(f"  → Match summary round_number: {ms.get('round_number', 'MISSING!')}")
        
        # Check if match summary has players
        if 'players' in ms and ms['players']:
            ms_player = ms['players'][0]
            print(f"\n  📋 Match Summary Player Sample: {ms_player['name']}")
            print(f"     - Kills: {ms_player.get('kills', 0)}")
            print(f"     - Deaths: {ms_player.get('deaths', 0)}")
            print(f"     - XP: {ms_player.get('xp', 0)}")
    
    # Check differential (main result)
    print(f"\n⚔️  Round 2 Differential Check:")
    print(f"  → Main result round_num: {result.get('round_num', 'MISSING!')}")
    
    if result.get('players'):
        diff_player = result['players'][0]
        print(f"\n  📋 Differential Player Sample: {diff_player['name']}")
        print(f"     - Kills: {diff_player.get('kills', 0)}")
        print(f"     - Deaths: {diff_player.get('deaths', 0)}")
        print(f"     - XP: {diff_player.get('xp', 0)}")
        print(f"     → Should be LOWER than match summary (R2 only, not cumulative)")
    
    # Comparison
    if has_match_summary and result.get('players') and ms.get('players'):
        print(f"\n{'='*70}")
        print(f"🔬 DIFFERENTIAL VALIDATION")
        print(f"{'='*70}")
        
        # Find same player in both
        for ms_p in ms['players'][:3]:  # Check first 3 players
            name = ms_p['name']
            diff_p = next((p for p in result['players'] if p['name'] == name), None)
            
            if diff_p:
                ms_kills = ms_p.get('kills', 0)
                diff_kills = diff_p.get('kills', 0)
                
                print(f"\n👤 {name}:")
                print(f"   Match Summary (R1+R2): {ms_kills} kills")
                print(f"   Differential (R2 only): {diff_kills} kills")
                
                if diff_kills > ms_kills:
                    print(f"   ❌ BUG! Differential > Cumulative")
                elif diff_kills == ms_kills:
                    print(f"   ⚠️  WARNING: Equal values (might be R1=0 kills)")
                else:
                    print(f"   ✅ CORRECT: Differential < Cumulative")
    
    print(f"\n{'='*70}")
    print(f"✅ Analysis complete!")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    try:
        check_differential()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
