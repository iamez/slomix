#!/usr/bin/env python3
"""
Comprehensive File Sync Diagnostic Tool
Checks discrepancies between server files, local files, and database records
"""
import os
import sqlite3
from collections import defaultdict
from pathlib import Path

# Paths
LOCAL_STATS_PATH = Path('./local_stats')
DB_PATH = Path('./etlegacy_production.db')

def count_desktop_files():
    """Ask user for desktop file count"""
    print("\n" + "="*70)
    print("📋 DESKTOP FILE COUNT")
    print("="*70)
    print("Please paste your copy result (files on server excluding _ws.txt):")
    print("Example: '3,245 files copied' or just the number")
    
    user_input = input("\nDesktop file count: ").strip()
    
    # Extract number from various formats
    import re
    numbers = re.findall(r'\d+', user_input.replace(',', ''))
    if numbers:
        return int(numbers[0])
    return 0

def check_local_files():
    """Check local_stats directory"""
    print("\n" + "="*70)
    print("📁 LOCAL FILES CHECK")
    print("="*70)
    
    if not LOCAL_STATS_PATH.exists():
        print("❌ local_stats directory does not exist!")
        return [], []
    
    all_files = list(LOCAL_STATS_PATH.glob('*.txt'))
    
    # Separate regular stats files from _ws.txt files
    stats_files = [f.name for f in all_files if not f.name.endswith('_ws.txt')]
    ws_files = [f.name for f in all_files if f.name.endswith('_ws.txt')]
    
    print(f"Total .txt files: {len(all_files)}")
    print(f"  • Stats files (excluding _ws.txt): {len(stats_files)}")
    print(f"  • Weapon stats files (_ws.txt): {len(ws_files)}")
    
    # Check for any unusual patterns
    print("\n📊 File pattern breakdown:")
    patterns = defaultdict(int)
    for f in stats_files:
        if '-round-1.txt' in f:
            patterns['round-1'] += 1
        elif '-round-2.txt' in f:
            patterns['round-2'] += 1
        else:
            patterns['other'] += 1
    
    for pattern, count in sorted(patterns.items()):
        print(f"  • {pattern}: {count} files")
    
    # Show date range
    if stats_files:
        stats_files_sorted = sorted(stats_files)
        print(f"\n📅 Date range:")
        print(f"  • Oldest: {stats_files_sorted[0][:10]}")
        print(f"  • Newest: {stats_files_sorted[-1][:10]}")
    
    return stats_files, ws_files

def check_database():
    """Check database records"""
    print("\n" + "="*70)
    print("🗄️ DATABASE CHECK")
    print("="*70)
    
    if not DB_PATH.exists():
        print("❌ Database does not exist!")
        return {}
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check sessions table
    cursor.execute("SELECT COUNT(*) FROM sessions")
    session_count = cursor.fetchone()[0]
    print(f"Sessions in database: {session_count}")
    
    # Check processed_files table
    cursor.execute("""
        SELECT COUNT(*) 
        FROM processed_files 
        WHERE success = 1
    """)
    processed_count = cursor.fetchone()[0]
    print(f"Processed files (success=1): {processed_count}")
    
    # Get all processed filenames
    cursor.execute("""
        SELECT filename, success, processed_at 
        FROM processed_files 
        ORDER BY filename
    """)
    processed_files = cursor.fetchall()
    
    # Get session details with date range
    cursor.execute("""
        SELECT 
            MIN(session_date) as earliest,
            MAX(session_date) as latest,
            COUNT(DISTINCT session_date) as unique_dates
        FROM sessions
    """)
    date_info = cursor.fetchone()
    if date_info[0]:
        print(f"\n📅 Session date range:")
        print(f"  • Earliest: {date_info[0]}")
        print(f"  • Latest: {date_info[1]}")
        print(f"  • Unique dates: {date_info[2]}")
    
    # Check for round distribution
    cursor.execute("""
        SELECT round_number, COUNT(*) 
        FROM sessions 
        GROUP BY round_number
        ORDER BY round_number
    """)
    rounds = cursor.fetchall()
    print(f"\n📊 Sessions by round:")
    for round_num, count in rounds:
        print(f"  • Round {round_num}: {count} sessions")
    
    conn.close()
    
    return {f[0]: f[1] for f in processed_files}

def check_in_memory_cache():
    """Info about in-memory cache"""
    print("\n" + "="*70)
    print("💾 IN-MEMORY CACHE")
    print("="*70)
    print("The bot maintains a self.processed_files set in memory.")
    print("This is populated from:")
    print("  1. processed_files table on startup")
    print("  2. local_stats/ directory scan on startup")
    print("  3. Files processed during current run")
    print("\nNote: Cache is cleared on bot restart!")

def analyze_discrepancy(desktop_count, local_files, processed_dict):
    """Analyze the discrepancy"""
    print("\n" + "="*70)
    print("🔍 DISCREPANCY ANALYSIS")
    print("="*70)
    
    local_count = len(local_files)
    processed_count = sum(1 for success in processed_dict.values() if success == 1)
    
    print(f"Files on server (your desktop copy): {desktop_count}")
    print(f"Files in local_stats/ directory:     {local_count}")
    print(f"Files in processed_files table:      {processed_count}")
    print()
    
    # Calculate differences
    server_vs_local = desktop_count - local_count
    server_vs_processed = desktop_count - processed_count
    local_vs_processed = local_count - processed_count
    
    print("Differences:")
    print(f"  • Server has {abs(server_vs_local)} {'more' if server_vs_local > 0 else 'fewer'} files than local_stats/")
    print(f"  • Server has {abs(server_vs_processed)} {'more' if server_vs_processed > 0 else 'fewer'} files than processed_files table")
    print(f"  • local_stats/ has {abs(local_vs_processed)} {'more' if local_vs_processed > 0 else 'fewer'} files than processed_files table")
    
    # Check if files in processed_files exist locally
    print("\n🔍 Checking processed_files consistency...")
    missing_from_disk = []
    for filename, success in processed_dict.items():
        if success == 1:  # Only check successful ones
            if filename not in local_files:
                missing_from_disk.append(filename)
    
    if missing_from_disk:
        print(f"\n⚠️  Found {len(missing_from_disk)} files in processed_files but NOT in local_stats/:")
        for f in missing_from_disk[:10]:
            print(f"     • {f}")
        if len(missing_from_disk) > 10:
            print(f"     ... and {len(missing_from_disk) - 10} more")
    else:
        print("✅ All files in processed_files exist in local_stats/")
    
    # Check if local files are in processed_files
    print("\n🔍 Checking local files consistency...")
    not_in_processed = []
    for filename in local_files:
        if filename not in processed_dict:
            not_in_processed.append(filename)
    
    if not_in_processed:
        print(f"\n⚠️  Found {len(not_in_processed)} files in local_stats/ but NOT in processed_files:")
        for f in not_in_processed[:10]:
            print(f"     • {f}")
        if len(not_in_processed) > 10:
            print(f"     ... and {len(not_in_processed) - 10} more")
    else:
        print("✅ All local files are tracked in processed_files")

def check_hybrid_system():
    """Check the 4-layer hybrid system"""
    print("\n" + "="*70)
    print("🔄 HYBRID SYSTEM CHECK")
    print("="*70)
    print("\nThe bot uses a 4-layer check to avoid re-processing files:")
    print()
    print("Layer 1: In-Memory Cache (self.processed_files set)")
    print("  • Populated from processed_files table on startup")
    print("  • Populated from local_stats/ scan on startup")
    print("  • Added during runtime processing")
    print()
    print("Layer 2: Local File Check (os.path.exists)")
    print("  • Checks if file exists in local_stats/ directory")
    print()
    print("Layer 3: processed_files Table")
    print("  • Database table tracking all processed files")
    print("  • Records success/failure status")
    print()
    print("Layer 4: sessions Table")
    print("  • Checks if session with same timestamp/map/round exists")
    print("  • Most definitive check")

def recommendations(desktop_count, local_count):
    """Provide recommendations"""
    print("\n" + "="*70)
    print("💡 RECOMMENDATIONS")
    print("="*70)
    
    if desktop_count > local_count:
        diff = desktop_count - local_count
        print(f"\n⚠️  Server has {diff} MORE files than local_stats/")
        print("\nPossible causes:")
        print("  1. Files were deleted from local_stats/ but still exist on server")
        print("  2. Bot hasn't synced recently")
        print("  3. SSH sync was interrupted")
        print("  4. File filter mismatch (e.g., _ws.txt handling)")
        print("\nSuggested actions:")
        print("  ✅ Run: python tools/sync_stats.py")
        print("  ✅ This will download the missing files")
        print("  ✅ Bot will auto-import them on next run")
    elif local_count > desktop_count:
        diff = local_count - desktop_count
        print(f"\n⚠️  local_stats/ has {diff} MORE files than server")
        print("\nPossible causes:")
        print("  1. Files were deleted from server but not locally")
        print("  2. Your desktop copy is incomplete")
        print("  3. Server was cleaned up/rotated logs")
        print("\nThis is usually OK - local files are already imported.")
    else:
        print("\n✅ File counts match! Everything looks good.")
        print("\nNext steps:")
        print("  • Check that processed_files table is up to date")
        print("  • Verify bot startup sync works correctly")
        print("  • Monitor SSH monitoring for new files")

def main():
    """Main diagnostic function"""
    print("="*70)
    print("🔍 FILE SYNC DIAGNOSTIC TOOL")
    print("="*70)
    print("\nThis tool helps diagnose discrepancies between:")
    print("  • Files on the game server")
    print("  • Files in local_stats/ directory")
    print("  • Records in processed_files table")
    print("  • Sessions in the database")
    
    # Get desktop count from user
    desktop_count = count_desktop_files()
    
    if desktop_count == 0:
        print("\n❌ Invalid file count. Please run again and provide the number.")
        return 1
    
    print(f"\n✅ Server file count: {desktop_count}")
    
    # Check local files
    local_files, ws_files = check_local_files()
    
    # Check database
    processed_dict = check_database()
    
    # Check in-memory cache info
    check_in_memory_cache()
    
    # Analyze discrepancy
    analyze_discrepancy(desktop_count, local_files, processed_dict)
    
    # Hybrid system check
    check_hybrid_system()
    
    # Recommendations
    recommendations(desktop_count, len(local_files))
    
    print("\n" + "="*70)
    print("✅ DIAGNOSTIC COMPLETE")
    print("="*70)
    
    return 0

if __name__ == '__main__':
    exit(main())
