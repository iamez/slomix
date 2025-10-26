#!/usr/bin/env python3
"""Test stats parsing and differential calculation"""

from c0rnporn3_parser import C0RNP0RN3StatsParser

def test_differential():
    parser = C0RNP0RN3StatsParser()
    
    # Test with first pair
    r1_file = '2025-09-24-233255-te_escape2-round-1.txt'
    r2_file = '2025-09-24-233657-te_escape2-round-2.txt'
    
    print("Testing differential calculation:")
    print(f"  Round 1: {r1_file}")
    print(f"  Round 2: {r2_file}")
    print()
    
    try:
        r1_result = parser.parse_stats_file(r1_file)
        r2_result = parser.parse_stats_file(r2_file)
        
        if not r1_result or not r1_result.get('success'):
            print("Failed to parse Round 1")
            return False
            
        if not r2_result or not r2_result.get('success'):
            print("Failed to parse Round 2")
            return False
        
        r1_players = r1_result['players']
        r2_players = r2_result['players']
        
        print(f"Round 1: {len(r1_players)} players")
        print(f"Round 2: {len(r2_players)} players")
        
        # Create GUID->player mappings
        r1_by_guid = {p['guid']: p for p in r1_players}
        r2_by_guid = {p['guid']: p for p in r2_players}
        
        common_guids = set(r1_by_guid.keys()) & set(r2_by_guid.keys())
        print(f"Common players: {len(common_guids)}")
        
        if common_guids:
            first_guid = next(iter(common_guids))
            r1_player = r1_by_guid[first_guid]
            r2_player = r2_by_guid[first_guid]
            
            print(f"\nFirst player GUID: {first_guid}")
            print(f"Name: {r1_player.get('clean_name', 'Unknown')}")
            print(f"R1 kills: {r1_player.get('total_kills', 0)}")
            print(f"R2 kills (cumulative): {r2_player.get('total_kills', 0)}")
            differential = r2_player.get('total_kills', 0) - r1_player.get('total_kills', 0)
            print(f"R2 differential: {differential}")
            
            r1_dpm = r1_player.get('dpm', 0)
            r2_dpm = r2_player.get('dpm', 0)
            print(f"R1 DPM: {r1_dpm:.1f}")
            print(f"R2 DPM (cumulative): {r2_dpm:.1f}")
            
            # This demonstrates the bug - R2 DPM should be lower if it's truly differential
            if r2_dpm > r1_dpm * 1.5:
                print("⚠️  R2 DPM suspiciously high - likely cumulative bug!")
            
            return True
        else:
            print("No common players found")
            return False
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_differential()