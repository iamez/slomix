"""
ULTIMATE COMPREHENSIVE VALIDATION
Compare every single field between database and raw files for last 2 sessions
"""
import sqlite3
import json
import sys
from pathlib import Path

sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser

# Session IDs to validate
SESSIONS = [16, 17]  # Nov 2-3

def get_all_fields():
    """Return ALL fields we want to validate"""
    return [
        'kills', 'deaths', 'headshot_kills', 'damage_given', 'damage_received',
        'team_damage_given', 'team_damage_received', 'team_kills', 'team_gibs',
        'self_kills', 'gibs', 'revives_given', 'revives_received',
        'ammo_given', 'health_given', 'bullets_fired', 'bullets_hit',
        'accuracy', 'time_played_seconds', 'xp', 'obj_captured',
        'obj_destroyed', 'obj_returned', 'obj_taken'
    ]

def get_database_round_data(cursor, round_id):
    """Get ALL data for a round from database"""
    cursor.execute('''
        SELECT 
            id, player_name, team, guid,
            kills, deaths, headshot_kills, damage_given, damage_received,
            team_damage_given, team_damage_received, team_kills, team_gibs,
            self_kills, gibs, revives_given, revives_received,
            ammo_given, health_given, bullets_fired, bullets_hit,
            accuracy, time_played_seconds, xp, obj_captured,
            obj_destroyed, obj_returned, obj_taken
        FROM player_comprehensive_stats
        WHERE round_id = ?
        ORDER BY player_name
    ''', (round_id,))
    
    columns = [
        'id', 'player_name', 'team', 'guid',
        'kills', 'deaths', 'headshot_kills', 'damage_given', 'damage_received',
        'team_damage_given', 'team_damage_received', 'team_kills', 'team_gibs',
        'self_kills', 'gibs', 'revives_given', 'revives_received',
        'ammo_given', 'health_given', 'bullets_fired', 'bullets_hit',
        'accuracy', 'time_played_seconds', 'xp', 'obj_captured',
        'obj_destroyed', 'obj_returned', 'obj_taken'
    ]
    
    players = []
    for row in cursor.fetchall():
        player_data = dict(zip(columns, row))
        players.append(player_data)
    
    return players

def parse_raw_file(file_path, parser):
    """Parse raw stat file"""
    if not Path(file_path).exists():
        return None
    
    result = parser.parse_stats_file(file_path)
    if not result.get('success'):
        return None
    
    return result

def build_stat_filename(round_date, round_time, map_name, round_number):
    """Build the stat filename"""
    return f"{round_date}-{round_time}-{map_name}-round-{round_number}.txt"

def compare_player_data(db_player, raw_player, fields):
    """Compare database player vs raw file player"""
    mismatches = []
    
    for field in fields:
        # Map field names (database vs parser)
        parser_field_map = {
            'headshot_kills': 'headshots',
            'bullets_hit': 'hits_total',
            'bullets_fired': 'shots_total',
            'time_played_seconds': 'time_played_seconds',
            'obj_captured': 'obj_captured',
            'obj_destroyed': 'obj_destroyed',
            'obj_returned': 'obj_returned',
            'obj_taken': 'obj_taken',
        }
        
        raw_field = parser_field_map.get(field, field)
        
        db_val = db_player.get(field)
        
        # Get raw value from player or objective_stats
        if raw_field in ['obj_captured', 'obj_destroyed', 'obj_returned', 'obj_taken']:
            raw_val = raw_player.get('objective_stats', {}).get(raw_field, 0)
        else:
            raw_val = raw_player.get(raw_field)
        
        # Handle XP - parser returns xp_total
        if field == 'xp':
            raw_val = raw_player.get('xp_total', 0)
        
        # Handle accuracy (database stores as float, parser as percentage)
        if field == 'accuracy' and raw_val is not None and db_val is not None:
            # Parser returns percentage (e.g., 45.5), database stores decimal
            raw_val = float(raw_val)  # Parser already gives percentage
        
        if raw_val is None:
            raw_val = 0
        if db_val is None:
            db_val = 0
        
        # Compare
        if field == 'accuracy':
            # Allow small float differences
            if abs(float(raw_val) - float(db_val)) > 0.01:
                mismatches.append({
                    'field': field,
                    'db_value': float(db_val),
                    'raw_value': float(raw_val),
                    'difference': abs(float(raw_val) - float(db_val))
                })
        else:
            if raw_val != db_val:
                mismatches.append({
                    'field': field,
                    'db_value': db_val,
                    'raw_value': raw_val,
                    'difference': abs(raw_val - db_val) if isinstance(raw_val, (int, float)) else 'N/A'
                })
    
    return mismatches

# Main validation
print("="*80)
print("ULTIMATE COMPREHENSIVE VALIDATION - Last 2 Sessions")
print("="*80)
print()

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()
parser = C0RNP0RN3StatsParser()

validation_data = {
    'sessions': [],
    'summary': {
        'total_rounds': 0,
        'total_players': 0,
        'perfect_matches': 0,
        'players_with_mismatches': 0,
        'missing_files': 0
    }
}

fields_to_check = get_all_fields()

for session_id in SESSIONS:
    print(f"\n{'='*80}")
    print(f"SESSION {session_id}")
    print(f"{'='*80}\n")
    
    # Get all rounds in session
    cursor.execute('''
        SELECT id, round_date, round_time, map_name, round_number
        FROM rounds
        WHERE gaming_session_id = ?
        ORDER BY id
    ''', (session_id,))
    
    rounds = cursor.fetchall()
    
    session_data = {
        'session_id': session_id,
        'rounds': []
    }
    
    for round_id, round_date, round_time, map_name, round_number in rounds:
        print(f"Round {round_id}: {round_date} {round_time} - {map_name} (R{round_number})")
        
        # Build filename
        filename = build_stat_filename(round_date, round_time, map_name, round_number)
        file_path = f"local_stats/{filename}"
        
        # Get database data
        db_players = get_database_round_data(cursor, round_id)
        
        # Parse raw file
        raw_data = parse_raw_file(file_path, parser)
        
        round_data = {
            'round_id': round_id,
            'date': round_date,
            'time': round_time,
            'map': map_name,
            'round_number': round_number,
            'filename': filename,
            'file_exists': raw_data is not None,
            'db_players': db_players,
            'raw_players': raw_data['players'] if raw_data else [],
            'player_comparisons': []
        }
        
        if not raw_data:
            print(f"  ⚠️  No stat file found: {filename}")
            validation_data['summary']['missing_files'] += 1
        else:
            print("  ✅ Found stat file")
            print(f"  Database: {len(db_players)} players | Raw file: {len(raw_data['players'])} players")
            
            # Compare each database player with raw file
            for db_player in db_players:
                # Find matching raw player
                raw_player = None
                for rp in raw_data['players']:
                    if rp['name'].lower().strip() == db_player['player_name'].lower().strip():
                        raw_player = rp
                        break
                
                if not raw_player:
                    print(f"    ❌ {db_player['player_name']}: NOT IN RAW FILE")
                    round_data['player_comparisons'].append({
                        'player_name': db_player['player_name'],
                        'in_database': True,
                        'in_raw': False,
                        'mismatches': [{'field': 'MISSING', 'db_value': 'EXISTS', 'raw_value': 'NOT FOUND', 'difference': 0}]
                    })
                    validation_data['summary']['players_with_mismatches'] += 1
                else:
                    # Compare all fields
                    mismatches = compare_player_data(db_player, raw_player, fields_to_check)
                    
                    if mismatches:
                        print(f"    ❌ {db_player['player_name']}: {len(mismatches)} mismatches")
                        validation_data['summary']['players_with_mismatches'] += 1
                    else:
                        print(f"    ✅ {db_player['player_name']}: Perfect match")
                        validation_data['summary']['perfect_matches'] += 1
                    
                    round_data['player_comparisons'].append({
                        'player_name': db_player['player_name'],
                        'in_database': True,
                        'in_raw': True,
                        'db_data': db_player,
                        'raw_data': {
                            'kills': raw_player.get('kills'),
                            'deaths': raw_player.get('deaths'),
                            'headshots': raw_player.get('headshots'),
                            'damage_given': raw_player.get('damage_given'),
                            'time_played_seconds': raw_player.get('time_played_seconds'),
                            # Add more as needed
                        },
                        'mismatches': mismatches
                    })
            
            # Check for players in raw but not in database
            for raw_player in raw_data['players']:
                found = False
                for db_player in db_players:
                    if db_player['player_name'].lower().strip() == raw_player['name'].lower().strip():
                        found = True
                        break
                
                if not found:
                    print(f"    ⚠️  {raw_player['name']}: IN RAW FILE BUT NOT IN DATABASE")
                    round_data['player_comparisons'].append({
                        'player_name': raw_player['name'],
                        'in_database': False,
                        'in_raw': True,
                        'mismatches': [{'field': 'MISSING', 'db_value': 'NOT FOUND', 'raw_value': 'EXISTS', 'difference': 0}]
                    })
        
        validation_data['summary']['total_players'] += len(db_players)
        validation_data['summary']['total_rounds'] += 1
        session_data['rounds'].append(round_data)
    
    validation_data['sessions'].append(session_data)

conn.close()

# Save to JSON
output_file = 'tools/last_2_sessions_validation.json'
with open(output_file, 'w') as f:
    json.dump(validation_data, f, indent=2)

print(f"\n{'='*80}")
print("SUMMARY")
print(f"{'='*80}")
print(f"Total rounds: {validation_data['summary']['total_rounds']}")
print(f"Total players: {validation_data['summary']['total_players']}")
print(f"Perfect matches: {validation_data['summary']['perfect_matches']}")
print(f"Players with mismatches: {validation_data['summary']['players_with_mismatches']}")
print(f"Missing files: {validation_data['summary']['missing_files']}")
print(f"\n✅ Data saved to: {output_file}")
