#!/usr/bin/env python3
"""
Complete field-by-field verification of ALL stats.
Shows EVERY field from raw file, differential calculation, and database value.
"""

import sqlite3

def parse_player_extended_stats(line):
    """Parse all extended stats from a player line."""
    parts = line.split('\\')
    if len(parts) < 5:
        return None
    
    guid = parts[0]
    name = parts[1]
    team_start = parts[2]
    team_end = parts[3]
    stats_section = parts[4]
    
    # Split weapon stats from extended stats (TAB-separated)
    if '\t' in stats_section:
        weapon_section, extended_section = stats_section.split('\t', 1)
        weapon_parts = weapon_section.split()
        tab_fields = extended_section.split('\t')
    else:
        weapon_parts = stats_section.split()
        tab_fields = []
    
    # Parse extended stats (following parser logic lines 728-778)
    extended = {}
    if len(tab_fields) >= 38:
        extended = {
            'damage_given': int(tab_fields[0]),
            'damage_received': int(tab_fields[1]),
            'team_damage_given': int(tab_fields[2]),
            'team_damage_received': int(tab_fields[3]),
            'gibs': int(tab_fields[4]),
            'self_kills': int(tab_fields[5]),
            'team_kills': int(tab_fields[6]),
            'team_gibs': int(tab_fields[7]),
            'time_played_percent': float(tab_fields[8]),
            'xp': int(tab_fields[9]),
            'killing_spree': int(tab_fields[10]),
            'death_spree': int(tab_fields[11]),
            'kill_assists': int(tab_fields[12]),
            'kill_steals': int(tab_fields[13]),
            'headshot_kills': int(tab_fields[14]),
            'objectives_stolen': int(tab_fields[15]),
            'objectives_returned': int(tab_fields[16]),
            'dynamites_planted': int(tab_fields[17]),
            'dynamites_defused': int(tab_fields[18]),
            'times_revived': int(tab_fields[19]),
            'bullets_fired': int(tab_fields[20]),
            'dpm': float(tab_fields[21]),
            'time_played_minutes': float(tab_fields[22]),
            'tank_meatshield': float(tab_fields[23]),
            'time_dead_ratio': float(tab_fields[24]),
            'time_dead_minutes': float(tab_fields[25]),
            'kd_ratio': float(tab_fields[26]),
            'useful_kills': int(tab_fields[27]),
            'denied_playtime': int(tab_fields[28]),
            'multikill_2x': int(tab_fields[29]),
            'multikill_3x': int(tab_fields[30]),
            'multikill_4x': int(tab_fields[31]),
            'multikill_5x': int(tab_fields[32]),
            'multikill_6x': int(tab_fields[33]),
            'useless_kills': int(tab_fields[34]),
            'full_selfkills': int(tab_fields[35]),
            'repairs_constructions': int(tab_fields[36]),
            'revives_given': int(tab_fields[37]),
        }
    
    return {
        'guid': guid,
        'name': name,
        'team_start': team_start,
        'team_end': team_end,
        'weapon_mask': int(weapon_parts[0]) if weapon_parts else 0,
        'weapon_fields_count': len(weapon_parts),
        'extended': extended,
        'tab_fields_count': len(tab_fields),
    }

def get_db_player_stats(session_id, guid):
    """Get all player stats from database."""
    conn = sqlite3.connect('bot/etlegacy_production.db')
    c = conn.cursor()
    
    # Get ALL columns from player_comprehensive_stats
    c.execute("PRAGMA table_info(player_comprehensive_stats)")
    columns = [row[1] for row in c.fetchall()]
    
    query = f"SELECT {', '.join(columns)} FROM player_comprehensive_stats WHERE session_id = ? AND player_guid = ?"
    c.execute(query, (session_id, guid))
    
    row = c.fetchone()
    conn.close()
    
    if not row:
        return None
    
    return dict(zip(columns, row))

def verify_complete_mapping():
    """Verify complete field mapping for endekk across R1 and R2."""
    
    print("\n" + "="*100)
    print("COMPLETE FIELD-BY-FIELD VERIFICATION: endekk (Oct 28 adlernest)")
    print("="*100)
    
    # Parse R1
    with open('local_stats/2025-10-28-212120-etl_adlernest-round-1.txt', 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    r1_line = None
    for line in lines:
        if '7B84BE88' in line and 'endekk' in line:
            r1_line = line.strip()
            break
    
    if not r1_line:
        print("❌ endekk not found in R1 file")
        return
    
    r1_data = parse_player_extended_stats(r1_line)
    
    # Parse R2
    with open('local_stats/2025-10-28-212654-etl_adlernest-round-2.txt', 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    r2_line = None
    for line in lines:
        if '7B84BE88' in line and 'endekk' in line:
            r2_line = line.strip()
            break
    
    if not r2_line:
        print("❌ endekk not found in R2 file")
        return
    
    r2_data = parse_player_extended_stats(r2_line)
    
    # Get database stats
    r1_db = get_db_player_stats(3404, '7B84BE88')
    r2_db = get_db_player_stats(3405, '7B84BE88')
    
    if not r1_db or not r2_db:
        print("❌ endekk not found in database")
        return
    
    # Print header
    print(f"\n{'Field Name':<35} {'R1 File':<15} {'R2 File':<15} {'R2-R1 Calc':<15} {'R1 DB':<15} {'R2 DB':<15} {'Status'}")
    print("-"*130)
    
    # Basic fields
    print(f"{'GUID':<35} {r1_data['guid']:<15} {r2_data['guid']:<15} {'N/A':<15} {r1_db['player_guid']:<15} {r2_db['player_guid']:<15} {'✅' if r1_db['player_guid'] == r1_data['guid'] else '❌'}")
    print(f"{'Name':<35} {r1_data['name']:<15} {r2_data['name']:<15} {'N/A':<15} {r1_db['player_name']:<15} {r2_db['player_name']:<15} {'✅' if r2_db['player_name'] == r2_data['name'] else '❌'}")
    print(f"{'Team':<35} {r1_data['team_end']:<15} {r2_data['team_end']:<15} {'N/A':<15} {str(r1_db['team']):<15} {str(r2_db['team']):<15} {'✅' if str(r2_db['team']) == r2_data['team_end'] else '❌'}")
    
    print("\n" + "="*130)
    print("EXTENDED STATS (TAB-SEPARATED FIELDS)")
    print("="*130)
    
    # Compare all extended stats
    for field_name in r1_data['extended'].keys():
        r1_val = r1_data['extended'][field_name]
        r2_val = r2_data['extended'][field_name]
        
        # Calculate differential
        if isinstance(r1_val, (int, float)):
            diff_calc = max(0, r2_val - r1_val)
        else:
            diff_calc = 'N/A'
        
        # Get DB values (handle missing fields)
        r1_db_val = r1_db.get(field_name, 'N/A')
        r2_db_val = r2_db.get(field_name, 'N/A')
        
        # Format values for display
        r1_str = f"{r1_val:.2f}" if isinstance(r1_val, float) else str(r1_val)
        r2_str = f"{r2_val:.2f}" if isinstance(r2_val, float) else str(r2_val)
        diff_str = f"{diff_calc:.2f}" if isinstance(diff_calc, float) and diff_calc != 'N/A' else str(diff_calc)
        r1_db_str = f"{r1_db_val:.2f}" if isinstance(r1_db_val, float) else str(r1_db_val)
        r2_db_str = f"{r2_db_val:.2f}" if isinstance(r2_db_val, float) else str(r2_db_val)
        
        # Check if R1 DB matches R1 file
        r1_match = False
        if r1_db_val != 'N/A' and isinstance(r1_val, (int, float)) and isinstance(r1_db_val, (int, float)):
            r1_match = abs(float(r1_val) - float(r1_db_val)) < 0.01
        
        # Check if R2 DB matches differential
        r2_match = False
        if r2_db_val != 'N/A' and diff_calc != 'N/A' and isinstance(r2_db_val, (int, float)) and isinstance(diff_calc, (int, float)):
            r2_match = abs(float(r2_db_val) - float(diff_calc)) < 0.01
        
        # Overall status
        if r1_db_val == 'N/A' or r2_db_val == 'N/A':
            status = '⚠️ Missing'
        elif r1_match and r2_match:
            status = '✅'
        else:
            status = f"❌ R1:{r1_match} R2:{r2_match}"
        
        print(f"{field_name:<35} {r1_str:<15} {r2_str:<15} {diff_str:<15} {r1_db_str:<15} {r2_db_str:<15} {status}")
    
    # Show database-only fields that don't have raw file equivalents
    print("\n" + "="*130)
    print("DATABASE-ONLY FIELDS (calculated or derived)")
    print("="*130)
    
    db_only_fields = ['id', 'session_id', 'kills', 'deaths', 'efficiency']
    for field in db_only_fields:
        if field in r1_db and field in r2_db:
            print(f"{field:<35} {'N/A':<15} {'N/A':<15} {'N/A':<15} {str(r1_db[field]):<15} {str(r2_db[field]):<15} {'ℹ️ Derived'}")
    
    # Show ALL database columns to catch anything we missed
    print("\n" + "="*130)
    print("ALL DATABASE COLUMNS (complete list)")
    print("="*130)
    print(f"\nR1 Database (session_id={r1_db['session_id']}):")
    for key, val in r1_db.items():
        print(f"  {key:<40} = {val}")
    
    print(f"\nR2 Database (session_id={r2_db['session_id']}):")
    for key, val in r2_db.items():
        print(f"  {key:<40} = {val}")

if __name__ == '__main__':
    verify_complete_mapping()
