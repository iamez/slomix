"""
Quick demo showing the advanced team detector's internal workings
"""

import sqlite3
from bot.core.advanced_team_detector import AdvancedTeamDetector

# Connect to database
db = sqlite3.connect('bot/etlegacy_production.db')
session_date = '2025-11-01'

print("=" * 80)
print("🔬 ADVANCED TEAM DETECTOR - DETAILED ANALYSIS")
print("=" * 80)
print(f"Session: {session_date}")
print()

# Create detector
detector = AdvancedTeamDetector()

# Get player data
print("📊 Step 1: Loading player data...")
players_data = detector._get_session_player_data(db, session_date)
print(f"   Found {len(players_data)} players")
for guid, data in list(players_data.items())[:5]:
    print(f"   - {data['name']}: {len(data['rounds'])} rounds")
print()

# Historical analysis
print("📚 Step 2: Historical pattern analysis...")
historical = detector._analyze_historical_patterns(db, players_data, session_date)
if historical:
    print(f"   Analyzed {len(historical)} players with historical data")
    for guid, score in list(historical.items())[:3]:
        print(f"   - {score.player_name}:")
        print(f"      Team A score: {score.team_a_score:.2%}")
        print(f"      Team B score: {score.team_b_score:.2%}")
        print(f"      Confidence: {score.confidence:.2%}")
else:
    print("   ⚠️  No historical data available")
print()

# Multi-round consensus
print("🔄 Step 3: Multi-round consensus analysis...")
consensus = detector._analyze_multi_round_consensus(db, session_date, players_data)
if consensus:
    print(f"   Analyzed consensus for {len(consensus)} players")
    for guid, score in list(consensus.items())[:3]:
        print(f"   - {score.player_name}:")
        print(f"      Team A score: {score.team_a_score:.2%}")
        print(f"      Team B score: {score.team_b_score:.2%}")
        print(f"      Confidence: {score.confidence:.2%}")
print()

# Co-occurrence
print("📈 Step 4: Co-occurrence matrix analysis...")
cooccurrence = detector._analyze_cooccurrence(db, session_date, players_data)
if cooccurrence:
    print(f"   Analyzed co-occurrence for {len(cooccurrence)} players")
    for guid, score in list(cooccurrence.items())[:3]:
        print(f"   - {score.player_name}:")
        print(f"      Team A score: {score.team_a_score:.2%}")
        print(f"      Team B score: {score.team_b_score:.2%}")
        print(f"      Confidence: {score.confidence:.2%}")
print()

# Combined
print("⚖️  Step 5: Combining strategies...")
combined = detector._combine_strategies(players_data, historical, consensus, cooccurrence)
print(f"   Combined scores for {len(combined)} players")
print()
print("   Final Scores:")
for guid, score in sorted(combined.items(), key=lambda x: x[1].team_a_score, reverse=True):
    team = "🔴 Team A" if score.likely_team == 'A' else "🔵 Team B"
    print(f"   {team} - {score.player_name}")
    print(f"      A: {score.team_a_score:.2%} | B: {score.team_b_score:.2%} | Confidence: {score.confidence:.2%}")
print()

# Final detection
print("🎯 Step 6: Running full detection...")
result = detector.detect_session_teams(db, session_date)
print()

if result:
    metadata = result['metadata']
    print("✅ DETECTION COMPLETE")
    print(f"   Quality: {metadata['detection_quality'].upper()}")
    print(f"   Average Confidence: {metadata['avg_confidence']:.1%}")
    print(f"   Team A: {len(result['Team A']['guids'])} players")
    print(f"   Team B: {len(result['Team B']['guids'])} players")
    
    if metadata['uncertain_players']:
        print(f"   ⚠️  Uncertain: {', '.join(metadata['uncertain_players'])}")
else:
    print("❌ Detection failed")

print()
print("=" * 80)

db.close()
