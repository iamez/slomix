#!/usr/bin/env python3
"""
Complete field-by-field mapping of raw stat file to database.
Shows EVERY field from the raw file and where it goes in the database.
"""

import sqlite3

def parse_stat_file_detailed(filepath):
    """Parse stat file and extract every single field."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    lines = content.strip().split('\n')
    if len(lines) < 2:
        return None
    
    # Parse header - show EXACT raw format
    header_line = lines[0]
    parts = header_line.split('\\')
    
    print(f"\n{'='*100}")
    print(f"RAW HEADER LINE:")
    print(f"{'='*100}")
    print(f"{header_line}")
    print(f"\n{'='*100}")
    print(f"HEADER FIELDS (split by \\):")
    print(f"{'='*100}")
    for i, part in enumerate(parts):
        print(f"  [{i}]: {part}")
    
    header_data = {
        'field_0': parts[0] if len(parts) > 0 else None,
        'field_1_map': parts[1] if len(parts) > 1 else None,
        'field_2_mode': parts[2] if len(parts) > 2 else None,
        'field_3_round': parts[3] if len(parts) > 3 else None,
        'field_4_team1': parts[4] if len(parts) > 4 else None,
        'field_5_team2': parts[5] if len(parts) > 5 else None,
        'field_6_time': parts[6] if len(parts) > 6 else None,
        'field_7_time': parts[7] if len(parts) > 7 else None,
    }
    
    # Parse first player line in detail
    if len(lines) > 1:
        player_line = lines[1]
        player_parts = player_line.split('\\')
        
        print(f"\n{'='*100}")
        print(f"RAW PLAYER LINE (first player):")
        print(f"{'='*100}")
        print(f"{player_line}")
        print(f"\n{'='*100}")
        print(f"PLAYER FIELDS (split by \\):")
        print(f"{'='*100}")
        for i, part in enumerate(player_parts):
            if i < 5:  # Show first few fields clearly
                print(f"  [{i}]: {part}")
            elif i == len(player_parts) - 1:  # Last field is stats
                print(f"  [{i}] (STATS): {part[:100]}..." if len(part) > 100 else f"  [{i}] (STATS): {part}")
        
        # Parse stats section
        stats_str = player_parts[-1] if player_parts else ""
        stats = stats_str.split()
        
        print(f"\n{'='*100}")
        print(f"STATS FIELDS (split by space/tab):")
        print(f"{'='*100}")
        print(f"Total stats fields: {len(stats)}")
        
        # Map known stat fields
        stat_mapping = {
            0: "xp_timestamp",
            1: "skill_battlesense_xp",
            2: "skill_engineering_xp", 
            3: "skill_medic_xp",
            4: "skill_fieldops_xp",
            5: "skill_lightweapons_xp",
            6: "skill_heavyweapons_xp",
            7: "skill_covertops_xp",
            8: "skill_battlesense_level",
            9: "skill_engineering_level",
            10: "skill_medic_level",
            11: "skill_fieldops_level",
            12: "skill_lightweapons_level",
            13: "skill_heavyweapons_level",
            14: "skill_covertops_level",
            15: "medals_awarded",
            16: "damage_given",
            17: "damage_received",
            18: "damage_team",
            19: "deaths",
            20: "dyn_planted",
            21: "dyn_defused",
            22: "obj_captured",
            23: "obj_destroyed",
            24: "obj_returned",
            25: "obj_taken",
            26: "kills",
            27: "teamkills",
            28: "gibs",
            29: "selfkills",
            30: "teamgibs",
            31: "headshots",
            32: "revives",
            33: "ammogiven",
            34: "healthgiven",
            35: "poisoned",
            36: "knifekills",
            37: "killpeak",
            38: "efficiency",
            39: "accuracy",
            # Continue with weapon stats...
        }
        
        for i in range(min(45, len(stats))):
            field_name = stat_mapping.get(i, f"unknown_{i}")
            print(f"  [{i:2d}] {field_name:<30} = {stats[i]}")
        
        if len(stats) > 45:
            print(f"  ... and {len(stats) - 45} more weapon/hit stat fields")
        
        return {
            'header': header_data,
            'player_line': player_line,
            'player_parts': player_parts,
            'stats': stats,
            'stats_count': len(stats)
        }
    
    return {'header': header_data}

def get_db_session_detailed(round_date, map_name, round_num):
    """Get complete session data from database."""
    conn = sqlite3.connect('bot/etlegacy_production.db')
    c = conn.cursor()
    
    # Get round with ALL columns
    c.execute("PRAGMA table_info(sessions)")
    session_columns = [row[1] for row in c.fetchall()]
    
    query = f"SELECT {', '.join(session_columns)} FROM rounds WHERE round_date = ? AND map_name = ? AND round_number = ?"
    c.execute(query, (round_date, map_name, round_num))
    
    session = c.fetchone()
    if not session:
        return None
    
    session_dict = dict(zip(session_columns, session))
    round_id = session_dict['id']
    
    # Get player stats with ALL columns
    c.execute("PRAGMA table_info(player_comprehensive_stats)")
    player_columns = [row[1] for row in c.fetchall()]
    
    query = f"SELECT {', '.join(player_columns)} FROM player_comprehensive_stats WHERE round_id = ? LIMIT 1"
    c.execute(query, (round_id,))
    
    player = c.fetchone()
    player_dict = dict(zip(player_columns, player)) if player else None
    
    conn.close()
    
    return {
        'session': session_dict,
        'session_columns': session_columns,
        'player': player_dict,
        'player_columns': player_columns
    }

def map_fields():
    """Show complete field mapping."""
    
    filepath = 'local_stats/2025-10-28-212120-etl_adlernest-round-1.txt'
    round_date = '2025-10-28-212120'
    
    print("\n" + "="*100)
    print("COMPLETE FIELD-BY-FIELD MAPPING: RAW FILE → DATABASE")
    print("="*100)
    
    # Parse file
    file_data = parse_stat_file_detailed(filepath)
    if not file_data:
        print("❌ Failed to parse file")
        return
    
    # Get DB data
    db_data = get_db_session_detailed(
        round_date, 
        file_data['header']['field_1_map'], 
        int(file_data['header']['field_3_round'])
    )
    
    if not db_data:
        print("❌ Database round not found")
        return
    
    # Map header fields to database
    print(f"\n{'='*100}")
    print("HEADER FIELD MAPPING:")
    print(f"{'='*100}\n")
    
    mappings = [
        ("Field [0]", file_data['header']['field_0'], "→", "server_info (not stored)"),
        ("Field [1]", file_data['header']['field_1_map'], "→", f"sessions.map_name = {db_data['session']['map_name']}"),
        ("Field [2]", file_data['header']['field_2_mode'], "→", "game_mode (not stored)"),
        ("Field [3]", file_data['header']['field_3_round'], "→", f"sessions.round_number = {db_data['session']['round_number']}"),
        ("Field [4]", file_data['header']['field_4_team1'], "→", "team1_number (not stored separately)"),
        ("Field [5]", file_data['header']['field_5_team2'], "→", "team2_number (not stored separately)"),
        ("Field [6]", file_data['header']['field_6_time'], "→", 
         f"sessions.original_time_limit = {db_data['session']['original_time_limit']} (R1) OR sessions.time_to_beat (R2)"),
        ("Field [7]", file_data['header']['field_7_time'], "→", 
         f"sessions.completion_time = {db_data['session']['completion_time']}"),
    ]
    
    for label, raw_val, arrow, db_field in mappings:
        print(f"{label:<12} = {str(raw_val):<20} {arrow} {db_field}")
    
    print(f"\n{'='*100}")
    print("OLD vs NEW TIME STORAGE:")
    print(f"{'='*100}")
    print(f"OLD: time_limit = {db_data['session']['time_limit']}, actual_time = {db_data['session']['actual_time']}")
    print(f"NEW: original_time_limit = {db_data['session']['original_time_limit']}, time_to_beat = {db_data['session']['time_to_beat']}, completion_time = {db_data['session']['completion_time']}")
    
    # Map player fields
    if 'player_parts' in file_data and db_data['player']:
        print(f"\n{'='*100}")
        print("PLAYER FIELD MAPPING:")
        print(f"{'='*100}\n")
        
        player_mappings = [
            ("Field [0]", file_data['player_parts'][0], "→", 
             f"player_comprehensive_stats.player_guid = {db_data['player']['player_guid']}"),
            ("Field [1]", file_data['player_parts'][1], "→", 
             f"player_comprehensive_stats.player_name = {db_data['player']['player_name']}"),
            ("Field [2]", file_data['player_parts'][2], "→", 
             "team_start (not stored, but determines final team)"),
            ("Field [3]", file_data['player_parts'][3], "→", 
             f"player_comprehensive_stats.team = {db_data['player']['team']}"),
        ]
        
        for label, raw_val, arrow, db_field in player_mappings:
            raw_display = raw_val[:30] + "..." if len(str(raw_val)) > 30 else str(raw_val)
            print(f"{label:<12} = {raw_display:<35} {arrow} {db_field}")
    
    # Map stats to database
    if 'stats' in file_data and db_data['player']:
        print(f"\n{'='*100}")
        print("STATS FIELD MAPPING (sample - first 30 fields):")
        print(f"{'='*100}\n")
        
        stats = file_data['stats']
        player = db_data['player']
        
        # Show key stat mappings
        key_mappings = [
            (16, "damage_given", player.get('damage_given')),
            (17, "damage_received", player.get('damage_received')),
            (19, "deaths", player.get('deaths')),
            (26, "kills", player.get('kills')),
            (27, "teamkills", player.get('teamkills')),
            (31, "headshots", player.get('headshots')),
            (32, "revives", player.get('revives')),
            (33, "ammogiven", player.get('ammogiven')),
            (34, "healthgiven", player.get('healthgiven')),
            (38, "efficiency", player.get('efficiency')),
        ]
        
        for idx, field_name, db_value in key_mappings:
            if idx < len(stats):
                file_value = stats[idx]
                match = "✅" if str(file_value) == str(db_value) or abs(float(file_value) - float(db_value)) < 0.1 else "❌"
                print(f"Stats[{idx:2d}] {field_name:<20} = {file_value:<15} → DB: {db_value:<15} {match}")
    
    # Show ALL database columns
    print(f"\n{'='*100}")
    print("ALL DATABASE COLUMNS - sessions table:")
    print(f"{'='*100}\n")
    for col in db_data['session_columns']:
        value = db_data['session'][col]
        print(f"  {col:<30} = {value}")
    
    print(f"\n{'='*100}")
    print("ALL DATABASE COLUMNS - player_comprehensive_stats table (first player):")
    print(f"{'='*100}\n")
    if db_data['player']:
        for col in db_data['player_columns']:
            value = db_data['player'][col]
            # Truncate long values
            if isinstance(value, str) and len(value) > 50:
                value = value[:50] + "..."
            print(f"  {col:<30} = {value}")

if __name__ == '__main__':
    map_fields()
