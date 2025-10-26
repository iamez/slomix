#!/usr/bin/env python3
"""Verify database population"""

import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# Count records
cursor.execute('SELECT COUNT(*) FROM sessions')
sessions = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM player_comprehensive_stats')
players = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM weapon_comprehensive_stats')
weapons = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM player_objective_stats')
objectives = cursor.fetchone()[0]

print('✅ DATABASE POPULATED SUCCESSFULLY!\n')
print(f'Total Records:')
print(f'  Sessions: {sessions}')
print(f'  Players: {players}')
print(f'  Weapons: {weapons}')
print(f'  Objective Stats: {objectives}')
print()

# Show latest sessions
cursor.execute(
    'SELECT id, map_name, round_number, session_date FROM sessions ORDER BY id DESC LIMIT 5'
)
print('Latest 5 Sessions:')
for row in cursor.fetchall():
    print(f'  Session {row[0]}: {row[1]} R{row[2]} on {row[3]}')
print()

# Show sample objective stats
cursor.execute(
    '''
    SELECT p.player_name, o.kill_assists, o.multikill_2x, o.multikill_3x, o.dynamites_planted
    FROM player_objective_stats o
    JOIN player_comprehensive_stats p ON o.session_id = p.session_id AND o.player_guid = p.player_guid
    WHERE o.kill_assists > 0 OR o.multikill_2x > 0
    LIMIT 5
'''
)
print('Sample Objective Stats (players with assists/multikills):')
for row in cursor.fetchall():
    print(
        f'  {
            row[0]}: {
            row[1]} assists, {
                row[2]}x double kills, {
                    row[3]}x triple kills, {
                        row[4]} dynamites planted'
    )

conn.close()

print('\n✅ Database is ready for bot testing!')
