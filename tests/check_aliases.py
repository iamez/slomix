import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / 'bot' / 'etlegacy_production.db'
print('DB Path:', DB)
if not DB.exists():
    print('ERROR: DB not found at', DB)
    raise SystemExit(1)

con = sqlite3.connect(str(DB))
con.row_factory = sqlite3.Row
cur = con.cursor()

print('\nPRAGMA table_info(player_aliases):')
for r in cur.execute("PRAGMA table_info(player_aliases)"):
    print(tuple(r))

print('\nPRAGMA table_info(player_comprehensive_stats):')
for r in cur.execute("PRAGMA table_info(player_comprehensive_stats)"):
    print(tuple(r))

# Try the query that failed in the bot logs
sample_guids = ['E587CA5F', 'EDBB5DA9']
for guid in sample_guids:
    print(f"\nQuerying aliases for GUID={guid} (param primary_name='Ciril'/'SuperBoyy')")
    try:
        for primary in ('Ciril', 'SuperBoyy'):
            q = '''
            SELECT alias
            FROM player_aliases
            WHERE guid = ? AND LOWER(alias) != LOWER(?)
            ORDER BY last_seen DESC, times_seen DESC
            LIMIT 3
            '''
            rows = list(cur.execute(q, (guid, primary)))
            print(f' params=({guid!r},{primary!r}) rows={len(rows)}')
            for r in rows:
                print('  ->', tuple(r))
    except Exception as e:
        print(' Query failed:', e)

con.close()
print('\nDone')
