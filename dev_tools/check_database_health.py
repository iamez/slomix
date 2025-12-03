import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

print("=" * 80)
print("DATABASE HEALTH CHECK")
print("=" * 80)

# Check each table's row count and schema
tables = ['rounds', 'player_comprehensive_stats', 'weapon_comprehensive_stats', 
          'player_links', 'processed_files', 'session_teams', 'player_aliases']

print("\n📊 TABLE POPULATIONS:")
print("-" * 80)

for table in tables:
    try:
        count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # nosec B608 - hardcoded table names
        # Get column count
        pragma = cursor.execute(f"PRAGMA table_info({table})").fetchall()  # nosec B608
        cols = len(pragma)
        
        status = "✅" if count > 0 else "⚠️ EMPTY"
        print(f"{status} {table:35} | Rows: {count:>8,} | Columns: {cols:>2}")
        
        # Show sample for populated tables
        if count > 0 and count < 5:
            print(f"      (Only {count} rows - might be incomplete)")
    except Exception as e:
        print(f"❌ {table:35} | ERROR: {e}")

# Check rounds table structure in detail
print("\n" + "=" * 80)
print("📋 SESSIONS TABLE STRUCTURE:")
print("-" * 80)
schema = cursor.execute("PRAGMA table_info(sessions)").fetchall()
for col in schema:
    col_id, name, type_, notnull, default, pk = col
    pk_marker = " [PRIMARY KEY]" if pk else ""
    notnull_marker = " NOT NULL" if notnull else ""
    print(f"   {name:30} {type_:15}{notnull_marker}{pk_marker}")

# Check for team-related tables that might be expected
print("\n" + "=" * 80)
print("🔍 CHECKING FOR EXPECTED TEAM TABLES:")
print("-" * 80)

expected_tables = ['team_lineups', 'gaming_sessions', 'team_assignments']
for table in expected_tables:
    exists = cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='{table}'
    """).fetchone()
    if exists:
        count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"   ✅ {table:30} EXISTS (Rows: {count:,})")
    else:
        print(f"   ❌ {table:30} MISSING")

# Check round_teams structure since it exists
print("\n" + "=" * 80)
print("📋 SESSION_TEAMS TABLE STRUCTURE:")
print("-" * 80)
schema = cursor.execute("PRAGMA table_info(session_teams)").fetchall()
if schema:
    for col in schema:
        col_id, name, type_, notnull, default, pk = col
        pk_marker = " [PRIMARY KEY]" if pk else ""
        notnull_marker = " NOT NULL" if notnull else ""
        print(f"   {name:30} {type_:15}{notnull_marker}{pk_marker}")
else:
    print("   ⚠️ Table exists but has no schema (empty)")

# Sample recent sessions to verify data quality
print("\n" + "=" * 80)
print("📊 RECENT SESSION DATA QUALITY CHECK:")
print("-" * 80)

recent_sessions = cursor.execute("""
    SELECT id, round_date, map_name, round_number, actual_time
    FROM rounds 
    ORDER BY id DESC 
    LIMIT 10
""").fetchall()

print(f"\nShowing last {len(recent_sessions)} sessions:")
for sess in recent_sessions:
    id_, date, map_name, round_num, time = sess
    print(f"   ID:{id_:>6} | {date} | R{round_num} | {time:>6} | {map_name}")

# Check player_comprehensive_stats
print("\n" + "=" * 80)
print("👤 PLAYER DATA CHECK:")
print("-" * 80)

player_count = cursor.execute("""
    SELECT COUNT(DISTINCT player_name) FROM player_comprehensive_stats
""").fetchone()[0]

if player_count > 0:
    print(f"   ✅ {player_count} unique players found")
    
    top_players = cursor.execute("""
        SELECT player_name, COUNT(*) as sessions, SUM(kills) as total_kills
        FROM player_comprehensive_stats
        GROUP BY player_name
        ORDER BY sessions DESC
        LIMIT 5
    """).fetchall()
    
    print("\n   Top 5 players by sessions:")
    for name, sessions, kills in top_players:
        print(f"      {name:30} | Sessions: {sessions:>4} | Kills: {kills:>6}")
else:
    print("   ⚠️ NO PLAYER DATA FOUND!")

# Check weapon data
print("\n" + "=" * 80)
print("🔫 WEAPON DATA CHECK:")
print("-" * 80)

weapon_count = cursor.execute("SELECT COUNT(*) FROM weapon_comprehensive_stats").fetchone()[0]
if weapon_count > 0:
    print(f"   ✅ {weapon_count:,} weapon stat records")
else:
    print("   ⚠️ NO WEAPON DATA FOUND!")

print("\n" + "=" * 80)
print("SUMMARY:")
print("=" * 80)

# Determine if database is properly populated
sessions_count = cursor.execute("SELECT COUNT(*) FROM rounds").fetchone()[0]
players_count = cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats").fetchone()[0]

if sessions_count > 0 and players_count > 0:
    print("✅ Database appears PROPERLY POPULATED")
    print(f"   - {sessions_count:,} round records")
    print(f"   - {players_count:,} player stat records")
    print("   - Core tables functional")
else:
    print("❌ Database appears EMPTY or INCOMPLETE")
    print("   - May need to run bulk_import_stats.py")

# Check for missing critical tables
if not cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='team_lineups'").fetchone():
    print("\n⚠️  MISSING: team_lineups table")
    print("   - This is a NEW feature table")
    print("   - Not critical for basic bot operation")
    print("   - Needed for /team_history command")

conn.close()
