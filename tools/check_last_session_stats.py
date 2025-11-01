import sqlite3
import os
import sys

DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bot', 'etlegacy_production.db')
if not os.path.exists(DB):
    print('DB not found:', DB)
    sys.exit(2)

conn = sqlite3.connect(DB)
cur = conn.cursor()

# Get latest date
cur.execute("SELECT DISTINCT SUBSTR(session_date,1,10) as d FROM sessions ORDER BY d DESC LIMIT 1")
row = cur.fetchone()
if not row:
    print('No sessions found')
    sys.exit(0)

latest = row[0]
print('Latest session date:', latest)

# Get session ids
cur.execute("SELECT id FROM sessions WHERE SUBSTR(session_date,1,10)=? ORDER BY id", (latest,))
sids = [r[0] for r in cur.fetchall()]
if not sids:
    print('No sessions for date')
    sys.exit(0)

print('Session IDs:', sids)

# For each player, compare aggregated weapon hits/shots/headshots to player_comprehensive_stats
placeholders = ','.join('?' for _ in sids)

# Aggregate weapon stats per player
q = f"""
SELECT w.player_guid, p.player_name,
       SUM(w.hits) as hits, SUM(w.shots) as shots, SUM(w.headshots) as headshots,
       SUM(w.kills) as w_kills
FROM weapon_comprehensive_stats w
LEFT JOIN player_comprehensive_stats p ON p.player_guid = w.player_guid AND p.session_id = w.session_id
WHERE w.session_id IN ({placeholders})
GROUP BY w.player_guid
"""
cur.execute(q, sids)
weapon_stats = {r[0]: {'name': r[1], 'hits': r[2] or 0, 'shots': r[3] or 0, 'headshots': r[4] or 0, 'w_kills': r[5] or 0} for r in cur.fetchall()}

# Get player aggregates
q2 = f"""
SELECT player_guid, player_name, SUM(kills) as kills, SUM(headshot_kills) as headshots, AVG(accuracy) as accuracy
FROM player_comprehensive_stats
WHERE session_id IN ({placeholders})
GROUP BY player_guid
"""
cur.execute(q2, sids)
player_stats = {r[0]: {'name': r[1], 'kills': r[2] or 0, 'headshots': r[3] or 0, 'accuracy': r[4] or 0.0} for r in cur.fetchall()}

# Compare
print('\nPlayers with weapon rows missing or zeroed:')
bad = []
for guid, p in player_stats.items():
    ws = weapon_stats.get(guid)
    if not ws:
        bad.append((guid, p['name'], 'NO_WEAPON_ROWS', p['kills'], p['headshots'], p['accuracy']))
    else:
        # if player has non-zero kills or headshots but hits/shots are zero, it's suspicious
        if (p['kills'] > 0 or p['headshots'] > 0) and (ws['hits'] == 0 and ws['shots'] == 0):
            bad.append((guid, p['name'], 'ZERO_HITS_SHOTS', p['kills'], p['headshots'], p['accuracy'], ws['w_kills'], ws['hits'], ws['shots'], ws['headshots']))
        # Compare accuracy within tolerance
        calc_acc = (ws['hits'] / ws['shots'] * 100) if ws['shots'] > 0 else 0.0
        if abs(calc_acc - p['accuracy']) > 1.0:
            bad.append((guid, p['name'], 'ACC_MISMATCH', p['accuracy'], calc_acc, ws['hits'], ws['shots']))

if not bad:
    print('OK - no discrepancies found')
else:
    for b in bad:
        print(b)

# Also list any weapon rows that don't match a player row (orphaned weapon rows)
cur.execute(f"SELECT DISTINCT player_guid FROM weapon_comprehensive_stats WHERE session_id IN ({placeholders})", sids)
guids_in_weapons = {r[0] for r in cur.fetchall()}
missing_players = guids_in_weapons - set(player_stats.keys())
if missing_players:
    print('\nOrphaned weapon player_guids (no player row):')
    for g in missing_players:
        print(g)

conn.close()
