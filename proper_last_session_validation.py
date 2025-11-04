"""
Proper validation of last gaming session comparing database vs parser output.
This correctly extracts fields from objective_stats dict!
"""
import sys
import sqlite3
import os
from pathlib import Path

sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser

def get_last_session_rounds():
    """Get all rounds from the last gaming session."""
    conn = sqlite3.connect('bot/etlegacy_production.db')
    cursor = conn.cursor()
    
    # Get last session ID
    cursor.execute('SELECT MAX(gaming_session_id) FROM rounds')
    last_session_id = cursor.fetchone()[0]
    
    if not last_session_id:
        print("❌ No sessions found!")
        return None, []
    
    # Get session info (basic stats from rounds)
    cursor.execute('''
        SELECT gaming_session_id, 
               MIN(round_date) as session_date,
               MIN(round_time) as start_time,
               MAX(round_time) as end_time,
               COUNT(*) as total_rounds
        FROM rounds 
        WHERE gaming_session_id = ?
    ''', (last_session_id,))
    session_info = cursor.fetchone()
    
    # Get all rounds in this session
    cursor.execute('''
        SELECT id, round_date, round_time, map_name, round_number, match_id
        FROM rounds
        WHERE gaming_session_id = ?
        ORDER BY id
    ''', (last_session_id,))
    rounds = cursor.fetchall()
    
    conn.close()
    return session_info, rounds

def get_database_player_stats(round_id):
    """Get all player stats from database for a round."""
    conn = sqlite3.connect('bot/etlegacy_production.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            player_name, team, kills, deaths, damage_given, damage_received,
            headshot_kills, gibs, self_kills, team_kills, team_damage_given,
            team_damage_received, time_played_seconds, time_played_minutes,
            time_dead_minutes, time_dead_ratio, xp, kd_ratio, dpm, efficiency,
            bullets_fired, accuracy, most_useful_kills, useless_kills, kill_steals,
            constructions, denied_playtime, tank_meatshield,
            double_kills, triple_kills, quad_kills, multi_kills, mega_kills,
            killing_spree_best, death_spree_worst,
            objectives_stolen, objectives_returned, 
            dynamites_planted, dynamites_defused, revives_given, times_revived
        FROM player_comprehensive_stats
        WHERE round_id = ?
        ORDER BY player_name
    ''', (round_id,))
    
    players = {}
    for row in cursor.fetchall():
        players[row[0]] = {
            'team': row[1],
            'kills': row[2],
            'deaths': row[3],
            'damage_given': row[4],
            'damage_received': row[5],
            'headshot_kills': row[6],
            'gibs': row[7],
            'self_kills': row[8],
            'team_kills': row[9],
            'team_damage_given': row[10],
            'team_damage_received': row[11],
            'time_played_seconds': row[12],
            'time_played_minutes': row[13],
            'time_dead_minutes': row[14],
            'time_dead_ratio': row[15],
            'xp': row[16],
            'kd_ratio': row[17],
            'dpm': row[18],
            'efficiency': row[19],
            'bullets_fired': row[20],
            'accuracy': row[21],
            'most_useful_kills': row[22],
            'useless_kills': row[23],
            'kill_steals': row[24],
            'constructions': row[25],
            'denied_playtime': row[26],
            'tank_meatshield': row[27],
            'double_kills': row[28],
            'triple_kills': row[29],
            'quad_kills': row[30],
            'multi_kills': row[31],
            'mega_kills': row[32],
            'killing_spree_best': row[33],
            'death_spree_worst': row[34],
            'objectives_stolen': row[35],
            'objectives_returned': row[36],
            'dynamites_planted': row[37],
            'dynamites_defused': row[38],
            'revives_given': row[39],
            'times_revived': row[40]
        }
    
    conn.close()
    return players

def find_raw_file(round_date, round_time, map_name, round_number):
    """Find the raw stats file for this round."""
    time_formatted = round_time.replace(':', '')
    pattern = f"{round_date}-{time_formatted}-{map_name}-round-{round_number}.txt"
    
    search_dirs = ['local_stats', 'bot/local_stats']
    for search_dir in search_dirs:
        if os.path.exists(search_dir):
            filepath = os.path.join(search_dir, pattern)
            if os.path.exists(filepath):
                return filepath
    return None

def extract_parser_field(parser_player, field_name):
    """Extract a field from parser output (handles objective_stats nesting)."""
    # Direct fields
    direct_mapping = {
        'headshot_kills': 'headshots',
        'bullets_fired': 'shots_total',
    }
    
    # Check direct fields first
    if field_name in direct_mapping:
        return parser_player.get(direct_mapping[field_name])
    if field_name in parser_player:
        return parser_player.get(field_name)
    
    # Check objective_stats
    obj_stats = parser_player.get('objective_stats', {})
    if not obj_stats:
        return None
    
    # Map database field names to parser objective_stats fields
    obj_mapping = {
        'team_damage_given': 'team_damage_given',
        'team_damage_received': 'team_damage_received',
        'gibs': 'gibs',
        'self_kills': 'self_kills',
        'team_kills': 'team_kills',
        'xp': 'xp',
        'killing_spree_best': 'killing_spree',
        'death_spree_worst': 'death_spree',
        'kill_steals': 'kill_steals',
        'objectives_stolen': 'objectives_stolen',
        'objectives_returned': 'objectives_returned',
        'dynamites_planted': 'dynamites_planted',
        'dynamites_defused': 'dynamites_defused',
        'times_revived': 'times_revived',
        'revives_given': 'revives_given',
        'most_useful_kills': 'useful_kills',
        'useless_kills': 'useless_kills',
        'constructions': 'repairs_constructions',
        'denied_playtime': 'denied_playtime',
        'tank_meatshield': 'tank_meatshield',
        'double_kills': 'multikill_2x',
        'triple_kills': 'multikill_3x',
        'quad_kills': 'multikill_4x',
        'multi_kills': 'multikill_5x',
        'mega_kills': 'multikill_6x',
    }
    
    if field_name in obj_mapping:
        return obj_stats.get(obj_mapping[field_name])
    
    return None

def compare_stats(db_stats, parser_player, round_number):
    """Compare database stats with parser output."""
    # Core fields to check (ones that parser definitely returns)
    core_fields = [
        'kills', 'deaths', 'damage_given', 'damage_received',
        'headshot_kills', 'time_played_seconds', 'accuracy',
        'team_damage_given', 'team_damage_received', 'gibs',
        'self_kills', 'team_kills', 'xp'
    ]
    
    # Advanced fields that parser returns in objective_stats
    advanced_fields = [
        'most_useful_kills', 'useless_kills', 'kill_steals',
        'denied_playtime', 'tank_meatshield',
        'killing_spree_best', 'death_spree_worst',
        'objectives_stolen', 'objectives_returned',
        'dynamites_planted', 'dynamites_defused',
        'revives_given', 'times_revived', 'constructions',
        'double_kills', 'triple_kills', 'quad_kills',
        'multi_kills', 'mega_kills'
    ]
    
    all_fields = core_fields + advanced_fields
    
    mismatches = []
    matches = []
    
    for field in all_fields:
        db_val = db_stats.get(field)
        parser_val = extract_parser_field(parser_player, field)
        
        if parser_val is None:
            continue  # Parser doesn't return this field
        
        # Handle floating point comparisons
        if isinstance(db_val, float) or isinstance(parser_val, float):
            if abs(db_val - parser_val) < 0.01:
                matches.append(field)
            else:
                mismatches.append({
                    'field': field,
                    'db': db_val,
                    'parser': parser_val,
                    'diff': db_val - parser_val
                })
        else:
            if db_val == parser_val:
                matches.append(field)
            else:
                mismatches.append({
                    'field': field,
                    'db': db_val,
                    'parser': parser_val,
                    'diff': db_val - parser_val
                })
    
    return matches, mismatches

def main():
    print("=" * 100)
    print("PROPER LAST SESSION VALIDATION")
    print("Comparing Database vs Parser Output (with correct objective_stats extraction)")
    print("=" * 100)
    
    # Get last session
    session_info, rounds = get_last_session_rounds()
    
    if not session_info:
        return
    
    session_id, session_date, start_time, end_time, total_rounds = session_info
    
    print(f"\n📊 Session {session_id}")
    print(f"   Date: {session_date}")
    print(f"   Time: {start_time} - {end_time}")
    print(f"   Total Rounds: {total_rounds}")
    print(f"\n{'=' * 100}\n")
    
    parser = C0RNP0RN3StatsParser()
    
    total_players = 0
    perfect_players = 0
    total_mismatches = 0
    
    for round_id, round_date, round_time, map_name, round_number, match_id in rounds:
        print(f"\n🎮 Round {round_id} | {map_name} | R{round_number} | {round_date} {round_time}")
        
        # Find raw file
        raw_file = find_raw_file(round_date, round_time, map_name, round_number)
        
        if not raw_file:
            print(f"   ⚠️  Raw file not found")
            continue
        
        print(f"   📄 {os.path.basename(raw_file)}")
        
        # Parse raw file
        parsed = parser.parse_stats_file(raw_file)
        
        if not parsed or not parsed.get('players'):
            print(f"   ❌ Failed to parse")
            continue
        
        # Get database stats
        db_players = get_database_player_stats(round_id)
        
        # Compare each player
        round_mismatches = 0
        round_perfect = 0
        
        for parser_player in parsed['players']:
            player_name = parser_player['name']
            total_players += 1
            
            if player_name not in db_players:
                print(f"   ❌ {player_name}: NOT IN DATABASE")
                continue
            
            matches, mismatches = compare_stats(db_players[player_name], parser_player, round_number)
            
            if mismatches:
                round_mismatches += len(mismatches)
                total_mismatches += len(mismatches)
                print(f"   ⚠️  {player_name}: {len(matches)} matches, {len(mismatches)} mismatches")
                for mm in mismatches:
                    print(f"       • {mm['field']}: DB={mm['db']} Parser={mm['parser']} (diff={mm['diff']})")
            else:
                round_perfect += 1
                perfect_players += 1
                print(f"   ✅ {player_name}: PERFECT ({len(matches)} fields matched)")
        
        if round_mismatches == 0:
            print(f"   🎉 ALL {round_perfect} PLAYERS PERFECT!")
    
    # Summary
    print(f"\n{'=' * 100}")
    print(f"SUMMARY")
    print(f"{'=' * 100}")
    print(f"Total players checked: {total_players}")
    print(f"Perfect matches: {perfect_players} ({100*perfect_players/total_players if total_players > 0 else 0:.1f}%)")
    print(f"Total mismatches: {total_mismatches}")
    
    if perfect_players == total_players:
        print(f"\n🎉🎉🎉 DATABASE IS PERFECT! 🎉🎉🎉")
    elif total_mismatches < 10:
        print(f"\n✅ Database is {100*(1-total_mismatches/(total_players*30)):.1f}% accurate - excellent!")
    else:
        print(f"\n⚠️  Some issues found - review mismatches above")

if __name__ == '__main__':
    main()
