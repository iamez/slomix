import os
import sqlite3
import shutil
import datetime
import subprocess
import sys

DB = 'bot/etlegacy_production.db'
LOCAL_DIR = 'local_stats'
REIMPORT_SCRIPT = os.path.join('tools', 'reimport_worker.py')

if not os.path.exists(DB):
    print('DB not found:', DB)
    sys.exit(1)

# 1) Backup DB
now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
backup = f"{DB}.{now}.bak"
shutil.copy2(DB, backup)
print('Backup created:', backup)

conn = sqlite3.connect(DB)
c = conn.cursor()

# 2) Find sessions with 0 weapon rows
q = '''
SELECT s.id, s.session_date
FROM sessions s
LEFT JOIN weapon_comprehensive_stats w ON w.session_id = s.id
GROUP BY s.id
HAVING COUNT(w.session_id) = 0
ORDER BY s.id DESC
'''
rows = c.execute(q).fetchall()
print(f'Found {len(rows)} sessions with 0 weapon rows')

# Map sessions -> filenames
sessions = []  # list of dicts: {id, session_date, filename}
for sid, sdate in rows:
    prefix = sdate.replace(' ', '-')[:15]  # YYYY-MM-DD-HHMMSS slice
    # Look in processed_files
    cur = conn.cursor()
    cur.execute(
        "SELECT filename FROM processed_files WHERE filename LIKE ?",
        (prefix + '%',),
    )
    r = cur.fetchone()
    if r:
        fname = r[0]
    else:
        # fallback to local_stats file starting with prefix
        if os.path.exists(LOCAL_DIR):
            candidates = [
                f
                for f in os.listdir(LOCAL_DIR)
                if f.startswith(prefix)
            ]
        else:
            candidates = []
        fname = candidates[0] if candidates else None
    sessions.append({'id': sid, 'session_date': sdate, 'filename': fname})

# Show mapping summary
for s in sessions:
    print(s)

# Confirm with user? we'll proceed

# 3) Delete those sessions and player rows, and 4) clear processed_files
ids = [s['id'] for s in sessions]
filenames = [s['filename'] for s in sessions if s['filename']]

if ids:
    print(
        'Deleting sessions, player rows, and weapon rows for',
        len(ids),
        'sessions',
    )
    # Delete weapon rows
    c.executemany(
        'DELETE FROM weapon_comprehensive_stats WHERE session_id=?',
        [(i,) for i in ids],
    )
    # Delete player rows
    c.executemany(
        'DELETE FROM player_comprehensive_stats WHERE session_id=?',
        [(i,) for i in ids],
    )
    # Delete sessions
    c.executemany(
        'DELETE FROM sessions WHERE id=?',
        [(i,) for i in ids],
    )
    # Delete processed_files entries for filenames
    c.executemany(
        'DELETE FROM processed_files WHERE filename=?',
        [(fn,) for fn in filenames],
    )
    conn.commit()
    print('Deleted rows and cleared processed_files')
else:
    print('No sessions to delete')

# 5) Re-import files with diagnostic logging
failures = []
for fn in filenames:
    if not fn:
        failures.append(
            {
                'file': None,
                'error': 'No filename found for session',
            }
        )
        continue
    print('\n--- Re-importing', fn, '---')
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    # Call worker script. Use bytes output and decode explicitly
    # to avoid platform encoding issues when reading subprocess pipes
    try:
        proc = subprocess.run(
            [
                sys.executable,
                REIMPORT_SCRIPT,
                fn,
            ],
            capture_output=True,
            env=env,
        )
        if proc.stdout is not None:
            stdout = proc.stdout.decode('utf-8', errors='replace')
        else:
            stdout = ''
        if proc.stderr is not None:
            stderr = proc.stderr.decode('utf-8', errors='replace')
        else:
            stderr = ''
        out = stdout + '\n' + stderr
    except Exception as e:
        out = f'Exception when running reimport worker: {e}'
    print(out)
    # Look for failure indicators
    failure_cond = (
        'Failed to insert weapon stats' in out
        or 'NOT NULL constraint failed' in out
        or "'success': False" in out
        or out.startswith('Exception')
    )
    if failure_cond:
        failures.append({'file': fn, 'output': out})

conn.close()

# 6) Report failures
print('\n==== REIMPORT FAILURE REPORT ====')
if not failures:
    print('None — all re-imports succeeded (no failures captured)')
else:
    for f in failures:
        print('FAILED:', f['file'])
        print(f.get('output', '(no output)'))

print('\nBulk re-import complete')
