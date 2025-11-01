import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

# Add the missing player_objective_stats table
c.execute(
    '''
    CREATE TABLE IF NOT EXISTS player_objective_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        player_guid TEXT NOT NULL,
        killing_spree_best INTEGER DEFAULT 0,
        death_spree_worst INTEGER DEFAULT 0,
        kill_assists INTEGER DEFAULT 0,
        kill_steals INTEGER DEFAULT 0,
        objectives_stolen INTEGER DEFAULT 0,
        objectives_returned INTEGER DEFAULT 0,
        dynamites_planted INTEGER DEFAULT 0,
        dynamites_defused INTEGER DEFAULT 0,
        times_revived INTEGER DEFAULT 0,
        bullets_fired INTEGER DEFAULT 0,
        tank_meatshield_score REAL DEFAULT 0.0,
        time_dead_ratio REAL DEFAULT 0.0,
        time_dead_minutes REAL DEFAULT 0.0,
        useful_kills INTEGER DEFAULT 0,
        useless_kills INTEGER DEFAULT 0,
        denied_playtime_seconds INTEGER DEFAULT 0,
        full_selfkills INTEGER DEFAULT 0,
        repairs_constructions INTEGER DEFAULT 0,
        multikill_2x INTEGER DEFAULT 0,
        multikill_3x INTEGER DEFAULT 0,
        multikill_4x INTEGER DEFAULT 0,
        multikill_5x INTEGER DEFAULT 0,
        multikill_6x INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions(id),
        UNIQUE(session_id, player_guid)
    )
'''
)

conn.commit()
print("✅ player_objective_stats table created!")

# Verify
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print(f"\nDatabase now has {len(tables)} tables:")
for table in tables:
    print(f"  - {table[0]}")

conn.close()
