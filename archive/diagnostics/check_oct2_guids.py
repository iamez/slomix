"""Check actual player GUIDs from October 2nd session."""
import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# Get October 2nd players
cursor.execute("""
    SELECT DISTINCT player_guid, player_name
    FROM player_comprehensive_stats
    WHERE session_date = '2025-10-02'
    ORDER BY player_name
""")

players = cursor.fetchall()

print("="*80)
print("PLAYERS IN OCTOBER 2ND SESSION:")
print("="*80)
for guid, name in players:
    print(f"{name:<20} {guid}")

print()
print("="*80)
print("COMPARISON WITH SESSION_TEAMS TABLE:")
print("="*80)
print()
print("Team A (from session_teams):")
print("  GUIDs: ['1C747DF1', '652EB4A6', 'EDBB5DA9']")
print("  Names: ['SmetarskiProner', 'qmr', 'SuperBoyy']")
print()
print("Team B (from session_teams):")
print("  GUIDs: ['5D989160', '7B84BE88', 'D8423F90']")
print("  Names: ['endekk', 'vid', '.olz']")
print()

conn.close()
