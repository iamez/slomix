#!/usr/bin/env python3
"""
Analyze October 2nd Round 2 defender teams

The screenshot shows ALL Round 2 have defender=0, which is WRONG!
In Stopwatch, teams SWAP sides, so:
- Round 1: Team A attacks (defender=1), Team B defends
- Round 2: Team B attacks (defender=2), Team A defends

Let's check what it SHOULD be vs what we have
"""

import sqlite3

conn = sqlite3.connect('github/etlegacy_production.db')
cursor = conn.cursor()

print("\n" + "="*70)
print("🔍 ANALYZING OCTOBER 2nd DEFENDER BUG")
print("="*70)

cursor.execute('''
    SELECT map_name, round_number, defender_team, winner_team, 
           time_limit, actual_time
    FROM sessions
    WHERE session_date LIKE "2025-10-02%"
    ORDER BY id
''')

rows = cursor.fetchall()

print("\nCurrent data (BUGGY):")
print(f"{'Map':<20} | Rnd | Def | Win | Limit | Actual")
print("-" * 70)

for row in rows:
    map_name, rnd, defender, winner, limit, actual = row
    print(f"{map_name:<20} | {rnd:>3} | {defender:>3} | {winner:>3} | {limit:>5} | {actual:>6}")

print("\n" + "="*70)
print("🐛 THE BUG:")
print("="*70)
print("❌ All Round 2 have defender_team = 0 (IMPOSSIBLE!)")
print("✅ Round 1 has defender_team = 1 (correct)")
print("\n💡 FIX: In Stopwatch mode:")
print("   Round 1: defender_team = 1 (Axis defends)")
print("   Round 2: defender_team = 2 (Allies defends, teams SWAPPED)")

print("\n" + "="*70)
print("🔧 EXPECTED vs ACTUAL:")
print("="*70)

# Process pairs
i = 0
while i < len(rows) - 1:
    r1 = rows[i]
    r2 = rows[i + 1]
    
    if r1[0] == r2[0]:  # Same map
        print(f"\n{r1[0]}:")
        print(f"  Round 1: defender={r1[2]} (EXPECTED: 1) {'✅' if r1[2] == 1 else '❌'}")
        print(f"  Round 2: defender={r2[2]} (EXPECTED: 2) {'✅' if r2[2] == 2 else '❌'}")
        
        # Check if times are equal (tie)
        if r1[5] == r2[5]:
            print(f"  Result: TIE ({r1[5]} = {r2[5]}) → R1 attackers get 1pt, R2 defenders get 1pt = 1-1")
        elif r2[5] < r1[5]:
            print(f"  Result: R2 BEAT TIME ({r2[5]} < {r1[5]}) → R2 attackers get 2pts")
        else:
            print(f"  Result: R2 SLOWER ({r2[5]} >= {r1[5]}) → Should not happen if winner=0")
        
        i += 2
    else:
        i += 1

conn.close()

print("\n" + "="*70)
print("📊 CONCLUSION:")
print("="*70)
print("The parser is setting defender_team = header_parts[4] correctly,")
print("but the stats files have defender_team = 0 for Round 2!")
print("\nThis means the game server c0rnp0rn3.lua mod is NOT setting")
print("the defender field correctly in Round 2 headers.")
print("\n💡 SOLUTION: We need to INFER Round 2 defender:")
print("   If round_number == 2: defender_team = 3 - round1_defender")
print("   (i.e., if R1 defender was 1, R2 defender is 2)")
print("="*70 + "\n")
