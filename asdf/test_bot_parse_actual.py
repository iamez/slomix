#!/usr/bin/env python3
"""
Test the bot's actual parsing methods
"""
import sys
sys.path.append('./bot')

from community_stats_parser import C0RNP0RN3StatsParser

def test_bot_parse_methods():
    """Test the bot's actual parsing methods"""
    
    print("🤖 Testing Bot's Actual Parse Methods...")
    print("=" * 50)
    
    parser = C0RNP0RN3StatsParser()
    test_file = "./test_files/2025-09-24-233255-te_escape2-round-1.txt"
    
    try:
        # Test the parse_stats_file method
        print("📁 Testing parse_stats_file method...")
        result = parser.parse_stats_file(test_file)
        
        print(f"📊 Parse result type: {type(result)}")
        
        if isinstance(result, dict):
            print("🔍 Result keys:")
            for key in result.keys():
                print(f"   - {key}")
            print()
            
            # Look for player data
            if 'players' in result:
                players = result['players']
                print(f"👥 Found {len(players)} players")
                
                for i, player in enumerate(players[:2], 1):
                    print(f"\n👤 Player {i}:")
                    for key, value in player.items():
                        if key in ['name', 'damage', 'dpm', 'time_played', 'kills', 'deaths']:
                            print(f"   {key}: {value}")
                            
            # Look for round info
            if 'round_info' in result:
                round_info = result['round_info']
                print(f"\n📋 Round Info:")
                for key, value in round_info.items():
                    print(f"   {key}: {value}")
                    
        else:
            print(f"📊 Result: {result}")
            
    except Exception as e:
        print(f"❌ Error testing parse methods: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_bot_parse_methods()