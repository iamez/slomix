"""
Update team names in session_teams table from generic "Team A"/"Team B" 
to actual team names based on player rosters.

Configure the TEAM_MAPPING below to match your teams!
"""

import sqlite3
import json


# 🎯 CONFIGURE YOUR TEAM MAPPING HERE
# Match player GUIDs or names to determine which team is which
TEAM_MAPPING = {
    # Team A: SuperBoyy, qmr, SmetarskiProner
    'Team A': 'puran',
    
    # Team B: vid, endekk, .olz  
    'Team B': 'insAne',
}

# Alternative: If you want to identify teams by specific players
# Uncomment and customize this instead:
"""
PLAYER_BASED_MAPPING = {
    'puran': ['SuperBoyy', 'qmr', 'SmetarskiProner'],
    'insAne': ['vid', 'endekk', '.olz'],
    'sWat': ['player4', 'player5', 'player6'],
    'maDdogs': ['player7', 'player8', 'player9'],
    'slomix': ['player10', 'player11', 'player12'],
    'slo': ['player13', 'player14', 'player15'],
}
"""


def update_team_names():
    """Update team names in session_teams table."""
    
    db_path = "etlegacy_production.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("=" * 80)
    print("🎮 ET:Legacy - Update Team Names")
    print("=" * 80)
    print()
    
    # Show current team names
    print("📋 Current team names:")
    cursor.execute('''
        SELECT DISTINCT team_name, player_names 
        FROM session_teams 
        ORDER BY team_name
    ''')
    
    for team_name, names_json in cursor.fetchall():
        names = json.loads(names_json)
        print(f"  {team_name}: {', '.join(names)}")
    
    print()
    print("🔄 Mapping configuration:")
    for old_name, new_name in TEAM_MAPPING.items():
        print(f"  {old_name} → {new_name}")
    
    print()
    input("Press ENTER to continue with the update, or Ctrl+C to cancel...")
    print()
    
    # Update each team name
    updates_made = 0
    for old_name, new_name in TEAM_MAPPING.items():
        cursor.execute('''
            UPDATE session_teams
            SET team_name = ?
            WHERE team_name = ?
        ''', (new_name, old_name))
        
        count = cursor.rowcount
        updates_made += count
        print(f"✅ Updated {count} records: {old_name} → {new_name}")
    
    conn.commit()
    
    print()
    print("=" * 80)
    print(f"🎉 SUCCESS! Updated {updates_made} records")
    print("=" * 80)
    print()
    
    # Verify the changes
    print("📊 Verification - New team names:")
    cursor.execute('''
        SELECT DISTINCT team_name, player_names 
        FROM session_teams 
        ORDER BY team_name
    ''')
    
    for team_name, names_json in cursor.fetchall():
        names = json.loads(names_json)
        print(f"  {team_name}: {', '.join(names)}")
    
    print()
    print("✅ Team names updated successfully!")
    print("   Restart the Discord bot to see the new names in action.")
    
    conn.close()
    return True


if __name__ == "__main__":
    try:
        update_team_names()
    except KeyboardInterrupt:
        print("\n\n❌ Update cancelled by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
