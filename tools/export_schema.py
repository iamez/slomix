#!/usr/bin/env python3
"""
Export SQLite schema to file
"""
import sqlite3

# Connect to database
conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Get all schema definitions
cursor.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type, name")
schema_lines = [row[0] for row in cursor.fetchall()]

# Write to file
with open('tools/schema_sqlite.sql', 'w', encoding='utf-8') as f:
    f.write('-- SQLite Schema Export\n')
    f.write('-- Exported from: bot/etlegacy_production.db\n')
    f.write('-- Date: 2025-11-05\n\n')
    for sql in schema_lines:
        f.write(sql + ';\n\n')

conn.close()
print('✅ Schema exported to tools/schema_sqlite.sql')
