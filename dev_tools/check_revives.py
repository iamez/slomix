"""Quick check of revives in raw files vs database"""
import sys
import sqlite3
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'bot'))

from community_stats_parser import C0RNP0RN3StatsParser

# Check first round
filepath = Path('local_stats/2025-11-02-211530-etl_adlernest-round-1.txt')
round_id = 2134

print(f"Checking: {filepath.name}")
print(f"Round ID: {round_id}\n")

# Parse raw file
parser = C0RNP0RN3StatsParser()
result = parser.parse_stats_file(str(filepath))

# Get database stats
db_path = Path('bot/etlegacy_production.db')
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("""
    SELECT player_guid, player_name, revives_given, times_revived
    FROM player_comprehensive_stats
    WHERE round_id = ?
    ORDER BY player_name
""", (round_id,))

db_stats = {row['player_guid']: dict(row) for row in cursor.fetchall()}
conn.close()

# Compare
print("REVIVES COMPARISON:")
print("="*80)
print(f"{'Player':<20} {'GUID':<10} {'Raw revives_given':<20} {'DB revives_given':<20} {'Match':<10}")
print(f"{'Player':<20} {'GUID':<10} {'Raw times_revived':<20} {'DB times_revived':<20} {'Match':<10}")
print("="*80)

for player in result['players']:
    guid = player['guid'][:8]
    name = player['name']
    raw_revives_given = player['objective_stats'].get('revives_given', 0)
    raw_times_revived = player['objective_stats'].get('times_revived', 0)
    
    if guid in db_stats:
        db_revives_given = db_stats[guid]['revives_given']
        db_times_revived = db_stats[guid]['times_revived']
        
        match_given = "✓" if raw_revives_given == db_revives_given else "✗ MISMATCH"
        match_revived = "✓" if raw_times_revived == db_times_revived else "✗ MISMATCH"
        
        print(f"{name:<20} {guid:<10} {raw_revives_given:<20} {db_revives_given:<20} {match_given:<10}")
        print(f"{'':<20} {'':<10} {raw_times_revived:<20} {db_times_revived:<20} {match_revived:<10}")
        print()
    else:
        print(f"{name:<20} {guid:<10} NOT IN DATABASE")
        print()

print("\n" + "="*80)
print("SUMMARY:")
print(f"Total players in raw file: {len(result['players'])}")
print(f"Total players in database: {len(db_stats)}")
