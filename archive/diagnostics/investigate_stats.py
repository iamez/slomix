#!/usr/bin/env python3
"""
Investigate database stats in detail
"""
import sqlite3


def investigate_database():
    conn = sqlite3.connect('etlegacy_production.db')
    cursor = conn.cursor()

    print("=" * 80)
    print("SESSIONS TABLE ANALYSIS")
    print("=" * 80)

    # Get sessions structure
    cursor.execute('PRAGMA table_info(sessions)')
    cols = cursor.fetchall()
    print("\n📋 Column Structure:")
    for col in cols:
        print(f"  {col[1]:<20} {col[2]:<12} NOT NULL:{col[3]}  DEFAULT:{col[4]}")

    # Get sessions sample data
    cursor.execute('SELECT * FROM sessions LIMIT 5')
    rows = cursor.fetchall()
    col_names = [col[1] for col in cols]

    print(f"\n📊 Sample Data ({len(rows)} rows):")
    for i, row in enumerate(rows, 1):
        print(f"\n  Session {i}:")
        for j, val in enumerate(row):
            print(f"    {col_names[j]:<20} = {val}")

    # Get count
    cursor.execute('SELECT COUNT(*) FROM sessions')
    count = cursor.fetchone()[0]
    print(f"\n  Total sessions: {count}")

    print("\n" + "=" * 80)
    print("PLAYER_STATS TABLE ANALYSIS")
    print("=" * 80)

    # Get player_stats structure
    cursor.execute('PRAGMA table_info(player_stats)')
    cols = cursor.fetchall()
    print("\n📋 Column Structure:")
    for col in cols:
        print(f"  {col[1]:<20} {col[2]:<12} NOT NULL:{col[3]}  DEFAULT:{col[4]}")

    # Get count
    cursor.execute('SELECT COUNT(*) FROM player_stats')
    count = cursor.fetchone()[0]
    print(f"\n  Total player_stats rows: {count}")

    if count > 0:
        # Get sample data
        cursor.execute('SELECT * FROM player_stats LIMIT 3')
        rows = cursor.fetchall()
        col_names = [col[1] for col in cols]

        print(f"\n📊 Sample Data ({len(rows)} rows):")
        for i, row in enumerate(rows, 1):
            print(f"\n  Record {i}:")
            for j, val in enumerate(row):
                # Truncate long text fields
                if isinstance(val, str) and len(val) > 100:
                    val = val[:100] + "..."
                print(f"    {col_names[j]:<20} = {val}")

    print("\n" + "=" * 80)
    print("PLAYER_COMPREHENSIVE_STATS TABLE ANALYSIS")
    print("=" * 80)

    # Get player_comprehensive_stats structure
    cursor.execute('PRAGMA table_info(player_comprehensive_stats)')
    cols = cursor.fetchall()
    print("\n📋 Column Structure:")
    for col in cols:
        print(f"  {col[1]:<20} {col[2]:<12} NOT NULL:{col[3]}  DEFAULT:{col[4]}")

    # Get sample with aggregates
    cursor.execute(
        '''
        SELECT COUNT(*) as total_records,
               COUNT(DISTINCT session_id) as unique_sessions,
               COUNT(DISTINCT player_guid) as unique_players,
               MIN(created_at) as earliest_record,
               MAX(created_at) as latest_record
        FROM player_comprehensive_stats
    '''
    )
    row = cursor.fetchone()
    print(f"\n📊 Statistics:")
    print(f"    Total records:     {row[0]}")
    print(f"    Unique sessions:   {row[1]}")
    print(f"    Unique players:    {row[2]}")
    print(f"    Earliest record:   {row[3]}")
    print(f"    Latest record:     {row[4]}")

    # Get sample data
    cursor.execute('SELECT * FROM player_comprehensive_stats LIMIT 3')
    rows = cursor.fetchall()
    col_names = [col[1] for col in cols]

    print(f"\n📊 Sample Data ({len(rows)} rows):")
    for i, row in enumerate(rows, 1):
        print(f"\n  Record {i}:")
        for j, val in enumerate(row):
            print(f"    {col_names[j]:<20} = {val}")

    print("\n" + "=" * 80)
    print("WEAPON_COMPREHENSIVE_STATS TABLE ANALYSIS")
    print("=" * 80)

    # Get weapon stats structure
    cursor.execute('PRAGMA table_info(weapon_comprehensive_stats)')
    cols = cursor.fetchall()
    print("\n📋 Column Structure:")
    for col in cols:
        print(f"  {col[1]:<20} {col[2]:<12} NOT NULL:{col[3]}  DEFAULT:{col[4]}")

    # Get weapon sample
    cursor.execute(
        '''
        SELECT weapon_name, COUNT(*) as usage_count, SUM(kills) as total_kills
        FROM weapon_comprehensive_stats
        GROUP BY weapon_name
        ORDER BY total_kills DESC
        LIMIT 10
    '''
    )
    rows = cursor.fetchall()

    print(f"\n📊 Top 10 Weapons by Kills:")
    for weapon, usage, kills in rows:
        print(f"    {weapon:<25} Usage: {usage:>5}  Kills: {kills:>6}")

    # Check for awards/achievements data
    print("\n" + "=" * 80)
    print("CHECKING FOR OBJECTIVE/AWARDS DATA")
    print("=" * 80)

    # Search all tables for objective-related columns
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cursor.fetchall()]

    objective_keywords = [
        'award',
        'achievement',
        'objective',
        'revive',
        'build',
        'dynamite',
        'plant',
        'defuse',
        'medic',
        'engineer',
    ]

    for table in tables:
        cursor.execute(f'PRAGMA table_info({table})')
        cols = cursor.fetchall()
        matching_cols = [
            col for col in cols if any(kw in col[1].lower() for kw in objective_keywords)
        ]

        if matching_cols:
            print(f"\n📌 Table: {table}")
            for col in matching_cols:
                print(f"    ✓ {col[1]} ({col[2]})")

                # Try to get sample data
                try:
                    cursor.execute(
                        f'SELECT {
                            col[1]} FROM {table} WHERE {
                            col[1]} IS NOT NULL LIMIT 3'
                    )
                    samples = cursor.fetchall()
                    if samples:
                        print(f"      Sample values: {[s[0] for s in samples]}")
                except BaseException:
                    pass

    conn.close()


if __name__ == '__main__':
    investigate_database()
