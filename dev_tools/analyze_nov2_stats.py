import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

print("Analyzing Nov 2 session data:")
print("="*70)

# Check all sessions on Nov 2
cursor.execute("""
    SELECT id, round_date, map_name, round_number
    FROM rounds
    WHERE SUBSTR(round_date, 1, 10) = '2025-11-02'
    ORDER BY round_date
""")

nov2_sessions = cursor.fetchall()
print(f"Total sessions on Nov 2: {len(nov2_sessions)}\n")

for row in nov2_sessions:
    print(f"ID {row[0]}: {row[1]} - {row[2]} R{row[3]}")

print("\n" + "="*70)
print("Checking player 'endekk' stats across sessions:")
print("="*70)

# Check endekk's stats per session
cursor.execute("""
    SELECT s.round_date, s.map_name, s.round_number,
           p.kills, p.deaths, p.damage_given, p.time_played_seconds
    FROM player_comprehensive_stats p
    JOIN rounds s ON p.round_id = s.id
    WHERE p.player_name LIKE '%endekk%'
    AND SUBSTR(s.round_date, 1, 10) = '2025-11-02'
    ORDER BY s.round_date
""")

endekk_stats = cursor.fetchall()
print(f"\nendekk appears in {len(endekk_stats)} sessions on Nov 2:")

total_kills = 0
total_damage = 0
total_time = 0

for row in endekk_stats:
    total_kills += row[3]
    total_damage += row[5]
    total_time += row[6]
    dpm = (row[5] / (row[6] / 60.0)) if row[6] > 0 else 0
    print(f"  {row[0]} - {row[1]} R{row[2]}: {row[3]}K {row[4]}D {row[5]} dmg in {row[6]//60}min ({dpm:.0f} DPM)")

print(f"\nTotal: {total_kills}K, {total_damage} damage, {total_time//60} minutes")
avg_dpm = (total_damage / (total_time / 60.0)) if total_time > 0 else 0
print(f"Average DPM: {avg_dpm:.0f}")

print("\n" + "="*70)
print("Checking different player name variants:")
print("="*70)

cursor.execute("""
    SELECT DISTINCT player_name, COUNT(*) as appearances
    FROM player_comprehensive_stats p
    JOIN rounds s ON p.round_id = s.id
    WHERE SUBSTR(s.round_date, 1, 10) = '2025-11-02'
    GROUP BY player_name
    ORDER BY player_name
""")

print("All player names on Nov 2:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]} appearances")

conn.close()
