import sqlite3

# Check the backup database for the correct schema
conn = sqlite3.connect(
    'database_backups/dpm_fix_20251003_103546/etlegacy_production_before_dpm_fix.db'
)
c = conn.cursor()

# Get the CREATE statement for player_objective_stats
schema = c.execute(
    "SELECT sql FROM sqlite_master WHERE type='table' AND name='player_objective_stats'"
).fetchone()

if schema:
    print("player_objective_stats schema:")
    print(schema[0])
else:
    print("⚠️ Table not found in backup either!")

conn.close()
