import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

print("=" * 80)
print("CHECKING DATABASE SCHEMA FOR OBJECTIVE FIELDS")
print("=" * 80)
print()

print("player_comprehensive_stats columns:")
cursor.execute('PRAGMA table_info(player_comprehensive_stats)')
comp_cols = [c[1] for c in cursor.fetchall()]
for c in comp_cols:
    print(f"  {c}")

print()
print("player_objective_stats columns:")
cursor.execute('PRAGMA table_info(player_objective_stats)')
obj_cols = [c[1] for c in cursor.fetchall()]
for c in obj_cols:
    print(f"  {c}")

print()
print("=" * 80)
print("CHECKING FOR KEY FIELDS")
print("=" * 80)
print()

key_fields = [
    'times_revived',
    'revives_given',
    'most_useful_kills',
    'useless_kills',
    'denied_playtime',
    'dynamites_planted',
    'kill_assists',
    'kill_steals',
    'bullets_fired',
    'tank_meatshield',
]

print("In player_comprehensive_stats:")
for field in key_fields:
    if field in comp_cols:
        print(f"  ✅ {field}")
    else:
        print(f"  ❌ {field}")

print()
print("In player_objective_stats:")
for field in key_fields:
    if field in obj_cols:
        print(f"  ✅ {field}")
    else:
        print(f"  ❌ {field}")

conn.close()
