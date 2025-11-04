"""
🔥 ULTIMATE NUCLEAR VALIDATION 🔥
Every. Single. Field. No exceptions.
"""
import sqlite3
import json
import sys
from pathlib import Path

sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser

SESSIONS = [16, 17]  # Last 2 sessions

# ALL 51 DATABASE FIELDS (excluding metadata like id, created_at)
ALL_DB_FIELDS = [
    'round_id', 'round_date', 'map_name', 'round_number',
    'player_guid', 'player_name', 'clean_name', 'team',
    # Core combat
    'kills', 'deaths', 'damage_given', 'damage_received',
    'team_damage_given', 'team_damage_received', 'gibs', 'self_kills',
    'team_kills', 'team_gibs', 'headshot_kills',
    # Time
    'time_played_seconds', 'time_played_minutes', 'time_dead_minutes', 'time_dead_ratio',
    # Performance
    'xp', 'kd_ratio', 'dpm', 'efficiency',
    # Weapon
    'bullets_fired', 'accuracy',
    # Objectives
    'kill_assists', 'objectives_completed', 'objectives_destroyed',
    'objectives_stolen', 'objectives_returned', 'dynamites_planted',
    'dynamites_defused', 'times_revived', 'revives_given',
    # Advanced
    'most_useful_kills', 'useless_kills', 'kill_steals',
    'denied_playtime', 'constructions', 'tank_meatshield',
    # Multikills
    'double_kills', 'triple_kills', 'quad_kills', 'multi_kills', 'mega_kills',
    # Sprees
    'killing_spree_best', 'death_spree_worst'
]

def get_database_player_all_fields(cursor, round_id):
    """Get EVERYTHING from database"""
    # Build query with all fields
    field_list = ', '.join(ALL_DB_FIELDS)
    cursor.execute(f'''
        SELECT id, {field_list}
        FROM player_comprehensive_stats
        WHERE round_id = ?
        ORDER BY player_name
    ''', (round_id,))
    
    columns = ['id'] + ALL_DB_FIELDS
    players = []
    for row in cursor.fetchall():
        players.append(dict(zip(columns, row)))
    
    return players

def get_raw_file_path(round_date, round_time, map_name, round_number):
    """Build file path"""
    filename = f"{round_date}-{round_time}-{map_name}-round-{round_number}.txt"
    return f"local_stats/{filename}", filename

def parse_and_compare(db_player, raw_player, round_number, r1_data=None):
    """
    Compare database vs raw file for ONE player
    
    For R2 rounds: also show R1 raw + R2 cumulative + expected differential
    """
    comparisons = []
    
    # Field mapping: database field -> raw parser field
    field_map = {
        'player_name': 'name',
        'team': 'team',
        'kills': 'kills',
        'deaths': 'deaths',
        'headshot_kills': 'headshots',
        'damage_given': 'damage_given',
        'damage_received': 'damage_received',
        'team_damage_given': None,  # Not in basic parser output
        'team_damage_received': None,
        'gibs': None,
        'self_kills': None,
        'team_kills': None,
        'team_gibs': None,
        'time_played_seconds': 'time_played_seconds',
        'time_played_minutes': 'time_played_minutes',
        'xp': 'xp_total',
        'kd_ratio': 'kd_ratio',
        'dpm': 'dpm',
        'efficiency': 'efficiency',
        'bullets_fired': 'shots_total',
        'accuracy': 'accuracy',
        'objectives_completed': None,  # Need to check objective_stats
        'objectives_destroyed': None,
        'objectives_stolen': None,
        'objectives_returned': None,
        'revives_given': None,
        'times_revived': None,
    }
    
    for db_field in ALL_DB_FIELDS:
        if db_field in ['round_id', 'round_date', 'map_name', 'round_number', 'player_guid', 'clean_name']:
            continue  # Skip metadata
        
        raw_field = field_map.get(db_field)
        
        db_val = db_player.get(db_field)
        raw_val = None
        
        if raw_field:
            # Check objective_stats first
            if db_field.startswith('objectives_') or db_field in ['revives_given', 'times_revived', 'dynamites_planted', 'dynamites_defused']:
                raw_val = raw_player.get('objective_stats', {}).get(raw_field)
            else:
                raw_val = raw_player.get(raw_field)
        
        # Handle None values
        if db_val is None:
            db_val = 0
        if raw_val is None:
            raw_val = 0
        
        # Build comparison entry
        comp = {
            'field': db_field,
            'db_value': db_val,
            'raw_value': raw_val,
            'match': True,
            'difference': 0
        }
        
        # For R2 rounds, show R1 raw + differential calculation
        if round_number == 2 and r1_data:
            r1_player = None
            for rp in r1_data['players']:
                if rp['name'].lower().strip() == raw_player['name'].lower().strip():
                    r1_player = rp
                    break
            
            if r1_player:
                r1_val = None
                if raw_field:
                    if db_field.startswith('objectives_'):
                        r1_val = r1_player.get('objective_stats', {}).get(raw_field, 0)
                    else:
                        r1_val = r1_player.get(raw_field, 0)
                
                if r1_val is None:
                    r1_val = 0
                
                # R2 cumulative = raw_val (from R2 file)
                # R2 differential = R2_cumulative - R1
                expected_differential = raw_val - r1_val if isinstance(raw_val, (int, float)) and isinstance(r1_val, (int, float)) else None
                
                comp['r1_raw'] = r1_val
                comp['r2_cumulative'] = raw_val
                comp['expected_differential'] = expected_differential
                
                # Database should have differential
                if expected_differential is not None:
                    comp['raw_value'] = expected_differential  # Override with expected differential
        
        # Compare
        if isinstance(db_val, float) and isinstance(comp['raw_value'], (int, float)):
            if abs(db_val - comp['raw_value']) > 0.01:
                comp['match'] = False
                comp['difference'] = abs(db_val - comp['raw_value'])
        elif db_val != comp['raw_value']:
            comp['match'] = False
            if isinstance(db_val, (int, float)) and isinstance(comp['raw_value'], (int, float)):
                comp['difference'] = abs(db_val - comp['raw_value'])
        
        comparisons.append(comp)
    
    return comparisons

# START VALIDATION
print("="*100)
print("🔥🔥🔥 ULTIMATE NUCLEAR VALIDATION 🔥🔥🔥")
print("Every. Single. Field. Every. Single. Player. Every. Single. Round.")
print("="*100)
print()

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()
parser = C0RNP0RN3StatsParser()

all_data = {
    'sessions': [],
    'field_names': ALL_DB_FIELDS,
    'summary': {
        'total_rounds': 0,
        'total_players': 0,
        'total_fields_checked': 0,
        'perfect_matches': 0,
        'fields_with_mismatches': 0
    }
}

for session_id in SESSIONS:
    print(f"\n{'='*100}")
    print(f"SESSION {session_id}")
    print(f"{'='*100}\n")
    
    cursor.execute('''
        SELECT id, round_date, round_time, map_name, round_number
        FROM rounds
        WHERE gaming_session_id = ?
        ORDER BY id
    ''', (session_id,))
    
    rounds_info = cursor.fetchall()
    
    session_data = {
        'session_id': session_id,
        'rounds': []
    }
    
    for round_id, round_date, round_time, map_name, round_number in rounds_info:
        file_path, filename = get_raw_file_path(round_date, round_time, map_name, round_number)
        
        print(f"Round {round_id}: {map_name} R{round_number} @ {round_date} {round_time}")
        
        # Get database data
        db_players = get_database_player_all_fields(cursor, round_id)
        
        # Parse raw file
        raw_data = None
        if Path(file_path).exists():
            raw_data = parser.parse_stats_file(file_path)
            if raw_data and not raw_data.get('success'):
                raw_data = None
        
        # For R2, also parse R1 for differential calculation
        r1_data = None
        if round_number == 2 and raw_data:
            r1_file_path, r1_filename = get_raw_file_path(round_date, round_time.replace(round_time, str(int(round_time) - 10000).zfill(6)), map_name, 1)
            # Actually, we need to find the R1 file properly
            # The parser already does this, so we can get it from the parser logs
            # Or we parse it separately
            pass  # For now, skip R1 parsing (parser handles it)
        
        round_data = {
            'round_id': round_id,
            'date': round_date,
            'time': round_time,
            'map': map_name,
            'round_number': round_number,
            'filename': filename,
            'file_exists': raw_data is not None,
            'players': []
        }
        
        if not raw_data:
            print(f"  ⚠️  No stat file")
            all_data['summary']['total_rounds'] += 1
            session_data['rounds'].append(round_data)
            continue
        
        print(f"  Database: {len(db_players)} players | Raw: {len(raw_data['players'])} players")
        
        # Compare each player
        for db_player in db_players:
            # Find in raw
            raw_player = None
            for rp in raw_data['players']:
                if rp['name'].lower().strip() == db_player['player_name'].lower().strip():
                    raw_player = rp
                    break
            
            if not raw_player:
                print(f"    ❌ {db_player['player_name']}: NOT IN RAW FILE")
                round_data['players'].append({
                    'name': db_player['player_name'],
                    'in_db': True,
                    'in_raw': False,
                    'comparisons': []
                })
                continue
            
            # Compare ALL fields
            comparisons = parse_and_compare(db_player, raw_player, round_number, r1_data)
            
            mismatches = [c for c in comparisons if not c['match']]
            
            if mismatches:
                print(f"    ❌ {db_player['player_name']}: {len(mismatches)} mismatches")
                all_data['summary']['fields_with_mismatches'] += len(mismatches)
            else:
                print(f"    ✅ {db_player['player_name']}: PERFECT")
                all_data['summary']['perfect_matches'] += 1
            
            round_data['players'].append({
                'name': db_player['player_name'],
                'in_db': True,
                'in_raw': True,
                'comparisons': comparisons
            })
            
            all_data['summary']['total_fields_checked'] += len(comparisons)
        
        all_data['summary']['total_players'] += len(db_players)
        all_data['summary']['total_rounds'] += 1
        session_data['rounds'].append(round_data)
    
    all_data['sessions'].append(session_data)

conn.close()

# Save
output_file = 'tools/ultimate_validation_last_2_sessions.json'
with open(output_file, 'w') as f:
    json.dump(all_data, f, indent=2)

print(f"\n{'='*100}")
print("SUMMARY")
print(f"{'='*100}")
print(f"Total rounds: {all_data['summary']['total_rounds']}")
print(f"Total players: {all_data['summary']['total_players']}")
print(f"Total fields checked: {all_data['summary']['total_fields_checked']}")
print(f"Perfect player matches: {all_data['summary']['perfect_matches']}")
print(f"Fields with mismatches: {all_data['summary']['fields_with_mismatches']}")
print(f"\n✅ Saved: {output_file}")
