#!/usr/bin/env python3
"""Check revive columns"""
import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()
cursor.execute('PRAGMA table_info(player_comprehensive_stats)')
cols = {row[1]: row[2] for row in cursor.fetchall()}

print('\n🔍 Revive Columns Check:')
print(f'  times_revived: {"✅ " + cols["times_revived"] if "times_revived" in cols else "❌ MISSING"}')
print(f'  revives_given: {"✅ " + cols["revives_given"] if "revives_given" in cols else "❌ MISSING"}')

conn.close()
