#!/usr/bin/env python3
"""
Complete field mapping using ACTUAL parser logic.
Only analyzes Oct 28 and Oct 30 data.
"""

import sqlite3
import re

def parse_with_actual_logic(filepath):
    """Parse using the EXACT logic from community_stats_parser.py"""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # Header parsing (lines 550-558 in parser)
    header = lines[0].strip()
    header_parts = header.split('\\')
    
    map_name = header_parts[1]
    round_num = int(header_parts[3]) if header_parts[3].isdigit() else 1
    defender_team = int(header_parts[4]) if len(header_parts) > 4 and header_parts[4].isdigit() else 1
    winner_team = int(header_parts[5]) if len(header_parts) > 5 and header_parts[5].isdigit() else 0
    map_time = header_parts[6]
    actual_time = header_parts[7] if len(header_parts) > 7 else "Unknown"
    
    # Player parsing (lines 640-660 in parser)
    player_line = lines[1].strip()
    parts = player_line.split('\\')
    
    guid = parts[0]
    raw_name = parts[1]
    rounds = int(parts[2]) if parts[2].isdigit() else 0
    team = int(parts[3]) if parts[3].isdigit() else 0
    stats_section = parts[4]
    
    # Split weapon stats (space) from extended stats (TAB) - line 650
    if '\t' in stats_section:
        weapon_section, extended_section = stats_section.split('\t', 1)
        stats_parts = weapon_section.split()
        tab_fields = extended_section.split('\t')
    else:
        stats_parts = stats_section.split()
        tab_fields = []
    
    # Extended stats parsing (lines 728-778 in parser)
    damage_given = int(tab_fields[0]) if len(tab_fields) > 0 else 0
    damage_received = int(tab_fields[1]) if len(tab_fields) > 1 else 0
    team_damage_given = int(tab_fields[2]) if len(tab_fields) > 2 else 0
    team_damage_received = int(tab_fields[3]) if len(tab_fields) > 3 else 0
    gibs = int(tab_fields[4]) if len(tab_fields) > 4 else 0
    self_kills = int(tab_fields[5]) if len(tab_fields) > 5 else 0
    team_kills = int(tab_fields[6]) if len(tab_fields) > 6 else 0
    team_gibs = int(tab_fields[7]) if len(tab_fields) > 7 else 0
    
    return {
        'header': {
            'map_name': map_name,
            'round_num': round_num,
            'defender_team': defender_team,
            'winner_team': winner_team,
            'map_time': map_time,
            'actual_time': actual_time,
        },
        'player': {
            'guid': guid,
            'raw_name': raw_name,
            'team_start': rounds,
            'team_end': team,
            'damage_given': damage_given,
            'damage_received': damage_received,
            'team_damage_given': team_damage_given,
            'team_damage_received': team_damage_received,
            'gibs': gibs,
            'self_kills': self_kills,
            'team_kills': team_kills,
            'team_gibs': team_gibs,
        },
        'tab_fields': tab_fields,
        'weapon_stats_count': len(stats_parts),
    }

def get_db_data(round_date, map_name, round_num):
    """Get database data."""
    conn = sqlite3.connect('bot/etlegacy_production.db')
    c = conn.cursor()
    
    # Get round
    c.execute("""
        SELECT id, map_name, round_number, winner_team,
               time_limit, actual_time,
               original_time_limit, time_to_beat, completion_time,
               map_id
        FROM rounds
        WHERE round_date = ? AND map_name = ? AND round_number = ?
    """, (round_date, map_name, round_num))
    
    session = c.fetchone()
    if not session:
        return None
    
    round_id = session[0]
    
    # Get first player
    c.execute("""
        SELECT player_guid, player_name, team,
               kills, deaths, damage_given, damage_received,
               efficiency
        FROM player_comprehensive_stats
        WHERE round_id = ?
        LIMIT 1
    """, (round_id,))
    
    player = c.fetchone()
    conn.close()
    
    return {
        'session': session,
        'player': player
    }

def compare_all():
    """Compare Oct 28 and Oct 30 files."""
    
    files = [
        ('2025-10-28-212120', 'local_stats/2025-10-28-212120-etl_adlernest-round-1.txt'),
        ('2025-10-28-212654', 'local_stats/2025-10-28-212654-etl_adlernest-round-2.txt'),
        ('2025-10-30-212526', 'local_stats/2025-10-30-212526-supply-round-1.txt'),
        ('2025-10-30-213454', 'local_stats/2025-10-30-213454-supply-round-2.txt'),
    ]
    
    for round_date, filepath in files:
        print("\n" + "="*100)
        print(f"FILE: {filepath}")
        print("="*100)
        
        try:
            file_data = parse_with_actual_logic(filepath)
        except FileNotFoundError:
            print("⚠️  File not found, skipping")
            continue
        except Exception as e:
            print(f"❌ Parse error: {e}")
            continue
        
        db_data = get_db_data(
            round_date,
            file_data['header']['map_name'],
            file_data['header']['round_num']
        )
        
        if not db_data:
            print("❌ Database round not found!")
            continue
        
        # Compare header fields
        print("\n📄 HEADER COMPARISON:")
        print("  File → DB")
        print(f"  map_name:        {file_data['header']['map_name']:<20} → {db_data['session'][1]}")
        print(f"  round_number:    {file_data['header']['round_num']:<20} → {db_data['session'][2]}")
        print(f"  winner_team:     {file_data['header']['winner_team']:<20} → {db_data['session'][3]}")
        print(f"  map_time:        {file_data['header']['map_time']:<20} → time_limit={db_data['session'][4]}")
        print(f"  actual_time:     {file_data['header']['actual_time']:<20} → actual_time={db_data['session'][5]}")
        
        print("\n⏱️  TIME FIELD BREAKDOWN:")
        if file_data['header']['round_num'] == 1:
            print(f"  R1 Field 6:      {file_data['header']['map_time']:<20} → original_time_limit={db_data['session'][6]}")
            print(f"  R1 Field 7:      {file_data['header']['actual_time']:<20} → completion_time={db_data['session'][8]}")
            print(f"  time_to_beat:    N/A                  → {db_data['session'][7]}")
        else:
            print(f"  R2 Field 6:      {file_data['header']['map_time']:<20} → time_to_beat={db_data['session'][7]}")
            print(f"  R2 Field 7:      {file_data['header']['actual_time']:<20} → completion_time={db_data['session'][8]}")
            print(f"  original_limit:  N/A                  → {db_data['session'][6]}")
        
        # Compare player fields
        if db_data['player']:
            print("\n👤 PLAYER COMPARISON (first player):")
            print("  File → DB")
            print(f"  guid:            {file_data['player']['guid']:<20} → {db_data['player'][0]}")
            print(f"  name:            {file_data['player']['raw_name'][:20]:<20} → {db_data['player'][1]}")
            print(f"  team:            {file_data['player']['team_end']:<20} → {db_data['player'][2]}")
            
            print("\n📊 STATS COMPARISON:")
            print("  File → DB")
            print(f"  damage_given:    {file_data['player']['damage_given']:<20} → {db_data['player'][5]}")
            print(f"  damage_received: {file_data['player']['damage_received']:<20} → {db_data['player'][6]}")
            
            # Validation
            stats_match = (
                file_data['player']['damage_given'] == db_data['player'][5] and
                file_data['player']['damage_received'] == db_data['player'][6]
            )
            
            if stats_match:
                print("\n  ✅ Stats match perfectly!")
            else:
                print("\n  ❌ Stats MISMATCH!")
        
        print(f"\n🔢 TAB FIELDS FOUND: {len(file_data['tab_fields'])}")
        if len(file_data['tab_fields']) >= 10:
            print(f"  [0] damage_given:     {file_data['tab_fields'][0]}")
            print(f"  [1] damage_received:  {file_data['tab_fields'][1]}")
            print(f"  [2] team_damage_giv:  {file_data['tab_fields'][2]}")
            print(f"  [3] team_damage_rec:  {file_data['tab_fields'][3]}")
            print(f"  [4] gibs:             {file_data['tab_fields'][4]}")
            print(f"  [5] self_kills:       {file_data['tab_fields'][5]}")
            print(f"  [6] team_kills:       {file_data['tab_fields'][6]}")
            print(f"  [7] team_gibs:        {file_data['tab_fields'][7]}")
            print(f"  [8] time_played_pct:  {file_data['tab_fields'][8]}")
            print(f"  [9] xp:               {file_data['tab_fields'][9]}")

if __name__ == '__main__':
    compare_all()
