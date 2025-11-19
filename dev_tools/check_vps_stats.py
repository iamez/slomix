"""
Quick check of VPS stats directory
"""
import os
import paramiko

VPS_HOST = 'puran.hehe.si'
VPS_PORT = 48101
VPS_USER = 'et'
VPS_KEY = os.path.expanduser('~/.ssh/etlegacy_bot')
STATS_PATH = '/home/et/.etlegacy/legacy/gamestats'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

print(f"Connecting to {VPS_USER}@{VPS_HOST}:{VPS_PORT}...")
ssh.connect(hostname=VPS_HOST, port=VPS_PORT, username=VPS_USER, key_filename=VPS_KEY)

# Check if directory exists
print("\n1. Checking if stats directory exists...")
stdin, stdout, stderr = ssh.exec_command(f'ls -ld {STATS_PATH} 2>&1')
print(stdout.read().decode())

# List all .txt files
print("2. Listing all .txt files...")
stdin, stdout, stderr = ssh.exec_command(f'ls -lh {STATS_PATH}/*.txt 2>&1 | head -50')
output = stdout.read().decode()
print(output if output else "No .txt files found")

# Count total files
print("3. Count of .txt files...")
stdin, stdout, stderr = ssh.exec_command(f'ls {STATS_PATH}/*.txt 2>/dev/null | wc -l')
count = stdout.read().decode().strip()
print(f"Total .txt files: {count}")

# Show newest files
print("\n4. Newest 10 files (by date)...")
stdin, stdout, stderr = ssh.exec_command(f'ls -lt {STATS_PATH}/*.txt 2>/dev/null | head -10')
print(stdout.read().decode())

ssh.close()
