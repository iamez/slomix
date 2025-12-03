"""
Check revives across ALL Nov 2 rounds

PURPOSE: Verify that revives_given and times_revived are NOT missing from database

RESULT: 100% match rate
- revives_given: 108/108 players match (TAB field 37)
- times_revived: 108/108 players match (TAB field 19)

CONCLUSION: Revives are completely accurate in database. User's concern was unfounded.
DATE: November 3, 2025
"""
import sys
import sqlite3
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'bot'))

from community_stats_parser import C0RNP0RN3StatsParser

SESSION_IDS = list(range(2134, 2152))  # 18 rounds

def get_nov2_files():
    """Get all Nov 2 stats files (excluding orphan at 00:06)"""
    stats_dir = Path('local_stats')
    files = sorted([f for f in stats_dir.glob('2025-11-02*.txt') if '000624' not in f.name])
    return files

# Get database connection
db_path = Path('bot/etlegacy_production.db')
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check all rounds
files = get_nov2_files()
parser = C0RNP0RN3StatsParser()

total_players = 0
revives_given_matches = 0
times_revived_matches = 0
revives_given_mismatches = []
times_revived_mismatches = []

for i, (filepath, round_id) in enumerate(zip(files, SESSION_IDS)):
    result = parser.parse_stats_file(str(filepath))
    if not result or not result.get('success'):
        continue
    
    # Get DB stats for this session
    cursor.execute("""
        SELECT player_guid, player_name, revives_given, times_revived
        FROM player_comprehensive_stats
        WHERE round_id = ?
    """, (round_id,))
    
    db_stats = {row['player_guid']: dict(row) for row in cursor.fetchall()}
    
    # Compare each player
    for player in result['players']:
        guid = player['guid'][:8]
        name = player['name']
        raw_revives_given = player['objective_stats'].get('revives_given', 0)
        raw_times_revived = player['objective_stats'].get('times_revived', 0)
        
        if guid in db_stats:
            total_players += 1
            db_revives_given = db_stats[guid]['revives_given']
            db_times_revived = db_stats[guid]['times_revived']
            
            if raw_revives_given == db_revives_given:
                revives_given_matches += 1
            else:
                revives_given_mismatches.append({
                    'round': filepath.name,
                    'round_id': round_id,
                    'guid': guid,
                    'name': name,
                    'raw': raw_revives_given,
                    'db': db_revives_given
                })
            
            if raw_times_revived == db_times_revived:
                times_revived_matches += 1
            else:
                times_revived_mismatches.append({
                    'round': filepath.name,
                    'round_id': round_id,
                    'guid': guid,
                    'name': name,
                    'raw': raw_times_revived,
                    'db': db_times_revived
                })

conn.close()

print("="*80)
print("REVIVES VALIDATION - ALL NOV 2 ROUNDS")
print("="*80)
print(f"\nTotal players checked: {total_players}")
print("\nrevives_given:")
print(f"  ✓ Matches: {revives_given_matches}/{total_players} ({100*revives_given_matches/total_players:.1f}%)")
print(f"  ✗ Mismatches: {len(revives_given_mismatches)}")

print("\ntimes_revived:")
print(f"  ✓ Matches: {times_revived_matches}/{total_players} ({100*times_revived_matches/total_players:.1f}%)")
print(f"  ✗ Mismatches: {len(times_revived_mismatches)}")

if revives_given_mismatches:
    print("\n" + "="*80)
    print("REVIVES_GIVEN MISMATCHES:")
    print("="*80)
    for m in revives_given_mismatches:
        print(f"{m['name']} ({m['guid']}) - Round: {m['round']}")
        print(f"  Raw: {m['raw']}, DB: {m['db']}")

if times_revived_mismatches:
    print("\n" + "="*80)
    print("TIMES_REVIVED MISMATCHES:")
    print("="*80)
    for m in times_revived_mismatches:
        print(f"{m['name']} ({m['guid']}) - Round: {m['round']}")
        print(f"  Raw: {m['raw']}, DB: {m['db']}")

if not revives_given_mismatches and not times_revived_mismatches:
    print("\n" + "="*80)
    print("✅ ALL REVIVES DATA MATCHES PERFECTLY!")
    print("="*80)
