#!/usr/bin/env python3
"""
Test SSH connection and download new stats files
"""
import os
import sys

import paramiko
from dotenv import load_dotenv

# Load environment
load_dotenv()

# SSH Configuration
SSH_HOST = os.getenv('SSH_HOST', 'puran.hehe.si')
SSH_PORT = int(os.getenv('SSH_PORT', '48101'))
SSH_USER = os.getenv('SSH_USER', 'et')
SSH_KEY_PATH = os.path.expanduser(os.getenv('SSH_KEY_PATH', '~/.ssh/etlegacy_bot'))
REMOTE_STATS_PATH = '/home/et/.etlegacy/legacy/gamestats/'
LOCAL_STATS_PATH = './local_stats/'

print("🔐 SSH Connection Test")
print("=" * 60)
print(f"Host: {SSH_HOST}:{SSH_PORT}")
print(f"User: {SSH_USER}")
print(f"Key:  {SSH_KEY_PATH}")
print(f"Remote: {REMOTE_STATS_PATH}")
print(f"Local:  {LOCAL_STATS_PATH}")
print("=" * 60)
print()

# Check if key file exists
if not os.path.exists(SSH_KEY_PATH):
    print(f"❌ SSH key not found at: {SSH_KEY_PATH}")
    print(f"   Please create the key file first!")
    sys.exit(1)

print(f"✅ SSH key found: {SSH_KEY_PATH}")
print()

try:
    # Create SSH client
    print("🔌 Connecting to server...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Connect
    ssh.connect(
        hostname=SSH_HOST, port=SSH_PORT, username=SSH_USER, key_filename=SSH_KEY_PATH, timeout=10
    )
    print("✅ SSH connection established!")
    print()

    # List files in remote directory
    print(f"📂 Listing files in {REMOTE_STATS_PATH}...")
    sftp = ssh.open_sftp()

    # Get all .txt files (excluding _ws.txt weapon stats)
    remote_files = []
    for filename in sftp.listdir(REMOTE_STATS_PATH):
        if filename.endswith('.txt') and '_ws' not in filename:
            remote_files.append(filename)

    remote_files.sort()
    print(f"   Found {len(remote_files)} stat files on server")

    if remote_files:
        print(f"   Latest: {remote_files[-1]}")
        print(f"   Oldest: {remote_files[0]}")
    print()

    # Get local files
    local_files = set()
    if os.path.exists(LOCAL_STATS_PATH):
        for filename in os.listdir(LOCAL_STATS_PATH):
            if filename.endswith('.txt') and '_ws' not in filename:
                local_files.add(filename)

    print(f"📁 Local files: {len(local_files)}")
    print()

    # Find new files
    new_files = [f for f in remote_files if f not in local_files]
    new_files.sort()

    if new_files:
        print(f"🆕 Found {len(new_files)} NEW files to download!")
        print()

        # Show first 10 and last 10
        if len(new_files) <= 20:
            for f in new_files:
                print(f"   • {f}")
        else:
            print("   First 10:")
            for f in new_files[:10]:
                print(f"   • {f}")
            print(f"   ... ({len(new_files) - 20} more) ...")
            print("   Last 10:")
            for f in new_files[-10:]:
                print(f"   • {f}")
        print()

        # Ask to download
        response = input(f"📥 Download {len(new_files)} files? (y/N): ").strip().lower()

        if response == 'y':
            print()
            print("⬇️  Downloading files...")

            # Ensure local directory exists
            os.makedirs(LOCAL_STATS_PATH, exist_ok=True)

            downloaded = 0
            for filename in new_files:
                try:
                    remote_path = REMOTE_STATS_PATH + filename
                    local_path = os.path.join(LOCAL_STATS_PATH, filename)

                    sftp.get(remote_path, local_path)
                    downloaded += 1

                    # Progress indicator
                    if downloaded % 10 == 0:
                        print(f"   Downloaded {downloaded}/{len(new_files)}...")

                except Exception as e:
                    print(f"   ❌ Failed to download {filename}: {e}")

            print()
            print(f"✅ Successfully downloaded {downloaded}/{len(new_files)} files!")
            print()
            print(f"📊 Next step: Run bulk import to process these files")
            print(f"   python dev/bulk_import_stats.py")
        else:
            print("   Skipped download.")
    else:
        print("✅ No new files found - database is up to date!")

    sftp.close()
    ssh.close()
    print()
    print("🔌 SSH connection closed")

except paramiko.AuthenticationException:
    print("❌ Authentication failed!")
    print("   Check your SSH key and credentials in .env")
    sys.exit(1)

except paramiko.SSHException as e:
    print(f"❌ SSH error: {e}")
    sys.exit(1)

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
