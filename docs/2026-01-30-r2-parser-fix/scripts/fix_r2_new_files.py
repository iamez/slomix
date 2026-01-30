#!/usr/bin/env python3
"""
Fix R2 records from newly downloaded files (2026-01-16 onwards)
"""

import sys
import os
import subprocess
from datetime import datetime

sys.path.insert(0, '/home/samba/share/slomix_discord')

from bot.community_stats_parser import C0RNP0RN3StatsParser

LOCAL_STATS = '/home/samba/share/slomix_discord/local_stats'

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'etlegacy',
    'user': 'etlegacy_user',
    'password': 'etlegacy_secure_2025'
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

def get_new_round2_files():
    """Get R2 files from 2026-01-16 onwards"""
    r2_files = []
    for filename in os.listdir(LOCAL_STATS):
        if filename.endswith('-round-2.txt') and '-endstats' not in filename:
            # Extract date from filename
            parts = filename.split('-')
            if len(parts) >= 3:
                try:
                    file_date = f"{parts[0]}-{parts[1]}-{parts[2]}"
                    if file_date >= "2026-01-16":
                        r2_files.append((filename, os.path.join(LOCAL_STATS, filename)))
                except:
                    continue

    r2_files.sort()
    return r2_files

def main():
    print("=" * 100)
    print("FIX NEWLY DOWNLOADED R2 FILES (2026-01-16 onwards)")
    print("=" * 100)

    # Get files
    r2_files = get_new_round2_files()
    print(f"\n📊 Found {len(r2_files)} R2 files from 2026-01-16 onwards")

    if not r2_files:
        print("\n⚠️ No files to process")
        return 0

    # Process files
    print("\n" + "=" * 100)
    print("PROCESSING FILES")
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

            # Extract match_id from R1 filename
            r1_filename = result.get('r1_filename')
            if not r1_filename:
                print(f"  ⏭️ No R1 filename in result")
                skipped_count += 1
                continue

            match_id = '-'.join(r1_filename.split('-')[:4])

            # Update each player
            player_updates = 0
            for player in result['players']:
                guid = player['guid']
                obj = player.get('objective_stats', {})

                # Build UPDATE
                updates = []

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
        print("\n🎉 SUCCESS! Newly downloaded R2 records have been fixed.")

    return 0

if __name__ == '__main__':
    sys.exit(main())
