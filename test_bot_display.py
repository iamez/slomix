#!/usr/bin/env python3
"""
Simulate bot display of Stopwatch scores
"""

from tools.stopwatch_scoring import StopwatchScoring

print("\n" + "="*60)
print("🤖 BOT DISPLAY SIMULATION")
print("="*60)

# Test with October 2nd data
session_date = '2025-10-02'
scorer = StopwatchScoring('etlegacy_production.db')
scoring_result = scorer.calculate_session_scores(session_date)

if not scoring_result:
    print("\n❌ No scoring data found")
    exit(1)

# Extract team names (same logic as bot)
team_names = [k for k in scoring_result.keys()
              if k not in ['maps', 'total_maps']]

if len(team_names) < 2:
    print("\n❌ Not enough teams found")
    exit(1)

team_1_name = team_names[0]
team_2_name = team_names[1]
team_1_score = scoring_result[team_1_name]
team_2_score = scoring_result[team_2_name]

print(f"\n📋 Discord Embed Preview:")
print("-" * 60)
print(f"Title: Last Session Stats")
print(f"Description:")
print(f"  Session Date: {session_date}")
print(f"  🏆 Team Score: {team_1_name} {team_1_score} - {team_2_score} {team_2_name}")
print(f"  Total Maps: {scoring_result['total_maps']}")
print()
print(f"Map Results:")
for map_result in scoring_result['maps']:
    map_name = map_result['map']
    t1_pts = map_result['team1_points']
    t2_pts = map_result['team2_points']
    desc = map_result['description']
    
    if t1_pts == t2_pts:
        result = f"{t1_pts}-{t2_pts} (tie)"
    elif t1_pts > t2_pts:
        result = f"{t1_pts}-{t2_pts} {team_1_name}"
    else:
        result = f"{t1_pts}-{t2_pts} {team_2_name}"
    
    print(f"  • {map_name}: {result}")
    print(f"    {desc}")

print("-" * 60)
print("\n✅ Bot display simulation complete!")
print("="*60 + "\n")
