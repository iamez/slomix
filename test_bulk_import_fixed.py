"""
Test bulk importer with ONE file to verify all fields are populated correctly
"""
import sqlite3
import sys
from pathlib import Path

# Delete test database if exists
test_db = Path("test_import.db")
if test_db.exists():
    test_db.unlink()
    print("🗑️  Deleted old test database")

# Import ONE file
print("\n📥 Importing ONE test file...")
import subprocess
result = subprocess.run([
    sys.executable, 
    "dev/bulk_import_stats.py",
    "--limit", "1",
    "--db", "test_import.db"
], capture_output=True, text=True)

print(result.stdout)
if result.returncode != 0:
    print("❌ Import failed!")
    print(result.stderr)
    sys.exit(1)

# Check database
print("\n🔍 Checking imported data...")
conn = sqlite3.connect("test_import.db")
cursor = conn.cursor()

# Get player count
cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats")
player_count = cursor.fetchone()[0]
print(f"✅ Players imported: {player_count}")

if player_count == 0:
    print("❌ No players imported!")
    sys.exit(1)

# Get first player and check ALL fields
cursor.execute("SELECT * FROM player_comprehensive_stats LIMIT 1")
row = cursor.fetchone()
cols = [desc[0] for desc in cursor.description]
player = dict(zip(cols, row))

print(f"\n👤 Sample player: {player['player_name']}")
print("="*80)

# Check critical fields that were broken before
checks = [
    ('team_damage_given', 'Should NOT be 0 if player did team damage'),
    ('team_damage_received', 'Should NOT be 0 if player received team damage'),
    ('headshot_kills', 'Should be from objective_stats, not weapon headshots'),
    ('most_useful_kills', 'Should NOT be 0 if player had useful kills'),
    ('bullets_fired', 'Should NOT be 0 for active players'),
    ('time_dead_minutes', 'Should NOT be 0 for players who died'),
    ('constructions', 'Should NOT be 0 for engineers'),
    ('double_kills', 'Should NOT be 0 if player had multikills'),
    ('denied_playtime', 'Should NOT be 0 if player denied playtime'),
    ('tank_meatshield', 'Should NOT be 0 if player tanked damage'),
]

issues = []
ok_fields = []

for field, description in checks:
    value = player.get(field, 'MISSING')
    if value == 'MISSING':
        issues.append(f"❌ {field}: COLUMN MISSING!")
    elif value == 0 or value is None:
        print(f"⚠️  {field}: {value} ({description})")
    else:
        ok_fields.append(f"✅ {field}: {value}")

# Print successes
if ok_fields:
    print("\n" + "="*80)
    print("FIELDS WITH DATA:")
    print("="*80)
    for msg in ok_fields:
        print(msg)

# Print all field values for inspection
print("\n" + "="*80)
print("ALL FIELD VALUES:")
print("="*80)
for col in cols:
    value = player[col]
    if value not in [0, None, '', 'Unknown']:
        print(f"{col:30} = {value}")

if issues:
    print("\n" + "="*80)
    print("CRITICAL ISSUES:")
    print("="*80)
    for issue in issues:
        print(issue)
    sys.exit(1)
else:
    print("\n" + "="*80)
    print("✅ ALL FIELDS PRESENT!")
    print("="*80)
    print("\nNote: Some fields showing 0 is expected if the player didn't perform that action.")
    print("The important thing is that columns exist and non-zero values appear when appropriate.")

conn.close()
