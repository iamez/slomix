"""
3-way comparison: Local DB vs VPS vs local_stats directory
"""
import os
import sqlite3
from pathlib import Path
import paramiko

# VPS Configuration
VPS_HOST = os.getenv('SSH_HOST', 'puran.hehe.si')
VPS_PORT = int(os.getenv('SSH_PORT', '48101'))
VPS_USER = os.getenv('SSH_USER', 'et')
VPS_KEY = os.path.expanduser(os.getenv('SSH_KEY_PATH', '~/.ssh/etlegacy_bot'))
VPS_STATS_PATH = '/home/et/.etlegacy/legacy/gamestats'
LOCAL_STATS_DIR = 'local_stats'

def parse_filename(filename):
    """Parse ET:Legacy stats filename: YYYY-MM-DD-HHMMSS-mapname-round-N.txt"""
    try:
        parts = filename.replace('.txt', '').split('-')
        if len(parts) < 7:
            return None
        
        date = f"{parts[0]}-{parts[1]}-{parts[2]}"
        map_name = '-'.join(parts[4:-2])
        round_num = int(parts[-1])
        
        return {'date': date, 'map': map_name, 'round': round_num, 'filename': filename}
    except:
        return None

def get_local_db_rounds(target_date):
    """Get rounds from local SQLite database"""
    conn = sqlite3.connect('bot/etlegacy_production.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT round_number, map_name
        FROM player_comprehensive_stats 
        WHERE round_date = ?
        GROUP BY round_number, map_name
    ''', (target_date,))
    
    rounds = {(row[1], row[0]) for row in cursor.fetchall()}
    conn.close()
    return rounds

def get_vps_rounds(target_date):
    """Get rounds from VPS via SSH"""
    if not os.path.exists(VPS_KEY):
        print(f"❌ SSH key not found: {VPS_KEY}")
        return None
    
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=VPS_HOST, port=VPS_PORT, username=VPS_USER, key_filename=VPS_KEY)
        
        # List files for target date
        cmd = f'ls {VPS_STATS_PATH}/*{target_date}*.txt 2>/dev/null'
        stdin, stdout, stderr = ssh.exec_command(cmd)
        files_output = stdout.read().decode('utf-8')
        ssh.close()
        
        rounds = set()
        for line in files_output.split('\n'):
            line = line.strip()
            if not line or not line.endswith('.txt'):
                continue
            
            filename = os.path.basename(line)
            parsed = parse_filename(filename)
            if parsed and parsed['date'] == target_date:
                rounds.add((parsed['map'], parsed['round']))
        
        return rounds
    except Exception as e:
        print(f"❌ VPS connection failed: {e}")
        return None

def get_local_stats_rounds(target_date):
    """Get rounds from local_stats directory"""
    if not os.path.exists(LOCAL_STATS_DIR):
        print(f"❌ Local stats directory not found: {LOCAL_STATS_DIR}")
        return None
    
    rounds = set()
    for filename in os.listdir(LOCAL_STATS_DIR):
        if not filename.endswith('.txt'):
            continue
        
        parsed = parse_filename(filename)
        if parsed and parsed['date'] == target_date:
            rounds.add((parsed['map'], parsed['round']))
    
    return rounds

def main():
    # Get latest date from DB
    conn = sqlite3.connect('bot/etlegacy_production.db')
    cursor = conn.cursor()
    cursor.execute('SELECT MAX(round_date) FROM player_comprehensive_stats')
    target_date = cursor.fetchone()[0]
    conn.close()
    
    print("=" * 80)
    print(f"3-WAY COMPARISON FOR {target_date}")
    print("=" * 80)
    
    # Get rounds from all sources
    print("\n[1/3] Querying local database...")
    db_rounds = get_local_db_rounds(target_date)
    print(f"  Found {len(db_rounds)} rounds")
    
    print("\n[2/3] Checking VPS...")
    vps_rounds = get_vps_rounds(target_date)
    if vps_rounds is None:
        print("  Skipping VPS comparison")
    else:
        print(f"  Found {len(vps_rounds)} rounds")
    
    print("\n[3/3] Checking local_stats directory...")
    local_rounds = get_local_stats_rounds(target_date)
    if local_rounds is None:
        print("  Skipping local_stats comparison")
    else:
        print(f"  Found {len(local_rounds)} rounds")
    
    # Compare
    print("\n" + "=" * 80)
    print("DETAILED COMPARISON")
    print("=" * 80)
    
    all_rounds = db_rounds | (vps_rounds or set()) | (local_rounds or set())
    
    for map_name, round_num in sorted(all_rounds):
        in_db = (map_name, round_num) in db_rounds
        in_vps = vps_rounds and (map_name, round_num) in vps_rounds
        in_local = local_rounds and (map_name, round_num) in local_rounds
        
        status = []
        if in_db:
            status.append("DB")
        if in_vps:
            status.append("VPS")
        if in_local:
            status.append("LOCAL")
        
        status_str = " + ".join(status) if status else "NONE"
        
        # Color code
        if in_db and in_vps and in_local:
            icon = "✅"  # Perfect - everywhere
        elif in_db and (in_vps or in_local):
            icon = "✅"  # Good - in DB + at least one source
        elif in_vps or in_local:
            icon = "⚠️ "  # Warning - available but not imported
        else:
            icon = "❌"  # Error - shouldn't happen
        
        print(f"{icon} {map_name:20} Round {round_num} - [{status_str}]")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if vps_rounds and local_rounds:
        in_all = db_rounds & vps_rounds & local_rounds
        in_db_only = db_rounds - (vps_rounds | local_rounds)
        in_vps_not_db = vps_rounds - db_rounds
        in_local_not_db = local_rounds - db_rounds
        available_not_imported = (vps_rounds | local_rounds) - db_rounds
        
        print(f"\n✅ In all 3 locations: {len(in_all)}")
        print(f"✅ In DB (imported): {len(db_rounds)}")
        print(f"📊 Available on VPS: {len(vps_rounds)}")
        print(f"📁 Available locally: {len(local_rounds)}")
        
        if available_not_imported:
            print(f"\n⚠️  NEEDS IMPORT ({len(available_not_imported)} rounds):")
            for map_name, round_num in sorted(available_not_imported):
                sources = []
                if (map_name, round_num) in vps_rounds:
                    sources.append("VPS")
                if (map_name, round_num) in local_rounds:
                    sources.append("local_stats")
                print(f"   {map_name:20} Round {round_num} - Available in: {', '.join(sources)}")
        
        if in_db_only:
            print(f"\n⚠️  In DB but missing from sources: {len(in_db_only)}")
            for map_name, round_num in sorted(in_db_only):
                print(f"   {map_name:20} Round {round_num}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
