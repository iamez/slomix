import sqlite3, os, shutil, datetime, sys

DB = 'bot/etlegacy_production.db'
FILENAME = '2025-10-27-230734-sw_goldrush_te-round-2.txt'
SESSION_ID = 3397
LOCAL_FILE = os.path.join('local_stats', FILENAME)

if not os.path.exists(DB):
    print('DB not found:', DB)
    sys.exit(1)

# Backup
now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
backup = f"{DB}.{now}.bak"
shutil.copy2(DB, backup)
print('Backup created:', backup)

conn = sqlite3.connect(DB)
c = conn.cursor()

# Show counts before
def counts():
    c.execute('SELECT COUNT(*) FROM sessions WHERE id=?', (SESSION_ID,))
    s = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM player_comprehensive_stats WHERE session_id=?', (SESSION_ID,))
    p = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM weapon_comprehensive_stats WHERE session_id=?', (SESSION_ID,))
    w = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM processed_files WHERE filename=?', (FILENAME,))
    pf = c.fetchone()[0]
    return s,p,w,pf

before = counts()
print('Before: sessions, player_rows, weapon_rows, processed_files:', before)

# Delete related rows
c.execute('DELETE FROM weapon_comprehensive_stats WHERE session_id=?', (SESSION_ID,))
c.execute('DELETE FROM player_comprehensive_stats WHERE session_id=?', (SESSION_ID,))
c.execute('DELETE FROM sessions WHERE id=?', (SESSION_ID,))
c.execute('DELETE FROM processed_files WHERE filename=?', (FILENAME,))
conn.commit()

after = counts()
print('After:  sessions, player_rows, weapon_rows, processed_files:', after)

conn.close()

# Now re-import using the bot's process_gamestats_file
print('\nRe-importing file with diagnostics enabled:', LOCAL_FILE)

# Run the previously created run_import_specific.py logic to import
# Import by executing a Python snippet that uses the bot class
import subprocess
res = subprocess.run([sys.executable, os.path.join('tools','run_import_specific.py')], capture_output=True, text=True)
print(res.stdout)
print(res.stderr)

print('Done')
