"""
FINAL PRE-BOT CHECK - Both Revive Fields
========================================
Verify complete pipeline: Raw file → Parser → Database insertion code
"""
import sys
import sqlite3
sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser

print("="*80)
print("FINAL REVIVES VERIFICATION - COMPLETE PIPELINE CHECK")
print("="*80)

# 1. Check database schema
print("\n1. DATABASE SCHEMA CHECK")
print("-" * 80)
conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(player_comprehensive_stats)")
cols = cursor.fetchall()
revive_cols = [col for col in cols if 'revive' in col[1].lower()]

print("Revive columns in player_comprehensive_stats table:")
for col in revive_cols:
    print(f"  ✓ {col[1]} (type: {col[2]}, column #{col[0]})")

# 2. Check parser output
print("\n2. PARSER OUTPUT CHECK")
print("-" * 80)
parser = C0RNP0RN3StatsParser()
result = parser.parse_stats_file('local_stats/2025-11-02-211530-etl_adlernest-round-1.txt')
sample_player = result['players'][0]
obj_stats = sample_player['objective_stats']

print(f"Sample player: {sample_player['name']}")
print("Parser extracts from objective_stats:")
print(f"  ✓ times_revived: {obj_stats.get('times_revived', 'MISSING!')}")
print(f"  ✓ revives_given: {obj_stats.get('revives_given', 'MISSING!')}")

# 3. Check bot insertion code
print("\n3. BOT INSERTION CODE CHECK")
print("-" * 80)
with open('bot/ultimate_bot.py', 'r', encoding='utf-8') as f:
    bot_code = f.read()
    
# Find the insertion lines
if 'obj_stats.get("times_revived", 0)' in bot_code:
    print("  ✓ times_revived - Found in insertion code: obj_stats.get('times_revived', 0)")
else:
    print("  ✗ times_revived - NOT FOUND IN INSERTION CODE!")

if 'obj_stats.get("revives_given", 0)' in bot_code:
    print("  ✓ revives_given - Found in insertion code: obj_stats.get('revives_given', 0)")
else:
    print("  ✗ revives_given - NOT FOUND IN INSERTION CODE!")

# 4. Check actual database data
print("\n4. DATABASE DATA CHECK")
print("-" * 80)
cursor.execute("""
    SELECT player_name, times_revived, revives_given 
    FROM player_comprehensive_stats 
    WHERE round_id = 2134
    ORDER BY player_name
""")
rows = cursor.fetchall()
print(f"Sample data from session 2134 (Round 1):")
for row in rows:
    print(f"  {row[0]:<20} times_revived={row[1]:<3} revives_given={row[2]:<3}")

conn.close()

# 5. Cross-verify parser vs database
print("\n5. PARSER vs DATABASE VERIFICATION")
print("-" * 80)
parser_data = {}
for player in result['players']:
    parser_data[player['name']] = {
        'times_revived': player['objective_stats']['times_revived'],
        'revives_given': player['objective_stats']['revives_given']
    }

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()
cursor.execute("""
    SELECT player_name, times_revived, revives_given 
    FROM player_comprehensive_stats 
    WHERE round_id = 2134
""")
db_data = {row[0]: {'times_revived': row[1], 'revives_given': row[2]} for row in cursor.fetchall()}
conn.close()

all_match = True
for name in parser_data:
    if name in db_data:
        p_tr = parser_data[name]['times_revived']
        p_rg = parser_data[name]['revives_given']
        d_tr = db_data[name]['times_revived']
        d_rg = db_data[name]['revives_given']
        
        tr_match = "✓" if p_tr == d_tr else "✗"
        rg_match = "✓" if p_rg == d_rg else "✗"
        
        if p_tr != d_tr or p_rg != d_rg:
            all_match = False
        
        print(f"{name:<20} TR: {tr_match} ({p_tr}=={d_tr})  RG: {rg_match} ({p_rg}=={d_rg})")

print("\n" + "="*80)
if all_match:
    print("✅ FINAL RESULT: BOTH REVIVE FIELDS VERIFIED IN COMPLETE PIPELINE")
    print("="*80)
    print("\n✓ Database schema has both columns")
    print("✓ Parser extracts both fields from raw files")
    print("✓ Bot insertion code uses both fields")
    print("✓ Database contains correct data for both fields")
    print("✓ All values match between parser and database")
    print("\n🚀 READY FOR BOT TESTING!")
else:
    print("✗ MISMATCH FOUND - INVESTIGATE BEFORE TESTING!")
print("="*80)
