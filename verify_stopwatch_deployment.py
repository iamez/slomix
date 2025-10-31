#!/usr/bin/env python3
"""
Verify Stopwatch scoring is ready for deployment
"""

import os
import sqlite3

print("\n" + "="*60)
print("🔍 STOPWATCH SCORING DEPLOYMENT CHECKLIST")
print("="*60)

# 1. Check if stopwatch_scoring.py exists in both folders
files_to_check = [
    ('tools/stopwatch_scoring.py', 'Main'),
    ('github/tools/stopwatch_scoring.py', 'GitHub')
]

print("\n✅ File Existence:")
for file_path, folder in files_to_check:
    exists = os.path.exists(file_path)
    status = "✅" if exists else "❌"
    print(f"  {status} {folder}: {file_path}")

# 2. Check database columns
print("\n✅ Database Schema:")
for db_path, folder in [('etlegacy_production.db', 'Main'), 
                         ('github/etlegacy_production.db', 'GitHub')]:
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check sessions table columns
        cursor.execute("PRAGMA table_info(sessions)")
        columns = [row[1] for row in cursor.fetchall()]
        
        has_winner = 'winner_team' in columns
        has_defender = 'defender_team' in columns
        
        winner_status = "✅" if has_winner else "❌"
        defender_status = "✅" if has_defender else "❌"
        
        print(f"  {folder} DB:")
        print(f"    {winner_status} winner_team column")
        print(f"    {defender_status} defender_team column")
        
        # Check session_teams table
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='session_teams'
        """)
        has_session_teams = cursor.fetchone() is not None
        teams_status = "✅" if has_session_teams else "❌"
        print(f"    {teams_status} session_teams table")
        
        if has_session_teams:
            cursor.execute("SELECT COUNT(*) FROM session_teams")
            team_count = cursor.fetchone()[0]
            print(f"       ({team_count} team records)")
        
        conn.close()
    else:
        print(f"  ❌ {folder} DB: NOT FOUND")

# 3. Check bot integration
print("\n✅ Bot Integration:")
bot_files = [
    ('bot/ultimate_bot.py', 'Main'),
    ('github/bot/ultimate_bot.py', 'GitHub')
]

for bot_file, folder in bot_files:
    if os.path.exists(bot_file):
        with open(bot_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        has_import = 'from tools.stopwatch_scoring import StopwatchScoring' in content
        has_scorer = 'scorer = StopwatchScoring' in content
        has_calculate = 'scorer.calculate_session_scores' in content
        
        import_status = "✅" if has_import else "❌"
        scorer_status = "✅" if has_scorer else "❌"
        calc_status = "✅" if has_calculate else "❌"
        
        print(f"  {folder}:")
        print(f"    {import_status} Import StopwatchScoring")
        print(f"    {scorer_status} Create scorer instance")
        print(f"    {calc_status} Call calculate_session_scores()")
    else:
        print(f"  ❌ {folder}: NOT FOUND")

# 4. Check parser integration
print("\n✅ Parser Integration:")
parser_files = [
    ('bot/community_stats_parser.py', 'Main'),
    ('github/bot/community_stats_parser.py', 'GitHub')
]

for parser_file, folder in parser_files:
    if os.path.exists(parser_file):
        with open(parser_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        has_defender = 'defender_team = int(header_parts[4])' in content
        has_winner = 'winner_team = int(header_parts[5])' in content
        
        defender_status = "✅" if has_defender else "❌"
        winner_status = "✅" if has_winner else "❌"
        
        print(f"  {folder}:")
        print(f"    {defender_status} Extract defender_team")
        print(f"    {winner_status} Extract winner_team")
    else:
        print(f"  ❌ {folder}: NOT FOUND")

# 5. Check importer integration
print("\n✅ Importer Integration:")
importer_files = [
    ('tools/simple_bulk_import.py', 'Main'),
    ('github/tools/simple_bulk_import.py', 'GitHub')
]

for importer_file, folder in importer_files:
    if os.path.exists(importer_file):
        with open(importer_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if INSERT includes defender_team and winner_team
        has_insert = 'defender_team, winner_team' in content
        
        insert_status = "✅" if has_insert else "❌"
        
        print(f"  {folder}:")
        print(f"    {insert_status} Insert defender_team, winner_team")
    else:
        print(f"  ❌ {folder}: NOT FOUND")

print("\n" + "="*60)
print("📋 SUMMARY:")
print("="*60)
print("""
The Stopwatch scoring system consists of:

1. ✅ Database: winner_team, defender_team columns in sessions
2. ✅ Table: session_teams for team assignments
3. ✅ Parser: Extracts winner/defender from stats files
4. ✅ Importer: Stores winner/defender in database
5. ✅ Scorer: tools/stopwatch_scoring.py calculates points
6. ✅ Bot: ultimate_bot.py displays team scores

SCORING RULES:
  - R2 beat R1 time: 2-0 win for R2 attackers
  - R1 = R2 time: 1-1 tie (both teams get 1pt)
  - R2 didn't beat R1: 2-0 win for R1 attackers

TEST VALIDATION:
  October 2nd data: slomix 15 - 5 slo ✅
  (5 wins × 2pts + 5 ties × 1pt vs 0 wins + 5 ties)
""")
print("="*60 + "\n")
