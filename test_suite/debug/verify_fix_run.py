#!/usr/bin/env python3
"""
Small verification script to run parser on a sample stats file and query
weapon rows for the latest session in bot/etlegacy_production.db.

Usage: python verify_fix_run.py

This prints parser results summary and weapon row counts for latest session.
"""
import os
import sys
import sqlite3
import glob

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
# Path to parser (bot package lives at bot/)
BOT_DIR = os.path.join(ROOT, 'bot')
DB_PATH = os.path.join(ROOT, 'bot', 'etlegacy_production.db')
LOCAL_STATS_DIR = os.path.join(ROOT, 'local_stats')

sys.path.insert(0, BOT_DIR)

SAMPLE_FILE = None
# Pick a recent stats file from local_stats if present
if os.path.isdir(LOCAL_STATS_DIR):
    files = sorted(glob.glob(os.path.join(LOCAL_STATS_DIR, '*.txt')))
    if files:
        SAMPLE_FILE = files[-1]

print('\nVERIFY FIX RUN')
print('Project root:', ROOT)
print('DB path:', DB_PATH)
if SAMPLE_FILE:
    print('Sample stats file selected:', SAMPLE_FILE)
else:
    print('No sample stats file found under local_stats; parser test will be skipped')

# 1) Run parser test if we have a sample file
if SAMPLE_FILE:
    try:
        from community_stats_parser import C0RNP0RN3StatsParser
    except Exception as e:
        print('\nERROR: Failed to import parser:', e)
        print('Make sure bot/community_stats_parser.py is present and importable')
    else:
        print('\nRunning parser...')
        try:
            parser = C0RNP0RN3StatsParser()
            result = parser.parse_stats_file(SAMPLE_FILE)
        except Exception as e:
            print('\nPARSER CRASHED:')
            import traceback
            traceback.print_exc()
            result = None

        if result:
            print('\nPARSER RESULT:')
            print('  map_name:', result.get('map_name'))
            print('  round_num:', result.get('round_num'))
            players = result.get('players', [])
            print('  players parsed:', len(players))
            if players:
                p = players[0]
                print('  sample player name:', p.get('name'))
                ws = p.get('weapon_stats') or {}
                print('  sample player weapon count:', len(ws))
                # Print first 3 weapons
                for i, (wname, wdata) in enumerate(list(ws.items())[:3]):
                    print(f"    - {wname}: kills={wdata.get('kills')} hits={wdata.get('hits')} shots={wdata.get('shots')} headshots={wdata.get('headshots')} accuracy={wdata.get('accuracy')}")
        else:
            print('\nParser returned no result or error')

# 2) Query DB for latest session weapon rows
print('\nQuerying DB for latest session weapon stats...')
if not os.path.exists(DB_PATH):
    print('ERROR: DB file not found at', DB_PATH)
    sys.exit(1)

try:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, session_date, map_name, round_number FROM sessions ORDER BY session_date DESC LIMIT 1")
    row = cur.fetchone()
    if not row:
        print('No sessions found in sessions table')
    else:
        session_id, session_date, map_name, round_number = row
        print(f"Latest session: id={session_id}, map={map_name}, round={round_number}, date={session_date}")
        cur.execute("SELECT COUNT(*) FROM weapon_comprehensive_stats WHERE session_id = ?", (session_id,))
        cnt = cur.fetchone()[0]
        print('weapon_comprehensive_stats row count for latest session:', cnt)
        cur.execute("SELECT SUM(hits), SUM(shots), SUM(headshots) FROM weapon_comprehensive_stats WHERE session_id = ?", (session_id,))
        sums = cur.fetchone()
        print('SUM(hits), SUM(shots), SUM(headshots):', sums)
    conn.close()
except Exception as e:
    print('DB query failed:')
    import traceback
    traceback.print_exc()

print('\nVerify run complete')
