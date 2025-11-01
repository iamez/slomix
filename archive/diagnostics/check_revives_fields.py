import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# Check schema of both tables
print("=" * 80)
print("CHECKING REVIVES FIELDS")
print("=" * 80)
print()

print("player_comprehensive_stats columns:")
cursor.execute('PRAGMA table_info(player_comprehensive_stats)')
comp_cols = cursor.fetchall()
for col in comp_cols:
    if 'revive' in col[1].lower():
        print(f"  ✓ {col[1]} (type: {col[2]})")

print()
print("player_objective_stats columns:")
cursor.execute('PRAGMA table_info(player_objective_stats)')
obj_cols = cursor.fetchall()
for col in obj_cols:
    if 'revive' in col[1].lower():
        print(f"  ✓ {col[1]} (type: {col[2]})")

print()
print("=" * 80)
print("CHECKING DATA IN REVIVES FIELDS")
print("=" * 80)
print()

# Check comprehensive stats
cursor.execute('''
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN revives > 0 THEN 1 END) as have_revives,
        SUM(revives) as total_revives,
        MAX(revives) as max_revives
    FROM player_comprehensive_stats
''')
row = cursor.fetchone()
print(f"player_comprehensive_stats.revives:")
print(f"  Total players: {row[0]}")
print(f"  Players with revives > 0: {row[1]} ({100*row[1]/row[0]:.1f}%)")
print(f"  Total revives: {row[2]}")
print(f"  Max revives: {row[3]}")

print()

# Check objective stats - revives
cursor.execute('''
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN revives > 0 THEN 1 END) as have_revives,
        SUM(revives) as total_revives,
        MAX(revives) as max_revives
    FROM player_objective_stats
''')
row = cursor.fetchone()
print(f"player_objective_stats.revives:")
print(f"  Total players: {row[0]}")
print(f"  Players with revives > 0: {row[1]} ({100*row[1]/row[0]:.1f}%)")
print(f"  Total revives: {row[2]}")
print(f"  Max revives: {row[3]}")

print()

# Check objective stats - times_revived
cursor.execute('''
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN times_revived > 0 THEN 1 END) as have_times_revived,
        SUM(times_revived) as total_times_revived,
        MAX(times_revived) as max_times_revived
    FROM player_objective_stats
''')
row = cursor.fetchone()
print(f"player_objective_stats.times_revived:")
print(f"  Total players: {row[0]}")
print(f"  Players with times_revived > 0: {row[1]} ({100*row[1]/row[0]:.1f}%)")
print(f"  Total times_revived: {row[2]}")
print(f"  Max times_revived: {row[3]}")

# Show sample of players with times_revived > 0
print()
print("=" * 80)
print("SAMPLE PLAYERS WITH TIMES_REVIVED > 0")
print("=" * 80)
cursor.execute('''
    SELECT player_name, times_revived
    FROM player_objective_stats
    WHERE times_revived > 0
    ORDER BY times_revived DESC
    LIMIT 10
''')
rows = cursor.fetchall()
if rows:
    print()
    for row in rows:
        print(f"  {row[0]:<30} times_revived = {row[1]}")
else:
    print("  No players found with times_revived > 0")

conn.close()
