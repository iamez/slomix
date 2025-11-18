import sqlite3
import json

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

print("="*80)
print("CHECKING SESSION_TEAMS TABLE")
print("="*80)

# Check Oct 28 and 30
for date in ['2024-10-28', '2024-10-30', '2025-10-27', '2025-11-01']:
    cursor.execute("""
        SELECT session_start_date, team_name, player_guids, player_names
        FROM session_teams
        WHERE session_start_date = ?
        ORDER BY team_name
    """, (date,))
    
    rows = cursor.fetchall()
    
    if rows:
        print(f"\n{date}:")
        print("-"*80)
        for row in rows:
            team_name = row[1]
            guids = json.loads(row[2]) if row[2] else []
            names = json.loads(row[3]) if row[3] else []
            
            print(f"\n  Team: {team_name}")
            print(f"  Players: {len(guids)}")
            for i, name in enumerate(names):
                guid = guids[i] if i < len(guids) else "?"
                print(f"    - {name} ({guid})")
    else:
        print(f"\n{date}: No teams stored")

conn.close()
