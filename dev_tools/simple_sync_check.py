#!/usr/bin/env python3
"""
Simple 3-way sync check - just list files and compare
"""
import os
import sys

print("=" * 80)
print("📋 SIMPLE FILE SYNC CHECK")
print("=" * 80)

target_date = sys.argv[1] if len(sys.argv) > 1 else "2025-11-06"
print(f"Checking date: {target_date}\n")

# Step 1: Game server files
print("=" * 80)
print("1️⃣  GAME SERVER (puran.hehe.si)")
print("=" * 80)
print("Run this command manually and paste the count:")
print(f'   ssh -p 48101 et@puran.hehe.si "ls -1 /home/et/.etlegacy/legacy/gamestats/{target_date}*.txt | wc -l"')
game_count = input("\nHow many files on game server? ")

# Step 2: VPS local_stats files  
print("\n" + "=" * 80)
print("2️⃣  VPS LOCAL_STATS (samba@192.168.64.116)")
print("=" * 80)
print("Run this command manually and paste the count:")
print(f'   ssh samba@192.168.64.116 "ls -1 /home/samba/share/slomix_discord/local_stats/{target_date}*.txt | wc -l"')
vps_count = input("\nHow many files on VPS? ")

# Step 3: VPS database
print("\n" + "=" * 80)
print("3️⃣  VPS DATABASE")
print("=" * 80)
print("Run this command manually and paste the count:")
print(f'   ssh samba@192.168.64.116 "psql -U etlegacy -d et_stats -t -c \\"SELECT COUNT(*) FROM processed_files WHERE filename LIKE \'{target_date}%\' AND success = true\\""')
db_count = input("\nHow many files in database? ")

# Compare
print("\n" + "=" * 80)
print("📊 RESULTS")
print("=" * 80)
try:
    game = int(game_count.strip())
    vps = int(vps_count.strip())
    db = int(db_count.strip())
    
    print(f"\n🎮 Game Server:  {game} files")
    print(f"🖥️  VPS Files:    {vps} files")
    print(f"🗄️  VPS Database: {db} files")
    
    print("\n" + "=" * 80)
    if game == vps == db:
        print("✅ PERFECT SYNC!")
    else:
        if game != vps:
            print(f"⚠️  Game → VPS: Missing {abs(game - vps)} files")
        if vps != db:
            print(f"⚠️  VPS Files → Database: Missing {abs(vps - db)} files")
        if game != db:
            print(f"⚠️  Game → Database: Missing {abs(game - db)} files")
    
except ValueError:
    print("❌ Invalid input")

print("=" * 80)
