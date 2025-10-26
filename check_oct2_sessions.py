#!/usr/bin/env python3
"""Check Oct 2 sessions data"""

import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

# Check sessions table
print("=== SESSIONS TABLE (Oct 2) ===")
c.execute('SELECT COUNT(*) FROM sessions WHERE session_date LIKE "2025-10-02%"')
sessions_count = c.fetchone()[0]
print(f"Total records: {sessions_count}")

c.execute('SELECT id, session_date, map_name, round_number FROM sessions WHERE session_date LIKE "2025-10-02%" ORDER BY id')
sessions = c.fetchall()
print(f"\nAll {len(sessions)} sessions:")
for row in sessions:
    print(f"  ID {row[0]}: {row[1]} - {row[2]} R{row[3]}")

# Check player_comprehensive_stats
print("\n=== PLAYER_COMPREHENSIVE_STATS (Oct 2) ===")
c.execute('SELECT COUNT(DISTINCT session_id) FROM player_comprehensive_stats WHERE session_date = "2025-10-02"')
player_sessions = c.fetchone()[0]
print(f"Unique session_ids: {player_sessions}")

c.execute('SELECT DISTINCT session_id FROM player_comprehensive_stats WHERE session_date = "2025-10-02" ORDER BY session_id')
player_session_ids = [row[0] for row in c.fetchall()]
print(f"Session IDs: {player_session_ids[:10]}...")

# Check what the bot is seeing
print("\n=== WHAT BOT SEES (last_session query) ===")
c.execute('''
    SELECT DISTINCT session_date as date
    FROM sessions
    ORDER BY date DESC
    LIMIT 1
''')
latest_date = c.fetchone()[0]
print(f"Latest date from sessions table: {latest_date}")

# Get all sessions for that date
c.execute('''
    SELECT id, map_name, round_number, actual_time
    FROM sessions
    WHERE session_date = ?
    ORDER BY id ASC
''', (latest_date,))
bot_sessions = c.fetchall()
print(f"\nBot found {len(bot_sessions)} sessions for {latest_date}:")
for s in bot_sessions:
    print(f"  ID {s[0]}: {s[1]} R{s[2]} ({s[3]})")

# Check maps played
c.execute('''
    SELECT DISTINCT map_name, COUNT(DISTINCT round_number) as rounds
    FROM sessions
    WHERE session_date = ?
    GROUP BY map_name
''', (latest_date,))
maps = c.fetchall()
print(f"\nMaps: {len(maps)} unique maps:")
for m in maps:
    print(f"  {m[0]}: {m[1]} rounds")

conn.close()
