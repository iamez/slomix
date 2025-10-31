import os
import sys
import shutil
import datetime
import sqlite3
import subprocess

DB = 'bot/etlegacy_production.db'
LOCAL_DIR = 'local_stats'
REIMPORT_SCRIPT = os.path.join('tools', 'reimport_worker.py')

if not os.path.exists(DB):
    print('DB not found:', DB)
    sys.exit(1)

# Dates from argv or default
dates = sys.argv[1:] if len(sys.argv) > 1 else ['2025-10-28', '2025-10-30']

# 1) Backup DB
now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
backup = f"{DB}.{now}.bak"
shutil.copy2(DB, backup)
print('Backup created:', backup)

conn = sqlite3.connect(DB)
c = conn.cursor()

# Collect local files matching dates
files_to_import = []
for d in dates:
    # Look in processed_files for entries starting with date
    c.execute("SELECT filename FROM processed_files WHERE filename LIKE ? ORDER BY filename", (d + '%',))
    rows = c.fetchall()
    # Prefer local_stats file if present, else use processed_files filename
    for (fname,) in rows:
        local_path = os.path.join(LOCAL_DIR, fname)
        if os.path.exists(local_path):
            files_to_import.append(fname)
        else:
            # If local not present, try to find any local_stats file that starts with date
            if os.path.exists(LOCAL_DIR):
                candidates = [f for f in os.listdir(LOCAL_DIR) if f.startswith(d)]
                if candidates:
                    files_to_import.extend(candidates)

# Deduplicate while preserving order
seen = set()
files = []
for f in files_to_import:
    if f not in seen:
        seen.add(f)
        files.append(f)

if not files:
    print('No local files found for dates:', dates)
    conn.close()
    sys.exit(0)

print('Will re-import', len(files), 'files for dates:', dates)
for f in files:
    print(' -', f)

# 2) Remove processed_files entries so the importer will run
for f in files:
    c.execute('DELETE FROM processed_files WHERE filename = ?', (f,))
conn.commit()
print('Cleared processed_files entries for these files')

# 3) Run reimport_worker for each file
failures = []
for f in files:
    print('\n--- Re-importing', f, '---')
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    try:
        proc = subprocess.run([sys.executable, REIMPORT_SCRIPT, f], capture_output=True, env=env)
        stdout = proc.stdout.decode('utf-8', errors='replace') if proc.stdout is not None else ''
        stderr = proc.stderr.decode('utf-8', errors='replace') if proc.stderr is not None else ''
        out = stdout + '\n' + stderr
    except Exception as e:
        out = f'Exception when running reimport worker: {e}'

    print(out)
    if "'success': False" in out or 'Failed to insert weapon stats' in out or 'NOT NULL constraint failed' in out or out.startswith('Exception'):
        failures.append({'file': f, 'output': out})

conn.close()

print('\n==== REIMPORT SUMMARY ====')
print('Total files attempted:', len(files))
print('Failures:', len(failures))
for fa in failures:
    print('FAILED:', fa['file'])
    print(fa['output'])

print('\nDone')
