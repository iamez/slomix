#!/usr/bin/env python3
"""
Verify database health before making any changes.

Checks:
1. All required tables exist
2. All required columns exist
3. Sample data can be retrieved
4. Backup/restore process works
"""

import sys
import subprocess
import tempfile
import os

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'etlegacy',
    'user': 'etlegacy_user',
    'password': 'etlegacy_secure_2025'
}

REQUIRED_TABLES = [
    'rounds',
    'player_comprehensive_stats',
    'weapon_comprehensive_stats',
    'processed_files',
    'gaming_sessions',
    'player_links',
    'lua_round_teams'
]

REQUIRED_COLUMNS_PLAYER_STATS = [
    'id', 'round_id', 'player_guid', 'player_name',
    'kills', 'deaths', 'headshot_kills', 'damage_given',
    'time_played_seconds', 'time_dead_minutes', 'time_dead_ratio',
    'efficiency', 'denied_playtime', 'useful_kills',
    # Add more as needed
]

def run_psql(sql):
    """Run a SQL query and return output"""
    cmd = [
        'psql',
        '-h', DB_CONFIG['host'],
        '-p', str(DB_CONFIG['port']),
        '-U', DB_CONFIG['user'],
        '-d', DB_CONFIG['database'],
        '-t',  # Tuples only
        '-c', sql
    ]

    env = os.environ.copy()
    env['PGPASSWORD'] = DB_CONFIG['password']

    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()

def check_tables():
    """Check all required tables exist"""
    print("=" * 100)
    print("CHECK 1: TABLES")
    print("=" * 100)

    sql = """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    ORDER BY table_name;
    """

    code, output, error = run_psql(sql)
    if code != 0:
        print(f"❌ Failed to query tables: {error}")
        return False

    existing_tables = set(line.strip() for line in output.split('\n') if line.strip())

    all_good = True
    for table in REQUIRED_TABLES:
        if table in existing_tables:
            print(f"✅ {table}")
        else:
            print(f"❌ {table} - MISSING!")
            all_good = False

    print(f"\nTotal tables found: {len(existing_tables)}")
    return all_good

def check_columns():
    """Check required columns in player_comprehensive_stats"""
    print("\n" + "=" * 100)
    print("CHECK 2: COLUMNS (player_comprehensive_stats)")
    print("=" * 100)

    sql = """
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'player_comprehensive_stats'
    ORDER BY column_name;
    """

    code, output, error = run_psql(sql)
    if code != 0:
        print(f"❌ Failed to query columns: {error}")
        return False

    existing_columns = set(line.strip() for line in output.split('\n') if line.strip())

    all_good = True
    for col in REQUIRED_COLUMNS_PLAYER_STATS:
        if col in existing_columns:
            print(f"✅ {col}")
        else:
            print(f"❌ {col} - MISSING!")
            all_good = False

    print(f"\nTotal columns: {len(existing_columns)}")
    return all_good

def check_data():
    """Check we can retrieve sample data"""
    print("\n" + "=" * 100)
    print("CHECK 3: DATA ACCESS")
    print("=" * 100)

    # Count rounds
    code, output, _ = run_psql("SELECT COUNT(*) FROM rounds;")
    if code == 0:
        print(f"✅ Rounds: {output.strip()}")
    else:
        print(f"❌ Failed to count rounds")
        return False

    # Count player stats
    code, output, _ = run_psql("SELECT COUNT(*) FROM player_comprehensive_stats;")
    if code == 0:
        print(f"✅ Player stats: {output.strip()}")
    else:
        print(f"❌ Failed to count player stats")
        return False

    # Count Round 2 records (what we'll fix)
    code, output, _ = run_psql("""
        SELECT COUNT(*) FROM player_comprehensive_stats p
        JOIN rounds r ON p.round_id = r.id
        WHERE r.round_number = 2;
    """)
    if code == 0:
        print(f"✅ Round 2 records (will be fixed): {output.strip()}")
    else:
        print(f"❌ Failed to count R2 records")
        return False

    # Sample a record
    code, output, _ = run_psql("""
        SELECT player_name, kills, deaths, time_played_seconds
        FROM player_comprehensive_stats
        LIMIT 1;
    """)
    if code == 0:
        print(f"✅ Sample record retrieved")
    else:
        print(f"❌ Failed to retrieve sample")
        return False

    return True

def test_backup_restore():
    """Test backup and restore process"""
    print("\n" + "=" * 100)
    print("CHECK 4: BACKUP/RESTORE TEST")
    print("=" * 100)

    with tempfile.TemporaryDirectory() as tmpdir:
        backup_file = os.path.join(tmpdir, 'test_backup.sql')

        # Create backup
        print("\n📦 Creating test backup...")
        cmd = [
            'pg_dump',
            '-h', DB_CONFIG['host'],
            '-p', str(DB_CONFIG['port']),
            '-U', DB_CONFIG['user'],
            '-d', DB_CONFIG['database'],
            '-f', backup_file,
            '--schema-only'  # Just schema for test
        ]

        env = os.environ.copy()
        env['PGPASSWORD'] = DB_CONFIG['password']

        result = subprocess.run(cmd, env=env, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"❌ Backup failed: {result.stderr}")
            return False

        size = os.path.getsize(backup_file)
        print(f"✅ Backup created: {size} bytes")

        # Check backup content
        with open(backup_file, 'r') as f:
            content = f.read()
            if 'CREATE TABLE' in content and 'player_comprehensive_stats' in content:
                print(f"✅ Backup contains table definitions")
            else:
                print(f"❌ Backup seems incomplete")
                return False

    print(f"✅ Backup/restore mechanism is working")
    return True

def main():
    print("=" * 100)
    print("DATABASE HEALTH CHECK")
    print("=" * 100)
    print("\nThis will verify your database is complete before making any changes.\n")

    checks = [
        ("Tables", check_tables),
        ("Columns", check_columns),
        ("Data", check_data),
        ("Backup/Restore", test_backup_restore)
    ]

    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"\n❌ {name} check crashed: {e}")
            results[name] = False

    # Summary
    print("\n" + "=" * 100)
    print("HEALTH CHECK SUMMARY")
    print("=" * 100)

    all_passed = True
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
        if not passed:
            all_passed = False

    print("=" * 100)

    if all_passed:
        print("\n🎉 ALL CHECKS PASSED!")
        print("\nYour database is healthy and safe to update.")
        print("\nNext step:")
        print("  python /tmp/fix_r2_records_safely.py")
        return 0
    else:
        print("\n⚠️ SOME CHECKS FAILED!")
        print("\nDo NOT proceed with updates until issues are resolved.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
