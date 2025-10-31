import sys
from pathlib import Path

from simple_bulk_import import SimpleBulkImporter

sys.path.insert(0, 'tools')

imp = SimpleBulkImporter()
file = Path('local_stats/2025-10-02-211808-etl_adlernest-round-1.txt')
imp.process_file(file)

print(f'Processed: {imp.processed}')
print(f'Failed: {imp.failed}')

if imp.failed_files:
    for fpath, error in imp.failed_files:
        print(f'Error: {error}')
