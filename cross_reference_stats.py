#!/usr/bin/env python3
"""
Cross-reference raw stat files against database.
Check for missing data points in both directions.
"""

import sqlite3
import re

def parse_stat_file(filepath):
    """Parse a stat file and extract all data."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    lines = content.strip().split('\n')
    if len(lines) < 2:
        return None
    
    # Parse header
    header = lines[0]
    parts = header.split('\\')
    
    header_data = {
        'map_name': parts[1] if len(parts) > 1 else None,
        'mode': parts[2] if len(parts) > 2 else None,
        'round_number': int(parts[3]) if len(parts) > 3 else None,
        'team1': int(parts[4]) if len(parts) > 4 else None,
        'team2': int(parts[5]) if len(parts) > 5 else None,
        'time_field_6': parts[6] if len(parts) > 6 else None,
        'time_field_7': parts[7] if len(parts) > 7 else None,
    }
    
    # Parse player lines
    players = []
    for line in lines[1:]:
        if not line.strip():
            continue
        
        # Split by backslash
        player_parts = line.split('\\')
        if len(player_parts) < 4:
            continue
        
        guid = player_parts[0]
        name = player_parts[1]
        team = player_parts[2] if len(player_parts) > 2 else None
        team_at_end = player_parts[3] if len(player_parts) > 3 else None
        
        # Get stats after last backslash
        stats_line = player_parts[-1] if player_parts else ""
        stats = stats_line.split()
        
        player_data = {
            'guid': guid,
            'name': name,
            'team_start': team,
            'team_end': team_at_end,
            'stats_count': len(stats),
            'stats': stats
        }
        players.append(player_data)
    
    return {
        'header': header_data,
        'players': players,
        'total_players': len(players)
    }

def get_db_session(session_date, map_name, round_num):
    """Get session data from database."""
    conn = sqlite3.connect('bot/etlegacy_production.db')
    c = conn.cursor()
    
    c.execute("""
        SELECT 
            id, session_date, map_name, round_number,
            winner_team, time_limit, actual_time,
            original_time_limit, time_to_beat, completion_time,
            map_id
        FROM sessions
        WHERE session_date = ? AND map_name = ? AND round_number = ?
    """, (session_date, map_name, round_num))
    
    session = c.fetchone()
    if not session:
        return None
    
    session_id = session[0]
    
    # Get player stats
    c.execute("""
        SELECT 
            player_guid, player_name, team, 
            kills, deaths, damage_given, damage_received,
            efficiency
        FROM player_comprehensive_stats
        WHERE session_id = ?
    """, (session_id,))
    
    players = c.fetchall()
    conn.close()
    
    return {
        'session': session,
        'players': players,
        'total_players': len(players)
    }

def cross_reference():
    """Cross-reference the two adlernest files against database."""
    
    files = [
        ('2025-10-28-212120', 'local_stats/2025-10-28-212120-etl_adlernest-round-1.txt'),
        ('2025-10-28-212654', 'local_stats/2025-10-28-212654-etl_adlernest-round-2.txt')
    ]
    
    print("\n" + "="*80)
    print("CROSS-REFERENCE: RAW STAT FILES vs DATABASE")
    print("="*80 + "\n")
    
    for session_date, filepath in files:
        print(f"\n{'='*80}")
        print(f"File: {filepath}")
        print(f"{'='*80}\n")
        
        # Parse stat file
        stat_data = parse_stat_file(filepath)
        if not stat_data:
            print("❌ Failed to parse stat file")
            continue
        
        header = stat_data['header']
        print(f"📄 RAW FILE HEADER:")
        print(f"   Map: {header['map_name']}")
        print(f"   Round: {header['round_number']}")
        print(f"   Teams: {header['team1']} vs {header['team2']}")
        print(f"   Time Field 6: {header['time_field_6']}")
        print(f"   Time Field 7: {header['time_field_7']}")
        print(f"   Total Players: {stat_data['total_players']}")
        
        # Get database data
        db_data = get_db_session(session_date, header['map_name'], header['round_number'])
        
        if not db_data:
            print(f"\n❌ DATABASE: Session NOT FOUND!")
            print(f"   Looking for: {session_date}, {header['map_name']}, R{header['round_number']}")
            continue
        
        session = db_data['session']
        print(f"\n💾 DATABASE SESSION:")
        print(f"   ID: {session[0]}")
        print(f"   Session Date: {session[1]}")
        print(f"   Map: {session[2]}, Round: {session[3]}")
        print(f"   Winner Team: {session[4]}")
        print(f"   time_limit: {session[5]}")
        print(f"   actual_time: {session[6]}")
        print(f"   original_time_limit: {session[7]}")
        print(f"   time_to_beat: {session[8]}")
        print(f"   completion_time: {session[9]}")
        print(f"   map_id: {session[10]}")
        print(f"   Total Players: {db_data['total_players']}")
        
        # Compare time values
        print(f"\n⏱️  TIME VALUES COMPARISON:")
        print(f"   File field 6: {header['time_field_6']}")
        print(f"   File field 7: {header['time_field_7']}")
        print(f"   ---")
        print(f"   DB original_time_limit: {session[7]}")
        print(f"   DB time_to_beat: {session[8]}")
        print(f"   DB completion_time: {session[9]}")
        print(f"   DB time_limit (old): {session[5]}")
        print(f"   DB actual_time (old): {session[6]}")
        
        # Check if times match
        if header['round_number'] == 1:
            orig_match = header['time_field_6'] == session[7]
            comp_match = header['time_field_7'] == session[9]
            print(f"\n   R1 Validation:")
            print(f"   ✅ Original matches" if orig_match else f"   ❌ Original mismatch: {header['time_field_6']} != {session[7]}")
            print(f"   ✅ Completion matches" if comp_match else f"   ❌ Completion mismatch: {header['time_field_7']} != {session[9]}")
        else:
            beat_match = header['time_field_6'] == session[8]
            comp_match = header['time_field_7'] == session[9]
            print(f"\n   R2 Validation:")
            print(f"   ✅ Time-to-beat matches" if beat_match else f"   ❌ Time-to-beat mismatch: {header['time_field_6']} != {session[8]}")
            print(f"   ✅ Completion matches" if comp_match else f"   ❌ Completion mismatch: {header['time_field_7']} != {session[9]}")
        
        # Compare player counts
        print(f"\n👥 PLAYER COUNT:")
        print(f"   File: {stat_data['total_players']} players")
        print(f"   Database: {db_data['total_players']} players")
        if stat_data['total_players'] != db_data['total_players']:
            print(f"   ⚠️  MISMATCH: {abs(stat_data['total_players'] - db_data['total_players'])} player difference")
        else:
            print(f"   ✅ Match!")
        
        # Compare player GUIDs
        file_guids = set(p['guid'] for p in stat_data['players'])
        db_guids = set(p[0] for p in db_data['players'])
        
        missing_in_db = file_guids - db_guids
        missing_in_file = db_guids - file_guids
        
        print(f"\n🔍 PLAYER GUID COMPARISON:")
        if missing_in_db:
            print(f"   ❌ In file but NOT in database ({len(missing_in_db)}):")
            for guid in missing_in_db:
                player = next(p for p in stat_data['players'] if p['guid'] == guid)
                print(f"      {guid}: {player['name']}")
        
        if missing_in_file:
            print(f"   ❌ In database but NOT in file ({len(missing_in_file)}):")
            for guid in missing_in_file:
                player = next(p for p in db_data['players'] if p[0] == guid)
                print(f"      {guid}: {player[1]}")
        
        if not missing_in_db and not missing_in_file:
            print(f"   ✅ All players match!")
        
        # Sample player stat comparison
        if stat_data['players'] and db_data['players']:
            print(f"\n📊 SAMPLE PLAYER STATS (first player):")
            file_player = stat_data['players'][0]
            db_player = next((p for p in db_data['players'] if p[0] == file_player['guid']), None)
            
            print(f"   File: {file_player['guid']} - {file_player['name']}")
            print(f"      Team start: {file_player['team_start']}, end: {file_player['team_end']}")
            print(f"      Stats count: {file_player['stats_count']}")
            print(f"      First 10 stats: {' '.join(file_player['stats'][:10])}")
            
            if db_player:
                print(f"\n   Database: {db_player[0]} - {db_player[1]}")
                print(f"      Team: {db_player[2]}")
                print(f"      Kills: {db_player[3]}, Deaths: {db_player[4]}")
                print(f"      Damage Given: {db_player[5]}, Received: {db_player[6]}")
                print(f"      Efficiency: {db_player[7]}")
            else:
                print(f"\n   ❌ Player NOT FOUND in database!")

if __name__ == '__main__':
    cross_reference()
