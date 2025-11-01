"""
Show all possible scoring interpretations for October 2nd.
Based on the detailed_round_breakdown.py output.
"""

print("="*80)
print("🔍 OCTOBER 2ND - ALL POSSIBLE SCORING SYSTEMS")
print("="*80)
print()

# Results from detailed_round_breakdown.py
matches = [
    {"num": 1, "map": "etl_adlernest", "winner": "Team A", "score_a": 2, "score_b": 0},
    {"num": 2, "map": "supply", "winner": "Team B", "score_a": 0, "score_b": 2},
    {"num": 3, "map": "etl_sp_delivery", "winner": "Team A", "score_a": 2, "score_b": 0},
    {"num": 4, "map": "te_escape2 (#1)", "winner": "Team A", "score_a": 2, "score_b": 0},
    {"num": 5, "map": "te_escape2 (#2)", "winner": "Team B", "score_a": 0, "score_b": 2},
    {"num": 6, "map": "sw_goldrush_te", "winner": "Team B", "score_a": 0, "score_b": 2},
    {"num": 7, "map": "et_brewdog", "winner": "Team A", "score_a": 2, "score_b": 0},
    {"num": 8, "map": "etl_frostbite", "winner": "Team B", "score_a": 0, "score_b": 2},
    {"num": 9, "map": "braundorf_b4", "winner": "Team A", "score_a": 2, "score_b": 0},
    {"num": 10, "map": "erdenberg_t2", "winner": "Team B", "score_a": 0, "score_b": 2},
]

print("📋 Match-by-Match Results:")
print()
print(f"{'#':<4} {'Map':<22} {'Winner':<12} {'Team A Pts':<12} {'Team B Pts':<12}")
print("-" * 70)

map_wins_a = 0
map_wins_b = 0
points_a = 0
points_b = 0

for match in matches:
    print(f"{match['num']:<4} {match['map']:<22} {match['winner']:<12} {match['score_a']:<12} {match['score_b']:<12}")
    
    if match['winner'] == 'Team A':
        map_wins_a += 1
    else:
        map_wins_b += 1
    
    points_a += match['score_a']
    points_b += match['score_b']

print("-" * 70)
print()

print("="*80)
print("🏆 SCORING SYSTEM #1: MAP WINS (Winner-Takes-All)")
print("="*80)
print()
print(f"  Team A: {map_wins_a} maps won")
print(f"  Team B: {map_wins_b} maps won")
print()
print(f"  📊 SCORE: {map_wins_a}-{map_wins_b} TIE")
print()

print("="*80)
print("🏆 SCORING SYSTEM #2: POINTS (2 per win, like goals)")
print("="*80)
print()
print(f"  Team A: {points_a} points")
print(f"  Team B: {points_b} points")
print()
print(f"  📊 SCORE: {points_a}-{points_b} TIE")
print()

print("="*80)
print("🏆 SCORING SYSTEM #3: ROUND WINS (Count rounds, not maps)")
print("="*80)
print()

# Count rounds won by each team
# Team A wins maps 1,3,4,7,9 = they won both rounds (2 rounds each) = 10 rounds
# Team B wins maps 2,5,6,8,10 = they won both rounds (2 rounds each) = 10 rounds

round_wins_a = 0
round_wins_b = 0

for match in matches:
    if match['winner'] == 'Team A':
        # Team A won this map, meaning:
        # R1: Team A completed, Team B failed = Team A won R1
        # R2: Team B failed, Team A held = Team A won R2
        round_wins_a += 2
    else:
        # Team B won this map
        round_wins_b += 2

print(f"  Team A: {round_wins_a} rounds won")
print(f"  Team B: {round_wins_b} rounds won")
print()
print(f"  📊 SCORE: {round_wins_a}-{round_wins_b} TIE")
print()

print("="*80)
print("🤔 WAIT... WHERE DOES 8-2 COME FROM?")
print("="*80)
print()
print("None of these scoring systems give 8-2!")
print()
print("Possible explanations:")
print("  1. 8-2 was a DIFFERENT session/date")
print("  2. 8-2 was from PARTIAL data (not all 10 maps)")
print("  3. 8-2 was calculated using a DIFFERENT formula")
print()
print("Let me check if 8-2 could come from first 5 maps only...")
print()

# Check first 5 maps
first_5_map_wins_a = sum(1 for m in matches[:5] if m['winner'] == 'Team A')
first_5_map_wins_b = sum(1 for m in matches[:5] if m['winner'] == 'Team B')

print(f"First 5 maps: Team A {first_5_map_wins_a}, Team B {first_5_map_wins_b}")

# Check different combinations
for i in range(1, 11):
    subset = matches[:i]
    subset_wins_a = sum(1 for m in subset if m['winner'] == 'Team A')
    subset_wins_b = sum(1 for m in subset if m['winner'] == 'Team B')
    
    if subset_wins_a == 8 or subset_wins_b == 8 or subset_wins_a == 2 or subset_wins_b == 2:
        print(f"After {i} maps: Team A {subset_wins_a}, Team B {subset_wins_b}")

print()
print("="*80)
print()
