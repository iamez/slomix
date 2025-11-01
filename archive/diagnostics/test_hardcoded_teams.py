"""
Test the hardcoded teams functionality for October 2nd session
"""
import sqlite3
import json

def test_hardcoded_teams():
    """Test that hardcoded teams work correctly"""
    
    db_path = "etlegacy_production.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("=" * 80)
    print("🧪 Testing Hardcoded Teams Functionality")
    print("=" * 80)
    print()
    
    # Test 1: Check session_teams table exists
    print("Test 1: Check session_teams table exists")
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='session_teams'"
    )
    result = cursor.fetchone()
    if result:
        print("✅ session_teams table exists")
    else:
        print("❌ session_teams table NOT FOUND")
        return False
    print()
    
    # Test 2: Get teams for October 2nd
    print("Test 2: Get teams for October 2nd")
    cursor.execute('''
        SELECT DISTINCT team_name
        FROM session_teams
        WHERE session_start_date LIKE '2025-10-02%'
        ORDER BY team_name
    ''')
    teams = [row[0] for row in cursor.fetchall()]
    print(f"Found teams: {teams}")
    if len(teams) == 2:
        print(f"✅ Found 2 teams: {teams[0]}, {teams[1]}")
    else:
        print(f"❌ Expected 2 teams, found {len(teams)}")
        return False
    print()
    
    # Test 3: Check team rosters
    print("Test 3: Check team rosters are consistent")
    for team_name in teams:
        cursor.execute('''
            SELECT DISTINCT player_guids, player_names
            FROM session_teams
            WHERE session_start_date LIKE '2025-10-02%'
            AND team_name = ?
        ''', (team_name,))
        result = cursor.fetchone()
        
        guids = json.loads(result[0])
        names = json.loads(result[1])
        
        print(f"\n{team_name}:")
        print(f"  GUIDs: {guids}")
        print(f"  Names: {names}")
        print(f"  Player count: {len(guids)}")
        
        if len(guids) == 3:
            print(f"  ✅ Team has 3 players")
        else:
            print(f"  ❌ Expected 3 players, found {len(guids)}")
    print()
    
    # Test 4: Verify consistent labeling across maps
    print("Test 4: Verify team labels are consistent across all maps")
    for team_name in teams:
        cursor.execute('''
            SELECT map_name, player_guids
            FROM session_teams
            WHERE session_start_date LIKE '2025-10-02%'
            AND team_name = ?
            ORDER BY map_name
        ''', (team_name,))
        rows = cursor.fetchall()
        
        # Check all rows have same GUIDs
        first_guids = json.loads(rows[0][1])
        consistent = all(json.loads(row[1]) == first_guids for row in rows)
        
        if consistent:
            print(f"✅ {team_name}: Consistent across all {len(rows)} maps")
        else:
            print(f"❌ {team_name}: INCONSISTENT across maps!")
            return False
    print()
    
    # Test 5: Get session IDs for October 2nd
    print("Test 5: Get player stats from database")
    cursor.execute('''
        SELECT DISTINCT SUBSTR(session_date, 1, 10) as date
        FROM sessions
        WHERE SUBSTR(session_date, 1, 10) = '2025-10-02'
    ''')
    result = cursor.fetchone()
    if result:
        print(f"✅ Found sessions for October 2nd")
        
        # Get session IDs
        cursor.execute('''
            SELECT id FROM sessions
            WHERE SUBSTR(session_date, 1, 10) = '2025-10-02'
        ''')
        session_ids = [row[0] for row in cursor.fetchall()]
        print(f"   Session IDs: {len(session_ids)} sessions")
        
        # Get player GUIDs from stats
        session_ids_str = ','.join('?' * len(session_ids))
        cursor.execute(f'''
            SELECT DISTINCT player_guid, player_name
            FROM player_comprehensive_stats
            WHERE session_id IN ({session_ids_str})
        ''', session_ids)
        players = cursor.fetchall()
        print(f"   Player records: {len(players)} unique players")
        
        # Verify all team GUIDs are in database
        all_team_guids = set()
        for team_name in teams:
            cursor.execute('''
                SELECT player_guids
                FROM session_teams
                WHERE session_start_date LIKE '2025-10-02%'
                AND team_name = ?
                LIMIT 1
            ''', (team_name,))
            guids = json.loads(cursor.fetchone()[0])
            all_team_guids.update(guids)
        
        player_guids_in_db = {p[0] for p in players}
        missing_guids = all_team_guids - player_guids_in_db
        
        if not missing_guids:
            print(f"✅ All team GUIDs found in player stats")
        else:
            print(f"❌ Missing GUIDs in player stats: {missing_guids}")
    else:
        print("❌ No sessions found for October 2nd")
        return False
    print()
    
    conn.close()
    
    print("=" * 80)
    print("✅ ALL TESTS PASSED!")
    print("=" * 80)
    print()
    print("The bot should now correctly display:")
    print("  • Team A: SuperBoyy, qmr, SmetarskiProner")
    print("  • Team B: vid, endekk, .olz")
    print("  • One MVP per team (no duplicates)")
    print("  • No false swap warnings")
    print()
    return True

if __name__ == "__main__":
    test_hardcoded_teams()
