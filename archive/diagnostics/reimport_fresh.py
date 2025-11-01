#!/usr/bin/env python3
"""
FRESH DATABASE RE-IMPORT SCRIPT
================================
Automates the database recreation and re-import process
"""

import os
import sys
from pathlib import Path
import subprocess

print('\n' + '='*80)
print('FRESH DATABASE RE-IMPORT - All Bugs Fixed')
print('='*80)

# Check prerequisites
print('\n📋 Prerequisites Check:')

db_path = Path('etlegacy_production.db')
migrate_script = Path('migrate_database.py')
import_script = Path('dev/bulk_import_stats.py')

if not migrate_script.exists():
    print(f'❌ {migrate_script} not found!')
    sys.exit(1)
print(f'✅ Found: {migrate_script}')

if not import_script.exists():
    print(f'❌ {import_script} not found!')
    sys.exit(1)
print(f'✅ Found: {import_script}')

# Show current database status
if db_path.exists():
    size_mb = db_path.stat().st_size / (1024 * 1024)
    print(f'\n⚠️  Current database: {db_path} ({size_mb:.1f} MB)')
    
    response = input('\n❓ Delete current database and start fresh? (yes/no): ')
    if response.lower() not in ['yes', 'y']:
        print('Aborted.')
        sys.exit(0)
else:
    print(f'\n✅ No existing database found')

print('\n' + '='*80)
print('STEP 1: Delete Current Database')
print('='*80)

if db_path.exists():
    try:
        db_path.unlink()
        print(f'✅ Deleted: {db_path}')
    except Exception as e:
        print(f'❌ Error deleting database: {e}')
        sys.exit(1)

print('\n' + '='*80)
print('STEP 2: Create Fresh Database')
print('='*80)

print(f'\nRunning: python {migrate_script}')
result = subprocess.run(['python', str(migrate_script)], capture_output=True, text=True)

if result.returncode != 0:
    print('❌ Database creation failed!')
    print(result.stderr)
    sys.exit(1)

print(result.stdout)
print('✅ Fresh database created successfully!')

# Verify database was created
if not db_path.exists():
    print(f'❌ Database {db_path} was not created!')
    sys.exit(1)

print('\n' + '='*80)
print('STEP 3: Import Stats Files')
print('='*80)

print('\nOptions:')
print('  1. Import 2025 only (fast, for testing)')
print('  2. Import all years (complete, takes longer)')

choice = input('\nChoose option (1/2): ')

if choice == '1':
    cmd = ['python', str(import_script), '--year', '2025']
    print(f'\nRunning: python {import_script} --year 2025')
elif choice == '2':
    cmd = ['python', str(import_script)]
    print(f'\nRunning: python {import_script}')
else:
    print('Invalid choice. Defaulting to 2025 only.')
    cmd = ['python', str(import_script), '--year', '2025']

print('\n⏳ This may take several minutes...\n')

result = subprocess.run(cmd, text=True)

if result.returncode != 0:
    print('\n❌ Import failed!')
    sys.exit(1)

print('\n' + '='*80)
print('STEP 4: Verify Fixes')
print('='*80)

print('\nVerifying olz in erdenberg rounds...')

verify_script = Path('check_erdenberg_oct2.py')
if verify_script.exists():
    subprocess.run(['python', str(verify_script)])
else:
    print('⚠️  Verification script not found, skipping...')

print('\n' + '='*80)
print('✅ RE-IMPORT COMPLETE!')
print('='*80)

print('\n📊 Summary of fixes applied:')
print('   • Parser now accepts players with 1+ weapons (was 6+)')
print('   • Multiple plays of same map allowed')
print('   • Each file creates unique session')
print('   • olz should now appear in both erdenberg rounds')
print('   • 2 escape entries for October 2 (was 1)')

print('\n💡 Next steps:')
print('   • Test bot commands: python bot/ultimate_bot.py')
print('   • Check stats: !last_session')
print('   • Verify all data looks correct')

print('\n' + '='*80)
print()
