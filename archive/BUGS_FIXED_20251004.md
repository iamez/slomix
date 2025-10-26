================================================================================
BUGS FIXED - October 4, 2025
================================================================================

🐛 BUG #1: Parser Dropping Players with Fewer Weapons
------------------------------------------------------
Location: bot/community_stats_parser.py line 661

PROBLEM:
   Parser had validation: if len(stats_parts) < 30: return None
   This dropped any player using fewer than 6 weapons
   
EXAMPLE:
   olz in erdenberg Round 1 used only 5 weapons (26 fields)
   Parser silently dropped olz from Round 1 results
   
FIX APPLIED:
   Changed validation from < 30 to < 6 fields
   Now accepts any player with at least 1 weapon
   
IMPACT:
   - olz now appears in erdenberg Round 1: 8K/8D, 1863 damage
   - Any other players with fewer weapons will now be included
   - Historical data may have missing players who need re-import


🐛 BUG #2: Database UNIQUE Constraint Blocking Duplicate Maps
--------------------------------------------------------------
Location: Multiple schema files (migrate_database.py, etc.)

PROBLEM:
   UNIQUE(session_date, map_name, round_number) constraint
   Prevented playing same map multiple times on same date
   
EXAMPLE:
   October 2nd: 4 escape files (2 complete plays)
   Database: Only 1 escape entry (2nd play blocked)
   
FIX APPLIED:
   Removed UNIQUE constraint from all database schema files:
   - migrate_database.py
   - dev/create_production_database.py
   - dev/comprehensive_discord_bot.py
   - dev/initialize_database.py
   - tools/create_fresh_database.py
   - prompt_instructions/create_fresh_database.py
   
IMPACT:
   - Players can play same map multiple times per day
   - Each play tracked separately with full granularity


🐛 BUG #3: Importer Session Deduplication Logic
------------------------------------------------
Location: dev/bulk_import_stats.py lines 127-135

PROBLEM:
   Even without database UNIQUE constraint, importer had:
   
   cursor.execute("SELECT id FROM sessions WHERE ...")
   if existing:
       return existing[0]  # Reused same session!
   
   This meant multiple plays would UPDATE same session instead of CREATE new ones
   
EXAMPLE:
   Both escape plays would reuse same session ID
   Stats would be overwritten, not tracked separately
   
FIX APPLIED:
   Removed the lookup logic entirely
   Every file now creates a NEW session
   
IMPACT:
   - Multiple plays of same map = multiple sessions
   - Full granularity: every individual match tracked
   - Players can play 2, 3, 7 escapes if they want!


================================================================================
ADDITIONAL FIX: Round 2 DPM Correction
================================================================================

SIDE EFFECT DISCOVERED:
   olz's Round 2 DPM was showing 805.8 (wrong)
   This was cumulative stats (R1+R2 combined)
   
CORRECT STATS (after differential calculation):
   Round 2 only: 5K/4D, 1360 damage
   Actual DPM: (1360 × 60) / 240 = 340 DPM
   
This correction is automatic once parser fix is applied.


================================================================================
RE-IMPORT REQUIRED
================================================================================

To apply all fixes to historical data:

1. Delete current database:
   del etlegacy_production.db

2. Create fresh database with all tables:
   python migrate_database.py

3. Import all stats files:
   python dev/bulk_import_stats.py --year 2025

4. Verify fixes:
   python check_erdenberg_oct2.py


================================================================================
VERIFICATION CHECKLIST
================================================================================

After re-import, verify:

✅ olz appears in erdenberg Round 1
   Expected: 8K/8D, 1863 damage

✅ olz appears in erdenberg Round 2  
   Expected: 5K/4D, 1360 damage (differential)

✅ Two escape entries for October 2
   Expected: 4 sessions (2 × Round 1, 2 × Round 2)

✅ Multiple plays tracked separately
   Expected: Each file = unique session

✅ All players included (no missing players)
   Expected: Parser accepts 1+ weapons


================================================================================
FILES MODIFIED
================================================================================

1. bot/community_stats_parser.py
   - Line 661: Changed validation from < 30 to < 6 fields

2. migrate_database.py
   - Line 161: Removed UNIQUE constraint

3. dev/bulk_import_stats.py
   - Lines 127-135: Removed session lookup/reuse logic

4. tools/create_fresh_database.py
   - Line 43: Removed UNIQUE constraint

5. dev/create_production_database.py
   - Line 58: Removed UNIQUE constraint

6. dev/comprehensive_discord_bot.py
   - Line 92: Removed UNIQUE constraint

7. dev/initialize_database.py
   - Line 44: Removed UNIQUE constraint

8. prompt_instructions/create_fresh_database.py
   - Line 42: Removed UNIQUE constraint


================================================================================
COMMIT MESSAGE
================================================================================

Fix parser dropping players + allow multiple map plays

- Fix parser validation: change from < 30 to < 6 weapon fields
  Resolves issue where players using fewer weapons were silently dropped
  
- Remove UNIQUE constraint on sessions table
  Allow multiple plays of same map on same date
  
- Remove session deduplication in importer
  Each stat file creates unique session for full granularity
  
Fixes #issue_olz_missing_round1
Fixes #issue_escape_count_wrong

================================================================================
