import sqlite3
import json
import sys
from pathlib import Path

DB = 'bot/etlegacy_production.db'
OUT_SQL = 'bot/schema.sql'
OUT_JSON = 'bot/schema.json'

try:
    conn = sqlite3.connect(DB)
    c = conn.cursor()
except Exception as e:
    print('ERROR opening DB', DB, e)
    sys.exit(1)

# Collect CREATE statements (tables, indexes, triggers, views)
c.execute("SELECT type, name, sql FROM sqlite_master WHERE sql NOT NULL ORDER BY type, name")
rows = c.fetchall()

sql_stmts = []
for typ, name, sql in rows:
    # Skip sqlite_sequence and internal objects if present
    if name.startswith('sqlite_'):
        continue
    sql_stmts.append(f"-- {typ} {name}\n{sql.strip()}\n")

Path('bot').mkdir(parents=True, exist_ok=True)
with open(OUT_SQL, 'w', encoding='utf-8') as f:
    f.write('-- Schema export (no data)\n')
    f.write('\n'.join(sql_stmts))

# Build JSON skeleton: tables -> columns
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
tables = [r[0] for r in c.fetchall()]

schema = {}
for t in tables:
    c.execute(f"PRAGMA table_info('{t}')")
    cols = c.fetchall()
    schema[t] = [
        {
            'cid': col[0],
            'name': col[1],
            'type': col[2],
            'notnull': bool(col[3]),
            'dflt_value': col[4],
            'pk': bool(col[5]),
        }
        for col in cols
    ]

with open(OUT_JSON, 'w', encoding='utf-8') as f:
    json.dump(schema, f, indent=2)

print('Wrote', OUT_SQL)
print('Wrote', OUT_JSON)
conn.close()
