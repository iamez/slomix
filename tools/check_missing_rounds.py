"""
Check for missing Round 1 or Round 2 files between local and remote
"""
import os
import paramiko
from collections import defaultdict

def get_local_files():
    """Get all local stats files (excluding _ws.txt)"""
    local_dir = 'local_stats'
    files = [f for f in os.listdir(local_dir) 
             if f.endswith('.txt') and not f.endswith('_ws.txt')]
    return set(files)

def get_remote_files():
    """Get all remote stats files via SSH (excluding _ws.txt)"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    key_path = os.path.expanduser('~/.ssh/etlegacy_bot')
    ssh.connect(
        hostname='puran.hehe.si',
        port=48101,
        username='et',
        key_filename=key_path
    )
    
    sftp = ssh.open_sftp()
    all_files = sftp.listdir('/home/et/.etlegacy/legacy/gamestats')
    files = [f for f in all_files 
             if f.endswith('.txt') and not f.endswith('_ws.txt')]
    
    sftp.close()
    ssh.close()
    
    return set(files)

def parse_filename(filename):
    """
    Parse filename into components
    Format: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
    Returns: (date, time, mapname, round_num)
    """
    try:
        parts = filename.replace('.txt', '').split('-')
        if len(parts) < 7:
            return None
        
        date = f"{parts[0]}-{parts[1]}-{parts[2]}"
        time = parts[3]
        # Map name is everything between time and 'round'
        map_parts = []
        for i in range(4, len(parts) - 2):
            map_parts.append(parts[i])
        mapname = '-'.join(map_parts)
        round_num = int(parts[-1])
        
        return (date, time, mapname, round_num)
    except:
        return None

def find_missing_rounds(files):
    """
    Find files that have Round 2 but missing Round 1, or vice versa
    """
    # Group files by date-time-map
    sessions = defaultdict(list)
    
    for filename in files:
        parsed = parse_filename(filename)
        if not parsed:
            continue
        
        date, time, mapname, round_num = parsed
        session_key = f"{date}-{time}-{mapname}"
        sessions[session_key].append((round_num, filename))
    
    # Find incomplete sessions
    missing_round1 = []
    missing_round2 = []
    
    for session_key, rounds in sessions.items():
        round_nums = [r[0] for r in rounds]
        filenames = {r[0]: r[1] for r in rounds}
        
        if 2 in round_nums and 1 not in round_nums:
            missing_round1.append({
                'session': session_key,
                'round2_file': filenames[2]
            })
        
        if 1 in round_nums and 2 not in round_nums:
            missing_round2.append({
                'session': session_key,
                'round1_file': filenames[1]
            })
    
    return missing_round1, missing_round2

def main():
    print("🔍 Comparing local vs remote stats files...\n")
    
    # Get files
    print("📁 Scanning local files...")
    local_files = get_local_files()
    print(f"   Found: {len(local_files)} files")
    
    print("\n📡 Scanning remote files...")
    remote_files = get_remote_files()
    print(f"   Found: {len(remote_files)} files")
    
    # Compare
    print("\n🔄 Comparing files...")
    only_local = local_files - remote_files
    only_remote = remote_files - local_files
    
    print(f"\n📊 Comparison Results:")
    print(f"   Files only in local: {len(only_local)}")
    print(f"   Files only in remote: {len(only_remote)}")
    print(f"   Files in both: {len(local_files & remote_files)}")
    
    if only_local:
        print(f"\n⚠️ Files in local but NOT on remote:")
        for f in sorted(only_local)[:20]:
            print(f"   - {f}")
        if len(only_local) > 20:
            print(f"   ... and {len(only_local) - 20} more")
    
    if only_remote:
        print(f"\n⚠️ Files on remote but NOT in local:")
        for f in sorted(only_remote)[:20]:
            print(f"   - {f}")
        if len(only_remote) > 20:
            print(f"   ... and {len(only_remote) - 20} more")
    
    # Check for missing rounds in LOCAL files
    print("\n\n🔍 Checking LOCAL files for missing rounds...")
    missing_r1_local, missing_r2_local = find_missing_rounds(local_files)
    
    if missing_r1_local:
        print(f"\n⚠️ LOCAL: Sessions with Round 2 but NO Round 1: {len(missing_r1_local)}")
        for item in missing_r1_local[:10]:
            print(f"   - {item['session']}")
            print(f"     Has: {item['round2_file']}")
            expected_r1 = item['round2_file'].replace('round-2.txt', 'round-1.txt')
            print(f"     Missing: {expected_r1}")
        if len(missing_r1_local) > 10:
            print(f"   ... and {len(missing_r1_local) - 10} more")
    else:
        print(f"\n✅ LOCAL: All Round 2 files have corresponding Round 1")
    
    if missing_r2_local:
        print(f"\n⚠️ LOCAL: Sessions with Round 1 but NO Round 2: {len(missing_r2_local)}")
        for item in missing_r2_local[:10]:
            print(f"   - {item['session']}")
            print(f"     Has: {item['round1_file']}")
            expected_r2 = item['round1_file'].replace('round-1.txt', 'round-2.txt')
            print(f"     Missing: {expected_r2}")
        if len(missing_r2_local) > 10:
            print(f"   ... and {len(missing_r2_local) - 10} more")
    else:
        print(f"\n✅ LOCAL: All Round 1 files have corresponding Round 2")
    
    # Check for missing rounds in REMOTE files
    print("\n\n🔍 Checking REMOTE files for missing rounds...")
    missing_r1_remote, missing_r2_remote = find_missing_rounds(remote_files)
    
    if missing_r1_remote:
        print(f"\n⚠️ REMOTE: Sessions with Round 2 but NO Round 1: {len(missing_r1_remote)}")
        for item in missing_r1_remote[:10]:
            print(f"   - {item['session']}")
            print(f"     Has: {item['round2_file']}")
            expected_r1 = item['round2_file'].replace('round-2.txt', 'round-1.txt')
            print(f"     Missing: {expected_r1}")
        if len(missing_r1_remote) > 10:
            print(f"   ... and {len(missing_r1_remote) - 10} more")
    else:
        print(f"\n✅ REMOTE: All Round 2 files have corresponding Round 1")
    
    if missing_r2_remote:
        print(f"\n⚠️ REMOTE: Sessions with Round 1 but NO Round 2: {len(missing_r2_remote)}")
        for item in missing_r2_remote[:10]:
            print(f"   - {item['session']}")
            print(f"     Has: {item['round1_file']}")
            expected_r2 = item['round1_file'].replace('round-1.txt', 'round-2.txt')
            print(f"     Missing: {expected_r2}")
        if len(missing_r2_remote) > 10:
            print(f"   ... and {len(missing_r2_remote) - 10} more")
    else:
        print(f"\n✅ REMOTE: All Round 1 files have corresponding Round 2")
    
    print("\n\n✅ Check complete!")

if __name__ == '__main__':
    main()
