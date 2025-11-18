#!/usr/bin/env python3
"""Extract schema from backup database"""
import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db.backup_before_wipe_20251103')
cursor = conn.cursor()

# Get all tables
tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print(f"Found {len(tables)} tables:\n")

for table_name, in tables:
    print(f"\n{'='*70}")
    print(f"TABLE: {table_name}")
    print('='*70)
    
    # Get schema
    schema = cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'").fetchone()[0]
    print(schema)
    print()

conn.close()
