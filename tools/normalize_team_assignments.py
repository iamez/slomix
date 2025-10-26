"""
Normalize team assignments in session_teams table.

Problem: Teams are labeled "Team A"/"Team B" based on who attacks first (Allies),
but we need consistent labels based on player composition.

Solution: Identify the two unique player sets and assign consistent team names.
"""

import sqlite3
import json


def normalize_team_assignments():
    """Normalize team assignments to be consistent across all maps."""
    
    db_path = "etlegacy_production.db"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("📊 Analyzing team compositions...")
    
    # Get all teams from October 2nd
    cursor.execute('''
        SELECT id, session_start_date, map_name, team_name, player_guids, player_names
        FROM session_teams
        WHERE session_start_date LIKE '2025-10-02%'
        ORDER BY session_start_date
    ''')
    
    all_teams = cursor.fetchall()
    
    # Group by unique player GUID sets
    guid_sets = {}
    
    for row in all_teams:
        team_id, session_date, map_name, team_name, guids_json, names_json = row
        guids = json.loads(guids_json)
        names = json.loads(names_json)
        
        # Create a sorted tuple for comparison
        guid_tuple = tuple(sorted(guids))
        
        if guid_tuple not in guid_sets:
            guid_sets[guid_tuple] = {
                'names': names,
                'occurrences': []
            }
        
        guid_sets[guid_tuple]['occurrences'].append({
            'id': team_id,
            'session_date': session_date,
            'map_name': map_name,
            'old_team_name': team_name
        })
    
    print(f"\n✅ Found {len(guid_sets)} unique team compositions\n")
    
    # Assign consistent team names
    team_mapping = {}
    for idx, (guid_tuple, data) in enumerate(sorted(guid_sets.items()), 1):
        team_letter = chr(64 + idx)  # A, B, C, etc.
        new_team_name = f"Team {team_letter}"
        team_mapping[guid_tuple] = new_team_name
        
        names_str = ', '.join(data['names'])
        print(f"{new_team_name}: {names_str}")
        print(f"  Appears in {len(data['occurrences'])} maps")
        
        # Show which maps need updating
        for occ in data['occurrences']:
            if occ['old_team_name'] != new_team_name:
                print(f"    {occ['map_name']:20} | {occ['old_team_name']} → {new_team_name}")
    
    print("\n" + "="*80)
    print("🔧 UPDATING DATABASE...")
    print("="*80 + "\n")
    
    # Due to UNIQUE constraint, delete ALL October 2nd records first
    print("🗑️  Deleting all October 2nd records...")
    cursor.execute('''
        DELETE FROM session_teams
        WHERE session_start_date LIKE '2025-10-02%'
    ''')
    print(f"   Deleted {cursor.rowcount} records\n")
    
    # Now re-insert everything with correct team names
    print("📝 Re-inserting with normalized team names...\n")
    
    inserts_made = 0
    for guid_tuple, new_team_name in team_mapping.items():
        guids_list = list(guid_tuple)
        names_list = guid_sets[guid_tuple]['names']
        
        for occ in guid_sets[guid_tuple]['occurrences']:
            cursor.execute('''
                INSERT INTO session_teams
                (session_start_date, map_name, team_name,
                 player_guids, player_names)
                VALUES (?, ?, ?, ?, ?)
            ''', (occ['session_date'], occ['map_name'], new_team_name,
                  json.dumps(guids_list), json.dumps(names_list)))
            
            inserts_made += 1
            
            if occ['old_team_name'] != new_team_name:
                map_name = occ['map_name']
                old_name = occ['old_team_name']
                print(f"✅ {map_name:20} | {old_name} → {new_team_name}")
            else:
                print(f"   {occ['map_name']:20} | {new_team_name} "
                      f"(no change)")
    
    conn.commit()
    
    print(f"\n🎉 {inserts_made} records re-inserted with "
          f"normalized team names!")
    
    # Verification
    print("\n" + "="*80)
    print("📊 VERIFICATION - Final Team Assignments")
    print("="*80 + "\n")
    
    cursor.execute('''
        SELECT session_start_date, map_name, team_name, player_names
        FROM session_teams
        WHERE session_start_date LIKE '2025-10-02%'
        ORDER BY session_start_date, team_name
    ''')
    
    for row in cursor.fetchall():
        session_date, map_name, team_name, names_json = row
        names = json.loads(names_json)
        names_str = ', '.join(names)
        print(f"{session_date} | {map_name:20} | {team_name:7} | {names_str}")
    
    conn.close()
    
    return True


if __name__ == "__main__":
    print("=" * 80)
    print("🎮 ET:Legacy - Normalize Team Assignments")
    print("=" * 80)
    print()
    
    success = normalize_team_assignments()
    
    if success:
        print("\n✅ Team assignments normalized successfully!")
        print("Teams are now consistently labeled across all maps")
    else:
        print("\n❌ Failed to normalize teams")
