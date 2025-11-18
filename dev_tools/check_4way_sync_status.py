#!/usr/bin/env python3
"""
4-Way Sync Status Check
========================
Compares files across all 4 sources:
1. Game server (puran.hehe.si) - where stats are generated
2. Local Windows machine (local_stats/) - our dev copy
3. VPS local_stats - bot's file directory
4. VPS PostgreSQL database - final storage

Shows what's missing from each location and calculates sync percentage.
"""
import asyncio
import asyncpg
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import subprocess

sys.path.insert(0, str(Path(__file__).parent))
from bot.config import load_config


def run_ssh_command(host, user, command, key_path=None):
    """Run SSH command and return output"""
    ssh_cmd = ["ssh"]
    if key_path:
        ssh_cmd.extend(["-i", key_path])
    ssh_cmd.extend([f"{user}@{host}", command])
    
    try:
        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
        return result.stdout.strip()
    except Exception as e:
        print(f"   ❌ SSH error: {e}")
        return None


async def check_4way_sync(target_date=None):
    """
    Compare files across 4 locations for a specific date (defaults to today)
    """
    config = load_config()
    
    # Use today if no date specified
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")
    
    print("=" * 80)
    print("🔍 4-WAY SYNC STATUS CHECK")
    print("=" * 80)
    print(f"\n📅 Checking date: {target_date}")
    print(f"⏰ Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # ========================================================================
    # SOURCE 1: Game Server (puran.hehe.si)
    # ========================================================================
    print("\n" + "=" * 80)
    print("🎮 SOURCE 1: Game Server (puran.hehe.si)")
    print("=" * 80)
    
    game_server_files = []
    ssh_host = "puran.hehe.si"
    ssh_port = "48101"
    ssh_user = "et"
    remote_path = "/home/et/.etlegacy/legacy/gamestats"
    
    print(f"   Connecting to {ssh_user}@{ssh_host}:{ssh_port}...")
    print(f"   (You may be prompted for password)")
    # Don't capture output so password prompt shows
    ssh_cmd = f"ssh -p {ssh_port} {ssh_user}@{ssh_host} ls -1 {remote_path}/{target_date}*.txt 2>/dev/null"
    try:
        result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=30, input=None)
        ls_output = result.stdout.strip()
        if not ls_output or result.returncode != 0:
            print(f"   ⚠️  No files found or connection failed")
            ls_output = "NO_FILES"
    except Exception as e:
        print(f"   ❌ SSH error: {e}")
        ls_output = "NO_FILES"
    
    if ls_output and ls_output != "NO_FILES":
        game_server_files = [
            Path(line).name for line in ls_output.split('\n') 
            if line.strip() and target_date in line
        ]
    
    print(f"   ✅ Found {len(game_server_files)} files on game server for {target_date}")
    
    # ========================================================================
    # SOURCE 2: Local Windows Machine
    # ========================================================================
    print("\n" + "=" * 80)
    print("💻 SOURCE 2: Local Windows Machine (local_stats/)")
    print("=" * 80)
    
    local_stats_dir = Path("local_stats")
    local_files = []
    
    if local_stats_dir.exists():
        local_files = [
            f.name for f in local_stats_dir.glob(f"{target_date}*.txt")
        ]
        print(f"   ✅ Found {len(local_files)} files locally")
    else:
        print(f"   ⚠️  Directory not found: {local_stats_dir}")
    
    # ========================================================================
    # SOURCE 3: VPS local_stats
    # ========================================================================
    print("\n" + "=" * 80)
    print("🖥️  SOURCE 3: VPS local_stats (192.168.64.116)")
    print("=" * 80)
    
    vps_files = []
    vps_host = "192.168.64.116"
    vps_user = "samba"
    vps_path = "/home/samba/share/slomix_discord/local_stats"
    
    print(f"   Connecting to {vps_user}@{vps_host}...")
    vps_ls_output = run_ssh_command(
        vps_host,
        vps_user,
        f"ls -1 {vps_path}/{target_date}*.txt 2>/dev/null || echo 'NO_FILES'"
    )
    
    if vps_ls_output and vps_ls_output != "NO_FILES":
        vps_files = [
            Path(line).name for line in vps_ls_output.split('\n')
            if line.strip() and target_date in line
        ]
    
    print(f"   ✅ Found {len(vps_files)} files on VPS")
    
    # ========================================================================
    # SOURCE 4: VPS PostgreSQL Database
    # ========================================================================
    print("\n" + "=" * 80)
    print("🗄️  SOURCE 4: VPS PostgreSQL Database")
    print("=" * 80)
    
    db_files = []
    db_rounds = []
    
    try:
        # Connect to VPS PostgreSQL
        pool = await asyncpg.create_pool(
            host=config.postgres_host.split(':')[0],
            port=int(config.postgres_host.split(':')[1]) if ':' in config.postgres_host else 5432,
            database=config.postgres_database,
            user=config.postgres_user,
            password=config.postgres_password,
            min_size=1,
            max_size=3
        )
        
        async with pool.acquire() as conn:
            # Check processed_files table
            processed = await conn.fetch(
                "SELECT filename FROM processed_files WHERE filename LIKE $1 AND success = true",
                f"{target_date}%"
            )
            db_files = [row['filename'] for row in processed]
            
            # Check rounds table
            rounds = await conn.fetch(
                """
                SELECT match_id, round_number, map_name, round_time
                FROM rounds
                WHERE round_date = $1
                ORDER BY round_time
                """,
                target_date
            )
            db_rounds = rounds
            
        await pool.close()
        
        print(f"   ✅ Found {len(db_files)} processed files in database")
        print(f"   ✅ Found {len(db_rounds)} rounds in database")
        
    except Exception as e:
        print(f"   ❌ Database error: {e}")
    
    # ========================================================================
    # COMPARISON ANALYSIS
    # ========================================================================
    print("\n" + "=" * 80)
    print("📊 COMPARISON RESULTS")
    print("=" * 80)
    
    # Convert to sets for comparison
    game_set = set(game_server_files)
    local_set = set(local_files)
    vps_set = set(vps_files)
    db_set = set(db_files)
    
    # Find the "truth" - the most complete source
    all_files = game_set | local_set | vps_set | db_set
    total_files = len(all_files)
    
    print(f"\n📈 Total unique files across all sources: {total_files}")
    print(f"\n   🎮 Game Server:    {len(game_set):3d} / {total_files} ({len(game_set)/total_files*100 if total_files else 0:5.1f}%)")
    print(f"   💻 Local Windows:  {len(local_set):3d} / {total_files} ({len(local_set)/total_files*100 if total_files else 0:5.1f}%)")
    print(f"   🖥️  VPS Files:      {len(vps_set):3d} / {total_files} ({len(vps_set)/total_files*100 if total_files else 0:5.1f}%)")
    print(f"   🗄️  VPS Database:   {len(db_set):3d} / {total_files} ({len(db_set)/total_files*100 if total_files else 0:5.1f}%)")
    
    # Find missing files per source
    print("\n" + "=" * 80)
    print("🔍 MISSING FILES BY SOURCE")
    print("=" * 80)
    
    missing_from_local = all_files - local_set
    missing_from_vps = all_files - vps_set
    missing_from_db = all_files - db_set
    
    if missing_from_local:
        print(f"\n⚠️  Missing from LOCAL Windows ({len(missing_from_local)} files):")
        for f in sorted(missing_from_local)[:5]:
            print(f"   - {f}")
        if len(missing_from_local) > 5:
            print(f"   ... and {len(missing_from_local) - 5} more")
    
    if missing_from_vps:
        print(f"\n⚠️  Missing from VPS local_stats ({len(missing_from_vps)} files):")
        for f in sorted(missing_from_vps)[:5]:
            print(f"   - {f}")
        if len(missing_from_vps) > 5:
            print(f"   ... and {len(missing_from_vps) - 5} more")
    
    if missing_from_db:
        print(f"\n⚠️  Missing from VPS DATABASE ({len(missing_from_db)} files):")
        for f in sorted(missing_from_db)[:5]:
            print(f"   - {f}")
        if len(missing_from_db) > 5:
            print(f"   ... and {len(missing_from_db) - 5} more")
    
    # ========================================================================
    # RECOMMENDATIONS
    # ========================================================================
    print("\n" + "=" * 80)
    print("💡 RECOMMENDATIONS")
    print("=" * 80)
    
    if len(db_set) == total_files:
        print("\n   ✅ PERFECT! All files are in the database.")
        print("   ✅ No sync needed!")
    elif len(missing_from_db) > 0:
        print(f"\n   ⚠️  Database is missing {len(missing_from_db)} files")
        print(f"   📥 Recommend: Use !sync_today command in Discord")
        print(f"   📥 Or: Run rebuild with option 2 (last 30 days)")
    
    if len(missing_from_vps) > 0:
        print(f"\n   ⚠️  VPS local_stats is missing {len(missing_from_vps)} files")
        print(f"   📥 Recommend: Bot will auto-download on next check")
    
    if len(missing_from_local) > 0:
        print(f"\n   ⚠️  Local Windows is missing {len(missing_from_local)} files")
        print(f"   📥 Recommend: scp from game server or VPS")
    
    # Summary table
    print("\n" + "=" * 80)
    print("📋 SYNC STATUS SUMMARY")
    print("=" * 80)
    print(f"\n   Date checked: {target_date}")
    print(f"   Total files found: {total_files}")
    print(f"\n   Game Server → VPS Files:    {'✅ SYNCED' if game_set == vps_set else f'❌ {len(game_set - vps_set)} missing'}")
    print(f"   VPS Files → VPS Database:   {'✅ SYNCED' if vps_set == db_set else f'❌ {len(vps_set - db_set)} missing'}")
    print(f"   Game Server → VPS Database: {'✅ SYNCED' if game_set == db_set else f'❌ {len(game_set - db_set)} missing'}")
    
    overall_health = (len(db_set) / len(game_set) * 100) if game_set else 100
    print(f"\n   Overall sync health: {overall_health:.1f}%")
    
    if overall_health >= 100:
        print("   Status: 🟢 EXCELLENT - Everything synced!")
    elif overall_health >= 90:
        print("   Status: 🟡 GOOD - Minor sync needed")
    else:
        print("   Status: 🔴 NEEDS ATTENTION - Run sync!")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    # Allow specifying date as argument
    import sys
    target_date = sys.argv[1] if len(sys.argv) > 1 else None
    
    asyncio.run(check_4way_sync(target_date))
