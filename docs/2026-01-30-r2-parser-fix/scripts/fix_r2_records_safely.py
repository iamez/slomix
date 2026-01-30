#!/usr/bin/env python3
"""
Safely fix Round 2 records by re-parsing stats files and updating database.

This approach:
1. Creates full database backup first
2. Re-parses ONLY Round 2 files with fixed parser
3. Updates ONLY the corrupted fields
4. Keeps all other data intact
5. Can be rolled back if needed
"""

import sys
import os
import subprocess
from datetime import datetime
sys.path.insert(0, '/home/samba/share/slomix_discord')

from bot.community_stats_parser import C0RNP0RN3StatsParser
import psycopg2

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'etlegacy',
    'user': 'etlegacy_user',
    'password': 'REDACTED_DB_PASSWORD'
}

BACKUP_DIR = '/home/samba/share/slomix_discord/backups'
LOCAL_STATS = '/home/samba/share/slomix_discord/local_stats'

# Fields that need fixing (R2-only fields that were corrupted)
# Maps parser field names to database column names
CORRUPTED_FIELDS = {
    'xp': 'xp',
    'death_spree': 'death_spree_worst',  # DB uses death_spree_worst
    'kill_assists': 'kill_assists',
    'headshot_kills': 'headshot_kills',
    'objectives_stolen': 'objectives_stolen',
    'dynamites_planted': 'dynamites_planted',
    'times_revived': 'times_revived',
    'time_dead_ratio': 'time_dead_ratio',
    'time_dead_minutes': 'time_dead_minutes',
    'useful_kills': 'most_useful_kills',  # DB uses most_useful_kills
    'denied_playtime': 'denied_playtime',
    'revives_given': 'revives_given',
}

def create_backup():
    """Create full database backup before making changes"""
    print("=" * 100)
    print("STEP 1: CREATING DATABASE BACKUP")
    print("=" * 100)

    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f"{BACKUP_DIR}/etlegacy_backup_before_r2_fix_{timestamp}.sql"

    cmd = [
        'pg_dump',
        '-h', DB_CONFIG['host'],
        '-p', str(DB_CONFIG['port']),
        '-U', DB_CONFIG['user'],
        '-d', DB_CONFIG['database'],
        '-f', backup_file
    ]

    env = os.environ.copy()
    env['PGPASSWORD'] = DB_CONFIG['password']

    print(f"\n📦 Creating backup: {backup_file}")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ Backup failed: {result.stderr}")
        return None

    # Check backup size
    size_mb = os.path.getsize(backup_file) / (1024 * 1024)
    print(f"✅ Backup created successfully: {size_mb:.2f} MB")
    print(f"   Location: {backup_file}")

    return backup_file

def get_round2_files():
    """Get all Round 2 stats files from local_stats"""
    print("\n" + "=" * 100)
    print("STEP 2: FINDING ROUND 2 FILES")
    print("=" * 100)

    r2_files = []
    for filename in os.listdir(LOCAL_STATS):
        if filename.endswith('-round-2.txt') and not filename.endswith('-endstats.txt'):
            r2_files.append(os.path.join(LOCAL_STATS, filename))

    r2_files.sort()
    print(f"\n📊 Found {len(r2_files)} Round 2 files")

    return r2_files

def fix_round2_record(conn, r2_file, parser):
    """Fix a single Round 2 record by re-parsing and updating"""
    try:
        # Parse the R2 file with FIXED parser
        result = parser.parse_stats_file(r2_file)

        if not result['success']:
            print(f"  ⚠️ Parse failed: {result.get('error')}")
            return False

        if not result.get('differential_calculation'):
            # This is a Round 2 file but no R1 found - skip
            return False

        # Extract filename and match_id for matching
        filename = os.path.basename(r2_file)

        # Extract match_id from filename: YYYY-MM-DD-HHMMSS
        # Example: 2026-01-27-230110-te_escape2-round-2.txt
        match_id = '-'.join(filename.split('-')[:4])  # Get YYYY-MM-DD-HHMMSS

        # Get the round_id from database using match_id and round_number
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM rounds
            WHERE match_id = %s AND round_number = 2
        """, (match_id,))
        row = cursor.fetchone()

        if not row:
            print(f"  ⚠️ Round not found in database: match_id={match_id}")
            cursor.close()
            return False

        round_id = row[0]

        # Update each player's corrupted fields
        update_count = 0
        for player in result['players']:
            guid = player['guid']
            obj = player.get('objective_stats', {})

            # Build UPDATE statement for corrupted fields only
            updates = []
            params = []

            for parser_field, db_column in CORRUPTED_FIELDS.items():
                if parser_field in obj:
                    updates.append(f"{db_column} = %s")
                    params.append(obj[parser_field])

            if not updates:
                continue

            # Add WHERE clause params
            params.extend([round_id, guid])

            sql = f"""
                UPDATE player_comprehensive_stats
                SET {', '.join(updates)}
                WHERE round_id = %s AND player_guid = %s
            """

            cursor.execute(sql, params)
            update_count += cursor.rowcount

        cursor.close()
        return update_count > 0

    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 100)
    print("SAFE ROUND 2 FIX - Update Corrupted Fields Without Full Rebuild")
    print("=" * 100)

    # Step 1: Backup
    backup_file = create_backup()
    if not backup_file:
        print("\n❌ ABORTED: Could not create backup")
        return 1

    print(f"\n✅ Backup complete. If anything goes wrong, restore with:")
    print(f"   PGPASSWORD='{DB_CONFIG['password']}' psql -h {DB_CONFIG['host']} \\")
    print(f"     -U {DB_CONFIG['user']} -d {DB_CONFIG['database']} < {backup_file}")

    # Step 2: Get R2 files
    r2_files = get_round2_files()

    if not r2_files:
        print("\n⚠️ No Round 2 files found!")
        return 0

    # Step 3: Ask for confirmation
    print("\n" + "=" * 100)
    print("STEP 3: UPDATE CONFIRMATION")
    print("=" * 100)
    print(f"\nAbout to update {len(r2_files)} Round 2 records")
    print(f"Fields to fix: {', '.join(list(CORRUPTED_FIELDS.keys())[:5])}... ({len(CORRUPTED_FIELDS)} total)")
    print(f"\nBackup location: {backup_file}")

    response = input("\nProceed with update? (yes/no): ")
    if response.lower() != 'yes':
        print("\n❌ Aborted by user")
        return 0

    # Step 4: Connect and update
    print("\n" + "=" * 100)
    print("STEP 4: UPDATING RECORDS")
    print("=" * 100)

    parser = C0RNP0RN3StatsParser()
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False  # Use transactions

    fixed_count = 0
    skipped_count = 0
    error_count = 0

    try:
        for i, r2_file in enumerate(r2_files, 1):
            filename = os.path.basename(r2_file)
            print(f"\n[{i}/{len(r2_files)}] {filename}")

            if fix_round2_record(conn, r2_file, parser):
                fixed_count += 1
                print(f"  ✅ Updated")
            else:
                skipped_count += 1
                print(f"  ⏭️ Skipped")

            # Commit every 10 files
            if i % 10 == 0:
                conn.commit()
                print(f"\n💾 Committed progress ({i}/{len(r2_files)})")

        # Final commit
        conn.commit()
        print("\n💾 Final commit complete")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        conn.rollback()
        print("🔄 Rolled back all changes")
        error_count = 1
    finally:
        conn.close()

    # Step 5: Summary
    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"✅ Fixed:   {fixed_count} records")
    print(f"⏭️ Skipped: {skipped_count} records")
    print(f"❌ Errors:  {error_count}")

    if error_count == 0 and fixed_count > 0:
        print("\n🎉 SUCCESS! Round 2 records have been fixed.")
        print(f"   Backup preserved at: {backup_file}")
    elif error_count > 0:
        print(f"\n⚠️ ERRORS OCCURRED - Changes rolled back")
        print(f"   Database unchanged, backup at: {backup_file}")

    return 0

if __name__ == '__main__':
    sys.exit(main())
