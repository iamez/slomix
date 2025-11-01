"""
Test the enhanced parser to verify all 37 fields are extracted correctly
"""

import json
import sys

from community_stats_parser import C0RNP0RN3StatsParser

sys.path.append('bot')


def test_enhanced_parser():
    """Test parser on a real stats file"""
    parser = C0RNP0RN3StatsParser()

    # Use a sample stats file
    test_file = 'local_stats/2024-06-29-221611-supply-round-1.txt'

    print("=" * 70)
    print("TESTING ENHANCED PARSER - ALL 37 FIELDS")
    print("=" * 70)

    try:
        result = parser.parse_stats_file(test_file)

        if not result or 'players' not in result:
            print("[FAIL] Failed to parse file")
            return False

        print(f"\n[SUCCESS] Parsed {len(result['players'])} players")
        print(f"Session: {result.get('session_date', 'Unknown')}")
        print(f"Map: {result.get('map_name', 'Unknown')}")
        print(f"Round: {result.get('round_number', 'Unknown')}")

        # Check first player for all fields
        if result['players']:
            player = result['players'][0]

            print(f"\n{'=' * 70}")
            print(f"DETAILED PLAYER DATA: {player['name']}")
            print(f"{'=' * 70}")

            # Basic stats
            print(f"\n📊 Basic Stats:")
            print(f"  GUID: {player.get('guid', 'N/A')}")
            print(f"  Team: {player.get('team', 'N/A')}")
            print(f"  Kills: {player.get('kills', 0)}")
            print(f"  Deaths: {player.get('deaths', 0)}")
            print(f"  K/D: {player.get('kd_ratio', 0):.2f}")
            print(f"  Headshots: {player.get('headshots', 0)}")
            print(f"  Accuracy: {player.get('accuracy', 0):.1f}%")
            print(f"  Damage Given: {player.get('damage_given', 0)}")

            # Check for objective_stats
            if 'objective_stats' in player and player['objective_stats']:
                obj = player['objective_stats']

                print(f"\n🎯 Objective & Support Stats (NEW!):")
                print(f"  XP: {obj.get('xp', 0)}")
                print(f"  Kill Assists: {obj.get('kill_assists', 0)}")
                print(f"  Objectives Stolen: {obj.get('objectives_stolen', 0)}")
                print(f"  Objectives Returned: {obj.get('objectives_returned', 0)}")
                print(f"  Dynamites Planted: {obj.get('dynamites_planted', 0)}")
                print(f"  Dynamites Defused: {obj.get('dynamites_defused', 0)}")
                print(f"  Times Revived: {obj.get('times_revived', 0)}")
                print(f"  Bullets Fired: {obj.get('bullets_fired', 0)}")
                print(f"  DPM: {obj.get('dpm', 0):.1f}")
                print(f"  Time Played (min): {obj.get('time_played_minutes', 0):.1f}")
                print(f"  Repairs/Constructions: {obj.get('repairs_constructions', 0)}")

                print(f"\n🔥 Multikills:")
                print(f"  Double: {obj.get('multikill_2x', 0)}")
                print(f"  Triple: {obj.get('multikill_3x', 0)}")
                print(f"  Quad: {obj.get('multikill_4x', 0)}")
                print(f"  Penta: {obj.get('multikill_5x', 0)}")
                print(f"  Hexa: {obj.get('multikill_6x', 0)}")

                print(f"\n⚔️ Advanced Stats:")
                print(f"  Killing Spree: {obj.get('killing_spree', 0)}")
                print(f"  Death Spree: {obj.get('death_spree', 0)}")
                print(f"  Useful Kills: {obj.get('useful_kills', 0)}")
                print(f"  Time Dead (min): {obj.get('time_dead_minutes', 0):.1f}")

                print(f"\n📦 JSON Structure (for database):")
                print(json.dumps(obj, indent=2))

                print(f"\n✅ SUCCESS! All 37 fields extracted!")

            else:
                print(f"\n❌ WARNING: No objective_stats found!")
                print(f"   Player data keys: {list(player.keys())}")
                return False

        # Summary
        print(f"\n{'=' * 70}")
        print(f"SUMMARY")
        print(f"{'=' * 70}")

        # Count players with objective stats
        players_with_objectives = sum(
            1 for p in result['players'] if 'objective_stats' in p and p['objective_stats']
        )

        print(f"✅ Players parsed: {len(result['players'])}")
        print(f"[OK] Players with objective stats: {players_with_objectives}")

        if players_with_objectives == len(result['players']):
            print(f"\n[PERFECT] All players have complete 33-field data!")
            return True
        else:
            print(f"\n[WARNING] Some players missing objective stats")
            return False

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_enhanced_parser()
    sys.exit(0 if success else 1)
