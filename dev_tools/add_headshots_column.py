"""
Add headshots column to player_comprehensive_stats table

The database was storing headshot_kills (TAB field 14 - actual kills with headshot)
but we also need headshots (sum of weapon headshot hits) which is what we display.

To match parser naming:
- headshots = player['headshots'] (weapon hits sum)
- headshot_kills = objective_stats['headshot_kills'] (TAB field 14)
"""

import sqlite3
import sys

def migrate():
    db_path = 'bot/etlegacy_production.db'
    
    print(f"Connecting to {db_path}...")
    db = sqlite3.connect(db_path)
    c = db.cursor()
    
    # Check if column already exists
    cols = c.execute("PRAGMA table_info(player_comprehensive_stats)").fetchall()
    col_names = [col[1] for col in cols]
    
    if 'headshots' in col_names:
        print("✅ Column 'headshots' already exists!")
        return
    
    print("Adding 'headshots' column...")
    c.execute("""
        ALTER TABLE player_comprehensive_stats 
        ADD COLUMN headshots INTEGER DEFAULT 0
    """)
    
    db.commit()
    print("✅ Migration complete!")
    print("\nNext steps:")
    print("1. Update ultimate_bot.py INSERT to include headshots")
    print("2. Update ultimate_bot.py query to SELECT headshots")
    print("3. Optionally backfill data from weapon_comprehensive_stats")

if __name__ == '__main__':
    migrate()
