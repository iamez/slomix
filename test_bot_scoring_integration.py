#!/usr/bin/env python3
"""
Test the bot integration with StopwatchScoring

Simulates what the bot does when !last_session is called
"""

import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.stopwatch_scoring import StopwatchScoring

# Test with October 2nd data
session_date = "2025-10-02"
db_path = "github/etlegacy_production.db"  # Using github DB which has Oct 2nd data

print(f"\n🧪 Testing Bot Integration with StopwatchScoring")
print(f"{'='*60}\n")

# Simulate what the bot does
scorer = StopwatchScoring(db_path)
scoring_result = scorer.calculate_session_scores(session_date)

if scoring_result and 'teams' in scoring_result:
    teams_dict = scoring_result['teams']
    team_names = list(teams_dict.keys())
    
    if len(team_names) >= 2:
        team_1_name = team_names[0]
        team_2_name = team_names[1]
        team_1_score = teams_dict[team_1_name]
        team_2_score = teams_dict[team_2_name]
        
        print(f"✅ Successfully calculated scores!")
        print(f"\n🎯 FINAL SCORE:")
        print(f"   {team_1_name}: {team_1_score} points")
        print(f"   {team_2_name}: {team_2_score} points")
        
        # Determine winner
        if team_1_score > team_2_score:
            print(f"\n🏆 WINNER: {team_1_name}")
        elif team_2_score > team_1_score:
            print(f"\n🏆 WINNER: {team_2_name}")
        else:
            print(f"\n🤝 TIE!")
        
        # Show what the bot will display
        print(f"\n📱 Bot Embed Preview:")
        print(f"{'─'*60}")
        print(f"📊 Session Summary: {session_date}")
        print(f"")
        print(f"**10 maps** • **20 rounds** • **6 players**")
        print(f"")
        winner_icon = "🏆" if team_1_score > team_2_score else ("🏆" if team_2_score > team_1_score else "🤝")
        print(f"**🎯 FINAL SCORE:** {winner_icon}")
        print(f"**{team_1_name}:** {team_1_score} points")
        print(f"**{team_2_name}:** {team_2_score} points")
        if team_1_score == team_2_score:
            print(f" *(TIE)*")
        print(f"{'─'*60}")
        
        # Show map breakdown
        if 'maps' in scoring_result:
            print(f"\n🗺️  Map-by-Map Results:")
            for map_data in scoring_result['maps']:
                print(f"   {map_data['map']}: {team_1_name} {map_data[team_1_name]} - {map_data[team_2_name]} {team_2_name}")
        
        print(f"\n✅ Bot integration test PASSED!")
    else:
        print(f"❌ ERROR: Not enough teams found")
else:
    print(f"❌ ERROR: No scoring result returned")

print(f"\n{'='*60}\n")
