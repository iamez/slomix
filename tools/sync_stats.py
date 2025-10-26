#!/usr/bin/env python3
"""
Intelligent SSH Sync & I        ssh.connect(
            hostname=SSH_HOST,
            port=SSH_PORT,
            username=SSH_USER,
            key_filename=os.path.expanduser(SSH_KEY_PATH),
            timeout=10
        )
        if verbose:
            print("✅ Connected!")
            print()============================
Downloads new files from SSH server and immediately imports ONLY those files.
Much faster than running bulk import on everything!
"""
import os
import sqlite3
import sys
from pathlib import Path

import paramiko
from dotenv import load_dotenv

from dev.bulk_import_stats import BulkStatsImporter

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

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


def main():
    print("🚀 INTELLIGENT SSH SYNC & IMPORT")
    print("=" * 70)
    print(f"Server: {SSH_HOST}:{SSH_PORT}")
    print(f"Remote: {REMOTE_PATH}")
    print(f"Local:  {LOCAL_PATH}")
    print("=" * 70)
    print()

    try:
        # Check SSH key
        if not os.path.exists(SSH_KEY_PATH):
            print(f"❌ SSH key not found: {SSH_KEY_PATH}")
            return 1

        # Connect to SSH
        print("🔌 Connecting to SSH server...")
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
        print("📁 Checking local files...")
        if not os.path.exists(LOCAL_PATH):
            os.makedirs(LOCAL_PATH)

        local_files = {f for f in os.listdir(LOCAL_PATH) if f.endswith('.txt') and '_ws' not in f}
        print(f"   Found {len(local_files)} local files")
        print()

        # Find new files
        new_files = [f for f in remote_files if f not in local_files]
        new_files.sort()

        if not new_files:
            print("✅ No new files to download!")
            print("   Database is up to date.")
            sftp.close()
            ssh.close()
            return 0

        # Show what we'll download
        print(f"🆕 Found {len(new_files)} NEW files!")
        print()
        if len(new_files) <= 20:
            for f in new_files:
                print(f"   • {f}")
        else:
            print(f"   First 10:")
            for f in new_files[:10]:
                print(f"   • {f}")
            print(f"   ... ({len(new_files) - 20} more) ...")
            print(f"   Last 10:")
            for f in new_files[-10:]:
                print(f"   • {f}")
        print()

        # Download files
        print(f"📥 Downloading {len(new_files)} files...")
        downloaded = []

        for i, filename in enumerate(new_files, 1):
            try:
                remote = REMOTE_PATH + filename
                local = os.path.join(LOCAL_PATH, filename)

                sftp.get(remote, local)
                downloaded.append(filename)

                if verbose and (i % 10 == 0 or i == len(new_files)):
                    print(f"   {i}/{len(new_files)} downloaded...")

            except Exception as e:
                if verbose:
                    print(f"   ❌ Failed: {filename} - {e}")

        # Close SSH
        sftp.close()
        ssh.close()

        result['downloaded_count'] = len(downloaded)

        if verbose:
            print()
            print(f"✅ Downloaded {len(downloaded)}/{len(new_files)} files")
            print("🔌 SSH connection closed")
            print()

        if not downloaded:
            if verbose:
                print("❌ No files were downloaded successfully")
            result['error'] = "Download failed"
            return result

        # Now import ONLY the downloaded files
        if verbose:
            print("=" * 70)
            print(f"📊 IMPORTING {len(downloaded)} NEW FILES...")
            print("=" * 70)
            print()

        # Use the BulkStatsImporter but only for our files
        importer = BulkStatsImporter(DB_PATH)

        # Get full paths for downloaded files
        files_to_import = [os.path.join(LOCAL_PATH, f) for f in downloaded]

        # Import only these files
        imported = 0
        failed = 0

        for i, filepath in enumerate(files_to_import, 1):
            filename = os.path.basename(filepath)

            try:
                # Check if already processed (shouldn't be, but just in case)
                if importer.is_file_processed(filename):
                    if verbose:
                        print(f"   ⏭️  Skipped: {filename} (already processed)")
                    continue

                # Process the file
                import_result = importer.process_file(filepath)

                if import_result:
                    imported += 1
                    if verbose and (i % 5 == 0 or i == len(files_to_import)):
                        print(
                            f"   ✅ {imported}/{len(files_to_import)} "
                            f"imported (failed: {failed})"
                        )
                else:
                    failed += 1
                    if verbose:
                        print(f"   ❌ Failed: {filename}")

            except Exception as e:
                failed += 1
                if verbose:
                    print(f"   ❌ Error: {filename} - {e}")

        # Store results
        result['imported_count'] = imported
        result['failed_count'] = failed

        # Show summary
        if verbose:
            print()
            print("=" * 70)
            print("🎉 SYNC & IMPORT COMPLETE!")
            print("=" * 70)
            print(f"Downloaded: {len(downloaded)} files")
            print(f"Imported:   {imported} files")
            print(f"Failed:     {failed} files")
            print()

        # Get sessions by date for result
        if imported > 0:
            # Get sessions that were just created
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()

            # Get the dates from downloaded files
            dates = set()
            for f in downloaded:
                # Extract date from filename (YYYY-MM-DD format)
                if len(f) >= 10:
                    dates.add(f[:10])

            sessions_by_date = {}
            for date in sorted(dates):
                c.execute(
                    '''
                    SELECT COUNT(*), map_name
                    FROM sessions
                    WHERE session_date LIKE ?
                    GROUP BY map_name
                    ORDER BY map_name
                ''',
                    (f"{date}%",),
                )

                sessions = c.fetchall()
                if sessions:
                    sessions_by_date[date] = sessions
                    if verbose:
                        print(f"📅 {date}:")
                        for count, map_name in sessions:
                            rounds = "rounds" if count > 1 else "round"
                            print(f"   • {map_name}: {count} {rounds}")

            result['sessions_by_date'] = sessions_by_date
            conn.close()

            if verbose:
                print()

        if verbose:
            print("💡 Next steps:")
            print("   • Test bot commands: python bot/ultimate_bot.py")
            print("   • View latest session: !last_session")
            print()

        result['success'] = True
        return result

    except paramiko.AuthenticationException as e:
        result['error'] = f"SSH Authentication failed: {e}"
        if verbose:
            print("❌ SSH Authentication failed!")
            print("   Check your SSH key and credentials in .env")
        return result

    except Exception as e:
        result['error'] = str(e)
        if verbose:
            print(f"❌ Error: {e}")
            import traceback

            traceback.print_exc()
        return result


def main():
    """CLI entry point - runs sync with verbose output"""
    result = do_sync_and_import(verbose=True)
    return 0 if result['success'] else 1


if __name__ == '__main__':
    sys.exit(main())
