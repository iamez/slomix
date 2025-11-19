import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Check round IDs for Nov 4
cursor.execute('''
    SELECT round_id, map_name, round_number, COUNT(*) as players
    FROM player_comprehensive_stats 
    WHERE round_date = '2025-11-04'
    GROUP BY round_id, map_name, round_number
    ORDER BY round_id
''')

print("Nov 4, 2025 - Round IDs in database:")
print("=" * 60)
for row in cursor.fetchall():
    print(f"Round ID {row[0]:3}: {row[1]:20} Round {row[2]} - {row[3]} players")

# Check if there are te_escape2 round 2 entries at all
cursor.execute('''
    SELECT COUNT(*), string_agg(DISTINCT round_id, ', ')
    FROM player_comprehensive_stats 
    WHERE round_date = '2025-11-04'
    AND map_name = 'te_escape2'
    AND round_number = 2
''')
print(f"\nte_escape2 Round 2 query result: {cursor.fetchone()}")

conn.close()

# Now check what round_id WOULD be generated for missing files
print("\n" + "=" * 60)
print("What round_id would the missing files have?")
print("=" * 60)

missing = [
    ('2025-11-04-225627-etl_frostbite-round-1.txt', 'etl_frostbite', 1),
    ('2025-11-04-224353-te_escape2-round-2.txt', 'te_escape2', 2),
]

for filename, map_name, round_num in missing:
    # Extract timestamp
    parts = filename.split('-')
    date_str = f"{parts[0]}-{parts[1]}-{parts[2]}"
    time_str = parts[3]
    
    # round_id format appears to be timestamp-based
    round_id_guess = f"{date_str}_{time_str}_{map_name}_R{round_num}"
    print(f"{filename}")
    print(f"  Estimated round_id: {round_id_guess}")
