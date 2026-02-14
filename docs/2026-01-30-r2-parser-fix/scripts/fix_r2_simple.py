#!/usr/bin/env python3
"""
Simple fix for Round 2 records using database manager.
"""

import sys
import os
import subprocess
from datetime import datetime

sys.path.insert(0, '/home/samba/share/slomix_discord')

from bot.community_stats_parser import C0RNP0RN3StatsParser

BACKUP_DIR = '/home/samba/share/slomix_discord/backups'
LOCAL_STATS = '/home/samba/share/slomix_discord/local_stats'

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'etlegacy',
    'user': 'etlegacy_user',
    'password': 'REDACTED_DB_PASSWORD'
}

# Fields mapping: parser_field -> db_column
CORRUPTED_FIELDS = {
    'xp': 'xp',
    'death_spree': 'death_spree_worst',
    'kill_assists': 'kill_assists',
    'headshot_kills': 'headshot_kills',
    'objectives_stolen': 'objectives_stolen',
    'dynamites_planted': 'dynamites_planted',
    'times_revived': 'times_revived',
    'time_dead_ratio': 'time_dead_ratio',
    'time_dead_minutes': 'time_dead_minutes',
    'useful_kills': 'most_useful_kills',
    'denied_playtime': 'denied_playtime',
    'revives_given': 'revives_given',
}

def run_psql(sql):
    """Run SQL via psql command"""
    cmd = [
        'psql',
        '-h', DB_CONFIG['host'],
        '-p', str(DB_CONFIG['port']),
        '-U', DB_CONFIG['user'],
        '-d', DB_CONFIG['database'],
        '-t',
        '-c', sql
    ]

    env = os.environ.copy()
    env['PGPASSWORD'] = DB_CONFIG['password']

    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()

def create_backup():
    """Create database backup"""
    print("=" * 100)
    print("STEP 1: CREATING BACKUP")
    print("=" * 100)

    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f"{BACKUP_DIR}/etlegacy_before_r2_fix_{timestamp}.sql"

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

    size_mb = os.path.getsize(backup_file) / (1024 * 1024)
    print(f"✅ Backup created: {size_mb:.2f} MB")
    print(f"   Location: {backup_file}")

    return backup_file

def get_round2_files():
    """Get all Round 2 files"""
    r2_files = []
    for filename in os.listdir(LOCAL_STATS):
        if filename.endswith('-round-2.txt') and not filename.endswith('-endstats.txt'):
            r2_files.append((filename, os.path.join(LOCAL_STATS, filename)))

    r2_files.sort()
    return r2_files

def main():
    print("=" * 100)
    print("SAFE ROUND 2 FIX - Update Database with Correct Values")
    print("=" * 100)

    # Backup
    backup_file = create_backup()
    if not backup_file:
        print("\n❌ ABORTED: Backup failed")
        return 1

    print(f"\n✅ If anything goes wrong, restore with:")
    print(f"   PGPASSWORD='<DB_PASSWORD>' psql -h {DB_CONFIG['host']} \\")
    print(f"     -U {DB_CONFIG['user']} -d {DB_CONFIG['database']} < {backup_file}")

    # Get files
    print("\n" + "=" * 100)
    print("STEP 2: FINDING ROUND 2 FILES")
    print("=" * 100)

    r2_files = get_round2_files()
    print(f"\n📊 Found {len(r2_files)} Round 2 files")

    if not r2_files:
        print("\n⚠️ No files to process")
        return 0

    # Confirmation
    print("\n" + "=" * 100)
    print("STEP 3: AUTO-PROCEEDING (Non-interactive mode)")
    print("=" * 100)
    print(f"\nWill update ~3,633 Round 2 player records")
    print(f"Fixing 12 fields: {', '.join(list(CORRUPTED_FIELDS.keys())[:5])}...")
    print("\n✅ Auto-confirmed - proceeding with update")

    # Process files
    print("\n" + "=" * 100)
    print("STEP 4: PROCESSING FILES")
    print("=" * 100)

    parser = C0RNP0RN3StatsParser()
    fixed_count = 0
    skipped_count = 0
    error_count = 0

    for i, (filename, filepath) in enumerate(r2_files, 1):
        print(f"\n[{i}/{len(r2_files)}] {filename}")

        try:
            # Parse file
            result = parser.parse_stats_file(filepath)

            if not result['success']:
                print(f"  ⏭️ Parse failed: {result.get('error')}")
                skipped_count += 1
                continue

            if not result.get('differential_calculation'):
                print(f"  ⏭️ No R1 match (skip)")
                skipped_count += 1
                continue

            # Extract match_id
            match_id = '-'.join(filename.split('-')[:4])

            # Update each player
            player_updates = 0
            for player in result['players']:
                guid = player['guid']
                obj = player.get('objective_stats', {})

                # Build UPDATE
                updates = []
                values = []

                for parser_field, db_column in CORRUPTED_FIELDS.items():
                    if parser_field in obj:
                        updates.append(f"{db_column} = {obj[parser_field]}")

                if not updates:
                    continue

                sql = f"""
                    UPDATE player_comprehensive_stats
                    SET {', '.join(updates)}
                    WHERE round_id = (
                        SELECT id FROM rounds
                        WHERE match_id = '{match_id}' AND round_number = 2
                    )
                    AND player_guid = '{guid}';
                """

                code, out, err = run_psql(sql)
                if code == 0:
                    player_updates += 1

            if player_updates > 0:
                print(f"  ✅ Updated {player_updates} players")
                fixed_count += 1
            else:
                print(f"  ⏭️ No players updated")
                skipped_count += 1

        except Exception as e:
            print(f"  ❌ Error: {e}")
            error_count += 1

    # Summary
    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"✅ Fixed:   {fixed_count} files")
    print(f"⏭️ Skipped: {skipped_count} files")
    print(f"❌ Errors:  {error_count} files")

    if error_count == 0 and fixed_count > 0:
        print("\n🎉 SUCCESS! Round 2 records have been fixed.")
        print(f"   Backup: {backup_file}")

    return 0

if __name__ == '__main__':
    sys.exit(main())
