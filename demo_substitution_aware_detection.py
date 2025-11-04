"""
Demo: Advanced Team Detection WITH Substitution Awareness

Shows how substitution detection improves team assignment accuracy.
"""

import sqlite3
from bot.core.advanced_team_detector import AdvancedTeamDetector
from bot.core.substitution_detector import SubstitutionDetector

def demo_with_substitutions(round_date: str, db_path: str = "bot/etlegacy_production.db"):
    """
    Demonstrate team detection with substitution awareness
    """
    
    db = sqlite3.connect(db_path)
    
    print("=" * 80)
    print("🎯 TEAM DETECTION WITH SUBSTITUTION AWARENESS")
    print("=" * 80)
    print(f"Round: {round_date}")
    print()
    
    # Step 1: Analyze substitutions
    print("📋 Step 1: Analyzing Roster Changes...")
    print("-" * 80)
    
    sub_detector = SubstitutionDetector()
    sub_analysis = sub_detector.analyze_session_roster_changes(db, round_date)
    
    if sub_analysis:
        print(sub_analysis['summary'])
        print()
        
        if sub_analysis['substitutions']:
            print(f"🔄 Found {len(sub_analysis['substitutions'])} substitutions:")
            player_activity = sub_analysis['player_activity']
            for guid_out, guid_in, round_num in sub_analysis['substitutions'][:5]:
                name_out = player_activity[guid_out].player_name
                name_in = player_activity[guid_in].player_name
                print(f"   Round {round_num}: {name_out} → {name_in}")
            print()
        
        if sub_analysis['late_joiners']:
            print(f"⏱️  Late joiners ({len(sub_analysis['late_joiners'])}):")
            for guid in sub_analysis['late_joiners'][:5]:
                activity = sub_analysis['player_activity'][guid]
                print(f"   - {activity.player_name} (joined round {activity.first_round})")
            print()
        
        if sub_analysis['early_leavers']:
            print(f"👋 Early leavers ({len(sub_analysis['early_leavers'])}):")
            for guid in sub_analysis['early_leavers'][:5]:
                activity = sub_analysis['player_activity'][guid]
                print(f"   - {activity.player_name} (left after round {activity.last_round})")
            print()
    else:
        print("✅ No roster changes detected - stable session")
        print()
    
    # Step 2: Run team detection
    print("🔍 Step 2: Running Advanced Team Detection...")
    print("-" * 80)
    
    team_detector = AdvancedTeamDetector()
    result = team_detector.detect_session_teams(db, round_date)
    
    if not result:
        print("❌ Detection failed")
        db.close()
        return
    
    metadata = result['metadata']
    print(f"Quality: {metadata['detection_quality'].upper()}")
    print(f"Confidence: {metadata['avg_confidence']:.1%}")
    print()
    
    # Step 3: Show team assignments with roster context
    print("👥 Step 3: Team Assignments with Context...")
    print("-" * 80)
    
    team_a = result['Team A']
    team_b = result['Team B']
    
    print(f"🔴 Team A ({len(team_a['guids'])} players):")
    for guid, name in zip(team_a['guids'], team_a['names']):
        context = ""
        if sub_analysis:
            activity = sub_analysis['player_activity'].get(guid)
            if activity:
                if activity.is_late_joiner:
                    context = f" [joined R{activity.first_round}]"
                elif activity.first_round == 1:
                    context = " [full session]"
        
        print(f"   - {name}{context}")
    print()
    
    print(f"🔵 Team B ({len(team_b['guids'])} players):")
    for guid, name in zip(team_b['guids'], team_b['names']):
        context = ""
        if sub_analysis:
            activity = sub_analysis['player_activity'].get(guid)
            if activity:
                if activity.is_late_joiner:
                    context = f" [joined R{activity.first_round}]"
                elif activity.first_round == 1:
                    context = " [full session]"
        
        print(f"   - {name}{context}")
    print()
    
    # Step 4: Show improvement from substitution awareness
    print("💡 Step 4: Substitution-Based Improvements...")
    print("-" * 80)
    
    if sub_analysis and sub_analysis['substitutions']:
        print("✅ Substitution detection helps by:")
        print("   1. Assigning substitutes to same team as the player they replaced")
        print("   2. Reducing uncertainty for late joiners")
        print("   3. Improving confidence scores")
        print()
        print(f"   Without substitution awareness: Some late joiners might be misassigned")
        print(f"   With substitution awareness: Late joiners inherit team from predecessor")
    elif sub_analysis and (sub_analysis['late_joiners'] or sub_analysis['early_leavers']):
        print("ℹ️  Roster changes detected but no clear substitutions")
        print("   Late joiners still assigned using co-occurrence analysis")
    else:
        print("✅ Stable roster - no substitutions needed")
        print("   All players present from round 1, standard detection works perfectly")
    
    print()
    print("=" * 80)
    
    db.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        demo_with_substitutions(sys.argv[1])
    else:
        print("Usage: python demo_substitution_aware_detection.py <round_date>")
        print("Example: python demo_substitution_aware_detection.py 2025-11-01")
