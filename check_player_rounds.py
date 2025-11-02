#!/usr/bin/env python3
"""Check individual player round participation"""

import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

# Check carniee
player = "carniee"
date = "2025-10-30"

c.execute("""
    SELECT COUNT(DISTINCT session_id) as rounds_played
    FROM player_comprehensive_stats
    WHERE session_date LIKE ? AND clean_name = ?
""", (f"{date}%", player))

rounds_played = c.fetchone()[0]
print(f"{player} played {rounds_played} rounds on {date}")

# Total rounds in session
c.execute("""
    SELECT COUNT(DISTINCT id) as total_rounds
    FROM sessions
    WHERE session_date LIKE ?
""", (f"{date}%",))

total_rounds = c.fetchone()[0]
print(f"Total rounds in session: {total_rounds}")
print(f"{player} played {rounds_played/total_rounds*100:.1f}% of rounds")

conn.close()
