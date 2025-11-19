import sqlite3
from pathlib import Path

db_path = Path("bot/etlegacy_production.db")

print("=" * 100)
print("ALL SESSIONS IN DATABASE")
print("=" * 100)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all sessions with full details
cursor.execute("""
    SELECT 
        id,
        round_date,
        map_name,
        round_number,
        time_limit,
        actual_time,
        winner_team,
        defender_team,
        is_tied,
        round_outcome,
        created_at
    FROM rounds
    ORDER BY id
""")

sessions = cursor.fetchall()

print(f"\nTotal Sessions: {len(sessions)}\n")
print(f"{'ID':<5} {'Date':<12} {'Map':<25} {'Rnd':<4} {'TimeLimit':<10} {'ActualTime':<10} {'Winner':<7} {'Defender':<9} {'Tied':<5} {'Outcome':<15} {'Created':<20}")
print("-" * 140)

for session in sessions:
    (id, round_date, map_name, round_number, time_limit, actual_time, 
     winner_team, defender_team, is_tied, round_outcome, created_at) = session
    
    # Format values for display
    winner_str = "None" if winner_team is None else ("Axis" if winner_team == 0 else "Allies")
    defender_str = "None" if defender_team is None else ("Axis" if defender_team == 0 else "Allies")
    tied_str = "Yes" if is_tied else "No"
    time_limit_str = time_limit or "N/A"
    actual_time_str = actual_time or "N/A"
    outcome_str = round_outcome or "N/A"
    created_str = created_at[:19] if created_at else "N/A"
    
    print(f"{id:<5} {round_date:<12} {map_name:<25} R{round_number:<3} {time_limit_str:<10} {actual_time_str:<10} {winner_str:<7} {defender_str:<9} {tied_str:<5} {outcome_str:<15} {created_str:<20}")

print("\n" + "=" * 100)

# Get player counts per session
print("\nPLAYER PARTICIPATION PER SESSION:")
print("-" * 100)
print(f"{'Session ID':<12} {'Map':<25} {'Round':<6} {'Players':<10}")
print("-" * 100)

cursor.execute("""
    SELECT 
        s.id,
        s.map_name,
        s.round_number,
        COUNT(DISTINCT pcs.player_guid) as player_count
    FROM rounds s
    LEFT JOIN player_comprehensive_stats pcs ON s.id = pcs.round_id
    GROUP BY s.id
    ORDER BY s.id
""")

player_counts = cursor.fetchall()
for round_id, map_name, round_num, player_count in player_counts:
    print(f"{round_id:<12} {map_name:<25} R{round_num:<5} {player_count:<10}")

print("\n" + "=" * 100)

# Get weapon stats per session
print("\nWEAPON STATS RECORDS PER SESSION:")
print("-" * 100)
print(f"{'Session ID':<12} {'Map':<25} {'Round':<6} {'Weapon Records':<15}")
print("-" * 100)

cursor.execute("""
    SELECT 
        s.id,
        s.map_name,
        s.round_number,
        COUNT(*) as weapon_records
    FROM rounds s
    LEFT JOIN weapon_comprehensive_stats wcs ON s.id = wcs.round_id
    GROUP BY s.id
    ORDER BY s.id
""")

weapon_counts = cursor.fetchall()
for round_id, map_name, round_num, weapon_count in weapon_counts:
    print(f"{round_id:<12} {map_name:<25} R{round_num:<5} {weapon_count:<15}")

conn.close()
print("\n" + "=" * 100)
