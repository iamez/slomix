#!/usr/bin/env python3
"""
SSH Sync & Import - Download new files and import them directly
"""
import os
import sqlite3
import sys

import paramiko
from dotenv import load_dotenv

from bot.community_stats_parser import C0RNP0RN3StatsParser

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Load environment
load_dotenv()

# Configuration
SSH_HOST = os.getenv('SSH_HOST', 'puran.hehe.si')
SSH_PORT = int(os.getenv('SSH_PORT', '48101'))
SSH_USER = os.getenv('SSH_USER', 'et')
SSH_KEY_PATH = os.path.expanduser(os.getenv('SSH_KEY_PATH', '~/.ssh/etlegacy_bot'))
REMOTE_PATH = '/home/et/.etlegacy/legacy/gamestats/'
LOCAL_PATH = './local_stats/'
DB_PATH = './etlegacy_production.db'

print("🚀 SSH SYNC & IMPORT")
print("=" * 70)
print(f"Server: {SSH_HOST}:{SSH_PORT}")
print(f"Remote: {REMOTE_PATH}")
print(f"Local:  {LOCAL_PATH}")
print(f"DB:     {DB_PATH}")
print("=" * 70)
print()


def get_local_files():
    """Get set of local filenames"""
    if not os.path.exists(LOCAL_PATH):
        return set()
    return {f for f in os.listdir(LOCAL_PATH) if f.endswith('.txt') and '_ws' not in f}


def download_new_files(sftp, remote_files, local_files):
    """Download files that don't exist locally"""
    new_files = [f for f in remote_files if f not in local_files]

    if not new_files:
        print("✅ No new files to download")
        return []

    print(f"📥 Downloading {len(new_files)} new files...")
    print()

    os.makedirs(LOCAL_PATH, exist_ok=True)
    downloaded = []

    for i, filename in enumerate(new_files, 1):
        try:
            remote = REMOTE_PATH + filename
            local = os.path.join(LOCAL_PATH, filename)

            sftp.get(remote, local)
            downloaded.append(filename)

            if i % 10 == 0 or i == len(new_files):
                print(f"   Downloaded {i}/{len(new_files)}...")

        except Exception as e:
            print(f"   ❌ Failed: {filename} - {e}")

    print()
    print(f"✅ Downloaded {len(downloaded)}/{len(new_files)} files")
    return downloaded


def import_files(files_to_import):
    """Import files into database"""
    if not files_to_import:
        print("✅ No files to import")
        return

    print()
    print(f"📊 Importing {len(files_to_import)} files into database...")
    print()

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    parser = C0RNP0RN3StatsParser()

    imported = 0
    failed = 0
    skipped = 0

    for i, filename in enumerate(sorted(files_to_import), 1):
        try:
            filepath = os.path.join(LOCAL_PATH, filename)

            # Check if already processed
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM processed_files WHERE filename = ?', (filename,))
            if cursor.fetchone():
                skipped += 1
                continue

            # Parse and import
            result = parser.parse_file(filepath)

            if result and 'error' not in result:
                # Insert session
                cursor.execute(
                    '''
                    INSERT INTO sessions (
                        session_date, map_name, round_number,
                        time_limit, actual_time
                    ) VALUES (?, ?, ?, ?, ?)
                ''',
                    (
                        result['timestamp'],
                        result['map'],
                        result['round'],
                        result.get('time_limit', '0:00'),
                        result.get('actual_time', '0:00'),
                    ),
                )

                session_id = cursor.lastrowid

                # Insert player stats
                for player in result.get('players', []):
                    cursor.execute(
                        '''
                        INSERT INTO player_comprehensive_stats (
                            session_id, session_date, player_guid,
                            player_name, team, kills, deaths,
                            damage_given, damage_received, headshot_kills,
                            dpm
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                        (
                            session_id,
                            result['timestamp'],
                            player.get('guid', ''),
                            player.get('name', 'Unknown'),
                            player.get('team', 3),
                            player.get('kills', 0),
                            player.get('deaths', 0),
                            player.get('damage_given', 0),
                            player.get('damage_received', 0),
                            player.get('headshots', 0),
                            player.get('dpm', 0),
                        ),
                    )

                    player_stats_id = cursor.lastrowid

                    # Insert weapon stats
                    for weapon in player.get('weapons', []):
                        cursor.execute(
                            '''
                            INSERT INTO weapon_comprehensive_stats (
                                session_id, player_comprehensive_stat_id,
                                player_guid, weapon_name, kills, deaths,
                                headshots, hits, shots
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''',
                            (
                                session_id,
                                player_stats_id,
                                player.get('guid', ''),
                                weapon.get('name', 'unknown'),
                                weapon.get('kills', 0),
                                weapon.get('deaths', 0),
                                weapon.get('headshots', 0),
                                weapon.get('hits', 0),
                                weapon.get('shots', 0),
                            ),
                        )

                # Mark as processed
                cursor.execute(
                    '''
                    INSERT INTO processed_files (filename, success)
                    VALUES (?, 1)
                ''',
                    (filename,),
                )

                conn.commit()
                imported += 1

                if i % 5 == 0 or i == len(files_to_import):
                    print(
                        f"   Imported {imported}/{len(files_to_import)}"
                        f" (skipped: {skipped}, failed: {failed})"
                    )

            else:
                # Mark as failed
                cursor.execute(
                    '''
                    INSERT INTO processed_files (filename, success)
                    VALUES (?, 0)
                ''',
                    (filename,),
                )
                conn.commit()
                failed += 1

        except Exception as e:
            print(f"   ❌ Error importing {filename}: {e}")
            failed += 1
            # Mark as failed
            try:
                cursor.execute(
                    '''
                    INSERT INTO processed_files (filename, success)
                    VALUES (?, 0)
                ''',
                    (filename,),
                )
                conn.commit()
            except BaseException:
                pass

    conn.close()

    print()
    print(f"✅ Import complete!")
    print(f"   Imported: {imported}")
    print(f"   Skipped:  {skipped}")
    print(f"   Failed:   {failed}")


def main():
    try:
        # Check SSH key
        if not os.path.exists(SSH_KEY_PATH):
            print(f"❌ SSH key not found: {SSH_KEY_PATH}")
            return 1

        print("🔌 Connecting to server...")

        # SSH connection
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=SSH_HOST,
            port=SSH_PORT,
            username=SSH_USER,
            key_filename=SSH_KEY_PATH,
            timeout=10,
        )

        print("✅ Connected!")
        print()

        # Open SFTP
        sftp = ssh.open_sftp()

        # Get remote files (exclude _ws.txt weapon stats)
        print("📂 Scanning remote directory...")
        remote_files = [
            f for f in sftp.listdir(REMOTE_PATH) if f.endswith('.txt') and '_ws' not in f
        ]
        remote_files.sort()

        print(f"   Found {len(remote_files)} stat files on server")
        if remote_files:
            print(f"   Latest: {remote_files[-1]}")
        print()

        # Get local files
        print("📁 Scanning local directory...")
        local_files = get_local_files()
        print(f"   Found {len(local_files)} local files")
        print()

        # Download new files
        new_files = download_new_files(sftp, remote_files, local_files)

        # Close SSH
        sftp.close()
        ssh.close()
        print("🔌 SSH connection closed")

        # Import the new files
        if new_files:
            import_files(new_files)

        print()
        print("=" * 70)
        print("🎉 SYNC & IMPORT COMPLETE!")
        print("=" * 70)

        return 0

    except paramiko.AuthenticationException:
        print("❌ Authentication failed!")
        return 1

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
