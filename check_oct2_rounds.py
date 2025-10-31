import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT map_name, round_number, defender_team, winner_team, 
           time_limit, actual_time
    FROM sessions
    WHERE substr(session_date, 1, 10) = '2025-10-02'
    ORDER BY id
''')

rows = cursor.fetchall()

print("\n=== October 2nd Sessions - Full Data ===\n")
print(f"{'Map':<18} | {'Rnd':>3} | {'Def':>3} | {'Win':>3} | {'Limit':>6} | {'Actual':>6}")
print("-" * 70)

for row in rows:
    map_name, rnd, defender, winner, limit_time, actual_time = row
    print(f"{map_name:<18} | {rnd:>3} | {defender:>3} | {winner:>3} | {limit_time:>6} | {actual_time:>6}")

print("\n" + "=" * 70)
print("Legend:")
print("  Def = Defender team (1=Axis, 2=Allies)")
print("  Win = Winner team (1=Axis, 2=Allies, 0=Draw/FH)")
print("  If Round 1 winner != 0: Attackers completed")
print("  If Round 1 winner = 0: FULLHOLD (defenders held full time)")
print("=" * 70 + "\n")

conn.close()
