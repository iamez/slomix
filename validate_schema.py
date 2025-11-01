#!/usr/bin/env python3
"""
Validate Database Schema vs Import Script Requirements
Checks ALL tables that simple_bulk_import.py uses
"""

import sqlite3

# Connect to database
conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

print('\n' + '='*70)
print('🔍 COMPREHENSIVE SCHEMA VALIDATION')
print('='*70)

# ============================================================================
# 1. SESSIONS TABLE
# ============================================================================
print('\n📋 SESSIONS TABLE')
print('-'*70)

cursor.execute('PRAGMA table_info(sessions)')
sessions_cols = {row[1] for row in cursor.fetchall()}

sessions_required = ['session_date', 'map_name', 'round_number', 
                     'time_limit', 'actual_time']
sessions_missing = [c for c in sessions_required if c not in sessions_cols]

if sessions_missing:
    print('❌ MISSING COLUMNS:')
    for c in sessions_missing:
        print(f'   - {c}')
    print('\n   Fix: ALTER TABLE sessions ADD COLUMN <name> <type>')
else:
    print('✅ All required columns present')

# ============================================================================
# 2. PLAYER_COMPREHENSIVE_STATS TABLE
# ============================================================================
print('\n🎮 PLAYER_COMPREHENSIVE_STATS TABLE')
print('-'*70)

cursor.execute('PRAGMA table_info(player_comprehensive_stats)')
player_cols = {row[1] for row in cursor.fetchall()}

# Required columns from simple_bulk_import.py (lines 180-197)
player_required = [
    'session_id', 'session_date', 'map_name', 'round_number',
    'player_guid', 'player_name', 'clean_name', 'team',
    'kills', 'deaths', 'damage_given', 'damage_received',
    'team_damage_given', 'team_damage_received',
    'gibs', 'self_kills', 'team_kills', 'team_gibs', 'headshot_kills',
    'time_played_seconds', 'time_played_minutes',
    'time_dead_minutes', 'time_dead_ratio',
    'xp', 'kd_ratio', 'dpm', 'efficiency',
    'bullets_fired', 'accuracy',
    'kill_assists',
    'objectives_completed', 'objectives_destroyed',
    'objectives_stolen', 'objectives_returned',
    'dynamites_planted', 'dynamites_defused',
    'times_revived', 'revives_given',
    'most_useful_kills', 'useless_kills', 'kill_steals',
    'denied_playtime', 'constructions', 'tank_meatshield',
    'double_kills', 'triple_kills', 'quad_kills',
    'multi_kills', 'mega_kills',
    'killing_spree_best', 'death_spree_worst'
]

player_missing = [c for c in player_required if c not in player_cols]

print(f'Required: {len(player_required)} columns')
print(f'Present: {len(player_required) - len(player_missing)}')
print(f'Missing: {len(player_missing)}')

if player_missing:
    print('\n❌ MISSING COLUMNS:')
    for c in player_missing:
        print(f'   - {c}')
    print('\n   Fix: ALTER TABLE player_comprehensive_stats ADD COLUMN <name> <type>')
else:
    print('✅ All required columns present')

# ============================================================================
# 3. WEAPON_COMPREHENSIVE_STATS TABLE
# ============================================================================
print('\n🔫 WEAPON_COMPREHENSIVE_STATS TABLE')
print('-'*70)

cursor.execute('PRAGMA table_info(weapon_comprehensive_stats)')
weapon_cols_info = cursor.fetchall()
weapon_cols = {row[1]: row for row in weapon_cols_info}

# Required columns from simple_bulk_import.py (lines 220-230)
weapon_required = {
    'session_id': 'INTEGER',
    'session_date': 'TEXT',
    'map_name': 'TEXT', 
    'round_number': 'INTEGER',
    'player_guid': 'TEXT',
    'player_name': 'TEXT',
    'weapon_name': 'TEXT',
    'kills': 'INTEGER',
    'deaths': 'INTEGER',
    'headshots': 'INTEGER',
    'shots': 'INTEGER',
    'hits': 'INTEGER'
}

weapon_missing = []
weapon_constraint_issues = []

for col_name, expected_type in weapon_required.items():
    if col_name not in weapon_cols:
        weapon_missing.append(col_name)
    else:
        # Check if weapon_id or weapon_name have NOT NULL constraints
        if col_name in ['weapon_id', 'weapon_name']:
            col_info = weapon_cols[col_name]
            is_not_null = col_info[3] == 1  # notnull flag
            if is_not_null:
                weapon_constraint_issues.append(
                    f'{col_name} has NOT NULL constraint (import doesn\'t populate it)'
                )

print(f'Required: {len(weapon_required)} columns')
print(f'Present: {len(weapon_required) - len(weapon_missing)}')
print(f'Missing: {len(weapon_missing)}')

if weapon_missing:
    print('\n❌ MISSING COLUMNS:')
    for c in weapon_missing:
        print(f'   - {c} ({weapon_required[c]})')
    print('\n   Fix: ALTER TABLE weapon_comprehensive_stats ADD COLUMN <name> <type>')
else:
    print('✅ All required columns present')

if weapon_constraint_issues:
    print('\n⚠️  CONSTRAINT ISSUES:')
    for issue in weapon_constraint_issues:
        print(f'   - {issue}')
    print('\n   Fix: Recreate table without NOT NULL on weapon_id/weapon_name')

# ============================================================================
# FINAL VERDICT
# ============================================================================
print('\n' + '='*70)
print('� VALIDATION SUMMARY')
print('='*70)

total_issues = len(sessions_missing) + len(player_missing) + len(weapon_missing) + len(weapon_constraint_issues)

if total_issues == 0:
    print('\n✅ DATABASE IS READY FOR IMPORT!')
    print('   All required columns present')
    print('   No constraint issues detected')
    print('\n🚀 Next step: python tools/simple_bulk_import.py')
else:
    print(f'\n❌ FOUND {total_issues} ISSUE(S) - IMPORT WILL FAIL')
    print('\n   Fix these issues before running import!')
    print('   See details above for specific ALTER TABLE commands')
    
print('='*70 + '\n')

conn.close()
conn.close()
