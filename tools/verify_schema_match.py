import json
import sqlite3
from pathlib import Path

DB = 'bot/etlegacy_production.db'
SCHEMA_JSON = 'bot/schema.json'

if not Path(DB).exists():
    print('DB not found:', DB)
    raise SystemExit(1)

if not Path(SCHEMA_JSON).exists():
    print('Schema JSON not found:', SCHEMA_JSON)
    raise SystemExit(1)

schema = json.loads(Path(SCHEMA_JSON).read_text(encoding='utf-8'))
conn = sqlite3.connect(DB)
c = conn.cursor()

ok = True
for table, cols in schema.items():
    print(f'Checking table: {table}')
    try:
        cur = c.execute(f"PRAGMA table_info('{table}')")
        live_cols = cur.fetchall()
    except Exception as e:
        print('  ERROR reading PRAGMA for', table, e)
        ok = False
        continue

    # Build dicts by column name for comparison
    live_map = {c[1]: c for c in live_cols}
    exported_map = {c['name']: c for c in cols}

    # Check for missing/extra columns
    missing = [n for n in exported_map if n not in live_map]
    extra = [n for n in live_map if n not in exported_map]
    if missing:
        ok = False
        print('  MISSING in live DB:', missing)
    if extra:
        ok = False
        print('  EXTRA in live DB:', extra)

    # For shared columns compare attributes
    for name in set(exported_map.keys()).intersection(live_map.keys()):
        exp = exported_map[name]
        live = live_map[name]
        # live: (cid, name, type, notnull, dflt_value, pk)
        diffs = []
        if exp['type'].upper() != (live[2] or '').upper():
            diffs.append(('type', exp['type'], live[2]))
        if bool(exp.get('notnull')) != bool(live[3]):
            diffs.append(('notnull', exp.get('notnull'), bool(live[3])))
        # Normalize default value representation for simple comparison
        exp_d = exp.get('dflt_value')
        live_d = live[4]
        if exp_d is None and live_d is not None:
            # allow CURRENT_TIMESTAMP and similar; show as diff
            if str(live_d) != 'NULL':
                diffs.append(('dflt', exp_d, live_d))
        elif exp_d is not None and live_d is None:
            diffs.append(('dflt', exp_d, live_d))
        else:
            # compare strings
            if exp_d is not None and str(exp_d).strip().upper() != str(live_d).strip().upper():
                diffs.append(('dflt', exp_d, live_d))
        if bool(exp.get('pk')) != bool(live[5]):
            diffs.append(('pk', exp.get('pk'), bool(live[5])))

        if diffs:
            ok = False
            print(f"  Column differences for {name}:")
            for d in diffs:
                print('   -', d[0], 'exported=', d[1], 'live=', d[2])

if ok:
    print('\nSchema JSON matches live DB schema (no differences found).')
else:
    print('\nSchema differences found; see output above.')

conn.close()
