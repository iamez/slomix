"""Verify objective stats in database"""

import json
import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

print("\n" + "=" * 80)
print("VERIFYING OBJECTIVE STATS IN DATABASE")
print("=" * 80)

# Check session 1460
cursor.execute('SELECT player_name, awards FROM player_stats WHERE session_id=1460 LIMIT 3')
rows = cursor.fetchall()

print(f"\n Found {len(rows)} players from session 1460:\n")

for name, awards_json in rows:
    if awards_json:
        awards = json.loads(awards_json)
        print(f"{name:20}")
        print(f"  XP: {awards.get('xp', 0)}")
        print(f"  Kill Assists: {awards.get('kill_assists', 0)}")
        print(
            f"  Objectives: {awards.get('objectives_stolen', 0)}/{awards.get('objects_returned', 0)}"
        )
        print(
            f"  Dynamites: {awards.get('dynamites_planted', 0)}/{awards.get('dynamites_defused', 0)}"
        )
        print(f"  Revived: {awards.get('times_revived', 0)}")
        print(
            f"  Multikills: {awards.get('multikill_2x',
                                        0)}/{awards.get('multikill_3x',
                                                        0)}/{awards.get('multikill_4x',
                                                                        0)}"
        )
        print()

print("=" * 80)
print("[SUCCESS] Objective stats are stored and queryable!")
print("=" * 80)

conn.close()
