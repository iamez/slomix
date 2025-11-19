"""
Query latest gaming session rounds
"""
import sqlite3
from datetime import datetime

# Connect to database
conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# List all tables
print("Database Tables:")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
for table in tables:
    print(f"  - {table[0]}")
print()

# Get latest date from stats
cursor.execute('''
    SELECT MAX(round_date) as latest_date
    FROM player_comprehensive_stats
''')
latest_date = cursor.fetchone()[0]

if not latest_date:
    print("No data found in database")
    conn.close()
    exit(1)

print(f"Latest Session Date: {latest_date}")
print("=" * 80)

# Get all rounds from latest date
cursor.execute('''
    SELECT 
        round_number,
        map_name,
        round_date,
        COUNT(DISTINCT player_name) as players
    FROM player_comprehensive_stats 
    WHERE round_date = ? 
    GROUP BY round_number, map_name, round_date
    ORDER BY round_number
''', (latest_date,))

rounds = cursor.fetchall()

print(f"\nRounds from {latest_date}:\n")
for round_num, map_name, date, player_count in rounds:
    print(f"Round {round_num}: {map_name:20} | {date} | {player_count} players")

print(f"\nTotal Rounds: {len(rounds)}")

conn.close()
