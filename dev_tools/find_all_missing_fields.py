"""
Comprehensive analysis: Find ALL fields that are 0 in DB but have values in raw files
Accounts for differential calculation (R2 = cumulative - R1)
"""
import sqlite3
from pathlib import Path
from collections import defaultdict

# Field mapping from raw file index to database column
FIELD_MAPPING = {
    0: 'damage_given',
    1: 'damage_received',
    2: 'team_damage_given',
    3: 'team_damage_received',
    4: 'gibs',
    5: 'self_kills',
    6: 'team_kills',
    7: 'team_gibs',
    9: 'xp',
    10: 'killing_spree_best',
    11: 'death_spree_worst',
    12: 'kill_assists',
    13: 'kill_steals',
    14: 'headshot_kills',
    15: 'objectives_stolen',
    16: 'objectives_returned',
    17: 'dynamites_planted',
    18: 'dynamites_defused',
    19: 'times_revived',
    20: 'bullets_fired',
    27: 'most_useful_kills',
    28: 'denied_playtime',
    29: 'double_kills',
    30: 'triple_kills',
    31: 'quad_kills',
    32: 'multi_kills',
    33: 'mega_kills',
    34: 'useless_kills',
    36: 'constructions',
    37: 'revives_given',
}

def parse_raw_file(filepath):
    """Parse raw file and return player stats"""
    players = {}
    
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    for line in lines[1:]:  # Skip header
        line = line.strip()
        if not line:
            continue
            
        parts = line.split('\\')
        if len(parts) < 5:
            continue
        
        guid = parts[0][:8]  # Truncate to 8 chars
        stats_section = parts[4]
        
        if '\t' not in stats_section:
            continue
        
        weapon_section, extended_section = stats_section.split('\t', 1)
        tab_fields = extended_section.split('\t')
        
        # Extract all fields
        player_stats = {'guid': guid}
        for idx, db_field in FIELD_MAPPING.items():
            if idx < len(tab_fields):
                try:
                    player_stats[db_field] = int(tab_fields[idx])
                except (ValueError, IndexError):
                    player_stats[db_field] = 0
            else:
                player_stats[db_field] = 0
        
        players[guid] = player_stats
    
    return players

def get_r1_stats(round_date, map_name):
    """Get R1 stats for differential calculation"""
    file_path = Path('local_stats') / f"{round_date}-{map_name}-round-1.txt"
    if file_path.exists():
        return parse_raw_file(file_path)
    return {}

def analyze_session(round_id, round_date, map_name, round_num):
    """Analyze one round for missing fields"""
    
    # Get database stats
    conn = sqlite3.connect('bot/etlegacy_production.db')
    cursor = conn.cursor()
    
    # Query by round_id (which links to sessions.id)
    query_fields = ', '.join(FIELD_MAPPING.values())
    cursor.execute(f"""
        SELECT 
            player_guid,
            {query_fields}
        FROM player_comprehensive_stats
        WHERE round_id = ?
    """, (round_id,))
    
    db_players = {}
    for row in cursor.fetchall():
        guid = row[0][:8]
        db_players[guid] = {
            field: row[i+1] for i, field in enumerate(FIELD_MAPPING.values())
        }
    
    conn.close()
    
    # Get raw file stats
    filename = f"{round_date}-{map_name}-round-{round_num}.txt"
    file_path = Path('local_stats') / filename
    
    if not file_path.exists():
        return None
    
    raw_players = parse_raw_file(file_path)
    
    # For R2, get R1 stats for differential calculation
    r1_players = {}
    if round_num == 2:
        r1_players = get_r1_stats(round_date, map_name)
    
    # Compare each player
    mismatches = []
    
    for guid in db_players.keys():
        if guid not in raw_players:
            continue
        
        db_stats = db_players[guid]
        raw_stats = raw_players[guid]
        
        for field in FIELD_MAPPING.values():
            db_val = db_stats.get(field, 0)
            raw_val = raw_stats.get(field, 0)
            
            # Apply differential for R2
            if round_num == 2 and guid in r1_players:
                r1_val = r1_players[guid].get(field, 0)
                expected_val = raw_val - r1_val
            else:
                expected_val = raw_val
            
            # Check if there's a mismatch
            if db_val == 0 and expected_val > 0:
                mismatches.append({
                    'session': f"{round_date} {map_name} R{round_num}",
                    'guid': guid,
                    'field': field,
                    'db_value': db_val,
                    'raw_value': raw_val,
                    'expected_value': expected_val,
                })
            elif db_val != expected_val and abs(db_val - expected_val) > 1:
                # Also catch significant mismatches (allowing for rounding)
                mismatches.append({
                    'session': f"{round_date} {map_name} R{round_num}",
                    'guid': guid,
                    'field': field,
                    'db_value': db_val,
                    'raw_value': raw_val,
                    'expected_value': expected_val,
                })
    
    return mismatches

def main():
    """Run full analysis on Oct 28 & 30"""
    
    conn = sqlite3.connect('bot/etlegacy_production.db')
    cursor = conn.cursor()
    
    # Get all sessions for Oct 28 & 30
    cursor.execute("""
        SELECT id, round_date, map_name, round_number
        FROM rounds
        WHERE round_date LIKE '2025-10-28%' OR round_date LIKE '2025-10-30%'
        ORDER BY round_date, map_name, round_number
    """)
    
    sessions = cursor.fetchall()
    conn.close()
    
    print(f"Analyzing {len(sessions)} sessions from Oct 28 & 30...")
    print("=" * 80)
    
    # Track fields with issues
    field_issues = defaultdict(int)
    all_mismatches = []
    
    for round_id, round_date, map_name, round_num in sessions:
        mismatches = analyze_session(round_id, round_date, map_name, round_num)
        
        if mismatches:
            all_mismatches.extend(mismatches)
            for m in mismatches:
                field_issues[m['field']] += 1
    
    print(f"\n{'='*80}")
    print(f"SUMMARY: Found {len(all_mismatches)} field mismatches")
    print(f"{'='*80}\n")
    
    # Sort fields by number of issues
    sorted_fields = sorted(field_issues.items(), key=lambda x: x[1], reverse=True)
    
    print("Fields with issues (sorted by frequency):")
    print(f"{'Field':<30} {'Count':>10}")
    print("-" * 42)
    for field, count in sorted_fields:
        print(f"{field:<30} {count:>10}")
    
    print(f"\n{'='*80}")
    print("DETAILED MISMATCH LIST")
    print(f"{'='*80}\n")
    
    # Group by field for easier review
    mismatches_by_field = defaultdict(list)
    for m in all_mismatches:
        mismatches_by_field[m['field']].append(m)
    
    for field in sorted([f for f, _ in sorted_fields]):
        matches = mismatches_by_field[field]
        print(f"\n{field.upper()} - {len(matches)} mismatches:")
        print("-" * 80)
        
        # Show first 5 examples
        for m in matches[:5]:
            print(f"  {m['session']:<40} GUID:{m['guid']}")
            print(f"    DB={m['db_value']}, Raw={m['raw_value']}, Expected={m['expected_value']}")
        
        if len(matches) > 5:
            print(f"  ... and {len(matches) - 5} more")
    
    print(f"\n{'='*80}")
    print("CONFIRMATION NEEDED:")
    print(f"{'='*80}\n")
    
    # Identify which fields need fixing in code
    print("Based on this analysis, the following fields need code fixes:")
    print("(These are consistently 0 in DB but have values in raw files)\n")
    
    for field, count in sorted_fields:
        if count > 10:  # Fields with many issues likely need code fixes
            print(f"  ✓ {field}")
            # Find example to show the issue
            example = mismatches_by_field[field][0]
            print(f"    Example: {example['session']}")
            print(f"    DB=0, File={example['raw_value']}, Expected={example['expected_value']}")
            print()

if __name__ == '__main__':
    main()
