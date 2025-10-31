#!/usr/bin/env python3
"""
DB Dump: prints schema and sample rows for each table in a SQLite DB.
Usage: python dump_db.py /path/to/db
"""
import sqlite3
import sys
import os
import json

def dump_db(db_path):
    if not os.path.exists(db_path):
        print(f"ERROR: DB not found: {db_path}")
        return 2
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("DB PATH:", os.path.abspath(db_path))
    print()
    # List tables and views
    cur.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view') ORDER BY name")
    objs = cur.fetchall()
    if not objs:
        print("No tables or views found")
        return 0
    print(f"Found {len(objs)} objects (tables/views):")
    for name, typ in objs:
        print(f" - {name} ({typ})")
    print('\n' + '='*80 + '\n')

    for name, typ in objs:
        print(f"TABLE/VIEW: {name} ({typ})")
        print('-'*60)
        try:
            cur.execute(f"PRAGMA table_info('{name}')")
            cols = cur.fetchall()
            if cols:
                print(f"Columns ({len(cols)}):")
                for c in cols:
                    cid, colname, coltype, notnull, dflt, pk = c
                    print(f"  - {colname} ({coltype}) notnull={notnull} pk={pk} dflt={dflt}")
            else:
                print("  (no PRAGMA table_info results)")
        except Exception as e:
            print(f"  PRAGMA failed: {e}")

        # Row count
        try:
            cur.execute(f"SELECT COUNT(*) FROM '{name}'")
            count = cur.fetchone()[0]
            print(f"Row count: {count}")
        except Exception as e:
            print(f"Row count query failed: {e}")

        # Sample rows
        try:
            cur.execute(f"SELECT * FROM '{name}' LIMIT 10")
            rows = cur.fetchall()
            if rows:
                print(f"Sample rows (up to 10):")
                for r in rows:
                    # Convert to regular dict for pretty printing
                    d = {k: (v if not isinstance(v, bytes) else f'<bytes {len(v)}>') for k, v in dict(r).items()}
                    print(json.dumps(d, default=str, ensure_ascii=False))
            else:
                print("No rows to show")
        except Exception as e:
            print(f"Sample rows query failed: {e}")

        print('\n' + '-'*80 + '\n')

    conn.close()
    return 0

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'bot/etlegacy_production.db'
    sys.exit(dump_db(path))
