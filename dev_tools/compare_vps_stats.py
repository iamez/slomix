"""
Compare local database stats with VPS game stats directory
"""
import os
import sqlite3
from datetime import datetime
import paramiko
from pathlib import Path

# VPS Configuration (from .env file)
VPS_HOST = os.getenv('SSH_HOST', 'puran.hehe.si')
VPS_PORT = int(os.getenv('SSH_PORT', '48101'))
VPS_USER = os.getenv('SSH_USER', 'et')
VPS_KEY = os.path.expanduser(os.getenv('SSH_KEY_PATH', '~/.ssh/etlegacy_bot'))
VPS_STATS_PATH = os.getenv('REMOTE_STATS_PATH', '/home/et/.etlegacy/legacy/gamestats')

def get_local_stats():
    """Get stats from local database"""
    conn = sqlite3.connect('bot/etlegacy_production.db')
    cursor = conn.cursor()
    
    # Get latest date
    cursor.execute('SELECT MAX(round_date) FROM player_comprehensive_stats')
    latest_date = cursor.fetchone()[0]
    
    # Get all rounds from latest date
    cursor.execute('''
        SELECT round_number, map_name, COUNT(DISTINCT player_name) as players
        FROM player_comprehensive_stats 
        WHERE round_date = ?
        GROUP BY round_number, map_name
        ORDER BY map_name, round_number
    ''', (latest_date,))
    
    rounds = cursor.fetchall()
    conn.close()
    
    return latest_date, rounds

def get_vps_stats_files():
    """List stats files on VPS via SSH"""
    if not os.path.exists(VPS_KEY):
        print(f"❌ SSH key not found: {VPS_KEY}")
        print("   Please set SSH_KEY_PATH environment variable or create key")
        return None
    
    try:
        # Connect via SSH
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        print(f"Connecting to {VPS_USER}@{VPS_HOST}:{VPS_PORT}...")
        ssh.connect(
            hostname=VPS_HOST,
            port=VPS_PORT,
            username=VPS_USER,
            key_filename=VPS_KEY,
            timeout=10
        )
        
        # List stats files (use simple ls without -l to avoid line wrapping)
        cmd = f'ls {VPS_STATS_PATH}/*2025-11-04*.txt 2>/dev/null'
        stdin, stdout, stderr = ssh.exec_command(cmd)
        
        files_output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        
        ssh.close()
        
        if error and 'No such file' in error:
            print(f"❌ Stats directory not found: {VPS_STATS_PATH}")
            return None
        
        return files_output
        
    except Exception as e:
        print(f"❌ SSH connection failed: {e}")
        return None

def parse_filename(filename):
    """Parse ET:Legacy stats filename: YYYY-MM-DD-HHMMSS-mapname-round-N.txt"""
    try:
        parts = filename.replace('.txt', '').split('-')
        if len(parts) < 7:
            return None
        
        date = f"{parts[0]}-{parts[1]}-{parts[2]}"
        time = parts[3]
        map_name = '-'.join(parts[4:-2])  # Handle maps with dashes
        round_num = int(parts[-1])
        
        return {
            'date': date,
            'time': time,
            'map': map_name,
            'round': round_num,
            'filename': filename
        }
    except:
        return None

def main():
    print("=" * 80)
    print("Local DB vs VPS Stats Comparison")
    print("=" * 80)
    
    # Get local database stats
    print("\n[1/2] Querying local database...")
    latest_date, local_rounds = get_local_stats()
    
    print(f"\nLocal Database (latest session: {latest_date}):")
    print(f"  Total rounds: {len(local_rounds)}")
    
    local_maps = {}
    for round_num, map_name, players in local_rounds:
        key = (map_name, round_num)
        local_maps[key] = players
    
    print("\n  Rounds by map:")
    for (map_name, round_num), players in sorted(local_maps.items()):
        print(f"    {map_name:20} Round {round_num} - {players} players")
    
    # Get VPS stats files
    print("\n[2/2] Checking VPS stats directory...")
    vps_files = get_vps_stats_files()
    
    if vps_files is None:
        print("\n⚠️  Could not connect to VPS - showing local data only")
        return
    
    print("\nVPS Stats Files (last 30):")
    print(vps_files)
    
    # Parse VPS filenames
    print("\nParsing VPS filenames...")
    vps_rounds = {}
    for line in vps_files.split('\n'):
        line = line.strip()
        if not line or not line.endswith('.txt'):
            continue
        
        # Extract just the filename from full path
        filename = os.path.basename(line)
        parsed = parse_filename(filename)
        if parsed and parsed['date'] == latest_date:
            key = (parsed['map'], parsed['round'])
            vps_rounds[key] = parsed['filename']
    
    print(f"\nVPS files from {latest_date}: {len(vps_rounds)}")
    for (map_name, round_num), filename in sorted(vps_rounds.items()):
        print(f"    {map_name:20} Round {round_num} - {filename}")
    
    # Compare
    print("\n" + "=" * 80)
    print("COMPARISON")
    print("=" * 80)
    
    in_db_not_vps = set(local_maps.keys()) - set(vps_rounds.keys())
    in_vps_not_db = set(vps_rounds.keys()) - set(local_maps.keys())
    in_both = set(local_maps.keys()) & set(vps_rounds.keys())
    
    print(f"\n✅ In both DB and VPS: {len(in_both)}")
    for map_name, round_num in sorted(in_both):
        print(f"   {map_name:20} Round {round_num}")
    
    if in_db_not_vps:
        print(f"\n⚠️  In DB but NOT on VPS: {len(in_db_not_vps)}")
        for map_name, round_num in sorted(in_db_not_vps):
            print(f"   {map_name:20} Round {round_num}")
    
    if in_vps_not_db:
        print(f"\n⚠️  On VPS but NOT in DB: {len(in_vps_not_db)}")
        for map_name, round_num in sorted(in_vps_not_db):
            print(f"   {map_name:20} Round {round_num} - {vps_rounds[(map_name, round_num)]}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
