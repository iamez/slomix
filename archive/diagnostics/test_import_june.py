#!/usr/bin/env python3
"""Test import of June 2024 files"""

from pathlib import Path

from dev.bulk_import_stats import BulkStatsImporter

# Create importer
importer = BulkStatsImporter('etlegacy_production.db')

# Find June 2024 files (skip broken March files)
local_stats = Path('local_stats')
files = sorted([f for f in local_stats.glob('*.txt') if f.name.startswith('2024-06')])

print(f'Found {len(files)} files from June 2024')
print(f'Testing import on first 10 files...\n')

success_count = 0
for i, f in enumerate(files[:10], 1):
    print(f'{i}. {f.name}... ', end='', flush=True)
    success, msg = importer.process_single_file(f)
    if success:
        success_count += 1
        print(f'✅ {msg}')
    else:
        print(f'❌ {msg}')

print(f'\n✅ Successfully imported {success_count}/10 files')
print(f'\nDatabase stats:')
print(f'  Sessions created: {importer.stats["sessions_created"]}')
print(f'  Players inserted: {importer.stats["players_inserted"]}')
print(f'  Weapons inserted: {importer.stats["weapons_inserted"]}')
