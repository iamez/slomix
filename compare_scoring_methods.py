"""
Compare the two scoring methods to see why we get 8-2 vs 5-5.

Method 1: track_team_scoring.py logic (gave 8-2)
Method 2: detailed_round_breakdown.py logic (gave 5-5)
"""

# From detailed_round_breakdown.py output (5-5 tie):
matches_5_5 = [
    (1, "etl_adlernest", "Team A", 2, 0),      # A wins 2-0
    (2, "supply", "Team B", 0, 2),              # B wins 0-2
    (3, "etl_sp_delivery", "Team A", 2, 0),    # A wins 2-0
    (4, "te_escape2 #1", "Team A", 2, 0),      # A wins 2-0
    (5, "te_escape2 #2", "Team B", 0, 2),      # B wins 0-2
    (6, "sw_goldrush_te", "Team B", 0, 2),     # B wins 0-2
    (7, "et_brewdog", "Team A", 2, 0),         # A wins 2-0
    (8, "etl_frostbite", "Team B", 0, 2),      # B wins 0-2
    (9, "braundorf_b4", "Team A", 2, 0),       # A wins 2-0
    (10, "erdenberg_t2", "Team B", 0, 2),      # B wins 0-2
]

print("="*80)
print("DETAILED_ROUND_BREAKDOWN.PY RESULTS (5-5 TIE)")
print("="*80)
print()

team_a_maps = 0
team_b_maps = 0
team_a_points = 0
team_b_points = 0

for match_num, map_name, winner, score_a, score_b in matches_5_5:
    print(f"Match {match_num}: {map_name:<20} → {winner} ({score_a}-{score_b})")
    
    if winner == "Team A":
        team_a_maps += 1
    else:
        team_b_maps += 1
    
    team_a_points += score_a
    team_b_points += score_b

print()
print(f"MAPS WON: Team A {team_a_maps}, Team B {team_b_maps}")
print(f"POINTS: Team A {team_a_points}, Team B {team_b_points}")
print()

print("="*80)
print("QUESTION: Where does 8-2 come from?")
print("="*80)
print()
print("Hypothesis 1: Track_team_scoring.py counted ROUNDS not MAPS")
print()

# In 2-0 victories, the winner wins BOTH rounds
# In 2-1 victories, winner wins 1 round, loser wins 1 round

team_a_rounds = 0
team_b_rounds = 0

for match_num, map_name, winner, score_a, score_b in matches_5_5:
    if score_a == 2 and score_b == 0:
        # Team A won 2-0 (both rounds)
        team_a_rounds += 2
    elif score_a == 0 and score_b == 2:
        # Team B won 2-0 (both rounds)
        team_b_rounds += 2
    elif score_a == 2 and score_b == 1:
        # Team A won 2-1 (1 round each)
        team_a_rounds += 1
        team_b_rounds += 1
    elif score_a == 1 and score_b == 2:
        # Team B won 2-1 (1 round each)
        team_a_rounds += 1
        team_b_rounds += 1

print(f"ROUNDS WON: Team A {team_a_rounds}, Team B {team_b_rounds}")
print()

if team_a_rounds == 8 or team_a_rounds == 2:
    print("❌ Nope, that's 10-10 rounds, not 8-2")
print()

print("="*80)
print("Hypothesis 2: Different team identification")
print("="*80)
print()
print("Maybe track_team_scoring.py got the teams BACKWARDS?")
print("If Team A and Team B labels were swapped:")
print()

# Swap the teams
for match_num, map_name, winner, score_a, score_b in matches_5_5:
    swapped_winner = "Team B" if winner == "Team A" else "Team A"
    print(f"Match {match_num}: {map_name:<20} → {swapped_winner}")

print()
print("Still gives 5-5! Not 8-2.")
print()

print("="*80)
print("Hypothesis 3: track_team_scoring.py counted PARTIAL session")
print("="*80)
print()

for num_maps in range(1, 11):
    partial_a = sum(1 for m in matches_5_5[:num_maps] if m[2] == "Team A")
    partial_b = sum(1 for m in matches_5_5[:num_maps] if m[2] == "Team B")
    
    if partial_a == 8 or partial_b == 8 or partial_a == 2 or partial_b == 2:
        print(f"After {num_maps} maps: Team A {partial_a}, Team B {partial_b}")

print()
print("No combination gives 8-2!")
print()

print("="*80)
print("CONCLUSION")
print("="*80)
print()
print("The 5-5 tie from detailed_round_breakdown.py appears CORRECT.")
print("The 8-2 score from track_team_scoring.py must have a BUG!")
print()
print("Possible bugs in track_team_scoring.py:")
print("  1. Wrongly identified which team is Team A vs Team B")
print("  2. Scoring logic error (wrong calculation)")
print("  3. File parsing error (reading wrong rounds)")
print()
print("We need to DEBUG track_team_scoring.py to find the issue!")
print()
